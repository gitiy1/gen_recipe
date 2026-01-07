import requests
import feedparser
import math
import sys

# --- 配置区 ---
TARGET_DOMAIN = "https://jidujiaojiaoyu.org/"
RECIPE_FILENAME = "Jidujiao_Verified.recipe"
# 为了防止分类下有几千篇文章导致 Calibre 抓取卡死，可以设置每个分类最大抓取页数
# 如果你想全量抓取，可以把这个数字设得很大 (比如 100)
MAX_PAGES_LIMIT = 50 

def get_all_categories(domain):
    """通过 API 获取所有分类信息（含文章数 count）"""
    categories = {} 
    base_url = domain.rstrip('/')
    api_url = f"{base_url}/wp-json/wp/v2/categories"
    page = 1
    
    print(f"1. 正在通过 API 获取站点分类结构...")
    while True:
        try:
            params = {'per_page': 100, 'page': page}
            response = requests.get(api_url, params=params, timeout=10)
            if response.status_code != 200: break
            data = response.json()
            if not data: break
            
            for cat in data:
                categories[cat['id']] = {
                    'id': cat['id'],
                    'name': cat['name'],
                    'parent': cat['parent'],
                    'link': cat['link'],
                    'count': cat['count']
                }
            if len(data) < 100: break
            page += 1
        except Exception as e:
            print(f"   API 请求警告: {e}")
            break
    print(f"   -> 共获取到 {len(categories)} 个分类信息")
    return categories

def detect_real_rss_page_size(categories):
    """
    挑选一个文章数较多的分类，实地下载 RSS，检测每页到底包含多少篇文章
    """
    print(f"2. 正在探测真实的 RSS 分页大小...")
    
    # 找一个文章数量大于 10 的分类来测试
    # 按文章数量倒序排，找文章最多的那个测试最准
    sorted_cats = sorted(categories.values(), key=lambda x: x['count'], reverse=True)
    
    test_cat = None
    for cat in sorted_cats:
        if cat['count'] > 10:
            test_cat = cat
            break
    
    if not test_cat:
        print("   -> 警告：所有分类文章数都很少，无法精确探测，默认使用 10 篇/页")
        return 10

    print(f"   -> 选取分类 [{test_cat['name']}] (共 {test_cat['count']} 篇) 作为探测样本")
    feed_url = test_cat['link'].rstrip('/') + '/feed/'
    
    try:
        # 解析 RSS
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            print("   -> 探测失败：Feed 为空，回退到默认 10 篇")
            return 10
            
        real_count = len(feed.entries)
        print(f"   -> 探测成功！RSS 第一页实际包含 {real_count} 篇文章")
        return real_count
        
    except Exception as e:
        print(f"   -> 探测出错 ({e})，回退到默认 10 篇")
        return 10

def get_full_path_name(cat_id, categories, memo):
    """递归构建路径名称"""
    if cat_id not in categories: return ""
    if cat_id in memo: return memo[cat_id]
    
    cat = categories[cat_id]
    parent_id = cat['parent']
    
    if parent_id == 0 or parent_id not in categories:
        full_name = cat['name']
    else:
        parent_name = get_full_path_name(parent_id, categories, memo)
        full_name = f"{parent_name} > {cat['name']}"
        
    memo[cat_id] = full_name
    return full_name

def generate_verified_recipe(domain, filename):
    # 1. 获取分类
    categories = get_all_categories(domain)
    if not categories: return

    # 2. 探测 RSS 实际容量
    rss_page_size = detect_real_rss_page_size(categories)
    
    # 3. 识别父节点（用于去重）
    parent_ids = set()
    for cat in categories.values():
        if cat['parent'] != 0:
            parent_ids.add(cat['parent'])
            
    # 4. 生成 Feed 列表
    print(f"3. 正在计算每个分类的分页策略 (基于每页 {rss_page_size} 篇)...")
    
    feeds_entries = []
    name_memo = {}
    total_feeds_count = 0
    skipped_parents = 0
    
    for cat_id, cat in categories.items():
        # 跳过父节点和空分类
        if cat_id in parent_ids:
            skipped_parents += 1
            continue
        if cat['count'] == 0:
            continue
            
        full_name = get_full_path_name(cat_id, categories, name_memo)
        base_feed_url = cat['link'].rstrip('/') + '/feed/'
        
        # 计算页数
        # 比如 count=53, size=10 -> 5.3 -> 6页
        pages_needed = math.ceil(cat['count'] / rss_page_size)
        
        # 限制最大页数
        pages_to_fetch = min(pages_needed, MAX_PAGES_LIMIT)
        
        # 生成每一页的链接
        for p in range(1, pages_to_fetch + 1):
            if p == 1:
                url = base_feed_url
            else:
                url = f"{base_feed_url}?paged={p}"
            
            feeds_entries.append((full_name, url))
            total_feeds_count += 1

    # 排序
    feeds_entries.sort(key=lambda x: x[0])
    
    # 5. 生成 Recipe 代码
    recipe_code = f"""from calibre.web.feeds.news import BasicNewsRecipe

class JidujiaoVerifiedRecipe(BasicNewsRecipe):
    title          = '基督教教育网 (全站 - 智能分页版)'
    description    = '自动探测 RSS 页容量为 {rss_page_size} 篇/页，已去重父级分类。'
    
    oldest_article = 36500
    max_articles_per_feed = 1000
    auto_cleanup   = True
    language       = 'zh'
    encoding       = 'utf-8'
    timeout        = 60
    simultaneous_downloads = 5

    feeds = [
"""
    for name, url in feeds_entries:
        recipe_code += f"        (u'{name}', u'{url}'),\n"
    recipe_code += "    ]\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(recipe_code)
        
    print(f"\n{'='*40}")
    print(f"生成报告:")
    print(f"1. 探测到的 RSS 页容量: {rss_page_size} 篇")
    print(f"2. 排除父级分类数量: {skipped_parents} 个")
    print(f"3. 生成抓取链接总数: {total_feeds_count} 个 (含分页)")
    print(f"4. 配方文件: {filename}")
    print(f"{'='*40}")
    print("现在可以在 Calibre 中加载此配方了。")

# gen_recipe.py 的最后部分
if __name__ == "__main__":
    # 强制指定输出文件名为 site.recipe，方便 Action 调用
    generate_verified_recipe("https://jidujiaojiaoyu.org/", "site.recipe")
