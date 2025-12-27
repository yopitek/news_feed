"""
Normalize raw RSS/Atom entries to a common schema.
"""
import re
import hashlib
import logging
from datetime import datetime, timezone
from html import unescape
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from time import mktime

from dateutil import parser as dateutil_parser

from .models import NormalizedArticle, FeedsConfig

logger = logging.getLogger(__name__)

# Tracking parameters to remove from URLs
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'ref', 'source', 'mc_cid', 'mc_eid', 'ocid'
}


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    clean = unescape(clean)
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    if not url:
        return ""
    
    try:
        parsed = urlparse(url)
        
        # Remove tracking params
        query = parse_qs(parsed.query)
        filtered_query = {k: v for k, v in query.items() 
                          if k.lower() not in TRACKING_PARAMS}
        
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip('/') or '/',
            parsed.params,
            urlencode(filtered_query, doseq=True),
            ''  # Remove fragment
        ))
        return normalized
    except Exception:
        return url


def parse_datetime(entry: dict) -> datetime:
    """Parse published/updated datetime from feed entry."""
    # Try structured time first
    struct_time = entry.get('published_parsed')
    if struct_time:
        try:
            return datetime.fromtimestamp(mktime(struct_time), tz=timezone.utc)
        except Exception:
            pass
    
    # Try string parsing
    date_str = entry.get('published', '')
    if date_str:
        try:
            dt = dateutil_parser.parse(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    
    # Fallback to current time
    return datetime.now(timezone.utc)


def generate_guid(entry: dict, link: str, title: str) -> str:
    """Generate or extract unique identifier."""
    # Try existing ID/GUID
    guid = entry.get('guid', entry.get('id', ''))
    if guid:
        if isinstance(guid, dict):
            guid = guid.get('value', str(guid))
        return str(guid)
    
    # Fallback: use link
    if link:
        return link
    
    # Final fallback: hash of title
    return hashlib.md5((title or "").encode()).hexdigest()


def get_source_name(entry: dict, default: str = "") -> str:
    """Get source name from entry metadata or fallback."""
    # Check if we have explicit source_name
    source_name = entry.get('_source_name', '')
    if source_name:
        return source_name
    
    # Try to extract from feed URL
    feed_url = entry.get('source_feed_url', '')
    if feed_url:
        try:
            domain = urlparse(feed_url).netloc
            # Clean up domain
            domain = domain.replace('www.', '').replace('feeds.', '')
            return domain.split('.')[0].title()
        except Exception:
            pass
    
    return default or "Unknown"


def normalize_entry(
    entry: dict,
    tab: str,
    language: str,
    rss_category: str,
    source_name: str
) -> Optional[NormalizedArticle]:
    """
    Normalize a single feed entry.
    
    Args:
        entry: Raw feedparser entry dict
        tab: Tab ID (e.g., 'zh_news')
        language: Language code ('zh', 'en', 'ja')
        rss_category: Category from feeds.yaml
        source_name: Human-readable source name
    
    Returns:
        NormalizedArticle or None if entry is invalid
    """
    # Extract and clean title
    title = strip_html(entry.get('title', ''))
    if not title:
        return None  # Skip entries without title
    
    # Extract and normalize link
    link = entry.get('link', '')
    link = normalize_url(link)
    
    if not link:
        return None  # Skip entries without link
    
    # Parse datetime
    published = parse_datetime(entry)
    
    # Extract description
    description = strip_html(entry.get('summary', ''))
    if description:
        # Truncate to 500 chars while preserving words
        if len(description) > 500:
            description = description[:500].rsplit(' ', 1)[0] + '...'
    else:
        description = None
    
    # Generate GUID
    guid = generate_guid(entry, link, title)
    
    # Get source name
    final_source_name = source_name or get_source_name(entry)
    
    return NormalizedArticle(
        title=title,
        link=link,
        published=published,
        source_name=final_source_name,
        language=language,
        tab=tab,
        rss_category=rss_category,
        guid=guid,
        description=description,
        final_category=None  # Set later by classifier
    )


def normalize_all(
    raw_feeds: dict[str, list[dict]], 
    config: FeedsConfig
) -> list[NormalizedArticle]:
    """
    Normalize all raw entries from all feeds.
    
    Args:
        raw_feeds: Dict of tab_id -> list of raw entries
        config: FeedsConfig for metadata
    
    Returns:
        List of NormalizedArticle objects
    """
    articles = []
    
    for tab_id, entries in raw_feeds.items():
        tab_config = config.tabs.get(tab_id)
        if not tab_config:
            logger.warning(f"No config found for tab: {tab_id}")
            continue
        
        for entry in entries:
            # Get metadata from entry (added during fetch)
            language = entry.get('_language', tab_config.language)
            rss_category = entry.get('_category', '')
            source_name = entry.get('_source_name', '')
            
            article = normalize_entry(
                entry=entry,
                tab=tab_id,
                language=language,
                rss_category=rss_category,
                source_name=source_name
            )
            
            if article:
                articles.append(article)
    
    logger.info(f"Normalized {len(articles)} articles")
    return articles
