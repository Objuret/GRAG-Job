"""Fast deterministic retrieval recall — no LLM judge.

Scores export JSONL by checking whether reference tokens (eid_*, URLs, etc.)
appear in retrieved chunk text. Use for retrieval iteration; RAGAS for final
reporting only.

    python -m evaluation.retrieval_recall_fast \\
      --input ../ragas_exports/A_tags_v2_weighted.jsonl \\
      --report ../ragas_exports/A_tags_v2_weighted.recall_fast.json

Typical runtime: <5s on gold-100.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_DEFAULT_INPUT = Path(__file__).resolve().parent / "ragas_samples.jsonl"
_TOKEN_SPLIT = re.compile(r"[;\n,|]+")


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for r in rows:
        rid = str(r.get("id") or "")
        if not rid:
            continue
        prev = by_id.get(rid)
        if prev is None or not (prev.get("meta") or {}).get("error"):
            by_id[rid] = r
    return list(by_id.values())


def _reference_tokens(reference: str) -> list[str]:
    tokens: list[str] = []
    for part in _TOKEN_SPLIT.split(reference):
        t = part.strip()
        if len(t) >= 4:
            tokens.append(t)
    return tokens


def _score_row(
    contexts: list[str],
    reference: str,
    *,
    max_contexts: int,
) -> dict[str, Any]:
    tokens = _reference_tokens(reference)
    if not tokens:
        return {"token_recall": None, "n_tokens": 0, "missing": []}

    hay = "\n".join(contexts[:max_contexts] if max_contexts > 0 else contexts).lower()
    missing = [t for t in tokens if t.lower() not in hay]
    found = len(tokens) - len(missing)
    return {
        "token_recall": found / len(tokens),
        "n_tokens": len(tokens),
        "n_found": found,
        "missing": missing[:20],
    }


def main() -> None:
    p = argparse.ArgumentParser(
        prog="python -m evaluation.retrieval_recall_fast",
        description="Deterministic token-in-context recall (seconds, no LLM).",
    )
    p.add_argument("--input", type=Path, default=_DEFAULT_INPUT)
    p.add_argument("--report", type=Path, default=None)
    p.add_argument(
        "--max-contexts",
        type=int,
        default=0,
        help="Only search top-N contexts (0 = all). Match RAGAS --judge-max-contexts.",
    )
    p.add_argument("--max", type=int, default=0, help="Cap rows (0 = all)")
    args = p.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    rows = _dedupe_rows(
        [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    )
    if args.max > 0:
        rows = rows[: args.max]

    per_sample: list[dict[str, Any]] = []
    skipped = 0
    recalls: list[float] = []

    for r in rows:
        rid = str(r.get("id") or "?")
        if (r.get("meta") or {}).get("error"):
            skipped += 1
            continue
        ref = (r.get("reference") or "").strip()
        ctx = [c for c in (r.get("retrieved_contexts") or []) if c]
        if not ref:
            skipped += 1
            continue
        scored = _score_row(ctx, ref, max_contexts=args.max_contexts)
        row = {"id": rid, "n_chunks": len(ctx), **scored}
        per_sample.append(row)
        if isinstance(scored["token_recall"], float):
            recalls.append(scored["token_recall"])

    overall = sum(recalls) / len(recalls) if recalls else 0.0
    sep = "-" * 64
    print(f"\n{sep}\nToken recall (fast) — {len(recalls)} sample(s), skipped {skipped}\n{sep}")
    for row in per_sample:
        tr = row["token_recall"]
        label = f"{tr:.3f}" if isinstance(tr, float) else "NA"
        print(f"  {row['id']:<28} recall={label}  chunks={row['n_chunks']}  tokens={row['n_tokens']}")
    print(sep)
    print(f"  overall token_recall={overall:.4f} (n={len(recalls)})")
    if args.max_contexts > 0:
        print(f"  (top-{args.max_contexts} contexts only)")
    print(sep)

    payload = {
        "overall_token_recall": overall,
        "n_samples": len(recalls),
        "skipped": skipped,
        "max_contexts": args.max_contexts,
        "per_sample": per_sample,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
