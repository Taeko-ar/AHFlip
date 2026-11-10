import contextlib
import io
import sqlite3
import unittest

from ahflip import db, items, market, prices


class Market(unittest.TestCase):
    def test_daily_lows(self):
        day = 86400
        self.assertEqual(market.daily_lows([(0, 50), (100, 40), (day, 60)], 30), [40, 60, 30])

    def test_views(self):
        c = db.init(sqlite3.connect(":memory:"))
        self.addCleanup(c.close)
        items.save_info(c, [(1, "Wool Cloth", 50), (2, "Copper Ore", 25), (3, "Peacebloom", 5)])
        for ts in (100, 200, 300):  # usual prices: wool 1000, ore 100, peacebloom 40
            prices.store(c, 113, {1: (1000 + ts, 5), 2: (100, 5), 3: (40 + ts % 3, 9)}, ts, "addon")
        prices.store(c, 113, {1: (600, 5), 2: (20, 5), 3: (60, 9)}, 400, "addon")
        s = db.settings(c)
        m = market.load_market(c, s, "below")
        self.assertEqual([r["item"] for r in m["rows"]], [2, 1])  # biggest drop first
        self.assertEqual(m["counts"], {"below": 2, "vendor": 1, "rising": 1, "all": 3})
        self.assertEqual(market.load_market(c, s, "vendor")["rows"][0]["item"], 2)
        self.assertEqual(market.load_market(c, s, "all", "peace")["rows"][0]["item"], 3)
        with self.assertRaises(ValueError):
            market.load_market(c, s, "nope")

    def test_unreliable_items_are_hidden(self):
        c = db.init(sqlite3.connect(":memory:"))
        self.addCleanup(c.close)
        # 1: one flask usually listed at 250g, now 1g (thin market). 2: price swung 1g..250g. 3: normal drop.
        for ts in (100, 200, 300):
            # item 3's price changes a little each time, or identical snapshots would be skipped
            snap = {1: (2_500_000, 1), 2: (10_000 if ts == 100 else 2_500_000, 9), 3: (100 + ts // 100, 9)}
            prices.store(c, 113, snap, ts, "addon")
        prices.store(c, 113, {1: (10_000, 1), 2: (10_000, 9), 3: (50, 9)}, 400, "addon")
        s = db.settings(c)
        m = market.load_market(c, s, "below")
        self.assertEqual(([r["item"] for r in m["rows"]], m["hidden"]), ([3], 2))
        loose = dict(s, min_listed=1, max_spread=1000)
        self.assertEqual(len(market.load_market(c, loose, "below")["rows"]), 3)

    def test_sold_auction_matched_by_name(self):
        from ahflip import ledger

        c = db.init(sqlite3.connect(":memory:"))
        self.addCleanup(c.close)
        items.save_info(c, [(2318, "Light Leather", 15)])
        rows = [((10, 1), "sell", 0, 20, 30, None, "Light Leather"), ((10, 2), "sell", 0, 1, 99, None, "Nope")]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(ledger.import_addon(c, rows), 1)
        self.assertIn("'Nope'", out.getvalue())
        e = ledger.summary(c)["entries"]
        self.assertEqual([(x["item"], x["qty"], x["price"]) for x in e], [(2318, 20, 30)])
        self.assertEqual(ledger.import_addon(c, rows), 0)  # watermark covers the skipped one too

    def test_goblin_house_has_its_own_cut(self):
        c = db.init(sqlite3.connect(":memory:"))
        self.addCleanup(c.close)
        s = db.settings(c)
        self.assertEqual(db.house_cut(s), 0.05)
        self.assertEqual(db.house_cut(dict(s, house=s["house_goblin"])), 0.15)
