"""All of a question's query tags together: do the graph tags group on their closeness to several
query tags at once, where each single list slides?

Numbers only. Reads the arrays the 2026-10-03 instrument measurement saved (query-role cosines of
every query tag of the ten smoke questions against the 16,654 graph tags, which of the two
querytagger lists each tag came from, the eligible mask, the edges, each chunk's product index).
No question text, no tag name, no gold, no model call, no graph read, no embedder. Estimators are
the instrument's own (instrument_lib.py).

What is the orchestrator's construction here, not his: every joint score, the two "stands out"
levels, the reference built from other questions' lists.

usage: python look_joint.py <evidence_arrays.npz> [seed]
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / '2026-10-03-evidence-design' / 'scratch'))
import instrument_lib as L  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
T0 = time.perf_counter()
NPZ = sys.argv[1]
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20261004
rng = np.random.default_rng(SEED)
BUNDLES = 40                                  # reference bundles per question

Z = np.load(NPZ, allow_pickle=False)
eligible = Z['eligible'].astype(bool)
N = int(eligible.sum())
U = math.sqrt(2.0 * math.log(N))          # universal level in spreads (Donoho & Johnstone 1994)
NQ = int(Z['n_questions'][0])
new_index = np.full(eligible.size, -1, dtype=np.int64)
new_index[eligible] = np.arange(N)
edge_ok = eligible[Z['edge_tag']]
edge_tag = new_index[Z['edge_tag'][edge_ok]]
edge_chunk = Z['edge_chunk'][edge_ok]
chunk_product = Z['chunk_product']
REF = L.spacing_reference()
SCORES = ('best', 'second', 'third', 'mean', 'possum', 'ranksum')
LABEL = {'best': 'best single list', 'second': 'second-best list', 'third': 'third-best list',
         'mean': 'mean over the lists', 'possum': 'sum of what is above the bulk',
         'ranksum': 'sum of -ln(rank/N)'}


def unique_rows(F):
    keep = []
    for j in range(F.shape[0]):
        if not any(np.max(np.abs(F[j] - F[i])) < 1e-9 for i in keep):
            keep.append(j)
    return np.array(keep)


def top_of(x):
    """How the top of one score list stands above that list's own bulk, and whether it breaks."""
    xs = np.sort(x)
    med = float(np.median(xs))
    s = float(L.MAD_K * np.median(np.abs(xs - med)))
    desc = xs[::-1]
    g = L.gap_stats(desc, s, REF)
    return {'raw1': float(desc[0]), 'top1': (desc[0] - med) / s, 'top10': (desc[9] - med) / s,
            'top100': (desc[99] - med) / s, 'n_univ': int(((xs - med) / s > U).sum()),
            'clear100': g['clear_breaks_top100'] > 0, 'fisher100': g['fisher_top100_p'] < 0.01,
            'break_rank': g['first_clear_break_rank']}


def joint_scores(z, lnr):
    """z: lists x tags, standings. lnr: lists x tags, -ln(rank/N). One value per tag each."""
    part = -np.sort(-z, axis=0)
    out = {'best': part[0], 'second': part[1], 'mean': z.mean(axis=0),
           'possum': np.clip(z, 0, None).sum(axis=0), 'ranksum': lnr.sum(axis=0)}
    if z.shape[0] > 2:
        out['third'] = part[2]
    return out


def reach(tags):
    """chunks reached by a set of tags, the share of them in the commonest product, products."""
    if tags.size == 0:
        return 0, float('nan'), 0
    mask = np.zeros(N, dtype=bool)
    mask[tags] = True
    chunks = np.unique(edge_chunk[mask[edge_tag]])
    prod = chunk_product[chunks]
    prod = prod[prod >= 0]
    if prod.size == 0:
        return int(chunks.size), float('nan'), 0
    counts = np.bincount(prod)
    return int(chunks.size), float(counts.max() / prod.size), int((counts > 0).sum())


def poisson_binomial_tail(p):
    dist = np.zeros(len(p) + 1)
    dist[0] = 1.0
    for pj in p:
        dist[1:] = dist[1:] * (1 - pj) + dist[:-1] * pj
        dist[0] *= (1 - pj)
    return np.cumsum(dist[::-1])[::-1]


def gap_statistic(X, kmax=6, refs=10):
    """Tibshirani, Walther & Hastie 2001: k-means dispersion against uniform references drawn in
    the box of the data's principal axes."""
    from sklearn.cluster import KMeans
    Xc = X - X.mean(axis=0)
    _, _, vt = np.linalg.svd(Xc, full_matrices=False)
    R = Xc @ vt.T
    lo, hi = R.min(axis=0), R.max(axis=0)

    def logw(data):
        return np.array([math.log(KMeans(n_clusters=k, n_init=2, random_state=SEED)
                                  .fit(data).inertia_) for k in range(1, kmax + 1)])

    w = logw(R)
    ref = np.array([logw(rng.uniform(lo, hi, size=R.shape)) for _ in range(refs)])
    gap = ref.mean(axis=0) - w
    sk = ref.std(axis=0) * math.sqrt(1 + 1 / refs)
    khat = kmax
    for k in range(1, kmax):
        if gap[k - 1] >= gap[k] - sk[k]:
            khat = k
            break
    sizes = []
    if khat > 1:
        km = KMeans(n_clusters=khat, n_init=2, random_state=SEED).fit(R)
        sizes = sorted(np.bincount(km.labels_).tolist(), reverse=True)
    return khat, sizes


def bundle_from_others(qi, m):
    """m lists from the other questions, as many different questions as possible."""
    pick = []
    others = np.flatnonzero(owner != qi)
    while len(pick) < m:
        for oq in rng.permutation(np.unique(owner[others])):
            cand = [c for c in others[owner[others] == oq] if c not in pick]
            if cand:
                pick.append(int(rng.choice(cand)))
            if len(pick) == m:
                break
    return np.array(pick)


def mm(v, digits=1):
    v = np.asarray(v, dtype=np.float64)
    return f'{np.nanmedian(v):.{digits}f} ({np.nanmin(v):.{digits}f}-{np.nanmax(v):.{digits}f})'


# ---- every question's lists, duplicates merged --------------------------------------------
lists, owner, side = [], [], []
per_q = []
for qi in range(NQ):
    F = Z[f'fits_{qi}'][:, eligible]
    sd = Z[f'side_{qi}']
    keep = unique_rows(F)
    per_q.append((F.shape[0], keep.size, int((sd[keep] == 0).sum()), int((sd[keep] == 1).sum())))
    for j in keep:
        lists.append(F[j])
        owner.append(qi)
        side.append(int(sd[j]))
ALL = np.vstack(lists)
owner, side = np.array(owner), np.array(side)
MED = np.median(ALL, axis=1, keepdims=True)
SPR = L.MAD_K * np.median(np.abs(ALL - MED), axis=1, keepdims=True)
ZALL = (ALL - MED) / SPR
RK = np.vstack([rankdata(-row, method='average') for row in ALL])
LNR = -np.log(RK / N)
OUT_U = ZALL > U                                    # above the universal level
OUT_R = ALL > (2 * MED - ALL.min(axis=1, keepdims=True))   # beyond the mirrored lowest value
print(f'{N} eligible graph tags; universal level {U:.3f} spreads; {ALL.shape[0]} distinct lists '
      f'over {NQ} questions')
print(f'lists per question (cached, distinct, description-side, question-side): {per_q}')

# ---- the single lists, against the instrument's published figures ---------------------------
single = [top_of(row) for row in ALL]
print('\nSINGLE LISTS (the instrument on 100 cached lists: 67 tags above the universal level, '
      'top-1/10/100 at 8.6/6.4/4.0 spreads, a break in the top 100 on 8-13)')
print(f'  tags above the universal level: {mm(OUT_U.sum(axis=1), 0)}; beyond the mirrored lowest '
      f'value: {mm(OUT_R.sum(axis=1), 0)}')
print(f"  top-1 / top-10 / top-100 in spreads, median: {np.median([s['top1'] for s in single]):.1f}"
      f" / {np.median([s['top10'] for s in single]):.1f} / "
      f"{np.median([s['top100'] for s in single]):.1f}")
print(f"  lists with a break in the top 100: clear-break rule {sum(s['clear100'] for s in single)},"
      f" Fisher g p<0.01 {sum(s['fisher100'] for s in single)}, of {len(single)}")

# ---- two lists at a time -----------------------------------------------------------------
R0 = np.vstack([rankdata(row) for row in ALL])
R0 = (R0 - R0.mean(axis=1, keepdims=True)) / R0.std(axis=1, keepdims=True)
SPEAR = (R0 @ R0.T) / N
iu = np.triu_indices(ALL.shape[0], 1)
same = owner[iu[0]] == owner[iu[1]]
print('\nTWO LISTS AT A TIME: pairs inside one question against pairs from two different '
      f'questions ({int(same.sum())} inside, {int((~same).sum())} across)')
sp = SPEAR[iu]
print(f'  rank correlation over all tags, median (5%-95%): inside {np.median(sp[same]):.2f} '
      f'({np.quantile(sp[same], .05):.2f}-{np.quantile(sp[same], .95):.2f}), across '
      f'{np.median(sp[~same]):.2f} ({np.quantile(sp[~same], .05):.2f}-{np.quantile(sp[~same], .95):.2f});'
      f' inside pairs above 0.8: {int((sp[same] > 0.8).sum())}')
LIFT_ACROSS = {}
for name, OUT in (('universal level', OUT_U), ('mirrored lowest value', OUT_R)):
    n_out = OUT.sum(axis=1).astype(np.float64)
    inter = OUT.astype(np.float64) @ OUT.T.astype(np.float64)
    expected = np.outer(n_out, n_out) / N
    ii, ee = inter[iu], expected[iu]
    lift_in = ii[same].sum() / ee[same].sum()
    lift_ac = ii[~same].sum() / ee[~same].sum()
    LIFT_ACROSS[name] = lift_ac
    union = n_out[:, None] + n_out[None, :] - inter
    with np.errstate(divide='ignore', invalid='ignore'):
        jac = (inter / union)[iu]
    print(f'  stand-out = above the {name}:')
    print(f'    pairs sharing at least one stand-out tag: inside {int((ii[same] > 0).sum())} of '
          f'{int(same.sum())} ({(ii[same] > 0).mean():.0%}), across {int((ii[~same] > 0).sum())} of '
          f'{int((~same).sum())} ({(ii[~same] > 0).mean():.0%})')
    print(f'    shared tags over what unrelated lists of the same sizes would share: inside '
          f'{lift_in:.1f}x, across {lift_ac:.1f}x')
    print(f'    inside pairs whose two sets are more than half the same: '
          f'{int((np.nan_to_num(jac[same]) > 0.5).sum())}')

# ---- per question -----------------------------------------------------------------------------
rows = []
for qi in range(NQ):
    idx = np.flatnonzero(owner == qi)
    m = idx.size
    z, lnr = ZALL[idx], LNR[idx]
    js = joint_scores(z, lnr)
    tops = {name: top_of(v) for name, v in js.items()}
    ref_tops = {name: [] for name in js}
    ref_counts = {'universal level': [], 'mirrored lowest value': []}
    for _ in range(BUNDLES):
        pick = bundle_from_others(qi, m)
        for name, v in joint_scores(ZALL[pick], LNR[pick]).items():
            if name in ref_tops:
                ref_tops[name].append(top_of(v))
        for name, OUT in (('universal level', OUT_U), ('mirrored lowest value', OUT_R)):
            kk = OUT[pick].sum(axis=0)
            ref_counts[name].append([(kk >= r).sum() for r in (1, 2, 3, 4)])
    above_ref = {name: int((js[name] > np.median([t['raw1'] for t in ref_tops[name]])).sum())
                 for name in js}
    counts = {}
    for name, OUT in (('universal level', OUT_U), ('mirrored lowest value', OUT_R)):
        out = OUT[idx]
        k = out.sum(axis=0)
        n_out = out.sum(axis=1).astype(np.float64)
        inter = out.astype(np.float64) @ out.T.astype(np.float64)
        pu = np.triu_indices(m, 1)
        seen_pairs = float(inter[pu].sum())
        matched = float((np.outer(n_out, n_out) / N)[pu].sum() * LIFT_ACROSS[name])
        d, q = out[side[idx] == 0], out[side[idx] == 1]
        counts[name] = dict(
            per_list=sorted(n_out.astype(int).tolist()), k=k,
            seen=[int((k >= r).sum()) for r in (1, 2, 3, 4)],
            indep=(poisson_binomial_tail(out.mean(axis=1)) * N)[1:5],
            ref=np.mean(ref_counts[name], axis=0), seen_pairs=seen_pairs, matched=matched,
            biggest_pair=float(inter[pu].max()) if m > 1 else 0.0,
            d2=int((d.sum(axis=0) >= 2).sum()) if d.shape[0] > 1 else 0,
            q2=int((q.sum(axis=0) >= 2).sum()) if q.shape[0] > 1 else 0,
            both=int(((d.sum(axis=0) >= 1) & (q.sum(axis=0) >= 1)).sum()) if q.shape[0] else 0)
    k = counts['universal level']['k']
    levels = {r: np.flatnonzero(k >= r) for r in (1, 2, 3)}
    reaches = {r: reach(t) for r, t in levels.items()}
    rand = {}
    for r in (1, 2, 3):
        draws = [reach(rng.choice(N, size=levels[r].size, replace=False)) for _ in range(30)] \
            if levels[r].size else []
        rand[r] = (np.mean([d[0] for d in draws]) if draws else float('nan'),
                   np.mean([d[1] for d in draws]) if draws else float('nan'))
    one = np.array([reach(np.flatnonzero(o))[:2] for o in OUT_U[idx]], dtype=np.float64)
    khat, sizes = gap_statistic(z.T)
    rows.append(dict(m=m, tops=tops, ref_tops=ref_tops, above_ref=above_ref, counts=counts,
                     reaches=reaches, rand=rand, khat=khat, sizes=sizes, levels=levels))

    print(f'\nQUESTION {qi + 1}: {m} distinct lists ({int((side[idx] == 0).sum())} description-side, '
          f'{int((side[idx] == 1).sum())} question-side)')
    for name in ('universal level', 'mirrored lowest value'):
        c = counts[name]
        print(f'  stand-out = above the {name}; per list {c["per_list"]}')
        print(f'    tags standing out on at least 1 / 2 / 3 / 4 lists: seen {c["seen"]}; '
              f'unrelated lists {[round(float(v), 1) for v in c["indep"]]}; '
              f'lists of other questions {[round(float(v), 1) for v in c["ref"]]}')
        print(f'    shared tags summed over the pairs: seen {c["seen_pairs"]:.0f}; lists of these sizes '
              f'overlapping as lists of different questions do {c["matched"]:.0f}; the one biggest '
              f'pair {c["biggest_pair"]:.0f}')
        print(f'    on at least 2 description-side lists {c["d2"]}; on at least 2 question-side '
              f'lists {c["q2"]}; on at least one of each {c["both"]}')
    print('  one value per graph tag from all the lists; the top of that list in spreads above its '
          'own bulk (top-1 / top-10 / top-100) | the same from lists of other questions (median) | '
          'tags above anything those typically reach | break in the top 100 (clear / Fisher)')
    for name in SCORES:
        if name not in tops:
            continue
        t, r = tops[name], ref_tops[name]
        print(f'    {LABEL[name]:30s} {t["top1"]:5.1f} / {t["top10"]:5.1f} / {t["top100"]:5.1f} | '
              f'{np.median([x["top1"] for x in r]):5.1f} / {np.median([x["top10"] for x in r]):5.1f} / '
              f'{np.median([x["top100"] for x in r]):5.1f} | {above_ref[name]:4d} | '
              f'{"yes" if t["clear100"] else "no "} / {"yes" if t["fisher100"] else "no "}'
              + (f' (after rank {int(t["break_rank"])})' if t['clear100'] else '')
              + f' | other questions break on {sum(x["clear100"] for x in r)} of {len(r)}')
    print('  what each level reaches (universal level): tags, chunks, share of the chunks in the '
          'commonest product, products | a random tag set of the same size: chunks, share')
    for r in (1, 2, 3):
        c, share, prods = reaches[r]
        print(f'    at least {r} list(s): {levels[r].size:5d} tags, {c:5d} chunks, {share:.2f}, '
              f'{prods:2d} products | {rand[r][0]:.0f}, {rand[r][1]:.2f}')
    print(f'    one list alone, median over the lists: {np.median(OUT_U[idx].sum(axis=1)):.0f} tags, '
          f'{np.median(one[:, 0]):.0f} chunks, {np.nanmedian(one[:, 1]):.2f}')
    print(f'  gap statistic on the {m} lists together: {khat} group(s)'
          + (f', sizes {sizes}' if sizes else ''), flush=True)

# ---- summary over the ten ------------------------------------------------------------------
print('\nSUMMARY OVER THE TEN QUESTIONS (median, min-max)')
for name in ('universal level', 'mirrored lowest value'):
    print(f'  stand-out = above the {name}')
    for r in (1, 2, 3, 4):
        print(f'    on at least {r} list(s): seen {mm([x["counts"][name]["seen"][r - 1] for x in rows], 0)}; '
              f'unrelated lists {mm([x["counts"][name]["indep"][r - 1] for x in rows])}; lists of '
              f'other questions {mm([x["counts"][name]["ref"][r - 1] for x in rows])}')
    print(f'    shared tags summed over the pairs: seen '
          f'{mm([x["counts"][name]["seen_pairs"] for x in rows], 0)}; size-matched from other '
          f'questions {mm([x["counts"][name]["matched"] for x in rows], 0)}; ratio '
          f'{mm([x["counts"][name]["seen_pairs"] / x["counts"][name]["matched"] for x in rows])}')
    print(f'    at least 2 description-side {mm([x["counts"][name]["d2"] for x in rows], 0)}; at '
          f'least 2 question-side {mm([x["counts"][name]["q2"] for x in rows], 0)}; one of each '
          f'{mm([x["counts"][name]["both"] for x in rows], 0)}')
for r in (1, 2, 3):
    print(f'  reach at least {r} list(s): tags {mm([x["levels"][r].size for x in rows], 0)}, chunks '
          f'{mm([x["reaches"][r][0] for x in rows], 0)}, share in the commonest product '
          f'{mm([x["reaches"][r][1] for x in rows], 2)}, random set of the same size '
          f'{mm([x["rand"][r][1] for x in rows], 2)}')
for name in SCORES:
    have = [x for x in rows if name in x['tops']]
    print(f'  {LABEL[name]}: top-1 {mm([x["tops"][name]["top1"] for x in have])}, from other '
          f'questions {mm([np.median([t["top1"] for t in x["ref_tops"][name]]) for x in have])}; '
          f'tags above what those typically reach {mm([x["above_ref"][name] for x in have], 0)}; '
          f'break in the top 100 on {sum(x["tops"][name]["clear100"] for x in have)} (clear) / '
          f'{sum(x["tops"][name]["fisher100"] for x in have)} (Fisher) of {len(have)}; other '
          f'questions\' bundles break on '
          f'{sum(sum(t["clear100"] for t in x["ref_tops"][name]) for x in have)} of '
          f'{sum(len(x["ref_tops"][name]) for x in have)}')
print(f'  gap statistic on the lists together, groups per question: {[x["khat"] for x in rows]}')
print(f'\nseed {SEED}; {BUNDLES} reference bundles a question; {time.perf_counter() - T0:.0f}s')
