"""Adapter checks with frozen development captures and mocked external boundaries.

Never opens benchmark questions, gold, raw products, or invokes model transports.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from types import SimpleNamespace

import numpy as np
import pytest
from threadpoolctl import threadpool_limits

from arms import artefact_facet_joint as A
from arms import artefact_v2 as V2
from harness.contract import ModelUsage


BASE = A.ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'


@pytest.fixture(scope='module')
def prepared():
    return A.prepare_over_corpus('unused-by-frozen-preparation')


def test_real_frozen_development_replay_scores_and_recovery_membership(prepared):
    captures = A._read(BASE / 'query_capture/query_captures.json')['captures']
    capture = next(c for c in captures if c['question_id'] == 'independent_durable_messages_current_models')
    query = next(q for q in A._read(BASE / 'query_snapshot/queries.json')['queries']
                 if q['generation_id'] == capture['generation_id'])
    values = {v['t']: v['facets'] for v in capture['readings'][0]['values']}
    weights = np.array([[values[t][f] for f in A.FACETS] for t in capture['clean_tags']])
    with np.load(BASE / 'query_snapshot/arrays.npz') as arrays:
        idx = query['query_tag_indices']
        di = query['description_index']
        matrices = {'query_tag_cosines': arrays['query_tag_graph_cos'][idx],
                    'query_chunk_cosines': arrays['query_tag_chunk_cos'][idx],
                    'query_description_cosines': arrays['description_chunk_cos'][di]}
        # Independently verify frozen graph-vector alignment used by fresh queries.
        np.testing.assert_allclose(arrays['query_tag_vectors'][idx] @ prepared.tag_vectors.T,
                                   matrices['query_tag_cosines'], atol=2e-15, rtol=0)
        np.testing.assert_allclose(arrays['query_tag_vectors'][idx] @ prepared.chunk_vectors.T,
                                   matrices['query_chunk_cosines'], atol=2e-15, rtol=0)
    with threadpool_limits(limits=4):
        result = A._rank(prepared, capture['question'],
                         {'description': capture['description'], 'tags': capture['clean_tags']},
                         weights, matrices)
    old_dir = BASE / 'demo_run/actiongenie-verified-area-reading0'
    archived = A._read(old_dir / 'retrieval.json')
    with np.load(old_dir / 'ranking_arrays.npz') as arrays:
        np.testing.assert_array_equal(result['ranking']['scores'], arrays['scores'])
        np.testing.assert_array_equal(result['ranking']['per_facet_scores'], arrays['per_facet_scores'])
    current, old = result['recruitment'], archived['recruitment']
    # The sponsor-first repair intentionally changes within-frontier order.
    # All saved evidence, depths, recovery triggers and budget membership must
    # still match exactly, independently of that ordering change.
    by_id = {row['chunk_id']: row for row in current['rows']}
    assert by_id == {row['chunk_id']: row for row in old['rows']}
    assert len(current['frontiers']) == len(old['frontiers'])
    for frontier, previous in zip(current['frontiers'], old['frontiers']):
        assert {**frontier, 'chunk_ids': sorted(frontier['chunk_ids'])} == {
            **previous, 'chunk_ids': sorted(previous['chunk_ids'])}
        advanced = [by_id[cid]['context_added'] for cid in frontier['chunk_ids']]
        assert advanced == sorted(advanced)
    for key in ('nomination', 'unsupported_chunk_ids'):
        assert current[key] == old[key]
    assert current['selected_chunk_ids'] == [cid for frontier in current['frontiers']
                                            for cid in frontier['chunk_ids']]
    # The archived demo used a whole-frontier research budget. Serving requests
    # an unlimited order and later applies the actual serialized character cut.
    budgeted = A.recruit_with_verified_area(
        chunk_rows=prepared.chunks, joint_scores=result['ranking']['scores'],
        area_chunk_ids=result['area']['area']['chunk_ids'],
        source_character_budget=old['source_character_budget'])['recruitment']
    assert set(budgeted['selected_chunk_ids']) == set(old['selected_chunk_ids'])
    assert budgeted['selected_source_characters'] == old['selected_source_characters']
    assert result['area']['area']['chunk_ids'] == archived['verified_area']['area']['chunk_ids']
    assert not prepared.edge_facets.flags.writeable
    assert not prepared.tag_vectors.flags.writeable


def test_actual_structural_capture_is_loaded_and_pinned(prepared):
    assert prepared.structural_index.provenance['structural_capture_sha256']==A.STRUCTURAL_SHA256
    assert prepared.structural_index.eligible==frozenset(c['chunkId'] for c in prepared.chunks)
    assert {key[0] for key in prepared.structural_index.nodes}=={'Product','Employee','Channel','Customer','Company'}


def test_rank_calls_structural_resolver_and_retains_global_access(monkeypatch):
    chunks=tuple({'chunkId':cid,'locator':{},'relpath':'synthetic','source_text':'unit'} for cid in 'abc')
    prepared=SimpleNamespace(chunks=chunks,edge_ids=[],edge_tag=[],edge_chunk=[],edge_facets=[],
        reference=None,groups={},adjacency_pairs=(),structural_index=object(),scope_scheduling='equal_depth')
    monkeypatch.setattr(A,'retrieve_prepared_query',lambda **kwargs:{'ranking':{'scores':np.array([.8,.7,.9])}})
    calls=[]
    def resolve(text,index):
        calls.append((text,index))
        return frozenset(['b']),{'status':'resolved','landings':[{'name':'synthetic person'}]}
    monkeypatch.setattr(A,'resolve_structural_area',resolve)
    result=A._rank(prepared,'person and product',{'tags':['semantic tag']},np.ones((1,5)),{})
    assert calls==[('person and product',prepared.structural_index)]
    assert result['area']['area']['chunk_ids']==['b']
    assert set(result['recruitment']['selected_chunk_ids'])==set('abc')
    np.testing.assert_array_equal(result['ranking']['scores'],[.8,.7,.9])


def test_embedding_text_transform_matches_actual_frozen_serving_helper():
    tags = ['  semantic_phrase  ', 'semantic phrase', 'semantic_phrase']
    expected = list(dict.fromkeys([V2._readable(tag) for tag in tags] + ['description']))
    assert A._query_embedding_texts('description', tags) == expected
    assert expected == ['semantic_phrase', 'semantic phrase', 'description']


def test_stage_cache_calls_once_for_concurrent_identical_requests_and_revalidates(tmp_path, monkeypatch):
    calls = []
    def post(path, payload, **kwargs):
        calls.append((path, payload, kwargs))
        return {'choices': [{'message': {'content': '{"description":"Review findings","tags":["semantic phrase"]}'}}],
                'usage': {'prompt_tokens': 12, 'completion_tokens': 6}}
    monkeypatch.setattr(A.chat, 'post', post)
    def request():
        return A._cached_stage('generate', 'system', 'user', A.S.parse_generate, tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: request(), range(2)))
    assert len(calls) == 1 and calls[0][2]['max_tries'] == 1
    assert sum(row[1].calls for row in rows) == 1
    assert sorted(row[2]['cache_hit'] for row in rows) == [False, True]
    assert rows[0][0] == rows[1][0]


def test_failed_or_uncertain_interpretation_never_retries(tmp_path, monkeypatch):
    calls = []
    def post(*args, **kwargs):
        calls.append(1)
        raise TimeoutError('private error')
    monkeypatch.setattr(A.chat, 'post', post)
    for _ in range(2):
        with pytest.raises(RuntimeError, match='key='):
            A._cached_stage('generate', 'system', 'user', A.S.parse_generate, tmp_path)
    assert len(calls) == 1
    for path in (tmp_path / 'generate').glob('*.json'):
        if not path.name.endswith('.started.json'):
            path.unlink()  # simulate started transport without completed result
    with pytest.raises(RuntimeError, match='uncertain'):
        A._cached_stage('generate', 'system', 'user', A.S.parse_generate, tmp_path)
    assert len(calls) == 1


def test_harness_budget_gets_full_recovered_order_and_artifact_ids(tmp_path, monkeypatch):
    chunks = tuple({'chunkId': cid} for cid in ('a', 'b', 'c'))
    prepared = SimpleNamespace(chunks=chunks, provenance={'frozen': True}, scope_scheduling='equal_depth')
    monkeypatch.setattr(A, '_interpret', lambda *args: (
        {'description': 'description', 'tags': ['tag']}, np.ones((1, 5)), ModelUsage(), {}))
    monkeypatch.setattr(A, '_query_cosines', lambda *args: ({}, ModelUsage(), {}))
    result = {'ranking': {'rows': [], 'ranked_chunk_ids': ['a', 'b', 'c']},
              'recruitment': {'selected_chunk_ids': ['b', 'a', 'c']}, 'area': {}}
    monkeypatch.setattr(A, '_rank', lambda *args: result)
    resolved = []
    def resolve(row, cache):
        resolved.append(row['chunkId'])
        return row['chunkId'] * 4, ['artifact-' + row['chunkId']]
    monkeypatch.setattr(V2, '_resolve_chunk', resolve)
    out = A.answer_one_question(('private-id', 'A development question'), prepared, None, k=1, char_budget=6)
    assert out.contexts == ['bbbb', 'aa']
    assert out.context_ids == ['artifact-b']  # shared helper excludes partial boundary's ID
    assert resolved == ['b', 'a']
    assert out.meta['full_recovered_order'] == ['b', 'a', 'c']  # k ignored in character-budget mode
    assert out.meta['delivered_chunk_ids'] == ['b', 'a']
    assert out.meta['char_budget']['boundary'] == {'id': 'a', 'chars_kept': 2, 'chars_full': 4}


def test_bad_budget_fails_before_interpretation(monkeypatch):
    monkeypatch.setattr(A, '_interpret', lambda *args: pytest.fail('must validate before calls'))
    with pytest.raises(ValueError, match='char_budget'):
        A.answer_one_question(('id', 'question'), None, None, char_budget=0)
