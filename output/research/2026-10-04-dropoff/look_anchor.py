"""Beside each tag's closeness to the probe, its closeness to the list's nearest tags, measured
tag-to-tag on the stored vectors. Same probes and ranks as look_dropoff.py. Read-only: one graph
read, the pinned local embedder for the probes, no model call, nothing written."""
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
RETURN t.name AS name, t.emb AS vector ORDER BY name
'''
OWN = ['API rate limiting', 'customer onboarding process', 'data privacy compliance',
       'user interface redesign', 'performance bottleneck', 'quarterly revenue forecast',
       'security vulnerability fix', 'feedback from beta testers']
SHOW_TOP = 25
SHOW_AT = (30, 40, 50, 75, 100, 150, 200, 300, 500, 1000, 3000, 8000)


def unit(a):
    a = np.asarray(a, dtype=np.float64)
    return a / np.linalg.norm(a, axis=1, keepdims=True)


def spread(row):
    med = float(np.median(row))
    return med, float(1.4826 * np.median(np.abs(row - med)))


driver = _driver()
with driver.session(database=DB, default_access_mode='READ') as s:
    rows = s.execute_read(lambda tx: list(tx.run(TAGS, run=RUN)))
    products = {r['name'].casefold() for r in s.run('MATCH (p:Product) RETURN p.name AS name')}
driver.close()
names = [r['name'] for r in rows]
keep = np.array([n.casefold() not in products for n in names])
names = [n for n, k in zip(names, keep) if k]
vectors = unit(np.asarray([r['vector'] for r in rows], dtype=np.float32)[keep])

# the same four graph-tag probes as look_dropoff.py (same seed, same pool rule)
with _driver() as d2, d2.session(database=DB, default_access_mode='READ') as s:
    cnt = {r['name']: r['c'] for r in s.run(
        'MATCH (t:Tag)<-[:HAS_TAG]-(c:Chunk) RETURN t.name AS name, count(c) AS c')}
counts = np.array([cnt.get(n, 0) for n in names])
rng = np.random.default_rng(20261004)
multi = np.flatnonzero((counts >= 5) & (np.array([len(n.split()) for n in names]) >= 2))
graph_probes = [names[i] for i in rng.choice(multi, size=4, replace=False)]
probes = OWN + graph_probes
q = unit(embed._embed(probes, 'query', bar=False)[0])
cos = q @ vectors.T

print(f'{len(names)} eligible graph tags')
print('columns: rank | closeness to the probe | closeness to the nearest tag (tag-to-tag) | '
      'the same in spreads above that tag\'s own bulk | mean closeness to the 5 nearest tags')
for p, row in zip(probes, cos):
    order = np.argsort(-row)
    anchor = vectors[order[0]] @ vectors.T           # tag-to-tag, stored vectors
    a_med, a_sd = spread(anchor)
    head = vectors[order[:5]] @ vectors.T            # (5, tags)
    kind = 'graph tag' if p in graph_probes else 'own phrase'
    print(f'\n=== PROBE ({kind}): {p!r}   nearest tag: {names[order[0]]!r}   '
          f'its own tag-to-tag bulk {a_med:.3f} spread {a_sd:.3f}')
    shown = list(range(SHOW_TOP)) + [r - 1 for r in SHOW_AT if r <= len(order)]
    for rank in shown:
        i = order[rank]
        others = [h for k, h in enumerate(head[:, i]) if order[k] != i]
        print(f'{rank + 1:>5}  probe {row[i]:.3f}  anchor {anchor[i]:.3f}  '
              f'z {((anchor[i] - a_med) / a_sd):5.1f}  top5 {float(np.mean(others)):.3f}  {names[i]}')
