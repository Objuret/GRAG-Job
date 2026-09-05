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

from harness import abort
from harness import orchestrator
from harness import questions
from harness.run_lock import RunLock

_HERE = Path(__file__).parent.parent
for _p in (Path(__file__).parent, Path(__file__).parent.parent / "test"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
DATA = _HERE / "data"
ARMS = ("lucene", "vector", "hybrid", "artefact", "artefact_v1", "artefact_v1_det",
        "artefact_v1_relevance_weight", "artefact_v1_five_questions", "artefact_v2",
        "artefact_volmax", "artefact_graph", "artefact_composed", "artefact_chain",
        "artefact_scope", "artefact_cluster")
CHAR_BUDGET_ARMS = ("lucene", "vector", "artefact_v1", "artefact_v1_det", "artefact_v2",
                    "artefact_graph", "artefact_composed", "artefact_chain",
                    "artefact_scope", "artefact_cluster")
DEFAULT_CHAR_BUDGET = 72000
CHUNKS_ROOT = orchestrator.CHUNKS_ROOT
CHARS_ROOT = orchestrator.CHARS_ROOT


def _write_dev_ids(n, dest):
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
    if qset == "gold":
        return DATA / "gold100.jsonl"
    if qset == "10smoke":
        return DATA / "10smoke.jsonl"
    return Path(qset)


def _run_root(char_budget):
    return CHUNKS_ROOT if char_budget is None else CHARS_ROOT


def _checked_out(out, char_budget):
    out_dir = Path(out)
    root = _run_root(char_budget)
    other = CHARS_ROOT if char_budget is None else CHUNKS_ROOT
    if out_dir.resolve().is_relative_to(other.resolve()):
        mode = "depth" if char_budget is None else "fill-to-budget"
        raise SystemExit(f"--out {out_dir} files a {mode} run under {other.name}/ "
                         f"— a {mode} run's root is {root.name}/")
    return out_dir


def _resolve_depth(k, char_budget, arm):
    if k is None and char_budget is None:
        char_budget = DEFAULT_CHAR_BUDGET
    if char_budget is not None and arm not in CHAR_BUDGET_ARMS:
        raise SystemExit(
            f"--arm {arm} has no fill-to-budget mode (the arms that do: "
            f"{', '.join(CHAR_BUDGET_ARMS)}) — pass -k K to run it at a depth cut")
    return (orchestrator.DEFAULT_TOP_K if k is None else k), char_budget


def _resolve_set(qset, arm, n, stamp, root):
    if qset == "smoke":
        out = root / "smoke" / f"{arm}__smoke__{stamp}"
        out.mkdir(parents=True, exist_ok=True)
        return _write_dev_ids(n, out / "question_ids.jsonl"), out
    if qset == "full":
        return None, root / f"{arm}__full__{stamp}"
    ids = _fixed_ids_file(qset)
    if not ids.is_file():
        raise SystemExit(f"id-set file not found: {ids}")
    return ids, root / f"{arm}__{ids.stem}__{stamp}"


def _print_table(rows, arm, n):
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
    return re.sub(r"[^a-z0-9.]+", "-", model.split("/")[-1].lower())


def _wide_parallel_judge(model: str) -> bool:
    model = model.lower()
    return "claude" in model or "gpt-" in model or "gemini" in model


def _stratified_ids(by_id, ids, n):
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

    common = set.intersection(*({r["id"] for r in rs} for rs in recs.values()))
    unknown = sorted(common - set(by_id))
    if unknown:
        raise SystemExit(f"{len(unknown)} answered id(s) not in the question set, e.g. {unknown[:3]}")
    ids = [i for i in by_id if i in common]
    set_stem = None
    if args.qset not in ("smoke", "full"):
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
    if narrowed:
        suffix += f"__n{args.n}"

    print(f"{len(ids)} questions x {len(folders)} folder(s)", flush=True)
    for f in folders:
        print(f"  {f.name}  ->  {f.name}{suffix}", flush=True)
    print("loading eval stack (ragas/langchain - takes a minute cold)...", flush=True)
    import eval.ragas as scorer
    from eval.ragas_catalog import metrics_to_run
    if args.workers is None:
        args.workers = (max(1, len(ids) * len(metrics_to_run()))
                        if _wide_parallel_judge(args.judge) else 1)

    corpus = orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS)
    abort.watch()
    print("running - press q to abort\n", flush=True)
    for f in folders:
        out_dir = f.parent / (f.name + suffix)
        out_dir.mkdir(parents=True, exist_ok=True)
        arm = f.name.split("__")[0]
        with RunLock(out_dir):
            seed = out_dir / "arm_outputs.jsonl"
            if seed.is_file():
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
            judge_config = {
                "judge_model": args.judge,
                "judge_backend": getattr(scorer, "LAST_JUDGE_BACKEND", None),
                "judge_effort": getattr(scorer, "LAST_JUDGE_REASONING_EFFORT", None),
                "judge_usage": getattr(scorer, "LAST_JUDGE_USAGE", None),
                "judge_elapsed_s": getattr(scorer, "LAST_JUDGE_WALL_TIME_S", None),
            }
            manifest_path = out_dir / "eval_manifest.json"
            manifest = orchestrator.build_eval_manifest(judge_config, "ragas", arm, f)
            if manifest_path.is_file():
                try:
                    prior = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    prior = None
                manifest = orchestrator._accumulated_judge(prior, manifest)
            manifest_path.write_text(
                json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
                encoding="utf-8")
        cells = [json.loads(x) for x in (out_dir / "eval_results.jsonl")
                 .read_text(encoding="utf-8").splitlines() if x.strip()]
        _print_table(cells, f"{arm} | {args.judge}", len(chosen))
    print(f"\ndone - {len(folders)} folder(s) re-judged with {args.judge}")


def _flag(spec):
    name, sep, value = spec.partition("=")
    if not sep or not name:
        raise argparse.ArgumentTypeError(f"expected NAME=VALUE, got {spec!r}")
    return name, value


def _apply_flags(pairs):
    if not pairs:
        return
    for name, value in pairs:
        if value:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)
    line = "flags: " + "  ".join(f"{n}={v}" for n, v in pairs)
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)


def main():
    p = argparse.ArgumentParser(
        prog="run.py",
        description="Run one retrieval arm over a question set and score it with RAGAS.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--arm", choices=ARMS, default="lucene", help="retrieval arm; the current artefact edition is artefact_v2")
    p.add_argument("--set", dest="qset", default="smoke", metavar="smoke|10smoke|gold|full|FILE",
                   help="questions: smoke (dev subset), 10smoke (fixed comparison ten), "
                        "gold (gold-100), full (all), "
                        "or a path to an id-set jsonl")
    p.add_argument("-n", type=int, default=None, metavar="N",
                   help="question subset size: dev subset for --set smoke (default 5); "
                        "with --rejudge, a type-stratified N of the answers")
    p.add_argument("-k", type=int, default=None, metavar="K",
                   help="depth mode: K passages retrieved per question (top-k) "
                        "instead of the character budget — the cut the archived "
                        "k=50 runs were produced under. The run files under "
                        f"{CHUNKS_ROOT.name}/ and its manifest records a null "
                        "char_budget. Does not combine with --char-budget")
    p.add_argument("--char-budget", type=int, default=None, metavar="N",
                   help=f"the run's character budget, {DEFAULT_CHAR_BUDGET} when "
                        "neither -k nor this names a depth: consume the arm's "
                        "ranking until the context text totals exactly N characters "
                        "— whole retrieval units (a baseline's artifact, an artefact "
                        "leg's chunk) in rank order, the crossing unit cut mid-text "
                        "as the final context, a ranking that runs out recorded at "
                        "its true total (arms: "
                        + ", ".join(CHAR_BUDGET_ARMS) + "); the run folder carries "
                        "cb<N> and the manifest records char_budget")
    p.add_argument("--workers", type=int, default=None, metavar="W",
                   help="parallelism: questions while answering, cells while re-judging "
                        "(default 1, safest under NIM's rate cap; a claude-*, gpt-*, or gemini-* --judge "
                        "auto-sizes to every cell at once)")
    p.add_argument("--out", metavar="DIR",
                   help="output dir (default: auto from --set). A run belongs to the "
                        f"root its depth cut names — {CHARS_ROOT.name}/ filling to a "
                        f"character budget, {CHUNKS_ROOT.name}/ at -k — and a DIR "
                        "inside the other one is refused")
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
                        "scores); the judge+embed pass is skipped, so zero model calls. "
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
                        "--flag HERB_DESC_CUT=0 — applied in this process before the "
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
    if args.k is not None and args.k < 1:
        p.error("-k must be >= 1")
    if args.k is not None and args.char_budget is not None:
        p.error("-k and --char-budget are the two depth cuts and a run takes one: "
                "-k K consumes K retrieval units, --char-budget N fills the context "
                "to N characters")
    if args.char_budget is not None:
        if args.char_budget < 1:
            p.error("--char-budget must be >= 1")
        if args.build:
            p.error("--char-budget is a run option; --build only builds the index")
    _apply_flags(args.flag)
    if args.judge:
        os.environ["RAGAS_JUDGE_MODEL"] = args.judge
    if args.rejudge:
        if not args.judge:
            p.error("--rejudge needs --judge (the judge to re-score with)")
        if (args.build or args.no_eval or args.retrieval_only or args.out
                or args.char_budget is not None):
            p.error("--rejudge is eval-only; it does not combine with "
                    "--build/--no-eval/--retrieval-only/--out/--char-budget")
        _rejudge(args)
        return
    if args.n is None:
        args.n = 5
    if args.workers is None:
        args.workers = 1

    pipeline = importlib.import_module(f"arms.{args.arm}")

    if args.build:
        corpus = orchestrator.open_corpus(orchestrator.DEFAULT_CORPUS)
        bs = pipeline.prepare_over_corpus(corpus).build_stats
        print(f"{args.arm} index built - {bs.model.calls} embed calls, "
              f"in={bs.model.tokens_in} out={bs.model.tokens_out} tokens, {bs.build_time_s:.1f}s "
              f"(model: {', '.join(bs.models) or 'none'})")
        return

    top_k, args.char_budget = _resolve_depth(args.k, args.char_budget, args.arm)
    if (args.char_budget is not None
            and (getattr(pipeline, "RETRIEVAL_FLAGS", None) or {}).get("HERB_CURVE_WALK")):
        raise SystemExit("HERB_CURVE_WALK's stop rule sets its own kept depth and "
                         "does not combine with the character budget — pass an "
                         "explicit -k K to run the curve walk at a depth cut")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stamp = ts if args.char_budget is None else f"cb{args.char_budget}__{ts}"
    ids_file, out_dir = _resolve_set(args.qset, args.arm, args.n, stamp,
                                     _run_root(args.char_budget))
    if args.out:
        out_dir = _checked_out(args.out, args.char_budget)
    config = {"top_k": top_k, "workers": args.workers, "out_dir": str(out_dir),
              "retrieval_only": args.retrieval_only,
              "char_budget": args.char_budget}
    if args.generator:
        config["generator_model"] = args.generator

    pace = "serial" if args.workers == 1 else f"{args.workers} workers"
    n_q = (len(questions.load_questions()) if ids_file is None
           else sum(1 for ln in ids_file.read_text(encoding="utf-8").splitlines() if ln.strip()))
    mode = ("retrieval only (no generation)" if args.retrieval_only
            else "answers only (no eval)" if args.no_eval
            else "answers + RAGAS eval")
    depth = (f"k={top_k}" if args.char_budget is None
             else f"char-budget={args.char_budget} | k={top_k}")
    print(f"{args.arm} | set={args.qset} | {n_q} questions | {depth} | {pace} | {mode}"
          f"\n  ->  {out_dir}", flush=True)
    abort.watch()
    print("running - press q to abort\n")
    if args.no_eval:
        scorer = None
    else:
        import eval.ragas as scorer
    with RunLock(out_dir):
        summary = orchestrator.run(pipeline, scorer, ids_file, config)

    if not args.no_eval:
        rows = [json.loads(x) for x in
                (Path(summary["out_dir"]) / "eval_results.jsonl").read_text(encoding="utf-8").splitlines()
                if x.strip()]
        _print_table(rows, args.arm, summary["n_ran"])
    short = ("" if summary["n_exhausted"] is None else
             f", {summary['n_exhausted']} did not fill the "
             f"{args.char_budget} char budget")
    print(f"\n{summary['n_ran']}/{summary['n_questions']} answered, "
          f"{summary['n_failed']} failed{short}  ->  {summary['out_dir']}")


if __name__ == "__main__":
    main()
