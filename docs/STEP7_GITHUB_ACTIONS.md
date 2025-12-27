# Step 7: GitHub Actions Workflow

## 1. Workflow Configuration

### File: `.github/workflows/daily_digest.yml`

```yaml
name: Daily Multilingual News Digest

on:
  # Scheduled run at 08:00 Asia/Taipei = 00:00 UTC
  schedule:
    - cron: '0 0 * * *'
  
  # Manual trigger for testing
  workflow_dispatch:
    inputs:
      skip_email:
        description: 'Skip sending email (for testing)'
        required: false
        default: 'false'
        type: boolean
      debug_mode:
        description: 'Enable debug logging'
        required: false
        default: 'false'
        type: boolean

# Prevent concurrent runs
concurrency:
  group: daily-digest
  cancel-in-progress: false

jobs:
  generate-digest:
    name: Generate and Send Digest
    runs-on: ubuntu-latest
    timeout-minutes: 15
    
    permissions:
      contents: write  # For uploading artifacts to repo
    
    steps:
      # ============================================
      # Setup
      # ============================================
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      # ============================================
      # Generate Digest
      # ============================================
      - name: Run digest pipeline
        id: generate
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          DEBUG_MODE: ${{ inputs.debug_mode || 'false' }}
          TZ: Asia/Taipei
        run: |
          python -m src.main
          echo "digest_generated=true" >> $GITHUB_OUTPUT
      
      # ============================================
      # Send Email
      # ============================================
      - name: Send email digest
        if: ${{ steps.generate.outputs.digest_generated == 'true' && inputs.skip_email != 'true' }}
        env:
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          EMAIL_RECIPIENT: ${{ secrets.EMAIL_RECIPIENT }}
          EMAIL_SUBJECT_PREFIX: '[News Digest]'
        run: |
          python -c "
          from src.mailer import send_digest_email
          send_digest_email()
          "
      
      # ============================================
      # Upload Artifacts
      # ============================================
      - name: Upload output artifacts
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: digest-output-${{ github.run_number }}
          path: |
            output/web_digest.html
            output/email_digest.html
            output/run_log.jsonl
            output/run_summary.json
            output/articles_data.json
          retention-days: 30
      
      # ============================================
      # Error Notification (Optional)
      # ============================================
      - name: Notify on failure
        if: failure()
        env:
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          EMAIL_RECIPIENT: ${{ secrets.EMAIL_RECIPIENT }}
        run: |
          python -c "
          from src.mailer import send_error_notification
          send_error_notification('${{ github.run_id }}', '${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}')
          "
```

---

## 2. Environment Variables & Secrets

### Required GitHub Secrets

| Secret Name          | Description                                  | Example                          |
|----------------------|----------------------------------------------|----------------------------------|
| `DEEPSEEK_API_KEY`   | DeepSeek API authentication key              | `sk-xxxxxxxxxxxxxxxx`            |
| `SMTP_HOST`          | SMTP server hostname                         | `smtp.gmail.com`                 |
| `SMTP_PORT`          | SMTP server port                             | `465` (SSL) or `587` (TLS)       |
| `SMTP_USER`          | SMTP username (email address)                | `yourname@gmail.com`             |
| `SMTP_PASSWORD`      | SMTP password (app password, not main)       | `xxxx xxxx xxxx xxxx`            |
| `EMAIL_RECIPIENT`    | Digest recipient email address               | `recipient@example.com`          |

### Setting Up GitHub Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with its name and value

### Gmail App Password Setup

For Gmail SMTP, you **must** use an App Password (not your main password):

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Go to **App passwords** (under 2-Step Verification)
4. Select app: **Mail**, device: **Other (Custom name)** → e.g., "News Digest"
5. Copy the 16-character password → use as `SMTP_PASSWORD`

---

## 3. Timezone Configuration

### Schedule Cron Expression

```yaml
# 08:00 Asia/Taipei = 00:00 UTC (Taiwan has no DST)
schedule:
  - cron: '0 0 * * *'
```

### Timezone Reference

| Timezone       | UTC Offset | 08:00 Local = UTC |
|----------------|------------|-------------------|
| Asia/Taipei    | +8         | 00:00             |
| Asia/Tokyo     | +9         | 23:00 (prev day)  |
| America/LA     | -8 (PST)   | 16:00             |
| Europe/London  | +0 (GMT)   | 08:00             |

### In-Code Timezone Handling

```python
import pytz
from datetime import datetime

TAIPEI_TZ = pytz.timezone('Asia/Taipei')

def get_taipei_now():
    """Get current time in Taipei timezone."""
    return datetime.now(TAIPEI_TZ)

def format_taipei_date(dt):
    """Format datetime for display in Taipei timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    taipei_dt = dt.astimezone(TAIPEI_TZ)
    return taipei_dt.strftime("%Y年%m月%d日")
```

---

## 4. Error Notification Strategy

### Email Notification on Failure

```python
# src/mailer.py

def send_error_notification(run_id: str, run_url: str) -> bool:
    """
    Send error notification email when pipeline fails.
    """
    import os
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from datetime import datetime
    import pytz
    
    # Load config from environment
    smtp_host = os.environ.get('SMTP_HOST')
    smtp_port = int(os.environ.get('SMTP_PORT', 465))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    recipient = os.environ.get('EMAIL_RECIPIENT')
    
    if not all([smtp_host, smtp_user, smtp_password, recipient]):
        print("Error notification: Missing SMTP configuration")
        return False
    
    # Generate timestamp
    taipei_tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(taipei_tz)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # Compose email
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'[News Digest] Pipeline Failed - {now.strftime("%Y-%m-%d")}'
    msg['From'] = smtp_user
    msg['To'] = recipient
    
    text_content = f"""
News Digest Pipeline Failed

Time: {timestamp} (Asia/Taipei)
Run ID: {run_id}
Details: {run_url}

Please check the GitHub Actions logs for details.
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; background: #f3efe6; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: #fff; border: 1px solid #e6e1d6; padding: 24px;">
        <h2 style="color: #c00; margin-top: 0;">⚠️ Pipeline Failed</h2>
        <p><strong>Time:</strong> {timestamp} (Asia/Taipei)</p>
        <p><strong>Run ID:</strong> {run_id}</p>
        <p><a href="{run_url}" style="color: #0f5499;">View Details on GitHub</a></p>
        <hr style="border: none; border-top: 1px solid #e6e1d6;">
        <p style="font-size: 12px; color: #666;">Please check the GitHub Actions logs for error details.</p>
    </div>
</body>
</html>
"""
    
    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))
    
    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        
        print(f"Error notification sent to {recipient}")
        return True
        
    except Exception as e:
        print(f"Failed to send error notification: {e}")
        return False
```

---

## 5. Workflow Run Modes

### Scheduled Run (Daily at 08:00 Taipei)

- Runs automatically via cron
- Full pipeline: fetch → process → summarize → render → email
- Artifacts uploaded for 30 days

### Manual Run (Testing)

```yaml
workflow_dispatch:
  inputs:
    skip_email:
      description: 'Skip sending email (for testing)'
      default: 'false'
    debug_mode:
      description: 'Enable debug logging'
      default: 'false'
```

**To trigger manually:**
1. Go to repository → **Actions** tab
2. Select "Daily Multilingual News Digest" workflow
3. Click **Run workflow**
4. Optionally check "Skip sending email" for testing
5. Click **Run workflow**

---

## 6. Artifact Management

### Output Files

| File                  | Purpose                                    | Retention |
|-----------------------|-------------------------------------------|-----------|
| `web_digest.html`     | Web version with JS tabs                   | 30 days   |
| `email_digest.html`   | Email version with anchors                 | 30 days   |
| `run_log.jsonl`       | Detailed execution log                     | 30 days   |
| `run_summary.json`    | Run statistics                             | 30 days   |
| `articles_data.json`  | Raw selected articles (debug)              | 30 days   |

### Downloading Artifacts

1. Go to repository → **Actions** tab
2. Click on a workflow run
3. Scroll to **Artifacts** section
4. Click to download the zip file

---

## 7. Main Entry Point

### File: `src/main.py`

```python
#!/usr/bin/env python3
"""
Main entry point for the Daily Multilingual News Digest pipeline.
"""
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

import pytz

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_feeds_config, load_classification_rules
from src.feed_fetcher import fetch_all_feeds
from src.normalizer import normalize_all
from src.deduper import deduplicate
from src.classifier import classify_articles
from src.selector import select_top_n
from src.summarizer import summarize_all
from src.renderer_web import render_web
from src.renderer_email import render_email
from src.logger import setup_logging, RunLogger

# Configuration
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
OUTPUT_DIR = PROJECT_ROOT / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)

# Ensure debug mode from environment
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'


def main():
    """
    Main pipeline execution.
    """
    start_time = datetime.now(TAIPEI_TZ)
    
    # Setup logging
    log_file = OUTPUT_DIR / 'run_log.jsonl'
    setup_logging(log_file, debug=DEBUG_MODE)
    logger = logging.getLogger(__name__)
    run_logger = RunLogger(log_file)
    
    logger.info(f"Starting digest pipeline at {start_time.isoformat()}")
    run_logger.log('pipeline_start', {'time': start_time.isoformat()})
    
    try:
        # Step 1: Load configuration
        logger.info("Loading configuration...")
        feeds_config = load_feeds_config(PROJECT_ROOT / 'config' / 'feeds.yaml')
        classification_rules = load_classification_rules(PROJECT_ROOT / 'config' / 'classification_rules.yaml')
        run_logger.log('config_loaded', {'feeds_count': len(feeds_config.get_all_sources())})
        
        # Step 2: Fetch all feeds
        logger.info("Fetching RSS feeds...")
        raw_feeds = fetch_all_feeds(feeds_config)
        total_fetched = sum(len(items) for items in raw_feeds.values())
        run_logger.log('feeds_fetched', {'total_items': total_fetched})
        
        # Step 3: Normalize entries
        logger.info("Normalizing entries...")
        normalized = normalize_all(raw_feeds, feeds_config)
        run_logger.log('normalized', {'count': len(normalized)})
        
        # Step 4: Deduplicate
        logger.info("Deduplicating...")
        deduped = deduplicate(normalized)
        run_logger.log('deduplicated', {'before': len(normalized), 'after': len(deduped)})
        
        # Step 5: Classify Chinese articles
        logger.info("Classifying articles...")
        classified = classify_articles(deduped, classification_rules)
        run_logger.log('classified', {'count': len(classified)})
        
        # Step 6: Select top 5 per tab
        logger.info("Selecting top articles...")
        selected = select_top_n(classified, n=5)
        total_selected = sum(len(items) for items in selected.values())
        run_logger.log('selected', {'total': total_selected, 'by_tab': {k: len(v) for k, v in selected.items()}})
        
        # Step 7: Generate summaries
        logger.info("Generating summaries...")
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")
        
        summarized = summarize_all(selected, api_key)
        summary_count = sum(len(items) for items in summarized.values())
        run_logger.log('summarized', {'count': summary_count})
        
        # Step 8: Render HTML
        logger.info("Rendering HTML...")
        date_str = start_time.strftime("%Y年%m月%d日 星期") + ['一', '二', '三', '四', '五', '六', '日'][start_time.weekday()]
        
        web_html = render_web(summarized, date_str)
        email_html = render_email(summarized, date_str)
        
        # Step 9: Write output files
        logger.info("Writing output files...")
        
        (OUTPUT_DIR / 'web_digest.html').write_text(web_html, encoding='utf-8')
        (OUTPUT_DIR / 'email_digest.html').write_text(email_html, encoding='utf-8')
        
        # Write articles data for debugging
        articles_data = {
            tab: [
                {
                    'title': a.title,
                    'link': a.link,
                    'source': a.source_name,
                    'published': a.published.isoformat(),
                    'summary': a.summary,
                    'category': a.final_category
                }
                for a in articles
            ]
            for tab, articles in summarized.items()
        }
        (OUTPUT_DIR / 'articles_data.json').write_text(
            json.dumps(articles_data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
        run_logger.log('output_written', {
            'web_html': 'output/web_digest.html',
            'email_html': 'output/email_digest.html'
        })
        
        # Step 10: Write run summary
        end_time = datetime.now(TAIPEI_TZ)
        duration = (end_time - start_time).total_seconds()
        
        run_summary = {
            'run_date': start_time.strftime('%Y-%m-%d'),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': round(duration, 2),
            'feeds_fetched': total_fetched,
            'articles_normalized': len(normalized),
            'articles_deduplicated': len(deduped),
            'articles_selected': total_selected,
            'summaries_generated': summary_count,
            'status': 'success'
        }
        
        (OUTPUT_DIR / 'run_summary.json').write_text(
            json.dumps(run_summary, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
        logger.info(f"Pipeline completed successfully in {duration:.2f}s")
        run_logger.log('pipeline_complete', run_summary)
        
        return 0
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        run_logger.log('pipeline_error', {'error': str(e)})
        
        # Write error summary
        error_summary = {
            'run_date': start_time.strftime('%Y-%m-%d'),
            'start_time': start_time.isoformat(),
            'error': str(e),
            'status': 'failed'
        }
        (OUTPUT_DIR / 'run_summary.json').write_text(
            json.dumps(error_summary, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
        return 1


if __name__ == '__main__':
    sys.exit(main())
```

---

## 8. Complete requirements.txt

```
# Core dependencies
feedparser>=6.0.10
requests>=2.31.0
python-dateutil>=2.8.2
PyYAML>=6.0.1
pytz>=2023.3

# Optional: async HTTP client (for future optimization)
# httpx>=0.25.0

# Development dependencies (in requirements-dev.txt)
# pytest>=7.4.0
# pytest-cov>=4.1.0
```

---

## 9. Quick Start Guide

### Local Testing

```bash
# 1. Clone and setup
git clone <your-repo-url>
cd RssNews2
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# 2. Set environment variables
export DEEPSEEK_API_KEY="your-api-key"
export DEBUG_MODE="true"

# 3. Run pipeline
python -m src.main

# 4. Check output
open output/web_digest.html
```

### Deploy to GitHub Actions

1. Push code to GitHub
2. Add secrets in repository settings
3. Enable Actions in repository settings
4. Wait for scheduled run or trigger manually

---

## 10. Monitoring & Observability

### Check Workflow Status

1. Go to repository → **Actions** tab
2. View run history and status
3. Click on runs to see step-by-step logs

### Log Analysis

```bash
# Download artifacts and analyze
cat run_log.jsonl | jq '.msg'

# Check run summary
cat run_summary.json | jq
```

### Common Issues

| Issue                    | Symptom                          | Solution                                |
|--------------------------|----------------------------------|-----------------------------------------|
| DEEPSEEK_API_KEY missing | Pipeline fails at summarization  | Add secret to repository settings       |
| SMTP auth failure        | Email not sent                   | Check App Password, not main password   |
| Feed timeout             | Some feeds skipped               | Normal degradation, check logs          |
| Rate limit               | Slow summaries                   | Increase delays between API calls       |

---

This completes the 7-step documentation. The system is now fully specified and ready for implementation.
