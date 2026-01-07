import requests
import math
import sys

# --- 配置区 ---
TARGET_DOMAIN = "https://jidujiaojiaoyu.org/"
RECIPE_FILENAME = "site.recipe"
RSS_PAGE_SIZE_GUESS = 10  # 默认假设，脚本会自动探测
MAX_PAGES_LIMIT = 50      # 单个分类最大抓取页数

def get_all_categories(domain):
    """API 获取分类信息"""
    categories = {} 
    base_url = domain.rstrip('/')
    api_url = f"{base_url}/wp-json/wp/v2/categories"
    page = 1
    
    print(f"1. 分析站点结构...", file=sys.stderr)
    while True:
        try:
            params = {'per_page': 100, 'page': page}
            response = requests.get(api_url, params=params, timeout=10)
            if response.status_code != 200: break
            data = response.json()
            if not data: break
            for cat in data:
                categories[cat['id']] = {
                    'id': cat['id'], 'name': cat['name'], 
                    'parent': cat['parent'], 'link': cat['link'], 
                    'count': cat['count']
                }
            if len(data) < 100: break
            page += 1
        except: break
    return categories

def get_full_path_name(cat_id, categories, memo):
    """递归构建层级名称"""
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

def generate_smart_recipe(domain, filename):
    categories = get_all_categories(domain)
    if not categories: return

    # 1. 识别父节点（去重）
    parent_ids = set(c['parent'] for c in categories.values() if c['parent'] != 0)
    
    # 2. 构建注入到 Recipe 的数据结构
    # 我们不再直接生成 feeds 列表，而是生成一个 category_map
    # 结构: [ {'name': '世界观 > 历史', 'url': '...', 'count': 53}, ... ]
    
    cat_data_list = []
    name_memo = {}
    
    for cat_id, cat in categories.items():
        if cat_id in parent_ids or cat['count'] == 0:
            continue # 跳过父级和空分类
            
        full_name = get_full_path_name(cat_id, categories, name_memo)
        base_feed_url = cat['link'].rstrip('/') + '/feed/'
        
        cat_data_list.append({
            'name': full_name,
            'url': base_feed_url,
            'count': cat['count']
        })

    # 按名称排序
    cat_data_list.sort(key=lambda x: x['name'])
    
    # 3. 生成 Recipe 内容
    # 注意：这里我们注入了复杂的逻辑代码到 Recipe 类中
    
    recipe_code = f"""import feedparser
import math
import time
from calibre.web.feeds.news import BasicNewsRecipe

class JidujiaoChronological(BasicNewsRecipe):
    title          = '基督教教育网 (全站编年史版)'
    description    = '已合并分页目录，并按时间【从旧到新】排序。'
    language       = 'zh'
    encoding       = 'utf-8'
    oldest_article = 36500
    max_articles_per_feed = 1000
    auto_cleanup   = True
    timeout        = 30
    simultaneous_downloads = 5

    # 注入的分类数据
    MY_CATEGORIES = {cat_data_list}
    
    # 全局配置
    RSS_PAGE_SIZE = 10
    MAX_PAGES = {MAX_PAGES_LIMIT}

    def parse_feeds(self):
        # 覆写 Calibre 默认的 Feed 解析逻辑
        # 我们自己手动下载所有分页，合并，然后排序
        
        master_feeds_list = []
        
        for cat in self.MY_CATEGORIES:
            category_name = cat['name']
            base_url = cat['url']
            total_count = cat['count']
            
            # 计算需要抓取多少页
            pages_needed = math.ceil(total_count / self.RSS_PAGE_SIZE)
            pages_to_fetch = min(pages_needed, self.MAX_PAGES)
            if pages_to_fetch < 1: pages_to_fetch = 1
            
            print(f"正在处理分类: {{category_name}} (共 {{total_count}} 篇, 需抓取 {{pages_to_fetch}} 页)")
            
            all_articles = []
            
            # --- 循环抓取所有分页 ---
            for p in range(1, pages_to_fetch + 1):
                if p == 1:
                    feed_url = base_url
                else:
                    feed_url = f"{{base_url}}?paged={{p}}"
                
                try:
                    # 使用 Calibre 内置或环境中的 feedparser
                    # 注意：为了让 Calibre 的缓存生效，理论上应该用 self.index_to_soup
                    # 但 RSS 解析用 feedparser 更稳
                    f = feedparser.parse(feed_url)
                    
                    if not f.entries:
                        print(f"  -> 第 {{p}} 页为空，跳过")
                        break
                        
                    for entry in f.entries:
                        # 提取必要信息构建 Article 对象
                        title = entry.get('title', 'Untitled')
                        url   = entry.get('link', '')
                        desc  = entry.get('description', '')
                        date  = entry.get('published_parsed', None) # struct_time
                        
                        if not url: continue
                        
                        all_articles.append({{
                            'title': title,
                            'url': url,
                            'description': desc,
                            'date': date, # 用于排序
                            'date_str': entry.get('published', '') # 用于显示
                        }})
                        
                except Exception as e:
                    print(f"  -> 抓取 {{feed_url}} 失败: {{e}}")
            
            # --- 关键步骤：按时间正序排序 (从旧到新) ---
            # published_parsed 是一个 time.struct_time 元组，可以直接比较
            # 如果日期获取失败，放到最后
            all_articles.sort(key=lambda x: x['date'] if x['date'] else time.localtime(0))
            
            # 移除 'date' 字段 (Calibre 不需要它) 并转换格式
            final_articles = []
            for a in all_articles:
                final_articles.append({{
                    'title': a['title'],
                    'url':   a['url'],
                    'description': a['description'],
                    'date':  a['date_str']
                }})
            
            if final_articles:
                # 将合并后的列表作为一个 Feed 添加
                master_feeds_list.append((category_name, final_articles))
                print(f"  -> {{category_name}} 完成: 合并了 {{len(final_articles)}} 篇文章")
        
        return master_feeds_list

"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(recipe_code)
    print(f"成功生成高级 Recipe: {filename}")

if __name__ == "__main__":
    generate_smart_recipe(TARGET_DOMAIN, RECIPE_FILENAME)
