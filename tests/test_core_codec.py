import tempfile
import unittest
from pathlib import Path

from ahflip.codec import cbor, lua_str
from ahflip.sources import addon
from ahflip.sources.auctionator import read_scan


class LuaStr(unittest.TestCase):
    def test_unterminated(self):
        with self.assertRaises(ValueError):
            lua_str(b'"abc', 0)


class Cbor(unittest.TestCase):
    def test_indefinite_strings(self):
        self.assertEqual(cbor(bytes([0x5F, 0x41, 0x61, 0x41, 0x62, 0xFF])), (b"ab", 6))
        self.assertEqual(cbor(bytes([0x7F, 0x61, 0x61, 0x61, 0x62, 0xFF])), ("ab", 6))

    def test_simple_values_and_floats(self):
        self.assertEqual(cbor(bytes([0xF4]))[0], False)
        self.assertEqual(cbor(bytes([0xF5]))[0], True)
        self.assertIsNone(cbor(bytes([0xF6]))[0])
        self.assertEqual(cbor(bytes([0xF9, 0x3C, 0x00])), (1.0, 3))
        self.assertEqual(cbor(bytes([0xFA, 0x3F, 0xC0, 0x00, 0x00])), (1.5, 5))
        self.assertEqual(cbor(bytes([0xFB, 0x40, 0x04, 0, 0, 0, 0, 0, 0])), (2.5, 9))

    def test_unsupported(self):
        # reserved length, tag (major type 6), one-byte simple value
        for b in ([0x1C], [0xC0], [0xF8, 0x00]):
            with self.assertRaises(ValueError):
                cbor(bytes(b))


class Sources(unittest.TestCase):
    def file(self, content):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        f = Path(d.name) / "SV.lua"
        (f.write_bytes if isinstance(content, bytes) else f.write_text)(content)
        return f

    def test_addon_v1_format_and_default_side(self):
        f = self.file('["time"] = 5,\n["items"] = "7:100:3:120;;8:50:1,50",\n')
        self.assertEqual(addon.read(f), (5, {7: (100, 3), 8: (1, 50)}, {8: [(1, 50)]}, "horde"))

    def test_addon_no_scan(self):
        with self.assertRaises(ValueError):
            addon.read(self.file('["time"] = 5,\n'))

    def test_addon_names_skip_bad_parts(self):
        f = self.file('["names"] = "x:1:Bad;5:2:;6:3;7:x:Say \\"hi\\""')
        self.assertEqual(addon.read_names(f), [(7, 'Say "hi"', None)])
        self.assertEqual(addon.read_names(self.file("")), [])

    def test_auctionator_missing_data(self):
        f = self.file(b'["TimeOfLastBrowseScan"] = 1,\nAUCTIONATOR_PRICE_DATABASE = {\n["PvP"] = "x",\n}\n')
        with self.assertRaises(ValueError):
            read_scan(f, "Normal")
