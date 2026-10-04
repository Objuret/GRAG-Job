"""Geometry, clone handling and KKT contracts; no retrieval quality claims."""
import numpy as np
import pytest

from artefact.facet_query_reconstruction import (
    aggregate_route_profiles, reconstruct_query_description,
)


def test_known_orthogonal_projection_and_route_sum():
    tags = np.array([[1., 0, 0], [0, 1., 0]])
    d = np.array([.6, 0, .8])
    result = reconstruct_query_description(tags, d)
    np.testing.assert_allclose(result['reconstructed_vector'], [.6, 0, 0])
    assert result['residual_norm'] == pytest.approx(.8)
    assert result['objective'] == pytest.approx(.64)
    assert result['input_rank'] == 2
    routes = np.array([[[2, 1], [4, 3]], [[.5, 2], [8, 7]]])
    aggregate = aggregate_route_profiles(routes, result)
    np.testing.assert_allclose(aggregate['profiles'], .6 * routes[:, 0, :])
    np.testing.assert_allclose(aggregate['group_contributions'].sum(axis=0), aggregate['profiles'])


def test_exact_clones_and_input_permutation_preserve_mass_and_aggregation():
    tags = np.eye(2)
    d = [.6, .8]
    routes = np.array([[[2., 1], [1, 5]], [[0, 3], [4, 2]]])
    original = reconstruct_query_description(tags, d)
    cloned_tags, cloned_routes = tags[[1, 0, 1]], routes[:, [1, 0, 1], :]
    clone = reconstruct_query_description(cloned_tags, d)
    np.testing.assert_array_equal(original['group_vectors'], clone['group_vectors'])
    np.testing.assert_array_equal(original['coefficients'], clone['coefficients'])
    assert sorted(len(g['member_indices']) for g in clone['groups']) == [1, 2]
    np.testing.assert_array_equal(aggregate_route_profiles(routes, original)['profiles'],
                                  aggregate_route_profiles(cloned_routes, clone)['profiles'])
    np.testing.assert_array_equal(clone['reconstructed_vector'], original['reconstructed_vector'])


def test_duplicate_conflicting_profiles_rejected_even_for_zero_mass():
    result = reconstruct_query_description([[1., 0], [1., 0]], [-1., 0])
    assert result['coefficients'].tolist() == [0.]
    with pytest.raises(ValueError, match='conflicting route profiles'):
        aggregate_route_profiles(np.array([[[1.], [2.]]]), result)


def test_negative_coordinates_allowed_and_negative_projection_has_zero_mass_kkt():
    exact = reconstruct_query_description([[-1., 0], [0, 1.]], [-.6, .8])
    np.testing.assert_allclose(exact['reconstructed_vector'], [-.6, .8])
    zero = reconstruct_query_description(np.eye(2), [-.6, -.8])
    np.testing.assert_array_equal(zero['coefficients'], [0., 0.])
    assert zero['objective'] == pytest.approx(1)
    assert np.all(zero['gradient'] > 0)
    assert all(value == 0 for value in zero['kkt'].values())


def test_nonorthogonal_solution_satisfies_actual_objective_gradient_and_kkt():
    tags = np.array([[1., 0, 0], [.6, .8, 0], [0, 0, 1.]])
    d = np.array([.6, .8, 0])
    result = reconstruct_query_description(tags, d)
    residual = result['group_vectors'].T @ result['coefficients'] - d
    np.testing.assert_allclose(result['gradient'], 2 * result['group_vectors'] @ residual)
    assert result['objective'] == pytest.approx(residual @ residual)
    assert result['solver_residual_norm'] == pytest.approx(result['residual_norm'])
    assert all(value < 1e-12 for value in result['kkt'].values())
    assert result['group_full_row_rank']


def test_input_validation_rejects_zero_nonunit_or_nonfinite_without_normalizing():
    for tags, d in [([[0., 0]], [1., 0]), ([[2., 0]], [1., 0]),
                    ([[1., 0]], [0., 0]), ([[1., 0]], [-2., 0]),
                    ([[np.nan, 0]], [1., 0]), ([[1., 0]], [np.inf, 0]),
                    ([], [1., 0]), ([[1., 0]], [1.])]:
        with pytest.raises(ValueError):
            reconstruct_query_description(tags, d)
    near = np.array([[1. + 1e-7, 0]])
    result = reconstruct_query_description(near, [1., 0], unit_tolerance=1e-6)
    np.testing.assert_array_equal(result['group_vectors'], near)
    with pytest.raises(ValueError, match='unit vectors'):
        reconstruct_query_description(near, [1., 0], unit_tolerance=1e-8)
