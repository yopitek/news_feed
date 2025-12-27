"""
Select articles by category for each tab.
Groups articles by category and selects top N per category.

Updated for:
- English: Startup (8) + Tech News (8) + BBC subcategories (6 each)
"""
import logging
from collections import defaultdict
from .models import NormalizedArticle

logger = logging.getLogger(__name__)

# Category definitions for each tab
TAB_CATEGORIES = {
    'zh_news': [
        '頭條新聞', '產經', '股市', '全球國際新聞',
        '社會', '生活', '娛樂', '運動', '房市'
    ],
    'en_news': [
        'Startup', 'Tech News',
        'BBC Top Stories', 'BBC World', 'BBC Business', 'BBC Education',
        'BBC Technology', 'BBC Health', 'BBC Science & Environment'
    ],
    'ja_news': ['頭條', '國際', '政治', '運動', '商業', '文化', '娛樂']
}

# Items per category (different for BBC)
ITEMS_PER_CATEGORY = {
    'zh_news': 8,
    'en_news': {
        'Startup': 8,
        'Tech News': 8,
        'BBC Top Stories': 6,
        'BBC World': 6,
        'BBC Business': 6,
        'BBC Education': 6,
        'BBC Technology': 6,
        'BBC Health': 6,
        'BBC Science & Environment': 6
    },
    'ja_news': 8
}


def get_items_per_category(tab: str, category: str) -> int:
    """Get the number of items for a specific tab/category."""
    config = ITEMS_PER_CATEGORY.get(tab, 8)
    if isinstance(config, dict):
        return config.get(category, 8)
    return config


def map_to_display_category(article: NormalizedArticle) -> str:
    """Map article to its display category based on tab and RSS category."""
    tab = article.tab
    rss_cat = article.rss_category or ''
    final_cat = article.final_category or ''
    
    if tab == 'zh_news':
        # Chinese uses final_category from classifier
        return final_cat if final_cat in TAB_CATEGORIES['zh_news'] else '頭條新聞'
    
    elif tab == 'en_news':
        # English: directly use rss_category from feeds.yaml
        if rss_cat in TAB_CATEGORIES['en_news']:
            return rss_cat
        # Fallback mapping for legacy categories
        legacy_mapping = {
            'Tech': 'Tech News',
            'Tech Media': 'Tech News',
            'BBC': 'BBC Top Stories'
        }
        return legacy_mapping.get(rss_cat, 'Tech News')
    
    elif tab == 'ja_news':
        # Japanese: directly use rss_category from feeds.yaml
        if rss_cat in TAB_CATEGORIES['ja_news']:
            return rss_cat
        else:
            return '頭條'  # fallback
    
    return rss_cat


def select_by_category(
    articles: list[NormalizedArticle],
    items_per_category: int = 8  # default, overridden by ITEMS_PER_CATEGORY
) -> dict[str, dict[str, list[NormalizedArticle]]]:
    """
    Select articles grouped by category within each tab.
    
    Args:
        articles: All classified articles
        items_per_category: Default number of articles per category
    
    Returns:
        Nested dict: tab_id -> category -> list of articles
    """
    # Group articles by tab first
    tab_articles: dict[str, list[NormalizedArticle]] = defaultdict(list)
    for article in articles:
        tab_articles[article.tab].append(article)
    
    result = {}
    
    for tab_id, tab_items in tab_articles.items():
        categories_order = TAB_CATEGORIES.get(tab_id, [])
        if not categories_order:
            continue
        
        # Map each article to display category
        category_groups: dict[str, list[NormalizedArticle]] = defaultdict(list)
        for article in tab_items:
            display_cat = map_to_display_category(article)
            if display_cat in categories_order:
                category_groups[display_cat].append(article)
        
        # Select top N from each category, sorted by date
        tab_result = {}
        for category in categories_order:
            cat_articles = category_groups.get(category, [])
            # Sort by published date (newest first)
            sorted_articles = sorted(
                cat_articles,
                key=lambda a: a.published,
                reverse=True
            )
            # Get items count for this category
            n = get_items_per_category(tab_id, category)
            # Take top N
            selected = sorted_articles[:n]
            
            if selected:
                tab_result[category] = selected
                logger.info(f"Tab '{tab_id}' / Category '{category}': {len(selected)} articles")
            else:
                logger.warning(f"Tab '{tab_id}' / Category '{category}': No articles")
        
        result[tab_id] = tab_result
    
    # Ensure all tabs exist
    for tab_id in TAB_CATEGORIES.keys():
        if tab_id not in result:
            result[tab_id] = {}
    
    return result


def flatten_to_list(
    categorized: dict[str, dict[str, list[NormalizedArticle]]]
) -> dict[str, list[NormalizedArticle]]:
    """
    Flatten category-grouped articles to a simple list per tab.
    Preserves category order.
    """
    result = {}
    for tab_id, categories in categorized.items():
        flat_list = []
        for category in TAB_CATEGORIES.get(tab_id, []):
            if category in categories:
                flat_list.extend(categories[category])
        result[tab_id] = flat_list
    return result
