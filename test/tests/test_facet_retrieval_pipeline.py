"""Prepared-query composition contracts, not semantic retrieval validation."""
from copy import deepcopy

import numpy as np
import pytest

from artefact.facet_joint_candidate import freeze_reference
from artefact.facet_retrieval_pipeline import retrieve_prepared_query
from artefact.facet_stream_envelope import rank_facet_stream_envelope


def inputs():
    def chunk(cid, bounds, record='record'):
        return {'chunkId': cid, 'relpath': 'file.json', 'source_text': cid * 5,
                'locator': {'parent_ref': record, 'id': record, 'index': 0,
                            'field': 'content', 'section': 'documents', 'char_range': bounds}}
    return dict(
        chunk_rows=[chunk('a', [0, 5]), chunk('b', [5, 10]), chunk('c', [5, 10], 'other')],
        coefficients=[1., 0., 2., 0., 0.], source_character_budget=None,
        query_tag_ids=['first', 'second'], edge_ids=['ea', 'eb', 'ec'],
        edge_tag_indices=[0, 1, 2], edge_chunk_indices=[0, 1, 2],
        edge_facets=np.ones((3, 5)),
        query_facet_weights=np.array([[.8, 0, 0, 0, 0], [0, 0, .6, 0, 0]]),
        query_tag_cosines=np.array([[1., 0, 0], [0, .9, 0]]),
        query_chunk_cosines=np.ones((2, 3)), query_description_cosines=np.ones(3),
        reference=freeze_reference([[0.] * 5, [1.] * 5]),
    )


def test_explicit_coefficients_reorder_and_contributions_preserve_query_values():
    args = inputs()
    original_weights = args['query_facet_weights'].copy()
    result = retrieve_prepared_query(**args)
    ranking = result['ranking']
    assert ranking['ranked_chunk_ids'] == ['b', 'a', 'c']
    np.testing.assert_allclose(ranking['scores'], [.6, .81, 0])
    for row in ranking['rows']:
        assert row['score'] == pytest.approx(sum(
            w['contribution'] for w in row['provenance'].values() if w is not None))
        for f, witness in enumerate(row['provenance'].values()):
            if witness is not None:
                assert witness['u'] == original_weights[witness['query_tag_index'], f]
                assert witness['coefficient'] == args['coefficients'][f]
    np.testing.assert_array_equal(args['query_facet_weights'], original_weights)
    args['coefficients'] = [1, 0, .25, 0, 0]
    assert retrieve_prepared_query(**args)['ranking']['ranked_chunk_ids'] == ['a', 'b', 'c']


def test_recovered_sibling_has_source_context_but_no_invented_facet_evidence():
    args = inputs()
    args['query_tag_cosines'][1, :] = 0
    result = retrieve_prepared_query(**args)
    contexts = {c['chunk_id']: c for c in result['contexts']}
    assert set(contexts) == {'a', 'b'}  # c touches the same range but is another record
    assert contexts['b']['source_text'] == 'bbbbb'
    assert contexts['b']['nomination_score'] == 0
    assert all(v is None for v in contexts['b']['facet_provenance'].values())
    assert contexts['b']['recovery']['original_depth'] is None
    assert contexts['b']['recovery']['trigger_chunk_ids'] == ['a']
    assert contexts['b']['recovery']['context_added'] is True
    assert result['recruitment']['nomination']['unsupported_chunk_ids'] == ['b', 'c']


def test_budget_cannot_split_recovered_frontier_or_skip_it():
    args = inputs()
    args['query_tag_cosines'][1, :] = 0
    args['query_tag_cosines'][0, 2] = .1  # later supported singleton
    args['source_character_budget'] = 9
    result = retrieve_prepared_query(**args)
    assert result['contexts'] == []
    assert result['recruitment']['crossing_frontier_chunk_ids'] == ['a', 'b']
    assert result['recruitment']['unused_capacity'] == 9
    args['source_character_budget'] = 10
    exact = retrieve_prepared_query(**args)
    assert [c['chunk_id'] for c in exact['contexts']] == ['a', 'b']
    assert exact['recruitment']['selected_source_characters'] == 10
    assert exact['recruitment']['crossing_frontier_chunk_ids'] == ['c']


def test_graph_winner_is_preserved_while_final_coefficient_is_replaced():
    args = inputs()
    args['adjacency_pairs'] = [(0, 2), (1, 2)]
    bare = {k: v for k, v in args.items() if k not in
            {'chunk_rows', 'coefficients', 'source_character_budget'}}
    baseline = rank_facet_stream_envelope(chunk_ids=['a', 'b', 'c'], **bare)
    before = deepcopy(baseline['rows'])
    result = retrieve_prepared_query(**args)
    old = next(r for r in baseline['rows'] if r['chunk_id'] == 'c')
    new = next(r for r in result['ranking']['rows'] if r['chunk_id'] == 'c')
    for facet in ['topic', 'why']:
        assert new['provenance'][facet]['route_type'] == 'file_adjacency'
        for key, value in old['provenance'][facet].items():
            if key not in {'coefficient', 'contribution'}:
                assert new['provenance'][facet][key] == value
    assert baseline['rows'] == before
    assert new['score'] == pytest.approx(.5 * (.6 + .81))


def test_invalid_policy_rejected_before_scoring_and_misaligned_arrays_rejected(monkeypatch):
    import artefact.facet_retrieval_pipeline as pipeline
    with monkeypatch.context() as patch:
        def unexpected(**kwargs):
            pytest.fail('Invalid policy reached scoring')
        patch.setattr(pipeline, 'rank_facet_stream_envelope', unexpected)
        for coefficients in [[1, 0], [0, 1, 1, 1, 1], [-1, 0, 0, 0, 0],
                             [1, -.1, 0, 0, 0], [1, np.nan, 0, 0, 0], [np.inf, 0, 0, 0, 0]]:
            args = inputs()
            args['coefficients'] = coefficients
            with pytest.raises(ValueError, match='coefficients'):
                retrieve_prepared_query(**args)
        args = inputs()
        args['source_character_budget'] = True
        with pytest.raises(ValueError, match='budget'):
            retrieve_prepared_query(**args)
    args = inputs()
    args['query_chunk_cosines'] = np.ones((2, 2))
    with pytest.raises(ValueError, match='query_chunk_cosines'):
        retrieve_prepared_query(**args)
