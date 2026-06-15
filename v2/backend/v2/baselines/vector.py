"""v2 vector baseline — dense kNN on chunk content embeddings.

Conventional semantic RAG control: embed the question, rank chunks by cosine
similarity on `Chunk.emb_content` via Neo4j vector index `chunk_emb_content`.
No tags, no interpret, no graph combinator.

Requires a one-time index on the v2 graph, e.g.:

  CREATE VECTOR INDEX chunk_emb_content IF NOT EXISTS
  FOR (c:Chunk) ON (c.emb_content)
  OPTIONS { indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }};
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from shared.config import Settings

from .common import (
    CONTENT_VECTOR_INDEX,
    DEFAULT_EXCLUDED_SECTIONS,
    RetrievedChunk,
    exclusion_clause,
    normalize_limit,
    neo4j_session,
    row_to_chunk,
    validate_dataset,
)


@lru_cache(maxsize=1)
def _embed_model():
    settings = Settings()
    from sentence_transformers import SentenceTransformer

    return settings.embedding_model, SentenceTransformer(settings.embedding_model)


def embed_query(text: str) -> list[float]:
    model_name, model = _embed_model()
    del model_name  # reserved for future mismatch checks
    vec = model.encode(
        [f"query: {text.strip()}"],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]
    return [float(x) for x in vec]


def retrieve_baseline_vector(
    question: str,
    *,
    limit: int = 0,
    dataset_id: str | None = None,
    excluded_sections: Sequence[str] | None = None,
    database: str | None = None,
    k: int | None = None,
) -> list[RetrievedChunk]:
    """Dense vector retrieval over `chunk_emb_content` on `c.emb_content`."""
    q = (question or "").strip()
    if not q:
        return []

    cap = normalize_limit(limit)
    knn_k = cap if cap > 0 else int(k or 1000)
    excluded = tuple(dict.fromkeys(excluded_sections or DEFAULT_EXCLUDED_SECTIONS))
    exclude = exclusion_clause(excluded)
    vec = embed_query(q)

    cypher = f"""
CALL db.index.vector.queryNodes($idx, $k, $vec) YIELD node AS c, score AS sim
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND c.emb_content IS NOT NULL
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  {exclude}
RETURN c.chunk_id   AS chunkId,
       c.file_id    AS fileId,
       c.content    AS content,
       c.description AS description,
       c.relevance_to_file AS relevanceToFile,
       round(sim, 4) AS score
ORDER BY sim DESC
{"LIMIT $limit" if cap > 0 else ""}
"""
    params: dict = {
        "idx": CONTENT_VECTOR_INDEX,
        "k": knn_k,
        "vec": vec,
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
            if _missing_vector_index(msg):
                raise RuntimeError(
                    f"Vector baseline index '{CONTENT_VECTOR_INDEX}' is missing or "
                    f"chunks lack `emb_content`. Create the index after embedding "
                    f"chunk bodies for the v2 graph (see module docstring)."
                ) from err
            raise
    finally:
        session.close()
        driver.close()


def _missing_vector_index(msg: str) -> bool:
    import re

    return bool(re.search(r"no such vector schema index|chunk_emb_content|emb_content", msg, re.I))
