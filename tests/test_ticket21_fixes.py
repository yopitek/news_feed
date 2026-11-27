"""
Regression tests for the bugs fixed under OpenBot ticket 21.

All tests run offline: SMTP is replaced by a fake recorder and the weekly
pipeline's network search step is monkeypatched. Nothing connects to any
network, inbox, or external API.
"""
import logging
from datetime import datetime, timezone
from email.header import decode_header, make_header

import pytest

import src.mailer as mailer
import src.weekly_main as weekly_main
from src.models import ArticleWithSummary
from src.renderer_email import render_news_item_email
from src.renderer_web import render_news_item
from src.twitter_searcher import TweetResult
from src.weekly_renderer import WeeklyItem, _render_item_html

ENV_KEYS = (
    "SMTP_HOST", "SMTP_SERVER", "SMTP_PORT", "SMTP_USER", "SMTP_USERNAME",
    "SMTP_PASSWORD", "EMAIL_RECIPIENT", "EMAIL_SUBJECT_PREFIX",
    "TAVILY_API_KEY", "NVIDIA_API_KEY", "NVIDIA_MODEL", "DEEPSEEK_API_KEY",
)


def fake_env(monkeypatch, **extra):
    """Start from a clean env so the host machine's variables cannot leak in."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in extra.items():
        monkeypatch.setenv(key, value)


class FakeSMTPSSL:
    """Stand-in for smtplib.SMTP_SSL that records messages and never connects."""

    captured = []

    def __init__(self, host, port, **kwargs):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTPSSL.captured.append(msg)


def html_parts(msg):
    return [
        part.get_payload(decode=True).decode("utf-8", "replace")
        for part in msg.walk()
        if part.get_content_type() == "text/html"
    ]


def subject_of(msg):
    return str(make_header(decode_header(str(msg["Subject"]))))


def fake_tweets(n=4):
    return [
        TweetResult(
            handle=f"handle{i}", title=f"tool {i}", url=f"https://x.com/i/{i}",
            content="a practical workflow tip " * 10, score=0.9,
            published_date="", priority=1,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------- B1 weekly email

class TestWeeklyDigestEmail:
    def test_weekly_pipeline_sends_the_weekly_html_and_subject(self, monkeypatch, tmp_path, caplog):
        """The weekly run must hand its own HTML + subject to the mailer, not crash."""
        FakeSMTPSSL.captured = []
        fake_env(
            monkeypatch,
            EMAIL_RECIPIENT="reader@example.com",
            SMTP_HOST="smtp.invalid", SMTP_PORT="465",
            SMTP_USER="sender", SMTP_PASSWORD="pw",
            TAVILY_API_KEY="fake-offline-key",
        )
        monkeypatch.setattr(weekly_main, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTPSSL)
        monkeypatch.setattr(weekly_main, "run_all_searches", lambda key, path: fake_tweets())

        html = weekly_main.run_weekly_pipeline()

        assert FakeSMTPSSL.captured, "weekly email never reached SMTP"
        msg = FakeSMTPSSL.captured[-1]
        assert "AI乾貨週報" in subject_of(msg)
        bodies = html_parts(msg)
        assert bodies and "item-block" in bodies[0]
        assert bodies[0] == html

    def test_daily_default_path_is_unchanged(self, monkeypatch, tmp_path):
        """send_digest_email() with no args still reads the daily file (regression guard)."""
        FakeSMTPSSL.captured = []
        (tmp_path / "email_digest.html").write_text("<html>daily</html>", encoding="utf-8")
        fake_env(
            monkeypatch,
            EMAIL_RECIPIENT="reader@example.com",
            SMTP_HOST="smtp.invalid", SMTP_PORT="465",
            SMTP_USER="sender", SMTP_PASSWORD="pw",
        )
        monkeypatch.setattr(mailer, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTPSSL)

        assert mailer.send_digest_email() is True
        assert "<html>daily</html>" in html_parts(FakeSMTPSSL.captured[-1])[0]

    def test_email_failure_logs_the_underlying_cause_and_flow_survives(self, monkeypatch, tmp_path, caplog):
        monkeypatch.setattr(weekly_main, "OUTPUT_DIR", tmp_path)
        fake_env(monkeypatch, TAVILY_API_KEY="fake-offline-key")
        monkeypatch.setattr(weekly_main, "run_all_searches", lambda key, path: fake_tweets())

        def boom(*args, **kwargs):
            raise TypeError("boom")

        monkeypatch.setattr(mailer, "send_digest_email", boom)
        with caplog.at_level(logging.WARNING):
            weekly_main.run_weekly_pipeline()  # must not raise

        records = [r for r in caplog.records if "Email failed" in r.getMessage()]
        assert records, "email failure was not logged"
        assert records[-1].exc_info, "failure cause (traceback) was swallowed"


# ---------------------------------------------------------------- N2 empty SMTP_PORT

class TestSmtpPort:
    def test_empty_smtp_port_falls_back_to_default(self, monkeypatch):
        """GitHub Actions injects '' for an unset secret; int('') must not crash."""
        fake_env(monkeypatch, SMTP_HOST="smtp.invalid", SMTP_PORT="")
        config = mailer.get_smtp_config_from_env()
        assert config.port == 465
        assert config.use_ssl is True

    def test_real_smtp_port_still_wins(self, monkeypatch):
        fake_env(monkeypatch, SMTP_HOST="smtp.invalid", SMTP_PORT="587")
        assert mailer.get_smtp_config_from_env().port == 587


# ---------------------------------------------------------------- B2 weekly renderer escaping

def evil_item(**overrides):
    item = WeeklyItem(
        handle='evil"><script>alert(1)</script>',
        title_zh="<b>Title</b>",
        url='https://x.com/a" onclick="alert(1)',
        core_method=["<img src=x onerror=alert(1)>"],
        why_useful="<script>x</script>",
        type_icon="💡",
        priority=1,
    )
    for key, value in overrides.items():
        setattr(item, key, value)
    return item


class TestWeeklyRenderer:
    def test_untrusted_fields_are_escaped(self):
        out = _render_item_html(evil_item())
        assert "<script>" not in out
        assert "<img" not in out
        assert "<b>" not in out
        assert '" onclick=' not in out  # the quote cannot break out of href="..."

    def test_javascript_urls_are_neutralised(self):
        out = _render_item_html(evil_item(url="javascript:alert(1)"))
        assert "javascript:" not in out
        assert 'href="#"' in out

    def test_normal_https_item_is_rendered(self):
        item = WeeklyItem(handle="h", title_zh="標題", url="https://example.com/a?b=1",
                          core_method=["step"], why_useful="why", type_icon="💡", priority=1)
        out = _render_item_html(item)
        assert 'href="https://example.com/a?b=1"' in out
        assert "標題" in out and "@h" in out


# ---------------------------------------------------------------- B3 email renderer href

def news_article(link):
    return ArticleWithSummary(
        title="Test <Title>", link=link,
        published=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_name="Src", summary="", tab="news",
    )


class TestEmailRenderer:
    def test_link_is_attribute_escaped(self):
        out = render_news_item_email(news_article('https://example.com/" onmouseover="alert(1)'))
        assert '" onmouseover=' not in out
        assert "&quot;" in out

    def test_javascript_links_are_neutralised(self):
        out = render_news_item_email(news_article("javascript:alert(1)"))
        assert "javascript:" not in out
        assert 'href="#"' in out


# ---------------------------------------------------------------- N4 web renderer scheme

class TestWebRenderer:
    def test_javascript_links_are_neutralised(self):
        out = render_news_item(news_article("javascript:alert(1)"))
        assert "javascript:" not in out
        assert 'href="#"' in out
        assert 'data-link="#"' in out

    def test_normal_https_link_is_unchanged(self):
        out = render_news_item(news_article("https://example.com/a?b=1&c=2"))
        assert 'href="https://example.com/a?b=1&amp;c=2"' in out
