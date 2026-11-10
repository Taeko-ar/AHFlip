import contextlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from ahflip import config, db, items, prices
from ahflip.sources import blizzard


class Resp(io.BytesIO):
    """Fake urlopen response: JSON body + headers."""

    def __init__(self, data, headers=None):
        super().__init__(json.dumps(data).encode())
        self.headers = headers or {}


def http_error(code):
    return urllib.error.HTTPError("https://x", code, "err", {}, None)


class TempDB(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        p = mock.patch.object(config, "DB_PATH", self.dir / "ah.db")
        p.start()
        self.addCleanup(p.stop)


class EnvToken(TempDB):
    def test_env_and_token(self):
        f = self.dir / "fake.env"
        f.write_text("# comment\n\nBNET_CLIENT_ID = 'x'\nBNET_CLIENT_SECRET=\"y\"\n=novalue\n")
        with mock.patch.object(config, "ENV_PATH", f):
            self.assertEqual(blizzard.env(), {"BNET_CLIENT_ID": "x", "BNET_CLIENT_SECRET": "y"})
            with mock.patch("urllib.request.urlopen", return_value=Resp({"access_token": "tok"})) as u:
                self.assertEqual(blizzard.token(), "tok")
        req = u.call_args[0][0]
        self.assertEqual(req.get_header("Authorization"), "Basic eDp5")  # base64("x:y")

    def test_configured(self):
        f = self.dir / "fake.env"
        with mock.patch.object(config, "ENV_PATH", f):
            self.assertFalse(blizzard.configured())  # no file
            f.write_text("BNET_CLIENT_ID=x\nBNET_CLIENT_SECRET=\n")
            self.assertFalse(blizzard.configured())
            f.write_text("BNET_CLIENT_ID=x\nBNET_CLIENT_SECRET=y\n")
            self.assertTrue(blizzard.configured())


class Get(unittest.TestCase):
    def test_json_and_last_modified(self):
        lm = {"Last-Modified": "Tue, 10 Nov 2026 12:00:00 GMT"}
        with mock.patch("urllib.request.urlopen", return_value=Resp({"a": 1}, lm)) as u:
            self.assertEqual(blizzard.get("t", "/p"), {"a": 1})
        self.assertIn("namespace=dynamic-forever-us", u.call_args[0][0].full_url)
        with mock.patch("urllib.request.urlopen", return_value=Resp({"a": 1}, lm)):
            self.assertEqual(blizzard.get("t", "/p", with_time=True), ({"a": 1}, 1794312000))
        for headers in ({}, {"Last-Modified": "garbage"}):  # missing (TypeError) / bad (ValueError) date
            with mock.patch("urllib.request.urlopen", return_value=Resp({"a": 1}, headers)):
                self.assertEqual(blizzard.get("t", "/p", with_time=True), ({"a": 1}, None))

    def test_404_and_other_errors(self):
        with mock.patch("urllib.request.urlopen", side_effect=http_error(404)):
            self.assertIsNone(blizzard.get("t", "/p"))
            self.assertEqual(blizzard.get("t", "/p", with_time=True), (None, None))
        with mock.patch("urllib.request.urlopen", side_effect=http_error(500)), self.assertRaises(urllib.error.HTTPError):
            blizzard.get("t", "/p")


def fake_get(responses):
    """get() stand-in: path -> response; item paths return names, except item 404s (None)."""

    def get(tok, path, ns="dynamic", with_time=False):
        if path.startswith("/data/wow/item/"):
            i = int(path.rsplit("/", 1)[1])
            return None if i == 404 else {"name": f"Item {i}", "sell_price": i}
        return responses[path]

    return get


class Snap(TempDB):
    base = "/data/wow/ruleset/1/auctions/113"

    def run_snap(self, a, cm):
        out = io.StringIO()
        get = fake_get({self.base: a, self.base + "/commodities": cm})
        with (
            mock.patch.object(blizzard, "token", return_value="t"),
            mock.patch.object(blizzard, "get", get),
            contextlib.redirect_stdout(out),
        ):
            return blizzard.snap(1, 113), out.getvalue()

    def test_snap_saves_then_unchanged(self):
        a = ({"auctions": [{"item": {"id": 7}, "buyout": 100, "quantity": 1}]}, 1000)
        cm = ({"auctions": [{"item": {"id": 404}, "unit_price": 5, "quantity": 3}]}, 900)
        msg, out = self.run_snap(a, cm)
        self.assertIn("2 auctions, 2 items saved", msg)
        self.assertIn("item info 2/2", out)
        with db.session() as c:
            self.assertEqual(prices.latest(c, 113), 900)  # dated by the oldest Last-Modified
            self.assertEqual(items.info(c)[0], {7: "Item 7", 404: None})
            self.assertTrue(db.meta(c, "attempt:113"))
        msg, out = self.run_snap(({}, None), ({"auctions": None}, None))  # no times: dated now
        self.assertIn("0 auctions, 0 items saved", msg)
        msg, _ = self.run_snap(({}, None), ({}, None))
        self.assertIn("unchanged since last snapshot, not saved", msg)

    def test_half_snapshot_refused(self):
        for a, cm, which in (((None, None), ({}, 1), "auctions"), (({}, 1), (None, None), "commodities")):
            with self.assertRaisesRegex(RuntimeError, f"{which} returned 404"):
                self.run_snap(a, cm)


class FetchRetry(TempDB):
    def test_fetch_items_batches_of_100(self):
        ids = list(range(1, 102))
        with mock.patch.object(blizzard, "get", fake_get({})), contextlib.redirect_stdout(io.StringIO()) as out:
            blizzard.fetch_items("t", ids)
        self.assertEqual(out.getvalue().split(), ["item", "info", "100/101", "item", "info", "101/101"])
        with db.session() as c:
            self.assertEqual(items.known_ids(c), set(ids))

    def test_retry(self):
        with db.session() as c:
            items.save_info(c, [(5, None, None), (404, None, None)])
        with (
            mock.patch.object(blizzard, "token", return_value="t"),
            mock.patch.object(blizzard, "get", fake_get({})),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(blizzard.retry(), "retried 2 items, 1 now have info")


class Probe(unittest.TestCase):
    def run_probe(self, args, resp):
        with (
            mock.patch.object(blizzard, "token", return_value="t"),
            mock.patch.object(blizzard, "get", return_value=resp) as g,
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            blizzard.probe(args)
        return g.call_args[0][1], out.getvalue()

    def test_paths(self):
        self.assertEqual(self.run_probe([], {"x": 1}), ("/data/wow/ruleset/index", '{\n "x": 1\n}\n'))
        self.assertEqual(self.run_probe([1], {})[0], "/data/wow/ruleset/1/auctions/")

    def test_house_shape(self):
        path, out = self.run_probe([1, 113], {"auctions": [1, 2, 3], "id": 5})
        self.assertEqual(path, "/data/wow/ruleset/1/auctions/113")
        self.assertEqual(out, "{'auctions': 'list', 'id': 'int'}\n[\n 1,\n 2\n]\n")
        self.assertEqual(self.run_probe([1, 113], None)[1], "{}\nnull\n")  # 404
