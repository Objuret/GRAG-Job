from dataclasses import replace
import json

import numpy as np
import pytest

from harness import chat
from harness.contract import BuildStats, ModelUsage
from arms import artefact_v4 as V
from artefact import query_content as Q
from artefact import v4_walk as WK

QUESTION = 'placeholder question'
TREE = 'A\n  documents'


def answer(*tags, asked=('asked phrase',)):
    def rows(names):
        return [{'t': name, 'facets': dict(zip(Q.FACETS, [1, .5, 0, .25, .75]))}
                for name in names]
    return {'description': 'Sought content', 'tags': rows(tags or ('one', 'two')),
            'query_tags': rows(asked)}


def prepared(tmp_path=None, **fields):
    base = dict(chunk_rows=(), chunk_ids=(), graph_tags=(), tag_vectors=np.eye(2),
                chunk_vectors=np.eye(2), layer={}, tree={'text': TREE, 'paths': {}},
                cache_dir=tmp_path, provenance={}, build_stats=BuildStats(0., ModelUsage(), []))
    return V.Prepared(**{**base, **fields})


def cached(folder, stage, system, user, schema, saved):
    signature = {'cache_version': 1, 'stage': stage, 'model': V.INTERPRET_MODEL,
                 'system': system, 'user': user, 'max_tries': 1, 'schema': schema}
    key = V._sha(json.dumps(signature, sort_keys=True, ensure_ascii=False))
    path = folder / stage / (key + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'signature': signature, **saved}), encoding='utf-8')
    return key, path


def no_model(monkeypatch):
    monkeypatch.setattr(chat, 'post', lambda *a, **k: (_ for _ in ()).throw(
        AssertionError('a model call')))


def test_the_tree_lists_products_kinds_and_channels_and_holds_each_places_chunks():
    rows = [{'product': 'B', 'channels': []}, {'product': 'A', 'channels': ['c2', 'c1']},
            {'product': 'A', 'channels': []}, {'product': 'A', 'channels': ['c1']},
            {'product': 'A', 'channels': []}]
    kinds = ['document', 'slack_thread_batch', 'pr_batch', 'slack_thread_batch', 'odd_kind']
    tree = V.scope_tree(rows, kinds, {'c1': 'bug-x-A', 'c2': 'plan/A'})
    assert tree['text'].split('\n') == [
        'A', '  odd kind', '  pull requests', '  slack threads', '    #bug-x-A', '    #plan-A',
        'B', '  documents']
    assert tree['products'] == 2 and tree['places'] == 8
    assert tree['paths']['A'] == {1, 2, 3, 4} and tree['paths']['B'] == {0}
    assert tree['paths']['A/slack threads/#bug-x-A'] == {1, 3}
    assert tree['paths']['A/slack threads/#plan-A'] == {1}
    with pytest.raises(ValueError, match='one record kind per chunk'):
        V.scope_tree(rows, kinds[:-1], {})
    # a returned place puts its whole product first; a path the tree lacks names no chunk
    first, scope = V.scope_first(('A/slack threads/#plan-A', 'Nowhere'), tree, 5)
    assert first.tolist() == [False, True, True, True, True]
    assert scope['places_in_the_tree'] == ['A/slack threads/#plan-A']
    assert scope['places_not_in_the_tree'] == ['Nowhere']
    assert scope['chunks_under_the_products'] == 4
    assert not V.scope_first((), tree, 5)[0].any()


def test_the_two_calls_are_asked_as_the_request_functions_write_them(monkeypatch, tmp_path):
    asked = []

    def asking(stage, system, user, validate, cache_dir, model=None, schema=None):
        asked.append((stage, system, user, schema, model))
        raw = {'places': ['A/documents']} if stage == 'scope' else answer()
        return validate(raw), ModelUsage(calls=1), {'cache_hit': False, 'key': 'k' + stage}

    monkeypatch.setattr(V, '_cached_stage', asking)
    monkeypatch.delenv('HERB_V4_OFFLINE', raising=False)
    content, usage, stages = V._interpret(QUESTION, prepared(tmp_path))
    first = Q.parse(QUESTION, answer())
    assert asked == [('querytag', *Q.request(QUESTION), V.INTERPRET_MODEL),
                     ('scope', *Q.scope_request(first, TREE), V.INTERPRET_MODEL)]
    # the first call carries no tree; the places come from the second; each has its schema
    assert TREE not in asked[0][1] and content.places == ('A/documents',)
    assert asked[0][3] == Q.SCHEMA and asked[1][3] == Q.PLACES_SCHEMA
    assert content.tags == first.tags and usage.calls == 2
    assert [(s['stage'], s['key'], s['asks']) for s in stages] == [
        ('querytag', 'kquerytag', 1), ('scope', 'kscope', 1)]
    monkeypatch.setenv('HERB_V4_OFFLINE', 'maybe')
    with pytest.raises(ValueError, match='HERB_V4_OFFLINE must be off or on'):
        V._interpret(QUESTION, prepared(tmp_path))


def test_offline_reads_both_answers_from_the_cache_and_asks_no_model(monkeypatch, tmp_path):
    no_model(monkeypatch)
    monkeypatch.setenv('HERB_V4_OFFLINE', 'on')
    held = prepared(tmp_path)
    with pytest.raises(RuntimeError, match='no cached querytagger answer'):
        V._interpret(QUESTION, held)
    first_key, _ = cached(tmp_path, 'querytag', *Q.request(QUESTION),
                          {'ok': True, 'raw': answer(), 'usage': {}})
    with pytest.raises(RuntimeError, match='no cached scope answer'):
        V._interpret(QUESTION, held)
    request = Q.scope_request(Q.parse(QUESTION, answer()), TREE)
    key, path = cached(tmp_path, 'scope', *request, {'ok': False})
    with pytest.raises(RuntimeError, match='cached scope answer is not a good answer'):
        V._interpret(QUESTION, held)
    assert path.exists()
    cached(tmp_path, 'scope', *request, {'ok': True, 'raw': {'places': ['A']}, 'usage': {}})
    content, usage, stages = V._interpret(QUESTION, held)
    assert content.places == ('A',) and usage.calls == 0
    assert [(s['stage'], s['key'], s['cache_hit']) for s in stages] == [
        ('querytag', first_key, True), ('scope', key, True)]


def test_an_unusable_answer_is_asked_once_more_and_no_more(monkeypatch, tmp_path):
    monkeypatch.delenv('HERB_V4_OFFLINE', raising=False)
    key = 'k' * 64
    folder = tmp_path / 'scope'
    folder.mkdir()
    saved, marker = folder / (key + '.json'), folder / (key + '.started.json')
    calls = []

    def attempt(good_from):
        def asking(stage, system, user, validate, cache_dir, model=None, schema=None):
            calls.append(stage)
            if stage == 'querytag':
                return validate(answer()), ModelUsage(), {'cache_hit': True, 'key': 'q'}
            if calls.count('scope') < good_from:
                marker.write_text('{}', encoding='utf-8')
                saved.write_text(json.dumps({'ok': False}), encoding='utf-8')
                raise RuntimeError(f'Facet interpreter scope failed; key={key}; no retry')
            return validate({'places': ['A']}), ModelUsage(calls=1), {'cache_hit': False,
                                                                      'key': key}
        return asking

    monkeypatch.setattr(V, '_cached_stage', attempt(good_from=2))
    content, _, stages = V._interpret(QUESTION, prepared(tmp_path))
    assert calls == ['querytag', 'scope', 'scope'] and content.places == ('A',)
    assert stages[1]['asks'] == 2 and not saved.exists() and not marker.exists()
    del calls[:]
    monkeypatch.setattr(V, '_cached_stage', attempt(good_from=3))
    with pytest.raises(RuntimeError, match='scope failed'):
        V._interpret(QUESTION, prepared(tmp_path))
    assert calls == ['querytag', 'scope', 'scope']
    # a marker another worker wrote is left alone
    del calls[:]
    saved.unlink()

    def in_flight(stage, system, user, validate, cache_dir, model=None, schema=None):
        raise RuntimeError(f'Facet interpreter uncertain {stage} attempt; key={key}')

    monkeypatch.setattr(V, '_cached_stage', in_flight)
    with pytest.raises(RuntimeError, match='uncertain'):
        V._interpret(QUESTION, prepared(tmp_path))
    assert marker.exists()


def toy_prepared(seed=3, chunks=30, tags=20):
    rng = np.random.default_rng(seed)
    eligible = np.ones(tags, dtype=bool)
    eligible[0] = False
    pairs = sorted({(c, int(t)) for c in range(chunks)
                    for t in rng.choice(tags, size=3, replace=False)})
    edge_chunk, edge_tag = (np.array(column) for column in zip(*pairs))
    ptr = np.zeros(chunks + 1, dtype=np.int64)
    ptr[1:] = np.cumsum([1 if c in (0, 1) else 0 for c in range(chunks)])
    product = np.arange(chunks) % 3
    ids = tuple(f'c{c:02d}' for c in range(chunks))
    layer = WK.build_layer(ids, ['document'] * chunks, eligible, edge_tag, edge_chunk,
                           rng.uniform(0, .5, size=edge_tag.size),
                           rng.normal(size=(edge_tag.size, 4)), (.8, 1.1, .9, 1.3), .9, product,
                           ptr, np.array([1, 0]))
    paths = {name: frozenset(np.flatnonzero(product == p).tolist())
             for p, name in enumerate('ABC')}
    cosines = {'tags': rng.normal(.7, .06, size=(3, tags)),
               'description': rng.normal(.2, .06, size=chunks),
               'tags_to_description': np.array([.4, .8, .6]),
               'question': rng.normal(.18, .06, size=chunks)}
    held = prepared(chunk_rows=tuple({'chunkId': c} for c in ids), chunk_ids=ids, layer=layer,
                    tree={'text': TREE, 'paths': paths})
    return held, cosines, product


def test_a_question_is_ordered_by_the_chain_with_the_returned_product_first(monkeypatch):
    no_model(monkeypatch)
    held, cosines, product = toy_prepared()
    content = Q.parse(QUESTION, answer('one', 'two', asked=('three',)))
    content = replace(content, places=('B/documents', 'B', 'Gone'))
    monkeypatch.setattr(V, '_interpret', lambda text, p: (content, ModelUsage(), []))

    def tag_cosines(description, tags, p):
        rows = slice(0, 2) if tags == ['one', 'two'] else slice(2, 3)
        return ({'tags': cosines['tags'][rows], 'description': cosines['description'],
                 'tags_to_description': cosines['tags_to_description'][rows]},
                ModelUsage(), {'vector_sha256': 'v'})

    def question_cosines(text, tags, p):
        assert text == QUESTION and tags == []
        return ({'query_description_cosines': cosines['question']}, ModelUsage(),
                {'vector_sha256': 'q'})

    def budget(rows, char_budget, docs):
        kept = rows[:6]
        return ([r['chunkId'] for r in kept], [[r['chunkId']] for r in kept],
                [r['chunkId'] for r in kept], {'kept': 5, 'boundary': {'id': kept[5]['chunkId']}})

    monkeypatch.setattr(V, '_tag_cosines', tag_cosines)
    monkeypatch.setattr(V, '_query_cosines', question_cosines)
    monkeypatch.setattr(V, '_budget_contexts', budget)
    out = V.answer_one_question(('q', QUESTION), held, None, 50, 100)
    walked = WK.chain(held.layer, {
        'cosines': cosines['tags'],
        'readings': np.array([t.readings for t in (*content.tags, *content.query_tags)]),
        'description_cosines': cosines['tags_to_description'],
        'd_description': cosines['description'], 'd_question': cosines['question']}, V.COS_NOISE)
    # the chunks of product B first, each part in the chain's own order; nothing removed
    in_b = [i for i in walked['order'] if product[i] == 1]
    rest = [i for i in walked['order'] if product[i] != 1]
    ranking = out.meta['ranking']
    assert ranking['ordered_chunk_ids'] == [held.chunk_ids[i] for i in in_b + rest]
    assert ranking['delivered_chunk_ids'] == [held.chunk_ids[i] for i in in_b[:5]]
    assert out.context_ids == [held.chunk_ids[i] for i in in_b[:6]]
    # a delivered chunk's four terms add up to its strength
    terms = ranking['delivered_terms']
    assert [sum(terms[name][k] for name in V.TERMS) for k in range(5)] == pytest.approx(
        ranking['delivered_strength'])
    assert ranking['delivered_strength'] == [float(walked['strength'][i]) for i in in_b[:5]]
    scope = out.meta['scope']
    assert scope['places_in_the_tree'] == ['B'] and scope['places_not_in_the_tree'] == [
        'B/documents', 'Gone']
    assert scope['chunks_under_the_products'] == 10
    assert scope['delivered_under_the_products'] == 5
    assert out.meta['diagnostics']['query_tags'] == 3
    assert out.answer == '' and out.retrieval.calls == 0
