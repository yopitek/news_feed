"""
Configuration loader for feeds.yaml and classification_rules.yaml
"""
import yaml
from pathlib import Path
from typing import Union

from .models import FeedsConfig, TabConfig, FeedSource


def load_feeds_config(path: Union[str, Path] = "config/feeds.yaml") -> FeedsConfig:
    """
    Load and validate RSS feed configuration.
    
    Args:
        path: Path to feeds.yaml file
    
    Returns:
        FeedsConfig object with all tab configurations
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"Feeds configuration not found: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Parse tabs
    tabs = {}
    for tab_id, tab_data in data.get('tabs', {}).items():
        sources = []
        for source_data in tab_data.get('sources', []):
            sources.append({
                'category': source_data.get('category', ''),
                'url': source_data.get('url', ''),
                'source_name': source_data.get('source_name')
            })
        
        tabs[tab_id] = TabConfig(
            name=tab_data.get('name', tab_id),
            language=tab_data.get('language', 'en'),
            item_limit=tab_data.get('item_limit', 5),
            sources=sources
        )
    
    return FeedsConfig(
        tabs=tabs,
        settings=data.get('settings', {})
    )


def load_classification_rules(path: Union[str, Path] = "config/classification_rules.yaml") -> dict:
    """
    Load Chinese category classification rules.
    
    Args:
        path: Path to classification_rules.yaml file
    
    Returns:
        Dictionary with classification rules
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"Classification rules not found: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# For convenience, also provide a class-based interface
class ConfigLoader:
    """Class-based configuration loader."""
    
    def __init__(self, config_dir: Union[str, Path] = "config"):
        self.config_dir = Path(config_dir)
        self._feeds_config = None
        self._classification_rules = None
    
    @property
    def feeds(self) -> FeedsConfig:
        """Lazy-load feeds configuration."""
        if self._feeds_config is None:
            self._feeds_config = load_feeds_config(self.config_dir / "feeds.yaml")
        return self._feeds_config
    
    @property
    def classification_rules(self) -> dict:
        """Lazy-load classification rules."""
        if self._classification_rules is None:
            self._classification_rules = load_classification_rules(
                self.config_dir / "classification_rules.yaml"
            )
        return self._classification_rules
    
    def reload(self):
        """Force reload all configurations."""
        self._feeds_config = None
        self._classification_rules = None
