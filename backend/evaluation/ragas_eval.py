"""RAGAS evaluation harness for the graph query layer.

    python -m evaluation.ragas_eval [options]

What is evaluated
-----------------
For each query in the queries YAML file the harness:
  1. Runs the graph query (by_canonical / recent_active / multidim) to get
     the top-N ranked files.
  2. For each file, fetches the top-K chunks ordered by relevance_to_file.
  3. Builds one RAGAS SingleTurnSample per (query, file):
       user_input         = the natural-language question
       retrieved_contexts = raw chunk content strings  (what the LLM should
                            be able to ground its extraction in)
       response           = joined chunk descriptions  (what the LLM actually
                            extracted — the claims to verify)
  4. Skips files where no chunk has a description yet (LLM extraction not run).

Metrics (reference-free — no ground truth needed)
-----------
  faithfulness      Does the chunk description contradict its source content?
                    A score < 1.0 indicates hallucination in the extraction.
  answer_relevancy  Is the aggregated description relevant to the search query?
                    A score < 1.0 means the query layer returned off-topic files.

The evaluator LLM is the same OpenAI-compatible endpoint configured in .env
(LLM_BASE_URL / LLM_MODEL / LLM_API_KEY), so no extra credentials are needed.

Requirements
------------
    pip install -r requirements-eval.txt   # ragas>=0.2.0, openai>=1.30

Options
-------
    --queries PATH         YAML file with query definitions
                           (default: evaluation/sample_queries.yaml)
    --query-ids ID ...     Run only these query ids (default: all)
    --files-per-query N    Max files to evaluate per query (default: 5)
    --chunks-per-file N    Max chunks to fetch per file (default: 8)
    --metrics LIST         Comma-separated: faithfulness,answer_relevancy
                           (default: faithfulness,answer_relevancy)
    --output PATH          Write JSON report to this path (default: stdout only)
    --dry-run              Print samples without calling RAGAS
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from shared.config import Settings
from shared.neo4j_client import Neo4jClient
from clustering.query import (
    FileResult,
    ChunkResult,
    files_by_canonical,
    files_recent_active,
    files_multidim,
    chunks_for_file,
)

_DEFAULT_QUERIES_PATH = Path(__file__).resolve().parent / "sample_queries.yaml"


# ---------------------------------------------------------------------------
# Query definitions
# ---------------------------------------------------------------------------


@dataclass
class QueryDef:
    id: str
    question: str
    query_type: str                           # canonical | recent_active | multidim
    cluster: str | None = None
    canonical_id: str | None = None
    constraints: list[dict[str, str]] = field(default_factory=list)
    files_limit: int | None = None            # per-query override
    chunks_limit: int | None = None


def _load_queries(path: Path) -> list[QueryDef]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = raw.get("queries", raw) if isinstance(raw, dict) else raw
    out: list[QueryDef] = []
    for item in items:
        out.append(QueryDef(
            id=item["id"],
            question=item["question"],
            query_type=item["query_type"],
            cluster=item.get("cluster"),
            canonical_id=item.get("canonical_id"),
            constraints=item.get("constraints", []),
            files_limit=item.get("files_limit"),
            chunks_limit=item.get("chunks_limit"),
        ))
    return out


# ---------------------------------------------------------------------------
# Graph retrieval
# ---------------------------------------------------------------------------


async def _retrieve_files(
    client: Neo4jClient,
    qdef: QueryDef,
    files_per_query: int,
) -> list[FileResult]:
    limit = qdef.files_limit or files_per_query
    if qdef.query_type == "canonical":
        return await files_by_canonical(
            client,
            cluster=qdef.cluster or "",
            canonical_id=qdef.canonical_id or "",
            limit=limit,
        )
    if qdef.query_type == "recent_active":
        return await files_recent_active(client, limit=limit)
    if qdef.query_type == "multidim":
        pairs = [(c["cluster"], c["canonical_id"]) for c in qdef.constraints]
        return await files_multidim(client, constraints=pairs, limit=limit)
    raise ValueError(f"Unknown query_type: {qdef.query_type!r}")


# ---------------------------------------------------------------------------
# Sample building
# ---------------------------------------------------------------------------


@dataclass
class EvalSample:
    query_id: str
    question: str
    file_id: str
    rel_path: str
    user_input: str
    response: str
    retrieved_contexts: list[str]


async def _build_samples(
    client: Neo4jClient,
    qdef: QueryDef,
    files_per_query: int,
    chunks_per_file: int,
) -> list[EvalSample]:
    files = await _retrieve_files(client, qdef, files_per_query)
    samples: list[EvalSample] = []

    for file_result in files:
        limit = qdef.chunks_limit or chunks_per_file
        chunks: list[ChunkResult] = await chunks_for_file(
            client, file_result.file_id, limit=limit
        )

        contexts = [c.content for c in chunks if c.content]
        descriptions = [c.description for c in chunks if c.description]

        if not contexts or not descriptions:
            # Nothing to evaluate — extraction hasn't run on these chunks yet.
            continue

        response = "\n".join(descriptions)
        samples.append(EvalSample(
            query_id=qdef.id,
            question=qdef.question,
            file_id=file_result.file_id,
            rel_path=f"{file_result.dataset_id}/{file_result.rel_path}",
            user_input=qdef.question,
            response=response,
            retrieved_contexts=contexts,
        ))

    return samples


# ---------------------------------------------------------------------------
# RAGAS evaluation
# ---------------------------------------------------------------------------


def _make_ragas_llm(settings: Settings) -> Any:
    try:
        from openai import AsyncOpenAI
        from ragas.llms import llm_factory
    except ImportError as exc:
        print(
            f"\nMissing evaluation dependencies: {exc}\n"
            "Install with: pip install -r requirements-eval.txt\n",
            file=sys.stderr,
        )
        sys.exit(1)

    openai_client = AsyncOpenAI(
        api_key=settings.agent_api_key,
        base_url=settings.agent_base_url,
    )
    return llm_factory(settings.agent_model, openai_client=openai_client)


def _build_metric_list(metric_names: list[str], llm: Any) -> list[Any]:
    try:
        from ragas.metrics import Faithfulness, AnswerRelevancy
    except ImportError as exc:
        print(f"ragas import error: {exc}", file=sys.stderr)
        sys.exit(1)

    available = {
        "faithfulness": Faithfulness,
        "answer_relevancy": AnswerRelevancy,
    }
    metrics = []
    for name in metric_names:
        cls = available.get(name)
        if cls is None:
            print(f"Unknown metric '{name}'. Choose from: {list(available)}", file=sys.stderr)
            sys.exit(1)
        metrics.append(cls(llm=llm))
    return metrics


async def _run_ragas(
    samples: list[EvalSample],
    metric_names: list[str],
    llm: Any,
) -> dict[str, Any]:
    try:
        from ragas import evaluate, EvaluationDataset, SingleTurnSample
    except ImportError as exc:
        print(f"ragas import error: {exc}", file=sys.stderr)
        sys.exit(1)

    metrics = _build_metric_list(metric_names, llm)

    ragas_samples = [
        SingleTurnSample(
            user_input=s.user_input,
            response=s.response,
            retrieved_contexts=s.retrieved_contexts,
        )
        for s in samples
    ]
    dataset = EvaluationDataset(samples=ragas_samples)
    result = await evaluate(dataset=dataset, metrics=metrics)
    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_report(
    query_reports: list[dict[str, Any]],
    overall: dict[str, float],
) -> None:
    sep = "─" * 64
    print(f"\n{sep}")
    print("RAGAS Evaluation Report")
    print(sep)

    for qr in query_reports:
        print(f"\nQuery: {qr['query_id']}  —  \"{qr['question']}\"")
        print(f"  files evaluated : {qr['n_files']}")
        print(f"  samples built   : {qr['n_samples']}")
        if qr.get("scores"):
            for metric, score in qr["scores"].items():
                print(f"  {metric:<20}: {score:.4f}")
        elif qr.get("skipped"):
            print(f"  (skipped — {qr['skipped']})")

    print(f"\n{sep}")
    print("Overall averages:")
    for metric, score in overall.items():
        print(f"  {metric:<20}: {score:.4f}")
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _main(args: Any) -> None:
    settings = Settings()

    if not settings.agent_api_key:
        print("Error: LLM_API_KEY (or AGENT_API_KEY) is not set.", file=sys.stderr)
        sys.exit(2)

    metric_names = [m.strip() for m in args.metrics.split(",")]
    queries_path = Path(args.queries)
    all_queries = _load_queries(queries_path)

    if args.query_ids:
        filter_ids = set(args.query_ids)
        all_queries = [q for q in all_queries if q.id in filter_ids]
        if not all_queries:
            print(f"No queries matched ids: {filter_ids}", file=sys.stderr)
            sys.exit(1)

    print(f"Loaded {len(all_queries)} query definition(s) from {queries_path}")

    client = Neo4jClient(settings)
    llm = None if args.dry_run else _make_ragas_llm(settings)

    all_samples: list[EvalSample] = []
    query_reports: list[dict[str, Any]] = []

    try:
        for qdef in all_queries:
            print(f"  [{qdef.id}] retrieving…", end=" ", flush=True)
            samples = await _build_samples(
                client, qdef, args.files_per_query, args.chunks_per_file
            )
            print(f"{len(samples)} sample(s)")

            report: dict[str, Any] = {
                "query_id": qdef.id,
                "question": qdef.question,
                "n_files": args.files_per_query,
                "n_samples": len(samples),
            }

            if not samples:
                report["skipped"] = "no chunks with descriptions found"
            else:
                all_samples.extend(samples)

            query_reports.append(report)
    finally:
        await client.close()

    if args.dry_run:
        print(f"\nDry run — {len(all_samples)} sample(s) built, RAGAS not called.")
        for s in all_samples:
            print(f"  {s.query_id}  {s.rel_path}")
            print(f"    contexts: {len(s.retrieved_contexts)}  "
                  f"response chars: {len(s.response)}")
        return

    if not all_samples:
        print("No samples to evaluate. Run more indexing before evaluating.", file=sys.stderr)
        sys.exit(1)

    print(f"\nRunning RAGAS on {len(all_samples)} sample(s) "
          f"with metrics: {metric_names}…")
    ragas_result = await _run_ragas(all_samples, metric_names, llm)

    # Attach per-query scores by slicing the result DataFrame.
    scores_df = ragas_result.to_pandas()
    sample_idx = 0
    for qr in query_reports:
        n = qr["n_samples"]
        if n == 0:
            continue
        slice_df = scores_df.iloc[sample_idx : sample_idx + n]
        qr["scores"] = {col: float(slice_df[col].mean()) for col in metric_names
                        if col in slice_df.columns}
        sample_idx += n

    overall: dict[str, float] = {
        col: float(scores_df[col].mean()) for col in metric_names
        if col in scores_df.columns
    }

    _print_report(query_reports, overall)

    # Optionally write JSON.
    if args.output:
        out_path = Path(args.output)
        payload = {
            "queries": query_reports,
            "overall": overall,
            "n_samples": len(all_samples),
            "metrics": metric_names,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport written to {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m evaluation.ragas_eval",
        description="RAGAS faithfulness + relevancy evaluation for the graph query layer.",
    )
    parser.add_argument(
        "--queries",
        default=str(_DEFAULT_QUERIES_PATH),
        help="Path to queries YAML (default: evaluation/sample_queries.yaml)",
    )
    parser.add_argument(
        "--query-ids",
        nargs="*",
        metavar="ID",
        help="Run only these query ids (default: all)",
    )
    parser.add_argument(
        "--files-per-query",
        type=int,
        default=5,
        metavar="N",
        help="Max files to evaluate per query (default: 5)",
    )
    parser.add_argument(
        "--chunks-per-file",
        type=int,
        default=8,
        metavar="N",
        help="Max chunks to fetch per file (default: 8)",
    )
    parser.add_argument(
        "--metrics",
        default="faithfulness,answer_relevancy",
        help="Comma-separated metric names (default: faithfulness,answer_relevancy)",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write JSON report to this path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build samples and print them without calling RAGAS",
    )

    _args = parser.parse_args()
    asyncio.run(_main(_args))
