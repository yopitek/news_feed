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
FALLBACK_USER_AGENT = "Mozilla/5.0 (compatible; NewsDigest/1.0; +https://github.com/yopitek/news_feed)"
LAST_FETCH_STATS: list[dict] = []
LAST_SNAPSHOT_META: dict = {}
LAST_PTT_SNAPSHOT_META: dict = {}


def get_last_fetch_stats() -> list[dict]:
    """Return per-source stats from the latest fetch_all_feeds run."""
    return list(LAST_FETCH_STATS)


def get_last_snapshot_meta() -> dict:
    """Metadata of the Dcard snapshot used by the latest run (may be empty)."""
    return dict(LAST_SNAPSHOT_META)


def get_last_ptt_snapshot_meta() -> dict:
    """
    Metadata of the PTT snapshot used by the latest run.

    Empty when PTT was fetched live (i.e. we are running on a Taiwan IP), so the
    renderer can show the "captured at ..." banner only when it is true.
    """
    return dict(LAST_PTT_SNAPSHOT_META)


def summarize_source_health(stats: list[dict], selected: dict | None = None) -> dict:
    """Build a compact source health summary for output and rendering.

    The three buckets are mutually exclusive and must sum to total_sources:

    - ``ok``     — the feed was fetched and parsed
    - ``empty``  — fetched fine, the feed itself had no entries
    - ``failed`` — the fetch itself broke (DNS, timeout, HTTP error, unparseable)

    ``fetch_feed`` used to return ``[]`` for both "empty" and "failed", which
    collapsed the last two into one bucket and made ``failed_sources`` a
    double count of ``empty_sources`` (18 followed / 14 ok / 4 empty / 4 failed
    added up to 22).  ``fetch_feed`` now reports the distinction via its
    ``outcome`` argument and this function trusts ``status`` only.
    """
    selected = selected or {}
    tech_stats = [row for row in stats if row.get('tab') == 'tech_blogs']
    ok_sources = sum(1 for row in tech_stats if row.get('status') == 'ok')
    empty_sources = sum(1 for row in tech_stats if row.get('status') == 'empty')
    failed_sources = sum(1 for row in tech_stats if row.get('status') == 'failed')
    selected_articles = sum(len(items) for items in selected.get('tech_blogs', {}).values()) if selected else None
    return {
        'total_sources': len(tech_stats),
        'ok_sources': ok_sources,
        'empty_sources': empty_sources,
        'failed_sources': failed_sources,
        'selected_articles': selected_articles,
        'sources': tech_stats,
        # Every tab, not just tech_blogs. New key: older readers ignore it.
        'all': summarize_all_sources(stats),
    }


def _fetch_non_rss(source: dict, timeout: int, retries: int, user_agent: str,
                   max_items: int) -> tuple[list[dict], str]:
    """
    Dispatch a source to its collector.

    Returns:
        (entries, status). `status` is 'ok', 'empty', or a specific failure label
        surfaced in the run summary.
    """
    source_type = source.get('type', 'rss')
    url = source.get('url', '')
    source_name = source.get('source_name') or _get_domain(url)

    if source_type == 'ptt_list':
        from .ptt_fetcher import fetch_ptt_board
        from .snapshot_loader import load_ptt_board, load_ptt_snapshot, snapshot_meta

        board = source.get('board') or ''
        if not board:
            logger.error("ptt_list source %s has no `board`; skipping", source_name)
            return [], 'config_error'

        entries, status = fetch_ptt_board(
            url=url,
            board=board,
            source_name=source_name,
            fallback_url=source.get('fallback_url', ''),
            timeout=timeout,
            retries=retries,
            user_agent=user_agent,
            max_items=max_items,
            pages=int(source.get('pages', 1) or 1),
        )
        if status in ('ok', 'ok_atom_fallback'):
            return entries, status

        # Live PTT is unreachable from CI (403 on datacenter IPs). Fall back to
        # the locally-collected snapshot rather than shipping an empty tab.
        snapshot = load_ptt_snapshot()
        board_name = source.get('board_name') or source.get('category') or board
        fallback, snap_status = load_ptt_board(
            board=board, board_name=board_name, source_name=source_name
        )
        if fallback:
            if not LAST_PTT_SNAPSHOT_META:
                LAST_PTT_SNAPSHOT_META.update(snapshot_meta(snapshot))
                LAST_PTT_SNAPSHOT_META['live_status'] = status
            logger.info(
                "PTT %s: live fetch %s, served %d rows from snapshot",
                source_name, status, len(fallback),
            )
            return fallback, 'ok_snapshot'

        logger.warning("PTT %s: live %s and snapshot %s", source_name, status, snap_status)
        return [], status

    if source_type == 'dcard_snapshot':
        from .snapshot_loader import load_dcard_board

        board = source.get('board') or ''
        board_name = source.get('board_name') or source.get('category') or board
        return load_dcard_board(
            board_slug=board,
            board_name=board_name,
            source_name=source_name,
        )

    # Unknown type: fail loudly in the health table rather than silently fetching RSS.
    logger.error("Unknown source type '%s' for %s", source_type, source_name)
    return [], 'config_error'


def fetch_feed(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    max_items: int = DEFAULT_MAX_ITEMS,
    user_agent: str = DEFAULT_USER_AGENT,
    outcome: dict | None = None,
) -> list[dict]:
    """
    Fetch a single RSS/Atom feed with retry logic.

    Args:
        url: Feed URL to fetch
        timeout: HTTP timeout in seconds
        retries: Number of retry attempts
        max_items: Maximum items to return
        user_agent: User-Agent header
        outcome: Optional dict mutated in place so the caller can tell an empty
            feed apart from a broken one. Gets ``{'status': 'ok'|'empty'|'failed',
            'error': str|None}``. Pass it whenever the distinction matters — the
            return value alone is ``[]`` for both empty and failed.

    Returns:
        List of raw feed entries (as dicts)
    """
    def _record(status: str, error: str | None = None) -> None:
        if outcome is not None:
            outcome['status'] = status
            outcome['error'] = error

    backoff = [1, 2, 4]  # Exponential backoff
    last_error: str | None = None

    for attempt in range(retries + 1):
        try:
            # Fetch with custom headers
            headers = {
                'User-Agent': user_agent,
                'Accept': 'application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8',
            }
            response = requests.get(url, headers=headers, timeout=timeout)
            if getattr(response, 'status_code', None) in (403, 406) and user_agent != FALLBACK_USER_AGENT:
                # Several publishers answer 403/406 to an unknown agent string but
                # serve the same public feed to a browser-style one. One retry,
                # same URL, nothing else changed.
                logger.info(f"{_get_domain(url)} answered {response.status_code}; retrying with fallback User-Agent")
                headers['User-Agent'] = FALLBACK_USER_AGENT
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
                _record('failed', f'unparseable feed: {feed.bozo_exception}')
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
            _record('ok' if entries else 'empty')
            return entries

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/{retries + 1})")
            last_error = f'timeout after {timeout}s'
            if attempt < retries:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])
            continue

        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error for {url}: {e} (attempt {attempt + 1}/{retries + 1})")
            last_error = _short_error(e)
            if attempt < retries:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])
            continue

        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            _record('failed', f'unexpected error: {e}')
            return []

    logger.error(f"Failed to fetch {url} after {retries + 1} attempts")
    _record('failed', f'{last_error or "request failed"} (gave up after {retries + 1} attempts)')
    return []


def _short_error(exc: Exception) -> str:
    """One-line reason for the health table: 'HTTP 404', 'DNS failure', ..."""
    response = getattr(exc, 'response', None)
    if response is not None and getattr(response, 'status_code', None):
        return f'HTTP {response.status_code}'
    name = type(exc).__name__
    text = str(exc)
    if 'NameResolution' in text or 'getaddrinfo' in text or 'Name or service not known' in text:
        return 'DNS failure'
    if 'SSL' in name or 'CERTIFICATE' in text.upper():
        return 'TLS error'
    return name


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


def _newest_entry(entries: list[dict]) -> tuple[str | None, float | None]:
    """
    Newest publish time among fetched entries, as (ISO string, age in hours).

    Returns (None, None) when no entry carries a parseable date. Used to flag
    feeds that still answer 200 but stopped publishing: they look healthy in a
    fetched/failed count and silently contribute nothing to the digest.
    """
    import calendar
    from datetime import datetime, timezone

    newest = None
    for entry in entries:
        parsed = entry.get('published_parsed')
        if not parsed:
            continue
        try:
            ts = calendar.timegm(parsed)
        except Exception:
            continue
        if newest is None or ts > newest:
            newest = ts
    if newest is None:
        return None, None
    dt = datetime.fromtimestamp(newest, tz=timezone.utc)
    age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    return dt.isoformat(), round(age, 1)


# A news feed whose newest item is older than this is reported as stale.
STALE_AFTER_HOURS = 24 * 7
# Tabs where "no post for a week" is normal (personal blogs) or where the data
# is an engagement-ranked snapshot rather than a dated feed.
STALE_EXEMPT_TABS = {'tech_blogs', 'ptt_hot', 'dcard_hot'}


def summarize_all_sources(stats: list[dict], stale_after_hours: float = STALE_AFTER_HOURS) -> dict:
    """
    Health of every configured source, across all tabs.

    ``summarize_source_health`` only ever covered the tech_blogs tab, so a dead
    news feed (wrong URL, 403, site gone) was invisible: the run still finished
    "successfully" with that section thin or missing. This reports all of them
    and lists the ones that need attention.

    Buckets are mutually exclusive and sum to ``total_sources``:
    ok / stale / empty / failed. Any status starting with ``ok`` (``ok``,
    ``ok_snapshot``, ``ok_atom_fallback``) counts as ok.
    """
    rows = []
    by_tab: dict[str, dict] = {}
    for row in stats:
        raw_status = str(row.get('status') or '')
        age = row.get('newest_age_hours')
        if raw_status.startswith('ok'):
            if (
                row.get('tab') not in STALE_EXEMPT_TABS
                and age is not None
                and age > stale_after_hours
            ):
                health = 'stale'
            else:
                health = 'ok'
        elif raw_status == 'empty':
            health = 'empty'
        else:
            health = 'failed'
        out = dict(row)
        out['health'] = health
        rows.append(out)
        tab = by_tab.setdefault(
            row.get('tab', ''),
            {'total': 0, 'ok': 0, 'stale': 0, 'empty': 0, 'failed': 0, 'fetched_items': 0},
        )
        tab['total'] += 1
        tab[health] += 1
        tab['fetched_items'] += int(row.get('fetched_count') or 0)

    def _count(name: str) -> int:
        return sum(1 for r in rows if r['health'] == name)

    problems = [
        {
            'tab': r.get('tab'),
            'category': r.get('category'),
            'source_name': r.get('source_name'),
            'url': r.get('url'),
            'health': r['health'],
            'status': r.get('status'),
            'error': r.get('error'),
            'newest_published': r.get('newest_published'),
            'newest_age_hours': r.get('newest_age_hours'),
        }
        for r in rows if r['health'] != 'ok'
    ]
    return {
        'total_sources': len(rows),
        'ok_sources': _count('ok'),
        'stale_sources': _count('stale'),
        'empty_sources': _count('empty'),
        'failed_sources': _count('failed'),
        'stale_after_hours': stale_after_hours,
        'by_tab': by_tab,
        'problem_sources': problems,
        'sources': rows,
    }


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
    LAST_FETCH_STATS.clear()
    LAST_SNAPSHOT_META.clear()
    LAST_PTT_SNAPSHOT_META.clear()

    # Fresh policy-block verdict per run: this process may be on a different
    # network than the last one (laptop vs CI runner).
    from .ptt_fetcher import reset_live_state

    reset_live_state()
    
    for tab_id, tab_config in config.tabs.items():
        tab_entries = []
        
        for source in tab_config.sources:
            url = source.get('url', '')
            source_type = source.get('type', 'rss')
            if not url and source_type != 'dcard_snapshot':
                continue
            
            # Fetch this source (RSS by default, dedicated collector otherwise)
            if source_type == 'rss':
                # `outcome` is what lets us tell "the feed is fine but had no
                # entries" apart from "the fetch broke" — the return value is []
                # in both cases, and conflating them double-counts the health
                # summary (see summarize_source_health).
                outcome: dict = {}
                entries = fetch_feed(
                    url=url,
                    timeout=timeout,
                    retries=retries,
                    max_items=max_items,
                    user_agent=user_agent,
                    outcome=outcome
                )
                status = outcome.get('status') or ('ok' if entries else 'empty')
                error = outcome.get('error')
            else:
                error = None
                entries, status = _fetch_non_rss(
                    source, timeout=timeout, retries=retries,
                    user_agent=user_agent, max_items=max_items
                )
                if source_type == 'dcard_snapshot':
                    from .snapshot_loader import load_snapshot, snapshot_age_hours
                    snapshot = load_snapshot()
                    if snapshot and not LAST_SNAPSHOT_META:
                        LAST_SNAPSHOT_META.update({
                            'collected_at': snapshot.get('collected_at'),
                            'age_hours': snapshot_age_hours(snapshot),
                            'boards': snapshot.get('boards', []),
                            'total_posts': len(snapshot.get('posts', [])),
                        })
                elif source_type == 'ptt_list' and status == 'ok':
                    # PTT paginates politely: pause between boards — but only
                    # when we are actually talking to PTT (not on a snapshot).
                    from .ptt_fetcher import INTER_BOARD_DELAY
                    time.sleep(INTER_BOARD_DELAY)

            fetched_count = len(entries)
            newest_iso, newest_age_hours = _newest_entry(entries)
            LAST_FETCH_STATS.append({
                'tab': tab_id,
                'language': tab_config.language,
                'category': source.get('category', ''),
                'source_name': source.get('source_name', '') or _get_domain(url),
                'group': source.get('group', ''),
                'url': url,
                'type': source_type,
                'status': status,
                'fetched_count': fetched_count,
                'error': error,
                'newest_published': newest_iso,
                'newest_age_hours': newest_age_hours,
            })

            for entry in entries:
                entry['_tab'] = tab_id
                entry['_language'] = tab_config.language
                entry['_category'] = source.get('category', '')
                entry['_source_name'] = source.get('source_name', '')
                if tab_id == 'tech_blogs':
                    entry['_source_type'] = 'tech_blog'
                elif source_type == 'rss':
                    entry['_source_type'] = 'news'
                else:
                    entry['_source_type'] = source_type
            
            tab_entries.extend(entries)
        
        results[tab_id] = tab_entries
        logger.info(f"Tab '{tab_id}': {len(tab_entries)} total entries")
    
    return results
