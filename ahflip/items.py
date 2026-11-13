"""Item info (table item(id, name, sell, cls, sub); name/sell NULL when the API returned 404, cls/sub NULL
until an AHFlip scan saw the item) and the watchlist."""


def info(c):
    """({id: name}, {id: vendor sell price})"""
    names, sell = {}, {}
    for i, n, v in c.execute("select id, name, sell from item"):
        names[i], sell[i] = n, v
    return names, sell


def cats(c):
    """{id: (class, subclass)} for items with a category."""
    return {i: (k, s) for i, k, s in c.execute("select id, cls, sub from item where cls is not null")}


def save_cats(c, rows):
    """rows [(id, class, subclass)] from the game, for items already in the table (the scan's names add them)."""
    with c:
        c.executemany("update item set cls=?, sub=? where id=?", [(k, s, i) for i, k, s in rows])


def known_ids(c):
    return {r[0] for r in c.execute("select id from item")}


def missing_ids(c):
    return [r[0] for r in c.execute("select id from item where name is null")]


def save_info(c, rows):
    """rows: [(id, name, sell)]"""
    with c:
        c.executemany(
            "insert into item(id, name, sell) values(?,?,?) on conflict(id) do update set name=excluded.name, sell=excluded.sell",
            rows,
        )


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
    """rows [(id, name, sell|None)] from the game: added for unknown items; names fill items the API had no
    info for (404). The game's vendor price replaces the API's: the API is wrong for some Forever items
    (Iron Grenade: API 5s, game 1s 25c)."""
    with c:
        c.executemany(
            """insert into item(id, name, sell) values(?,?,?) on conflict(id) do update
                         set name = coalesce(item.name, excluded.name), sell = coalesce(excluded.sell, item.sell)""",
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
