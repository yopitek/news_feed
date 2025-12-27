# Step 2: File / Repository Structure

## Complete Project Structure

```
RssNews2/
│
├── .github/
│   └── workflows/
│       └── daily_digest.yml          # GitHub Actions workflow (08:00 Asia/Taipei)
│
├── config/
│   ├── feeds.yaml                    # RSS source configuration (SINGLE SOURCE OF TRUTH)
│   └── classification_rules.yaml     # Chinese category mapping rules
│
├── src/
│   ├── __init__.py
│   │
│   ├── main.py                       # Pipeline orchestrator / entry point
│   │
│   ├── config_loader.py              # YAML configuration loading
│   │
│   ├── feed_fetcher.py               # RSS/Atom fetching with retry/timeout
│   │
│   ├── normalizer.py                 # Normalize feed entries to common schema
│   │
│   ├── deduper.py                    # Deduplication logic (GUID, URL, title)
│   │
│   ├── classifier.py                 # Chinese category classification
│   │
│   ├── selector.py                   # Select top N items per tab
│   │
│   ├── summarizer.py                 # DeepSeek API integration for summaries
│   │
│   ├── renderer_web.py               # Web HTML generation (JS tabs)
│   │
│   ├── renderer_email.py             # Email HTML generation (anchor-based)
│   │
│   ├── mailer.py                     # SMTP email sending
│   │
│   ├── logger.py                     # Structured logging utilities
│   │
│   └── models.py                     # Data classes / schemas
│
├── templates/
│   ├── web_template.html             # Jinja2 template for web version
│   └── email_template.html           # Jinja2 template for email version
│
├── output/                           # Generated outputs (gitignored except samples)
│   ├── .gitkeep
│   ├── web_digest.html               # Latest web digest
│   ├── email_digest.html             # Latest email digest
│   ├── run_log.jsonl                 # Execution log
│   ├── run_summary.json              # Run statistics
│   └── articles_data.json            # Debug: selected articles
│
├── docs/
│   ├── STEP1_SYSTEM_ARCHITECTURE.md  # Architecture documentation
│   ├── STEP2_FILE_STRUCTURE.md       # This file
│   ├── STEP3_RSS_NORMALIZATION.md    # RSS normalization & dedup logic
│   ├── STEP4_CLASSIFICATION.md       # Classification rules
│   ├── STEP5_DEEPSEEK_PROMPTS.md     # DeepSeek prompt design
│   ├── STEP6_HTML_TEMPLATES.md       # Template documentation
│   └── STEP7_GITHUB_ACTIONS.md       # Deployment guide
│
├── tests/
│   ├── __init__.py
│   ├── test_feed_fetcher.py
│   ├── test_normalizer.py
│   ├── test_deduper.py
│   ├── test_classifier.py
│   ├── test_summarizer.py
│   └── fixtures/
│       ├── sample_rss.xml            # Test RSS data
│       └── sample_atom.xml           # Test Atom data
│
├── .env.example                      # Example environment variables
├── .gitignore                        # Git ignore rules
├── requirements.txt                  # Python dependencies
├── requirements-dev.txt              # Development dependencies (pytest, etc.)
└── README.md                         # Project overview & quick start
```

---

## Module Responsibilities

### Core Modules (`src/`)

| Module               | Single Responsibility                                           |
|----------------------|----------------------------------------------------------------|
| `main.py`            | Pipeline orchestration: call modules in sequence, handle errors |
| `config_loader.py`   | Load and validate `feeds.yaml` and `classification_rules.yaml` |
| `feed_fetcher.py`    | Fetch RSS/Atom feeds with retry, timeout, error handling        |
| `normalizer.py`      | Convert raw feed entries to `NormalizedArticle` schema          |
| `deduper.py`         | Remove duplicate articles based on GUID/URL/title               |
| `classifier.py`      | Assign Chinese articles to predefined categories                |
| `selector.py`        | Pick top 5 most recent articles per tab                        |
| `summarizer.py`      | Generate summaries via DeepSeek API with fallback               |
| `renderer_web.py`    | Generate web HTML with real JavaScript tabs                     |
| `renderer_email.py`  | Generate email-safe HTML with anchor navigation                |
| `mailer.py`          | Send HTML email via SMTP                                        |
| `logger.py`          | Structured logging (JSON Lines format)                          |
| `models.py`          | Pydantic/dataclass models for type safety                       |

---

### Configuration Files (`config/`)

| File                        | Purpose                                           |
|-----------------------------|---------------------------------------------------|
| `feeds.yaml`                | RSS source URLs, tab assignments, category mappings |
| `classification_rules.yaml` | Keyword rules for Chinese category classification  |

---

### Templates (`templates/`)

| File                  | Purpose                                                |
|-----------------------|--------------------------------------------------------|
| `web_template.html`   | Jinja2 template with JS/CSS tabs, FT-inspired styling  |
| `email_template.html` | Email-safe HTML with anchor navigation, table layout   |

---

## Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              LAYER SEPARATION                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATION LAYER                                                             │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  main.py                                                                         │
│  - Reads config                                                                  │
│  - Calls modules in sequence                                                     │
│  - Handles top-level exceptions                                                  │
│  - Writes run summary                                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  DATA PROCESSING LAYER                                                           │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  feed_fetcher.py → normalizer.py → deduper.py → classifier.py → selector.py    │
│  - Pure data transformations                                                     │
│  - No side effects except logging                                                │
│  - Easily testable in isolation                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  EXTERNAL API LAYER                                                              │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  summarizer.py                                                                   │
│  - Interacts with DeepSeek API                                                   │
│  - Handles rate limits, retries, fallbacks                                       │
│  - Isolated for easy mocking in tests                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  OUTPUT LAYER                                                                    │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  renderer_web.py  │  renderer_email.py  │  mailer.py                            │
│  - Template rendering                                                            │
│  - File I/O (write HTML)                                                         │
│  - SMTP communication                                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  CROSS-CUTTING CONCERNS                                                          │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  config_loader.py  │  logger.py  │  models.py                                   │
│  - Used by all layers                                                            │
│  - No business logic                                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Interface Contracts (Key Functions)

### `config_loader.py`
```python
def load_feeds_config(path: str = "config/feeds.yaml") -> FeedsConfig:
    """Load and validate RSS feed configuration."""

def load_classification_rules(path: str = "config/classification_rules.yaml") -> ClassificationRules:
    """Load Chinese category classification rules."""
```

### `feed_fetcher.py`
```python
def fetch_feed(url: str, timeout: int = 10, retries: int = 2) -> list[RawFeedEntry]:
    """Fetch a single RSS/Atom feed. Returns empty list on failure."""

def fetch_all_feeds(config: FeedsConfig) -> dict[str, list[RawFeedEntry]]:
    """Fetch all feeds organized by tab. Keys: 'zh_news', 'zh_industry', 'en_news', 'ja_news'"""
```

### `normalizer.py`
```python
def normalize_entry(raw: RawFeedEntry, source_name: str, language: str, rss_category: str) -> NormalizedArticle:
    """Convert raw feed entry to normalized schema."""

def normalize_all(raw_feeds: dict[str, list[RawFeedEntry]], config: FeedsConfig) -> list[NormalizedArticle]:
    """Normalize all raw entries from all feeds."""
```

### `deduper.py`
```python
def deduplicate(articles: list[NormalizedArticle]) -> list[NormalizedArticle]:
    """Remove duplicates. Keep most recent by published date."""
```

### `classifier.py`
```python
def classify_chinese(article: NormalizedArticle, rules: ClassificationRules) -> str:
    """Return final category for Chinese article. Uses RSS category + keyword fallback."""
```

### `selector.py`
```python
def select_top_n(articles: list[NormalizedArticle], n: int = 5) -> dict[str, list[NormalizedArticle]]:
    """Select top N articles per tab, sorted by published date (newest first)."""
```

### `summarizer.py`
```python
def summarize_article(article: NormalizedArticle, api_key: str) -> str:
    """Generate summary using DeepSeek API. Handles fallback internally."""

def summarize_all(articles: dict[str, list[NormalizedArticle]], api_key: str) -> dict[str, list[ArticleWithSummary]]:
    """Summarize all selected articles, organized by tab."""
```

### `renderer_web.py`
```python
def render_web(articles: dict[str, list[ArticleWithSummary]], date_str: str) -> str:
    """Render web HTML with JavaScript tabs."""
```

### `renderer_email.py`
```python
def render_email(articles: dict[str, list[ArticleWithSummary]], date_str: str) -> str:
    """Render email-safe HTML with anchor navigation."""
```

### `mailer.py`
```python
def send_email(html_content: str, subject: str, recipient: str, smtp_config: SMTPConfig) -> bool:
    """Send HTML email via SMTP. Returns True on success."""
```

---

## Data Models (`models.py`)

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class RawFeedEntry:
    """Raw entry directly from feedparser."""
    title: str
    link: str
    published: Optional[str]  # Raw string, to be parsed
    summary: Optional[str]
    guid: Optional[str]
    source_feed_url: str

@dataclass
class NormalizedArticle:
    """Normalized article with consistent schema."""
    title: str
    link: str
    published: datetime
    source_name: str
    language: str  # 'zh', 'en', 'ja'
    tab: str  # 'zh_news', 'zh_industry', 'en_news', 'ja_news'
    rss_category: str
    final_category: Optional[str]  # Only for Chinese
    guid: str  # GUID or URL hash
    description: Optional[str]

@dataclass
class ArticleWithSummary:
    """Article with generated or extracted summary."""
    title: str
    link: str
    published: datetime
    source_name: str
    summary: str  # Generated or RSS description
    tab: str
    final_category: Optional[str]
```

---

## Git Ignore Rules

```gitignore
# Output files (regenerated on each run)
output/*.html
output/*.json
output/*.jsonl
!output/.gitkeep

# Environment
.env
*.env
venv/
.venv/

# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

**Next Step**: Step 3 — RSS Normalization & Deduplication Logic
