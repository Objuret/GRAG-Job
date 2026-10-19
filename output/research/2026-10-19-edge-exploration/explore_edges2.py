"""Second pass: shapes, chunk/tag/pair split with a shuffled control, clusters against a shuffled control."""
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.stats import rankdata, spearmanr, norm
from sklearn.mixture import GaussianMixture
from sklearn.metrics import adjusted_mutual_info_score

S = str(Path(__file__).parent)
D = np.load(S + '/edges.npz', allow_pickle=True)
V, R, kind, chunk, tag, recs = D['V'], D['R'], D['kind'], D['chunk'], D['tag'], D['recs']
NAMES = ('topic', 'temporal', 'why', 'activity', 'concreteness')
rng = np.random.default_rng(0)
cdeg = Counter(chunk.tolist()); tdeg = Counter(tag.tolist())
cd = np.array([cdeg[c] for c in chunk]); td = np.array([tdeg[t] for t in tag])

print('A. SHAPE of each facet (raw values)')
for j, n in enumerate(NAMES):
    x = V[:, j]
    q = np.quantile(x, [.01, .25, .5, .75, .99])
    h, _ = np.histogram(x, bins=12)
    bar = ''.join(' .:-=+*#%@'[min(9, int(9 * v / h.max()))] for v in h)
    print(f'  {n:13s} distinct {len(np.unique(np.round(x, 6))):6d}  q01..q99 ' + ' '.join(f'{v:6.2f}' for v in q) + f'   histogram |{bar}|')


def shuffle_within(X, groups):
    Y = X.copy()
    for g in np.unique(groups):
        idx = np.flatnonzero(groups == g)
        for j in range(X.shape[1]):
            Y[idx, j] = X[rng.permutation(idx), j]
    return Y


def backfit(x, a_idx, b_idx, iters=30):
    """x = mean + chunk effect + tag effect + rest, fitted by turns."""
    mu = x.mean(); a = np.zeros(a_idx.max() + 1); b = np.zeros(b_idx.max() + 1)
    na = np.bincount(a_idx); nb = np.bincount(b_idx)
    for _ in range(iters):
        a = np.bincount(a_idx, x - mu - b[b_idx]) / na
        b = np.bincount(b_idx, x - mu - a[a_idx]) / nb
    rest = x - mu - a[a_idx] - b[b_idx]
    tot = ((x - mu) ** 2).sum()
    return (a[a_idx] ** 2).sum() / tot, (b[b_idx] ** 2).sum() / tot, (rest ** 2).sum() / tot, rest


print('\nB. CHUNK / TAG / PAIR, edges whose chunk has 2+ edges and whose tag sits on 2+ chunks')
m = (cd >= 2) & (td >= 2)
_, ci = np.unique(chunk[m], return_inverse=True); _, ti = np.unique(tag[m], return_inverse=True)
print(f'  {m.sum()} edges, {ci.max() + 1} chunks, {ti.max() + 1} tags')
Rm = R[m]
Rnull = shuffle_within(Rm, kind[m])
rests = {}
print(f'  {"":13s} {"chunk":>13s} {"tag":>13s} {"pair (rest)":>13s}    (shuffled inside kind in brackets)')
for j, n in enumerate(NAMES):
    a, b, r, rest = backfit(Rm[:, j], ci, ti)
    a0, b0, r0, _ = backfit(Rnull[:, j], ci, ti)
    rests[n] = rest
    print(f'  {n:13s} {a:5.2f} ({a0:4.2f}) {b:6.2f} ({b0:4.2f}) {r:6.2f} ({r0:4.2f})')
print('  the pair part of one facet against the pair part of another (Spearman):')
for i in range(5):
    print('   ' + f'{NAMES[i]:13s}' + ' '.join(f'{spearmanr(rests[NAMES[i]], rests[NAMES[j]]).correlation:6.2f}' for j in range(5)))

print('\nC. WHAT ELSE GOES WITH EACH FACET (Spearman inside Slack batches / inside document parts)')
for k in ('slack_thread_batch', 'document_part'):
    mk = kind == k
    print(f'  {k}: ' + '; '.join(f'{n}: records {spearmanr(R[mk, j], recs[mk]).correlation:+.2f}, '
                                 f'tag on n chunks {spearmanr(R[mk, j], td[mk]).correlation:+.2f}'
                                 for j, n in enumerate(NAMES)))

print('\nD. CLUSTERS AGAINST A SHUFFLED CONTROL (Gaussian mixture, BIC; the control keeps each facet\'s spread inside each kind, breaks the ties between facets)')
Z = norm.ppf(np.clip(R, 1e-4, 1 - 1e-4))


def bic_curve(X, ks=range(1, 11)):
    return np.array([GaussianMixture(k, covariance_type='full', random_state=0, n_init=1).fit(X).bic(X) for k in ks])


def bend(b):
    ks = np.arange(1, len(b) + 1)
    line = b[0] + (b[-1] - b[0]) * (ks - 1) / (ks[-1] - 1)
    return int(ks[np.argmax(line - b)])


for label, X, grp in (('all edges', Z, kind),
                      ('kind taken out (each ranking less its kind\'s middle)', None, kind)):
    if X is None:
        Rk = R.copy()
        for k in np.unique(kind):
            Rk[kind == k] -= np.median(R[kind == k], axis=0)
        X = Rk / Rk.std(0)
    real = bic_curve(X)
    ctrl = bic_curve(shuffle_within(X, grp))
    gain_real = real[0] - real; gain_ctrl = ctrl[0] - ctrl
    print(f'  {label}: BIC fall from one cluster, real | shuffled:')
    print('   ' + ' '.join(f'{k}:{gr / 1000:.1f}k|{gc / 1000:.1f}k' for k, gr, gc in zip(range(1, 11), gain_real, gain_ctrl)))
    print(f'   bend real {bend(real)}, bend shuffled {bend(ctrl)}')

print('\nE. THE FOUR CLUSTERS OF ALL EDGES, most frequent tags and seed stability')
labs = []
for seed in range(3):
    g = GaussianMixture(4, covariance_type='full', random_state=seed, n_init=1).fit(Z)
    labs.append(g.predict(Z))
print('  agreement between seeds (AMI):', [round(adjusted_mutual_info_score(labs[0], l), 2) for l in labs[1:]])
lab = labs[0]
for c in np.argsort(-np.bincount(lab)):
    mm = lab == c
    top = Counter(tag[mm].tolist()).most_common(8)
    print(f'  cluster {c} ({mm.sum()} edges; middle ' + ', '.join(f'{n[:4]} {np.median(R[mm, j]):.2f}' for j, n in enumerate(NAMES)) + '):')
    print('     ' + ', '.join(f'{t} ({v})' for t, v in top))
