"""The two ID scores on the three final runs: how many records each arm passes, how much of the
passed text belongs to cited records, and which cited records were passed only in part (not
credited). Prints a summary."""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "prod")]
from harness.orchestrator import DEFAULT_CORPUS  # noqa: E402
from harness.record_text import ARTIFACT_TYPES, record_text  # noqa: E402

RUNS = {"lucene": "lucene__gold100__cb72000__20261008T234209Z",
        "vector": "vector__gold100__cb72000__20261017T061242Z",
        "artefact": "artefact_v4__gold100__cb72000__20261023T021439Z"}


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


raw, kind_of = {}, {}
for pf in sorted((Path(DEFAULT_CORPUS) / "products").glob("*.json")):
    data = json.loads(pf.read_text(encoding="utf-8"))
    for kind in ARTIFACT_TYPES:
        for rec in data.get(kind, []) or []:
            aid = rec.get("id")
            if aid is not None and str(aid) not in raw:
                raw[str(aid)], kind_of[str(aid)] = rec, kind
cites = {q["id"]: {str(c) for c in q["citations"]} for q in rows(ROOT / "data/questions.jsonl")}


def pieces_of(arm, row):
    texts = row["contexts"]
    if arm == "artefact":
        out = []
        for text, ids in zip(texts, row["meta"]["chunk_ids"]):
            ids = [str(i) for i in ids]
            if len(ids) == 1:
                out.append((text, ids[0], text == record_text(kind_of[ids[0]], raw[ids[0]])))
                continue
            at = 0
            for i in ids:
                piece = record_text(kind_of[i], raw[i])
                if at >= len(text):
                    break
                part = text[at:at + len(piece)]
                out.append((part, i, part == piece))
                at += len(piece) + 2
        return out
    ids = [str(i) for i in row["context_ids"]]
    cut = (row["meta"].get("char_budget") or {}).get("boundary")
    text_ids = ids + ([str(cut["id"])] if cut else [])
    return [(t, i, t == record_text(kind_of[i], raw[i])) for t, i in zip(texts, text_ids)]


for arm, folder in RUNS.items():
    d = ROOT / "output/k=chars" / folder
    stored = {(r["question_id"], r["metric"]): r["value"] for r in rows(d / "eval_results.jsonl")}
    credited, cited_n, char_prec, part_only, part_only_q = [], [], [], 0, 0
    for row in rows(d / "arm_outputs.jsonl"):
        c = cites[row["id"]]
        pieces = pieces_of(arm, row)
        given = {str(i) for i in row["context_ids"]}
        credited.append(len(given))
        cited_n.append(len(c))
        total = sum(len(t) for t, _, _ in pieces)
        char_prec.append(sum(len(t) for t, i, _ in pieces if i in c) / total)
        partial = {i for _, i, w in pieces if not w and i in c} - given
        part_only += len(partial)
        part_only_q += bool(partial)
    print(f"=== {arm}")
    print(f"  records credited per question: mean {np.mean(credited):.1f}; cited per question: mean {np.mean(cited_n):.1f}")
    print(f"  context_precision_id (stored mean) {np.mean([stored[(r['id'], 'context_precision_id')] for r in rows(d / 'arm_outputs.jsonl')]):.3f}; "
          f"share of passed characters that belong to cited records: mean {np.mean(char_prec):.3f}")
    print(f"  cited records passed only in part (not credited by ID): {part_only}, in {part_only_q} questions")
