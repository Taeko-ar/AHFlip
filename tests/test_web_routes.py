import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ahflip import db, items, ledger, prices
from ahflip.web import jobs, routes


class Routes(unittest.TestCase):
    def setUp(self):
        self.c = db.init(sqlite3.connect(":memory:"))
        self.addCleanup(self.c.close)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # scan file globs point at nothing, so status never looks at the real WoW folder
        db.save_settings(self.c, {"addon_file": str(Path(tmp.name) / "a*.lua"), "scan_file": str(Path(tmp.name) / "s*.lua")})
        self.addCleanup(jobs.STATE.update, {"job": None, "error": None, "last": None})
        p = mock.patch.object(routes.blizzard, "configured", return_value=True)  # never reads the real .env
        self.api = p.start()
        self.addCleanup(p.stop)

    def seed(self):
        items.save_info(self.c, [(1, "Wool Cloth", 50), (2, "Copper Ore", 25)])
        for ts in (100, 200, 300):
            prices.store(self.c, 113, {1: (1000 + ts, 5), 2: (100, 5)}, ts, "addon")
        prices.store(self.c, 113, {1: (600, 5), 2: (20, 5)}, 400, "addon")

    def test_status(self):
        r = routes.status(self.c, {})
        self.assertIsNone(r["latest"])
        self.assertEqual(r["next"], 600)  # no attempt yet: 0 + 10 min
        self.assertEqual(r["houses"], {"horde": 113, "goblin": 116})
        self.assertEqual((r["api"], r["setup_done"]), (True, True))
        self.seed()
        db.save_settings(self.c, {"snap_minutes": 0})
        r = routes.status(self.c, {})
        self.assertEqual((r["latest"], r["attempt"], r["snaps"], r["next"]), (400, 400, 4, None))

    def test_market_history_watch(self):
        self.seed()
        self.assertEqual(routes.watch_set(self.c, {"item": "wool cloth"}), {"item": 1, "on": True})
        m = routes.market(self.c, {})
        self.assertEqual((m["watch"], m["cut"]), ([1], 0.05))
        self.assertEqual(routes.market(self.c, {"view": "all", "q": "ore"})["rows"][0]["item"], 2)
        ledger.add(self.c, "buy", 1, 5, 100)
        ledger.add(self.c, "sell", 1, 2, 200)
        ledger.add(self.c, "buy", 2, 1, 10)
        h = routes.history(self.c, {"item": "1"})
        self.assertEqual((h["held"], h["watched"], h["min"], len(h["points"]), len(h["trades"])), (3, True, 600, 4, 2))
        self.assertEqual(routes.watch(self.c, {})["items"][0]["item"], 1)
        self.assertEqual(routes.watch_set(self.c, {"item": 1, "on": 0}), {"item": 1, "on": False})
        self.assertEqual(routes.watch(self.c, {}), {"items": []})
        with self.assertRaises(KeyError):
            routes.history(self.c, {})

    def test_ledger(self):
        self.assertEqual(routes.ledger_get(self.c, {})["now"], {})  # no snapshot yet
        routes.ledger_set(self.c, {"kind": "buy", "item": 3, "qty": 1, "price": 5})  # unknown item, no price
        self.assertEqual(routes.ledger_get(self.c, {})["now"], {3: {"min": None, "sell": None}})
        self.seed()
        self.assertEqual(routes.ledger_set(self.c, {"kind": "buy", "item": 1, "qty": 2, "price": 100, "note": "x"}), {"ok": True})
        L = routes.ledger_get(self.c, {})
        self.assertEqual(L["now"][1], {"min": 600, "sell": 50})
        self.assertEqual(L["cut"], 0.05)
        eid = next(e["id"] for e in L["entries"] if e["item"] == 1)
        routes.ledger_set(self.c, {"edit": eid, "kind": "sell", "item": 2, "qty": 1, "price": 7})
        self.assertEqual({e["item"] for e in routes.ledger_get(self.c, {})["entries"]}, {2, 3})
        routes.ledger_set(self.c, {"delete": eid})
        self.assertEqual(ledger.count(self.c), 1)

    def test_settings(self):
        self.assertEqual(routes.settings_get(self.c, {})["cut"], 0.05)
        self.assertEqual(routes.settings_set(self.c, {"cut": 0.1})["cut"], 0.1)
        with self.assertRaises(ValueError):
            routes.settings_set(self.c, {"bogus": 1})

    def test_snap_retry(self):
        with mock.patch.object(jobs, "start_snapshot", return_value=True) as snap:
            self.assertEqual(routes.snap(self.c, {}), {"started": True, "job": None})
        self.assertEqual(snap.call_args[0][0]["house"], 113)
        jobs.STATE["job"] = "snapshot"
        with mock.patch.object(jobs, "start_retry", return_value=False):
            self.assertEqual(routes.retry(self.c, {}), {"started": False, "job": "snapshot"})
        self.api.return_value = False
        for fn in (routes.snap, routes.retry):
            with self.assertRaisesRegex(ValueError, "No Battle.net API keys"):
                fn(self.c, {})

    def test_setup(self):
        self.assertTrue(routes.setup_get(self.c, {})["api"])
        r = routes.setup_set(self.c, {"rs": "3"})
        self.assertEqual((r["done"], r["rs"]), (True, 3))
        with self.assertRaises(KeyError):
            routes.setup_set(self.c, {})

    def test_routes_table(self):
        self.assertIs(routes.ROUTES[("GET", "/api/status")], routes.status)
        self.assertIs(routes.ROUTES[("GET", "/api/setup")], routes.setup_get)
        self.assertIs(routes.ROUTES[("POST", "/api/setup")], routes.setup_set)
        self.assertEqual(len(routes.ROUTES), 13)


if __name__ == "__main__":
    unittest.main()
