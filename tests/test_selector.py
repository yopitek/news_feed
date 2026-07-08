"""Tests for article selection behavior."""
from datetime import datetime, timezone, timedelta

from src.models import NormalizedArticle
from src.selector import select_by_category


def make_article(source_name: str, minutes_ago: int) -> NormalizedArticle:
    return NormalizedArticle(
        title=f"{source_name} article {minutes_ago}",
        link=f"https://example.com/{source_name}/{minutes_ago}",
        published=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        source_name=source_name,
        language="en",
        tab="tech_blogs",
        rss_category="Tech Blogs",
        guid=f"{source_name}-{minutes_ago}",
        description="summary",
    )


def test_tech_blogs_applies_per_source_cap():
    articles = [make_article("Simon Willison", i) for i in range(5)]
    articles += [make_article("Ed Zitron", 20 + i) for i in range(3)]
    articles += [make_article("Dwarkesh Patel", 40 + i) for i in range(3)]

    selected = select_by_category(articles)
    tech_articles = selected["tech_blogs"]["Tech Blogs"]

    counts = {}
    for article in tech_articles:
        counts[article.source_name] = counts.get(article.source_name, 0) + 1

    assert len(tech_articles) == 6
    assert counts == {
        "Simon Willison": 2,
        "Ed Zitron": 2,
        "Dwarkesh Patel": 2,
    }
