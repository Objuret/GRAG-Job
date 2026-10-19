"""artefact_v4's chain asked of the database: the Cypher and the parameters it takes.

A question's tags, their closeness to the graph's tags, the links to the chunks with their facet
values, and the description side are all read where they stand, per question. The arithmetic is
`v4_walk`'s; this module says it in Cypher.

The database's closeness function gives (1 + cosine) / 2; the queries turn it back.
"""
from __future__ import annotations

MAD_TO_SPREAD = 1.4826

# The pool: a tag with a vector and a link into the pool, whose name is no product's name; a
# chunk with a description vector, a link and a product.
_TAG = '''t.emb IS NOT NULL
  AND EXISTS { MATCH (t)<-[x:HAS_TAG]-(y:Chunk) WHERE x.run_id = $run AND (y)-[:product]->() }
  AND NOT EXISTS { MATCH (p:Product) WHERE toLower(p.name) = toLower(t.name) }'''
_LINK = 'r.run_id = $run AND c.desc_emb IS NOT NULL AND (c)-[:product]->()'
_CHUNK = '''c.desc_emb IS NOT NULL AND (c)-[:product]->()
  AND EXISTS { MATCH (c)-[x:HAS_TAG]->() WHERE x.run_id = $run }'''

# The largest value of each of the four ranking facets over the pool's links, in the facets'
# order: a link's class per facet counts gaps down from it.
FACET_TOPS = f'''
MATCH (t:Tag) WHERE {_TAG}
MATCH (t)<-[r:HAS_TAG]-(c:Chunk) WHERE {_LINK}
RETURN max(r.w_facets[1]) AS temporal, max(r.w_facets[2]) AS why,
       max(r.w_facets[3]) AS activity, max(r.w_facets[4]) AS concreteness
'''

# Per chunk the tag strength and the text strength of one question.
#
# $tags: per query tag `at` (its number), `vector`, `weight` (its closeness to the query
# description over the question's largest) and `order` (the four ranking facets as 0..3, the
# largest reading first). $same: the same-thing level. $tops: FACET_TOPS as a list.
# $description, $question: the two text vectors.
#
# Per query tag: the closeness of every pool tag, the middle and the spread of those, the
# closest. The links of the tags at or above $same are put in order by their facet classes in
# the query tag's order, then topic, then closeness, then (chunk id, tag), and spread evenly
# from the closest down to $same in that order; every other link keeps its tag's closeness. A
# link's fit is its standing above the middle, never below 0; a chunk keeps its best link, and
# over the query tags the largest of weight times that.
# The text strength is the larger of the description's and the question's standing over the
# chunks. The product lift goes along the chunk's product relation: the mean of tag plus text
# strength over the product's other chunks, less the mean over all chunks, never below 0.
STRENGTHS = f'''
MATCH (layer:FacetLayer {{run_id: $run}})
WITH layer.equal_gap AS gaps
UNWIND $tags AS q
CALL {{
  WITH q, gaps
  MATCH (t:Tag) WHERE {_TAG}
  WITH q, gaps, t, 2 * vector.similarity.cosine(t.emb, q.vector) - 1 AS cosine
  WITH q, gaps, collect({{tag: t, cosine: cosine}}) AS rows,
       percentileCont(cosine, 0.5) AS middle, max(cosine) AS closest
  UNWIND rows AS row
  WITH q, gaps, rows, middle, closest,
       {MAD_TO_SPREAD} * percentileCont(abs(row.cosine - middle), 0.5) AS spread
  UNWIND rows AS row
  WITH q, gaps, middle, closest, spread, row.tag AS t, row.cosine AS cosine
  MATCH (t)<-[r:HAS_TAG]-(c:Chunk) WHERE {_LINK}
  WITH q, middle, closest, spread, c, t.name AS tag, cosine, r.w_facets[0] AS topic,
       cosine >= $same AS same,
       [k IN range(0, 3) | toInteger(floor(($tops[k] - r.w_facets[k + 1]) / gaps[k]))] AS cls
  ORDER BY same DESC, cls[q.order[0]], cls[q.order[1]], cls[q.order[2]], cls[q.order[3]],
           topic DESC, cosine DESC, c.chunk_id, tag
  WITH middle, closest, spread, collect({{c: c, cosine: cosine, same: same}}) AS links
  WITH middle, closest, spread, links, size([l IN links WHERE l.same]) AS picked
  UNWIND range(0, size(links) - 1) AS place
  WITH middle, closest, spread, picked, links[place] AS link, place
  WITH middle, spread, link.c AS c,
       CASE WHEN link.same AND closest > $same
            THEN closest - ((closest - $same) * (1 + 1e-9) + 1e-12) * place / toFloat(picked)
            ELSE link.cosine END AS moved
  WITH c, spread, CASE WHEN moved > middle THEN (moved - middle) / spread ELSE 0.0 END AS fit
  RETURN c, max(fit) AS value, spread
}}
WITH collect({{c: c, tags: q.weight * value}}) AS found,
     collect(DISTINCT [q.at, spread]) AS spreads
UNWIND found AS row
WITH spreads, row.c AS c, max(row.tags) AS tags
WITH spreads, collect({{c: c, tags: tags}}) AS tag_rows
MATCH (c:Chunk) WHERE {_CHUNK}
WITH spreads, tag_rows, c,
     2 * vector.similarity.cosine(c.desc_emb, $description) - 1 AS d,
     2 * vector.similarity.cosine(c.desc_emb, $question) - 1 AS a
WITH spreads, tag_rows, collect({{c: c, d: d, a: a}}) AS texts,
     percentileCont(d, 0.5) AS d_middle, percentileCont(a, 0.5) AS a_middle
UNWIND texts AS text
WITH spreads, tag_rows, texts, d_middle, a_middle,
     {MAD_TO_SPREAD} * percentileCont(abs(text.d - d_middle), 0.5) AS d_spread,
     {MAD_TO_SPREAD} * percentileCont(abs(text.a - a_middle), 0.5) AS a_spread
UNWIND texts AS text
WITH spreads, tag_rows, text.c AS c,
     (text.d - d_middle) / d_spread AS d_standing, (text.a - a_middle) / a_spread AS a_standing
WITH spreads, tag_rows,
     collect({{c: c, text: CASE WHEN d_standing > a_standing THEN d_standing
                               ELSE a_standing END}}) AS text_rows
UNWIND tag_rows + text_rows AS row
WITH spreads, row.c AS c, sum(coalesce(row.tags, 0.0)) AS tags,
     sum(coalesce(row.text, 0.0)) AS text
WITH spreads, collect({{c: c, tags: tags, text: text, base: tags + text}}) AS rows,
     avg(tags + text) AS overall
UNWIND rows AS row
WITH spreads, overall, row, row.c AS c
MATCH (c)-[:product]->(p:Product)
WITH spreads, overall, p, collect(row) AS members, sum(row.base) AS total
UNWIND members AS row
WITH spreads, row,
     CASE WHEN size(members) > 1
          THEN (total - row.base) / (size(members) - 1) - overall ELSE 0.0 END AS above
RETURN row.c.chunk_id AS chunk, row.tags AS tags, row.text AS text,
       CASE WHEN above > 0 THEN above ELSE 0.0 END AS product_lift, spreads
'''
