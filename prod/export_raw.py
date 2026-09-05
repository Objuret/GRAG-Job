import argparse
import csv
import json
import re
from pathlib import Path

from harness import orchestrator
from harness.progress import progress

HERE = Path(__file__).resolve().parent
RUNS = orchestrator.CHUNKS_ROOT
DIR_RE = re.compile(r"^(?P<arm>[a-z]+)__gold100__(?P<ts>\d{8}T\d{6}Z)(?:__k(?P<k>\d+))?$")
MANIFEST = "run_manifest.json"

FIELDS = ["arm", "k", "question_id", "type", "metric", "value"]


def _manifest(d: Path) -> dict | None:
    mf = d / MANIFEST
    if not mf.is_file():
        return None
    return json.loads(mf.read_text(encoding="utf-8"))


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
    print(f"export_raw: reading {RUNS}", flush=True)

    seen: set[tuple] = set()
    rows: list[dict] = []

    all_dirs, manifests = [], {}
    for d in RUNS.iterdir():
        if not DIR_RE.match(d.name):
            continue
        mf = _manifest(d)
        if (mf or {}).get("char_budget") is not None:
            continue
        all_dirs.append(d)
        manifests[d] = mf
    print(f"  {len(all_dirs)} run folder(s)", flush=True)

    unlabeled = sorted([d for d in all_dirs if not DIR_RE.match(d.name).group("k")], reverse=True)
    labeled   = sorted([d for d in all_dirs if     DIR_RE.match(d.name).group("k")], reverse=True)

    for d in progress(unlabeled, desc="full-eval runs", unit="run"):
        m = DIR_RE.match(d.name)
        mf = manifests[d]
        if mf is None:
            continue
        k = mf.get("top_k")
        if k is None:
            continue
        k = int(k)
        arm = m.group("arm")
        if (arm, k) in seen:
            continue
        seen.add((arm, k))
        rows.extend(_collect_rows(d, arm, k))

    for d in progress(labeled, desc="k-labelled runs", unit="run"):
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
