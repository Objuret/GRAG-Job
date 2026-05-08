"""Writes FileOrchestrationOutput results back to Neo4j.

Sets the file-level description and stamps each chunk's relevance_to_file. The
relevance score feeds into the deterministic file-level rollup
(:File)-[:TAGGED]->(:Tag) (see indexing/file_rollup.py).
"""

from __future__ import annotations

from agents.schemas import FileOrchestrationOutput
from shared.neo4j_client import Neo4jClient


class FileExtractionWriter:
    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    async def write_file_orchestration(
        self,
        file_id: str,
        output: FileOrchestrationOutput,
        run_id: str,
    ) -> None:
        async with self._client.session() as session:
            await session.run(
                """
                MATCH (f:File {file_id: $fid})
                SET f.description = $description,
                    f.description_run_id = $run_id
                """,
                fid=file_id,
                description=output.description,
                run_id=run_id,
            )

            if not output.chunk_relevance:
                return

            relevance_rows = [
                {"chunk_id": cid, "score": float(score)}
                for cid, score in output.chunk_relevance.items()
            ]
            await session.run(
                """
                UNWIND $rows AS row
                MATCH (c:Chunk {chunk_id: row.chunk_id})
                SET c.relevance_to_file = row.score
                """,
                rows=relevance_rows,
            )
