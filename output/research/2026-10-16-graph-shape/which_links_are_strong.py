"""Which relations between chunks in the graph's shape lead to cited chunks? (his 2026-10-16 goal:
"find relationships in the graph shape that can be enhanced or is related to the facets, or just
good perks overall emerging from the graph shape").

A link: a handed-over chunk, one of its tags, and another chunk of the border with that tag that
is not handed over. What a link can carry, fixed before the count (mine as readings):
  centrality   the topic facet, "how central is the tag to the topic of the chunk" (his 09-08):
               on each chunk its tags' topic values cut in two by least squares (`levels`, 2);
               the upper cluster are the chunk's central tags. A link is central at both ends,
               at one end, or at neither
  size         the tag's chunks over the graph, log, cut into the arm's five clusters (`levels`):
               2 to 3 chunks, 4 to 8, 9 to 27, 28 or more (a tag with one chunk links nothing)
  parent       both chunks under the same parent (the same channel, document, batch) or not
  role         the tag ranks best in the same facet in both chunks, among the tag's chunks
Counted three ways, since a chunk reached through more links is cited more anyway:
  every link once, by centrality, inside each size and parent
  the chunks reached through one link only, by each carrier
  every reached chunk, by how many links reach it and whether one of them is central at both ends
On the gold hundred (the arm's own order and hand-over, facets off, cached first calls) and on the
first hundred of the seeded draw of the unused questions (the order from the question alone, as
`the_persons_lines_on_unused_questions.py` makes it; the arm's hand-over). No model call. The gold
ids are read inside; numbers only.
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
os.environ["HERB_V4_FACETS"] = "off"
os.environ.pop("HERB_V4_SCOPE_STEP", None)

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
SETS = (("the gold hundred", [q for q in every if q.id in ids_of["gold100"]]),
        ("100 unused questions", random.Random(20261011).sample(fresh, 300)[:100]))
p = V.prepare_over_corpus("which links are strong")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, place, id_rank = layer["edge_tag"], layer["edge_chunk"], layer["pos"][:, 1:], layer["id_rank"]
topic = np.asarray(layer["raw"][:, 0], dtype=np.float64)
edges_of_tag, edges_of_chunk = defaultdict(list), defaultdict(list)
for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist())):
    edges_of_tag[t].append(k)
    edges_of_chunk[c].append(k)
edge_of = {(int(c), int(t)): k for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist()))}
central = np.zeros(len(tag_e), dtype=bool)
for c, ks in edges_of_chunk.items():
    ks = np.array(ks)
    central[ks] = WK.levels(topic[ks], 2) == 1 if ks.size > 1 else True
tag_ids = sorted(edges_of_tag)
size_level = dict(zip(tag_ids, WK.levels(np.log([len(edges_of_tag[t]) for t in tag_ids]), CLUSTERS).tolist()))
size_name = {}
for lv in sorted(set(size_level.values())):
    sizes = [len(edges_of_tag[t]) for t in tag_ids if size_level[t] == lv]
    size_name[lv] = f"{min(sizes)} to {max(sizes)} chunks"
parents = [str(row["parent"]) for row in p.chunk_rows]
parent_ids = {name: k for k, name in enumerate(sorted(set(parents)))}
parent_of = np.array([parent_ids[name] for name in parents], dtype=np.int64)
kinds = [str(row["kind"]) for row in p.chunk_rows]
CV = np.asarray(p.chunk_vectors, dtype=np.float64)
TV = np.asarray(p.tag_vectors, dtype=np.float64)
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("central tags per chunk: median share", float(np.median([central[np.array(ks)].mean() for ks in edges_of_chunk.values()])))
print("tag sizes:", ", ".join(f"level {lv} {size_name[lv]}" for lv in sorted(size_name)), flush=True)


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def closest_tag(vector):
    row = vector @ TV.T
    out = np.full(n, float(row.min()))
    np.maximum.at(out, chunk_e, row[tag_e])
    return out


captured = {}
the_hand = V._hand_over


def hand_rec(order, prepared, char_budget, k, cache):
    out = the_hand(order, prepared, char_budget, k, cache)
    captured["delivered"] = list(out[4])
    return out


CENTRAL = ("central at both ends", "central at one end", "central at neither")


def tally():
    return defaultdict(lambda: [0, 0])


for label, drawn in SETS:
    per_link, one_link, per_chunk = tally(), tally(), tally()
    used = 0
    for q in drawn:
        cites = {str(c) for c in q.citations}
        if label == "the gold hundred":
            V._hand_over = hand_rec
            V.answer_one_question((q.id, q.question), p, None, 50, BUDGET)
            V._hand_over = the_hand
            delivered = set(captured["delivered"])
            border, _ = V.scope_by_name(q.question, p.tree, n)
        else:
            border, said = V.scope_by_name(q.question, p.tree, n)
            names = said["names_in_the_question"]
            if len(names) != 1:
                continue
            inside = np.flatnonzero(border)
            vector = np.asarray(V._query_cosines(V._without_names(q.question, names), [], AXES)[0]["query_description_cosines"],
                                dtype=np.float64)
            D, T = (CV @ vector)[inside], closest_tag(vector)[inside]
            step = WK.levels(D, CLUSTERS) + WK.levels(T, CLUSTERS)
            z = standing(D) + standing(T)
            taken = WK.majority_scopes(step <= max(3, int(step.min())), parent_of[inside])
            in_scope = np.isin(parent_of[inside], taken)
            order = inside[np.lexsort((id_rank[inside], -z, ~in_scope, step))].tolist()
            out = V._hand_over(order, p, BUDGET, 50, doc_cache)
            delivered = set(out[4])
        used += 1
        links = defaultdict(list)
        for a in delivered:
            for t in {int(tag_e[k]) for k in edges_of_chunk[a]}:
                e = np.array([k for k in edges_of_tag[t] if border[chunk_e[k]]])
                if e.size < 2:
                    continue
                ranks = np.column_stack([rankdata(-place[e, f], method="average") for f in range(place.shape[1])])
                best = np.argmin(ranks, axis=1)
                at = {int(chunk_e[k]): j for j, k in enumerate(e)}
                ka, ja = edge_of[(a, t)], at[a]
                for c, jc in at.items():
                    if c == a or c in delivered:
                        continue
                    kc = edge_of[(c, t)]
                    cen = CENTRAL[2 - int(central[ka]) - int(central[kc])]
                    links[c].append({"central": cen, "size": size_level[t],
                                     "parent": "same parent" if parent_of[a] == parent_of[c] and kinds[a] == kinds[c] else "another parent",
                                     "role": "same role" if best[jc] == best[ja] else "another role"})
        for c, got in links.items():
            g = int(bool(cites & records[c]))
            for link in got:
                for key in ((link["central"], f"size {size_name[link['size']]}", link["parent"]),):
                    per_link[key][0] += 1
                    per_link[key][1] += g
            if len(got) == 1:
                link = got[0]
                for key in (("centrality", link["central"]), ("size", size_name[link["size"]]), ("parent", link["parent"]),
                            ("role", link["role"])):
                    one_link[key][0] += 1
                    one_link[key][1] += g
            m = len(got)
            band = "1 link" if m == 1 else ("2 links" if m == 2 else ("3 to 5 links" if m <= 5 else "6 links or more"))
            both = any(link["central"] == CENTRAL[0] for link in got)
            per_chunk[(band, "a link central at both ends" if both else "no link central at both ends")][0] += 1
            per_chunk[(band, "a link central at both ends" if both else "no link central at both ends")][1] += g
    print(f"\n{label}: {used} questions")
    print("  every link once (links a question, share leading to a cited chunk), by centrality inside each size and parent:")
    for lv in sorted(size_name):
        for par in ("same parent", "another parent"):
            cells = []
            for cen in CENTRAL:
                m, g = per_link[(cen, f"size {size_name[lv]}", par)]
                cells.append(f"{cen} {m / used:6.1f}/q {g / max(m, 1):5.1%}")
            if any(per_link[(cen, f"size {size_name[lv]}", par)][0] for cen in CENTRAL):
                print(f"    {size_name[lv]:16s} {par:15s} | " + " | ".join(cells))
    print("  chunks reached through one link only:")
    for group in ("centrality", "size", "parent", "role"):
        keys = sorted(k for k in one_link if k[0] == group)
        print("    " + " | ".join(f"{k[1]} {one_link[k][0] / used:5.1f}/q {one_link[k][1] / max(one_link[k][0], 1):5.1%}"
                                   f" ({one_link[k][1]})" for k in keys))
    print("  every reached chunk, by links and whether one is central at both ends:")
    for band in ("1 link", "2 links", "3 to 5 links", "6 links or more"):
        cells = []
        for key in ("a link central at both ends", "no link central at both ends"):
            m, g = per_chunk[(band, key)]
            cells.append(f"{key} {m / used:5.1f}/q {g / max(m, 1):5.1%} ({g})")
        print(f"    {band:16s} | " + " | ".join(cells))
print("done", flush=True)
