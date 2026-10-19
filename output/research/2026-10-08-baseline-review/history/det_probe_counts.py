"""Counts only, from run folders on disk. No question, answer, gold or context text is printed.

1. The three artefact_v1_det ten-question folders of 2026-08-21 (same arm, same budget): on how many
   questions the delivered ids, the delivered contexts and the answer are identical between folders.
2. T205659Z against its `__j-claude-haiku-4-5` sibling: same answers judged a second time. Per score:
   cells present in both with status ok, cells with equal value, mean and max absolute difference.
3. The two lucene and two vector hundred-question baseline folders: rows whose answer is non-empty
   while the generator's token counters are zero (the 09-25 audit's "missing token counters").

Answers and contexts are compared by sha256; values printed are counts and differences of scores.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"C:\Coding\exjobbet\GRAG-Job\output\k=chars")
V1DET = ["artefact_v1_det__10smoke__cb72000__20260821T205659Z",
         "artefact_v1_det__10smoke__cb72000__20260821T211728Z",
         "artefact_v1_det__10smoke__cb72000__20260821T212445Z"]
REJUDGE = ("artefact_v1_det__10smoke__cb72000__20260821T205659Z",
           "artefact_v1_det__10smoke__cb72000__20260821T205659Z__j-claude-haiku-4-5")
BASELINES = ["lucene__gold100__cb72000__20260814T134547Z", "vector__gold100__cb72000__20260814T145615Z",
             "lucene__gold100__cb72000__20261007T211014Z", "vector__gold100__cb72000__20261007T211515Z"]


def rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("== 1. three artefact_v1_det 10smoke folders, 2026-08-21")
    data = {}
    for name in V1DET:
        rs = rows(ROOT / name / "arm_outputs.jsonl")
        data[name] = {r["id"]: r for r in rs}
        man = ROOT / name / "run_manifest.json"
        gm = json.loads(man.read_text(encoding="utf-8")).get("generator_model") if man.is_file() else None
        print(f"   {name[-16:]}: {len(rs)} rows; generator_model in manifest: {gm}; "
              f"non-empty answers: {sum(1 for r in rs if (r.get('answer') or '').strip())}; "
              f"files: {sorted(p.name for p in (ROOT / name).iterdir())}")
    for i in range(len(V1DET)):
        for j in range(i + 1, len(V1DET)):
            a, b = data[V1DET[i]], data[V1DET[j]]
            common = sorted(set(a) & set(b))
            same_ids = sum(1 for q in common if a[q]["context_ids"] == b[q]["context_ids"])
            same_ctx = sum(1 for q in common if h(a[q]["contexts"]) == h(b[q]["contexts"]))
            same_ans = sum(1 for q in common if h(a[q]["answer"]) == h(b[q]["answer"]))
            print(f"   {V1DET[i][-16:]} vs {V1DET[j][-16:]}: common questions {len(common)}; "
                  f"identical context_ids (order kept) {same_ids}; identical contexts {same_ctx}; "
                  f"identical answer text {same_ans}")

    print("\n== 2. the same answers judged a second time")
    a_dir, b_dir = (ROOT / REJUDGE[0]), (ROOT / REJUDGE[1])
    for d in (a_dir, b_dir):
        em = d / "eval_manifest.json"
        if em.is_file():
            m = json.loads(em.read_text(encoding="utf-8"))
            print(f"   {d.name[-36:]}: eval_manifest judge_model={m.get('judge_model')} timestamp={m.get('timestamp')}")
        else:
            print(f"   {d.name[-36:]}: NO eval_manifest.json in the folder")
    ao_a = {r["id"]: r for r in rows(a_dir / "arm_outputs.jsonl")}
    ao_b = {r["id"]: r for r in rows(b_dir / "arm_outputs.jsonl")}
    common = sorted(set(ao_a) & set(ao_b))
    print(f"   answers identical on {sum(1 for q in common if h(ao_a[q]['answer']) == h(ao_b[q]['answer']))} "
          f"of {len(common)}; contexts identical on "
          f"{sum(1 for q in common if h(ao_a[q]['contexts']) == h(ao_b[q]['contexts']))} of {len(common)}")
    ev = {}
    for tag, d in (("first", a_dir), ("second", b_dir)):
        cells = {}
        for r in rows(d / "eval_results.jsonl"):
            cells[(r["question_id"], r["metric"])] = r
        ev[tag] = cells
    per = defaultdict(lambda: {"both": 0, "both_ok": 0, "equal": 0, "diffs": [], "one_not_ok": 0})
    for key in sorted(set(ev["first"]) & set(ev["second"])):
        ra, rb = ev["first"][key], ev["second"][key]
        p = per[key[1]]
        p["both"] += 1
        if ra["status"] == "ok" and rb["status"] == "ok":
            p["both_ok"] += 1
            d = abs(float(ra["value"]) - float(rb["value"]))
            p["diffs"].append(d)
            if d == 0.0:
                p["equal"] += 1
        else:
            p["one_not_ok"] += 1
    print("   score | cells in both | both ok | equal value | mean |diff| | max |diff| | not ok in one")
    for metric, p in sorted(per.items()):
        ds = p["diffs"]
        mean = sum(ds) / len(ds) if ds else float("nan")
        mx = max(ds) if ds else float("nan")
        print(f"   {metric} | {p['both']} | {p['both_ok']} | {p['equal']} | {mean:.4f} | {mx:.4f} | {p['one_not_ok']}")

    print("\n== 3. baseline folders: non-empty answer with zero generator token counters")
    for name in BASELINES:
        rs = rows(ROOT / name / "arm_outputs.jsonl")
        zero = sum(1 for r in rs if (r.get("answer") or "").strip()
                   and not (r["generator"].get("tokens_in") or r["generator"].get("tokens_out")))
        zero_in = sum(1 for r in rs if (r.get("answer") or "").strip() and not r["generator"].get("tokens_in"))
        man = json.loads((ROOT / name / "run_manifest.json").read_text(encoding="utf-8"))
        em = json.loads((ROOT / name / "eval_manifest.json").read_text(encoding="utf-8"))
        print(f"   {name}: rows {len(rs)}; answers with tokens_in and tokens_out both 0: {zero}; "
              f"with tokens_in 0: {zero_in}")
        print(f"      manifest: commit {str((man.get('code_version') or {}).get('commit'))[:7]} "
              f"dirty={(man.get('code_version') or {}).get('dirty')} host={(man.get('environment') or {}).get('host')} "
              f"python={(man.get('environment') or {}).get('python')} "
              f"bm25s={((man.get('environment') or {}).get('packages') or {}).get('bm25s')} "
              f"embedder={(man.get('environment') or {}).get('embedder')} "
              f"build_time_s={man['build_stats']['build_time_s']:.1f} build_calls={man['build_stats']['model']['calls']} "
              f"build_tokens_in={man['build_stats']['model']['tokens_in']}")
        print(f"      eval manifest: judge_model={em.get('judge_model')} judge_backend={em.get('judge_backend')} "
              f"calls={(em.get('judge_usage') or {}).get('calls')} elapsed_s={em.get('judge_elapsed_s')} "
              f"legs={len(em.get('judge_legs') or [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
