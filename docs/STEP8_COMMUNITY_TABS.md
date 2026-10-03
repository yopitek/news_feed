# STEP 8 — Community Tabs (PTT 熱門 / Dcard 熱門)

This step added two tabs that are not plain RSS feeds, and the plumbing that lets
them coexist with the existing pipeline.

---

## 1. Why these two sources need custom collectors

| Source | Reachable from CI? | Recommended surface | Kept data |
|--------|--------------------|---------------------|-----------|
| PTT | ✅ yes | board index page (`/bbs/<Board>/index.html`) | title, link, 推文數, author, `M/D` |
| PTT (fallback) | ✅ yes | official Atom (`/atom/<Board>.xml`) | title, link, ISO timestamp (no push count) |
| Dcard | ❌ no — HTTP 403 + Cloudflare Turnstile | local Brave session → committed JSON snapshot | title, link, ISO timestamp, 愛心/留言/分享, school |

Evidence gathered on 2026-10-03:

* `https://www.ptt.cc/robots.txt` → **404** (no robots policy published); PTT publishes no AI-crawler directives.
* `https://www.ptt.cc/bbs/Gossiping/index.html` → **200**, 13 rows parsed.
* `https://www.ptt.cc/atom/Stock.xml` → **200**, valid Atom.
* `https://www.dcard.tw/robots.txt` → only disallows `/emails/activate`; no AI policy.
* `curl` / `urllib` (browser-like headers) / `curl_cffi(impersonate="chrome")` against `dcard.tw/f/*` → **403**, body is the Turnstile challenge page.
* The same pages load fine in a real Brave session, so collection is delegated to the operator's machine.

---

## 2. Source `type` field

`config/feeds.yaml` sources gained an optional `type`:

```yaml
- category: 股票板
  type: ptt_list
  board: Stock
  url: https://www.ptt.cc/bbs/Stock/index.html
  fallback_url: https://www.ptt.cc/atom/Stock.xml
  source_name: PTT 股票板
```

`src/config_loader.parse_source()` whitelists `type`, `group`, `board`,
`board_name`, `fallback_url`. Anything else in YAML is dropped, so a typo cannot
silently change behaviour.

`src/feed_fetcher.fetch_all_feeds()` dispatches:

| `type` | Collector |
|--------|-----------|
| `rss` (default) | `feed_fetcher.fetch_feed` |
| `ptt_list` | `ptt_fetcher.fetch_ptt_board` |
| `dcard_snapshot` | `snapshot_loader.load_dcard_board` |

Unknown types produce a `config_error` row in the health table instead of silently
falling back to RSS.

---

## 3. Engagement metrics

`NormalizedArticle` and `ArticleWithSummary` gained an optional `metrics: dict`.
It is populated by the collectors, carried through the normalizer and the
summarizer, and rendered as a badge:

| Tab | `metrics` keys | Badge |
|-----|----------------|-------|
| `ptt_hot` | `push`, `push_label`, `author`, `date_precision: day` | `推 爆 · waitrop` |
| `dcard_hot` | `like`, `comment`, `share`, `author`, `origin` | `愛心 137 · 留言 110` |

Push-count parsing (`ptt_fetcher.parse_push_count`) understands PTT's vocabulary:
empty → `0`, `爆` → `100`, `X1`..`X9` → `-10..-90`.

PTT board rows only expose `M/D`, so those metrics carry `date_precision: day` and
the renderer prints `%m/%d` without inventing a time of day. The year is inferred by
`infer_year()`: a date that lands more than a day in the future must be last year.

### Rows that are dropped

Two classes of row are removed before ranking, because a push-ranked list would
otherwise be dominated by them:

| Dropped | How it is detected | Why |
|---------|--------------------|-----|
| 置底 (pinned) block | everything after `<div class="r-list-sep">` | moderator notices, not posts |
| `[公告]` titles | title prefix | board announcements, not news |

Measured on 2026-10-03: 3–5 pinned rows per board out of 12–19 total.

### Only page 1 is fetched — and why

`fetch_ptt_board` accepts a `pages` argument, but every source leaves it at the
default of **1**. A first attempt used `pages: 2` to top up thin sections; measuring
the dates proved that was wrong:

| Board | page 1 | page 2 |
|-------|--------|--------|
| Gossiping | 2026-10-03 | **2026-06-21 … 06-22** |
| Stock | 2026-10-03 | 2026-08-03 … 09-11 |
| Tech_Job | 2026-09-28 … 10-03 | 2026-01-21 … 04-10 |
| Soft_Job | 2026-09-10 … 09-29 | 2026-06-14 |
| PC_Shopping | 2026-10-02 … 10-03 | **2025-10-05 … 2026-09-28** |

PTT index pages beyond the first are a 熱門文章 archive, **not** a chronological
continuation. Pulling them in injected three-month-old posts (a 06/22 Gossiping post
with 94 pushes topped the tab) into a push-ranked list. Page 1 alone is the board's
genuinely current list, so that is what we take.

---

## 4. Ranking and the recency window

Two tabs break the "newest first / last 24 hours" rule that every other tab follows:

* **Ranking** — `selector.TAB_SORT_METRIC` maps `ptt_hot → push` and
  `dcard_hot → like`. Selection sorts by `(metric, published)` descending, so a
  three-day-old post with 90 pushes outranks a fresh post with 2.
* **Window** — `settings.tab_time_window_hours` disables the 24h cutoff for these
  tabs (`null`). A board's front page is already bounded by the site itself, and a
  24h filter would silently drop exactly the highest-ranked posts.

Missing metrics sort last (`engagement_value` returns `-1`), which is what keeps
Atom-fallback rows from jumping to the top of the PTT tab.

---

## 5. The Dcard snapshot

```
tools/collect_dcard.py         (local: bsk + Brave)
        │  writes
        ▼
data/dcard_latest.json         (committed to the repo)
        │  read by
        ▼
src/snapshot_loader.py  →  pipeline  →  docs/index.html
```

Snapshot schema:

```json
{
  "schema_version": 1,
  "collected_at": "2026-10-03T21:26:22+08:00",
  "collector": "tools/collect_dcard.py (bsk + Brave)",
  "boards": [{"slug": "tech_job", "name": "科技業板", "status": "ok", "count": 20}],
  "posts": [{"board_slug": "...", "title": "...", "link": "...",
             "published": "2026-10-02T16:42:34.534Z", "like": 149,
             "comment": 113, "author": "國立陽明交通大學", "...": "..."}]
}
```

Design decisions worth keeping:

1. **One page load per board**, 2s settle, 1s between nav calls. No pagination, no
   infinite scroll — we take the board's own front page.
2. **Never blank the tab.** A run that collects zero posts refuses to overwrite an
   existing non-empty snapshot and exits non-zero.
3. **Metrics are read from SVG path signatures**, not button index. Dcard renders
   a variable number of reaction-emoji buttons, which shifts positions; the heart
   (`M7.999 14s6.666-3.917…`) and speech bubble (`M6.475 11.206v1.343…`) paths are
   stable across cards.
4. **The timestamp comes from `<time datetime="…">`**, an absolute ISO value — not
   from the relative "19 小時" label that is also on the card.
5. **The page always prints the snapshot time**, and flags it in red past 48h, so a
   stale snapshot is visible rather than silent.

---

## 6. Board slugs

Dcard — verified against `https://www.dcard.tw/forum/popular`:

| Section | Slug | Note |
|---------|------|------|
| 科技業板 | `tech_job` | |
| AI 工作者板 | `ai_builder` | |
| 3C 板 | `3c` | |
| 理財板 | `money` | |

⚠️ `soft_job` and `salary` are **not** Dcard boards — both return「找不到頁面」.
They were tried first and rejected.

PTT: `Gossiping`, `Stock`, `Tech_Job`, `Soft_Job`, `PC_Shopping` — all HTTP 200.

---

## 7. Verification performed

* `pytest tests/` → 45 passed (11 new cases: push parsing, date inference, index
  parsing, engagement ranking, snapshot loading).
* Full pipeline run: 72 sources → 6 tabs rendered, snapshot notice present,
  `output/run_summary.json` carries `dcard_snapshot` and the new tab categories.
* Snapshot collection: 84 posts from 4/4 boards.
