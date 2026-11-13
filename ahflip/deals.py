"""Deal rules. find_deals() is pure (unit-tested); load_deals() feeds it from the DB."""

import statistics

from . import items, prices
from .db import house_cut


def find_deals(cur, hist, sell, cut, discount, min_snaps):
    """cur {item: (min, qty)}, hist {item: [past mins]}, sell {item: vendor price}.
    Returns [(kind, item, buy_at, worth, profit_per_unit)] best first.
      vendor: buy price < vendor sell price.
      flip:   enough history, price <= discount x median, and median after AH cut beats the price."""
    # shortcut: ignores AH deposit and undercut competition; profit is an upper bound
    out = []
    for i, (m, _) in cur.items():
        v = sell.get(i) or 0
        if m < v:
            out.append(("vendor", i, m, v, v - m))
            continue
        past = hist.get(i, [])
        if len(past) >= min_snaps:
            usual = statistics.median(past)
            profit = int(usual * (1 - cut) - m)
            if m <= usual * discount and profit > 0:
                out.append(("flip", i, m, int(usual), profit))
    return sorted(out, key=lambda d: -d[4])


def depth_profit(levels, gain):
    """(units, total profit) over price levels [(price, qty)] where gain(price) > 0."""
    hits = [(gain(p), q) for p, q in levels if gain(p) > 0]
    return sum(q for _, q in hits), sum(g * q for g, q in hits)


def gain_fn(kind, worth, cut, discount):
    """Profit per unit when buying at price p, for this deal kind."""
    if kind == "vendor":
        return lambda p: worth - p
    return lambda p: int(worth * (1 - cut) - p) if p <= worth * discount else 0


def load_deals(c, s, hist=None):
    """(ts of the latest snapshot or None, [deal dicts]) for settings s. With price depth (AHFlip scans),
    each deal also gets `units` (how many are profitable to buy) and `total` (their summed profit).
    hist: prices.past() result if the caller already has it."""
    house = s["house"]
    ts = prices.latest(c, house)
    if ts is None:
        return None, []
    cur = prices.current(c, house, ts)
    names, sell = items.info(c)
    if hist is None:
        hist = prices.past(c, house, ts, s["hist_days"])
    cut = house_cut(s)
    found = find_deals(cur, hist, sell, cut, s["flip_discount"], s["min_snaps"])
    levels = prices.depth(c, house, ts)
    out = []
    for k, i, b, w, p in found:
        if p < s["min_profit"]:
            continue
        d = dict(kind=k, item=i, name=names.get(i), buy=b, worth=w, profit=p, qty=cur[i][1], units=None, total=None)
        if i in levels:
            # shortcut: only the 20 cheapest price levels are saved; more profitable levels are undercounted
            d["units"], d["total"] = depth_profit(levels[i], gain_fn(k, w, cut, s["flip_discount"]))
        out.append(d)
    out.sort(key=lambda d: -(d["total"] if d["total"] is not None else d["profit"]))
    return ts, out
