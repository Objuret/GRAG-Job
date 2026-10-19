"""What the database itself can do for the chain: read-only, no model call.
Run from the repo root."""
import sys
import time

import numpy as np

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from graph.db import _driver  # noqa: E402

DATABASE = 'herb-eval-volmax'
RUN = 'pilot_full_herb'
driver = _driver()


def read(query, **params):
    with driver.session(database=DATABASE, default_access_mode='READ') as session:
        started = time.perf_counter()
        rows = [dict(r) for r in session.run(query, **params)]
        return rows, time.perf_counter() - started


rows, _ = read('CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition')
print('database:', rows)
rows, _ = read('SHOW INDEXES YIELD name, type, labelsOrTypes, properties, options '
               'WHERE type = "VECTOR" RETURN name, labelsOrTypes, properties, options')
for r in rows:
    config = (r['options'] or {}).get('indexConfig') or {}
    print('vector index:', r['name'], r['labelsOrTypes'], r['properties'], config)

# what a Channel node carries
rows, _ = read('MATCH (c:Channel) RETURN keys(c) AS keys, count(*) AS n ORDER BY n DESC')
print('Channel nodes by the properties they carry:', rows)
rows, _ = read('MATCH (c:Channel) RETURN properties(c) AS p LIMIT 2')
for r in rows:
    print('  a Channel node:', {k: (str(v)[:90]) for k, v in r['p'].items()})
for label in ('Product', 'Employee', 'Kind', 'Customer'):
    rows, _ = read(f'MATCH (c:{label}) RETURN keys(c) AS keys, count(*) AS n ORDER BY n DESC LIMIT 3')
    print(f'{label} nodes by the properties they carry:', rows)

# the database's own closeness against numpy's cosine, on stored tag vectors
rows, _ = read('MATCH (t:Tag) WHERE t.emb IS NOT NULL RETURN t.name AS name, t.emb AS emb '
               'ORDER BY name LIMIT 40')
names = [r['name'] for r in rows]
vectors = np.asarray([r['emb'] for r in rows], dtype=np.float64)
print('a tag vector:', vectors.shape[1], 'numbers, length', float(np.linalg.norm(vectors[0])))
unit = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
probe = names[0]
rows, took = read('MATCH (q:Tag {name: $name}) WITH q.emb AS v MATCH (t:Tag) WHERE t.name IN $names '
                  'RETURN t.name AS name, vector.similarity.cosine(t.emb, v) AS s', name=probe,
                  names=names)
got = {r['name']: r['s'] for r in rows}
mine = unit @ unit[0]
apart_raw = max(abs(got[n] - mine[i]) for i, n in enumerate(names))
apart_half = max(abs(got[n] - (1 + mine[i]) / 2) for i, n in enumerate(names))
print(f'database closeness against cosine: max apart {apart_raw:.2e}; against (1 + cosine) / 2: '
      f'max apart {apart_half:.2e}')

# one vector against every tag, inside the database
query = ('MATCH (q:Tag {name: $name}) WITH q.emb AS v '
         'MATCH (t:Tag) WHERE t.emb IS NOT NULL '
         'WITH t, vector.similarity.cosine(t.emb, v) AS s '
         'RETURN count(t) AS tags, percentileCont(s, 0.5) AS median, max(s) AS top')
for attempt in range(3):
    rows, took = read(query, name=probe)
    print(f'one vector against every tag, in the database: {rows[0]} in {took * 1000:.0f} ms')

# from the tags to their chunks along the links, inside the database
query = ('MATCH (q:Tag {name: $name}) WITH q.emb AS v '
         'MATCH (t:Tag) WHERE t.emb IS NOT NULL '
         'WITH t, vector.similarity.cosine(t.emb, v) AS s '
         'MATCH (t)<-[r:HAS_TAG]-(c:Chunk) WHERE r.run_id = $run AND (c)-[:product]->() '
         'WITH c, max(s) AS best, count(r) AS links '
         'RETURN count(c) AS chunks, sum(links) AS links, max(best) AS top')
for attempt in range(2):
    rows, took = read(query, name=probe, run=RUN)
    print(f'every tag handed along its links to the chunks, each chunk keeping its best: '
          f'{rows[0]} in {took * 1000:.0f} ms')

# one vector against every chunk description
query = ('MATCH (q:Tag {name: $name}) WITH q.emb AS v '
         'MATCH (c:Chunk) WHERE c.desc_emb IS NOT NULL AND (c)-[:product]->() '
         'RETURN count(c) AS chunks, max(vector.similarity.cosine(c.desc_emb, v)) AS top')
rows, took = read(query, name=probe)
print(f'one vector against every chunk description: {rows[0]} in {took * 1000:.0f} ms')
driver.close()
