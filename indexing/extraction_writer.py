"""Writes ChunkExtraction results back to Neo4j.

Idempotent: re-extracting a chunk wipes its previous HAS_TAG edges (under any
prior run_id) before writing the fresh set. Tag nodes are NEVER deleted, only
edges. Proposals accumulate across runs (observed_count increments).

The writer never validates that an agent-supplied `canonical` exists as a
CanonicalTag node. That belongs in a future cleanup query.
"""

from __future__ import annotations

from agents.schemas import ChunkExtraction
from shared.neo4j_client import Neo4jClient
from shared.utils import iso_utc, stable_short_hash, utc_now


class ExtractionWriter:
    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    async def write_chunk_extraction(
        self,
        chunk_id: str,
        extraction: ChunkExtraction,
        run_id: str,
    ) -> None:
        if extraction.empty:
            await self._write_empty(chunk_id, extraction.empty_reason or "")
            return
        await self._write_non_empty(chunk_id, extraction, run_id)

    async def _write_empty(self, chunk_id: str, reason: str) -> None:
        async with self._client.session() as session:
            await session.run(
                """
                MATCH (c:Chunk {chunk_id: $cid})
                SET c.empty = true,
                    c.empty_reason = $reason,
                    c.description = null
                """,
                cid=chunk_id,
                reason=reason,
            )
            await session.run(
                """
                MATCH (c:Chunk {chunk_id: $cid})-[r:HAS_TAG]->()
                DELETE r
                """,
                cid=chunk_id,
            )

    async def _write_non_empty(
        self,
        chunk_id: str,
        extraction: ChunkExtraction,
        run_id: str,
    ) -> None:
        tag_payloads = [
            {
                "name": t.name,
                "cluster": t.cluster,
                "canonical_id": None if t.propose else t.canonical,
                "weight_local": float(t.weight_local),
                "propose": bool(t.propose),
                "proposal_id": (
                    stable_short_hash(f"{t.cluster}:{t.name}", 24) if t.propose else None
                ),
                "gloss": t.gloss,
                "rationale": t.rationale,
            }
            for t in extraction.tags
        ]
        now = iso_utc(utc_now())

        async with self._client.session() as session:
            # 1. Set chunk-level fields.
            await session.run(
                """
                MATCH (c:Chunk {chunk_id: $cid})
                SET c.empty = false,
                    c.empty_reason = null,
                    c.description = $description
                """,
                cid=chunk_id,
                description=extraction.description,
            )
            # 2. Wipe any prior HAS_TAG edges so re-extraction is idempotent.
            await session.run(
                """
                MATCH (c:Chunk {chunk_id: $cid})-[r:HAS_TAG]->()
                DELETE r
                """,
                cid=chunk_id,
            )
            # 3. Write fresh tags + proposals + edges in one UNWIND.
            if tag_payloads:
                await session.run(
                    """
                    MATCH (c:Chunk {chunk_id: $cid})
                    UNWIND $tags AS tag
                    MERGE (t:Tag {name: tag.name})
                    FOREACH (_ IN CASE WHEN tag.propose THEN [1] ELSE [] END |
                      MERGE (p:CanonicalTagProposal {proposal_id: tag.proposal_id})
                        ON CREATE SET p.label = tag.name,
                                      p.cluster = tag.cluster,
                                      p.gloss = tag.gloss,
                                      p.rationale = tag.rationale,
                                      p.observed_count = 1,
                                      p.first_seen = $now,
                                      p.last_seen = $now,
                                      p.run_id = $run_id
                        ON MATCH SET p.observed_count = coalesce(p.observed_count, 0) + 1,
                                     p.last_seen = $now
                      MERGE (p)-[:OBSERVED_IN]->(c)
                    )
                    CREATE (c)-[:HAS_TAG {
                      cluster: tag.cluster,
                      canonical_id: tag.canonical_id,
                      weight_local: tag.weight_local,
                      run_id: $run_id
                    }]->(t)
                    """,
                    cid=chunk_id,
                    tags=tag_payloads,
                    now=now,
                    run_id=run_id,
                )
