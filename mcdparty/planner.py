"""The party planner: chains the 5 McDonald's party MCP tools into a decision.

    query-party-city        -> match the city (no silent fallback)
    query-party-store       -> first store in the list (no distance/rating sort yet)
    query-partystore-date   -> nearest weekend when possible
    query-partystore-session-> scored slot (afternoon-biased for kids)
    party-order-create      -> optional booking, guarded behind --confirm

Only the session step is scored; store and date are simple heuristics, and the
reason strings say so. Every raw MCP payload is kept in ``plan.tool_trace``.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

from .mcp_client import MCPClient
from .models import (
    City,
    PartyDate,
    PartyRequest,
    Plan,
    Session,
    Store,
    as_list,
    first,
    to_float,
    to_int,
)

WEEKEND = {5, 6}  # Saturday=5, Sunday=6 in .weekday()

AFTERNOON_HINTS = ("14", "15", "16", "17")
EVENING_HINTS = ("18", "19", "20")


class PartyPlanner:
    def __init__(self, client: MCPClient):
        self.client = client

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _trace(plan: Plan, tool: str, arguments: Dict[str, Any], payload: Any) -> None:
        plan.tool_trace.append({"tool": tool, "arguments": arguments, "response": payload})

    @staticmethod
    def _weekday(date_str: str) -> Optional[int]:
        try:
            return _dt.date.fromisoformat(date_str[:10]).weekday()
        except ValueError:
            return None

    # ----------------------------------------------------------------- step 1
    def resolve_city(self, request: PartyRequest, plan: Plan) -> City:
        payload = self.client.call_tool("query-party-city", {})
        self._trace(plan, "query-party-city", {}, payload)
        cities = [City.parse(item) for item in as_list(payload, "cities", "list", "data", "items")]
        cities = [c for c in cities if c.name]
        if not cities:
            raise RuntimeError("query-party-city returned no cities")
        keyword = (request.city or "").strip()
        for city in cities:
            if keyword and (keyword in city.name or city.name in keyword):
                return city
        raise RuntimeError(
            f"「{keyword or '（空）'}」不在可办派对的城市列表里，不会替你改到别的城市。"
            f"可选：{'、'.join(c.name for c in cities[:8])}"
            f"{' 等' if len(cities) > 8 else ''}（共 {len(cities)} 城）"
        )

    # ----------------------------------------------------------------- step 2
    def resolve_store(self, city: City, request: PartyRequest, plan: Plan) -> Store:
        args: Dict[str, Any] = {"cityId": city.city_id} if city.city_id else {"city": city.name}
        payload = self.client.call_tool("query-party-store", args)
        self._trace(plan, "query-party-store", args, payload)
        stores = [Store.parse(item) for item in as_list(payload, "stores", "list", "data", "items")]
        stores = [s for s in stores if s.store_id]
        if not stores:
            raise RuntimeError(f"query-party-store returned no stores for {city.name}")
        plan.stores = stores
        store = stores[0]
        plan.reasons.append(
            f"门店取列表首家「{store.name}」（当前未按距离或评分排序，{len(stores)} 家可选）"
        )
        return store

    # ----------------------------------------------------------------- step 3
    def resolve_dates(self, store: Store, request: PartyRequest, plan: Plan) -> List[str]:
        args = {"storeId": store.store_id} if store.store_id else {"store": store.name}
        payload = self.client.call_tool("query-partystore-date", args)
        self._trace(plan, "query-partystore-date", args, payload)
        dates = [PartyDate.parse(item).date for item in as_list(payload, "dates", "list", "data", "items")]
        dates = sorted({d for d in dates if d})
        if not dates:
            raise RuntimeError(f"query-partystore-date returned no dates for {store.name}")
        plan.dates = dates
        return dates

    # ----------------------------------------------------------------- step 4
    def resolve_sessions(self, store: Store, date: str, plan: Plan) -> List[Session]:
        args = {"storeId": store.store_id, "date": date}
        payload = self.client.call_tool("query-partystore-session", args)
        self._trace(plan, "query-partystore-session", args, payload)
        sessions = [Session.parse(item) for item in as_list(payload, "sessions", "list", "data", "items")]
        sessions = [s for s in sessions if s.session_id]
        if not sessions:
            raise RuntimeError(f"query-partystore-session returned no slots for {date}")
        for session in sessions:
            session.date = session.date or date
        plan.sessions = sessions
        return sessions

    # ------------------------------------------------------------- scoring
    def score_session(self, session: Session, request: PartyRequest) -> tuple[int, List[str]]:
        score, why = 0, []
        weekday = self._weekday(session.date)
        if weekday is not None:
            if weekday in WEEKEND:
                score += 3
                why.append("周末场，亲友到场率最高")
            elif request.prefer_weekend:
                why.append("工作日场（备选）")
        start = (session.start or "")[:5]
        hour = start[:2]
        if request.occasion in ("birthday", "family") and hour in AFTERNOON_HINTS:
            score += 2
            why.append("下午场，适合小朋友作息")
        elif request.occasion == "team" and hour in EVENING_HINTS:
            score += 2
            why.append("傍晚场，方便下班后团建")
        if session.capacity and request.party_size:
            if session.capacity >= request.party_size:
                score += 2
                why.append(f"容量 {session.capacity} 人 ≥ 预计 {request.party_size} 人")
            else:
                score -= 5
                why.append(f"容量 {session.capacity} 人 < 预计 {request.party_size} 人，不推荐")
        if request.budget and session.price:
            if session.price <= request.budget:
                score += 1
                why.append(f"人均 ¥{session.price:g} 在预算内")
            else:
                score -= 3
                why.append(f"人均 ¥{session.price:g} 超预算 ¥{request.budget:g}")
        return score, why

    def choose_session(self, request: PartyRequest, plan: Plan) -> Session:
        scored = []
        for session in plan.sessions:
            score, why = self.score_session(session, request)
            scored.append((score, session, why))
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best, why = scored[0]
        plan.chosen = best
        plan.reasons.extend(why)
        runner_up = scored[1][1] if len(scored) > 1 else None
        if runner_up is not None and scored[1][0] == best_score:
            plan.reasons.append(f"与 {runner_up.start} 场并列首选，可作备选")
        return best

    # ------------------------------------------------------------------ flow
    def plan(self, request: PartyRequest, pin_session: str = "",
             strict_date: bool = False) -> Plan:
        """Resolve a full plan.

        ``strict_date``: when the caller named a date that is not bookable,
        fail loudly instead of silently moving to another date (booking path).
        ``pin_session``: book exactly this slot, skipping the scoring step
        (so what the user reviewed is what gets ordered).
        """
        plan = Plan(request=request)
        plan.city = self.resolve_city(request, plan)
        plan.store = self.resolve_store(plan.city, request, plan)
        dates = self.resolve_dates(plan.store, request, plan)

        target = request.date if request.date in dates else self._pick_date(dates, request, plan)
        if strict_date and request.date and request.date not in dates:
            raise RuntimeError(
                f"{request.date} 不可约；可约日期：{', '.join(dates[:6])}。"
                "未做任何改期，也未下单。"
            )
        sessions = self.resolve_sessions(plan.store, target, plan)
        if pin_session:
            pinned = [s for s in sessions if s.session_id == pin_session]
            if not pinned:
                raise RuntimeError(
                    f"场次 {pin_session} 在 {target} 不存在；可选："
                    + ", ".join(s.session_id for s in sessions)
                )
            plan.chosen = pinned[0]
            plan.reasons.append(f"按指定场次 {pin_session} 预订，未参与自动评分")
            return plan
        self.choose_session(request, plan)
        return plan

    def _pick_date(self, dates: List[str], request: PartyRequest, plan: Plan) -> str:
        if request.date:
            plan.reasons.append(f"指定日期 {request.date} 不可约，已自动改选")
        weekend = [d for d in dates if (self._weekday(d) or -1) in WEEKEND]
        if request.prefer_weekend and weekend:
            if len(weekend) == len(dates):
                tail = f"共 {len(dates)} 天可约，全部是周末"
            else:
                tail = f"{len(weekend)} 天周末可约，共 {len(dates)} 天可选"
            plan.reasons.append(f"自动选定最近周末 {weekend[0]}（{tail}）")
            return weekend[0]
        plan.reasons.append(f"自动选定最近可约日期 {dates[0]}（共 {len(dates)} 天可选）")
        return dates[0]

    # --------------------------------------------------------------- booking
    def book(self, plan: Plan, confirm: bool = False, people: Optional[int] = None) -> Dict[str, Any]:
        """Create the party order. Dry-run unless ``confirm=True``."""
        session = plan.chosen
        if session is None:
            raise RuntimeError("no session chosen - run plan() first")
        args = {
            "storeId": plan.store.store_id if plan.store else "",
            "date": session.date,
            "sessionId": session.session_id,
            "people": people or plan.request.party_size,
        }
        if not confirm:
            return {"dry_run": True, "would_call": "party-order-create", "arguments": args}
        payload = self.client.call_tool("party-order-create", args)
        self._trace(plan, "party-order-create", args, payload)
        return payload
