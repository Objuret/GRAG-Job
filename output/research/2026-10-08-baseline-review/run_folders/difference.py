"""Key paths by folder group, from inventory.json: what C has and A lacks, and what any of
A, B, D has and C lacks. A path counts for a group when any folder of the group has it."""
import json
import sys
from collections import defaultdict
from pathlib import Path

from folders import GROUP_OF

sys.stdout.reconfigure(encoding="utf-8")
inv = json.loads((Path(__file__).resolve().parent / "inventory.json").read_text(encoding="utf-8"))


def kind_of(fname):
    return "code.*.diff" if fname.startswith("code.") and fname.endswith(".diff") else fname


paths = defaultdict(lambda: defaultdict(set))      # kind -> group -> paths
where = defaultdict(lambda: defaultdict(set))      # kind -> path -> folders
for name, files in inv.items():
    for fname, rec in files.items():
        for p in rec["paths"]:
            paths[kind_of(fname)][GROUP_OF[name]].add(p)
            where[kind_of(fname)][p].add(name)


def leaves(ps):
    """Drop a path when a longer one under it is listed, so only the leaves are shown."""
    ps = sorted(ps)
    return [p for p in ps if not any(q != p and (q.startswith(p + ".") or q.startswith(p + "[")) for q in ps)]


def group_by_head(ps, depth):
    out = defaultdict(list)
    for p in ps:
        parts = p.replace("[]", "[].").replace("..", ".").strip(".").split(".")
        out[".".join(parts[:depth])].append(p)
    return out


for kind in ("arm_outputs.jsonl", "run_manifest.json", "eval_results.jsonl", "eval_manifest.json", "eval_calls.jsonl"):
    g = paths[kind]
    c, a, b, d = g.get("C", set()), g.get("A", set()), g.get("B", set()), g.get("D", set())
    print("=" * 110)
    print(f"{kind}: key paths  A {len(a)}  B {len(b)}  C {len(c)}  D {len(d)}")
    only_c = c - a
    print(f"  in C, not in A: {len(only_c)} paths ({len(leaves(only_c))} leaves)")
    for head, ps in sorted(group_by_head(leaves(only_c), 2).items()):
        folders = sorted(set(f for p in ps for f in where[kind][p] if f.startswith("C.")))
        tails = [p[len(head):].lstrip(".") or "(itself)" for p in ps]
        print(f"     {head:<34} {len(ps):>3} leaves  in {','.join(folders)}")
        print(f"         {', '.join(tails)}")
    for label, other in (("A", a), ("B", b), ("D", d)):
        gone = other - c
        print(f"  in {label}, not in C: {len(gone)} paths ({len(leaves(gone))} leaves)")
        for head, ps in sorted(group_by_head(leaves(gone), 2).items()):
            folders = sorted(set(f for p in ps for f in where[kind][p] if f.startswith(label + ".")))
            tails = [p[len(head):].lstrip(".") or "(itself)" for p in ps]
            print(f"     {head:<34} {len(ps):>3} leaves  in {','.join(folders)}")
            print(f"         {', '.join(tails)}")
    print(f"  in A, not in B: {sorted(leaves(a - b))}")
    print(f"  in B, not in A: {sorted(leaves(b - a))}")

print("=" * 110)
print("C folder by folder: key paths one C folder has and another lacks (arm_outputs.jsonl, run_manifest.json; leaves)")
for kind in ("arm_outputs.jsonl", "run_manifest.json"):
    per = {n: set(rec["paths"]) for n, files in inv.items() if n.startswith("C.") for fname, rec in files.items() if kind_of(fname) == kind}
    allc = set().union(*per.values())
    for n, ps in per.items():
        miss = leaves(allc - ps)
        heads = sorted(group_by_head(miss, 2))
        print(f"  {kind} {n}: lacks {len(miss)} leaves under {heads}")
