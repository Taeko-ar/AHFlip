"""JSON API. Each route is fn(c, args) -> JSON-able; args is the query (GET) or JSON body (POST).
Raise ValueError/KeyError/TypeError for bad input (becomes HTTP 400)."""

from .. import config, db, items, ledger, prices, setup
from ..market import load_market
from ..sources import blizzard, scans
from . import jobs

NO_API = "No Battle.net API keys (.env): the site runs on in-game scans only. See the README to add keys."


def status(c, _):
    s = db.settings(c)
    house = s["house"]
    ts = prices.latest(c, house)
    attempt = db.meta(c, f"attempt:{house}") or ts
    return dict(
        jobs.STATE,
        latest=ts,
        src=prices.source(c, house, ts),
        snaps=prices.count(c, house),
        attempt=attempt,
        rs=s["rs"],
        house=house,
        scan_ts=scans.last_scan(c),
        scan_files=scans.found_files(s),
        next=(attempt or 0) + s["snap_minutes"] * 60 if s["snap_minutes"] else None,
        retried=db.meta(c, "retried"),
        missing=len(items.missing_ids(c)),
        ledger_n=ledger.count(c),
        houses={side: s[f"house_{side}"] for side in config.SIDES},
        api=blizzard.configured(),
        setup_done=bool(db.meta(c, "setup_done") or db.meta(c, "settings") is not None),
    )


def market(c, a):
    s = db.settings(c)
    m = load_market(c, s, a.get("view", "below"), a.get("q", ""), a.get("cat", ""))
    return dict(m, watch=sorted(items.watched(c)), cut=db.house_cut(s))


def history(c, a):
    """One item: stats, price points, and your trades of it."""
    s = db.settings(c)
    i = int(a["item"])
    trades = [e for e in ledger.summary(c)["entries"] if e["item"] == i]
    held = sum(e["qty"] if e["kind"] == "buy" else -e["qty"] for e in trades)
    return dict(
        prices.item_stats(c, s, i, prices.latest(c, s["house"])),
        points=prices.history(c, s["house"], i),
        watched=i in items.watched(c),
        trades=trades[:20],
        held=max(0, held),
    )


def watch(c, _):
    s = db.settings(c)
    ts = prices.latest(c, s["house"])
    return dict(items=[prices.item_stats(c, s, i, ts) for i in sorted(items.watched(c))])


def watch_set(c, b):
    i = items.resolve(c, b["item"])
    on = bool(b.get("on", True))
    items.set_watch(c, i, on)
    return dict(item=i, on=on)


def ledger_get(c, _):
    """Entries plus, per traded item, its lowest AH price now and vendor price (to value held stock)."""
    s = db.settings(c)
    L = ledger.summary(c)
    ts = prices.latest(c, s["house"])
    cur = prices.current(c, s["house"], ts) if ts else {}
    _, sell = items.info(c)
    L["now"] = {i: dict(min=cur.get(i, (None,))[0], sell=sell.get(i)) for i in {e["item"] for e in L["entries"]}}
    L["cut"] = db.house_cut(s)
    return L


def ledger_set(c, b):
    if "delete" in b:
        ledger.delete(c, b["delete"])
    elif "edit" in b:
        ledger.edit(c, b["edit"], b["kind"], b["item"], b["qty"], b["price"], b.get("note"))
    else:
        ledger.add(c, b["kind"], b["item"], b["qty"], b["price"], b.get("note"))
    return dict(ok=True)


def settings_get(c, _):
    return db.settings(c)


def settings_set(c, b):
    return db.save_settings(c, b)


def snap(c, _):
    if not blizzard.configured():
        raise ValueError(NO_API)
    return dict(started=jobs.start_snapshot(db.settings(c)), job=jobs.STATE["job"])


def retry(c, _):
    if not blizzard.configured():
        raise ValueError(NO_API)
    return dict(started=jobs.start_retry(), job=jobs.STATE["job"])


def setup_get(c, _):
    return setup.state(c)


def setup_set(c, b):
    return setup.save(c, b["rs"])


ROUTES = {
    ("GET", "/api/status"): status,
    ("GET", "/api/market"): market,
    ("GET", "/api/history"): history,
    ("GET", "/api/watch"): watch,
    ("GET", "/api/ledger"): ledger_get,
    ("GET", "/api/settings"): settings_get,
    ("GET", "/api/setup"): setup_get,
    ("POST", "/api/setup"): setup_set,
    ("POST", "/api/watch"): watch_set,
    ("POST", "/api/ledger"): ledger_set,
    ("POST", "/api/settings"): settings_set,
    ("POST", "/api/snap"): snap,
    ("POST", "/api/retry"): retry,
}
