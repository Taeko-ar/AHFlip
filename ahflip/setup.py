"""First run: the setup page asks the player's faction and ruleset, pre-filled from their AHFlip saved file.
An existing install (settings already saved) counts as set up."""

import re
from pathlib import Path

from . import config, db
from .sources import blizzard, scans

RULESETS = {1: "PvP", 2: "Normal", 3: "Roleplay", 15: "Roleplay PvP"}
FACTIONS = ("horde", "alliance")


def detect(path):
    """{faction, rs} guessed from an AHFlip saved file (the player's faction and realm name); missing keys if unknown."""
    if not path:
        return {}
    raw = Path(path).read_text(errors="replace")
    out = {}
    f = re.search(r'\["faction"\] = "(Horde|Alliance)"', raw)
    if f:
        out["faction"] = f.group(1).lower()
    r = re.search(r'\["realm"\] = "([^"]*)"', raw)
    if r:
        words = set(re.findall(r"[a-z]+", r.group(1).lower()))  # e.g. "CAMWOW US2 Realm 6 PvP"
        rp, pvp = bool(words & {"rp", "roleplay"}), "pvp" in words
        out["rs"] = 15 if rp and pvp else 3 if rp else 1 if pvp else 2
    return out


def state(c):
    s = db.settings(c)
    side = next((f for f in FACTIONS if s[f"house_{f}"] == s["house"]), "horde")
    return dict(
        done=bool(db.meta(c, "setup_done") or db.meta(c, "settings") is not None),
        detected=detect(scans.newest(s["addon_file"])),
        faction=side,
        rs=s["rs"],
        rulesets=RULESETS,
        wow=str(config.WOW) if config.WOW_FOUND else None,
        addons=str(config.ADDONS),
        files=scans.found_files(s),
        api=blizzard.configured(),
    )


def save(c, rs, faction):
    """Store the player's ruleset and faction (their faction's auction house becomes the selected one)."""
    rs = int(rs)
    if rs not in RULESETS or faction not in FACTIONS:
        raise ValueError("pick a ruleset and Horde or Alliance")
    s = db.settings(c)
    db.save_settings(c, {"rs": rs, "house": s[f"house_{faction}"]})
    db.set_meta(c, "setup_done", True)
    return state(c)
