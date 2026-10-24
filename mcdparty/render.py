"""Render a PartyPlan as Markdown, JSON or a shareable HTML invitation.

``live`` controls two things that must never lie:
  * the footer - offline replay is labelled as replay, not as live data
  * the booking hint - the offline demo must not print a ``--confirm`` order
    command, because its session ids come from fixtures, not the real API
"""

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

FOOTER_LIVE = "数据来自 query-party-* 四个工具的实时返回；价格与余位以麦当劳官方渠道为准。"
FOOTER_DEMO = "离线回放（内置 fixtures），非实时数据；真实价格与余位以麦当劳官方渠道为准。"


def _occasion_label(plan: Plan) -> str:
    return OCCASION_LABELS.get(plan.request.occasion, plan.request.occasion or "派对")


def _weekday_cn(d: _dt.date) -> str:
    return "一二三四五六日"[d.weekday()]


def _fmt_date(date_str: str) -> str:
    try:
        d = _dt.date.fromisoformat(date_str[:10])
        return f"{d.month} 月 {d.day} 日（周{_weekday_cn(d)}）"
    except ValueError:
        return date_str


def _fmt_price(value: float) -> str:
    return f"¥{value:g}/人" if value else ""


def _plan_json(plan: Plan) -> Dict[str, Any]:
    data = plan.to_dict()
    data["occasion_label"] = _occasion_label(plan)
    return data


def render_markdown(plan: Plan, live: bool = True) -> str:
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
        lines.append("、".join(_fmt_date(d) for d in others))

    if plan.sessions:
        lines += [
            "", "## 当天场次", "",
            "加粗为当前推荐场次。", "",
            "| 场次 ID | 时间 | 容量 | 参考价 |", "| --- | --- | --- | --- |",
        ]
        for s in plan.sessions:
            row = [s.session_id, f"{s.start} - {s.end}", str(s.capacity or "-"),
                   f"¥{s.price:g}" if s.price else "-"]
            if chosen and s.session_id == chosen.session_id:
                row = [f"**{cell}**" for cell in row]
            lines.append("| " + " | ".join(row) + " |")

    lines += ["", "## 预订", ""]
    book = (
        f"mcdparty book --city {req.city} --date {chosen.date if chosen else ''} "
        f"--session {chosen.session_id if chosen else ''} --size {req.party_size}"
    )
    if live:
        lines += [
            "```bash",
            f"{book} --confirm",
            "```",
            "",
            "不加 `--confirm` 时只预览下单参数，不会提交。",
        ]
    else:
        lines += [
            "离线演示不提供下单。接入真实 MCP 后，同一条命令先预览：",
            "",
            "```bash",
            book,
            "```",
            "",
            "确认参数无误后再追加 `--confirm` 提交。",
        ]
    lines += ["", f"> {FOOTER_LIVE if live else FOOTER_DEMO}"]
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
  .hero { padding:24px 24px 18px; border-bottom:1px solid #ece0bb; }
  .hero h1 { font-size:22px; font-weight:600; margin:0 0 6px; }
  .hero p { font-size:13px; color:#6b6152; margin:0; }
  .body { padding:8px 24px 22px; }
  .row { display:flex; justify-content:space-between; gap:16px; padding:11px 0;
         font-size:14px; border-top:1px solid #ece0bb; }
  .row:first-child { border-top:none; }
  .row .k { color:#6b6152; }
  .row .v { font-weight:600; text-align:right; }
  .why { margin-top:18px; padding:2px 0 2px 14px; border-left:2px solid #FFC72C; }
  .why h2 { font-size:12px; font-weight:600; letter-spacing:.06em; color:#6b6152; margin:0 0 6px; }
  .why ul { margin:0; padding:0 0 0 1.1em; }
  .why li { font-size:13px; line-height:1.7; }
  .footer { margin-top:18px; font-size:12px; color:#6b6152; text-align:center; line-height:1.6; }
</style>
</head>
<body>
  <div class="card">
    <div class="hero">
      <h1>__TITLE__</h1>
      <p>__WHEN__</p>
    </div>
    <div class="body">
      <div class="rows">
        <div class="row"><span class="k">门店</span><span class="v">__STORE__</span></div>
        <div class="row"><span class="k">人数</span><span class="v">__SIZE__ 人</span></div>
        <div class="row"><span class="k">参考价</span><span class="v">__PRICE__</span></div>
      </div>
      <div class="why"><h2>选择理由</h2><ul>__REASONS__</ul></div>
      <div class="footer">__FOOTER__<br>独立开发作品，非麦当劳官方产品</div>
    </div>
  </div>
</body>
</html>
"""


def _guest_reasons(plan: Plan) -> List[str]:
    """At most two human-facing reasons for the invitation card.

    Falls back to a neutral guest-facing line - never to the internal scoring
    log, which is only meant for the CLI transcript.
    """
    keep: List[str] = []
    for reason in plan.reasons:
        if "周末场" in reason and len(keep) < 2:
            keep.append("周末场，亲友到场率最高")
        elif "下午场" in reason and len(keep) < 2:
            keep.append("下午场，小朋友不用请假")
        elif "傍晚场" in reason and len(keep) < 2:
            keep.append("傍晚场，下班后直接到店")
        elif "容量" in reason and "≥" in reason and len(keep) < 2 and plan.chosen:
            keep.append(f"场地可容纳 {plan.chosen.capacity} 人，够坐")
    return keep or ["按可约日期就近安排"]


def render_html(plan: Plan, live: bool = True) -> str:
    chosen = plan.chosen
    req = plan.request
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in _guest_reasons(plan))
    occasion = _occasion_label(plan)
    date_text = _fmt_date(chosen.date) if chosen else "-"
    time_text = f"{chosen.start} - {chosen.end}" if chosen else "-"
    when = f"{date_text} · {time_text}" if chosen else "-"
    page_title = f"{occasion} · {date_text} {chosen.start if chosen else ''}".strip(" ·")
    store_parts = [html.escape(plan.store.name)] if plan.store else ["-"]
    if plan.store and plan.store.address:
        store_parts.append(html.escape(plan.store.address))
    store_line = "<br>".join(store_parts)
    return (
        _HTML_TEMPLATE.replace("__PAGE_TITLE__", html.escape(page_title))
        .replace("__OG_DESC__", html.escape(f"{occasion}邀请 · {when} · {req.party_size} 人"))
        .replace("__TITLE__", html.escape(f"{occasion}邀请"))
        .replace("__WHEN__", html.escape(when))
        .replace("__STORE__", store_line)  # pre-escaped + <br>
        .replace("__SIZE__", html.escape(str(req.party_size)))
        .replace("__PRICE__", html.escape(_fmt_price(chosen.price) if chosen else "以官方页面为准"))
        .replace("__REASONS__", reasons)
        .replace("__FOOTER__", html.escape(FOOTER_LIVE if live else FOOTER_DEMO))
    )


def render(plan: Plan, fmt: str = "markdown", live: bool = True) -> str:
    if fmt == "json":
        return json.dumps(_plan_json(plan), ensure_ascii=False, indent=2)
    if fmt == "html":
        return render_html(plan, live=live)
    return render_markdown(plan, live=live)
