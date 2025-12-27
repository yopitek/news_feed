"""
Data models for the Daily Multilingual News Digest system.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RawFeedEntry:
    """Raw entry directly from feedparser."""
    title: str
    link: str
    published: Optional[str] = None
    summary: Optional[str] = None
    guid: Optional[str] = None
    source_feed_url: str = ""


@dataclass
class NormalizedArticle:
    """Normalized article with consistent schema."""
    title: str
    link: str
    published: datetime
    source_name: str
    language: str  # 'zh', 'en', 'ja'
    tab: str  # 'zh_news', 'zh_industry', 'en_news', 'ja_news'
    rss_category: str
    guid: str  # GUID or URL hash
    description: Optional[str] = None
    final_category: Optional[str] = None  # Assigned category (Chinese only)


@dataclass
class ArticleWithSummary:
    """Article with generated or extracted summary."""
    title: str
    link: str
    published: datetime
    source_name: str
    summary: str  # Generated or RSS description
    tab: str
    final_category: Optional[str] = None


@dataclass
class FeedSource:
    """Single RSS feed source configuration."""
    category: str
    url: str
    source_name: Optional[str] = None


@dataclass
class TabConfig:
    """Configuration for a single tab."""
    name: str
    language: str
    item_limit: int
    sources: list = field(default_factory=list)


@dataclass
class FeedsConfig:
    """Complete feeds configuration."""
    tabs: dict = field(default_factory=dict)  # tab_id -> TabConfig
    settings: dict = field(default_factory=dict)
    
    def get_all_sources(self) -> list:
        """Get all feed sources across all tabs."""
        sources = []
        for tab_id, tab_config in self.tabs.items():
            for source in tab_config.sources:
                sources.append({
                    'tab': tab_id,
                    'language': tab_config.language,
                    **source
                })
        return sources


@dataclass
class SMTPConfig:
    """SMTP configuration for email sending."""
    host: str
    port: int
    user: str
    password: str
    use_ssl: bool = True
