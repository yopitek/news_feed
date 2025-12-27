"""
Tests for the deduper module.
"""
import pytest
from datetime import datetime, timezone, timedelta

from src.models import NormalizedArticle
from src.deduper import deduplicate, normalize_title_for_comparison


class TestNormalizeTitleForComparison:
    """Tests for title normalization."""
    
    def test_lowercases_text(self):
        result = normalize_title_for_comparison("Hello WORLD")
        assert result == "hello world"
    
    def test_removes_punctuation(self):
        result = normalize_title_for_comparison("Hello, World!")
        assert result == "hello world"
    
    def test_collapses_whitespace(self):
        result = normalize_title_for_comparison("Hello   World")
        assert result == "hello world"


class TestDeduplicate:
    """Tests for deduplication."""
    
    def create_article(
        self, 
        title: str = "Test Article",
        link: str = "https://example.com/article",
        guid: str = None,
        source_name: str = "Test Source",
        published: datetime = None,
        tab: str = "zh_news"
    ) -> NormalizedArticle:
        """Helper to create test articles."""
        return NormalizedArticle(
            title=title,
            link=link,
            published=published or datetime.now(timezone.utc),
            source_name=source_name,
            language="zh",
            tab=tab,
            rss_category="Test",
            guid=guid or link,
            description=None,
            final_category=None
        )
    
    def test_removes_guid_duplicates(self):
        now = datetime.now(timezone.utc)
        articles = [
            self.create_article(title="Article 1", guid="same-guid", published=now),
            self.create_article(title="Article 2", guid="same-guid", published=now - timedelta(hours=1)),
        ]
        result = deduplicate(articles)
        assert len(result) == 1
        assert result[0].title == "Article 1"  # Newer one kept
    
    def test_removes_url_duplicates(self):
        now = datetime.now(timezone.utc)
        articles = [
            self.create_article(title="Article 1", link="https://example.com/same", guid="guid1", published=now),
            self.create_article(title="Article 2", link="https://example.com/same", guid="guid2", published=now - timedelta(hours=1)),
        ]
        result = deduplicate(articles)
        assert len(result) == 1
    
    def test_removes_title_duplicates_same_source(self):
        now = datetime.now(timezone.utc)
        articles = [
            self.create_article(
                title="Breaking News Today",
                link="https://example.com/1",
                guid="guid1",
                source_name="Same Source",
                published=now
            ),
            self.create_article(
                title="Breaking News Today",
                link="https://example.com/2",
                guid="guid2",
                source_name="Same Source",
                published=now - timedelta(hours=1)
            ),
        ]
        result = deduplicate(articles)
        assert len(result) == 1
    
    def test_keeps_different_articles(self):
        articles = [
            self.create_article(title="Article 1", link="https://example.com/1", guid="guid1"),
            self.create_article(title="Article 2", link="https://example.com/2", guid="guid2"),
            self.create_article(title="Article 3", link="https://example.com/3", guid="guid3"),
        ]
        result = deduplicate(articles)
        assert len(result) == 3
    
    def test_handles_empty_list(self):
        result = deduplicate([])
        assert result == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
