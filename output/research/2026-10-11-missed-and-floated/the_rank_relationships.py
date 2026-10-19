"""His 2026-10-15 "its a RANKING system.. so, jsut fucking try using the actual rank relationships?
such as.. when that happens, compare to other chunks that tag has etc, is there a correlation to
the rank of the facet and the good chunks vs bad ETC". Ranks only.

For a graph tag inside the border (the question's product) that carries a chunk holding a cited
record (good) and one that does not (bad):
  the tag's ranking     its chunks ranked against each other in each facet (1 = the chunk where
                        that tag stands highest in the facet's ranking)
  the chunk's ranking   the chunk's own tags ranked against each other in each facet (1 = the
                        chunk's top tag in that facet)
  mutual top            the tag ranks the chunk first and the chunk ranks the tag first
Counted: how often the tag's first-ranked chunk is good, beside the share of good chunks among
the tag's chunks (what a blind pick gets); where the good chunks stand in the tag's ranking (0 the
first, 1 the last) against the bad ones; the same with the ranking taken inside one record kind
(the tag's chunks of the good chunk's kind only); how often a chunk is good when the tag is its
first-ranked tag against when it is not; mutual top against not. For two sets of tags: the tags a
query tag picked (when it happens), and every tag of the border. Also the facet the query tag
names against the other three.

The hundred, cached first calls, the `name` step's pick (each query tag's five nearest graph
tags), no lane call. The gold ids are read inside; numbers only.
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
os.environ["HERB_V4_SCOPE_STEP"] = "name"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
FOUR = list(WK.RANKING_FACETS)
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the rank relationships")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e = layer["edge_tag"], layer["edge_chunk"]
place = layer["pos"][:, 1:]                                        # each edge's place in each facet's ranking
kinds = np.array([str(row["kind"]) for row in p.chunk_rows])
edges_of_chunk, edges_of_tag = defaultdict(list), defaultdict(list)
for k, (t, c) in enumerate(zip(tag_e.tolist(), chunk_e.tolist())):
    edges_of_chunk[c].append(k)
    edges_of_tag[t].append(k)
# the chunk's ranking of its own tags, per facet: 1 = the chunk's top tag
chunk_rank = np.zeros(place.shape, dtype=np.float64)
chunk_size = np.zeros(place.shape[0], dtype=np.int64)
for c, es in edges_of_chunk.items():
    es = np.array(es)
    chunk_size[es] = es.size
    for f in range(len(FOUR)):
        chunk_rank[es, f] = rankdata(-place[es, f], method="average")
# the check: the chunk's tags in a random order (one draw per chunk), so "the tag is the chunk's first" by chance alone
rng = np.random.default_rng(20261015)
random_first = np.zeros(place.shape[0], dtype=bool)
any_first = np.zeros(place.shape[0], dtype=bool)
for c, es in edges_of_chunk.items():
    es = np.array(es)
    random_first[es[rng.integers(es.size)]] = True
    any_first[es] = (chunk_rank[es] == 1).any(axis=1)
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)

captured = {}
the_chain = WK.chain


def recording(layer_, query, cos_noise, k):
    out = the_chain(layer_, query, cos_noise, k)
    captured["query"], captured["out"] = query, out
    return out


WK.chain = recording
SETS = ("the tags a query tag picked", "every tag of the border")
T = {s: defaultdict(lambda: [0., 0.]) for s in SETS}
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    query, out = captured["query"], captured["out"]
    named = np.asarray(query["named_facet"], dtype=np.int64)
    rows = np.asarray(query["cosines"], dtype=np.float64)
    border, _ = V.scope_by_name(q.question, p.tree, n)
    gold = np.array([bool(cites & records[i]) for i in range(n)])
    picked_by = out["picked_edge"]
    for t in np.unique(tag_e[np.flatnonzero(border[chunk_e])]).tolist():
        e = np.array([k for k in edges_of_tag[t] if border[chunk_e[k]]])
        good = gold[chunk_e[e]]
        if e.size < 2 or not good.any() or good.all():
            continue
        pickers = np.flatnonzero(picked_by[:, e[0]])
        sets = [SETS[1]] + ([SETS[0]] if pickers.size else [])
        for s in sets:
            for flag, label in ((random_first[e], "random: the tag is the chunk's first"), (~random_first[e], "random: not first"),
                                (any_first[e], "the tag is the chunk's first in at least one facet"),
                                (~any_first[e], "the tag is the chunk's first in no facet")):
                T[s][("check", label)][0] += good[flag].sum()
                T[s][("check", label)][1] += flag.sum()
        named_f = int(named[pickers[np.argmax(rows[pickers, t])]]) if pickers.size else None
        for f, name in enumerate(FOUR):
            r = rankdata(-place[e, f], method="average")                 # the tag's ranking, 1 = first
            u = (r - 1) / (e.size - 1)                                    # 0 = first, 1 = last
            first = r == r.min()
            same_kind = kinds[chunk_e[e]]
            for s in sets:
                for key in (name,) + (("the facet the query tag names",) if s == SETS[0] and f == named_f else ()) \
                        + (("the other three facets",) if s == SETS[0] and named_f is not None and f != named_f else ()):
                    tt = T[s]
                    tt[(key, "first is good")][0] += good[first].mean()
                    tt[(key, "first is good")][1] += 1
                    tt[(key, "blind")][0] += good.mean()
                    tt[(key, "blind")][1] += 1
                    tt[(key, "place good")][0] += u[good].sum()
                    tt[(key, "place good")][1] += good.sum()
                    tt[(key, "place bad")][0] += u[~good].sum()
                    tt[(key, "place bad")][1] += (~good).sum()
                    for kd in np.unique(same_kind[good]).tolist():
                        m = same_kind == kd
                        if m.sum() < 2 or good[m].all():
                            continue
                        rk = rankdata(-place[e[m], f], method="average")
                        uk = (rk - 1) / (m.sum() - 1)
                        tt[(key, "one kind: place good")][0] += uk[good[m]].sum()
                        tt[(key, "one kind: place good")][1] += good[m].sum()
                        tt[(key, "one kind: place bad")][0] += uk[~good[m]].sum()
                        tt[(key, "one kind: place bad")][1] += (~good[m]).sum()
                        fk = rk == rk.min()
                        tt[(key, "one kind: first is good")][0] += good[m][fk].mean()
                        tt[(key, "one kind: first is good")][1] += 1
                        tt[(key, "one kind: blind")][0] += good[m].mean()
                        tt[(key, "one kind: blind")][1] += 1
                    top_of_chunk = chunk_rank[e, f] == 1
                    for flag, label in ((top_of_chunk, "the tag is the chunk's first"), (~top_of_chunk, "the tag is not the chunk's first")):
                        tt[(key, label)][0] += good[flag].sum()
                        tt[(key, label)][1] += flag.sum()
                    mutual = first & top_of_chunk
                    for flag, label in ((mutual, "mutual top"), (~mutual, "not mutual top")):
                        tt[(key, label)][0] += good[flag].sum()
                        tt[(key, label)][1] += flag.sum()
WK.chain = the_chain


def rate(tt, key, what):
    a, b = tt[(key, what)]
    return a / b if b else float("nan")


for s in SETS:
    tt = T[s]
    print(f"\n== {s}: {int(tt[(FOUR[0], 'blind')][1])} tags with a good and a bad chunk ==")
    keys = FOUR + (["the facet the query tag names", "the other three facets"] if s == SETS[0] else [])
    for key in keys:
        print(f"  {key}:")
        print(f"    the tag's first-ranked chunk is good {rate(tt, key, 'first is good'):.0%} (a blind pick {rate(tt, key, 'blind'):.0%}) ; "
              f"where they stand in the tag's ranking (0 first, 1 last): good {rate(tt, key, 'place good'):.2f}, bad {rate(tt, key, 'place bad'):.2f}")
        print(f"    inside one record kind: first-ranked good {rate(tt, key, 'one kind: first is good'):.0%} (blind {rate(tt, key, 'one kind: blind'):.0%}) ; "
              f"good {rate(tt, key, 'one kind: place good'):.2f}, bad {rate(tt, key, 'one kind: place bad'):.2f}")
        print(f"    the chunk is good when the tag is its first-ranked tag {rate(tt, key, 'the tag is the chunk' + chr(39) + 's first'):.0%}, "
              f"when not {rate(tt, key, 'the tag is not the chunk' + chr(39) + 's first'):.0%} ; mutual top {rate(tt, key, 'mutual top'):.0%}, "
              f"not {rate(tt, key, 'not mutual top'):.0%} ({int(tt[(key, 'mutual top')][1])} mutual-top edges)")
    print("  the checks: the chunk is good when " + " ; ".join(
        f"{label} {rate(tt, 'check', label):.0%} ({int(tt[('check', label)][1])} edges)"
        for label in ("random: the tag is the chunk's first", "random: not first",
                      "the tag is the chunk's first in at least one facet", "the tag is the chunk's first in no facet")))
    for key in FOUR:
        print(f"  {key}: edges where the tag is the chunk's first {int(tt[(key, 'the tag is the chunk' + chr(39) + 's first')][1])}")
print("done", flush=True)
