"""His 2026-10-15 "ok, but can it instead actually be a good scope-deteministic instead then?" The
facet ranking tells kinds of record apart, so can the query's facets set the scope one level up:
the KIND of record (a level of the tree: product, kind, channel) where the cited records lie?
Deterministic, no model naming a place.

Per question, from the query, an order of the four facets:
  named   the facets the model named across the question's query tags, the most named first
  net     his net's order of the four per query tag (`query_facets`, read against the query
          description), ranks turned into points (3, 2, 1, 0) and added over the question's tags
  other   the net's order of ANOTHER question (the check)
A kind's place in a facet: the middle place of its edges in that facet's ranking (0 bottom, 1
top; `output/facet_pairs/rounds/round1/scores.jsonl`). The kinds are put in order by their place
in the query's first facet, ties by the next facet; the first kind is the scope, then the first
two kinds.

Counted on the hundred, inside the border: how often the scope is the kind holding the most of
the question's cited chunks; the share of the cited chunks inside the scope; the share of the
product's chunks the scope keeps. Beside it: always the one kind holding the most cited chunks
over the hundred (read off the gold, a reference and not a rule). No arm change, no lane call;
the gold ids are read inside; numbers only.
"""
import json
import os
import random
import sys
import warnings
from collections import Counter, defaultdict
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
FOUR = list(WK.RANKING_FACETS)
places = defaultdict(lambda: defaultdict(list))
for line in open(REPO / "output/facet_pairs/rounds/round1/scores.jsonl", encoding="utf-8"):
    row = json.loads(line)
    for f in FOUR:
        places[row["kind"]][f].append(row[f + "_pos"])
KIND_PLACE = {k: [float(np.median(places[k][f])) for f in FOUR] for k in places}

wanted = [json.loads(line)["id"] for line in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the facets as scope")
n = len(p.chunk_ids)
kinds = [str(row["kind"]) for row in p.chunk_rows]
doc_cache = {}
records = [{str(x) for x in _resolve_chunk(row, doc_cache)[1]} for row in p.chunk_rows]
print("prepared", flush=True)

captured = {}
the_interpret = V._interpret


def interpreting(text, prepared):
    got = the_interpret(text, prepared)
    captured["content"] = got[0]
    return got


V._interpret = interpreting


def kinds_in_order(order, present):
    """The kinds present in the border, by their place in the query's first facet, ties by the next."""
    return sorted(present, key=lambda k: tuple(-KIND_PLACE[k][f] for f in order) + (k,))


questions = []
for at, qid in enumerate(wanted):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    captured.clear()
    V._interpret(q.question, p)
    content = captured["content"]
    tags = (*content.tags, *content.query_tags)
    phrases = [t.text for t in tags]
    net = QF.head_scores(phrases, content.description)[:, 1:]
    named_count = Counter(t.facet for t in tags)
    named_order = sorted(range(len(FOUR)), key=lambda j: (-named_count.get(FOUR[j], 0), j))
    points = np.zeros(len(FOUR))
    for row in net:
        points[np.argsort(-row, kind="stable")] += np.arange(len(FOUR) - 1, -1, -1)
    net_order = list(np.argsort(-points, kind="stable"))
    border, _ = V.scope_by_name(q.question, p.tree, n)
    inside = np.flatnonzero(border)
    gold = [i for i in inside.tolist() if cites & records[i]]
    questions.append({"named": named_order, "net": net_order, "kinds": Counter(kinds[i] for i in inside.tolist()),
                      "gold": Counter(kinds[i] for i in gold)})
    if (at + 1) % 25 == 0:
        print(f"   {at + 1} questions", flush=True)
V._interpret = the_interpret

overall = Counter()
for qd in questions:
    overall.update(qd["gold"])
most = overall.most_common(1)[0][0]
print(f"\nthe cited chunks of the hundred by kind: " + ", ".join(f"{k} {c}" for k, c in overall.most_common()))
print("the first facet the query gives, over the hundred: named " + ", ".join(
    f"{FOUR[j]} {c}" for j, c in Counter(qd["named"][0] for qd in questions).most_common())
      + " ; net " + ", ".join(f"{FOUR[j]} {c}" for j, c in Counter(qd["net"][0] for qd in questions).most_common()))
rng = random.Random(20261015)
rules = ("named", "net", "other", "always")
for width in (1, 2):
    tally = {rule: [0, 0., 0.] for rule in rules}       # the main kind hit, share of cited chunks inside, share of the product kept
    for k, qd in enumerate(questions):
        present = sorted(qd["kinds"])
        main = {kd for kd, c in qd["gold"].items() if c == max(qd["gold"].values())} if qd["gold"] else set()
        other = rng.choice([o for j, o in enumerate(questions) if j != k])["net"]
        for rule in rules:
            if rule == "always":
                scope = [most] + [kd for kd, _ in overall.most_common() if kd != most][:width - 1]
            else:
                scope = kinds_in_order({"named": qd["named"], "net": qd["net"], "other": other}[rule], present)[:width]
            tally[rule][0] += bool(main & set(scope))
            total = sum(qd["gold"].values())
            tally[rule][1] += sum(qd["gold"][kd] for kd in scope) / total if total else 0.
            tally[rule][2] += sum(qd["kinds"][kd] for kd in scope) / sum(qd["kinds"].values())
    words = {"named": "the facets the model named", "net": "his net's order", "other": "his net's order of another question",
             "always": "always the kinds holding the most cited chunks (read off the gold)"}
    print(f"\n== the scope is the first {width} kind{'s' if width > 1 else ''}: the kind holding the most cited chunks inside it "
          f"(of 100) | share of the cited chunks inside it | share of the product's chunks it keeps ==")
    for rule in rules:
        t = tally[rule]
        print(f"  {t[0]:3d} | {t[1] / len(questions):.2f} | {t[2] / len(questions):.2f}  {words[rule]}")
print("done", flush=True)
