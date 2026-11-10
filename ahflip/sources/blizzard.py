"""Battle.net web API (WoW Forever namespaces): snapshots (src 'api') and item info."""

import base64
import email.utils
import json
import time
import urllib.error
import urllib.request

from .. import config, db, items, prices

API = f"https://{config.REGION}.api.blizzard.com"


def env():
    out = {}
    for line in config.ENV_PATH.read_text().splitlines():
        k, _, v = line.strip().partition("=")
        if k and not k.startswith("#"):
            out[k.strip()] = v.strip().strip("'\"")
    return out


def configured():
    """True if .env has both API keys. Without them the site works from in-game scans only."""
    try:
        e = env()
    except OSError:
        return False
    return bool(e.get("BNET_CLIENT_ID") and e.get("BNET_CLIENT_SECRET"))


def token():
    e = env()
    auth = base64.b64encode(f"{e['BNET_CLIENT_ID']}:{e['BNET_CLIENT_SECRET']}".encode()).decode()
    req = urllib.request.Request(
        "https://oauth.battle.net/token", data=b"grant_type=client_credentials", headers={"Authorization": f"Basic {auth}"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def get(tok, path, ns="dynamic", with_time=False):
    """JSON or None on 404. with_time: (json, Last-Modified as unix time or None)."""
    url = f"{API}{path}?namespace={ns}-forever-{config.REGION}&locale=en_US"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
            lm = r.headers.get("Last-Modified")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (None, None) if with_time else None
        raise
    if not with_time:
        return d
    try:
        return d, int(email.utils.parsedate_to_datetime(lm).timestamp())
    except (TypeError, ValueError):
        return d, None


def lowest(auctions):
    """{item_id: (lowest unit price in copper, total quantity)}. Skips bid-only auctions, and auctions whose
    bid has reached the buyout: in game those refuse buyout ("There is already a higher bid on that item")."""
    best = {}
    for a in auctions:
        qty = a.get("quantity", 1)
        if a.get("bid") and a.get("buyout") and a["bid"] >= a["buyout"]:
            continue
        unit = a.get("unit_price") or (a["buyout"] // qty if a.get("buyout") else None)
        if not unit:
            continue
        i = a["item"]["id"]
        m, q = best.get(i, (unit, 0))
        best[i] = (min(m, unit), q + qty)
    return best


def fetch_items(tok, ids):
    """Fetch name + vendor price per item, ~1 s each. Network first, then short writes."""
    rows = []
    for n, i in enumerate(ids, 1):
        d = get(tok, f"/data/wow/item/{i}", "static")  # ~40% of Forever items 404 for now
        rows.append((i, d and d.get("name"), d and d.get("sell_price")))
        if n % 100 == 0 or n == len(ids):
            with db.session() as c:
                items.save_info(c, rows)
            rows = []
            print(f"item info {n}/{len(ids)}", flush=True)


def snap(rs, house):
    """Save one API snapshot of house, then fetch info for items never seen before."""
    ts = int(time.time())
    with db.session() as c:
        db.set_meta(c, f"attempt:{house}", ts)  # the scheduler times auto snapshots off attempts
    tok = token()
    base = f"/data/wow/ruleset/{rs}/auctions/{house}"
    (a, t1), (cm, t2) = get(tok, base, with_time=True), get(tok, base + "/commodities", with_time=True)
    if a is None or cm is None:  # a half snapshot would hide every commodity (or item) deal
        raise RuntimeError(f"{'auctions' if a is None else 'commodities'} returned 404, snapshot not saved")
    # Date the snapshot by when Blizzard made the data, so lagging API data sorts behind newer in-game scans.
    ts = min((t for t in (t1, t2) if t), default=ts)
    auctions = (a.get("auctions") or []) + (cm.get("auctions") or [])
    best = lowest(auctions)
    with db.session() as c:
        saved = prices.store(c, house, best, ts, "api")
        new = set(best) - items.known_ids(c) if saved else set()
    msg = f"API data from {time.strftime('%H:%M', time.localtime(ts))}: {len(auctions)} auctions, {len(best)} items " + (
        "saved" if saved else "unchanged since last snapshot, not saved"
    )
    print(msg, flush=True)
    fetch_items(tok, sorted(new))
    return msg


def retry():
    """Refetch info for items whose info returned 404 before."""
    with db.session() as c:
        db.set_meta(c, "retried", int(time.time()))
        ids = items.missing_ids(c)
    fetch_items(token(), ids)
    with db.session() as c:
        left = len(items.missing_ids(c))
    return f"retried {len(ids)} items, {len(ids) - left} now have info"


def probe(args):
    """Print ruleset index / houses of a ruleset / raw shape of one house."""
    tok = token()
    if not args:
        path = "/data/wow/ruleset/index"
    elif len(args) == 1:
        path = f"/data/wow/ruleset/{args[0]}/auctions/"  # trailing slash required
    else:
        d = get(tok, f"/data/wow/ruleset/{args[0]}/auctions/{args[1]}")
        print({k: type(v).__name__ for k, v in (d or {}).items()})
        a = (d or {}).get("auctions")
        print(json.dumps(a[:2] if isinstance(a, list) else a, indent=1))
        return
    print(json.dumps(get(tok, path), indent=1)[:4000])
