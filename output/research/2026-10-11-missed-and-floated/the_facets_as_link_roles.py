"""His 2026-10-15 "find a creative clever way of actually using those facets in a meaningful way",
after "they are supposed to influence the already existing relationship for chunks and tags".
His thesis 6.4: "samma taggnamn kan ha olika analytisk funktion beroende på kontext" - the facets
say what function a tag has in a chunk. So two chunks that share a tag are tied in the same
sense only when the tag has the same function on both edges.

A tag's role on an edge (mine): the facet in which that edge stands highest in the ranking (its
place in each facet's ranking over all edges, the four compared; the layer's positions). Two
edges of one tag have the same role when that facet is the same.

From the chunks the arm as it stands delivers inside 72,000 characters (the persons step, the
hundred, cached first calls, no lane call), every tag of a delivered chunk leads to the other
chunks of the border that carry it: a link, of the same role or of a different role. Counted:
the chunks reached that are not delivered, how many a question and how often they hold a cited
record: reached by a same-role link, reached only by different-role links; from a delivered
chunk that holds a cited record and from one that does not; with both chunks one record kind;
by the tag's size. The base: a chunk of the border not delivered. The gold ids are read inside;
numbers only.
"""
import json
import os
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
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the facets as link roles")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e = layer["edge_tag"], layer["edge_chunk"]
role = np.argmax(layer["pos"][:, 1:], axis=1)                 # the facet the edge stands highest in
kinds = np.array([str(row["kind"]) for row in p.chunk_rows])
edges_of_chunk = defaultdict(list)
edges_of_tag = defaultdict(list)
for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist())):
    edges_of_chunk[c].append(k)
    edges_of_tag[t].append(k)
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)

captured = {}
the_hand = V._hand_over


def recording(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


V._hand_over = recording

tally = defaultdict(lambda: [0, 0])          # reached chunks, of them cited
base = [0, 0]
size_of_tag = {}
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    delivered = set(captured["delivered"])
    border, _ = V.scope_by_name(q.question, p.tree, n)
    gold = np.array([bool(cites & records[i]) for i in range(n)])
    outside = [i for i in np.flatnonzero(border).tolist() if i not in delivered]
    base[0] += len(outside)
    base[1] += int(gold[outside].sum())
    reached = defaultdict(lambda: {"same": False, "other": False, "same_kind_same": False, "same_kind_other": False,
                                   "from_cited_same": False, "from_cited_other": False, "from_uncited_same": False,
                                   "from_uncited_other": False, "sizes": set()})
    for s in delivered:
        for e1 in edges_of_chunk[s]:
            t = int(tag_e[e1])
            ends = [e2 for e2 in edges_of_tag[t] if border[chunk_e[e2]] and chunk_e[e2] not in delivered]
            size = 1 + len(ends) + sum(1 for e2 in edges_of_tag[t] if chunk_e[e2] in delivered and chunk_e[e2] != s)
            for e2 in ends:
                c = int(chunk_e[e2])
                same = role[e1] == role[e2]
                r = reached[c]
                r["same" if same else "other"] = True
                if kinds[s] == kinds[c]:
                    r["same_kind_same" if same else "same_kind_other"] = True
                r[("from_cited_" if gold[s] else "from_uncited_") + ("same" if same else "other")] = True
                r["sizes"].add(size)
    for c, r in reached.items():
        cited = bool(gold[c])
        small = min(r["sizes"])
        for key, ok in (("reached by a same-role link", r["same"]),
                        ("reached only by different-role links", r["other"] and not r["same"]),
                        ("one record kind: reached by a same-role link", r["same_kind_same"]),
                        ("one record kind: reached only by different-role links", r["same_kind_other"] and not r["same_kind_same"]),
                        ("from a cited chunk: by a same-role link", r["from_cited_same"]),
                        ("from a cited chunk: only by different-role links", r["from_cited_other"] and not r["from_cited_same"]),
                        ("from an uncited chunk: by a same-role link", r["from_uncited_same"]),
                        ("from an uncited chunk: only by different-role links", r["from_uncited_other"] and not r["from_uncited_same"])):
            if ok:
                tally[key][0] += 1
                tally[key][1] += cited
        tally[("smallest tag", small)][0] += 1
        tally[("smallest tag", small)][1] += cited
        if r["same"]:
            tally[("smallest tag, same role", small)][0] += 1
            tally[("smallest tag, same role", small)][1] += cited
V._hand_over = the_hand

count = len(wanted)
print(f"\na chunk of the border that is not delivered holds a cited record {base[1] / base[0]:.1%} of the time")
print("chunks reached from the delivered ones through a shared tag, not delivered themselves: how many a question | share holding a cited record")
for key in ("reached by a same-role link", "reached only by different-role links",
            "one record kind: reached by a same-role link", "one record kind: reached only by different-role links",
            "from a cited chunk: by a same-role link", "from a cited chunk: only by different-role links",
            "from an uncited chunk: by a same-role link", "from an uncited chunk: only by different-role links"):
    r = tally[key]
    print(f"  {key:55s}: {r[0] / count:6.1f} | {r[1] / max(r[0], 1):.1%}")
sizes = sorted({k[1] for k in tally if isinstance(k, tuple) and k[0] == "smallest tag"})
bounds = [2, 3, 5, 10, 20, 10 ** 9]
print("by the size of the smallest tag that reaches it (chunks carrying it in the border): all links | same-role links")
for lo, hi in zip(bounds, bounds[1:]):
    a = [tally[("smallest tag", s)] for s in sizes if lo <= s < hi]
    b = [tally[("smallest tag, same role", s)] for s in sizes if lo <= s < hi]
    na, ca = sum(x[0] for x in a), sum(x[1] for x in a)
    nb, cb = sum(x[0] for x in b), sum(x[1] for x in b)
    print(f"  {lo:3d} to {hi - 1 if hi < 10 ** 9 else 'more':>4}: {na / count:6.1f} a question, {ca / max(na, 1):.1%} | {nb / count:6.1f}, {cb / max(nb, 1):.1%}")
print("done", flush=True)
