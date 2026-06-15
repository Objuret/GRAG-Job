"""v2 Lucene baseline — plain full-text on raw `Chunk.content`.

Port of `frontend/src/services/retrieval.ts:retrieveBaselineContent`.
No tags, no interpret, no grounding, no hard gate. The graph is only a chunk
store; eval section exclusions still apply.
"""

from __future__ import annotations

from typing import Sequence

from .common import (
    CONTENT_FULLTEXT_INDEX,
    DEFAULT_EXCLUDED_SECTIONS,
    RetrievedChunk,
    exclusion_clause,
    normalize_limit,
    neo4j_session,
    row_to_chunk,
    sanitize_lucene,
    validate_dataset,
)


def retrieve_baseline_content(
    question: str,
    *,
    limit: int = 0,
    dataset_id: str | None = None,
    excluded_sections: Sequence[str] | None = None,
    database: str | None = None,
) -> list[RetrievedChunk]:
    """Lucene full-text retrieval over `chunk_content_ft` on `c.content` only."""
    q = sanitize_lucene(question)
    if not q:
        return []

    cap = normalize_limit(limit)
    excluded = tuple(dict.fromkeys(excluded_sections or DEFAULT_EXCLUDED_SECTIONS))
    exclude = exclusion_clause(excluded)
    cypher = f"""
CALL db.index.fulltext.queryNodes($idx, $q) YIELD node AS c, score AS lex
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  {exclude}
RETURN c.chunk_id   AS chunkId,
       c.file_id    AS fileId,
       c.content    AS content,
       c.description AS description,
       c.relevance_to_file AS relevanceToFile,
       round(lex, 4) AS score
ORDER BY lex DESC
{"LIMIT $limit" if cap > 0 else ""}
"""
    params: dict = {
        "idx": CONTENT_FULLTEXT_INDEX,
        "q": q,
        "datasetId": dataset_id,
        "excludedSections": list(excluded),
    }
    if cap > 0:
        params["limit"] = cap

    driver, session = neo4j_session(database)
    try:
        validate_dataset(session, dataset_id)
        try:
            result = session.run(cypher, **params)
            return [row_to_chunk(rec.data()) for rec in result]
        except Exception as err:
            msg = str(err)
            if re_missing_index(msg):
                raise RuntimeError(
                    f"Baseline content index '{CONTENT_FULLTEXT_INDEX}' is missing. "
                    f"Create it once: CREATE FULLTEXT INDEX {CONTENT_FULLTEXT_INDEX} "
                    f"IF NOT EXISTS FOR (c:Chunk) ON EACH [c.content]; "
                    f"then CALL db.awaitIndexes()."
                ) from err
            raise
    finally:
        session.close()
        driver.close()


def re_missing_index(msg: str) -> bool:
    import re

    return bool(re.search(r"no such (fulltext schema )?index|chunk_content_ft", msg, re.I))
