"""CLI + rendering tests."""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from mcdparty import cli
from mcdparty.mcp_client import MCPClient
from mcdparty.models import PartyRequest
from mcdparty.planner import PartyPlanner
from mcdparty.render import render, render_html, render_markdown
from mcdparty.replay import ReplayTransport

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run_cli(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(argv)
    return code, buf.getvalue()


def make_plan():
    client = MCPClient("tok", transport=ReplayTransport(FIXTURES))
    return PartyPlanner(client).plan(PartyRequest(city="杭州", occasion="birthday", party_size=10))


class TestDemoCommand(unittest.TestCase):
    def test_demo_json(self):
        code, out = run_cli(["demo", "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["city"], "杭州")
        self.assertEqual(data["store"], "杭州湖滨餐厅")
        self.assertEqual(data["chosen_session"]["id"], "S102")
        self.assertEqual(len(data["tool_trace"]), 4)

    def test_demo_markdown(self):
        code, out = run_cli(["demo"])
        self.assertEqual(code, 0)
        self.assertIn("生日派对策划案", out)
        self.assertIn("14:00 - 16:00", out)
        self.assertIn("mcdparty book", out)

    def test_demo_html(self):
        code, out = run_cli(["demo", "--format", "html"])
        self.assertEqual(code, 0)
        self.assertIn("<!DOCTYPE html>", out)
        self.assertIn("杭州湖滨餐厅", out)

    def test_tools_demo_lists_party_tools(self):
        code, out = run_cli(["tools", "--demo"])
        self.assertEqual(code, 0)
        self.assertIn("共 33 个工具", out)
        self.assertIn("query-party-city", out)
        self.assertIn("party-order-create", out)

    def test_demo_missing_fixtures_fails_cleanly(self):
        code, _ = run_cli(["demo", "--fixtures", str(FIXTURES.parent / "nope")])
        self.assertEqual(code, 1)

    def test_demo_refuses_city_outside_fixtures(self):
        """Offline data covers Hangzhou only - say so instead of showing Hangzhou stores."""
        code, out = run_cli(["demo", "--city", "北京"])
        self.assertEqual(code, 1)
        self.assertNotIn("杭州湖滨餐厅", out)


class TestRendering(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan()

    def test_markdown_contains_core_fields(self):
        text = render_markdown(self.plan)
        for needle in ("杭州", "湖滨", "10 月 31 日", "S102", "选择理由"):
            self.assertIn(needle, text)

    def test_html_is_self_contained(self):
        html = render_html(self.plan)
        self.assertIn("<style>", html)
        self.assertNotIn("__TITLE__", html)  # all placeholders substituted
        self.assertIn("非麦当劳官方产品", html)

    def test_render_dispatch(self):
        self.assertIsInstance(json.loads(render(self.plan, "json")), dict)


if __name__ == "__main__":
    unittest.main()
