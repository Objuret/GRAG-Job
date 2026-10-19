"""The chunks the picked tags hit, by product, on the made-up question's arrays
(`structure_last_arrays.npz`, the tree in `structure_last_arrays.json`): a graph tag is picked
for a querytag when its cosine is at or above the arm's same-thing level; a chunk is hit when
it carries a picked tag. Per querytag and for all together: how many chunks each product holds
against what its size gives. Then the same count for the first chunks on the tags' number and
on the description's number. No model call, no benchmark file. Run from the repo root."""
import json
import pathlib
import sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
HERE = pathlib.Path('output/research/2026-10-07-structure-last')
A = np.load(HERE / 'structure_last_arrays.npz')
J = json.loads((HERE / 'structure_last_arrays.json').read_text(encoding='utf-8'))
RIGHT = 'EdgeForce'
cos, edge_tag, edge_chunk = A['cosines'].astype(float), A['edge_tag'], A['edge_chunk']
n, same = A['tags'].size, J['same_level']
paths = {p: np.array(c) for p, c in J['paths'].items() if p.count('/') == 0}
names = list(paths)
size = np.array([paths[p].size for p in names], dtype=float)
right = names.index(RIGHT)


def report(label, hit):
    total = int(hit.sum())
    if not total:
        print(f'  {label}: no chunk')
        return
    got = np.array([hit[paths[p]].sum() for p in names], dtype=float)
    expect = total * size / n
    over = (got - expect) / np.sqrt(expect * (1 - size / n))
    first = ', '.join(f'{names[i]} {int(got[i])} (size gives {expect[i]:.1f})'
                      for i in np.argsort(-over)[:3])
    print(f'  {label}: {total} chunks; {RIGHT} holds {int(got[right])}, its size gives '
          f'{expect[right]:.1f}; {RIGHT} is number {int((over > over[right]).sum()) + 1} of '
          f'{len(names)} by chunks against size; first three: {first}')


print(f'the question: {J["question"]}')
print(f'the arm\'s same-thing level: {same:.4f}')
union = np.zeros(n, dtype=bool)
for i, tag in enumerate(J['query_tags']):
    picked = cos[i][edge_tag] >= same
    hit = np.zeros(n, dtype=bool)
    hit[edge_chunk[picked]] = True
    union |= hit
    print(f'querytag "{tag}": {np.unique(edge_tag[picked]).size} graph tags picked')
    report('its chunks', hit)
report('all querytags together', union)
tags, text = A['tags'].astype(float), A['text'].astype(float)
print(f'the tags\' number: hit chunks middle {np.median(tags[union]):.2f}, lowest '
      f'{tags[union].min():.2f}; the other {int((~union).sum())} chunks middle '
      f'{np.median(tags[~union]):.2f}, largest {tags[~union].max():.2f}')
for name, v in (('the tags\' number', tags), ('the description\'s number', text)):
    for top in (50, 100, 200):
        hit = np.zeros(n, dtype=bool)
        hit[np.argsort(-v, kind='stable')[:top]] = True
        report(f'the first {top} chunks on {name}', hit)
