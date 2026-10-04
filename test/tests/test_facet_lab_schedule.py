"""Synthetic scheduling checks; no Lab construction, corpus or benchmark read."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from artefact.facet_joint_candidate import FACETS
from artefact.facet_recruitment_candidate import _components
from artefact.facet_scope_recruitment import recruit_with_verified_area


_path = Path(__file__).resolve().parents[2] / 'tools/facet_retrieval_lab.py'
_spec = importlib.util.spec_from_file_location('facet_lab_schedule_under_test', _path)
lab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lab)


def chunks():
    def part(cid, bounds):
        return {'chunkId': cid, 'source_text': 'xx', 'relpath': 'synthetic.json',
                'locator': {'parent_ref': 'r', 'id': 'r', 'index': 0,
                            'field': 'body', 'section': 'text', 'char_range': bounds}}
    return [part('z-sponsor', [0, 2]), part('a-recovered', [2, 4]),
            part('b-later', [4, 6]),
            {'chunkId': 'x-other', 'source_text': 'x', 'relpath': 'synthetic.json', 'locator': {}},
            {'chunkId': 'c-tie', 'source_text': 'x', 'relpath': 'synthetic.json', 'locator': {}},
            {'chunkId': 'd-zero', 'source_text': 'x', 'relpath': 'synthetic.json', 'locator': {}}]


def labels_and_order(data):
    ids = [c['chunkId'] for c in data]
    at = {cid: i for i, cid in enumerate(ids)}
    labels = np.arange(len(data))
    components, _, _ = _components(data)
    for component in components:
        members = [at[m['chunk_id']] for m in component['members']]
        labels[members] = min(members)
    return labels, np.argsort(np.argsort(np.asarray(ids)))


@pytest.mark.parametrize('scope', ['equal_depth', 'area_first', 'all'])
@pytest.mark.parametrize('area', [None, [True, False, False, False, True, False], [False] * 6])
@pytest.mark.parametrize('recovery', ['on', 'off'])
def test_canonical_one_stream_matches_actual_nomination_and_recovery(scope, area, recovery):
    data = chunks()
    ids = [c['chunkId'] for c in data]
    labels, id_order = labels_and_order(data)
    # Multiplication yields exact ties at 4, plus unsupported/advanced siblings.
    streams, q = np.array([[8., 0, 2, 4, 8, 0]]), np.array([.5, 1, .5, 1, .5, 0])
    mask = None if area is None else np.asarray(area)
    policy = {**lab.DEFAULT, 'scope': scope, 'recovery': recovery}
    actual_order, _, original, recovered = lab.schedule(streams, q, policy, mask, labels, id_order)
    # An explicitly empty mask in the laboratory has no local nominations; the
    # serving helper represents this unresolved-area fallback as None.
    area_ids = [cid for cid, active in zip(ids, area) if active] if area is not None else None
    if scope == 'all' or not area_ids:
        area_ids = None
    reference = recruit_with_verified_area(chunk_rows=data, joint_scores=streams[0] * q,
        area_chunk_ids=area_ids, source_character_budget=None,
        scheduling='area_first' if scope == 'area_first' else 'equal_depth')['recruitment']
    if recovery == 'on':
        expected = reference['selected_chunk_ids']
    else:
        expected = [r['chunk_id'] for r in reference['nomination']['rows'] if r['depth'] is not None]
    assert [ids[i] for i in actual_order] == expected
    nom = {r['chunk_id']: r['depth'] for r in reference['nomination']['rows']}
    assert original.tolist() == [nom[cid] if nom[cid] is not None else len(ids) + 1 for cid in ids]
    if recovery == 'on':
        rec = {r['chunk_id']: r['depth'] for r in reference['rows']}
        assert recovered.tolist() == [rec[cid] if rec[cid] is not None else len(ids) + 1 for cid in ids]


def test_area_only_excludes_outside_even_when_recovery_reaches_it():
    data = chunks()
    labels, ids = labels_and_order(data)
    mask = np.array([True, False, False, False, False, False])
    order, _, original, recovered = lab.schedule(np.array([[1., 0, 3, 8, 0, 0]]), np.ones(6),
        {**lab.DEFAULT, 'scope': 'area_only'}, mask, labels, ids)
    assert order.tolist() == [0]
    assert original[1] == 7 and recovered[1] == 1  # reached but not admitted
    empty, _, _, _ = lab.schedule(np.ones((1, 6)), np.ones(6),
        {**lab.DEFAULT, 'scope': 'area_only'}, np.zeros(6, dtype=bool), labels, ids)
    assert empty.size == 0


@pytest.mark.parametrize('description,expected', [
    ('multiply', [2, 1, 5, 5]), ('off', [1, 2, 5, 5]),
    ('independent_union', [1, 2, 5, 1]), ('independent_intersection', [3, 2, 5, 5]),
])
def test_description_policies_have_explicit_rank_semantics(description, expected):
    streams = np.array([[2., 1, 0, 0]])
    q = np.array([.1, .3, 0, .8])
    np.testing.assert_array_equal(lab.semantic_depth(streams, q, description), expected)


def test_independent_description_stream_respects_scope_mask():
    streams = np.array([[2., 1, 0, 0]])
    q = np.array([.1, .3, 0, .8])
    mask = np.array([True, True, False, False])
    np.testing.assert_array_equal(lab.semantic_depth(streams, q, 'independent_union', mask), [1, 1, 5, 5])
    np.testing.assert_array_equal(lab.semantic_depth(streams, q, 'independent_intersection', mask), [2, 2, 5, 5])


@pytest.mark.parametrize('lexical', lab.LEXICAL)
def test_all_120_lexicographic_orders_match_independent_tuple_comparison(lexical):
    streams = np.concatenate([np.eye(5), np.eye(5)[:, :1], np.full((5, 1), .5), np.zeros((5, 1))], axis=1)
    priority = [FACETS.index(f) for f in lexical[4:].split(',')]
    keys = {i: tuple(-streams[f, i] for f in priority) for i in range(7)}
    expected = [1 + sum(other < keys[i] for other in keys.values()) for i in range(7)] + [9]
    actual = lab.semantic_depth(streams, np.ones(8), 'off', lex_order=priority)
    np.testing.assert_array_equal(actual, expected)
    assert actual[0] == actual[5]  # exact vector ties retain the same depth
    mask = np.array([True, False, True, False, True, True, True, False])
    local = lab.semantic_depth(streams, np.ones(8), 'off', mask, priority)
    masked_keys = {i: key for i, key in keys.items() if mask[i]}
    expected_local = [1 + sum(other < masked_keys[i] for other in masked_keys.values())
                      if i in masked_keys else 9 for i in range(8)]
    np.testing.assert_array_equal(local, expected_local)


def test_multiple_streams_keep_equal_access_without_duplicate_votes():
    streams = np.array([[3., 2, 0], [0, 1, 4]])
    depth = lab.semantic_depth(streams, np.ones(3), 'off')
    np.testing.assert_array_equal(depth, [1, 2, 1])
    np.testing.assert_array_equal(lab.semantic_depth(np.vstack([streams, streams]), np.ones(3), 'off'), depth)


def test_no_supported_component_stays_absent_and_id_order_only_breaks_final_ties():
    data = chunks()
    labels, id_order = labels_and_order(data)
    zeros = np.zeros((1, 6))
    order, _, original, recovered = lab.schedule(zeros, np.ones(6),
        {**lab.DEFAULT, 'description': 'off'}, None, labels, id_order)
    assert not len(order) and (original == 7).all() and (recovered == 7).all()
