"""The main session's own check on the made-up question's arrays (`structure_last_arrays.npz`,
written by `structure_last_arrays.py`): do the values slide or step, what two clusterings of the
values hand, and what each scope holds against what its size gives. Reads the value before the
product lift and the near lift (tags + text), so a scope is not gauged on its own echo.
No model call, no benchmark file, nothing uses the 72,000 cut. Run from the repo root."""
import json
import pathlib
import sys

import numpy as np
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.mixture import GaussianMixture

sys.stdout.reconfigure(encoding='utf-8')
HERE = pathlib.Path('output/research/2026-10-07-structure-last')
A = np.load(HERE / 'structure_last_arrays.npz')
J = json.loads((HERE / 'structure_last_arrays.json').read_text(encoding='utf-8'))
SHUFFLES = 1000
rng = np.random.default_rng(20261007)

tags, text = A['tags'].astype(float), A['text'].astype(float)
base = tags + text
strength = A['strength'].astype(float)
N = base.size


def spread_of(x):
    middle = float(np.median(x))
    return middle, 1.4826 * float(np.median(np.abs(x - middle)))


print(f'{N} chunks, {len(J["query_tags"])} querytags')
print('\n== the values ==')
print('                          1%     25%  middle     75%     95%     99%   99.9%     top   skew')
for name, x in (('from the tags', tags), ('from the text', text), ('tags + text', base),
                ('product lift', A['lift_product'].astype(float)),
                ('near lift', A['lift_near'].astype(float)), ('the arm\'s value', strength)):
    q = np.percentile(x, [1, 25, 50, 75, 95, 99, 99.9])
    print(f'{name:22s}' + ''.join(f'{v:8.2f}' for v in q) + f'{x.max():8.2f}{stats.skew(x):7.2f}')
print(f'chunks with a product lift above 0: {int((A["lift_product"] > 0).sum())}; '
      f'with a near lift above 0: {int((A["lift_near"] > 0).sum())}')

middle, spread = spread_of(base)
z = (base - middle) / spread
print(f'\ntags + text: middle {middle:.2f}, spread {spread:.2f} (1.4826 x median absolute deviation)')
print('spreads above the middle | chunks there | a bell-shaped bulk of this size would put there')
for k in (2, 3, 4, 5, 6):
    print(f'   beyond {k}                 {int((z > k).sum()):6d}         {N * stats.norm.sf(k):8.2f}')
alone = stats.norm.isf(1. / N)
print(f'   beyond {alone:.2f} (where a bell-shaped bulk of {N} leaves one chunk): '
      f'{int((z > alone).sum())} chunks')

top = np.sort(base)[::-1]
print('\nthe 30 largest values of tags + text, in order:')
print('  ' + ' '.join(f'{v:.2f}' for v in top[:30]))
gaps = top[:300] - top[1:301]
biggest = np.argsort(-gaps)[:5]
print(f'steps between neighbours among the 300 largest: middle step {np.median(gaps):.4f}; the '
      f'five widest: ' + ', '.join(f'{gaps[i]:.2f} after place {i + 1}' for i in sorted(biggest)))

print('\n== what a clustering of the values hands (tags + text) ==')
column = base.reshape(-1, 1)
bics = {}
for k in range(1, 7):
    bics[k] = GaussianMixture(k, n_init=5, random_state=0).fit(column)
scores = {k: m.bic(column) for k, m in bics.items()}
best_k = min(scores, key=scores.get)
print('bell-shaped groups, the number chosen by BIC: '
      + ', '.join(f'{k}: {scores[k]:.0f}' for k in scores) + f' -> {best_k} groups')
labels = bics[best_k].predict(column)
means = bics[best_k].means_.ravel()
upper = int(np.argmax(means))
line_bic = float(base[labels == upper].min())
print(f'   its top group: {int((labels == upper).sum())} chunks, from {line_bic:.2f} up')
silhouettes = {}
fits = {}
for k in range(2, 7):
    fits[k] = KMeans(k, n_init=10, random_state=0).fit(column)
    silhouettes[k] = silhouette_score(column, fits[k].labels_)
best_s = max(silhouettes, key=silhouettes.get)
print('k-means, the number chosen by the silhouette: '
      + ', '.join(f'{k}: {silhouettes[k]:.3f}' for k in silhouettes) + f' -> {best_s} groups')
centres = fits[best_s].cluster_centers_.ravel()
upper = int(np.argmax(centres))
line_km = float(base[fits[best_s].labels_ == upper].min())
print(f'   its top group: {int((fits[best_s].labels_ == upper).sum())} chunks, from {line_km:.2f} up')
line_bell = middle + alone * spread
lines = (('BIC\'s top group', line_bic), ('k-means\' top group', line_km),
         ('where a bell-shaped bulk ends', line_bell))

# the scopes, three levels of the tree
levels = {0: 'product', 1: 'product / kind of record', 2: 'channel'}
scopes = {d: [] for d in levels}
for path, members in J['paths'].items():
    scopes[path.count('/')].append((path, np.array(members, dtype=np.int64)))
order = np.argsort(-base, kind='stable')
rank = np.empty(N, dtype=np.int64)
rank[order] = np.arange(1, N + 1)
mu, sigma = float(base.mean()), float(base.std())


def depth_scan(ranks_of_members, sizes, starts):
    """Per scope: the smallest chance, over every depth, of holding at least as many of the top
    chunks as it does; the count and the depth where that is."""
    who = np.repeat(np.arange(sizes.size), sizes)
    inside = np.lexsort((ranks_of_members, who))
    r = ranks_of_members[inside]
    k = np.arange(r.size) - np.repeat(starts, sizes) + 1
    p = stats.hypergeom.sf(k - 1, N, np.repeat(sizes, sizes), r)
    low = np.minimum.reduceat(p, starts)
    at = np.array([s + int(np.argmin(p[s:s + n])) for s, n in zip(starts, sizes)])
    return low, k[at], r[at]


kept = {}
for depth, name in levels.items():
    paths = [p for p, _ in scopes[depth]]
    members = [m for _, m in scopes[depth]]
    sizes = np.array([m.size for m in members])
    starts = np.r_[0, np.cumsum(sizes)[:-1]]
    flat = np.concatenate(members)
    total = np.add.reduceat(base[flat], starts)
    mean = total / sizes
    zed = (total - sizes * mu) / (sigma * np.sqrt(sizes * (N - sizes) / (N - 1.)))
    low, count, where = depth_scan(rank[flat], sizes, starts)
    null = np.empty((SHUFFLES, sizes.size))
    for b in range(SHUFFLES):
        null[b], _, _ = depth_scan(rng.permutation(N)[flat] + 1, sizes, starts)
    own = (null <= low[None, :]).mean(axis=0)            # this scope alone against shuffles
    family = (null.min(axis=1)[:, None] <= low[None, :]).mean(axis=0)   # any scope of the level
    zm, zs = spread_of(zed)
    kept[depth] = dict(paths=paths, sizes=sizes, low=low, count=count, where=where, null=null,
                       own=own, family=family, zed=zed, total=total, mean=mean, members=members)
    print(f'\n== {name}: {sizes.size} scopes, {sizes.min()} to {sizes.max()} chunks, '
          f'middle {int(np.median(sizes))} ==')
    print(f'first by plain sum : ' + '; '.join(f'{paths[i]} ({sizes[i]} chunks)'
                                               for i in np.argsort(-total)[:3]))
    print(f'first by plain mean: ' + '; '.join(f'{paths[i]} ({sizes[i]} chunks)'
                                               for i in np.argsort(-mean)[:3]))
    print(f'sum against what its size gives, in chance spreads: across the scopes its middle is '
          f'{zm:.2f} and its spread {zs:.2f} (0 and 1 if a scope were a random handful)')
    print(f'the shuffle\'s own largest cloud at this level, as -log10 chance: middle '
          f'{np.median(-np.log10(null.min(axis=1))):.2f}, largest of {SHUFFLES} '
          f'{(-np.log10(null.min(axis=1))).max():.2f}')
    print(f'chance for one scope alone, across the scopes: a tenth lie under '
          f'{np.percentile(own, 10):.3f}, half under {np.median(own):.3f} '
          f'(0.100 and 0.500 if a scope were a random handful)')
    print('  chunks  in top  depth  size gives  -log10  shuffles as large:  sum in   scope')
    print('                                      chance  alone   any scope  spreads')
    for i in np.argsort(low)[:8]:
        print(f'  {sizes[i]:6d}  {count[i]:6d}  {where[i]:5d}  {where[i] * sizes[i] / N:10.2f}'
              f'  {-np.log10(low[i]):6.2f}  {own[i]:6.3f}  {family[i]:9.3f}  {zed[i]:7.2f}'
              f'   {paths[i]}')
    ordered = np.sort(-np.log10(low))[::-1][:10]
    print('  the ten largest -log10 chance in order: ' + ' '.join(f'{v:.1f}' for v in ordered))
    for label, line in lines:
        above = base >= line
        T = int(above.sum())
        got = np.add.reduceat(above[flat].astype(int), starts)
        tail = stats.hypergeom.sf(got - 1, N, sizes, T)
        first = np.argsort(tail)[:3]
        print(f'  a line at {label} ({T} chunks above {line:.2f}): '
              + '; '.join(f'{paths[i]} holds {got[i]} of its {sizes[i]} (size gives '
                          f'{T * sizes[i] / N:.1f})' for i in first))

# under the product with the largest cloud: its own scopes, judged among themselves
P = kept[0]
first = int(np.argmin(P['low']))
parent = P['paths'][first]
print(f'\n== under {parent} ==')
for depth in (1, 2):
    L = kept[depth]
    mine = np.array([i for i, p in enumerate(L['paths']) if p.startswith(parent + '/')])
    among = (L['null'][:, mine].min(axis=1)[:, None] <= L['low'][mine][None, :]).mean(axis=0)
    print(f'{levels[depth]}: {mine.size} scopes under it')
    print('  chunks  in top  depth  size gives  shuffles as large: alone  any of these  any of the level')
    for j in np.argsort(L['low'][mine]):
        i = mine[j]
        print(f'  {L["sizes"][i]:6d}  {L["count"][i]:6d}  {L["where"][i]:5d}'
              f'  {L["where"][i] * L["sizes"][i] / N:10.2f}  {L["own"][i]:24.3f}  {among[j]:12.3f}'
              f'  {L["family"][i]:16.3f}   {L["paths"][i]}')
