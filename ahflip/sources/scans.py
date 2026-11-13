"""Import flow shared by in-game scan files (WoW SavedVariables, written on /reload or logout).
To add a scan source: a reader path -> (ts, {item: (min, qty)}[, {item: [(price, qty), ...]}]),
a path setting in config.DEFAULTS, and an entry in SOURCES. The optional third value is price depth."""

import glob
import os
import time

from .. import db, items, ledger, prices
from . import addon, auctionator

# src -> (setting holding the file glob, reader(path, settings))
SOURCES = {
    "addon": ("addon_file", lambda path, s: addon.read(path)),
    "scan": ("scan_file", lambda path, s: auctionator.read_scan(path, s["scan_realm"])),
}
LABELS = {"addon": "AHFlip scan", "scan": "Auctionator scan"}


def newest(pattern):
    """Newest file matching the glob, or None."""
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else None


def import_one(s, src, path):
    """Store the file's scan as a snapshot of the auction house it was taken at, unless imported already.
    The AHFlip file also carries logged trades (to the ledger, scan or not) and item names from the game."""
    if src == "addon":
        with db.session() as c:
            n = ledger.import_addon(c, addon.read_ledger(path))
            items.fill_missing(c, addon.read_names(path))
            items.save_cats(c, addon.read_cats(path))
        if n:
            print(f"AHFlip: {n} trades added to the ledger", flush=True)
    ts, best, *extra = SOURCES[src][1](path, s)
    depth = extra[0] if extra else None
    # shortcut: Auctionator scans don't say which AH they're from; they count as Horde (the player's side)
    side = extra[1] if len(extra) > 1 else "horde"
    house = s[f"house_{side}"]
    when = time.strftime("%H:%M", time.localtime(ts))
    with db.session() as c:
        db.set_meta(c, f"{src}_mtime", os.path.getmtime(path))
        if ts == db.meta(c, f"{src}_ts"):
            return f"{LABELS[src]} from {when} already imported"
        saved = prices.store(c, house, best, ts, src) if best else False
        if depth:
            prices.store_depth(c, house, ts, depth)
        db.set_meta(c, f"{src}_ts", ts)
    msg = f"{LABELS[src]} ({side} AH) from {when}: {len(best)} items " + ("saved" if saved else "not saved (empty or unchanged)")
    print(msg, flush=True)
    return msg


def changed(s):
    """[(src, path)] whose file changed since the last import attempt."""
    out = []
    with db.session() as c:
        for src, (key, _) in SOURCES.items():
            path = newest(s[key])
            if path and os.path.getmtime(path) != db.meta(c, f"{src}_mtime"):
                out.append((src, path))
    return out


def mark_seen(src, path):
    """Don't retry a bad file until it changes again."""
    with db.session() as c:
        db.set_meta(c, f"{src}_mtime", os.path.getmtime(path))


def last_scan(c):
    """Time of the newest imported in-game scan, any source."""
    return max((db.meta(c, f"{src}_ts") or 0 for src in SOURCES), default=0) or None


def found_files(s):
    return {LABELS[src]: newest(s[key]) for src, (key, _) in SOURCES.items()}
