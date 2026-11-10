"""The user's own trades: table ledger(id, ts, kind 'buy'|'sell', item, qty, price per unit, note, src).
src is 'manual' (website form) or 'addon' (logged in game by AHFlip). Sells are gold received after the AH cut."""

import time

from . import items
from .db import meta, set_meta
from .gold import parse_gold


def _fields(c, kind, item, qty, price, note):
    if kind not in ("buy", "sell"):
        raise ValueError("kind must be buy or sell")
    qty = int(qty)
    if qty < 1:
        raise ValueError("qty must be at least 1")
    return kind, items.resolve(c, item), qty, parse_gold(price), str(note or "")[:200]


def add(c, kind, item, qty, price, note=""):
    with c:
        c.execute(
            "insert into ledger(ts, kind, item, qty, price, note, src) values(?,?,?,?,?,?,'manual')",
            (int(time.time()), *_fields(c, kind, item, qty, price, note)),
        )


def edit(c, entry_id, kind, item, qty, price, note=""):
    with c:
        n = c.execute(
            "update ledger set kind=?, item=?, qty=?, price=?, note=? where id=?",
            (*_fields(c, kind, item, qty, price, note), int(entry_id)),
        ).rowcount
    if not n:
        raise ValueError("no such entry")


def import_addon(c, rows):
    """Add AHFlip-logged trades (sources.addon.read_ledger) newer than the last import; returns how many.
    A watermark, not per-entry keys, so entries deleted on the site don't come back on the next import."""
    mark = tuple(meta(c, "ledger_mark", (0, 0)))
    new = [r for r in rows if r[0] > mark]
    if not new:
        return 0
    set_meta(c, "ledger_mark", max(r[0] for r in new))
    new = [_with_id(c, r) for r in new]
    new = [r for r in new if r[2]]
    with c:
        c.executemany(
            "insert into ledger(ts, kind, item, qty, price, note, src) values(?,?,?,?,?,'','addon')",
            [(key[0], kind, item, qty, price) for key, kind, item, qty, price, _, _ in new],
        )
    # names for items the API never returned (404) or that aren't in any snapshot yet
    items.fill_missing(c, [(item, name, sell) for _, _, item, _, _, sell, name in new])
    return len(new)


def _with_id(c, r):
    """A sold auction comes with item id 0 when the game couldn't look the name up: find the id by name.
    Still unknown (or the name fits several items): the entry is dropped and reported."""
    key, kind, item, qty, price, sell, name = r
    if item == 0:
        try:
            item = items.resolve(c, name)
        except ValueError:
            print(f"AHFlip: skipped a {kind} of {qty}x {name!r}: unknown item name", flush=True)
            item = 0
    return (key, kind, item, qty, price, sell, name)


def delete(c, entry_id):
    with c:
        c.execute("delete from ledger where id=?", (int(entry_id),))


def count(c):
    return c.execute("select count(*) from ledger").fetchone()[0]


def summary(c):
    """Entries newest first, per-item totals, and overall spent/earned/net (unsold items not counted)."""
    entries = [
        dict(id=r[0], ts=r[1], kind=r[2], item=r[3], name=r[4], qty=r[5], price=r[6], note=r[7], src=r[8])
        for r in c.execute("""select l.id, l.ts, l.kind, l.item, i.name, l.qty, l.price, l.note, l.src
                                     from ledger l left join item i on i.id = l.item order by l.ts desc, l.id desc""")
    ]
    per = {}
    for e in entries:
        p = per.setdefault(e["item"], dict(item=e["item"], name=e["name"], bought=0, sold=0, spent=0, earned=0))
        if e["kind"] == "buy":
            p["bought"] += e["qty"]
            p["spent"] += e["qty"] * e["price"]
        else:
            p["sold"] += e["qty"]
            p["earned"] += e["qty"] * e["price"]
    for p in per.values():
        p["net"], p["held"] = p["earned"] - p["spent"], p["bought"] - p["sold"]
    spent = sum(p["spent"] for p in per.values())
    earned = sum(p["earned"] for p in per.values())
    return dict(entries=entries, items=list(per.values()), spent=spent, earned=earned, net=earned - spent)
