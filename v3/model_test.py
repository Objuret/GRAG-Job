"""model_test.py — 3-question head-to-head: the full artefact_v1 pipeline
(interpret + generate) on ONE model per leg, judged by the standard qwen judge.

    python model_test.py glm                # answers + RAGAS eval (canon judge)
    python model_test.py qwen --workers 3   # all three questions in flight
    python model_test.py glm --no-eval      # answers only; re-run without it to score
    python model_test.py glm --judge z-ai/glm-5.2   # re-judge same answers, new dir

Question ids live in model_test_ids.jsonl. Output lands in
output/artefact_v1__modeltest3_<leg>/ — re-running resumes (answered ids are
skipped; the eval scores the full persisted set).
"""
import argparse
import importlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
os.chdir(_HERE)

MODELS = {"glm": "z-ai/glm-5.2", "qwen": "qwen/qwen3.5-397b-a17b"}


def _wide_parallel_judge(model: str) -> bool:
    """Judges with no queue to respect: open every cell at once."""
    model = model.lower()
    return "claude" in model or "gpt-" in model or "gemini" in model


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("leg", choices=sorted(MODELS),
                   help="which model runs interpret + generate")
    p.add_argument("--workers", type=int, default=None, metavar="W",
                   help="parallelism: questions while answering, cells while scoring "
                        "(default 1; a claude-*, gpt-*, or gemini-* judge auto-sizes to every cell at once)")
    p.add_argument("-k", type=int, default=50, help="retrieval depth (default 50)")
    p.add_argument("--no-eval", action="store_true",
                   help="answers only — skip RAGAS scoring")
    p.add_argument("--judge", metavar="MODEL",
                   help="re-judge the leg's existing answers with this judge model, "
                        "into a separate __j-<slug> dir (the canon-judged dir is "
                        "never touched; claude-*, gpt-*, and gemini-* auto-max the cell fan-out)")
    args = p.parse_args()
    if args.judge and args.no_eval:
        p.error("--judge with --no-eval scores nothing")

    model = MODELS[args.leg]
    os.environ["HERB_INTERPRET_MODEL"] = model  # read at pipeline import

    ids_file = _HERE / "model_test_ids.jsonl"
    base_dir = _HERE / "output" / f"artefact_v1__modeltest3_{args.leg}"
    out_dir = base_dir
    if args.judge:
        os.environ["RAGAS_JUDGE_MODEL"] = args.judge  # read at eval import
        slug = re.sub(r"[^a-z0-9.]+", "-", args.judge.split("/")[-1].lower())
        out_dir = base_dir.parent / f"{base_dir.name}__j-{slug}"
        # Same answers, different judge: seed the judge dir with the leg's answer
        # file so resume skips all generation and the run is eval-only.
        if not (out_dir / "arm_outputs.jsonl").exists():
            if not (base_dir / "arm_outputs.jsonl").exists():
                sys.exit(f"no answers to re-judge — run the {args.leg} leg first ({base_dir})")
            out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(base_dir / "arm_outputs.jsonl", out_dir / "arm_outputs.jsonl")

    n_q = sum(1 for ln in ids_file.read_text(encoding="utf-8").splitlines() if ln.strip())
    if args.workers is None:
        if args.judge and _wide_parallel_judge(args.judge):
            # Subscription CLI judges queue every cell; their shared judge pool
            # sets the real in-flight cap.
            from eval.ragas_catalog import metrics_to_run
            args.workers = max(1, n_q * len(metrics_to_run()))
        else:
            args.workers = 1
    pace = "serial" if args.workers == 1 else f"{args.workers} workers"
    mode = ("answers only (no eval)" if args.no_eval
            else f"re-judge existing answers ({args.judge})" if args.judge
            else "answers + RAGAS eval")
    print(f"{args.leg} | {model} | {n_q} questions | k={args.k} | {pace} | {mode}"
          f"\n  ->  {out_dir}", flush=True)

    import abort
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
