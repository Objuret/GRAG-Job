// Non-empty chunks for a file, ranked by relevance_to_file.
//
// Primary use: retrieve the context chunks for a given file after a
// file-level query (by_canonical / recent_active / multidim) to support
// downstream evaluation (e.g. RAGAS context retrieval).
//
// Chunks whose file orchestrator has not yet run have relevance_to_file = null;
// they sort after scored chunks (coalesce to 0.5 for ordering only, matching
// the rollup default) and before ordinal within that group.
//
// Parameters:
//   $file_id – target file_id
//   $limit   – max chunks to return (use a small number, e.g. 10-20, for
//              prompt-sized context windows)

MATCH (f:File {file_id: $file_id})-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
OPTIONAL MATCH (c)-[r:HAS_TAG]->(t:Tag)
WITH c,
     collect(
       CASE WHEN t IS NULL THEN null
            ELSE {
              name:         t.name,
              cluster:      r.cluster,
              canonical_id: r.canonical_id,
              weight_local: r.weight_local
            }
       END
     ) AS all_tag_rows
RETURN c.chunk_id          AS chunk_id,
       c.ordinal            AS ordinal,
       c.kind               AS kind,
       c.content            AS content,
       c.description        AS description,
       c.relevance_to_file  AS relevance_to_file,
       [x IN all_tag_rows WHERE x IS NOT NULL] AS tags
ORDER BY coalesce(c.relevance_to_file, 0.5) DESC, c.ordinal ASC
LIMIT $limit
