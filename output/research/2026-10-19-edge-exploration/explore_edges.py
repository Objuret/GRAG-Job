"""Blind exploration of the tag-to-chunk edges: the five facet values, ranked; no gold, no question."""
import sys
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.stats import rankdata, spearmanr
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.metrics import adjusted_mutual_info_score

sys.path[:0] = [r'C:\Coding\exjobbet\GRAG-Job\prod', r'C:\Coding\exjobbet\GRAG-Job\test']
from graph.db import _driver  # noqa: E402

d = _driver()
with d.session(database='herb-eval-volmax', default_access_mode='READ') as s:
    rows = s.run('''MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
      WHERE r.run_id = 'pilot_full_herb' AND c.desc_emb IS NOT NULL AND t.emb IS NOT NULL
      MATCH (c)-[:product]->(p:Product)
      RETURN c.chunk_id AS chunk, c.kind AS kind, c.parent_ref AS parent, p.name AS product,
             size(coalesce(c.times, [])) AS records, t.name AS tag, r.w_facets AS v''').data()
d.close()
NAMES = ('topic', 'temporal', 'why', 'activity', 'concreteness')
V = np.array([r['v'] for r in rows], dtype=float)
R = np.column_stack([rankdata(V[:, j]) / len(V) for j in range(5)])
kind = np.array([r['kind'] for r in rows]); chunk = np.array([r['chunk'] for r in rows])
tag = np.array([r['tag'] for r in rows]); product = np.array([r['product'] for r in rows])
parent = np.array([r['parent'] for r in rows]); recs = np.array([r['records'] for r in rows])
print('edges', len(rows), 'chunks', len(set(chunk)), 'tags', len(set(tag)), 'products', len(set(product)))
deg = Counter(tag.tolist()); tag_deg = np.array([deg[t] for t in tag])
cdeg = Counter(chunk.tolist()); chunk_deg = np.array([cdeg[c] for c in chunk])
print('edges per chunk: middle', np.median(list(cdeg.values())), 'edges per tag: middle', np.median(list(deg.values())),
      'tags on one chunk only', sum(1 for v in deg.values() if v == 1))

print('\n1. SPEARMAN between the five, all edges')
C = spearmanr(V).correlation
print('              ' + ' '.join(f'{n[:6]:>7s}' for n in NAMES))
for i, n in enumerate(NAMES):
    print(f'  {n:12s}' + ' '.join(f'{C[i, j]:7.2f}' for j in range(5)))
for k in ('slack_thread_batch', 'document_part', 'meeting_transcript'):
    m = kind == k
    C = spearmanr(V[m]).correlation
    print(f'  inside {k} ({m.sum()} edges): ' + ', '.join(f'{NAMES[i][:4]}-{NAMES[j][:4]} {C[i, j]:.2f}'
                                                         for i in range(5) for j in range(i + 1, 5)))


def eta2(x, g):
    """Share of x's spread that lies between the groups g."""
    _, inv, cnt = np.unique(g, return_inverse=True, return_counts=True)
    means = np.bincount(inv, x) / cnt
    return ((means[inv] - x.mean()) ** 2).sum() / ((x - x.mean()) ** 2).sum()


def eta2_null(x, g, within, reps=5, seed=0):
    """The same with the edges shuffled inside `within` (keeps group sizes), mean over reps."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        y = x.copy()
        for w in np.unique(within):
            idx = np.flatnonzero(within == w)
            y[idx] = y[rng.permutation(idx)]
        out.append(eta2(y, g))
    return float(np.mean(out))


print('\n2. WHAT DECIDES AN EDGE\'S PLACE: share of each ranking between groups (shuffled inside kind in brackets)')
print(f'  {"":13s} {"kind":>6s} {"product":>8s} {"parent":>12s} {"chunk":>12s} {"tag":>12s}')
for j, n in enumerate(NAMES):
    x = R[:, j]
    vals = [eta2(x, kind), eta2(x, product)]
    for g in (parent, chunk, tag):
        vals.append((eta2(x, g), eta2_null(x, g, kind)))
    print(f'  {n:13s} {vals[0]:6.2f} {vals[1]:8.2f} ' + ' '.join(f'{a:5.2f} ({b:4.2f})' for a, b in vals[2:]))

# inside a chunk: do the tags on the same chunk stand apart? spread inside chunk vs spread inside tag
print('\n3. INSIDE ONE CHUNK (chunks with 5+ edges): middle spread of the ranking among its own tags, against the same for random edges of the same kind')
many = np.array([cdeg[c] >= 5 for c in chunk])
rng = np.random.default_rng(1)
for j, n in enumerate(NAMES):
    sd_in = []
    for c in np.unique(chunk[many]):
        sd_in.append(R[chunk == c, j].std())
    sd_rand = []
    for c in np.unique(chunk[many])[:3000]:
        k = kind[chunk == c][0]; size = cdeg[c]
        pool = np.flatnonzero(kind == k)
        sd_rand.append(R[rng.choice(pool, size, replace=False), j].std())
    print(f'  {n:13s} inside a chunk {np.median(sd_in):.3f}   random of same kind {np.median(sd_rand):.3f}')

print('\n4. PCA on the five rankings')
p = PCA().fit(R - R.mean(0))
print('  share of spread per direction', np.round(p.explained_variance_ratio_, 3))
for i in range(3):
    print(f'  direction {i + 1}: ' + ', '.join(f'{n} {w:+.2f}' for n, w in zip(NAMES, p.components_[i])))


def mixture(X, label, ks=range(1, 13)):
    bics, fits = [], []
    for k in ks:
        g = GaussianMixture(k, covariance_type='full', random_state=0, n_init=2).fit(X)
        bics.append(g.bic(X)); fits.append(g)
    best = int(np.argmin(bics))
    print(f'\n5. CLUSTERS ({label}): BIC by number', ' '.join(f'{k}:{b / 1000:.1f}k' for k, b in zip(ks, bics)), '-> lowest at', list(ks)[best])
    return fits, bics


# the rankings put through a normal score so the mixture sees a continuous scale
from scipy.stats import norm  # noqa: E402
Z = norm.ppf(np.clip(R, 1e-4, 1 - 1e-4))
fits, bics = mixture(Z, 'all edges, five rankings')
# the bend of the BIC curve as the number (the clustering's own knee)
b = np.array(bics); ks = np.arange(1, len(b) + 1)
line = b[0] + (b[-1] - b[0]) * (ks - 1) / (ks[-1] - 1)
knee = int(ks[np.argmax(line - b)])
print('  bend of the BIC curve at', knee)
for kk in sorted({knee, int(np.argmin(bics)) + 1}):
    g = fits[kk - 1]; lab = g.predict(Z)
    print(f'\n  {kk} clusters: AMI with kind {adjusted_mutual_info_score(kind, lab):.2f}, with product {adjusted_mutual_info_score(product, lab):.2f}')
    print(f'  {"cl":>3s} {"edges":>6s}  ' + ' '.join(f'{n[:6]:>6s}' for n in NAMES) + '   kinds (share of the cluster)')
    for c in np.argsort(-np.bincount(lab)):
        m = lab == c
        kc = Counter(kind[m].tolist()).most_common(3)
        print(f'  {c:3d} {m.sum():6d}  ' + ' '.join(f'{np.median(R[m, j]):6.2f}' for j in range(5))
              + '   ' + ', '.join(f'{k} {v / m.sum():.0%}' for k, v in kc)
              + f' | tags on few chunks {np.median(tag_deg[m]):.0f}, edges/chunk {np.median(chunk_deg[m]):.0f}')

m = kind == 'slack_thread_batch'
fits_s, bics_s = mixture(Z[m], 'Slack batches only')
b = np.array(bics_s); line = b[0] + (b[-1] - b[0]) * (ks - 1) / (ks[-1] - 1)
knee_s = int(ks[np.argmax(line - b)])
print('  bend of the BIC curve at', knee_s)
g = fits_s[knee_s - 1]; lab = g.predict(Z[m])
print(f'  {knee_s} clusters inside Slack batches: AMI with product {adjusted_mutual_info_score(product[m], lab):.2f}')
for c in np.argsort(-np.bincount(lab)):
    mm = lab == c
    print(f'  {c:3d} {mm.sum():6d}  ' + ' '.join(f'{np.median(R[m][mm, j]):6.2f}' for j in range(5))
          + f' | records in chunk {np.median(recs[m][mm]):.0f}, tag on {np.median(tag_deg[m][mm]):.0f} chunks')
np.savez(str(Path(__file__).parent / 'edges.npz'),
         V=V, R=R, kind=kind, chunk=chunk, tag=tag, product=product, parent=parent, recs=recs)
