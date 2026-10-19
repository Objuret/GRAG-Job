"""His 2026-10-15 "if we first rank all chunks from the chosen tags via the facets, THEN we chose
chunks or cloudoverlap with that from desc.. what do we get?" and "dont be lazy.. actually do it".

Two readings of "the chosen tags":
  A  each query tag's five nearest graph tags (the chain's pick, his version of 10-11)
  B  the tags the arm itself hits first: the closest tags of the chunks in the first cluster of
     the arm's tags side (its tag cloud)
All chunks of the chosen tags inside the border make the pool. Inside the pool the chunks are put
in order by one of:
  facets, model    the facets in the query tag's order (the facet the model names first), his
                   multi-key: each facet's place in the ranking cut into five clusters over the
                   pool's edges as the equal range; a chunk takes its best edge to a chosen tag
  facets, net      the same with his net's order of the four for the query tag
  facets, other    the same with the order of a query tag of another question (check)
  closeness        the chosen tag's closeness to the query tag (check: no facets)
  kind             the record kind alone, in the order the kinds' cited share runs over the
                   other 99 questions (check: is it the kind)
  blind            a random order (check: what the pool alone gives)
The pool order is cut into five clusters (its first cluster is the tag cloud) and put together
with the description cloud as the combo does it: step = the two levels added, the scope gauged
from the first two steps, in scope first, then the pool order, then the description. Chunks
outside the pool come after the pool's clusters. And the overlap of the two first clouds first,
then the arm's order.

Printed: top text holds a cited record | among the first three | context_recall_id | against the
arm; and per reading the mechanism: the pool's size, how much of it the arm already delivers,
its share of cited chunks, how often a cited chunk stands above another inside the pool by each
order (0.50 says nothing).

A side run through the arm's own delivery (`_hand_over`), the hundred, cached first calls, no lane
call; the arm's file is not changed. Five clusters as in the arm is my choice. The gold ids are
read inside; numbers only.
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
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import query_facets as QF  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
K = 5
FOUR = list(WK.RANKING_FACETS)
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("facet cloud and description cloud")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, id_rank, place = layer["edge_tag"], layer["edge_chunk"], layer["id_rank"], layer["pos"][:, 1:]
kinds = np.array([str(row["kind"]) for row in p.chunk_rows])
edges_of_tag = defaultdict(list)
for k, t in enumerate(tag_e.tolist()):
    edges_of_tag[t].append(k)
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)

captured = {}
the_combo, the_chain, the_interpret, the_hand = WK.cloud_combo, WK.chain, V._interpret, V._hand_over


def combo_rec(layer_, cosines, d_near, inside, scope_of, k):
    out = the_combo(layer_, cosines, d_near, inside, scope_of, k)
    captured.update(combo=out, inside=np.asarray(inside, dtype=np.int64), d_near=np.asarray(d_near, dtype=np.float64),
                    scope_of=np.asarray(scope_of, dtype=np.int64), cosines=np.asarray(cosines, dtype=np.float64))
    return out


def chain_rec(layer_, query, cos_noise, k):
    out = the_chain(layer_, query, cos_noise, k)
    captured.update(chain=out)
    return out


def interpreting(text, prepared):
    got = the_interpret(text, prepared)
    captured["content"] = got[0]
    return got


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


WK.cloud_combo, WK.chain, V._interpret, V._hand_over = combo_rec, chain_rec, interpreting, hand_rec


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = WK.MAD_TO_SPREAD * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


rows_q = []
for at, qid in enumerate(wanted):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    base = score(out.meta["chunk_ids"], out.context_ids, cites)
    keep = {k: captured[k] for k in ("combo", "inside", "d_near", "scope_of", "content", "cosines", "delivered")}
    os.environ["HERB_V4_SCOPE_STEP"] = "name"
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    os.environ.pop("HERB_V4_SCOPE_STEP", None)
    tags = (*keep["content"].tags, *keep["content"].query_tags)
    net = QF.head_scores([t.text for t in tags], keep["content"].description)[:, 1:]
    rows_q.append({"cites": cites, "base": base, **keep, "picked": captured["chain"]["picked_edge"],
                   "gold": {i for i in keep["inside"].tolist() if cites & records[i]},
                   "named": [[FOUR.index(t.facet)] + [j for j in range(4) if j != FOUR.index(t.facet)] for t in tags],
                   "net": [list(np.argsort(-row, kind="stable")) for row in net]})
    if (at + 1) % 25 == 0:
        print(f"   {at + 1} questions", flush=True)
WK.cloud_combo, WK.chain, V._interpret, V._hand_over = the_combo, the_chain, the_interpret, the_hand

rng = random.Random(20261015)
ORDERS = ("facets, model", "facets, net", "facets, other", "closeness", "kind", "blind")
READINGS = ("A: the five nearest graph tags of each query tag", "B: the tags the arm hits first (its tag cloud)")
results = {"the arm as it stands": [r["base"] for r in rows_q]}
mechanism = {rd: defaultdict(lambda: [0., 0.]) for rd in READINGS}
for rd in READINGS:
    for o in ORDERS:
        results[f"{rd} | {o} | combined as the combo"] = []
        results[f"{rd} | {o} | the two first clouds' overlap first"] = []
cache = {}
for k, r in enumerate(rows_q):
    inside, combo = r["inside"], r["combo"]
    member = np.zeros(n, dtype=bool)
    member[inside] = True
    gold = r["gold"]
    others = [x for j, x in enumerate(rows_q) if j != k]
    other_net = rng.choice(others)["net"]
    kind_share = Counter()
    kind_all = Counter()
    for x in others:
        for c in x["inside"].tolist():
            kind_all[kinds[c]] += 1
            kind_share[kinds[c]] += c in x["gold"]
    kind_rank = {kd: kind_share[kd] / kind_all[kd] for kd in kind_all}
    d_level = np.zeros(n, dtype=np.int64)
    d_level[inside] = WK.levels(r["d_near"][inside], K)
    d_stand = np.zeros(n)
    d_stand[inside] = standing(r["d_near"][inside])
    rows = r["cosines"]
    for rd in READINGS:
        # the chosen tags and, per chosen tag, the query tag it answers to
        if rd == READINGS[0]:
            picked = r["picked"] & member[chunk_e][None, :]
            pairs = [(int(e), int(i)) for i, e in zip(*np.nonzero(picked))]
        else:
            t_level = combo["level"]["tags"]
            cloud = inside[t_level[inside] == 1]
            chosen = {int(tag_e[combo["edge"][c]]): int(combo["query_tag"][c]) for c in cloud.tolist() if combo["edge"][c] >= 0}
            pairs = [(e, i) for t, i in chosen.items() for e in edges_of_tag[t] if member[chunk_e[e]]]
        if not pairs:
            for o in ORDERS:
                results[f"{rd} | {o} | combined as the combo"].append(r["base"])
                results[f"{rd} | {o} | the two first clouds' overlap first"].append(r["base"])
            continue
        edges = np.array(sorted({e for e, _ in pairs}))
        at_edge = {e: j for j, e in enumerate(edges.tolist())}
        f_levels = np.column_stack([WK.levels(place[edges, f], K) if edges.size > 1 else np.ones(edges.size, dtype=np.int64)
                                    for f in range(len(FOUR))])
        close = np.array([rows[:, tag_e[e]].max() for e in edges])
        c_levels = WK.levels(close, K) if edges.size > 1 else np.ones(edges.size, dtype=np.int64)
        pool = sorted({int(chunk_e[e]) for e in edges.tolist()})
        blind = {c: rng.random() for c in pool}
        keys = {}
        for o in ORDERS:
            best = {}
            for e, i in pairs:
                c, j = int(chunk_e[e]), at_edge[e]
                if o.startswith("facets"):
                    order = {"facets, model": r["named"][i], "facets, net": r["net"][i],
                             "facets, other": other_net[i % len(other_net)]}[o]
                    key = tuple(int(f_levels[j, f]) for f in order)
                elif o == "closeness":
                    key = (int(c_levels[j]), -float(close[j]))
                elif o == "kind":
                    key = (-kind_rank.get(kinds[c], 0.),)
                else:
                    key = (blind[c],)
                best[c] = min(best.get(c, key), key)
            keys[o] = best
        delivered = set(r["delivered"])
        mech = mechanism[rd]
        mech["pool"][0] += len(pool)
        mech["pool"][1] += 1
        mech["already delivered"][0] += sum(c in delivered for c in pool)
        mech["already delivered"][1] += len(pool)
        mech["cited"][0] += sum(c in gold for c in pool)
        mech["cited"][1] += len(pool)
        g = [c for c in pool if c in gold]
        h = [c for c in pool if c not in gold]
        for o in ORDERS:
            for a in g:
                for b in h:
                    ka, kb = keys[o][a], keys[o][b]
                    mech[("above", o)][0] += 1. if ka < kb else (0.5 if ka == kb else 0.)
                    mech[("above", o)][1] += 1
        for o in ORDERS:
            ranked = sorted(pool, key=lambda c: (keys[o][c], id_rank[c]))
            rank_level = {c: lv for c, lv in zip(ranked, WK.levels(-np.arange(len(ranked), dtype=np.float64), K)
                                                  if len(ranked) > 1 else [1])}
            at_rank = {c: j for j, c in enumerate(ranked)}
            p_level = np.array([rank_level.get(c, K + 1) for c in inside.tolist()], dtype=np.int64)
            p_rank = np.array([at_rank.get(c, len(ranked)) for c in inside.tolist()], dtype=np.int64)
            step = p_level + d_level[inside]
            hits = step <= max(3, int(step.min()))
            in_scope = np.isin(r["scope_of"][inside], WK.majority_scopes(hits, r["scope_of"][inside]))
            by = np.lexsort((id_rank[inside], -d_stand[inside], p_rank, ~in_scope, step))
            _, id_lists, context_ids, _, _, _ = V._hand_over(inside[by].tolist(), p, BUDGET, 50, cache)
            results[f"{rd} | {o} | combined as the combo"].append(score(id_lists, context_ids, r["cites"]))
            both = {c for c, lv in zip(inside.tolist(), p_level.tolist()) if lv == 1 and d_level[c] == 1}
            order = [c for c in combo["order"] if c in both] + [c for c in combo["order"] if c not in both]
            _, id_lists, context_ids, _, _, _ = V._hand_over(order, p, BUDGET, 50, cache)
            results[f"{rd} | {o} | the two first clouds' overlap first"].append(score(id_lists, context_ids, r["cites"]))

print("\ntop text holds a cited record | a cited record among the first three texts | context_recall_id | against the arm: mean "
      "difference (standard error), questions higher / lower")
base = np.array([x[2] for x in results["the arm as it stands"]])
for label, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.4f} | {diff.mean():+.3f} "
          f"({diff.std(ddof=1) / np.sqrt(diff.size):.3f}), {int((diff > 1e-9).sum())} / {int((diff < -1e-9).sum())}  {label}")
for rd in READINGS:
    mech = mechanism[rd]
    print(f"\n{rd}: the pool {mech['pool'][0] / max(mech['pool'][1], 1):.1f} chunks a question, the arm already delivers "
          f"{mech['already delivered'][0] / max(mech['already delivered'][1], 1):.0%} of it, {mech['cited'][0] / max(mech['cited'][1], 1):.0%} "
          f"of it cited; inside the pool a cited chunk above another by: "
          + " ; ".join(f"{o} {mech[('above', o)][0] / max(mech[('above', o)][1], 1):.2f}" for o in ORDERS))
print("done", flush=True)
