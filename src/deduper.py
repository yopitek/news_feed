"""
Deduplicate normalized articles.
"""
import re
import logging
from typing import Optional

from .models import NormalizedArticle
from .normalizer import normalize_url

logger = logging.getLogger(__name__)


def normalize_title_for_comparison(title: str) -> str:
    """Normalize title for near-duplicate detection."""
    title = title.lower()
    # Remove punctuation
    title = re.sub(r'[^\w\s]', '', title)
    # Collapse whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def deduplicate(articles: list[NormalizedArticle]) -> list[NormalizedArticle]:
    """
    Remove duplicate articles.
    
    Deduplication strategy:
    1. Primary: GUID
    2. Secondary: Normalized URL
    3. Tertiary: Similar titles from same source
    
    When duplicates found, keep the one with most recent published date.
    
    Args:
        articles: List of normalized articles
    
    Returns:
        Deduplicated list of articles
    """
    if not articles:
        return []
    
    original_count = len(articles)
    
    # Stage 1: Deduplicate by GUID
    guid_map: dict[str, NormalizedArticle] = {}
    for article in articles:
        key = article.guid
        if key in guid_map:
            # Keep the newer one
            if article.published > guid_map[key].published:
                guid_map[key] = article
        else:
            guid_map[key] = article
    
    stage1_results = list(guid_map.values())
    stage1_removed = original_count - len(stage1_results)
    
    # Stage 2: Deduplicate by normalized URL
    url_map: dict[str, NormalizedArticle] = {}
    for article in stage1_results:
        key = normalize_url(article.link)
        if key in url_map:
            # Keep the newer one
            if article.published > url_map[key].published:
                url_map[key] = article
        else:
            url_map[key] = article
    
    stage2_results = list(url_map.values())
    stage2_removed = len(stage1_results) - len(stage2_results)
    
    # Stage 3: Deduplicate by title + source (near-duplicates)
    title_source_map: dict[str, NormalizedArticle] = {}
    for article in stage2_results:
        normalized_title = normalize_title_for_comparison(article.title)
        # Only dedupe within same tab to avoid cross-language issues
        key = f"{article.tab}|{normalized_title}|{article.source_name}"
        if key in title_source_map:
            # Keep the newer one
            if article.published > title_source_map[key].published:
                title_source_map[key] = article
        else:
            title_source_map[key] = article
    
    final_results = list(title_source_map.values())
    stage3_removed = len(stage2_results) - len(final_results)
    
    logger.info(
        f"Deduplication: {original_count} → {len(final_results)} "
        f"(GUID: -{stage1_removed}, URL: -{stage2_removed}, Title: -{stage3_removed})"
    )
    
    return final_results


def deduplicate_within_tab(
    articles: list[NormalizedArticle], 
    tab_id: str
) -> list[NormalizedArticle]:
    """
    Deduplicate articles within a specific tab.
    
    Args:
        articles: All articles
        tab_id: Tab to filter and dedupe
    
    Returns:
        Deduplicated articles for that tab
    """
    tab_articles = [a for a in articles if a.tab == tab_id]
    return deduplicate(tab_articles)
