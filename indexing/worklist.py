"""WorkItem repository.

WorkItems are the explicit register of "stuff to do" in the run. There are two
kinds: chunk_extraction (one per Chunk) and file_orchestration (one per File).
Status flow: unrun -> done | failed. On a new run, all failed items are reset
to unrun (auto_retry_all policy).

A WorkItem's id is f"{kind}:{target_id}" — readable and naturally unique.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from shared.neo4j_client import Neo4jClient
from shared.utils import iso_utc, utc_now


WorkItemKind = Literal["chunk_extraction", "file_orchestration"]
WorkItemStatus = Literal["unrun", "done", "failed"]


@dataclass(frozen=True)
class WorkItemRecord:
    work_item_id: str
    kind: WorkItemKind
    target_id: str
    file_id: str
    status: WorkItemStatus


def make_work_item_id(kind: WorkItemKind, target_id: str) -> str:
    return f"{kind}:{target_id}"


class WorkList:
    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    async def seed_chunk_extraction_items(self, file_id: str) -> int:
        """Ensure a chunk_extraction WorkItem exists for every Chunk under the file.

        Returns the total number of items present after seeding (created or not).
        """
        async with self._client.session() as s:
            result = await s.run(
                "MATCH (f:File {file_id: $file_id})-[:HAS_CHUNK]->(c:Chunk) RETURN c.chunk_id AS cid",
                file_id=file_id,
            )
            chunk_ids = [r["cid"] async for r in result]

        if not chunk_ids:
            return 0

        items = [
            {"work_item_id": make_work_item_id("chunk_extraction", cid), "target_id": cid}
            for cid in chunk_ids
        ]

        async with self._client.session() as s:
            await s.run(
                """
                UNWIND $items AS item
                MERGE (w:WorkItem {work_item_id: item.work_item_id})
                ON CREATE SET
                    w.kind = 'chunk_extraction',
                    w.target_id = item.target_id,
                    w.file_id = $file_id,
                    w.status = 'unrun',
                    w.created_at = $now
                WITH w
                MATCH (c:Chunk {chunk_id: w.target_id})
                MERGE (w)-[:TARGETS]->(c)
                """,
                items=items,
                file_id=file_id,
                now=iso_utc(utc_now()),
            )
        return len(items)

    async def seed_file_orchestration_item(self, file_id: str) -> None:
        work_item_id = make_work_item_id("file_orchestration", file_id)
        async with self._client.session() as s:
            await s.run(
                """
                MERGE (w:WorkItem {work_item_id: $work_item_id})
                ON CREATE SET
                    w.kind = 'file_orchestration',
                    w.target_id = $file_id,
                    w.file_id = $file_id,
                    w.status = 'unrun',
                    w.created_at = $now
                WITH w
                MATCH (f:File {file_id: $file_id})
                MERGE (w)-[:TARGETS]->(f)
                """,
                work_item_id=work_item_id,
                file_id=file_id,
                now=iso_utc(utc_now()),
            )

    async def reset_failed_to_unrun(self) -> int:
        """Auto-retry policy: at run start, all failed WorkItems get reset."""
        async with self._client.session() as s:
            result = await s.run(
                """
                MATCH (w:WorkItem) WHERE w.status = 'failed'
                SET w.status = 'unrun',
                    w.error_class = null,
                    w.error_message = null,
                    w.assigned_at = null,
                    w.completed_at = null
                RETURN count(w) AS reset_count
                """
            )
            record = await result.single()
            return record["reset_count"] if record else 0

    async def pull_unrun_chunk_items(
        self,
        limit: int,
        dataset_id_filter: str | None = None,
        file_id_filter: str | None = None,
    ) -> list[WorkItemRecord]:
        """Pull unrun chunk_extraction work items.

        When filters are provided, only items whose ``file_id`` belongs to that
        dataset and/or exact file are returned.
        """
        async with self._client.session() as s:
            cypher = """
            MATCH (w:WorkItem)
            WHERE w.kind = 'chunk_extraction' AND w.status = 'unrun'
              AND ($file_id IS NULL OR w.file_id = $file_id)
              AND (
                  $dataset_id IS NULL OR EXISTS {
                      MATCH (:Source {source_id: $dataset_id})-[:CONTAINS]->(f:File)
                      WHERE f.file_id = w.file_id
                  }
              )
            RETURN w.work_item_id AS work_item_id,
                   w.kind AS kind,
                   w.target_id AS target_id,
                   w.file_id AS file_id,
                   w.status AS status
            ORDER BY w.file_id, w.target_id
            LIMIT $limit
            """
            params = {
                "limit": limit,
                "dataset_id": dataset_id_filter,
                "file_id": file_id_filter,
            }
            result = await s.run(cypher, **params)
            return [
                WorkItemRecord(
                    work_item_id=r["work_item_id"],
                    kind=r["kind"],
                    target_id=r["target_id"],
                    file_id=r["file_id"],
                    status=r["status"],
                )
                async for r in result
            ]

    async def pull_unrun_file_items_with_chunks_done(
        self,
        limit: int,
        dataset_id_filter: str | None = None,
        file_id_filter: str | None = None,
    ) -> list[WorkItemRecord]:
        """Pull file_orchestration items whose file has no unrun chunk_extraction items.

        Failed chunk extractions don't block the file orchestrator: the orchestrator
        works with whatever chunks succeeded. Filters can narrow by dataset
        and/or exact file.
        """
        async with self._client.session() as s:
            cypher = """
                MATCH (w:WorkItem)
                WHERE w.kind = 'file_orchestration' AND w.status = 'unrun'
                  AND ($file_id IS NULL OR w.file_id = $file_id)
                  AND (
                      $dataset_id IS NULL OR EXISTS {
                          MATCH (:Source {source_id: $dataset_id})-[:CONTAINS]->(f:File)
                          WHERE f.file_id = w.file_id
                      }
                  )
                  AND NOT EXISTS {
                      MATCH (cw:WorkItem)
                      WHERE cw.kind = 'chunk_extraction'
                        AND cw.file_id = w.target_id
                        AND cw.status = 'unrun'
                  }
                RETURN w.work_item_id AS work_item_id,
                       w.kind AS kind,
                       w.target_id AS target_id,
                       w.file_id AS file_id,
                       w.status AS status
                ORDER BY w.file_id
                LIMIT $limit
            """
            params = {
                "limit": limit,
                "dataset_id": dataset_id_filter,
                "file_id": file_id_filter,
            }
            result = await s.run(cypher, **params)
            return [
                WorkItemRecord(
                    work_item_id=r["work_item_id"],
                    kind=r["kind"],
                    target_id=r["target_id"],
                    file_id=r["file_id"],
                    status=r["status"],
                )
                async for r in result
            ]

    async def mark_assigned(self, work_item_id: str) -> None:
        """Stamp assigned_at when the dispatcher picks up an item.

        Useful for debugging stuck runs (assigned but no completed_at means the
        orchestrator died mid-call). Does not change status.
        """
        async with self._client.session() as s:
            await s.run(
                "MATCH (w:WorkItem {work_item_id: $wid}) SET w.assigned_at = $now",
                wid=work_item_id,
                now=iso_utc(utc_now()),
            )

    async def mark_done(
        self,
        work_item_id: str,
        run_id: str,
        in_tokens: int,
        out_tokens: int,
        duration_ms: int,
    ) -> None:
        async with self._client.session() as s:
            await s.run(
                """
                MATCH (w:WorkItem {work_item_id: $wid})
                SET w.status = 'done',
                    w.run_id = $run_id,
                    w.completed_at = $now,
                    w.in_tokens = $in_tokens,
                    w.out_tokens = $out_tokens,
                    w.duration_ms = $duration_ms,
                    w.error_class = null,
                    w.error_message = null
                """,
                wid=work_item_id,
                run_id=run_id,
                now=iso_utc(utc_now()),
                in_tokens=in_tokens,
                out_tokens=out_tokens,
                duration_ms=duration_ms,
            )

    async def mark_failed(
        self,
        work_item_id: str,
        run_id: str,
        error_class: str,
        error_message: str,
        in_tokens: int,
        out_tokens: int,
        duration_ms: int,
    ) -> None:
        async with self._client.session() as s:
            await s.run(
                """
                MATCH (w:WorkItem {work_item_id: $wid})
                SET w.status = 'failed',
                    w.run_id = $run_id,
                    w.completed_at = $now,
                    w.in_tokens = $in_tokens,
                    w.out_tokens = $out_tokens,
                    w.duration_ms = $duration_ms,
                    w.error_class = $error_class,
                    w.error_message = $error_message
                """,
                wid=work_item_id,
                run_id=run_id,
                now=iso_utc(utc_now()),
                in_tokens=in_tokens,
                out_tokens=out_tokens,
                duration_ms=duration_ms,
                error_class=error_class,
                error_message=error_message[:5000],
            )

    async def counts_by_status(self) -> dict[str, int]:
        async with self._client.session() as s:
            result = await s.run(
                """
                MATCH (w:WorkItem)
                RETURN w.kind AS kind, w.status AS status, count(w) AS n
                """
            )
            out: dict[str, int] = {}
            async for r in result:
                out[f"{r['kind']}.{r['status']}"] = r["n"]
            return out
