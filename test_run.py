#!/usr/bin/env python3
"""
Test script to run the pipeline without DeepSeek API.
Uses RSS descriptions as summaries for testing.
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Set up path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Disable API requirement for testing
os.environ['DEBUG_MODE'] = 'true'

import pytz

from src.config_loader import load_feeds_config, load_classification_rules
from src.feed_fetcher import fetch_all_feeds
from src.normalizer import normalize_all
from src.deduper import deduplicate
from src.classifier import classify_articles
from src.selector import select_top_n
from src.renderer_web import render_web
from src.renderer_email import render_email
from src.models import ArticleWithSummary
from src.logger import setup_logging, RunLogger

TAIPEI_TZ = pytz.timezone('Asia/Taipei')
OUTPUT_DIR = PROJECT_ROOT / 'output'
CONFIG_DIR = PROJECT_ROOT / 'config'


def fallback_summarize(articles: dict) -> dict:
    """
    Create summaries using RSS descriptions (no API needed).
    """
    result = {}
    for tab, tab_articles in articles.items():
        summarized = []
        for article in tab_articles:
            # Use description or title as summary
            summary = article.description or article.title
            if len(summary) > 200:
                summary = summary[:197] + '...'
            
            summarized.append(ArticleWithSummary(
                title=article.title,
                link=article.link,
                published=article.published,
                source_name=article.source_name,
                summary=summary,
                tab=article.tab,
                final_category=article.final_category
            ))
        result[tab] = summarized
    return result


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    start_time = datetime.now(TAIPEI_TZ)
    
    # Setup logging
    log_file = OUTPUT_DIR / 'run_log.jsonl'
    if log_file.exists():
        log_file.unlink()
    setup_logging(log_file, debug=True)
    
    print(f"\n{'='*60}")
    print(f"  Daily News Digest - Test Run")
    print(f"  {start_time.strftime('%Y-%m-%d %H:%M:%S')} (Asia/Taipei)")
    print(f"{'='*60}\n")
    
    # Step 1: Load configuration
    print("[1/7] Loading configuration...")
    feeds_config = load_feeds_config(CONFIG_DIR / 'feeds.yaml')
    classification_rules = load_classification_rules(CONFIG_DIR / 'classification_rules.yaml')
    print(f"      Loaded {len(feeds_config.get_all_sources())} feed sources")
    
    # Step 2: Fetch all feeds
    print("[2/7] Fetching RSS feeds (this may take a minute)...")
    raw_feeds = fetch_all_feeds(feeds_config)
    total_fetched = sum(len(items) for items in raw_feeds.values())
    print(f"      Fetched {total_fetched} total items")
    for tab, items in raw_feeds.items():
        print(f"        - {tab}: {len(items)} items")
    
    # Step 3: Normalize entries
    print("[3/7] Normalizing entries...")
    normalized = normalize_all(raw_feeds, feeds_config)
    print(f"      Normalized {len(normalized)} articles")
    
    # Step 4: Deduplicate
    print("[4/7] Deduplicating...")
    deduped = deduplicate(normalized)
    print(f"      After dedup: {len(deduped)} articles")
    
    # Step 5: Classify Chinese articles
    print("[5/7] Classifying articles...")
    classified = classify_articles(deduped, classification_rules)
    
    # Step 6: Select top 5 per tab
    print("[6/7] Selecting top articles...")
    selected = select_top_n(classified, n=5)
    for tab, items in selected.items():
        print(f"        - {tab}: {len(items)} selected")
    
    # Step 7: Generate fallback summaries (no API)
    print("[7/7] Generating summaries (using RSS descriptions)...")
    summarized = fallback_summarize(selected)
    
    # Render HTML
    print("\nRendering HTML...")
    weekdays = ['一', '二', '三', '四', '五', '六', '日']
    date_str = start_time.strftime("%Y年%m月%d日 星期") + weekdays[start_time.weekday()]
    
    web_html = render_web(summarized, date_str)
    email_html = render_email(summarized, date_str)
    
    # Write output
    web_path = OUTPUT_DIR / 'web_digest.html'
    email_path = OUTPUT_DIR / 'email_digest.html'
    
    web_path.write_text(web_html, encoding='utf-8')
    email_path.write_text(email_html, encoding='utf-8')
    
    # Write articles data
    articles_data = {
        tab: [
            {
                'title': a.title,
                'link': a.link,
                'source': a.source_name,
                'published': a.published.isoformat(),
                'summary': a.summary[:100] + '...' if len(a.summary) > 100 else a.summary,
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
    
    end_time = datetime.now(TAIPEI_TZ)
    duration = (end_time - start_time).total_seconds()
    
    print(f"\n{'='*60}")
    print(f"  ✅ Pipeline completed in {duration:.1f} seconds!")
    print(f"{'='*60}")
    print(f"\n📄 Output files:")
    print(f"   - Web version:   {web_path}")
    print(f"   - Email version: {email_path}")
    print(f"\n🌐 To view the result, run:")
    print(f"   open {web_path}")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
