"""Minimal MCP Streamable-HTTP client, standard library only.

Speaks JSON-RPC 2.0 over HTTP POST against ``https://mcp.mcd.cn``:
    initialize -> notifications/initialized -> tools/list -> tools/call

Handles both ``application/json`` and ``text/event-stream`` responses and
tracks the ``Mcp-Session-Id`` header exactly like the spec requires.

The HTTP layer is injectable (``transport``) so tests and the offline demo
mode can replay recorded responses without touching the network.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple

DEFAULT_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-03-26"

# transport(request_dict) -> (status_code, headers, body_bytes)
Transport = Callable[[Dict[str, Any]], Tuple[int, Dict[str, str], bytes]]


class MCPError(Exception):
    """Base error for MCP failures."""


class MCPAuthError(MCPError):
    """401 - token invalid, expired or missing."""


class MCPRateLimitError(MCPError):
    """429 - more than 600 requests / minute."""


class MCPToolError(MCPError):
    """Server answered with isError=true or an unusable payload."""

    def __init__(self, message: str, tool: str = "", payload: Any = None):
        super().__init__(message)
        self.tool = tool
        self.payload = payload


def _default_transport(url: str, token: str, timeout: float) -> Transport:
    def transport(request: Dict[str, Any]) -> Tuple[int, Dict[str, str], bytes]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + token,
        }
        headers.update(request.get("extra_headers", {}))
        body = json.dumps(
            {k: v for k, v in request.items() if k != "extra_headers"},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            raise _http_error(exc.code, raw) from exc
        except urllib.error.URLError as exc:
            raise MCPError(f"network unreachable: {exc.reason}") from exc

    return transport


def _http_error(status: int, raw: bytes) -> MCPError:
    detail = ""
    try:
        detail = json.loads(raw.decode("utf-8", "replace")).get("error", {}).get("message", "")
    except Exception:
        detail = raw.decode("utf-8", "replace")[:300]
    if status == 401:
        return MCPAuthError(f"401 unauthorized - check MCD_MCP_TOKEN ({detail})")
    if status == 429:
        return MCPRateLimitError("429 rate limited - keep under 600 req/min")
    return MCPError(f"HTTP {status}: {detail}")


def _parse_body(headers: Dict[str, str], raw: bytes) -> Dict[str, Any]:
    """Parse either a plain JSON body or an SSE stream, return the JSON-RPC message."""
    text = raw.decode("utf-8", "replace")
    content_type = headers.get("content-type", "")
    if "text/event-stream" in content_type or text.lstrip().startswith("event:"):
        data_lines = [
            line[len("data:"):].strip()
            for line in text.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            raise MCPError("empty SSE stream from MCP server")
        return json.loads("\n".join(data_lines))
    if not text.strip():
        raise MCPError("empty response body from MCP server")
    return json.loads(text)


class MCPClient:
    """Tiny synchronous MCP client for the McDonald's China server."""

    def __init__(
        self,
        token: str,
        url: str = DEFAULT_URL,
        timeout: float = 30.0,
        transport: Optional[Transport] = None,
    ):
        if not token:
            raise MCPAuthError("missing MCP token - set MCD_MCP_TOKEN")
        self.url = url
        self.token = token
        self.timeout = timeout
        self._transport = transport or _default_transport(url, token, timeout)
        self._session_id: Optional[str] = None
        self._next_id = 1
        self._initialized = False
        self._tools_cache: Optional[list] = None

    # ------------------------------------------------------------------ rpc
    def _rpc(self, method: str, params: Optional[Dict[str, Any]] = None,
             notify: bool = False) -> Optional[Dict[str, Any]]:
        request: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            request["params"] = params
        if not notify:
            request["id"] = self._next_id
            self._next_id += 1
        if self._session_id:
            request["extra_headers"] = {"Mcp-Session-Id": self._session_id}

        status, headers, raw = self._transport(request)
        if status >= 400:
            raise _http_error(status, raw)
        session = headers.get("mcp-session-id")
        if session:
            self._session_id = session
        if notify:
            return None
        message = _parse_body(headers, raw)
        if "error" in message:
            err = message["error"]
            raise MCPError(f"JSON-RPC error {err.get('code')}: {err.get('message')}")
        return message.get("result")

    # ------------------------------------------------------------- lifecycle
    def initialize(self) -> Dict[str, Any]:
        result = self._rpc("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mcd-party-planner", "version": "1.0.0"},
        })
        self._rpc("notifications/initialized", notify=True)
        self._initialized = True
        return result or {}

    def _ensure_init(self) -> None:
        if not self._initialized:
            self.initialize()

    # ----------------------------------------------------------------- tools
    def list_tools(self, refresh: bool = False) -> list:
        self._ensure_init()
        if self._tools_cache is None or refresh:
            result = self._rpc("tools/list") or {}
            self._tools_cache = result.get("tools", [])
        return self._tools_cache

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Call a tool and return its parsed payload (usually a JSON object/list)."""
        self._ensure_init()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}}) or {}
        if result.get("isError"):
            raise MCPToolError(f"tool {name} returned isError", tool=name, payload=result)
        return self._unwrap_content(result)

    @staticmethod
    def _unwrap_content(result: Dict[str, Any]) -> Any:
        content = result.get("content") or []
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        structured = result.get("structuredContent")
        if structured not in (None, {}):
            return structured
        for text in texts:
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                continue
        return texts[0] if len(texts) == 1 else {"content": texts, "raw": result}
