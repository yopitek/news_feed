"""Static validation for curated source configuration."""
from urllib.parse import urlparse

import yaml


def test_tech_blog_sources_have_valid_urls_and_groups():
    data = yaml.safe_load(open("config/tech_blogs.yaml", encoding="utf-8"))
    sources = data["tech_blogs"]["sources"]

    assert len(sources) == 18
    for source in sources:
        parsed = urlparse(source["url"])
        assert parsed.scheme in {"http", "https"}
        assert parsed.netloc
        assert source.get("source_name")
        assert source.get("group") in {
            "AI / ML",
            "Software Engineering",
            "Security",
            "Startups / Product",
            "Commentary",
        }


def test_twitter_accounts_are_unique_and_enriched():
    data = yaml.safe_load(open("config/twitter_accounts.yaml", encoding="utf-8"))
    accounts = data["accounts"]
    handles = [account["handle"].lower() for account in accounts]

    assert len(handles) == len(set(handles))
    assert "adityaagpriority" not in handles
    assert "adityaag" in handles
    for account in accounts:
        assert account.get("topic")
        assert account.get("reason")
        assert account.get("status") == "active"
