"""Tests of estimation meaning and data separation, not benchmark performance."""
import numpy as np

from artefact.facet_tradeoff import (
    comparison_probabilities, crossfit_nonnegative, fit_nonnegative, query_edge_products,
)


def test_known_comparison_law_recovered_from_fractional_observations():
    d = np.array([[a, b] for a in (-2., -.5, 0., .5, 2.) for b in (-2., -.5, 0., .5, 2.)])
    truth = np.array([1.3, .6])
    eta = -.3
    p = comparison_probabilities(d, truth, eta)
    fit = fit_nonnegative(np.repeat(d, 3, axis=0), np.tile([0,1,2], len(d)),
                          l2=1e-9, sample_weight=p.ravel())
    np.testing.assert_allclose(fit["coefficients"], truth, atol=2e-5)
    np.testing.assert_allclose(fit["tie_log"], eta, atol=2e-5)


def test_exchanging_candidates_exchanges_win_probabilities_and_preserves_ties():
    d = np.array([[2., -1.], [.2, .5]])
    p = comparison_probabilities(d, [.4, .7], .1)
    np.testing.assert_allclose(comparison_probabilities(-d, [.4, .7], .1), p[:, [1,0,2]])


def test_duplicated_readings_with_split_mass_do_not_change_fit():
    d = np.array([[1., 0.], [0., 1.], [-1., 1.], [2., -.5]])
    y = np.array([0, 1, 2, 0])
    a = fit_nonnegative(d, y, l2=.01)
    b = fit_nonnegative(np.r_[d, d[:1]], np.r_[y, y[:1]], l2=.01,
                        sample_weight=[.5,1,1,1,.5])
    np.testing.assert_allclose(a["coefficients"], b["coefficients"], atol=1e-8)
    np.testing.assert_allclose(a["tie_log"], b["tie_log"], atol=1e-8)


def test_excluded_labels_cannot_select_penalty_or_coefficients():
    d = np.array([[1., .2], [-.5, 1.], [.7,-.3], [-1.,.2], [.1,1.], [-.2,-.9]])
    y = np.array([0,1,0,2,0,1])
    groups = np.array(["a","a","b","b","c","c"])
    changed = y.copy()
    changed[groups == "c"] = [2,0]
    one = crossfit_nonnegative(d,y,groups,penalties=[.01,.1,1.])
    two = crossfit_nonnegative(d,changed,groups,penalties=[.01,.1,1.])
    assert one["folds"][-1] == two["folds"][-1]
    np.testing.assert_array_equal(one["probabilities"][groups == "c"], two["probabilities"][groups == "c"])


def test_query_magnitude_survives_and_zero_facet_has_no_effect():
    q = np.array([.5, 0., .2])
    e = np.array([.3, .6, .9])
    base = query_edge_products(q,e)
    e[1] = 1e6
    np.testing.assert_array_equal(query_edge_products(q,e),base)
    np.testing.assert_allclose(query_edge_products(q*.01,e),base*.01)
