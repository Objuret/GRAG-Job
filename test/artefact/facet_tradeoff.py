"""Experimental query-conditioned combination fitting; not wired to retrieval.

The inputs are measured features, not automatically commensurate utilities.
Coefficients are estimated from separate query-conditioned preferences. A
nonnegative additive model is an explicit hypothesis, not a semantic identity.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp


def comparison_probabilities(difference, coefficients, tie_log):
    d, b = np.asarray(difference, dtype=float), np.asarray(coefficients, dtype=float)
    if d.ndim != 2 or b.shape != (d.shape[1],) or not np.isfinite(d).all() or not np.isfinite(b).all() or not np.isfinite(tie_log):
        raise ValueError("finite aligned matrix and coefficients required")
    h = d @ b / 2
    logits = np.column_stack([h, -h, np.full(len(h), tie_log)])
    return np.exp(logits-logsumexp(logits, axis=1, keepdims=True))


def fit_nonnegative(difference, outcomes, *, l2, sample_weight=None):
    """Convex Davidson likelihood with nonnegative coefficients and L2 penalty.

Outcome 0=first, 1=second, 2=equal. The tie logit has no sign constraint. L2
penalizes both coefficients and tie logit, ensuring a finite fit for separable
or all-tie data. Select the positive penalty using independent grouped folds.
"""
    d, y = np.asarray(difference, dtype=float), np.asarray(outcomes)
    if d.ndim != 2 or not d.shape[0] or not d.shape[1] or y.shape != (len(d),) or not np.isfinite(d).all() or not np.isin(y, [0, 1, 2]).all() or not np.isfinite(l2) or l2 <= 0:
        raise ValueError("finite nonempty aligned observations and positive penalty required")
    weights = np.ones(len(d)) if sample_weight is None else np.asarray(sample_weight, dtype=float)
    if weights.shape != (len(d),) or not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError("nonnegative observation mass required")
    weights = weights/weights.sum()
    y = y.astype(int)
    target = np.eye(3)[y]

    def objective(theta):
        h = d @ theta[:-1]/2
        logits = np.column_stack([h, -h, np.full(len(h), theta[-1])])
        lp = logits-logsumexp(logits, axis=1, keepdims=True)
        residual = (np.exp(lp)-target)*weights[:, None]
        gradient = np.r_[d.T @ (residual[:, 0]-residual[:, 1])/2, residual[:, 2].sum()]
        loss = -(weights*lp[np.arange(len(y)), y]).sum() + l2*(theta@theta)/2
        return float(loss), gradient+l2*theta

    r = minimize(objective, np.zeros(d.shape[1]+1), jac=True, method="L-BFGS-B",
                 bounds=[(0., None)]*d.shape[1]+[(None, None)],
                 options={"ftol": 1e-12, "gtol": 1e-8, "maxiter": 2000, "maxls": 100})
    if not r.success or not np.isfinite(r.x).all():
        raise RuntimeError(f"fit failed: {r.message}; coefficients={r.x}; gradient={r.jac}")
    return {"coefficients": r.x[:-1].tolist(), "tie_log": float(r.x[-1]),
            "l2": float(l2), "objective": float(r.fun), "optimizer": str(r.message)}


def query_edge_products(query, edge):
    q, e = np.asarray(query, dtype=float), np.asarray(edge, dtype=float)
    if q.shape != e.shape or not np.isfinite(q).all() or not np.isfinite(e).all():
        raise ValueError("finite aligned query and edge arrays required")
    return q*e


def crossfit_nonnegative(difference, outcomes, groups, *, penalties, sample_weight=None):
    """Nested leave-one-group-out selection; returns only outer test predictions.

Every group is excluded as a whole. Penalty choice uses inner held-out groups
among the remaining groups, with equal mass per inner group. This does not make
groups independent when the data collection shares templates or a single judge.
"""
    d, y, g = np.asarray(difference, dtype=float), np.asarray(outcomes), np.asarray(groups)
    mass = np.ones(len(y)) if sample_weight is None else np.asarray(sample_weight, dtype=float)
    domains = sorted(set(g.tolist()))
    if d.ndim != 2 or y.shape != (len(d),) or g.shape != y.shape or mass.shape != y.shape or len(domains) < 3 or not len(penalties):
        raise ValueError("aligned inputs and at least three groups required")
    probabilities, gap, folds = np.empty((len(y), 3)), np.empty(len(y)), []
    for excluded in domains:
        train, test = g != excluded, g == excluded
        candidates = []
        for penalty in penalties:
            losses = []
            for validation in domains:
                if validation == excluded:
                    continue
                inner_fit = train & (g != validation)
                inner_val = train & (g == validation)
                m = fit_nonnegative(d[inner_fit], y[inner_fit], l2=penalty, sample_weight=mass[inner_fit])
                p = comparison_probabilities(d[inner_val], m["coefficients"], m["tie_log"])
                loss = -(mass[inner_val]*np.log(np.maximum(p[np.arange(inner_val.sum()), y[inner_val]], 1e-300))).sum()/mass[inner_val].sum()
                losses.append(float(loss))
            candidates.append({"l2": penalty, "inner_domain_mean_log_loss": float(np.mean(losses))})
        selected = min(candidates, key=lambda r:r["inner_domain_mean_log_loss"])["l2"]
        m = fit_nonnegative(d[train], y[train], l2=selected, sample_weight=mass[train])
        probabilities[test] = comparison_probabilities(d[test], m["coefficients"], m["tie_log"])
        gap[test] = d[test] @ m["coefficients"]
        folds.append({"excluded_domain": excluded, "model": m, "inner_selection": candidates})
    return {"probabilities": probabilities, "gap": gap, "folds": folds}
