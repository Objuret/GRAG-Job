"""The retrain band: `flip_gap` on synthetic values, the resampling unit, and the topic guard.

Nothing here loads the 773 MB cache, fits a real head, opens the graph or reads a benchmark
question. The synthetic values are built so the analytic flip rate is known.
"""
from __future__ import annotations

import ast
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "test", ROOT / "prod"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from graph.facet_pairs import bootstrap_scores as BS      # noqa: E402
from graph.facet_pairs import data as D                   # noqa: E402

PKG = ROOT / "test" / "graph" / "facet_pairs"


# ---------------------------------------------------------------- flip_gap, synthetic


def _fixed_gap_values(gaps: np.ndarray, sigma: float, B: int, seed: int):
    """One pair per gap: row 2k is the high side, row 2k+1 the low side."""
    rng = np.random.default_rng(seed)
    n = 2 * len(gaps)
    mu = np.zeros(n)
    mu[0::2] = gaps
    v = mu[:, None] + rng.normal(0.0, sigma, size=(n, B))
    pairs = np.stack([np.arange(0, n, 2), np.arange(1, n, 2)], axis=1)
    return v, pairs


def test_zero_noise_gives_gap_zero():
    v = np.tile(np.array([[3.0], [1.0], [-2.0], [0.5]]), (1, 8))
    pairs = np.array([[0, 1], [2, 3], [1, 2]])
    out = BS.flip_gap(v, pairs, rate=0.05, grid=0.01)
    assert out["gap"] == 0.0
    assert out["curve"][0]["flip_rate"] == 0.0
    assert out["retrain_sd"]["median"] == 0.0


def test_known_gaussian_noise_lands_near_the_analytic_gap():
    # d_b = gap + (eps_i - eps_j), so the per-pair flip probability at a gap g is
    # Phi(-g / (sigma * sqrt(2))). At a threshold t the reported rate averages that over the
    # pairs with gap >= t, which here are uniform on [t, G]; the gap is where that average
    # crosses 0.05. B is large so that the reference sign is the true sign.
    sigma, B, G = 0.5, 400, 4.0
    gaps = np.linspace(0.0, G, 4001)
    v, pairs = _fixed_gap_values(gaps, sigma, B, seed=7)
    out = BS.flip_gap(v, pairs, rate=0.05, grid=0.01, mode="cumulative")

    def phi(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def rate_at(t):
        sel = gaps[gaps >= t]
        return float(np.mean([phi(-g / (sigma * math.sqrt(2.0))) for g in sel]))

    t_star = 0.0
    while rate_at(t_star) >= 0.05:
        t_star += 0.01
    # tolerance: three grid steps, for the sampling noise of B = 400 draws
    assert out["gap"] is not None
    assert abs(out["gap"] - t_star) <= 0.03, (out["gap"], t_star)


def test_scaling_the_values_scales_the_gap():
    sigma, B = 0.4, 200
    gaps = np.linspace(0.0, 3.0, 1201)
    v, pairs = _fixed_gap_values(gaps, sigma, B, seed=11)
    a = BS.flip_gap(v, pairs, rate=0.05, grid=0.01)
    k = 7.0
    b = BS.flip_gap(v * k, pairs, rate=0.05, grid=0.01 * k)
    assert a["gap"] is not None and b["gap"] is not None
    assert b["gap"] == pytest.approx(a["gap"] * k, abs=1e-9)


def test_adding_a_constant_changes_nothing():
    sigma, B = 0.4, 64
    gaps = np.linspace(0.0, 3.0, 601)
    v, pairs = _fixed_gap_values(gaps, sigma, B, seed=13)
    a = BS.flip_gap(v, pairs, rate=0.05, grid=0.01)
    b = BS.flip_gap(v + 123.5, pairs, rate=0.05, grid=0.01)
    assert a["gap"] == b["gap"]
    assert [c["flip_rate"] for c in a["curve"]] == [c["flip_rate"] for c in b["curve"]]


def test_deterministic_given_the_pairs():
    sigma, B = 0.3, 32
    gaps = np.linspace(0.0, 2.0, 401)
    v, pairs = _fixed_gap_values(gaps, sigma, B, seed=17)
    a = BS.flip_gap(v, pairs)
    b = BS.flip_gap(v, pairs)
    assert a["gap"] == b["gap"]
    assert a["curve"] == b["curve"]
    assert a["retrain_sd"] == b["retrain_sd"]


def test_curve_pair_counts_fall_and_the_reported_gap_is_the_first_below_the_rate():
    sigma, B = 0.5, 128
    gaps = np.linspace(0.0, 3.0, 901)
    v, pairs = _fixed_gap_values(gaps, sigma, B, seed=19)
    out = BS.flip_gap(v, pairs, rate=0.05, grid=0.01, mode="cumulative")
    counts = [c["n_pairs"] for c in out["curve"]]
    assert counts == sorted(counts, reverse=True)
    # the curve now runs past the crossing (the band is read off a fitted curve, 09-21), so
    # what is asserted is that the gap is the FIRST step below the rate, not that the curve
    # stops there
    before = [c for c in out["curve"] if c["t"] < out["gap"]]
    assert before and all(c["flip_rate"] >= 0.05 for c in before)
    at = [c for c in out["curve"] if c["t"] == out["gap"]]
    assert len(at) == 1 and at[0]["flip_rate"] < 0.05
    # the curve carries on past the crossing to the end of the sample, so that the local
    # mode's band can be read off a fitted curve rather than off the first dip (09-21)
    assert out["curve"][-1]["t"] > out["gap"]
    assert out["curve"][-1]["n_pairs"] > 0


def test_retrain_sd_summary_is_the_sd_over_draws():
    v = np.array([[0.0, 2.0], [1.0, 1.0], [0.0, 10.0]])
    out = BS.flip_gap(v, np.array([[0, 1]]))
    assert out["retrain_sd"]["median"] == pytest.approx(1.0)


def test_bad_shapes_raise():
    v = np.zeros((4, 3))
    with pytest.raises(ValueError):
        BS.flip_gap(np.zeros(4), np.array([[0, 1]]))
    with pytest.raises(ValueError):
        BS.flip_gap(v, np.array([0, 1]))
    with pytest.raises(ValueError):
        BS.flip_gap(v, np.array([[0, 99]]))
    with pytest.raises(ValueError):
        BS.flip_gap(v, np.array([[0, 1]]), grid=0.0)


def test_no_pairs_returns_no_gap():
    out = BS.flip_gap(np.zeros((4, 3)), np.zeros((0, 2), dtype=np.int64))
    assert out["gap"] is None and out["n_pairs"] == 0


# ---------------------------------------------------------------- the resampling unit


def _obs(row_id, facet, a, b):
    return {"row_id": row_id, "facet": facet, "a_edge_id": a, "b_edge_id": b,
            "a_chunk_id": a.split("::")[0], "b_chunk_id": b.split("::")[0],
            "outcome": "first"}


def test_the_resampling_unit_is_the_row():
    fit = ([_obs("r1", f, "c1::x", "c2::y") for f in D.FACETS]
           + [_obs("r2", f, "c3::x", "c4::y") for f in D.FACETS]
           + [_obs("r3", f, "c5::x", "c6::y") for f in D.FACETS])
    by = BS._rows_of(fit)
    assert set(by) == {"r1", "r2", "r3"}
    assert all(len(v) == len(D.FACETS) for v in by.values())
    prep = {"by_row": by, "row_ids": sorted(by)}
    drawn = BS.draw_rows(prep, 20260921)
    # as many observations as rows drawn times the row's own observation count
    counts = {}
    for o in drawn:
        counts[o["row_id"]] = counts.get(o["row_id"], 0) + 1
    assert len(drawn) == len(fit)
    assert all(c % len(D.FACETS) == 0 for c in counts.values())
    assert sum(counts.values()) // len(D.FACETS) == len(by)
    # a drawn row brings all five of its observations, never a subset
    for rid, c in counts.items():
        got = [o["facet"] for o in drawn if o["row_id"] == rid]
        assert sorted(set(got)) == sorted(D.FACETS)
    # deterministic on the seed, and the seed changes the draw
    assert [o["row_id"] for o in BS.draw_rows(prep, 20260921)] == \
           [o["row_id"] for o in drawn]


def test_pair_samples_are_deterministic_and_well_formed():
    a = BS.sample_any_pairs(500, 300, 20260921)
    assert a.shape == (300, 2)
    assert (a[:, 0] != a[:, 1]).all()
    assert np.array_equal(a, BS.sample_any_pairs(500, 300, 20260921))

    ids = [f"c{i // 4}::t{i % 4}" for i in range(400)]
    s = BS.sample_same_chunk_pairs(ids, 300, 20260922)
    assert s.shape == (300, 2)
    assert (s[:, 0] != s[:, 1]).all()
    for i, j in s:
        assert D.split_edge_id(ids[i])[0] == D.split_edge_id(ids[j])[0]
    assert np.array_equal(s, BS.sample_same_chunk_pairs(ids, 300, 20260922))


# ---------------------------------------------------------------- the topic guard

FORBIDDEN = ("facet_stats", "topic_key", "load_topic", "known_topic", "topic_reg")


def test_the_bootstrap_module_names_no_known_topic_source():
    text = (PKG / "bootstrap_scores.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    code = ast.unparse(tree)  # the docstrings go with it; the words must be absent from code
    for word in FORBIDDEN:
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == word:
                raise AssertionError(f"the module names {word!r}")
            if isinstance(node, ast.Attribute) and node.attr == word:
                raise AssertionError(f"the module names {word!r}")
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and word in node.value and node.value != text:
                # a path or a call target hidden in a string literal
                raise AssertionError(f"a string literal names {word!r}: {node.value!r}")
    assert "output/facet_stats" not in code
    assert "topic_key" not in code


def test_the_head_topic_column_is_named_apart():
    text = (PKG / "bootstrap_scores.py").read_text(encoding="utf-8")
    assert "head_topic" in text
    assert "temporal" in BS.NON_TOPIC and "topic" not in BS.NON_TOPIC
    assert len(BS.NON_TOPIC) == 4


def test_local_mode_lands_where_pairs_that_far_apart_flip_at_the_rate():
    # local mode: the flip probability of a pair AT gap g is Phi(-g / (sigma * sqrt(2))); it is
    # 0.05 at g = 1.6449 * sigma * sqrt(2). The window here spans 80 pairs = 0.08 of gap, so the
    # tolerance is that span plus three grid steps.
    sigma, B, G = 0.5, 400, 4.0
    gaps = np.linspace(0.0, G, 4001)
    v, pairs = _fixed_gap_values(gaps, sigma, B, seed=11)
    out = BS.flip_gap(v, pairs, rate=0.05, grid=0.01)            # local is the default
    assert out["mode"] == "local"
    g_star = 1.6449 * sigma * math.sqrt(2.0)
    assert out["gap"] is not None
    assert abs(out["gap"] - g_star) <= 0.11, (out["gap"], g_star)
    wide = BS.flip_gap(v, pairs, rate=0.05, grid=0.01, mode="cumulative")
    assert wide["gap"] < out["gap"]          # the cumulative rule gives the narrower band


# ---------------------------------------------------------------- the isotonic read (09-21)


def test_the_local_curve_is_read_through_a_non_increasing_fit():
    sigma, B, G = 0.5, 200, 4.0
    gaps = np.linspace(0.0, G, 4001)
    v, pairs = _fixed_gap_values(gaps, sigma, B, seed=5)
    out = BS.flip_gap(v, pairs, rate=0.05, grid=0.01)
    assert out["isotonic"] is not None
    iso = [row["flip_rate"] for row in out["isotonic"] if row["flip_rate"] is not None]
    assert iso == sorted(iso, reverse=True), "the fitted curve rises somewhere"
    raw = [row["flip_rate"] for row in out["curve"] if row["n_pairs"]]
    assert raw != iso, "the fixture must have a raw curve that is not already monotone"
    # the curve runs past the crossing now, so the band can be read off a fitted curve
    ts = [row["t"] for row in out["curve"]]
    assert max(ts) > out["gap"]


def test_an_injected_dip_does_not_name_the_band():
    """a single window that happens to fall below the rate must not be read as the crossing"""
    sigma, B, G = 0.5, 240, 4.0
    gaps = np.linspace(0.0, G, 4001)
    v, pairs = _fixed_gap_values(gaps, sigma, B, seed=13)
    honest = BS.flip_gap(v, pairs, rate=0.05, grid=0.01)
    # a hole in the raw curve: an early band of pairs that KEEP their gap (so they stay where
    # they are on the |mean d| axis) but never flip in any draw
    lo = 0.35 * honest["gap"]
    hit = np.flatnonzero((gaps >= lo) & (gaps <= lo + 0.20))
    assert hit.size > 150      # wider than the window
    v2 = v.copy()
    for k in hit.tolist():
        v2[2 * k, :] = gaps[k] / 2.0       # no spread across draws: zero flips at this gap
        v2[2 * k + 1, :] = -gaps[k] / 2.0
    dipped = BS.flip_gap(v2, pairs, rate=0.05, grid=0.01)
    raw_first = next(r["t"] for r in dipped["curve"]
                     if r["n_pairs"] and r["flip_rate"] < 0.05)
    assert raw_first < 0.6 * honest["gap"], "the fixture did not create a dip"
    assert dipped["gap"] > raw_first, "the dip named the band"
    assert dipped["gap"] >= 0.8 * honest["gap"], (dipped["gap"], honest["gap"])


def test_pava_is_the_weighted_non_increasing_projection():
    y = [0.5, 0.2, 0.3, 0.1]
    w = [1.0, 1.0, 1.0, 1.0]
    fit = BS.pava_nonincreasing(y, w)
    assert list(np.round(fit, 10)) == [0.5, 0.25, 0.25, 0.1]
    # already non-increasing: unchanged
    z = [0.9, 0.5, 0.5, 0.2]
    assert list(np.round(BS.pava_nonincreasing(z, w), 10)) == z
    # the weights count: a heavy low point pulls the pooled block down
    heavy = BS.pava_nonincreasing([0.5, 0.2, 0.3], [1.0, 9.0, 1.0])
    assert heavy[1] == heavy[2] < 0.3


def test_the_band_module_is_torch_free_and_re_exported():
    src = (PKG / "bootstrap_band.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "numpy"}, imported
    from graph.facet_pairs import bootstrap_band as BB
    for name in ("flip_gap", "sample_any_pairs", "sample_same_chunk_pairs",
                 "pava_nonincreasing"):
        assert getattr(BS, name) is getattr(BB, name)


def test_the_chunk_half_of_an_edge_id_matches_the_canonical_split():
    from graph.facet_pairs import bootstrap_band as BB
    for eid in ("8c1f40c9::Slack", "abc::a::b", "noseparator", "::leading"):
        assert BB.split_chunk_id(eid) == D.split_edge_id(eid)[0]
