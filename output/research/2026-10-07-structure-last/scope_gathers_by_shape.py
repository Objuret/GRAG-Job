"""What a scope gathers under each shape of the numbers, per place (the tags' number, the
description's number), on the made-up question's arrays (`structure_last_arrays.npz`, the tree
in `structure_last_arrays.json`). The question is about EdgeForce, so the product that should
gather is known. Per shape: does what a product gathers follow its number of chunks, where
EdgeForce lands, and how far ahead of the other products it is. No model call, no benchmark
file, nothing uses the 72,000 cut. Run from the repo root."""
import json
import pathlib
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, 'test/artefact')
from v4_walk import MAD_TO_SPREAD, standing  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
HERE = pathlib.Path('output/research/2026-10-07-structure-last')
A = np.load(HERE / 'structure_last_arrays.npz')
J = json.loads((HERE / 'structure_last_arrays.json').read_text(encoding='utf-8'))
RIGHT = 'EdgeForce'
kind = A['kind']
n = kind.size
paths = {p: np.array(c, dtype=np.int64) for p, c in J['paths'].items()}
levels = {'product': [p for p in paths if p.count('/') == 0],
          'product / kind of record': [p for p in paths if p.count('/') == 1],
          'product / kind of record / channel': [p for p in paths if p.count('/') == 2]}


def share_below(v):
    return (stats.rankdata(v, method='average') - 0.5) / v.size


def own_kind(v):
    """The middle taken off and the spread divided out among the chunks of the chunk's own kind
    of record; a kind whose spread is zero keeps the pool's."""
    out, _, _ = standing(v)
    for code in np.unique(kind).tolist():
        at = kind == code
        try:
            out[at], _, _ = standing(v[at])
        except ValueError:
            pass
    return out


SHAPES = (
    ('as it is', lambda v: v),
    ('smallest to 0, largest to 1', lambda v: (v - v.min()) / (v.max() - v.min())),
    ('by order (share of chunks below)', share_below),
    ('middle off, in spreads; below 0 as 0', lambda v: np.clip(standing(v)[0], 0., None)),
    ('middle off, in spreads', lambda v: standing(v)[0]),
    ('by order, 0.5 off', lambda v: share_below(v) - 0.5),
    ('minus log of the share at least as good, 1 off', lambda v: -np.log(1. - share_below(v)) - 1.),
    ('middle off, in spreads, among its own kind of record', own_kind),
)


def ahead(values, names):
    """The right product's value less the middle of the others, in the others' spreads."""
    at = names.index(RIGHT)
    others = np.delete(values, at)
    middle = np.median(others)
    return (values[at] - middle) / (MAD_TO_SPREAD * np.median(np.abs(others - middle)))


def position(values, names):
    return int((values > values[names.index(RIGHT)]).sum()) + 1


print(f'the question: {J["question"]}')
print(f'{n} chunks, {len(levels["product"])} products; {RIGHT} has {paths[RIGHT].size} chunks')
for place, key in (('the tags\' number', 'tags'), ('the description\'s number', 'text')):
    raw = A[key].astype(float)
    print(f'\n==== {place} ====')
    for label, shape in SHAPES:
        v = shape(raw)
        names = levels['product']
        size = np.array([paths[p].size for p in names], dtype=float)
        added = np.array([v[paths[p]].sum() for p in names])
        averaged = added / size
        per_root = added / np.sqrt(size)
        first = [names[i] for i in np.argsort(-added, kind='stable')[:3]]
        print(f'\n{label}   (an ordinary chunk sits at {np.median(v):+.3f})')
        print(f'  added up per product: follows the number of chunks {stats.spearmanr(added, size)[0]:+.2f}; '
              f'{RIGHT} is number {position(added, names)} of {len(names)}, {ahead(added, names):+.1f} '
              f'spreads from the others\' middle; first three: {", ".join(first)}')
        print(f'  averaged per product: follows the number of chunks {stats.spearmanr(averaged, size)[0]:+.2f}; '
              f'{RIGHT} is number {position(averaged, names)}, {ahead(averaged, names):+.1f} spreads')
        print(f'  added up over the root of the number of chunks: follows the number of chunks '
              f'{stats.spearmanr(per_root, size)[0]:+.2f}; {RIGHT} is number '
              f'{position(per_root, names)}, {ahead(per_root, names):+.1f} spreads')
        for level in ('product / kind of record', 'product / kind of record / channel'):
            names = levels[level]
            size = np.array([paths[p].size for p in names], dtype=float)
            added = np.array([v[paths[p]].sum() for p in names])
            top = [names[i] for i in np.argsort(-added, kind='stable')[:5]]
            print(f'  {level}: added up follows the number of chunks '
                  f'{stats.spearmanr(added, size)[0]:+.2f}; of the first five, '
                  f'{sum(p.startswith(RIGHT + "/") for p in top)} are {RIGHT}\'s')
