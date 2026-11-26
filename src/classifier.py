"""
Chinese article classification into predefined categories.
"""
import logging
from typing import Optional

from .models import NormalizedArticle

logger = logging.getLogger(__name__)

# Valid Chinese categories
VALID_CATEGORIES = {
    '頭條新聞', '產經', '股市', '全球國際新聞',
    '社會', '生活', '娛樂', '運動', '房市'
}


class Classifier:
    """Chinese article classifier."""
    
    def __init__(self, rules: dict):
        """
        Initialize classifier with rules.
        
        Args:
            rules: Classification rules dictionary from YAML
        """
        self.rules = rules
        self.rss_mapping = rules.get('rss_to_target_mapping', {})
        self.keyword_rules = rules.get('keyword_rules', {})
        self.source_defaults = rules.get('source_defaults', {})
        self.default_category = rules.get('default_category', '頭條新聞')
        # Title keywords that win over the RSS mapping (see classify()).
        self.priority_title_rules = rules.get('priority_title_rules', {}) or {}
        self.priority_skip_rss = set(rules.get('priority_title_skip_rss_categories', []) or [])
    
    def classify(self, article: NormalizedArticle) -> str:
        """
        Classify a Chinese article into one of the valid categories.
        
        Classification order:
        1. RSS category mapping
        2. Keyword rules
        3. Source-based default
        4. Fallback to default_category
        
        Args:
            article: Article to classify
        
        Returns:
            Category name
        """
        # Only classify Chinese articles
        if article.language != 'zh':
            return article.rss_category or ''
        
        # STEP 0: Priority title keywords.
        # Every CNA feed category is in rss_to_target_mapping, so STEP 1 always
        # returned first and the 股市 / 房市 keyword rules below were dead code:
        # both sections were empty on every run. A short, specific title keyword
        # list is checked first so a stock or housing story filed under 產經 or
        # 生活 lands in its own section.
        priority_match = self._classify_by_priority_title(article)
        if priority_match:
            return priority_match

        # STEP 1: RSS Category Mapping
        if article.rss_category in self.rss_mapping:
            mapped = self.rss_mapping[article.rss_category]
            if mapped in VALID_CATEGORIES:
                return mapped
        
        # STEP 2: Keyword Rules
        keyword_match = self._classify_by_keywords(
            article.title, 
            article.description or ''
        )
        if keyword_match:
            return keyword_match
        
        # STEP 3: Source-Based Default
        for pattern, default_cat in self.source_defaults.items():
            if pattern in article.link:
                if default_cat in VALID_CATEGORIES:
                    return default_cat
        
        # STEP 4: Fallback
        return self.default_category
    
    def _classify_by_priority_title(self, article: NormalizedArticle) -> Optional[str]:
        """Match the priority keyword lists against the title only."""
        if not self.priority_title_rules:
            return None
        if article.rss_category in self.priority_skip_rss:
            return None
        title = (article.title or '').lower()
        if not title:
            return None
        for category, keywords in self.priority_title_rules.items():
            if category not in VALID_CATEGORIES:
                continue
            for keyword in keywords or []:
                if str(keyword).lower() in title:
                    return category
        return None

    def _classify_by_keywords(self, title: str, description: str) -> Optional[str]:
        """Match keywords in title/description."""
        text = f"{title} {description}".lower()
        
        # Build list of (category, priority, keywords)
        rules_list = []
        for category, rule_data in self.keyword_rules.items():
            if isinstance(rule_data, dict):
                keywords = rule_data.get('keywords', [])
                priority = rule_data.get('priority', 99)
            else:
                # Handle potential list structure
                keywords = rule_data
                priority = 99
            rules_list.append((category, priority, keywords))
        
        # Sort by priority (lower = higher priority)
        rules_list.sort(key=lambda x: x[1])
        
        for category, priority, keywords in rules_list:
            for keyword in keywords:
                if keyword.lower() in text:
                    if category in VALID_CATEGORIES:
                        return category
        
        return None


def classify_articles(
    articles: list[NormalizedArticle],
    rules: dict
) -> list[NormalizedArticle]:
    """
    Classify all Chinese articles.
    
    Args:
        articles: List of normalized articles
        rules: Classification rules dictionary
    
    Returns:
        Articles with final_category set
    """
    classifier = Classifier(rules)
    classified_count = 0
    
    for article in articles:
        if article.language == 'zh':
            article.final_category = classifier.classify(article)
            classified_count += 1
        else:
            # For EN/JA, use RSS category as-is
            article.final_category = article.rss_category
    
    logger.info(f"Classified {classified_count} Chinese articles")
    return articles
