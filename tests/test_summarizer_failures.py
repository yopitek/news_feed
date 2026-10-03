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
