#!/usr/bin/env python3
"""
PTT local collector — plain HTTP, no browser needed.

Why this exists
---------------
PTT blocks datacenter IP ranges. Measured 2026-10-03:

    from this machine (Taiwan residential)   → HTTP 200 on every board
    from a GitHub Actions runner (Azure, US) → HTTP 403 on every board
                                               and on every Atom fallback

So the CI run cannot read PTT at all, and the PTT tab renders empty. Unlike
Dcard there is no Cloudflare challenge to defeat — a normal HTTP request from a
Taiwan IP works fine. This tool therefore just calls `src.ptt_fetcher`, which
already knows how to parse the board index (push counts, 置底 exclusion, etc.),
and writes the rows to a JSON snapshot the pipeline can read.

Note this is deliberately NOT a browser collector: `bsk` + Brave would work too
but is slower and unnecessary.

Board list is read from `config/feeds.yaml` (`ptt_hot.sources`) so the snapshot
can never drift from what the pipeline expects.

Output
------
data/ptt_latest.json

    {
      "schema_version": 1,
      "collected_at": "2026-10-03T23:05:00+08:00",
      "collector": "tools/collect_ptt.py (direct HTTP)",
      "requested_boards": ["Gossiping", ...],
      "boards": [{"board": ..., "name": ..., "status": "ok", "count": 30}],
      "posts": [{"board": ..., "title": ..., "push": 42, ...}]
    }

Usage
-----
    python3 tools/collect_ptt.py                  # collect, write snapshot
    python3 tools/collect_ptt.py --dry-run        # print counts, write nothing
    python3 tools/collect_ptt.py --boards Stock,Tech_Job
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_feeds_config  # noqa: E402
from src.ptt_fetcher import (  # noqa: E402
    INTER_BOARD_DELAY,
    PttPolicyBlocked,
    fetch_ptt_board,
)
from src.snapshot_loader import DEFAULT_PTT_SNAPSHOT_PATH  # noqa: E402

import time  # noqa: E402

TAIPEI = timezone(timedelta(hours=8))
POSTS_PER_BOARD = 30


def load_board_specs(tab_id: str = "ptt_hot") -> list[dict]:
    """Read the PTT board definitions the pipeline uses, so they cannot drift."""
    config = load_feeds_config()
    tab = config.tabs.get(tab_id)
    if tab is None:
        raise SystemExit(f"config/feeds.yaml has no tab '{tab_id}'")
    specs = []
    for source in tab.sources:
        if source.get("type") != "ptt_list":
            continue
        specs.append(
            {
                "board": source.get("board", ""),
                "name": source.get("board_name") or source.get("category") or source.get("board"),
                "url": source.get("url", ""),
                "fallback_url": source.get("fallback_url", ""),
                "source_name": source.get("source_name", ""),
            }
        )
    return specs


def build_snapshot(specs: list[dict], limit: int) -> dict:
    board_reports: list[dict] = []
    all_posts: list[dict] = []
    collected_at = datetime.now(TAIPEI).isoformat(timespec="seconds")

    for index, spec in enumerate(specs):
        try:
            rows, status = fetch_ptt_board(
                url=spec["url"],
                board=spec["board"],
                source_name=spec["source_name"],
                fallback_url=spec["fallback_url"],
                max_items=limit,
            )
        except PttPolicyBlocked as exc:
            rows, status = [], f"policy_blocked: {exc}"
        except Exception as exc:  # noqa: BLE001 - one bad board must not kill the run
            print(f"  ! {spec['board']}: {exc}", file=sys.stderr)
            rows, status = [], f"error: {type(exc).__name__}"

        posts = [
            {
                "board": spec["board"],
                "board_name": spec["name"],
                "title": row.get("title", ""),
                "link": row.get("link", ""),
                "published": row.get("published") or "",
                "author": (row.get("_metrics") or {}).get("author", ""),
                "push": (row.get("_metrics") or {}).get("push"),
                "push_label": (row.get("_metrics") or {}).get("push_label", ""),
                "date_precision": (row.get("_metrics") or {}).get("date_precision", "day"),
                "summary": row.get("summary") or "",
                "collected_at": collected_at,
            }
            for row in rows
            if row.get("link") and row.get("title")
        ]
        board_reports.append(
            {
                "board": spec["board"],
                "name": spec["name"],
                "status": status,
                "count": len(posts),
            }
        )
        all_posts.extend(posts)
        print(f"  {spec['board']:<14} {str(status):<20} {len(posts)} rows")

        # Pause between live boards only. Once the breaker trips (a 403), every
        # later board returns instantly without touching the network, so there
        # is nothing to rate-limit.
        if status in ("ok", "ok_atom_fallback") and index < len(specs) - 1:
            time.sleep(INTER_BOARD_DELAY)

    return {
        "schema_version": 1,
        "collected_at": collected_at,
        "collector": "tools/collect_ptt.py (direct HTTP)",
        "requested_boards": [s["board"] for s in specs],
        "boards": board_reports,
        "posts": all_posts,
    }


def read_snapshot(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect PTT board listings over plain HTTP.")
    parser.add_argument("--boards", help="comma-separated board names (default: from feeds.yaml)")
    parser.add_argument("--limit", type=int, default=POSTS_PER_BOARD, help="rows per board")
    parser.add_argument("--out", default=str(DEFAULT_PTT_SNAPSHOT_PATH), help="snapshot output path")
    parser.add_argument("--dry-run", action="store_true", help="print counts, write nothing")
    args = parser.parse_args()

    specs = load_board_specs()
    if args.boards:
        wanted = {s.strip() for s in args.boards.split(",") if s.strip()}
        specs = [s for s in specs if s["board"] in wanted]
        if not specs:
            print("no matching boards in config/feeds.yaml", file=sys.stderr)
            return 1

    print(f"collecting {len(specs)} PTT board(s) ...")
    snapshot = build_snapshot(specs, args.limit)

    total = len(snapshot["posts"])
    ok_boards = sum(1 for b in snapshot["boards"] if str(b["status"]).startswith("ok"))
    print(f"collected {total} rows from {ok_boards}/{len(specs)} boards")

    if args.dry_run:
        print(json.dumps(snapshot["boards"], ensure_ascii=False, indent=2))
        return 0 if total else 1

    if total == 0:
        previous = read_snapshot(Path(args.out))
        if previous and previous.get("posts"):
            print("no rows collected; keeping existing snapshot", file=sys.stderr)
            return 1
        print("no rows collected and no previous snapshot to keep", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
