"""Pre-flight: scan raw datasets, upsert File nodes, chunk, update working file.

Runs before the agent dispatcher. Idempotent — re-running picks up new files
and skips Files that already have Chunks.

Filters to file_class == 'payload_data' from the raw scanner.

Per-file fault tolerance: if any step for a single file raises, we log a one-
line summary, record the failure, and continue with the next file. The
the working file is only updated after the file has been upserted and chunked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from data_access.raw.api import scan_raw_tree

from shared.config import Settings
from shared.neo4j_client import Neo4jClient
from shared.utils import iso_utc, utc_now

from .chunker import Chunker, dispatch_mode_for
from .worklist import WorkList


@dataclass
class PreflightResult:
    files_seen: int = 0
    files_new: int = 0
    files_skipped_no_chunks: int = 0
    chunks_created: int = 0
    working_items_seeded: int = 0
    failures: list[dict] = field(default_factory=list)


async def upsert_source_node(client: Neo4jClient, dataset_id: str) -> None:
    async with client.session() as s:
        await s.run(
            """
            MERGE (src:Source {source_id: $sid})
            ON CREATE SET src.dataset_id = $sid, src.created_at = $now
            """,
            sid=dataset_id,
            now=iso_utc(utc_now()),
        )


async def upsert_file_node(
    client: Neo4jClient,
    *,
    file_id: str,
    sha256: str,
    dataset_id: str,
    rel_path: str,
    file_path: str,
    format_family: str,
    size_bytes: int,
    dispatch_mode: str,
) -> bool:
    """Returns True if a new File node was created, False if it already existed."""
    async with client.session() as s:
        result = await s.run(
            """
            MERGE (f:File {file_id: $fid})
            ON CREATE SET
                f.sha256 = $sha256,
                f.dataset_id = $dataset_id,
                f.rel_path = $rel_path,
                f.file_path = $file_path,
                f.format_family = $format_family,
                f.size_bytes = $size_bytes,
                f.dispatch_mode = $dispatch_mode,
                f.created_at = $now,
                f._is_new = true
            ON MATCH SET
                f.dispatch_mode = coalesce(f.dispatch_mode, $dispatch_mode),
                f._is_new = false
            WITH f
            MATCH (src:Source {source_id: $dataset_id})
            MERGE (src)-[:CONTAINS]->(f)
            WITH f, f._is_new AS is_new
            REMOVE f._is_new
            RETURN is_new AS is_new
            """,
            fid=file_id,
            sha256=sha256,
            dataset_id=dataset_id,
            rel_path=rel_path,
            file_path=file_path,
            format_family=format_family,
            size_bytes=size_bytes,
            dispatch_mode=dispatch_mode,
            now=iso_utc(utc_now()),
        )
        record = await result.single()
        return bool(record["is_new"]) if record else False


def _record_failure(
    result: "PreflightResult",
    *,
    rel_path: str,
    dataset_id: str,
    format_family: str,
    exc: BaseException,
) -> None:
    """Append a structured failure entry and emit a single-line stdout summary."""
    error_class = type(exc).__name__
    full_message = str(exc)
    first_line = full_message.splitlines()[0] if full_message else ""
    print(f"[preflight] FAIL {rel_path}: {error_class}: {first_line}", flush=True)
    result.failures.append(
        {
            "rel_path": rel_path,
            "dataset_id": dataset_id,
            "format_family": format_family,
            "error_class": error_class,
            "error_message": full_message[:500],
        }
    )


async def run_preflight(
    settings: Settings,
    client: Neo4jClient,
    *,
    dataset_id_filter: str | None = None,
) -> PreflightResult:
    catalog = scan_raw_tree(settings.data_root)
    payload = catalog[catalog["file_class"] == "payload_data"]
    if dataset_id_filter is not None:
        payload = payload[payload["dataset_id"] == dataset_id_filter]

    chunker = Chunker(client)
    worklist = WorkList(client)
    result = PreflightResult()

    seen_datasets: set[str] = set()

    for row in payload.itertuples(index=False):
        dataset_id = row.dataset_id
        rel_path = row.rel_path
        format_family = row.format_family

        # Source upsert is cheap and shared across many files; if it fails we
        # still try to record per-file work, but that file will then almost
        # certainly fail too. Treat source upsert errors as per-file failures.
        try:
            if dataset_id not in seen_datasets:
                await upsert_source_node(client, dataset_id)
                seen_datasets.add(dataset_id)
        except Exception as exc:  # noqa: BLE001 — explicit per-file isolation
            _record_failure(
                result,
                rel_path=rel_path,
                dataset_id=dataset_id,
                format_family=format_family,
                exc=exc,
            )
            continue

        result.files_seen += 1

        try:
            file_id = row.sha256[:24]
            dispatch_mode = dispatch_mode_for(format_family)

            is_new = await upsert_file_node(
                client,
                file_id=file_id,
                sha256=row.sha256,
                dataset_id=dataset_id,
                rel_path=rel_path,
                file_path=row.file_path,
                format_family=format_family,
                size_bytes=int(row.size_bytes),
                dispatch_mode=dispatch_mode,
            )
            if is_new:
                result.files_new += 1

            n_chunks = await chunker.chunk_file(
                file_id, Path(row.file_path), format_family
            )
            result.chunks_created += n_chunks

            seeded_chunk_items = await worklist.seed_chunk_extraction_items(file_id)
            if seeded_chunk_items == 0:
                result.files_skipped_no_chunks += 1
                continue
            # file_orchestration MUST be the LAST step. If anything above raises,
            # or if the file cannot produce chunks, this file gets no
            # orchestration item this run.
            await worklist.seed_file_orchestration_item(file_id)
            result.working_items_seeded += seeded_chunk_items + 1
        except Exception as exc:  # noqa: BLE001 — explicit per-file isolation
            _record_failure(
                result,
                rel_path=rel_path,
                dataset_id=dataset_id,
                format_family=format_family,
                exc=exc,
            )
            continue

    return result
