"""Key paths, value types and counts of the files in run folders. NEVER a value.

    python keys_only.py <folder> [<folder> ...] [--depth N] [--files]

For every .json / .jsonl / .csv file in each folder: the union of key paths over all rows
(JSONL) or the document (JSON), with the Python type names seen at that path and, for JSONL,
on how many rows the path is present. Lists are walked through their elements as `[]`.
A dict whose keys look like data (more than --wide keys, or keys that are ids) is collapsed to
`{*}` so ids never print. No string, number or boolean value is ever printed.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

ID_LIKE = re.compile(r"(::|^\d+$|^[0-9a-f]{12,}$|/|\\|\s)")


def walk(obj, path: str, acc: "OrderedDict[str, dict]", depth: int, max_depth: int, wide: int) -> None:
    ent = acc.setdefault(path, {"types": set(), "n": 0})
    ent["types"].add(type(obj).__name__)
    ent["n"] += 1
    if depth >= max_depth:
        return
    if isinstance(obj, dict):
        keys = list(obj.keys())
        data_keyed = len(keys) > wide or (keys and sum(1 for k in keys if ID_LIKE.search(str(k))) > len(keys) / 2)
        if data_keyed:
            for v in list(obj.values())[:50]:
                walk(v, path + ".{*}", acc, depth + 1, max_depth, wide)
            return
        for k, v in obj.items():
            walk(v, f"{path}.{k}", acc, depth + 1, max_depth, wide)
    elif isinstance(obj, list):
        for v in obj[:200]:
            walk(v, path + "[]", acc, depth + 1, max_depth, wide)


def report(name: str, docs: list, max_depth: int, wide: int) -> None:
    acc: "OrderedDict[str, dict]" = OrderedDict()
    for d in docs:
        walk(d, "", acc, 0, max_depth, wide)
    print(f"--- {name}: {len(docs)} row(s)")
    for path, ent in acc.items():
        if not path:
            continue
        types = "|".join(sorted(ent["types"]))
        print(f"    {path.lstrip('.')} : {types} (x{ent['n']})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--depth", type=int, default=7)
    ap.add_argument("--wide", type=int, default=45)
    ap.add_argument("--files", action="store_true", help="list file names and sizes only")
    ap.add_argument("--only", default="", help="comma-separated file names to read")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    only = {x for x in args.only.split(",") if x}
    for folder in args.folders:
        p = Path(folder)
        print(f"\n=================== {p}")
        if p.is_file():
            files = [p]
        else:
            files = sorted(x for x in p.iterdir() if x.is_file())
            print("files: " + ", ".join(f"{x.name} ({x.stat().st_size:,} B)" for x in files))
            dirs = sorted(x.name for x in p.iterdir() if x.is_dir())
            if dirs:
                print("subfolders: " + ", ".join(dirs[:40]) + (" …" if len(dirs) > 40 else ""))
        if args.files:
            continue
        for f in files:
            if only and f.name not in only:
                continue
            try:
                if f.suffix == ".jsonl":
                    docs = []
                    with f.open(encoding="utf-8") as fh:
                        for line in fh:
                            line = line.strip()
                            if line:
                                docs.append(json.loads(line))
                    report(f.name, docs, args.depth, args.wide)
                elif f.suffix == ".json":
                    report(f.name, [json.loads(f.read_text(encoding="utf-8"))], args.depth, args.wide)
                elif f.suffix == ".csv":
                    with f.open(encoding="utf-8", newline="") as fh:
                        r = csv.reader(fh)
                        header = next(r, [])
                        n = sum(1 for _ in r)
                    print(f"--- {f.name}: {n} data row(s); columns: {', '.join(header)}")
            except Exception as exc:
                print(f"--- {f.name}: could not read ({exc!r})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
