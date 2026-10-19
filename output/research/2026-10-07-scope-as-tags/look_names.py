"""Second look at "scope as extra tags": tags that carry names, the way a question's tags would
if names were allowed, against the topology's names and against the graph's tags.

The tags here are written by hand around the made-up question (one of them, "EdgeForce", is
what the model wrote for it); they are not a model's answer and not from a test question.
Beside each cosine stands whether the two texts are the same letters, so that closeness can be
told from spelling. Nothing is written to the graph, no model call. Run from the repo root."""
import collections
import json
import pathlib
import re
import sys

import numpy as np

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _query_cosines  # noqa: E402
from graph.db import _driver, _readable  # noqa: E402

TAGS = ['EdgeForce', 'Edge Force', 'Julia Martinez', 'Julia',
        'develop-juliamartinez-EdgeForce', "Julia Martinez's development channel for EdgeForce",
        'pull requests', 'rollback procedure']
DESCRIPTION = 'An explanation of why a team revised its rollback procedure for model updates.'
KINDS = ('product', 'channel', 'employee', 'employee (first name)', 'customer', 'company',
         'kind of record')

cache = pathlib.Path('output/private/artefact_v4_cache')
prepared = V.prepare_over_corpus('data/corpus')
eligible = prepared.layer['eligible']
dim = prepared.chunk_vectors.shape[1]
bare = V._QueryAxes(prepared.tag_vectors, np.eye(dim))

pieces = collections.defaultdict(collections.Counter)
for row in json.loads((cache / 'landing_names.json').read_text(encoding='utf-8'))['landings']:
    pieces[row['name']][row['label'].lower() + (' (first name)' if row['kind'] == 'first' else '')] += 1
driver = _driver()
with driver.session(database=V.DATABASE, default_access_mode='READ') as session:
    for row in session.run('MATCH (k:Kind) RETURN k.name AS name'):
        pieces[_readable(str(row['name']))]['kind of record'] += 1
driver.close()
names = sorted(pieces)
print('kinds of record in the graph:', sorted(n for n in names if 'kind of record' in pieces[n]))

matrices, _, _ = _query_cosines(DESCRIPTION, names, bare, 'passage')
piece_vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
matrices, _, _ = _query_cosines(DESCRIPTION, TAGS, bare, 'passage')
tag_vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
to_pieces = tag_vectors @ piece_vectors.T
to_tags = tag_vectors @ prepared.tag_vectors.T.astype(np.float64)
graph_names = [_readable(t) for t in prepared.graph_tags]


def letters(text):
    return re.sub(r'[^a-z0-9]', '', text.casefold())


def spelling(a, b):
    a, b = letters(a), letters(b)
    return 'same letters' if a == b else ('one inside the other' if a in b or b in a else 'different')


for i, tag in enumerate(TAGS):
    print(f'\n"{tag}"')
    for kind in KINDS:
        rows = [j for j, name in enumerate(names) if kind in pieces[name]]
        j = rows[int(np.argmax(to_pieces[i, rows]))]
        runner = sorted((to_pieces[i, k] for k in rows), reverse=True)[1]
        print(f'   closest {kind}: {names[j]}  {to_pieces[i, j]:.3f}  ({spelling(tag, names[j])}; '
              f'next of that kind {runner:.3f}; {pieces[names[j]][kind]} node(s) carry the name)')
    inside = np.flatnonzero(eligible)
    j = inside[int(np.argmax(to_tags[i][inside]))]
    print(f'   closest graph tag: {graph_names[j]}  {to_tags[i, j]:.3f}  ({spelling(tag, graph_names[j])})')
    outside = np.flatnonzero(~eligible)
    j = outside[int(np.argmax(to_tags[i][outside]))]
    print(f'   closest product-named graph tag (left out of the matching today): {graph_names[j]}  '
          f'{to_tags[i, j]:.3f}  ({spelling(tag, graph_names[j])})')

print('\nnames of one kind against each other (cosine between two different names):')
for kind in KINDS:
    rows = [j for j, name in enumerate(names) if kind in pieces[name]]
    block = piece_vectors[rows] @ piece_vectors[rows].T
    off = block[~np.eye(len(rows), dtype=bool)]
    print(f'   {kind}: {len(rows)} names, median {np.median(off):.3f}, largest {off.max():.3f}')
edges = collections.Counter(int(t) for t in prepared.layer['edge_tag'])
print('\nproduct-named graph tags:', int((~eligible).sum()), 'of', eligible.size,
      '(they have links to chunks and are left out of the matching today)')
