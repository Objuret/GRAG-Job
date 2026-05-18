// Native Neo4j 5.x vector indexes.
//
// Tag.embedding: the grounding bridge between free-form prompt tags and the
// corpus tag vocabulary. Written by `python -m tagging embed-tags`
// (backend/tagging/pipeline.py:stage_embed_tags) using the model named by
// EMBEDDING_MODEL (default intfloat/e5-small-v2, 384-d, cosine). The browser
// embeds prompt tags with the SAME model and queries this index by kNN.
CREATE VECTOR INDEX tag_embedding IF NOT EXISTS
FOR (t:Tag) ON (t.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
} };
