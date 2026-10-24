"""Render a PartyPlan as Markdown, JSON or a shareable HTML invitation."""

from __future__ import annotations

import datetime as _dt
import html
import json
from typing import Any, Dict, List

from .models import Plan

OCCASION_LABELS = {
    "birthday": "生日派对",
    "team": "团队团建",
    "family": "家庭聚会",
    "tasting": "品鉴会",
}


def _occasion_label(plan: Plan) -> str:
    return OCCASION_LABELS.get(plan.request.occasion, plan.request.occasion or "派对")


def _fmt_date(date_str: str) -> str:
    try:
        d = _dt.date.fromisoformat(date_str[:10])
        week = "一二三四五六日"[d.weekday()]
        return f"{d.month} 月 {d.day} 日（周{week}）"
    except ValueError:
        return date_str


def _short_date(date_str: str) -> str:
    try:
        d = _dt.date.fromisoformat(date_str[:10])
        return f"{d.month}/{d.day}"
    except ValueError:
        return date_str


def _fmt_price(value: float) -> str:
    return f"¥{value:g}/人" if value else ""


def _plan_json(plan: Plan) -> Dict[str, Any]:
    data = plan.to_dict()
    data["occasion_label"] = _occasion_label(plan)
    return data


def render_markdown(plan: Plan) -> str:
    req = plan.request
    chosen = plan.chosen
    lines = [
        f"# {_occasion_label(plan)}策划案",
        "",
        f"- 城市：{plan.city.name if plan.city else '-'}",
        f"- 门店：{plan.store.name if plan.store else '-'}"
        + (f"（{plan.store.address}）" if plan.store and plan.store.address else ""),
        f"- 日期：{_fmt_date(chosen.date) if chosen else '-'}",
        f"- 场次：{(chosen.start + ' - ' + chosen.end) if chosen else '-'}",
        f"- 人数：{req.party_size} 人",
    ]
    if chosen and chosen.price:
        lines.append(f"- 参考价：{_fmt_price(chosen.price)}")
    lines += ["", "## 选择理由", ""]
    lines += [f"- {reason}" for reason in plan.reasons] or ["- （无）"]

    others = [d for d in plan.dates if not chosen or d != chosen.date]
    if others:
        lines += ["", f"## 其他可约日期（{len(others)} 天）", ""]
        lines += [" · ".join(_short_date(d) for d in others[i:i + 4])
                  for i in range(0, len(others), 4)]

    if plan.sessions:
        lines += ["", "## 当天场次", "", "| 时间 | 容量 | 参考价 |", "| --- | --- | --- |"]
        for s in plan.sessions:
            start = f"**{s.start}**" if chosen and s.session_id == chosen.session_id else s.start
            lines.append(f"| {start} - {s.end} | {s.capacity or '-'} | "
                         f"{('¥%g' % s.price) if s.price else '-'} |")

    lines += [
        "",
        "## 预订",
        "",
        "```bash",
        f"mcdparty book --city {req.city} --date {chosen.date if chosen else ''} "
        f"--session {chosen.session_id if chosen else ''} --size {req.party_size} --confirm",
        "```",
        "",
        "> 数据来自 query-party-* 四个工具的实时返回；价格与余位以麦当劳官方渠道为准。",
    ]
    return "\n".join(lines)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__PAGE_TITLE__</title>
<meta property="og:title" content="__PAGE_TITLE__">
<meta property="og:description" content="__OG_DESC__">
<style>
  body { margin:0; padding:32px 16px; background:#fffdf5; color:#2b2b2b;
         font-family:"PingFang SC","Microsoft YaHei",sans-serif;
         display:flex; justify-content:center; }
  .card { width:100%; max-width:520px; background:#fff; border:1px solid #f0dfa8;
          border-radius:16px; overflow:hidden; }
  .hero { padding:24px 24px 18px; border-bottom:1px solid #f6ecc9; }
  .hero h1 { font-size:22px; font-weight:600; margin:0 0 6px; }
  .hero p { font-size:13px; color:#6b6152; margin:0; }
  .body { padding:8px 24px 22px; }
  .rows { margin:0; }
  .row { display:flex; justify-content:space-between; gap:16px; padding:11px 0;
         font-size:14px; border-top:1px solid #f6ecc9; }
  .row:first-child { border-top:none; }
  .row .k { color:#6b6152; }
  .row .v { font-weight:600; text-align:right; }
  .why { margin-top:18px; padding:2px 0 2px 14px; border-left:2px solid #FFC72C; }
  .why h2 { font-size:13px; font-weight:600; margin:0 0 6px; }
  .why li { font-size:13px; line-height:1.7; margin-left:18px; }
  .footer { margin-top:18px; font-size:12px; color:#6b6152; text-align:center; line-height:1.6; }
</style>
</head>
<body>
  <div class="card">
    <div class="hero">
      <h1>__TITLE__</h1>
      <p>__CITY__ · __STORE__</p>
    </div>
    <div class="body">
      <div class="rows">
        <div class="row"><span class="k">日期</span><span class="v">__DATE__</span></div>
        <div class="row"><span class="k">场次</span><span class="v">__TIME__</span></div>
        <div class="row"><span class="k">人数</span><span class="v">__SIZE__ 人</span></div>
        <div class="row"><span class="k">参考价</span><span class="v">__PRICE__</span></div>
      </div>
      <div class="why"><h2>为什么选这一场</h2><ul>__REASONS__</ul></div>
      <div class="footer">由「麦麦派对策划师」整理 · 价格与余位以麦当劳官方渠道为准<br>
      独立开发作品，非麦当劳官方产品</div>
    </div>
  </div>
</body>
</html>
"""


def _guest_reasons(plan: Plan) -> List[str]:
    """Keep at most two human-facing reasons for the invitation card.

    The full scoring log belongs to the CLI output; an invitee only needs to
    know why this slot suits them.
    """
    keep: List[str] = []
    for reason in plan.reasons:
        if "周末场" in reason and len(keep) < 2:
            keep.append("周末场，亲友到场率最高")
        elif "下午场" in reason and len(keep) < 2:
            keep.append("下午场，小朋友不用请假")
        elif "傍晚场" in reason and len(keep) < 2:
            keep.append("傍晚场，下班后直接到店")
        elif "容量" in reason and "≥" in reason and len(keep) < 2:
            keep.append(f"场地可容纳 {plan.chosen.capacity} 人，够坐")
    return keep or plan.reasons[:2]


def render_html(plan: Plan) -> str:
    chosen = plan.chosen
    req = plan.request
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in _guest_reasons(plan))
    occasion = _occasion_label(plan)
    date_text = _fmt_date(chosen.date) if chosen else "-"
    time_text = f"{chosen.start} - {chosen.end}" if chosen else "-"
    page_title = f"{occasion} · {_short_date(chosen.date) if chosen else ''} {chosen.start if chosen else ''} · " \
                 f"{plan.store.name if plan.store else ''}".strip(" ·")
    store_line = plan.store.name if plan.store else "-"
    if plan.store and plan.store.address:
        store_line = f"{plan.store.name}（{plan.store.address}）"
    return (
        _HTML_TEMPLATE.replace("__PAGE_TITLE__", html.escape(page_title))
        .replace("__OG_DESC__", html.escape(f"{occasion}邀请 · {date_text} {time_text} · {req.party_size} 人"))
        .replace("__TITLE__", html.escape(f"{occasion}邀请"))
        .replace("__CITY__", html.escape(plan.city.name if plan.city else "-"))
        .replace("__STORE__", html.escape(store_line))
        .replace("__DATE__", html.escape(date_text))
        .replace("__TIME__", html.escape(time_text))
        .replace("__SIZE__", html.escape(str(req.party_size)))
        .replace("__PRICE__", html.escape(_fmt_price(chosen.price) if chosen else "以官方页面为准"))
        .replace("__REASONS__", reasons)
    )


def render(plan: Plan, fmt: str = "markdown") -> str:
    if fmt == "json":
        return json.dumps(_plan_json(plan), ensure_ascii=False, indent=2)
    if fmt == "html":
        return render_html(plan)
    return render_markdown(plan)
