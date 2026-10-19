"""His 2026-10-15 "dude, find the fucking actual use for the facets..". Relevance feedback for the
facets (mine; Rocchio, RM3): the facet a question needs is read off the arm's strongest hits, not
off the query. The strongest hits: the chunks both sides put in their first cluster (the combo's
lowest step). A chunk's role: the facet in which its closest-tag edge ranks best among that tag's
chunks inside the border (ranks inside the tag; ties: the first in the fixed order). The
question's role: the role most of the strongest hits have (the majority; ties: all of the tied).

  1  no order changed: inside the border, chunks whose role is the question's role against the
     others, how often cited; inside one record kind; the chunks outside the strongest hits only
  2  through the arm's delivery: inside the step (and inside or outside the scope), chunks with
     the question's role first, then the standings; and the chunks the same-role tag links reach
     from the delivered ones, only those with the question's role, brought in after the hits
  3  the check: the role of another question

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
from scipy.stats import rankdata

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
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the facet from the hits")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, place, id_rank = layer["edge_tag"], layer["edge_chunk"], layer["pos"][:, 1:], layer["id_rank"]
kinds = np.array([str(row["kind"]) for row in p.chunk_rows])
edges_of_tag, edges_of_chunk = defaultdict(list), defaultdict(list)
for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist())):
    edges_of_tag[t].append(k)
    edges_of_chunk[c].append(k)
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)

captured = {}
the_combo, the_hand = WK.cloud_combo, V._hand_over


def combo_rec(layer_, cosines, d_near, inside, scope_of, k):
    out = the_combo(layer_, cosines, d_near, inside, scope_of, k)
    captured.update(combo=out, inside=np.asarray(inside, dtype=np.int64))
    return out


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


WK.cloud_combo, V._hand_over = combo_rec, hand_rec


def score(id_lists, context_ids, cites):
    got = {str(x) for x in context_ids}
    whole = [u for u in ([str(x) for x in unit] for unit in id_lists if unit) if set(u) <= got]
    return (bool(whole and set(whole[0]) & cites), any(set(u) & cites for u in whole[:3]), len(cites & got) / len(cites))


def edge_role(e, member):
    """The facet in which edge e ranks best among its tag's edges inside the border (None for a tag with one chunk there)."""
    es = np.array([k for k in edges_of_tag[int(tag_e[e])] if member[chunk_e[k]]])
    if es.size < 2:
        return None
    j = int(np.flatnonzero(es == e)[0])
    ranks = np.column_stack([rankdata(-place[es, f], method="average") for f in range(place.shape[1])])
    return int(np.argmin(ranks[j]))


rows_q = []
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    out = V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    combo, inside, delivered = captured["combo"], captured["inside"], set(captured["delivered"])
    member = np.zeros(n, dtype=bool)
    member[inside] = True
    role = {}
    for c in inside.tolist():
        e = int(combo["edge"][c])
        role[c] = edge_role(e, member) if e >= 0 else None
    step = combo["step"]
    strongest = [c for c in inside.tolist() if step[c] == int(step[inside].min())]
    votes = Counter(role[c] for c in strongest if role[c] is not None)
    top = max(votes.values()) if votes else 0
    q_roles = {r for r, v in votes.items() if v == top}
    rows_q.append({"cites": cites, "base": score(out.meta["chunk_ids"], out.context_ids, cites), "combo": combo, "inside": inside,
                   "member": member, "delivered": delivered, "role": role, "q_roles": q_roles, "strongest": set(strongest),
                   "gold": {c for c in inside.tolist() if cites & records[c]}})
WK.cloud_combo, V._hand_over = the_combo, the_hand

rng = random.Random(20261015)
tally = defaultdict(lambda: [0, 0])
results = defaultdict(list)
cache = {}
for k, r in enumerate(rows_q):
    other_roles = rng.choice([x for j, x in enumerate(rows_q) if j != k])["q_roles"]
    inside, combo, gold = r["inside"], r["combo"], r["gold"]
    for label, roles in (("the question's role", r["q_roles"]), ("another question's role", other_roles)):
        for c in inside.tolist():
            if r["role"][c] is None or c in r["strongest"]:
                continue
            match = r["role"][c] in roles
            tally[(label, "match" if match else "no match")][0] += 1
            tally[(label, "match" if match else "no match")][1] += c in gold
        match = np.array([r["role"][c] in roles if r["role"][c] is not None else False for c in inside.tolist()])
        by = np.lexsort((id_rank[inside], -combo["value"][inside], ~match, ~combo["in_scope"][inside], combo["step"][inside]))
        _, id_lists, context_ids, _, _, _ = V._hand_over(inside[by].tolist(), p, BUDGET, 50, cache)
        results[f"inside the step, chunks with {label} first"].append(score(id_lists, context_ids, r["cites"]))
        # the chunks the same-role tag links reach from the delivered ones, only those with this role, after the strongest hits
        reach = set()
        for a in r["delivered"]:
            for e1 in edges_of_chunk[a]:
                for e2 in edges_of_tag[int(tag_e[e1])]:
                    c = int(chunk_e[e2])
                    if r["member"][c] and c not in r["delivered"] and r["role"].get(c) in roles:
                        reach.add(c)
        tally[(label, "reached and matching")][0] += len(reach)
        tally[(label, "reached and matching")][1] += len(reach & gold)
        first = [c for c in combo["order"] if c in r["strongest"]]
        rest = [c for c in combo["order"] if c not in r["strongest"]]
        order = first + [c for c in rest if c in reach] + [c for c in rest if c not in reach]
        _, id_lists, context_ids, _, _, _ = V._hand_over(order, p, BUDGET, 50, cache)
        results[f"the strongest hits, then what the links reach with {label}, then the rest"].append(score(id_lists, context_ids, r["cites"]))

count = len(rows_q)
print("\nthe question's role, read off its strongest hits: " + ", ".join(
    f"{k} {v}" for k, v in Counter(tuple(sorted(r["q_roles"])) for r in rows_q).most_common(6)))
for label in ("the question's role", "another question's role"):
    m, nm = tally[(label, "match")], tally[(label, "no match")]
    rm = tally[(label, "reached and matching")]
    print(f"  {label}: chunks outside the strongest hits with that role {m[0] / count:.1f} a question, {m[1] / max(m[0], 1):.1%} cited ; "
          f"without it {nm[0] / count:.1f}, {nm[1] / max(nm[0], 1):.1%} ; reached by the links and with it {rm[0] / count:.1f}, "
          f"{rm[1] / max(rm[0], 1):.1%}")
print("\ntop text holds a cited record | among the first three | context_recall_id | against the arm: mean difference (standard error), up / down")
base = np.array([x["base"][2] for x in rows_q])
print(f"  {sum(x['base'][0] for x in rows_q):3d} | {sum(x['base'][1] for x in rows_q):3d} | {base.mean():.4f} | the arm as it stands")
for label, got in results.items():
    a = np.array(got, dtype=np.float64)
    diff = a[:, 2] - base
    print(f"  {int(a[:, 0].sum()):3d} | {int(a[:, 1].sum()):3d} | {a[:, 2].mean():.4f} | {diff.mean():+.3f} "
          f"({diff.std(ddof=1) / np.sqrt(diff.size):.3f}), {int((diff > 1e-9).sum())} / {int((diff < -1e-9).sum())}  {label}")
print("done", flush=True)
