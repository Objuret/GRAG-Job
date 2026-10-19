"""For his 2026-10-12 goal "solve this" (the order): what a reader of the first hits would give. The
order is left where every vector reading leaves it; the one route not measured on clean units
is a model that reads the question and a unit together and says how well they fit. The project
has one on the desktop already, the facet instrument's backbone (the reranker
Alibaba-NLP/gte-reranker-modernbert-base, `extract_standalone.py`), used on 2026-10-11 on batch
texts for the ten. Here its pairs are written for the hundred on clean units: (the question
without the product's name, a unit of the question's product), a unit being an own
conversation whole, an own pull request, or any other chunk as the arm hands it over. A side
measurement for him to weigh: a reader in the artefact is "more ai", which he ruled out.
No lane call. The questions are written into the pairs file (the desktop's job folder holds
them already); no gold is.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/reader_pairs.py <out folder> [gold100|unused300]
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

import ties as TI  # noqa: E402
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from harness import questions as HQ  # noqa: E402

OUT = Path(sys.argv[1])
SET = sys.argv[2] if len(sys.argv) > 2 else "gold100"
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
if SET == "gold100":
    questions = [q for q in HQ.load_questions() if q.id in ids_of["gold100"]]
else:                       # the seeded draw of 300 questions in neither hundred, as the other checks use
    import random
    fresh = sorted((q for q in HQ.load_questions() if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations),
                   key=lambda q: q.id)
    questions = random.Random(20261011).sample(fresh, 300)
own_rows = [json.loads(line) for line in open(HERE / "own_units" / "own_units.jsonl", encoding="utf-8")]
unit_of_record = {}
for row in own_rows:
    for r in row["records"]:
        unit_of_record[r] = row["id"]
p = V.prepare_over_corpus("reader pairs")
n = len(p.chunk_ids)
doc_cache = {}
rows = {row["id"]: row["text"] for row in own_rows}
units_of_chunk = []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, doc_cache)
    ids = [str(x) for x in ids]
    product = str(row["parent"]).split(".")[1]
    P = TI.product(product)
    if row["kind"] in ("slack_thread_batch", "pr_batch"):
        units_of_chunk.append(list(dict.fromkeys(unit_of_record[r] for r in ids if not TI.apart(r, P))))
    else:
        uid = f"chunk|{p.chunk_ids[i]}"
        rows[uid] = text
        units_of_chunk.append([uid])
pairs = []
for q in questions:
    border, scope = V.scope_by_name(q.question, p.tree, n)
    names = scope["names_in_the_question"]
    if len(names) != 1:
        raise SystemExit(f"a question names {len(names)} products")
    bare = V._without_names(q.question, names)
    units = list(dict.fromkeys(u for i in np.flatnonzero(border).tolist() for u in units_of_chunk[i]))
    pairs.extend({"edge_id": f"{q.id}||{u}", "tag": bare, "chunk_id": u} for u in units)
used = {pair["chunk_id"] for pair in pairs}
OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "reader_rows.jsonl", "w", encoding="utf-8", newline="\n") as handle:
    for uid in sorted(used):
        handle.write(json.dumps({"chunk_id": uid, "text": rows[uid]}, ensure_ascii=False) + "\n")
with open(OUT / f"reader_pairs__{SET}.jsonl", "w", encoding="utf-8", newline="\n") as handle:
    for pair in pairs:
        handle.write(json.dumps(pair, ensure_ascii=False) + "\n")
chars = [len(rows[u]) for u in used]
print(f"{len(questions)} questions, {len(pairs)} pairs ({len(pairs) / len(questions):.0f} a question), {len(used)} units; "
      f"characters a unit: middle {int(np.median(chars))}, longest {max(chars)}")
