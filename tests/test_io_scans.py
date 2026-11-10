import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ahflip import config, db, items, ledger, prices
from ahflip.sources import scans

ADDON = (
    'AHFlipDB = {{\n["time"] = {t},\n["items"] = "{items}",\n["ah"] = "goblin",\n'
    '["names"] = "2865:12:Elixir of Lesser Agility",\n'
    '["ledger"] = {{\n"1794290000.1:buy:2865:2:600:12:Elixir of Lesser Agility",\n}},\n}}\n'
)


class Scans(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        p = mock.patch.object(config, "DB_PATH", self.dir / "ah.db")
        p.start()
        self.addCleanup(p.stop)
        self.s = {
            **config.DEFAULTS,
            "addon_file": str(self.dir / "*" / "AHFlip.lua"),
            "scan_file": str(self.dir / "*" / "Auctionator.lua"),
        }
        self.out = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def addon_file(self, t=1794290042, items_="2865:725:600,3,610,722", sub="a"):
        f = self.dir / sub / "AHFlip.lua"
        f.parent.mkdir(exist_ok=True)
        f.write_text(ADDON.format(t=t, items=items_))
        return str(f)

    def test_addon_import(self):
        path = self.addon_file()
        msg = scans.import_one(self.s, "addon", path)
        self.assertRegex(msg, r"AHFlip scan \(goblin AH\) from \d\d:\d\d: 1 items saved")
        self.assertIn("AHFlip: 1 trades added to the ledger", self.out.getvalue())
        with db.session() as c:
            self.assertEqual(prices.latest(c, 116), 1794290042)
            self.assertEqual(prices.depth(c, 116, 1794290042), {2865: [(600, 3), (610, 722)]})
            self.assertEqual(ledger.count(c), 1)
            self.assertEqual(items.info(c)[0], {2865: "Elixir of Lesser Agility"})
            self.assertEqual(db.meta(c, "addon_mtime"), os.path.getmtime(path))
        self.assertIn("already imported", scans.import_one(self.s, "addon", path))  # no new trades either

    def test_v1_addon_without_depth_and_empty_scan(self):
        msg = scans.import_one(self.s, "addon", self.addon_file(items_="2865:600:725:610"))
        self.assertIn("1 items saved", msg)
        with db.session() as c:
            self.assertEqual(prices.depth(c, 116, 1794290042), {})
        msg = scans.import_one(self.s, "addon", self.addon_file(t=1794290099, items_=""))
        self.assertIn("0 items not saved (empty or unchanged)", msg)

    def test_auctionator_counts_as_horde(self):
        with mock.patch("ahflip.sources.auctionator.read_scan", return_value=(1794286387, {6309: (1700, 109)})) as r:
            msg = scans.import_one(self.s, "scan", self.addon_file())
        r.assert_called_once_with(self.addon_file(), "PvP")
        self.assertIn("Auctionator scan (horde AH)", msg)
        with db.session() as c:
            self.assertEqual(prices.latest(c, 113), 1794286387)
            self.assertEqual(scans.last_scan(c), 1794286387)

    def test_changed_mark_seen_found_files(self):
        with db.session() as c:
            self.assertIsNone(scans.last_scan(c))
        self.assertEqual(scans.changed(self.s), [])
        self.assertIsNone(scans.newest(self.s["addon_file"]))
        old = self.addon_file(sub="a")
        new = self.addon_file(sub="b")
        os.utime(old, (1, 1))
        self.assertEqual(scans.found_files(self.s), {"AHFlip scan": new, "Auctionator scan": None})
        self.assertEqual(scans.changed(self.s), [("addon", new)])
        scans.mark_seen("addon", new)
        self.assertEqual(scans.changed(self.s), [])
