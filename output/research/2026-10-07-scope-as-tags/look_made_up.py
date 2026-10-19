"""A first look at "scope as extra tags" on the made-up question: the topology's names stand
beside the graph's tags, embedded the same way, and each of the question's tags is compared
with both. Nothing is written to the graph and no model is called: the question's tags come
from the saved first-call answer, the names from the graph and the corpus pointers.
Run from the repo root."""
import collections
import json
import pathlib
import sys

import numpy as np

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _query_cosines  # noqa: E402
from artefact import query_content as Q  # noqa: E402
from graph.db import _driver, _readable  # noqa: E402

cache = pathlib.Path('output/private/artefact_v4_cache')
question = json.loads(pathlib.Path('output/walkthrough/20261005T040000Z/walkthrough.json')
                      .read_text(encoding='utf-8'))['question']


def validate(raw):
    cleaned, _ = V._collapse_duplicate_tags(raw)
    return Q.parse(question, cleaned)


content, _, _ = V._ask('querytag', Q.request(question), validate, cache, True)
lists = [('content tag', t.text) for t in content.tags] + [('question tag', t.text)
                                                          for t in content.query_tags]
prepared = V.prepare_over_corpus('data/corpus')
level = prepared.layer['same_level']
eligible = prepared.layer['eligible']
dim = prepared.chunk_vectors.shape[1]
bare = V._QueryAxes(prepared.tag_vectors, np.eye(dim))

# the topology's names: products, companies, channels, employees, customers from the graph's
# nodes (through their pointers), kinds of record from the graph
pieces = collections.defaultdict(lambda: collections.Counter())
held = json.loads((cache / 'landing_names.json').read_text(encoding='utf-8'))['landings']
for row in held:
    kind = row['label'].lower() + (' (first name)' if row['kind'] == 'first' else '')
    pieces[row['name']][kind] += 1
driver = _driver()
with driver.session(database=V.DATABASE, default_access_mode='READ') as session:
    for row in session.run('MATCH (k:Kind) RETURN k.name AS name'):
        pieces[_readable(str(row['name']))]['kind of record'] += 1
driver.close()
names = sorted(pieces)
print(f'{len(names)} distinct names in the topology:',
      dict(collections.Counter(k for name in names for k in pieces[name])), flush=True)

# both sides embedded as passages, the mode of the graph's tags
matrices, _, _ = _query_cosines(content.description, names, bare, 'passage')
piece_vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
matrices, _, _ = _query_cosines(content.description, [t for _, t in lists], bare, 'passage')
tag_vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
to_pieces = tag_vectors @ piece_vectors.T
to_tags = tag_vectors @ prepared.tag_vectors.T.astype(np.float64)
graph_names = [_readable(t) for t in prepared.graph_tags]

print(f'\nthe same-thing level from the graph\'s own tags: {level:.4f}\n')
for i, (side, text) in enumerate(lists):
    order = np.argsort(-to_pieces[i])[:5]
    tags_in = np.flatnonzero(eligible)
    best_tags = tags_in[np.argsort(-to_tags[i][tags_in])[:3]]
    print(f'{side}: "{text}"')
    print('   topology:   ' + ';  '.join(
        f'{names[j]} [{", ".join(sorted(pieces[names[j]]))}] {to_pieces[i, j]:.3f}'
        for j in order))
    print('   graph tags: ' + ';  '.join(f'{graph_names[j]} {to_tags[i, j]:.3f}' for j in best_tags))
    print(f'   at or above the level: {int((to_pieces[i] >= level).sum())} names of the topology, '
          f'{int((to_tags[i][tags_in] >= level).sum())} graph tags;  largest: topology '
          f'{to_pieces[i].max():.3f}, graph tags {to_tags[i][tags_in].max():.3f}')

# how close the topology's names are to each other, by kind
print('\nnames of one kind against each other (cosine, off the diagonal):')
for kind in ('product', 'channel', 'employee', 'customer', 'company', 'kind of record'):
    rows = [j for j, name in enumerate(names) if kind in pieces[name]]
    if len(rows) < 2:
        continue
    block = piece_vectors[rows] @ piece_vectors[rows].T
    off = block[~np.eye(len(rows), dtype=bool)]
    print(f'   {kind}: {len(rows)} names, median {np.median(off):.3f}, largest {off.max():.3f}, '
          f'pairs at or above the level {int((off >= level).sum() // 2)}')
