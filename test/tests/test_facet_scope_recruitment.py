"""Verified-area integration mechanics, not semantic scope validation."""
import numpy as np
import pytest

from artefact.facet_recruitment_candidate import recruit_with_record_context
from artefact.facet_scope_recruitment import recruit_with_verified_area


def chunks():
    return [{'chunkId': cid, 'source_text': text, 'relpath': 'file.json', 'locator': {}}
            for cid, text in [('a', 'aa'), ('b', 'bbb'), ('c', 'c')]]


def run(scores, area=None, budget=None, provenance=None, scheduling='equal_depth'):
    return recruit_with_verified_area(chunk_rows=chunks(), joint_scores=scores,
        area_chunk_ids=area, area_provenance=provenance, source_character_budget=budget,
        scheduling=scheduling)


def test_no_area_exactly_preserves_global_recruitment():
    result = run([5, 1, 4], budget=3)
    baseline = recruit_with_record_context(chunk_rows=chunks(), stream_ids=['all'],
        stream_scores=[[5, 1, 4]], source_character_budget=3)
    assert result['recruitment'] == baseline
    assert result['stream_ids'] == ['all'] and result['area']['chunk_ids'] is None
    np.testing.assert_array_equal(result['stream_scores'], [[5, 1, 4]])


def test_area_preserves_pair_order_and_duplicate_ids_supply_no_votes():
    scores = np.array([5., 1., 4.])
    provenance = {'node_id': 'actual-node', 'path': 'Chunk-product-Product'}
    result = run(scores, ['b', 'c', 'b'], provenance=provenance)
    assert result['recruitment']['nomination'] == run(scores, ['b', 'c'])['recruitment']['nomination']
    rows = {r['chunk_id']: r for r in result['recruitment']['nomination']['rows']}
    assert rows['c']['depth'] < rows['b']['depth']
    assert rows['c']['stream_ranks']['verified_area'] < rows['b']['stream_ranks']['verified_area']
    np.testing.assert_array_equal(result['stream_scores'], [[5, 1, 4], [0, 1, 4]])
    np.testing.assert_array_equal(scores, [5, 1, 4])
    result['area']['provenance']['node_id'] = 'changed copy'
    assert provenance['node_id'] == 'actual-node'


def test_high_scoring_outside_chunk_survives_with_area_nominee():
    result = run([5, 1, 4], ['b'])['recruitment']
    assert result['frontiers'][0]['chunk_ids'] == ['a', 'b']
    assert result['selected_chunk_ids'] == ['a', 'b', 'c']
    rows = {r['chunk_id']: r for r in result['nomination']['rows']}
    assert rows['a']['winning_streams'] == ['all']
    assert rows['b']['winning_streams'] == ['verified_area']


def test_budget_preserves_complete_global_area_frontier():
    short = run([5, 1, 4], ['b'], 4)['recruitment']
    assert short['selected_chunk_ids'] == []
    assert short['crossing_frontier_chunk_ids'] == ['a', 'b']
    assert short['unused_capacity'] == 4
    exact = run([5, 1, 4], ['b'], 5)['recruitment']
    assert exact['selected_chunk_ids'] == ['a', 'b']
    assert exact['selected_source_characters'] == 5
    assert exact['crossing_frontier_chunk_ids'] == ['c']


def test_zero_area_support_cannot_invent_nomination():
    result = run([5, 0, 0], ['b', 'c'])['recruitment']
    assert result['selected_chunk_ids'] == ['a']
    assert result['nomination']['unsupported_chunk_ids'] == ['b', 'c']
    assert all('verified_area' not in r['stream_ranks'] for r in result['nomination']['rows'])
    assert run([0, 0, 0], ['a'])['recruitment']['selected_chunk_ids'] == []


def test_invalid_area_or_score_vector_fails_explicitly():
    for area in [[], ['unknown'], 'a', [['a']]]:
        with pytest.raises(ValueError, match='area'):
            run([5, 1, 4], area)
    for scores in [[1, 2], [[1, 2, 3]], [1, -1, 2], [1, np.nan, 2], [1, np.inf, 2]]:
        with pytest.raises(ValueError, match='joint_scores'):
            run(scores, ['a'])


def test_area_first_is_optional_and_keeps_outside_candidates_and_raw_scores():
    equal = run([5, 1, 4], ['b'])
    first = run([5, 1, 4], ['b'], scheduling='area_first')
    assert equal['recruitment']['selected_chunk_ids'] == ['a', 'b', 'c']
    assert first['recruitment']['selected_chunk_ids'] == ['b', 'a', 'c']
    assert set(first['recruitment']['selected_chunk_ids']) == set(equal['recruitment']['selected_chunk_ids'])
    assert first['stream_ids'] == ['verified_area', 'outside_area']
    np.testing.assert_array_equal(first['stream_scores'], [[0, 1, 0], [5, 0, 4]])


def test_area_first_without_area_is_exact_legacy_global_recruitment():
    for budget in (None, 3):
        legacy = run([5, 1, 4], budget=budget)
        first = run([5, 1, 4], budget=budget, scheduling='area_first')
        assert first['recruitment'] == legacy['recruitment']
        assert first['stream_ids'] == legacy['stream_ids']
        np.testing.assert_array_equal(first['stream_scores'], legacy['stream_scores'])


def test_area_first_preserves_phase_score_order_and_complete_ties():
    data = [{'chunkId': cid, 'source_text': 'x', 'relpath': 'file.json', 'locator': {}}
            for cid in 'abcdefg']
    result = recruit_with_verified_area(chunk_rows=data, joint_scores=[2, 2, 1, 9, 9, 5, 0],
        area_chunk_ids=['a', 'b', 'c', 'g'], source_character_budget=None, scheduling='area_first')
    nomination = {r['chunk_id']: r for r in result['recruitment']['nomination']['rows']}
    assert [nomination[c]['depth'] for c in 'abcdefg'] == [1, 1, 3, 4, 4, 6, None]
    assert [nomination[c]['phase_rank'] for c in 'abcdefg'] == [1, 1, 3, 1, 1, 3, None]
    assert result['recruitment']['selected_chunk_ids'] == list('abcdef')
    assert result['recruitment']['unsupported_chunk_ids'] == ['g']
    assert [f['chunk_ids'] for f in result['recruitment']['frontiers']] == [['a', 'b'], ['c'], ['d', 'e'], ['f']]
    short = recruit_with_verified_area(chunk_rows=data, joint_scores=[2, 2, 1, 9, 9, 5, 0],
        area_chunk_ids=['a', 'b', 'c', 'g'], source_character_budget=1, scheduling='area_first')['recruitment']
    assert short['selected_chunk_ids'] == []
    assert short['crossing_frontier_chunk_ids'] == ['a', 'b']


def test_area_first_record_recovery_can_cross_phases_without_fabricating_support():
    def row(cid, bounds):
        return {'chunkId': cid, 'source_text': 'xx', 'relpath': 'file.json',
                'locator': {'parent_ref': 'r', 'id': 'r', 'index': 0, 'field': 'body',
                            'section': 'text', 'char_range': bounds}}
    data = [row('z-area', [0, 2]), row('a-outside', [2, 4]), row('b-zero', [4, 6])]
    result = recruit_with_verified_area(chunk_rows=data, joint_scores=[1, 9, 0],
        area_chunk_ids=['z-area'], source_character_budget=None, scheduling='area_first')['recruitment']
    assert result['selected_chunk_ids'] == ['z-area', 'a-outside', 'b-zero']
    original = {r['chunk_id']: r for r in result['nomination']['rows']}
    assert original['a-outside']['depth'] == 2
    assert original['b-zero']['depth'] is None
    assert original['b-zero']['stream_ranks'] == {}
    assert all(r['depth'] == 1 and r['trigger_chunk_ids'] == ['z-area'] for r in result['rows'])


def test_area_first_research_budget_keeps_whole_frontiers_and_does_not_skip():
    short = run([5, 1, 4], ['b'], budget=2, scheduling='area_first')['recruitment']
    assert short['selected_chunk_ids'] == []
    assert short['crossing_frontier_chunk_ids'] == ['b']
    exact = run([5, 1, 4], ['b'], budget=5, scheduling='area_first')['recruitment']
    assert exact['selected_chunk_ids'] == ['b', 'a']
    assert exact['crossing_frontier_chunk_ids'] == ['c']
    assert run([5, 0, 0], ['b'], scheduling='area_first')['recruitment']['selected_chunk_ids'] == ['a']


def test_invalid_scheduling_is_rejected():
    with pytest.raises(ValueError, match='scheduling'):
        run([5, 1, 4], ['a'], scheduling='unknown')
