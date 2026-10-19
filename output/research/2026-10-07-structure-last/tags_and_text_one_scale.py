"""The two numbers a chunk gets (from its tags, from its description) put on one scale before
they are put together, on the made-up question's arrays (`structure_last_arrays.npz`).
Each step prints what it does to the order. The lifts are left out on both sides.
No model call, no benchmark file, nothing uses the 72,000 cut. Run from the repo root."""
import json
import pathlib
import sys

import numpy as np
from scipy import stats

sys.stdout.reconfigure(encoding='utf-8')
HERE = pathlib.Path('output/research/2026-10-07-structure-last')
A = np.load(HERE / 'structure_last_arrays.npz')
J = json.loads((HERE / 'structure_last_arrays.json').read_text(encoding='utf-8'))

t, x = A['tags'].astype(float), A['text'].astype(float)
N = t.size
today = t + x
kind = A['kind'].astype(np.int64)
names = [str(k) for k in J['kind_names']]
per_link = A['per_link'].astype(float)
chunk_of = A['edge_chunk'].astype(np.int64)
E = per_link.size
m = np.bincount(chunk_of, minlength=N)
best = np.zeros(N)
np.maximum.at(best, chunk_of, per_link)
print(f'{N} chunks, {E} links; the best link per chunk against the tags\' number: largest '
      f'difference {np.abs(best - t).max():.3g}; links a chunk: {m.min()} to {m.max()}, '
      f'middle {int(np.median(m))}')


def share_at_or_above(v):
    """Per value: the share of the values at least as large."""
    return stats.rankdata(-v, method='max') / v.size


def first(order_value, k):
    return np.argsort(-order_value, kind='stable')[:k]


# 1. what one unit means today
print('\n== 1. what one unit means today ==')
for name, v in (('from the tags', t), ('from the description', x)):
    mid = float(np.median(v))
    for step in (1., 2.):
        print(f'{name}: middle {mid:.2f}; chunks at least {step:.0f} above the middle: '
              f'{int((v >= mid + step).sum())} of {N} (1 in {N / max((v >= mid + step).sum(), 1):.0f})')

# 2. each number as the share of chunks at least as good
p_x = share_at_or_above(x)
p_t_plain = share_at_or_above(t)
ordered = np.sort(per_link)
q = (E - np.searchsorted(ordered, best, side='left')) / E          # links at least as good
p_t = np.where(q >= 1., 1., -np.expm1(m * np.log1p(-np.minimum(q, 1. - 1e-15))))
print('\n== 2. the tags\' number and the number of tags a chunk has ==')
print('rank correlation with the number of tags: the tags\' number '
      f'{stats.spearmanr(m, t)[0]:+.3f}; its plain share among the chunks '
      f'{stats.spearmanr(m, -p_t_plain)[0]:+.3f}; the share with the tries taken out '
      f'{stats.spearmanr(m, -p_t)[0]:+.3f}')
print('chunks per tenth of the share with the tries taken out (481 each if every chunk\'s tags '
      'were random draws): ' + ' '.join(str(int(c)) for c in
                                        np.histogram(p_t, bins=np.linspace(0, 1, 11))[0]))
quarters = np.percentile(m, [25, 50, 75])
groups = np.digitize(m, quarters, right=True)
labels = [f'{int(m[groups == g].min())}-{int(m[groups == g].max())} tags' for g in range(4)]
tenth_plain = p_t_plain <= 0.1
tenth_fair = p_t <= np.percentile(p_t, 10)
print('share of each group in the best tenth on the tags (0.100 each if the number of tags '
      'did not matter):')
print('   ' + '; '.join(f'{labels[g]}: plain {tenth_plain[groups == g].mean():.3f}, tries taken '
                        f'out {tenth_fair[groups == g].mean():.3f}' for g in range(4)))

# 3. do the two numbers have anything to do with each other over the pool
print('\n== 3. the two numbers against each other ==')
print(f'rank correlation over the pool: tags\' number with the description\'s {stats.spearmanr(t, x)[0]:+.3f}; '
      f'with the tries taken out {stats.spearmanr(-p_t, -p_x)[0]:+.3f}')
for cut in (0.1, 0.02):
    a, b = p_t <= np.percentile(p_t, cut * 100), p_x <= cut
    print(f'chunks in the best {cut:.0%} on both: {int((a & b).sum())}; if the two had nothing '
          f'to do with each other: {a.sum() * b.sum() / N:.1f}')

# 4. ways of putting the two together
both = -np.log(p_t) - np.log(p_x)                      # the two shares multiplied
ways = (('added as they are (today)', today),
        ('the two shares multiplied', both),
        ('the two shares multiplied, tries left in', -np.log(p_t_plain) - np.log(p_x)),
        ('the two positions added', (1. - p_t) + (1. - p_x)),
        ('the better of the two shares only', -np.log(np.minimum(p_t, p_x))),
        ('each in its own spreads, added', stats.zscore(t) + stats.zscore(x)))
top_t = p_t <= np.percentile(p_t, 10)
top_x = p_x <= 0.1
print('\n== 4. ways of putting the two together ==')
print('way                                        same first 20/50/100 as today   as the product    '
      'of its first 100: best tenth on tags only / description only / both / neither   '
      'rank correlation of the order with the number of tags')
ref_today = {k: set(first(today, k).tolist()) for k in (20, 50, 100)}
ref_both = set(first(both, 100).tolist())
for name, v in ways:
    f = first(v, 100)
    same = '/'.join(str(len(ref_today[k] & set(first(v, k).tolist()))) for k in (20, 50, 100))
    a, b = top_t[f], top_x[f]
    print(f'{name:42s} {same:>12s} {len(ref_both & set(f.tolist())):18d}        '
          f'{int((a & ~b).sum()):3d} / {int((~a & b).sum()):3d} / {int((a & b).sum()):3d} / '
          f'{int((~a & ~b).sum()):3d}                         {stats.spearmanr(m, v)[0]:+.3f}')

print('\nthe first 100 by kind of record (chunks of that kind in the pool):')
kinds = [k for k in np.unique(kind)]
print(' ' * 44 + ''.join(f'{names[k][:16]:>18s}' for k in kinds))
print(f'{"in the pool":44s}' + ''.join(f'{int((kind == k).sum()):18d}' for k in kinds))
for name, v in ways[:2]:
    f = first(v, 100)
    print(f'{name:44s}' + ''.join(f'{int((kind[f] == k).sum()):18d}' for k in kinds))

# 5. the product has a known chance: how many chunks are better on the pair than chance gives
k = p_t * p_x
chance = k * (1. - np.log(k))                 # P(product of two unrelated shares <= k)
print('\n== 5. how many chunks are this good on the pair, against chance ==')
for level in (0.1, 0.01, 0.001):
    print(f'chunks whose pair is rarer than {level:g}: {int((chance <= level).sum())}; '
          f'chance alone gives {N * level:.1f}')
print(f'chunks so good on the pair that fewer than one unrelated chunk in {N} would be: '
      f'{int((N * chance < 1.).sum())}')

# 6. the description's number among chunks of its own kind of record
p_x_kind = np.empty(N)
for kk in kinds:
    mem = np.flatnonzero(kind == kk)
    p_x_kind[mem] = stats.rankdata(-x[mem], method='max') / mem.size
own_kind = -np.log(p_t) - np.log(p_x_kind)
f = first(own_kind, 100)
print('\n== 6. the same product, the description\'s number read among chunks of its own kind ==')
print(f'same first 100 as the product over the whole pool: {len(ref_both & set(f.tolist()))}')
print(f'{"its first 100 by kind of record":44s}' + ''.join(f'{int((kind[f] == kk).sum()):18d}' for kk in kinds))
