# Step 5: DeepSeek Prompt Design

## 1. Overview

DeepSeek API is used for:
1. **Chinese Summary Generation** (中文新聞 + 中文產業新聞) — MANDATORY
2. **English Summary Generation** (English News) — Only when RSS lacks summary
3. **Japanese Summary Generation** (日本語ニュース) — Only when RSS lacks summary
4. **Chinese Classification** (Optional fallback)

---

## 2. API Configuration

```python
# DeepSeek API Configuration
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"  # or "deepseek-coder" for code-related

# Rate limits (adjust based on your plan)
MAX_REQUESTS_PER_MINUTE = 60
MAX_TOKENS_PER_REQUEST = 1024

# Timeout and retries
API_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # seconds
```

---

## 3. Chinese Summary Prompt (~150 characters)

### System Prompt

```
你是一位專業新聞編輯，擅長撰寫客觀中立的新聞摘要。你的摘要風格應該像《財經時報》或《路透社》的專業報導。
```

### User Prompt Template

```
請將以下新聞內容整理成約150個繁體中文字的摘要。

【規則】
1. 客觀中立，禁止評論、臆測或主觀判斷
2. 保留關鍵人事時地物、具體數字、重要時間點
3. 使用簡潔有力的新聞語言，避免冗詞贅字
4. 禁止使用列點形式，以流暢段落呈現
5. 禁止使用emoji、感嘆號或誇張語氣
6. 若原文內容不足，請以現有內容濃縮，不要補充外部資訊
7. 字數目標150字（允許範圍130-170字）

【新聞標題】
{title}

【新聞來源】
{source_name}

【新聞內容】
{content}

【輸出格式】
只輸出摘要正文，不要標題、不要引號、不要額外說明。
```

### Response Validation

```python
def validate_chinese_summary(summary: str) -> tuple[bool, str]:
    """
    Validate Chinese summary meets requirements.
    
    Returns:
        (is_valid, cleaned_summary or error_message)
    """
    # Remove quotes if wrapped
    summary = summary.strip().strip('"').strip('"').strip('"')
    
    # Count Chinese characters
    import re
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', summary)
    char_count = len(chinese_chars)
    
    # Validate length
    if char_count < 50:
        return False, "Summary too short (< 50 chars)"
    
    if char_count > 200:
        # Truncate to ~170 chars
        summary = summary[:180].rsplit('。', 1)[0] + '。'
    
    # Check for forbidden patterns
    forbidden = ['！', '😀', '🎉', '👍', '❗', '?!', '!!']
    for pattern in forbidden:
        if pattern in summary:
            summary = summary.replace(pattern, '。')
    
    return True, summary
```

---

## 4. English Summary Prompt (~150 words)

### When to Use

| Condition                          | Action                                    |
|-----------------------------------|-------------------------------------------|
| RSS provides summary/description  | Truncate cleanly (no API call)            |
| RSS summary missing or too short  | Generate via DeepSeek API                 |

### System Prompt

```
You are a professional news editor specializing in concise, objective news summaries. Write in a neutral, authoritative style similar to Reuters or BBC News.
```

### User Prompt Template

```
Summarize the following news article in approximately 150 words.

【Rules】
1. Maintain strict objectivity - no opinions, speculation, or editorial commentary
2. Preserve key facts: who, what, when, where, why, and how
3. Include specific numbers, dates, and names when available
4. Write in clear, professional English prose (no bullet points)
5. Do not add information not present in the original content
6. If the content is insufficient, summarize what is available concisely
7. Target: 150 words (acceptable range: 120-180 words)

【Article Title】
{title}

【Source】
{source_name}

【Article Content】
{content}

【Output】
Write only the summary paragraph. No title, no quotes, no additional commentary.
```

### RSS Summary Truncation (Preferred)

```python
def truncate_english_summary(text: str, max_words: int = 150) -> str:
    """
    Cleanly truncate English text to approximately max_words.
    Preserves complete sentences.
    """
    if not text:
        return ""
    
    words = text.split()
    
    if len(words) <= max_words:
        return text
    
    # Find sentence boundary near target
    truncated = ' '.join(words[:max_words])
    
    # Try to end at sentence boundary
    for punct in ['. ', '? ', '! ']:
        last_punct = truncated.rfind(punct)
        if last_punct > len(truncated) * 0.7:  # At least 70% of target
            return truncated[:last_punct + 1]
    
    # Fallback: end at word boundary with ellipsis
    return truncated.rsplit(' ', 1)[0] + '...'
```

---

## 5. Japanese Summary Prompt (~150 characters)

### When to Use

| Condition                          | Action                                    |
|-----------------------------------|-------------------------------------------|
| RSS provides summary/description  | Truncate cleanly (no API call)            |
| RSS summary missing or too short  | Generate via DeepSeek API                 |

### System Prompt

```
あなたはプロのニュース編集者です。客観的で中立的なニュース要約を作成することを専門としています。NHKや共同通信のような報道スタイルで書いてください。
```

### User Prompt Template

```
以下のニュース記事を約150文字の日本語で要約してください。

【ルール】
1. 客観的かつ中立的に記述し、意見や推測を含めない
2. 重要な事実（誰が、何を、いつ、どこで、なぜ、どのように）を保持する
3. 具体的な数字、日付、名前があれば含める
4. 箇条書きではなく、流暢な文章で書く
5. 元の内容にない情報を追加しない
6. 内容が不十分な場合は、利用可能な内容を簡潔に要約する
7. 目標：150文字（許容範囲：130〜170文字）

【記事タイトル】
{title}

【ソース】
{source_name}

【記事内容】
{content}

【出力】
要約本文のみを出力してください。タイトル、引用符、追加のコメントは不要です。
```

### RSS Summary Truncation (Preferred)

```python
def truncate_japanese_summary(text: str, max_chars: int = 150) -> str:
    """
    Cleanly truncate Japanese text to approximately max_chars.
    Preserves complete sentences.
    """
    if not text:
        return ""
    
    if len(text) <= max_chars:
        return text
    
    # Find sentence boundary (。) near target
    truncated = text[:max_chars]
    
    # Try to end at sentence boundary
    last_period = truncated.rfind('。')
    if last_period > max_chars * 0.7:  # At least 70% of target
        return truncated[:last_period + 1]
    
    # Fallback: end at word/character with ellipsis
    return truncated[:max_chars - 3] + '…'
```

---

## 6. Chinese Classification Prompt (Optional)

### System Prompt

```
你是新聞分類助手。你的任務是將新聞準確分類到指定類別中。
```

### User Prompt Template

```
請將以下新聞分類到其中一個類別（只輸出類別名稱）：

【可選類別】
產經、股市、頭條新聞、娛樂、生活、運動、全球國際新聞、社會、房市

【分類指南】
- 產經：經濟、產業、企業、科技業務相關
- 股市：股票、證券、金融市場相關
- 頭條新聞：政治、政府政策、重大事件
- 娛樂：演藝圈、明星、電影電視
- 生活：健康、美食、旅遊、消費
- 運動：體育賽事、運動員
- 全球國際新聞：國際事務、外國新聞
- 社會：社會事件、犯罪、意外
- 房市：房地產、住宅市場

【新聞標題】
{title}

【新聞內容】
{content}

【輸出】
只輸出一個類別名稱，不要其他說明。
```

---

## 7. DeepSeek API Implementation

### Complete Summarizer Module

```python
"""
summarizer.py - DeepSeek API integration for news summarization
"""
import time
import requests
from typing import Optional
import logging

from .models import NormalizedArticle, ArticleWithSummary

logger = logging.getLogger(__name__)

# Configuration
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
API_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]


class DeepSeekSummarizer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def _call_api(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Call DeepSeek API with retry logic.
        """
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,  # Lower temperature for factual content
            "max_tokens": 512
        }
        
        for attempt, backoff in enumerate(RETRY_BACKOFF):
            try:
                response = requests.post(
                    DEEPSEEK_API_BASE,
                    headers=self.headers,
                    json=payload,
                    timeout=API_TIMEOUT
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content'].strip()
                
                elif response.status_code == 429:  # Rate limited
                    logger.warning(f"Rate limited, waiting {backoff}s before retry")
                    time.sleep(backoff)
                    continue
                
                else:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(backoff)
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"API timeout, attempt {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(backoff)
                    continue
                return None
                
            except Exception as e:
                logger.error(f"API call failed: {e}")
                return None
        
        return None
    
    def summarize_chinese(self, article: NormalizedArticle) -> str:
        """
        Generate Chinese summary (~150 chars).
        Falls back to RSS description if API fails.
        """
        system_prompt = """你是一位專業新聞編輯，擅長撰寫客觀中立的新聞摘要。你的摘要風格應該像《財經時報》或《路透社》的專業報導。"""
        
        content = article.description or article.title
        
        user_prompt = f"""請將以下新聞內容整理成約150個繁體中文字的摘要。

【規則】
1. 客觀中立，禁止評論、臆測或主觀判斷
2. 保留關鍵人事時地物、具體數字、重要時間點
3. 使用簡潔有力的新聞語言，避免冗詞贅字
4. 禁止使用列點形式，以流暢段落呈現
5. 禁止使用emoji、感嘆號或誇張語氣
6. 若原文內容不足，請以現有內容濃縮，不要補充外部資訊
7. 字數目標150字（允許範圍130-170字）

【新聞標題】
{article.title}

【新聞來源】
{article.source_name}

【新聞內容】
{content}

【輸出格式】
只輸出摘要正文，不要標題、不要引號、不要額外說明。"""
        
        result = self._call_api(system_prompt, user_prompt)
        
        if result:
            # Validate and clean
            result = result.strip().strip('"').strip('"').strip('"')
            return result
        
        # Fallback: use RSS description or title
        return self._fallback_chinese(article)
    
    def _fallback_chinese(self, article: NormalizedArticle) -> str:
        """Fallback summary from RSS description."""
        if article.description and len(article.description) > 20:
            # Truncate to ~150 chars
            desc = article.description
            if len(desc) > 170:
                desc = desc[:160].rsplit('，', 1)[0]
                if not desc.endswith('。'):
                    desc += '。'
            return desc
        return article.title
    
    def summarize_english(self, article: NormalizedArticle) -> str:
        """
        Generate English summary (~150 words).
        Prefers RSS description if available.
        """
        # First try to use RSS description
        if article.description and len(article.description.split()) > 30:
            return self._truncate_english(article.description)
        
        # Generate via API
        system_prompt = """You are a professional news editor specializing in concise, objective news summaries. Write in a neutral, authoritative style similar to Reuters or BBC News."""
        
        content = article.description or article.title
        
        user_prompt = f"""Summarize the following news article in approximately 150 words.

【Rules】
1. Maintain strict objectivity - no opinions, speculation, or editorial commentary
2. Preserve key facts: who, what, when, where, why, and how
3. Include specific numbers, dates, and names when available
4. Write in clear, professional English prose (no bullet points)
5. Do not add information not present in the original content
6. Target: 150 words (acceptable range: 120-180 words)

【Article Title】
{article.title}

【Source】
{article.source_name}

【Article Content】
{content}

【Output】
Write only the summary paragraph. No title, no quotes, no additional commentary."""
        
        result = self._call_api(system_prompt, user_prompt)
        
        if result:
            return result.strip()
        
        # Fallback
        return self._truncate_english(article.description or article.title)
    
    def _truncate_english(self, text: str, max_words: int = 150) -> str:
        """Truncate English text to max words."""
        if not text:
            return ""
        
        words = text.split()
        if len(words) <= max_words:
            return text
        
        truncated = ' '.join(words[:max_words])
        
        # Try to end at sentence boundary
        for punct in ['. ', '? ', '! ']:
            last = truncated.rfind(punct)
            if last > len(truncated) * 0.7:
                return truncated[:last + 1]
        
        return truncated.rsplit(' ', 1)[0] + '...'
    
    def summarize_japanese(self, article: NormalizedArticle) -> str:
        """
        Generate Japanese summary (~150 chars).
        Prefers RSS description if available.
        """
        # First try to use RSS description
        if article.description and len(article.description) > 50:
            return self._truncate_japanese(article.description)
        
        # Generate via API
        system_prompt = """あなたはプロのニュース編集者です。客観的で中立的なニュース要約を作成することを専門としています。NHKや共同通信のような報道スタイルで書いてください。"""
        
        content = article.description or article.title
        
        user_prompt = f"""以下のニュース記事を約150文字の日本語で要約してください。

【ルール】
1. 客観的かつ中立的に記述し、意見や推測を含めない
2. 重要な事実（誰が、何を、いつ、どこで、なぜ、どのように）を保持する
3. 具体的な数字、日付、名前があれば含める
4. 箇条書きではなく、流暢な文章で書く
5. 元の内容にない情報を追加しない
6. 目標：150文字（許容範囲：130〜170文字）

【記事タイトル】
{article.title}

【ソース】
{article.source_name}

【記事内容】
{content}

【出力】
要約本文のみを出力してください。タイトル、引用符、追加のコメントは不要です。"""
        
        result = self._call_api(system_prompt, user_prompt)
        
        if result:
            return result.strip()
        
        # Fallback
        return self._truncate_japanese(article.description or article.title)
    
    def _truncate_japanese(self, text: str, max_chars: int = 150) -> str:
        """Truncate Japanese text to max chars."""
        if not text:
            return ""
        
        if len(text) <= max_chars:
            return text
        
        truncated = text[:max_chars]
        last_period = truncated.rfind('。')
        
        if last_period > max_chars * 0.7:
            return truncated[:last_period + 1]
        
        return truncated[:max_chars - 1] + '…'
    
    def summarize(self, article: NormalizedArticle) -> str:
        """
        Summarize article based on language.
        """
        if article.language == 'zh':
            return self.summarize_chinese(article)
        elif article.language == 'en':
            return self.summarize_english(article)
        elif article.language == 'ja':
            return self.summarize_japanese(article)
        else:
            return article.description or article.title


def summarize_all(
    articles: dict[str, list[NormalizedArticle]], 
    api_key: str
) -> dict[str, list[ArticleWithSummary]]:
    """
    Summarize all selected articles.
    
    Args:
        articles: Dict of tab -> list of articles
        api_key: DeepSeek API key
    
    Returns:
        Dict of tab -> list of ArticleWithSummary
    """
    summarizer = DeepSeekSummarizer(api_key)
    result = {}
    
    for tab, tab_articles in articles.items():
        summarized = []
        for article in tab_articles:
            summary = summarizer.summarize(article)
            
            summarized.append(ArticleWithSummary(
                title=article.title,
                link=article.link,
                published=article.published,
                source_name=article.source_name,
                summary=summary,
                tab=article.tab,
                final_category=article.final_category
            ))
        
        result[tab] = summarized
    
    return result
```

---

## 8. Prompt Quality Guidelines

### DO ✅

- **Be specific**: Exact target counts (150 chars, 150 words)
- **Provide examples**: Show expected output style
- **Set boundaries**: Explicitly forbid unwanted behaviors
- **Use temperature 0.3**: More deterministic output

### DON'T ❌

- **Don't ask open questions**: "How would you summarize this?"
- **Don't allow creativity**: "Feel free to add your perspective"
- **Don't leave outputs undefined**: Always specify exact format
- **Don't use high temperature**: Leads to inconsistent output

---

## 9. Cost Estimation

| Operation            | Tokens (Input) | Tokens (Output) | Cost per Article |
|----------------------|----------------|-----------------|------------------|
| Chinese Summary      | ~500           | ~150            | ~$0.0005         |
| English Summary      | ~500           | ~200            | ~$0.0005         |
| Japanese Summary     | ~500           | ~200            | ~$0.0005         |
| Classification       | ~300           | ~10             | ~$0.0002         |

**Daily estimate**: 20 articles × $0.0005 = **~$0.01/day**

---

**Next Step**: Step 6 — HTML Templates
