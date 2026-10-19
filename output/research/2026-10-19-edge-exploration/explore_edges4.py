"""Can the facets be made relative to the tag (adaptive), deterministically? How often two edges of the same
graph tag, in the same product, differ by more than the facet's equal range (the net's 24 refits), against
two tags on the same chunk and two random edges of the same product and kind."""
from collections import Counter, defaultdict
from pathlib import Path
import sys
import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[3] / 'prod'), str(Path(__file__).resolve().parents[3] / 'test')]
from graph.db import _driver  # noqa: E402

D = np.load(str(Path(__file__).parent / 'edges.npz'), allow_pickle=True)
V, kind, chunk, tag, product = D['V'], D['kind'], D['chunk'], D['tag'], D['product']
d = _driver()
with d.session(database='herb-eval-volmax', default_access_mode='READ') as s:
    row = s.run("MATCH (l:FacetLayer {run_id: 'pilot_full_herb'}) RETURN l.equal_gap AS g, l.equal_gap_facets AS f").single()
d.close()
gap = dict(zip(row['f'], row['g']))
print('equal ranges', {k: round(v, 2) for k, v in gap.items()})
FAC = {'temporal': 1, 'why': 2, 'activity': 3, 'concreteness': 4}
rng = np.random.default_rng(0)


def groups(keys):
    g = defaultdict(list)
    for i, k in enumerate(keys):
        g[k].append(i)
    return [np.array(v) for v in g.values() if len(v) >= 2]


by_tag = groups(list(zip(tag.tolist(), product.tolist(), kind.tolist())))   # the structure gives product and kind
by_chunk = groups(chunk.tolist())
in_tag_group = np.zeros(len(V), bool)
for g in by_tag:
    in_tag_group[g] = True
print(f'edges whose graph tag is on another chunk of the same product and kind: {in_tag_group.sum()} of {len(V)} ({in_tag_group.mean():.0%})')
sizes = Counter(len(g) for g in by_tag)
print('  chunks per (tag, product, kind) group, middle', int(np.median([len(g) for g in by_tag])),
      '| groups of 2:', sizes[2], 'of', len(by_tag))


def share_beyond(groups_, j, g):
    over = tot = 0
    for idx in groups_:
        x = V[idx, j]
        dif = np.abs(x[:, None] - x[None, :])[np.triu_indices(len(x), 1)]
        over += (dif > g).sum(); tot += dif.size
    return over / tot, tot


print('\nshare of pairs that the facet ranks apart (difference beyond its equal range):')
print(f'  {"":13s} {"same tag+kind, other chunk":>22s} {"same chunk, other tag":>22s} {"random, same product+kind":>26s}')
pk = list(zip(product.tolist(), kind.tolist()))
pk_groups = groups(pk)
for n, j in FAC.items():
    a, na = share_beyond(by_tag, j, gap[n])
    b, nb = share_beyond(by_chunk, j, gap[n])
    # random pairs inside product+kind, as many as the same-tag pairs
    over = 0; tot = 0
    for idx in pk_groups:
        m = min(len(idx) * 3, 3000)
        i1 = rng.choice(idx, m); i2 = rng.choice(idx, m)
        keep = i1 != i2
        over += (np.abs(V[i1[keep], j] - V[i2[keep], j]) > gap[n]).sum(); tot += keep.sum()
    print(f'  {n:13s} {a:22.0%} {b:22.0%} {over / tot:26.0%}     ({na} and {nb} pairs)')
