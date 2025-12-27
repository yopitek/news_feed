"""
RSS/Atom feed fetcher with retry and timeout handling.
"""
import time
import logging
from typing import Optional
from urllib.parse import urlparse

import feedparser
import requests

from .models import FeedsConfig, RawFeedEntry

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 2
DEFAULT_MAX_ITEMS = 20
DEFAULT_USER_AGENT = "NewsDigest/1.0 (RSS Reader)"


def fetch_feed(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    max_items: int = DEFAULT_MAX_ITEMS,
    user_agent: str = DEFAULT_USER_AGENT
) -> list[dict]:
    """
    Fetch a single RSS/Atom feed with retry logic.
    
    Args:
        url: Feed URL to fetch
        timeout: HTTP timeout in seconds
        retries: Number of retry attempts
        max_items: Maximum items to return
        user_agent: User-Agent header
    
    Returns:
        List of raw feed entries (as dicts)
    """
    backoff = [1, 2, 4]  # Exponential backoff
    
    for attempt in range(retries + 1):
        try:
            # Fetch with custom headers
            headers = {'User-Agent': user_agent}
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            # Parse feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo and not feed.entries:
                # Feed parsing error with no entries
                logger.warning(f"Feed parsing error for {url}: {feed.bozo_exception}")
                if attempt < retries:
                    time.sleep(backoff[min(attempt, len(backoff) - 1)])
                    continue
                return []
            
            # Extract entries (up to max_items)
            entries = []
            for entry in feed.entries[:max_items]:
                entries.append({
                    'title': entry.get('title', ''),
                    'link': _extract_link(entry),
                    'published': entry.get('published', entry.get('updated', '')),
                    'published_parsed': entry.get('published_parsed', entry.get('updated_parsed')),
                    'summary': entry.get('summary', entry.get('description', '')),
                    'guid': entry.get('id', entry.get('guid', '')),
                    'source_feed_url': url
                })
            
            logger.info(f"Fetched {len(entries)} items from {_get_domain(url)}")
            return entries
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/{retries + 1})")
            if attempt < retries:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])
            continue
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error for {url}: {e} (attempt {attempt + 1}/{retries + 1})")
            if attempt < retries:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])
            continue
            
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return []
    
    logger.error(f"Failed to fetch {url} after {retries + 1} attempts")
    return []


def _extract_link(entry: dict) -> str:
    """Extract the best link from a feed entry."""
    # Try direct link
    link = entry.get('link', '')
    if link:
        if isinstance(link, str):
            return link
        elif isinstance(link, list) and link:
            # Atom feeds may have multiple links
            for l in link:
                if isinstance(l, dict) and l.get('rel') == 'alternate':
                    return l.get('href', '')
            return link[0].get('href', '') if isinstance(link[0], dict) else str(link[0])
    
    # Fallback to id
    return entry.get('id', '')


def _get_domain(url: str) -> str:
    """Extract domain from URL for logging."""
    try:
        return urlparse(url).netloc
    except Exception:
        return url[:50]


def fetch_all_feeds(config: FeedsConfig) -> dict[str, list[dict]]:
    """
    Fetch all feeds organized by tab.
    
    Args:
        config: FeedsConfig with all tab/source definitions
    
    Returns:
        Dict of tab_id -> list of raw feed entries
    """
    settings = config.settings
    timeout = settings.get('fetch_timeout', DEFAULT_TIMEOUT)
    retries = settings.get('fetch_retries', DEFAULT_RETRIES)
    max_items = settings.get('max_items_per_feed', DEFAULT_MAX_ITEMS)
    user_agent = settings.get('user_agent', DEFAULT_USER_AGENT)
    
    results = {}
    
    for tab_id, tab_config in config.tabs.items():
        tab_entries = []
        
        for source in tab_config.sources:
            url = source.get('url', '')
            if not url:
                continue
            
            # Fetch this feed
            entries = fetch_feed(
                url=url,
                timeout=timeout,
                retries=retries,
                max_items=max_items,
                user_agent=user_agent
            )
            
            # Add metadata to each entry
            for entry in entries:
                entry['_tab'] = tab_id
                entry['_language'] = tab_config.language
                entry['_category'] = source.get('category', '')
                entry['_source_name'] = source.get('source_name', '')
            
            tab_entries.extend(entries)
        
        results[tab_id] = tab_entries
        logger.info(f"Tab '{tab_id}': {len(tab_entries)} total entries")
    
    return results
