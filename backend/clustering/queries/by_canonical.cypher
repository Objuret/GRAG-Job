// Files ranked by weight_global for a given cluster + canonical_id.
//
// Use this for single-dimension queries such as "by_theme" and "by_information_need".
// Multiple raw Tag nodes can map to the same canonical_id for the same file;
// their weight_global scores are summed so files with stronger or repeated signal
// for the canonical rank higher.
//
// Parameters:
//   $cluster      – one of: theme, object_entity, event_process,
//                           time_relevance, information_need
//   $canonical_id – canonical label string, e.g. 'advertising'
//   $limit        – max rows to return

MATCH (f:File)-[r:TAGGED]->(t:Tag)
WHERE r.cluster = $cluster
  AND r.canonical_id = $canonical_id
WITH f,
     sum(r.weight_global)  AS score,
     sum(r.n_chunks)       AS n_chunks,
     collect({
       tag_name:     t.name,
       cluster:      r.cluster,
       canonical_id: r.canonical_id,
       weight_global: r.weight_global
     }) AS matched_tags
RETURN f.file_id      AS file_id,
       f.dataset_id   AS dataset_id,
       f.rel_path     AS rel_path,
       f.description  AS description,
       score,
       n_chunks,
       matched_tags
ORDER BY score DESC
LIMIT $limit
