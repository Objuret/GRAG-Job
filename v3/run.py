"""run.py — the single entry point for an evaluation run: choose an arm, a question
set, and the knobs, then generate answers and score them with RAGAS. A thin CLI over
orchestrator.run (the engine); progress bars (generation, then scoring) show it's
working. Every setting is a flag — see `python run.py --help`.

    python run.py                          # smoke: lucene, dev-5 -> output/smoke/
    python run.py --arm vector             # smoke, vector arm
    python run.py --set gold               # gold-100 -> output/
    python run.py --set full --arm vector  # all questions, vector -> output/
    python run.py --set full --no-eval     # arm run: answers only, skip RAGAS
    python run.py --set my_ids.jsonl       # a custom id-set jsonl
    python run.py -n 20 -k 15 --workers 8  # subset size / top-k / parallelism
    python run.py --help                   # every option + its default
"""
import argparse
import importlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import abort
import orchestrator
import questions
from run_lock import RunLock

_HERE = Path(__file__).parent
DATA = _HERE / "data"
OUTPUT = _HERE / "output"
ARMS = ("lucene", "vector", "artefact", "artefact_v1")


def _write_dev_ids(n, dest):
    """Write a fixed dev id-set (one answerable per HERB type first, then in file
    order) to dest. Deterministic — the smoke set."""
    answerable = [q for q in questions.load_questions() if "::a::" in q.id]
    chosen, seen = [], set()
    for q in answerable:
        if q.type not in {c.type for c in chosen}:
            chosen.append(q); seen.add(q.id)
    for q in answerable:
        if len(chosen) >= n:
            break
        if q.id not in seen:
            chosen.append(q); seen.add(q.id)
    with dest.open("w", encoding="utf-8") as fh:
        for q in chosen[:n]:
            fh.write(json.dumps({"id": q.id}, ensure_ascii=False) + "\n")
    return dest


def _resolve_set(qset, arm, n, ts):
    """--set -> (ids_file, out_dir). smoke = a fresh dev id-set under output/smoke/;
    gold = data/gold100.jsonl; full = the whole set (ids_file None); else a path."""
    if qset == "smoke":
        out = OUTPUT / "smoke" / f"{arm}__smoke__{ts}"
        out.mkdir(parents=True, exist_ok=True)
        return _write_dev_ids(n, out / "question_ids.jsonl"), out
    if qset == "full":
        return None, OUTPUT / f"{arm}__full__{ts}"
    ids = DATA / "gold100.jsonl" if qset == "gold" else Path(qset)
    if not ids.is_file():
        raise SystemExit(f"id-set file not found: {ids}")
    return ids, OUTPUT / f"{arm}__{ids.stem}__{ts}"


def _print_table(rows, arm, n):
    """Mean per metric over the cells that scored, with an error tally."""
    from eval.ragas_catalog import metrics_to_run
    ok, err = defaultdict(list), defaultdict(int)
    for r in rows:
        if r["status"] == "ok":
            ok[r["metric"]].append(r["value"])
        else:
            err[r["metric"]] += 1
    print(f"\nresults  ({arm}, n={n})")
    for metric in metrics_to_run():
        vals = ok.get(metric, [])
        cell = f"{mean(vals):.2f}" if vals else "   -"
        tail = f"   ({err[metric]} err)" if err.get(metric) else ""
        print(f"  {metric:<26} {cell}{tail}")


def main():
    p = argparse.ArgumentParser(
        prog="run.py",
        description="Run one retrieval arm over a question set and score it with RAGAS.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--arm", choices=ARMS, default="lucene", help="retrieval arm")
    p.add_argument("--set", dest="qset", default="smoke", metavar="smoke|gold|full|FILE",
                   help="questions: smoke (dev subset), gold (gold-100), full (all), "
                        "or a path to an id-set jsonl")
    p.add_argument("-n", type=int, default=5, metavar="N",
                   help="dev subset size (only --set smoke)")
    p.add_argument("-k", type=int, default=orchestrator.DEFAULT_TOP_K, metavar="K",
                   help="passages retrieved per question (top-k)")
    p.add_argument("--workers", type=int, default=1, metavar="W",
                   help="questions answered in parallel (1 = serial, safest under NIM's rate cap)")
    p.add_argument("--out", metavar="DIR", help="output dir (default: auto from --set)")
    p.add_argument("--build", action="store_true",
                   help="build and cache the arm's index over the corpus, then exit — "
                        "no questions, no scoring. The construction cost is saved beside "
                        "the index. Re-run an eval later; it loads the cached index.")
    p.add_argument("--no-eval", action="store_true",
                   help="arm run only — generate answers to arm_outputs.jsonl, skip "
                        "RAGAS scoring")
    p.add_argument("--retrieval-only", action="store_true",
                   help="retrieval only — no generation (generator=None); ArmOutput.answer "
                        "is empty. RAGAS retrieval metrics (context_precision_id, "
                        "context_recall_id, context_precision_nonllm, context_recall_nonllm) "
                        "still score real values; answer-based metrics are 0. Use when the "
                        "shared generator is down but retrieval comparison is still wanted.")
    args = p.parse_args()

    pipeline = importlib.import_module(f"pipelines.{args.arm}")

    if args.build:
        corpus = orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS)
        bs = pipeline.prepare_over_corpus(corpus).build_stats
        print(f"{args.arm} index built - {bs.model.calls} embed calls, "
              f"in={bs.model.tokens_in} out={bs.model.tokens_out} tokens, {bs.build_time_s:.1f}s "
              f"(model: {', '.join(bs.models) or 'none'})")
        return

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ids_file, out_dir = _resolve_set(args.qset, args.arm, args.n, ts)
    if args.out:
        out_dir = Path(args.out)
    config = {"top_k": args.k, "workers": args.workers, "out_dir": str(out_dir),
              "retrieval_only": args.retrieval_only}

    pace = "serial" if args.workers == 1 else f"{args.workers} workers"
    n_q = (len(questions.load_questions()) if ids_file is None
           else sum(1 for ln in ids_file.read_text(encoding="utf-8").splitlines() if ln.strip()))
    mode = ("retrieval only (no generation)" if args.retrieval_only
            else "answers only (no eval)" if args.no_eval
            else "answers + RAGAS eval")
    print(f"{args.arm} | set={args.qset} | {n_q} questions | k={args.k} | {pace} | {mode}\n  ->  {out_dir}")
    abort.watch()  # press q to stop the run gracefully (Ctrl+C can be swallowed)
    print("running - press q to abort\n")
    if args.no_eval:
        scorer = None
    else:  # eval deps (ragas/langchain) load only when a run actually scores
        import eval.ragas as scorer
    with RunLock(out_dir):
        summary = orchestrator.run(pipeline, scorer, ids_file, config)

    if not args.no_eval:
        rows = [json.loads(x) for x in
                (Path(summary["out_dir"]) / "eval_results.jsonl").read_text(encoding="utf-8").splitlines()
                if x.strip()]
        _print_table(rows, args.arm, summary["n_ran"])
    print(f"\n{summary['n_ran']}/{summary['n_questions']} answered, "
          f"{summary['n_failed']} failed  ->  {summary['out_dir']}")


if __name__ == "__main__":
    main()
