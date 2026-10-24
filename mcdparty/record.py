"""Record live MCP responses into fixture files.

Usage (requires a real token):

    MCD_MCP_TOKEN=xxx python -m mcdparty.record --out tests/fixtures

Walks the full party flow for a city (default 杭州) and writes one JSON file
per tools/call, named ``call__<tool>__<args-hash>.json``. The recorded
payloads are what the demo mode and the unit tests replay, so they stay
byte-for-byte honest to the real API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from .mcp_client import DEFAULT_URL, MCPClient
from .planner import PartyPlanner
from .models import PartyRequest


def _dump(path: Path, arguments: dict, payload) -> None:
    digest = hashlib.sha1(
        json.dumps(arguments, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:8]
    tool = path.name
    target = path / f"call__{tool}__{digest}.json"
    target.write_text(
        json.dumps({"arguments": arguments, "payload": payload}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"recorded {target.name}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="杭州")
    parser.add_argument("--out", default="tests/fixtures")
    parser.add_argument("--url", default=os.environ.get("MCD_MCP_URL", DEFAULT_URL))
    args = parser.parse_args(argv)

    token = os.environ.get("MCD_MCP_TOKEN", "")
    if not token:
        print("MCD_MCP_TOKEN is required", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    client = MCPClient(token, url=args.url)
    client.initialize()
    (out / "tools__list.json").write_text(
        json.dumps({"result": {"tools": client.list_tools()}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("recorded tools__list.json")

    plan = PartyPlanner(client).plan(PartyRequest(city=args.city))
    for entry in plan.tool_trace:
        _dump(out, entry["arguments"], entry["response"])
    print(f"done - {len(plan.tool_trace)} calls recorded for {args.city}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
