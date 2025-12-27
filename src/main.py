#!/usr/bin/env python3
"""
Main entry point for the Daily Multilingual News Digest pipeline.
Updated for category-based grouping with 8 articles per category.
"""
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

import pytz

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_feeds_config, load_classification_rules
from src.feed_fetcher import fetch_all_feeds
from src.normalizer import normalize_all
from src.deduper import deduplicate
from src.classifier import classify_articles
from src.selector import select_by_category, TAB_CATEGORIES
from src.summarizer import summarize_by_category
from src.renderer_web import render_web
from src.renderer_email import render_email
from src.logger import setup_logging, RunLogger

TAIPEI_TZ = pytz.timezone('Asia/Taipei')
OUTPUT_DIR = PROJECT_ROOT / 'output'
CONFIG_DIR = PROJECT_ROOT / 'config'

DEBUG_MODE = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
ITEMS_PER_CATEGORY = 8


def main():
    """Main pipeline execution."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    start_time = datetime.now(TAIPEI_TZ)
    
    log_file = OUTPUT_DIR / 'run_log.jsonl'
    if log_file.exists():
        log_file.unlink()
    
    setup_logging(log_file, debug=DEBUG_MODE)
    logger = logging.getLogger(__name__)
    run_logger = RunLogger(log_file)
    
    logger.info(f"Starting digest pipeline at {start_time.isoformat()}")
    run_logger.log('pipeline_start', {'time': start_time.isoformat()})
    
    try:
        # Step 1: Load configuration
        logger.info("Loading configuration...")
        feeds_config = load_feeds_config(CONFIG_DIR / 'feeds.yaml')
        classification_rules = load_classification_rules(CONFIG_DIR / 'classification_rules.yaml')
        
        all_sources = feeds_config.get_all_sources()
        run_logger.log('config_loaded', {'feeds_count': len(all_sources)})
        logger.info(f"Loaded {len(all_sources)} feed sources")
        
        # Step 2: Fetch all feeds
        logger.info("Fetching RSS feeds...")
        raw_feeds = fetch_all_feeds(feeds_config)
        total_fetched = sum(len(items) for items in raw_feeds.values())
        run_logger.log('feeds_fetched', {'total_items': total_fetched})
        logger.info(f"Fetched {total_fetched} total items")
        
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
        
        # Step 6: Select by category (8 per category)
        logger.info(f"Selecting {ITEMS_PER_CATEGORY} articles per category...")
        selected = select_by_category(classified, items_per_category=ITEMS_PER_CATEGORY)
        
        # Count total selected
        total_selected = 0
        selection_stats = {}
        for tab, categories in selected.items():
            tab_count = sum(len(articles) for articles in categories.values())
            selection_stats[tab] = {cat: len(arts) for cat, arts in categories.items()}
            total_selected += tab_count
        
        run_logger.log('selected', {'total': total_selected, 'by_tab': selection_stats})
        logger.info(f"Selected {total_selected} articles across {len(selected)} tabs")
        
        # Step 7: Generate summaries (200 chars)
        logger.info("Generating summaries (200 chars/words)...")
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")
        
        summarized = summarize_by_category(selected, api_key)
        summary_count = sum(
            len(arts)
            for cats in summarized.values()
            for arts in cats.values()
        )
        run_logger.log('summarized', {'count': summary_count})
        
        # Step 8: Render HTML
        logger.info("Rendering HTML (category-grouped)...")
        weekdays = ['一', '二', '三', '四', '五', '六', '日']
        date_str = start_time.strftime("%Y年%m月%d日 星期") + weekdays[start_time.weekday()]
        
        web_html = render_web(summarized, date_str)
        email_html = render_email(summarized, date_str)
        
        # Step 9: Write output files
        logger.info("Writing output files...")
        
        (OUTPUT_DIR / 'web_digest.html').write_text(web_html, encoding='utf-8')
        (OUTPUT_DIR / 'email_digest.html').write_text(email_html, encoding='utf-8')
        
        # Write articles data for debugging
        articles_data = {}
        for tab, categories in summarized.items():
            articles_data[tab] = {}
            for category, articles in categories.items():
                articles_data[tab][category] = [
                    {
                        'title': a.title,
                        'link': a.link,
                        'source': a.source_name,
                        'published': a.published.isoformat(),
                        'summary': a.summary[:100] + '...' if len(a.summary) > 100 else a.summary
                    }
                    for a in articles
                ]
        
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
            'items_per_category': ITEMS_PER_CATEGORY,
            'categories': {
                'zh_news': list(TAB_CATEGORIES['zh_news']),
                'en_news': list(TAB_CATEGORIES['en_news']),
                'ja_news': list(TAB_CATEGORIES['ja_news'])
            },
            'status': 'success'
        }
        
        (OUTPUT_DIR / 'run_summary.json').write_text(
            json.dumps(run_summary, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
        logger.info(f"Pipeline completed successfully in {duration:.2f}s")
        logger.info(f"Total articles: {total_selected} across {sum(len(c) for c in TAB_CATEGORIES.values())} categories")
        run_logger.log('pipeline_complete', run_summary)
        
        return 0
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        run_logger.log('pipeline_error', {'error': str(e)})
        
        end_time = datetime.now(TAIPEI_TZ)
        error_summary = {
            'run_date': start_time.strftime('%Y-%m-%d'),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'error': str(e),
            'status': 'failed'
        }
        
        try:
            (OUTPUT_DIR / 'run_summary.json').write_text(
                json.dumps(error_summary, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception:
            pass
        
        return 1


if __name__ == '__main__':
    sys.exit(main())
