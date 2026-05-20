"""RAGAS runner for the HERB browser pipeline.

    python -m evaluation.ragas_eval [--input PATH] [--metrics LIST] ...

Reads the JSONL produced by `frontend/scripts/ragas-export.ts` and scores it
with RAGAS. It does NOT run any pipeline, touch Neo4j, or import the legacy
clustering layer — it is purely the consumer of the harness output.

Per JSONL row it uses:
    user_input         <- row.user_input        (the question)
    response           <- row.response          (the answer the pipeline gave)
    retrieved_contexts <- row.retrieved_contexts (chunk contents retrieved)
    reference          <- row.reference          (HERB gold answer; ref metrics)
Rows with `meta.error` or empty `response` are skipped. When a reference-based
metric is requested, zero-context rows are KEPT on purpose (context_recall
scores them ~0 — the retrieval recall hole faithfulness alone hides); rows
without a `reference` are skipped for those metrics.

Metrics:
  Reference-free (no ground truth):
    faithfulness       Is the answer grounded in the retrieved chunks? LLM-only,
                       the default, works out of the box.
    answer_relevancy   Is the answer on-topic? Needs embeddings (opt-in).
  Reference-based (need row.reference = HERB ground_truth):
    context_recall     Did retrieval fetch what the gold answer needs? LLM-only.
    context_precision  Are the retrieved contexts well-targeted? LLM-only
                       (LLMContextPrecisionWithReference).
    answer_correctness Is the answer factually right vs gold? Needs embeddings.

Judge LLM
---------
OpenAI-compatible providers (default: **DeepSeek** `deepseek-chat`, same as
the export answer model). Anthropic still available via `--judge-provider
anthropic`. Keys resolve from env / backend `.env` / `frontend/.env.local`
(`VITE_DEEPSEEK_API_KEY`, `VITE_ANTHROPIC_API_KEY`).

Embeddings (only needed for answer_relevancy)
---------------------------------------------
This venv is Python 3.14 and has no torch/sentence-transformers (no 3.14
wheels), so a local embeddings model is intentionally NOT a dependency. If you
request answer_relevancy, set OPENAI_API_KEY and it uses OpenAI embeddings;
otherwise the harness errors loudly telling you so. faithfulness alone needs
no embeddings.

    pip install -r requirements-eval.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_FRONTEND_ROOT = _BACKEND_ROOT.parent / "frontend"
_DEFAULT_INPUT = Path(__file__).resolve().parent / "ragas_samples.jsonl"


# --- minimal .env reader (mirrors the harness; never logs values) ----------


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        if key:
            out[key] = val
    return out


def _resolve_key(*names: str) -> str:
    import os

    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    backend_env = _parse_env_file(_BACKEND_ROOT / ".env")
    for name in names:
        if backend_env.get(name):
            return backend_env[name]
    fe = _parse_env_file(_FRONTEND_ROOT / ".env.local")
    for name in names:
        if fe.get(name):
            return fe[name]
    return ""


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resume exports can append duplicate ids; keep the best row per id."""
    by_id: dict[str, dict[str, Any]] = {}
    for r in rows:
        rid = str(r.get("id") or "")
        if not rid:
            continue
        prev = by_id.get(rid)
        if prev is None:
            by_id[rid] = r
            continue

        def _score(row: dict[str, Any]) -> tuple[int, int]:
            err = bool((row.get("meta") or {}).get("error"))
            resp = bool((row.get("response") or "").strip())
            return (0 if err else 1, 1 if resp else 0)

        if _score(r) >= _score(prev):
            by_id[rid] = r
    return list(by_id.values())


# --- load + filter samples -------------------------------------------------


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"Input not found: {path}", file=sys.stderr)
        sys.exit(2)
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


REF_METRICS = {"context_recall", "context_precision", "answer_correctness"}

# Match headless export answer cap (`ANSWER_EXPORT_MAX_CHUNKS` in ragas-export.ts).
JUDGE_DEFAULT_MAX_CONTEXTS = 200
JUDGE_DEFAULT_MAX_CONTEXT_CHARS = 1800


def _cap_contexts_for_judge(
    contexts: list[str],
    max_contexts: int,
    max_context_chars: int,
) -> list[str]:
    """JSONL keeps full retrieval; the judge sees a bounded slice only."""
    out = contexts[:max_contexts] if max_contexts > 0 else contexts
    if max_context_chars > 0:
        out = [c[:max_context_chars] for c in out]
    return out


def _valid_samples(
    rows: list[dict[str, Any]],
    metric_names: list[str],
    judge_max_contexts: int,
    judge_max_context_chars: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    # When a reference-based metric is requested we KEEP zero-context rows on
    # purpose: context_recall scores them ~0, which is exactly the retrieval
    # recall hole that reference-free faithfulness silently hid. faithfulness
    # on such a row just comes back NaN (reported as NA).
    wants_ref = any(m in REF_METRICS for m in metric_names)
    samples: list[dict[str, Any]] = []
    skipped: list[str] = []
    for r in rows:
        rid = r.get("id", "?")
        if (r.get("meta") or {}).get("error"):
            skipped.append(f"{rid} (pipeline error)")
            continue
        resp = (r.get("response") or "").strip()
        ctx = _cap_contexts_for_judge(
            [c for c in (r.get("retrieved_contexts") or []) if c],
            judge_max_contexts,
            judge_max_context_chars,
        )
        ref = (r.get("reference") or "").strip()
        if not resp:
            skipped.append(f"{rid} (empty response — dry-run?)")
            continue
        if wants_ref and not ref:
            skipped.append(f"{rid} (no reference — needed for {sorted(REF_METRICS & set(metric_names))})")
            continue
        if not ctx and not wants_ref:
            skipped.append(f"{rid} (no retrieved contexts)")
            continue
        samples.append(
            {
                "id": rid,
                "user_input": r.get("user_input") or r.get("question") or "",
                "response": resp,
                "retrieved_contexts": ctx,
                "reference": ref or None,
            }
        )
    return samples, skipped


# --- RAGAS wiring (defensive across 0.2/0.3 API) ---------------------------


def _build_judge_llm(
    provider: str,
    model: str,
    api_key: str,
    max_tokens: int,
    base_url: str | None = None,
) -> Any:
    try:
        from ragas.llms import LangchainLLMWrapper
    except ImportError as exc:
        print(
            f"Missing eval deps ({exc}). Install: pip install -r requirements-eval.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            print(f"Missing langchain-anthropic ({exc}).", file=sys.stderr)
            sys.exit(1)
        llm = ChatAnthropic(model=model, api_key=api_key, temperature=0, max_tokens=max_tokens)
    else:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            print(f"Missing langchain-openai ({exc}).", file=sys.stderr)
            sys.exit(1)
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com",
            temperature=0,
            max_tokens=max_tokens,
        )
    return LangchainLLMWrapper(llm)


def _build_embeddings_or_exit() -> Any:
    import os

    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "answer_relevancy needs an embeddings model. This venv has no local "
            "embeddings (Python 3.14, no torch wheels). Set OPENAI_API_KEY to use "
            "OpenAI embeddings, or run with --metrics faithfulness only.",
            file=sys.stderr,
        )
        sys.exit(1)
    from langchain_openai import OpenAIEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    return LangchainEmbeddingsWrapper(OpenAIEmbeddings())


def _build_metrics(names: list[str], llm: Any, needs_embeddings: list[str]) -> list[Any]:
    from ragas import metrics as M

    out: list[Any] = []
    for name in names:
        if name == "faithfulness":
            out.append(M.Faithfulness(llm=llm))
        elif name in ("answer_relevancy", "response_relevancy"):
            cls = getattr(M, "ResponseRelevancy", None) or getattr(M, "AnswerRelevancy")
            needs_embeddings.append(name)
            out.append(cls(llm=llm))  # embeddings attached after, see _run
        elif name == "context_recall":
            # LLM-only, reference-based: did retrieval fetch what the gold
            # answer needs? Scores zero-context rows ~0 — the recall hole.
            cls = getattr(M, "LLMContextRecall", None) or getattr(M, "ContextRecall")
            out.append(cls(llm=llm))
        elif name == "context_precision":
            # LLM-only, reference-based ranking quality of retrieved contexts.
            cls = getattr(M, "LLMContextPrecisionWithReference", None) or getattr(M, "ContextPrecision")
            out.append(cls(llm=llm))
        elif name == "answer_correctness":
            needs_embeddings.append(name)  # factual (LLM) + semantic (embeddings)
            out.append(M.AnswerCorrectness(llm=llm))
        else:
            print(
                f"Unknown metric '{name}'. Known: faithfulness, answer_relevancy, "
                f"context_recall, context_precision, answer_correctness",
                file=sys.stderr,
            )
            sys.exit(1)
    return out


def _run(
    samples: list[dict[str, Any]],
    metric_names: list[str],
    judge_provider: str,
    judge_model: str,
    judge_max_tokens: int,
    concurrency: int,
    timeout: int,
) -> Any:
    try:
        from ragas import EvaluationDataset, SingleTurnSample, evaluate
        from ragas.run_config import RunConfig
    except ImportError as exc:
        print(
            f"Missing eval deps ({exc}). Install: pip install -r requirements-eval.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    provider = judge_provider.lower()
    if provider == "anthropic":
        api_key = _resolve_key("ANTHROPIC_API_KEY", "VITE_ANTHROPIC_API_KEY")
        base_url = None
        if not api_key:
            print(
                "No Anthropic key found (ANTHROPIC_API_KEY / VITE_ANTHROPIC_API_KEY).",
                file=sys.stderr,
            )
            sys.exit(2)
    else:
        provider = "deepseek"
        api_key = _resolve_key("DEEPSEEK_API_KEY", "VITE_DEEPSEEK_API_KEY")
        base_url = "https://api.deepseek.com"
        if not api_key:
            print(
                "No DeepSeek key found (DEEPSEEK_API_KEY / VITE_DEEPSEEK_API_KEY).",
                file=sys.stderr,
            )
            sys.exit(2)

    llm = _build_judge_llm(provider, judge_model, api_key, judge_max_tokens, base_url)
    needs_embeddings: list[str] = []
    metrics = _build_metrics(metric_names, llm, needs_embeddings)
    embeddings = _build_embeddings_or_exit() if needs_embeddings else None
    if embeddings is not None:
        for m in metrics:
            if hasattr(m, "embeddings"):
                m.embeddings = embeddings

    def _mk(s: dict[str, Any]) -> Any:
        kw: dict[str, Any] = {
            "user_input": s["user_input"],
            "response": s["response"],
            "retrieved_contexts": s["retrieved_contexts"],
        }
        if s.get("reference"):
            kw["reference"] = s["reference"]
        return SingleTurnSample(**kw)

    ds = EvaluationDataset(samples=[_mk(s) for s in samples])
    run_config = RunConfig(max_workers=max(1, concurrency), timeout=max(30, timeout))
    result = evaluate(
        dataset=ds,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        run_config=run_config,
    )
    # Some RAGAS builds return an awaitable; tolerate both.
    import inspect

    if inspect.isawaitable(result):
        import asyncio

        result = asyncio.run(result)
    # Real metric column names (e.g. llm_context_precision_with_reference) so
    # the report extracts the right df columns regardless of requested alias.
    metric_cols = [getattr(m, "name", None) for m in metrics]
    return result, [c for c in metric_cols if c]


# --- reporting -------------------------------------------------------------


def _report(
    result: Any,
    samples: list[dict[str, Any]],
    metric_cols: list[str],
    *,
    judge_max_contexts: int,
    judge_max_context_chars: int,
) -> dict[str, Any]:
    import math

    df = result.to_pandas()
    sep = "-" * 64
    print(f"\n{sep}\nRAGAS report ({len(samples)} sample(s))\n{sep}")

    cols = [c for c in metric_cols if c in df.columns]
    if not cols:  # fall back: any numeric column that looks like a known metric
        known = ("faithfulness", "answer_relevancy", "response_relevancy",
                 "context_recall", "context_precision",
                 "llm_context_precision_with_reference", "answer_correctness")
        cols = [c for c in df.columns if c in known]

    per_sample = []
    for i, s in enumerate(samples):
        row = {"id": s["id"]}
        for c in cols:
            try:
                v = float(df.iloc[i][c])
                row[c] = None if math.isnan(v) else v  # NaN -> None (e.g. faithfulness on 0-context rows)
            except Exception:
                row[c] = None
        per_sample.append(row)
        scores = "  ".join(
            f"{c}={row[c]:.4f}" if isinstance(row[c], float) else f"{c}=NA" for c in cols
        )
        print(f"  {s['id']:<28} {scores}")

    # Mean over finite values only. A NaN row (e.g. faithfulness with 0
    # retrieved contexts) must not poison the aggregate — it is excluded from
    # that metric's mean but still counts for metrics where it is finite.
    overall: dict[str, float] = {}
    overall_n: dict[str, int] = {}
    for c in cols:
        vals = [
            r[c] for r in per_sample
            if isinstance(r[c], (int, float))
            and not (isinstance(r[c], float) and math.isnan(r[c]))
        ]
        if vals:
            overall[c] = sum(vals) / len(vals)
            overall_n[c] = len(vals)
    print(sep)
    print(
        "  overall: "
        + ("  ".join(f"{k}={v:.4f} (n={overall_n[k]})" for k, v in overall.items()) or "(none)")
    )
    print(sep)
    return {
        "per_sample": per_sample,
        "overall": overall,
        "overall_n": overall_n,
        "n_samples": len(samples),
        "judge_max_contexts": judge_max_contexts,
        "judge_max_context_chars": judge_max_context_chars,
    }


# --- main ------------------------------------------------------------------


def main() -> None:
    p = argparse.ArgumentParser(
        prog="python -m evaluation.ragas_eval",
        description="RAGAS over the harness JSONL (reference-free + reference-based).",
    )
    p.add_argument("--input", type=Path, default=_DEFAULT_INPUT,
                   help=f"Harness JSONL. Default: {_DEFAULT_INPUT}")
    p.add_argument("--metrics", default="faithfulness",
                   help="Comma-separated. Reference-free: faithfulness, "
                        "answer_relevancy. Reference-based (need row.reference): "
                        "context_recall, context_precision, answer_correctness. "
                        "(default: faithfulness)")
    p.add_argument("--judge-provider", default="deepseek", choices=("deepseek", "anthropic"),
                   help="Judge backend (default: deepseek).")
    p.add_argument("--judge-model", default="deepseek-chat",
                   help="Judge model id (default: deepseek-chat).")
    p.add_argument("--judge-max-tokens", type=int, default=8192,
                   help="Judge output token budget (default: 8192). Too low -> "
                        "truncated judge output -> nan scores.")
    p.add_argument("--judge-max-contexts", type=int, default=JUDGE_DEFAULT_MAX_CONTEXTS,
                   help=f"Max retrieved contexts passed to judge (default: {JUDGE_DEFAULT_MAX_CONTEXTS}). "
                        "JSONL keeps full retrieval.")
    p.add_argument("--judge-max-context-chars", type=int, default=JUDGE_DEFAULT_MAX_CONTEXT_CHARS,
                   help=f"Max chars per context string for judge (default: {JUDGE_DEFAULT_MAX_CONTEXT_CHARS}).")
    p.add_argument("--concurrency", type=int, default=8,
                   help="Parallel RAGAS workers (default: 8).")
    p.add_argument("--timeout", type=int, default=600,
                   help="Per-job timeout in seconds (default: 600). RAGAS default 180s "
                        "times out on large HERB contexts under parallel load.")
    p.add_argument("--max", type=int, default=0, help="Cap samples (0 = all)")
    p.add_argument("--report", type=Path, default=None, help="Write JSON report here")
    args = p.parse_args()

    metric_names = [m.strip() for m in args.metrics.split(",") if m.strip()]

    rows = _dedupe_rows(_load_rows(args.input))
    samples, skipped = _valid_samples(
        rows,
        metric_names,
        args.judge_max_contexts,
        args.judge_max_context_chars,
    )
    if args.max > 0:
        samples = samples[: args.max]

    print(f"Loaded {len(rows)} row(s) from {args.input}")
    if skipped:
        print(f"Skipped {len(skipped)}: " + ", ".join(skipped))
    if not samples:
        print("No scorable samples (run the harness WITHOUT --dry-run first).", file=sys.stderr)
        sys.exit(1)

    print(
        f"Scoring {len(samples)} sample(s) with {metric_names}, "
        f"judge={args.judge_provider}/{args.judge_model}, "
        f"contexts<={args.judge_max_contexts}×{args.judge_max_context_chars}chars, "
        f"concurrency={args.concurrency}, timeout={args.timeout}s…"
    )

    result, metric_cols = _run(
        samples,
        metric_names,
        args.judge_provider,
        args.judge_model,
        args.judge_max_tokens,
        args.concurrency,
        args.timeout,
    )
    payload = _report(
        result,
        samples,
        metric_cols,
        judge_max_contexts=args.judge_max_contexts,
        judge_max_context_chars=args.judge_max_context_chars,
    )

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
