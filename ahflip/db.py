"""SQLite connection, schema, meta key/value store and settings."""

import contextlib
import json
import sqlite3

from . import config
from .gold import parse_gold

SCHEMA = """
    create table if not exists price(ts int, house int, item int, min int, qty int);
    create index if not exists price_hi on price(house, item);
    create index if not exists price_ht on price(house, ts);
    create table if not exists item(id int primary key, name text, sell int);
    create table if not exists meta(k text primary key, v text);
    create table if not exists watch(item int primary key);
    create table if not exists depth(house int, ts int, item int, price int, qty int);
    create index if not exists depth_hi on depth(house, item);
    create table if not exists ledger(id integer primary key, ts int, kind text, item int, qty int, price int, note text);
"""


def init(c):
    """Create tables and run migrations. Safe to call on every connect."""
    c.executescript(SCHEMA)
    if "src" not in [r[1] for r in c.execute("pragma table_info(price)")]:
        with c:  # snapshots before this column existed all came from the API
            c.execute("alter table price add column src text default 'api'")
    if "src" not in [r[1] for r in c.execute("pragma table_info(ledger)")]:
        with c:  # 'manual' (website form) or 'addon' (logged in game); addon imports were noted 'AHFlip' before
            c.execute("alter table ledger add column src text default 'manual'")
            c.execute("update ledger set src='addon', note='' where note='AHFlip'")
    return c


def connect():
    return init(sqlite3.connect(config.DB_PATH, timeout=30))


@contextlib.contextmanager
def session():
    """`with db.session() as c:` opens and always closes a connection. Keep it short: hold no
    connection across network calls, so the web server stays writable."""
    c = connect()
    try:
        yield c
    finally:
        c.close()


def meta(c, k, default=None):
    r = c.execute("select v from meta where k=?", (k,)).fetchone()
    return json.loads(r[0]) if r else default


def set_meta(c, k, v):
    with c:
        c.execute("insert or replace into meta values(?,?)", (k, json.dumps(v)))


def settings(c):
    return {**config.DEFAULTS, **meta(c, "settings", {})}


def house_cut(s):
    """AH cut of the selected auction house: the goblin (Blackwater) house takes more."""
    return s["cut_goblin"] if s["house"] == s["house_goblin"] else s["cut"]


def save_settings(c, new):
    s = settings(c)
    for k, v in new.items():
        if k not in config.DEFAULTS:
            raise ValueError(f"unknown setting {k}")
        if k == "min_profit" and isinstance(v, str):
            v = parse_gold(v)
        v = type(config.DEFAULTS[k])(v)
        lo, hi = config.LIMITS.get(k, (v, v))
        if not lo <= v <= hi or (k == "snap_minutes" and 0 < v < 5):
            raise ValueError(f"{k} must be between {lo} and {hi}" + (" (0 or at least 5)" if k == "snap_minutes" else ""))
        s[k] = v
    set_meta(c, "settings", s)
    return s
