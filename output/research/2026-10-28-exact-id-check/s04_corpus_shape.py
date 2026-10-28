"""Print the key-path tree of the HERB corpus files with value types and counts. No values."""
import json
import glob
from collections import Counter

ROOT = "C:/Coding/exjobbet/GRAG-Job/data/corpus/Salesforce__HERB"


def walk(prefix, v, out):
    if isinstance(v, dict):
        out[prefix + "{}"] += 1
        many = len(v) > 20
        for k, x in v.items():
            walk(f"{prefix}.<key>" if many else f"{prefix}.{k}", x, out)
    elif isinstance(v, list):
        out[prefix + "[]"] += 1
        for x in v:
            walk(prefix + "[]", x, out)
    else:
        out[f"{prefix}:{type(v).__name__}"] += 1


for group in ("metadata/*.json", "products/*.json"):
    out = Counter()
    files = sorted(glob.glob(f"{ROOT}/{group}"))
    for fp in files:
        d = json.load(open(fp, encoding="utf-8"))
        name = fp.replace("\\", "/").split("/")[-1] if group.startswith("metadata") else "<product>"
        walk(name, d, out)
    print("==", group, len(files), "files")
    for k in sorted(out):
        # collapse dict keys that look like ids (many distinct keys) by printing only the count
        print("  ", k, out[k])
