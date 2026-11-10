"""In-game scans (src 'scan') from Auctionator's SavedVariables file. No network.

AUCTIONATOR_PRICE_DATABASE[realm] is a Lua string holding CBOR:
{itemId: {m: latest min price, a: {day: available}, h/l: {day: daily high/low}}}, day = unix day - AUCTIONATOR_DAY0.
AUCTIONATOR_SAVEDVARS.TimeOfLastBrowseScan is the time of the last full scan.
Weaker than the AHFlip addon: one min price per item, can't skip bid-locked listings."""

import re
from pathlib import Path

from .. import config
from ..codec import cbor, lua_str


def read_scan(path, realm):
    """-> (time of last full scan, {item: (lowest unit price, qty)}) for items seen on the scan's day."""
    raw = Path(path).read_bytes()
    t = re.search(rb'\["TimeOfLastBrowseScan"\] = (\d+)', raw)
    start = raw.find(b"AUCTIONATOR_PRICE_DATABASE = {")
    m = re.compile(rb'\["' + re.escape(realm.encode()) + rb'"\] = "').search(raw, max(start, 0))
    if not t or start < 0 or not m:
        raise ValueError(f"no full scan or no {realm!r} price data in {path}")
    data, _ = cbor(lua_str(raw, m.end() - 1)[0])
    ts = int(t.group(1))
    day = str(ts // 86400 - config.AUCTIONATOR_DAY0)
    # shortcut: an item seen earlier that day but gone by the full scan keeps its earlier price;
    # upgrade if stale items show up (would need Auctionator's per-scan data, which it doesn't save).
    best = {}
    for k, v in data.items():
        if (
            isinstance(k, str)
            and k.isdigit()
            and isinstance(v, dict)
            and v.get("m")
            and isinstance(v.get("a"), dict)
            and day in v["a"]
        ):
            best[int(k)] = (v["m"], v["a"][day])
    return ts, best
