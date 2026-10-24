"""Field access helpers + data models for the party flow.

The McDonald's MCP responses are not yet fully documented, so every accessor
here is defensive: it tries several plausible key names and degrades to None
instead of raising. Parsers are unit-tested against both the synthetic
fixtures and (later) real recorded responses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


def first(mapping: Any, *keys: str, default: Any = None) -> Any:
    """Return the first present, non-empty value among ``keys``."""
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        if key in mapping and mapping[key] not in (None, "", [], {}):
            return mapping[key]
    return default


def as_list(payload: Any, *keys: str) -> List[Any]:
    """Extract a list from a payload that may wrap it under common keys."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = as_list(value, *keys)
                if nested:
                    return nested
            if isinstance(value, str):
                try:
                    nested = as_list(json.loads(value), *keys)
                    if nested:
                        return nested
                except ValueError:
                    continue
        for value in payload.values():
            if isinstance(value, list) and value:
                return value
            if isinstance(value, dict):
                nested = as_list(value)
                if nested:
                    return nested
    if isinstance(payload, str):
        try:
            return as_list(json.loads(payload), *keys)
        except ValueError:
            return []
    return []


def as_dict(payload: Any, *keys: str) -> Dict[str, Any]:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        if not keys:
            return payload
    if isinstance(payload, str):
        try:
            return as_dict(json.loads(payload), *keys)
        except ValueError:
            return {}
    return {}


def as_text(value: Any) -> str:
    return "" if value is None else str(value)


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# models
# --------------------------------------------------------------------------

@dataclass
class City:
    city_id: str
    name: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: Dict[str, Any]) -> "City":
        return cls(
            city_id=as_text(first(raw, "cityId", "city_id", "id", "cityCode", default="")),
            name=as_text(first(raw, "cityName", "city_name", "name", "city", default="")),
            raw=raw,
        )


@dataclass
class Store:
    store_id: str
    name: str
    address: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: Dict[str, Any]) -> "Store":
        return cls(
            store_id=as_text(first(raw, "storeId", "store_id", "id", "storeCode", default="")),
            name=as_text(first(raw, "storeName", "store_name", "name", "storeName", default="")),
            address=as_text(first(raw, "address", "storeAddress", "addr", default="")),
            raw=raw,
        )


@dataclass
class PartyDate:
    date: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: Any) -> "PartyDate":
        if isinstance(raw, str):
            return cls(date=raw, raw={"date": raw})
        return cls(
            date=as_text(first(raw, "date", "day", "partyDate", "bookDate", default="")),
            raw=raw if isinstance(raw, dict) else {"date": raw},
        )


@dataclass
class Session:
    session_id: str
    date: str
    start: str
    end: str
    capacity: int
    price: float
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: Dict[str, Any]) -> "Session":
        return cls(
            session_id=as_text(first(raw, "sessionId", "session_id", "id", "slotId", default="")),
            date=as_text(first(raw, "date", "day", default="")),
            start=as_text(first(raw, "startTime", "start", "beginTime", "sessionStart", default="")),
            end=as_text(first(raw, "endTime", "end", "finishTime", "sessionEnd", default="")),
            capacity=to_int(first(raw, "capacity", "maxPeople", "maxNum", "stock", "remain", default=0)),
            price=to_float(first(raw, "price", "amount", "fee", "salePrice", default=0.0)),
            raw=raw,
        )


@dataclass
class PartyRequest:
    """What the host tells the planner."""

    city: str = "杭州"
    occasion: str = "birthday"     # birthday | team | family | tasting
    date: Optional[str] = None     # YYYY-MM-DD, optional
    party_size: int = 10
    budget: Optional[float] = None
    prefer_weekend: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "city": self.city,
            "occasion": self.occasion,
            "date": self.date,
            "party_size": self.party_size,
            "budget": self.budget,
        }


@dataclass
class Plan:
    """A fully-resolved party recommendation."""

    request: PartyRequest
    city: Optional[City] = None
    stores: List[Store] = field(default_factory=list)
    store: Optional[Store] = None
    dates: List[str] = field(default_factory=list)
    sessions: List[Session] = field(default_factory=list)
    chosen: Optional[Session] = None
    reasons: List[str] = field(default_factory=list)
    tool_trace: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request": self.request.as_dict(),
            "city": self.city.name if self.city else None,
            "store": self.store.name if self.store else None,
            "store_address": self.store.address if self.store else "",
            "dates": self.dates,
            "chosen_session": {
                "id": self.chosen.session_id,
                "date": self.chosen.date,
                "start": self.chosen.start,
                "end": self.chosen.end,
                "price": self.chosen.price,
            } if self.chosen else None,
            "reasons": self.reasons,
            # full request/response per call, so the JSON export is auditable
            "tool_trace": self.tool_trace,
        }
