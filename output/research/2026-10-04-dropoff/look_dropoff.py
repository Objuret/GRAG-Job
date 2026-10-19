"""Read where relevance drops along a nearness list: probes are phrases of my own and graph tag
names (never benchmark questions), the list is the eligible graph tags in order of closeness.
Read-only: one graph read, the pinned local embedder, no model call, nothing written."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, 'test'))
sys.path.insert(0, os.path.join(ROOT, 'prod'))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import numpy as np
from graph.db import _driver
from harness import embed

DB = 'herb-eval-volmax'
RUN = 'pilot_full_herb'
TAGS = '''
MATCH (t:Tag) WHERE t.emb IS NOT NULL AND EXISTS {
    MATCH (t)<-[r:HAS_TAG]-(c:Chunk) WHERE r.run_id = $run AND (c)-[:product]->() }
RETURN t.name AS name, t.emb AS vector, COUNT { (t)<-[:HAS_TAG]-(:Chunk) } AS chunks
ORDER BY name
'''

OWN = ['API rate limiting', 'customer onboarding process', 'data privacy compliance',
       'user interface redesign', 'performance bottleneck', 'quarterly revenue forecast',
       'security vulnerability fix', 'feedback from beta testers']
SHOW_TOP = 25
SHOW_AT = (30, 40, 50, 75, 100, 150, 200, 300, 500, 1000, 3000, 8000)


def unit(a):
    a = np.asarray(a, dtype=np.float64)
    return a / np.linalg.norm(a, axis=1, keepdims=True)


driver = _driver()
with driver.session(database=DB, default_access_mode='READ') as s:
    rows = s.execute_read(lambda tx: list(tx.run(TAGS, run=RUN)))
    products = {r['name'].casefold() for r in s.run('MATCH (p:Product) RETURN p.name AS name')}
driver.close()
names = [r['name'] for r in rows]
keep = np.array([n.casefold() not in products for n in names])
names = [n for n, k in zip(names, keep) if k]
counts = np.array([r['chunks'] for r in rows])[keep]
vectors = unit(np.asarray([r['vector'] for r in rows], dtype=np.float32)[keep])
print(f'{len(names)} eligible graph tags')

rng = np.random.default_rng(20261004)
multi = np.flatnonzero((counts >= 5) & (np.array([len(n.split()) for n in names]) >= 2))
graph_probes = [names[i] for i in rng.choice(multi, size=4, replace=False)]
probes = OWN + graph_probes
embedded = embed._embed(probes, 'query', bar=False)[0]
q = unit(embedded)
cos = q @ vectors.T

for p, row in zip(probes, cos):
    med = float(np.median(row))
    sd = float(1.4826 * np.median(np.abs(row - med)))
    order = np.argsort(-row)
    kind = 'graph tag' if p in graph_probes else 'own phrase'
    print(f'\n=== PROBE ({kind}): {p!r}   bulk {med:.3f}  spread {sd:.3f}')
    shown = list(range(SHOW_TOP)) + [r - 1 for r in SHOW_AT if r <= len(order)]
    for rank in shown:
        i = order[rank]
        print(f'{rank + 1:>5}  cos {row[i]:.3f}  z {((row[i] - med) / sd):5.1f}  '
              f'chunks {counts[i]:>3}  {names[i]}')
