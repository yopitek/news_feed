"""
Read the locally-collected Dcard snapshot produced by tools/collect_dcard.py.

Dcard is Cloudflare-protected: server-side requests (curl / urllib / curl_cffi
with a Chrome fingerprint) all return HTTP 403 with a Turnstile challenge, so the
GitHub Actions runner cannot fetch Dcard directly. Instead the operator's machine
collects the public board listings with Brave and commits `data/dcard_latest.json`;
the pipeline reads that snapshot and renders it, labelling the snapshot time so
readers know the data is not live.

Dcard's robots.txt only disallows `/emails/activate` and the site publishes no
AI-crawler policy, so reading these public listings is compliant. We deliberately
keep the collection rate low (one page load per board).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "dcard_latest.json"


def load_snapshot(path: Optional[Path | str] = None) -> Optional[dict]:
    """Read the snapshot JSON, or None when it is missing/unreadable."""
    path = Path(path) if path else DEFAULT_SNAPSHOT_PATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read Dcard snapshot %s: %s", path, exc)
        return None


def snapshot_age_hours(snapshot: dict) -> Optional[float]:
    """Hours since the snapshot was collected, for staleness labelling."""
    stamp = snapshot.get("collected_at")
    if not stamp:
        return None
    try:
        collected = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if collected.tzinfo is None:
        collected = collected.replace(tzinfo=timezone.utc)
    return round((datetime.now(collected.tzinfo) - collected).total_seconds() / 3600, 1)


def load_dcard_board(
    board_slug: str,
    board_name: str,
    source_name: str = "",
    snapshot_path: Optional[Path | str] = None,
) -> tuple[list[dict], str]:
    """
    Extract one board's posts from the snapshot.

    Returns:
        (entries, status): 'ok' when posts were found, 'snapshot_missing' when
        there is no snapshot file, 'empty' when the board is absent from it.
    """
    snapshot = load_snapshot(snapshot_path)
    if snapshot is None:
        logger.warning("Dcard snapshot not found (%s); tab will be empty", snapshot_path)
        return [], "snapshot_missing"

    label = source_name or f"Dcard {board_name}"
    entries: list[dict] = []
    for post in snapshot.get("posts", []):
        if post.get("board_slug") != board_slug:
            continue
        link = post.get("link")
        title = post.get("title")
        if not link or not title:
            continue
        entries.append(
            {
                "title": title,
                "link": link,
                "published": post.get("published") or "",
                "published_parsed": None,
                "summary": post.get("excerpt") or "",
                "guid": link,
                "source_feed_url": f"https://www.dcard.tw/f/{board_slug}",
                "_metrics": {
                    "like": post.get("like"),
                    "comment": post.get("comment"),
                    "share": post.get("share"),
                    "author": post.get("author"),
                    "board": board_slug,
                    "board_name": board_name,
                    "origin": "dcard_snapshot",
                    "collected_at": post.get("collected_at") or snapshot.get("collected_at"),
                },
            }
        )

    if not entries:
        logger.warning("Dcard board %s missing from snapshot %s", board_slug, label)
        return [], "empty"
    logger.info("Dcard snapshot %s: %d posts", label, len(entries))
    return entries, "ok"
