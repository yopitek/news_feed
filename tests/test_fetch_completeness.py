"""Tests for the 2026-11-26 completeness fixes: backfill, source balance,
stock/housing classification, all-source health, raw export grouping."""
import time
from datetime import datetime, timedelta, timezone

from src.classifier import Classifier
from src.config_loader import load_classification_rules
from src.export_raw import group_articles
from src.feed_fetcher import _newest_entry, _short_error, summarize_all_sources, summarize_source_health
from src.models import FeedsConfig, NormalizedArticle, TabConfig
from src.normalizer import normalize_all
from src.selector import _round_robin_by_source, pick_balanced_with_backfill, select_by_category

NOW = datetime.now(timezone.utc)


def art(title, hours_ago, source='S', tab='en_news', cat='Startup', backfill=False, lang='en', final=None):
    return NormalizedArticle(
        title=title, link=f'https://e.x/{title}', published=NOW - timedelta(hours=hours_ago),
        source_name=source, language=lang, tab=tab, rss_category=cat, guid=title,
        final_category=final, backfill=backfill,
    )


# ---------- selector ----------

def test_round_robin_gives_every_source_a_slot():
    busy = [art(f'hn{i}', i, 'Hacker News') for i in range(1, 31)]
    quiet = [art('tc1', 40, 'TechCrunch Startups'), art('ac1', 50, 'Andrew Chen')]
    ordered = sorted(busy + quiet, key=lambda a: a.published, reverse=True)
    picked = _round_robin_by_source(ordered, 8)
    assert len(picked) == 8
    assert {a.source_name for a in picked} == {'Hacker News', 'TechCrunch Startups', 'Andrew Chen'}
    assert [a.published for a in picked] == sorted((a.published for a in picked), reverse=True)


def test_round_robin_single_source_is_plain_slice():
    items = [art(f'a{i}', i) for i in range(1, 6)]
    assert _round_robin_by_source(items, 3) == items[:3]
    assert _round_robin_by_source(items, 0) == []


def test_backfill_only_tops_up():
    fresh = [art(f'f{i}', i) for i in range(1, 4)]
    old = [art(f'o{i}', 30 + i, backfill=True) for i in range(1, 10)]
    ordered = sorted(fresh + old, key=lambda a: a.published, reverse=True)
    picked = pick_balanced_with_backfill(ordered, 6)
    assert [a.title for a in picked[:3]] == ['f1', 'f2', 'f3']
    assert len(picked) == 6 and all(a.backfill for a in picked[3:])


def test_backfill_never_displaces_fresh():
    fresh = [art(f'f{i}', i) for i in range(1, 10)]
    old = [art('o1', 30, source='Other', backfill=True)]
    picked = pick_balanced_with_backfill(fresh + old, 6)
    assert len(picked) == 6 and not any(a.backfill for a in picked)


def test_select_by_category_fills_thin_category():
    items = [art('f1', 2, 'BBC Education', cat='BBC Education')]
    items += [art(f'o{i}', 30 + i, 'BBC Education', cat='BBC Education', backfill=True) for i in range(8)]
    selected = select_by_category(items)
    assert len(selected['en_news']['BBC Education']) == 6
    assert selected['en_news']['BBC Education'][0].title == 'f1'


# ---------- normalizer ----------

def _entry(title, hours_ago):
    dt = NOW - timedelta(hours=hours_ago)
    return {'title': title, 'link': f'https://e.x/{title}', 'published_parsed': time.gmtime(dt.timestamp()),
            'summary': 'x', 'guid': title, '_language': 'en', '_category': 'Startup', '_source_name': 'S'}


def _cfg(settings):
    return FeedsConfig(tabs={'en_news': TabConfig(name='EN', language='en', item_limit=8, sources=[])}, settings=settings)


def test_normalizer_flags_backfill_and_drops_older():
    raw = {'en_news': [_entry('fresh', 3), _entry('older', 40), _entry('ancient', 100)]}
    out = {a.title: a for a in normalize_all(raw, _cfg({'backfill_window_hours': 72}))}
    assert set(out) == {'fresh', 'older'}
    assert out['fresh'].backfill is False and out['older'].backfill is True


def test_normalizer_backfill_can_be_disabled():
    raw = {'en_news': [_entry('fresh', 3), _entry('older', 40)]}
    assert [a.title for a in normalize_all(raw, _cfg({'backfill_window_hours': 24}))] == ['fresh']


def test_explicit_tab_window_gets_no_backfill():
    raw = {'en_news': [_entry('fresh', 3), _entry('older', 40)]}
    cfg = _cfg({'backfill_window_hours': 72, 'tab_time_window_hours': {'en_news': 24}})
    assert [a.title for a in normalize_all(raw, cfg)] == ['fresh']


# ---------- classifier ----------

def _zh(title, cat):
    return art(title, 1, '中央社', tab='zh_news', cat=cat, lang='zh')


def test_stock_and_housing_sections_are_reachable():
    c = Classifier(load_classification_rules('config/classification_rules.yaml'))
    assert c.classify(_zh('台股收盤大漲300點 台積電領軍', '產經')) == '股市'
    assert c.classify(_zh('央行理監事會 房貸限制不變', '產經')) == '房市'
    assert c.classify(_zh('雙北預售屋交易量回升', '生活')) == '房市'
    assert c.classify(_zh('Yahoo 盤勢報導', '股市')) == '股市'


def test_priority_rules_leave_other_news_alone():
    c = Classifier(load_classification_rules('config/classification_rules.yaml'))
    assert c.classify(_zh('出口連三月成長 經濟部看好下半年', '產經')) == '產經'
    assert c.classify(_zh('土地公廟百年慶典登場', '地方')) == '社會'
    # skip list: entertainment/sport stories are never re-bucketed
    assert c.classify(_zh('藝人買房千萬豪宅曝光', '娛樂')) == '娛樂'


def test_classifier_without_priority_rules_is_unchanged():
    c = Classifier({'rss_to_target_mapping': {'產經': '產經'}})
    assert c.classify(_zh('台股收盤大漲', '產經')) == '產經'


# ---------- health ----------

def _row(tab, status, age=None, name='n', error=None, count=5):
    return {'tab': tab, 'category': 'c', 'source_name': name, 'url': 'u', 'type': 'rss', 'status': status,
            'fetched_count': count, 'error': error, 'newest_published': None, 'newest_age_hours': age}


def test_all_sources_buckets_sum_and_flag_stale():
    stats = [
        _row('zh_news', 'ok', 2), _row('en_news', 'ok', 24 * 90, name='Penn Olson'),
        _row('en_news', 'failed', error='HTTP 404', count=0), _row('ja_news', 'empty', count=0),
        _row('ptt_hot', 'ok_snapshot', 24 * 30), _row('tech_blogs', 'ok', 24 * 60), _row('en_news', 'ok', None),
    ]
    h = summarize_all_sources(stats)
    assert (h['total_sources'], h['ok_sources'], h['stale_sources'], h['empty_sources'], h['failed_sources']) == (7, 4, 1, 1, 1)
    assert h['ok_sources'] + h['stale_sources'] + h['empty_sources'] + h['failed_sources'] == h['total_sources']
    assert {p['health'] for p in h['problem_sources']} == {'stale', 'failed', 'empty'}
    assert h['by_tab']['en_news'] == {'total': 3, 'ok': 1, 'stale': 1, 'empty': 0, 'failed': 1, 'fetched_items': 10}


def test_legacy_health_shape_kept_and_all_added():
    h = summarize_source_health([_row('tech_blogs', 'ok'), _row('zh_news', 'failed', count=0)])
    assert h['total_sources'] == 1 and h['ok_sources'] == 1
    assert h['all']['total_sources'] == 2 and h['all']['failed_sources'] == 1


def test_newest_entry_and_short_error():
    assert _newest_entry([]) == (None, None)
    assert _newest_entry([{'published_parsed': None}]) == (None, None)
    iso, age = _newest_entry([{'published_parsed': time.gmtime((NOW - timedelta(hours=5)).timestamp())},
                              {'published_parsed': time.gmtime((NOW - timedelta(hours=50)).timestamp())}])
    assert iso and 4.5 <= age <= 5.5

    class R: status_code = 404
    class E(Exception): response = R()
    assert _short_error(E()) == 'HTTP 404'
    assert _short_error(Exception('Name or service not known')) == 'DNS failure'


# ---------- raw export ----------

def test_group_articles_lists_every_configured_category():
    items = [art('a', 1, tab='zh_news', cat='產經', lang='zh', final='股市'),
             art('b', 30, tab='zh_news', cat='產經', lang='zh', final='股市', backfill=True),
             art('c', 2, tab='zh_news', cat='產經', lang='zh', final='股市')]
    grouped = group_articles(items)
    assert list(grouped['zh_news'])[:3] == ['頭條新聞', '產經', '股市']
    assert [x['title'] for x in grouped['zh_news']['股市']] == ['a', 'c', 'b']
    assert grouped['zh_news']['房市'] == [] and grouped['en_news']['Startup'] == []
    assert group_articles(items, per_category_limit=1)['zh_news']['股市'][0]['title'] == 'a'
