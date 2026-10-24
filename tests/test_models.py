"""Defensive parsing tests - the MCP schema is not documented, so every
accessor must survive shape variations instead of crashing."""

import unittest

from mcdparty.models import Session, Store, as_dict, as_list, first, to_float, to_int


class TestFirst(unittest.TestCase):
    def test_skips_empty_values(self):
        self.assertEqual(first({"a": "", "b": None, "c": 1}, "a", "b", "c"), 1)
        self.assertEqual(first({}, "x", default="d"), "d")
        self.assertEqual(first(None, "x", default=7), 7)


class TestAsList(unittest.TestCase):
    def test_bare_list(self):
        self.assertEqual(as_list([1, 2]), [1, 2])

    def test_wrapped_keys(self):
        self.assertEqual(as_list({"data": {"list": [3]}}, "data", "list"), [3])
        self.assertEqual(as_list({"items": [4]}, "items"), [4])

    def test_json_string_payload(self):
        self.assertEqual(as_list('{"list": [5]}', "list"), [5])

    def test_falls_back_to_any_list_value(self):
        self.assertEqual(as_list({"weird": [6]}), [6])

    def test_garbage_returns_empty(self):
        self.assertEqual(as_list("not json"), [])
        self.assertEqual(as_list(None), [])
        self.assertEqual(as_list({}), [])


class TestAsDict(unittest.TestCase):
    def test_nested(self):
        self.assertEqual(as_dict({"data": {"x": 1}}, "data"), {"x": 1})
        self.assertEqual(as_dict('{"y": 2}'), {"y": 2})
        self.assertEqual(as_dict("junk"), {})


class TestCoercion(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(to_int("12"), 12)
        self.assertEqual(to_int(None, default=5), 5)
        self.assertEqual(to_int("abc", default=9), 9)
        self.assertEqual(to_float("3.5"), 3.5)
        self.assertEqual(to_float("", default=1.5), 1.5)


class TestModelParsers(unittest.TestCase):
    def test_session_alternative_keys(self):
        session = Session.parse({
            "id": "X1", "day": "2026-11-01", "start": "14:00", "end": "16:00",
            "maxPeople": 20, "amount": "168",
        })
        self.assertEqual(session.session_id, "X1")
        self.assertEqual(session.date, "2026-11-01")
        self.assertEqual(session.start, "14:00")
        self.assertEqual(session.capacity, 20)
        self.assertEqual(session.price, 168.0)

    def test_store_alternative_keys(self):
        store = Store.parse({"id": "S1", "name": "测试餐厅", "addr": "某路 1 号"})
        self.assertEqual((store.store_id, store.name, store.address), ("S1", "测试餐厅", "某路 1 号"))


if __name__ == "__main__":
    unittest.main()
