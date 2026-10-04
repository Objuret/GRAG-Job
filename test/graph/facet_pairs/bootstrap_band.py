"""The band read off stored bootstrap score matrices, and the pair samples it is read over.

Split out of `bootstrap_scores.py` on 2026-09-21 so that a reader of the band — the arm at
prepare time — needs neither torch nor the fitting siblings. `bootstrap_scores.py` re-exports
every name here, so it stays the one place the band is defined.

Nothing here reads a known facet value, a question or a gold field.
"""
from __future__ import annotations

import numpy as np


def split_chunk_id(edge_id: str) -> str:
    """the chunk half of an edge id — the same partition `data.split_edge_id` performs, kept
    here so this module imports nothing"""
    return edge_id.partition("::")[0]


def pava_nonincreasing(y, w) -> np.ndarray:
    """the weighted least-squares fit of `y` under the one constraint that it never rises
    (pool adjacent violators; Ayer et al. 1955, Barlow et al. 1972).

    No number is chosen: the fit is the projection of the observed rates onto the set of
    non-increasing sequences, with the pair counts as the weights."""
    y = np.asarray(y, dtype=np.float64).ravel()
    w = np.asarray(w, dtype=np.float64).ravel()
    if y.size != w.size:
        raise ValueError(f"y and w differ in length: {y.size} vs {w.size}")
    vals: list = []
    wts: list = []
    cnt: list = []
    for yi, wi in zip(y.tolist(), w.tolist()):
        vals.append(yi)
        wts.append(max(wi, 0.0))
        cnt.append(1)
        while len(vals) > 1 and vals[-2] < vals[-1]:      # a rise: pool the two blocks
            v2, w2, c2 = vals.pop(), wts.pop(), cnt.pop()
            v1, w1, c1 = vals.pop(), wts.pop(), cnt.pop()
            tw = w1 + w2
            vals.append((v1 * w1 + v2 * w2) / tw if tw > 0 else 0.5 * (v1 + v2))
            wts.append(tw)
            cnt.append(c1 + c2)
    out = np.empty(y.size, dtype=np.float64)
    at = 0
    for v, c in zip(vals, cnt):
        out[at:at + c] = v
        at += c
    return out


def flip_gap(values_b: np.ndarray, pairs: np.ndarray, rate: float = 0.05,
             grid: float = 0.01, mode: str = "local", window: int = 2000) -> dict:
    """The smallest difference between two edges that survives retraining.

    `values_b` is [n, B] — one column of the layer, or any weighted combination of columns the
    caller has already formed. `pairs` is [m, 2] of row indices into it.

    For a pair (i, j) and a draw b, d_b = values_b[i, b] - values_b[j, b]. The pair's reference
    sign is the sign of the mean of d over the draws; a flip in draw b is sign(d_b) differing
    from it. At a threshold t only the pairs with |mean d| >= t are considered, and the flip
    rate at t is the mean of the flip indicator over those pairs and over the draws.

    `mode="cumulative"`: the rate at t is taken over every pair beyond t, and the gap is the
    first t on the grid whose rate is below `rate`.
    `mode="local"` (the default, 2026-09-21) asks the question a band needs answered — "two
    edges THIS far apart: how often does a retrain swap them?": at a threshold t the rate is
    taken over the `window` pairs whose |mean d| is nearest above t. `window` is a smoothing
    count, not a band: 2,000 pairs x B draws puts the standard error of a 5% rate under 0.002.
    A local rate read off a finite window wobbles, so the crossing is NOT read off the raw
    curve — a single noise dip below `rate` would name a band narrower than the data supports.
    The curve is first projected onto the non-increasing sequences (pool adjacent violators,
    weights = the window's pair counts, no number chosen), and the gap is the first t whose
    ISOTONIC rate is below `rate`. Both curves are returned.

    Deterministic given `values_b` and `pairs`.
    """
    if mode not in ("local", "cumulative"):
        raise ValueError(f"mode is {mode!r}; local or cumulative")
    if window < 1:
        raise ValueError("window must be at least 1")
    v = np.asarray(values_b, dtype=np.float64)
    pr = np.asarray(pairs, dtype=np.int64)
    if v.ndim != 2:
        raise ValueError(f"values_b must be [n, B], got shape {v.shape}")
    if pr.ndim != 2 or pr.shape[1] != 2:
        raise ValueError(f"pairs must be [m, 2], got shape {pr.shape}")
    if grid <= 0:
        raise ValueError("grid must be positive")
    n, B = v.shape
    if pr.size and (pr.min() < 0 or pr.max() >= n):
        raise ValueError("a pair index is outside values_b")

    sd = v.std(axis=1, ddof=0)
    sd_summary = {"median": float(np.median(sd)) if n else float("nan"),
                  "p90": float(np.percentile(sd, 90)) if n else float("nan")}
    if pr.shape[0] == 0:
        return {"gap": None, "rate": rate, "grid": grid, "n_pairs": 0, "draws": B,
                "mode": mode, "window": int(window), "curve": [], "isotonic": None,
                "retrain_sd": sd_summary}

    d = v[pr[:, 0], :] - v[pr[:, 1], :]                     # [m, B]
    mean_d = d.mean(axis=1)
    ref = np.sign(mean_d)
    flips = (np.sign(d) != ref[:, None])
    per_pair = flips.mean(axis=1)                           # [m]
    am = np.abs(mean_d)

    order = np.argsort(am, kind="stable")
    am_s = am[order]
    pf_s = per_pair[order]
    # suffix sums: suffix[k] is the sum of pf_s[k:]
    suffix = np.concatenate([np.cumsum(pf_s[::-1])[::-1], [0.0]])

    m = pr.shape[0]
    t_max = float(am_s[-1])
    w_eff = max(1, min(int(window), m // 50 if m >= 50 else m))
    ts: list = []
    rates: list = []
    counts: list = []
    step = 0
    while True:
        t = step * grid
        k = int(np.searchsorted(am_s, t, side="left"))
        if mode == "cumulative":
            n_sel = m - k
            r = float(suffix[k] / n_sel) if n_sel else float("nan")
        else:
            hi = min(m, k + w_eff)
            n_sel = hi - k
            if n_sel < max(1, w_eff // 4):        # too few pairs left to read a rate from
                n_sel = 0
            r = float((suffix[k] - suffix[hi]) / n_sel) if n_sel else float("nan")
        if n_sel == 0:
            break               # past the last window the sample can answer for
        ts.append(round(t, 10))
        rates.append(r)
        counts.append(int(n_sel))
        if t > t_max:
            break
        step += 1
    if not ts:
        return {"gap": None, "rate": rate, "grid": grid, "n_pairs": m, "draws": B,
                "mode": mode, "window": int(window), "curve": [], "isotonic": None,
                "retrain_sd": sd_summary}

    raw = np.asarray(rates, dtype=np.float64)
    cnt = np.asarray(counts, dtype=np.float64)
    usable = (cnt > 0) & np.isfinite(raw)
    iso = np.full(raw.size, np.nan, dtype=np.float64)
    if usable.any():
        iso[usable] = pava_nonincreasing(raw[usable], cnt[usable])
    read = iso if mode == "local" else raw
    gap = None
    for i in range(raw.size):
        if counts[i] and np.isfinite(read[i]) and read[i] < rate:
            gap = ts[i]
            break
    curve = [{"t": ts[i], "flip_rate": rates[i], "n_pairs": counts[i]} for i in range(len(ts))]
    iso_curve = (None if mode != "local" else
                 [{"t": ts[i], "flip_rate": (None if not np.isfinite(iso[i]) else float(iso[i])),
                   "n_pairs": counts[i]} for i in range(len(ts))])
    return {"gap": gap, "rate": rate, "grid": grid, "n_pairs": m, "draws": B, "mode": mode,
            "window": int(window), "curve": curve, "isotonic": iso_curve,
            "retrain_sd": sd_summary}


def sample_any_pairs(n_edges: int, m: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.integers(0, n_edges, m)
    b = rng.integers(0, n_edges, m)
    same = a == b
    while same.any():
        b[same] = rng.integers(0, n_edges, int(same.sum()))
        same = a == b
    return np.stack([a, b], axis=1).astype(np.int64)


def sample_same_chunk_pairs(edge_ids: list, m: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    by: dict = {}
    for i, e in enumerate(edge_ids):
        by.setdefault(split_chunk_id(e), []).append(i)
    groups = [np.asarray(v, dtype=np.int64) for k, v in sorted(by.items()) if len(v) >= 2]
    if not groups:
        return np.zeros((0, 2), dtype=np.int64)
    gi = rng.integers(0, len(groups), m)
    a = np.empty(m, dtype=np.int64)
    b = np.empty(m, dtype=np.int64)
    for k in range(m):
        g = groups[int(gi[k])]
        two = rng.choice(len(g), 2, replace=False)
        a[k], b[k] = g[two[0]], g[two[1]]
    return np.stack([a, b], axis=1)
