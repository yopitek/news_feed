"""Source-health accounting must not double-count.

Regression cover for the Tech Blogs status line that read
``18 sources followed · 14 returned articles · 4 empty · 4 failed``
— the buckets summed to 22 because `fetch_feed` returned `[]` for both
"feed is fine, nothing new" and "the fetch broke", and
`failed_sources` counted every non-ok row a second time.
"""
import pytest

from src.feed_fetcher import fetch_feed, summarize_source_health


# --- summarize_source_health: buckets must be mutually exclusive ---------

def _stats(*statuses):
    return [{'tab': 'tech_blogs', 'status': s, 'source_name': f's{i}'}
            for i, s in enumerate(statuses)]


def test_buckets_sum_to_total():
    health = summarize_source_health(
        _stats('ok', 'ok', 'ok', 'empty', 'failed'))
    assert health['total_sources'] == 5
    assert (health['ok_sources'] + health['empty_sources']
            + health['failed_sources']) == health['total_sources']


def test_empty_and_failed_are_distinct_buckets():
    health = summarize_source_health(_stats('ok', 'empty', 'failed', 'failed'))
    assert health['ok_sources'] == 1
    assert health['empty_sources'] == 1
    assert health['failed_sources'] == 2


def test_failed_does_not_swallow_empty():
    """The exact regression: 'empty' rows used to be re-counted as failures."""
    health = summarize_source_health(_stats('ok', 'ok', 'empty', 'empty'))
    assert health['empty_sources'] == 2
    assert health['failed_sources'] == 0


def test_healthy_feed_reports_no_failures():
    health = summarize_source_health(_stats(*(['ok'] * 18)))
    assert health['failed_sources'] == 0
    assert health['empty_sources'] == 0
    assert health['total_sources'] == 18


def test_ignores_non_tech_tabs():
    stats = [{'tab': 'zh_news', 'status': 'failed'},
             {'tab': 'tech_blogs', 'status': 'ok'}]
    health = summarize_source_health(stats)
    assert health['total_sources'] == 1
    assert health['failed_sources'] == 0


# --- fetch_feed: outcome distinguishes empty from broken ----------------

class _FakeResponse:
    def __init__(self, content=b'', status=200):
        self.content = content
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise Exception(f'HTTP {self.status}')


def test_outcome_reports_ok(monkeypatch):
    import src.feed_fetcher as ff
    payload = (b'<?xml version="1.0"?><rss version="2.0"><channel>'
               b'<item><title>T</title><link>http://x/1</link></item>'
               b'</channel></rss>')
    monkeypatch.setattr(ff.requests, 'get',
                        lambda *a, **k: _FakeResponse(payload))
    outcome = {}
    entries = fetch_feed('http://x/feed', outcome=outcome)
    assert len(entries) == 1
    assert outcome['status'] == 'ok'
    assert outcome['error'] is None


def test_outcome_reports_empty_not_failed(monkeypatch):
    """A well-formed feed with zero items is 'empty', never 'failed'."""
    import src.feed_fetcher as ff
    payload = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    monkeypatch.setattr(ff.requests, 'get',
                        lambda *a, **k: _FakeResponse(payload))
    outcome = {}
    entries = fetch_feed('http://x/feed', outcome=outcome)
    assert entries == []
    assert outcome['status'] == 'empty'
    assert outcome['error'] is None


def test_outcome_reports_failed_on_http_error(monkeypatch):
    import src.feed_fetcher as ff

    def boom(*a, **k):
        raise ff.requests.exceptions.ConnectionError('dns')

    monkeypatch.setattr(ff.requests, 'get', boom)
    monkeypatch.setattr(ff.time, 'sleep', lambda *_: None)
    outcome = {}
    entries = fetch_feed('http://x/feed', retries=1, outcome=outcome)
    assert entries == []
    assert outcome['status'] == 'failed'
    assert outcome['error']


def test_outcome_reports_failed_on_unparseable_feed(monkeypatch):
    import src.feed_fetcher as ff
    monkeypatch.setattr(ff.requests, 'get',
                        lambda *a, **k: _FakeResponse(b'not xml at all <<<'))
    monkeypatch.setattr(ff.time, 'sleep', lambda *_: None)
    outcome = {}
    entries = fetch_feed('http://x/feed', retries=0, outcome=outcome)
    assert entries == []
    assert outcome['status'] == 'failed'
    assert 'unparseable' in outcome['error']


def test_outcome_is_optional_and_backward_compatible(monkeypatch):
    """Callers that pass no outcome dict must not crash."""
    import src.feed_fetcher as ff
    payload = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    monkeypatch.setattr(ff.requests, 'get',
                        lambda *a, **k: _FakeResponse(payload))
    assert fetch_feed('http://x/feed') == []


# --- footer wording: the two modes must be reported separately ---------

def _health(**kw):
    base = {'total_sources': 18, 'ok_sources': 16, 'empty_sources': 2,
            'failed_sources': 0, 'selected_articles': 6}
    base.update(kw)
    return base


@pytest.mark.parametrize('failed,empty,expect', [
    (0, 0, 'sources checked'),
    (3, 0, '3 Tech Blogs sources could not be fetched'),
    (1, 0, '1 Tech Blogs source could not be fetched'),
    (0, 4, '4 Tech Blogs sources had no new articles'),
    (2, 3, '2 Tech Blogs sources could not be fetched'),
    (1, 1, '1 Tech Blogs source could not be fetched'),
])
def test_footer_reports_each_mode(failed, empty, expect):
    from src.renderer_web import render_pipeline_status
    text = render_pipeline_status(
        {'generated_at': '2026-10-04 07:14 CST', 'articles_selected': 230,
         'feeds_count': 72},
        _health(failed_sources=failed, empty_sources=empty),
    )
    assert expect in text


def test_footer_does_not_conflate_failure_with_emptiness():
    from src.renderer_web import render_pipeline_status
    text = render_pipeline_status(
        {'generated_at': 'x', 'articles_selected': 1, 'feeds_count': 1},
        _health(failed_sources=0, empty_sources=4),
    )
    assert 'could not be fetched' not in text
    assert 'returned no usable feed' not in text
