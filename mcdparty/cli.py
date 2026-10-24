"""Command line interface.

    mcdparty tools                     list MCP tools (proves live integration)
    mcdparty cities [--keyword 杭州]    list party cities
    mcdparty plan --city 杭州 ...       full flow + rendered plan (md/json/html)
    mcdparty book ... --confirm         create the order (dry-run without --confirm)
    mcdparty demo [--fixtures DIR]      offline replay, no network, no token

Auth comes from MCD_MCP_TOKEN (or --token). Nothing is ever written to disk
except an explicit -o output file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .mcp_client import DEFAULT_URL, MCPClient, MCPError
from .models import PartyRequest
from .planner import PartyPlanner
from .render import render
from .replay import ReplayTransport

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def _client(args) -> MCPClient:
    token = args.token or os.environ.get("MCD_MCP_TOKEN", "")
    url = args.url or os.environ.get("MCD_MCP_URL", DEFAULT_URL)
    if getattr(args, "demo", False):
        return MCPClient("demo-token", url=url, transport=ReplayTransport(args.fixtures or FIXTURES_DIR))
    return MCPClient(token, url=url, timeout=args.timeout)


def _emit(text: str, args, suffix: str = ".md") -> None:
    if getattr(args, "output", None):
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"written: {args.output}", file=sys.stderr)
    else:
        print(text)


def cmd_tools(args) -> int:
    client = _client(args)
    tools = client.list_tools()
    party = [t for t in tools if "party" in t.get("name", "")]
    print(f"共 {len(tools)} 个工具，其中派对相关 {len(party)} 个：")
    for tool in tools:
        mark = "★" if "party" in tool.get("name", "") else " "
        desc = (tool.get("description") or "").split("\n")[0][:60]
        print(f" {mark} {tool.get('name'):<28} {desc}")
    return 0


def cmd_cities(args) -> int:
    client = _client(args)
    payload = client.call_tool("query-party-city", {})
    from .models import City, as_list
    cities = [City.parse(c) for c in as_list(payload, "cities", "list", "data", "items")]
    if args.keyword:
        cities = [c for c in cities if args.keyword in c.name]
    for city in cities:
        print(f"{city.city_id:<12} {city.name}")
    print(f"-- {len(cities)} 个城市", file=sys.stderr)
    return 0


def cmd_plan(args) -> int:
    request = PartyRequest(
        city=args.city,
        occasion=args.occasion,
        date=args.date,
        party_size=args.size,
        budget=args.budget,
        prefer_weekend=not args.any_day,
    )
    client = _client(args)
    plan = PartyPlanner(client).plan(request)
    _emit(render(plan, args.format), args,
          suffix=".md" if args.format == "markdown" else f".{args.format}")
    return 0


def cmd_book(args) -> int:
    request = PartyRequest(city=args.city, party_size=args.size, date=args.date)
    client = _client(args)
    planner = PartyPlanner(client)
    plan = planner.plan(request)
    result = planner.book(plan, confirm=args.confirm, people=args.size)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.confirm:
        print("\n( dry-run：未真正下单。确认无误后加 --confirm 执行 )", file=sys.stderr)
    return 0


def cmd_demo(args) -> int:
    """Offline end-to-end replay - the transcript shown in the README."""
    args.demo = True
    request = PartyRequest(
        city=args.city, occasion=args.occasion, date=args.date,
        party_size=args.size, budget=args.budget,
    )
    client = _client(args)
    print(f"# 离线演示（fixtures: {args.fixtures or FIXTURES_DIR}）\n", file=sys.stderr)
    plan = PartyPlanner(client).plan(request)
    _emit(render(plan, args.format), args,
          suffix=".md" if args.format == "markdown" else f".{args.format}")
    trace = " -> ".join(t["tool"] for t in plan.tool_trace)
    print(f"\nMCP 调用链: {trace}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcdparty",
        description="麦麦派对策划师 - 基于麦当劳 MCP 的派对预订助手",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--token", help="MCP token (default: $MCD_MCP_TOKEN)")
    parser.add_argument("--url", default=DEFAULT_URL, help="MCP endpoint")
    parser.add_argument("--timeout", type=float, default=30.0)

    # shared by every subcommand: offline replay mode
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--demo", action="store_true",
                        help="离线回放模式：使用录制的 fixtures，无需 Token")
    common.add_argument("--fixtures", help="fixture 目录（默认 tests/fixtures）")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("tools", parents=[common], help="列出 MCP 工具")
    p.set_defaults(func=cmd_tools)

    p = sub.add_parser("cities", parents=[common], help="列出派对城市")
    p.add_argument("--keyword")
    p.set_defaults(func=cmd_cities)

    p = sub.add_parser("plan", parents=[common], help="生成派对策划案")
    p.add_argument("--city", default="杭州")
    p.add_argument("--occasion", default="birthday",
                   choices=["birthday", "team", "family", "tasting"])
    p.add_argument("--date", help="指定日期 YYYY-MM-DD（可选）")
    p.add_argument("--size", type=int, default=10)
    p.add_argument("--budget", type=float)
    p.add_argument("--any-day", action="store_true", help="不优先周末")
    p.add_argument("--format", default="markdown", choices=["markdown", "json", "html"])
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("book", parents=[common], help="预订（默认 dry-run）")
    p.add_argument("--city", default="杭州")
    p.add_argument("--date")
    p.add_argument("--size", type=int, default=10)
    p.add_argument("--confirm", action="store_true", help="真正调用 party-order-create")
    p.set_defaults(func=cmd_book)

    p = sub.add_parser("demo", parents=[common], help="离线回放演示（无需 Token）")
    p.add_argument("--city", default="杭州")
    p.add_argument("--occasion", default="birthday")
    p.add_argument("--date")
    p.add_argument("--size", type=int, default=10)
    p.add_argument("--budget", type=float)
    p.add_argument("--format", default="markdown", choices=["markdown", "json", "html"])
    p.set_defaults(func=cmd_demo)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except MCPError as exc:
        print(f"MCP 错误: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
