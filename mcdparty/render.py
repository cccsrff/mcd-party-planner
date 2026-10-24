"""Render a PartyPlan as Markdown, JSON or a shareable HTML invitation."""

from __future__ import annotations

import datetime as _dt
import html
import json
from typing import Any, Dict

from .models import Plan

OCCASION_LABELS = {
    "birthday": "🎂 生日派对",
    "team": "💼 团队团建",
    "family": "👨‍👩‍👧 家庭聚会",
    "tasting": "🍔 品鉴会",
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


def _plan_json(plan: Plan) -> Dict[str, Any]:
    data = plan.to_dict()
    data["occasion_label"] = _occasion_label(plan)
    return data


def render_markdown(plan: Plan) -> str:
    req = plan.request
    chosen = plan.chosen
    lines = [
        f"# {_occasion_label(plan)} · 麦麦派对策划案",
        "",
        f"- 城市：**{plan.city.name if plan.city else '-'}**",
        f"- 门店：**{plan.store.name if plan.store else '-'}**{('（' + plan.store.address + '）') if plan.store and plan.store.address else ''}",
        f"- 日期：**{_fmt_date(chosen.date) if chosen else '-'}**",
        f"- 场次：**{(chosen.start + ' - ' + chosen.end) if chosen else '-'}**",
        f"- 人数：**{req.party_size} 人**",
    ]
    if chosen and chosen.price:
        lines.append(f"- 参考价：**¥{chosen.price:g} / 人**")
    lines += ["", "## 为什么选这一场", ""]
    lines += [f"- {reason}" for reason in plan.reasons] or ["- （无）"]
    if plan.dates:
        lines += ["", "## 其他可约日期", ", ".join(plan.dates[:10])]
    if plan.sessions:
        lines += ["", "## 当天全部场次", ""]
        lines += ["| 场次 | 时间 | 容量 | 参考价 |", "| --- | --- | --- | --- |"]
        for s in plan.sessions:
            mark = " ✅" if chosen and s.session_id == chosen.session_id else ""
            lines.append(
                f"| {s.start}{mark} | {s.start} - {s.end} | {s.capacity or '-'} | "
                f"{('¥%g' % s.price) if s.price else '-'} |"
            )
    lines += [
        "",
        "## 预订方式",
        "",
        "```bash",
        "mcdparty book --city %s --date %s --session %s --confirm" % (
            req.city, chosen.date if chosen else "", chosen.session_id if chosen else ""),
        "```",
        "",
        "> 由 麦麦派对策划师 基于麦当劳 MCP 实时数据生成；价格与库存以官方渠道为准。",
    ]
    return "\n".join(lines)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { --mcd-yellow:#FFC72C; --mcd-red:#DA291C; --ink:#2b2b2b; --paper:#fffdf5; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "PingFang SC","Microsoft YaHei",sans-serif; background: var(--paper);
         color: var(--ink); display:flex; justify-content:center; padding:32px 16px; }
  .card { width: 100%; max-width: 520px; background:#fff; border-radius:20px;
          border:3px solid var(--mcd-yellow); box-shadow:0 12px 32px rgba(218,41,28,.12);
          overflow:hidden; }
  .hero { background: linear-gradient(135deg,var(--mcd-yellow),#ffd95e); padding:28px 24px 20px; }
  .hero .tag { display:inline-block; background:var(--mcd-red); color:#fff; font-size:12px;
               padding:3px 10px; border-radius:999px; margin-bottom:10px; }
  .hero h1 { font-size:24px; }
  .hero p { margin-top:6px; font-size:13px; opacity:.75; }
  .body { padding:20px 24px 24px; }
  .row { display:flex; justify-content:space-between; padding:10px 0;
         border-bottom:1px dashed #eadfae; font-size:14px; }
  .row:last-of-type { border-bottom:none; }
  .row .k { color:#8a7c4e; }
  .row .v { font-weight:600; text-align:right; }
  .why { margin-top:14px; background:#fff8e1; border-radius:12px; padding:12px 14px; }
  .why h2 { font-size:13px; color:var(--mcd-red); margin-bottom:6px; }
  .why li { font-size:12.5px; margin-left:18px; margin-bottom:3px; }
  .footer { margin-top:16px; font-size:11px; color:#a89c78; text-align:center; line-height:1.6; }
  .arches { text-align:center; font-size:26px; margin-top:4px; }
</style>
</head>
<body>
  <div class="card">
    <div class="hero">
      <span class="tag">__OCCASION__</span>
      <h1>__TITLE__</h1>
      <p>__CITY__ · __STORE__</p>
    </div>
    <div class="body">
      <div class="row"><span class="k">📅 日期</span><span class="v">__DATE__</span></div>
      <div class="row"><span class="k">⏰ 场次</span><span class="v">__TIME__</span></div>
      <div class="row"><span class="k">👥 人数</span><span class="v">__SIZE__ 人</span></div>
      <div class="row"><span class="k">💰 参考价</span><span class="v">__PRICE__</span></div>
      <div class="why"><h2>为什么选这一场</h2><ul>__REASONS__</ul></div>
      <div class="arches">🍟🍔🥤</div>
      <div class="footer">由「麦麦派对策划师」基于麦当劳 MCP 实时数据生成<br>
      餐品、价格与供应状态以麦当劳官方渠道为准 · 本项目为独立开发作品，非麦当劳官方产品</div>
    </div>
  </div>
</body>
</html>
"""


def render_html(plan: Plan) -> str:
    chosen = plan.chosen
    req = plan.request
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in plan.reasons) or "<li>（无）</li>"
    return (
        _HTML_TEMPLATE.replace("__TITLE__", html.escape(_occasion_label(plan).split(" ", 1)[-1]))
        .replace("__OCCASION__", html.escape(_occasion_label(plan)))
        .replace("__CITY__", html.escape(plan.city.name if plan.city else "-"))
        .replace("__STORE__", html.escape(plan.store.name if plan.store else "-"))
        .replace("__DATE__", html.escape(_fmt_date(chosen.date) if chosen else "-"))
        .replace("__TIME__", html.escape(f"{chosen.start} - {chosen.end}" if chosen else "-"))
        .replace("__SIZE__", html.escape(str(req.party_size)))
        .replace("__PRICE__", html.escape(f"¥{chosen.price:g} / 人" if chosen and chosen.price else "以官方页面为准"))
        .replace("__REASONS__", reasons)
    )


def render(plan: Plan, fmt: str = "markdown") -> str:
    if fmt == "json":
        return json.dumps(_plan_json(plan), ensure_ascii=False, indent=2)
    if fmt == "html":
        return render_html(plan)
    return render_markdown(plan)
