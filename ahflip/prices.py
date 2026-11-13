"""Price snapshots: table price(ts, house, item, min, qty, src). One row per item per snapshot.
`min` is the lowest buyable unit price in copper, `qty` the total listed, `src` 'addon', 'scan' or 'api'."""

import hashlib
import json
import statistics

from .db import meta


def store(c, house, best, ts, src="api"):
    """Save one snapshot {item: (min, qty)}. False (nothing saved) if identical to the previous one from
    the same source, so repeated snapshots of unchanged data don't count as extra price history."""
    digest = hashlib.sha1(json.dumps(sorted(best.items())).encode()).hexdigest()
    key = f"digest:{house}:{src}"
    if digest == meta(c, key):
        return False
    with c:
        c.executemany("insert into price values(?,?,?,?,?,?)", [(ts, house, i, m, q, src) for i, (m, q) in best.items()])
        c.execute("insert or replace into meta values(?,?)", (key, json.dumps(digest)))
    return True


def store_depth(c, house, ts, depth):
    """Replace the house's price depth (cheapest price levels per item) with one scan's.
    Only the newest scan's depth is kept: it's for "how many can I buy at a profit now"."""
    with c:
        c.execute("delete from depth where house=?", (house,))
        c.executemany(
            "insert into depth values(?,?,?,?,?)", [(house, ts, i, p, q) for i, levels in depth.items() for p, q in levels]
        )


def depth(c, house, ts):
    """{item: [(price, qty), ...] cheapest first} if the stored depth is from snapshot ts, else {}."""
    out = {}
    for i, p, q in c.execute("select item, price, qty from depth where house=? and ts=? order by item, price", (house, ts)):
        out.setdefault(i, []).append((p, q))
    return out


FRESH = 3600  # seconds an AHFlip scan stays current behind newer data (it alone has price depth)


def latest(c, house):
    """ts of the current snapshot: the newest from any source, except the newest AHFlip scan while it is less
    than FRESH older (keeps deal depth between hourly API snapshots). API snapshots are dated by Last-Modified;
    taken minutes apart, all sources agree within 10% on 97-99% of items (checked 2026-11-11)."""
    newest = c.execute("select max(ts) from price where house=?", (house,)).fetchone()[0]
    scan = c.execute("select max(ts) from price where house=? and src='addon'", (house,)).fetchone()[0]
    return scan if scan and newest - scan < FRESH else newest


def source(c, house, ts):
    r = c.execute("select src from price where house=? and ts=? order by rowid desc limit 1", (house, ts)).fetchone()
    return r and r[0]


def count(c, house):
    return c.execute("select count(distinct ts) from price where house=?", (house,)).fetchone()[0]


def current(c, house, ts):
    """{item: (min, qty)} at ts. Sources share a ts only by coincidence; the newest row wins."""
    return {
        i: (m, q) for i, m, q in c.execute("select item, min, qty from price where house=? and ts=? order by rowid", (house, ts))
    }


def series(c, house, ts, days):
    """{item: [(ts, min, qty), ...] oldest first} for snapshots from every source in the `days` before ts."""
    out = {}
    for i, t, m, q in c.execute(
        "select item, ts, min, qty from price where house=? and ts<? and ts>=? order by ts",
        (house, ts, ts - days * 86400),
    ):
        out.setdefault(i, []).append((t, m, q))
    return out


def past(c, house, ts, days):
    """{item: [min, ...]}: series() prices only."""
    return {i: [m for _, m, _ in pts] for i, pts in series(c, house, ts, days).items()}


def history(c, house, item):
    """[(ts, min, qty, src)] oldest first."""
    return c.execute("select ts, min, qty, src from price where house=? and item=? order by ts", (house, item)).fetchall()


def item_stats(c, s, item, ts):
    name, sell = c.execute("select name, sell from item where id=?", (item,)).fetchone() or (None, None)
    cur = c.execute("select min, qty from price where house=? and item=? and ts=?", (s["house"], item, ts)).fetchone()
    mins = [
        r[0]
        for r in c.execute(
            "select min from price where house=? and item=? and ts<? and ts>=?",
            (s["house"], item, ts or 0, (ts or 0) - s["hist_days"] * 86400),
        )
    ]
    return dict(
        item=item,
        name=name,
        sell=sell,
        min=cur and cur[0],
        qty=cur and cur[1],
        median=int(statistics.median(mins)) if mins else None,
        past=len(mins),
    )
