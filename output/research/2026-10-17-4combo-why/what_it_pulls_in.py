"""Exactly what the 4-combo pulls into the 72,000 (his 2026-10-17 "tell me exactly WHAT you pull in"). From the
two run folders of the hundred and the graph; no question text, no citation, no model call.

The chunks delivered after and not before: their kind of record, whether their parent is a chosen chunk's
parent, whether it is one of the parents where the clouds' first hits gather (the combo's scope), where they
stood in the clouds' order, and which ways tie them to the chosen chunks. The same for the chunks they pushed out.

    .venv/Scripts/python.exe output/research/2026-10-17-4combo-why/what_it_pulls_in.py <before> <after>
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
from graph.db import _driver  # noqa: E402

dr = _driver()
with dr.session(database="herb-eval-volmax") as s:
    info = {r["id"]: (r["kind"], r["parent"]) for r in s.run(
        "MATCH (c:Chunk) WHERE (c)-[:product]->() RETURN c.chunk_id AS id, c.kind AS kind, c.parent_ref AS parent")}
dr.close()


def rows(folder):
    return {r["id"]: r for r in (json.loads(l) for l in (Path(folder) / "arm_outputs.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip())}


before, after = rows(sys.argv[1]), rows(sys.argv[2])
pulled, pushed = [], []
for q, a in after.items():
    b = before[q]
    rk_a, rk_b = a["meta"]["ranking"], b["meta"]["ranking"]
    chosen = a["meta"]["scope"]["storyline"]["chosen_chunk_ids"]
    chosen_parents = {info[c][1] for c in chosen}
    scope_parents = set(a["meta"]["scope"]["combo"]["scopes_taken"])
    place_before = {c: k + 1 for k, c in enumerate(rk_b["ordered_chunk_ids"])}
    in_a, in_b = set(rk_a["delivered_chunk_ids"]), set(rk_b["delivered_chunk_ids"])
    for k, c in enumerate(rk_a["delivered_chunk_ids"]):
        if c in in_b:
            continue
        kind, parent = info[c]
        pulled.append({"kind": kind, "chosen_parent": parent in chosen_parents,
                       "scope_parent": parent in scope_parents, "place_before": place_before[c],
                       "delivered_before": len(rk_b["delivered_chunk_ids"]),
                       "ways": {w: n[k] for w, n in rk_a["delivered_storyline_ways"].items()},
                       "chosen": len(chosen)})
    for c in rk_b["delivered_chunk_ids"]:
        if c in in_a:
            continue
        kind, parent = info[c]
        pushed.append({"kind": kind, "chosen_parent": parent in chosen_parents,
                       "scope_parent": parent in scope_parents})

n = len(pulled)
pct = lambda x, m: f"{x} ({100 * x / m:.0f}%)"  # noqa: E731
print(f"pulled into the 72,000: {n} chunks over the hundred, {n / len(after):.1f} a question")
print("   by kind: " + ", ".join(f"{k} {pct(v, n)}" for k, v in Counter(p['kind'] for p in pulled).most_common()))
print(f"   under the parent of a chosen chunk: {pct(sum(p['chosen_parent'] for p in pulled), n)}")
print(f"   under a parent where the clouds' first hits gather (the scope): {pct(sum(p['scope_parent'] for p in pulled), n)}")
print(f"   under neither: {pct(sum(not p['chosen_parent'] and not p['scope_parent'] for p in pulled), n)}")
places = [p["place_before"] for p in pulled]
print(f"   their place in the clouds' order before: middle {np.median(places):.0f} (quartiles "
      f"{np.percentile(places, 25):.0f}-{np.percentile(places, 75):.0f}); the 72,000 then held "
      f"{np.median([p['delivered_before'] for p in pulled]):.0f} chunks (middle)")
print("   tied to the chosen chunks, chunks tied by each way: " + ", ".join(
    f"{w} {pct(sum(p['ways'][w] > 0 for p in pulled), n)}" for w in ("scope", "entities", "time", "nearness")))
only_people = sum(p["ways"]["entities"] > 0 and not any(p["ways"][w] for w in ("scope", "time", "nearness"))
                  for p in pulled)
print(f"   tied by the people alone: {pct(only_people, n)}")
m = len(pushed)
print(f"\npushed out of the 72,000: {m} chunks")
print("   by kind: " + ", ".join(f"{k} {pct(v, m)}" for k, v in Counter(p['kind'] for p in pushed).most_common()))
print(f"   under the parent of a chosen chunk: {pct(sum(p['chosen_parent'] for p in pushed), m)}; under a scope "
      f"parent: {pct(sum(p['scope_parent'] for p in pushed), m)}")
