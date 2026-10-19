"""His 2026-10-14 "What fucking values, we did a ranking on them, check if the RANKING is
meaningful". Ranks only: no value is added, subtracted or averaged across facets; a pair of edges
is compared by which one the ranking puts above.

The ranking: the four facet columns of the round-1 instrument as the graph carries them (the
edge's mean over the 24 bootstrap refits, `output/facet_pairs/rounds/round1/bootstrap/
scores_b24.npz`), and his "equal if within a certain range" read off the refits: a pair is
ordered only when at least 23 of the 24 refits put the same edge above (the 95% of the retrain
band, BANDS.md); otherwise the two are equal.

  A  no gold. Is it a ranking at all: of the pairs of edges, how many does it order (any two
     edges; two edges of one tag; two tags of one chunk; two edges of one tag and one record
     kind). Does it order held-out pairs as Opus did (where Opus picked one), by pair type and
     by whether the two chunks are of one record kind.
  B  gold in hand, the hundred. Under one tag inside the border, a cited chunk's edge against
     another edge of that tag: of the pairs the ranking orders, how often it puts the cited one
     above (0.50 says nothing); the same where both chunks are one record kind. And the facet's
     place among the edge's own four (the other ranking in the arm).
The gold ids are read inside; numbers only.
"""
import glob
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
os.environ["HERB_V4_SCOPE_STEP"] = "name"

BOOT = REPO / "output/facet_pairs/rounds/round1/bootstrap/scores_b24.npz"
z = np.load(BOOT)
edge_ids = [str(x) for x in z["edge_ids"]]
FOUR = [str(x) for x in z["facets"]]
draws = z["scores"].astype(np.float64)                  # edges, four, 24
mean = draws.mean(axis=2)
at = {e: k for k, e in enumerate(edge_ids)}
kind_of = {}
for line in open(REPO / "output/facet_pairs/rounds/round1/scores.jsonl", encoding="utf-8"):
    row = json.loads(line)
    kind_of[row["edge_id"]] = row["kind"]
kind = np.array([kind_of.get(e, "") for e in edge_ids])
chunk_of = np.array([e.split("::", 1)[0] for e in edge_ids])
tag_of = np.array([e.split("::", 1)[1] for e in edge_ids])
NEED = 23                                               # of 24 refits: the 95% of the retrain band


def ordered(a, b, f):
    """+1 when the ranking holds a above b in facet f, -1 when below, 0 when they are equal (fewer than 23 of 24 refits agree)."""
    above = (draws[a, f, :] > draws[b, f, :]).sum(axis=-1)
    return np.where(above >= NEED, 1, np.where(len(draws[0, 0]) - above >= NEED, -1, 0))


rng = np.random.default_rng(20261014)
groups = {"tag": defaultdict(list), "chunk": defaultdict(list)}
for k, e in enumerate(edge_ids):
    groups["tag"][tag_of[k]].append(k)
    groups["chunk"][chunk_of[k]].append(k)


def pairs_within(by, limit, same_kind=False):
    out = []
    keys = [g for g in by.values() if len(g) > 1]
    while len(out) < limit:
        g = keys[rng.integers(len(keys))]
        a, b = rng.choice(g, 2, replace=False)
        if same_kind and kind[a] != kind[b]:
            continue
        out.append((a, b))
    return np.array(out)


print("== A: is it a ranking at all (no gold) ==")
samples = {"any two edges": rng.integers(0, len(edge_ids), size=(200000, 2)),
           "two edges of one tag": pairs_within(groups["tag"], 200000),
           "two edges of one tag, one record kind": pairs_within(groups["tag"], 200000, same_kind=True),
           "two tags of one chunk": pairs_within(groups["chunk"], 200000)}
for label, pr in samples.items():
    pr = pr[pr[:, 0] != pr[:, 1]]
    said = []
    for f, name in enumerate(FOUR):
        o = ordered(pr[:, 0], pr[:, 1], f)
        said.append(f"{name} {np.mean(o != 0):.0%}")
    print(f"  pairs the ranking orders, {label}: " + " ; ".join(said))

agree = defaultdict(lambda: [0, 0])
for path in glob.glob(str(REPO / "output/facet_pairs/answers/heldout/*.json")):
    row = json.load(open(path, encoding="utf-8"))
    # "first" in answers_canonical is the pair's edge with the smaller edge id (test/graph/facet_pairs/data.py)
    lo, hi = sorted((row["a"], row["b"]), key=lambda side: side["edge_id"])
    a = at.get(f"{lo['chunk_id']}::{lo['tag']}")
    b = at.get(f"{hi['chunk_id']}::{hi['tag']}")
    if a is None or b is None:
        continue
    same = "one record kind" if kind[a] == kind[b] else "two record kinds"
    for f, name in enumerate(FOUR):
        said = row["answers_canonical"].get(name)
        if said not in ("first", "second"):
            continue
        hit = (mean[a, f] > mean[b, f]) == (said == "first")
        for key in ((name, "all"), (name, row["pair_type"]), (name, same)):
            agree[key][0] += hit
            agree[key][1] += 1
print("\n  held-out pairs where Opus picked one: how often the ranking puts the same edge above (Opus repeats itself 0.87 to 0.905)")
for name in FOUR:
    print(f"    {name:13s}: " + " ; ".join(f"{key} {agree[(name, key)][0] / max(agree[(name, key)][1], 1):.2f} ({agree[(name, key)][1]})"
                                         for key in ("all", "cross", "same_tag", "same_chunk", "one record kind", "two record kinds")))

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from harness import questions as HQ  # noqa: E402

wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("is the facet ranking meaningful")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e = layer["edge_tag"], layer["edge_chunk"]
graph_tags = [str(t) for t in p.graph_tags]
boot_of = np.array([at.get(f"{p.chunk_ids[c]}::{graph_tags[t]}", -1) for t, c in zip(tag_e.tolist(), chunk_e.tolist())])
print(f"\n== B: the hundred. {int((boot_of >= 0).sum())} of {boot_of.size} graph edges found in the refits ==")
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
place = np.argsort(np.argsort(-mean, axis=1, kind="stable"), axis=1)        # the facet's place among the edge's own four, 0 the first
tally = defaultdict(lambda: [0., 0, 0])        # cited above (ties half), pairs ordered, pairs
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    border, _ = V.scope_by_name(q.question, p.tree, n)
    gold = np.array([bool(cites & records[i]) for i in range(n)])
    inside = np.flatnonzero(border[chunk_e] & (boot_of >= 0))
    for t in np.unique(tag_e[inside]).tolist():
        e = inside[tag_e[inside] == t]
        g, h = e[gold[chunk_e[e]]], e[~gold[chunk_e[e]]]
        if not g.size or not h.size:
            continue
        A = np.repeat(boot_of[g], h.size)
        B = np.tile(boot_of[h], g.size)
        one_kind = kind[A] == kind[B]
        for f, name in enumerate(FOUR):
            o = ordered(A, B, f)
            pl = np.sign(place[B, f] - place[A, f])                  # +1 when the facet stands higher among the cited edge's own four
            for key, mask in (("all", np.ones(A.size, dtype=bool)), ("one record kind", one_kind)):
                row = tally[(name, "the ranking", key)]
                row[0] += float((o[mask] > 0).sum())
                row[1] += int((o[mask] != 0).sum())
                row[2] += int(mask.sum())
                row = tally[(name, "the place among the edge's own four", key)]
                row[0] += float((pl[mask] > 0).sum() + 0.5 * (pl[mask] == 0).sum())
                row[1] += int(mask.sum())
                row[2] += int(mask.sum())
print("under one tag, a cited chunk's edge against another edge of that tag")
for key in ("all", "one record kind"):
    print(f"  {key}:")
    for name in FOUR:
        r, s = tally[(name, "the ranking", key)], tally[(name, "the place among the edge's own four", key)]
        print(f"    {name:13s}: the ranking orders {r[1] / max(r[2], 1):.0%} of {r[2]} pairs and puts the cited edge above in "
              f"{r[0] / max(r[1], 1):.2f} of those ; the facet's place among the edge's own four higher for the cited edge {s[0] / max(s[1], 1):.2f}")
print("done", flush=True)
