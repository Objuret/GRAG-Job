"""Offline RAGAS scorer for the workbench's exported runs.

Input: the JSONL produced by the frontend History tab's **Export RAGAS**
button — one record per (run, lane):

    {"run_id": "...", "at": "...", "lane": "A"|"B", "dataset": "...",
     "question": "...", "answer": "...", "contexts": ["chunk text", ...]}

This is the real browser run data (no ground-truth column, so we score the
two reference-free RAGAS metrics): **faithfulness** (is the answer grounded in
the retrieved contexts) and **answer_relevancy** (does the answer address the
question). It prints per-lane means and the A−B delta so the HERB-tags lane
(A) can be compared to the baseline (B).

Run:
    pip install -r backend/eval/requirements-eval.txt
    export OPENAI_API_KEY=...        # RAGAS default judge/embeddings
    python -m backend.eval.ragas_eval runs.jsonl

There is no silent fallback: a missing dependency, missing API key, empty
input, or a record missing required fields is a loud error.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

REQUIRED_FIELDS = ("lane", "question", "answer", "contexts")


def _die(msg: str) -> "None":
    print(f"ragas_eval: {msg}", file=sys.stderr)
    raise SystemExit(2)


def load_rows(path: Path) -> list[dict]:
    if not path.is_file():
        _die(f"input file not found: {path}")
    rows: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            _die(f"line {i} is not valid JSON: {e}")
        missing = [f for f in REQUIRED_FIELDS if f not in obj]
        if missing:
            _die(f"line {i} missing required field(s): {', '.join(missing)}")
        if not obj["contexts"]:
            _die(
                f"line {i} (run {obj.get('run_id')}, lane {obj['lane']}) has no "
                f"contexts — RAGAS faithfulness is undefined with zero retrieved "
                f"chunks. Re-run retrieval or exclude this run."
            )
        rows.append(obj)
    if not rows:
        _die(f"no records in {path}")
    return rows


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        _die("usage: python -m backend.eval.ragas_eval <runs.jsonl>")

    if not os.environ.get("OPENAI_API_KEY"):
        _die(
            "OPENAI_API_KEY is not set. RAGAS uses it as the default judge LLM "
            "and embedding model. Set it (or configure a different RAGAS "
            "llm/embeddings in this script) before scoring."
        )

    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness
    except ModuleNotFoundError as e:
        _die(
            f"missing dependency: {e.name}. Install the eval extras: "
            f"pip install -r backend/eval/requirements-eval.txt"
        )
        return 2  # unreachable (｜_die raises) — keeps type checkers happy

    rows = load_rows(Path(argv[1]))
    by_lane: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_lane[r["lane"]].append(r)

    metrics = [faithfulness, answer_relevancy]
    summary: dict[str, dict[str, float]] = {}

    for lane in sorted(by_lane):
        lane_rows = by_lane[lane]
        ds = Dataset.from_dict(
            {
                "question": [r["question"] for r in lane_rows],
                "answer": [r["answer"] for r in lane_rows],
                "contexts": [r["contexts"] for r in lane_rows],
            }
        )
        print(f"\n== Lane {lane} — {len(lane_rows)} samples ==", file=sys.stderr)
        result = evaluate(ds, metrics=metrics)
        df = result.to_pandas()
        summary[lane] = {
            m.name: float(df[m.name].mean()) for m in metrics if m.name in df
        }

    print("\n=== RAGAS summary (means) ===")
    for lane, scores in summary.items():
        pretty = "  ".join(f"{k}={v:.3f}" for k, v in scores.items())
        print(f"Lane {lane}: {pretty}")

    if "A" in summary and "B" in summary:
        print("\n=== A − B (HERB tags vs baseline) ===")
        for k in summary["A"]:
            if k in summary["B"]:
                print(f"{k}: {summary['A'][k] - summary['B'][k]:+.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
