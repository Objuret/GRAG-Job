from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from facet_edge_controls import edge_shuffle, query_shuffle


def fixture():
    return SimpleNamespace(
        chunks=[{'source_kind': k, 'original_description_metadata': {'k': k}}
                for k in ('document', 'document', 'slack_thread_batch')],
        edge_tag=np.array([0, 0, 0, 0, 1, 1, 2]),
        edge_chunk=np.array([0, 1, 0, 2, 0, 1, 2]),
        edge_facets=np.arange(35, dtype=float).reshape(7, 5) / 35)


def sorted_rows(a):
    return sorted(map(tuple, a.tolist()))


@pytest.mark.parametrize('seed', range(8))
def test_edge_shuffle_preserves_conditional_vectors_topic_and_input(seed):
    p = fixture(); saved = p.edge_facets.copy()
    shuffled, coverage = edge_shuffle(p, seed)
    repeated, second = edge_shuffle(p, seed)
    np.testing.assert_array_equal(p.edge_facets, saved)
    np.testing.assert_array_equal(shuffled, repeated)
    np.testing.assert_array_equal(shuffled[:, 0], saved[:, 0])
    assert coverage == second and coverage['non_singleton_edges'] == 5
    for positions in ([0, 1, 2], [3], [4, 5], [6]):
        assert sorted_rows(shuffled[positions, 1:]) == sorted_rows(saved[positions, 1:])
        np.testing.assert_allclose(shuffled[positions, 1:].T @ shuffled[positions, 1:],
                                   saved[positions, 1:].T @ saved[positions, 1:], rtol=1e-14)
    np.testing.assert_array_equal(shuffled[[3, 6]], saved[[3, 6]])
    shuffled[:] = -1
    np.testing.assert_array_equal(p.edge_facets, saved)


@pytest.mark.parametrize('seed', range(8))
def test_query_shuffle_moves_whole_vectors_and_preserves_topic(seed):
    weights = fixture().edge_facets.copy(); saved = weights.copy()
    shuffled, coverage = query_shuffle(weights, 'synthetic-question-id', seed)
    again, same = query_shuffle(weights, 'synthetic-question-id', seed)
    np.testing.assert_array_equal(weights, saved)
    np.testing.assert_array_equal(shuffled, again)
    np.testing.assert_array_equal(shuffled[:, 0], saved[:, 0])
    assert sorted_rows(shuffled[:, 1:]) == sorted_rows(saved[:, 1:])
    np.testing.assert_allclose(shuffled[:, 1:].T @ shuffled[:, 1:], saved[:, 1:].T @ saved[:, 1:], rtol=1e-14)
    assert coverage == same


def test_query_singleton_and_invalid_source_kind():
    singleton = np.array([[.1, .2, .3, .4, .5]])
    shuffled, coverage = query_shuffle(singleton, 'one-tag', 0)
    np.testing.assert_array_equal(shuffled, singleton)
    assert coverage['actually_changed_vectors'] == 0
    p = fixture(); p.chunks[0]['original_description_metadata']['k'] = 'other'
    with pytest.raises(ValueError, match='inconsistent'):
        edge_shuffle(p, 0)
    with pytest.raises(ValueError, match='seed'):
        query_shuffle(singleton, 'one-tag', 8)
