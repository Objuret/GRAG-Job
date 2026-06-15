"""v2 shape-probe prototype — dataset-agnostic structural profiler.

Walks any parsed JSON and emits a FUSED shape tree (repetition collapsed),
annotated with JSON-pointer paths, plus derived CANDIDATES:
  - collections   : homogeneous arrays of objects (record types)
  - document leaves: long-text string leaves (content to reference, not decompose)

Pure structure. Zero dataset-specific names. This is the probe described in
the v2 design: it describes shape + candidates, it does NOT decide meaning.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LONG_TEXT_CHARS = 200          # string longer than this = document-leaf candidate
SCALAR_KINDS = ("null", "bool", "int", "float", "str")


def scalar_kind(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str_long" if len(v) > LONG_TEXT_CHARS else "str"
    return "unknown"


def fuse(a: dict, b: dict) -> dict:
    """Merge two shape signatures into one (for array-element fusion)."""
    if a is None:
        return b
    if a["t"] != b["t"]:
        kinds = set()
        for s in (a, b):
            kinds |= s.get("kinds", {s["t"]})
        return {"t": "ragged", "kinds": kinds}
    t = a["t"]
    if t == "object":
        keys = {}
        all_k = set(a["keys"]) | set(b["keys"])
        for k in all_k:
            sa, sb = a["keys"].get(k), b["keys"].get(k)
            if sa and sb:
                merged = fuse(sa, sb)
            else:
                merged = sa or sb
                merged = {**merged, "optional": True}
            if k not in a["keys"] or k not in b["keys"]:
                merged["optional"] = True
            keys[k] = merged
        return {"t": "object", "keys": keys}
    if t == "array":
        return {"t": "array",
                "len_min": min(a["len_min"], b["len_min"]),
                "len_max": max(a["len_max"], b["len_max"]),
                "elem": fuse(a.get("elem"), b.get("elem")) if a.get("elem") and b.get("elem")
                        else a.get("elem") or b.get("elem")}
    if t == "scalar":
        return {"t": "scalar", "kinds": a["kinds"] | b["kinds"],
                "maxlen": max(a.get("maxlen", 0), b.get("maxlen", 0))}
    return a


def profile(v) -> dict:
    if isinstance(v, dict):
        return {"t": "object", "keys": {k: profile(val) for k, val in v.items()}}
    if isinstance(v, list):
        if not v:
            return {"t": "array", "len_min": 0, "len_max": 0, "elem": None}
        fused = None
        for item in v:
            fused = fuse(fused, profile(item)) if fused else profile(item)
        return {"t": "array", "len_min": len(v), "len_max": len(v), "elem": fused}
    k = scalar_kind(v)
    return {"t": "scalar", "kinds": {k}, "maxlen": len(v) if isinstance(v, str) else 0}


def kinds_str(s: dict) -> str:
    if s["t"] == "scalar":
        ks = ",".join(sorted(s["kinds"]))
        ml = f" maxlen={s['maxlen']}" if s.get("maxlen") else ""
        return f"{ks}{ml}"
    if s["t"] == "ragged":
        return "RAGGED(" + ",".join(sorted(s["kinds"])) + ")"
    return s["t"]


def render(s: dict, path: str, out: list, collections: list, docleaves: list, depth: int = 0):
    pad = "  " * depth
    opt = " [opt]" if s.get("optional") else ""
    if s["t"] == "object":
        out.append(f"{pad}{path or '/'}  object ({len(s['keys'])} keys){opt}")
        for k, sub in s["keys"].items():
            render(sub, f"{path}/{k}", out, collections, docleaves, depth + 1)
    elif s["t"] == "array":
        elem = s.get("elem")
        et = elem["t"] if elem else "empty"
        n = s["len_min"] if s["len_min"] == s["len_max"] else f"{s['len_min']}-{s['len_max']}"
        out.append(f"{pad}{path}  array[{n}] of {et}{opt}")
        if elem and elem["t"] == "object":
            collections.append((path, n, list(elem["keys"].keys())))
        if elem:
            render(elem, f"{path}/*", out, collections, docleaves, depth + 1)
    elif s["t"] == "scalar":
        out.append(f"{pad}{path}  {kinds_str(s)}{opt}")
        if "str_long" in s["kinds"]:
            docleaves.append((path, s.get("maxlen", 0)))
    else:
        out.append(f"{pad}{path}  {kinds_str(s)}{opt}")


def main():
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "backend/data/raw/Salesforce__HERB/products/PitchForce.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    shape = profile(data)

    out, collections, docleaves = [], [], []
    render(shape, "", out, collections, docleaves)

    print(f"=== SHAPE TREE: {p.name} ===")
    print("\n".join(out))

    print("\n=== CANDIDATE COLLECTIONS (homogeneous arrays of objects = record types) ===")
    for path, n, keys in collections:
        print(f"  {path}  (n={n})  keys: {keys}")

    print("\n=== CANDIDATE DOCUMENT LEAVES (long-text, str > %d chars) ===" % LONG_TEXT_CHARS)
    seen = set()
    for path, ml in docleaves:
        if path not in seen:
            seen.add(path)
            print(f"  {path}  (maxlen ~{ml})")


if __name__ == "__main__":
    main()
