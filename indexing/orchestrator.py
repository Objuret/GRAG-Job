"""Agent dispatcher.

Three stages, run in order:
  1. chunk_extraction WorkItems  -> ChunkExtraction agent calls -> ExtractionWriter.
  2. file_orchestration WorkItems -> FileOrchestrationOutput agent calls -> FileExtractionWriter.
  3. Deterministic FileRollup     -> (:File)-[:TAGGED]->(:Tag) edges.

Concurrency is bounded by an asyncio.Semaphore sized from
``Settings.agent_max_concurrency``. Every result is fed through the
``CircuitBreaker`` under an asyncio.Lock so the rolling-window logic stays
serialisable; if the breaker trips we let ``BreakerTripped`` propagate up to
the run-level caller, which records the abort in the Run node and exits.

The orchestrator only mutates rows it owns. Per-batch failures (a 500 from the
agent, a schema validation error, etc.) become ``mark_failed`` rows in the
WorkItem table and increment the failed counter on ``RunSummary``. The next
``Orchestrator.run`` call resets all ``failed`` items back to ``unrun`` via
``WorkList.reset_failed_to_unrun``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agents.client import AgentClient
from agents.schemas import ChunkExtraction, FileOrchestrationOutput
from shared.config import REPO_ROOT, Settings
from shared.neo4j_client import Neo4jClient

from .breaker import BreakerTripped, CircuitBreaker
from .extraction_writer import ExtractionWriter
from .file_rollup import FileRollup
from .file_writer import FileExtractionWriter
from .runs import RunRepository, RunSummary
from .worklist import WorkItemRecord, WorkList


CHUNK_BATCH_SIZE = 200
FILE_BATCH_SIZE = 50

# Order in which canonical clusters are listed in the chunk prompt.
CLUSTER_ORDER: tuple[str, ...] = (
    "theme",
    "object_entity",
    "event_process",
    "time_relevance",
    "information_need",
)

PREV_TAIL_CHARS = 240
FILE_INVENTORY_DESC_MAX = 400


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        client: Neo4jClient,
        agent: AgentClient,
        breaker: CircuitBreaker,
        worklist: WorkList,
        runs: RunRepository,
        chunk_writer: ExtractionWriter,
        file_writer: FileExtractionWriter,
        rollup: FileRollup,
    ) -> None:
        self._settings = settings
        self._client = client
        self._agent = agent
        self._breaker = breaker
        self._worklist = worklist
        self._runs = runs
        self._chunk_writer = chunk_writer
        self._file_writer = file_writer
        self._rollup = rollup

        self._semaphore = asyncio.Semaphore(settings.agent_max_concurrency)
        self._breaker_lock = asyncio.Lock()

        # Public so the CLI can read partial counters when the breaker trips.
        self.summary = RunSummary()

        self._chunk_prompt: str | None = None
        self._file_prompt: str | None = None
        self._canonical_block: str | None = None

    # ------------------------------------------------------------------ run

    async def run(
        self,
        run_id: str,
        *,
        dataset_id: str | None = None,
        chunk_limit: int | None = None,
        file_limit: int | None = None,
    ) -> RunSummary:
        n_reset = await self._worklist.reset_failed_to_unrun()
        if n_reset:
            print(f"[orchestrator] reset {n_reset} failed work items to unrun")
        else:
            print("[orchestrator] no failed items to reset")

        self._chunk_prompt = self._read_prompt("extract_chunk.md")
        self._file_prompt = self._read_prompt("file_descriptor.md")
        await self._load_canonical_vocab()
        print(f"[orchestrator] canonical vocab loaded; dataset_id filter = {dataset_id!r}")

        await self._run_chunk_stage(run_id, dataset_id=dataset_id, chunk_limit=chunk_limit)
        await self._run_file_stage(run_id, dataset_id=dataset_id, file_limit=file_limit)

        edges = await self._rollup.run(run_id, dataset_id=dataset_id)
        print(f"[orchestrator] rollup wrote {edges} (:File)-[:TAGGED]->(:Tag) edges")

        return self.summary

    # ---------------------------------------------------------------- prompts

    def _read_prompt(self, filename: str) -> str:
        path: Path = REPO_ROOT / "prompts" / filename
        return path.read_text(encoding="utf-8")

    async def _load_canonical_vocab(self) -> None:
        groups: dict[str, list[str]] = {}
        async with self._client.session() as session:
            result = await session.run(
                """
                MATCH (c:CanonicalTag)
                RETURN c.cluster AS cluster, c.label AS label
                ORDER BY c.cluster, c.label
                """
            )
            async for record in result:
                groups.setdefault(record["cluster"], []).append(record["label"])

        lines: list[str] = ["Canonical tags by cluster:"]
        for cluster in CLUSTER_ORDER:
            labels = groups.get(cluster, [])
            if labels:
                lines.append(f"- {cluster}: {', '.join(labels)}")
            else:
                lines.append(f"- {cluster}: (no canonicals seeded yet)")
        self._canonical_block = "\n".join(lines)

    # --------------------------------------------------------------- stage 1

    async def _run_chunk_stage(
        self,
        run_id: str,
        *,
        dataset_id: str | None,
        chunk_limit: int | None,
    ) -> None:
        processed = 0
        while True:
            if chunk_limit is not None and processed >= chunk_limit:
                break

            batch_limit = CHUNK_BATCH_SIZE
            if chunk_limit is not None:
                batch_limit = min(batch_limit, chunk_limit - processed)
            if batch_limit <= 0:
                break

            items = await self._worklist.pull_unrun_chunk_items(
                batch_limit, dataset_id_filter=dataset_id
            )
            if not items:
                break

            results = await asyncio.gather(
                *[self._process_chunk(item, run_id) for item in items],
                return_exceptions=True,
            )
            self._maybe_raise_breaker(results)
            self._log_unexpected(results, where="chunk batch")

            processed += len(items)
            print(
                f"[orchestrator] chunk stage: processed={processed} "
                f"done={self.summary.chunks_done} failed={self.summary.chunks_failed}"
            )

    async def _process_chunk(self, item: WorkItemRecord, run_id: str) -> None:
        async with self._semaphore:
            await self._worklist.mark_assigned(item.work_item_id)

            try:
                ctx = await self._load_chunk_context(item.target_id)
            except Exception as exc:  # noqa: BLE001 - explicit per-item isolation
                msg = f"context load failed: {type(exc).__name__}: {exc}"
                print(f"[orchestrator] {item.work_item_id} {msg}")
                await self._worklist.mark_failed(
                    item.work_item_id, run_id, "http_other", msg, 0, 0, 0
                )
                self.summary.chunks_failed += 1
                return

            if ctx is None:
                await self._worklist.mark_failed(
                    item.work_item_id,
                    run_id,
                    "http_other",
                    "chunk not found in graph",
                    0,
                    0,
                    0,
                )
                self.summary.chunks_failed += 1
                return

            user_text = self._render_chunk_user_message(ctx)
            assert self._chunk_prompt is not None  # set in run()

            result = await self._agent.call(
                system=self._chunk_prompt,
                user=user_text,
                schema=ChunkExtraction,
                call_id=item.work_item_id,
            )

            self.summary.total_in_tokens += result.in_tokens
            self.summary.total_out_tokens += result.out_tokens
            self.summary.total_duration_ms += result.duration_ms

            async with self._breaker_lock:
                self._breaker.observe(result.error_class)  # may raise BreakerTripped

            if result.error_class == "ok" and result.parsed is not None:
                expected_off = ctx.get("end_offset")
                if expected_off is not None and int(expected_off) != int(
                    result.parsed.chunk_end_offset
                ):
                    msg = (
                        "chunk_end_offset mismatch: "
                        f"agent={result.parsed.chunk_end_offset} graph={expected_off}"
                    )
                    await self._worklist.mark_failed(
                        item.work_item_id,
                        run_id,
                        "schema_validation",
                        msg,
                        result.in_tokens,
                        result.out_tokens,
                        result.duration_ms,
                    )
                    self.summary.chunks_failed += 1
                    return

                await self._chunk_writer.write_chunk_extraction(
                    item.target_id, result.parsed, run_id
                )
                await self._worklist.mark_done(
                    item.work_item_id,
                    run_id,
                    result.in_tokens,
                    result.out_tokens,
                    result.duration_ms,
                )
                self.summary.chunks_done += 1
            else:
                await self._worklist.mark_failed(
                    item.work_item_id,
                    run_id,
                    result.error_class,
                    result.error_message or "",
                    result.in_tokens,
                    result.out_tokens,
                    result.duration_ms,
                )
                self.summary.chunks_failed += 1

    async def _load_chunk_context(self, chunk_id: str) -> dict[str, Any] | None:
        async with self._client.session() as session:
            result = await session.run(
                """
                MATCH (c:Chunk {chunk_id: $cid})<-[:HAS_CHUNK]-(f:File)
                OPTIONAL MATCH (prev:Chunk)-[:NEXT]->(c)
                RETURN c.content AS content,
                       c.kind AS kind,
                       c.ordinal AS ordinal,
                       c.start_offset AS start_offset,
                       c.end_offset AS end_offset,
                       c.token_estimate AS token_estimate,
                       f.dataset_id AS dataset_id,
                       f.rel_path AS rel_path,
                       f.format_family AS format_family,
                       f.dispatch_mode AS dispatch_mode,
                       prev.content AS prev_content
                """,
                cid=chunk_id,
            )
            record = await result.single()
            if record is None:
                return None
            return dict(record)

    def _render_chunk_user_message(self, ctx: dict[str, Any]) -> str:
        parts: list[str] = [
            f"File: {ctx['dataset_id']}/{ctx['rel_path']}  (format={ctx['format_family']})",
            (
                f"Chunk ordinal: {ctx['ordinal']}, kind: {ctx['kind']}, "
                f"end_offset: {ctx['end_offset']}"
            ),
            "",
            self._canonical_block or "Canonical tags by cluster: (vocab not loaded)",
            "",
        ]
        if ctx.get("dispatch_mode") == "sequential" and ctx.get("prev_content"):
            tail = (ctx["prev_content"] or "")[-PREV_TAIL_CHARS:]
            parts.append(f'Previous chunk ended with: "...{tail}"')
            parts.append("")
        parts.append("Chunk content:")
        parts.append("---")
        parts.append(ctx.get("content") or "")
        parts.append("---")
        parts.append("")
        parts.append(f"Output JSON. Set chunk_end_offset = {ctx['end_offset']}.")
        return "\n".join(parts)

    # --------------------------------------------------------------- stage 2

    async def _run_file_stage(
        self,
        run_id: str,
        *,
        dataset_id: str | None,
        file_limit: int | None,
    ) -> None:
        processed = 0
        while True:
            if file_limit is not None and processed >= file_limit:
                break

            batch_limit = FILE_BATCH_SIZE
            if file_limit is not None:
                batch_limit = min(batch_limit, file_limit - processed)
            if batch_limit <= 0:
                break

            items = await self._worklist.pull_unrun_file_items_with_chunks_done(
                batch_limit, dataset_id_filter=dataset_id
            )
            if not items:
                break

            results = await asyncio.gather(
                *[self._process_file(item, run_id) for item in items],
                return_exceptions=True,
            )
            self._maybe_raise_breaker(results)
            self._log_unexpected(results, where="file batch")

            processed += len(items)
            print(
                f"[orchestrator] file stage: processed={processed} "
                f"done={self.summary.files_done} failed={self.summary.files_failed}"
            )

    async def _process_file(self, item: WorkItemRecord, run_id: str) -> None:
        async with self._semaphore:
            await self._worklist.mark_assigned(item.work_item_id)

            try:
                ctx = await self._load_file_context(item.target_id)
            except Exception as exc:  # noqa: BLE001 - explicit per-item isolation
                msg = f"context load failed: {type(exc).__name__}: {exc}"
                print(f"[orchestrator] {item.work_item_id} {msg}")
                await self._worklist.mark_failed(
                    item.work_item_id, run_id, "http_other", msg, 0, 0, 0
                )
                self.summary.files_failed += 1
                return

            if ctx is None:
                await self._worklist.mark_failed(
                    item.work_item_id,
                    run_id,
                    "http_other",
                    "file not found in graph",
                    0,
                    0,
                    0,
                )
                self.summary.files_failed += 1
                return

            if not ctx["chunks"]:
                await self._worklist.mark_failed(
                    item.work_item_id,
                    run_id,
                    "http_other",
                    "file has no non-empty chunks to orchestrate",
                    0,
                    0,
                    0,
                )
                self.summary.files_failed += 1
                return

            user_text = self._render_file_user_message(ctx)
            assert self._file_prompt is not None  # set in run()

            result = await self._agent.call(
                system=self._file_prompt,
                user=user_text,
                schema=FileOrchestrationOutput,
                call_id=item.work_item_id,
            )

            self.summary.total_in_tokens += result.in_tokens
            self.summary.total_out_tokens += result.out_tokens
            self.summary.total_duration_ms += result.duration_ms

            async with self._breaker_lock:
                self._breaker.observe(result.error_class)

            if result.error_class == "ok" and result.parsed is not None:
                expected_ids = {ch["chunk_id"] for ch in ctx["chunks"]}
                got_ids = set(result.parsed.chunk_relevance.keys())
                if expected_ids != got_ids:
                    missing = sorted(expected_ids - got_ids)
                    extra = sorted(got_ids - expected_ids)
                    msg = (
                        "chunk_relevance must cover every chunk_id exactly once; "
                        f"missing={missing} extra={extra}"
                    )
                    await self._worklist.mark_failed(
                        item.work_item_id,
                        run_id,
                        "schema_validation",
                        msg,
                        result.in_tokens,
                        result.out_tokens,
                        result.duration_ms,
                    )
                    self.summary.files_failed += 1
                    return

                await self._file_writer.write_file_orchestration(
                    item.target_id, result.parsed, run_id
                )
                await self._worklist.mark_done(
                    item.work_item_id,
                    run_id,
                    result.in_tokens,
                    result.out_tokens,
                    result.duration_ms,
                )
                self.summary.files_done += 1
            else:
                await self._worklist.mark_failed(
                    item.work_item_id,
                    run_id,
                    result.error_class,
                    result.error_message or "",
                    result.in_tokens,
                    result.out_tokens,
                    result.duration_ms,
                )
                self.summary.files_failed += 1

    async def _load_file_context(self, file_id: str) -> dict[str, Any] | None:
        async with self._client.session() as session:
            meta_result = await session.run(
                """
                MATCH (f:File {file_id: $fid})
                RETURN f.dataset_id AS dataset_id,
                       f.rel_path AS rel_path,
                       f.format_family AS format_family
                """,
                fid=file_id,
            )
            meta = await meta_result.single()
            if meta is None:
                return None

            chunks_result = await session.run(
                """
                MATCH (f:File {file_id: $fid})-[:HAS_CHUNK]->(c:Chunk)
                WHERE coalesce(c.empty, false) = false
                OPTIONAL MATCH (c)-[r:HAS_TAG]->(t:Tag)
                WITH c, r, t
                ORDER BY c.ordinal
                WITH c,
                     collect(
                       CASE WHEN t IS NULL THEN null
                            ELSE {name: t.name, cluster: r.cluster, weight_local: r.weight_local}
                       END
                     ) AS tag_rows
                RETURN c.chunk_id AS chunk_id,
                       c.ordinal AS ordinal,
                       c.kind AS kind,
                       c.description AS description,
                       [x IN tag_rows WHERE x IS NOT NULL] AS tags
                ORDER BY c.ordinal
                """,
                fid=file_id,
            )

            chunks: list[dict[str, Any]] = []
            async for record in chunks_result:
                chunks.append(
                    {
                        "chunk_id": record["chunk_id"],
                        "ordinal": record["ordinal"],
                        "kind": record["kind"],
                        "description": record["description"] or "",
                        "tags": list(record["tags"] or []),
                    }
                )

        return {
            "dataset_id": meta["dataset_id"],
            "rel_path": meta["rel_path"],
            "format_family": meta["format_family"],
            "chunks": chunks,
        }

    def _render_file_user_message(self, ctx: dict[str, Any]) -> str:
        parts: list[str] = [
            f"File: {ctx['dataset_id']}/{ctx['rel_path']}  (format={ctx['format_family']})",
            f"Chunks (non-empty): {len(ctx['chunks'])}",
            "",
            "Inventory (one line per chunk):",
        ]
        for ch in ctx["chunks"]:
            tag_str = ", ".join(
                f"{t['name']}({t['cluster']}):{float(t['weight_local']):.2f}"
                for t in (ch["tags"] or [])
            )
            desc_one = (ch["description"] or "").replace("\n", " ").strip()
            if len(desc_one) > FILE_INVENTORY_DESC_MAX:
                desc_one = desc_one[: FILE_INVENTORY_DESC_MAX - 3] + "..."
            parts.append(
                f'chunk_id={ch["chunk_id"]}, ordinal={ch["ordinal"]}, '
                f'kind={ch["kind"]}: "{desc_one}", tags=[{tag_str}]'
            )
        parts.append("")
        parts.append(
            "Output JSON: a 3-5 sentence file description plus a chunk_relevance "
            "map covering EVERY chunk_id above."
        )
        return "\n".join(parts)

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _maybe_raise_breaker(results: list[Any]) -> None:
        for r in results:
            if isinstance(r, BreakerTripped):
                raise r

    @staticmethod
    def _log_unexpected(results: list[Any], *, where: str) -> None:
        for r in results:
            if isinstance(r, BaseException) and not isinstance(r, BreakerTripped):
                print(f"[orchestrator] unexpected error in {where}: {type(r).__name__}: {r}")
