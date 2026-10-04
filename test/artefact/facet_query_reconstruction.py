"""Unfitted nonnegative query reconstruction and explicit route aggregation.

All vectors must use the same serving query role. Coefficients express geometric
tag sponsorship, not facet importance, calibrated utility, or probabilities.
Every supplied tag participates; no top-N, regularizer, or semantic threshold is
introduced. Exact vector clones are represented by one mass with all members.
"""
import numpy as np
from scipy.optimize import nnls


def _spectrum(matrix):
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = float(singular[0] * max(matrix.shape) * np.finfo(float).eps)
    return singular, int(np.count_nonzero(singular > tolerance)), tolerance


def reconstruct_query_description(tag_vectors, description_vector, *, unit_tolerance=1e-6):
    """Minimize ||T.T a - d||^2 subject to a>=0, grouping exact duplicate rows.

    Inputs are [tag,dimension] and [dimension]. Negative embedding coordinates
    are valid; zero or non-unit vectors are not. The explicit unit tolerance is
    solely a floating-point input check: inputs are never rescaled or pruned.

    ``coefficients`` aligns with canonical ``groups``/``group_vectors``, NOT with
    original tags. Exact duplicate members retain only a joint coefficient: no
    tag receives an arbitrary share before its downstream profiles are checked.
    Gradients use the squared residual objective (including its factor of two).
    Diagnostics report numerical errors directly, without a semantic pass cutoff.
    """
    if not np.isscalar(unit_tolerance) or not np.isfinite(unit_tolerance) or unit_tolerance < 0:
        raise ValueError('unit_tolerance must be finite and nonnegative')
    tags = np.asarray(tag_vectors, dtype=float)
    description = np.asarray(description_vector, dtype=float)
    if (tags.ndim != 2 or not tags.shape[0] or not tags.shape[1]
            or description.shape != (tags.shape[1],)
            or not np.isfinite(tags).all() or not np.isfinite(description).all()):
        raise ValueError('finite nonempty tag vectors and an aligned description vector required')
    tag_norms = np.linalg.norm(tags, axis=1)
    description_norm = float(np.linalg.norm(description))
    if (np.any(tag_norms == 0) or description_norm == 0
            or np.any(np.abs(tag_norms - 1) > unit_tolerance)
            or abs(description_norm - 1) > unit_tolerance):
        raise ValueError('tag and description vectors must be unit vectors within unit_tolerance')
    unique, inverse = np.unique(tags, axis=0, return_inverse=True)
    coefficients, solver_residual = nnls(unique.T, description)
    reconstructed = unique.T @ coefficients
    residual = reconstructed - description
    gradient = 2 * unique @ residual
    singular, rank, rank_tolerance = _spectrum(tags)
    group_singular, group_rank, group_tolerance = _spectrum(unique)
    groups = [{'member_indices': np.flatnonzero(inverse == i).tolist(),
               'coefficient': float(coefficients[i])} for i in range(len(unique))]
    active = coefficients > 0  # exact NNLS support; no tag-pruning tolerance
    return {
        'coefficients': coefficients, 'groups': groups, 'group_vectors': unique,
        'tag_to_group': inverse, 'input_tag_count': len(tags),
        'reconstructed_vector': reconstructed, 'residual_vector': residual,
        'residual_norm': float(np.linalg.norm(residual)),
        'objective': float(residual @ residual), 'solver_residual_norm': float(solver_residual),
        'gradient': gradient, 'input_gradient': gradient[inverse],
        'kkt': {
            'primal_violation': float(max(0., -coefficients.min())),
            'dual_violation': float(max(0., -gradient.min())),
            'complementarity_max_abs': float(np.max(np.abs(coefficients * gradient))),
            'active_stationarity_max_abs': float(np.max(np.abs(gradient[active]))) if active.any() else 0.,
        },
        'input_rank': rank, 'input_singular_values': singular,
        'input_rank_tolerance': rank_tolerance,
        'group_rank': group_rank, 'group_singular_values': group_singular,
        'group_rank_tolerance': group_tolerance,
        'group_full_row_rank': group_rank == len(unique),
        'identifiability': ('Unique coefficient solution for independent group vectors.'
                            if group_rank == len(unique) else
                            'Dependent group vectors: coefficient uniqueness is not established; NNLS returns one canonical-order solution.'),
        'unit_tolerance': float(unit_tolerance), 'input_tag_norms': tag_norms,
        'input_description_norm': description_norm,
        'coefficient_meaning': 'Geometric tag sponsorship; not facet importance, calibrated utility, or probabilities.',
    }


def aggregate_route_profiles(route_profiles, reconstruction):
    """Sum grouped sponsorship times existing profiles [facet,tag,chunk].

    Duplicate-vector members must have exactly equal profiles over ALL facets
    and chunks, even when the group's coefficient is zero. Otherwise geometry
    cannot decide how to allocate mass among their different facet profiles;
    raise explicitly instead of averaging or selecting a member. Existing query
    facet weights are already in the profiles and are not renormalized here.
    """
    profiles = np.asarray(route_profiles, dtype=float)
    if (profiles.ndim != 3 or not profiles.shape[0]
            or profiles.shape[1] != reconstruction['input_tag_count']
            or not np.isfinite(profiles).all() or (profiles < 0).any()):
        raise ValueError('route_profiles must be finite nonnegative [facet,tag,chunk] aligned to reconstruction')
    coefficients = np.asarray(reconstruction['coefficients'], dtype=float)
    groups = reconstruction['groups']
    if (coefficients.shape != (len(groups),) or not np.isfinite(coefficients).all()
            or (coefficients < 0).any()):
        raise ValueError('invalid reconstruction coefficients')
    members = [i for group in groups for i in group['member_indices']]
    if sorted(members) != list(range(profiles.shape[1])):
        raise ValueError('reconstruction groups must partition all input tags exactly once')
    contributions = []
    for coefficient, group in zip(coefficients, groups):
        indices = group['member_indices']
        if not indices:
            raise ValueError('reconstruction group must contain a tag')
        representative = profiles[:, indices[0], :]
        if any(not np.array_equal(representative, profiles[:, i, :]) for i in indices[1:]):
            raise ValueError('duplicate tag vectors have conflicting route profiles; coefficient allocation is unidentified')
        contributions.append(coefficient * representative)
    grouped = np.asarray(contributions)
    return {'profiles': grouped.sum(axis=0), 'group_contributions': grouped}
