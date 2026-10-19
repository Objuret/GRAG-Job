"""Structure last, as a filter, asked of the database: the chunks the query's tags hit are
clustered by scope, and every chunk hanging outside the kept scopes is cut from the pool.

A chunk's scope is its channel, or its kind of record under its product when it has no channel.
A scope's parent is the product it hangs under. Where the truth seems to be is the scope holding
the most hit chunks, a tie keeping all the tied; a minority is kept when it has the same parent.
"""
from __future__ import annotations

TRUTH = 'where the truth seems to be'
MINORITY = 'minority kept, same parent'
CUT = 'cut'

# One row a scope that holds a hit chunk: its parent, the hit chunks it holds, its role.
CLUSTERS = '''
UNWIND $hits AS id
MATCH (c:Chunk {chunk_id: id})-[:product]->(p:Product)
MATCH (c)-[:kind]->(k:Kind)
OPTIONAL MATCH (c)-[:channel]->(ch:Channel)
WITH p, c, CASE WHEN ch IS NULL THEN k ELSE ch END AS scope
WITH p, scope, count(DISTINCT c) AS hits
WITH collect({parent: p.name, kind_of_scope: labels(scope)[0],
              scope: CASE WHEN 'Channel' IN labels(scope) THEN scope.id ELSE scope.name END,
              hits: hits}) AS clusters, max(hits) AS most
WITH clusters, most, [x IN clusters WHERE x.hits = most | x.parent] AS parents
UNWIND clusters AS x
RETURN x.parent AS parent, x.kind_of_scope AS kind_of_scope, x.scope AS scope, x.hits AS hits,
       CASE WHEN x.hits = most THEN $truth WHEN x.parent IN parents THEN $minority
            ELSE $cut END AS role
ORDER BY hits DESC, parent, scope
'''

# Every pool chunk hanging in one of the kept scopes, with the scope it hangs in.
POOL = '''
UNWIND $kept AS s
MATCH (p:Product {name: s.parent})<-[:product]-(c:Chunk)
WHERE c.desc_emb IS NOT NULL AND EXISTS { MATCH (c)-[x:HAS_TAG]->() WHERE x.run_id = $run }
  AND ((s.kind_of_scope = 'Channel'
        AND EXISTS { MATCH (c)-[:channel]->(:Channel {id: s.scope}) })
    OR (s.kind_of_scope = 'Kind' AND NOT (c)-[:channel]->()
        AND EXISTS { MATCH (c)-[:kind]->(:Kind {name: s.scope}) }))
RETURN DISTINCT c.chunk_id AS chunk, s.parent AS parent, s.kind_of_scope AS kind_of_scope,
       s.scope AS scope
'''

# Every pool chunk's scopes and parent, read once for the run's record.
SCOPES = '''
MATCH (c:Chunk)-[:product]->(p:Product)
WHERE c.desc_emb IS NOT NULL AND EXISTS { MATCH (c)-[x:HAS_TAG]->() WHERE x.run_id = $run }
MATCH (c)-[:kind]->(k:Kind)
OPTIONAL MATCH (c)-[:channel]->(ch:Channel)
WITH c, p, k, collect(ch.id) AS channels
RETURN c.chunk_id AS chunk, p.name AS parent,
       CASE WHEN size(channels) = 0 THEN ['Kind:' + k.name]
            ELSE [x IN channels | 'Channel:' + x] END AS scopes
'''


def cut(session, hits, run):
    """hits: the ids of the hit chunks. Returns the clusters (one a scope: parent, kind_of_scope,
    scope, hits, role, and for a kept scope the pool chunks it holds) and the ids of every chunk
    hanging in a kept scope; (clusters, None) when nothing was hit, and then nothing is cut."""
    hits = sorted(set(hits))
    if not hits:
        return [], None
    clusters = [dict(row) for row in session.run(CLUSTERS, hits=hits, truth=TRUTH,
                                                  minority=MINORITY, cut=CUT)]
    kept = [{'parent': c['parent'], 'kind_of_scope': c['kind_of_scope'], 'scope': c['scope']}
            for c in clusters if c['role'] != CUT]
    rows = [dict(row) for row in session.run(POOL, kept=kept, run=run)]
    held = {}
    for row in rows:
        key = (row['parent'], row['kind_of_scope'], row['scope'])
        held[key] = held.get(key, 0) + 1
    for cluster in clusters:
        key = (cluster['parent'], cluster['kind_of_scope'], cluster['scope'])
        cluster['pool_chunks_in_the_scope'] = held.get(key) if cluster['role'] != CUT else None
    return clusters, sorted({row['chunk'] for row in rows})
