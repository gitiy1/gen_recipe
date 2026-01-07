import requests
import math
import sys
import datetime

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

    parent_ids = set(c['parent'] for c in categories.values() if c['parent'] != 0)
    
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
    
    # 将复杂的配置注入到字符串中
    recipe_code = f"""import feedparser
import math
import time
from calibre.web.feeds.news import BasicNewsRecipe

class MyArticle:
    def __init__(self, title, url, description, author, published, content):
        self.title = title
        self.url = url
        self.description = description
        self.summary = description 
        self.text_summary = description
        self.author = author
        self.author_sort = author
        self.published = published
        self.formatted_date = published if published else 'Unknown Date'
        self.content = content
        self.text = content
        self.toc_thumbnail = None
        self.id = None
        self.date = None
        self.utctime = None
        self.downloaded = True
        self.orig_url = url
        self.internal_toc_entries = []

class MyFeed:
    def __init__(self, title, articles):
        self.title = title
        self.articles = articles
        self.image_url = None 
        self.description = None
        self.id = None

    def __len__(self): return len(self.articles)
    def __iter__(self): return iter(self.articles)
    def __getitem__(self, index): return self.articles[index]
    def has_embedded_content(self): return False
    def is_empty(self): return len(self.articles) == 0

class JidujiaoPro(BasicNewsRecipe):
    title          = '基督教教育网'
    description    = '仅保留标题、描述、分类、标签和正文。'
    language       = 'zh'
    encoding       = 'utf-8'
    oldest_article = 36500
    max_articles_per_feed = 1000
    
    # --- 1. 关闭自动清理 (我们要手动手术) ---
    auto_cleanup = False

    # --- 2. 墨水屏优化 ---
    no_stylesheets = True
    remove_javascript = True
    compress_news_images = True
    scale_news_images = (800, 1000)
    remove_attributes = ['style', 'width', 'height', 'align']

    # --- 3. DOM 级精准保留 (白名单) ---
    # Calibre 会丢弃除此之外的所有 HTML
    keep_only_tags = [
        # 兼容常见的 H1 标题写法，以及用户指定的 page-title
        dict(name='h1'), 
        dict(attrs={{'class': lambda x: x and 'page-title' in x}}),
        
        # 页面描述
        dict(attrs={{'class': lambda x: x and 'page-description' in x}}),
        
        # 分类信息
        dict(attrs={{'class': lambda x: x and 'meta-categories' in x}}),
        
        # 标签
        dict(attrs={{'class': lambda x: x and 'entry-tags' in x}}),
        
        # 正文核心
        dict(attrs={{'class': lambda x: x and 'entry-content' in x}}),
    ]

    # --- 4. DOM 级精准剔除 (黑名单) ---
    # 这些元素即使在上面的保留区域内，也会被强制挖掉
    remove_tags = [
        # 移除文章内的目录插件块
        dict(attrs={{'class': lambda x: x and 'wp-block-uagb-table-of-contents' in x}}),
        
        # 移除特定的无用图片 (wp-image-5896)
        dict(attrs={{'class': lambda x: x and 'wp-image-5896' in x}}),
        
        # 额外移除常见的干扰元素，以防万一
        dict(name=['script', 'style', 'noscript', 'iframe', 'nav', 'footer']),
        dict(attrs={{'class': ['sharedaddy', 'related-posts', 'post-navigation']}})
    ]

    timeout = 120
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
                            'title': title, 'url': url, 'description': desc,
                            'author': 'Unknown', 'date': date, 'date_str': date_str, 'content': '' 
                        }})
                except Exception as e:
                    print(f"  -> 抓取失败: {{e}}")
            
            all_articles.sort(key=lambda x: x['date'] if x['date'] else time.localtime(0))
            
            final_articles = []
            for a in all_articles:
                art = MyArticle(a['title'], a['url'], a['description'], a['author'], a['date_str'], a['content'])
                final_articles.append(art)
            
            if final_articles:
                master_feeds_list.append(MyFeed(category_name, final_articles))
                print(f"  -> {{category_name}} 完成")
        
        return master_feeds_list
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(recipe_code)
    print(f"成功生成 DOM 定制版 Recipe: {filename}")

if __name__ == "__main__":
    generate_smart_recipe(TARGET_DOMAIN, RECIPE_FILENAME)
