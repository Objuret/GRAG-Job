"""The arm's border as built on 2026-10-11 (`v4_walk.border_by_nearness` on the chunk descriptions'
closeness to the question): on the hundred, does it keep the gold's branch? Cached query vectors,
no model call. The gold ids are read inside this script; it prints counts only.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/border_gauge.py [gold100]
"""
import json
import os
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"       # the description texts are not needed here

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the border gauge")
n = len(p.chunk_ids)
docs, records = {}, []
for row in p.chunk_rows:
    records.append(frozenset(str(x) for x in _resolve_chunk(row, docs)[1]))
branches = dict(V.tree_level(p.tree, "product"))
names = sorted(branches)
branch_of = np.full(n, -1, dtype=np.int64)
for b, name in enumerate(names):
    branch_of[branches[name]] = b
found = {k: Counter() for k in (3, 4, 5, 6, 7)}
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    gold = np.flatnonzero([bool(records[i] & cites) for i in range(n)])
    main = names[Counter(branch_of[gold].tolist()).most_common(1)[0][0]]
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    for k in found:
        _, record = WK.border_by_nearness(d_question, branches, k)
        kept = record["kept"]
        found[k]["the gold's branch alone" if kept == [main] else "the gold's branch with others" if main in kept
                 else "nothing cut" if record["nothing_cut"] else "another branch"] += 1
print(f"{SET}: {len(wanted)} questions; the border from the chunk descriptions' closeness to the question")
for k, counts in found.items():
    print(f"  cut into {k} clusters: " + ", ".join(f"{name} {count}" for name, count in counts.most_common()))
print("done", flush=True)
