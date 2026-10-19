"""His concept is about ONE tag that many chunks carry ("samma taggnamn kan ha olika analytisk
funktion beroende på kontext", thesis 6.4): the facets choose among that tag's chunks. Most of
the graph tags a query tag picks carry a single chunk in the product, so the counts over the
picked edges had little to sort. Here: every graph tag inside the border that carries a chunk
holding a cited record and one that does not, by how many chunks it carries. Under one tag
every edge has the same closeness, so only the edge's values can choose.

A side count on the hundred: no arm change, no lane call (HERB_V4_OFFLINE=on, the cached first
calls; the facet net reads the query tags here). The gold ids are read inside; numbers only.

  sizes      the tags' sizes (edges inside the border) cut into three clusters on their logarithms
  per size   how often the cited chunk's edge stands above another edge of the same tag (0.50
             says nothing): each of the five values as it is and less the chunk's own mean; the
             chunk description's closeness to the question beside them
  picked     for the tags a query tag picked: the facet the model names for that query tag; the
             facet his net reads highest for it; his multi-key in the net's order with five
             clusters as the equal range; each beside the same from a query tag of another question
  changes    does the facet that sorts change with the question: per question its tags split in
             halves, the facet best on one half read on the other, beside one fixed facet
"""
import json
import os
import random
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
os.environ["HERB_V4_SCOPE_STEP"] = "name"
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import query_facets as QF  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
FACETS, FOUR = WK.FACETS, WK.RANKING_FACETS
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the facets on hub tags")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e, raw = layer["edge_tag"], layer["edge_chunk"], layer["raw"]
n_c = np.maximum(layer["n_c"], 1)
chunk_mean = np.column_stack([np.bincount(chunk_e, weights=raw[:, f], minlength=n) / n_c for f in range(len(FACETS))])
VALUES = {"as it is": raw, "less the chunk's own mean": raw - chunk_mean[chunk_e]}
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)

captured = {}
the_chain, the_interpret = WK.chain, V._interpret


def recording(layer_, query, cos_noise, k):
    out = the_chain(layer_, query, cos_noise, k)
    captured["query"], captured["out"] = query, out
    return out


def interpreting(text, prepared):
    got = the_interpret(text, prepared)
    captured["content"] = got[0]
    return got


WK.chain, V._interpret = recording, interpreting


def above(score, is_gold):
    g, h = score[is_gold][:, None], score[~is_gold][None, :]
    return float((g > h).sum() + 0.5 * (g == h).sum()), g.size * h.size


def keyed(keys):
    order = np.lexsort(tuple(keys[:, j] for j in range(keys.shape[1] - 1, -1, -1)))
    place = np.empty(len(order))
    place[order] = np.cumsum(np.r_[True, (np.diff(keys[order], axis=0) != 0).any(axis=1)])
    return -place


groups, readings_pool = [], []
for at, qid in enumerate(wanted):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    content, query, out = captured["content"], captured["query"], captured["out"]
    phrases = [t.text for t in (*content.tags, *content.query_tags)]
    read = QF.head_scores(phrases, content.description)[:, 1:]
    readings_pool += [(at, row) for row in read]
    named = np.asarray(query["named_facet"], dtype=np.int64)
    rows = np.asarray(query["cosines"], dtype=np.float64)
    d_q = np.asarray(query["d_question"], dtype=np.float64)
    border, _ = V.scope_by_name(q.question, p.tree, n)
    gold = np.array([bool(cites & records[i]) for i in range(n)])
    inside = np.flatnonzero(border[chunk_e])
    picked_by = out["picked_edge"]
    for t in np.unique(tag_e[inside]).tolist():
        e = inside[tag_e[inside] == t]
        is_gold = gold[chunk_e[e]]
        if e.size < 2 or not is_gold.any() or is_gold.all():
            continue
        row = {"question": at, "size": int(e.size), "values": {}, "description": above(d_q[chunk_e[e]], is_gold)}
        for label, values in VALUES.items():
            for f, name in enumerate(FACETS):
                row["values"][(label, name)] = above(values[e, f], is_gold)
        pickers = np.flatnonzero(picked_by[:, e[0]])
        if pickers.size:
            i = int(pickers[np.argmax(rows[pickers, t])])
            row["picked"] = {"edges": e, "is_gold": is_gold, "named": 1 + int(named[i]), "reading": read[i]}
        groups.append(row)
    if (at + 1) % 25 == 0:
        print(f"   {at + 1} questions", flush=True)
WK.chain, V._interpret = the_chain, the_interpret

sizes = np.array([g["size"] for g in groups])
level = WK.levels(np.log(sizes.astype(np.float64)), 3)
rng = random.Random(20261014)
print(f"\n{len(groups)} tags inside a border carry a cited chunk and one that is not (over {len(set(g['question'] for g in groups))} questions)")
STRATA = [("every size", np.ones(len(groups), dtype=bool))] + [
    (f"size cluster {k} ({int(sizes[level == k].min())} to {int(sizes[level == k].max())} chunks)", level == k)
    for k in sorted(set(level.tolist()), reverse=True)]
for title, mask in STRATA:
    chosen = [g for g, ok in zip(groups, mask) if ok]
    print(f"\n== {title}: {len(chosen)} tags, the middle one {int(np.median([g['size'] for g in chosen]))} chunks ==")
    for label in VALUES:
        said = []
        for name in FACETS:
            w = sum(g["values"][(label, name)][0] for g in chosen)
            m = sum(g["values"][(label, name)][1] for g in chosen)
            said.append(f"{name} {w / m:.2f}")
        print(f"  {label:26s}: " + " ; ".join(said))
    w = sum(g["description"][0] for g in chosen)
    m = sum(g["description"][1] for g in chosen)
    print(f"  the chunk description's closeness to the question: {w / m:.2f}")
    held = [g for g in chosen if "picked" in g]
    if held:
        tally = defaultdict(lambda: [0., 0])
        for g in held:
            pk = g["picked"]
            e, is_gold = pk["edges"], pk["is_gold"]
            other = rng.choice([row for k, row in readings_pool if k != g["question"]])
            for label, values in VALUES.items():
                four = values[e, 1:]
                for who, reading in (("its own", pk["reading"]), ("another question's", other)):
                    by = np.argsort(-reading, kind="stable")
                    scores = {"the facet his net reads highest": four[:, by[0]],
                              "his multi-key in the net's order": keyed(np.column_stack([WK.levels(four[:, f], 5) for f in by]))}
                    for way, score in scores.items():
                        w, m = above(np.asarray(score, dtype=np.float64), is_gold)
                        tally[(label, way, who)][0] += w
                        tally[(label, way, who)][1] += m
                w, m = above(values[e, pk["named"]], is_gold)
                tally[(label, "the facet the model names", "its own")][0] += w
                tally[(label, "the facet the model names", "its own")][1] += m
        print(f"  of them picked by a query tag: {len(held)}")
        for label in VALUES:
            def rate(way, who):
                w, m = tally[(label, way, who)]
                return f"{w / m:.2f}" if m else "-"
            print(f"    {label:26s}: the facet the model names {rate('the facet the model names', 'its own')} ; the facet his net reads "
                  f"highest {rate('the facet his net reads highest', 'its own')} (another question's {rate('the facet his net reads highest', chr(97) + 'nother question' + chr(39) + 's')}) ; "
                  f"his multi-key in the net's order {rate('his multi-key in the net' + chr(39) + 's order', 'its own')} "
                  f"(another question's {rate('his multi-key in the net' + chr(39) + 's order', chr(97) + 'nother question' + chr(39) + 's')})")
    # does the facet that sorts change with the question
    by_question = defaultdict(list)
    for g in chosen:
        by_question[g["question"]].append(g)
    for label in VALUES:
        own, fixed_w, fixed_m, used = [], np.zeros(len(FOUR)), np.zeros(len(FOUR)), 0
        for split in range(50):
            w_own = m_own = 0.
            for held_q in by_question.values():
                if len(held_q) < 2:
                    continue
                used += split == 0
                order = list(range(len(held_q)))
                rng.shuffle(order)
                half = len(order) // 2
                for first, second in ((order[:half], order[half:]), (order[half:], order[:half])):
                    score = [sum(held_q[k]["values"][(label, name)][0] for k in first)
                             / max(sum(held_q[k]["values"][(label, name)][1] for k in first), 1) for name in FOUR]
                    mine = FOUR[int(np.argmax(score))]
                    w_own += sum(held_q[k]["values"][(label, mine)][0] for k in second)
                    m_own += sum(held_q[k]["values"][(label, mine)][1] for k in second)
                    for j, name in enumerate(FOUR):
                        fixed_w[j] += sum(held_q[k]["values"][(label, name)][0] for k in second)
                        fixed_m[j] += sum(held_q[k]["values"][(label, name)][1] for k in second)
            own.append(w_own / max(m_own, 1))
        fixed = fixed_w / np.maximum(fixed_m, 1)
        print(f"  changes with the question? {label:26s}: {used} questions with two tags or more ; the question's own best facet "
              f"{np.mean(own):.3f} (between splits {np.std(own):.3f}) ; one fixed facet: "
              + " ".join(f"{name} {fixed[j]:.3f}" for j, name in enumerate(FOUR)))
print("done", flush=True)
