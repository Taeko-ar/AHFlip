import contextlib
import io
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ahflip import cli, config, db, items, prices
from ahflip.sources import blizzard, scans


class Cli(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        p = mock.patch.object(config, "DB_PATH", self.dir / "ah.db")
        p.start()
        self.addCleanup(p.stop)

    def run_cli(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out, mock.patch.object(sys, "argv", ["ah.py", *argv]):
            cli.main()
        return out.getvalue()

    def test_web(self):
        with mock.patch("ahflip.web.server.serve") as serve:
            self.run_cli("web")
            self.run_cli("web", "9000")
        self.assertEqual(serve.call_args_list, [mock.call(8000), mock.call(9000)])

    def test_probe_and_snap(self):
        with mock.patch.object(blizzard, "probe") as probe, mock.patch.object(blizzard, "snap") as snap:
            self.run_cli("probe", "1", "113")
            self.run_cli("snap", "1", "113")
        probe.assert_called_once_with([1, 113])
        snap.assert_called_once_with(1, 113)

    def test_import(self):
        with db.session() as c:
            db.set_meta(c, "settings", {"addon_file": str(self.dir / "AHFlip.lua"), "scan_file": str(self.dir / "none*.lua")})
        (self.dir / "AHFlip.lua").write_text('AHFlipDB = {\n["time"] = 1794290042,\n["items"] = "2865:5:600,5",\n}\n')
        out = self.run_cli("import")
        self.assertIn("AHFlip scan (horde AH)", out)
        self.assertIn("Auctionator scan: no file matches", out)
        out = self.run_cli("import")
        self.assertIn("AHFlip scan from", out)
        self.assertIn("already imported", out)
        self.assertEqual(out.count("\n"), 2)

    def test_deals(self):
        with self.assertRaisesRegex(SystemExit, "no snapshots yet"):
            self.run_cli("deals", "113")
        with db.session() as c:
            items.save_info(c, [(1, "Linen Cloth", 100), (2, None, 100)])
            prices.store(c, 113, {1: (5, 2), 2: (10, 3)}, 1794290042, "addon")
            prices.store_depth(c, 113, 1794290042, {1: [(5, 2)]})
        out = self.run_cli("deals", "113").splitlines()
        self.assertRegex(out[0], r"^1 snapshots, latest .* \(addon\)$")
        self.assertIn("Linen Cloth", out[1])
        self.assertIn("profitable 2 = +", out[1])
        self.assertRegex(out[2], r"^vendor 2 ")
        self.assertNotIn("profitable", out[2])

    def test_test_command(self):
        with (
            mock.patch.object(unittest.defaultTestLoader, "discover", return_value=unittest.TestSuite()) as discover,
            mock.patch.object(sys, "stderr", io.StringIO()),
            self.assertRaises(SystemExit) as e,
        ):
            self.run_cli("test")
        self.assertFalse(e.exception.code)
        discover.assert_called_once_with(str(config.ROOT / "tests"), top_level_dir=str(config.ROOT))

    def test_ah_py_entry_point(self):
        with mock.patch.object(scans, "newest", return_value=None):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), mock.patch.object(sys, "argv", ["ah.py", "import"]):
                runpy.run_path(str(config.ROOT / "ah.py"), run_name="__main__")
        self.assertIn("AHFlip scan: no file matches", out.getvalue())
