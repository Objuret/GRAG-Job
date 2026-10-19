"""His 2026-10-13 "also, does tthis perhaps apply to the "next /previous chunk" situation?" (after
the things before a good hit on its people's line held a cited record more often than the
things after it). The chunk right above and the chunk right under a well-hit chunk by its
pointer: its place (`ordinal`) in its parent, his 2026-10-12 "No I literally meant the one above
or under it. Pointer-based". The chunk as it is, every record of it. On the gold hundred and on
the first 100 of the seeded draw of unused questions. No model call; the gold ids are read
inside; numbers only.

  the start     the first chunk of the order | the chunks both sides put in their first cluster
  per side      how many previous / next chunks there are, how often one holds a cited record;
                the same for those that are not themselves in both first clusters
  by kind       the same by the kind of the hit chunk
  beside it     how often any chunk of the product holds a cited record
"""
import json
import os
import random
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

CLUSTERS = 5
STARTS = ("the first chunk of the order", "the chunks in both first clusters")
SIDES = ("previous", "next")
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "100 unused questions": random.Random(20261011).sample(fresh, 300)[:100]}
p = V.prepare_over_corpus("the next and the previous chunk")
layer, n_chunks = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
kinds = [str(row["kind"]) for row in p.chunk_rows]
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
by_parent = defaultdict(list)
for i, row in enumerate(p.chunk_rows):
    by_parent[parents[i]].append((row["ordinal"], i))
beside = {}
for line in by_parent.values():
    line.sort()
    for (_, a), (_, b) in zip(line, line[1:]):
        beside[(a, "next")], beside[(b, "previous")] = b, a
print("prepared", flush=True)


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = WK.MAD_TO_SPREAD * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def closest_tag(vector):
    row = vector @ TV.T
    out = np.full(n_chunks, float(row.min()))
    np.maximum.at(out, ec, row[et])
    return out


for label, drawn in SETS.items():
    tally = {(s, side): [0, 0, 0, 0] for s in STARTS for side in SIDES}
    by_kind = defaultdict(lambda: {side: [0, 0] for side in SIDES})
    either = {s: [0, 0, 0, 0] for s in STARTS}          # starts with both a previous and a next: only previous cited, only next, both
    base, hit_base = [0, 0], [0, 0]
    for q in drawn:
        border, scope_said = V.scope_by_name(q.question, p.tree, n_chunks)
        names = scope_said["names_in_the_question"]
        if len(names) != 1:
            continue
        inside = np.flatnonzero(border)
        cites = {str(c) for c in q.citations}
        vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                            dtype=np.float64)
        D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
        step = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
        z = standing(D) + standing(T)
        taken = WK.majority_scopes(step <= max(3, int(step.min())), parent_of[inside])
        in_scope = np.isin(parent_of[inside], taken)
        ordered = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()
        step_at = dict(zip(inside.tolist(), step.tolist()))
        base[0] += len(ordered)
        base[1] += sum(bool(cites & records[i]) for i in ordered)
        good = [i for i in ordered if step_at[i] == 2]
        hit_base[0] += len(good)
        hit_base[1] += sum(bool(cites & records[i]) for i in good)
        for name, chosen in ((STARTS[0], ordered[:1]), (STARTS[1], good)):
            for c in chosen:
                found = {}
                for side in SIDES:
                    other = beside.get((c, side))
                    if other is None or other not in step_at:
                        continue
                    found[side] = cited = bool(cites & records[other])
                    row = tally[(name, side)]
                    row[0] += 1
                    row[1] += cited
                    if step_at[other] != 2:
                        row[2] += 1
                        row[3] += cited
                    if name == STARTS[1]:
                        by_kind[kinds[c]][side][0] += 1
                        by_kind[kinds[c]][side][1] += cited
                if len(found) == 2:
                    row = either[name]
                    row[0] += 1
                    row[1] += found["previous"] and not found["next"]
                    row[2] += found["next"] and not found["previous"]
                    row[3] += found["previous"] and found["next"]
    print(f"\n==== {label} ====")
    print(f"a chunk of the product holds a cited record {base[1] / base[0]:.1%} of the time ; a chunk in both first clusters "
          f"{hit_base[1] / max(hit_base[0], 1):.0%} ({hit_base[0] / len(drawn):.1f} such chunks a question)")
    for name in STARTS:
        said = " | ".join(f"the {side} chunk: {tally[(name, side)][0]}, {tally[(name, side)][1] / max(tally[(name, side)][0], 1):.0%} hold a "
                          f"cited record (not itself in both first clusters: {tally[(name, side)][2]}, "
                          f"{tally[(name, side)][3] / max(tally[(name, side)][2], 1):.0%})" for side in SIDES)
        e = either[name]
        print(f"   {name}: {said}\n      of the {e[0]} that have both a previous and a next chunk: only the previous holds a cited record "
              f"{e[1]} ({e[1] / max(e[0], 1):.0%}), only the next {e[2]} ({e[2] / max(e[0], 1):.0%}), both {e[3]} ({e[3] / max(e[0], 1):.0%})")
    print("   by the kind of the hit chunk (the chunks in both first clusters): " + " ; ".join(
        f"{kind}: previous {t['previous'][1] / max(t['previous'][0], 1):.0%} ({t['previous'][0]}), next "
        f"{t['next'][1] / max(t['next'][0], 1):.0%} ({t['next'][0]})" for kind, t in sorted(by_kind.items())))
print("done", flush=True)
