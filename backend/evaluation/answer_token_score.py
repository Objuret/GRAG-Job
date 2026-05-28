"""Deterministic answer correctness vs HERB gold (response vs reference tokens).

HERB gold is mostly semicolon-separated eid_* handles. This scores whether the
pipeline answer mentions those tokens — the correctness metric RAGAS
answer_correctness was meant to cover, without extra API cost.

    python -m evaluation.answer_token_score \\
      --input ../ragas_exports/A_tags_k40.jsonl \\
      --merge-report ../ragas_exports/A_tags_k40.report.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from evaluation.metrics_common import (
    answer_token_scores,
    dedupe_rows,
    load_jsonl,
    merge_report_payload,
    write_report,
)

_DEFAULT_INPUT = Path(__file__).resolve().parent / "ragas_samples.jsonl"


def score_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    per_sample: list[dict[str, Any]] = []
    skipped = 0
    for r in rows:
        rid = str(r.get("id") or "?")
        if (r.get("meta") or {}).get("error"):
            skipped += 1
            continue
        ref = (r.get("reference") or "").strip()
        resp = (r.get("response") or "").strip()
        if not ref or not resp:
            skipped += 1
            continue
        scored = answer_token_scores(ref, resp)
        per_sample.append({"id": rid, **scored})
    return per_sample, skipped


def main() -> None:
    p = argparse.ArgumentParser(
        prog="python -m evaluation.answer_token_score",
        description="Answer vs reference token F1 (deterministic, no LLM).",
    )
    p.add_argument("--input", type=Path, default=_DEFAULT_INPUT)
    p.add_argument("--report", type=Path, default=None, help="Write standalone JSON report")
    p.add_argument(
        "--merge-report",
        type=Path,
        default=None,
        help="Merge scores into an existing RAGAS report JSON",
    )
    p.add_argument("--max", type=int, default=0)
    args = p.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    rows = dedupe_rows(load_jsonl(args.input))
    if args.max > 0:
        rows = rows[: args.max]

    per_sample, skipped = score_rows(rows)
    f1_vals = [r["answer_token_f1"] for r in per_sample if isinstance(r.get("answer_token_f1"), float)]
    overall_f1 = sum(f1_vals) / len(f1_vals) if f1_vals else 0.0

    sep = "-" * 64
    print(f"\n{sep}\nAnswer token F1 — {len(f1_vals)} sample(s), skipped {skipped}\n{sep}")
    for row in per_sample[:5]:
        print(f"  {row['id']:<28} f1={row['answer_token_f1']:.3f}  recall={row['answer_token_recall']:.3f}")
    if len(per_sample) > 5:
        print(f"  … ({len(per_sample) - 5} more)")
    print(sep)
    print(f"  overall answer_token_f1={overall_f1:.4f} (n={len(f1_vals)})")
    print(sep)

    patch = {
        "per_sample": per_sample,
        "overall": {
            "answer_token_recall": sum(r["answer_token_recall"] for r in per_sample if r.get("answer_token_recall") is not None) / max(1, len(f1_vals)),
            "answer_token_precision": sum(r["answer_token_precision"] for r in per_sample if r.get("answer_token_precision") is not None) / max(1, len(f1_vals)),
            "answer_token_f1": overall_f1,
        },
        "overall_n": {
            "answer_token_recall": len(f1_vals),
            "answer_token_precision": len(f1_vals),
            "answer_token_f1": len(f1_vals),
        },
        "n_samples": len(f1_vals),
    }

    if args.report:
        write_report(args.report, patch)
        print(f"Wrote {args.report}")

    if args.merge_report:
        if not args.merge_report.exists():
            print(f"Merge target not found: {args.merge_report}", file=sys.stderr)
            sys.exit(2)
        import json

        base = json.loads(args.merge_report.read_text(encoding="utf-8"))
        merged = merge_report_payload(base, patch)
        write_report(args.merge_report, merged)
        print(f"Merged into {args.merge_report}")


if __name__ == "__main__":
    main()
