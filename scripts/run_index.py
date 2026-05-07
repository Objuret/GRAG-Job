"""CLI entry point for the indexing run.

    python scripts/run_index.py [--dataset-id ID] [--chunk-limit N] [--file-limit N] [--concurrency N]

Reads `.env` for LLM/agent settings (recommended: `LLM_BASE_URL`, `LLM_MODEL`,
`LLM_API_KEY`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_CONCURRENCY`; legacy: `AGENT_*`
for the same fields) plus all `NEO4J_*` vars. Base URL and model default to
OpenAI `https://api.openai.com/v1` and `gpt-4o-mini` when unset; an API key is
still required.
The script:
  1. Validates that the API key is set.
  2. Spins up Neo4j + agent clients.
  3. Starts a Run node, dispatches the orchestrator, captures the summary.
  4. Records `ok` or `aborted` (with reason) on the Run node.
  5. Always closes the clients in `finally`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agents.client import AgentClient, AgentConfig  # noqa: E402
from indexing.breaker import BreakerTripped, CircuitBreaker  # noqa: E402
from indexing.extraction_writer import ExtractionWriter  # noqa: E402
from indexing.file_rollup import FileRollup  # noqa: E402
from indexing.file_writer import FileExtractionWriter  # noqa: E402
from indexing.orchestrator import Orchestrator  # noqa: E402
from indexing.runs import RunRepository  # noqa: E402
from indexing.worklist import WorkList  # noqa: E402
from shared.config import Settings  # noqa: E402
from shared.neo4j_client import Neo4jClient  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the indexing orchestrator.")
    parser.add_argument(
        "--dataset-id",
        type=str,
        default=None,
        help="Limit work to a single Source/dataset_id (matches Source.source_id).",
    )
    parser.add_argument(
        "--chunk-limit",
        type=int,
        default=None,
        help="Cap how many chunk_extraction WorkItems to process this run.",
    )
    parser.add_argument(
        "--file-limit",
        type=int,
        default=None,
        help="Cap how many file_orchestration WorkItems to process this run.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Override Settings.agent_max_concurrency for this run.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = Settings()
    if args.concurrency is not None:
        settings = settings.model_copy(update={"agent_max_concurrency": args.concurrency})

    if not (settings.agent_api_key and settings.agent_api_key.strip()):
        lines = [
            "FEL: API-nyckel saknas. Sätt en av följande i .env eller som miljövariabler:",
            "  • LLM_API_KEY (rekommenderat)",
            "  • AGENT_API_KEY (äldre namn, samma sak)",
            "",
            "Bas-URL och modell är valfria: om de utelämnas används standard "
            "OpenAI (https://api.openai.com/v1, LLM_BASE_URL) respektive gpt-4o-mini (LLM_MODEL). "
            "Andra OpenAI-kompatibla leverantörer: sätt LLM_BASE_URL till deras API-rot.",
            "",
            "ERROR: Missing API key. Set LLM_API_KEY or AGENT_API_KEY.",
        ]
        print("\n".join(lines), file=sys.stderr)
        sys.exit(2)

    client = Neo4jClient(settings)
    agent_client = AgentClient(
        AgentConfig(
            base_url=settings.agent_base_url,
            model=settings.agent_model,
            api_key=settings.agent_api_key,
            timeout_seconds=settings.agent_timeout_seconds,
        )
    )
    breaker = CircuitBreaker()
    worklist = WorkList(client)
    runs_repo = RunRepository(client)
    chunk_writer = ExtractionWriter(client)
    file_writer = FileExtractionWriter(client)
    rollup = FileRollup(client)

    orchestrator = Orchestrator(
        settings,
        client,
        agent_client,
        breaker,
        worklist,
        runs_repo,
        chunk_writer,
        file_writer,
        rollup,
    )

    run_id = await runs_repo.start_run(settings)
    print(f"Run started: {run_id}")

    abort_reason: str | None = None
    final_status: str = "ok"
    try:
        await orchestrator.run(
            run_id,
            dataset_id=args.dataset_id,
            chunk_limit=args.chunk_limit,
            file_limit=args.file_limit,
        )
    except BreakerTripped as exc:
        final_status = "aborted"
        abort_reason = str(exc)
        print(f"BREAKER TRIPPED: {abort_reason}", file=sys.stderr)
    finally:
        summary = orchestrator.summary
        try:
            await runs_repo.finish_run(run_id, final_status, summary, abort_reason=abort_reason)
        finally:
            await client.close()
            await agent_client.aclose()

    print(f"Run finished: {final_status}")
    print(
        f"  chunks_done={summary.chunks_done}, chunks_failed={summary.chunks_failed}"
    )
    print(
        f"  files_done={summary.files_done}, files_failed={summary.files_failed}"
    )
    print(
        f"  tokens in/out = {summary.total_in_tokens}/{summary.total_out_tokens}, "
        f"duration_ms = {summary.total_duration_ms}"
    )

    if final_status == "aborted":
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
