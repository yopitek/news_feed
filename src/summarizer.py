"""
DeepSeek API integration for news summarization.
Updated for 200 character/word summaries.
"""
import time
import logging
from typing import Optional

import requests

from .models import NormalizedArticle, ArticleWithSummary

logger = logging.getLogger(__name__)

# Configuration
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
API_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]

# Summary lengths (updated to 200)
SUMMARY_LENGTH_ZH = 200
SUMMARY_LENGTH_EN = 200  # words
SUMMARY_LENGTH_JA = 200


class DeepSeekSummarizer:
    """DeepSeek API client for summarization."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def _call_api(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call DeepSeek API with retry logic."""
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 800
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
    
    def summarize_chinese(self, article: NormalizedArticle) -> str:
        """Generate Chinese summary (~200 chars)."""
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


def summarize_by_category(
    articles: dict[str, dict[str, list[NormalizedArticle]]], 
    api_key: str
) -> dict[str, dict[str, list[ArticleWithSummary]]]:
    """
    Summarize articles organized by tab and category.
    
    Args:
        articles: Nested dict: tab -> category -> articles
        api_key: DeepSeek API key
    
    Returns:
        Same structure with ArticleWithSummary objects
    """
    summarizer = DeepSeekSummarizer(api_key)
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
                    final_category=category  # Use display category
                ))
                total_summarized += 1
            
            result[tab][category] = summarized
    
    logger.info(f"Summarized {total_summarized} articles")
    return result
