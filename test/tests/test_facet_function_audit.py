"""Check the audit's measurements against the model's actual probability law."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import torch

# Legacy training imports prepend script directories globally. Do not leak that
# side effect into unrelated arm tests when checking its probability law.
_before = sys.path.copy()
try:
    from graph.facet_pairs.train import davidson_log_probs
finally:
    sys.path[:] = _before

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("facet_audit", ROOT / "tools/facet_function_audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_audit_probabilities_match_training_likelihood():
    rng = np.random.default_rng(2121)
    a, b, log_nu = rng.normal(size=(3, 100)) * 3
    actual = AUDIT.davidson_probabilities(a - b, log_nu)
    expected = torch.stack(davidson_log_probs(
        torch.tensor(a), torch.tensor(b), torch.tensor(np.exp(log_nu))), dim=-1).exp().numpy()
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)


def test_probabilities_are_symmetric_and_numerically_stable():
    gaps = np.array([-1e6, -3, 0, 3, 1e6])
    p = AUDIT.davidson_probabilities(gaps, 0)
    assert np.isfinite(p).all()
    np.testing.assert_allclose(p.sum(axis=1), 1)
    np.testing.assert_allclose(p[:, 0], p[::-1, 1])
    np.testing.assert_allclose(p[:, 2], p[::-1, 2])
    np.testing.assert_allclose(p[2], [1/3] * 3)


def test_repeat_judgements_do_not_connect_unrelated_components():
    obs = [{"a_edge_id": "a", "b_edge_id": "b"}] * 20
    obs += [{"a_edge_id": "c", "b_edge_id": "d"},
            {"a_edge_id": "d", "b_edge_id": "e"}]
    assert AUDIT.component_sizes(obs) == [3, 2]
