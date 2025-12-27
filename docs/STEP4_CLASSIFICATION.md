# Step 4: Classification Rules

## 1. Overview

Classification is required **ONLY for Chinese content** (中文新聞 and 中文產業新聞 tabs).

English and Japanese content uses the RSS-defined category directly from `feeds.yaml` without reclassification.

---

## 2. Target Categories (Chinese Only)

The following 9 categories are the **ONLY** valid output categories:

| Category         | Description                        |
|------------------|-----------------------------------|
| `頭條新聞`        | Breaking news, major headlines    |
| `產經`           | Economy, business, industry       |
| `股市`           | Stock market, finance             |
| `全球國際新聞`    | International, world news         |
| `社會`           | Society, crime, local incidents   |
| `生活`           | Lifestyle, health, consumer       |
| `娛樂`           | Entertainment, celebrity          |
| `運動`           | Sports                            |
| `房市`           | Real estate, housing market       |

---

## 3. Classification Strategy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        CLASSIFICATION DECISION TREE                              │
└─────────────────────────────────────────────────────────────────────────────────┘

For each Chinese article:
    │
    ├─▶ [STEP 1] RSS CATEGORY MAPPING
    │     │
    │     ├─ RSS category maps directly to target category?
    │     │   YES → Use mapped category → DONE
    │     │
    │     └─ NO (unmapped or ambiguous)
    │           │
    │           ▼
    ├─▶ [STEP 2] KEYWORD RULES
    │     │
    │     ├─ Title contains keywords matching a category?
    │     │   YES → Use matched category → DONE
    │     │
    │     └─ NO (no keyword match)
    │           │
    │           ▼
    ├─▶ [STEP 3] SOURCE-BASED DEFAULT
    │     │
    │     ├─ Source feed has a default category?
    │     │   YES → Use source default → DONE
    │     │
    │     └─ NO
    │           │
    │           ▼
    └─▶ [STEP 4] FALLBACK TO 頭條新聞
          │
          └─ Assign to 頭條新聞 → DONE

```

---

## 4. RSS Category Mapping Rules

### Primary Mapping (from CNA feeds)

| RSS Feed URL Pattern         | RSS Category | Target Category   |
|------------------------------|--------------|-------------------|
| `/rsscna/politics`           | 政治         | 頭條新聞          |
| `/rsscna/intworld`           | 國際         | 全球國際新聞      |
| `/rsscna/mainland`           | 兩岸         | 全球國際新聞      |
| `/rsscna/technology`         | 科技         | 產經              |
| `/rsscna/lifehealth`         | 生活健康     | 生活              |
| `/rsscna/social`             | 社會         | 社會              |
| `/rsscna/local`              | 地方         | 社會              |
| `/rsscna/culture`            | 文化         | 生活              |
| `/rsscna/sport`              | 運動         | 運動              |
| `/rsscna/stars`              | 娛樂         | 娛樂              |

### Category Mapping Table (YAML format)

```yaml
# classification_rules.yaml

# Direct RSS category to target category mapping
rss_to_target_mapping:
  # CNA Categories
  政治: 頭條新聞
  國際: 全球國際新聞
  兩岸: 全球國際新聞
  科技: 產經
  生活: 生活
  生活健康: 生活
  社會: 社會
  地方: 社會
  文化: 生活
  運動: 運動
  娛樂: 娛樂
  
  # Custom categories from feeds.yaml
  產經: 產經
  股市: 股市
  房市: 房市
  頭條: 頭條新聞
  頭條新聞: 頭條新聞
  全球國際新聞: 全球國際新聞
```

---

## 5. Keyword Rules

When RSS category mapping fails, use keyword-based classification.

### Keyword Ruleset

```yaml
# classification_rules.yaml (continued)

keyword_rules:
  股市:
    - keywords: [股票, 股市, 股價, 上市, 上櫃, 台股, 美股, 港股, 陸股, 期貨, 選擇權, 指數, 成交量, 漲停, 跌停, 融資, 融券, 外資, 投信, 自營商, 法人, 買超, 賣超, 證交所, 櫃買中心, IPO, 除權息, 殖利率, 本益比, EPS, 財報]
    - priority: 1  # High priority (check first)
  
  房市:
    - keywords: [房市, 房價, 房貸, 買房, 賣房, 租房, 租金, 房屋, 住宅, 豪宅, 預售屋, 中古屋, 建案, 建商, 土地, 地價, 容積率, 建蔽率, 都更, 危老, 社會住宅, 青年安心, 房仲, 591, 信義, 永慶, 房產]
    - priority: 1
  
  產經:
    - keywords: [景氣, GDP, 經濟, 物價, 通膨, 利率, 央行, 匯率, 貿易, 出口, 進口, 製造業, 服務業, 產業, 企業, 公司, 科技業, 半導體, 晶片, 台積電, 鴻海, 電子業, 營收, 獲利, 財報, 供應鏈]
    - priority: 2
  
  全球國際新聞:
    - keywords: [美國, 日本, 韓國, 中國, 歐洲, 俄羅斯, 烏克蘭, 中東, 以色列, 聯合國, 北約, WHO, WTO, G7, G20, 白宮, 國務院, 外交, 峰會, 制裁, 戰爭, 衝突]
    - priority: 2
  
  運動:
    - keywords: [棒球, 籃球, 足球, 網球, 高爾夫, 羽球, 桌球, 游泳, 田徑, 奧運, 亞運, 世錦賽, 中職, CPBL, NBA, MLB, 英超, 歐冠, 世界盃, 大谷翔平, LeBron, 球員, 教練, 比賽, 冠軍]
    - priority: 2
  
  娛樂:
    - keywords: [明星, 藝人, 偶像, 演員, 歌手, 電影, 電視, 戲劇, 綜藝, 演唱會, 金曲獎, 金馬獎, 金鐘獎, Netflix, 串流, MV, 專輯, 拍攝, 緋聞, 結婚, 離婚]
    - priority: 2
  
  社會:
    - keywords: [警方, 警察, 檢察, 法院, 法官, 判刑, 起訴, 逮捕, 犯罪, 詐騙, 毒品, 車禍, 火災, 意外, 死亡, 受傷, 失蹤, 民眾, 抗議, 陳情]
    - priority: 3
  
  生活:
    - keywords: [健康, 醫療, 疫苗, 疫情, COVID, 流感, 醫院, 醫師, 藥物, 飲食, 美食, 旅遊, 觀光, 天氣, 氣象, 颱風, 地震, 環保, 交通, 捷運, 高鐵, 台鐵]
    - priority: 3
  
  頭條新聞:
    - keywords: [總統, 行政院, 立法院, 院長, 部長, 政府, 政策, 選舉, 民調, 立委, 議員, 縣市長]
    - priority: 4  # Lower priority (classify as headline if nothing else matches)
```

### Keyword Matching Logic

```python
def classify_by_keywords(title: str, description: str, rules: dict) -> Optional[str]:
    """
    Classify article by keyword matching.
    
    Args:
        title: Article title
        description: Article description (optional)
        rules: Keyword rules dictionary
    
    Returns:
        Category name or None if no match
    """
    text = f"{title} {description or ''}".lower()
    
    # Sort rules by priority (lower number = higher priority)
    sorted_rules = sorted(rules.items(), key=lambda x: x[1].get('priority', 99))
    
    for category, rule_data in sorted_rules:
        keywords = rule_data.get('keywords', [])
        for keyword in keywords:
            if keyword.lower() in text:
                return category
    
    return None
```

---

## 6. Source-Based Default Categories

Some feeds should default to a specific category if no other classification applies:

```yaml
# classification_rules.yaml (continued)

source_defaults:
  # CNA Feed URL patterns → Default category
  "rsscna/politics": 頭條新聞
  "rsscna/intworld": 全球國際新聞
  "rsscna/mainland": 全球國際新聞
  "rsscna/technology": 產經
  "rsscna/lifehealth": 生活
  "rsscna/social": 社會
  "rsscna/local": 社會
  "rsscna/culture": 生活
  "rsscna/sport": 運動
  "rsscna/stars": 娛樂
```

---

## 7. Complete Classification Algorithm

```python
"""
classifier.py - Chinese article classification
"""
from typing import Optional
import yaml

from .models import NormalizedArticle


class Classifier:
    def __init__(self, rules_path: str = "config/classification_rules.yaml"):
        with open(rules_path, 'r', encoding='utf-8') as f:
            self.rules = yaml.safe_load(f)
        
        self.rss_mapping = self.rules.get('rss_to_target_mapping', {})
        self.keyword_rules = self.rules.get('keyword_rules', {})
        self.source_defaults = self.rules.get('source_defaults', {})
        
        # Valid categories
        self.valid_categories = {
            '頭條新聞', '產經', '股市', '全球國際新聞',
            '社會', '生活', '娛樂', '運動', '房市'
        }
    
    def classify(self, article: NormalizedArticle) -> str:
        """
        Classify a Chinese article into one of the valid categories.
        
        Classification order:
        1. RSS category mapping
        2. Keyword rules
        3. Source-based default
        4. Fallback to 頭條新聞
        """
        # Only classify Chinese articles
        if article.language != 'zh':
            return article.rss_category
        
        # STEP 1: RSS Category Mapping
        if article.rss_category in self.rss_mapping:
            mapped = self.rss_mapping[article.rss_category]
            if mapped in self.valid_categories:
                return mapped
        
        # STEP 2: Keyword Rules
        keyword_match = self._classify_by_keywords(
            article.title, 
            article.description or ''
        )
        if keyword_match:
            return keyword_match
        
        # STEP 3: Source-Based Default
        for pattern, default_category in self.source_defaults.items():
            if pattern in article.link or pattern in (article.source_name or ''):
                if default_category in self.valid_categories:
                    return default_category
        
        # STEP 4: Fallback
        return '頭條新聞'
    
    def _classify_by_keywords(self, title: str, description: str) -> Optional[str]:
        """Match keywords in title/description."""
        text = f"{title} {description}".lower()
        
        # Sort by priority
        sorted_rules = sorted(
            self.keyword_rules.items(),
            key=lambda x: x[1][0].get('priority', 99) if isinstance(x[1], list) else x[1].get('priority', 99)
        )
        
        for category, rule_data in sorted_rules:
            # Handle both list and dict formats
            if isinstance(rule_data, list):
                rule = rule_data[0]
            else:
                rule = rule_data
            
            keywords = rule.get('keywords', [])
            for keyword in keywords:
                if keyword.lower() in text:
                    if category in self.valid_categories:
                        return category
        
        return None


def classify_articles(
    articles: list[NormalizedArticle],
    rules_path: str = "config/classification_rules.yaml"
) -> list[NormalizedArticle]:
    """
    Classify all Chinese articles.
    
    Returns articles with final_category set.
    """
    classifier = Classifier(rules_path)
    
    for article in articles:
        if article.language == 'zh':
            article.final_category = classifier.classify(article)
        else:
            # For EN/JA, use RSS category as-is
            article.final_category = article.rss_category
    
    return articles
```

---

## 8. Classification Examples

| Title                                          | RSS Category | Keywords Found | Final Category   |
|------------------------------------------------|--------------|----------------|------------------|
| 台股收盤大漲200點 外資買超百億                | 股市         | (direct map)   | 股市             |
| 台積電法說會 營收創新高                        | 科技         | 台積電, 營收   | 產經             |
| 北部房價創新高 專家:恐再漲                     | 生活         | 房價           | 房市             |
| 美國總統拜登訪日 雙邊關係升級                  | 國際         | 美國, 日本     | 全球國際新聞    |
| 中職冠軍賽 統一獅奪冠                          | 運動         | 中職, 冠軍     | 運動             |
| 知名歌手宣布結婚 粉絲祝福                      | 娛樂         | 歌手, 結婚     | 娛樂             |
| 新北市長宣布重大政策                           | 政治         | (source default) | 頭條新聞       |

---

## 9. Optional: LLM Classification (DeepSeek)

If deterministic rules fail for ambiguous cases, LLM classification can be used as **optional enhancement**:

```python
def classify_with_llm(article: NormalizedArticle, api_key: str) -> str:
    """
    Use DeepSeek API for ambiguous classification.
    Only called if deterministic classification returns '頭條新聞' as fallback.
    """
    prompt = f"""你是新聞分類助手。請將以下新聞分類到其中一類（只輸出類別名稱）：
[產經, 股市, 頭條新聞, 娛樂, 生活, 運動, 全球國際新聞, 社會, 房市]

新聞標題：{article.title}

新聞內容：{article.description or '(無內容)'}

只輸出一個類別名稱。"""
    
    # Call DeepSeek API (implementation in summarizer.py)
    result = call_deepseek(prompt, api_key)
    
    # Validate result
    valid = {'產經', '股市', '頭條新聞', '娛樂', '生活', '運動', '全球國際新聞', '社會', '房市'}
    result = result.strip()
    
    if result in valid:
        return result
    
    # If LLM returns invalid category, fallback to 頭條新聞
    return '頭條新聞'
```

⚠️ **LLM classification is OPTIONAL and should only be used when deterministic rules return fallback.**

---

**Next Step**: Step 5 — DeepSeek Prompt Design
