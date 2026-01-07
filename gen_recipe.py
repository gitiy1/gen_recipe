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
    recipe_code = f"""import feedparser
import math
import time
from calibre.web.feeds.news import BasicNewsRecipe

# --- 自定义 Article 类 ---
class MyArticle:
    def __init__(self, title, url, description, author, published, content):
        self.title = title
        self.url = url
        self.description = description
        self.summary = description 
        self.author = author
        self.published = published
        self.content = content
        self.text = content
        self.id = None
        self.date = None

# --- 自定义 Feed 类 (关键修复: 增加列表行为) ---
class MyFeed:
    def __init__(self, title, articles):
        self.title = title
        self.articles = articles
        self.image_url = None 
        self.description = None
        self.id = None

    # 让对象支持 len(feed)
    def __len__(self):
        return len(self.articles)

    # 让对象支持 for article in feed
    def __iter__(self):
        return iter(self.articles)

    # 让对象支持 feed[0]
    def __getitem__(self, index):
        return self.articles[index]

class JidujiaoChronological(BasicNewsRecipe):
    title          = '基督教教育网 (全站编年史版)'
    description    = '已合并分页目录，并按时间【从旧到新】排序。'
    language       = 'zh'
    encoding       = 'utf-8'
    oldest_article = 36500
    max_articles_per_feed = 1000
    auto_cleanup   = True
    timeout        = 60
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
            
            pages_needed = math.ceil(total_count / self.RSS_PAGE_SIZE)
            pages_to_fetch = min(pages_needed, self.MAX_PAGES)
            if pages_to_fetch < 1: pages_to_fetch = 1
            
            print(f"正在处理分类: {{category_name}} (共 {{total_count}} 篇, 需抓取 {{pages_to_fetch}} 页)")
            
            all_articles = []
            
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
                        date_str = entry.get('published', '')
                        
                        if not url: continue
                        
                        all_articles.append({{
                            'title': title,
                            'url': url,
                            'description': desc,
                            'author': 'Unknown',
                            'date': date,
                            'date_str': date_str,
                            'content': ''
                        }})
                except Exception as e:
                    print(f"  -> 抓取失败: {{e}}")
            
            # 排序：从旧到新
            all_articles.sort(key=lambda x: x['date'] if x['date'] else time.localtime(0))
            
            final_articles = []
            for a in all_articles:
                art = MyArticle(
                    a['title'],
                    a['url'],
                    a['description'],
                    a['author'],
                    a['date_str'],
                    a['content']
                )
                final_articles.append(art)
            
            if final_articles:
                # 使用自定义的 MyFeed 类
                feed_obj = MyFeed(category_name, final_articles)
                master_feeds_list.append(feed_obj)
                
                print(f"  -> {{category_name}} 完成: 合并了 {{len(final_articles)}} 篇文章")
        
        return master_feeds_list
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(recipe_code)
    print(f"成功生成无敌版 Recipe: {filename}")

if __name__ == "__main__":
    generate_smart_recipe(TARGET_DOMAIN, RECIPE_FILENAME)
