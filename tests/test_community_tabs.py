"""Tests for the community tabs: PTT board listings and the Dcard snapshot."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.models import NormalizedArticle
from src.ptt_fetcher import infer_year, parse_board_index, parse_post_date, parse_push_count
from src.selector import map_to_display_category, select_by_category
from src.snapshot_loader import load_dcard_board

PTT_INDEX_HTML = """
<html><body>
<div class="r-ent">
    <div class="nrec"><span class="hl f2">8</span></div>
    <div class="title"><a href="/bbs/Stock/M.1791010505.A.157.html">[公告] 水桶</a></div>
    <div class="meta">
        <div class="author">BlueBird5566</div>
    </div>
    <div class="date">10/03</div>
</div>
<div class="r-ent">
    <div class="nrec"><span class="hl f1">爆</span></div>
    <div class="title"><a href="/bbs/Stock/M.1791016608.A.717.html">[新聞] 台積電傳與馬斯克合作</a></div>
    <div class="meta">
        <div class="author">waitrop</div>
    </div>
    <div class="date">10/03</div>
</div>
<div class="r-ent">
    <div class="nrec"></div>
    <div class="title"><a href="/bbs/Stock/M.1791016999.A.999.html">Re: [請益] 該不該換工作</a></div>
    <div class="meta">
        <div class="author">someone</div>
    </div>
    <div class="date">10/02</div>
</div>
<div class="r-ent">
    <div class="nrec"></div>
    <div class="title">(本文已被刪除)</div>
    <div class="meta">
        <div class="author">-</div>
    </div>
    <div class="date">10/02</div>
</div>
<div class="r-ent">
    <div class="nrec"><span class="hl f3">X1</span></div>
    <div class="title"><a href="/bbs/Stock/search?q=thread%3A%5B公告%5D">搜尋同標題文章</a></div>
    <div class="meta">
        <div class="author">-</div>
    </div>
    <div class="date">10/02</div>
</div>
<div class="r-list-sep"></div>
<div class="r-ent">
    <div class="nrec"></div>
    <div class="title"><a href="/bbs/Stock/M.1771671779.A.6ED.html">[公告] 股票板板規</a></div>
    <div class="meta">
        <div class="author">moderator</div>
    </div>
    <div class="date">02/21</div>
</div>
</body></html>
"""


class TestPushCount:
    def test_numeric(self):
        assert parse_push_count("23") == (23, "23")

    def test_empty_means_zero(self):
        assert parse_push_count("") == (0, "0")
        assert parse_push_count("   ") == (0, "0")

    def test_bao_is_capped_at_100(self):
        assert parse_push_count("爆") == (100, "爆")

    def test_negative_scores(self):
        assert parse_push_count("X1") == (-10, "X1")
        assert parse_push_count("X9") == (-90, "X9")

    def test_unknown_label_is_kept_but_unvalued(self):
        value, label = parse_push_count("??")
        assert value is None
        assert label == "??"


class TestPostDate:
    def test_infer_year_rolls_back_for_future_dates(self):
        now = datetime(2026, 1, 2, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        # 12/31 with today = Jan 2 must belong to the previous year.
        assert infer_year(12, 31, now) == 2025
        assert infer_year(1, 1, now) == 2026

    def test_parse_post_date(self):
        now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        parsed = parse_post_date("10/02", now)
        assert parsed is not None
        assert (parsed.year, parsed.month, parsed.day) == (2026, 10, 2)

    def test_unparseable_date_returns_none(self):
        assert parse_post_date("") is None
        assert parse_post_date("昨天") is None


class TestParseBoardIndex:
    def test_extracts_rows_and_skips_noise(self):
        entries = parse_board_index(PTT_INDEX_HTML, "Stock")

        # Dropped: the [公告] announcement, the deleted post, the search link,
        # and everything after the pinned separator.
        assert len(entries) == 2
        titles = [e["title"] for e in entries]
        assert titles == ["[新聞] 台積電傳與馬斯克合作", "Re: [請益] 該不該換工作"]

    def test_pinned_and_announcement_rows_are_excluded(self):
        entries = parse_board_index(PTT_INDEX_HTML, "Stock")
        titles = " ".join(e["title"] for e in entries)
        assert "板規" not in titles
        assert "水桶" not in titles

    def test_push_counts_and_authors(self):
        entries = parse_board_index(PTT_INDEX_HTML, "Stock")
        assert entries[0]["_metrics"]["push"] == 100
        assert entries[0]["_metrics"]["push_label"] == "爆"
        assert entries[1]["_metrics"]["push"] == 0
        assert entries[0]["_metrics"]["author"] == "waitrop"
        assert entries[0]["_metrics"]["board"] == "Stock"
        assert entries[0]["_metrics"]["origin"] == "ptt_list"
        assert entries[0]["_metrics"]["date_precision"] == "day"

    def test_links_are_absolute(self):
        entries = parse_board_index(PTT_INDEX_HTML, "Stock")
        assert entries[0]["link"].startswith("https://www.ptt.cc/bbs/Stock/")


def make_ptt_article(board: str, push: int, minutes_ago: int) -> NormalizedArticle:
    return NormalizedArticle(
        title=f"{board} post push={push}",
        link=f"https://www.ptt.cc/bbs/Stock/M.{push}.html",
        published=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        source_name=f"PTT {board}",
        language="zh",
        tab="ptt_hot",
        rss_category=board,
        guid=f"{board}-{push}",
        description="",
        metrics={"push": push, "push_label": str(push), "origin": "ptt_list"},
    )


class TestPttSelection:
    def test_section_is_the_board_name(self):
        article = make_ptt_article("股票板", 10, 5)
        assert map_to_display_category(article) == "股票板"

    def test_ranked_by_push_not_recency(self):
        articles = [
            make_ptt_article("股票板", 5, 1),    # newest, low push
            make_ptt_article("股票板", 90, 600),  # oldest, highest push
            make_ptt_article("股票板", 40, 30),
        ]
        selected = select_by_category(articles)
        pushes = [a.metrics["push"] for a in selected["ptt_hot"]["股票板"]]
        # Highest push first, even though it is the oldest post.
        assert pushes == [90, 40, 5]


def test_dcard_snapshot_loader(tmp_path):
    snapshot = {
        "schema_version": 1,
        "collected_at": "2026-10-03T21:26:22+08:00",
        "collector": "tools/collect_dcard.py (bsk + Brave)",
        "boards": [{"slug": "tech_job", "name": "科技業板", "status": "ok", "count": 1}],
        "posts": [
            {
                "board_slug": "tech_job",
                "board_name": "科技業板",
                "source_name": "Dcard 科技業板",
                "title": "聯發科什麼公司啊",
                "link": "https://www.dcard.tw/f/tech_job/p/262238210",
                "published": "2026-10-02T02:15:32.490Z",
                "excerpt": "AI token使用上限一下就達標了",
                "like": 137,
                "comment": 134,
                "author": "國立臺灣大學",
            },
            {
                "board_slug": "money",
                "board_name": "理財板",
                "title": "其他看板的文章不該被選進科技業板",
                "link": "https://www.dcard.tw/f/money/p/1",
                "like": 1,
            },
        ],
    }
    path = tmp_path / "dcard_latest.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    entries, status = load_dcard_board("tech_job", "科技業板", snapshot_path=path)
    assert status == "ok"
    assert len(entries) == 1
    assert entries[0]["title"] == "聯發科什麼公司啊"
    assert entries[0]["_metrics"]["like"] == 137
    assert entries[0]["_metrics"]["origin"] == "dcard_snapshot"

    missing, status = load_dcard_board("nope", "不存在板", snapshot_path=path)
    assert status == "empty"
    assert missing == []


def test_dcard_snapshot_missing_file_is_reported(tmp_path):
    entries, status = load_dcard_board("tech_job", "科技業板", snapshot_path=tmp_path / "absent.json")
    assert status == "snapshot_missing"
    assert entries == []


@pytest.mark.parametrize("tab", ["ptt_hot", "dcard_hot"])
def test_community_tabs_are_registered(tab):
    from src.selector import ITEMS_PER_CATEGORY, TAB_CATEGORIES

    assert TAB_CATEGORIES[tab]
    assert ITEMS_PER_CATEGORY[tab] >= 1


def test_ptt_page_url_pagination():
    from src.ptt_fetcher import _page_url

    index = "https://www.ptt.cc/bbs/Stock/index.html"
    # Page 1 is the board's current list; pages >= 2 are a 熱門文章 archive, so
    # every shipped source keeps `pages` at its default of 1.
    assert _page_url(index, 1) == index
    assert _page_url(index, 2) == "https://www.ptt.cc/bbs/Stock/index2.html"
    assert _page_url(index, 3) == "https://www.ptt.cc/bbs/Stock/index3.html"
