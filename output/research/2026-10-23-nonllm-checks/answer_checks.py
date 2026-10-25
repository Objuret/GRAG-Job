"""The answer-side scores without a judge (string_similarity, bleu, rouge, chrf, exact_match,
string_presence, and semantic_similarity for comparison) on the three final runs: what they are
given, what they react to, and whether they rank the arms as answer_correctness does.
Writes answer_checks.json and prints a summary."""
import asyncio
import json
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
from ragas.dataset_schema import SingleTurnSample  # noqa: E402
from ragas.metrics import (BleuScore, ChrfScore, ExactMatch, NonLLMStringSimilarity,  # noqa: E402
                           RougeScore, StringPresence)
from sacrebleu import sentence_bleu  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

RUNS = {"lucene": "lucene__gold100__cb72000__20261008T234209Z",
        "vector": "vector__gold100__cb72000__20261017T061242Z",
        "artefact": "artefact_v4__gold100__cb72000__20261023T021439Z"}
FREE = {"string_similarity": NonLLMStringSimilarity(), "bleu": BleuScore(), "rouge": RougeScore(),
        "chrf": ChrfScore(), "exact_match": ExactMatch(), "string_presence": StringPresence()}
SHOWN = list(FREE) + ["semantic_similarity"]


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def score(metric, reference, response):
    return asyncio.run(metric._single_turn_ascore(SingleTurnSample(reference=reference, response=response), None))


qs = {q["id"]: q for q in rows(ROOT / "data/questions.jsonl")}
table = []
reproduced = {}
for arm, folder in RUNS.items():
    d = ROOT / "output/k=chars" / folder
    stored = {(r["question_id"], r["metric"]): r for r in rows(d / "eval_results.jsonl")}
    same = looked = 0
    for row in rows(d / "arm_outputs.jsonl"):
        q = row["id"]
        gold = [str(g) for g in (qs[q]["ground_truth"] or [])]
        ref, ans = " ".join(gold), row["answer"] or ""
        t = {"arm": arm, "q": q, "type": qs[q].get("type"), "ref_chars": len(ref), "ans_chars": len(ans),
             "gold_items": len(gold), "ref_sentences": len(ref.split(". ")),
             "ans_sentences": len(ans.split(". ")), "first_sentence_chars": len(ans.split(". ")[0]),
             "length_bound": min(len(ref), len(ans)) / max(len(ref), len(ans), 1),
             "bleu_whole_answer": sentence_bleu(ans, [ref]).score / 100}
        for name, metric in FREE.items():
            mine = score(metric, ref, ans)
            st = stored[(q, name)]
            if st["status"] == "ok":
                looked += 1
                same += abs(mine - st["value"]) < 1e-9
            t[name] = st["value"] if st["status"] == "ok" else None
        for name in ("semantic_similarity", "answer_correctness"):
            st = stored[(q, name)]
            t[name] = st["value"] if st["status"] == "ok" else None
        table.append(t)
    reproduced[arm] = f"{same} of {looked}"

(HERE / "answer_checks.json").write_text(json.dumps({"reproduced": reproduced, "rows": table},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")


def col(arm, key):
    return np.array([t[key] for t in table if t["arm"] == arm and t[key] is not None], dtype=float)


print("stored scores given again by RAGAS on these inputs:", reproduced)
refs = col("lucene", "ref_chars")
print(f"reference answer (HERB's ground_truth joined by spaces): median {np.median(refs):.0f} chars, "
      f"gold items median {np.median(col('lucene', 'gold_items')):.0f} (max {col('lucene', 'gold_items').max():.0f})")
for arm in RUNS:
    print(f"\n=== {arm}")
    print(f"  answer: median {np.median(col(arm, 'ans_chars')):.0f} chars, median {np.median(col(arm, 'ans_sentences')):.0f} "
          f"sentences ('. '); first sentence = {np.median(col(arm, 'first_sentence_chars') / np.maximum(col(arm, 'ans_chars'), 1)):.0%} "
          f"of the answer (median)")
    for name in SHOWN + ["bleu_whole_answer", "length_bound"]:
        print(f"  {name:<20} mean {col(arm, name).mean():.4f}")
    print(f"  exact_match 1s: {int(col(arm, 'exact_match').sum())}; string_presence 1s: {int(col(arm, 'string_presence').sum())}")

print("\nSpearman correlation over all 300 answers")
pooled = {k: np.array([t[k] for t in table], dtype=float) for k in SHOWN + ["bleu_whole_answer", "answer_correctness",
                                                                         "ans_chars", "length_bound"]}
for name in SHOWN + ["bleu_whole_answer"]:
    v = pooled[name]
    ok = ~np.isnan(v) & ~np.isnan(pooled["answer_correctness"])
    rho_c = spearmanr(v[ok], pooled["answer_correctness"][ok]).statistic
    rho_l = spearmanr(v[ok], pooled["ans_chars"][ok]).statistic
    rho_b = spearmanr(v[ok], pooled["length_bound"][ok]).statistic
    print(f"  {name:<20} with answer_correctness {rho_c:+.2f} | with answer length {rho_l:+.2f} | "
          f"with the length bound min/max {rho_b:+.2f}")
order = {name: sorted(RUNS, key=lambda a: -col(a, name).mean()) for name in SHOWN + ["bleu_whole_answer", "answer_correctness"]}
print("\narm order (best first):")
for name, o in order.items():
    print(f"  {name:<20} {' > '.join(o)}")
