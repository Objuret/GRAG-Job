"""The two id scores recomputed from the rows and the question file's citation ids, against
the stored eval rows. Definitions read from the installed ragas 0.4.3 source
(IDBasedContextRecall, IDBasedContextPrecision): sets of ids; recall = cited ids found among
the retrieved / cited ids; precision = retrieved ids that are cited / retrieved ids.
Ids and numbers only."""
import json
import math
import sys

from folders import ALL, REPO

sys.stdout.reconfigure(encoding="utf-8")


def rows(p):
    with open(p, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


q = {}
with open(REPO / "data" / "questions.jsonl", encoding="utf-8") as fh:
    for line in fh:
        if line.strip():
            d = json.loads(line)
            q[d["id"]] = d

for name in sys.argv[1:] or ["A.luc", "A.vec", "B.luc", "B.vec"]:
    out = rows(ALL[name] / "arm_outputs.jsonl")
    ev = {(r["question_id"], r["metric"]): r["value"] for r in rows(ALL[name] / "eval_results.jsonl")}
    rec_eq = pre_eq = 0
    rec, pre, rec_piece = [], [], []
    no_cites = 0
    for r in out:
        cites = set(str(c) for c in (q[r["id"]].get("citations") or []))
        got = set(str(c) for c in r["context_ids"])
        if not cites:
            no_cites += 1
            continue
        rv = len(cites & got) / len(cites)
        pv = len(cites & got) / len(got)
        piece = r["meta"]["char_budget"]["boundary"]
        got2 = got | ({str(piece["id"])} if piece else set())
        rec.append(rv)
        pre.append(pv)
        rec_piece.append(len(cites & got2) / len(cites))
        rec_eq += math.isclose(rv, ev[(r["id"], "context_recall_id")], abs_tol=1e-12)
        pre_eq += math.isclose(pv, ev[(r["id"], "context_precision_id")], abs_tol=1e-12)
    n = len(rec)
    print(f"{name}: rows {len(out)}, rows with no citation ids {no_cites}")
    print(f"   context_recall_id    recomputed == stored: {rec_eq}/{n}   mean recomputed {sum(rec) / n:.6f}")
    print(f"   context_precision_id recomputed == stored: {pre_eq}/{n}   mean recomputed {sum(pre) / n:.6f}")
    print(f"   context_recall_id with the cut piece's id counted as retrieved: mean {sum(rec_piece) / n:.6f}   rows that change: {sum(1 for a, b in zip(rec, rec_piece) if a != b)}")
