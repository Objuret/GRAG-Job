"""model_test.py — 3-question head-to-head: the full artefact_v1 pipeline
(interpret + generate) on ONE model per leg, judged by the standard qwen judge.

    python model_test.py glm                # answers + RAGAS eval
    python model_test.py qwen --workers 3   # all three questions in flight
    python model_test.py glm --no-eval      # answers only; re-run without it to score

Question ids live in model_test_ids.jsonl. Output lands in
output/artefact_v1__modeltest3_<leg>/ — re-running resumes (answered ids are
skipped; the eval scores the full persisted set).
"""
import argparse
import importlib
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
os.chdir(_HERE)

MODELS = {"glm": "z-ai/glm-5.2", "qwen": "qwen/qwen3.5-397b-a17b"}


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("leg", choices=sorted(MODELS),
                   help="which model runs interpret + generate")
    p.add_argument("--workers", type=int, default=1, metavar="W",
                   help="questions answered in parallel (one account lane each)")
    p.add_argument("-k", type=int, default=50, help="retrieval depth (default 50)")
    p.add_argument("--no-eval", action="store_true",
                   help="answers only — skip RAGAS scoring")
    args = p.parse_args()

    model = MODELS[args.leg]
    os.environ["HERB_INTERPRET_MODEL"] = model  # read at pipeline import

    ids_file = _HERE / "model_test_ids.jsonl"
    out_dir = _HERE / "output" / f"artefact_v1__modeltest3_{args.leg}"
    n_q = sum(1 for ln in ids_file.read_text(encoding="utf-8").splitlines() if ln.strip())
    pace = "serial" if args.workers == 1 else f"{args.workers} workers"
    mode = "answers only (no eval)" if args.no_eval else "answers + RAGAS eval"
    print(f"{args.leg} | {model} | {n_q} questions | k={args.k} | {pace} | {mode}"
          f"\n  ->  {out_dir}", flush=True)

    import abort
    import nim
    nim._load_dotenv()
    import orchestrator
    from run import _print_table
    from run_lock import RunLock
    pipeline = importlib.import_module("pipelines.artefact_v1")
    if args.no_eval:
        scorer = None
    else:  # eval deps (ragas/langchain) load only when a run actually scores
        print("loading eval stack (ragas/langchain - takes a minute cold)...", flush=True)
        import eval.ragas as scorer

    config = {"top_k": args.k, "workers": args.workers, "out_dir": str(out_dir),
              "retrieval_only": False, "generator_model": model}
    abort.watch()  # press q to stop the run gracefully
    print("running - press q to abort\n", flush=True)
    with RunLock(out_dir):
        summary = orchestrator.run(pipeline, scorer, ids_file, config)

    if not args.no_eval:
        rows = [json.loads(x) for x in
                (Path(summary["out_dir"]) / "eval_results.jsonl")
                .read_text(encoding="utf-8").splitlines() if x.strip()]
        _print_table(rows, args.leg, summary["n_ran"])
    print(f"\n{summary['n_ran']}/{summary['n_questions']} answered, "
          f"{summary['n_failed']} failed  ->  {summary['out_dir']}")


if __name__ == "__main__":
    main()
