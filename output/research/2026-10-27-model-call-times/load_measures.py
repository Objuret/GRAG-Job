"""Which measure of the login's sonnet load explains the sonnet calls' slowdown: the sonnet input tokens
over windows of 0.5 to 30 minutes before each start, the sonnet calls in flight at the start, and a token
bucket (refill R tokens/s, capacity C tokens) charged at each call's start. Rank correlation of each with
the server seconds per 1,000 output tokens, fitted on the answer calls and checked on the first calls;
then the band table of the best measure and a hinge fit of where its curve bends, with a bootstrap
interval. Reads the per-call table written by load_per_call.py; makes no model call."""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
calls = json.loads((HERE / "load_per_call.json").read_text(encoding="utf-8"))
son = sorted([c for c in calls if "sonnet" in c["model"]], key=lambda c: c["start"])
starts = np.array([c["start"] for c in son]); ends = np.array([c["end"] for c in son])
tok = np.array([c["in"] for c in son], dtype=float)
pref = np.concatenate([[0.0], np.cumsum(tok)])
idx = np.arange(len(son))


def window(w):
    j = np.searchsorted(starts, starts - w, side="right")
    return (pref[idx + 1] - pref[j]) / w


def in_flight():
    return (idx + 1) - np.searchsorted(np.sort(ends), starts, side="right")


def bucket(R, C):
    level, t, out = C, starts[0], np.empty(len(son))
    for k in range(len(son)):
        level = min(C, level + R * (starts[k] - t)); t = starts[k]
        level -= tok[k]
        out[k] = -level          # the bucket's deficit after the call is charged: larger = deeper in the limit
    return out


def ranks(x):
    return np.argsort(np.argsort(x, kind="stable"), kind="stable").astype(float)


def rc(x, y):
    return float(np.corrcoef(ranks(x), ranks(y))[0, 1])


ans = np.array([i for i, c in enumerate(son) if c["role"] == "answer" and c["ok"] and c["per1k"]])
first = np.array([i for i, c in enumerate(son) if c["role"] is None and c["ok"] and c["per1k"]])
y, yf = np.array([son[i]["per1k"] for i in ans]), np.array([son[i]["per1k"] for i in first])
print(f"sonnet calls: {len(son)}; answer calls with a server time: {len(ans)}; first calls with one: {len(first)}")

measures = {}
for w in (30, 60, 120, 180, 300, 600, 900, 1200, 1800):
    measures[f"tokens/s over {w / 60:g} min"] = window(w)
measures["calls in flight"] = in_flight().astype(float)
grid = []
for R in range(4000, 26001, 2000):
    for C in (2.5e5, 5e5, 1e6, 2e6, 4e6, 8e6, 1.6e7, 3.2e7):
        m = bucket(R, C)
        grid.append((rc(m[ans], y), R, C))
grid.sort(reverse=True)
print("bucket grid, best five (rank corr on answers, R tokens/s, C tokens):", [(round(r, 3), R, f"{C:.1e}") for r, R, C in grid[:5]])
_, R, C = grid[0]
measures[f"bucket R={R} C={C:.1e}"] = bucket(R, C)
print(f"\n{'measure':32} rank corr with s per 1,000 tokens: answer calls | first calls")
for name, m in measures.items():
    print(f"{name:32} {rc(m[ans], y):+.3f} | {rc(m[first], yf):+.3f}")

best = max(measures, key=lambda k: rc(measures[k][ans], y))
m = measures[best]
print(f"\n== best on the answer calls: {best}; band table (answer calls)")
qs = np.quantile(m[ans], np.linspace(0, 1, 13))
for lo_, hi_ in zip(qs[:-1], qs[1:]):
    s = y[(m[ans] >= lo_) & (m[ans] <= hi_)]
    print(f"   {lo_:12,.0f} to {hi_:12,.0f}: {len(s):4} | median {np.median(s):6.1f} | p75 {np.percentile(s, 75):6.1f} | p90 {np.percentile(s, 90):6.1f}")


def hinge(x, yl):
    best_ = None
    for x0 in np.quantile(x, np.linspace(0.05, 0.95, 91)):
        X = np.column_stack([np.ones_like(x), np.maximum(0, x - x0)])
        coef, *_ = np.linalg.lstsq(X, yl, rcond=None)
        sse = float(((X @ coef - yl) ** 2).sum())
        if best_ is None or sse < best_[0]:
            best_ = (sse, float(x0), coef)
    return best_


for name in (best, "tokens/s over 1 min"):
    x = measures[name][ans]; yl = np.log(y)
    sse, x0, coef = hinge(x, yl)
    rng = np.random.default_rng(0)
    boots = [hinge(x[b], yl[b])[1] for b in (rng.integers(0, len(x), len(x)) for _ in range(200))]
    print(f"\nhinge fit on log(s per 1,000 tokens) against {name}: bends at {x0:,.0f} (bootstrap 5-95%: {np.percentile(boots, 5):,.0f} to {np.percentile(boots, 95):,.0f});"
          f" flat level {np.exp(coef[0]):.1f} s per 1,000 tokens")
    flag_a, flag_f = measures[name][ans] >= x0, measures[name][first] >= x0
    print(f"   answer calls at or past the bend: {flag_a.sum()} of {len(ans)} | s per 1,000 tokens median, past: {np.median(y[flag_a]):.1f}, before: {np.median(y[~flag_a]):.1f}"
          f" | before the bend but over 30: {int(((~flag_a) & (y > 30)).sum())} | past the bend and under 20: {int((flag_a & (y < 20)).sum())}")
    print(f"   first calls at or past the bend: {flag_f.sum()} of {len(first)} | median past {np.median(yf[flag_f]) if flag_f.any() else float('nan'):.1f}, before {np.median(yf[~flag_f]):.1f}")
    for f in ("lucene100", "vector100", "artefact100", "artefact100_first_calls", "lucene715", "vector715", "artefact715"):
        sel = [k for k, i in enumerate(idx) if son[i]["final"] == f]
        if not sel:
            continue
        mm = measures[name][sel]
        roles = [son[i]["role"] for i in sel]
        a = sum(1 for k, r in zip(mm, roles) if k >= x0 and r == "answer"); fc = sum(1 for k, r in zip(mm, roles) if k >= x0 and r is None)
        print(f"   {f:24} past the bend: answer calls {a} of {roles.count('answer')}, first calls {fc} of {roles.count(None)}")
