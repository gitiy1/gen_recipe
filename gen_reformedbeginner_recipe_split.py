import requests
import math
import sys
import re
import os

# --- 配置区 ---
TARGET_DOMAIN = "https://www.reformedbeginner.net/"
MAX_PAGES_LIMIT = 50 
RSS_PAGE_SIZE = 10

# --- 新增：排除列表 ---
# 在这里填写你想排除的分类名称（全名或包含的关键词）
# 比如填写 "类别检索 > 多媒体"，脚本遇到这个分类就会跳过
EXCLUDED_CATEGORIES = [
    "类别检索 > 多媒体",
    "类别检索 > 合集系列",
    "未分类",
]

def sanitize_filename(name):
    """清理文件名，防止非法字符"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(' ', '_')

def get_all_categories(domain):
    """API 获取分类信息"""
    categories = {} 
    base_url = domain.rstrip('/')
    api_url = f"{base_url}/wp-json/wp/v2/categories"
    page = 1
    
    print(f"1. 正在分析全站分类结构...", file=sys.stderr)
    while True:
        try:
            params = {'per_page': 100, 'page': page}
            response = requests.get(api_url, params=params, timeout=300) # API 请求超时
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
        except Exception as e:
            print(f"API 获取警告: {e}", file=sys.stderr)
            break
    return categories

def get_root_id(cat_id, categories):
    """递归查找某分类的顶级父节点 ID"""
    if cat_id not in categories: return None
    parent_id = categories[cat_id]['parent']
    if parent_id == 0:
        return cat_id
    if parent_id not in categories: return cat_id 
    return get_root_id(parent_id, categories)

def get_full_path_name(cat_id, categories, memo):
    """构建面包屑名称"""
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

def generate_split_recipes(domain):
    categories = get_all_categories(domain)
    if not categories: return

    # 1. 将所有子分类归类到 Root ID
    groups = {}
    
    # 先找出所有 Root 节点的名字，用于生成书名
    root_names = {cid: c['name'] for cid, c in categories.items() if c['parent'] == 0}
    
    name_memo = {}
    
    for cat_id, cat in categories.items():
        if cat['count'] == 0: continue # 跳过空分类
        
        # 找到它的根
        root_id = get_root_id(cat_id, categories)
        if root_id is None: continue
        
        if root_id not in groups:
            groups[root_id] = []
            
        # 构建分类全名 (例如: 类别检索 > 多媒体)
        full_name = get_full_path_name(cat_id, categories, name_memo)
        
        # --- 新增：排除逻辑 ---
        should_skip = False
        for excluded in EXCLUDED_CATEGORIES:
            # 如果全名中包含排除列表里的词，则跳过
            if excluded in full_name:
                print(f"  [排除] 跳过分类: {full_name} (匹配规则: {excluded})", file=sys.stderr)
                should_skip = True
                break
        
        if should_skip:
            continue
        # ------------------
        
        base_feed_url = cat['link'].rstrip('/') + '/feed/'
        
        groups[root_id].append({
            'name': full_name,
            'url': base_feed_url,
            'count': cat['count']
        })

    print(f"2. 识别到 {len(groups)} 个顶级系列 (已过滤排除项)，准备生成分册...", file=sys.stderr)

    # 2. 循环生成多个 Recipe 文件
    generated_files = []
    
    for root_id, feed_list in groups.items():
        # 如果过滤后该系列为空，则跳过
        if not feed_list:
            continue
            
        # 获取系列名称 (如 "世界观", "系统神学")
        series_name = root_names.get(root_id, "其他合集")
        
        # 按名称排序
        feed_list.sort(key=lambda x: x['name'])
        
        # 生成安全的文件名
        safe_name = sanitize_filename(series_name)
        recipe_filename = f"改革宗初学者_{safe_name}.recipe"
        
        # 书名
        book_title = f"改革宗初学者：{series_name}"
        
        print(f"  -> 生成分册: {book_title} (包含 {len(feed_list)} 个子分类)", file=sys.stderr)

        # 注入代码
        recipe_code = f"""import feedparser
import math
import time
from calibre.web.feeds.news import BasicNewsRecipe

# --- 自定义类 ---
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
        self.sub_pages = [] 
        self.mime_type = None

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

class JidujiaoSplit(BasicNewsRecipe):
    title          = '{book_title}'
    description    = '在认信的土壤上栽种信仰'
    language       = 'zh'
    encoding       = 'utf-8'
    oldest_article = 36500
    max_articles_per_feed = 1000
    
    # --- 墨水屏优化 ---
    auto_cleanup = False
    no_stylesheets = True
    remove_javascript = True
    compress_news_images = True
    scale_news_images = (800, 1000)
    remove_attributes = ['style', 'width', 'height', 'align']

    # --- 网络稳定性优化 ---
    # 针对不稳定的服务器，降低并发是非常有效的手段
    timeout = 3000
    simultaneous_downloads = 1  # 建议改为 1 以获得最高稳定性
    delay = 1 # 每次下载间隔 1 秒

    # 白名单：只留这 4 个部分
    keep_only_tags = [
        dict(name='h1'), 
        dict(attrs={{'class': lambda x: x and 'entry-header' in x}}),
        dict(attrs={{'class': lambda x: x and 'entry-content' in x}}),
        dict(attrs={{'class': lambda x: x and 'attachment-post-thumbnail' in x}}),
    ]

    # 黑名单：移除目录插件和特定图片
    remove_tags = [
        dict(name=['script', 'style', 'noscript', 'iframe', 'nav', 'footer']),
        dict(attrs={{'class': ['sd-sharing-enabled', 'sharedaddy', 'jp-relatedposts', 'post-navigation', 'related-posts']}})
    ]

    MY_CATEGORIES = {feed_list}
    RSS_PAGE_SIZE = {RSS_PAGE_SIZE}
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
            
            print(f"正在处理: {{category_name}} ({{pages_to_fetch}} 页)")
            
            all_articles = []
            for p in range(1, pages_to_fetch + 1):
                feed_url = base_url if p == 1 else f"{{base_url}}?paged={{p}}"
                try:
                    # 增加 feedparser 的超时处理
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
                    print(f"  -> RSS 抓取失败: {{e}}")
            
            all_articles.sort(key=lambda x: x['date'] if x['date'] else time.localtime(0))
            
            final_articles = []
            for a in all_articles:
                art = MyArticle(a['title'], a['url'], a['description'], a['author'], a['date_str'], a['content'])
                final_articles.append(art)
            
            if final_articles:
                master_feeds_list.append(MyFeed(category_name, final_articles))
        
        return master_feeds_list
"""
        with open(recipe_filename, "w", encoding="utf-8") as f:
            f.write(recipe_code)
        generated_files.append(recipe_filename)
        
    print(f"所有分册 Recipe 生成完毕，共 {len(generated_files)} 个文件。")

if __name__ == "__main__":
    generate_split_recipes(TARGET_DOMAIN)
