"""Command line. Run through ah.py: `python3 ah.py <command>`."""

import argparse
import sys
import time
import unittest

from . import config, db, prices
from .deals import load_deals
from .gold import fmt


def deals(house):
    with db.session() as c:
        s = {**db.settings(c), "house": house}
        ts, rows = load_deals(c, s)
        if ts is None:
            sys.exit("no snapshots yet, run snap or import first")
        print(
            f"{prices.count(c, house)} snapshots, latest {time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))} "
            f"({prices.source(c, house, ts)})"
        )
    for d in rows[:40]:
        print(
            f"{d['kind']:6} {str(d['name'] or d['item']):40.40} buy<={fmt(d['buy']):14} worth {fmt(d['worth']):14} "
            f"+{fmt(d['profit'])}/u  qty {d['qty']}"
            + (f"  profitable {d['units']} = +{fmt(d['total'])}" if d["units"] is not None else "")
        )


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="ah.py",
        description="WoW Forever auction house tracker. Don't run snap/import while web is running: both write ah.db.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("web", help="local website (deals, search, watchlist, ledger, settings)").add_argument(
        "port", nargs="?", type=int, default=8000
    )
    sub.add_parser("import", help="import the last in-game scans (AHFlip addon, Auctionator)")
    sp = sub.add_parser("probe", help="show rulesets / houses of RULESET / raw shape of one HOUSE")
    sp.add_argument("ids", nargs="*", type=int)
    sp = sub.add_parser("snap", help="save an API snapshot (+ item info for new items)")
    sp.add_argument("ruleset", type=int)
    sp.add_argument("house", type=int)
    sub.add_parser("deals", help="list deals from saved snapshots").add_argument("house", type=int)
    sub.add_parser("test", help="run the tests in tests/, no network")
    a = p.parse_args(argv)

    if a.cmd == "web":
        from .web.server import serve

        serve(a.port)
    elif a.cmd == "import":
        from .sources import scans

        with db.session() as c:
            s = db.settings(c)
        for src, (key, _) in scans.SOURCES.items():
            path = scans.newest(s[key])
            if not path:
                print(f"{scans.LABELS[src]}: no file matches {s[key]}")
            elif "already" in (msg := scans.import_one(s, src, path)):
                print(msg)
    elif a.cmd == "probe":
        from .sources import blizzard

        blizzard.probe(a.ids)
    elif a.cmd == "snap":
        from .sources import blizzard

        blizzard.snap(a.ruleset, a.house)
    elif a.cmd == "deals":
        deals(a.house)
    else:  # "test" (argparse only accepts the commands above)
        suite = unittest.defaultTestLoader.discover(str(config.ROOT / "tests"), top_level_dir=str(config.ROOT))
        sys.exit(not unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful())
