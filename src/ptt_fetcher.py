"""
PTT board listing fetcher.

PTT exposes no per-board RSS with engagement data, but two server-side surfaces
are reachable from CI without any browser:

1. Board index page  https://www.ptt.cc/bbs/<Board>/index.html
   → title, link, author, post date, and the 推文數 (push count) shown in
     `<div class="nrec">`. This is the primary source because push count is what
     makes a "熱門" tab meaningful.

2. Official Atom feed  https://www.ptt.cc/atom/<Board>.xml
   → reliable timestamps but no push count. Used only as a fallback when the
     index page cannot be parsed.

Both were verified reachable (HTTP 200) from a clean CI-like environment on
2026-10-03. `https://www.ptt.cc/robots.txt` returns 404 (no robots policy
published), and PTT publishes no AI-crawler directives. Requests are rate-limited
to one per board with a polite User-Agent and a short delay between boards.
"""
from __future__ import annotations

import html as html_lib
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
import requests

logger = logging.getLogger(__name__)

TAIPEI = timezone(timedelta(hours=8))

PTT_BASE = "https://www.ptt.cc"
DEFAULT_USER_AGENT = "NewsDigest/1.0 (RSS Reader)"
DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 2
INTER_BOARD_DELAY = 1.0

# `<div class="r-ent">` is the per-row container on PTT board index pages.
_ROW_SPLIT = '<div class="r-ent">'
# Board index pages separate the live list from the moderator-pinned (置底)
# block with this marker. Pinned rows are announcements, not news — and since we
# rank by push count they would otherwise crowd out the real posts.
_PINNED_SEPARATOR = '<div class="r-list-sep">'
# Announcement posts also appear inline in the live list.
EXCLUDED_TITLE_PREFIXES = ('[公告]',)

_RE_TITLE = re.compile(r'<div class="title">(.*?)</div>', re.S)
_RE_TITLE_LINK = re.compile(r'<a href="([^"]+)">(.*?)</a>', re.S)
_RE_NREC = re.compile(r'<div class="nrec">(.*?)</div>', re.S)
_RE_NREC_SPAN = re.compile(r"<span[^>]*>(.*?)</span>", re.S)
_RE_AUTHOR = re.compile(r'<div class="author">(.*?)</div>', re.S)
_RE_DATE = re.compile(r'<div class="date">(.*?)</div>', re.S)
_RE_ARTICLE_HREF = re.compile(r"^/bbs/[^/]+/M\.[0-9A-Za-z.\-]+\.html$")


def parse_push_count(raw: str) -> tuple[Optional[int], str]:
    """
    Convert PTT's `nrec` cell into a numeric push count.

    PTT renders: '' (no pushes), a number, '爆' (>=100), 'XX' (>=100 dislikes),
    or 'X1'..'X9' (negative score).

    Returns:
        (numeric value or None, display label)
    """
    label = (raw or "").strip()
    if not label:
        return 0, "0"
    if label == "爆":
        return 100, "爆"
    if label.startswith("X"):
        tail = label[1:]
        if tail.isdigit():
            return -10 * int(tail), label
        return None, label
    if label.isdigit():
        return int(label), label
    return None, label


def infer_year(month: int, day: int, now: Optional[datetime] = None) -> int:
    """PTT index rows show `M/D` with no year; pick the year closest to today."""
    now = now or datetime.now(TAIPEI)
    year = now.year
    try:
        candidate = datetime(year, month, day, 0, 0, tzinfo=TAIPEI)
    except ValueError:
        return year
    # A row dated "in the future" by more than a day must belong to last year.
    if candidate - now > timedelta(days=1):
        year -= 1
    return year


def parse_post_date(raw: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Parse PTT's `M/D` post date into a timezone-aware datetime."""
    text = (raw or "").strip()
    match = re.match(r"^(\d{1,2})/(\d{1,2})$", text)
    if not match:
        return None
    month, day = int(match.group(1)), int(match.group(2))
    year = infer_year(month, day, now)
    try:
        return datetime(year, month, day, 12, 0, tzinfo=TAIPEI)
    except ValueError:
        return None


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return html_lib.unescape(text).strip()


def parse_board_index(page_html: str, board: str) -> list[dict]:
    """
    Parse a PTT board index page into feed-entry-shaped dicts.

    Rows in the pinned (置底) block and announcement titles are dropped: they are
    moderator notices, not posts, and would otherwise dominate a push-ranked list.
    """
    now = datetime.now(TAIPEI)
    entries: list[dict] = []

    # Drop everything from the pinned separator onwards.
    live_html = page_html.split(_PINNED_SEPARATOR, 1)[0]
    pinned_rows = page_html.count(_ROW_SPLIT) - live_html.count(_ROW_SPLIT)
    if pinned_rows > 0:
        logger.debug("PTT %s: skipped %d pinned rows", board, pinned_rows)

    skipped_announcements = 0
    for chunk in live_html.split(_ROW_SPLIT)[1:]:
        title_block = _RE_TITLE.search(chunk)
        if not title_block:
            continue
        link_match = _RE_TITLE_LINK.search(title_block.group(1))
        if not link_match:
            # Deleted posts render as `<a>`-less titles; skip them.
            continue

        href = html_lib.unescape(link_match.group(1)).strip()
        if not _RE_ARTICLE_HREF.match(href):
            # e.g. search links on announcement rows.
            continue

        title = _clean(link_match.group(2))
        if not title:
            continue
        if title.startswith(EXCLUDED_TITLE_PREFIXES):
            skipped_announcements += 1
            continue

        nrec_block = _RE_NREC.search(chunk)
        nrec_raw = ""
        if nrec_block:
            span = _RE_NREC_SPAN.search(nrec_block.group(1))
            nrec_raw = _clean(span.group(1)) if span else _clean(nrec_block.group(1))
        push_value, push_label = parse_push_count(nrec_raw)

        author_block = _RE_AUTHOR.search(chunk)
        author = _clean(author_block.group(1)) if author_block else ""

        date_block = _RE_DATE.search(chunk)
        published = parse_post_date(date_block.group(1) if date_block else "", now)

        link = href if href.startswith("http") else f"{PTT_BASE}{href}"
        entries.append(
            {
                "title": title,
                "link": link,
                "published": published.isoformat() if published else "",
                "published_parsed": published.timetuple() if published else None,
                "summary": "",
                "guid": link,
                "source_feed_url": f"{PTT_BASE}/bbs/{board}/index.html",
                "_metrics": {
                    "push": push_value,
                    "push_label": push_label,
                    "author": author,
                    "board": board,
                    "origin": "ptt_list",
                    # PTT board rows only expose `M/D` — the renderer must not
                    # invent a time-of-day for these.
                    "date_precision": "day",
                },
            }
        )

    if skipped_announcements:
        logger.debug("PTT %s: skipped %d announcement rows", board, skipped_announcements)
    return entries


def _fetch(url: str, timeout: int, retries: int, user_agent: str) -> Optional[requests.Response]:
    backoff = [1, 2, 4]
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "PTT request failed for %s (attempt %d/%d): %s", url, attempt + 1, retries + 1, exc
            )
            if attempt < retries:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])
    return None


def _fetch_atom(url: str, board: str, source_name: str, timeout: int, retries: int,
                user_agent: str, max_items: int) -> list[dict]:
    """Fallback: official Atom feed (no push counts available)."""
    response = _fetch(url, timeout, retries, user_agent)
    if response is None:
        return []
    feed = feedparser.parse(response.content)
    entries = []
    for entry in feed.entries[:max_items]:
        link = entry.get("link") or entry.get("id") or ""
        if not link:
            continue
        entries.append(
            {
                "title": _clean(entry.get("title", "")),
                "link": link,
                "published": entry.get("published", entry.get("updated", "")),
                "published_parsed": entry.get("published_parsed", entry.get("updated_parsed")),
                "summary": _clean(entry.get("summary", entry.get("description", ""))),
                "guid": entry.get("id", link),
                "source_feed_url": url,
                "_metrics": {
                    "push": None,
                    "push_label": "",
                    "author": "",
                    "board": board,
                    "origin": "ptt_atom",
                },
            }
        )
    if entries:
        logger.info("PTT Atom fallback for %s returned %d items", source_name, len(entries))
    return entries


def _page_url(url: str, page: int) -> str:
    """`index.html` → `index2.html` for the second page."""
    if page <= 1:
        return url
    if url.endswith("index.html"):
        return f"{url[:-len('index.html')]}index{page}.html"
    return url


def fetch_ptt_board(
    url: str,
    board: str,
    source_name: str = "",
    fallback_url: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    user_agent: str = DEFAULT_USER_AGENT,
    max_items: int = 30,
    pages: int = 1,
) -> tuple[list[dict], str]:
    """
    Fetch one PTT board.

    `pages` walks back through the index pages and merges rows by link.

    ⚠️ Default is 1 and that default matters. Measured 2026-10-03: PTT index pages
    past the first are a 熱門文章 archive, not a chronological continuation —
    Stock's page 2 spanned Aug–Sep, Tech_Job's Jan–Apr, PC_Shopping's 2025-10.
    Raising `pages` mixes months-old posts into a push-ranked list. Only raise it
    for a board that has been re-verified as chronological.

    Returns:
        (entries, status) where status is one of:
          'ok'            index page parsed
          'ok_atom_fallback'  index page unusable, Atom succeeded
          'empty'         both surfaces returned nothing
    """
    label = source_name or board
    entries: list[dict] = []
    seen: set[str] = set()

    for page in range(1, max(1, pages) + 1):
        response = _fetch(_page_url(url, page), timeout, retries, user_agent)
        if response is None:
            break
        page_entries = parse_board_index(response.text, board)
        if not page_entries:
            break
        added = 0
        for entry in page_entries:
            if entry["link"] in seen:
                continue
            seen.add(entry["link"])
            entries.append(entry)
            added += 1
        logger.debug("PTT %s page %d: %d new rows", label, page, added)
        if len(entries) >= max_items or page >= pages:
            break
        time.sleep(INTER_BOARD_DELAY)

    if entries:
        entries = entries[:max_items]
        logger.info("PTT index %s: %d rows", label, len(entries))
        return entries, "ok"

    logger.warning("PTT index %s parsed 0 rows; trying Atom fallback", label)
    if fallback_url:
        entries = _fetch_atom(fallback_url, board, label, timeout, retries, user_agent, max_items)
        if entries:
            return entries, "ok_atom_fallback"

    return [], "empty"
