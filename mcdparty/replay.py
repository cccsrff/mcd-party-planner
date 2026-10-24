"""Offline replay transport: serve recorded MCP responses from disk.

Powers two things:
  * ``mcdparty demo`` - run the whole planning flow with zero network, so the
    README can show a real transcript and CI tests never touch the API.
  * unit tests - inject the transport into MCPClient.

Recording format (one JSON file per interaction)::

    fixtures/call__query-party-city.json        {"result": {...}}
    fixtures/call__query-party-store__ab12.json {"arguments": {...}, "result": {...}}

``record.py`` writes these files verbatim from live MCP responses.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .mcp_client import Transport

INIT_RESULT = {
    "protocolVersion": "2025-03-26",
    "capabilities": {"tools": {"listChanged": False}},
    "serverInfo": {"name": "mcd-mcp", "version": "1.0.9"},
}


def _envelope(result: Any) -> Tuple[int, Dict[str, str], bytes]:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}, ensure_ascii=False)
    return 200, {"content-type": "application/json"}, body.encode("utf-8")


def _tool_envelope(payload: Any) -> Tuple[int, Dict[str, str], bytes]:
    """Wrap a business payload the way a real tools/call result looks."""
    result = {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": False,
    }
    return _envelope(result)


class ReplayTransport:
    """Transport backed by recorded fixture files. Raises on unknown calls."""

    def __init__(self, fixtures_dir: str | Path):
        self.dir = Path(fixtures_dir)
        self.calls: List[Dict[str, Any]] = []  # audit trail for tests/demo

    def _load(self, name: str) -> Optional[Dict[str, Any]]:
        path = self.dir / f"{name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def __call__(self, request: Dict[str, Any]) -> Tuple[int, Dict[str, str], bytes]:
        method = request.get("method")
        params = request.get("params") or {}
        self.calls.append({"method": method, "params": params})

        if method == "initialize":
            return _envelope(INIT_RESULT)
        if method == "notifications/initialized":
            return 202, {"content-type": "application/json"}, b""
        if method == "tools/list":
            fixture = self._load("tools__list")
            if fixture is None:
                raise FileNotFoundError(f"missing fixture tools__list.json in {self.dir}")
            return _envelope(fixture.get("result", fixture) if isinstance(fixture, dict) else fixture)

        if method == "tools/call":
            tool = params.get("name", "")
            args = params.get("arguments") or {}
            digest = hashlib.sha1(
                json.dumps(args, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()[:8]
            fixture = self._load(f"call__{tool}__{digest}") or self._load(f"call__{tool}")
            if fixture is None:
                raise FileNotFoundError(
                    f"missing fixture call__{tool}.json in {self.dir} "
                    f"(args: {json.dumps(args, ensure_ascii=False)})"
                )
            payload = fixture.get("payload", fixture.get("result", fixture))
            return _tool_envelope(payload)

        raise ValueError(f"replay transport cannot handle method {method!r}")


def as_transport(fixtures_dir: str | Path) -> Transport:
    return ReplayTransport(fixtures_dir)
