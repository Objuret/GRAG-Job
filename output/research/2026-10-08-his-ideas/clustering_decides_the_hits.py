"""His idea on the made-up question's raw nearness values (`structure_last_arrays.npz` of
2026-10-07): the clustering decides what is hit. For each querytag the graph tags' nearness
values are clustered on their own line by a mixture whose number of levels the fit itself
chooses; a tag's 0-1 number is how much it belongs to the nearest level. The same for the query
description and the question against the chunk descriptions. Then cluster by scope: each
place's cloud is its chunks' 0-1 relevancy added up. Prints the levels, the tags of the nearest
level by name, and the largest clouds. Reads the tag names from the graph (read only). No model
call, no benchmark file. Run from the repo root."""
import json
import pathlib
import sys
import warnings

import numpy as np
from sklearn.mixture import GaussianMixture

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')
from arms import artefact_v4 as V  # noqa: E402
from graph.db import _driver  # noqa: E402

SOURCE = pathlib.Path('output/research/2026-10-07-structure-last')
A = np.load(SOURCE / 'structure_last_arrays.npz')
J = json.loads((SOURCE / 'structure_last_arrays.json').read_text(encoding='utf-8'))
NAMES = ('MATCH (t:Tag) WHERE t.emb IS NOT NULL AND EXISTS { MATCH (t)<-[r:HAS_TAG]-(c:Chunk) '
         'WHERE r.run_id = $run AND (c)-[:product]->() } RETURN t.name AS id ORDER BY id')
driver = _driver()
try:
    with driver.session(database=V.DATABASE, default_access_mode='READ') as session:
        names = [r['id'] for r in session.run(NAMES, run=V.RUN_ID)]
finally:
    driver.close()
eligible = A['eligible'].astype(bool)
if len(names) != eligible.size:
    raise RuntimeError('the graph read now is not the one the saved arrays were made from')
edge_tag, edge_chunk = A['edge_tag'], A['edge_chunk']
n = A['tags'].size
paths = {p: np.array(c, dtype=np.int64) for p, c in J['paths'].items()}


def levels(values):
    """The values clustered on their line by a Gaussian mixture, the number of levels the one
    with the smallest BIC, searched upward from one until the BIC rises. Returns the number of
    levels, each level's middle, spread and share, and per value how much it belongs to the
    nearest (highest) level."""
    x = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    best = None
    for count in range(1, 30):
        start = np.quantile(x, (np.arange(count) + 0.5) / count).reshape(-1, 1)
        fit = GaussianMixture(count, means_init=start, random_state=0, max_iter=500).fit(x)
        score = fit.bic(x)
        if best is not None and score >= best[0]:
            break
        best = (score, count, fit)
    _, count, fit = best
    top = int(np.argmax(fit.means_.ravel()))
    order = np.argsort(fit.means_.ravel())
    return (count, fit.means_.ravel()[order], np.sqrt(fit.covariances_.ravel())[order],
            fit.weights_[order], fit.predict_proba(x)[:, top])


print(f'the question: {J["question"]}')
print(f'{int(eligible.sum())} graph tags compared, {edge_tag.size} links, {n} chunks\n')
print('== the tags: per querytag, the levels its own nearness values fall into ==')
tag_relevancy = np.zeros(n)
for i, tag in enumerate(J['query_tags']):
    row = A['cosines'][i].astype(float)
    count, middles, spreads, shares, belongs = levels(row[eligible])
    full = np.zeros(eligible.size)
    full[eligible] = belongs
    near = np.flatnonzero(full > 0.5)
    by = near[np.argsort(-row[near])]
    print(f'"{tag}": {count} levels; middles ' + ' '.join(f'{m:.3f}' for m in middles)
          + '; shares ' + ' '.join(f'{s:.4f}' for s in shares)
          + f'; tags mostly in the nearest level: {near.size}'
          + (f', nearness {row[by[-1]]:.3f} to {row[by[0]]:.3f}' if near.size else ''))
    print('    ' + ', '.join(f'{names[t]} {row[t]:.3f} ({full[t]:.2f})' for t in by[:14])
          + (' ...' if near.size > 14 else ''))
    lowest = np.argsort(-row * eligible)[near.size:near.size + 4]
    print('    next under it: ' + ', '.join(f'{names[t]} {row[t]:.3f} ({full[t]:.2f})'
                                            for t in lowest))
    per_chunk = np.zeros(n)
    np.maximum.at(per_chunk, edge_chunk, full[edge_tag])
    tag_relevancy = np.maximum(tag_relevancy, per_chunk)

print('\n== the chunk descriptions: the levels of the chunks\' nearness ==')
relevancy = {'tags': tag_relevancy}
for name, key in (('chunk_desc', 'd_description'), ('question', 'd_question')):
    row = A[key].astype(float)
    count, middles, spreads, shares, belongs = levels(row)
    relevancy[name] = belongs
    print(f'{name}: {count} levels; middles ' + ' '.join(f'{m:.3f}' for m in middles)
          + '; shares ' + ' '.join(f'{s:.4f}' for s in shares)
          + f'; chunks mostly in the nearest level: {int((belongs > 0.5).sum())}')

print('\n== cluster by scope: each place\'s cloud is its chunks\' 0-1 relevancy added up ==')
for name, values in relevancy.items():
    print(f'{name}: chunks with relevancy above 0.5: {int((values > 0.5).sum())}; above 0.01: '
          f'{int((values > 0.01).sum())}; all added up {values.sum():.1f}')
    for depth, label in enumerate(('product', 'kind of record', 'channel')):
        clouds = sorted(((float(values[m].sum()), p, m.size) for p, m in paths.items()
                         if p.count('/') == depth), reverse=True)
        print(f'  {label}: ' + '; '.join(f'{p} {size:.1f} of {chunks} chunks'
                                         for size, p, chunks in clouds[:5]))
