"""Stage 2: probe — recover the structural schema from shape. Meaning-free.

Profiles any parsed JSON into a fused shape tree (repetition collapsed:
an array of 12,000 objects becomes one element-shape), fuses trees across
files (a single file under-determines the schema), and derives candidates:

  - collections: homogeneous arrays of objects (record types)
  - document leaves: long-text string leaves (content to reference, not
    decompose)

A scalar position is a document-leaf candidate when its TYPICAL string length
across every instance of that position (the median, which the chunker dispatch
needs) reaches LONG_TEXT_CHARS — not when a single outlier instance is long.
The probe tracks per-scalar string lengths through the fuse so the median is
available; `shape_to_jsonable` collapses that distribution to summary stats so
the persisted tree stays compact.

Candidates are observations, not decisions. "This collection is chat" is
a meaning judgment and belongs to the per-dataset mapping key.

Paths are RFC 6901 JSON pointers ('~' -> '~0', '/' -> '~1'); '*' marks the
fused array-element position.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LONG_TEXT_CHARS = 200  # typical string length at/above this = document-leaf candidate


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
        return "str"
    raise TypeError(f"unsupported scalar type: {type(v).__name__}")


def profile(v: Any) -> dict:
    """One value -> its shape signature.

    A scalar position carries the lengths of its string instances (`str_lens`)
    so the fuse can accumulate the full distribution and a typical-length
    judgment is available downstream; non-string scalars contribute nothing.
    """
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
    return {"t": "scalar", "kinds": {k}, "str_lens": [len(v)] if isinstance(v, str) else []}


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
            "str_lens": a.get("str_lens", []) + b.get("str_lens", []),
        }
    if t == "ragged":
        return {"t": "ragged", "kinds": a["kinds"] | b["kinds"]}
    raise ValueError(f"unknown shape type: {t!r}")


def probe_file(path: Path) -> dict:
    return profile(json.loads(path.read_text(encoding="utf-8")))


def fuse_files(paths: list[Path], *, content_only: bool = False) -> dict:
    """Fuse the shapes of many files into one tree. Order-independent.

    With `content_only`, fuse only files carrying a content-collection root
    (`is_content_file`) so a heterogeneous metadata file cannot ragged-out the
    recovered root."""
    pool = content_files(paths) if content_only else paths
    if not pool:
        raise ValueError("fuse_files: no files given")
    fused: dict | None = None
    for p in pool:
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
    typical_len: int     # median string length across instances — the dispatch signal


def typical_str_len(shape: dict) -> int:
    """Median length of a scalar position's string instances (0 if it has none).
    The median, not the max, decides prose-vs-short: a field is prose only when
    its values are *typically* long, never because one outlier instance is."""
    lens = shape.get("str_lens", [])
    return int(statistics.median(lens)) if lens else 0


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
    elif t == "scalar":
        typ = typical_str_len(shape)
        if typ >= LONG_TEXT_CHARS:
            docleaves.append(DocLeaf(pointer, typ))
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
        typ = typical_str_len(shape)
        tl = f" typical_len={typ}" if typ else ""
        return [f"{pad}{pointer}  {kinds}{tl}{opt}"]
    if t == "ragged":
        return [f"{pad}{pointer}  RAGGED({','.join(sorted(shape['kinds']))}){opt}"]
    raise ValueError(f"unknown shape type: {t!r}")


def shape_to_jsonable(shape: dict) -> dict:
    """Sets -> sorted lists, and a scalar's `str_lens` distribution -> compact
    summary stats (count/median/mean/max), so the persisted shape tree stays
    small and serializes deterministically."""
    out: dict = {}
    for k, v in shape.items():
        if k == "kinds":
            out[k] = sorted(v)
        elif k == "keys":
            out[k] = {kk: shape_to_jsonable(vv) for kk, vv in v.items()}
        elif k == "elem":
            out[k] = shape_to_jsonable(v) if v else None
        elif k == "str_lens":
            if v:
                out["str_len_stats"] = {
                    "count": len(v),
                    "median": int(statistics.median(v)),
                    "mean": round(statistics.mean(v), 1),
                    "max": max(v),
                }
        else:
            out[k] = v
    return out


# ---------- content-file scoping (fuse) ----------

def is_content_file(value: Any) -> bool:
    """True when a parsed file's top-level object carries a content-collection
    root (a non-empty array of objects). Excludes id-directory files (a flat
    dict keyed by id) and top-level-array files (`customers_data.json`) — fusing
    either into a content object ragged-outs the root and recovers nothing."""
    if not isinstance(value, dict):
        return False
    return any(isinstance(v, list) and v and isinstance(v[0], dict) for v in value.values())


def content_files(paths: list[Path]) -> list[Path]:
    return [p for p in paths if is_content_file(json.loads(p.read_text(encoding="utf-8")))]


def prose_leaf_pointers(paths: list[Path]) -> set[str]:
    """The set of content-leaf pointer patterns that are PROSE (typical length
    >= LONG_TEXT_CHARS), recovered by fusing the content files. A collection
    whose content leaf is in this set holds prose records (one chunk each); one
    not in it is a short structured record collection (packed toward the cap).
    Pointers use '*' for the array-element position, matching the mapping key's
    `content` patterns."""
    shape = fuse_files(paths, content_only=True)
    return {d.pointer for d in derive_candidates(shape)[1]}
