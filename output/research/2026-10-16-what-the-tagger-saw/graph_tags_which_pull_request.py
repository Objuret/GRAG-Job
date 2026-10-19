# The graph's own tags on each PR batch with two or more pull requests: which pull request of the
# chunk does a tag stand in, when it stands in one of them alone. Reads herb-eval-volmax and data/raw.
import json, sys, collections
sys.path[:0] = ['prod', 'test']
from graph.db import _driver
from arms.artefact_v2 import _load_verified_doc
dr = _driver()
with dr.session(database='herb-eval-volmax') as s:
    rows = s.run(
        "MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk {kind: 'pr_batch'}) OPTIONAL MATCH (c)-[:HAS_TAG]->(t:Tag) "
        "RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath, f.sha256 AS sha256, "
        "collect(DISTINCT t.name) AS tags").data()
dr.close()
cache = {}; hits = collections.Counter(); ntags = collections.Counter(); n = 0
for row in rows:
    loc = json.loads(row['locator'])
    arr = _load_verified_doc(row['relpath'], row['sha256'], cache)[loc['section']]
    recs = [json.dumps(arr[i], ensure_ascii=False).lower() for i in (loc['indices'] if 'indices' in loc else [loc['index']])]
    if len(recs) < 2:
        continue
    n += 1
    where = set()
    for t in row['tags']:
        inside = [i for i, rec in enumerate(recs) if t.lower() in rec]
        if len(inside) == 1:
            where.add('last' if inside[0] == len(recs) - 1 else 'other')
    key = ('only the last pull request' if where == {'last'} else
           'the last and others' if where == {'last', 'other'} else
           'only others' if where == {'other'} else 'no tag stands in one pull request alone')
    hits[key] += 1; ntags[key] += len(row['tags'])
print('PR batches in the graph with two or more pull requests:', n)
for k, v in hits.most_common():
    print(f'  the tags that stand in one pull request alone stand in {k}: {v} chunks, graph tags a chunk {ntags[k]/v:.1f}')
