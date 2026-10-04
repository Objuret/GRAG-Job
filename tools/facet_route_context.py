"""Read actual sibling tags for the report/sharing diagnostic in live Volmax."""
from pathlib import Path
import json
import sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'prod'),str(ROOT/'test')]
from graph.db import _driver

base=ROOT/'output/research/2026-09-21-facet-validity'
m=json.loads((base/'corpus_tradeoff/manifest.json').read_text())
d=next(d for d in m['cases']['domains'] if d['id']=='g0')
with _driver() as driver:
    with driver.session(database='herb-eval-volmax',default_access_mode='READ') as session:
        rows=[dict(r) for r in session.run('''
            MATCH (c:Chunk)-[:HAS_TAG]->(t:Tag)
            WHERE c.chunk_id IN $ids
            RETURN c.chunk_id AS chunk,collect(t.name) AS tags
            ''',ids=d['source_chunks'])]
if {r['chunk'] for r in rows}!=set(d['source_chunks']):raise ValueError('Missing source chunks')
for r in rows:r['tags'].sort()
result={'protocol':__doc__,'database':'herb-eval-volmax','created_utc':datetime.now(timezone.utc).isoformat(),
    'source_kinds':dict(zip(d['source_chunks'],d['source_kinds'])),'rows':rows,
    'scope':'This reads adjacency only. It does not assume generated query tags or test their embedding match.'}
out=base/'route_context';out.mkdir(exist_ok=True)
(out/'report_tags.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
