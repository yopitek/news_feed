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


def format_date_day(dt: datetime) -> str:
    """Date only — for sources that publish no time of day (e.g. PTT boards)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(TAIPEI_TZ).strftime("%m/%d")


def format_item_date(article: ArticleWithSummary) -> str:
    """Pick the date format the article's source actually supports."""
    precision = (article.metrics or {}).get('date_precision')
    if precision == 'day':
        return format_date_day(article.published)
    return format_date_short(article.published)


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def escape_attr(text: str) -> str:
    """Escape text for use in HTML attributes."""
    return escape_html(text).replace("'", '&#x27;')


def format_metric_badge(article: ArticleWithSummary) -> str:
    """
    Build the engagement badge for community tabs (PTT / Dcard).

    Returns an empty string for plain RSS articles, so the same item renderer
    serves every tab.
    """
    metrics = article.metrics or {}
    origin = metrics.get('origin')
    parts: list[str] = []

    if origin == 'dcard_snapshot':
        if metrics.get('like') is not None:
            parts.append(f"愛心 {metrics['like']}")
        if metrics.get('comment') is not None:
            parts.append(f"留言 {metrics['comment']}")
        if metrics.get('author'):
            parts.append(escape_html(str(metrics['author'])))
    elif origin in ('ptt_list', 'ptt_atom', 'ptt_snapshot'):
        label = metrics.get('push_label')
        if label:
            parts.append(f"推 {escape_html(str(label))}")
        elif metrics.get('push') is not None:
            parts.append(f"推 {metrics['push']}")
        if metrics.get('author'):
            parts.append(escape_html(str(metrics['author'])))

    if not parts:
        return ''
    return f'<span class="metrics">{" · ".join(parts)}</span>'


def render_news_item(article: ArticleWithSummary) -> str:
    """Render a single news item HTML for web."""
    publish_date = format_item_date(article)
    title = escape_html(article.title)
    source = escape_html(article.source_name)
    badge = format_metric_badge(article)

    # Sources without a body (PTT rows, image-only Dcard posts) fall back to the
    # title as their "summary" — do not print the title twice.
    summary_text = (article.summary or '').strip()
    if summary_text and summary_text != (article.title or '').strip():
        summary_html = f'<p class="news-item-summary">{escape_html(summary_text)}</p>'
    else:
        summary_html = ''
    
    link = escape_attr(article.link)
    return f'''<div class="news-item" data-link="{link}">
    <h4 class="news-item-title">
        <a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a>
    </h4>
    <p class="news-item-meta">
        <span class="source">{source}</span>
        <span class="date">{publish_date}</span>
        {badge}
    </p>
    {summary_html}
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


def render_source_panel(
    tech_sources: list[dict] | None,
    source_health: dict | None,
    title: str = 'Followed sources',
    status_text: str | None = None,
) -> str:
    """Render a source list and, optionally, a fetch-status line."""
    tech_sources = tech_sources or []
    if not tech_sources:
        return ''

    source_items = []
    for source in tech_sources:
        name = escape_html(source.get('source_name') or source.get('url', 'Unknown'))
        category = escape_html(source.get('group') or source.get('category', ''))
        label = f'{name} · {category}' if category else name
        source_items.append(f'<li>{label}</li>')

    if status_text is None:
        health = source_health or {}
        total = health.get('total_sources', len(tech_sources))
        ok = health.get('ok_sources')
        empty = health.get('empty_sources')
        failed = health.get('failed_sources')
        selected = health.get('selected_articles')

        status_bits = [f'{total} sources followed']
        if ok is not None:
            status_bits.append(f'{ok} returned articles')
        if empty is not None:
            status_bits.append(f'{empty} empty')
        if failed is not None:
            status_bits.append(f'{failed} failed')
        if selected is not None:
            status_bits.append(f'{selected} selected')
        status_text = ' · '.join(status_bits)

    source_items_html = '\n        '.join(source_items)
    source_status = escape_html(status_text)
    return f'''<div class="source-panel">
    <h3 class="source-panel-title">{escape_html(title)}</h3>
    <ul class="source-list">
        {source_items_html}
    </ul>
    <p class="source-status">{source_status}</p>
</div>'''


def render_snapshot_notice(
    snapshot_meta: dict | None,
    board_count: int = 0,
    label: str = 'Dcard',
    collector: str = 'python3 tools/collect_dcard.py',
    live_ok_text: str = '',
) -> str:
    """
    Render the "data captured on <time>" banner for locally-collected tabs.

    Both the Dcard and PTT tabs are normally fed from a snapshot committed to the
    repo rather than a live fetch, so readers must be told how old the data is.
    `live_ok_text`, when given, replaces the banner entirely — used when PTT was
    fetched live (the operator is on a Taiwan IP and the data really is fresh).
    """
    meta = snapshot_meta or {}
    collected_at = meta.get('collected_at')
    if not collected_at:
        if live_ok_text:
            return f'<p class="snapshot-notice snapshot-notice--fresh">{live_ok_text}</p>'
        return (
            f'<p class="snapshot-notice snapshot-notice--stale">'
            f'尚未取得 {label} 快照資料，本頁目前無內容。'
            f'請於本機執行 <code>{escape_html(collector)}</code> 後重新產生。'
            '</p>'
        )

    stamp = escape_html(str(collected_at).replace('T', ' ')[:16])
    age = meta.get('age_hours')
    total = meta.get('total_posts')
    bits = [f'資料時間：{stamp}']
    if isinstance(age, (int, float)):
        bits.append(f'{age:g} 小時前收集')
    if total:
        bits.append(f'共 {total} 篇')
    if board_count:
        bits.append(f'{board_count} 個看板')

    freshness = 'fresh'
    if isinstance(age, (int, float)) and age > 48:
        freshness = 'stale'

    return (
        f'<p class="snapshot-notice snapshot-notice--{freshness}">'
        f'{" · ".join(bits)}　'
        '<span class="snapshot-hint">本區資料由本機收集後隨網站更新，非即時抓取。</span>'
        '</p>'
    )


def render_pipeline_status(run_stats: dict | None, source_health: dict | None) -> str:
    """Render footer pipeline status text."""
    run_stats = run_stats or {}
    source_health = source_health or {}
    generated_at = run_stats.get('generated_at', '08:00 Asia/Taipei')
    selected = run_stats.get('articles_selected')
    feed_count = run_stats.get('feeds_count')

    bits = [f'Generated automatically at {generated_at}.']
    if feed_count is not None:
        bits.append(f'{feed_count} RSS/Atom sources checked.')
    if selected is not None:
        bits.append(f'{selected} articles selected.')

    # Report the two failure modes separately. They used to be merged into
    # "failed or returned no usable feed", which conflated a broken fetch with
    # a healthy feed that simply had nothing new today.
    degraded = []
    if source_health.get('failed_sources'):
        n = source_health['failed_sources']
        degraded.append(
            f"{n} Tech Blogs source{'s' if n != 1 else ''} could not be fetched")
    if source_health.get('empty_sources'):
        n = source_health['empty_sources']
        degraded.append(
            f"{n} Tech Blogs source{'s' if n != 1 else ''} had no new articles")
    if degraded:
        bits.append('; '.join(degraded) + '.')
    return ' '.join(bits)


def render_web(
    articles: dict[str, dict[str, list[ArticleWithSummary]]],
    date_str: Optional[str] = None,
    tech_sources: list[dict] | None = None,
    source_health: dict | None = None,
    run_stats: dict | None = None,
    ptt_sources: list[dict] | None = None,
    dcard_sources: list[dict] | None = None,
    snapshot_meta: dict | None = None,
    ptt_snapshot_meta: dict | None = None
) -> str:
    """
    Render web HTML with JavaScript tabs, grouped by category.
    
    Args:
        articles: Nested dict: tab -> category -> list of articles
        date_str: Optional date string
        tech_sources: Tech Blogs source list for its source panel
        source_health: Tech Blogs fetch health summary
        run_stats: Footer pipeline stats
        ptt_sources: PTT board list for the PTT source panel
        dcard_sources: Dcard board list for the Dcard source panel
        snapshot_meta: Collection time / counts of the Dcard snapshot
        ptt_snapshot_meta: Collection time / counts of the PTT snapshot (empty
            when PTT was fetched live)
    
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
    tech_blogs_content = render_tab_content(articles.get('tech_blogs', {}), 'tech_blogs')
    ptt_content = render_tab_content(articles.get('ptt_hot', {}), 'ptt_hot')
    dcard_content = render_tab_content(articles.get('dcard_hot', {}), 'dcard_hot')

    tech_sources_content = render_source_panel(tech_sources, source_health)
    ptt_sources_content = render_source_panel(
        ptt_sources, None, title='PTT 看板', status_text='依推文數排序'
    )
    dcard_sources_content = render_source_panel(
        dcard_sources, None, title='Dcard 看板', status_text='依愛心數排序'
    )
    dcard_notice = render_snapshot_notice(
        snapshot_meta, len(dcard_sources or []),
        label='Dcard', collector='python3 tools/collect_dcard.py',
    )
    ptt_notice = render_snapshot_notice(
        ptt_snapshot_meta, len(ptt_sources or []),
        label='PTT', collector='python3 tools/collect_ptt.py',
        live_ok_text='本區為即時抓取（本機執行，PTT 直連成功）。',
    )
    pipeline_status = render_pipeline_status(run_stats, source_health)
    
    html = template.replace('{{DATE_DISPLAY}}', date_str)
    html = html.replace('{{ZH_NEWS_ITEMS}}', zh_content)
    html = html.replace('{{EN_NEWS_ITEMS}}', en_content)
    html = html.replace('{{JA_NEWS_ITEMS}}', ja_content)
    html = html.replace('{{TECH_BLOGS_ITEMS}}', tech_blogs_content)
    html = html.replace('{{TECH_BLOGS_SOURCES}}', tech_sources_content)
    html = html.replace('{{PTT_HOT_ITEMS}}', ptt_content)
    html = html.replace('{{PTT_HOT_SOURCES}}', ptt_sources_content)
    html = html.replace('{{PTT_SNAPSHOT_NOTICE}}', ptt_notice)
    html = html.replace('{{DCARD_HOT_ITEMS}}', dcard_content)
    html = html.replace('{{DCARD_HOT_SOURCES}}', dcard_sources_content)
    html = html.replace('{{DCARD_SNAPSHOT_NOTICE}}', dcard_notice)
    html = html.replace('{{PIPELINE_STATUS}}', escape_html(pipeline_status))
    
    return html
