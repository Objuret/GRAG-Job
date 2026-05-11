// Multi-dimensional file scoring across arbitrary cluster + canonical_id constraints.
//
// Score = sum of max(weight_global) per matched constraint dimension.
// Files that match more dimensions rank higher (dims_matched DESC).
// Among files with the same dims_matched, higher composite score wins.
//
// Using max() per dimension prevents double-counting when multiple raw Tag
// nodes on the same file share a canonical_id within a dimension.
//
// Parameters:
//   $constraints – list of maps: [{cluster: string, canonical_id: string}, ...]
//   $limit       – max rows to return
//
// Example constraints value:
//   [{cluster: 'theme', canonical_id: 'advertising'},
//    {cluster: 'time_relevance', canonical_id: 'recent'}]

UNWIND $constraints AS con
MATCH (f:File)-[r:TAGGED]->(t:Tag)
WHERE r.cluster = con.cluster
  AND r.canonical_id = con.canonical_id
WITH f,
     con.cluster + ':' + con.canonical_id AS dim_key,
     max(r.weight_global) AS dim_score,
     collect({
       tag_name:     t.name,
       cluster:      r.cluster,
       canonical_id: r.canonical_id,
       weight_global: r.weight_global
     })[0] AS best_tag
WITH f,
     count(dim_key)    AS dims_matched,
     sum(dim_score)    AS score,
     collect(best_tag) AS matched_tags
RETURN f.file_id      AS file_id,
       f.dataset_id   AS dataset_id,
       f.rel_path     AS rel_path,
       f.description  AS description,
       score,
       dims_matched,
       matched_tags
ORDER BY dims_matched DESC, score DESC
LIMIT $limit
