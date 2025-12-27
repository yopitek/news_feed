# System Architecture

## 1. High-Level Flow
Scheduler (08:00 Asia/Taipei) →
Fetch RSS/Atom →
Normalize →
Deduplicate →
Classify/Map →
Select Top 5 per Category →
Summarize/Excerpt →
Render (Web + Email) →
Send Email

## 2. Core Modules
- feed_fetcher: Fetch & parse RSS/Atom with retry/timeouts
- normalizer: Normalize fields (title, link, published, source, language)
- deduper: Deduplicate across feeds (GUID/URL/title similarity)
- classifier:
  - RSS category mapping (primary)
  - Keyword rules (fallback)
  - Optional LLM classification (opt-in)
- summarizer: DeepSeek summaries (Chinese); excerpt rules (EN/JA)
- renderer_web: 4-tab web HTML (or Next.js)
- renderer_email: anchor navigation email HTML (FT-inspired)
- mailer: SMTP send (Gmail App Password or other provider)
- logging: structured logs + daily run report

## 3. Deduplication Strategy
- Primary identifier:
  - RSS GUID if present
  - else canonical URL
- Secondary:
  - normalized title + source
  - fuzzy match for near-duplicates (optional)
- Window:
  - dedupe within last 24h (or current run scope for MVP)

## 4. Classification Strategy
- v1:
  - Use feed-defined category as the category bucket
  - For Chinese “產經/股市/房市” refinement, add keyword rules
- v2:
  - Optional LLM classification for ambiguous cases

## 5. Error Handling & Degradation
- Feed fetch fails:
  - log error, skip feed
- Parse fails:
  - log and continue (do not fail entire run)
- Summary API fails:
  - Chinese: fallback to RSS description truncated to 150 chars
  - EN/JA: fallback to RSS description/excerpt truncated
- Email send fails:
  - save rendered HTML to artifact storage (repo artifact) for manual retrieval

## 6. Scheduling & Timezone
- GitHub Actions cron uses UTC.
- 08:00 Asia/Taipei = 00:00 UTC.
- Application should still stamp timestamps in Asia/Taipei.

## 7. Observability
- Write `run_log.jsonl` per run
- Output a concise summary:
  - feeds fetched count
  - articles ingested
  - deduped count
  - selected count
  - summary calls count
  - send status
