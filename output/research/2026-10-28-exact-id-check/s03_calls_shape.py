"""Print the keys of the `calls` entries of each run's rows, and of nested dicts, with types. No values."""
import json
from collections import Counter

ROOT = "C:/Coding/exjobbet/GRAG-Job/output/k=chars"
RUNS = [
    "artefact_v4__gold100__cb72000__20261023T021439Z",
    "lucene__gold100__cb72000__20261008T234209Z",
    "vector__gold100__cb72000__20261017T061242Z",
    "artefact_v4__answerable715__cb72000__20261025T211532Z",
    "lucene__answerable715__cb72000__20261023T112745Z",
    "vector__answerable715__cb72000__20261024T004317Z",
]


def walk(prefix, v, out):
    if isinstance(v, dict):
        for k, x in v.items():
            walk(f"{prefix}.{k}", x, out)
    elif isinstance(v, list):
        out[prefix + "[]"] += 1
        for x in v[:3]:
            walk(prefix + "[]", x, out)
    else:
        out[f"{prefix}:{type(v).__name__}"] += 1


for run in RUNS:
    out = Counter()
    n = 0
    for line in open(f"{ROOT}/{run}/arm_outputs.jsonl", encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        n += 1
        walk("calls", r.get("calls"), out)
        if n >= 20:
            break
    print("==", run)
    for k in sorted(out):
        print("  ", k, out[k])
