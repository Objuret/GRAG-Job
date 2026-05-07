"""Deterministic File-level rollup.

Aggregates `(:Chunk)-[:HAS_TAG]->(:Tag)` edges into `(:File)-[:TAGGED]->(:Tag)`
edges, weighted by `Chunk.relevance_to_file` (the score from the file
orchestrator) multiplied by the per-chunk `weight_local`.

Strategy: rather than MERGE on a relationship key that can contain a null
`canonical_id` (Cypher's MERGE has tricky semantics around null property
values), we DELETE all existing TAGGED edges in scope and CREATE fresh ones
from the aggregation. This is safe because TAGGED edges are pure derivatives
of HAS_TAG + relevance_to_file - we can rebuild them at any time.

NO agent calls are made here.
"""

from __future__ import annotations

from shared.neo4j_client import Neo4jClient
from shared.utils import iso_utc, utc_now


class FileRollup:
    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    async def run(self, run_id: str, *, dataset_id: str | None = None) -> int:
        """Recompute (:File)-[:TAGGED]->(:Tag) edges. Returns the number of edges created."""
        now = iso_utc(utc_now())

        async with self._client.session() as session:
            # 1. Clear existing TAGGED edges in scope so the rebuild is idempotent.
            await session.run(
                """
                MATCH (f:File)-[r:TAGGED]->(:Tag)
                WHERE $dataset_id IS NULL OR f.dataset_id = $dataset_id
                DELETE r
                """,
                dataset_id=dataset_id,
            )

            # 2. Aggregate HAS_TAG -> TAGGED. Default missing relevance to 0.5
            #    so files whose orchestrator hasn't run yet still get sensible
            #    rollups.
            result = await session.run(
                """
                MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)-[r:HAS_TAG]->(t:Tag)
                WHERE $dataset_id IS NULL OR f.dataset_id = $dataset_id
                WITH f, t, r.cluster AS cluster, r.canonical_id AS canonical_id,
                     sum(coalesce(c.relevance_to_file, 0.5) * r.weight_local) AS weighted_sum,
                     count(c) AS n_chunks
                WITH f, t, cluster, canonical_id, n_chunks,
                     weighted_sum / toFloat(n_chunks) AS weight_global
                CREATE (f)-[ft:TAGGED]->(t)
                SET ft.cluster = cluster,
                    ft.canonical_id = canonical_id,
                    ft.weight_global = weight_global,
                    ft.n_chunks = n_chunks,
                    ft.run_id = $run_id,
                    ft.updated_at = $now
                RETURN count(ft) AS edges
                """,
                dataset_id=dataset_id,
                run_id=run_id,
                now=now,
            )
            record = await result.single()
            return int(record["edges"]) if record else 0
