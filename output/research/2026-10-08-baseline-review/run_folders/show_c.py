"""Print a C file (made-up question, free to read) with long strings shortened.

    python show_c.py <folder name> <file> [max string length]
"""
import json
import sys

from folders import ALL

sys.stdout.reconfigure(encoding="utf-8")
name, fname = sys.argv[1], sys.argv[2]
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 110
assert name.startswith("C."), "only C is free to print"


def short(v, depth=0):
    if isinstance(v, dict):
        return {k: short(x, depth + 1) for k, x in v.items()}
    if isinstance(v, list):
        if len(v) > 6 and all(not isinstance(x, (dict, list)) for x in v):
            return [short(x) for x in v[:3]] + [f"... {len(v)} items ..."] + [short(x) for x in v[-2:]]
        if len(v) > 6:
            return [short(v[0], depth + 1), f"... {len(v)} items ..."]
        return [short(x, depth + 1) for x in v]
    if isinstance(v, str) and len(v) > limit:
        return f"<str {len(v)} chars> " + v[:limit]
    return v


p = ALL[name] / fname
text = p.read_text(encoding="utf-8")
if fname.endswith(".jsonl"):
    for i, line in enumerate(x for x in text.splitlines() if x.strip()):
        print(f"--- line {i}")
        print(json.dumps(short(json.loads(line)), indent=1, ensure_ascii=False))
else:
    print(json.dumps(short(json.loads(text)), indent=1, ensure_ascii=False))
