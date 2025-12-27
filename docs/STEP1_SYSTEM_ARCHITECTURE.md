# Step 1: System Architecture — Daily Multilingual News Digest

## 1. High-Level Architecture Diagram (Text)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         GitHub Actions Scheduler                                 │
│                         (Cron: 08:00 Asia/Taipei = 00:00 UTC)                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              MAIN PIPELINE                                       │
│                              (run_pipeline.py)                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Feed Fetcher │───▶│  Normalizer  │───▶│   Deduper    │───▶│  Classifier  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                                                            │          │
│         │                                                            ▼          │
│         │            ┌──────────────────────────────────────────────────────┐   │
│         │            │                   Selector                            │   │
│         │            │   (Pick top 5 items per category per tab)            │   │
│         │            └──────────────────────────────────────────────────────┘   │
│         │                                       │                               │
│         ▼                                       ▼                               │
│  ┌──────────────┐                     ┌──────────────────┐                      │
│  │ feeds.yaml   │                     │    Summarizer    │                      │
│  │ (RSS Config) │                     │ (DeepSeek API)   │                      │
│  └──────────────┘                     └──────────────────┘                      │
│                                                 │                               │
│                           ┌─────────────────────┴─────────────────────┐         │
│                           ▼                                           ▼         │
│                  ┌─────────────────┐                        ┌─────────────────┐ │
│                  │  Web Renderer   │                        │ Email Renderer  │ │
│                  │ (Real JS Tabs)  │                        │ (Anchor-based)  │ │
│                  └─────────────────┘                        └─────────────────┘ │
│                           │                                           │         │
│                           ▼                                           ▼         │
│                  ┌─────────────────┐                        ┌─────────────────┐ │
│                  │  output/        │                        │     Mailer      │ │
│                  │  web_digest.html│                        │    (SMTP)       │ │
│                  └─────────────────┘                        └─────────────────┘ │
│                                                                       │         │
└───────────────────────────────────────────────────────────────────────┼─────────┘
                                                                        │
                                                                        ▼
                                                               ┌─────────────────┐
                                                               │  Email Inbox    │
                                                               │  (Recipient)    │
                                                               └─────────────────┘
```

---

## 2. Detailed Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW SEQUENCE                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

  [Step 1] FETCH
  ─────────────────────────────────────────────────────────────────────────────────
  Input:   feeds.yaml (RSS source configuration)
  Process: Iterate each tab → each source → HTTP GET with timeout/retry
  Output:  List[RawFeedEntry] per feed
  
  ─────────────────────────────────────────────────────────────────────────────────

  [Step 2] NORMALIZE
  ─────────────────────────────────────────────────────────────────────────────────
  Input:   RawFeedEntry (varying RSS/Atom formats)
  Process: Extract & normalize fields:
           - title (strip HTML)
           - link (canonical URL)
           - published (parse to datetime, fallback to now)
           - source_name (from feed metadata)
           - description/summary (if available)
           - language (zh/en/ja, determined by tab)
           - rss_category (from feed config)
           - guid (unique identifier)
  Output:  List[NormalizedArticle]
  
  ─────────────────────────────────────────────────────────────────────────────────

  [Step 3] DEDUPLICATE
  ─────────────────────────────────────────────────────────────────────────────────
  Input:   List[NormalizedArticle] (all articles from all feeds)
  Process: - Primary key: guid or canonical URL
           - Secondary key: normalized_title + source_name (for near-dups)
           - Keep most recent if duplicates found
           - Window: current run scope (24h lookback optional in v2)
  Output:  List[NormalizedArticle] (deduplicated)
  
  ─────────────────────────────────────────────────────────────────────────────────

  [Step 4] CLASSIFY (Chinese only)
  ─────────────────────────────────────────────────────────────────────────────────
  Input:   NormalizedArticle (Chinese articles only)
  Process: - Use RSS-defined category as primary (from feed config)
           - Keyword fallback for ambiguous cases
           - Optional LLM classification if deterministic fails
  Output:  NormalizedArticle with final_category
  
  Target Categories (Chinese):
  ┌────────────────────────────────────────────────┐
  │  頭條新聞 | 產經 | 股市 | 全球國際新聞       │
  │  社會 | 生活 | 娛樂 | 運動 | 房市             │
  └────────────────────────────────────────────────┘
  
  ─────────────────────────────────────────────────────────────────────────────────

  [Step 5] SELECT
  ─────────────────────────────────────────────────────────────────────────────────
  Input:   List[NormalizedArticle] per tab
  Process: - Group by tab
           - Sort by published datetime (descending)
           - Pick top 5 items per tab
  Output:  Dict[TabName, List[5 NormalizedArticle]]
  
  Tab Distribution:
  ┌────────────────────────────────────────────────┐
  │  中文新聞         → 5 items                    │
  │  中文產業新聞     → 5 items                    │
  │  English News     → 5 items                    │
  │  日本語ニュース   → 5 items                    │
  └────────────────────────────────────────────────┘
  
  ─────────────────────────────────────────────────────────────────────────────────

  [Step 6] SUMMARIZE
  ─────────────────────────────────────────────────────────────────────────────────
  Input:   Selected articles per tab
  Process: 
           ┌─────────────────────────────────────────────────────────────────────┐
           │ CHINESE (中文新聞 + 中文產業新聞):                                 │
           │   - Use DeepSeek API to generate ~150 char summary                 │
           │   - Tone: neutral, professional, news-style                        │
           │   - No opinion, no emojis, no exaggeration                         │
           │   - Fallback: RSS description truncated to 150 chars               │
           ├─────────────────────────────────────────────────────────────────────┤
           │ ENGLISH (English News):                                             │
           │   - DO NOT translate                                                │
           │   - If RSS summary exists: clean truncate                           │
           │   - If missing: generate ~150-word English summary via DeepSeek     │
           ├─────────────────────────────────────────────────────────────────────┤
           │ JAPANESE (日本語ニュース):                                          │
           │   - DO NOT translate                                                │
           │   - If RSS summary exists: clean truncate                           │
           │   - If missing: generate ~150-char Japanese summary via DeepSeek   │
           └─────────────────────────────────────────────────────────────────────┘
  Output:  List[ArticleWithSummary] per tab
  
  ─────────────────────────────────────────────────────────────────────────────────

  [Step 7] RENDER
  ─────────────────────────────────────────────────────────────────────────────────
  Input:   All summarized articles organized by tab
  Process: 
           ┌─────────────────────────────────────────────────────────────────────┐
           │ WEB RENDERER:                                                        │
           │   - Real JS/CSS tabs (4 tabs)                                        │
           │   - FT-inspired styling (serif headlines, muted colors)             │
           │   - Responsive layout                                                │
           │   - Output: output/web_digest.html                                   │
           ├─────────────────────────────────────────────────────────────────────┤
           │ EMAIL RENDERER:                                                      │
           │   - Anchor-based navigation (NO JS/CSS tabs)                        │
           │   - Email-safe table layout                                          │
           │   - FT-inspired styling within email constraints                     │
           │   - Output: output/email_digest.html                                 │
           └─────────────────────────────────────────────────────────────────────┘
  Output:  HTML files for web and email
  
  ─────────────────────────────────────────────────────────────────────────────────

  [Step 8] SEND EMAIL
  ─────────────────────────────────────────────────────────────────────────────────
  Input:   Email-rendered HTML
  Process: - SMTP connection (Gmail App Password or other provider)
           - Configure From/To/Subject
           - Send as HTML email
           - Log success/failure
  Output:  Email delivered to recipient inbox

```

---

## 3. Failure Handling Strategy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          FAILURE HANDLING MATRIX                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┬─────────────────────────────────┬─────────────────────────┐
│      FAILURE         │         HANDLING                │      RESULT             │
├──────────────────────┼─────────────────────────────────┼─────────────────────────┤
│ RSS Feed Timeout     │ Retry 2x with backoff           │ Skip feed if all fail   │
│ (single feed)        │ Log warning                     │ Pipeline continues      │
├──────────────────────┼─────────────────────────────────┼─────────────────────────┤
│ RSS Parse Error      │ Log error with feed URL         │ Skip malformed entry    │
│ (malformed entry)    │ Continue with valid entries     │ Pipeline continues      │
├──────────────────────┼─────────────────────────────────┼─────────────────────────┤
│ All Feeds Fail       │ Log critical error              │ Send alert, no digest   │
│ (complete blackout)  │ Exit with non-zero status       │ GH Actions shows fail   │
├──────────────────────┼─────────────────────────────────┼─────────────────────────┤
│ DeepSeek API Error   │ CHINESE: Use RSS desc (150ch)   │ Degraded summary        │
│ (summarization)      │ EN/JA: Use RSS desc or title    │ Pipeline continues      │
├──────────────────────┼─────────────────────────────────┼─────────────────────────┤
│ DeepSeek Rate Limit  │ Wait & retry (exponential)      │ Delay, then continue    │
│                      │ After 3 attempts → fallback     │ Use fallback summary    │
├──────────────────────┼─────────────────────────────────┼─────────────────────────┤
│ < 5 Items for Tab    │ Use available items             │ Partial tab content     │
│                      │ Log warning                     │ Still render & send     │
├──────────────────────┼─────────────────────────────────┼─────────────────────────┤
│ Render Failure       │ Log error                       │ Exit non-zero           │
│ (template error)     │ Save raw data JSON as artifact  │ Debug via artifacts     │
├──────────────────────┼─────────────────────────────────┼─────────────────────────┤
│ SMTP Auth Failure    │ Log error with masked creds     │ Save HTML as artifact   │
│                      │ Exit non-zero                   │ Manual send possible    │
├──────────────────────┼─────────────────────────────────┼─────────────────────────┤
│ Email Send Failure   │ Retry once                      │ Save HTML as artifact   │
│ (network issue)      │ Log error                       │ Exit non-zero           │
└──────────────────────┴─────────────────────────────────┴─────────────────────────┘

```

---

## 4. Module Dependency Graph

```
                              ┌─────────────────┐
                              │   run_pipeline  │
                              │     (main.py)   │
                              └────────┬────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             ▼                             ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  config_loader  │         │   feed_fetcher  │         │     logger      │
│  (feeds.yaml)   │         │                 │         │  (run_log.jsonl)│
└────────┬────────┘         └────────┬────────┘         └─────────────────┘
         │                           │
         │                           ▼
         │                  ┌─────────────────┐
         │                  │   normalizer    │
         │                  └────────┬────────┘
         │                           │
         │                           ▼
         │                  ┌─────────────────┐
         │                  │     deduper     │
         │                  └────────┬────────┘
         │                           │
         │                           ▼
         │                  ┌─────────────────┐
         │                  │   classifier    │
         │                  │ (zh categories) │
         │                  └────────┬────────┘
         │                           │
         │                           ▼
         │                  ┌─────────────────┐
         │                  │    selector     │
         │                  │ (top 5 per tab) │
         │                  └────────┬────────┘
         │                           │
         │                           ▼
         │                  ┌─────────────────┐
         └─────────────────▶│   summarizer    │◀──────── DeepSeek API
                            │                 │
                            └────────┬────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              │                                              │
              ▼                                              ▼
     ┌─────────────────┐                           ┌─────────────────┐
     │  renderer_web   │                           │ renderer_email  │
     │ (JS tabs HTML)  │                           │ (anchor HTML)   │
     └────────┬────────┘                           └────────┬────────┘
              │                                              │
              ▼                                              ▼
     ┌─────────────────┐                           ┌─────────────────┐
     │ output/web.html │                           │     mailer      │──────▶ SMTP
     └─────────────────┘                           │                 │
                                                   └─────────────────┘

```

---

## 5. Technology Stack

| Component           | Technology                          | Notes                                    |
|---------------------|-------------------------------------|------------------------------------------|
| **Language**        | Python 3.11+                        | Modern async/await support               |
| **RSS Parsing**     | `feedparser`                        | Handles RSS/Atom/RDF                     |
| **HTTP Client**     | `requests` (sync) or `httpx` (async)| Timeouts, retries                        |
| **Date Parsing**    | `python-dateutil`                   | Robust datetime parsing                  |
| **Configuration**   | `PyYAML`                            | `feeds.yaml` loading                     |
| **Summarization**   | DeepSeek API                        | Chinese summaries mandatory              |
| **Template Engine** | Python string templates / Jinja2    | HTML generation                          |
| **Scheduling**      | GitHub Actions                      | Cron at 00:00 UTC (08:00 Taipei)         |
| **Email**           | `smtplib` + `email.mime`            | Built-in Python libraries                |
| **Logging**         | Python `logging` + JSON Lines       | Structured observability                 |

---

## 6. Security Considerations

| Secret                | Storage                        | Usage                              |
|-----------------------|--------------------------------|------------------------------------|
| `DEEPSEEK_API_KEY`    | GitHub Secrets                 | Summarization API authentication   |
| `SMTP_HOST`           | GitHub Secrets                 | Email server hostname              |
| `SMTP_PORT`           | GitHub Secrets                 | Email server port (465/587)        |
| `SMTP_USER`           | GitHub Secrets                 | Email sender address               |
| `SMTP_PASSWORD`       | GitHub Secrets                 | App password (not main password)   |
| `EMAIL_RECIPIENT`     | GitHub Secrets                 | Digest delivery address            |

⚠️ **Never log or print secrets. Use masked output in logs.**

---

## 7. Observability & Logging

Each pipeline run generates:

1. **`run_log.jsonl`** — Structured JSON Lines log:
   ```jsonl
   {"ts":"2025-12-26T08:00:00+08:00","level":"INFO","module":"fetcher","msg":"Fetched 12 items from CNA politics"}
   {"ts":"2025-12-26T08:00:01+08:00","level":"WARN","module":"fetcher","msg":"Timeout on Asahi sports feed, skipping"}
   {"ts":"2025-12-26T08:00:05+08:00","level":"INFO","module":"summarizer","msg":"Generated 20 summaries via DeepSeek"}
   ```

2. **`run_summary.json`** — Final run metrics:
   ```json
   {
     "run_date": "2025-12-26",
     "feeds_attempted": 30,
     "feeds_succeeded": 28,
     "feeds_failed": 2,
     "articles_fetched": 450,
     "articles_after_dedup": 380,
     "articles_selected": 20,
     "summaries_generated": 20,
     "email_sent": true,
     "duration_seconds": 45.2
   }
   ```

---

## 8. Output Artifacts

```
output/
├── web_digest.html          # Web version with JS tabs
├── email_digest.html        # Email version with anchor navigation
├── run_log.jsonl            # Detailed execution log
├── run_summary.json         # Run statistics
└── articles_data.json       # Raw selected articles (for debugging)
```

---

## 9. Timezone Handling

- **Execution**: GitHub Actions cron runs at UTC
- **08:00 Asia/Taipei = 00:00 UTC** (no DST in Taiwan)
- **Display**: All timestamps in digest display as `Asia/Taipei`
- **Sorting**: Use UTC internally, convert for display

---

## 10. Scalability Notes (Future)

| Current (MVP)                | Future Enhancement                         |
|------------------------------|-------------------------------------------|
| Synchronous RSS fetching     | Async fetching with `asyncio` + `httpx`   |
| In-memory deduplication      | Redis/SQLite for cross-run dedup          |
| Single recipient email       | Distribution list support                 |
| Static HTML output           | GitHub Pages auto-deploy                  |
| GitHub Actions only          | Self-hosted runner option                 |

---

**Next Step**: Step 2 — File / Repo Structure
