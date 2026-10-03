# Daily Multilingual News Digest

A fully automated daily news digest system that aggregates RSS feeds from Chinese, English, and Japanese sources, generates AI-powered summaries, and delivers them via email and web.

## ✨ Features

- **6-Tab Multilingual Interface**: 中文新聞, English News, 日本語ニュース, Tech Blogs, PTT 熱門, Dcard 熱門
- **RSS-First Architecture**: mostly RSS/Atom feeds, plus two dedicated collectors for community sources
- **Engagement-Ranked Community Tabs**: PTT ranked by 推文數, Dcard ranked by 愛心數
- **AI Summarization**: NVIDIA NIM first, with Zeabur/Gemini/SiliconFlow/DeepSeek fallback
- **FT-Inspired Design**: Clean, editorial, professional layout
- **Dual Output**: Web (JS tabs) + Email (anchor-based navigation)
- **Automatic Scheduling**: Daily at 08:00 Asia/Taipei via GitHub Actions

## 📦 Project Structure

```
RssNews2/
├── .github/workflows/     # GitHub Actions workflow
├── config/                # RSS feeds & classification rules
├── data/                  # Committed snapshots (Dcard)
├── src/                   # Python source code
├── templates/             # HTML templates
├── tools/                 # Local collectors (run on your own machine)
├── output/                # Generated digests
├── docs/                  # Step-by-step documentation + published site
└── tests/                 # Test suite
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- NVIDIA API key from https://build.nvidia.com
- SMTP credentials (for email delivery)

### Local Development

```bash
# 1. Clone repository
git clone <your-repo-url>
cd RssNews2

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
export NVIDIA_API_KEY="nvapi-your-api-key"
export DEBUG_MODE="true"

# 5. Refresh the Dcard snapshot (see "Community tabs" below)
python3 tools/collect_dcard.py

# 6. Run pipeline
python -m src.main

# 7. View output
open output/web_digest.html
```

### Deploy to GitHub Actions

1. Push code to GitHub
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Add the following secrets:

| Secret             | Description                     |
|--------------------|---------------------------------|
| `NVIDIA_API_KEY` | NVIDIA NIM API key              |
| `SMTP_HOST`        | SMTP server (e.g., smtp.gmail.com) |
| `SMTP_PORT`        | SMTP port (465 for SSL)         |
| `SMTP_USER`        | Sender email address            |
| `SMTP_PASSWORD`    | App password (not main password)|
| `EMAIL_RECIPIENT`  | Recipient email address         |

4. The workflow runs automatically at **08:00 Asia/Taipei** (00:00 UTC)
5. Manual trigger available via Actions tab

## 📰 Sources

### Chinese (中央通訊社 CNA)
- Politics, International, Technology, Social, Sports, Entertainment, Culture, Local

### English
- TechCrunch, Hacker News, The Verge, BBC News, Associated Press, Forbes

### Japanese (朝日新聞 + Yahoo Japan)
- Headlines, National, International, Business, Politics, Sports, Culture, Technology

### Tech Blogs
18 first-party engineering blogs (AI/ML, Software Engineering, Security, Startups, Commentary)

### PTT 熱門 (`ptt_hot`)
Board index pages, ranked by 推文數:

| Section | Board | URL |
|---------|-------|-----|
| 八卦板 | Gossiping | `ptt.cc/bbs/Gossiping/index.html` |
| 股票板 | Stock | `ptt.cc/bbs/Stock/index.html` |
| 科技業板 | Tech_Job | `ptt.cc/bbs/Tech_Job/index.html` |
| 軟體工作板 | Soft_Job | `ptt.cc/bbs/Soft_Job/index.html` |
| 電蝦板 | PC_Shopping | `ptt.cc/bbs/PC_Shopping/index.html` |

Each board falls back to its official Atom feed (`ptt.cc/atom/<Board>.xml`) when the
index page cannot be parsed — the fallback carries no push count, so those rows
render without a 推 badge. `ptt.cc/robots.txt` returns 404 (no robots policy is
published) and PTT publishes no AI-crawler directives; requests are rate-limited to
one page per board with a delay between boards.

Two kinds of row are dropped before ranking: the pinned (置底) block after
`<div class="r-list-sep">`, and `[公告]` titles. Both are moderator notices that
would otherwise dominate a push-ranked list. Only `index.html` is fetched — measured
on 2026-10-03, PTT pages ≥ 2 are a 熱門文章 archive rather than a chronological
continuation (Stock page 2 spanned Aug–Sep, PC_Shopping's reached back to 2025-10).

### Dcard 熱門 (`dcard_hot`)
Fed from a committed snapshot, ranked by 愛心數:

| Section | Board | URL |
|---------|-------|-----|
| 科技業板 | tech_job | `dcard.tw/f/tech_job` |
| AI 工作者板 | ai_builder | `dcard.tw/f/ai_builder` |
| 3C 板 | 3c | `dcard.tw/f/3c` |
| 理財板 | money | `dcard.tw/f/money` |

## 🧩 Community tabs

Community sources need more than `feedparser`, so `config/feeds.yaml` sources carry a
`type` field:

| `type` | Collector | Runs where |
|--------|-----------|------------|
| `rss` (default) | `src/feed_fetcher.fetch_feed` | anywhere |
| `ptt_list` | `src/ptt_fetcher.fetch_ptt_board` | anywhere (incl. CI) |
| `dcard_snapshot` | `src/snapshot_loader.load_dcard_board` | anywhere, reads a committed file |

### Why Dcard needs a local collector

Dcard sits behind Cloudflare. Server-side requests — `curl`, `urllib` with browser-like
headers, and `curl_cffi` with a Chrome TLS fingerprint — all end at HTTP 403 with a
Turnstile challenge, so the Actions runner cannot read Dcard. Dcard's `robots.txt`
only disallows `/emails/activate` and the site publishes no AI-crawler policy, so
reading the public board listings from a real browser is compliant.

The operator therefore collects on their own machine with Brave and commits a JSON
snapshot that CI reads and renders:

```bash
# Collect (requires the `bsk` CLI + a connected Brave browser)
python3 tools/collect_dcard.py

# Options
python3 tools/collect_dcard.py --dry-run                  # inspect, write nothing
python3 tools/collect_dcard.py --session <id>             # reuse an open session
python3 tools/collect_dcard.py --boards tech_job,money    # subset
python3 tools/collect_dcard.py --limit 30                 # posts per board
```

The script refuses to overwrite a non-empty snapshot with an empty one, so a
Cloudflare hiccup cannot silently blank the tab. The Dcard tab always shows the
snapshot timestamp and flags data older than 48 hours.

**Daily schedule on macOS** (runs 30 minutes before the 08:00 digest):

```bash
crontab -e
# refresh the Dcard snapshot, then push so Actions picks it up
30 7 * * * cd /path/to/news_feed && /usr/bin/python3 tools/collect_dcard.py && git add data/dcard_latest.json && git commit -m "chore: refresh Dcard snapshot" && git push
```

### Ranking & time window

`ptt_hot` and `dcard_hot` are ordered by engagement (`src/selector.TAB_SORT_METRIC`)
rather than recency, and the 24-hour recency window is disabled for them via
`settings.tab_time_window_hours` — a board's front page is already bounded by the
site, and a 24h cutoff would silently drop the highest-ranked posts.

## 🎨 Design Philosophy

Following **Financial Times–style aesthetics**:
- Serif headlines (Georgia)
- Muted color palette (off-white, dark text)
- Clean editorial layout
- No modern card UI or excessive gradients
- Clear section dividers

## 📊 Output Tab Requirements

| Tab               | Items | Summary                          |
|-------------------|-------|----------------------------------|
| 中文新聞          | 5     | AI-generated ~150 Chinese chars  |
| 中文產業新聞      | 5     | AI-generated ~150 Chinese chars  |
| English News      | 5     | RSS summary or ~150 words        |
| 日本語ニュース    | 5     | RSS summary or ~150 chars        |

## 🔧 Configuration

### `config/feeds.yaml`
Define RSS sources, categories, and tab assignments.

### `config/classification_rules.yaml`
Chinese article classification rules with keyword-based categorization.

## 📖 Documentation

Detailed implementation docs in `docs/`:

1. **STEP1_SYSTEM_ARCHITECTURE.md** - High-level architecture
2. **STEP2_FILE_STRUCTURE.md** - Repository structure
3. **STEP3_RSS_NORMALIZATION.md** - RSS parsing & deduplication
4. **STEP4_CLASSIFICATION.md** - Chinese category rules
5. **STEP5_DEEPSEEK_PROMPTS.md** - AI summarization prompts and provider fallback notes
6. **STEP6_HTML_TEMPLATES.md** - Web & email templates
7. **STEP7_GITHUB_ACTIONS.md** - Deployment guide

## 🛡️ Error Handling

- **Feed timeout**: Retry with exponential backoff, skip on failure
- **API rate limit**: Wait and retry, fallback to RSS description
- **Email failure**: Save HTML as artifact for manual retrieval
- **Missing content**: Graceful degradation with available articles

## 📄 License

MIT License

---

Built with ❤️ for daily news consumption
