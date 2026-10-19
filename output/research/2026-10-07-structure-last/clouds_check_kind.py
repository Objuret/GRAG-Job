"""Follow-up to `clouds_check.py` on the made-up question's arrays: the kinds of record sit at
different heights in the values, so a scope is compared here with a random handful of chunks of
ITS OWN kinds of record (each chunk's value read as its place among the chunks of its kind, and
the shuffle done inside each kind). Reads tags + text, before the two lifts.
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
SHUFFLES = 1000
rng = np.random.default_rng(20261008)

tags, text = A['tags'].astype(float), A['text'].astype(float)
base = tags + text
links = A['links'].astype(float)
kind = A['kind'].astype(np.int64)
names = J['kind_names']
N = base.size
high = np.percentile(base, 90)

print('== the kinds of record ==')
print('kind of record         chunks  links a chunk  middle of: tags   text  tags+text   '
      'share above the pool\'s 90% point')
for k in np.unique(kind):
    m = kind == k
    print(f'{str(names[k]):22s}{int(m.sum()):6d}  {links[m].mean():13.1f}  '
          f'{np.median(tags[m]):15.2f}{np.median(text[m]):7.2f}{np.median(base[m]):11.2f}'
          f'{(base[m] > high).mean():22.3f}')
rho, _ = stats.spearmanr(links, tags)
print(f'over the pool, a chunk\'s number of links against its value from the tags: rank '
      f'correlation {rho:.3f}')
for k in np.unique(kind):
    m = kind == k
    if m.sum() > 30:
        r, _ = stats.spearmanr(links[m], tags[m])
        print(f'   inside {names[k]}: {r:.3f}')
rho, _ = stats.spearmanr(links, text)
print(f'number of links against the value from the text: {rho:.3f}')

# each chunk's place among the chunks of its own kind of record, then one order over the pool
place = np.empty(N)
for k in np.unique(kind):
    m = np.flatnonzero(kind == k)
    inside = stats.rankdata(-base[m], method='ordinal')
    place[m] = (inside - 0.5) / m.size
rank = stats.rankdata(place, method='ordinal').astype(np.int64)
by_kind = [np.flatnonzero(kind == k) for k in np.unique(kind)]


def shuffled():
    out = rank.copy()
    for m in by_kind:
        out[m] = rank[rng.permutation(m)]
    return out


def depth_scan(ranks_of_members, sizes, starts):
    who = np.repeat(np.arange(sizes.size), sizes)
    inside = np.lexsort((ranks_of_members, who))
    r = ranks_of_members[inside]
    k = np.arange(r.size) - np.repeat(starts, sizes) + 1
    p = stats.hypergeom.sf(k - 1, N, np.repeat(sizes, sizes), r)
    low = np.minimum.reduceat(p, starts)
    at = np.array([s + int(np.argmin(p[s:s + n])) for s, n in zip(starts, sizes)])
    return low, k[at], r[at]


levels = {0: 'product', 1: 'product / kind of record', 2: 'channel'}
scopes = {d: [] for d in levels}
for path, members in J['paths'].items():
    scopes[path.count('/')].append((path, np.array(members, dtype=np.int64)))
draws = [shuffled() for _ in range(SHUFFLES)]
kept = {}
for depth, name in levels.items():
    paths = [p for p, _ in scopes[depth]]
    members = [m for _, m in scopes[depth]]
    sizes = np.array([m.size for m in members])
    starts = np.r_[0, np.cumsum(sizes)[:-1]]
    flat = np.concatenate(members)
    low, count, where = depth_scan(rank[flat], sizes, starts)
    null = np.empty((SHUFFLES, sizes.size))
    for b, drawn in enumerate(draws):
        null[b], _, _ = depth_scan(drawn[flat], sizes, starts)
    own = (null <= low[None, :]).mean(axis=0)
    family = (null.min(axis=1)[:, None] <= low[None, :]).mean(axis=0)
    kept[depth] = dict(paths=paths, sizes=sizes, low=low, count=count, where=where, null=null,
                       own=own, family=family)
    print(f'\n== {name}, each chunk read among its own kind of record: {sizes.size} scopes ==')
    print(f'the shuffle\'s own largest cloud at this level, as -log10: middle '
          f'{np.median(-np.log10(null.min(axis=1))):.2f}, largest of {SHUFFLES} '
          f'{(-np.log10(null.min(axis=1))).max():.2f}')
    print(f'chance for one scope alone, across the scopes: a tenth lie under '
          f'{np.percentile(own, 10):.3f}, half under {np.median(own):.3f} '
          f'(0.100 and 0.500 if a scope were a random handful of its kinds)')
    print('  chunks  in top  depth  size gives  -log10  shuffles as large:   scope')
    print('                                              alone   any scope')
    for i in np.argsort(low)[:8]:
        print(f'  {sizes[i]:6d}  {count[i]:6d}  {where[i]:5d}  {where[i] * sizes[i] / N:10.2f}'
              f'  {-np.log10(low[i]):6.2f}  {own[i]:6.3f}  {family[i]:9.3f}   {paths[i]}')
    ordered = np.sort(-np.log10(low))[::-1]
    print(f'  all -log10 in order, the first {min(30, ordered.size)}: '
          + ' '.join(f'{v:.1f}' for v in ordered[:30]))

P = kept[0]
parent = P['paths'][int(np.argmin(P['low']))]
print(f'\n== under {parent}, each chunk read among its own kind of record ==')
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
