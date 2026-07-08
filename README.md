# Daily Multilingual News Digest

A fully automated daily news digest system that aggregates RSS feeds from Chinese, English, and Japanese sources, generates AI-powered summaries, and delivers them via email and web.

## ✨ Features

- **4-Tab Multilingual Interface**: 中文新聞, 中文產業新聞, English News, 日本語ニュース
- **RSS-First Architecture**: No web scraping, 100% RSS/Atom feeds
- **AI Summarization**: NVIDIA NIM first, with Zeabur/Gemini/SiliconFlow/DeepSeek fallback
- **FT-Inspired Design**: Clean, editorial, professional layout
- **Dual Output**: Web (JS tabs) + Email (anchor-based navigation)
- **Automatic Scheduling**: Daily at 08:00 Asia/Taipei via GitHub Actions

## 📦 Project Structure

```
RssNews2/
├── .github/workflows/     # GitHub Actions workflow
├── config/                # RSS feeds & classification rules
├── src/                   # Python source code
├── templates/             # HTML templates
├── output/                # Generated digests
├── docs/                  # Step-by-step documentation
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

# 5. Run pipeline
python -m src.main

# 6. View output
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

## 📰 RSS Sources

### Chinese (中央通訊社 CNA)
- Politics, International, Technology, Social, Sports, Entertainment, Culture, Local

### English
- TechCrunch, Hacker News, The Verge, BBC News, Associated Press, Forbes

### Japanese (朝日新聞 + Yahoo Japan)
- Headlines, National, International, Business, Politics, Sports, Culture, Technology

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
