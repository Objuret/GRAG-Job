"""Which dicts in the row files carry the same keys in every row (a schema) and which carry
keys that change from row to row (data used as keys). Prints counts; a key name is printed
only where every dict at that path has the same key set. No value is printed."""
import json
import sys
from collections import defaultdict

from folders import ALL, MAY_OPEN_EVAL_CALLS

sys.stdout.reconfigure(encoding="utf-8")


def walk(v, path, seen):
    if isinstance(v, dict):
        seen[path].append(tuple(sorted(v)))
        for k, x in v.items():
            walk(x, path + "." + k if path else k, seen)
    elif isinstance(v, list):
        for x in v:
            walk(x, path + "[]", seen)


def collapse(path, dynamic):
    """Rewrite a path so every key under a data-keyed dict reads {*}."""
    return path


for name, folder in ALL.items():
    for f in sorted(folder.iterdir()):
        if f.suffix != ".jsonl" or f.stat().st_size == 0:
            continue
        if f.name == "eval_calls.jsonl" and name not in MAY_OPEN_EVAL_CALLS:
            print(f"== {name} {f.name}: not opened (gold rule)")
            continue
        seen = defaultdict(list)
        n = 0
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    walk(json.loads(line), "", seen)
                    n += 1
        print(f"== {name} {f.name}: {n} rows")
        for path in sorted(seen):
            sets = seen[path]
            distinct_sets = set(sets)
            keys = set(k for s in sets for k in s)
            label = path or "<row>"
            if len(distinct_sets) == 1:
                print(f"   {label}: {len(sets)} dicts, 1 key set, {len(keys)} keys")
            else:
                sizes = sorted(len(s) for s in sets)
                print(f"   {label}: {len(sets)} dicts, {len(distinct_sets)} key sets, "
                      f"{len(keys)} distinct keys, keys per dict {sizes[0]}..{sizes[-1]}  <-- VARIES")
