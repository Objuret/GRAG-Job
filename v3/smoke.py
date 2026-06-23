"""smoke.py — tiny wiring check: run a few questions through one pipeline +
evaluator into its own per-run folder under output/smoke/, confirming the
contract flows end to end. Throwaway — never reported numbers.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import orchestrator
import questions

_HERE = Path(__file__).parent
SMOKE_ROOT = _HERE / "output" / "smoke"


def pick_few_question_ids(n, dest_dir):
    """A small FIXED subset of answerable ids — one per type first (so the smoke
    exercises every scoring route), then in file order — written into dest_dir as
    an id-set file run() reads. Returns the path. Fixed = deterministic.
    linked to: orchestrator.load_chosen_questions / _read_ids
    """
    answerable = [q for q in questions.load_questions() if "::a::" in q.id]
    chosen, seen_type, seen_id = [], set(), set()
    for q in answerable:
        if q.type not in seen_type:
            seen_type.add(q.type); seen_id.add(q.id); chosen.append(q)
    for q in answerable:
        if len(chosen) >= n:
            break
        if q.id not in seen_id:
            seen_id.add(q.id); chosen.append(q)
    chosen = chosen[:n]
    dest = Path(dest_dir) / "question_ids.smoke.jsonl"
    with dest.open("w", encoding="utf-8") as fh:
        for q in chosen:
            fh.write(json.dumps(
                {"id": q.id, "type": q.type, "question": q.question},
                ensure_ascii=False) + "\n")
    return dest


def run_smoke(pipeline, evaluator, n=5, config=None):
    """Run orchestrator.run over n fixed questions into a per-run folder
    output/smoke/<arm>__smoke__<timestamp>/ (arm·set·time, like real runs).
    linked to: orchestrator.run
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = SMOKE_ROOT / f"{orchestrator._arm_name(pipeline)}__smoke__{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    ids = pick_few_question_ids(n, out_dir)
    cfg = {"out_dir": out_dir, **(config or {})}
    return orchestrator.run(pipeline, evaluator, ids, cfg)


if __name__ == "__main__":
    import eval.herb as herb
    import pipelines.lucene as lucene
    print(run_smoke(lucene, herb))
