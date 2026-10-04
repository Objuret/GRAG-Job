"""Scheduler invariants; these do not validate semantic retrieval quality."""

import numpy as np
import pytest

from artefact.facet_need_frontier import build_streams, merge_frontiers


def by_id(result):
    return {r['chunk_id']: r for r in result['rows']}


def test_empty_and_sparse_streams_do_not_recruit_unsupported_chunks():
    result = merge_frontiers(['a', 'b', 'c'], ['empty', 'sparse'], [[0, 0, 0], [7, 0, 0]])
    assert result['supported_count'] == 1
    assert result['unsupported_chunk_ids'] == ['b', 'c']
    assert by_id(result)['a']['stream_ranks'] == {'sparse': 1}
    assert by_id(result)['b']['depth'] is None
    assert by_id(result)['b']['last_position'] is None


def test_competition_rank_keeps_whole_tied_frontier():
    result = merge_frontiers(['a', 'b', 'c', 'd'], ['x', 'y'],
                             [[4, 4, 2, 0], [0, 0, 5, 1]])
    rows = by_id(result)
    assert rows['c']['stream_ranks'] == {'x': 3, 'y': 1}
    assert all((rows[c]['first_position'], rows[c]['last_position']) == (1, 3) for c in 'abc')
    assert rows['d']['depth'] == 2
    assert result['frontier_sizes'] == [
        {'depth': 1, 'size': 3, 'cumulative_size': 3},
        {'depth': 2, 'size': 1, 'cumulative_size': 4},
    ]


def test_duplicate_support_does_not_become_a_vote_or_advance_other_lists():
    scores = np.array([[8, 6, 1], [7, 2, 5]])
    first = merge_frontiers(['a', 'b', 'c'], ['x', 'y'], scores)
    repeated = merge_frontiers(['a', 'b', 'c'], ['x', 'y', 'duplicate_x'], scores[[0, 1, 0]])
    assert first['frontier_sizes'] == repeated['frontier_sizes']
    for cid in 'abc':
        assert by_id(first)[cid]['depth'] == by_id(repeated)[cid]['depth']
    assert by_id(first)['b']['depth'] == by_id(first)['c']['depth'] == 2


def test_stream_and_candidate_permutation_invariance():
    scores = np.array([[4, 4, 2, 0], [0, 1, 5, 1]])
    first = merge_frontiers(['a', 'b', 'c', 'd'], ['x', 'y'], scores)
    perm = [2, 0, 3, 1]
    second = merge_frontiers([['a', 'b', 'c', 'd'][i] for i in perm], ['y', 'x'], scores[::-1, perm])
    assert first == second


def test_separate_needs_survive_a_stronger_subject():
    routes = np.zeros((5, 2, 3))
    routes[0] = [[10, 9, 0], [0, 0, 1]]
    groups = {'first': [0], 'second': [1]}
    joint_ids, joint_scores = build_streams(routes, [1, 1, 1], groups, 'joint')
    need_ids, need_scores = build_streams(routes, [1, 1, 1], groups, 'needs')
    assert by_id(merge_frontiers(['a', 'b', 'c'], joint_ids, joint_scores))['c']['depth'] == 3
    result = merge_frontiers(['a', 'b', 'c'], need_ids, need_scores)
    assert by_id(result)['c']['depth'] == 1
    assert by_id(result)['c']['last_position'] == 2


def test_one_need_reproduces_joint_scores_and_duplicate_tag_does_not_vote():
    rng = np.random.default_rng(12)
    routes = rng.random((5, 2, 6))
    q = rng.random(6)
    _, joint = build_streams(routes, q, {'only': [0, 1]}, 'joint')
    _, needs = build_streams(routes, q, {'only': [0, 1]}, 'needs')
    _, repeated = build_streams(routes[:, [0, 1, 0]], q, {'only': [0, 1, 2]}, 'needs')
    np.testing.assert_array_equal(joint, needs)
    np.testing.assert_array_equal(needs, repeated)


def test_zero_query_factor_cannot_recruit_and_facet_scales_do_not_change_ranks():
    routes = np.arange(1, 31, dtype=float).reshape(5, 2, 3)
    ids, scores = build_streams(routes, [1, 0, 1], {'a': [0], 'b': [1]}, 'need_facets')
    original = merge_frontiers(['x', 'y', 'z'], ids, scores)
    scaled = merge_frontiers(['x', 'y', 'z'], ids, scores * np.arange(1, 11)[:, None])
    assert original == scaled
    assert original['unsupported_chunk_ids'] == ['y']


@pytest.mark.parametrize('scores', [[[float('nan')]], [[-1]], [[float('inf')]]])
def test_bad_scores_fail_closed(scores):
    with pytest.raises(ValueError):
        merge_frontiers(['a'], ['x'], scores)


def test_missing_query_tag_is_not_silently_dropped():
    with pytest.raises(ValueError, match='every original'):
        build_streams(np.ones((5, 2, 3)), [1, 1, 1], {'only': [0]}, 'needs')
