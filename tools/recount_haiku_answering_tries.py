"""The time of the claude-haiku-4-5 calls that described and tagged the graph's 4,869 chunks, counted by
their answering tries (his 2026-10-21 "a model call's time is its answering try; the seconds of failed
tries are out of the call, the question and the run"), from the tagging run's own records.

    python tools/recount_haiku_answering_tries.py [--write]

The records are the extract stage's lines of io.jsonl (the main run) and recovery_io.jsonl (the
recovery) in the run's snapshot, read from git (SNAPSHOT at COMMIT); the chunks are the run's chunk ids
without the kinds the graph leaves out (DROP), as test/graph/build_cost.json counts them. A record's
duration_ms is the client's clock from before its first try to its answer, so:
  1. a record answered on its first try counts by its duration_ms;
  2. a record that never answered (no usage) counts with nothing;
  3. a record answered on a later try holds its failed tries and the pauses after them as well: it
     counts by a + b x its output tokens, fitted (least squares) on the records of rule 1;
  4. a main-run record whose answer failed the pipeline's validation (errors.jsonl) and whose chunk
     the recovery made again counts with nothing, nor do its tokens: its answer is not in the graph
     (his 2026-10-21 "The ONLY thing that matters, at all, is the iteration that ran the RAGAS").
With --write it writes test/graph/build_cost_haiku_answering_tries.json, which the export reads.
"""
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
COMMIT = "bcc3156"
SNAPSHOT = "backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip"
INSIDE = "pilot_full_herb_snapshot_20260514T052226Z/"
DROP = {"qa_record", "qa_record_part", "unanswerable_question_batch", "product_profile"}
OUT = REPO / "test" / "graph" / "build_cost_haiku_answering_tries.json"


def main():
    raw = subprocess.run(["git", "show", f"{COMMIT}:{SNAPSHOT}"], cwd=REPO, capture_output=True, check=True).stdout
    z = zipfile.ZipFile(io.BytesIO(raw))
    run = json.loads(z.read(INSIDE + "run.json"))
    chunks = {c["chunk_id"] for c in run["chunk_ids"] if c["kind"] not in DROP}
    records = []
    for name in ("io.jsonl", "recovery_io.jsonl"):
        for line in z.read(INSIDE + name).decode("utf-8").splitlines():
            r = json.loads(line)
            if r.get("stage") == "extract" and r.get("target_id") in chunks:
                u = r.get("usage") or {}
                records.append({"file": name, "target": r["target_id"], "attempt": r.get("attempt"),
                                "seconds": (r.get("duration_ms") or 0) / 1000, "answered": bool(u),
                                "in": int(u.get("prompt_tokens") or 0), "out": int(u.get("completion_tokens") or 0)})
    errors = [json.loads(x) for x in z.read(INSIDE + "errors.jsonl").decode("utf-8").splitlines() if x.strip()]
    failed_validation = {e["target_id"] for e in errors if e.get("stage") == "extract" and str(e.get("error", "")).startswith("pydantic")}
    remade = {r["target"] for r in records if r["file"] == "recovery_io.jsonl"}
    for r in records:  # rule 4
        r["replaced"] = r["file"] == "io.jsonl" and r["answered"] and r["target"] in failed_validation & remade
    first = [r for r in records if r["answered"] and r["attempt"] == 1]
    later = [r for r in records if r["answered"] and r["attempt"] != 1]
    never = [r for r in records if not r["answered"]]
    x = np.array([r["out"] for r in first], float)
    s = np.array([r["seconds"] for r in first])
    b, a = np.polyfit(x, s, 1)
    loo = [abs(s[k] - np.polyval(np.polyfit(np.delete(x, k), np.delete(s, k), 1), x[k])) for k in range(0, len(x), 7)]
    estimated = sum(a + b * r["out"] for r in later)
    cost = json.loads((REPO / "test/graph/build_cost.json").read_text(encoding="utf-8"))
    subset = {st["id"]: st for st in cost["steps"]}["descriptions_and_tags"]["the_4869_chunks_of_this_graph"]["extract"]
    answered = first + later
    counts = (len(answered), sum(r["in"] for r in answered), sum(r["out"] for r in answered))
    if len(chunks) != 4869 or counts != (subset["calls_with_usage"], subset["tokens_in"], subset["tokens_out"]):
        raise SystemExit(f"the records are not build_cost.json's: chunks {len(chunks)}, answered calls, tokens in, out {counts}, "
                         f"build_cost.json {(subset['calls_with_usage'], subset['tokens_in'], subset['tokens_out'])}")
    # rule 4: the answers the graph does not hold count with nothing
    kept_first = [r for r in first if not r["replaced"]]
    kept_later = [r for r in later if not r["replaced"]]
    replaced = [r for r in answered if r["replaced"]]
    value = sum(r["seconds"] for r in kept_first) + sum(a + b * r["out"] for r in kept_later)
    kept = kept_first + kept_later
    result = {
        "what": "seconds of the claude-haiku-4-5 calls that described and tagged the graph's 4,869 chunks, by their answering tries",
        "seconds": value,
        "calls": len(kept), "tokens_in": sum(r["in"] for r in kept), "tokens_out": sum(r["out"] for r in kept),
        "rule": __doc__.split("so:\n", 1)[1].split("With --write", 1)[0].strip(),
        "answered_on_the_first_try": {"calls": len(kept_first), "seconds": sum(r["seconds"] for r in kept_first)},
        "answered_on_a_later_try": {"calls": len(kept_later), "recorded_seconds_with_their_failed_tries": sum(r["seconds"] for r in kept_later),
                                    "seconds_by_the_relation": sum(a + b * r["out"] for r in kept_later)},
        "answers_the_graph_does_not_hold": {"calls": len(replaced), "seconds_left_out": sum(r["seconds"] for r in replaced),
                                            "tokens_in": sum(r["in"] for r in replaced), "tokens_out": sum(r["out"] for r in replaced)},
        "never_answered": {"records": len(never), "recorded_seconds_left_out": sum(r["seconds"] for r in never)},
        "relation": {"a_seconds": float(a), "b_seconds_per_output_token": float(b), "fitted_on": len(first),
                     "leave_one_out_abs_error_median_s_every_7th": float(np.median(loo))},
        "as_build_cost_json_had_it": subset["seconds_summed_per_call"],
        "records": {"commit": COMMIT, "path": SNAPSHOT, "sha256": hashlib.sha256(raw).hexdigest(),
                    "files": ["io.jsonl", "recovery_io.jsonl"], "stage": "extract"},
        "script": "tools/recount_haiku_answering_tries.py",
    }
    print(json.dumps({k: v for k, v in result.items() if k not in ("rule", "records")}, indent=1))
    if "--write" in sys.argv:
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"written: {OUT}")


if __name__ == "__main__":
    main()
