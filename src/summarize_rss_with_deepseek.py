"""
summarize_rss_with_deepseek.py

Use DeepSeek (SiliconFlow) to summarize RSS content.

Input  (from rss_client.fetch_all_rss):
{
  "fetched_at": "...",
  "feeds": [
    {
      "id": "...",
      "label": "...",
      "url": "...",
      "items": [
        {
          "source": "...",
          "title": "...",
          "url": "...",
          "summary_raw": "...",
          "published_at": "..."
        }
      ]
    }
  ]
}

Output (normalized):
{
  "date_local": "YYYY-MM-DD",
  "timezone": "Asia/Taipei",
  "feeds": [
    {
      "id": "...",
      "items": [
        {
          "title": "...",
          "url": "...",
          "summary_zh_tw": "...",
          "importance": 1,
          "confidence": "high|medium|low"
        }
      ]
    }
  ]
}
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

import requests

logger = logging.getLogger(__name__)

SILICONFLOW_API = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"


# ------------------------------------------------------------------------------
# UTILITIES
# ------------------------------------------------------------------------------

def _require_env(var: str) -> str:
    value = os.getenv(var)
    if not value:
        raise RuntimeError(f"Missing required env: {var}")
    return value


def _json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _chunk(items: List[Any], size: int) -> List[List[Any]]:
    for i in range(0, len(items), size):
        yield items[i: i + size]


# ------------------------------------------------------------------------------
# PROMPT
# ------------------------------------------------------------------------------

PROMPT_TEMPLATE = """
你是一位專業新聞編輯，請根據輸入 JSON 進行整理。

規則：
1) 輸出「只允許 JSON」，不可加入說明、文字或 Markdown
2) 每則新聞產生 80–120 字「繁體中文（台灣）」摘要
3) 不得臆測或新增不存在的內容
4) 只可根據 title + summary_raw 撰寫
5) 加上 importance（1=最重要）
6) confidence:
   - high: 標題 + 內容清楚
   - medium: 敘述模糊
   - low: 幾乎只有標題

輸入 JSON：
{INPUT}
"""


# ------------------------------------------------------------------------------
# API CALL
# ------------------------------------------------------------------------------

def _call_deepseek(payload: Dict[str, Any]) -> Dict[str, Any]:
    api_key = _require_env("SILICONFLOW_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(SILICONFLOW_API, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ------------------------------------------------------------------------------
# CORE
# ------------------------------------------------------------------------------

def summarize_feed_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Summarize a group of RSS items with DeepSeek.
    Chunking prevents overly long prompts.
    """

    results: List[Dict[str, Any]] = []

    # 每批處理 6~8 則，避免 token 過大
    for batch in _chunk(items, 6):
        payload_items = [
            {
                "title": it["title"],
                "url": it["url"],
                "summary_raw": it["summary_raw"],
            }
            for it in batch
        ]

        user_prompt = PROMPT_TEMPLATE.replace(
            "{INPUT}", _json_dumps(payload_items)
        )

        payload = {
            "model": MODEL,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "temperature": 0.4,
            "top_p": 0.7,
        }

        tries = 0
        while tries < 3:
            try:
                logger.info("[DeepSeek] Requesting batch summarization...")
                data = _call_deepseek(payload)

                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                # append validated items
                results.extend(parsed)
                break

            except Exception as exc:
                tries += 1
                logger.warning(f"[DeepSeek] Failed attempt {tries}: {exc}")
                time.sleep(2)

                if tries >= 3:
                    # fallback — 使用原始內容
                    logger.error("[DeepSeek] Fallback: using raw summaries")
                    for it in batch:
                        results.append(
                            {
                                "title": it["title"],
                                "url": it["url"],
                                "summary_zh_tw": it["summary_raw"][:120],
                                "importance": 5,
                                "confidence": "low",
                            }
                        )

    return results


def summarize_rss_payload(rss_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts output from rss_client.fetch_all_rss(), returns summarized structure.
    """

    logger.info("[Summary] Processing RSS feeds")

    output = {
        "date_local": datetime.now().strftime("%Y-%m-%d"),
        "timezone": "Asia/Taipei",
        "feeds": [],
    }

    for feed in rss_data.get("feeds", []):
        items = feed.get("items", [])

        summarized = summarize_feed_items(items)

        output["feeds"].append(
            {
                "id": feed["id"],
                "label": feed["label"],
                "items": summarized,
            }
        )

    return output


# ------------------------------------------------------------------------------
# LOCAL TEST
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from src.rss_client import fetch_all_rss

    rss_payload = fetch_all_rss(limit_per_feed=5)
    summary = summarize_rss_payload(rss_payload)

    print(_json_dumps(summary))
