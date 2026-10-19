"""Field inventory of every file in every run folder of the review.

For a row file (.jsonl) each key path gets: the JSON types seen, and in how many rows it is
present / not null / not zero. "Not zero" = a number other than 0, a string, list or dict that
is not empty, or true. Under a list ("[]") a row counts when any element of it does.
For a manifest (.json, one object) the same three are 1 or 0.
Nothing but key names, types, counts and lengths is printed. eval_calls.jsonl is opened in C only.
Writes inventory.json beside this file and prints one table per file kind.
"""
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from folders import ALL, GROUP_OF, MAY_OPEN_EVAL_CALLS

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent


def jtype(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "nan" if v != v else "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "dict"
    return type(v).__name__


def nonzero(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v == v and v != 0
    return len(v) > 0


def walk(v, path, row):
    """row: path -> [types set, present, nonnull, nonzero, list lengths]"""
    slot = row.setdefault(path, [set(), False, False, False, []])
    slot[0].add(jtype(v))
    slot[1] = True
    slot[2] = slot[2] or v is not None
    slot[3] = slot[3] or nonzero(v)
    if isinstance(v, dict):
        for k, x in v.items():
            walk(x, path + "." + k if path else k, row)
    elif isinstance(v, list):
        slot[4].append(len(v))
        for x in v:
            walk(x, path + "[]", row)


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def inventory_objects(objs):
    agg = {}
    n = 0
    for obj in objs:
        n += 1
        row = {}
        if isinstance(obj, dict):
            for k, x in obj.items():
                walk(x, k, row)
        for path, (types, pres, nn, nz, lens) in row.items():
            a = agg.setdefault(path, {"types": set(), "present": 0, "nonnull": 0, "nonzero": 0,
                                      "lens": []})
            a["types"] |= types
            a["present"] += pres
            a["nonnull"] += nn
            a["nonzero"] += nz
            a["lens"].extend(lens)
    out = {}
    for path, a in agg.items():
        lens = sorted(a["lens"])
        out[path] = {"types": sorted(a["types"]), "present": a["present"],
                     "nonnull": a["nonnull"], "nonzero": a["nonzero"],
                     "len_min": lens[0] if lens else None,
                     "len_med": lens[len(lens) // 2] if lens else None,
                     "len_max": lens[-1] if lens else None}
    return n, out


def rows_of(p):
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def main():
    inv = {}
    for name, folder in ALL.items():
        files = {}
        for f in sorted(folder.iterdir()):
            if not f.is_file():
                continue
            st = f.stat()
            rec = {"bytes": st.st_size,
                   "mtime_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds")}
            if f.name == "eval_calls.jsonl" and name not in MAY_OPEN_EVAL_CALLS:
                rec.update(kind="not opened (gold rule)", n=None, paths={})
            elif f.suffix == ".jsonl":
                n, paths = inventory_objects(rows_of(f)) if st.st_size else (0, {})
                rec.update(kind="rows", n=n, paths=paths, sha256=digest(f))
            elif f.suffix == ".json":
                n, paths = inventory_objects([json.loads(f.read_text(encoding="utf-8"))])
                rec.update(kind="object", n=1, paths=paths, sha256=digest(f))
            else:
                rec.update(kind="other", n=None, paths={}, sha256=digest(f))
            files[f.name] = rec
        inv[name] = files
    (HERE / "inventory.json").write_text(json.dumps(inv, indent=1), encoding="utf-8")

    print("FILES PER FOLDER (bytes, rows, last written UTC)")
    for name, files in inv.items():
        print(f"  {name}  [{GROUP_OF[name]}]  {ALL[name].name}")
        for fname, rec in files.items():
            n = "" if rec["n"] is None else f"{rec['n']} rows" if rec["kind"] == "rows" else "1 object"
            print(f"      {fname:<34}{rec['bytes']:>12,} B  {n:<10} {rec['mtime_utc']}  {rec['kind']}")

    def kind_of(fname):
        if fname.startswith("code.") and fname.endswith(".diff"):
            return "code.*.diff"
        if fname.startswith("eval_manifest.json"):
            return fname
        return fname

    kinds = []
    for files in inv.values():
        for fname in files:
            k = kind_of(fname)
            if k not in kinds:
                kinds.append(k)

    names = list(ALL)
    for kind in kinds:
        cols = [n for n in names if any(kind_of(f) == kind for f in inv[n])]
        paths, types = [], defaultdict(set)
        for n in cols:
            for fname, rec in inv[n].items():
                if kind_of(fname) != kind:
                    continue
                for p, a in rec["paths"].items():
                    if p not in paths:
                        paths.append(p)
                    types[p] |= set(a["types"])
        print()
        print(f"=== {kind}   cell = present/not-null/not-zero of n rows ('-' = key path absent)")
        head = "  ".join(f"{n:>13}" for n in cols)
        print(f"  {'key path':<64} {'type':<16} {head}")
        ns = []
        for n in cols:
            recs = [rec for fname, rec in inv[n].items() if kind_of(fname) == kind]
            ns.append("+".join("x" if r["n"] is None else str(r["n"]) for r in recs))
        print(f"  {'(n rows)':<64} {'':<16} " + "  ".join(f"{x:>13}" for x in ns))
        for p in sorted(paths):
            cells = []
            for n in cols:
                hit = [rec["paths"][p] for fname, rec in inv[n].items()
                       if kind_of(fname) == kind and p in rec["paths"]]
                if not hit:
                    cells.append("-")
                else:
                    a = hit[0]
                    cells.append(f"{a['present']}/{a['nonnull']}/{a['nonzero']}")
            t = "|".join(sorted(types[p]))
            print(f"  {p:<64} {t:<16} " + "  ".join(f"{c:>13}" for c in cells))


if __name__ == "__main__":
    main()
