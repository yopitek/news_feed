"""
Web HTML renderer with JavaScript tabs.
Groups news by category within each tab.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytz

from .models import ArticleWithSummary
from .selector import TAB_CATEGORIES

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "web_template.html"
TAIPEI_TZ = pytz.timezone('Asia/Taipei')


def format_date_short(dt: datetime) -> str:
    """Format datetime as short date."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    taipei_dt = dt.astimezone(TAIPEI_TZ)
    return taipei_dt.strftime("%m/%d %H:%M")


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def render_news_item(article: ArticleWithSummary) -> str:
    """Render a single news item HTML for web."""
    publish_date = format_date_short(article.published)
    title = escape_html(article.title)
    source = escape_html(article.source_name)
    summary = escape_html(article.summary)
    
    return f'''<div class="news-item">
    <h4 class="news-item-title">
        <a href="{article.link}" target="_blank" rel="noopener noreferrer">{title}</a>
    </h4>
    <p class="news-item-meta">
        <span class="source">{source}</span>
        <span class="date">{publish_date}</span>
    </p>
    <p class="news-item-summary">{summary}</p>
</div>'''


def render_category_section(category: str, articles: list[ArticleWithSummary]) -> str:
    """Render a category section with its articles."""
    if not articles:
        return ''
    
    category_escaped = escape_html(category)
    items_html = '\n'.join(render_news_item(article) for article in articles)
    
    return f'''<div class="category-section">
    <h3 class="category-header">{category_escaped}</h3>
    <div class="category-news-list">
        {items_html}
    </div>
</div>'''


def render_tab_content(categories_data: dict[str, list[ArticleWithSummary]], tab_id: str) -> str:
    """Render all category sections for a tab."""
    if not categories_data:
        return '<p class="no-news">No news available for this section.</p>'
    
    # Get ordered category list
    category_order = TAB_CATEGORIES.get(tab_id, [])
    
    sections = []
    for category in category_order:
        if category in categories_data:
            section = render_category_section(category, categories_data[category])
            if section:
                sections.append(section)
    
    # Also include any categories not in the predefined order
    for category, articles in categories_data.items():
        if category not in category_order:
            section = render_category_section(category, articles)
            if section:
                sections.append(section)
    
    return '\n'.join(sections) if sections else '<p class="no-news">No news available.</p>'


def render_web(
    articles: dict[str, dict[str, list[ArticleWithSummary]]],
    date_str: Optional[str] = None
) -> str:
    """
    Render web HTML with JavaScript tabs, grouped by category.
    
    Args:
        articles: Nested dict: tab -> category -> list of articles
        date_str: Optional date string
    
    Returns:
        Complete HTML string
    """
    # Load template
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Generate date display
    if date_str is None:
        now = datetime.now(TAIPEI_TZ)
        weekdays = ['一', '二', '三', '四', '五', '六', '日']
        date_str = now.strftime("%Y年%m月%d日 星期") + weekdays[now.weekday()]
    
    # Render each tab's content (grouped by category)
    zh_content = render_tab_content(articles.get('zh_news', {}), 'zh_news')
    en_content = render_tab_content(articles.get('en_news', {}), 'en_news')
    ja_content = render_tab_content(articles.get('ja_news', {}), 'ja_news')
    
    # Substitute placeholders
    html = template.replace('{{DATE_DISPLAY}}', date_str)
    html = html.replace('{{ZH_NEWS_ITEMS}}', zh_content)
    html = html.replace('{{EN_NEWS_ITEMS}}', en_content)
    html = html.replace('{{JA_NEWS_ITEMS}}', ja_content)
    
    return html
