"""In-game scans (src 'addon') from our AHFlip addon (_addon_/AHFlip/): SavedVariables/AHFlip.lua.
Built from every listing, skipping bid-locked and the player's own, so prices are buyable.
items format: "itemID:buyableQty:price,qty,price,qty,...;" (20 cheapest unit prices, ascending).
Also: ah (which auction house), names (item names from the game), ledger (logged trades)."""

import re
from pathlib import Path

LEDGER = re.compile(r'"(\d+)\.(\d+):(buy|sell):(\d+):(\d+):(\d+):(\d*):([^"\n]*)"')


def read_ledger(path):
    """AHFlipDB.ledger (_addon_/AHFlip/Ledger.lua) -> [((time, n), kind, item, qty, unit price, sell price|None, name)]."""
    raw = Path(path).read_text(errors="replace")
    return [
        ((int(t), int(n)), kind, int(item), int(qty), int(price), int(sell) if sell else None, name)
        for t, n, kind, item, qty, price, sell, name in LEDGER.findall(raw)
    ]


def read_names(path):
    """AHFlipDB.names "id:sell:name;..." (sell empty if the game hadn't loaded it) -> [(id, name, sell|None)]."""
    raw = Path(path).read_text(errors="replace")
    m = re.search(r'\["names"\] = "((?:[^"\\]|\\.)*)"', raw)
    out = []
    for part in (m.group(1) if m else "").split(";"):
        f = part.split(":", 2)
        if len(f) == 3 and f[0].isdigit() and f[2]:
            out.append((int(f[0]), f[2].replace('\\"', '"'), int(f[1]) if f[1].isdigit() else None))
    return out


def read_cats(path):
    """AHFlipDB.cats "id:class:subclass;..." -> [(id, class, subclass|None)]."""
    m = re.search(r'\["cats"\] = "([^"]*)"', Path(path).read_text(errors="replace"))
    out = []
    for part in (m.group(1) if m else "").split(";"):
        f = part.split(":")
        if len(f) == 3 and f[0].isdigit() and f[1]:
            out.append((int(f[0]), f[1], f[2] or None))
    return out


def read(path):
    """-> (scan time, {item: (lowest unit price, buyable qty)}, {item: [(price, qty), ...] cheapest first},
    side 'horde' (global, Horde and Alliance share it)|'goblin' of the auction house scanned)."""
    raw = Path(path).read_text(errors="replace")
    side = re.search(r'\["ah"\] = "(horde|alliance|goblin)"', raw)
    t = re.search(r'\["time"\] = (\d+)', raw)
    s = re.search(r'\["items"\] = "([0-9:;,]*)"', raw)
    if not t or not s:
        raise ValueError(f"no AHFlip scan in {path}")
    best, depth = {}, {}
    for part in s.group(1).split(";"):
        if not part:
            continue
        fields = part.split(":")
        if len(fields) == 4:  # addon v1 format "item:min:qty:min2" (no depth)
            best[int(fields[0])] = (int(fields[1]), int(fields[2]))
            continue
        item, qty, levels = fields
        n = [int(x) for x in levels.split(",")]
        depth[int(item)] = list(zip(n[0::2], n[1::2], strict=True))
        best[int(item)] = (n[0], int(qty))
    side = side.group(1) if side else "horde"  # scans before v2 were all Horde
    return int(t.group(1)), best, depth, "goblin" if side == "goblin" else "horde"  # older addons wrote "alliance"
