"""Hit and rank measures of a run's delivered ids against the gold citation ids. No model call.

    python rank_metrics.py <run folder> [<run folder> ...]

Read per question: `context_ids` of the run's arm_outputs.jsonl, in delivered order (the whole
units inside the cut), and the question's citation ids. Relevance is binary: a delivered id is
relevant when it is a citation id. Per question:

  hit              1 when at least one citation id was delivered, else 0
  reciprocal_rank  1 / rank of the first relevant delivered id, 0 when none
  average_precision  sum over relevant ranks k of (relevant in the first k) / k, divided by the
                     number of citation ids
  ndcg             sum over relevant ranks k of 1 / log2(k + 1), divided by the same sum for
                   the citation ids placed first, as many of them as the delivered list is long

Writes per_question.jsonl beside this file (run, question_id, type, metric, value) and prints
the means. Prints no question, no gold answer and no gold id.
"""
import json
import math
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(REPO / "prod"))

from harness import questions  # noqa: E402

METRICS = ("hit", "reciprocal_rank", "average_precision", "ndcg")


def measures(delivered, gold):
    seen, ranked = set(), []
    for i in delivered:
        if i not in seen:
            seen.add(i)
            ranked.append(i)
    rel_ranks = [k for k, i in enumerate(ranked, 1) if i in gold]
    hits = 0
    ap = 0.0
    for k in rel_ranks:
        hits += 1
        ap += hits / k
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(gold), len(ranked)) + 1))
    return {
        "hit": 1.0 if rel_ranks else 0.0,
        "reciprocal_rank": 1.0 / rel_ranks[0] if rel_ranks else 0.0,
        "average_precision": ap / len(gold),
        "ndcg": sum(1 / math.log2(k + 1) for k in rel_ranks) / ideal if ideal else 0.0,
        "_gold_outnumber": len(gold) > len(ranked),
        "_recall": len(rel_ranks) / len(gold),
        "_precision": len(rel_ranks) / len(ranked) if ranked else 0.0,
    }


def main(folders):
    by_id = {q.id: q for q in questions.load_questions()}
    out_rows = []
    print(f"{'run':<52}{'n':>4}" + "".join(f"{m:>19}" for m in METRICS))
    for folder in folders:
        folder = Path(folder)
        rows = [json.loads(line) for line in (folder / "arm_outputs.jsonl").open(encoding="utf-8")
                if line.strip()]
        stored = {}
        ev = folder / "eval_results.jsonl"
        if ev.is_file():
            for line in ev.open(encoding="utf-8"):
                if line.strip():
                    r = json.loads(line)
                    stored[(r["question_id"], r["metric"])] = r["value"]
        per = {m: [] for m in METRICS}
        mismatch = outnumber = 0
        for r in rows:
            q = by_id[r["id"]]
            gold = {str(c) for c in (q.citations or [])}
            if not gold:
                raise SystemExit(f"{folder.name}: a question has no citation ids")
            m = measures([str(c) for c in r["context_ids"]], gold)
            outnumber += m["_gold_outnumber"]
            for name in ("recall", "precision"):
                s = stored.get((r["id"], f"context_{name}_id"))
                mismatch += s is not None and abs(s - m[f"_{name}"]) > 1e-9
            for name in METRICS:
                per[name].append(m[name])
                out_rows.append({"run": folder.name, "question_id": r["id"], "type": q.type,
                                 "metric": name, "value": m[name]})
        print(f"{folder.name:<52}{len(rows):>4}" + "".join(f"{st.mean(per[m]):>19.4f}" for m in METRICS))
        print(f"{'':<52}{'':>4}  questions with a hit: {int(sum(per['hit']))}; recall and precision "
              f"recomputed here differ from the stored id scores on {mismatch} values; questions "
              f"with more citation ids than delivered ids: {outnumber}")
    with (HERE / "per_question.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for r in out_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"per-question values: {len(out_rows)} rows -> {(HERE / 'per_question.jsonl').relative_to(REPO)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
