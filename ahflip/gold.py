"""Gold amounts. Everything is stored and computed in copper (1g = 100s = 10000c)."""

import re


def parse_gold(s):
    """'1g 20s 5c' / '45s' / '130' (plain number = copper) -> copper."""
    s = str(s).strip().lower()
    if not re.fullmatch(r"(\d+\s*[gsc]?\s*)+", s):
        raise ValueError(f"bad gold amount {s!r}, use e.g. 1g 20s 5c")
    mult = {"g": 10000, "s": 100, "c": 1, "": 1}
    return sum(int(n) * mult[u] for n, u in re.findall(r"(\d+)\s*([gsc]?)", s))


def fmt(c):
    return f"{c // 10000}g {c // 100 % 100:02d}s {c % 100:02d}c"
