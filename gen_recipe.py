import requests
import math
import sys

# --- 配置区 ---
TARGET_DOMAIN = "https://jidujiaojiaoyu.org/"
RECIPE_FILENAME = "site.recipe"
MAX_PAGES_LIMIT = 50 

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

    # 1. 识别父节点
    parent_ids = set(c['parent'] for c in categories.values() if c['parent'] != 0)
    
    # 2. 构建数据
    cat_data_list = []
    name_memo = {}
    
    for cat_id, cat in categories.items():
        if cat_id in parent_ids or cat['count'] == 0:
            continue 
        full_name = get_full_path_name(cat_id, categories, name_memo)
        base_feed_url = cat['link'].rstrip('/') + '/feed/'
        cat_data_list.append({
            'name': full_name,
            'url': base_feed_url,
            'count': cat['count']
        })

    cat_data_list.sort(key=lambda x: x['name'])
    
    # 3. 生成 Recipe
    # 关键修复：同时引入 Feed 和 Article 类
    recipe_code = f"""import feedparser
import math
import time
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.web.feeds import Feed, Article  # <--- 关键修复：导入 Article

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

    MY_CATEGORIES = {cat_data_list}
    RSS_PAGE_SIZE = 10
    MAX_PAGES = {MAX_PAGES_LIMIT}

    def parse_feeds(self):
        master_feeds_list = []
        
        for cat in self.MY_CATEGORIES:
            category_name = cat['name']
            base_url = cat['url']
            total_count = cat['count']
            
            # 计算页数
            pages_needed = math.ceil(total_count / self.RSS_PAGE_SIZE)
            pages_to_fetch = min(pages_needed, self.MAX_PAGES)
            if pages_to_fetch < 1: pages_to_fetch = 1
            
            print(f"正在处理分类: {{category_name}} (共 {{total_count}} 篇, 需抓取 {{pages_to_fetch}} 页)")
            
            all_articles = []
            
            # 循环抓取
            for p in range(1, pages_to_fetch + 1):
                feed_url = base_url if p == 1 else f"{{base_url}}?paged={{p}}"
                try:
                    f = feedparser.parse(feed_url)
                    if not f.entries: break
                        
                    for entry in f.entries:
                        title = entry.get('title', 'Untitled')
                        url   = entry.get('link', '')
                        desc  = entry.get('description', '')
                        date  = entry.get('published_parsed', None)
                        
                        if not url: continue
                        
                        all_articles.append({{
                            'title': title,
                            'url': url,
                            'description': desc,
                            'date': date,
                            'date_str': entry.get('published', '')
                        }})
                except Exception as e:
                    print(f"  -> 抓取失败: {{e}}")
            
            # 排序：从旧到新
            all_articles.sort(key=lambda x: x['date'] if x['date'] else time.localtime(0))
            
            # --- 关键修复区 ---
            final_articles = []
            for a in all_articles:
                # 必须实例化 Article 对象，不能使用字典
                # Article(title, url, description, date, content)
                art = Article(
                    a['title'],
                    a['url'],
                    a['description'],
                    a['date_str'],
                    None  # content 留空，让 Calibre 自动去抓
                )
                final_articles.append(art)
            
            if final_articles:
                feed_obj = Feed()
                feed_obj.title = category_name
                feed_obj.articles = final_articles
                master_feeds_list.append(feed_obj)
                
                print(f"  -> {{category_name}} 完成: 合并了 {{len(final_articles)}} 篇文章")
        
        return master_feeds_list
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(recipe_code)
    print(f"成功生成修复版 Recipe: {filename}")

if __name__ == "__main__":
    generate_smart_recipe(TARGET_DOMAIN, RECIPE_FILENAME)
