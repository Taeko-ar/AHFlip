"""First run: the setup page asks the player's ruleset, pre-filled from their AHFlip saved file.
An existing install (settings already saved) counts as set up."""

import re
from pathlib import Path

from . import config, db
from .sources import blizzard, scans

RULESETS = {1: "PvP", 2: "Normal", 3: "Roleplay", 15: "Roleplay PvP"}


def detect(path):
    """{rs} guessed from an AHFlip saved file (the realm name); empty if unknown."""
    if not path:
        return {}
    raw = Path(path).read_text(errors="replace")
    out = {}
    r = re.search(r'\["realm"\] = "([^"]*)"', raw)
    if r:
        words = set(re.findall(r"[a-z]+", r.group(1).lower()))  # e.g. "CAMWOW US2 Realm 6 PvP"
        rp, pvp = bool(words & {"rp", "roleplay"}), "pvp" in words
        out["rs"] = 15 if rp and pvp else 3 if rp else 1 if pvp else 2
    return out


def state(c):
    s = db.settings(c)
    return dict(
        done=bool(db.meta(c, "setup_done") or db.meta(c, "settings") is not None),
        detected=detect(scans.newest(s["addon_file"])),
        rs=s["rs"],
        rulesets=RULESETS,
        wow=str(config.WOW) if config.WOW_FOUND else None,
        addons=str(config.ADDONS),
        files=scans.found_files(s),
        api=blizzard.configured(),
    )


def save(c, rs):
    """Store the player's ruleset; the global (Horde + Alliance) auction house becomes the selected one."""
    rs = int(rs)
    if rs not in RULESETS:
        raise ValueError("pick a ruleset")
    db.save_settings(c, {"rs": rs, "house": db.settings(c)["house_horde"]})
    db.set_meta(c, "setup_done", True)
    return state(c)
