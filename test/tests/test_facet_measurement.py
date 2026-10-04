import numpy as np
import pytest
from scipy.optimize import linprog

from artefact.facet_measurement import (fit_calibration, probabilities,
    reference_score_bounds, ordered_weight_difference_bounds)


def test_calibration_recovers_known_probability_law_without_sampling_noise():
    gap = np.linspace(-3, 3, 31)
    p = probabilities(gap, .7, -.4)
    fit = fit_calibration(np.repeat(gap, 3), np.tile([0, 1, 2], len(gap)), p.ravel())
    assert fit["alpha"] == pytest.approx(.7, abs=1e-5)
    assert fit["log_nu"] == pytest.approx(-.4, abs=1e-5)


def test_comparison_exchange_symmetry_and_offset_invariance():
    a, b = np.array([-.7, 2, 10]), np.array([1, -4, 0])
    p = probabilities(a-b, .8, .3)
    np.testing.assert_allclose(p[:, [1, 0, 2]], probabilities(b-a, .8, .3))
    np.testing.assert_allclose(p, probabilities((a+40)-(b+40), .8, .3))


def test_quadrature_bounds_contain_exact_weighted_reference_scores():
    rng = np.random.default_rng(91)
    x, ref, w = rng.normal(size=23), rng.normal(size=61), rng.uniform(size=61)
    # Includes ties and a zero-weight reference outside the support.
    ref[0], w[0] = -100, 0
    ref[2:5] = ref[1]
    p = probabilities(x[:, None]-ref, 1.3, -.2)
    exact = (p[..., 0] + .5*p[..., 2]) @ (w/w.sum())
    lo, hi = reference_score_bounds(x, ref, w, alpha=1.3, log_nu=-.2, bins=64)
    assert np.all(lo <= exact + 1e-14)
    assert np.all(hi >= exact - 1e-14)
    assert np.max(hi-lo) <= 1/64 + 1e-14


def test_candidates_do_not_change_reference_scores_or_pair_order():
    args = ([0., 1.], [1., 1.])
    before = reference_score_bounds(np.array([0., 1.]), *args, alpha=1, log_nu=0)
    after = reference_score_bounds(np.array([0., 1., -100]), *args, alpha=1, log_nu=0)
    for old, new in zip(before, after):
        np.testing.assert_array_equal(old, new[:2])


def test_ordered_weight_bounds_match_independent_linear_programs():
    rng = np.random.default_rng(19)
    for m in range(2, 7):
        constraints = np.zeros((m-1, m))
        for i in range(m-1):
            constraints[i, i], constraints[i, i+1] = -1, 1
        for _ in range(10):
            d = rng.normal(size=m)
            opts = dict(A_ub=constraints, b_ub=np.zeros(m-1),
                        A_eq=np.ones((1, m)), b_eq=[1], bounds=(0, None))
            low, high = linprog(d, **opts), linprog(-d, **opts)
            assert low.success and high.success
            np.testing.assert_allclose(ordered_weight_difference_bounds(d),
                                       [low.fun, -high.fun], atol=1e-9)


def test_a_weight_order_can_leave_the_preference_unresolved():
    # Even w1>=w2 does not decide whether A's first-facet advantage compensates.
    assert ordered_weight_difference_bounds([.1, -.8]) == pytest.approx((-.35, .1))


def test_invalid_calibration_inputs_are_not_silently_coerced():
    with pytest.raises(ValueError):
        fit_calibration([1, 2], [0, 1])
    with pytest.raises(ValueError):
        fit_calibration([1, 2, 3], [0, 1, 2], [1, -1, 1])
    with pytest.raises(ValueError):
        probabilities([1], -1, 0)
