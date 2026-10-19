"""The same as `the_link_roles_on_unused_questions.py`, with steps 5 to 8 split by how many links
reach the chunk (1, 2, 3 to 5, 6 or more), since a chunk reached through more links is cited more
anyway and has more chances at a same-role link. Its docstring follows unchanged.

Does the lead hold on questions no run has used? On 2026-10-16 the count on the gold hundred
(`the_link_roles_on_the_less_targeted.py`) showed: among the chunks the question hits weakly, a
link from a handed-over chunk where the tag ranks best in the same facet in both chunks goes with
more cited chunks; among the chunks it hits well, not. The weak steps were picked after seeing,
so the same groups are counted here, fixed in advance:
  steps 5 to 8                 every reached chunk
  one link, steps 6 to 10      reached through one link only
  steps 4 or less              the chunks the question hits well
on the first hundred of the seeded draw out of the 615 questions outside both hundreds (as
`the_persons_lines_on_unused_questions.py`), and on the gold hundred the same way beside it.

No model call: the unused questions have no first call, so the order is the one that script
makes from the question alone: the descriptions' closeness and each chunk's closest tag to the
question, each cut into the arm's five clusters, the levels added (the step), the scope's
parents first inside a step. Handed over: chunks in that order while their texts fit in 72,000
characters (simpler than the arm's hand-over: no conversations whole, no product's own work).
Roles as before: a tag's chunks inside the border ranked against each other in each facet; a
chunk's role in the tag is the facet it ranks best in. The gold ids are read inside; numbers only.
"""
import json
import os
import random
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

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
CLUSTERS = 5
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
SETS = {"100 unused questions": random.Random(20261011).sample(fresh, 300)[:100],
        "the gold hundred": [q for q in every if q.id in ids_of["gold100"]]}
p = V.prepare_over_corpus("the link roles on unused questions")
layer, n_chunks = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec, place = layer["edge_tag"], layer["edge_chunk"], layer["pos"][:, 1:]
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
edges_of_tag, tags_of_chunk = defaultdict(list), defaultdict(list)
for k, (t, c) in enumerate(zip(et.tolist(), ec.tolist())):
    edges_of_tag[t].append(k)
    tags_of_chunk[c].append(t)
doc_cache = {}
records, length = [], np.zeros(n_chunks, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, doc_cache)
    records.append({str(x) for x in ids})
    length[i] = len(text)
print("prepared", flush=True)


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def closest_tag(vector):
    row = vector @ TV.T
    out = np.full(n_chunks, float(row.min()))
    np.maximum.at(out, ec, row[et])
    return out


GROUPS = ("steps 5 to 8", "steps 5 to 8, 1 link", "steps 5 to 8, 2 links", "steps 5 to 8, 3 to 5 links",
          "steps 5 to 8, 6 links or more", "steps 4 or less")
for label, drawn in SETS.items():
    tally = {g: {True: [0, 0], False: [0, 0]} for g in GROUPS}
    by_step = defaultdict(lambda: {True: [0, 0], False: [0, 0]})
    used, skipped = 0, 0
    for q in drawn:
        border, said = V.scope_by_name(q.question, p.tree, n_chunks)
        names = said["names_in_the_question"]
        if len(names) != 1:
            skipped += 1
            continue
        used += 1
        inside = np.flatnonzero(border)
        vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                            dtype=np.float64)
        D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
        step_in = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
        z = standing(D) + standing(T)
        taken = WK.majority_scopes(step_in <= max(3, int(step_in.min())), parent_of[inside])
        in_scope = np.isin(parent_of[inside], taken)
        ordered = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step_in))].tolist()
        step = dict(zip(inside.tolist(), step_in.tolist()))
        handed, total = [], 0
        for i in ordered:
            if total + length[i] > BUDGET:
                break
            total += length[i]
            handed.append(i)
        delivered = set(handed)
        cites = {str(c) for c in q.citations}
        links = defaultdict(list)
        for a in delivered:
            for t in tags_of_chunk[a]:
                e = [k for k in edges_of_tag[t] if border[ec[k]]]
                if len(e) < 2:
                    continue
                e = np.array(e)
                ranks = np.column_stack([rankdata(-place[e, f], method="average") for f in range(place.shape[1])])
                best = np.argmin(ranks, axis=1)
                at = {int(ec[k]): j for j, k in enumerate(e)}
                ja = at[a]
                for c, jc in at.items():
                    if c != a and c not in delivered:
                        links[c].append(int(best[jc]) == int(best[ja]))
        for c, got in links.items():
            g = int(bool(cites & records[c]))
            same, s = any(got), step[c]
            by_step[s][same][0] += 1
            by_step[s][same][1] += g
            m = len(got)
            band = "1 link" if m == 1 else ("2 links" if m == 2 else ("3 to 5 links" if m <= 5 else "6 links or more"))
            for grp, ok in (("steps 5 to 8", 5 <= s <= 8), (f"steps 5 to 8, {band}", 5 <= s <= 8),
                            ("steps 4 or less", s <= 4)):
                if ok:
                    tally[grp][same][0] += 1
                    tally[grp][same][1] += g
    print(f"\n{label}: {used} questions counted, {skipped} left out (not one product name in the question)")
    for grp in GROUPS:
        (ms, gs), (mo, go) = tally[grp][True], tally[grp][False]
        ps, po = gs / max(ms, 1), go / max(mo, 1)
        se = (ps * (1 - ps) / max(ms, 1) + po * (1 - po) / max(mo, 1)) ** .5
        print(f"  {grp:31s}: same role {ms / used:5.1f}/q {ps:5.1%} ({gs}) | other roles only {mo / used:5.1f}/q {po:5.1%} ({go})"
              f" | difference {(ps - po) / se if se else 0:+.1f} standard errors")
    for s in sorted(by_step):
        (ms, gs), (mo, go) = by_step[s][True], by_step[s][False]
        print(f"    step {s:2d}: same role {gs / max(ms, 1):5.1%} ({gs} of {ms}) | other roles only {go / max(mo, 1):5.1%} ({go} of {mo})")
print("done", flush=True)
