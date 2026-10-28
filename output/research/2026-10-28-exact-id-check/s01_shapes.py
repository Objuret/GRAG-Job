"""Print only the shape of the data files: keys, types, lengths, counts. No values."""
import json
import sys
from collections import Counter

ROOT = "C:/Coding/exjobbet/GRAG-Job"


def typ(v):
    if isinstance(v, list):
        inner = Counter(type(x).__name__ for x in v)
        return f"list[{dict(inner)}] len={len(v)}"
    if isinstance(v, dict):
        return f"dict keys={sorted(v.keys())}"
    if isinstance(v, str):
        return f"str len={len(v)}"
    return type(v).__name__


def show_jsonl(path, n=2):
    print(f"== {path}")
    rows = 0
    keys = Counter()
    first = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            rows += 1
            if isinstance(r, dict):
                keys.update(r.keys())
                if len(first) < n:
                    first.append({k: typ(v) for k, v in r.items()})
            else:
                keys.update([type(r).__name__])
                if len(first) < n:
                    first.append(typ(r))
    print("rows", rows)
    print("keys", dict(keys))
    for x in first:
        print("  sample shape:", x)


show_jsonl(f"{ROOT}/data/questions.jsonl")
show_jsonl(f"{ROOT}/data/gold100.jsonl")
show_jsonl(f"{ROOT}/data/answerable715.jsonl")
