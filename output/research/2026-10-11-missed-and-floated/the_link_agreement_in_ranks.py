"""His 2026-10-15 "jsut fucking try using the actual rank relationships? such as.. when that happens,
compare to other chunks that tag has etc, is there a correlation to the rank of the facet and the
good chunks vs bad ETC", pointed back to on 2026-10-16 ("i mean this part"). The count before it
(`the_link_roles_in_ranks.py`) only asked whether two chunks rank best in the same facet. This one
asks how far their whole order of the four facets agrees. Ranks only, inside one tag.

For a tag inside the border with two chunks or more, its chunks are ranked against each other in
each facet (as in the count before). A chunk's order of the four facets in the tag: the facets
from the one where it ranks best among the tag's chunks to the one where it ranks worst.
Agreement of two chunks under the tag: of the six pairs of facets, how many the two orders put the
same way round (a pair one of them calls equal counts half). 6 = the same order, 0 = reversed.

From each chunk the arm delivers (the persons step as it stood, facets off, the hundred, cached
first calls, no lane call), through each of its tags, to the tag's other chunks that are not
delivered. A reached chunk keeps the highest agreement over its links; then the same with both
chunks one record kind. Per agreement: reached chunks a question and the share cited. The gold
ids are read inside; numbers only.
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
p = V.prepare_over_corpus("the link agreement in ranks")
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
    """Of the six facet pairs, how many the two chunks' orders put the same way round."""
    s = 0.
    for f, g in PAIRS:
        a, c = np.sign(ua[f] - ua[g]), np.sign(uc[f] - uc[g])
        s += 1. if a and a == c else (0.5 if not a or not c else 0.)
    return s


captured = {}
the_hand = V._hand_over


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


V._hand_over = hand_rec
tally = {scope: defaultdict(lambda: [0, 0]) for scope in ("all", "one kind")}
base = [0, 0]
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
    best = {"all": {}, "one kind": {}}
    for a in delivered:
        for t in tags_of_chunk[a]:
            e = [k for k in edges_of_tag[t] if border[chunk_e[k]]]
            if len(e) < 2:
                continue
            e = np.array(e)
            ranks = np.column_stack([rankdata(-place[e, f], method="average") for f in range(place.shape[1])])
            at = {int(chunk_e[k]): j for j, k in enumerate(e)}
            ja = at[a]
            for c, jc in at.items():
                if c == a or c in delivered:
                    continue
                s = agreement(ranks[ja], ranks[jc])
                best["all"][c] = max(best["all"].get(c, -1.), s)
                if kinds[c] == kinds[a]:
                    best["one kind"][c] = max(best["one kind"].get(c, -1.), s)
    for scope, got in best.items():
        for c, s in got.items():
            level = int(np.floor(s))
            tally[scope][level][0] += 1
            tally[scope][level][1] += int(gold[c])
V._hand_over = the_hand

count = len(wanted)
print(f"\na chunk of the border not delivered is cited {base[1] / base[0]:.1%} of the time")
print("agreement of the two chunks' facet orders under the tag (6 = the same order, 0 = reversed); a reached chunk keeps its highest")
for scope in ("all", "one kind"):
    print(f"  {scope}:")
    for level in sorted(tally[scope]):
        m, g = tally[scope][level]
        print(f"    {level}: {m / count:5.1f} a question, {g / max(m, 1):.1%} cited")
print("done", flush=True)
