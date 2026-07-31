"""export_raw.py — dump all eval_results to a single long-format CSV.

    python export_raw.py              # writes raw_results.csv next to this file
    python export_raw.py --out ~/Desktop/raw_results.csv
"""
import argparse
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
DIR_RE = re.compile(r"^(?P<arm>[a-z]+)__gold100__(?P<ts>\d{8}T\d{6}Z)(?:__k(?P<k>\d+))?$")
MANIFEST = "run_manifest.json"

FIELDS = ["arm", "k", "question_id", "type", "metric", "value"]


def _collect_rows(d: Path, arm: str, k: int) -> list[dict]:
    ev = d / "eval_results.jsonl"
    if not ev.is_file():
        return []
    rows = []
    for line in ev.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("status") != "ok":
            continue
        rows.append({
            "arm": arm, "k": k,
            "question_id": r["question_id"],
            "type": r.get("type", ""),
            "metric": r["metric"],
            "value": r["value"],
        })
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(HERE / "raw_results.csv"))
    args = p.parse_args()

    seen: set[tuple] = set()
    rows: list[dict] = []

    all_dirs = [d for d in OUTPUT.iterdir() if DIR_RE.match(d.name)]

    # Unlabeled dirs (no __kN suffix) are full-eval runs including LLM-judged metrics.
    # __kN dirs carry free metrics only regardless of whether they have a manifest.
    unlabeled = sorted([d for d in all_dirs if not DIR_RE.match(d.name).group("k")], reverse=True)
    labeled   = sorted([d for d in all_dirs if     DIR_RE.match(d.name).group("k")], reverse=True)

    # Pass 1: unlabeled dirs — newest timestamp first so a re-run supersedes the old one.
    for d in unlabeled:
        m = DIR_RE.match(d.name)
        mf = d / MANIFEST
        if not mf.is_file():
            continue
        k = json.loads(mf.read_text(encoding="utf-8")).get("top_k")
        if k is None:
            continue
        k = int(k)
        arm = m.group("arm")
        if (arm, k) in seen:
            continue
        seen.add((arm, k))
        rows.extend(_collect_rows(d, arm, k))

    # Pass 2: __kN dirs — newest timestamp first; skip any (arm, k) already covered above.
    for d in labeled:
        m = DIR_RE.match(d.name)
        arm, k = m.group("arm"), int(m.group("k"))
        if (arm, k) in seen:
            continue
        seen.add((arm, k))
        rows.extend(_collect_rows(d, arm, k))

    out = Path(args.out)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {len(rows):,} rows -> {out}")


if __name__ == "__main__":
    main()
