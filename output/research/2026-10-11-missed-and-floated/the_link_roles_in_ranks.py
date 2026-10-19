"""His 2026-10-15 "you keep giving them fucking values all the time, its a RANKING system.. so, jsut
fucking try using the actual rank relationships? such as.. when that happens, compare to other
chunks that tag has etc, is there a correlation to the rank of the facet and the good chunks vs
bad ETC", said of the tag links between chunks. Ranks only, inside one tag.

For a tag inside the border with two chunks or more, its chunks are ranked against each other in
each facet (1 = the chunk where the tag stands highest in that facet). A chunk's best facet in the
tag: the facet in which its rank among the tag's chunks is best (ties: the first in the fixed
order, mine).

From each chunk the arm delivers (the persons step, the hundred, cached first calls, no lane call),
through each of its tags, to the tag's other chunks that are not delivered:
  role       the reached chunk's best facet in the tag is the same as the delivered chunk's, or not
  rank       the reached chunk's rank in the delivered chunk's best facet, among the tag's chunks
             (0 the first, 1 the last): cited reached chunks against the others
  next to    the reached chunk stands right next to the delivered chunk in that facet's ranks
each also with both chunks one record kind. The base: a chunk of the border not delivered. The
gold ids are read inside; numbers only.
"""
import json
import os
import sys
import warnings
from collections import defaultdict
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
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the link roles in ranks")
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

captured = {}
the_hand = V._hand_over


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


V._hand_over = hand_rec
tally = defaultdict(lambda: [0, 0])
places = defaultdict(lambda: [0., 0])
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
    reached = defaultdict(lambda: defaultdict(bool))
    for a in delivered:
        for t in tags_of_chunk[a]:
            e = [k for k in edges_of_tag[t] if border[chunk_e[k]]]
            if len(e) < 2:
                continue
            e = np.array(e)
            ranks = np.column_stack([rankdata(-place[e, f], method="average") for f in range(place.shape[1])])
            u = (ranks - 1) / (len(e) - 1)                                   # 0 the first, 1 the last
            best = np.argmin(u, axis=1)
            at = {int(chunk_e[k]): j for j, k in enumerate(e)}
            ja = at[a]
            fa = int(best[ja])
            for c, jb in at.items():
                if c == a or c in delivered:
                    continue
                one = kinds[c] == kinds[a]
                r = reached[c]
                same = int(best[jb]) == fa
                r["same role"] |= same
                r["other role"] |= not same
                if one:
                    r["one kind: same role"] |= same
                    r["one kind: other role"] |= not same
                nxt = abs(ranks[jb, fa] - ranks[ja, fa]) <= 1
                r["next to it"] |= nxt
                r["not next to it"] |= not nxt
                places[("all", bool(gold[c]))][0] += u[jb, fa]
                places[("all", bool(gold[c]))][1] += 1
                if one:
                    places[("one kind", bool(gold[c]))][0] += u[jb, fa]
                    places[("one kind", bool(gold[c]))][1] += 1
    for c, r in reached.items():
        g = bool(gold[c])
        for key, ok in (("reached by a same-role link (ranks inside the tag)", r["same role"]),
                        ("reached only by other-role links", r["other role"] and not r["same role"]),
                        ("one record kind: same role", r["one kind: same role"]),
                        ("one record kind: only other roles", r["one kind: other role"] and not r["one kind: same role"]),
                        ("right next to the delivered chunk in its best facet", r["next to it"]),
                        ("never right next to it", r["not next to it"] and not r["next to it"])):
            if ok:
                tally[key][0] += 1
                tally[key][1] += g
V._hand_over = the_hand

count = len(wanted)
print(f"\na chunk of the border not delivered is cited {base[1] / base[0]:.1%} of the time")
for key, (m, g) in tally.items():
    print(f"  {key:55s}: {m / count:5.1f} a question, {g / max(m, 1):.1%} cited")
for scope in ("all", "one kind"):
    cited, other = places[(scope, True)], places[(scope, False)]
    print(f"  {scope}: in the delivered chunk's best facet, where the reached chunks rank among the tag's chunks (0 first, 1 last): "
          f"cited {cited[0] / max(cited[1], 1):.2f}, not cited {other[0] / max(other[1], 1):.2f}")
print("done", flush=True)
