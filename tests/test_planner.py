"""Planner decision tests - replay recorded fixtures, no network."""

import unittest
from pathlib import Path

from mcdparty.mcp_client import MCPClient
from mcdparty.models import PartyRequest
from mcdparty.planner import PartyPlanner
from mcdparty.replay import ReplayTransport

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def make_planner():
    client = MCPClient("tok", transport=ReplayTransport(FIXTURES))
    return PartyPlanner(client), client


class TestPlanFlow(unittest.TestCase):
    def test_birthday_plan_end_to_end(self):
        planner, client = make_planner()
        plan = planner.plan(PartyRequest(city="杭州", occasion="birthday", party_size=10))

        self.assertEqual(plan.city.name, "杭州")
        self.assertEqual(plan.store.name, "杭州湖滨餐厅")
        self.assertEqual(len(plan.dates), 5)
        # Saturday 2026-10-31 is the first weekend slot
        self.assertEqual(plan.chosen.date, "2026-10-31")
        # 14:00-16:00 wins: weekend +3, afternoon +2, capacity 20 >= 10 +2
        self.assertEqual(plan.chosen.session_id, "S102")
        self.assertEqual(plan.chosen.start, "14:00")
        # exactly 4 MCP calls, in order
        self.assertEqual(
            [t["tool"] for t in plan.tool_trace],
            ["query-party-city", "query-party-store",
             "query-partystore-date", "query-partystore-session"],
        )
        joined = " ".join(plan.reasons)
        self.assertIn("周末", joined)
        self.assertIn("容量 20", joined)

    def test_capacity_too_small_never_wins(self):
        planner, _ = make_planner()
        plan = planner.plan(PartyRequest(city="杭州", occasion="birthday", party_size=10))
        # S101 has capacity 8 < 10, must not be chosen even though it's cheapest-slot
        self.assertNotEqual(plan.chosen.session_id, "S101")

    def test_explicit_date_is_honoured(self):
        planner, _ = make_planner()
        plan = planner.plan(PartyRequest(city="杭州", date="2026-11-08", party_size=10))
        self.assertEqual(plan.chosen.date, "2026-11-08")

    def test_team_occasion_prefers_evening(self):
        planner, _ = make_planner()
        plan = planner.plan(PartyRequest(city="杭州", occasion="team", party_size=10))
        # team: evening slot 18:30-20:30 beats the kid-friendly afternoon slot
        self.assertEqual(plan.chosen.session_id, "S103")

    def test_unknown_city_is_rejected_not_swapped(self):
        """Never plan a party in a city the user did not ask for."""
        planner, _ = make_planner()
        with self.assertRaises(RuntimeError) as ctx:
            planner.plan(PartyRequest(city="拉萨", occasion="birthday"))
        self.assertIn("不在可办派对的城市列表", str(ctx.exception))
        self.assertIn("杭州", str(ctx.exception))

    def test_book_is_dry_run_by_default(self):
        planner, _ = make_planner()
        plan = planner.plan(PartyRequest(city="杭州", party_size=10))
        result = planner.book(plan, confirm=False)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["would_call"], "party-order-create")
        self.assertEqual(result["arguments"]["sessionId"], "S102")
        # no order call leaked into the trace
        self.assertNotIn("party-order-create", [t["tool"] for t in plan.tool_trace])

    def test_budget_penalty(self):
        planner, _ = make_planner()
        # ¥100 budget: every session exceeds it, the afternoon slot still wins
        plan = planner.plan(PartyRequest(city="杭州", party_size=10, budget=100))
        self.assertTrue(any("超预算" in r for r in plan.reasons))

    def test_strict_date_refuses_to_reschedule(self):
        """Booking path must never silently move to another date."""
        planner, _ = make_planner()
        with self.assertRaises(RuntimeError) as ctx:
            planner.plan(PartyRequest(city="杭州", date="2026-11-02"),
                         strict_date=True)
        self.assertIn("不可约", str(ctx.exception))
        self.assertIn("未做任何改期", str(ctx.exception))

    def test_pin_session_skips_scoring(self):
        """What the user reviewed is what gets ordered."""
        planner, _ = make_planner()
        plan = planner.plan(PartyRequest(city="杭州", occasion="birthday"), pin_session="S103")
        self.assertEqual(plan.chosen.session_id, "S103")
        self.assertTrue(any("未参与自动评分" in r for r in plan.reasons))

    def test_pin_unknown_session_fails(self):
        planner, _ = make_planner()
        with self.assertRaises(RuntimeError):
            planner.plan(PartyRequest(city="杭州"), pin_session="NOPE")


if __name__ == "__main__":
    unittest.main()
