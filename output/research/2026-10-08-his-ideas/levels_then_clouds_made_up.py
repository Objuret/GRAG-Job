"""His idea end to end on the made-up question's raw values (`structure_last_arrays.npz` of
2026-10-07), with the arm's own functions (`v4_walk.level_places`, `level_clouds`): the
clustering decides what is hit (the levels at the knees), a level is a 0-1 relevancy, each
chunk's own scope gathers its cloud, the largest clouds are kept with the minorities of the
same parent, the others are cut. Per place: the levels, the hit chunks, the clouds, the largest
clouds, the minorities, the chunks kept. No model call, no benchmark file. Run from the repo
root."""
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, 'test')
sys.stdout.reconfigure(encoding='utf-8')
from artefact import v4_walk as WK  # noqa: E402

SOURCE = pathlib.Path('output/research/2026-10-07-structure-last')
A = np.load(SOURCE / 'structure_last_arrays.npz')
J = json.loads((SOURCE / 'structure_last_arrays.json').read_text(encoding='utf-8'))
n = A['tags'].size
layer = {'eligible': A['eligible'].astype(bool), 'chunks': n, 'edge_tag': A['edge_tag'],
         'edge_chunk': A['edge_chunk']}
paths = J['paths']
inner = {p.rsplit('/', 1)[0] for p in paths if '/' in p}
leaves = [(p, np.array(sorted(paths[p]), dtype=np.int64)) for p in sorted(paths) if p not in inner]
relevancy, sizes = WK.level_places(WK.LEVEL_PLACES, A['cosines'].astype(float), layer,
                                   A['d_description'].astype(float),
                                   A['d_question'].astype(float))
print(f'the question: {J["question"]}')
print(f'{n} chunks, {len(leaves)} scopes (a chunk\'s own scope: its channel, or its kind of '
      'record under its product)')
print('\nthe levels of the tags, per querytag, sizes from the nearest:')
for tag, row in zip(J['query_tags'], sizes['tags']):
    print(f'  "{tag}": {row}')
print(f'the levels of chunk_desc: {sizes["chunk_desc"]}; of the question: {sizes["question"]}')
union = np.zeros(n, dtype=bool)
for place in WK.LEVEL_PLACES:
    keep, record = WK.level_clouds(relevancy[place], leaves)
    values = relevancy[place]
    print(f'\n== {place} ==')
    print(f'chunks hit (relevancy above 0): {record["hit_chunks"]} of {n}; at relevancy 1: '
          f'{int((values == 1.).sum())}; clouds: {record["clouds"]} of {len(leaves)} scopes')
    print('largest clouds (relevancy added up, chunks in the scope):')
    for c in record['largest']:
        print(f'  {c["scope"]}: {c["relevancy"]:.2f}, {c["chunks"]} chunks')
    print('minorities kept: ' + ('; '.join(f'{c["scope"]} {c["relevancy"]:.2f}'
                                           for c in record['minorities']) or 'none'))
    clouds = sorted(((float(values[m].sum()), p) for p, m in leaves if values[m].sum() > 0),
                    reverse=True)
    print('the next clouds below, cut: ' + '; '.join(
        f'{p} {size:.2f}' for size, p in clouds[len(record['largest']):len(record['largest']) + 6]
        if p not in {c['scope'] for c in record['minorities']}))
    print(f'chunks kept: {int(keep.sum())} of {n}')
    if place != 'question':
        union |= keep
print(f'\ntags and chunk_desc together: {int(union.sum())} chunks kept')
