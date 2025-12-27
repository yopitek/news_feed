# Step 3: RSS Normalization & Deduplication Logic

## 1. RSS Fetching Strategy

### Feed Fetching Rules

| Rule                     | Value                  | Rationale                                    |
|--------------------------|------------------------|----------------------------------------------|
| **Timeout**              | 10 seconds             | Prevent hanging on slow feeds                |
| **Retry attempts**       | 2 (total 3 tries)      | Handle transient failures                    |
| **Retry backoff**        | 1s, 2s                 | Exponential backoff                          |
| **Max items per feed**   | 20                     | Limit memory, get enough for selection       |
| **User-Agent**           | Custom identifier      | Some feeds block default Python UA           |

### Fetch Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FEED FETCHING FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

For each feed URL in feeds.yaml:
    │
    ├─▶ [Attempt 1] HTTP GET with timeout=10s
    │     │
    │     ├─ Success → Parse with feedparser → Extract entries → Continue
    │     │
    │     └─ Failure (timeout/connection error/4xx/5xx)
    │           │
    │           ├─▶ [Attempt 2] Wait 1s → Retry
    │           │     │
    │           │     ├─ Success → Parse → Continue
    │           │     │
    │           │     └─ Failure
    │           │           │
    │           │           └─▶ [Attempt 3] Wait 2s → Retry
    │           │                 │
    │           │                 ├─ Success → Parse → Continue
    │           │                 │
    │           │                 └─ Failure
    │           │                       │
    │           │                       └─ Log error, skip feed, continue pipeline
    │
    └─▶ Extract up to 20 most recent entries

```

---

## 2. Normalization Schema

### Raw Input (feedparser)

Different RSS/Atom feeds provide different field names:

| Field Type       | RSS 2.0            | Atom 1.0           | RDF/RSS 1.0       |
|------------------|--------------------|--------------------|-------------------|
| Title            | `title`            | `title`            | `title`           |
| Link             | `link`             | `link` (first)     | `link`            |
| Published        | `pubDate`          | `published`        | `dc:date`         |
| Summary          | `description`      | `summary`          | `description`     |
| GUID             | `guid`             | `id`               | `link` (as id)    |
| Author           | `author`           | `author.name`      | `dc:creator`      |

### Normalized Output Schema

```python
@dataclass
class NormalizedArticle:
    # Required fields
    title: str                    # Cleaned, HTML-stripped title
    link: str                     # Canonical URL
    published: datetime           # Parsed datetime (UTC internally)
    source_name: str              # Human-readable source name (e.g., "中央通訊社", "BBC")
    language: str                 # 'zh', 'en', 'ja'
    tab: str                      # 'zh_news', 'zh_industry', 'en_news', 'ja_news'
    rss_category: str             # Category from feeds.yaml
    guid: str                     # Unique identifier (GUID or URL hash)
    
    # Optional fields
    description: Optional[str]    # RSS description/summary if available
    final_category: Optional[str] # Assigned category (Chinese only)
```

### Normalization Rules

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FIELD NORMALIZATION RULES                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┬───────────────────────────────────────────────────────────┐
│ FIELD                │ NORMALIZATION RULE                                        │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ title                │ 1. Get entry.title                                        │
│                      │ 2. Strip HTML tags (BeautifulSoup or regex)               │
│                      │ 3. Decode HTML entities (&amp; → &)                       │
│                      │ 4. Normalize whitespace (collapse multiple spaces)        │
│                      │ 5. Trim leading/trailing whitespace                       │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ link                 │ 1. Get entry.link (prefer first if multiple)              │
│                      │ 2. Resolve relative URLs to absolute                      │
│                      │ 3. Remove tracking parameters (utm_*, fbclid, etc.)       │
│                      │ 4. Normalize URL (lowercase domain, remove fragments)     │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ published            │ 1. Try entry.published_parsed (struct_time)               │
│                      │ 2. Fallback: entry.published (string) → dateutil.parse    │
│                      │ 3. Fallback: entry.updated_parsed                         │
│                      │ 4. Final fallback: current UTC time                       │
│                      │ 5. Convert to timezone-aware datetime (UTC)               │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ source_name          │ 1. Use feed title from feedparser (feed.feed.title)       │
│                      │ 2. Fallback: extract domain from feed URL                 │
│                      │ 3. Override: use source_name from feeds.yaml if defined   │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ guid                 │ 1. Use entry.id if present                                │
│                      │ 2. Fallback: entry.guid                                   │
│                      │ 3. Fallback: entry.link                                   │
│                      │ 4. Final fallback: hash(title + link)                     │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ description          │ 1. Get entry.summary or entry.description                 │
│                      │ 2. Strip HTML tags                                        │
│                      │ 3. Decode HTML entities                                   │
│                      │ 4. Truncate to 500 chars if longer (preserve words)       │
│                      │ 5. None if empty or only whitespace                       │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ language             │ Determined by tab assignment in feeds.yaml:               │
│                      │ - zh_news, zh_industry → 'zh'                             │
│                      │ - en_news → 'en'                                          │
│                      │ - ja_news → 'ja'                                          │
├──────────────────────┼───────────────────────────────────────────────────────────┤
│ rss_category         │ Taken directly from feeds.yaml source.category            │
│                      │ (e.g., "政治", "Startup", "経済")                          │
└──────────────────────┴───────────────────────────────────────────────────────────┘
```

---

## 3. Deduplication Strategy

### Deduplication Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DEDUPLICATION PIPELINE                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

Input: List[NormalizedArticle] (all articles from all feeds)
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: PRIMARY KEY DEDUPLICATION                                                │
│ ─────────────────────────────────────────────────────────────────────────────── │
│ Key: guid (from RSS/Atom)                                                        │
│ Action: If same guid seen, keep the one with most recent published date         │
│ Result: Articles with unique GUIDs                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: SECONDARY KEY DEDUPLICATION                                              │
│ ─────────────────────────────────────────────────────────────────────────────── │
│ Key: normalized_link (canonical URL)                                             │
│ Action: If same URL seen, keep the one with most recent published date          │
│ Result: Articles with unique URLs                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: TITLE-BASED NEAR-DUPLICATE DETECTION (OPTIONAL)                          │
│ ─────────────────────────────────────────────────────────────────────────────── │
│ Key: normalized_title (lowercase, no punctuation, whitespace collapsed)          │
│ Action: If title similarity > 90% AND same source_name, keep newer              │
│ Result: Near-duplicates removed                                                  │
│                                                                                  │
│ ⚠️ This step is OPTIONAL for MVP. Enable if duplicate titles observed.          │
└─────────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
Output: List[NormalizedArticle] (deduplicated)
```

### Deduplication Keys

```python
# Primary Key: GUID
def get_primary_key(article: NormalizedArticle) -> str:
    return article.guid

# Secondary Key: Normalized URL
def normalize_url(url: str) -> str:
    """
    Normalize URL for comparison:
    1. Parse URL
    2. Lowercase scheme and host
    3. Remove trailing slash
    4. Remove query params: utm_*, fbclid, gclid, ref, etc.
    5. Remove fragment (#...)
    """
    from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
    
    parsed = urlparse(url)
    
    # Remove tracking params
    tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 
                       'utm_content', 'fbclid', 'gclid', 'ref', 'source'}
    query = parse_qs(parsed.query)
    filtered_query = {k: v for k, v in query.items() if k.lower() not in tracking_params}
    
    normalized = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip('/'),
        parsed.params,
        urlencode(filtered_query, doseq=True),
        ''  # Remove fragment
    ))
    
    return normalized

# Tertiary Key: Normalized Title (for fuzzy matching)
def normalize_title(title: str) -> str:
    """
    Normalize title for comparison:
    1. Lowercase
    2. Remove punctuation
    3. Collapse whitespace
    """
    import re
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title
```

### Conflict Resolution

When duplicates are detected, keep the article with:
1. **Primary**: Most recent `published` datetime
2. **Tie-breaker**: First encountered (maintains feed priority in config)

```python
def resolve_duplicate(existing: NormalizedArticle, new: NormalizedArticle) -> NormalizedArticle:
    """Keep the article with more recent published date."""
    if new.published > existing.published:
        return new
    return existing
```

---

## 4. Items Per Feed Configuration

### From `feeds.yaml`

```yaml
tabs:
  zh_news:
    name: 中文新聞
    item_limit_per_category: 5    # Select 5 final items for this tab
    max_items_per_feed: 20        # Fetch up to 20 items per feed (before dedup)
    sources:
      - category: 國際
        url: https://feeds.feedburner.com/rsscna/intworld
      # ... more sources
```

### Fetch vs. Select

| Stage                    | Count     | Purpose                                    |
|--------------------------|-----------|-------------------------------------------|
| **Fetch** (per feed)     | 20 max    | Get enough candidates for variety         |
| **After Dedup** (total)  | Variable  | Merge all feeds, remove duplicates        |
| **Select** (per tab)     | 5 exactly | Final output per tab                      |

---

## 5. Implementation Code

### `normalizer.py`

```python
"""
Normalize raw RSS/Atom entries to a common schema.
"""
import re
import hashlib
from datetime import datetime, timezone
from html import unescape
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from time import mktime

from dateutil import parser as dateutil_parser

from .models import RawFeedEntry, NormalizedArticle


# Tracking parameters to remove from URLs
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'ref', 'source', 'mc_cid', 'mc_eid'
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
    for field in ['published_parsed', 'updated_parsed', 'created_parsed']:
        struct_time = entry.get(field)
        if struct_time:
            try:
                return datetime.fromtimestamp(mktime(struct_time), tz=timezone.utc)
            except Exception:
                continue
    
    # Try string parsing
    for field in ['published', 'updated', 'created', 'date']:
        date_str = entry.get(field)
        if date_str:
            try:
                dt = dateutil_parser.parse(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                continue
    
    # Fallback to current time
    return datetime.now(timezone.utc)


def generate_guid(entry: dict, link: str, title: str) -> str:
    """Generate or extract unique identifier."""
    # Try existing ID/GUID
    for field in ['id', 'guid']:
        guid = entry.get(field)
        if guid:
            if isinstance(guid, dict):
                guid = guid.get('value', str(guid))
            return str(guid)
    
    # Fallback: use link
    if link:
        return link
    
    # Final fallback: hash of title
    return hashlib.md5((title or "").encode()).hexdigest()


def normalize_entry(
    entry: dict,
    source_name: str,
    language: str,
    tab: str,
    rss_category: str
) -> Optional[NormalizedArticle]:
    """
    Normalize a single feed entry.
    
    Args:
        entry: Raw feedparser entry
        source_name: Human-readable source name
        language: 'zh', 'en', or 'ja'
        tab: 'zh_news', 'zh_industry', 'en_news', 'ja_news'
        rss_category: Category from feeds.yaml
    
    Returns:
        NormalizedArticle or None if entry is invalid
    """
    # Extract and clean title
    title = strip_html(entry.get('title', ''))
    if not title:
        return None  # Skip entries without title
    
    # Extract and normalize link
    link = entry.get('link', '')
    if isinstance(link, list):
        link = link[0].get('href', '') if link else ''
    link = normalize_url(link)
    
    if not link:
        return None  # Skip entries without link
    
    # Parse datetime
    published = parse_datetime(entry)
    
    # Extract description
    description = strip_html(entry.get('summary', '') or entry.get('description', ''))
    if description:
        # Truncate to 500 chars while preserving words
        if len(description) > 500:
            description = description[:500].rsplit(' ', 1)[0] + '...'
    else:
        description = None
    
    # Generate GUID
    guid = generate_guid(entry, link, title)
    
    return NormalizedArticle(
        title=title,
        link=link,
        published=published,
        source_name=source_name,
        language=language,
        tab=tab,
        rss_category=rss_category,
        guid=guid,
        description=description,
        final_category=None  # Set later by classifier
    )
```

### `deduper.py`

```python
"""
Deduplicate normalized articles.
"""
import re
from typing import Optional

from .models import NormalizedArticle
from .normalizer import normalize_url


def normalize_title_for_comparison(title: str) -> str:
    """Normalize title for near-duplicate detection."""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def deduplicate(articles: list[NormalizedArticle]) -> list[NormalizedArticle]:
    """
    Remove duplicate articles.
    
    Deduplication strategy:
    1. Primary: GUID
    2. Secondary: Normalized URL
    3. Tertiary (optional): Similar titles from same source
    
    When duplicates found, keep the one with most recent published date.
    """
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
    
    # Stage 3: Deduplicate by title + source (optional, enabled by default)
    title_source_map: dict[str, NormalizedArticle] = {}
    for article in stage2_results:
        normalized_title = normalize_title_for_comparison(article.title)
        key = f"{normalized_title}|{article.source_name}"
        if key in title_source_map:
            # Keep the newer one
            if article.published > title_source_map[key].published:
                title_source_map[key] = article
        else:
            title_source_map[key] = article
    
    return list(title_source_map.values())
```

---

## 6. Expected Throughput

| Stage                      | Estimated Count (per run)      |
|----------------------------|-------------------------------|
| Total feeds                | ~35 (from feeds.yaml)         |
| Articles fetched (max)     | 35 × 20 = 700                 |
| After Stage 1 (GUID)       | ~600 (some GUID collisions)   |
| After Stage 2 (URL)        | ~550 (cross-feed URL dups)    |
| After Stage 3 (title)      | ~500 (same story, different time) |
| Final selection            | 20 (5 per tab × 4 tabs)       |

---

**Next Step**: Step 4 — Classification Rules
