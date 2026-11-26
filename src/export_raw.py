"""
Fetch-only export: every source, no LLM, no API keys.

    python -m src.export_raw                # writes output/feed_raw.json
    python -m src.export_raw --out docs     # writes docs/feed_raw.json
    python -m src.export_raw --check        # exit 1 when any source is failed/stale

Why this exists
---------------
``src.main`` fetches, then makes one summarization call per article. That second
half takes ~15 minutes and needs a working API key, so "did we get the data?"
could not be answered without running (and paying for) the whole pipeline, and a
summarizer outage looked the same as a fetch outage.

This module stops after classification and writes everything it fetched:

* ``feed_raw.json``   - all deduplicated articles of every tab, grouped by the
  same display categories the digest uses, each with title / link / published /
  source / RSS description. A downstream agent can classify and summarize
  from this file alone.
* ``feed_health.json`` - one row per configured source: ok / stale / empty /
  failed, the error, and the age of its newest item.

Nothing here publishes, emails, or calls a model.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pytz

from .classifier import classify_articles
from .config_loader import load_classification_rules, load_feeds_config
from .deduper import deduplicate
from .feed_fetcher import fetch_all_feeds, get_last_fetch_stats, summarize_all_sources
from .normalizer import normalize_all
from .selector import TAB_CATEGORIES, TAB_SORT_METRIC, engagement_value, map_to_display_category

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / 'config'
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
SCHEMA_VERSION = 1


def load_all_config():
    """feeds.yaml plus the optional tech_blogs.yaml, exactly as src.main does."""
    feeds_config = load_feeds_config(CONFIG_DIR / 'feeds.yaml')
    tech_blogs_path = CONFIG_DIR / 'tech_blogs.yaml'
    if tech_blogs_path.exists():
        from .config_loader import load_tech_blogs_config
        tech = load_tech_blogs_config(tech_blogs_path)
        tab = tech['tabs'].get('tech_blogs')
        if tab is not None:
            feeds_config.tabs['tech_blogs'] = tab
    return feeds_config


def article_to_dict(article) -> dict:
    return {
        'title': article.title,
        'link': article.link,
        'published': article.published.astimezone(TAIPEI_TZ).isoformat(),
        'source': article.source_name,
        'language': article.language,
        'rss_category': article.rss_category,
        'category': article.final_category or article.rss_category,
        'description': article.description or '',
        'backfill': bool(getattr(article, 'backfill', False)),
        'metrics': article.metrics or None,
    }


def group_articles(articles: list, per_category_limit: int | None = None) -> dict:
    """tab -> display category -> articles, in the digest's own category order."""
    grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for article in articles:
        grouped[article.tab][map_to_display_category(article)].append(article)

    result: dict[str, dict[str, list]] = {}
    for tab_id in list(TAB_CATEGORIES.keys()) + [t for t in grouped if t not in TAB_CATEGORIES]:
        if tab_id in result:
            continue
        cats = grouped.get(tab_id, {})
        ordered = list(TAB_CATEGORIES.get(tab_id, [])) + [c for c in cats if c not in TAB_CATEGORIES.get(tab_id, [])]
        metric = TAB_SORT_METRIC.get(tab_id)
        tab_out: dict[str, list] = {}
        for category in ordered:
            items = cats.get(category, [])
            if metric:
                items = sorted(items, key=lambda a: (engagement_value(a, metric), a.published), reverse=True)
            else:
                # Fresh first, then backfill; newest first inside each group.
                items = sorted(items, key=lambda a: (not getattr(a, 'backfill', False), a.published), reverse=True)
            if per_category_limit:
                items = items[:per_category_limit]
            tab_out[category] = [article_to_dict(a) for a in items]
        result[tab_id] = tab_out
    return result


def build_export(per_category_limit: int | None = None) -> tuple[dict, dict]:
    """Run fetch -> normalize -> dedupe -> classify and return (raw, health)."""
    started = datetime.now(TAIPEI_TZ)
    feeds_config = load_all_config()
    rules = load_classification_rules(CONFIG_DIR / 'classification_rules.yaml')

    raw_feeds = fetch_all_feeds(feeds_config)
    fetched_total = sum(len(v) for v in raw_feeds.values())
    normalized = normalize_all(raw_feeds, feeds_config)
    deduped = deduplicate(normalized)
    classified = classify_articles(deduped, rules)

    health = summarize_all_sources(get_last_fetch_stats())
    tabs = group_articles(classified, per_category_limit)

    counts = {tab: {cat: len(items) for cat, items in cats.items()} for tab, cats in tabs.items()}
    empty_categories = [
        {'tab': tab, 'category': cat}
        for tab, cats in counts.items() for cat, n in cats.items() if n == 0
    ]
    finished = datetime.now(TAIPEI_TZ)
    tab_names = {tab_id: cfg.name for tab_id, cfg in feeds_config.tabs.items() if cfg is not None}

    raw = {
        'schema_version': SCHEMA_VERSION,
        'generated_at': finished.isoformat(),
        'duration_seconds': round((finished - started).total_seconds(), 1),
        'window_hours': 24,
        'backfill_window_hours': feeds_config.settings.get('backfill_window_hours', 72),
        'totals': {
            'fetched_entries': fetched_total,
            'after_time_filter': len(normalized),
            'after_dedupe': len(deduped),
            'exported': sum(n for cats in counts.values() for n in cats.values()),
        },
        'tab_names': tab_names,
        'counts': counts,
        'empty_categories': empty_categories,
        'health_summary': {k: health[k] for k in (
            'total_sources', 'ok_sources', 'stale_sources', 'empty_sources', 'failed_sources'
        )},
        'problem_sources': health['problem_sources'],
        'tabs': tabs,
    }
    health_out = dict(health)
    health_out['generated_at'] = finished.isoformat()
    return raw, health_out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Fetch every source and export raw articles (no LLM).')
    parser.add_argument('--out', default='output', help='output directory (default: output)')
    parser.add_argument('--limit', type=int, default=0,
                        help='max articles per category in the export (default: 0 = all)')
    parser.add_argument('--check', action='store_true',
                        help='exit 1 when any source is failed or stale, or any category is empty')
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = BASE_DIR / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    raw, health = build_export(args.limit or None)
    (out_dir / 'feed_raw.json').write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding='utf-8')
    (out_dir / 'feed_health.json').write_text(json.dumps(health, ensure_ascii=False, indent=1), encoding='utf-8')

    hs = raw['health_summary']
    print(f"sources: {hs['ok_sources']}/{hs['total_sources']} ok, "
          f"{hs['stale_sources']} stale, {hs['empty_sources']} empty, {hs['failed_sources']} failed")
    print(f"articles exported: {raw['totals']['exported']} (fetched {raw['totals']['fetched_entries']})")
    for problem in raw['problem_sources']:
        print(f"  [{problem['health']}] {problem['tab']} / {problem['category']} / {problem['source_name']}: "
              f"{problem.get('error') or problem.get('status')} "
              f"(newest {problem.get('newest_age_hours')}h ago) {problem['url']}")
    for item in raw['empty_categories']:
        print(f"  [empty category] {item['tab']} / {item['category']}")
    print(f"wrote {out_dir / 'feed_raw.json'} and {out_dir / 'feed_health.json'}")

    if args.check and (raw['problem_sources'] or raw['empty_categories']):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
