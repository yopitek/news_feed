# Daily Multilingual News Digest – PRD

## 1. Product Overview
A daily multilingual news digest system that aggregates RSS feeds, classifies content, generates summaries, and delivers the result via:
1) Web version (with 4 tabs)
2) Email version (anchor-based navigation)

Delivery time: Every day at 08:00 (Asia/Taipei).

## 2. Target Users
- Primary: Single user (owner)
- Future extensibility: Multiple subscribers

## 3. Core Features
### 3.1 Tabs
1. Chinese News
2. Chinese Industry News
3. English News (original language)
4. Japanese News (original language)

### 3.2 Content Rules
- Each category outputs 5 news items.
- Each item includes:
  - Title
  - Source
  - Published time
  - Summary (~150 characters for Chinese; original-language excerpt for EN/JA)
  - Original link

### 3.3 Language Rules
- Chinese: Summary generated in Traditional Chinese.
- English: Original English output (no translation).
- Japanese: Original Japanese output (no translation).

### 3.4 Style
- Financial Times–inspired layout:
  - Neutral background
  - Serif-like typography
  - Section-based layout
  - Minimal decoration

## 4. Functional Requirements
- RSS-first ingestion
- Deduplication across feeds
- Category mapping & classification
- Summary generation via DeepSeek API
- HTML rendering for Web & Email
- Scheduled execution via cron (GitHub Actions)

## 5. Non-Functional Requirements
- Reliability: RSS fetch retry & graceful degradation
- Maintainability: Feed definitions configurable via YAML
- Cost control: Summarize only selected items
- Email compatibility: No JS, conservative CSS
- Observability: Logs for fetch, classify, summarize, send

## 6. Out of Scope (v1)
- Real-time updates
- User personalization
- Push notifications
- Full-text crawling (RSS-first by design)
