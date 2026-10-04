from types import SimpleNamespace

import numpy as np
import pytest

from artefact.facet_joint_candidate import freeze_reference, rank_joint_candidate
from artefact.facet_stream_envelope import rank_facet_stream_envelope
from artefact.facet_operator_matrix import score_families


def fixture():
    chunks = [{'chunkId': str(i)} for i in range(5)]
    f = np.array([[.8, .2, .5, .1, .7], [.6, .8, .1, .9, .4],
                  [.7, .5, .9, .2, .3], [.3, .7, .4, .8, .5]])
    prepared = SimpleNamespace(chunks=chunks, edge_tag=np.array([0, 1, 1, 2]),
        edge_chunk=np.array([0, 0, 1, 2]), edge_facets=f, reference=freeze_reference(f),
        groups={'group': [[0, 2, 3], [0, 1], [1, 1]]}, adjacency_pairs=[(1, 4), (4, 1), (2, 2)])
    matrices = {'query_tag_cosines': np.array([[.8, .3, -.1], [.2, .9, .5]]),
                'query_chunk_cosines': np.array([[.7, .1, .6, .8, .9], [.4, .6, .5, .3, .7]]),
                'query_description_cosines': np.array([.7, .6, .3, .5, .9])}
    weights = np.array([[.9, .2, .6, .1, .8], [.6, .8, .3, .9, .2]])
    return prepared, matrices, weights


def all_scores(prepared, matrices, weights):
    return {tuple(key[k] for k in ('match', 'topology', 'facet', 'graph_join')): streams
            for key, streams in score_families(prepared, matrices, weights)}


def reference_kwargs(p, m, w, topology):
    return dict(chunk_ids=[c['chunkId'] for c in p.chunks], query_tag_ids=['q0', 'q1'],
        edge_ids=['e0', 'e1', 'e2', 'e3'], edge_tag_indices=p.edge_tag, edge_chunk_indices=p.edge_chunk,
        edge_facets=p.edge_facets, query_facet_weights=w, **m, reference=p.reference,
        groups=p.groups if topology in ('groups', 'both') else {},
        adjacency_pairs=p.adjacency_pairs if topology in ('adjacency', 'both') else ())


@pytest.mark.parametrize('topology', ['none', 'adjacency', 'groups', 'both'])
def test_current_formula_parity_for_same_path_and_separate_facets(topology):
    p, m, w = fixture()
    scores = all_scores(p, m, w)
    kwargs = reference_kwargs(p, m, w, topology)
    joint = rank_joint_candidate(**kwargs)
    envelope = rank_facet_stream_envelope(**kwargs)
    q = m['query_description_cosines']
    np.testing.assert_allclose(scores['product', topology, 'same_path_sum', 'union'][0] * q,
                               joint['scores'], rtol=2e-14, atol=1e-16)
    np.testing.assert_allclose(scores['product', topology, 'separate_facet_sum', 'union'][0] * q,
                               envelope['scores'], rtol=2e-14, atol=1e-16)
    np.testing.assert_allclose(scores['product', topology, 'topic_only', 'union'][0],
                               envelope['per_facet_scores'][:, 0], rtol=2e-14, atol=1e-16)
    if topology != 'none':
        for join in ('intersection', 'graph_only'):
            joint_routes = (np.minimum(joint['direct_scores'], joint['graph_scores'])
                            if join == 'intersection' else joint['graph_scores'])
            facet_routes = (np.minimum(envelope['direct_scores'], envelope['graph_scores'])
                            if join == 'intersection' else envelope['graph_scores'])
            np.testing.assert_allclose(scores['product', topology, 'same_path_sum', join][0],
                                       joint_routes.max(axis=0), rtol=2e-14, atol=1e-16)
            np.testing.assert_allclose(scores['product', topology, 'separate_facet_streams', join],
                facet_routes.max(axis=1) * np.array([1, .25, .25, .25, .25])[:, None],
                rtol=2e-14, atol=1e-16)


def test_complete_matrix_stream_shapes_nonnegative_and_no_hidden_normalization():
    p, m, w = fixture()
    scores = all_scores(p, m, w)
    assert len(scores) == 200
    for (match, topology, facet, join), streams in scores.items():
        assert streams.shape == (5 if facet == 'separate_facet_streams' else 1, 5)
        assert np.isfinite(streams).all() and (streams >= 0).all()
        if facet == 'separate_facet_sum':
            np.testing.assert_allclose(streams, scores[match, topology, 'separate_facet_streams', join].sum(axis=0, keepdims=True))
    scaled = all_scores(p, m, 3 * w)
    for key in scores:
        np.testing.assert_allclose(scaled[key], 3 * scores[key], rtol=2e-14, atol=1e-16)


def test_q_is_not_applied_and_weights_inputs_are_not_modified():
    p, m, w = fixture()
    saved = w.copy()
    first = all_scores(p, m, w)
    m['query_description_cosines'] = np.zeros(5)
    second = all_scores(p, m, w)
    for key in first:
        np.testing.assert_array_equal(first[key], second[key])
    np.testing.assert_array_equal(w, saved)


def test_zero_support_empty_graph_and_self_exclusion_do_not_invent_routes():
    p, m, w = fixture()
    p.groups = {'self': [[0]]}; p.adjacency_pairs = [(0, 0)]
    scores = all_scores(p, m, w)
    for key, value in scores.items():
        if key[3] != 'union':
            assert not value.any()
    for value in all_scores(p, m, np.zeros_like(w)).values():
        assert not value.any()


def test_tied_group_seeds_preserve_equal_neighbor_support():
    p, m, w = fixture()
    m['query_tag_cosines'][:] = 1
    m['query_chunk_cosines'][:] = 1
    p.edge_facets[:] = 1; p.reference = freeze_reference(p.edge_facets)
    w[:] = 1
    kwargs = reference_kwargs(p, m, w, 'both')
    expected = rank_facet_stream_envelope(**kwargs)
    actual = all_scores(p, m, w)['product', 'both', 'separate_facet_sum', 'union'][0]
    np.testing.assert_allclose(actual * m['query_description_cosines'], expected['scores'])


def test_invalid_inputs_fail_before_yield():
    p, m, w = fixture()
    with pytest.raises(ValueError, match='weights'):
        next(score_families(p, m, w[:, :4]))
    with pytest.raises(ValueError, match='nonnegative'):
        next(score_families(p, m, -w))
    p.adjacency_pairs = [(0, 99)]
    with pytest.raises(ValueError, match='endpoint'):
        next(score_families(p, m, w))


def test_match_operators_have_explicit_unscaled_values():
    p = SimpleNamespace(chunks=[{'chunkId': 'a'}], edge_tag=[0], edge_chunk=[0],
        edge_facets=np.ones((1, 5)), reference=freeze_reference(np.ones((1, 5))),
        groups={}, adjacency_pairs=[])
    m = {'query_tag_cosines': [[.2]], 'query_chunk_cosines': [[.8]]}
    scores = all_scores(p, m, [[1, 0, 0, 0, 0]])
    for match, expected in [('product', .08), ('minimum', .1), ('maximum', .4),
                            ('tag_only', .1), ('description_only', .4)]:
        np.testing.assert_allclose(scores[match, 'none', 'topic_only', 'union'], [[expected]])
