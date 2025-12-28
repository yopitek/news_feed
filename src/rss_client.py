"""
rss_client.py

Fetch and normalize RSS feeds using feedparser.
Designed for daily newsletter ingestion (stateless, resilient).
"""

import feedparser
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# CONFIG — add more feeds here when needed
# ------------------------------------------------------------------------------

RSS_SOURCES = [
    {
        "id": "cna_world",
        "label": "CNA 國際新聞",
        "url": "https://feeds.feedburner.com/rsscna/intworld",
    },
    # you can add more feeds, for example:
    # {
    #     "id": "technews",
    #     "label": "TechNews",
    #     "url": "https://technews.tw/feed/",
    # },
]


# ------------------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_get(entry: dict, key: str, default: Optional[str] = "") -> Optional[str]:
    return entry.get(key) if entry.get(key) is not None else default


def _normalize_item(feed_id: str, entry: dict) -> Dict[str, Any]:
    """
    Normalize a single RSS entry into our internal structure.
    """
    return {
        "source": feed_id,
        "title": _safe_get(entry, "title", "").strip(),
        "url": _safe_get(entry, "link", "").strip(),
        "summary_raw": _safe_get(entry, "summary", "").strip(),
        "published_at": (
            entry.get("published") or entry.get("updated") or None
        ),
    }


# ------------------------------------------------------------------------------
# CORE FUNCTION
# ------------------------------------------------------------------------------

def fetch_all_rss(limit_per_feed: int = 20) -> Dict[str, Any]:
    """
    Fetch all configured RSS feeds and return normalized data.

    Returns:
        {
          "fetched_at": "...",
          "feeds": [
              {
                  "id": "...",
                  "label": "...",
                  "url": "...",
                  "items": [ {...}, ... ]
              }
          ]
        }
    """

    logger.info("Fetching RSS feeds...")

    result = {
        "fetched_at": _utc_now_iso(),
        "feeds": [],
    }

    for feed_cfg in RSS_SOURCES:
        feed_id = feed_cfg["id"]
        feed_url = feed_cfg["url"]

        logger.info(f"[RSS] Fetching {feed_id}: {feed_url}")

        try:
            feed = feedparser.parse(feed_url)

            if feed.bozo:
                logger.warning(
                    f"[RSS] Warning parsing feed ({feed_id}): {feed.bozo_exception}"
                )

            items = [
                _normalize_item(feed_id, entry)
                for entry in feed.entries[:limit_per_feed]
            ]

            result["feeds"].append(
                {
                    "id": feed_cfg["id"],
                    "label": feed_cfg["label"],
                    "url": feed_cfg["url"],
                    "items": items,
                }
            )

        except Exception as exc:
            logger.exception(f"[RSS] Failed to fetch {feed_id}: {exc}")
            result["feeds"].append(
                {
                    "id": feed_cfg["id"],
                    "label": feed_cfg["label"],
                    "url": feed_cfg["url"],
                    "items": [],
                    "error": str(exc),
                }
            )

    return result


# ------------------------------------------------------------------------------
# LOCAL TEST
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_all_rss(limit_per_feed=10)
    print(data)
