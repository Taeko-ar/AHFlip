"""ahflip: WoW Forever auction house tracker. Stdlib only.

Layout (one concern per module; functions that touch the DB take a sqlite3 connection `c`):
  config.py        paths, constants, setting defaults and limits
  db.py            connection, schema + migrations, meta key/value, settings
  gold.py          gold <-> copper
  codec.py         Lua string literal + CBOR decoding (Auctionator's saved data)
  prices.py        price snapshots: store (deduped), latest, history, per-item stats
  items.py         item names/vendor prices, watchlist
  deals.py         deal rules (pure) + loading them from the DB
  market.py        Market page views: items vs their usual price, daily trend
  ledger.py        the user's own buys/sells
  sources/         where snapshots come from: blizzard.py (web API), addon.py (AHFlip scans, trades, names),
                   auctionator.py (Auctionator scans), scans.py (shared import flow)
  web/             local website: server.py (HTTP), routes.py (JSON API), jobs.py (background work), static/
  cli.py           command line (ah.py is a thin wrapper)
"""
