"""Market overview (the site's home page): every item's price now vs its usual price, with a daily trend.
Views: below (well under usual), vendor (under vendor price), rising (well over usual), all.
Below usual / Rising skip unreliable items: rarely listed (setting min_listed) or with prices that swing wildly
(max_spread), since their "usual price" is one seller's asking price, not a market price."""

import statistics

from . import items, prices
from .deals import load_deals

VIEWS = ("below", "vendor", "rising", "all")
RISING = 1.2  # shortcut: fixed "rising" threshold (20% over usual); make it a setting if it needs tuning


def daily_lows(pts, now):
    """[(ts, min, ...)] oldest first -> lowest price per day, oldest first, then the current price."""
    days = {}
    for t, m, *_ in pts:
        d = t // 86400
        days[d] = min(days.get(d, m), m)
    return [days[d] for d in sorted(days)] + [now]


def reliable(mins, qtys, min_listed, max_spread):
    """Enough listings usually, and the lowest price stayed within max_spread times of itself."""
    lo, hi = min(mins), max(mins)
    return statistics.median(qtys) >= min_listed and (lo > 0 and hi / lo <= max_spread)


def matches(view, r, discount):
    if view == "below":
        return r["usual"] is not None and r["reliable"] and r["now"] <= r["usual"] * discount
    if view == "vendor":
        return bool(r["sell"]) and r["now"] < r["sell"]
    if view == "rising":
        return r["usual"] is not None and r["reliable"] and r["now"] >= r["usual"] * RISING
    return True


SORT = {  # best first
    "below": lambda r: r["pct"],
    "vendor": lambda r: -(r["sell"] - r["now"]),
    "rising": lambda r: -r["pct"],
    "all": lambda r: -r["listed"],
}


def load_market(c, s, view="below", q="", limit=300):
    """dict(ts, src, counts {view: n}, rows [...], more, hidden) for the current snapshot.
    hidden: items this view skips as unreliable (only Below usual / Rising skip any)."""
    if view not in VIEWS:
        raise ValueError(f"view must be one of {', '.join(VIEWS)}")
    house = s["house"]
    ts = prices.latest(c, house)
    if ts is None:
        return dict(ts=None, src=None, counts={v: 0 for v in VIEWS}, rows=[], more=0, hidden=0)
    src = prices.source(c, house, ts)
    cur = prices.current(c, house, ts)
    names, sell = items.info(c)
    series = prices.series(c, house, ts, s["hist_days"], src)
    deals = {d["item"]: d for d in load_deals(c, s, {i: [m for _, m, _ in p] for i, p in series.items()})[1]}
    rows = []
    for i, (m, qty) in cur.items():
        pts = series.get(i, [])
        mins = [p for _, p, _ in pts]
        usual = int(statistics.median(mins)) if len(pts) >= s["min_snaps"] else None
        rows.append(
            dict(
                item=i,
                name=names.get(i),
                now=m,
                usual=usual,
                listed=qty,
                sell=sell.get(i),
                pct=round((m / usual - 1) * 100) if usual else None,
                lo=min(mins, default=None),
                hi=max(mins, default=None),
                trend=daily_lows(pts, m),
                deal=deals.get(i),
                reliable=reliable(mins + [m], [q for *_, q in pts] + [qty], s["min_listed"], s["max_spread"]),
            )
        )
    disc = s["flip_discount"]
    counts = {v: sum(matches(v, r, disc) for r in rows) for v in VIEWS}
    hidden = sum(matches(view, dict(r, reliable=True), disc) for r in rows) - counts[view]
    q = q.strip().lower()
    out = [r for r in rows if matches(view, r, disc) and (not q or q in (r["name"] or "").lower() or q == str(r["item"]))]
    out.sort(key=SORT[view])
    return dict(ts=ts, src=src, counts=counts, rows=out[:limit], more=max(0, len(out) - limit), hidden=hidden)
