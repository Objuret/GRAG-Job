// Files tagged as 'recent' or 'active' in the time_relevance cluster,
// ranked by their maximum time_relevance weight_global.
//
// 'recent' and 'active' are treated as equivalent for ranking purposes:
// a file that is strongly 'active' is just as temporally relevant as one
// that is strongly 'recent'.  Use the matched_tags list in results to
// distinguish which canonical(s) contributed.
//
// Parameters:
//   $limit – max rows to return

MATCH (f:File)-[r:TAGGED]->(t:Tag)
WHERE r.cluster = 'time_relevance'
  AND r.canonical_id IN ['recent', 'active']
WITH f,
     max(r.weight_global) AS score,
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
       matched_tags
ORDER BY score DESC
LIMIT $limit
