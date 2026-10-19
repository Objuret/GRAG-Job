"""His 2026-10-16 "ok, but isnt this relevant for the edgecases? the less targeted ones?", said of
the tag links between chunks after the count per number of links. Two readings of "less
targeted", both counted:
  by the question  the reached chunk's step in the arm's own order (the combo: the tags' level
                   and the descriptions' level added; a higher step = the question hits it less)
  by the question, whole   questions whose first delivered chunk holds no cited record, against
                   the rest
  by the tag       general tags, on many chunks, where closeness cannot tell the tag's chunks
                   apart (the partner's reading of thesis 6.4): the tags' sizes over the graph
                   (log of the edge count) cut into the arm's number of clusters by `levels`,
                   level 1 the largest; counted per link
Per group: the reached chunks with a link where the tag has the same role in both chunks against
those with other roles only, and a high agreement of the two chunks' whole facet orders (5 or 6
of 6) against a lower one; the one-link chunks apart. Roles and agreement as in
`the_link_agreement_by_links.py` (ranks among the tag's chunks). The persons step as it stood,
facets off, the hundred, cached first calls, no lane call. The gold ids are read inside; numbers
only.
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
p = V.prepare_over_corpus("the link roles on the less targeted")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, place = layer["edge_tag"], layer["edge_chunk"], layer["pos"][:, 1:]
edges_of_tag, tags_of_chunk = defaultdict(list), defaultdict(list)
for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist())):
    edges_of_tag[t].append(k)
    tags_of_chunk[c].append(t)
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
tag_ids = sorted(edges_of_tag)
size_level = dict(zip(tag_ids, V.WK.levels(np.log([len(edges_of_tag[t]) for t in tag_ids]), V._k_nearest()).tolist()))
for lv in sorted(set(size_level.values())):
    sizes = [len(edges_of_tag[t]) for t in tag_ids if size_level[t] == lv]
    print(f"tag size level {lv}: {len(sizes)} tags, {min(sizes)} to {max(sizes)} chunks")
print("prepared", flush=True)


def agreement(ua, uc):
    s = 0.
    for f, g in PAIRS:
        a, c = np.sign(ua[f] - ua[g]), np.sign(uc[f] - uc[g])
        s += 1. if a and a == c else (0.5 if not a or not c else 0.)
    return s


captured = {}
the_hand, the_combo = V._hand_over, V.WK.cloud_combo


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


def combo_rec(*a, **kw):
    out = the_combo(*a, **kw)
    captured["step"] = np.asarray(out["step"]).copy()
    return out


V._hand_over, V.WK.cloud_combo = hand_rec, combo_rec
tally = defaultdict(lambda: [0, 0])
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    order = captured["delivered"]
    delivered, step = set(order), captured["step"]
    border, _ = V.scope_by_name(q.question, p.tree, n)
    gold = np.array([bool(cites & records[i]) for i in range(n)])
    question_group = "questions whose first delivered chunk is cited" if order and gold[order[0]] else \
        "questions whose first delivered chunk is not cited"
    links = defaultdict(list)
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
                s, same = agreement(ranks[ja], ranks[jc]), int(best[jc]) == int(best[ja])
                links[c].append((s, same))
                grp = f"links through tags of size level {size_level[t]}"
                for key in ("same role" if same else "other roles only",
                            "agreement 5 or 6" if s >= 5 else "agreement 4 or less"):
                    tally[(grp, key)][0] += 1
                    tally[(grp, key)][1] += int(gold[c])
    for c, got in links.items():
        g = int(gold[c])
        same = any(r for _, r in got)
        high = max(s for s, _ in got) >= 5
        groups = [f"step {int(step[c])}", question_group]
        if len(got) == 1:
            groups += [f"one link, step {int(step[c])}", f"one link, {question_group}"]
        for grp in groups:
            for key in ("same role" if same else "other roles only",
                        "agreement 5 or 6" if high else "agreement 4 or less"):
                tally[(grp, key)][0] += 1
                tally[(grp, key)][1] += g
V._hand_over, V.WK.cloud_combo = the_hand, the_combo

count = len(wanted)
names = sorted({grp for grp, _ in tally}, key=lambda s: (s.startswith("one link"), s.split()[-1].zfill(3) if "step" in s else s))
print()
for grp in names:
    parts = []
    for key in ("same role", "other roles only", "agreement 5 or 6", "agreement 4 or less"):
        m, g = tally[(grp, key)]
        parts.append(f"{key} {m / count:5.1f}/q {g / max(m, 1):5.1%} ({g})")
    print(f"{grp:58s} | " + " | ".join(parts))
print("done", flush=True)
