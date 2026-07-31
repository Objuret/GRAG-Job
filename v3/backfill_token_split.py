"""backfill_token_split.py — add tokens_in/tokens_out ONLY on rows with no token data.

Skips any row that already has generator.tokens (the NIM bill from the live run).
Does not delete or overwrite existing token fields."""
import argparse
import json
from pathlib import Path

from contract import backfill_generator_usage


def backfill_file(path: Path, *, force: bool = False) -> int:
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    out = []
    changed = 0
    for line in lines:
        rec = json.loads(line)
        before = json.dumps(rec.get("generator") or {}, sort_keys=True)
        rec["generator"] = backfill_generator_usage(rec, force=force)
        if json.dumps(rec["generator"], sort_keys=True) != before:
            changed += 1
        out.append(json.dumps(rec, ensure_ascii=False))
    if changed:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="ignored — rows with generator.tokens are never overwritten")
    ap.add_argument("paths", nargs="+", help="arm_outputs.jsonl files or run folders")
    args = ap.parse_args()
    total = 0
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            p = p / "arm_outputs.jsonl"
        if not p.is_file():
            raise SystemExit(f"not found: {p}")
        n = backfill_file(p, force=args.force)
        print(f"{p}: {n} rows updated")
        total += n
    print(f"done — {total} rows total")


if __name__ == "__main__":
    main()
