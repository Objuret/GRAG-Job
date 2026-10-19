"""Same arm, the 10-07 folder (A) against the August folder (B): what the rows share.
Counts and numbers only; no text is printed."""
import hashlib
import json
import statistics
import sys

from folders import ALL

sys.stdout.reconfigure(encoding="utf-8")


def rows(p):
    with open(p, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def h(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


for arm in ("luc", "vec"):
    a = {r["id"]: r for r in rows(ALL[f"A.{arm}"] / "arm_outputs.jsonl")}
    b = {r["id"]: r for r in rows(ALL[f"B.{arm}"] / "arm_outputs.jsonl")}
    ids = [i for i in a if i in b]
    same_ids = sum(1 for i in ids if a[i]["context_ids"] == b[i]["context_ids"])
    same_set = sum(1 for i in ids if set(a[i]["context_ids"]) == set(b[i]["context_ids"]))
    same_ctx = sum(1 for i in ids if a[i]["contexts"] == b[i]["contexts"])
    same_ans = sum(1 for i in ids if a[i]["answer"] == b[i]["answer"])
    same_bnd = sum(1 for i in ids if a[i]["meta"]["char_budget"]["boundary"] == b[i]["meta"]["char_budget"]["boundary"])
    jac = []
    first_diff = []
    for i in ids:
        x, y = a[i]["context_ids"], b[i]["context_ids"]
        jac.append(len(set(x) & set(y)) / len(set(x) | set(y)))
        k = next((n for n, (p, q) in enumerate(zip(x, y)) if p != q), None)
        if k is not None:
            first_diff.append(k)
    print(f"{arm}: questions in both {len(ids)}")
    print(f"   identical context_ids list (same ids, same order): {same_ids}/{len(ids)}   same id set: {same_set}/{len(ids)}")
    print(f"   identical contexts list (every text equal)        : {same_ctx}/{len(ids)}   identical cut piece record: {same_bnd}/{len(ids)}")
    print(f"   identical answer text                             : {same_ans}/{len(ids)}")
    print(f"   overlap of the two id sets (shared / union) min/median/max: {min(jac):.4f} / {statistics.median(jac):.4f} / {max(jac):.4f}")
    if first_diff:
        print(f"   rows whose order first differs at a rank: {len(first_diff)}; that rank (0-based) min/median/max: {min(first_diff)} / {statistics.median(first_diff)} / {max(first_diff)}")
    ea = {(r["question_id"], r["metric"]): r["value"] for r in rows(ALL[f"A.{arm}"] / "eval_results.jsonl")}
    eb = {(r["question_id"], r["metric"]): r["value"] for r in rows(ALL[f"B.{arm}"] / "eval_results.jsonl")}
    for m in ("context_precision_id", "context_recall_id", "context_precision_nonllm", "context_recall_nonllm"):
        eq = sum(1 for i in ids if ea[(i, m)] == eb[(i, m)])
        print(f"   {m:<26} equal value in both: {eq}/{len(ids)}")

print()
print("generator rows with cached_input_tokens > 0 (A): tokens_in, cached, tokens_in - cached, tokens_out, time_s, attempts, whole units")
for name in ("A.luc", "A.vec"):
    rs = rows(ALL[name] / "arm_outputs.jsonl")
    med = statistics.median(r["generator"]["tokens_in"] for r in rs if r["generator"]["cached_input_tokens"] == 0)
    print(f"  {name}: median tokens_in of the rows with cached == 0: {med}")
    for n, r in enumerate(rs):
        g = r["generator"]
        if g["cached_input_tokens"] > 0:
            print(f"     row {n:>3}: tokens_in {g['tokens_in']}  cached {g['cached_input_tokens']}  in - cached {g['tokens_in'] - g['cached_input_tokens']}  tokens_out {g['tokens_out']}  time_s {g['time_s']:.1f}  attempts {g['attempts']}  kept {r['meta']['char_budget']['kept']}")
for name in ("B.luc",):
    rs = rows(ALL[name] / "arm_outputs.jsonl")
    z = [(n, r) for n, r in enumerate(rs) if r["generator"]["tokens_in"] == 0]
    print(f"  {name}: rows with generator.tokens_in == 0: {len(z)}   their tokens_out {[r['generator']['tokens_out'] for _, r in z]}  answer chars {[len(r['answer']) for _, r in z]}  time_s {[round(r['generator']['time_s'], 1) for _, r in z]}")
