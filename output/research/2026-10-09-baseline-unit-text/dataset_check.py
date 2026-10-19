"""A run folder checked the way an analyst would open it: is every piece there, do the pieces agree,
and can each delivered text be traced back to its record. Counts and numbers only: no question,
answer, context or prompt text is printed (texts are compared, never shown).

    .venv/Scripts/python.exe output/research/2026-10-09-baseline-unit-text/dataset_check.py <run folder>
"""
import hashlib
import io
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "prod"))

from eval.ragas_catalog import metrics_to_run  # noqa: E402
from harness.contract import generator_messages  # noqa: E402
from harness.record_text import ARTIFACT_TYPES, record_text, units_digest  # noqa: E402

d = Path(sys.argv[1])
ok_all = True


def check(label, good, detail=""):
    global ok_all
    ok_all = ok_all and bool(good)
    print(f"   [{'ok' if good else 'NO'}] {label}{(' | ' + detail) if detail else ''}")


def lines(name):
    p = d / name
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.is_file() else []


rows, res, calls = lines("arm_outputs.jsonl"), lines("eval_results.jsonl"), lines("eval_calls.jsonl")
man = json.loads((d / "run_manifest.json").read_text(encoding="utf-8"))
ev = json.loads((d / "eval_manifest.json").read_text(encoding="utf-8"))
gold_ids = [json.loads(x)["id"] for x in (REPO / "data" / "gold100.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
selected = metrics_to_run()

print("1. is everything there")
check("one answer row per question of the hundred, in the hundred's order", [r["id"] for r in rows] == gold_ids, f"{len(rows)} rows")
check("no failed question on file", not lines("failures.jsonl") and man["n_failed"] == 0 and man["n_ran"] == 100)
cell = Counter((r["question_id"], r["metric"]) for r in res)
check("every question has each of the 14 scores exactly once", set(cell) == {(q, m) for q in gold_ids for m in selected} and set(cell.values()) == {1}, f"{len(res)} score rows")
check("every score row is ok, a number, between 0 and 1", all(r["status"] == "ok" and isinstance(r["value"], (int, float)) and not math.isnan(r["value"]) and -1e-9 <= r["value"] <= 1 + 1e-9 for r in res))
check("no failed score cell on file", not lines("eval_failures.jsonl"))
check("every answer is a non-empty text", all(isinstance(r["answer"], str) and r["answer"].strip() for r in rows))

print("2. do the pieces agree with each other")
bad_prompt = bad_answer = bad_usage = bad_budget = bad_scores = bad_ids = n_calls = 0
for r in rows:
    chat = [c for c in r["calls"] if c["kind"] == "chat"]
    n_calls += len(chat)
    c = chat[0]
    msgs = generator_messages(r["question"], r["contexts"])
    if c["prompt"] != msgs[1]["content"] or c["system"] != msgs[0]["content"]:
        bad_prompt += 1
    try:
        if json.loads(c["text"])["answer"] != r["answer"]:
            bad_answer += 1
    except (ValueError, KeyError):
        bad_answer += 1
    g = r["generator"]
    if (g["tokens_in"], g["tokens_out"], g["cached_input_tokens"]) != (c["usage"]["prompt_tokens"], c["usage"]["completion_tokens"], c["usage"]["cached_input_tokens"]):
        bad_usage += 1
    cb, rk = r["meta"]["char_budget"], r["meta"]["ranking"]
    if sum(map(len, r["contexts"])) != cb["chars"] or (cb["chars"] != cb["budget"] and not cb["exhausted"]) or cb["kept"] != len(r["context_ids"]):
        bad_budget += 1
    if len(rk["scores"]) != len(r["contexts"]) or rk["scores"] != sorted(rk["scores"], reverse=True):
        bad_scores += 1
    if len(set(r["context_ids"])) != len(r["context_ids"]):
        bad_ids += 1
check("one answer call per row", n_calls == len(rows), f"{n_calls} calls")
check("the kept prompt and system text are exactly what the row's question and contexts give", bad_prompt == 0, f"{bad_prompt} rows differ")
check("the kept reply of the call holds the row's answer", bad_answer == 0, f"{bad_answer} rows differ")
check("the row's token counts are the kept call's", bad_usage == 0, f"{bad_usage} rows differ")
check("delivered characters equal the budget's record (72,000 unless the ranking ran out)", bad_budget == 0, f"{bad_budget} rows differ; exhausted {sum(1 for r in rows if r['meta']['char_budget']['exhausted'])}")
check("one score per delivered context, in falling order", bad_scores == 0, f"{bad_scores} rows differ")
check("no record delivered twice to one question", bad_ids == 0, f"{bad_ids} rows")
settings = Counter((c["model"], json.dumps(c["applied"], sort_keys=True), json.dumps(sorted(c["not_applied"])), c["env_set"].get("CLAUDE_CONFIG_DIR") is not None)
                   for r in rows for c in r["calls"] if c["kind"] == "chat")
check("every answer call went out under the same settings", len(settings) == 1, f"{[(k[0], k[1], k[2]) for k in settings]}")

print("3. can each delivered text be traced back to its record")
corpus = {}
for pf in sorted((REPO / "data" / "corpus" / "Salesforce__HERB" / "products").glob("*.json")):
    data = json.loads(pf.read_text(encoding="utf-8"))
    for kind in ARTIFACT_TYPES:
        for rec in data.get(kind) or []:
            corpus.setdefault(rec["id"], (kind, rec, pf.name))
whole = partial = wrong = 0
for r in rows:
    cb = r["meta"]["char_budget"]
    for i, text in enumerate(r["contexts"]):
        if i < len(r["context_ids"]):
            kind, rec, _ = corpus[r["context_ids"][i]]
            whole += 1
            wrong += text != record_text(kind, rec)
        else:
            kind, rec, _ = corpus[cb["boundary"]["id"]]
            partial += 1
            wrong += text != record_text(kind, rec)[:cb["boundary"]["chars_kept"]]
check("every delivered context is its record's text, rebuilt from the corpus by the id the row names", wrong == 0, f"{whole} whole contexts, {partial} cut at the budget, {wrong} differ")
ids = list(corpus)
check("the manifest's unit digest is the corpus's as it stands now", man["index"]["units_sha256"] == units_digest(ids, [record_text(corpus[i][0], corpus[i][1]) for i in ids]) and man["index"]["units"] == len(ids))
check("the manifest names the commit, a clean code state and its inputs' hashes", bool(man["code_version"]["commit"]) and man["code_state"]["status"] == [] and "diff_file" not in man["code_state"] and all(man["inputs"].get(k) for k in ("questions_sha256", "ids_sha256", "corpus")),
      f"commit {man['code_version']['commit'][:7]}, ids sha {man['inputs']['ids_sha256'][:12]}")

print("4. the judging")
chat = [c for c in calls if c["kind"] == "chat"]
emb = [c for c in calls if c["kind"] == "embed"]
per = Counter((c["question_id"], c["score"]) for c in chat)
shape = Counter((s, n) for (q, s), n in per.items())
check("the same number of judge calls for a score on every question", len({s for s, n in shape}) == len(shape), f"{dict(sorted((s, n) for s, n in shape))}")
jset = Counter((c["model"], json.dumps(c["applied"], sort_keys=True), json.dumps(sorted(c["not_applied"])), len(c["system"])) for c in chat)
check("every judge call went out under the same settings, with no system text", len(jset) == 1 and list(jset)[0][3] == 0, f"{[(k[0], k[1]) for k in jset]}")
ju = ev["judge_usage"]
check("the kept judge calls add up to the manifest's totals", (len(chat), sum(c["usage"]["prompt_tokens"] for c in chat), sum(c["usage"]["completion_tokens"] for c in chat)) == (ju["calls"], ju["tokens_in"], ju["tokens_out"]),
      f"{len(chat)} calls, {sum(c['usage']['prompt_tokens'] for c in chat):,} in, {sum(c['usage']['completion_tokens'] for c in chat):,} out; embed requests kept {len(emb)}")
check("every judge call answered at its first try", all(len(c["attempts"]) == 1 and c["ok"] for c in chat))
usage_rows = sum(1 for r in res if (r.get("components") or {}).get("usage"))
check("every score row carries what its cell cost", usage_rows == len(res), f"{usage_rows} of {len(res)}")

print("5. the scores, as numbers (min / median / mean / max, and how many are exactly 0 or exactly 1)")
by = defaultdict(list)
for r in res:
    by[r["metric"]].append(r["value"])
for m in selected:
    v = by[m]
    print(f"   {m:<26} {min(v):.3f} / {st.median(v):.3f} / {st.mean(v):.3f} / {max(v):.3f} | exactly 0: {sum(1 for x in v if x == 0):>3} | exactly 1: {sum(1 for x in v if x == 1):>3}")
print("6. what a row and a manifest hold (keys)")
print(f"   row: {sorted(rows[0])}")
print(f"   row.generator: {sorted(rows[0]['generator'])}")
print(f"   row.meta: {{'char_budget': {sorted(rows[0]['meta']['char_budget'])}, 'ranking': {sorted(rows[0]['meta']['ranking'])}}}")
print(f"   run manifest: {sorted(man)}")
print(f"   score row: {sorted(res[0])} | components.usage: {sorted((res[0].get('components') or {}).get('usage') or {})}")
print(f"   files that describe the fields: {[p.name for p in d.iterdir() if p.suffix.lower() in ('.md', '.txt') and 'sleep' not in p.name] or 'none'}")
print(f"\nall checks ok: {ok_all}")
