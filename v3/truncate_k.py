"""truncate_k.py — re-emit a run's arm_outputs at each eval depth k, no regeneration.

An arm stores its full top-50 retrieval per question. The top-k list is a prefix of
the top-50, so scoring at depth k needs the same records with `contexts`/`context_ids`
sliced to the first k. This walks k high->low, trimming the list further each step
(never recomputing), and writes each as an ordinary arm_outputs.jsonl in a sibling run
folder `<run>__k{k}/`. The existing eval then runs over each folder unchanged: every id
is already answered, so generation is skipped and it scores the truncated contexts.

Run from v3/:
  python truncate_k.py output/<run> --ks 5,10,15,20,30,40,50
then score each folder with the normal eval, e.g.:
  python run.py --arm <arm> --set gold --out output/<run>__k5
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", help="a completed run folder containing arm_outputs.jsonl")
    ap.add_argument("--ks", default="5,10,15,20,30,40,50",
                    help="comma-separated eval depths (default 5,10,15,20,30,40,50)")
    args = ap.parse_args()

    run = Path(args.run)
    recs = [json.loads(x) for x in
            (run / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    ks = sorted({int(x) for x in args.ks.split(",") if x.strip()}, reverse=True)

    for k in ks:  # high -> low: each k trims the previous list further (prefixes nest)
        for r in recs:
            r["contexts"] = r["contexts"][:k]
            r["context_ids"] = r["context_ids"][:k]
        dst = run.with_name(run.name + f"__k{k}")
        dst.mkdir(exist_ok=True)
        (dst / "arm_outputs.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
        print(f"k={k:>3}  {len(recs)} questions -> {dst / 'arm_outputs.jsonl'}")


if __name__ == "__main__":
    main()
