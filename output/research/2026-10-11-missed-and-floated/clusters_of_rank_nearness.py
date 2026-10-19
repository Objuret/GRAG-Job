"""His 2026-10-15 "can you cluster their ranknearness? a combo of clusters? anything, do an actual
real fucking check for it".

Per question, every chunk inside the border has the four facet ranks of the edge it was reached
through (its closest tag to a query tag; each rank its place in that facet's ranking over all
edges). The chunks are clustered by how near those four ranks are (k-means on the four ranks; the
number of clusters where the curve of the fit bends, as his "dogleg decides"). The facet cloud:
the cluster holding the most of the strongest hits (the chunks both sides put in their first
cluster; his majority). Checks:
  1  chunks in the facet cloud against the rest (the strongest hits left out), how often cited;
     inside one record kind; the control: the kind holding the most strongest hits (the kind
     cloud); a cluster drawn at random instead of the majority one
  2  through the arm's delivery: inside the step the facet cloud first; the three first clouds'
     overlap first (the description's, the tags', the facet cloud); the same with the kind cloud
The arm as it stands, the hundred, cached first calls, no lane call; the arm's file is not
changed. The gold ids are read inside; numbers only.
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
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
KMAX = 8
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("clusters of rank nearness")
layer, n = p.layer, len(p.chunk_ids)
place, id_rank = layer["pos"][:, 1:], layer["id_rank"]
kinds = np.array([str(row["kind"]) for row in p.chunk_rows])
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)


def kmeans(x, k, seed):
    rng = np.random.default_rng(seed)
    centres = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d = np.min(((x[:, None, :] - np.array(centres)[None]) ** 2).sum(-1), axis=1)
        centres.append(x[rng.choice(len(x), p=d / d.sum())] if d.sum() > 0 else x[rng.integers(len(x))])
    c = np.array(centres)
    for _ in range(100):
        lab = ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        new = np.array([x[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
        if np.allclose(new, c):
            break
        c = new
    lab = ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
    return lab, float(((x - c[lab]) ** 2).sum())


def clusters_by_bend(x, seed):
    """k-means for 1..KMAX clusters; the number where the curve of the within-cluster squares bends (the point farthest
    from the line between its two ends)."""
    kmax = min(KMAX, len(np.unique(x, axis=0)))
    if kmax < 2:
        return np.zeros(len(x), dtype=np.int64)
    fits = [kmeans(x, k, seed) for k in range(1, kmax + 1)]
    w = np.array([f[1] for f in fits])
    ks = np.arange(1, kmax + 1, dtype=np.float64)
    a, b = np.array([ks[0], w[0]]), np.array([ks[-1], w[-1]])
    line = (b - a) / (np.linalg.norm(b - a) or 1.)
    pts = np.column_stack([ks, w]) - a
    dist = np.abs(pts[:, 0] * line[1] - pts[:, 1] * line[0])
    return fits[int(np.argmax(dist))][0]


captured = {}
the_combo = WK.cloud_combo


def combo_rec(layer_, cosines, d_near, inside, scope_of, k):
    out = the_combo(layer_, cosines, d_near, inside, scope_of, k)
    captured.update(combo=out, inside=np.asarray(inside, dtype=np.int64))
    return out


WK.cloud_combo = combo_rec


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


rng = random.Random(20261015)
tally = defaultdict(lambda: [0, 0])
results = defaultdict(list)
base_rows, n_clusters = [], []
cache = {}
for at, qid in enumerate(wanted):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    base_rows.append(score(out.meta["chunk_ids"], out.context_ids, cites))
    combo, inside = captured["combo"], captured["inside"]
    gold = np.array([bool(cites & records[c]) for c in inside.tolist()])
    edge = combo["edge"][inside]
    reached = edge >= 0
    x = np.zeros((inside.size, place.shape[1]))
    x[reached] = place[edge[reached]]
    lab = np.full(inside.size, -1, dtype=np.int64)
    lab[reached] = clusters_by_bend(x[reached], 20261015 + at)
    n_clusters.append(len(set(lab[reached].tolist())))
    step = combo["step"][inside]
    strongest = step == step.min()
    votes = Counter(lab[strongest & reached].tolist())
    cloud = np.zeros(inside.size, dtype=bool)
    if votes:
        top = max(votes.values())
        cloud = np.isin(lab, [c for c, v in votes.items() if v == top]) & reached
    kvotes = Counter(kinds[inside[strongest]].tolist())
    ktop = max(kvotes.values())
    kind_cloud = np.isin(kinds[inside], [k for k, v in kvotes.items() if v == ktop])
    others = sorted(set(lab[reached].tolist()))
    random_cloud = (lab == rng.choice(others)) & reached if others else np.zeros(inside.size, dtype=bool)
    main_kind = kinds[inside]
    for name, flag in (("the facet cloud", cloud), ("the kind cloud (control)", kind_cloud), ("a random rank cluster (check)", random_cloud)):
        rest = ~strongest
        for label, mask in ((f"{name}: in", rest & flag), (f"{name}: out", rest & ~flag)):
            tally[label][0] += int(mask.sum())
            tally[label][1] += int(gold[mask].sum())
        if name == "the facet cloud":
            for kd in set(main_kind[rest].tolist()):
                m = rest & (main_kind == kd)
                tally[("one kind", "in")][0] += int((m & flag).sum())
                tally[("one kind", "in")][1] += int(gold[m & flag].sum())
                tally[("one kind", "out")][0] += int((m & ~flag).sum())
                tally[("one kind", "out")][1] += int(gold[m & ~flag].sum())
        by = np.lexsort((id_rank[inside], -combo["value"][inside], ~flag, ~combo["in_scope"][inside], step))
        _, id_lists, context_ids, _, _, _ = V._hand_over(inside[by].tolist(), p, BUDGET, 50, cache)
        results[f"inside the step, {name} first"].append(score(id_lists, context_ids, cites))
        three = flag & (combo["level"]["tags"][inside] == 1) & (combo["level"]["description"][inside] == 1)
        first = [c for c in combo["order"] if c in set(inside[three].tolist())]
        order = first + [c for c in combo["order"] if c not in set(first)]
        _, id_lists, context_ids, _, _, _ = V._hand_over(order, p, BUDGET, 50, cache)
        results[f"the overlap of the tags' cloud, the description cloud and {name} first"].append(score(id_lists, context_ids, cites))
    if (at + 1) % 25 == 0:
        print(f"   {at + 1} questions", flush=True)
WK.cloud_combo = the_combo

count = len(base_rows)
print(f"\nclusters of rank nearness per question: middle {int(np.median(n_clusters))}, from {min(n_clusters)} to {max(n_clusters)}")
for name in ("the facet cloud", "the kind cloud (control)", "a random rank cluster (check)"):
    i, o = tally[f"{name}: in"], tally[f"{name}: out"]
    print(f"  {name}: chunks in it (the strongest hits left out) {i[0] / count:.1f} a question, {i[1] / max(i[0], 1):.1%} cited ; "
          f"outside {o[0] / count:.1f}, {o[1] / max(o[0], 1):.1%}")
i, o = tally[("one kind", "in")], tally[("one kind", "out")]
print(f"  the facet cloud inside one record kind: in {i[1] / max(i[0], 1):.1%} cited ({i[0]}), out {o[1] / max(o[0], 1):.1%} ({o[0]})")
print("\ntop text holds a cited record | among the first three | context_recall_id | against the arm: mean difference (standard error), up / down")
base = np.array([x[2] for x in base_rows])
print(f"  {sum(x[0] for x in base_rows):3d} | {sum(x[1] for x in base_rows):3d} | {base.mean():.4f} | the arm as it stands")
for label, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.4f} | {diff.mean():+.3f} "
          f"({diff.std(ddof=1) / np.sqrt(diff.size):.3f}), {int((diff > 1e-9).sum())} / {int((diff < -1e-9).sum())}  {label}")
print("done", flush=True)
