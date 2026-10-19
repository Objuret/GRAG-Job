"""The chain's tag strength and text strength asked of the database (`v4_db.STRENGTHS`), against
`v4_walk.chain` on the arm's arrays, on the made-up question. Read-only, no model call: the
first call's answer is read from the cache. Run from the repo root."""
import json
import pathlib
import sys
import time

import numpy as np

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _query_cosines  # noqa: E402
from artefact import query_content as Q  # noqa: E402
from artefact import v4_db as DB  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from graph.db import _driver  # noqa: E402

cache = pathlib.Path('output/private/artefact_v4_cache')
question = json.loads(pathlib.Path('output/walkthrough/20261005T040000Z/walkthrough.json')
                      .read_text(encoding='utf-8'))['question']


def validate(raw):
    cleaned, _ = V._collapse_duplicate_tags(raw)
    return Q.parse(question, cleaned)


content, _, _ = V._ask('querytag', Q.request(question), validate, cache, True)
query_tags = (*content.tags, *content.query_tags)
tags = [t.text for t in query_tags]
prepared = V.prepare_over_corpus('data/corpus')
layer = prepared.layer
n = len(prepared.chunk_ids)
dim = prepared.chunk_vectors.shape[1]
bare = V._QueryAxes(prepared.tag_vectors, np.eye(dim))

# the vectors, made as the arm makes them: tags and description as passages, the question as a query
matrices, _, _ = _query_cosines(content.description, tags, bare, 'passage')
tag_vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
description = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
matrices, _, _ = _query_cosines(content.question, [], bare)
asked = np.asarray(matrices['query_description_cosines'], dtype=np.float64)

# the arrays
readings = np.array([t.readings for t in query_tags], dtype=np.float64)
to_description = tag_vectors @ description
walked = WK.chain(layer, {
    'cosines': tag_vectors @ prepared.tag_vectors.T.astype(np.float64),
    'readings': readings, 'description_cosines': to_description,
    'd_description': description @ prepared.chunk_vectors.T,
    'd_question': asked @ prepared.chunk_vectors.T}, V.COS_NOISE)
weights = WK.centrality(to_description)

# the database
driver = _driver()
with driver.session(database=V.DATABASE, default_access_mode='READ') as session:
    started = time.perf_counter()
    top = session.run(DB.FACET_TOPS, run=V.RUN_ID).single()
    tops = [top[f] for f in WK.RANKING_FACETS]
    print(f'the facets\' largest values, asked of the database in {time.perf_counter() - started:.1f}s:'
          f' {tops}', flush=True)
    started = time.perf_counter()
    rows = list(session.run(DB.STRENGTHS, run=V.RUN_ID, same=layer['same_level'], tops=tops,
                            description=description.tolist(), question=asked.tolist(),
                            tags=[{'at': i, 'vector': tag_vectors[i].tolist(),
                                   'weight': float(weights[i]),
                                   'order': [int(k) for k in WK.facet_order(readings[i])]}
                                  for i in range(len(tags))]))
    took = time.perf_counter() - started
driver.close()

at = {chunk: i for i, chunk in enumerate(prepared.chunk_ids)}
db_tags, db_text, db_lift = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
for row in rows:
    db_tags[at[row['chunk']]] = row['tags']
    db_text[at[row['chunk']]] = row['text']
    db_lift[at[row['chunk']]] = row['product_lift']
spreads = dict(rows[0]['spreads'])
step = walked['step']
print(f'{len(tags)} query tags; the database answered {len(rows)} chunks in {took:.1f}s '
      f'(the pool holds {n})')
print(f'chunks the database left out: {int(np.isnan(db_tags).sum())}')
for name, got, want in (('tag strength', db_tags, walked['tags']),
                        ('text strength', db_text, walked['text']),
                        ('product lift', db_lift, walked['lift']['product'])):
    apart = np.abs(got - want)
    print(f'{name}: largest {want.max():.4f}; furthest apart {apart.max():.2e}; chunks further '
          f'apart than one level step ({step:.4f}): {int((apart > step).sum())}')
apart = max(abs(spreads[i] - walked['spread'][i]) for i in range(len(tags)))
print(f'the spreads per query tag: furthest apart {apart:.2e}')
same_edges = walked['same_edge'].sum(axis=1).tolist()
print('links of same-thing tags per query tag (arrays):', same_edges)
base_db, base = db_tags + db_text, walked['tags'] + walked['text']
order_db, order = np.argsort(-base_db, kind='stable'), np.argsort(-base, kind='stable')
for k in (10, 50, 200):
    print(f'the {k} strongest chunks before the lifts: {len(set(order_db[:k]) & set(order[:k]))} '
          f'of {k} the same')
