import argparse
import json
from pathlib import Path


def truncate_record(rec: dict, k: int) -> dict:
    if (rec.get("meta") or {}).get("char_budget") is not None:
        raise RuntimeError(
            f"record {rec.get('id', '?')!r} carries meta.char_budget — a fill-to-budget "
            f"record is cut by characters, not depth, so it has no k to truncate to")
    per_chunk = (rec.get("meta") or {}).get("chunk_ids")
    if per_chunk is None:
        if len(rec["context_ids"]) != len(rec["contexts"]):
            raise RuntimeError(
                f"record {rec.get('id', '?')!r} has {len(rec['contexts'])} contexts but "
                f"{len(rec['context_ids'])} context_ids and no meta.chunk_ids — "
                f"a flat slice misattributes ids across chunks")
        ids = rec["context_ids"][:k]
    else:
        seen, ids = set(), []
        for chunk_ids in per_chunk[:k]:
            for aid in chunk_ids:
                if aid not in seen:
                    seen.add(aid)
                    ids.append(aid)
    return {**rec, "contexts": rec["contexts"][:k], "context_ids": ids}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", help="a completed run folder containing arm_outputs.jsonl")
    ap.add_argument("--ks", default="5,10,15,20,30,40,50",
                    help="comma-separated eval depths (default 5,10,15,20,30,40,50)")
    args = ap.parse_args()

    run = Path(args.run)
    manifest = run / "run_manifest.json"
    if manifest.is_file() and json.loads(
            manifest.read_text(encoding="utf-8")).get("char_budget") is not None:
        raise SystemExit(
            f"{run.name} is a fill-to-budget run (char_budget in run_manifest.json) — "
            f"its records are cut by characters, not depth, so there is no k to truncate to")
    base = [json.loads(x) for x in
            (run / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    ks = sorted({int(x) for x in args.ks.split(",") if x.strip()}, reverse=True)

    for k in ks:
        recs = [truncate_record(r, k) for r in base]
        dst = run.with_name(run.name + f"__k{k}")
        dst.mkdir(exist_ok=True)
        (dst / "arm_outputs.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
        print(f"k={k:>3}  {len(recs)} questions -> {dst / 'arm_outputs.jsonl'}")


if __name__ == "__main__":
    main()
