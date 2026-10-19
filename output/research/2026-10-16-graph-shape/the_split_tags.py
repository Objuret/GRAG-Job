"""Tags that are the same word in another spelling (the arm's `same_thing_pairs`, 1,955 pairs of
graph tags) are separate nodes, so a chunk with one spelling and a chunk with the other share no
tag. A graph enhancement (mine): join each such pair into one tag. What would it add, and are the
links it adds as good as the links the graph already has?

From each handed-over chunk (the gold hundred, the arm's own order and hand-over, facets off,
cached first calls) to the chunks of the border that are not handed over:
  exact      reached through a tag the two chunks share
  joined     reached only through a tag of a same-thing pair (one spelling on each side)
Per kind of reach: chunks a question, the share holding a cited record; the joined ones also
split by whether the chunk was reached through one link only. Then the same over the whole
graph without any question: how many chunk pairs the joining ties that share no tag now. No
model call. The gold ids are read inside; numbers only.
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
os.environ["HERB_V4_FACETS"] = "off"
os.environ.pop("HERB_V4_SCOPE_STEP", None)

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

BUDGET = 72000
wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the split tags")
layer, n = p.layer, len(p.chunk_ids)
tag_e, chunk_e = layer["edge_tag"], layer["edge_chunk"]
names = [V._readable(t) for t in p.graph_tags]
pairs = WK.same_thing_pairs(names)
twin = defaultdict(set)
for a, b in pairs:
    twin[a].add(b)
    twin[b].add(a)
chunks_of_tag, tags_of_chunk = defaultdict(set), defaultdict(set)
for t, c in zip(tag_e.tolist(), chunk_e.tolist()):
    chunks_of_tag[t].add(c)
    tags_of_chunk[c].add(t)
added = set()
for a, b in pairs:
    for x in chunks_of_tag[a]:
        for y in chunks_of_tag[b]:
            if x != y and not (tags_of_chunk[x] & tags_of_chunk[y]):
                added.add((min(x, y), max(x, y)))
print(f"same-thing pairs {len(pairs)}, tags in them {len(twin)}, of them on a chunk {sum(1 for t in twin if chunks_of_tag[t])}")
print(f"chunk pairs the joining would tie that share no tag now: {len(added)}")
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
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    V.answer_one_question((qid, q.question), p, None, 50, BUDGET)
    delivered = set(captured["delivered"])
    border, _ = V.scope_by_name(q.question, p.tree, n)
    exact, joined = defaultdict(int), defaultdict(int)
    for a in delivered:
        for t in tags_of_chunk[a]:
            for c in chunks_of_tag[t]:
                if c != a and c not in delivered and border[c]:
                    exact[c] += 1
            for u in twin.get(t, ()):
                for c in chunks_of_tag[u]:
                    if c != a and c not in delivered and border[c] and not (tags_of_chunk[a] & tags_of_chunk[c]):
                        joined[c] += 1
    for c, m in exact.items():
        g = int(bool(cites & records[c]))
        tally["reached through a shared tag"][0] += 1
        tally["reached through a shared tag"][1] += g
        if m == 1:
            tally["reached through one shared tag only"][0] += 1
            tally["reached through one shared tag only"][1] += g
    for c, m in joined.items():
        if c in exact:
            continue
        g = int(bool(cites & records[c]))
        tally["reached only through a joined spelling"][0] += 1
        tally["reached only through a joined spelling"][1] += g
        if m == 1:
            tally["reached only through one joined spelling"][0] += 1
            tally["reached only through one joined spelling"][1] += g
V._hand_over = the_hand

count = len(wanted)
print()
for key, (m, g) in tally.items():
    print(f"  {key:44s}: {m / count:6.1f} chunks a question, {g / max(m, 1):5.1%} hold a cited record ({g})")
print("done", flush=True)
