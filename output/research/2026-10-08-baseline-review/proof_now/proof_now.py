"""The keep-everything proof again, with the harness AS IT STANDS, on the made-up question only.

Same path as output/research/2026-10-08-keep-everything-proof/proof.py (orchestrator.run, the real
harness, then the same folder started once more), into NEW folders beside this file. The earlier proof
folders are not touched. The gold answer is made up and says nothing true; the two citation ids are real
corpus ids so the id scores compute.

    .venv/Scripts/python.exe output/research/2026-10-08-baseline-review/proof_now/proof_now.py <arm> [--answer] [--evaluate] [--copies N] [--workers W]

--copies N asks the same made-up question under N ids (for more than one worker at once).
"""
import argparse
import importlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "prod"))
sys.path.insert(0, str(REPO / "test"))

from harness import orchestrator  # noqa: E402
from harness import provenance  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("arm")
    p.add_argument("--answer", action="store_true")
    p.add_argument("--evaluate", action="store_true")
    p.add_argument("--copies", type=int, default=1)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--suffix", default="", help="a new folder name for a new proof of the same shape")
    args = p.parse_args()

    walk = json.loads((REPO / "output/walkthrough/20261005T040000Z/walkthrough.json")
                      .read_text(encoding="utf-8"))
    from arms import lucene
    two_ids = lucene.ingest_corpus(orchestrator.DEFAULT_CORPUS)[:2]
    tag = f"{args.arm}{'__answer' if args.answer else ''}{'__eval' if args.evaluate else ''}" \
          f"{f'__x{args.copies}_w{args.workers}' if args.copies > 1 or args.workers > 1 else ''}"           f"{f'__{args.suffix}' if args.suffix else ''}"
    qfile, ids = HERE / f"madeup_question__{tag}.jsonl", HERE / f"madeup_ids__{tag}.jsonl"
    qids = [f"madeup::walkthrough::{i}" for i in range(args.copies)]
    qfile.write_text("".join(json.dumps({
        "id": q, "question": walk["question"], "type": "content",
        "ground_truth": ["This gold answer is made up for the proof and says nothing true."],
        "citations": [d["id"] for d in two_ids]}) + "\n" for q in qids), encoding="utf-8")
    ids.write_text("".join(json.dumps({"id": q}) + "\n" for q in qids), encoding="utf-8")

    out = HERE / tag
    pipeline = importlib.import_module(f"arms.{args.arm}")
    scorer = None
    if args.evaluate:
        import eval.ragas as scorer
    config = {"questions_path": qfile, "out_dir": str(out), "char_budget": 72000,
              "top_k": orchestrator.DEFAULT_TOP_K, "workers": args.workers,
              "retrieval_only": not args.answer}
    state = provenance.code_state()
    print(f"code state at the start: diff sha256 {state['diff_sha256'][:16]} | "
          f"{len(state['status'] or [])} changed or new paths", flush=True)
    t0 = time.perf_counter()
    orchestrator.run(pipeline, scorer, ids, dict(config))
    print(f"first start done in {time.perf_counter() - t0:.1f} s", flush=True)
    orchestrator.run(pipeline, scorer, ids, dict(config))
    print(f"\nfolder {out.relative_to(REPO)}")
    for f in sorted(out.iterdir()):
        print(f"  {f.name:<34}{f.stat().st_size:>12,} bytes")


if __name__ == "__main__":
    main()
