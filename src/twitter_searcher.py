"""
Search Twitter/X accounts via Tavily API for weekly AI digest.
Processes accounts in batches of 10 sorted by priority.
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import yaml

logger = logging.getLogger(__name__)


@dataclass
class TweetResult:
    handle: str
    title: str
    url: str
    content: str
    score: float
    published_date: str
    priority: int


def load_accounts(path: str = "config/twitter_accounts.yaml") -> list[dict]:
    """Load and return accounts sorted by priority (1 first)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    accounts = data.get("accounts", [])
    return sorted(accounts, key=lambda a: a["priority"])


def build_query(handle: str, keywords: str) -> str:
    """Build a Tavily search query for a Twitter account."""
    return (
        f"@{handle} ({keywords}) "
        f"site:x.com OR site:twitter.com"
    )


def search_account_batch(
    handles: list[str],
    keywords: str,
    client,
    days: int = 7,
    max_per_account: int = 3,
) -> list[TweetResult]:
    """
    Search a batch of handles. Returns TweetResult list.
    `client` is a TavilyClient instance (injected for testability).
    """
    results = []
    for handle in handles:
        query = build_query(handle, keywords)
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                days=days,
                max_results=max_per_account,
            )
            for item in response.get("results", []):
                results.append(
                    TweetResult(
                        handle=handle,
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        score=float(item.get("score", 0.0)),
                        published_date=item.get("published_date", ""),
                        priority=1,  # set by caller after load_accounts
                    )
                )
        except Exception as exc:
            logger.warning(f"Tavily search failed for @{handle}: {exc}")
    return results


def run_all_searches(
    tavily_api_key: str,
    accounts_path: str = "config/twitter_accounts.yaml",
    days: int = 7,
    max_per_account: int = 3,
    batch_size: int = 10,
) -> list[TweetResult]:
    """
    Main entry: load accounts, batch search, return all results.
    Prioritised accounts are searched first.
    Free-tier safe: 65 accounts ÷ batch_size=10 = 7 API calls/run.
    """
    from tavily import TavilyClient

    accounts = load_accounts(accounts_path)
    data = yaml.safe_load(Path(accounts_path).read_text(encoding="utf-8"))
    keywords = data.get("keywords", "tool OR workflow OR tutorial OR prompt")

    client = TavilyClient(api_key=tavily_api_key)
    all_results: list[TweetResult] = []

    for i in range(0, len(accounts), batch_size):
        batch = accounts[i : i + batch_size]
        handles = [a["handle"] for a in batch]
        priority_map = {a["handle"]: a["priority"] for a in batch}

        batch_results = search_account_batch(
            handles=handles,
            keywords=keywords,
            client=client,
            days=days,
            max_per_account=max_per_account,
        )
        for r in batch_results:
            r.priority = priority_map.get(r.handle, 3)
        all_results.extend(batch_results)

    logger.info(f"Twitter search complete: {len(all_results)} results")
    return all_results