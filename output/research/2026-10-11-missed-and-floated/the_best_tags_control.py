"""A control for `the_best_tags_there_are`: a chunk carries about 12 tags and nearly half of them sit
on no other chunk of the product, so ANY set of chunks can be picked out by naming one tag of its
own per chunk. What says something about the gold is the tags that several gold chunks share.

On the hundred, inside the question's product, no model call, no query side. Tags are picked with
the set in hand as before (at most 11), in two ways: any tag; only tags that sit on two or more
chunks of the set. Once for the gold chunks of the question and once for as many chunks of the
product drawn at random (seed 20261011).

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_best_tags_control.py [gold100]
"""
import json
import os
import random
import sys
import warnings
from collections import Counter, defaultdict
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
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
MOST = 11

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the best tags, a control")
layer, n = p.layer, len(p.chunk_ids)
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, records = {}, []
for row in p.chunk_rows:
    _, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
chunks_of_tag = defaultdict(set)
for e in range(et.size):
    chunks_of_tag[int(et[e])].add(int(ec[e]))


def best_tags(of_product, wanted_set, shared_only):
    here = {t: chunks for t, chunks in of_product.items()
            if len(chunks & wanted_set) >= (2 if shared_only else 1)}
    taken, best, picked = set(), 0., 0
    while picked < MOST:
        top, top_value = None, best
        for t, chunks in here.items():
            union = taken | chunks
            value = 2 * len(union & wanted_set) / (len(union) + len(wanted_set))
            if value > top_value + 1e-12:
                top, top_value = t, value
        if top is None:
            break
        taken |= here.pop(top)
        best = top_value
        picked += 1
    hit = len(taken & wanted_set)
    return picked, hit / max(len(wanted_set), 1), hit / max(len(taken), 1), len(taken)


draw = random.Random(20261011)
rows = defaultdict(list)
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    gold = {i for i in range(n) if records[i] & cites}
    main = Counter(branch_of[sorted(gold)].tolist()).most_common(1)[0][0]
    inside = sorted(np.flatnonzero(branch_of == main).tolist())
    gold &= set(inside)
    of_product = {t: chunks & set(inside) for t, chunks in chunks_of_tag.items()}
    of_product = {t: chunks for t, chunks in of_product.items() if chunks}
    drawn = set(draw.sample(inside, len(gold)))
    for label, chosen in (("the gold chunks", gold), ("as many chunks drawn at random", drawn)):
        for way, shared in (("any tag", False), ("only tags on two or more chunks of the set", True)):
            rows[label, way].append(best_tags(of_product, chosen, shared))

print(f"{SET}: {len(wanted)} questions, inside the question's product; at most {MOST} tags picked with the set in hand")
print("== tags picked | share of the set's chunks among the chunks they bring | share of those chunks that belong to "
      "the set | chunks they bring (middles, with the mean of the two shares) ==")
for (label, way), values in rows.items():
    a = np.asarray(values, dtype=np.float64)
    print(f"  {label}, {way}: {np.median(a[:, 0]):.0f} | {np.median(a[:, 1]):.2f} (mean {a[:, 1].mean():.2f}) | "
          f"{np.median(a[:, 2]):.2f} (mean {a[:, 2].mean():.2f}) | {np.median(a[:, 3]):.0f}")
print("done", flush=True)
