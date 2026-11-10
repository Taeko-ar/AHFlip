"""Background work for the web server: one network job at a time, plus a scheduler thread that
imports new in-game scans, takes auto API snapshots and retries missing item info."""

import sys
import threading
import time

from .. import config, db, prices
from ..sources import blizzard, scans

JOB = threading.Lock()  # one network job (snapshot or retry) at a time
STATE = {"job": None, "error": None, "last": None}  # shown in /api/status


def stamp(msg):
    return f"{time.strftime('%H:%M')} {msg}"


def run_job(name, fn):
    """Run fn in a thread unless another job runs. Returns whether it started."""
    if not JOB.acquire(blocking=False):
        return False

    def work():
        STATE["job"] = name
        try:
            STATE["last"] = stamp(fn())
            STATE["error"] = None
        except Exception as e:
            STATE["error"] = stamp(f"{name} failed: {e}")
            print(STATE["error"], file=sys.stderr, flush=True)
        finally:
            STATE["job"] = None
            JOB.release()

    threading.Thread(target=work, daemon=True).start()
    return True


def start_snapshot(s):
    return run_job("snapshot", lambda: blizzard.snap(s["rs"], s["house"]))


def start_retry():
    return run_job("retry missing item info", blizzard.retry)


def check_scans(s):
    """Import in-game scan files that changed. Local and quick, so not behind JOB."""
    for src, path in scans.changed(s):
        try:
            STATE["last"] = stamp(scans.import_one(s, src, path))
        except Exception as e:
            STATE["error"] = stamp(f"{scans.LABELS[src]} import failed: {e}")
            scans.mark_seen(src, path)


def scheduler():
    while True:
        time.sleep(5)
        try:
            with db.session() as c:
                s = db.settings(c)
                last = db.meta(c, f"attempt:{s['house']}") or prices.latest(c, s["house"]) or 0
                retried = db.meta(c, "retried", 0)
            check_scans(s)
            if not blizzard.configured():
                continue  # no API keys: in-game scans only
            now = time.time()
            if s["snap_minutes"] and now - last >= s["snap_minutes"] * 60:
                start_snapshot(s)
            elif now - retried >= config.RETRY_HOURS * 3600:
                start_retry()
        except Exception as e:
            print(f"scheduler: {e}", file=sys.stderr, flush=True)
