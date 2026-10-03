#!/usr/bin/env python3
"""
Dcard local collector — bsk (browser-skill CLI) + Brave Browser.

Why this exists
---------------
Dcard's public pages sit behind Cloudflare. Server-side fetches (curl / urllib /
curl_cffi with a Chrome fingerprint) all end at HTTP 403 with the Turnstile
challenge page, so GitHub Actions cannot fetch Dcard directly.

Dcard's robots.txt only disallows `/emails/activate` and the site publishes no
AI-crawler policy, so reading these public board listings from a real, logged-out
browser session is compliant. We therefore collect on the operator's own machine
with Brave and commit the result as a JSON snapshot the pipeline can read.

Output
------
data/dcard_latest.json

    {
      "schema_version": 1,
      "collected_at": "2026-10-03T21:40:12+08:00",
      "collector": "tools/collect_dcard.py (bsk + Brave)",
      "boards": [{"slug": ..., "name": ..., "status": "ok", "count": 24}],
      "posts": [{...}]
    }

Usage
-----
    python3 tools/collect_dcard.py                     # collect, write snapshot
    python3 tools/collect_dcard.py --dry-run           # print, do not write
    python3 tools/collect_dcard.py --session xsbc      # reuse an existing session
    python3 tools/collect_dcard.py --boards tech_job,money

Requires the `bsk` CLI and a connected Chromium-family browser. Per this
project's machine policy the browser is Brave.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = PROJECT_ROOT / "data" / "dcard_latest.json"

TAIPEI = timezone(timedelta(hours=8))

# Boards worth surfacing in a tech/business digest.
# `slug` is Dcard's forum id used in /f/<slug>; `name` is the tab section label.
# Slugs verified against https://www.dcard.tw/forum/popular on 2026-10-03 —
# note `soft_job` and `salary` are NOT valid Dcard boards (they 404).
DEFAULT_BOARDS = [
    {"slug": "tech_job", "name": "科技業板"},
    {"slug": "ai_builder", "name": "AI 工作者板"},
    {"slug": "3c", "name": "3C 板"},
    {"slug": "money", "name": "理財板"},
]

POSTS_PER_BOARD = 24
NAV_SETTLE_SECONDS = 2.0

# Runs inside the page. Returns a plain array so bsk's JSON wrapper stays small.
# Like / comment / share are identified by their inline SVG path signatures —
# robust across cards, unlike positional button indexes (reaction emoji buttons
# shift the order). Falls back to index order if a signature is not found.
EXTRACT_JS = r"""
(() => {
  const LIKE_SIG = 'M7.999 14s6.666-3.917';
  const COMMENT_SIG = 'M6.475 11.206v1.343';
  const SHARE_SIG = 'M7.298 10.332c.43-.267';

  const num = (t) => {
    if (!t) return null;
    const s = String(t).trim().replace(/,/g, '').replace(/\s+/g, '');
    const m = s.match(/^([0-9]+(?:\.[0-9]+)?)([KMkm萬千]?)/);
    if (!m) return null;
    let v = parseFloat(m[1]);
    const unit = m[2];
    if (unit === 'K' || unit === 'k') v *= 1000;
    else if (unit === 'M' || unit === 'm') v *= 1000000;
    else if (unit === '萬') v *= 10000;
    else if (unit === '千') v *= 1000;
    return Math.round(v);
  };

  const classify = (btn) => {
    const svg = btn.querySelector('svg');
    const html = svg ? (svg.innerHTML || '') : '';
    if (html.indexOf(LIKE_SIG) !== -1) return 'like';
    if (html.indexOf(COMMENT_SIG) !== -1) return 'comment';
    if (html.indexOf(SHARE_SIG) !== -1) return 'share';
    return null;
  };

  const out = [];
  document.querySelectorAll('article').forEach((art) => {
    const h2 = art.querySelector('h2');
    const timeEl = art.querySelector('time');
    const linkEl = art.querySelector('a[href*="/p/"]');
    if (!h2 || !linkEl) return;

    const href = linkEl.getAttribute('href') || '';
    const text = (art.innerText || '');

    // First line of the card text is the poster's school / affiliation.
    let school = null;
    const avatar = art.querySelector('img[alt]');
    if (avatar) school = (avatar.getAttribute('alt') || '').trim() || null;
    if (!school) {
      const first = text.split('\n').map((s) => s.trim()).filter(Boolean)[0];
      school = first && first.length < 40 ? first : null;
    }

    const metrics = { like: null, comment: null, share: null };
    const buttons = Array.from(art.querySelectorAll('button'));
    buttons.forEach((b, i) => {
      const kind = classify(b);
      const v = num(b.innerText);
      if (kind && metrics[kind] === null) metrics[kind] = v;
      if (!kind && i === 0 && metrics.like === null) metrics.like = v;
    });

    // Excerpt: the longest <p> in the card that is not the title itself.
    // Deliberately conservative — image-only posts have no excerpt, and guessing
    // from the card's loose text picks up the like/comment counters instead.
    let excerpt = null;
    const titleText = (h2.innerText || '').trim();
    Array.from(art.querySelectorAll('p')).forEach((p) => {
      const t = (p.innerText || '').trim();
      if (!t || t === titleText) return;
      if (!excerpt || t.length > excerpt.length) excerpt = t;
    });
    if (excerpt) excerpt = excerpt.slice(0, 240);

    out.push({
      title: (h2.innerText || '').trim(),
      href: href,
      published: timeEl ? timeEl.getAttribute('datetime') : null,
      published_local: timeEl ? timeEl.getAttribute('title') : null,
      age_text: timeEl ? (timeEl.innerText || '').trim() : null,
      school: school,
      excerpt: excerpt,
      like: metrics.like,
      comment: metrics.comment,
      share: metrics.share,
      has_image: !!art.querySelector('img[src*="megapx-assets"]'),
    });
  });
  return out.slice(0, __LIMIT__);
})()
"""


class BskError(RuntimeError):
    pass


def _bsk_bin() -> str:
    override = os.environ.get("BSK_BIN")
    if override:
        return override
    for candidate in (
        os.path.expanduser("~/.local/bin/bsk"),
        shutil.which("bsk"),
    ):
        if candidate and Path(candidate).exists():
            return candidate
    raise BskError("bsk CLI not found (set BSK_BIN or install browser-skill)")


def run_bsk(args: list[str], timeout: int = 60, want_json: bool = False) -> dict | str:
    cmd = [_bsk_bin(), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise BskError(
            f"bsk {' '.join(args[:2])} failed rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout).strip()[:400]}"
        )
    raw = (proc.stdout or "").strip()
    if not want_json:
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BskError(f"bsk returned non-JSON output: {raw[:400]}") from exc


def start_session() -> str:
    out = run_bsk(["session", "start", "--name", "dcard-collect"])
    session = str(out).strip().splitlines()[-1].strip()
    if not session:
        raise BskError("could not determine session id from `bsk session start`")
    return session


def stop_session(session: str) -> None:
    try:
        run_bsk(["session", "stop", session], timeout=30)
    except Exception:
        pass


def collect_board(session: str, board: dict, limit: int) -> list[dict]:
    """Navigate to one board and extract its visible cards."""
    url = f"https://www.dcard.tw/f/{board['slug']}"
    run_bsk(["navigate", "--session", session, url, "--wait-until", "domcontentloaded"], timeout=60)
    time.sleep(NAV_SETTLE_SECONDS)

    # Retry once: the first paint can race the client-side render.
    posts: list[dict] = []
    for attempt in range(2):
        payload = run_bsk(
            ["evaluate", "--session", session, "--json", EXTRACT_JS.replace("__LIMIT__", str(limit))],
            timeout=60,
            want_json=True,
        )
        value = payload.get("value") if isinstance(payload, dict) else None
        if isinstance(value, list) and value:
            posts = value
            break
        if attempt == 0:
            time.sleep(2.0)

    now_iso = datetime.now(TAIPEI).isoformat(timespec="seconds")
    normalized: list[dict] = []
    for post in posts:
        href = post.get("href") or ""
        if not href.startswith("/f/"):
            continue
        normalized.append(
            {
                "board_slug": board["slug"],
                "board_name": board["name"],
                "source_name": f"Dcard {board['name']}",
                "title": post.get("title") or "",
                "link": f"https://www.dcard.tw{href}",
                "published": post.get("published"),
                "published_local": post.get("published_local"),
                "age_text": post.get("age_text"),
                "author": post.get("school"),
                "excerpt": post.get("excerpt"),
                "like": post.get("like"),
                "comment": post.get("comment"),
                "share": post.get("share"),
                "has_image": bool(post.get("has_image")),
                "collected_at": now_iso,
            }
        )
    return normalized


def build_snapshot(session: str, boards: list[dict], limit: int) -> dict:
    board_reports: list[dict] = []
    all_posts: list[dict] = []

    for board in boards:
        try:
            posts = collect_board(session, board, limit)
            status = "ok" if posts else "empty"
        except Exception as exc:  # noqa: BLE001 - one bad board must not kill the run
            print(f"  ! {board['slug']}: {exc}", file=sys.stderr)
            posts, status = [], f"error: {type(exc).__name__}"
        board_reports.append(
            {"slug": board["slug"], "name": board["name"], "status": status, "count": len(posts)}
        )
        all_posts.extend(posts)
        print(f"  {board['slug']:<12} {status:<6} {len(posts)} posts")

    return {
        "schema_version": 1,
        "collected_at": datetime.now(TAIPEI).isoformat(timespec="seconds"),
        "collector": "tools/collect_dcard.py (bsk + Brave)",
        "requested_boards": [b["slug"] for b in boards],
        "boards": board_reports,
        "posts": all_posts,
    }


def read_snapshot(path: Path = SNAPSHOT_PATH) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Dcard board listings via Brave.")
    parser.add_argument("--boards", help="comma-separated slugs (default: built-in list)")
    parser.add_argument("--limit", type=int, default=POSTS_PER_BOARD, help="posts per board")
    parser.add_argument("--session", help="reuse an existing bsk session id")
    parser.add_argument("--out", default=str(SNAPSHOT_PATH), help="snapshot output path")
    parser.add_argument("--dry-run", action="store_true", help="print counts, write nothing")
    args = parser.parse_args()

    boards = DEFAULT_BOARDS
    if args.boards:
        wanted = [s.strip() for s in args.boards.split(",") if s.strip()]
        known = {b["slug"]: b for b in DEFAULT_BOARDS}
        boards = [known.get(slug, {"slug": slug, "name": slug}) for slug in wanted]

    session = args.session
    owns_session = False
    if not session:
        session = start_session()
        owns_session = True
        print(f"started bsk session {session}")
    print(f"collecting {len(boards)} Dcard board(s) ...")

    try:
        snapshot = build_snapshot(session, boards, args.limit)
    finally:
        if owns_session:
            stop_session(session)

    total = len(snapshot["posts"])
    ok_boards = sum(1 for b in snapshot["boards"] if b["status"] == "ok")
    print(f"collected {total} posts from {ok_boards}/{len(boards)} boards")

    if args.dry_run:
        print(json.dumps(snapshot["boards"], ensure_ascii=False, indent=2))
        return 0 if total else 1

    # Never overwrite a good snapshot with an empty one (Cloudflare hiccup, etc.).
    if total == 0:
        previous = read_snapshot(Path(args.out))
        if previous and previous.get("posts"):
            print("no posts collected; keeping existing snapshot", file=sys.stderr)
            return 1
        print("no posts collected and no previous snapshot to keep", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
