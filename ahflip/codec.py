"""Decoders for WoW SavedVariables data: Lua string literals and CBOR (Auctionator's price database)."""

import re
import struct

LUA_ESC = {b"n": 10, b"r": 13, b"t": 9, b"a": 7, b"b": 8, b"f": 12, b"v": 11, b"\\": 92, b'"': 34, b"'": 39, b"\n": 10}


def lua_str(b, i):
    """Decode the Lua string literal starting at b[i] (a quote). Returns (bytes, index after it).
    Lua \\ddd escapes are decimal."""
    i += 1
    out = bytearray()
    while True:
        ch = b[i : i + 1]
        if not ch:
            raise ValueError("unterminated Lua string")
        if ch == b'"':
            return bytes(out), i + 1
        if ch == b"\\":
            d = re.match(rb"\d{1,3}", b[i + 1 : i + 4])
            if d:
                out.append(int(d.group()))
                i += 1 + len(d.group())
            else:
                out.append(LUA_ESC[b[i + 1 : i + 2]])
                i += 2
        else:
            out += ch
            i += 1


def cbor(b, i=0):
    """Minimal CBOR decoder. Returns (value, next index). Byte-string map keys are decoded to str."""
    mt, ai = b[i] >> 5, b[i] & 31
    i += 1
    if ai < 24:
        n = ai
    elif ai <= 27:
        size = 1 << (ai - 24)
        n = int.from_bytes(b[i : i + size], "big")
        i += size
    elif ai == 31:
        n = None  # indefinite length, ends with 0xff
    else:
        raise ValueError(f"bad CBOR byte at {i - 1}")
    if mt == 0:
        return n, i
    if mt == 1:
        return -1 - n, i
    if mt in (2, 3):
        if n is None:
            parts = []
            while b[i] != 0xFF:
                p, i = cbor(b, i)
                parts.append(p)
            return (b"" if mt == 2 else "").join(parts), i + 1
        s = b[i : i + n]
        return (s if mt == 2 else s.decode()), i + n
    if mt in (4, 5):
        out = [] if mt == 4 else {}
        k = 0
        while (b[i] != 0xFF) if n is None else (k < n):
            v, i = cbor(b, i)
            if mt == 5:
                val, i = cbor(b, i)
                out[v.decode() if isinstance(v, bytes) else v] = val
            else:
                out.append(v)
            k += 1
        return out, i + (1 if n is None else 0)
    if mt == 7:
        if ai in (20, 21, 22, 23):
            return {20: False, 21: True}.get(ai), i
        fmt = {25: ">e", 26: ">f", 27: ">d"}.get(ai)
        if fmt:
            return struct.unpack(fmt, b[i - (1 << (ai - 24)) : i])[0], i
    raise ValueError(f"unsupported CBOR type {mt}/{ai}")
