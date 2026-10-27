"""The login's sonnet backlog per call (tokens sent above a steady refill R, charged at each start and paid
back at R per second), R fitted on a fine grid, the bend fitted by a hinge; then each arm's clean relation
(server seconds = a + b * output tokens) on the calls before the bend, answer calls and first calls apart;
the arms compared at the same lengths; the 715's own clean calls against the hundred's relation; and the
calls picked for the check: per arm, calls past the bend spread over their output length. Reads the
per-call table; makes no model call."""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
calls = json.loads((HERE / "load_per_call.json").read_text(encoding="utf-8"))
son = sorted([c for c in calls if "sonnet" in c["model"]], key=lambda c: c["start"])
t = np.array([c["start"] for c in son]); tok = np.array([c["in"] for c in son], dtype=float)


def backlog(R):
    A, out, prev = 0.0, np.empty(len(son)), t[0]
    for k in range(len(son)):
        A = max(0.0, A - R * (t[k] - prev)) + tok[k]; prev = t[k]
        out[k] = A
    return out


def ranks(x):
    return np.argsort(np.argsort(x, kind="stable"), kind="stable").astype(float)


def rc(x, y):
    return float(np.corrcoef(ranks(x), ranks(y))[0, 1])


ans = np.array([i for i, c in enumerate(son) if c["role"] == "answer" and c["ok"] and c["per1k"]])
fst = np.array([i for i, c in enumerate(son) if c["role"] is None and c["ok"] and c["per1k"]])
y, yf = np.array([son[i]["per1k"] for i in ans]), np.array([son[i]["per1k"] for i in fst])
grid = [(rc(backlog(R)[ans], y), R) for R in range(10000, 22001, 500)]
best_r, R = max(grid)
print("rank corr by refill R (answers):", " ".join(f"{R_ // 1000:g}k:{r:.3f}" for r, R_ in grid[::2]))
A = backlog(R)
print(f"best R = {R} tokens/s (rank corr answers {best_r:.3f}, first calls {rc(A[fst], yf):+.3f})")


def hinge(x, yl):
    best = None
    for x0 in np.quantile(x, np.linspace(0.05, 0.95, 181)):
        X = np.column_stack([np.ones_like(x), np.maximum(0, x - x0)])
        coef, *_ = np.linalg.lstsq(X, yl, rcond=None)
        sse = float(((X @ coef - yl) ** 2).sum())
        if best is None or sse < best[0]:
            best = (sse, float(x0), coef)
    return best


_, bend, coef = hinge(A[ans], np.log(y))
rng = np.random.default_rng(0)
boots = [hinge(A[ans][b], np.log(y)[b])[1] for b in (rng.integers(0, len(ans), len(ans)) for _ in range(300))]
lo5, hi95 = np.percentile(boots, 5), np.percentile(boots, 95)
print(f"bend at a backlog of {bend:,.0f} tokens (bootstrap 5-95%: {lo5:,.0f} to {hi95:,.0f}); level before it {np.exp(coef[0]):.1f} s per 1,000 tokens")
for cut, name in ((bend, "bend"), (lo5, "bend's lower 5% end")):
    fa = A[ans] >= cut
    print(f"   by the {name}: answers past it {fa.sum()} | median s/1k past {np.median(y[fa]):.1f}, before {np.median(y[~fa]):.1f} | before it but over 30: {int(((~fa) & (y > 30)).sum())} | past it and under 20: {int((fa & (y < 20)).sum())}")
for i, c in enumerate(son):
    c["backlog"], c["past"] = float(A[i]), bool(A[i] >= bend)

ARM = {"lucene100": "lucene", "lucene715": "lucene", "vector100": "vector", "vector715": "vector",
       "artefact100": "artefact", "artefact715": "artefact", "artefact100_first_calls": "artefact"}


def rows(kind, arm, past=None, finals=None):
    return [c for c in son if c["final"] in ARM and ARM[c["final"]] == arm and (finals is None or c["final"] in finals)
            and (c["role"] == "answer" if kind == "answer" else c["role"] is None)
            and c["ok"] and c["server"] > 0 and c["out"] > 0 and (past is None or c["past"] == past)
            and not (kind == "answer" and c["final"] == "artefact100_first_calls")]


def fit(rs):
    x = np.array([c["out"] for c in rs], float); s = np.array([c["server"] for c in rs])
    b, a = np.polyfit(x, s, 1)
    loo = [abs(s[k] - np.polyval(np.polyfit(np.delete(x, k), np.delete(s, k), 1), x[k])) for k in range(len(x))]
    return float(a), float(b), float(np.median(loo)), float(np.percentile(loo, 90))


rel = {}
print("\n== clean relations (calls before the bend): server s = a + b per 1,000 output tokens; leave-one-out |error| median, p90")
for kind in ("answer", "first"):
    for arm in ("lucene", "vector", "artefact"):
        rs = rows(kind, arm, past=False)
        if len(rs) < 10:
            continue
        a, b, e50, e90 = fit(rs)
        rel[(kind, arm)] = (a, b)
        lens = [c["out"] for c in rs]
        print(f"   {kind:6} {arm:8} n={len(rs):4} (from {sorted({c['final'] for c in rs})}) | a {a:5.2f} s, b {b * 1000:5.2f} s per 1,000 | LOO {e50:.2f}, {e90:.2f} s | output tokens median {np.median(lens):.0f}, range {min(lens)}-{max(lens)}")

print("\n== the arms' answer relations at the same lengths (seconds), bootstrap 5-95%")
for L in (200, 400, 800, 1500):
    line = []
    for arm in ("lucene", "vector", "artefact"):
        rs = rows("answer", arm, past=False)
        x = np.array([c["out"] for c in rs], float); s = np.array([c["server"] for c in rs])
        bs = []
        for _ in range(300):
            k = rng.integers(0, len(x), len(x))
            bb, aa = np.polyfit(x[k], s[k], 1); bs.append(aa + bb * L)
        a, b = rel[("answer", arm)]
        line.append(f"{arm} {a + b * L:5.2f} ({np.percentile(bs, 5):.2f}-{np.percentile(bs, 95):.2f})")
    print(f"   {L:5} tokens: " + " | ".join(line))

print("\n== the 715's own clean answer calls against the relation from the hundred (drift check): residual median, n")
for arm, h, n7 in (("lucene", "lucene100", "lucene715"), ("vector", "vector100", "vector715"), ("artefact", "artefact100", "artefact715")):
    rs_h = rows("answer", arm, past=False, finals={h}); rs_7 = rows("answer", arm, past=False, finals={n7})
    if len(rs_h) >= 10 and rs_7:
        a, b, *_ = fit(rs_h)
        res = [c["server"] - (a + b * c["out"]) for c in rs_7]
        print(f"   {arm:8} hundred n={len(rs_h)}, 715 clean n={len(rs_7)}: residual median {np.median(res):+.2f} s, |res| median {np.median(np.abs(res)):.2f}")
    else:
        print(f"   {arm:8} hundred clean n={len(rs_h)}, 715 clean n={len(rs_7)}: too few to compare")

print("\n== past the bend, per final run (answer calls | first calls)")
for f in ("lucene100", "vector100", "artefact100", "artefact100_first_calls", "lucene715", "vector715", "artefact715"):
    rs = [c for c in son if c["final"] == f]
    print(f"   {f:24} answers {sum(c['past'] for c in rs if c['role'] == 'answer')} of {sum(c['role'] == 'answer' for c in rs)}"
          f" | first calls {sum(c['past'] for c in rs if c['role'] is None)} of {sum(c['role'] is None for c in rs)}")


def spread(rs, n):
    rs = sorted(rs, key=lambda c: c["out"])
    return [rs[int(k * (len(rs) - 1) / (n - 1))] for k in range(n)] if len(rs) > n else rs


pick = []
for arm in ("lucene", "vector", "artefact"):
    pick += [{"final": c["final"], "id": c["id"], "role": "answer", "start": c["start"], "out": c["out"], "server": c["server"]}
             for c in spread(rows("answer", arm, past=True), 25)]
pick += [{"final": c["final"], "id": c["id"], "role": None, "start": c["start"], "out": c["out"], "server": c["server"]}
         for c in spread(rows("first", "artefact", past=True), 10)]
(HERE / "check_selection.json").write_text(json.dumps({"R": R, "bend": bend, "bend_5_95": [lo5, hi95],
                                                        "relations": {f"{k}|{a}": v for (k, a), v in rel.items()}, "calls": pick}, indent=1), encoding="utf-8")
print(f"\npicked for the check: {len(pick)} calls past the bend, spread over length (25 answers per arm, 10 first calls) -> check_selection.json")
