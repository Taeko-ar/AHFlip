import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ahflip import config, db, items, ledger, market, prices
from ahflip.deals import load_deals
from ahflip.gold import fmt


class Connect(unittest.TestCase):
    def test_session_uses_db_path_and_closes(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        with mock.patch.object(config, "DB_PATH", Path(d.name) / "t.db"):
            with db.session() as c:
                db.set_meta(c, "k", [1, 2])
            with self.assertRaises(sqlite3.ProgrammingError):
                c.execute("select 1")
            with db.session() as c:
                self.assertEqual(db.meta(c, "k"), [1, 2])

    def test_migrates_old_tables(self):
        c = sqlite3.connect(":memory:")
        self.addCleanup(c.close)
        c.executescript("""
            create table price(ts int, house int, item int, min int, qty int);
            create table ledger(id integer primary key, ts int, kind text, item int, qty int, price int, note text);
            insert into price values(1, 113, 7, 5, 1);
            insert into ledger values(1, 1, 'buy', 7, 1, 5, 'AHFlip'), (2, 1, 'buy', 7, 1, 5, 'mine');
        """)
        db.init(db.init(c))  # second run is a no-op
        self.assertEqual(c.execute("select src from price").fetchall(), [("api",)])
        self.assertEqual(c.execute("select src, note from ledger order by id").fetchall(), [("addon", ""), ("manual", "mine")])


class WithDB(unittest.TestCase):
    def setUp(self):
        self.c = db.init(sqlite3.connect(":memory:"))
        self.addCleanup(self.c.close)
        self.s = db.settings(self.c)

    def test_empty_db(self):
        self.assertIsNone(prices.latest(self.c, 113))
        self.assertEqual(load_deals(self.c, self.s), (None, []))
        m = market.load_market(self.c, self.s)
        self.assertEqual((m["ts"], m["rows"], m["counts"]["all"]), (None, [], 0))

    def test_flip_depth_and_min_profit(self):
        for t in (100, 200, 300):
            prices.store(self.c, 113, {1: (100 + t, 1)}, t, "addon")  # vary prices so the digest differs
        prices.store(self.c, 113, {1: (150, 7)}, 400, "addon")
        prices.store_depth(self.c, 113, 400, {1: [(150, 2), (160, 5), (230, 1)]})
        # usual 300, cut 5%: 285 - 150 = 135; 160 also under 75% (225), 230 is not
        d = load_deals(self.c, self.s)[1][0]
        self.assertEqual((d["kind"], d["profit"], d["units"], d["total"]), ("flip", 135, 7, 135 * 2 + 125 * 5))
        self.assertEqual(load_deals(self.c, {**self.s, "min_profit": 136})[1], [])

    def test_history(self):
        prices.store(self.c, 113, {1: (5, 2)}, 100)
        prices.store(self.c, 113, {1: (6, 3)}, 200, "scan")
        self.assertEqual(prices.history(self.c, 113, 1), [(100, 5, 2, "api"), (200, 6, 3, "scan")])

    def test_items_and_watchlist(self):
        items.save_info(self.c, [(1, "Linen Cloth", 13), (2, None, None)])
        self.assertEqual(items.known_ids(self.c), {1, 2})
        self.assertEqual(items.missing_ids(self.c), [2])
        items.fill_missing(self.c, [(1, "Other", 1), (2, "Light Leather", None), (3, "", 5)])
        self.assertEqual(items.info(self.c), ({1: "Linen Cloth", 2: "Light Leather"}, {1: 13, 2: None}))
        items.set_watch(self.c, 1, True)
        items.set_watch(self.c, 1, True)
        items.set_watch(self.c, 2, True)
        items.set_watch(self.c, 2, False)
        self.assertEqual(items.watched(self.c), {1})

    def test_ledger_validation_and_count(self):
        for kind, qty in (("trade", 1), ("buy", 0)):
            with self.assertRaises(ValueError):
                ledger.add(self.c, kind, "1", qty, "1c")
        ledger.add(self.c, "buy", "1", 1, "1c")
        self.assertEqual(ledger.count(self.c), 1)


class Gold(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(fmt(12005), "1g 20s 05c")
        self.assertEqual(fmt(0), "0g 00s 00c")
