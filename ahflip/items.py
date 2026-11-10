"""Item info (table item(id, name, sell); name/sell NULL when the API returned 404) and the watchlist."""


def info(c):
    """({id: name}, {id: vendor sell price})"""
    names, sell = {}, {}
    for i, n, v in c.execute("select id, name, sell from item"):
        names[i], sell[i] = n, v
    return names, sell


def known_ids(c):
    return {r[0] for r in c.execute("select id from item")}


def missing_ids(c):
    return [r[0] for r in c.execute("select id from item where name is null")]


def save_info(c, rows):
    """rows: [(id, name, sell)]"""
    with c:
        c.executemany("insert or replace into item values(?,?,?)", rows)


def resolve(c, v):
    """Item id from an id or an exact name (case-insensitive)."""
    v = str(v).strip()
    if v.isdigit():
        return int(v)
    rows = c.execute("select id from item where name = ? collate nocase", (v,)).fetchall()
    if len(rows) != 1:
        raise ValueError(f"{'no item' if not rows else 'several items'} named {v!r}; use the item id")
    return rows[0][0]


def fill_missing(c, rows):
    """rows [(id, name, sell|None)] from the game: added for unknown items, and fill items the API had no
    info for (404). Info the API did return is kept."""
    with c:
        c.executemany(
            """insert into item values(?,?,?) on conflict(id) do update
                         set name = excluded.name, sell = coalesce(excluded.sell, item.sell) where item.name is null""",
            [r for r in rows if r[1]],
        )


def watched(c):
    return {r[0] for r in c.execute("select item from watch")}


def set_watch(c, item, on):
    with c:
        if on:
            c.execute("insert or ignore into watch values(?)", (item,))
        else:
            c.execute("delete from watch where item=?", (item,))
