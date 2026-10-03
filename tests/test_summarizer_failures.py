"""
Tests for the summarizer's failure handling.

The important behaviour here is that a *permanent* API error disables the
provider immediately instead of being retried for every article.

Measured 2026-10-03: with a model id that returned HTTP 404, the CI digest spent
900s of its 943s runtime retrying — 222 articles x (1 attempt + 1 retry), each a
full round-trip. The `disabled` flag already existed but was only wired to
401/402/403, so 404/400 fell into the generic retry branch.
"""
from unittest.mock import patch

import pytest
import requests

from src.summarizer import NVIDIASummarizer, RETRY_BACKOFF


class _Resp:
    def __init__(self, status_code: int, text: str = "404 page not found", json_body=None):
        self.status_code = status_code
        self.text = text
        self._json = json_body

    def json(self):
        return self._json


@pytest.fixture
def summarizer():
    return NVIDIASummarizer("nvapi-test", model="definitely/not-a-real-model")


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404])
def test_permanent_errors_disable_immediately(summarizer, status):
    """One request, then the provider is switched off for good."""
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(kwargs.get("json"))
        return _Resp(status)

    with patch.object(requests, "post", fake_post):
        assert summarizer._call_api("sys", "user") is None
        assert summarizer.disabled is True
        # Every later article must short-circuit without a network call.
        assert summarizer._call_api("sys", "user") is None
        assert summarizer._call_api("sys", "user") is None

    assert len(calls) == 1


def test_404_does_not_sleep_through_the_retry_budget(summarizer):
    """The old code slept once per retry round — 222 articles made that a 15-min run."""
    slept = []

    with patch.object(requests, "post", lambda *a, **k: _Resp(404)):
        with patch("src.summarizer.time.sleep", lambda s: slept.append(s)):
            summarizer._call_api("sys", "user")

    assert slept == []


@pytest.mark.parametrize("status", [500, 502, 503])
def test_transient_errors_still_retry_then_give_up(summarizer, status):
    """A 5xx might recover, so it must keep the retry budget."""
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        return _Resp(status, text="upstream error")

    with patch.object(requests, "post", fake_post):
        with patch("src.summarizer.time.sleep", lambda _s: None):
            assert summarizer._call_api("sys", "user") is None

    assert len(calls) == len(RETRY_BACKOFF)
    # Transient exhaustion must not permanently disable the provider — the next
    # article is still allowed to try.
    assert summarizer.disabled is False


def test_successful_call_returns_content(summarizer):
    body = {"choices": [{"message": {"content": "  摘要內容  "}}]}
    with patch.object(requests, "post", lambda *a, **k: _Resp(200, json_body=body)):
        assert summarizer._call_api("sys", "user") == "摘要內容"


def test_rate_limit_waits_and_then_succeeds(summarizer):
    """429 is handled before the permanent-error branch: wait, retry, succeed."""
    responses = [_Resp(429), _Resp(200, json_body={"choices": [{"message": {"content": "ok"}}]})]

    def fake_post(*args, **kwargs):
        return responses.pop(0)

    with patch.object(requests, "post", fake_post):
        with patch("src.summarizer.time.sleep", lambda _s: None):
            assert summarizer._call_api("sys", "user") == "ok"
    assert summarizer.disabled is False


class _FakeSummarizer:
    """Minimal summarizer that can be instructed to succeed or disable itself."""

    def __init__(self, name: str, disabled: bool = False):
        self.name = name
        self.disabled = disabled
        self.calls = 0

    def summarize(self, article):
        self.calls += 1
        return f"{self.name}:summary"


def _article():
    from datetime import datetime, timezone

    from src.models import NormalizedArticle

    return NormalizedArticle(
        title="t",
        link="https://example.com/1",
        published=datetime.now(timezone.utc),
        source_name="src",
        language="zh",
        tab="zh_news",
        rss_category="科技",
        guid="1",
        description="原始描述",
    )


def test_falls_through_to_next_provider_when_one_is_disabled(monkeypatch):
    """
    Measured 2026-10-04: NVIDIA_API_KEY was set but returned 403 Authorization
    failed, so the picked provider disabled itself after one article and all 230
    summaries degraded to RSS — although ZEABUR_API_KEY was configured. One bad
    key must not turn the feature off for the whole run.
    """
    import src.summarizer as sm

    dead = _FakeSummarizer("nvidia", disabled=True)
    alive = _FakeSummarizer("zeabur")
    monkeypatch.setattr(sm, "get_summarizer_chain", lambda: [dead, alive])

    out = sm.summarize_by_category({"zh_news": {"科技": [_article(), _article()]}})

    summaries = [a.summary for a in out["zh_news"]["科技"]]
    assert summaries == ["zeabur:summary", "zeabur:summary"]
    assert dead.calls == 0
    assert alive.calls == 2


def test_first_provider_is_used_while_it_works(monkeypatch):
    """No failover when nothing is wrong."""
    import src.summarizer as sm

    primary = _FakeSummarizer("nvidia")
    backup = _FakeSummarizer("zeabur")
    monkeypatch.setattr(sm, "get_summarizer_chain", lambda: [primary, backup])

    out = sm.summarize_by_category({"zh_news": {"科技": [_article()]}})
    assert out["zh_news"]["科技"][0].summary == "nvidia:summary"
    assert backup.calls == 0


def test_get_summarizer_chain_order(monkeypatch):
    """NVIDIA > Zeabur > Gemini > SiliconFlow > DeepSeek, per the documented priority."""
    import src.summarizer as sm

    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-x")
    monkeypatch.setenv("ZEABUR_API_KEY", "sk-short")
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSy-x")
    chain = [type(c).__name__ for c in sm.get_summarizer_chain()]
    assert chain == ["NVIDIASummarizer", "ZeaburSummarizer", "GeminiSummarizer"]

    monkeypatch.delenv("NVIDIA_API_KEY")
    monkeypatch.delenv("GOOGLE_API_KEY")
    assert [type(c).__name__ for c in sm.get_summarizer_chain()] == ["ZeaburSummarizer"]

    monkeypatch.delenv("ZEABUR_API_KEY")
    # No keys at all -> the no-API fallback, still a single-element chain.
    chain = sm.get_summarizer_chain()
    assert len(chain) == 1
    assert isinstance(chain[0], sm.FallbackSummarizer)


def test_get_summarizer_still_returns_the_top_priority(monkeypatch):
    """Existing callers must keep getting one summarizer, not a list."""
    import src.summarizer as sm

    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-x")
    monkeypatch.setenv("ZEABUR_API_KEY", "sk-short")
    assert isinstance(sm.get_summarizer(), sm.NVIDIASummarizer)


def test_dead_host_disables_after_a_short_run_of_failures(summarizer):
    """
    A hostname that does not resolve will not resolve later in the same run.
    Measured 2026-10-04: a dead Zeabur host produced one identical error line
    for each of 230 articles.
    """
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        raise requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='hnd1.aihub.zeabur.ai', port=443): "
            "Failed to resolve 'hnd1.aihub.zeabur.ai'"
        )

    with patch.object(requests, "post", fake_post):
        for _ in range(10):
            summarizer._call_api("sys", "user")

    from src.summarizer import MAX_CONSECUTIVE_FAILURES

    assert len(calls) == MAX_CONSECUTIVE_FAILURES
    assert summarizer.disabled is True


def test_a_single_connection_error_is_allowed_to_recover(summarizer):
    """One blip must not permanently disable a working provider."""
    responses = [
        requests.exceptions.ConnectionError("connection reset"),
        _Resp(200, json_body={"choices": [{"message": {"content": "ok"}}]}),
    ]

    def fake_post(*args, **kwargs):
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    with patch.object(requests, "post", fake_post):
        assert summarizer._call_api("sys", "user") is None
        assert summarizer.disabled is False
        assert summarizer._call_api("sys", "user") == "ok"

    assert summarizer._consecutive_failures == 0


def test_gemini_permanent_error_disables_provider():

    """GeminiSummarizer is standalone, so it needs its own guard."""
    from src.summarizer import GeminiSummarizer

    g = GeminiSummarizer("fake-key")
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        return _Resp(404, text='{"error": {"message": "model not found"}}')

    with patch.object(requests, "post", fake_post):
        with patch("src.summarizer.time.sleep", lambda _s: None):
            assert g._call_api("prompt") is None
            assert g.disabled is True
            assert g._call_api("prompt") is None

    assert len(calls) == 1
