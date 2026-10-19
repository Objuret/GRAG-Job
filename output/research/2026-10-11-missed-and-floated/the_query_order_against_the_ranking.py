"""His 2026-10-14 "And what is coming from the query to match it against then?" The query's side
matched against the edges' facet RANKING, order only (his "we did a ranking on them").

What comes from the query, per query tag, an order of the four facets:
  named   the first model call names one facet for the tag (what the arm has); that facet first,
          the other three after it in the file's fixed order
  net     his net reads the query tag against the query description (`query_facets`, his
          2026-10-09 ruling) and its four scores put the four facets in order
  other   the net's order of a query tag of ANOTHER question (the check: does the query's own
          order matter)
What it is matched against: the edges' ranking in each facet (the mean over the 24 refits), a
pair ordered only when 23 of the 24 refits agree, else equal. Multi-key in the query tag's
order: the first facet decides where the ranking orders the pair; where it calls them equal, the
next facet; and so on.

Counted under one graph tag that a query tag picked, inside the border: a cited chunk's edge
against another edge of that tag. Of the pairs the multi-key orders, how often the cited one is
above (0.50 says nothing); all pairs, and pairs where both chunks are one record kind. Side
count, no arm change, no lane call; the gold ids are read inside; numbers only.
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
NEED = 23
z = np.load(REPO / "output/facet_pairs/rounds/round1/bootstrap/scores_b24.npz")
FOUR = [str(x) for x in z["facets"]]
if tuple(FOUR) != tuple(WK.RANKING_FACETS):
    raise SystemExit("the refits' facets are not the arm's four")
draws = z["scores"].astype(np.float64)
boot_at = {str(e): k for k, e in enumerate(z["edge_ids"])}
kind_of = {}
for line in open(REPO / "output/facet_pairs/rounds/round1/scores.jsonl", encoding="utf-8"):
    row = json.loads(line)
    kind_of[row["edge_id"]] = row["kind"]

wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the query order against the ranking")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e = layer["edge_tag"], layer["edge_chunk"]
graph_tags = [str(t) for t in p.graph_tags]
names = [f"{p.chunk_ids[c]}::{graph_tags[t]}" for t, c in zip(tag_e.tolist(), chunk_e.tolist())]
boot_of = np.array([boot_at.get(x, -1) for x in names])
kind = np.array([kind_of.get(x, "") for x in names])
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


def multikey(a, b, order):
    """+1 when the ranking holds edge a above b at the first facet of `order` that orders the pair, -1 below, 0 equal in all four."""
    out = np.zeros(a.size, dtype=np.int64)
    for f in order:
        above = (draws[a, f, :] > draws[b, f, :]).sum(axis=-1)
        here = np.where(above >= NEED, 1, np.where(draws.shape[2] - above >= NEED, -1, 0))
        out = np.where(out == 0, here, out)
    return out


groups, orders_pool = [], []
for at, qid in enumerate(wanted):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    content, query, out = captured["content"], captured["query"], captured["out"]
    phrases = [t.text for t in (*content.tags, *content.query_tags)]
    net = QF.head_scores(phrases, content.description)[:, 1:]
    named = np.asarray(query["named_facet"], dtype=np.int64)
    rows = np.asarray(query["cosines"], dtype=np.float64)
    border, _ = V.scope_by_name(q.question, p.tree, n)
    gold = np.array([bool(cites & records[i]) for i in range(n)])
    net_orders = [list(np.argsort(-net[i], kind="stable")) for i in range(len(phrases))]
    orders_pool += [(at, o) for o in net_orders]
    picked = np.flatnonzero(out["picked_edge"].any(axis=0) & border[chunk_e] & (boot_of >= 0))
    for t in np.unique(tag_e[picked]).tolist():
        e = np.flatnonzero((tag_e == t) & border[chunk_e] & (boot_of >= 0))
        g, h = e[gold[chunk_e[e]]], e[~gold[chunk_e[e]]]
        if not g.size or not h.size:
            continue
        pickers = np.flatnonzero(out["picked_edge"][:, e].any(axis=1))
        i = int(pickers[np.argmax(rows[pickers, t])])
        named_order = [int(named[i])] + [j for j in range(len(FOUR)) if j != int(named[i])]
        groups.append({"question": at, "g": g, "h": h, "named": named_order, "net": net_orders[i]})
    if (at + 1) % 25 == 0:
        print(f"   {at + 1} questions", flush=True)
WK.chain, V._interpret = the_chain, the_interpret

rng = random.Random(20261014)
tally = defaultdict(lambda: [0, 0, 0])          # cited above, ordered, pairs
for gr in groups:
    A = np.repeat(gr["g"], gr["h"].size)
    B = np.tile(gr["h"], gr["g"].size)
    one_kind = kind[A] == kind[B]
    other = rng.choice([o for k, o in orders_pool if k != gr["question"]])
    for source, order in (("named", gr["named"]), ("net", gr["net"]), ("other", other)):
        o = multikey(boot_of[A], boot_of[B], order)
        for key, mask in (("all pairs", np.ones(A.size, dtype=bool)), ("both chunks one record kind", one_kind)):
            row = tally[(source, key)]
            row[0] += int((o[mask] > 0).sum())
            row[1] += int((o[mask] != 0).sum())
            row[2] += int(mask.sum())
WORDS = {"named": "the facet the model names, first", "net": "his net's order of the four for the query tag",
         "other": "his net's order for a query tag of another question"}
print(f"\n{len(groups)} picked tags carry a cited chunk and another inside the border")
print("a cited chunk's edge against another edge of the tag, multi-key in the query tag's order on the ranking: of the pairs it "
      "orders, the cited one above (0.50 says nothing)")
for key in ("all pairs", "both chunks one record kind"):
    print(f"  {key}:")
    for source in ("named", "net", "other"):
        r = tally[(source, key)]
        print(f"    {WORDS[source]:52s}: orders {r[1]} of {r[2]} pairs, the cited one above in {r[0] / max(r[1], 1):.2f}")
print("done", flush=True)
