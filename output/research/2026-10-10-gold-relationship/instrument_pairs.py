"""The facet instrument read directly between the query side and the chunks: the pairs to run.

On the graph's edges the instrument read (tag, chunk text). Here the same instrument is to read
(query tag, chunk text) for every chunk of the question's branch, so a query tag gets its own
five readings against a chunk, with no graph tag in between. Beside the query tags the query
description and the question go in as phrases too; for those only the backbone's own relevance
score is of use.

Writes the pairs in the form the desktop's extractor takes (`edge_id`, `tag`, `chunk_id`) and a
side file saying what each phrase is. The branch is the one most of the question route's own
delivery sits in (the gauge that needs no gold). No model call; the query side is the cached one.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/instrument_pairs.py 10smoke
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "10smoke"
BUDGET = 72000
wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("instrument pairs")
n = len(p.chunk_ids)
docs, length = {}, np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    length[i] = len(_resolve_chunk(row, docs)[0])
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
id_rank = p.layer["id_rank"]

out = HERE / f"instrument_pairs__{SET}.jsonl"
side = {}
pairs = 0
with out.open("w", encoding="utf-8", newline="\n") as f:
    for qi, qid in enumerate(wanted):
        q = by_id[qid]
        content, _, _ = V._interpret(q.question, p)
        d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
        order = np.lexsort((id_rank, -d_question))
        fits = np.cumsum(length[order]) <= BUDGET
        own = order[:int(np.argmin(fits))]
        counts = np.bincount(branch_of[own], minlength=len(branches))
        branch = int(counts.argmax())
        inside = np.flatnonzero(branch_of == branch)
        phrases = ([{"role": "tag", "text": t.text, "facet": t.facet} for t in content.tags]
                   + [{"role": "question tag", "text": t.text, "facet": t.facet} for t in content.query_tags]
                   + [{"role": "description", "text": content.description, "facet": None},
                      {"role": "question", "text": q.question, "facet": None}])
        side[qid] = {"index": qi, "branch": branches[branch][0], "chunks": [p.chunk_ids[i] for i in inside],
                     "phrases": phrases}
        for pi, phrase in enumerate(phrases):
            for i in inside:
                f.write(json.dumps({"edge_id": f"{qi}|{pi}|{p.chunk_ids[i]}", "tag": phrase["text"],
                                    "chunk_id": p.chunk_ids[i]}, ensure_ascii=False) + "\n")
                pairs += 1
(HERE / f"instrument_pairs__{SET}.side.json").write_text(json.dumps(side, ensure_ascii=False), encoding="utf-8")
print(f"{SET}: {len(wanted)} questions, {pairs} pairs -> {out.name}")
