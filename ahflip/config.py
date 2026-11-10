"""Paths, constants and setting defaults."""

import glob
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("AH_DB") or ROOT / "ah.db")  # AH_DB: use another database (testing)
ENV_PATH = ROOT / ".env"  # BNET_CLIENT_ID / BNET_CLIENT_SECRET
STATIC = Path(__file__).resolve().parent / "web" / "static"

REGION = "us"  # shortcut: US only; EU players change this (API host and namespaces use it)
RETRY_HOURS = 24  # how often `web` retries items whose info returned 404
AUCTIONATOR_DAY0 = 18262  # Auctionator day 0 = 2020-01-01 UTC (checked: day 2505 = 2026-11-10)


def find_wow():
    """The World of Warcraft folder that has WoW Forever (_forever_) in it: the usual install places on
    Windows, in WSL (any drive) and on macOS. None if not found."""
    places = [os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES")]  # Windows env names ignore case
    candidates = [Path(p) / "World of Warcraft" for p in places if p]
    for pattern in ("/mnt/*/Program Files (x86)", "/mnt/*/Program Files", "/mnt/*/Games", "/mnt/*"):
        candidates += [Path(p) / "World of Warcraft" for p in sorted(glob.glob(pattern))]
    candidates += [Path("C:/Program Files (x86)/World of Warcraft"), Path("/Applications/World of Warcraft")]
    return next((p for p in candidates if (p / "_forever_").is_dir()), None)


_found = find_wow()
WOW_FOUND = _found is not None
WOW = _found or Path("/mnt/c/Program Files (x86)/World of Warcraft")  # fallback: the default Windows install, seen from WSL
SAVED = WOW / "_forever_" / "WTF" / "Account" / "*" / "SavedVariables"
ADDONS = WOW / "_forever_" / "Interface" / "AddOns"  # where the AHFlip addon folder goes

# Defaults. The web page can change them; changes are stored in ah.db (meta "settings").
DEFAULTS = {
    "cut": 0.05,  # Horde / Alliance AH cut
    "cut_goblin": 0.15,  # Blackwater (goblin) AH cut; one guide says 15%, not verified in game
    "min_listed": 3,  # Below usual / Rising: skip items usually listed fewer times than this (thin markets)
    "max_spread": 10,  # Below usual / Rising: skip items whose lowest price swung more than this many times over
    "flip_discount": 0.75,  # flip when current lowest <= 75% of usual price
    "min_snaps": 3,  # past snapshots needed before an item's "usual price" counts
    "hist_days": 7,  # usual price = median of past snapshots from this many days
    "min_profit": 0,  # hide deals below this profit per unit (copper)
    "snap_minutes": 10,  # web: auto API snapshot interval, 0 = off
    "rs": 1,  # ruleset: 1 PvP, 2 Normal, 3 Roleplay, 15 Roleplay PvP
    "house": 113,  # the auction house shown on the site (sidebar selector) and fetched from the API
    # Auction house ids per side on the PvP ruleset. Horde checked in game; Alliance / Blackwater (goblin)
    # follow the API's grouping (110/113/116), not verified.
    "house_horde": 113,
    "house_alliance": 110,
    "house_goblin": 116,
    # In-game scan files (globs; newest match wins). Written by WoW on /reload or logout.
    "addon_file": str(SAVED / "AHFlip.lua"),
    "scan_file": str(SAVED / "Auctionator.lua"),
    "scan_realm": "PvP",  # key in AUCTIONATOR_PRICE_DATABASE
}
LIMITS = {
    "cut": (0, 0.5),
    "cut_goblin": (0, 0.5),
    "min_listed": (0, 10**6),
    "max_spread": (1, 10**6),
    "flip_discount": (0.01, 1),
    "min_snaps": (1, 1000),
    "hist_days": (1, 365),
    "min_profit": (0, 10**9),
    "snap_minutes": (0, 1440),
    "rs": (1, 10**6),
    "house": (1, 10**6),
    "house_horde": (1, 10**6),
    "house_alliance": (1, 10**6),
    "house_goblin": (1, 10**6),
}
SIDES = ("horde", "alliance", "goblin")  # auction house sides; setting f"house_{side}" holds each id
