import sqlite3
import unittest

from ahflip import db, items, ledger, prices
from ahflip.gold import parse_gold


class Gold(unittest.TestCase):
    def test_parse(self):
        for s, c in (("1g 20s 5c", 12005), ("45s", 4500), ("130", 130), ("2g", 20000), ("0g 04s 00c", 400)):
            self.assertEqual(parse_gold(s), c)
        for bad in ("", "abc", "-5s", "1x"):
            with self.assertRaises(ValueError):
                parse_gold(bad)


class WithDB(unittest.TestCase):
    def setUp(self):
        self.c = db.init(sqlite3.connect(":memory:"))
        items.save_info(self.c, [(1, "Linen Cloth", 13), (2, "Light Leather", 15)])

    def tearDown(self):
        self.c.close()

    def test_store_skips_duplicates_per_source(self):
        c = self.c
        self.assertTrue(prices.store(c, 113, {1: (5, 2)}, 100))
        self.assertFalse(prices.store(c, 113, {1: (5, 2)}, 200))
        self.assertTrue(prices.store(c, 113, {1: (5, 2)}, 250, "scan"))
        self.assertTrue(prices.store(c, 113, {1: (4, 2)}, 300))
        self.assertEqual(prices.count(c, 113), 3)
        self.assertEqual(prices.source(c, 113, 250), "scan")

    def test_flips_ignore_other_source_history(self):
        from ahflip.deals import load_deals

        c = self.c
        for ts in (100, 200, 300):  # stale API data at 20g
            prices.store(c, 113, {1: (200000, 2), 2: (ts, 1)}, ts, "api")
        prices.store(c, 113, {1: (50000, 2)}, 400, "scan")  # fresh scan at 5g
        self.assertEqual(load_deals(c, db.settings(c))[1], [])
        self.assertIsNone(prices.item_stats(c, db.settings(c), 1, 400)["median"])

    def test_current_snapshot_prefers_best_source(self):
        c = self.c
        prices.store(c, 113, {1: (400, 794)}, 300, "scan")  # newest, but Auctionator (can't see bids)
        prices.store(c, 113, {1: (600, 709)}, 200, "addon")  # AHFlip
        prices.store(c, 113, {1: (400, 851)}, 100, "api")
        self.assertEqual(prices.latest(c, 113), 200)

    def test_profitable_units_from_depth(self):
        from ahflip.deals import load_deals

        c = self.c
        items.save_info(c, [(3, "Pristine Hide", 250)])
        prices.store(c, 113, {3: (245, 4067)}, 500, "addon")
        prices.store_depth(c, 113, 500, {3: [(245, 11), (250, 100), (260, 3956)]})
        d = load_deals(c, db.settings(c))[1][0]
        self.assertEqual((d["kind"], d["profit"], d["units"], d["total"]), ("vendor", 5, 11, 55))

    def test_settings(self):
        s = db.save_settings(self.c, {"cut": "0.1", "min_profit": "50c"})
        self.assertEqual((s["min_profit"], db.settings(self.c)["cut"]), (50, 0.1))
        for bad in ({"cut": 2}, {"snap_minutes": 2}, {"nope": 1}):
            with self.assertRaises(ValueError):
                db.save_settings(self.c, bad)

    def test_resolve_item(self):
        self.assertEqual(items.resolve(self.c, "linen cloth"), 1)
        self.assertEqual(items.resolve(self.c, "77"), 77)
        with self.assertRaises(ValueError):
            items.resolve(self.c, "Nope")

    def test_ledger_import_from_addon(self):
        import tempfile

        from ahflip.sources import addon

        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as f:
            f.write(
                'AHFlipDB = {\n["ledger"] = {\n"1000.1:buy:4672:1:100:25:Ancestral Belt",\n'
                '"1000.2:sell:2:5:15::",\n},\n["probe"] = {\n"04:54:29 call PlaceBid 34061972 100",\n},\n}\n'
            )
        rows = addon.read_ledger(f.name)
        self.assertEqual(rows[0], ((1000, 1), "buy", 4672, 1, 100, 25, "Ancestral Belt"))
        self.assertEqual(ledger.import_addon(self.c, rows), 2)
        self.assertEqual(ledger.import_addon(self.c, rows), 0)  # watermark: no duplicates
        L = ledger.summary(self.c)
        self.assertEqual((L["spent"], L["earned"]), (100, 75))
        self.assertEqual(items.info(self.c)[0][4672], "Ancestral Belt")
        self.assertEqual({e["src"] for e in L["entries"]}, {"addon"})
        ledger.delete(self.c, L["entries"][0]["id"])
        self.assertEqual(ledger.import_addon(self.c, rows), 0)  # deleted entries stay deleted

    def test_ledger(self):
        ledger.add(self.c, "buy", "Linen Cloth", 10, "20c")
        ledger.add(self.c, "sell", "1", 4, "1s")
        L = ledger.summary(self.c)
        self.assertEqual((L["spent"], L["earned"], L["net"], L["items"][0]["held"]), (200, 400, 200, 6))
        e = L["entries"][-1]  # the buy
        ledger.edit(self.c, e["id"], "buy", "1", 8, "25c", "fixed")
        L = ledger.summary(self.c)
        self.assertEqual((L["spent"], L["entries"][-1]["note"], L["entries"][-1]["src"]), (200, "fixed", "manual"))
        with self.assertRaises(ValueError):
            ledger.edit(self.c, 999, "buy", "1", 1, "1c")
