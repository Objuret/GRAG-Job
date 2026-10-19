"""His idea on the made-up question's raw nearness values (`structure_last_arrays.npz` of
2026-10-07): the distances are the clusters, the curve of fit decides K. Four clusterings of one
querytag's nearness values, each on the distances themselves, side by side:

  A  least-squares clusters on the line (natural breaks) of all values; K where the curve of
     the fit (within-cluster squares against K) bends most
  B  the same on the values nearer than an ordinary tag (above the middle)
  C  the jumps: a level ends where the step to the next value is larger than every step a
     smooth run of the same values gives (the steps of the same list below the middle, where
     nothing is near, measured in the same position from the end)
  D  the knee of the sorted nearness curve above the middle (the point furthest from the
     straight line between its ends), then the same again inside what is left above the knee

Prints, per querytag, each one's levels with their sizes and the tags of the first levels by
name. Reads the tag names from the graph (read only). No model call, no benchmark file. Run
from the repo root."""
import json
import pathlib
import sys

import numpy as np

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
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
        names = np.array([r['id'] for r in session.run(NAMES, run=V.RUN_ID)], dtype=object)
finally:
    driver.close()
eligible = A['eligible'].astype(bool)
if names.size != eligible.size:
    raise RuntimeError('the graph read now is not the one the saved arrays were made from')
K_MOST = 40          # the fit curve is drawn this far; the bend is looked for inside it


BINS = 1500


def squares_by_count(x, most):
    """Least-squares clusters on the line for every number of clusters up to `most`: the
    within-cluster squares and the cuts. The sorted values are first gathered into `BINS`
    equal-width bins (each bin its count, sum and sum of squares, so nothing is lost but the
    place of a cut inside a bin); the dynamic programme then runs over the bins."""
    edges = np.linspace(x[0], x[-1], BINS + 1)
    which = np.clip(np.searchsorted(edges, x, side='right') - 1, 0, BINS - 1)
    used = np.unique(which)
    w = np.array([(which == b).sum() for b in used], dtype=np.float64)
    a = np.array([x[which == b].sum() for b in used])
    q = np.array([(x[which == b] ** 2).sum() for b in used])
    m = used.size
    c0 = np.concatenate(([0.], np.cumsum(w)))
    c1 = np.concatenate(([0.], np.cumsum(a)))
    c2 = np.concatenate(([0.], np.cumsum(q)))
    j, i = np.meshgrid(np.arange(m), np.arange(m), indexing='ij')
    inside = i >= j
    size = np.where(inside, c0[i + 1] - c0[j], 1.)
    cost = np.where(inside, np.maximum(c2[i + 1] - c2[j] - (c1[i + 1] - c1[j]) ** 2 / size, 0.),
                    np.inf)
    at = np.arange(m)
    prev = cost[0].copy()
    back, totals = [np.zeros(m, dtype=np.int64)], [float(prev[-1])]
    for count in range(2, min(most, m) + 1):
        lead = np.full(m, np.inf)
        lead[1:] = prev[:-1]
        table = lead[:, None] + cost
        start = np.argmin(table, axis=0)
        prev = table[start, at]
        back.append(start)
        totals.append(float(prev[-1]))
    return np.array(totals), back, c0


def cuts_for(back, count, n, c0):
    """The first value of each cluster, from the bins' cuts."""
    starts, end = [], len(back[0]) - 1
    for g in range(count - 1, -1, -1):
        start = int(back[g][end]) if g else 0
        starts.append(int(c0[start]))
        end = start - 1
    return starts[::-1]


def bend(curve):
    """The point of a falling curve furthest from the straight line between its ends, both
    axes run from 0 to 1 (the knee)."""
    y = np.asarray(curve, dtype=np.float64)
    if y.size < 3 or y[0] == y[-1]:
        return 0
    x = np.linspace(0., 1., y.size)
    y = (y - y[-1]) / (y[0] - y[-1])
    return int(np.argmax((1. - x) - y))


def natural(values):
    """A and B: the levels of the values, nearest first, K at the bend of the fit curve."""
    x = np.sort(values)
    most = min(K_MOST, x.size - 1)
    totals, back, c0 = squares_by_count(x, most)
    count = bend(totals) + 1
    starts = cuts_for(back, count, x.size, c0)
    sizes = np.diff(starts + [x.size])[::-1]
    return count, sizes.tolist()


def jumps(values, middle):
    """C: the levels at the top that end at a step larger than every step of the same position
    counted from the other end of the list, below the middle."""
    above = np.sort(values[values > middle])[::-1]
    below = np.sort(values[values < middle])
    steps_above = above[:-1] - above[1:]
    steps_below = below[1:] - below[:-1]
    span = min(steps_above.size, steps_below.size)
    # a smooth list's steps shrink from its end inward: compare position by position
    larger = np.flatnonzero(steps_above[:span] > np.maximum.accumulate(
        np.r_[steps_below[:span][1:], 0.][::-1])[::-1])
    return larger


def knee_levels(values, middle):
    """D: the knee of the sorted curve above the middle, then again inside what lies above the
    knee, until three values or fewer are left."""
    above = np.sort(values[values > middle])[::-1]
    sizes, end = [], above.size
    while end > 3:
        k = bend(above[:end])
        if k < 1 or k >= end - 1:
            break
        sizes.append(end - k)
        end = k
    sizes.append(end)
    return sizes[::-1]


print(f'the question: {J["question"]}')
print(f'{int(eligible.sum())} graph tags compared; the fit curve of A and B is drawn to '
      f'{K_MOST} clusters')
seen = set()
for i, tag in enumerate(J['query_tags']):
    if tag in seen:
        continue
    seen.add(tag)
    row = A['cosines'][i].astype(float)
    values = row[eligible]
    tag_names = names[eligible]
    order = np.argsort(-values)
    middle = float(np.median(values))
    print(f'\n"{tag}"  (middle {middle:.3f}, nearest {values[order[0]]:.3f})')
    print('  the nearest 24: ' + ' '.join(f'{v:.3f}' for v in values[order[:24]]))
    count, sizes = natural(values)
    print(f'  A all values: K {count}; level sizes from the nearest: {sizes[:6]}'
          + (' ...' if count > 6 else ''))
    count, sizes = natural(values[values > middle])
    print(f'  B above the middle: K {count}; level sizes from the nearest: {sizes[:6]}'
          + (' ...' if count > 6 else ''))
    ends = jumps(values, middle)
    sizes_c = np.diff(np.r_[0, ends + 1]).tolist()
    print(f'  C the jumps: {len(sizes_c)} levels above the smooth run; sizes from the nearest: '
          f'{sizes_c[:8]}' + (' ...' if len(sizes_c) > 8 else ''))
    sizes_d = knee_levels(values, middle)
    print(f'  D the knee, repeated: level sizes from the nearest: {sizes_d[:8]}')
    first = sizes_c[:3] if sizes_c else []
    at = 0
    for level, size in enumerate(first, 1):
        members = order[at:at + size]
        print(f'    C level {level}: ' + ', '.join(f'{tag_names[t]} {values[t]:.3f}'
                                                   for t in members[:12])
              + (' ...' if size > 12 else ''))
        at += size
    at = 0
    for level, size in enumerate(sizes_d[:3], 1):
        members = order[at:at + size]
        print(f'    D level {level}: ' + ', '.join(f'{tag_names[t]} {values[t]:.3f}'
                                                   for t in members[:12])
              + (' ...' if size > 12 else ''))
        at += size

print('\n== the chunk descriptions ==')
for name, key in (('chunk_desc', 'd_description'), ('question', 'd_question')):
    values = A[key].astype(float)
    order = np.argsort(-values)
    middle = float(np.median(values))
    print(f'{name}  (middle {middle:.3f}, nearest {values[order[0]]:.3f})')
    print('  the nearest 24: ' + ' '.join(f'{v:.3f}' for v in values[order[:24]]))
    count, sizes = natural(values)
    print(f'  A all values: K {count}; level sizes from the nearest: {sizes[:6]}')
    count, sizes = natural(values[values > middle])
    print(f'  B above the middle: K {count}; level sizes from the nearest: {sizes[:6]}')
    ends = jumps(values, middle)
    print(f'  C the jumps: sizes from the nearest: {np.diff(np.r_[0, ends + 1]).tolist()[:8]}')
    print(f'  D the knee, repeated: level sizes from the nearest: {knee_levels(values, middle)[:8]}')
