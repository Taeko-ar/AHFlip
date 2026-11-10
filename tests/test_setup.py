import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ahflip import config, db, setup


def saved(faction=None, realm=None):
    lines = ["AHFlipDB = {"]
    if faction:
        lines.append(f'["faction"] = "{faction}",')
    if realm is not None:
        lines.append(f'["realm"] = "{realm}",')
    return "\n".join(lines + ["}"])


class Detect(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.f = Path(d.name) / "AHFlip.lua"

    def detect(self, text):
        self.f.write_text(text)
        return setup.detect(self.f)

    def test_empty_path(self):
        self.assertEqual(setup.detect(None), {})
        self.assertEqual(setup.detect(""), {})

    def test_faction_and_ruleset(self):
        self.assertEqual(self.detect(saved("Horde", "CAMWOW US2 Realm 6 PvP")), {"faction": "horde", "rs": 1})
        self.assertEqual(self.detect(saved("Alliance", "Some RP-PvP realm")), {"faction": "alliance", "rs": 15})
        self.assertEqual(self.detect(saved(realm="Roleplay Realm")), {"rs": 3})
        self.assertEqual(self.detect(saved(realm="Normal 1")), {"rs": 2})
        self.assertEqual(self.detect(saved("Goblin")), {})  # neither key recognised


class State(unittest.TestCase):
    def setUp(self):
        self.c = db.init(sqlite3.connect(":memory:"))
        self.addCleanup(self.c.close)
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        # scan file globs point at the temp dir, so state never looks at the real WoW folder
        files = {"addon_file": str(self.dir / "AHFlip*.lua"), "scan_file": str(self.dir / "Auctionator*.lua")}
        for p in (
            mock.patch.dict(config.DEFAULTS, files),
            mock.patch.object(setup.blizzard, "configured", return_value=False),  # never reads the real .env
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_fresh_install(self):
        s = setup.state(self.c)
        self.assertEqual((s["done"], s["detected"], s["faction"], s["rs"], s["api"]), (False, {}, "horde", 1, False))
        self.assertEqual(s["files"], {"AHFlip scan": None, "Auctionator scan": None})

    def test_detected_from_newest_file(self):
        old, new = self.dir / "AHFlip.lua", self.dir / "AHFlip2.lua"
        old.write_text(saved("Horde", "PvP"))
        new.write_text(saved("Alliance", "Normal"))
        os.utime(old, (1, 1))
        self.assertEqual(setup.state(self.c)["detected"], {"faction": "alliance", "rs": 2})

    def test_wow_found_or_not(self):
        with mock.patch.object(config, "WOW_FOUND", False):
            self.assertIsNone(setup.state(self.c)["wow"])
        with mock.patch.object(config, "WOW_FOUND", True), mock.patch.object(config, "WOW", self.dir):
            self.assertEqual(setup.state(self.c)["wow"], str(self.dir))

    def test_existing_settings_count_as_done(self):
        db.save_settings(self.c, {"cut": 0.1})
        self.assertTrue(setup.state(self.c)["done"])

    def test_save(self):
        s = setup.save(self.c, "15", "alliance")
        self.assertEqual((s["done"], s["rs"], s["faction"]), (True, 15, "alliance"))
        self.assertEqual(db.settings(self.c)["house"], 110)
        self.assertTrue(db.meta(self.c, "setup_done"))
        self.assertEqual(setup.save(self.c, 1, "horde")["faction"], "horde")
        self.assertEqual(db.settings(self.c)["house"], 113)

    def test_save_rejects(self):
        for rs, faction in ((4, "horde"), (1, "goblin")):
            with self.assertRaises(ValueError):
                setup.save(self.c, rs, faction)
        with self.assertRaises(ValueError):
            setup.save(self.c, "x", "horde")
        self.assertIsNone(db.meta(self.c, "setup_done"))


class FindWow(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)

    def find(self, env, globbed=()):
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(config.glob, "glob", return_value=list(globbed)):
            return config.find_wow()

    def wow(self, parent, forever=True):
        w = Path(parent) / "World of Warcraft"
        (w / "_forever_" if forever else w).mkdir(parents=True)
        return w

    def test_env_dirs(self):
        pf86, pf = self.dir / "x86", self.dir / "pf"
        self.wow(pf86, forever=False)  # retail only: skipped
        w = self.wow(pf)
        self.assertEqual(self.find({"PROGRAMFILES(X86)": str(pf86), "PROGRAMFILES": str(pf)}), w)

    def test_wsl_drives(self):
        w = self.wow(self.dir / "d")
        self.assertEqual(self.find({}, [str(self.dir / "d")]), w)

    def test_not_found(self):
        with mock.patch.object(config.Path, "is_dir", return_value=False):  # C:/ and /Applications too
            self.assertIsNone(self.find({"PROGRAMFILES": str(self.dir)}, [str(self.dir)]))


if __name__ == "__main__":
    unittest.main()
