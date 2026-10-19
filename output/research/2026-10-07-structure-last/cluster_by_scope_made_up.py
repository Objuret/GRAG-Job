"""A first look at "cluster by scope" on the made-up question: the chain ranks every chunk with
no scope step, and the chunks it would deliver are grouped by the place they hang under.

No model call (the first call's answer is read from the cache), nothing written. Run from the
repo root."""
import collections
import json
import pathlib
import sys

import numpy as np

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _query_cosines  # noqa: E402
from arms.artefact_v2 import _budget_contexts  # noqa: E402
from artefact import query_content as Q  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402

BUDGET = 72000
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
matrices, _, _ = _query_cosines(content.description, tags, bare, 'passage')
tag_vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
description = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
matrices, _, _ = _query_cosines(content.question, [], bare)
asked = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
walked = WK.chain(layer, {
    'cosines': tag_vectors @ prepared.tag_vectors.T.astype(np.float64),
    'readings': np.array([t.readings for t in query_tags], dtype=np.float64),
    'description_cosines': tag_vectors @ description,
    'd_description': description @ prepared.chunk_vectors.T,
    'd_question': asked @ prepared.chunk_vectors.T}, V.COS_NOISE)
order = walked['order']
strength = walked['strength']

# what would be delivered with no scope step at all
_, _, _, budget = _budget_contexts([prepared.chunk_rows[i] for i in order], BUDGET, {})
kept = int(budget['kept'])
top = order[:kept]
print(f'the chain alone delivers {kept} whole chunks under {BUDGET} characters; '
      f'their strengths run from {strength[top[0]]:.2f} down to {strength[top[-1]]:.2f}')

# every chunk's places, from the tree the arm builds out of the graph
places = collections.defaultdict(list)
for path, members in prepared.tree['paths'].items():
    for i in members:
        places[i].append(path)
levels = {1: 'product', 2: 'product / kind of record', 3: 'product / slack threads / channel'}
for depth, name in levels.items():
    held = collections.Counter()
    weight = collections.Counter()
    for i in top:
        for path in places[i]:
            if path.count('/') + 1 == depth:
                held[path] += 1
                weight[path] += float(strength[i])
    size = {path: len(prepared.tree['paths'][path]) for path in held}
    print(f'\nthe {kept} delivered chunks grouped by {name}:')
    for path, count in held.most_common():
        print(f'   {count:>2} chunks, summed strength {weight[path]:6.2f}, of {size[path]:>3} chunks '
              f'in that place: {path}')
    without = sum(1 for i in top if not any(p.count('/') + 1 == depth for p in places[i]))
    if without:
        print(f'   {without} delivered chunks hang under no place of this kind')

# the same grouping over each product's best chunk, down the whole ranking
best = {}
for i in order:
    product = next(p for p in places[i] if '/' not in p)
    best.setdefault(product, float(strength[i]))
ranked = sorted(best.items(), key=lambda item: -item[1])
print('\neach product\'s strongest chunk, the first eight products:')
for product, value in ranked[:8]:
    print(f'   {value:6.2f}  {product}')
values = [v for _, v in ranked]
gaps = [values[k] - values[k + 1] for k in range(len(values) - 1)]
at = int(np.argmax(gaps))
print(f'the widest gap between two neighbouring products in that list is {gaps[at]:.2f}, after '
      f'the first {at + 1}')
