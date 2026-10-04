"""Check the geometric claim behind the diagnostic intervention."""
import importlib.util
from pathlib import Path
import sys

import numpy as np

_path = Path(__file__).resolve().parents[2] / "tools/facet_coverage_transfer.py"
_spec = importlib.util.spec_from_file_location("coverage_transfer_experiment", _path)
_module = importlib.util.module_from_spec(_spec)
_old_path = list(sys.path)
try:
    _spec.loader.exec_module(_module)
finally:
    sys.path[:] = _old_path


def test_intervention_is_closest_feasible_and_preserves_observed_direction():
    # First coefficient is completely constrained by old comparisons. The two
    # free coefficients must each exceed 1 and sum to at least 3. The unique
    # closest feasible point to (0,0) is (1.5,1.5), not (1,2) or (2,1).
    original = np.array([7., 0., 0.])
    basis = np.array([[0., 1., 0.], [0., 0., 1.]])
    contrasts = np.array([[0., 1., 0.], [0., 0., 1.], [0., 1/3, 1/3]])
    got = _module.minimum_change(basis, contrasts, original, 1.)
    np.testing.assert_allclose(got, [7., 1.5, 1.5], atol=1e-8)
    np.testing.assert_allclose(np.array([[1., 0., 0.], [-4., 0., 0.]]) @ (got-original), 0.)


def test_no_intervention_when_original_already_satisfies_constraints():
    original = np.array([7., 4., 2.])
    basis = np.array([[0., 1., 0.], [0., 0., 1.]])
    got = _module.minimum_change(basis, basis, original, 1.)
    np.testing.assert_array_equal(got, original)
