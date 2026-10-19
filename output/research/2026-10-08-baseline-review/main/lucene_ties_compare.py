"""Compare the lucene rankings written by lucene_ties.py: same Python twice, and two bm25s versions.

    .venv/Scripts/python.exe .../lucene_ties_compare.py a.json b.json [c.json]
"""
import json
import sys
from collections import Counter
from pathlib import Path

files = [json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[1:]]
names = [Path(p).stem for p in sys.argv[1:]]

for n, f in zip(names, files):
    sc = f["scores"]
    c = Counter(sc)
    tied = sum(v for v in c.values() if v > 1)
    kept = f["kept"]
    inside = sc[:kept]
    ci = Counter(inside)
    edge = sc[kept - 1] if kept else None      # score of the last whole unit inside the cut
    nxt = sc[kept] if kept < len(sc) else None  # score of the unit that is cut
    print(f"{n}: bm25s {f['bm25s']} | ranked {f['n_ranked']} | units sharing their score with "
          f"another: {tied} ({tied / len(sc):.1%}) | inside the cut: {kept} whole units, "
          f"{sum(v for v in ci.values() if v > 1)} of them in a tie | last whole unit's score "
          f"{edge}, the cut unit's score {nxt}, same score on both sides of the cut: {edge == nxt}"
          f" | units with exactly the last whole unit's score, anywhere: {c[edge]}")

for i in range(len(files)):
    for j in range(i + 1, len(files)):
        a, b = files[i], files[j]
        same_order = a["ids"] == b["ids"]
        same_set_all = set(a["ids"]) == set(b["ids"])
        ka, kb = a["kept"], b["kept"]
        da, db = a["ids"][:ka], b["ids"][:kb]
        first = next((r for r, (x, y) in enumerate(zip(a["ids"], b["ids"])) if x != y), None)
        sa, sb = dict(zip(a["ids"], a["scores"])), dict(zip(b["ids"], b["scores"]))
        common = [u for u in a["ids"] if u in sb]
        diffs = [abs(sa[u] - sb[u]) for u in common]
        moved = sum(1 for x, y in zip(a["ids"], b["ids"]) if x != y)
        # of the ranks where the two orders differ: is the unit standing there in A tied, in A's
        # own scores, with the unit standing there in B?
        tie_swaps = sum(1 for x, y in zip(a["ids"], b["ids"])
                        if x != y and y in sa and sa[x] == sa[y])
        print(f"\n{names[i]} against {names[j]}:")
        print(f"  whole ranking in the same order: {same_order} | same units ranked: {same_set_all}"
              f" | ranks holding a different unit: {moved} of {min(len(a['ids']), len(b['ids']))}"
              f" | first such rank: {first}")
        print(f"  of those ranks, the two units have exactly equal scores in the first file: {tie_swaps}")
        print(f"  score of the same unit in both: largest difference {max(diffs) if diffs else None}, "
              f"units whose score differs at all: {sum(1 for d in diffs if d > 0)} of {len(common)}")
        print(f"  whole units inside 72,000: {ka} and {kb} | same units inside the cut: "
              f"{set(da) == set(db)} | same order inside the cut: {da == db} | "
              f"units inside one cut and not the other: {len(set(da) ^ set(db))} | "
              f"the cut unit: {a['boundary']['id'] == b['boundary']['id'] if a['boundary'] and b['boundary'] else None}")
