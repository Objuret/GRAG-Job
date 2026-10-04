"""Narrow numerical parity and boundary checks for selected weight channels."""
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from facet_weight_channels import SUPPORTED, channels, query_channels
from artefact.facet_operator_matrix import score_families
from artefact.facet_stream_envelope import COEFFICIENTS
from test_facet_operator_matrix import fixture


def selected_references(p, m, w):
    return {tuple(k[x] for x in ('match', 'topology', 'graph_join')): values / np.asarray(COEFFICIENTS)[:, None]
            for k, values in score_families(p, m, w)
            if k['facet'] == 'separate_facet_streams' and tuple(k[x] for x in ('match', 'topology', 'graph_join')) in SUPPORTED}


@pytest.mark.parametrize('rotate', [False, True])
def test_matches_full_engine_without_beta_and_does_not_apply_Q(rotate):
    p, m, w = fixture()
    if rotate:
        w = w[:, [0, 2, 3, 4, 1]]
    originals = {k: v.copy() for k, v in m.items()}
    saved = w.copy()
    expected = selected_references(p, m, w)
    for key in SUPPORTED:
        policy = dict(zip(('match', 'topology', 'graph_join'), key))
        np.testing.assert_array_equal(channels(p, m, w, policy), expected[key])
        zero_Q = {**m, 'query_description_cosines': np.zeros(len(p.chunks))}
        np.testing.assert_array_equal(channels(p, zero_Q, w, policy), expected[key])
    np.testing.assert_array_equal(w, saved)
    for k in m:
        np.testing.assert_array_equal(m[k], originals[k])


def test_empty_relations_do_not_invent_intersection_support():
    p, m, w = fixture()
    p.groups = {}; p.adjacency_pairs = []
    result = channels(p, m, w, dict(match='maximum', topology='both', graph_join='intersection'))
    assert result.shape == (5, 5) and not result.any()


def test_rejects_wrong_shape_negative_weights_and_unrequested_policies():
    p, m, w = fixture()
    policy = dict(match='product', topology='both', graph_join='union')
    with pytest.raises(ValueError, match='weights'):
        channels(p, m, w[:, :4], policy)
    with pytest.raises(ValueError, match='nonnegative'):
        channels(p, m, -w, policy)
    with pytest.raises(ValueError, match='Unsupported'):
        channels(p, m, w, {**policy, 'topology': 'groups'})


@pytest.mark.parametrize('rotate', [False, True])
def test_query_factorization_preserves_values_and_rankings(rotate):
    p, m, w = fixture()
    if rotate:
        w = w[:, [0, 2, 3, 4, 1]]
    for key in SUPPORTED:
        policy = dict(zip(('match', 'topology', 'graph_join'), key))
        reusable = query_channels(p, m, policy)
        assert reusable.shape == (5, len(w), len(p.chunks))
        expected = channels(p, m, w, policy)
        actual = (reusable * w.T[:, :, None]).max(axis=1)
        np.testing.assert_allclose(actual, expected, rtol=2e-14, atol=1e-16)
        for a, e in zip(actual, expected):
            np.testing.assert_array_equal(np.argsort(-a, kind='stable'), np.argsort(-e, kind='stable'))
        assert not (reusable * np.zeros_like(w).T[:, :, None]).any()
