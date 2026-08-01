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
    python run.py --flag HERB_TAG_FIRST=1  # a HERB_* toggle for this run only
    python run.py --rejudge output/<run> --judge claude-haiku-4-5 -n 10
                                           # re-score a run's answers, other judge
    python run.py --help                   # every option + its default
"""
import argparse
import importlib
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import asdict
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
ARMS = ("lucene", "vector", "hybrid", "artefact", "artefact_v1", "artefact_v1_det")


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


def _fixed_ids_file(qset):
    """Resolve a named fixed question set or an explicit id-set path."""
    if qset == "gold":
        return DATA / "gold100.jsonl"
    if qset == "10smoke":
        return DATA / "10smoke.jsonl"
    return Path(qset)


def _resolve_set(qset, arm, n, ts):
    """--set -> (ids_file, out_dir). smoke = a fresh dev id-set under output/smoke/;
    10smoke = the fixed ten-question comparison set; gold = data/gold100.jsonl;
    full = the whole set (ids_file None); else a path."""
    if qset == "smoke":
        out = OUTPUT / "smoke" / f"{arm}__smoke__{ts}"
        out.mkdir(parents=True, exist_ok=True)
        return _write_dev_ids(n, out / "question_ids.jsonl"), out
    if qset == "full":
        return None, OUTPUT / f"{arm}__full__{ts}"
    ids = _fixed_ids_file(qset)
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


def _slug(model):
    """'qwen/qwen3.5-397b-a17b' -> 'qwen3.5-397b-a17b' — dir-safe judge tag for
    __j-<slug> folder names."""
    return re.sub(r"[^a-z0-9.]+", "-", model.split("/")[-1].lower())


def _wide_parallel_judge(model: str) -> bool:
    """Judges with no queue to respect: open every cell at once."""
    model = model.lower()
    return "claude" in model or "gpt-" in model or "gemini" in model


def _stratified_ids(by_id, ids, n):
    """n of `ids` by round-robin over the HERB answer types, file order within each
    type — every type stays represented (the gold-100 rationale: a head-of-file cut
    drops the rare types entirely)."""
    pools = defaultdict(list)
    for i in ids:
        pools[by_id[i].type].append(i)
    order = sorted(pools)
    chosen, i = [], 0
    while len(chosen) < n and any(pools.values()):
        pool = pools[order[i % len(order)]]
        if pool:
            chosen.append(pool.pop(0))
        i += 1
    return chosen


def _rejudge(args):
    """--rejudge: score existing run folders' answers under --judge, each into a
    sibling <folder>__j-<slug> dir seeded with the chosen answer rows — the source
    folders are never touched. Eval-only: no pipeline, no index, no generation;
    scoring is resumable per cell like any eval run."""
    print(f"rejudge | judge={args.judge} | {len(args.rejudge)} folder(s)", flush=True)
    folders = [Path(f) for f in args.rejudge]
    missing = [str(f) for f in folders if not (f / "arm_outputs.jsonl").is_file()]
    if missing:
        raise SystemExit("no arm_outputs.jsonl in: " + ", ".join(missing))

    by_id = {q.id: q for q in questions.load_questions()}
    recs = {f: [json.loads(x)
                for x in (f / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()
                if x.strip()]
            for f in folders}

    # The judged ids: answers present in EVERY folder (one id set across arms, or
    # the judge comparison is apples to oranges), in question-file order — the pick
    # must not depend on which folder is listed first or how its rows are ordered.
    common = set.intersection(*({r["id"] for r in rs} for rs in recs.values()))
    unknown = sorted(common - set(by_id))
    if unknown:
        raise SystemExit(f"{len(unknown)} answered id(s) not in the question set, e.g. {unknown[:3]}")
    ids = [i for i in by_id if i in common]
    set_stem = None
    if args.qset not in ("smoke", "full"):  # gold or an ids file narrows the set
        ids_file = _fixed_ids_file(args.qset)
        if not ids_file.is_file():
            raise SystemExit(f"id-set file not found: {ids_file}")
        listed = orchestrator._read_ids(ids_file)
        absent = [i for i in listed if i not in common]
        if absent:
            raise SystemExit(f"{len(absent)} id(s) not answered in every folder, e.g. {absent[:3]}")
        ids, set_stem = listed, ids_file.stem
    if not ids:
        raise SystemExit("no common answered ids across the folders")
    narrowed = args.n is not None and args.n < len(ids)
    if narrowed:
        ids = _stratified_ids(by_id, ids, args.n)

    suffix = f"__j-{_slug(args.judge)}"
    if set_stem:
        suffix += f"__{set_stem}"
    if narrowed:  # the tag describes the dir's contents, so only when -n actually cut
        suffix += f"__n{args.n}"

    print(f"{len(ids)} questions x {len(folders)} folder(s)", flush=True)
    for f in folders:
        print(f"  {f.name}  ->  {f.name}{suffix}", flush=True)
    print("loading eval stack (ragas/langchain - takes a minute cold)...", flush=True)
    import eval.ragas as scorer  # reads RAGAS_JUDGE_MODEL, set from --judge in main
    from eval.ragas_catalog import metrics_to_run
    if args.workers is None:
        # Subscription CLI judges queue every cell; their shared judge pool sets
        # the real in-flight cap.
        args.workers = (max(1, len(ids) * len(metrics_to_run()))
                        if _wide_parallel_judge(args.judge) else 1)

    corpus = orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS)
    abort.watch()  # press q to stop; finished cells are on disk, resume continues
    print("running - press q to abort\n", flush=True)
    for f in folders:
        out_dir = f.parent / (f.name + suffix)
        out_dir.mkdir(parents=True, exist_ok=True)
        arm = f.name.split("__")[0]
        with RunLock(out_dir):
            seed = out_dir / "arm_outputs.jsonl"
            if seed.is_file():  # resume: an existing judge dir keeps its rows
                rows = [json.loads(x) for x in seed.read_text(encoding="utf-8").splitlines()
                        if x.strip()]
            else:
                wanted = {r["id"]: r for r in recs[f]}
                rows = [wanted[i] for i in ids]
                with seed.open("w", encoding="utf-8") as fh:
                    for r in rows:
                        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            chosen = [by_id[r["id"]] for r in rows]
            orchestrator.run_one_evaluator(
                scorer, [orchestrator._rehydrate(r) for r in rows], chosen, arm, corpus,
                out_dir / "eval_results.jsonl", args.workers)
            # source_run names the folder whose answers were scored — the judge dir's
            # one link back to the generation run.
            # The rejudge path writes its manifest directly rather than travelling
            # through orchestrator.run_arm, so explicitly preserve the scorer's
            # provider telemetry here too.  This keeps cross-judge comparisons
            # auditable: model/backend/effort plus aggregate token and wall time.
            judge_config = {
                "judge_model": args.judge,
                "judge_backend": getattr(scorer, "LAST_JUDGE_BACKEND", None),
                "judge_effort": getattr(scorer, "LAST_JUDGE_REASONING_EFFORT", None),
                "judge_usage": getattr(scorer, "LAST_JUDGE_USAGE", None),
                "judge_elapsed_s": getattr(scorer, "LAST_JUDGE_WALL_TIME_S", None),
            }
            (out_dir / "eval_manifest.json").write_text(
                json.dumps(asdict(orchestrator.build_eval_manifest(
                    judge_config, "ragas", arm, f)),
                    ensure_ascii=False, indent=2), encoding="utf-8")
        cells = [json.loads(x) for x in (out_dir / "eval_results.jsonl")
                 .read_text(encoding="utf-8").splitlines() if x.strip()]
        _print_table(cells, f"{arm} | {args.judge}", len(chosen))
    print(f"\ndone - {len(folders)} folder(s) re-judged with {args.judge}")


def _flag(spec):
    """--flag NAME=VALUE -> (NAME, VALUE). A spec with no '=' or an empty name
    fails at parse; the value passes through as a string, so the pipeline's own
    env parsing validates it."""
    name, sep, value = spec.partition("=")
    if not sep or not name:
        raise argparse.ArgumentTypeError(f"expected NAME=VALUE, got {spec!r}")
    return name, value


def _apply_flags(pairs):
    """Set each --flag pair in THIS process's environment — before any pipeline
    module imports, so constants read at import time see them — and print the
    flags the run carries. A --flag overwrites a session env var of the same
    name; a blank value (--flag NAME=) removes the name, so the run sees the
    pipeline's own default; nothing persists past the process."""
    if not pairs:
        return
    for name, value in pairs:
        if value:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)
    # print through the stream's own encoding so a value its codepage cannot
    # carry degrades to '?' instead of killing the run under a redirected stdout
    line = "flags: " + "  ".join(f"{n}={v}" for n, v in pairs)
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)


def main():
    p = argparse.ArgumentParser(
        prog="run.py",
        description="Run one retrieval arm over a question set and score it with RAGAS.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--arm", choices=ARMS, default="lucene", help="retrieval arm")
    p.add_argument("--set", dest="qset", default="smoke", metavar="smoke|10smoke|gold|full|FILE",
                   help="questions: smoke (dev subset), 10smoke (fixed comparison ten), "
                        "gold (gold-100), full (all), "
                        "or a path to an id-set jsonl")
    p.add_argument("-n", type=int, default=None, metavar="N",
                   help="question subset size: dev subset for --set smoke (default 5); "
                        "with --rejudge, a type-stratified N of the answers")
    p.add_argument("-k", type=int, default=orchestrator.DEFAULT_TOP_K, metavar="K",
                   help="passages retrieved per question (top-k)")
    p.add_argument("--workers", type=int, default=None, metavar="W",
                   help="parallelism: questions while answering, cells while re-judging "
                        "(default 1, safest under NIM's rate cap; a claude-*, gpt-*, or gemini-* --judge "
                        "auto-sizes to every cell at once)")
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
                        "is empty. RAGAS scores only the judge-free, embed-free metrics "
                        "(context_precision_id, context_recall_id, context_precision_nonllm, "
                        "context_recall_nonllm, and the deterministic answer-vs-gold string "
                        "scores); the judge+embed pass is skipped, so zero NIM scoring calls. "
                        "Use when the shared generator is down but retrieval comparison is "
                        "still wanted.")
    p.add_argument("--generator", metavar="MODEL",
                   help="generator model for this run (default: the shared canon "
                        "generator; claude-* runs through headless Claude Code)")
    p.add_argument("--judge", metavar="MODEL",
                   help="judge model for RAGAS scoring (claude-* runs through headless "
                        "Claude Code, gpt-* through subscription-authenticated Codex CLI, "
                        "gemini-* through signed-in Gemini CLI; "
                        "default: the canon judge)")
    p.add_argument("--rejudge", nargs="+", metavar="DIR",
                   help="re-score these existing run folders' answers with --judge, each "
                        "into a sibling __j-<slug> dir (sources untouched; --set/-n narrow "
                        "the ids, --arm/-k are ignored)")
    p.add_argument("--flag", action="append", type=_flag, default=[], metavar="NAME=VALUE",
                   help="set an env var for THIS run only (repeatable), e.g. "
                        "--flag HERB_TAG_FIRST=1 — applied in this process before the "
                        "pipeline module imports, so toggles read at import time see it; "
                        "overrides a session env var of the same name and never sticks "
                        "past the run. A blank value (--flag NAME=) removes the name, "
                        "so the run sees the pipeline's own default. Values pass "
                        "through as strings; the pipeline's own env parsing "
                        "validates them")
    args = p.parse_args()

    if args.n is not None and args.n < 1:
        p.error("-n must be >= 1")
    if args.workers is not None and args.workers < 1:
        p.error("--workers must be >= 1")
    _apply_flags(args.flag)
    if args.judge:
        os.environ["RAGAS_JUDGE_MODEL"] = args.judge  # read at eval import
    if args.rejudge:
        if not args.judge:
            p.error("--rejudge needs --judge (the judge to re-score with)")
        if args.build or args.no_eval or args.retrieval_only or args.out:
            p.error("--rejudge is eval-only; it does not combine with "
                    "--build/--no-eval/--retrieval-only/--out")
        _rejudge(args)
        return
    if args.n is None:
        args.n = 5
    if args.workers is None:
        args.workers = 1

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
    if args.generator:
        config["generator_model"] = args.generator

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
