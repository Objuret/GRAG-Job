"""Numbers from the two 10-07 runs on the hundred. Lengths, counts and stored values only:
no question, answer, context or gold text is printed or compared.

    .venv/Scripts/python.exe output/research/2026-10-08-baseline-review/main/rows_1007.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

REPO = Path(__file__).resolve().parents[4]
RUNS = {
    "lucene 10-07": REPO / "output/k=chars/lucene__gold100__cb72000__20261007T211014Z",
    "vector 10-07": REPO / "output/k=chars/vector__gold100__cb72000__20261007T211515Z",
    "lucene 08-14": REPO / "output/k=chars/lucene__gold100__cb72000__20260814T134547Z",
    "vector 08-14": REPO / "output/k=chars/vector__gold100__cb72000__20260814T145615Z",
}


def rows(p):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def q(vals, f):
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * f))]


print("== the answer call: output tokens against the length of the answer text")
print("run | n | answer chars: median | tokens_out: median | tokens_out per answer char: median "
      "(min, max) | rows with reasoning_tokens > 0 | rows with attempts > 1")
for name, folder in RUNS.items():
    rs = rows(folder / "arm_outputs.jsonl")
    alen = [len(r["answer"]) for r in rs]
    tout = [r["generator"].get("tokens_out", 0) for r in rs]
    ratio = [t / max(1, a) for t, a in zip(tout, alen)]
    print(f"  {name} | {len(rs)} | {median(alen):.0f} | {median(tout):.0f} | "
          f"{median(ratio):.3f} ({min(ratio):.3f}, {max(ratio):.3f}) | "
          f"{sum(1 for r in rs if r['generator'].get('reasoning_tokens', 0) > 0)} | "
          f"{sum(1 for r in rs if r['generator'].get('attempts', 0) > 1)}")

print("\n== seconds per question, as stored (10-07 runs were answered six at once)")
print("run | search_time_s: median, 90%, max | answer time_s: median, 90%, max | "
      "request_s median | retry_s sum | row keys beyond the standard ones")
std = {"id", "question", "answered_at", "answer", "contexts", "context_ids", "search_time_s",
       "generator", "retrieval", "meta"}
for name, folder in RUNS.items():
    rs = rows(folder / "arm_outputs.jsonl")
    st = [r["search_time_s"] for r in rs]
    gt = [r["generator"].get("time_s", 0.0) for r in rs]
    rq = [r["generator"].get("request_s", 0.0) for r in rs]
    extra = sorted(set().union(*(set(r) for r in rs)) - std)
    print(f"  {name} | {median(st):.3f}, {q(st, .9):.3f}, {max(st):.3f} | "
          f"{median(gt):.1f}, {q(gt, .9):.1f}, {max(gt):.1f} | {median(rq):.1f} | "
          f"{sum(r['generator'].get('retry_s', 0.0) for r in rs):.1f} | {extra}")

print("\n== delivered units per question and the cut piece")
for name, folder in RUNS.items():
    rs = rows(folder / "arm_outputs.jsonl")
    kept = [len(r["context_ids"]) for r in rs]
    chars = [sum(len(c) for c in r["contexts"]) for r in rs]
    cb = [((r.get("meta") or {}).get("char_budget") or {}) for r in rs]
    cut_piece = [b.get("boundary") for b in cb]
    kept_share = [b["chars_kept"] / b["chars_full"] for b in cut_piece if b]
    print(f"  {name} | whole units: min {min(kept)} median {median(kept):.0f} max {max(kept)} | "
          f"context chars: min {min(chars)} max {max(chars)} | rows with a cut piece: "
          f"{sum(1 for b in cut_piece if b)} | cut piece, full length in chars: median "
          f"{median([b['chars_full'] for b in cut_piece if b]):.0f} max "
          f"{max(b['chars_full'] for b in cut_piece if b)} | share of it delivered: median "
          f"{median(kept_share):.2f}")

print("\n== evaluation rows: n per score, stored values of semantic_similarity")
for name, folder in RUNS.items():
    ev = rows(folder / "eval_results.jsonl")
    per = defaultdict(list)
    for r in ev:
        per[r["metric"]].append(r)
    st = Counter(r["status"] for r in ev)
    types = Counter(r["type"] for r in per.get("context_recall_id", []))
    ss = [r["value"] for r in per.get("semantic_similarity", []) if r["status"] == "ok"]
    ac = [r["value"] for r in per.get("answer_correctness", []) if r["status"] == "ok"]
    print(f"  {name} | rows {len(ev)} | statuses {dict(st)} | question types {dict(types)}")
    if ss:
        print(f"      semantic_similarity n={len(ss)}: min {min(ss):.3f}  10% {q(ss, .1):.3f}  "
              f"median {median(ss):.3f}  90% {q(ss, .9):.3f}  max {max(ss):.3f}  "
              f"| values below 0: {sum(1 for v in ss if v < 0)}  below 0.1: {sum(1 for v in ss if v < 0.1)}")
    if ac:
        print(f"      answer_correctness n={len(ac)}: min {min(ac):.3f}  median {median(ac):.3f}  max {max(ac):.3f}")
    comp_keys = Counter(k for r in ev for k in (r.get("components") or {}))
    print(f"      keys under components: {dict(comp_keys)}")

print("\n== manifests: what each says about itself")
for name, folder in RUNS.items():
    m = json.loads((folder / "run_manifest.json").read_text(encoding="utf-8"))
    em = json.loads((folder / "eval_manifest.json").read_text(encoding="utf-8"))
    env = m.get("environment") or {}
    print(f"  {name} | run manifest keys: {sorted(m)}")
    print(f"      code_version {m.get('code_version')} | python_executable "
          f"{env.get('python_executable')} | packages {env.get('packages')}")
    print(f"      build_stats {json.dumps(m.get('build_stats'))[:300]}")
    print(f"      lane {m.get('lane')} | workers {m.get('workers')} | legs "
          f"{len(m.get('legs') or [])} | index {json.dumps(m.get('index'))[:200]}")
    print(f"      eval manifest keys: {sorted(em)} | judge_model {em.get('judge_model')} | "
          f"judge_usage {json.dumps(em.get('judge_usage'))[:260]} | elapsed "
          f"{em.get('judge_elapsed_s')} | legs {len(em.get('judge_legs') or [])}")
