"""
Email HTML renderer with anchor-based navigation.
Groups news by category within each tab.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytz

from .models import ArticleWithSummary
from .selector import TAB_CATEGORIES

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "email_template.html"
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


def render_news_item_email(article: ArticleWithSummary) -> str:
    """Render a single news item HTML for email."""
    publish_date = format_date_short(article.published)
    title = escape_html(article.title)
    source = escape_html(article.source_name)
    summary = escape_html(article.summary)
    
    return f'''<tr>
    <td style="padding: 12px 0; border-bottom: 1px dotted #d9d2c4;">
        <p style="font-family: Georgia, serif; font-size: 15px; font-weight: bold; margin: 0 0 4px 0; line-height: 1.4;">
            <a href="{article.link}" target="_blank" style="color: #1a1a1a; text-decoration: none;">{title}</a>
        </p>
        <p style="font-family: Arial, sans-serif; font-size: 11px; color: #666666; margin: 0 0 6px 0;">
            <strong>{source}</strong> · {publish_date}
        </p>
        <p style="font-family: Arial, sans-serif; font-size: 13px; line-height: 1.5; color: #333333; margin: 0;">
            {summary}
        </p>
    </td>
</tr>'''


def render_category_section_email(category: str, articles: list[ArticleWithSummary]) -> str:
    """Render a category section for email."""
    if not articles:
        return ''
    
    category_escaped = escape_html(category)
    items_html = '\n'.join(render_news_item_email(article) for article in articles)
    
    return f'''<tr>
    <td style="padding: 16px 0 8px 0;">
        <p style="font-family: Georgia, serif; font-size: 16px; font-weight: bold; color: #990f3d; margin: 0; padding-bottom: 8px; border-bottom: 2px solid #990f3d;">
            {category_escaped}
        </p>
    </td>
</tr>
<tr>
    <td>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            {items_html}
        </table>
    </td>
</tr>'''


def render_tab_content_email(categories_data: dict[str, list[ArticleWithSummary]], tab_id: str) -> str:
    """Render all category sections for a tab (email version)."""
    if not categories_data:
        return '''<tr><td style="padding: 14px 0;"><p style="font-family: Arial, sans-serif; font-size: 14px; color: #666666;">No news available.</p></td></tr>'''
    
    category_order = TAB_CATEGORIES.get(tab_id, [])
    
    sections = []
    for category in category_order:
        if category in categories_data:
            section = render_category_section_email(category, categories_data[category])
            if section:
                sections.append(section)
    
    for category, articles in categories_data.items():
        if category not in category_order:
            section = render_category_section_email(category, articles)
            if section:
                sections.append(section)
    
    return '\n'.join(sections) if sections else '''<tr><td><p>No news available.</p></td></tr>'''


def render_email(
    articles: dict[str, dict[str, list[ArticleWithSummary]]],
    date_str: Optional[str] = None
) -> str:
    """
    Render email HTML, grouped by category.
    
    Args:
        articles: Nested dict: tab -> category -> list of articles
        date_str: Optional date string
    
    Returns:
        Complete email HTML string
    """
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        template = f.read()
    
    if date_str is None:
        now = datetime.now(TAIPEI_TZ)
        weekdays = ['一', '二', '三', '四', '五', '六', '日']
        date_str = now.strftime("%Y年%m月%d日 星期") + weekdays[now.weekday()]
    
    zh_content = render_tab_content_email(articles.get('zh_news', {}), 'zh_news')
    en_content = render_tab_content_email(articles.get('en_news', {}), 'en_news')
    ja_content = render_tab_content_email(articles.get('ja_news', {}), 'ja_news')
    
    html = template.replace('{{DATE_DISPLAY}}', date_str)
    html = html.replace('{{ZH_NEWS_ITEMS}}', zh_content)
    html = html.replace('{{EN_NEWS_ITEMS}}', en_content)
    html = html.replace('{{JA_NEWS_ITEMS}}', ja_content)
    
    return html
