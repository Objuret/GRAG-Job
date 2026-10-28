"""Print only the shape of each final run's arm_outputs.jsonl: keys, types, counts. No values."""
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


def typ(v):
    if isinstance(v, list):
        inner = Counter(type(x).__name__ for x in v)
        return f"list[{','.join(sorted(inner))}]"
    if isinstance(v, dict):
        return f"dict[{len(v)} keys]"
    if isinstance(v, str):
        return "str"
    return type(v).__name__


for run in RUNS:
    path = f"{ROOT}/{run}/arm_outputs.jsonl"
    rows = 0
    keys = Counter()
    shapes = {}
    ids = Counter()
    meta_keys = Counter()
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        rows += 1
        keys.update(r.keys())
        for k, v in r.items():
            shapes.setdefault(k, Counter())[typ(v)] += 1
        qid = r.get("question_id") or r.get("id")
        ids[qid] += 1
        if isinstance(r.get("meta"), dict):
            meta_keys.update(r["meta"].keys())
    print(f"== {run}")
    print("  rows", rows, "distinct question ids", len(ids), "max repeats", max(ids.values()))
    for k in keys:
        print(f"  key {k}: {dict(shapes[k])}")
    print("  meta keys:", sorted(meta_keys.keys()))
