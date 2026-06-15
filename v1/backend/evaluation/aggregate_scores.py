"""Aggregate atomic scored JSONL into summary reports (means/medians).

Cleaning and cohort filtering belong here — not in the RAGAS scorer.

    python -m evaluation.aggregate_scores --input runs.scored.jsonl --report runs.report.json
    python -m evaluation.aggregate_scores --input runs.scored.jsonl --metrics faithfulness,context_recall
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

from evaluation.metrics_common import load_jsonl

_RAGAS_KEYS = (
    "faithfulness",
    "answer_relevancy",
    "response_relevancy",
    "context_recall",
    "context_precision",
    "llm_context_precision_with_reference",
    "answer_correctness",
    "answer_token_recall",
    "answer_token_precision",
    "answer_token_f1",
)


def _metric_values(row: dict[str, Any], key: str) -> float | None:
    ragas = row.get("ragas") or {}
    det = row.get("deterministic") or {}
    v = ragas.get(key)
    if v is None:
        v = det.get(key)
    if v is None:
        v = row.get(key)
    if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)):
        return float(v)
    return None


def _finite(vals: list[float]) -> list[float]:
    return [v for v in vals if isinstance(v, (int, float)) and not math.isnan(v)]


def build_summary(
    rows: list[dict[str, Any]],
    *,
    metric_filter: list[str] | None = None,
    scored_only: bool = True,
) -> dict[str, Any]:
    cohort = rows
    if scored_only:
        cohort = [r for r in rows if (r.get("score_meta") or {}).get("scored")]

    metric_keys: set[str] = set()
    for r in cohort:
        sm = r.get("score_meta") or {}
        for k in sm.get("metric_columns") or []:
            metric_keys.add(str(k))
        ragas = r.get("ragas") or {}
        for k in ragas:
            if k in _RAGAS_KEYS or not k.startswith("n_"):
                metric_keys.add(k)
        for k in (r.get("deterministic") or {}):
            metric_keys.add(k)

    if metric_filter:
        allowed = set(metric_filter)
        metric_keys = {k for k in metric_keys if k in allowed}

    per_sample: list[dict[str, Any]] = []
    for r in rows:
        rid = str(r.get("id") or "?")
        sample: dict[str, Any] = {"id": rid}
        for k in sorted(metric_keys):
            sample[k] = _metric_values(r, k)
        sm = r.get("score_meta") or {}
        if sm.get("skip_reason"):
            sample["skip_reason"] = sm["skip_reason"]
        per_sample.append(sample)

    overall: dict[str, float] = {}
    overall_median: dict[str, float] = {}
    overall_n: dict[str, int] = {}
    for k in sorted(metric_keys):
        vals = _finite([_metric_values(r, k) for r in cohort if _metric_values(r, k) is not None])
        if vals:
            overall[k] = sum(vals) / len(vals)
            overall_median[k] = statistics.median(vals)
            overall_n[k] = len(vals)

    skipped = [
        {
            "id": str(r.get("id") or "?"),
            "skip_reason": (r.get("score_meta") or {}).get("skip_reason"),
        }
        for r in rows
        if not (r.get("score_meta") or {}).get("scored")
    ]

    return {
        "per_sample": per_sample,
        "overall": overall,
        "overall_median": overall_median,
        "overall_n": overall_n,
        "n_rows": len(rows),
        "n_scored": len(cohort),
        "n_skipped": len(rows) - len(cohort),
        "skipped": skipped,
    }


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m evaluation.aggregate_scores")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument(
        "--metrics",
        default="",
        help="Comma-separated metric subset (default: all present in file)",
    )
    p.add_argument(
        "--include-skipped",
        action="store_true",
        help="Include skipped rows in overall means (default: scored rows only)",
    )
    args = p.parse_args()

    if not args.input.is_file():
        print(f"Input not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    rows = load_jsonl(args.input)
    if not rows:
        print(f"No rows in {args.input}", file=sys.stderr)
        sys.exit(1)

    metric_filter = [m.strip() for m in args.metrics.split(",") if m.strip()] or None
    payload = build_summary(
        rows,
        metric_filter=metric_filter,
        scored_only=not args.include_skipped,
    )
    payload["source"] = str(args.input)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.report} ({payload['n_scored']}/{payload['n_rows']} scored)")


if __name__ == "__main__":
    main()
