// Native Neo4j 5.x vector indexes.
//
// Facet-aware prompt grounding. The grounding vectors are stored as :Tag
// properties (`emb_<facet>`, plus `emb_all`), one per facet, written by
// `python -m tagging embed-tags` using EMBEDDING_MODEL (default
// intfloat/e5-small-v2, 384-d, cosine). One native vector index per facet;
// the browser embeds prompt tags with the same facet text and kNN-queries the
// matching index. The vectors are a tag-vocabulary lookup only — per-occurrence
// meaning stays on the HAS_TAG edges (w_chunk, w_facet), never here.

CREATE VECTOR INDEX tag_emb_topic IF NOT EXISTS
FOR (t:Tag) ON (t.emb_topic)
OPTIONS { indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
} };

CREATE VECTOR INDEX tag_emb_entities IF NOT EXISTS
FOR (t:Tag) ON (t.emb_entities)
OPTIONS { indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
} };

CREATE VECTOR INDEX tag_emb_activity IF NOT EXISTS
FOR (t:Tag) ON (t.emb_activity)
OPTIONS { indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
} };

CREATE VECTOR INDEX tag_emb_temporal IF NOT EXISTS
FOR (t:Tag) ON (t.emb_temporal)
OPTIONS { indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
} };

CREATE VECTOR INDEX tag_emb_evidence IF NOT EXISTS
FOR (t:Tag) ON (t.emb_evidence)
OPTIONS { indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
} };

CREATE VECTOR INDEX tag_emb_all IF NOT EXISTS
FOR (t:Tag) ON (t.emb_all)
OPTIONS { indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
} };
