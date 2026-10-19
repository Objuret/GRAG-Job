"""His 2026-10-11 "can our structure or scope help fix this somehow?": how the gold chunks of a
question sit in the structure around them, with no query side at all, so it runs on the hundred
without a model call.

Per question the gold chunks are the pool chunks that hold a record the gold answer cites; the
branch is the one that holds most of them. Inside that branch:

  parents      a chunk's parent is its channel, or its product's PRs, documents, transcripts
               (`parent_ref`, 581 of them; the same thing as a file sequence)
  neighbours   the chunks next to it in its parent's order
  likeness     its nearest other chunk by chunk description, and by shared tags

The gold ids are read inside this script; it prints numbers only: no question text, no answer,
no record text.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/gold_structure.py [gold100]
"""
import json
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from arms.artefact_v3 import file_adjacency  # noqa: E402
from graph.db import _driver  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
DRAWS = 200

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the gold structure test")
layer, n = p.layer, len(p.chunk_ids)
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
driver = _driver()
try:
    with driver.session(database=V.DATABASE, default_access_mode="READ") as session:
        found = {r["id"]: (r["parent"], r["ordinal"]) for r in session.run(
            "MATCH (c:Chunk) WHERE (c)-[:product]->() RETURN c.chunk_id AS id, c.parent_ref AS parent, "
            "c.ordinal AS ordinal")}
finally:
    driver.close()
parent_names = sorted({found[c][0] for c in p.chunk_ids})
parent_of = np.array([parent_names.index(found[c][0]) for c in p.chunk_ids], dtype=np.int64)
ordinal = np.array([found[c][1] for c in p.chunk_ids], dtype=np.int64)
adjacency = file_adjacency([dict(r) for r in p.chunk_rows])
ptr, members = np.asarray(adjacency["ptr"]), np.asarray(adjacency["members"])
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
leaves = V.tree_leaves(p.tree)
kind_of = layer["kind"]
tags_of = [set() for _ in range(n)]
for t, c in zip(layer["edge_tag"].tolist(), layer["edge_chunk"].tolist()):
    tags_of[c].add(t)
described = p.chunk_vectors.astype(np.float64)
print(f"{SET}: {len(wanted)} questions; pool {n} chunks in {len(parent_names)} parents; {len(members) // 2} neighbour pairs")

rng = np.random.default_rng(20261011)
S = {name: [] for name in (
    "gold", "cited", "cover", "branches", "outside", "kinds", "own", "largest_own", "parents",
    "largest_parent", "branch", "branch_parents", "density", "base", "neighbour", "neighbour_chance",
    "window", "near_desc", "near_tags", "chance", "top_half")}
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    g_all = np.flatnonzero(gold)
    if not g_all.size:
        continue
    held = Counter(branch_of[g_all].tolist())
    main = held.most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    g = g_all[branch_of[g_all] == main]
    is_gold = gold[inside]
    S["gold"].append(g_all.size)
    S["cited"].append(len(cites))
    S["branches"].append(len(held))
    S["outside"].append(1. - g.size / g_all.size)
    S["branch"].append(inside.size)
    S["kinds"].append(len(set(kind_of[g].tolist())))
    own = [int(gold[chunks][branch_of[chunks] == main].sum()) for _, chunks in leaves]
    own = [v for v in own if v]
    S["own"].append(len(own))
    S["largest_own"].append(max(own) / g.size)
    # the fewest gold chunks that hold every cited record
    left, taken, got = set(g.tolist()), 0, set()
    while True:
        best = max(left, key=lambda i: (len((records[i] & cites) - got), -length[i]), default=None)
        if best is None or not (records[best] & cites) - got:
            break
        got |= records[best] & cites
        left.discard(best)
        taken += 1
    S["cover"].append(taken)
    # parents: how many hold gold, and how full of gold those are
    per_parent = Counter(parent_of[g].tolist())
    in_branch = Counter(parent_of[inside].tolist())
    S["parents"].append(len(per_parent))
    S["branch_parents"].append(len(in_branch))
    S["largest_parent"].append(max(per_parent.values()) / g.size)
    S["density"].append(sum(per_parent.values()) / sum(in_branch[x] for x in per_parent))
    S["base"].append(g.size / inside.size)
    # of the parents, ordered by their gold: how much of the gold the top half of the gold-holding parents has
    counts = sorted(per_parent.values(), reverse=True)
    S["top_half"].append(sum(counts[:max(1, len(counts) // 2)]) / g.size)

    def with_gold_neighbour(mask):
        hit = 0
        for i in np.flatnonzero(mask):
            hit += bool(mask[members[ptr[i]:ptr[i + 1]]].any())
        return hit / max(int(mask.sum()), 1)

    S["neighbour"].append(with_gold_neighbour(gold))
    chance = []
    for _ in range(DRAWS):
        drawn = np.zeros(n, dtype=bool)
        drawn[rng.choice(inside, size=g.size, replace=False)] = True
        chance.append(with_gold_neighbour(drawn))
    S["neighbour_chance"].append(float(np.mean(chance)))
    # inside a parent that holds gold: the stretch from its first to its last gold chunk, as a share of the parent
    stretch = []
    for x, count in per_parent.items():
        chunks = inside[parent_of[inside] == x]
        if chunks.size < 2:
            continue
        place = np.argsort(np.argsort(ordinal[chunks]))
        of_gold = place[gold[chunks]]
        stretch.append((of_gold.max() - of_gold.min() + 1) / chunks.size)
    if stretch:
        S["window"].append(float(np.mean(stretch)))
    # likeness: is the nearest other chunk of a gold chunk gold?
    if g.size >= 2:
        near = described[inside] @ described[inside].T
        np.fill_diagonal(near, -np.inf)
        S["near_desc"].append(float(is_gold[near.argmax(axis=1)][is_gold].mean()))
        hit = []
        for a in np.flatnonzero(is_gold):
            ta = tags_of[inside[a]]
            share = np.array([len(ta & tags_of[c]) / max(len(ta | tags_of[c]), 1) for c in inside])
            share[a] = -1.
            best = np.flatnonzero(share == share.max())
            hit.append(float(is_gold[best].mean()) if share.max() > 0 else 0.)
        S["near_tags"].append(float(np.mean(hit)))
        S["chance"].append((g.size - 1) / (inside.size - 1))

m = len(S["gold"])
mean = lambda name: float(np.mean(S[name]))
mid = lambda name: float(np.median(S[name]))
print(f"\n== {m} questions with gold in the pool ==")
print(f"  gold chunks per question: middle {mid('gold'):.0f}, mean {mean('gold'):.1f}; cited records: middle {mid('cited'):.0f}; "
      f"the fewest gold chunks that hold every cited record: middle {mid('cover'):.0f}, mean {mean('cover'):.1f}")
print(f"  branches holding gold: one on {sum(1 for v in S['branches'] if v == 1)} questions, two on "
      f"{sum(1 for v in S['branches'] if v == 2)}, more on {sum(1 for v in S['branches'] if v > 2)}; share of the gold chunks "
      f"outside the main branch, mean {mean('outside'):.3f}")
print(f"  the branch: {mid('branch'):.0f} chunks in {mid('branch_parents'):.0f} parents at the middle; gold is {mean('base'):.3f} of the branch's chunks")
print(f"  kinds of record holding gold: middle {mid('kinds'):.0f}; own scopes holding gold: middle {mid('own'):.0f}, "
      f"share of the gold in the largest own scope {mean('largest_own'):.2f}")
print(f"  parents holding gold: middle {mid('parents'):.0f} of {mid('branch_parents'):.0f}; share of the gold in the largest parent "
      f"{mean('largest_parent'):.2f}; in the top half of the gold-holding parents {mean('top_half'):.2f}")
print(f"  inside the parents that hold gold, gold is {mean('density'):.3f} of the chunks (in the whole branch {mean('base'):.3f})")
print(f"  inside a parent that holds gold, the stretch from its first to its last gold chunk is {mean('window'):.2f} of the parent")
print(f"  a gold chunk has a gold neighbour (next to it in its parent): {mean('neighbour'):.3f}; the same for as many chunks "
      f"drawn at random in the branch: {mean('neighbour_chance'):.3f}")
print(f"  the nearest other chunk of a gold chunk is gold: by chunk description {mean('near_desc'):.3f}, by shared tags "
      f"{mean('near_tags'):.3f}; by chance {mean('chance'):.3f}")
print("done", flush=True)
