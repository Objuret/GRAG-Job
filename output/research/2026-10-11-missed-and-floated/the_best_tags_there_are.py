"""The agent's own question, 2026-10-11: could the tags find the gold at all, if the question's tags
were the right ones. On the gold's fullest day none of a question's about 11 query tags is the
same thing as a tag on that day's chunks (the middle). So: take the graph's own tags inside the
question's product and look, with the gold in hand, for the best few of them. This says what the
tag path could reach if the query side named tags that exist in the graph; it is not a retrieval.

On the hundred, inside the question's product, no model call, no query side. Tags are picked one
at a time, each time the tag that most raises the balance between the gold chunks covered and the
chunks taken that are not gold (the harmonic mean of the two shares), until no tag raises it or
as many tags are picked as the question has query tags (11 at the middle).

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_best_tags_there_are.py [gold100]
"""
import json
import os
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
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
MOST = 11

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the best tags there are")
layer, n = p.layer, len(p.chunk_ids)
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
chunks_of_tag = defaultdict(set)
for e in range(et.size):
    chunks_of_tag[int(et[e])].add(int(ec[e]))

facts = defaultdict(list)
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    gold = {i for i in range(n) if records[i] & cites}
    main = Counter(branch_of[sorted(gold)].tolist()).most_common(1)[0][0]
    inside = set(np.flatnonzero(branch_of == main).tolist())
    gold &= inside
    here = {t: chunks & inside for t, chunks in chunks_of_tag.items()}
    here = {t: chunks for t, chunks in here.items() if chunks & gold}
    taken, best, picked = set(), 0., 0
    while picked < MOST:
        top, top_value = None, best
        for t, chunks in here.items():
            union = taken | chunks
            hit = len(union & gold)
            value = 2 * hit / (len(union) + len(gold))
            if value > top_value + 1e-12:
                top, top_value = t, value
        if top is None:
            break
        taken |= here.pop(top)
        best = top_value
        picked += 1
    covered = len(taken & gold)
    facts["tags of the product that sit on a gold chunk"].append(len(here) + picked)
    facts["tags picked"].append(picked)
    facts["chunks those tags bring"].append(len(taken))
    facts["share of the gold chunks among them (of the gold)"].append(covered / max(len(gold), 1))
    facts["share of those chunks that are gold"].append(covered / max(len(taken), 1))
    facts["characters of those chunks"].append(int(length[sorted(taken)].sum()) if taken else 0)
    got = set().union(*(records[i] for i in taken)) if taken else set()
    facts["cited records in those chunks (what context_recall_id would be if they all fit)"].append(
        len(cites & got) / len(cites))
    facts["they fit in the 72,000"].append(float(length[sorted(taken)].sum() <= BUDGET) if taken else 1.)

print(f"{SET}: {len(wanted)} questions, inside the question's product; at most {MOST} tags picked with the gold in hand")
for name, values in facts.items():
    if name == "they fit in the 72,000":
        print(f"  {name}: on {int(sum(values))} of {len(values)} questions")
        continue
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    digits = 2 if "share" in name or "cited" in name else 0
    print(f"  {name}: {mid:,.{digits}f} ({q1:,.{digits}f}-{q3:,.{digits}f}); mean {float(np.mean(values)):,.{2 if digits else 0}f}")
print("done", flush=True)
