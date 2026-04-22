"""
Render the weekly AI digest email from WeeklyItem list.
Groups items by type icon and fills in the weekly_email.html template.
"""
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

TYPE_LABELS = {
    "🛠️": "工具與工作流",
    "💡": "洞見與思考",
    "📝": "教學與指南",
    "🚀": "產品與功能",
}

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "weekly_email.html"


@dataclass
class WeeklyItem:
    handle: str
    title_zh: str
    url: str
    core_method: list[str]
    why_useful: str
    type_icon: str
    priority: int


def _render_item_html(item: WeeklyItem) -> str:
    bullets_html = "\n".join(f"<li>{b}</li>" for b in item.core_method)
    return (
        f'<div class="item-block">'
        f'<a href="{item.url}" class="item-title">{item.type_icon} {item.title_zh}</a>'
        f'<p class="item-handle">@{item.handle}</p>'
        f'<ul class="item-bullets">{bullets_html}</ul>'
        f'<p class="item-why">{item.why_useful}</p>'
        f"</div>"
    )


def _render_type_section(type_icon: str, items: list[WeeklyItem]) -> str:
    if not items:
        return ""
    label = TYPE_LABELS.get(type_icon, type_icon)
    items_html = "\n".join(_render_item_html(i) for i in items)
    return (
        "<tr><td>"
        f'<div class="section-body">'
        f'<h2 class="section-header">{type_icon} {label}</h2>'
        f"{items_html}"
        f"</div>"
        "</td></tr>"
        "<tr><td><div class='divider'></div></td></tr>"
    )


def render_weekly_email(
    items: list[WeeklyItem],
    week_num: int,
    date_str: str,
) -> str:
    """Render weekly digest HTML from WeeklyItem list."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Group by type, in fixed display order
    type_order = ["🛠️", "💡", "📝", "🚀"]
    grouped: dict[str, list[WeeklyItem]] = {t: [] for t in type_order}
    for item in items:
        key = item.type_icon if item.type_icon in grouped else "💡"
        grouped[key].append(item)

    sections_html = "\n".join(
        _render_type_section(t, grouped[t]) for t in type_order
    )

    html = template.replace("{{DATE_DISPLAY}}", date_str)
    html = html.replace("{{WEEK_NUM}}", str(week_num))
    html = html.replace("{{WEEKLY_ITEMS}}", sections_html)
    return html