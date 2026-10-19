"""The check behind `the_link_agreement_in_ranks.py`: a chunk reached by more links has more
chances at a high agreement and at a same-role link, and more links may by themselves mean a
cited chunk. So the same counts are made per number of links that reach the chunk (a link: a
delivered chunk and one of its tags; the chunk at the other end not delivered).

Agreement and role as in the two counts before: ranks among the tag's chunks in each facet; the
agreement of two chunks' orders of the four facets (6 the same order, 0 reversed); the role is
the facet a chunk ranks best in among the tag's chunks. The persons step as it stood, facets off,
the hundred, cached first calls, no lane call. The gold ids are read inside; numbers only.
"""
import json
import os
import sys
import warnings
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_FACETS"] = "off"
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
PAIRS = list(combinations(range(4), 2))
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the link agreement by links")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, place = layer["edge_tag"], layer["edge_chunk"], layer["pos"][:, 1:]
kinds = np.array([str(row["kind"]) for row in p.chunk_rows])
edges_of_tag, tags_of_chunk = defaultdict(list), defaultdict(list)
for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist())):
    edges_of_tag[t].append(k)
    tags_of_chunk[c].append(t)
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)


def agreement(ua, uc):
    s = 0.
    for f, g in PAIRS:
        a, c = np.sign(ua[f] - ua[g]), np.sign(uc[f] - uc[g])
        s += 1. if a and a == c else (0.5 if not a or not c else 0.)
    return s


def band(m):
    return "1 link" if m == 1 else ("2 links" if m == 2 else ("3 to 5 links" if m <= 5 else "6 links or more"))


captured = {}
the_hand = V._hand_over


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


V._hand_over = hand_rec
single_agree = defaultdict(lambda: [0, 0])
single_role = defaultdict(lambda: [0, 0])
by_band_agree = defaultdict(lambda: [0, 0])
by_band_role = defaultdict(lambda: [0, 0])
per_link = defaultdict(lambda: [0, 0])
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    delivered = set(captured["delivered"])
    border, _ = V.scope_by_name(q.question, p.tree, n)
    gold = np.array([bool(cites & records[i]) for i in range(n)])
    links = defaultdict(list)                      # reached chunk -> [(agreement, same role)]
    for a in delivered:
        for t in tags_of_chunk[a]:
            e = [k for k in edges_of_tag[t] if border[chunk_e[k]]]
            if len(e) < 2:
                continue
            e = np.array(e)
            ranks = np.column_stack([rankdata(-place[e, f], method="average") for f in range(place.shape[1])])
            best = np.argmin(ranks, axis=1)
            at = {int(chunk_e[k]): j for j, k in enumerate(e)}
            ja = at[a]
            for c, jc in at.items():
                if c == a or c in delivered:
                    continue
                s = agreement(ranks[ja], ranks[jc])
                links[c].append((s, int(best[jc]) == int(best[ja])))
                per_link[int(np.floor(s))][0] += 1
                per_link[int(np.floor(s))][1] += int(gold[c])
    for c, got in links.items():
        g = int(gold[c])
        m = len(got)
        top = max(s for s, _ in got)
        same = any(r for _, r in got)
        if m == 1:
            single_agree[int(np.floor(top))][0] += 1
            single_agree[int(np.floor(top))][1] += g
            single_role[same][0] += 1
            single_role[same][1] += g
        hi = "highest agreement 5 or 6" if top >= 5 else "highest agreement 4 or less"
        by_band_agree[(band(m), hi)][0] += 1
        by_band_agree[(band(m), hi)][1] += g
        by_band_role[(band(m), same)][0] += 1
        by_band_role[(band(m), same)][1] += g
V._hand_over = the_hand

count = len(wanted)
print("\nchunks reached by exactly one link, by the agreement of the two chunks' facet orders:")
for level in sorted(single_agree):
    m, g = single_agree[level]
    print(f"  {level}: {m / count:5.1f} a question, {g / max(m, 1):.1%} cited")
for same in (True, False):
    m, g = single_role[same]
    print(f"  one link, {'same role' if same else 'other role'}: {m / count:5.1f} a question, {g / max(m, 1):.1%} cited")
print("\nper number of links that reach the chunk:")
for b in ("1 link", "2 links", "3 to 5 links", "6 links or more"):
    parts = []
    for hi in ("highest agreement 5 or 6", "highest agreement 4 or less"):
        m, g = by_band_agree[(b, hi)]
        parts.append(f"{hi}: {m / count:5.1f} a question, {g / max(m, 1):.1%} cited")
    for same in (True, False):
        m, g = by_band_role[(b, same)]
        parts.append(f"{'a same-role link' if same else 'only other roles'}: {m / count:5.1f} a question, {g / max(m, 1):.1%} cited")
    print(f"  {b}:\n    " + "\n    ".join(parts))
print("\nevery link counted once, by its agreement (a chunk counted once per link):")
for level in sorted(per_link):
    m, g = per_link[level]
    print(f"  {level}: {m / count:6.1f} links a question, {g / max(m, 1):.1%} lead to a cited chunk")
print("done", flush=True)
