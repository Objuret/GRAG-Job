"""RAGAS runner for the HERB browser pipeline.

    python -m evaluation.ragas_eval --input export.jsonl --out export.scored.jsonl

Reads export JSONL, calls RAGAS only on scorable rows, writes **atomic** JSONL:
every input row is preserved; failed/skipped rows get null metrics + skip_reason.
Use `python -m evaluation.aggregate_scores` for means/medians.

`retrieved_contexts` is scored as-is (no judge trim by default). Export must write
the same evidence slice the answer model saw (see ragas-export.ts).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.metrics_common import answer_token_scores

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_FRONTEND_ROOT = _BACKEND_ROOT.parent / "frontend"


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
        row = json.loads(line)
        if row.get("kind") == "run_frame":
            continue
        rows.append(row)
    return rows


REF_METRICS = {"context_recall", "context_precision", "answer_correctness"}

# Primary thesis comparison (graph vs baseline @ k=40).
THESIS_METRICS = "faithfulness,context_recall,context_precision,answer_correctness"

# 0 = no judge-side trim; export owns the evidence budget.
JUDGE_DEFAULT_MAX_CONTEXTS = 0
JUDGE_DEFAULT_MAX_CONTEXT_CHARS = 0


def _cap_contexts_for_judge(
    contexts: list[str],
    max_contexts: int,
    max_context_chars: int,
) -> list[str]:
    """Legacy opt-in trim only — default is no cap (export is authoritative)."""
    if max_contexts <= 0 and max_context_chars <= 0:
        return contexts
    out = contexts[:max_contexts] if max_contexts > 0 else contexts
    if max_context_chars > 0:
        out = [c[:max_context_chars] for c in out]
    return out


def _skip_reason(row: dict[str, Any], metric_names: list[str]) -> str | None:
    if (row.get("meta") or {}).get("error"):
        return "pipeline error"
    if not (row.get("response") or "").strip():
        return "empty response"
    wants_ref = any(m in REF_METRICS for m in metric_names)
    if wants_ref and not (row.get("reference") or "").strip():
        return "missing reference"
    ctx = [c for c in (row.get("retrieved_contexts") or []) if c]
    if not ctx and not wants_ref:
        return "no retrieved contexts"
    return None


def _sample_from_row(
    row: dict[str, Any],
    metric_names: list[str],
    judge_max_contexts: int,
    judge_max_context_chars: int,
) -> dict[str, Any]:
    ctx = _cap_contexts_for_judge(
        [c for c in (row.get("retrieved_contexts") or []) if c],
        judge_max_contexts,
        judge_max_context_chars,
    )
    return {
        "id": row.get("id", "?"),
        "user_input": row.get("user_input") or row.get("question") or "",
        "response": (row.get("response") or "").strip(),
        "retrieved_contexts": ctx,
        "reference": (row.get("reference") or "").strip() or None,
    }


def _deterministic_for_row(row: dict[str, Any]) -> dict[str, Any]:
    ref = (row.get("reference") or "").strip()
    resp = (row.get("response") or "").strip()
    if not ref or not resp:
        return {}
    return answer_token_scores(ref, resp)


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
            "answer_relevancy and answer_correctness need an embeddings model. "
            "This venv has no local embeddings (Python 3.14, no torch wheels). "
            "Set OPENAI_API_KEY for OpenAI embeddings, or use "
            "python -m evaluation.answer_token_score for deterministic HERB token F1.",
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
        description="Score export JSONL with RAGAS; write atomic scored JSONL.",
    )
    p.add_argument("--input", type=Path, required=True,
                   help="Export JSONL to score")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Atomic scored JSONL (default: <input>.scored.jsonl)",
    )
    p.add_argument("--metrics", default="faithfulness",
                   help=f"Comma-separated metrics. --thesis -> {THESIS_METRICS}")
    p.add_argument("--thesis", action="store_true",
                   help=f"Primary thesis eval: metrics={THESIS_METRICS}")
    p.add_argument("--merge-report", type=Path, default=None,
                   help="Merge summary into an existing report JSON (legacy)")
    p.add_argument("--judge-provider", default="deepseek", choices=("deepseek", "anthropic"))
    p.add_argument("--judge-model", default="deepseek-chat")
    p.add_argument("--judge-max-tokens", type=int, default=8192)
    p.add_argument(
        "--judge-max-contexts",
        type=int,
        default=JUDGE_DEFAULT_MAX_CONTEXTS,
        help="Legacy judge trim (0 = use export contexts as-is)",
    )
    p.add_argument(
        "--judge-max-context-chars",
        type=int,
        default=JUDGE_DEFAULT_MAX_CONTEXT_CHARS,
        help="Legacy per-context char trim (0 = off)",
    )
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--max", type=int, default=0, help="Cap scored samples (0 = all)")
    p.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional summary report (use aggregate_scores for filtering)",
    )
    args = p.parse_args()

    if args.thesis and args.metrics == "faithfulness":
        args.metrics = THESIS_METRICS

    metric_names = [m.strip() for m in args.metrics.split(",") if m.strip()]
    out_path = args.out or args.input.with_name(f"{args.input.stem}.scored.jsonl")

    rows = _load_rows(args.input)
    if args.max > 0:
        rows = rows[: args.max]

    score_jobs: list[tuple[int, dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        reason = _skip_reason(row, metric_names)
        if reason is None:
            score_jobs.append((idx, _sample_from_row(
                row, metric_names, args.judge_max_contexts, args.judge_max_context_chars,
            )))

    print(f"Loaded {len(rows)} row(s) from {args.input}")
    print(
        f"RAGAS: {len(score_jobs)} to score, {len(rows) - len(score_jobs)} skipped (no API)"
    )

    ragas_by_id: dict[str, dict[str, Any]] = {}
    metric_cols: list[str] = []
    if score_jobs:
        samples = [s for _, s in score_jobs]
        print(
            f"Scoring with {metric_names}, judge={args.judge_provider}/{args.judge_model}, "
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
        import math

        df = result.to_pandas()
        cols = [c for c in metric_cols if c in df.columns]
        if not cols:
            known = (
                "faithfulness", "answer_relevancy", "response_relevancy",
                "context_recall", "context_precision",
                "llm_context_precision_with_reference", "answer_correctness",
            )
            cols = [c for c in df.columns if c in known]
        for i, (_, sample) in enumerate(score_jobs):
            row_scores: dict[str, Any] = {}
            for c in cols:
                try:
                    v = float(df.iloc[i][c])
                    row_scores[c] = None if math.isnan(v) else v
                except Exception:
                    row_scores[c] = None
            ragas_by_id[str(sample["id"])] = row_scores

    scored_at = datetime.now(timezone.utc).isoformat()
    atomic_rows: list[dict[str, Any]] = []
    for row in rows:
        rid = str(row.get("id") or "?")
        reason = _skip_reason(row, metric_names)
        out_row = dict(row)
        out_row["deterministic"] = _deterministic_for_row(row)
        if reason:
            out_row["ragas"] = None
            out_row["score_meta"] = {
                "scored": False,
                "skip_reason": reason,
                "metrics_requested": metric_names,
                "judge_provider": args.judge_provider,
                "judge_model": args.judge_model,
                "judge_max_contexts": args.judge_max_contexts,
                "judge_max_context_chars": args.judge_max_context_chars,
                "scored_at": scored_at,
            }
        else:
            scores = ragas_by_id.get(rid, {})
            out_row["ragas"] = scores
            out_row["score_meta"] = {
                "scored": True,
                "skip_reason": None,
                "metrics_requested": metric_names,
                "metric_columns": list(scores.keys()),
                "judge_provider": args.judge_provider,
                "judge_model": args.judge_model,
                "judge_max_contexts": args.judge_max_contexts,
                "judge_max_context_chars": args.judge_max_context_chars,
                "scored_at": scored_at,
            }
        atomic_rows.append(out_row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for r in atomic_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {out_path}")

    if args.report or args.merge_report:
        from evaluation.aggregate_scores import build_summary

        summary = build_summary(atomic_rows)
        summary["judge_provider"] = args.judge_provider
        summary["judge_model"] = args.judge_model
        summary["judge_max_contexts"] = args.judge_max_contexts
        summary["judge_max_context_chars"] = args.judge_max_context_chars
        summary["metrics_requested"] = metric_names

        if args.merge_report:
            if not args.merge_report.exists():
                print(f"Merge target not found: {args.merge_report}", file=sys.stderr)
                sys.exit(2)
            from evaluation.metrics_common import merge_report_payload

            base = json.loads(args.merge_report.read_text(encoding="utf-8"))
            summary = merge_report_payload(base, summary)

        report_path = args.report or args.merge_report
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"Wrote {report_path}")

    if not rows:
        print("No rows in input.", file=sys.stderr)
        sys.exit(1)

    if not score_jobs:
        print("No rows sent to RAGAS (all skipped); atomic file still written.", file=sys.stderr)


if __name__ == "__main__":
    main()
