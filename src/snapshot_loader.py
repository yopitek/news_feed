"""
Read the locally-collected snapshots produced by the tools/ collectors.

Two sources cannot be fetched from CI and are snapshotted instead:

* **Dcard** — Cloudflare-protected. Server-side requests (curl / urllib /
  curl_cffi with a Chrome fingerprint) all return HTTP 403 with a Turnstile
  challenge. Collected with Brave via `tools/collect_dcard.py`.

* **PTT** — not Cloudflare, but the board pages return HTTP 403 to datacenter
  IP ranges. Measured 2026-10-03: every board and every Atom fallback is 403
  from a GitHub Actions runner (Azure, US) while all return 200 from a Taiwan
  residential IP. Collected with plain HTTP from the operator's machine via
  `tools/collect_ptt.py` — no browser needed.

The pipeline reads `data/dcard_latest.json` and `data/ptt_latest.json`, renders
them, and labels the capture time so readers know the data is not live.

Dcard's robots.txt only disallows `/emails/activate` and neither site publishes
an AI-crawler policy, so reading these public listings is compliant. We
deliberately keep the collection rate low (one page load per board).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SNAPSHOT_PATH = _DATA_DIR / "dcard_latest.json"
DEFAULT_PTT_SNAPSHOT_PATH = _DATA_DIR / "ptt_latest.json"


def snapshot_meta(snapshot: Optional[dict]) -> dict:
    """
    Build the meta dict the renderer uses for the "captured at ..." banner.

    Shared by the Dcard and PTT tabs so the notice stays identical in shape.
    """
    if not snapshot:
        return {}
    return {
        "collected_at": snapshot.get("collected_at"),
        "age_hours": snapshot_age_hours(snapshot),
        "boards": snapshot.get("boards", []),
        "total_posts": len(snapshot.get("posts", [])),
        "origin": snapshot.get("origin") or snapshot.get("collector"),
    }


def load_snapshot(path: Optional[Path | str] = None) -> Optional[dict]:
    """Read the Dcard snapshot JSON, or None when it is missing/unreadable."""
    return _load_json(Path(path) if path else DEFAULT_SNAPSHOT_PATH, "Dcard")


def load_ptt_snapshot(path: Optional[Path | str] = None) -> Optional[dict]:
    """Read the PTT snapshot JSON, or None when it is missing/unreadable."""
    return _load_json(Path(path) if path else DEFAULT_PTT_SNAPSHOT_PATH, "PTT")


def _load_json(path: Path, label: str) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read %s snapshot %s: %s", label, path, exc)
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


def load_ptt_board(
    board: str,
    board_name: str = "",
    source_name: str = "",
    snapshot_path: Optional[Path | str] = None,
) -> tuple[list[dict], str]:
    """
    Extract one board's rows from the PTT snapshot.

    The snapshot is written by `tools/collect_ptt.py`, which reuses
    `src.ptt_fetcher.parse_board_index`, so the records already carry the same
    `_metrics` shape as a live fetch (push / push_label / author / board /
    date_precision). We reconstruct the feed-entry dicts here rather than
    storing whole HTML-derived rows twice.

    Returns:
        (entries, status): 'ok' when rows were found, 'snapshot_missing' when
        there is no snapshot file, 'empty' when the board is absent from it.
    """
    snapshot = load_ptt_snapshot(snapshot_path)
    if snapshot is None:
        logger.warning(
            "PTT snapshot not found (%s); PTT tab will be empty. "
            "Run: python3 tools/collect_ptt.py",
            snapshot_path or DEFAULT_PTT_SNAPSHOT_PATH,
        )
        return [], "snapshot_missing"

    label = source_name or f"PTT {board_name or board}"
    collected_at = snapshot.get("collected_at")
    entries: list[dict] = []
    for post in snapshot.get("posts", []):
        if post.get("board") != board:
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
                "summary": post.get("summary") or "",
                "guid": link,
                "source_feed_url": f"https://www.ptt.cc/bbs/{board}/index.html",
                "_metrics": {
                    "push": post.get("push"),
                    "push_label": post.get("push_label", ""),
                    "author": post.get("author", ""),
                    "board": board,
                    "board_name": board_name or board,
                    "origin": "ptt_snapshot",
                    "date_precision": post.get("date_precision", "day"),
                    "collected_at": collected_at,
                },
            }
        )

    if not entries:
        logger.warning("PTT board %s missing from snapshot %s", board, label)
        return [], "empty"
    logger.info("PTT snapshot %s: %d rows", label, len(entries))
    return entries, "ok"
