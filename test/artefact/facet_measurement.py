"""Experimental facet measurement primitives; not connected to retrieval.

Probabilities concern a specified comparison judge. Reference scores concern a
specified reference population. Neither is automatically query relevance or utility.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp


def probabilities(gap, alpha: float, log_nu: float):
    gap = np.asarray(gap, dtype=float)
    if not np.isfinite(gap).all() or not np.isfinite([alpha, log_nu]).all() or alpha < 0:
        raise ValueError("finite scores and nonnegative alpha are required")
    h = alpha * gap / 2
    logits = np.stack([h, -h, np.full_like(h, log_nu)], axis=-1)
    return np.exp(logits - logsumexp(logits, axis=-1, keepdims=True))


def fit_calibration(gap, outcome, sample_weight=None):
    """Fit nonnegative slope and tie logit by convex weighted log loss.

Outcome is 0=A, 1=B, 2=tie. Positive slope preserves direction. Slope zero
explicitly means the fitted comparison data support no directional resolution.
No directional intercept is fitted, preserving exchange symmetry.
"""
    gap, y = np.asarray(gap, dtype=float), np.asarray(outcome)
    w = np.ones(gap.shape) if sample_weight is None else np.asarray(sample_weight, dtype=float)
    if (gap.ndim != 1 or gap.size == 0 or y.shape != gap.shape or w.shape != gap.shape
            or not np.isfinite(gap).all() or not np.isfinite(w).all()
            or (w < 0).any() or w.sum() <= 0 or not np.isin(y, [0, 1, 2]).all()):
        raise ValueError("nonempty aligned observations and nonnegative weights required")
    y = y.astype(int)
    if len(np.unique(y[w > 0])) < 3:
        raise ValueError("all three outcomes needed for a finite unconstrained tie calibration")
    w = w / w.sum()
    target = np.eye(3)[y]

    def loss_grad(theta):
        alpha, eta = theta
        h = alpha * gap / 2
        logits = np.column_stack([h, -h, np.full_like(h, eta)])
        lp = logits - logsumexp(logits, axis=1, keepdims=True)
        residual = np.exp(lp) - target
        loss = -(w * lp[np.arange(len(y)), y]).sum()
        grad = np.array([(w * gap / 2 * (residual[:, 0] - residual[:, 1])).sum(),
                         (w * residual[:, 2]).sum()])
        return float(loss), grad

    result = minimize(loss_grad, [1., 0.], jac=True, method="L-BFGS-B",
                      bounds=[(0., None), (None, None)],
                      options={"ftol": 1e-12, "gtol": 1e-8, "maxiter": 1000})
    if not result.success or not np.isfinite(result.x).all():
        raise RuntimeError(f"calibration failed: {result.message}")
    return {"alpha": float(result.x[0]), "log_nu": float(result.x[1]),
            "fit_nll": float(result.fun), "optimizer": str(result.message),
            "gradient": result.jac.tolist(), "n": len(y)}


def reference_score_bounds(values, references, reference_weight, *, alpha, log_nu, bins=1024):
    """Bound E[P(x beats anchor) + .5 P(tie)] with quantile quadrature.

The population and its weights are fixed by the caller. Returns lower/upper
NUMERICAL integration bounds, not confidence intervals. Monotonicity of the
comparison score in anchor score gives interval width <= 1/bins, independent
of the input score distribution. The bin count controls numerical precision.
"""
    x = np.asarray(values, dtype=float)
    ref, w = np.asarray(references, dtype=float), np.asarray(reference_weight, dtype=float)
    if (x.ndim != 1 or ref.ndim != 1 or ref.size == 0 or w.shape != ref.shape
            or not np.isfinite(x).all() or not np.isfinite(ref).all()
            or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0
            or not isinstance(bins, int) or bins < 1):
        raise ValueError("finite vectors, positive reference mass and positive integer bins required")
    keep = w > 0
    ref, w = ref[keep], w[keep]
    order = np.argsort(ref, kind="stable")
    ref, w = ref[order], w[order]
    cumulative = np.cumsum(w / w.sum())
    cumulative[-1] = 1.
    anchors = ref[np.clip(np.searchsorted(cumulative, np.linspace(0, 1, bins + 1),
                                         side="left"), 0, ref.size - 1)]
    lower, upper = np.empty(x.size), np.empty(x.size)
    for start in range(0, len(x), 256):
        stop = start + 256
        p = probabilities(x[start:stop, None] - anchors[None, :], alpha, log_nu)
        win_score = p[..., 0] + .5 * p[..., 2]
        lower[start:stop] = win_score[:, 1:].mean(axis=1)
        upper[start:stop] = win_score[:, :-1].mean(axis=1)
    return lower, upper


def ordered_weight_difference_bounds(differences):
    """Exact score-difference range for w1>=...>=wm>=0, sum(w)=1.

Input differences must already be on justified marginal value scales, ordered
by justified weight priority. This does NOT infer utility from facet names or
turn query-tag relevance into importance. Extremes occur at uniform prefixes.
"""
    d = np.asarray(differences, dtype=float)
    if d.ndim != 1 or not d.size or not np.isfinite(d).all():
        raise ValueError("a finite nonempty difference vector is required")
    prefix = np.cumsum(d) / np.arange(1, d.size + 1)
    return float(prefix.min()), float(prefix.max())
