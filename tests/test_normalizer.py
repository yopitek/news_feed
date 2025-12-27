"""
Tests for the normalizer module.
"""
import pytest
from datetime import datetime, timezone

from src.normalizer import strip_html, normalize_url, parse_datetime, generate_guid


class TestStripHtml:
    """Tests for HTML stripping."""
    
    def test_removes_html_tags(self):
        text = "<p>Hello <b>World</b></p>"
        result = strip_html(text)
        assert result == "Hello World"
    
    def test_decodes_html_entities(self):
        text = "Tom &amp; Jerry"
        result = strip_html(text)
        assert result == "Tom & Jerry"
    
    def test_normalizes_whitespace(self):
        text = "Hello    World\n\nTest"
        result = strip_html(text)
        assert result == "Hello World Test"
    
    def test_handles_empty_string(self):
        assert strip_html("") == ""
    
    def test_handles_none(self):
        assert strip_html(None) == ""


class TestNormalizeUrl:
    """Tests for URL normalization."""
    
    def test_removes_utm_params(self):
        url = "https://example.com/article?utm_source=twitter&utm_medium=social"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
    
    def test_removes_fbclid(self):
        url = "https://example.com/article?fbclid=abc123"
        result = normalize_url(url)
        assert "fbclid" not in result
    
    def test_preserves_important_params(self):
        url = "https://example.com/article?id=12345"
        result = normalize_url(url)
        assert "id=12345" in result
    
    def test_removes_trailing_slash(self):
        url = "https://example.com/article/"
        result = normalize_url(url)
        assert result.endswith("/article")
    
    def test_lowercases_domain(self):
        url = "HTTPS://EXAMPLE.COM/Article"
        result = normalize_url(url)
        assert "example.com" in result


class TestGenerateGuid:
    """Tests for GUID generation."""
    
    def test_uses_existing_id(self):
        entry = {'id': 'unique-id-123'}
        result = generate_guid(entry, 'https://example.com', 'Title')
        assert result == 'unique-id-123'
    
    def test_uses_guid_field(self):
        entry = {'guid': 'guid-456'}
        result = generate_guid(entry, 'https://example.com', 'Title')
        assert result == 'guid-456'
    
    def test_falls_back_to_link(self):
        entry = {}
        link = 'https://example.com/article'
        result = generate_guid(entry, link, 'Title')
        assert result == link
    
    def test_generates_hash_from_title(self):
        entry = {}
        result = generate_guid(entry, '', 'My Article Title')
        assert len(result) == 32  # MD5 hash length


class TestParseDatetime:
    """Tests for datetime parsing."""
    
    def test_parses_rfc822_format(self):
        entry = {'published': 'Wed, 25 Dec 2024 10:30:00 +0000'}
        result = parse_datetime(entry)
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 25
    
    def test_parses_iso_format(self):
        entry = {'published': '2024-12-25T10:30:00Z'}
        result = parse_datetime(entry)
        assert result.year == 2024
    
    def test_returns_utc_for_missing(self):
        entry = {}
        result = parse_datetime(entry)
        assert result.tzinfo is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
