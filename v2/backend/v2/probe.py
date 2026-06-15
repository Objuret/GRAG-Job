"""Stage 2: probe — recover the structural schema from shape. Meaning-free.

Profiles any parsed JSON into a fused shape tree (repetition collapsed:
an array of 12,000 objects becomes one element-shape), fuses trees across
files (a single file under-determines the schema), and derives candidates:

  - collections: homogeneous arrays of objects (record types)
  - document leaves: long-text string leaves (content to reference, not
    decompose)

Candidates are observations, not decisions. "This collection is chat" is
a meaning judgment and belongs to the per-dataset mapping key.

Paths are RFC 6901 JSON pointers ('~' -> '~0', '/' -> '~1'); '*' marks the
fused array-element position.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LONG_TEXT_CHARS = 200  # string longer than this = document-leaf candidate


def escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


# ---------- shape profiling ----------

def _scalar_kind(v: Any) -> str:
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
    raise TypeError(f"unsupported scalar type: {type(v).__name__}")


def profile(v: Any) -> dict:
    """One value -> its shape signature."""
    if isinstance(v, dict):
        return {"t": "object", "keys": {k: profile(val) for k, val in v.items()}}
    if isinstance(v, list):
        if not v:
            return {"t": "array", "len_min": 0, "len_max": 0, "elem": None}
        fused = None
        for item in v:
            fused = fuse(fused, profile(item))
        return {"t": "array", "len_min": len(v), "len_max": len(v), "elem": fused}
    k = _scalar_kind(v)
    return {"t": "scalar", "kinds": {k}, "maxlen": len(v) if isinstance(v, str) else 0}


def fuse(a: dict | None, b: dict | None) -> dict:
    """Merge two shape signatures (array-element fusion and cross-file fusion)."""
    if a is None:
        return b  # type: ignore[return-value]
    if b is None:
        return a
    if a["t"] != b["t"]:
        kinds: set[str] = set()
        for s in (a, b):
            kinds |= s.get("kinds", {s["t"]})
        return {"t": "ragged", "kinds": kinds}
    t = a["t"]
    if t == "object":
        keys: dict[str, dict] = {}
        for k in set(a["keys"]) | set(b["keys"]):
            sa, sb = a["keys"].get(k), b["keys"].get(k)
            if sa and sb:
                merged = fuse(sa, sb)
                if sa.get("optional") or sb.get("optional"):
                    merged["optional"] = True
            else:
                merged = dict(sa or sb)  # type: ignore[arg-type]
                merged["optional"] = True
            keys[k] = merged
        return {"t": "object", "keys": keys}
    if t == "array":
        return {
            "t": "array",
            "len_min": min(a["len_min"], b["len_min"]),
            "len_max": max(a["len_max"], b["len_max"]),
            "elem": fuse(a.get("elem"), b.get("elem")),
        }
    if t == "scalar":
        return {
            "t": "scalar",
            "kinds": a["kinds"] | b["kinds"],
            "maxlen": max(a.get("maxlen", 0), b.get("maxlen", 0)),
        }
    if t == "ragged":
        return {"t": "ragged", "kinds": a["kinds"] | b["kinds"]}
    raise ValueError(f"unknown shape type: {t!r}")


def probe_file(path: Path) -> dict:
    return profile(json.loads(path.read_text(encoding="utf-8")))


def fuse_files(paths: list[Path]) -> dict:
    """Fuse the shapes of many files into one tree. Order-independent."""
    if not paths:
        raise ValueError("fuse_files: no files given")
    fused: dict | None = None
    for p in paths:
        fused = fuse(fused, probe_file(p))
    return fused  # type: ignore[return-value]


# ---------- candidates + rendering ----------

@dataclass(frozen=True)
class Collection:
    pointer: str
    length: str          # "n" or "min-max" across files
    keys: tuple[str, ...]


@dataclass(frozen=True)
class DocLeaf:
    pointer: str
    maxlen: int


def derive_candidates(shape: dict, pointer: str = "") -> tuple[list[Collection], list[DocLeaf]]:
    collections: list[Collection] = []
    docleaves: list[DocLeaf] = []
    t = shape["t"]
    if t == "object":
        for k, sub in shape["keys"].items():
            c, d = derive_candidates(sub, f"{pointer}/{escape_pointer_token(k)}")
            collections += c
            docleaves += d
    elif t == "array":
        elem = shape.get("elem")
        if elem and elem["t"] == "object":
            n = (str(shape["len_min"]) if shape["len_min"] == shape["len_max"]
                 else f"{shape['len_min']}-{shape['len_max']}")
            collections.append(Collection(pointer, n, tuple(elem["keys"].keys())))
        if elem:
            c, d = derive_candidates(elem, f"{pointer}/*")
            collections += c
            docleaves += d
    elif t == "scalar" and "str_long" in shape["kinds"]:
        docleaves.append(DocLeaf(pointer, shape.get("maxlen", 0)))
    return collections, docleaves


def render_tree(shape: dict, pointer: str = "", depth: int = 0) -> list[str]:
    pad = "  " * depth
    opt = " [opt]" if shape.get("optional") else ""
    t = shape["t"]
    if t == "object":
        lines = [f"{pad}{pointer or '/'}  object ({len(shape['keys'])} keys){opt}"]
        for k, sub in shape["keys"].items():
            lines += render_tree(sub, f"{pointer}/{escape_pointer_token(k)}", depth + 1)
        return lines
    if t == "array":
        elem = shape.get("elem")
        et = elem["t"] if elem else "empty"
        n = (str(shape["len_min"]) if shape["len_min"] == shape["len_max"]
             else f"{shape['len_min']}-{shape['len_max']}")
        lines = [f"{pad}{pointer}  array[{n}] of {et}{opt}"]
        if elem:
            lines += render_tree(elem, f"{pointer}/*", depth + 1)
        return lines
    if t == "scalar":
        kinds = ",".join(sorted(shape["kinds"]))
        ml = f" maxlen={shape['maxlen']}" if shape.get("maxlen") else ""
        return [f"{pad}{pointer}  {kinds}{ml}{opt}"]
    if t == "ragged":
        return [f"{pad}{pointer}  RAGGED({','.join(sorted(shape['kinds']))}){opt}"]
    raise ValueError(f"unknown shape type: {t!r}")


def shape_to_jsonable(shape: dict) -> dict:
    """Sets -> sorted lists so the shape tree serializes deterministically."""
    out: dict = {}
    for k, v in shape.items():
        if k == "kinds":
            out[k] = sorted(v)
        elif k == "keys":
            out[k] = {kk: shape_to_jsonable(vv) for kk, vv in v.items()}
        elif k == "elem":
            out[k] = shape_to_jsonable(v) if v else None
        else:
            out[k] = v
    return out
