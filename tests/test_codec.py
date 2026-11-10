import tempfile
import unittest
from pathlib import Path

from ahflip.codec import cbor, lua_str
from ahflip.sources import addon
from ahflip.sources.auctionator import read_scan


class Codec(unittest.TestCase):
    def test_lua_str(self):
        self.assertEqual(lua_str(b'"a\\"b\\\\c\\nd\\000e\\0123"', 0), (b'a"b\\c\nd\x00e\x0c3', 22))  # \ddd is decimal

    def test_cbor_indefinite(self):
        self.assertEqual(cbor(bytes([0xBF, 0x41, 0x6B, 0x9F, 0x01, 0x20, 0xFF, 0xFF]))[0], {"k": [1, -1]})


class ReadScan(unittest.TestCase):
    def test_ahflip_addon_file(self):
        lua = (
            '\nAHFlipDB = {\n["lastRequest"] = 1794290000,\n["time"] = 1794290042,\n'
            '["items"] = "2865:725:600,3,610,722;6309:109:1700,109",\n["realm"] = "PvP",\n["ah"] = "goblin",\n'
            '["names"] = "2865:12:Elixir of Lesser Agility;286984::Odd Trinket",\n}\n'
        )
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "AHFlip.lua"
            f.write_text(lua)
            self.assertEqual(
                addon.read(f),
                (
                    1794290042,
                    {2865: (600, 725), 6309: (1700, 109)},
                    {2865: [(600, 3), (610, 722)], 6309: [(1700, 109)]},
                    "goblin",
                ),
            )
            self.assertEqual(addon.read_names(f), [(2865, "Elixir of Lesser Agility", 12), (286984, "Odd Trinket", None)])

    def test_auctionator_file(self):
        # {"6309": {"a": {"2505": 109}, "m": 1700}, "version": 2} as Auctionator writes it (byte-string keys)
        data = (
            bytes([0xA2, 0x44])
            + b"6309"
            + bytes([0xA2, 0x41])
            + b"a"
            + bytes([0xA1, 0x44])
            + b"2505"
            + bytes([0x18, 109, 0x41])
            + b"m"
            + bytes([0x19, 0x06, 0xA4, 0x47])
            + b"version"
            + bytes([0x02])
        )
        lua = (
            b'AUCTIONATOR_SAVEDVARS = {\n["TimeOfLastBrowseScan"] = 1794286387,\n}\n'
            b'AUCTIONATOR_PRICE_DATABASE = {\n["__dbversion"] = 8,\n["PvP"] = "'
            + data.replace(b"\\", b"\\\\").replace(b'"', b'\\"')
            + b'",\n}\n'
        )
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "Auctionator.lua"
            f.write_bytes(lua)
            self.assertEqual(read_scan(f, "PvP"), (1794286387, {6309: (1700, 109)}))
