"""compare_arms.py — side-by-side RAGAS comparison across the gold-100 runs.

Walks `output/k=chunks/` for `<arm>__gold100__*__k<k>/eval_results.jsonl`, groups by
(arm, k), and prints mean per metric. The three target metrics the artefact arm
is scored against — faithfulness, answer_correctness, context_recall_llm — are
printed first, then the full RAGAS set.

    python compare_arms.py            # all gold-100 runs found
    python compare_arms.py --k 10     # only k=10 runs
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
# Top-k runs — the family this comparison reads, since its grouping key is k.
RUNS = OUTPUT / "k=chunks"

TARGET_METRICS = ("faithfulness", "answer_correctness", "context_recall_llm")
DIR_RE = re.compile(r"^(?P<arm>[a-z]+)__gold100__(?P<ts>\d{8}T\d{6}Z)(?:__k(?P<k>\d+))?$")


def _scan() -> dict:
    """(arm, k) -> {metric: [values...]} over the ok cells in eval_results.jsonl."""
    runs: dict = defaultdict(lambda: defaultdict(list))
    for d in sorted(RUNS.iterdir()):
        m = DIR_RE.match(d.name)
        if not m:
            continue
        arm = m.group("arm")
        k = int(m.group("k")) if m.group("k") else None
        ev = d / "eval_results.jsonl"
        if not ev.is_file():
            continue
        for line in ev.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("status") != "ok":
                continue
            runs[(arm, k)][r["metric"]].append(float(r["value"]))
    return runs


def _print(runs: dict, ks: list[int] | None) -> None:
    arms = sorted({arm for arm, _ in runs})
    all_ks = sorted({k for _, k in runs if k is not None})
    ks = ks or all_ks
    all_metrics = sorted({m for by_metric in runs.values() for m in by_metric})
    ordered = [m for m in TARGET_METRICS if m in all_metrics] + \
              [m for m in all_metrics if m not in TARGET_METRICS]

    header_arms = "  arm  ".join(f"{a:^18}" for a in arms)
    print(f"\nRAGAS gold-100 — mean per metric  (arms={arms}, ks={ks})\n")
    for k in ks:
        print(f"  -- k={k} --")
        print(f"  {'metric':<28}{header_arms}")
        for metric in ordered:
            row = f"  {metric:<28}"
            for arm in arms:
                vals = runs.get((arm, k), {}).get(metric, [])
                cell = f"{mean(vals):.3f} (n={len(vals)})" if vals else "  -"
                row += f"{cell:^18}"
            print(row)
        print()


def main() -> None:
    p = argparse.ArgumentParser(description="Side-by-side RAGAS comparison over gold-100 runs.")
    p.add_argument("--k", type=int, nargs="*", help="only these k values (default: all found)")
    args = p.parse_args()
    runs = _scan()
    if not runs:
        print(f"no eval_results.jsonl found under {OUTPUT}/")
        return
    _print(runs, args.k)


if __name__ == "__main__":
    main()
