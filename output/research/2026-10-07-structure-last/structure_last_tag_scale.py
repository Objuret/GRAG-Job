"""On which scale are the unrelated graph tags bell-shaped, with no question: the 200 random
graph tags of `structure_last_arrays.py` (same seed, same draw) stand in for a querytag, one at
a time; the other eligible tags' nearness to it is read on the cosine and on Fisher's scale
(atanh of the cosine), each as a standing (middle and 1.4826 x median absolute deviation).
Reads the graph, writes nothing but its print, no model call, no embedding. Run from the repo
root."""
import sys

import numpy as np
from scipy import stats

sys.path[:0] = ['prod', 'test']
sys.stdout.reconfigure(encoding='utf-8')
from arms import artefact_v4 as V  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402

STAND_INS = 200
SEED = 20261007

prepared = V.prepare_over_corpus('data/corpus')
eligible = prepared.layer['eligible']
same_level = prepared.layer['same_level']
tv = prepared.tag_vectors.astype(np.float64)
rng = np.random.default_rng(SEED)
pool = np.flatnonzero(eligible)
drawn = rng.choice(pool, size=STAND_INS, replace=False)


def grenander(p):
    p = np.maximum(np.asarray(p, dtype=float), 1e-300)
    ux, cnt = np.unique(p, return_counts=True)
    xs, ys = np.r_[0., ux], np.r_[0., np.cumsum(cnt) / p.size]
    if xs[-1] < 1.:
        xs, ys = np.r_[xs, 1.], np.r_[ys, 1.]
    hull = [0]
    for i in range(1, xs.size):
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            if (ys[b] - ys[a]) * (xs[i] - xs[b]) <= (ys[i] - ys[b]) * (xs[b] - xs[a]):
                hull.pop()
            else:
                break
        hull.append(i)
    hx, hy = xs[hull], ys[hull]
    slopes = np.diff(hy) / np.diff(hx)
    return slopes[np.clip(np.searchsorted(hx, p, side='left') - 1, 0, slopes.size - 1)]


def bell_gap(z):
    zs = np.sort(z)
    k = int(np.ceil(0.9 * zs.size))
    F = stats.norm.cdf(zs[:k])
    return float(np.maximum(np.abs(np.arange(1, k + 1) / zs.size - F),
                            np.abs(np.arange(k) / zs.size - F)).max())


rows = []
for t in drawn:
    keep = pool[pool != t]
    c = np.clip(tv[keep] @ tv[t], -1., 1. - 1e-12)
    z, _, _ = WK.standing(c)
    zf, _, _ = WK.standing(np.arctanh(c))
    share = np.clip(1. - 1. / grenander(stats.norm.sf(zf)), 0., 1.)
    near = share > 0.5
    rows.append((stats.skew(z), stats.skew(zf), bell_gap(z), bell_gap(zf),
                 (z > 3).sum(), (zf > 3).sum(), (z < -3).sum(), (zf < -3).sum(),
                 np.percentile(z, 99), np.percentile(zf, 99),
                 np.percentile(z, 99.9), np.percentile(zf, 99.9),
                 near.sum(), c[near].min() if near.any() else np.nan,
                 (c >= same_level).sum(), c.max()))
R = np.array(rows, dtype=float)
n = pool.size - 1


def three(x):
    a, b, c = np.nanpercentile(x, [25, 50, 75])
    return f'{b:8.3f} ({a:.3f} to {c:.3f})'


print(f'{STAND_INS} random graph tags (seed {SEED}), each against the other {n} eligible tags; '
      f'middle over the stand-ins (quarter points)')
print(f'                                        on the cosine              on Fisher\'s scale        a bell')
print(f'skew                              {three(R[:, 0])}   {three(R[:, 1])}        0')
print(f'largest gap to a bell, lower 90%  {three(R[:, 2])}   {three(R[:, 3])}')
print(f'tags beyond +3 spreads            {three(R[:, 4])}   {three(R[:, 5])}     {n * stats.norm.sf(3):.1f}')
print(f'tags beyond -3 spreads            {three(R[:, 6])}   {three(R[:, 7])}     {n * stats.norm.sf(3):.1f}')
print(f'the 99% point, in spreads         {three(R[:, 8])}   {three(R[:, 9])}     2.326')
print(f'the 99.9% point, in spreads       {three(R[:, 10])}   {three(R[:, 11])}     3.090')
print(f'two groups on Fisher\'s scale (bell at the middle, Grenander, pi0 = 1): tags with a '
      f'share above 1/2: {three(R[:, 12])}; stand-ins with none: {int((R[:, 12] == 0).sum())}; '
      f'the cosine where the share reaches 1/2: {three(R[:, 13])}, from {np.nanmin(R[:, 13]):.3f} '
      f'to {np.nanmax(R[:, 13]):.3f}')
print(f'tags at or above the arm\'s same-thing level {same_level:.4f}: {three(R[:, 14])}; the '
      f'stand-in\'s closest other tag, cosine: {three(R[:, 15])}')
print(f'rank correlation over the stand-ins: tags with a share above 1/2 against tags at or '
      f'above the same-thing level: {stats.spearmanr(R[:, 12], R[:, 14])[0]:.3f}')
