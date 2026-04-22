"""
Weekly AI digest pipeline - fetches from Twitter/X accounts via Tavily,
structures with DeepSeek, renders HTML and sends email.
"""
import logging
import os
from datetime import datetime
from pathlib import Path

import pytz

from .twitter_searcher import TweetResult, load_accounts, run_all_searches
from .weekly_renderer import WeeklyItem, render_weekly_email
from .models import FeedsConfig, TabConfig

logger = logging.getLogger(__name__)

TAIPEI_TZ = pytz.timezone('Asia/Taipei')
OUTPUT_DIR = Path(__file__).parent.parent / "output" / "weekly"


def filter_results(results: list[TweetResult], exclude_keywords: list[str] | None = None) -> list[TweetResult]:
    """Filter results by score and exclude keywords."""
    if exclude_keywords is None:
        exclude_keywords = ["infrastructure", "academic paper", "funding", "raises", "benchmark", "SOTA"]
    
    filtered = []
    for r in results:
        if r.score < 0.5:
            continue
        content_lower = r.content.lower()
        if any(kw.lower() in content_lower for kw in exclude_keywords):
            continue
        filtered.append(r)
    
    # Sort by priority then score
    filtered.sort(key=lambda x: (x.priority, -x.score))
    return filtered[:15]  # Max 15 items


def structurize_tweet(tweet: TweetResult, api_key: str) -> WeeklyItem:
    """
    Call DeepSeek to generate structured WeeklyItem from TweetResult.
    Uses the summarizer pattern for structured output.
    """
    from .summarizer import BaseSummarizer
    
    class WeeklySummarizer(BaseSummarizer):
        def get_weekly_prompt(self, tweet: TweetResult) -> tuple[str, str]:
            system = """你是一位專業的AI資訊編輯。將Twitter內容轉化為結構化的每週精選項目。
你的輸出必須是有效的JSON格式，包含以下欄位：
- title_zh: 繁體中文標題 (20字以內)
- core_method: 陣列，最少1個核心方法/技巧 (每項20字以內)
- why_useful: 為什麼有用 (30字以內)
- type_icon: 類型標識 (🛠️, 💡, 📝, 或 🚀 之一)

只輸出JSON，不要其他文字。"""
            user = f"""轉換以下Twitter內容：
{tweet.content}
原始連結: {tweet.url}
來源: @{tweet.handle}

輸出JSON："""
            return system, user
    
    summarizer = WeeklySummarizer(api_key, "https://api.deepseek.com/v1/chat/completions", "deepseek-chat")
    system, user = summarizer.get_weekly_prompt(tweet)
    
    try:
        result = summarizer._call_api(system, user)
        if result:
            # Parse JSON from result
            import json
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return WeeklyItem(
                    handle=tweet.handle,
                    title_zh=data.get("title_zh", tweet.title),
                    url=tweet.url,
                    core_method=data.get("core_method", []),
                    why_useful=data.get("why_useful", ""),
                    type_icon=data.get("type_icon", "💡"),
                    priority=tweet.priority,
                )
    except Exception as e:
        logger.warning(f"Failed to structurize tweet: {e}")
    
    # Fallback
    return WeeklyItem(
        handle=tweet.handle,
        title_zh=tweet.title[:20],
        url=tweet.url,
        core_method=[tweet.content[:100]],
        why_useful="AI從業者分享",
        type_icon="💡",
        priority=tweet.priority,
    )


def run_weekly_pipeline():
    """Main entry point for weekly pipeline."""
    # Load config
    accounts_path = Path(__file__).parent.parent / "config" / "twitter_accounts.yaml"
    
    # Get API keys
    tavily_key = os.environ.get("TAVILY_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    
    if not tavily_key:
        logger.error("TAVILY_API_KEY not set")
        return
    
    # Search accounts
    logger.info("Starting weekly Twitter search...")
    raw_results = run_all_searches(tavily_key, str(accounts_path))
    logger.info(f"Raw results: {len(raw_results)}")
    
    # Filter
    filtered = filter_results(raw_results)
    logger.info(f"Filtered results: {len(filtered)}")
    
    if len(filtered) < 3:
        logger.warning("Not enough results, skipping email")
        return
    
    # Structurize with DeepSeek
    items = []
    if deepseek_key:
        logger.info("Structurizing with DeepSeek...")
        for tweet in filtered:
            item = structurize_tweet(tweet, deepseek_key)
            items.append(item)
    else:
        # Fallback to basic items
        for tweet in filtered:
            items.append(WeeklyItem(
                handle=tweet.handle,
                title_zh=tweet.title[:20],
                url=tweet.url,
                core_method=[tweet.content[:100]],
                why_useful="AI從業者分享",
                type_icon="💡",
                priority=tweet.priority,
            ))
    
    # Render
    now = datetime.now(TAIPEI_TZ)
    week_num = now.isocalendar()[1]
    date_str = now.strftime("%Y年%m月%d日")
    
    html = render_weekly_email(items, week_num, date_str)
    
    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{now.strftime('%Y-%m-%d')}.html"
    output_file.write_text(html, encoding="utf-8")
    logger.info(f"Saved to {output_file}")
    
    # Email (reuses existing mailer)
    try:
        from .mailer import send_digest_email
        subject = f"AI乾貨週報 · Week {week_num} · {date_str}"
        send_digest_email(html, subject)
    except Exception as e:
        logger.warning(f"Email failed: {e}")
    
    return html


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_weekly_pipeline()