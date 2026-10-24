"""MCP client protocol tests - fake transport, no network."""

import json
import unittest

from mcdparty.mcp_client import (
    MCPAuthError,
    MCPClient,
    MCPError,
    MCPRateLimitError,
    MCPToolError,
)


def json_body(result, status=200, headers=None):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode()
    return status, {"content-type": "application/json", **(headers or {})}, body


def sse_body(result):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}, ensure_ascii=False)
    text = f"event: message\ndata: {payload}\n\n"
    return 200, {"content-type": "text/event-stream"}, text.encode()


class FakeTransport:
    """Records requests, replies from a scripted queue or a handler."""

    def __init__(self, handler):
        self.handler = handler
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.handler(request)


class TestHandshake(unittest.TestCase):
    def test_initialize_then_notification_and_session_id(self):
        seen = []

        def handler(request):
            seen.append(request["method"])
            if request["method"] == "initialize":
                return json_body({"ok": True}, headers={"mcp-session-id": "sess-42"})
            if request["method"] == "notifications/initialized":
                return 202, {}, b""
            return json_body({"tools": []})

        client = MCPClient("tok", transport=FakeTransport(handler))
        client.initialize()
        self.assertEqual(seen, ["initialize", "notifications/initialized"])
        # session id must ride along on every later request
        client.list_tools()
        self.assertEqual(client._session_id, "sess-42")
        last = client._transport.requests[-1]
        self.assertEqual(last["extra_headers"]["Mcp-Session-Id"], "sess-42")

    def test_tools_call_unwraps_text_json(self):
        def handler(request):
            if request["method"] == "initialize":
                return json_body({})
            if request["method"] == "notifications/initialized":
                return 202, {}, b""
            return json_body({"content": [{"type": "text", "text": '{"a": 1}'}],
                              "isError": False})

        client = MCPClient("tok", transport=FakeTransport(handler))
        self.assertEqual(client.call_tool("x"), {"a": 1})

    def test_tools_call_prefers_structured_content(self):
        def handler(request):
            if request["method"] == "initialize":
                return json_body({})
            if request["method"] == "notifications/initialized":
                return 202, {}, b""
            return json_body({"content": [{"type": "text", "text": "raw"}],
                              "structuredContent": {"b": 2}})

        client = MCPClient("tok", transport=FakeTransport(handler))
        self.assertEqual(client.call_tool("x"), {"b": 2})

    def test_is_error_raises_tool_error(self):
        def handler(request):
            if request["method"] == "initialize":
                return json_body({})
            if request["method"] == "notifications/initialized":
                return 202, {}, b""
            return json_body({"content": [{"type": "text", "text": "boom"}], "isError": True})

        client = MCPClient("tok", transport=FakeTransport(handler))
        with self.assertRaises(MCPToolError):
            client.call_tool("x")


class TestTransportFailures(unittest.TestCase):
    def test_401_maps_to_auth_error(self):
        def handler(request):
            return 401, {"content-type": "application/json"}, b'{"error": {"message": "bad token"}}'

        client = MCPClient("tok", transport=FakeTransport(handler))
        with self.assertRaises(MCPAuthError):
            client.initialize()

    def test_429_maps_to_rate_limit(self):
        def handler(request):
            if request["method"] == "initialize":
                return json_body({})
            return 429, {}, b""

        client = MCPClient("tok", transport=FakeTransport(handler))
        with self.assertRaises(MCPRateLimitError):
            client.list_tools()

    def test_missing_token_rejected_early(self):
        with self.assertRaises(MCPAuthError):
            MCPClient("")

    def test_sse_stream_is_parsed(self):
        def handler(request):
            if request["method"] == "initialize":
                return sse_body({"ok": True})
            if request["method"] == "notifications/initialized":
                return 202, {}, b""
            return sse_body({"content": [{"type": "text", "text": "{\"v\": 7}"}]})

        client = MCPClient("tok", transport=FakeTransport(handler))
        client.initialize()
        self.assertEqual(client.call_tool("x"), {"v": 7})


if __name__ == "__main__":
    unittest.main()
