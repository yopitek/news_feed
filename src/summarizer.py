"""
Summarizer module - supports Zeabur, DeepSeek, SiliconFlow, and Google Gemini APIs.
Updated for 200 character/word summaries.

Priority:
1. ZEABUR_API_KEY (Zeabur AI Hub - GPT-4o-mini, fast and reliable)
2. GOOGLE_API_KEY (Gemini - free tier)
3. SILICONFLOW_API_KEY (SiliconFlow - free DeepSeek model)
4. DEEPSEEK_API_KEY (DeepSeek direct API)
5. Fallback to RSS description (no API)
"""
import os
import time
import logging
from typing import Optional

import requests

from .models import NormalizedArticle, ArticleWithSummary

logger = logging.getLogger(__name__)

# Configuration - Zeabur AI Hub (recommended, fast and reliable)
ZEABUR_API_BASE = "https://hnd1.aihub.zeabur.ai/v1/chat/completions"
ZEABUR_MODEL = "gpt-4o-mini"

# Configuration - Google Gemini
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_MODEL = "gemini-2.0-flash"

# Configuration - SiliconFlow
SILICONFLOW_API_BASE = "https://api.siliconflow.cn/v1/chat/completions"
SILICONFLOW_MODEL = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"

# Configuration - DeepSeek
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# Shared settings
API_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 4, 8]

# Rate limiting for Gemini free tier (15 requests/minute)
GEMINI_RATE_LIMIT_DELAY = 4.5  # seconds between requests

# Summary lengths (200)
SUMMARY_LENGTH_ZH = 200
SUMMARY_LENGTH_EN = 200  # words
SUMMARY_LENGTH_JA = 200


class BaseSummarizer:
    """Base summarizer class with shared methods."""
    
    def __init__(self, api_key: str, api_base: str, model: str):
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def _call_api(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call API with retry logic."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 800,
            "stream": False
        }
        
        for attempt, backoff in enumerate(RETRY_BACKOFF):
            try:
                response = requests.post(
                    self.api_base,
                    headers=self.headers,
                    json=payload,
                    timeout=API_TIMEOUT
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content'].strip()
                
                elif response.status_code == 429:
                    logger.warning(f"Rate limited, waiting {backoff}s")
                    time.sleep(backoff)
                    continue
                
                else:
                    logger.error(f"API error {response.status_code}: {response.text[:200]}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(backoff)
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"API timeout, attempt {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(backoff)
                continue
                
            except Exception as e:
                logger.error(f"API call failed: {e}")
                return None
        
        return None
    
    def _get_chinese_prompt(self, article: NormalizedArticle) -> tuple[str, str]:
        """Get prompts for Chinese summarization."""
        system_prompt = """你是一位專業新聞編輯，擅長撰寫客觀中立的新聞摘要。你的摘要風格應該像《財經時報》或《路透社》的專業報導。"""
        
        content = article.description or article.title
        
        user_prompt = f"""請將以下新聞內容整理成約200個繁體中文字的摘要。

【規則】
1. 客觀中立，禁止評論、臆測或主觀判斷
2. 保留關鍵人事時地物、具體數字、重要時間點
3. 使用簡潔有力的新聞語言，避免冗詞贅字
4. 禁止使用列點形式，以流暢段落呈現
5. 禁止使用emoji、感嘆號或誇張語氣
6. 若原文內容不足，請以現有內容濃縮，不要補充外部資訊
7. 字數目標200字（允許範圍180-220字）

【新聞標題】
{article.title}

【新聞來源】
{article.source_name}

【新聞內容】
{content}

【輸出格式】
只輸出摘要正文，不要標題、不要引號、不要額外說明。"""
        
        return system_prompt, user_prompt
    
    def _get_english_prompt(self, article: NormalizedArticle) -> tuple[str, str]:
        """Get prompts for English summarization."""
        system_prompt = """You are a professional news editor specializing in concise, objective news summaries. Write in a neutral, authoritative style similar to Reuters or BBC News."""
        
        content = article.description or article.title
        
        user_prompt = f"""Summarize the following news article in approximately 200 words.

【Rules】
1. Maintain strict objectivity - no opinions, speculation, or editorial commentary
2. Preserve key facts: who, what, when, where, why, and how
3. Include specific numbers, dates, and names when available
4. Write in clear, professional English prose (no bullet points)
5. Do not add information not present in the original content
6. Target: 200 words (acceptable range: 180-220 words)

【Article Title】
{article.title}

【Source】
{article.source_name}

【Article Content】
{content}

【Output】
Write only the summary paragraph. No title, no quotes, no additional commentary."""
        
        return system_prompt, user_prompt
    
    def _get_japanese_prompt(self, article: NormalizedArticle) -> tuple[str, str]:
        """Get prompts for Japanese summarization."""
        system_prompt = """あなたはプロのニュース編集者です。客観的で中立的なニュース要約を作成することを専門としています。NHKや共同通信のような報道スタイルで書いてください。"""
        
        content = article.description or article.title
        
        user_prompt = f"""以下のニュース記事を約200文字の日本語で要約してください。

【ルール】
1. 客観的かつ中立的に記述し、意見や推測を含めない
2. 重要な事実（誰が、何を、いつ、どこで、なぜ、どのように）を保持する
3. 具体的な数字、日付、名前があれば含める
4. 箇条書きではなく、流暢な文章で書く
5. 元の内容にない情報を追加しない
6. 目標：200文字（許容範囲：180〜220文字）

【記事タイトル】
{article.title}

【ソース】
{article.source_name}

【記事内容】
{content}

【出力】
要約本文のみを出力してください。タイトル、引用符、追加のコメントは不要です。"""
        
        return system_prompt, user_prompt
    
    def summarize_chinese(self, article: NormalizedArticle) -> str:
        """Generate Chinese summary (~200 chars)."""
        system_prompt, user_prompt = self._get_chinese_prompt(article)
        result = self._call_api(system_prompt, user_prompt)
        
        if result:
            result = result.strip().strip('"').strip('"').strip('"')
            return result
        
        return self._fallback_chinese(article)
    
    def _fallback_chinese(self, article: NormalizedArticle) -> str:
        """Fallback summary from RSS description."""
        if article.description and len(article.description) > 20:
            desc = article.description
            if len(desc) > 220:
                desc = desc[:210]
                for punct in ['。', '，', '、', '；']:
                    idx = desc.rfind(punct)
                    if idx > 150:
                        desc = desc[:idx + 1]
                        break
            return desc
        return article.title
    
    def summarize_english(self, article: NormalizedArticle) -> str:
        """Generate English summary (~200 words)."""
        if article.description and len(article.description.split()) > 40:
            return self._truncate_english(article.description, 200)
        
        system_prompt, user_prompt = self._get_english_prompt(article)
        result = self._call_api(system_prompt, user_prompt)
        
        if result:
            return result.strip()
        
        return self._truncate_english(article.description or article.title, 200)
    
    def _truncate_english(self, text: str, max_words: int = 200) -> str:
        """Truncate English text to max words."""
        if not text:
            return ""
        
        words = text.split()
        if len(words) <= max_words:
            return text
        
        truncated = ' '.join(words[:max_words])
        
        for punct in ['. ', '? ', '! ']:
            last = truncated.rfind(punct)
            if last > len(truncated) * 0.7:
                return truncated[:last + 1]
        
        return truncated.rsplit(' ', 1)[0] + '...'
    
    def summarize_japanese(self, article: NormalizedArticle) -> str:
        """Generate Japanese summary (~200 chars)."""
        if article.description and len(article.description) > 80:
            return self._truncate_japanese(article.description, 200)
        
        system_prompt, user_prompt = self._get_japanese_prompt(article)
        result = self._call_api(system_prompt, user_prompt)
        
        if result:
            return result.strip()
        
        return self._truncate_japanese(article.description or article.title, 200)
    
    def _truncate_japanese(self, text: str, max_chars: int = 200) -> str:
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
        """Summarize article based on language."""
        if article.language == 'zh':
            return self.summarize_chinese(article)
        elif article.language == 'en':
            return self.summarize_english(article)
        elif article.language == 'ja':
            return self.summarize_japanese(article)
        else:
            return article.description or article.title


class GeminiSummarizer:
    """Google Gemini API summarizer (fast, reliable free tier)."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_base = GEMINI_API_BASE
        self.last_request_time = 0
        logger.info(f"Using Google Gemini API with model: {GEMINI_MODEL}")
    
    def _rate_limit(self):
        """Ensure we don't exceed 15 requests/minute."""
        elapsed = time.time() - self.last_request_time
        if elapsed < GEMINI_RATE_LIMIT_DELAY:
            time.sleep(GEMINI_RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def _call_api(self, prompt: str) -> Optional[str]:
        """Call Gemini API with retry logic."""
        self._rate_limit()
        
        url = f"{self.api_base}?key={self.api_key}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 800
            }
        }
        
        headers = {"Content-Type": "application/json"}
        
        for attempt, backoff in enumerate(RETRY_BACKOFF):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=API_TIMEOUT
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'candidates' in data and len(data['candidates']) > 0:
                        content = data['candidates'][0].get('content', {})
                        parts = content.get('parts', [])
                        if parts:
                            return parts[0].get('text', '').strip()
                    return None
                
                elif response.status_code == 429:
                    logger.warning(f"Gemini rate limited, waiting {backoff * 2}s")
                    time.sleep(backoff * 2)
                    continue
                
                else:
                    logger.error(f"Gemini API error {response.status_code}: {response.text[:200]}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(backoff)
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Gemini timeout, attempt {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(backoff)
                continue
                
            except Exception as e:
                logger.error(f"Gemini API call failed: {e}")
                return None
        
        return None
    
    def summarize_chinese(self, article: NormalizedArticle) -> str:
        """Generate Chinese summary (~200 chars)."""
        content = article.description or article.title
        
        prompt = f"""你是一位專業新聞編輯，請將以下新聞整理成約200個繁體中文字的摘要。

規則：
- 客觀中立，禁止評論或主觀判斷
- 保留關鍵人事時地物和具體數字
- 使用簡潔新聞語言，禁止列點
- 字數目標180-220字

新聞標題：{article.title}
來源：{article.source_name}
內容：{content}

只輸出摘要正文："""
        
        result = self._call_api(prompt)
        
        if result:
            return result.strip().strip('"')
        
        return self._fallback(article)
    
    def summarize_english(self, article: NormalizedArticle) -> str:
        """Generate English summary (~200 words)."""
        if article.description and len(article.description.split()) > 40:
            return self._truncate_english(article.description, 200)
        
        content = article.description or article.title
        
        prompt = f"""You are a professional news editor. Summarize this article in approximately 200 words.

Rules:
- Maintain objectivity, no opinions
- Preserve key facts and numbers
- Write in clear prose, no bullet points
- Target: 180-220 words

Title: {article.title}
Source: {article.source_name}
Content: {content}

Output only the summary:"""
        
        result = self._call_api(prompt)
        
        if result:
            return result.strip()
        
        return self._truncate_english(article.description or article.title, 200)
    
    def summarize_japanese(self, article: NormalizedArticle) -> str:
        """Generate Japanese summary (~200 chars)."""
        if article.description and len(article.description) > 80:
            return self._truncate_japanese(article.description, 200)
        
        content = article.description or article.title
        
        prompt = f"""あなたはプロのニュース編集者です。以下の記事を約200文字で要約してください。

ルール：
- 客観的かつ中立的に記述
- 重要な事実を保持
- 流暢な文章で書く
- 目標：180〜220文字

タイトル：{article.title}
ソース：{article.source_name}
内容：{content}

要約のみを出力："""
        
        result = self._call_api(prompt)
        
        if result:
            return result.strip()
        
        return self._truncate_japanese(article.description or article.title, 200)
    
    def _fallback(self, article: NormalizedArticle) -> str:
        """Fallback to RSS description."""
        if article.description and len(article.description) > 20:
            desc = article.description
            if len(desc) > 220:
                desc = desc[:210]
                for punct in ['。', '，', '、', '；', '.', ',']:
                    idx = desc.rfind(punct)
                    if idx > 150:
                        desc = desc[:idx + 1]
                        break
            return desc
        return article.title
    
    def _truncate_english(self, text: str, max_words: int = 200) -> str:
        """Truncate English text to max words."""
        if not text:
            return ""
        words = text.split()
        if len(words) <= max_words:
            return text
        truncated = ' '.join(words[:max_words])
        for punct in ['. ', '? ', '! ']:
            last = truncated.rfind(punct)
            if last > len(truncated) * 0.7:
                return truncated[:last + 1]
        return truncated.rsplit(' ', 1)[0] + '...'
    
    def _truncate_japanese(self, text: str, max_chars: int = 200) -> str:
        """Truncate Japanese text to max chars."""
        if not text or len(text) <= max_chars:
            return text or ""
        truncated = text[:max_chars]
        last_period = truncated.rfind('。')
        if last_period > max_chars * 0.7:
            return truncated[:last_period + 1]
        return truncated[:max_chars - 1] + '…'
    
    def summarize(self, article: NormalizedArticle) -> str:
        """Summarize article based on language."""
        if article.language == 'zh':
            return self.summarize_chinese(article)
        elif article.language == 'en':
            return self.summarize_english(article)
        elif article.language == 'ja':
            return self.summarize_japanese(article)
        else:
            return article.description or article.title


class SiliconFlowSummarizer(BaseSummarizer):
    """SiliconFlow API summarizer (free DeepSeek model)."""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, SILICONFLOW_API_BASE, SILICONFLOW_MODEL)
        logger.info(f"Using SiliconFlow API with model: {SILICONFLOW_MODEL}")


class DeepSeekSummarizer(BaseSummarizer):
    """DeepSeek direct API summarizer."""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, DEEPSEEK_API_BASE, DEEPSEEK_MODEL)
        logger.info(f"Using DeepSeek API with model: {DEEPSEEK_MODEL}")


class ZeaburSummarizer(BaseSummarizer):
    """Zeabur AI Hub summarizer (GPT-4o-mini, fast and reliable)."""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, ZEABUR_API_BASE, ZEABUR_MODEL)
        logger.info(f"Using Zeabur AI Hub with model: {ZEABUR_MODEL}")


class FallbackSummarizer:
    """No-API fallback summarizer using RSS descriptions."""
    
    def __init__(self):
        logger.warning("No API key provided - using fallback RSS descriptions")
    
    def summarize(self, article: NormalizedArticle) -> str:
        """Use RSS description as summary."""
        if article.description:
            desc = article.description
            if len(desc) > 220:
                desc = desc[:210]
                for punct in ['。', '，', '.', ',', '、']:
                    idx = desc.rfind(punct)
                    if idx > 150:
                        desc = desc[:idx + 1]
                        break
            return desc
        return article.title


def get_summarizer():
    """
    Get appropriate summarizer based on available API keys.
    
    Priority:
    1. ZEABUR_API_KEY (Zeabur AI Hub - GPT-4o-mini, fast)
    2. GOOGLE_API_KEY (Gemini)
    3. SILICONFLOW_API_KEY
    4. DEEPSEEK_API_KEY
    5. Fallback (no API)
    """
    zeabur_key = os.environ.get('ZEABUR_API_KEY')
    google_key = os.environ.get('GOOGLE_API_KEY')
    siliconflow_key = os.environ.get('SILICONFLOW_API_KEY')
    deepseek_key = os.environ.get('DEEPSEEK_API_KEY')
    
    if zeabur_key:
        return ZeaburSummarizer(zeabur_key)
    elif google_key:
        return GeminiSummarizer(google_key)
    elif siliconflow_key:
        return SiliconFlowSummarizer(siliconflow_key)
    elif deepseek_key:
        return DeepSeekSummarizer(deepseek_key)
    else:
        return FallbackSummarizer()


def summarize_by_category(
    articles: dict[str, dict[str, list[NormalizedArticle]]], 
    api_key: str = None
) -> dict[str, dict[str, list[ArticleWithSummary]]]:
    """
    Summarize articles organized by tab and category.
    
    Args:
        articles: Nested dict: tab -> category -> articles
        api_key: Optional explicit API key (overrides env vars)
    
    Returns:
        Same structure with ArticleWithSummary objects
    """
    # Get summarizer based on available keys
    if api_key:
        # Detect API type by key format
        if api_key.startswith('sk-') and len(api_key) < 30:
            # Zeabur keys are short sk- format
            summarizer = ZeaburSummarizer(api_key)
        elif api_key.startswith('AIzaSy'):
            summarizer = GeminiSummarizer(api_key)
        elif api_key.startswith('sk-') and len(api_key) > 50:
            summarizer = SiliconFlowSummarizer(api_key)
        else:
            summarizer = DeepSeekSummarizer(api_key)
    else:
        summarizer = get_summarizer()
    
    result = {}
    total_summarized = 0
    
    for tab, categories in articles.items():
        result[tab] = {}
        for category, cat_articles in categories.items():
            summarized = []
            for article in cat_articles:
                summary = summarizer.summarize(article)
                
                summarized.append(ArticleWithSummary(
                    title=article.title,
                    link=article.link,
                    published=article.published,
                    source_name=article.source_name,
                    summary=summary,
                    tab=article.tab,
                    final_category=category
                ))
                total_summarized += 1
            
            result[tab][category] = summarized
    
    logger.info(f"Summarized {total_summarized} articles")
    return result
