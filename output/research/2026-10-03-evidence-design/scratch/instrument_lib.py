"""Estimators for the instrument measurement. Numbers in, numbers out; nothing is printed.

Literature (the estimator as published) and construction (what this scratch adds) are marked
per function.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize
from scipy.stats import kurtosis, norm, rankdata, skew

MAD_K = 1.4826   # 1 / Phi^-1(3/4): MAD -> sigma under a normal (Hampel 1974)


def half_sample_mode(xs):
    """Half-sample mode (Robertson & Cryer 1974; Bickel & Fruehwirth 2006). xs ascending."""
    x = np.asarray(xs, dtype=np.float64)
    while x.size > 3:
        h = (x.size + 1) // 2
        widths = x[h - 1:] - x[:x.size - h + 1]
        j = int(np.argmin(widths))
        x = x[j:j + h]
    if x.size == 3:
        left, right = x[1] - x[0], x[2] - x[1]
        if left < right:
            return float(0.5 * (x[0] + x[1]))
        if left > right:
            return float(0.5 * (x[1] + x[2]))
        return float(x[1])
    return float(np.mean(x))


def kde_mode(xs, bins=4000):
    """Argmax of a Gaussian kernel density, Silverman's rule-of-thumb bandwidth (Silverman
    1986, eq. 3.31), on a binned grid. xs ascending."""
    x = np.asarray(xs, dtype=np.float64)
    n = x.size
    q25, q75 = np.quantile(x, [0.25, 0.75])
    h = 0.9 * min(x.std(), (q75 - q25) / 1.349) * n ** (-0.2)
    lo, hi = x[0] - 4 * h, x[-1] + 4 * h
    counts, edges = np.histogram(x, bins=bins, range=(lo, hi))
    width = edges[1] - edges[0]
    half = int(math.ceil(4 * h / width))
    kernel = np.exp(-0.5 * ((np.arange(-half, half + 1) * width) / h) ** 2)
    dens = np.convolve(counts.astype(np.float64), kernel, mode='same')
    j = int(np.argmax(dens))
    return float(0.5 * (edges[j] + edges[j + 1])), float(h)


def ks_truncated_normal(xs, loc, scale, a, b):
    """Kolmogorov distance (Kolmogorov 1933) between the values in [a, b] and the normal
    N(loc, scale^2) truncated to [a, b]. A distance, not a test: the parameters are estimated
    from the same data (Lilliefors 1967), so no p-value is attached."""
    c = xs[(xs >= a) & (xs <= b)]
    k = c.size
    if k < 2:
        return float('nan')
    za, zb = norm.cdf((a - loc) / scale), norm.cdf((b - loc) / scale)
    if zb - za <= 0:
        return 1.0
    f0 = (norm.cdf((c - loc) / scale) - za) / (zb - za)
    up = np.arange(1, k + 1) / k
    dn = np.arange(0, k) / k
    return float(max(np.max(up - f0), np.max(f0 - dn)))


def truncated_normal_mle(xs, a, b, start):
    """Normal fitted by maximum likelihood to the values inside [a, b] only, as a truncated
    normal: the maximum-likelihood empirical null of Efron (2007, 'Size, power and false
    discovery rates'), with pi0 dropped (only location and scale are used here)."""
    c = xs[(xs >= a) & (xs <= b)]
    k = c.size

    def nll(theta):
        mu, ls = theta
        s = math.exp(ls)
        mass = norm.cdf((b - mu) / s) - norm.cdf((a - mu) / s)
        if mass <= 1e-300:
            return 1e300
        return k * ls + float(np.sum((c - mu) ** 2)) / (2 * s * s) + k * math.log(mass)

    res = minimize(nll, np.array([start[0], math.log(start[1])]), method='Nelder-Mead',
                   options={'xatol': 1e-9, 'fatol': 1e-9, 'maxiter': 4000})
    return float(res.x[0]), float(math.exp(res.x[1]))


def realness(x, loc, scale):
    """m(x) = 1 - min(1, N p0(x) / rank(x)), p0 the normal null's survival function, rank the
    number of values >= x. N p0(x) / rank(x) is the plug-in tail-area false discovery rate of
    Benjamini & Hochberg (1995) / Storey (2002) with pi0 = 1; its running minimum over all
    looser thresholds is the q-value (Storey & Tibshirani 2003). Both are returned: `m` as the
    task states it (no running minimum), `mq` = 1 - q-value."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    rank = rankdata(-x, method='max')
    fdr = np.minimum(1.0, n * norm.sf((x - loc) / scale) / rank)
    order = np.argsort(-x, kind='stable')
    q = np.empty(n)
    q[order] = np.minimum.accumulate(fdr[order][::-1])[::-1]
    return 1.0 - fdr, 1.0 - q, rank


def realness_reflection(x, centre):
    """Distribution-free symmetric-null version: the expected number of null values >= x is the
    number of values <= 2*centre - x (the reflection of the lower side). The estimator
    #{W <= -t} / #{W >= t} is that of Barber & Candes (2015, knockoffs; they add 1 to the
    numerator) and Arias-Castro & Chen (2017, 'Distribution-free multiple testing'); assuming
    the background here is symmetric about `centre` is this scratch's construction, not theirs."""
    x = np.asarray(x, dtype=np.float64)
    xs = np.sort(x)
    rank = rankdata(-x, method='max')
    null = np.searchsorted(xs, 2 * centre - x, side='right').astype(np.float64)
    fdr = np.where(x > centre, np.minimum(1.0, null / rank), 1.0)
    fdr1 = np.where(x > centre, np.minimum(1.0, (null + 1.0) / rank), 1.0)
    return 1.0 - fdr, 1.0 - fdr1


def realness_local(x, loc, scale, bins=4000):
    """1 - local false discovery rate, fdr(x) = f0(x) / f(x) with pi0 = 1 (Efron, Tibshirani,
    Storey & Tusher 2001; Efron 2004): the share of real items AT x, where the tail-area form
    of `realness` gives the share among all items at or above x. f is a Gaussian kernel density
    with Silverman's bandwidth on a binned grid, f0 the normal null's density. Counted above
    the centre only."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    q25, q75 = np.quantile(x, [0.25, 0.75])
    h = 0.9 * min(x.std(), (q75 - q25) / 1.349) * n ** (-0.2)
    lo, hi = x.min() - 4 * h, x.max() + 4 * h
    counts, edges = np.histogram(x, bins=bins, range=(lo, hi))
    width = edges[1] - edges[0]
    half = int(math.ceil(4 * h / width))
    kernel = np.exp(-0.5 * ((np.arange(-half, half + 1) * width) / h) ** 2)
    kernel /= kernel.sum() * width
    dens = np.convolve(counts / n, kernel, mode='same')
    centres = 0.5 * (edges[:-1] + edges[1:])
    f = np.interp(x, centres, dens)
    f0 = norm.pdf((x - loc) / scale) / scale
    fdr = np.where(f > 0, np.minimum(1.0, f0 / np.maximum(f, 1e-300)), 1.0)
    return np.where(x > loc, 1.0 - fdr, 0.0)


def fisher_g(xs, top=100):
    """Largest of the top-`top` normalised spacings D_i = i (x_(i) - x_(i+1)) against their sum.
    Under an exponential upper tail the D_i are iid exponential (Renyi 1953), and the largest
    share g = max D / sum D has Fisher's exact distribution (Fisher 1929). Returns g, the rank i
    after which the largest normalised spacing falls, and the exact p-value. Using it to ask
    whether the fit list has a break is this scratch's construction."""
    desc = np.asarray(xs, dtype=np.float64)[::-1][:top + 1]
    k = desc.size - 1
    d = np.arange(1, k + 1) * (desc[:-1] - desc[1:])
    total = float(d.sum())
    if total <= 0:
        return float('nan'), -1, float('nan')
    g = float(d.max() / total)
    p = 0.0
    for i in range(1, int(math.floor(1.0 / g)) + 1):
        if i > k:
            break
        p += (-1) ** (i - 1) * math.comb(k, i) * (1.0 - i * g) ** (k - 1)
    return g, int(np.argmax(d)) + 1, float(min(1.0, max(0.0, p)))


def fisher_g_p(d):
    """Fisher's exact p-value (Fisher 1929) for the largest of the spacings d against their
    sum, and the 1-based index of that largest spacing."""
    d = np.asarray(d, dtype=np.float64)
    k = d.size
    total = float(d.sum())
    if total <= 0:
        return float('nan'), -1
    g = float(d.max() / total)
    p = 0.0
    for i in range(1, min(k, int(math.floor(1.0 / g))) + 1):
        p += (-1) ** (i - 1) * math.comb(k, i) * (1.0 - i * g) ** (k - 1)
    return float(min(1.0, max(0.0, p))), int(np.argmax(d)) + 1


def spacing_reference(reps=200000, seed=20261003):
    """What an exponential tail gives for the statistics of `gap_stats`: iid exponential
    normalised spacings (Renyi 1953), the largest of the first 50 (or 100) over the mean of
    spacings 101-200. Simulated."""
    rng = np.random.default_rng(seed)
    r50, r100 = [], []
    for _ in range(reps // 20000):
        e = rng.exponential(size=(20000, 200))
        scale = e[:, 100:].mean(axis=1)
        r50.append(e[:, :50].max(axis=1) / scale)
        r100.append(e[:, :100].max(axis=1) / scale)
    r50, r100 = np.concatenate(r50), np.concatenate(r100)
    return {'max50_median': float(np.median(r50)), 'max50_p99': float(np.quantile(r50, 0.99)),
            'max100_median': float(np.median(r100)),
            'max100_p99': float(np.quantile(r100, 0.99)), 'reps': int(r50.size)}


def gap_stats(desc, s, ref):
    """The top of one list against its own tail. desc: the list's values, largest first (at
    least 201); s: the list's 1.4826 MAD; ref: `spacing_reference()`.

    Normalised spacing after rank i: D_i = i (x_(i) - x_(i+1)); under an exponential tail the
    D_i are iid with the tail's scale as mean (Renyi 1953), so the gap the tail predicts after
    rank i is scale / i. The scale is the mean D_i over ranks 101-200, below every rank that
    is tested. A clear break after rank i: D_i / scale above the 99th percentile of the largest
    of 100 such ratios under an exponential tail (simulated). All of it is this scratch's
    construction on Renyi's representation."""
    desc = np.asarray(desc, dtype=np.float64)[:201]
    gaps = desc[:-1] - desc[1:]
    d = np.arange(1, 201) * gaps
    scale = float(d[100:].mean())
    ratio = d[:100] / scale
    out = {'tail_scale_in_s': scale / s,
           'spacing_ratio_ranks_1_50': float(d[:50].mean() / scale),
           'spacing_ratio_ranks_51_100': float(d[50:100].mean() / scale)}
    j = int(np.argmax(gaps[:50]))
    out.update(largest_gap_top50_in_s=float(gaps[j] / s), largest_gap_top50_rank=j + 1,
               largest_gap_top50_predicted_in_s=float(scale / (j + 1) / s),
               largest_gap_top50_over_predicted=float(ratio[j]),
               max_ratio_top50=float(ratio[:50].max()),
               max_ratio_top50_rank=int(np.argmax(ratio[:50])) + 1,
               max_ratio_top100=float(ratio.max()),
               max_ratio_top100_rank=int(np.argmax(ratio)) + 1,
               gap_after_rank1_in_s=float(gaps[0] / s),
               gap_after_rank1_over_predicted=float(ratio[0]))
    clear = np.flatnonzero(ratio > ref['max100_p99'])
    out['clear_breaks_top100'] = int(clear.size)
    out['first_clear_break_rank'] = int(clear[0]) + 1 if clear.size else float('nan')
    clear50 = np.flatnonzero(ratio[:50] > ref['max50_p99'])
    out['clear_breaks_top50'] = int(clear50.size)
    out['first_clear_break_rank_top50'] = int(clear50[0]) + 1 if clear50.size else float('nan')
    p100, at100 = fisher_g_p(d[:100])
    p50, at50 = fisher_g_p(d[:50])
    out.update(fisher_top100_p=p100, fisher_top100_rank=at100, fisher_top50_p=p50,
               fisher_top50_rank=at50)
    return out


def chance_corrected(s_tag_edge, s_edge, edge_chunk, n_chunks):
    """Per chunk: the best path value v = max_i (S_tag_i + S_edge_i) over its edges, the
    probability p of a best path at least that good when the chunk's tags sit at independent
    uniform ranks (S_tag_i exponential) and the edge standings are as observed,
        p = 1 - prod_i (1 - min(1, exp(-(v - S_edge_i)))),
    and the evidence -ln p. The product over the chunk's tags is the exact form of the
    minimum-p correction (Tippett 1931; Sidak 1967); the path value and conditioning on the
    edge standings are the coordinator's construction."""
    v = np.full(n_chunks, -np.inf)
    np.maximum.at(v, edge_chunk, s_tag_edge + s_edge)
    with np.errstate(divide='ignore'):
        q = np.minimum(1.0, np.exp(-(v[edge_chunk] - s_edge)))
        log_none = np.zeros(n_chunks)
        np.add.at(log_none, edge_chunk, np.log1p(-q))
        p = -np.expm1(log_none)
        evidence = -np.log(p)
    return v, p, evidence


def describe(x, top_ranks=(1, 10, 100), central=(0.05, 0.95)):
    """Every statistic of one list (cosines of one probe to all N items)."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    xs = np.sort(x)
    out = {'n': int(n)}
    med = float(np.median(xs))
    s_mad = float(MAD_K * np.median(np.abs(xs - med)))
    mode = half_sample_mode(xs)
    mode_kde, bandwidth = kde_mode(xs)
    low = xs[xs < mode]
    s_mir = float(MAD_K * np.median(mode - low))
    s_mir_rms = float(np.sqrt(np.mean((low - mode) ** 2)))
    q = np.quantile(xs, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    out.update(
        median=med, s_mad=s_mad, mode_hsm=mode, mode_kde=mode_kde,
        mode_minus_median_in_s=(mode - med) / s_mad,
        kde_mode_minus_hsm_in_s=(mode_kde - mode) / s_mad,
        share_below_mode=float(low.size / n),
        s_mirror=s_mir, s_mirror_rms=s_mir_rms, s_mirror_over_s_mad=s_mir / s_mad,
        s_lower_half_median=float(MAD_K * (q[3] - q[2])),
        s_upper_half_median=float(MAD_K * (q[4] - q[3])),
        skewness=float(skew(xs)), excess_kurtosis=float(kurtosis(xs)),
        bowley=float((q[4] + q[2] - 2 * q[3]) / (q[4] - q[2])),
        tail_ratio_99_01=float((q[6] - q[3]) / (q[3] - q[0])),
        minimum=float(xs[0]), maximum=float(xs[-1]),
    )
    a, b = np.quantile(xs, central)
    mu_c, s_c = truncated_normal_mle(xs, a, b, (med, s_mad))
    out.update(central_mle_loc=mu_c, central_mle_scale=s_c,
               central_mle_scale_over_s_mad=s_c / s_mad,
               ks90_mad=ks_truncated_normal(xs, med, s_mad, a, b),
               ks90_mirror=ks_truncated_normal(xs, mode, s_mir, a, b),
               ks90_best_normal=ks_truncated_normal(xs, mu_c, s_c, a, b),
               ks_lower_half_mirror=ks_truncated_normal(xs, mode, s_mir, xs[0] - 1.0, mode),
               ks_kolmogorov_5pct=1.358 / math.sqrt(0.9 * n))
    s_mir_med = float(MAD_K * (q[3] - q[2]))
    out['z_min_mad'] = float((xs[0] - med) / s_mad)
    # mad: median, 1.4826 MAD. mirror: half-sample mode, spread of the values below it.
    # mirror_med: the median as the centre, spread of the lower half only (median - Q1).
    nulls = {'mad': (med, s_mad), 'mirror': (mode, s_mir), 'mirror_med': (med, s_mir_med)}
    universal = math.sqrt(2.0 * math.log(n))
    out['universal_z'] = universal
    arrays = {}
    for name, (loc, scale) in nulls.items():
        z = (xs - loc) / scale
        for r in top_ranks:
            out[f'z_top{r}_{name}'] = float(z[-r]) if n >= r else float('nan')
        out[f'cos_universal_{name}'] = float(loc + scale * universal)
        out[f'n_above_universal_{name}'] = int((z > universal).sum())
        for k in (2, 3, 4):
            expected = n * norm.sf(k)
            out[f'upper_obs_over_exp_z{k}_{name}'] = float((z > k).sum() / expected)
            out[f'lower_obs_over_exp_z{k}_{name}'] = float((z < -k).sum() / expected)
        m, mq, rank = realness(x, loc, scale)
        arrays[name] = m
        arrays[name + '_q'] = mq
        for cut in (0.0, 0.5, 0.9):
            out[f'n_m_gt_{cut}_{name}'] = int((m > cut).sum())
            out[f'n_mq_gt_{cut}_{name}'] = int((mq > cut).sum())
        # the literal m is positive wherever the empirical tail share exceeds the null's, also
        # below the centre; those are counted apart
        out[f'n_m_gt_0_above_centre_{name}'] = int(((m > 0) & (x > loc)).sum())
        out[f'n_m_gt_0_below_centre_{name}'] = int(((m > 0) & (x <= loc)).sum())
        out[f'max_m_below_centre_{name}'] = float(m[x <= loc].max()) if (x <= loc).any() else 0.0
        out[f'n_m_gt_0.05_{name}'] = int((m > 0.05).sum())
        order = np.argsort(-x, kind='stable')
        ms = m[order]
        out[f'm_top1_{name}'] = float(ms[0])
        out[f'm_top10_{name}'] = float(ms[9]) if n >= 10 else float('nan')
        out[f'm_max_{name}'] = float(ms.max())
        out[f'rank_of_max_m_{name}'] = int(np.argmax(ms)) + 1
        # how often the literal m is not monotone in the fit: a worse-fitting item more real
        # than the best-fitting one
        out[f'top1_m_below_max_m_{name}'] = float(ms.max() - ms[0])
    m_local = realness_local(x, med, s_mad)
    for cut in (0.5, 0.9):
        out[f'n_local_gt_{cut}_mad'] = int((m_local > cut).sum())
    for name, centre in (('reflection', mode), ('reflection_med', med)):
        m_ref, m_ref1 = realness_reflection(x, centre)
        arrays[name] = m_ref
        for cut in (0.0, 0.5, 0.9):
            out[f'n_m_gt_{cut}_{name}'] = int((m_ref > cut).sum())
            out[f'n_m_gt_{cut}_{name}_plus1'] = int((m_ref1 > cut).sum())
    out['n_beyond_reflected_minimum'] = int((xs > 2 * mode - xs[0]).sum())
    out['n_beyond_reflected_minimum_med'] = int((xs > 2 * med - xs[0]).sum())
    out['ratio_n_m_gt_0.5_mirror_over_mad'] = (
        out['n_m_gt_0.5_mirror'] / out['n_m_gt_0.5_mad'] if out['n_m_gt_0.5_mad'] else float('nan'))
    for r in top_ranks:
        out[f'cos_top{r}'] = float(xs[-r]) if n >= r else float('nan')
    g, at, p = fisher_g(xs, 100)
    out.update(fisher_g=g, fisher_g_rank=at, fisher_g_p=p,
               gap_top1_top2_in_s_mad=float((xs[-1] - xs[-2]) / s_mad))
    if n > 101:
        # mean excess of the top 100 over the 101st value: the scale of an exponential tail
        # (the maximum-likelihood estimate under the peaks-over-threshold model with shape 0;
        # Pickands 1975, Davison & Smith 1990)
        out['top100_mean_excess_in_s_mad'] = float((xs[-100:].mean() - xs[-101]) / s_mad)
    return out, arrays


def bootstrap_null_spread(x, rng, draws=100):
    """Bootstrap standard deviation (Efron 1979) of each null's centre and scale over resamples
    of the list, in units of the list's own s_mad."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    med0 = np.median(x)
    s0 = MAD_K * np.median(np.abs(x - med0))
    rows = np.empty((draws, 4))
    for b in range(draws):
        xs = np.sort(x[rng.integers(0, n, n)])
        med = np.median(xs)
        mode = half_sample_mode(xs)
        low = xs[xs < mode]
        rows[b] = (med, MAD_K * np.median(np.abs(xs - med)), mode,
                   MAD_K * np.median(mode - low))
    sd = rows.std(axis=0, ddof=1)
    return {'sd_median_in_s': float(sd[0] / s0), 'sd_s_mad_rel': float(sd[1] / s0),
            'sd_mode_in_s': float(sd[2] / s0), 'sd_s_mirror_rel': float(sd[3] / s0)}


def summarise(rows, keys=None):
    """median, min, max of every numeric key over a list of per-list dicts."""
    keys = keys or [k for k in rows[0] if isinstance(rows[0][k], (int, float))]
    summary = {}
    for k in keys:
        v = np.array([r.get(k, float('nan')) for r in rows], dtype=np.float64)
        v = v[np.isfinite(v)]
        if not v.size:
            continue
        summary[k] = {'median': float(np.median(v)), 'min': float(v.min()),
                      'max': float(v.max()), 'p05': float(np.quantile(v, 0.05)),
                      'p95': float(np.quantile(v, 0.95)), 'n': int(v.size)}
    return summary
