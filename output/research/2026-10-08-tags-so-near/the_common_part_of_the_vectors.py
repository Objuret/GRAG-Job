"""Why every tag is near every other tag: how much of each vector is one direction that all of
them share. On the local embedder's saved vectors (output/embed_local/20261007_...: the graph's
tags and chunk descriptions, both embedded in the passage role). For the tags and for the chunk
descriptions: the length of the mean of the unit vectors, the cosines of random pairs as they
are, and the same cosines after the mean is taken off every vector. Then one tag against all
tags, as they are and with the mean taken off. No model call, no benchmark file. Run from the
repo root."""
import pathlib
import sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
D = pathlib.Path('output/embed_local/20261007_rev113abe4acafa_float32')
rng = np.random.default_rng(20261008)


def unit(m):
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def pairs(m, n=200000):
    a, b = rng.integers(0, m.shape[0], n), rng.integers(0, m.shape[0], n)
    keep = a != b
    return np.einsum('ij,ij->i', m[a[keep]], m[b[keep]])


def line(values):
    q = np.percentile(values, [1, 25, 50, 75, 99])
    return (f'1% {q[0]:+.3f}  25% {q[1]:+.3f}  middle {q[2]:+.3f}  75% {q[3]:+.3f}  '
            f'99% {q[4]:+.3f}')


loaded = {}
for name, file in (('tags', 'tags_passage.npz'), ('chunk descriptions', 'descriptions_passage.npz')):
    z = np.load(D / file, allow_pickle=True)
    ids, m = z['ids'], unit(z['matrix'].astype(np.float64))
    mean = m.mean(axis=0)
    centred = unit(m - mean)
    loaded[name] = (ids, m, mean, centred)
    print(f'== {name}: {m.shape[0]} vectors of {m.shape[1]} numbers ==')
    print(f'  length of the mean of the unit vectors: {np.linalg.norm(mean):.3f}  (0 if they '
          f'pointed all ways, 1 if they were all the same); its square {np.linalg.norm(mean) ** 2:.3f}')
    print(f'  cosine of each vector to that mean:      {line(m @ (mean / np.linalg.norm(mean)))}')
    print(f'  random pairs, as they are:               {line(pairs(m))}')
    print(f'  random pairs, the mean taken off:        {line(pairs(centred))}')
    s = np.linalg.svd(m - mean, compute_uv=False) ** 2
    print(f'  after the mean is off, the share of what is left in its 1, 5, 50 strongest '
          f'directions: {s[0] / s.sum():.3f}, {s[:5].sum() / s.sum():.3f}, {s[:50].sum() / s.sum():.3f}')
t_mean, d_mean = loaded['tags'][2], loaded['chunk descriptions'][2]
print(f'\ncosine between the tags\' mean and the chunk descriptions\' mean: '
      f'{t_mean @ d_mean / np.linalg.norm(t_mean) / np.linalg.norm(d_mean):.3f}')

ids, m, mean, centred = loaded['tags']
names = [str(i) for i in ids]
for probe in ('rollback procedures', 'root cause analysis', 'GDPR'):
    if probe not in names:
        print(f'\n"{probe}" is not a graph tag')
        continue
    at = names.index(probe)
    for label, matrix in (('as they are', m), ('the mean taken off', centred)):
        row = matrix @ matrix[at]
        row[at] = -np.inf
        order = np.argsort(-row)
        finite = row[np.isfinite(row)]
        print(f'\n"{probe}" against all other tags, {label}: middle {np.median(finite):+.3f}, '
              f'nearest {row[order[0]]:+.3f}')
        print('  nearest 12: ' + ', '.join(f'{names[i]} {row[i]:+.3f}' for i in order[:12]))
        mid = order[len(order) // 2 - 2:len(order) // 2 + 2]
        print('  at the middle: ' + ', '.join(f'{names[i]} {row[i]:+.3f}' for i in mid))
