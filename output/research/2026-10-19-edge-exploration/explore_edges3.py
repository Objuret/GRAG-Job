"""Third pass: the kind of record taken out (the structure gives it). Each facet ranked among the edges of
the same kind; what is left: chunk / tag / pair, ties between facets, clusters with their tags, what goes
with each facet inside a kind. Reads edges.npz written by explore_edges.py."""
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.stats import rankdata, spearmanr, norm
from sklearn.mixture import GaussianMixture
from sklearn.metrics import adjusted_mutual_info_score

D = np.load(str(Path(__file__).parent / 'edges.npz'), allow_pickle=True)
R0, kind, chunk, tag, parent, recs = D['R'], D['kind'], D['chunk'], D['tag'], D['parent'], D['recs']
NAMES = ('topic', 'temporal', 'why', 'activity', 'concreteness')
rng = np.random.default_rng(0)
R = np.empty_like(R0)                       # each facet ranked inside its kind, 0..1
for k in np.unique(kind):
    m = kind == k
    for j in range(5):
        R[m, j] = rankdata(R0[m, j]) / m.sum()
cdeg = Counter(chunk.tolist()); tdeg = Counter(tag.tolist())
cd = np.array([cdeg[c] for c in chunk]); td = np.array([tdeg[t] for t in tag])
BIG = ('slack_thread_batch', 'document_part', 'pr_batch', 'document', 'meeting_transcript')


def shuffle_within(X, groups):
    Y = X.copy()
    for g in np.unique(groups):
        idx = np.flatnonzero(groups == g)
        for j in range(X.shape[1]):
            Y[idx, j] = X[rng.permutation(idx), j]
    return Y


def backfit(x, a_idx, b_idx, iters=30):
    mu = x.mean(); b = np.zeros(b_idx.max() + 1)
    na = np.bincount(a_idx); nb = np.bincount(b_idx)
    for _ in range(iters):
        a = np.bincount(a_idx, x - mu - b[b_idx]) / na
        b = np.bincount(b_idx, x - mu - a[a_idx]) / nb
    rest = x - mu - a[a_idx] - b[b_idx]
    tot = ((x - mu) ** 2).sum()
    return (a[a_idx] ** 2).sum() / tot, (b[b_idx] ** 2).sum() / tot, (rest ** 2).sum() / tot, rest


print('1. CHUNK / TAG / PAIR inside each kind (chunk 2+ edges, tag 2+ chunks of that kind; shuffled in brackets)')
for k in ('slack_thread_batch', 'document_part', 'document', 'pr_batch', 'meeting_transcript'):
    mk = kind == k
    c2 = Counter(chunk[mk].tolist()); t2 = Counter(tag[mk].tolist())
    m = mk & np.array([c2[c] >= 2 for c in chunk]) & np.array([t2[t] >= 2 for t in tag])
    _, ci = np.unique(chunk[m], return_inverse=True); _, ti = np.unique(tag[m], return_inverse=True)
    Rm = R[m]; Rn = shuffle_within(Rm, np.zeros(m.sum()))
    print(f'  {k}: {m.sum()} edges, {ci.max() + 1} chunks, {ti.max() + 1} tags')
    for j, n in enumerate(NAMES):
        a, b, r, _ = backfit(Rm[:, j], ci, ti)
        a0, b0, r0, _ = backfit(Rn[:, j], ci, ti)
        print(f'    {n:13s} chunk {a:4.2f} ({a0:4.2f})  tag {b:4.2f} ({b0:4.2f})  pair {r:4.2f} ({r0:4.2f})')

print('\n2. TIES BETWEEN THE FACETS inside each kind (Spearman)')
for k in BIG:
    mk = kind == k
    C = spearmanr(R[mk]).correlation
    print(f'  {k:20s} ' + ', '.join(f'{NAMES[i][:4]}-{NAMES[j][:4]} {C[i, j]:+.2f}' for i in range(5) for j in range(i + 1, 5)))

print('\n3. WHAT GOES WITH EACH FACET inside a kind (Spearman): records in the chunk | chunks the tag sits on | share of the facet the parent (channel, meeting, file) holds, shuffled in brackets')


def eta2(x, g):
    _, inv, cnt = np.unique(g, return_inverse=True, return_counts=True)
    means = np.bincount(inv, x) / cnt
    return ((means[inv] - x.mean()) ** 2).sum() / ((x - x.mean()) ** 2).sum()


for k in ('slack_thread_batch', 'pr_batch', 'document_part', 'meeting_transcript'):
    mk = kind == k
    out = []
    for j, n in enumerate(NAMES):
        x = R[mk, j]
        rr = spearmanr(x, recs[mk]).correlation if np.ptp(recs[mk]) > 0 else float('nan')
        e = eta2(x, parent[mk]); e0 = eta2(rng.permutation(x), parent[mk])
        out.append(f'{n[:5]} {rr:+.2f} | {spearmanr(x, td[mk]).correlation:+.2f} | {e:.2f} ({e0:.2f})')
    print(f'  {k}: ' + ';  '.join(out))

print('\n4. CLUSTERS inside Slack batches on the within-kind ranks, against a shuffled control')
mk = kind == 'slack_thread_batch'
Z = norm.ppf(np.clip(R[mk], 1e-4, 1 - 1e-4))
Zc = shuffle_within(Z, np.zeros(mk.sum()))
real = np.array([GaussianMixture(k, covariance_type='full', random_state=0).fit(Z).bic(Z) for k in range(1, 9)])
ctrl = np.array([GaussianMixture(k, covariance_type='full', random_state=0).fit(Zc).bic(Zc) for k in range(1, 9)])
print('  BIC fall from one cluster, real | shuffled: ' + ' '.join(f'{k}:{(real[0] - a) / 1000:.1f}k|{(ctrl[0] - b) / 1000:.1f}k'
                                                          for k, a, b in zip(range(1, 9), real, ctrl)))
for kk in (3, 4):
    labs = [GaussianMixture(kk, covariance_type='full', random_state=s).fit(Z).predict(Z) for s in range(3)]
    print(f'\n  {kk} clusters, agreement between seeds: {[round(adjusted_mutual_info_score(labs[0], l), 2) for l in labs[1:]]}')
    lab = labs[0]
    for c in np.argsort(-np.bincount(lab)):
        m = lab == c
        top = Counter(tag[mk][m].tolist()).most_common(8)
        print(f'   {c}: {m.sum()} edges; middle ' + ', '.join(f'{n[:4]} {np.median(R[mk][m, j]):.2f}' for j, n in enumerate(NAMES))
              + f'; records {np.median(recs[mk][m]):.0f}; tag on {np.median(td[mk][m]):.0f} chunks')
        print('      ' + ', '.join(f'{t} ({v})' for t, v in top))
