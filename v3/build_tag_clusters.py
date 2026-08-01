"""Build the artefact arm's cluster-guide cache: five per-facet fuzzy
membership matrices over the tag pool.

Reads every tag reachable through HAS_TAG under the arm's tagging run —
`t.emb` (unit-norm) plus each edge's `facets` array — sorted by name, the
determinism anchor. Per facet, a tag's participation ω is the fraction of its
edges carrying that facet, floored to ω̃ = λ + (1 − λ)·ω so no tag is
invisible to any facet's fit. One shared k-means++ init (D² seeding on cosine
distance, uniform weights, fixed seed) starts all five fits; each facet runs
weighted spherical k-means — objective Σ_t ω̃·(1 − x_t·v), prototypes the
L2-normalized ω̃-weighted means — and its matrix is the fuzzy membership of
every tag over the fitted prototypes (fuzzifier m, rows summing to 1).

Cache entry: output/tag_cluster_cache/<db>__<run>__C…__m…__lam…__seed…/ holding
memberships.npz (the five float32 n×C matrices in facet order), tags.json
(the row order), manifest.json (constants + n_tags + per-facet convergence
iters, written last as the completeness marker). The entry is keyed by the
constants: a re-run with the same constants skips, changed constants build a
sibling entry. Deterministic, no model calls.

Run with Neo4j up and NEO4J_PASSWORD in v3/.env:

    python build_tag_clusters.py
    HERB_STR_GUIDE=0.4 python run.py --arm artefact_v1_det --set gold -k 50
"""
from __future__ import annotations

if __name__ == "__main__":
    print("build_tag_clusters: per-facet membership matrices over the tag pool "
          "— loading numpy + neo4j …", flush=True)

import json
import time

import numpy as np

from pipelines.artefact_v1 import (
    ALL_FACETS, DATABASE, GUIDE_C, GUIDE_CACHE_DIR, GUIDE_LAMBDA, GUIDE_M,
    GUIDE_SEED, RUN_ID, _driver, _guide_key, _unit,
)
from progress import progress

MAX_ITER = 60
TOL = 1e-7

_FACET_COL = {f: i for i, f in enumerate(ALL_FACETS)}


def facet_participation(edge_facets: list) -> np.ndarray:
    """Per-tag facet participation ω, an (n_tags, n_facets) matrix: row t,
    column f = the fraction of tag t's edges whose facets array contains
    ALL_FACETS[f]."""
    omega = np.zeros((len(edge_facets), len(ALL_FACETS)))
    for t, edges in enumerate(edge_facets):
        for arr in edges:
            for f in set(arr or ()):
                if f in _FACET_COL:
                    omega[t, _FACET_COL[f]] += 1.0
        omega[t] /= len(edges)
    return omega


def floor_participation(omega: np.ndarray, lam: float) -> np.ndarray:
    """The floored participation ω̃ = λ + (1 − λ)·ω: every tag keeps at least
    λ weight in every facet's fit, so a facet a tag never carries still places
    it instead of leaving it unconstrained."""
    return lam + (1.0 - lam) * omega


def kmeanspp_init(X: np.ndarray, C: int, seed: int, bar=None) -> np.ndarray:
    """k-means++ prototypes over unit rows: D² seeding on cosine distance,
    uniform weights. The first prototype is a seeded uniform draw; each next
    is drawn with probability proportional to the squared cosine distance to
    its nearest prototype so far."""
    if C > len(X):
        raise ValueError(f"C={C} exceeds the {len(X)}-tag pool")
    rng = np.random.default_rng(seed)
    V = np.empty((C, X.shape[1]), dtype=X.dtype)
    V[0] = X[rng.integers(len(X))]
    d = np.maximum(1.0 - X @ V[0], 0.0)
    if bar is not None:
        bar.update(1)
    for c in range(1, C):
        p = d * d
        total = p.sum()
        idx = rng.choice(len(X), p=p / total) if total > 0 else rng.integers(len(X))
        V[c] = X[idx]
        np.minimum(d, np.maximum(1.0 - X @ V[c], 0.0), out=d)
        if bar is not None:
            bar.update(1)
    return V


def weighted_spherical_kmeans(X: np.ndarray, w: np.ndarray, init: np.ndarray,
                              max_iter: int = MAX_ITER, tol: float = TOL,
                              bar=None) -> tuple:
    """Weighted spherical k-means from a shared init -> (prototypes, Lloyd
    iterations run). Objective Σ_t w_t·(1 − x_t·v_c(t)). Assignment is the
    nearest prototype by cosine, ties to the lowest prototype index; each
    prototype updates to the L2-normalized w-weighted mean of its members, an
    empty cluster keeping its previous prototype. Stops when the objective
    moves less than `tol`, or at `max_iter`."""
    V = init.copy()
    n = len(X)
    prev = None
    for it in range(1, max_iter + 1):
        sims = X @ V.T
        assign = np.argmax(sims, axis=1)
        obj = float((w * (1.0 - sims[np.arange(n), assign])).sum())
        if bar is not None:
            bar.update(1)
        if prev is not None and abs(prev - obj) < tol:
            return V, it
        prev = obj
        wx = np.zeros_like(V)
        np.add.at(wx, assign, X * w[:, None])
        norms = np.linalg.norm(wx, axis=1)
        live = norms > 0
        V[live] = wx[live] / norms[live, None]
    return V, max_iter


def memberships(X: np.ndarray, V: np.ndarray, m: float) -> np.ndarray:
    """Fuzzy membership of every row of X over the prototypes, float32 rows
    summing to 1: d_c = max(1 − x·v_c, 1e-6), u_c = d_c^(−2/(m−1)) / Σ_c′
    d_c′^(−2/(m−1))."""
    d = np.maximum(1.0 - X @ V.T, 1e-6)
    p = d ** (-2.0 / (m - 1.0))
    return (p / p.sum(axis=1, keepdims=True)).astype(np.float32)


def fetch_tags(s) -> tuple:
    """The tag pool under the arm's tagging run, sorted by name -> (names,
    unit-norm embedding matrix, facet participation ω). A reachable tag
    without `t.emb` fails loud — the semantic layer must be complete."""
    recs = list(s.run(
        "MATCH (t:Tag)<-[r:HAS_TAG]-(:Chunk) WHERE r.run_id = $runId "
        "RETURN t.name AS name, t.emb AS emb, "
        "collect(coalesce(r.facets, [])) AS edgeFacets ORDER BY name",
        runId=RUN_ID))
    if not recs:
        raise SystemExit(f"no :Tag reachable via HAS_TAG run_id={RUN_ID!r} in {DATABASE!r}")
    missing = [r["name"] for r in recs if r["emb"] is None]
    if missing:
        raise SystemExit(
            f"{len(missing)} tag(s) without t.emb (e.g. {missing[:5]}) — "
            f"run `python reembed_herb_eval.py` once.")
    names = [r["name"] for r in recs]
    X = _unit(np.asarray([r["emb"] for r in recs], dtype=np.float64))
    return names, X, facet_participation([r["edgeFacets"] for r in recs])


def main() -> None:
    t0 = time.perf_counter()
    entry = GUIDE_CACHE_DIR / _guide_key()
    if (entry / "manifest.json").is_file():
        print(f"cache entry {entry.name} already complete — skipping "
              f"(change a HERB_GUIDE_* constant for a new entry).", flush=True)
        return
    print(f"reading the tag pool from {DATABASE!r} (run_id={RUN_ID!r}) …", flush=True)
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            names, X, omega = fetch_tags(s)
    finally:
        drv.close()
    print(f"  {len(names)} tags, dim={X.shape[1]}", flush=True)

    bar = progress(total=GUIDE_C, desc="k-means++ init", unit="proto")
    init = kmeanspp_init(X, GUIDE_C, GUIDE_SEED, bar=bar)
    bar.close()
    print(f"shared init ready (C={GUIDE_C}, seed={GUIDE_SEED})", flush=True)

    floored = floor_participation(omega, GUIDE_LAMBDA)
    mats, iters = {}, {}
    for fi, facet in enumerate(ALL_FACETS):
        bar = progress(total=MAX_ITER, desc=f"fit {facet}", unit="iter")
        V, it = weighted_spherical_kmeans(X, floored[:, fi], init, bar=bar)
        bar.close()
        mats[facet] = memberships(X, V, GUIDE_M)
        iters[facet] = it
        print(f"  {facet}: {it} Lloyd iters", flush=True)

    entry.mkdir(parents=True, exist_ok=True)
    np.savez(entry / "memberships.npz", **mats)
    (entry / "tags.json").write_text(json.dumps(names, ensure_ascii=False),
                                     encoding="utf-8")
    (entry / "manifest.json").write_text(json.dumps({
        "run_id": RUN_ID, "C": GUIDE_C, "m": GUIDE_M, "lambda": GUIDE_LAMBDA,
        "seed": GUIDE_SEED, "n_tags": len(names), "iters": iters,
    }, indent=1), encoding="utf-8")
    print(f"done — {entry.name} written ({time.perf_counter() - t0:.0f}s).", flush=True)


if __name__ == "__main__":
    main()
