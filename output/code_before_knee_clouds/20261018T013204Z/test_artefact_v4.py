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
        return [{'t': name, 'facet': 'why'}
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
    # a channel the names do not hold stands under its id
    assert V.scope_tree(rows, kinds, {})['paths']['A/slack threads/#c2'] == {1}
    assert [path for path, _ in V.tree_level(tree, 'product')] == ['A', 'B']
    with pytest.raises(ValueError, match='one record kind per chunk'):
        V.scope_tree(rows, kinds[:-1], {})


def test_the_first_call_is_asked_as_the_request_function_writes_it(monkeypatch, tmp_path):
    asked = []

    def asking(stage, system, user, validate, cache_dir, model=None, schema=None):
        asked.append((stage, system, user, schema, model))
        return validate(answer()), ModelUsage(calls=1), {'cache_hit': False, 'key': 'k' + stage}

    monkeypatch.setattr(V, '_cached_stage', asking)
    monkeypatch.delenv('HERB_V4_OFFLINE', raising=False)
    content, usage, stages = V._interpret(QUESTION, prepared(tmp_path))
    # one call, asked as the request function writes it, with its schema; no tree in it
    assert asked == [('querytag', *Q.request(QUESTION), V.INTERPRET_MODEL)]
    assert asked[0][3] == Q.SCHEMA and TREE not in asked[0][1]
    assert content == Q.parse(QUESTION, answer()) and usage.calls == 1
    assert [(s['stage'], s['key'], s['asks']) for s in stages] == [('querytag', 'kquerytag', 1)]
    monkeypatch.setenv('HERB_V4_OFFLINE', 'maybe')
    with pytest.raises(ValueError, match='HERB_V4_OFFLINE must be off or on'):
        V._interpret(QUESTION, prepared(tmp_path))


def test_offline_reads_the_answer_from_the_cache_and_asks_no_model(monkeypatch, tmp_path):
    no_model(monkeypatch)
    monkeypatch.setenv('HERB_V4_OFFLINE', 'on')
    held = prepared(tmp_path)
    with pytest.raises(RuntimeError, match='no cached querytagger answer'):
        V._interpret(QUESTION, held)
    key, path = cached(tmp_path, 'querytag', *Q.request(QUESTION), {'ok': False})
    with pytest.raises(RuntimeError, match='cached querytagger answer is not a good answer'):
        V._interpret(QUESTION, held)
    assert path.exists()
    cached(tmp_path, 'querytag', *Q.request(QUESTION), {'ok': True, 'raw': answer(), 'usage': {}})
    content, usage, stages = V._interpret(QUESTION, held)
    assert content == Q.parse(QUESTION, answer()) and usage.calls == 0
    assert [(s['stage'], s['key'], s['cache_hit']) for s in stages] == [('querytag', key, True)]


def test_an_unusable_answer_is_asked_once_more_and_no_more(monkeypatch, tmp_path):
    monkeypatch.delenv('HERB_V4_OFFLINE', raising=False)
    key = 'k' * 64
    folder = tmp_path / 'querytag'
    folder.mkdir()
    saved, marker = folder / (key + '.json'), folder / (key + '.started.json')
    calls = []

    def attempt(good_from):
        def asking(stage, system, user, validate, cache_dir, model=None, schema=None):
            calls.append(stage)
            if len(calls) < good_from:
                marker.write_text('{}', encoding='utf-8')
                saved.write_text(json.dumps({'ok': False}), encoding='utf-8')
                raise RuntimeError(f'Facet interpreter querytag failed; key={key}; no retry')
            return validate(answer()), ModelUsage(calls=1), {'cache_hit': False, 'key': key}
        return asking

    monkeypatch.setattr(V, '_cached_stage', attempt(good_from=2))
    content, _, stages = V._interpret(QUESTION, prepared(tmp_path))
    assert calls == ['querytag', 'querytag'] and content == Q.parse(QUESTION, answer())
    assert stages[0]['asks'] == 2 and not saved.exists() and not marker.exists()
    del calls[:]
    monkeypatch.setattr(V, '_cached_stage', attempt(good_from=3))
    with pytest.raises(RuntimeError, match='querytag failed'):
        V._interpret(QUESTION, prepared(tmp_path))
    assert calls == ['querytag', 'querytag']
    # a marker another worker wrote is left alone
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
    product = np.arange(chunks) % 3
    ids = tuple(f'c{c:02d}' for c in range(chunks))
    layer = WK.build_layer(ids, ['document'] * chunks, eligible, edge_tag, edge_chunk,
                           rng.uniform(0, .5, size=edge_tag.size),
                           rng.normal(size=(edge_tag.size, 4)))
    paths = {name: frozenset(np.flatnonzero(product == p).tolist())
             for p, name in enumerate('ABC')}
    cosines = {'tags': rng.normal(.7, .06, size=(3, tags)),
               'description': rng.normal(.2, .06, size=chunks),
               'tags_to_description': np.array([.4, .8, .6]),
               'question': rng.normal(.18, .06, size=chunks)}
    held = prepared(chunk_rows=tuple({'chunkId': c, 'parent': f'P{k % 4}'}
                                     for k, c in enumerate(ids)), chunk_ids=ids, layer=layer,
                    tree={'text': TREE, 'paths': paths})
    return held, cosines, product


def test_the_border_the_question_names_and_the_two_clouds_order_it(monkeypatch):
    monkeypatch.setenv('HERB_V4_K', '3')
    no_model(monkeypatch)
    held, cosines, product = toy_prepared()
    held = replace(held, graph_tags=tuple(f't{t:02d}' for t in range(20)))
    asked, bare = 'What did B decide, and why?', 'What did the product decide, and why?'
    without_the_name = np.random.default_rng(11).normal(.2, .06, size=30)
    texts = []

    def tag_cosines(description, tags, p):
        rows = slice(0, 2) if tags == ['one', 'two'] else slice(2, 3)
        return ({'tags': cosines['tags'][rows], 'description': cosines['description'],
                 'tags_to_description': cosines['tags_to_description'][rows]},
                ModelUsage(), {'vector_sha256': 'v'})

    def question_cosines(text, tags, p):
        texts.append(text)
        near = cosines['question'] if text in (asked, QUESTION) else without_the_name
        return {'query_description_cosines': near}, ModelUsage(), {'vector_sha256': 'q'}

    def hand_over(order, p, char_budget, k, docs):
        kept = list(order)[:6]
        record = {'products': {}, 'chunks_gone_through': 6,
                  'chunks_with_nothing_handed_over': {}, 'records_left_out': {},
                  'conversations_handed_over': 0, 'conversations_reaching_into_another_chunk': 0}
        return ([held.chunk_ids[i] for i in kept], [[held.chunk_ids[i]] for i in kept],
                [held.chunk_ids[i] for i in kept],
                {'budget': char_budget, 'kept': 5, 'boundary': {'id': held.chunk_ids[kept[5]]}},
                kept[:5], {'record': record, 'per_chunk': {}})

    monkeypatch.setattr(V, '_interpret', lambda text, p: (
        Q.parse(text, answer('one', 'two', asked=('three',))), ModelUsage(), []))
    monkeypatch.setattr(V, '_tag_cosines', tag_cosines)
    monkeypatch.setattr(V, '_query_cosines', question_cosines)
    monkeypatch.setattr(V, '_hand_over', hand_over)
    monkeypatch.setattr(V, '_storyline_pairs', lambda chosen, chunks: [])   # no tie: the clouds' order
    # facet readings in no level of any facet: the facets weigh nothing
    monkeypatch.setattr(V, '_query_facet_readings', lambda query, phrases: np.full((3, 4), -9.))
    out = V.answer_one_question(('q', asked), held, None, 50, 100)
    # the question is embedded as asked and with the border's name taken out
    assert texts == [asked, bare]
    parent_of = np.arange(30) % 4
    inside = np.flatnonzero(product == 1)
    combo = WK.cloud_combo(held.layer, cosines['tags'], without_the_name, inside, parent_of, 3)
    ranking, scope = out.meta['ranking'], out.meta['scope']
    # the border is the named branch; inside it the order is the two clouds' with the scope
    assert ranking['ordered_chunk_ids'] == [held.chunk_ids[i] for i in combo['order']]
    assert ranking['delivered_chunk_ids'] == [held.chunk_ids[i] for i in combo['order'][:5]]
    assert out.context_ids == [held.chunk_ids[i] for i in combo['order'][:6]]
    assert scope['names_in_the_question'] == ['B'] and not scope['nothing_cut']
    assert scope['chunks_kept'] == 10 and scope['chunks_cut'] == 20
    assert scope['chunks_under_the_products'] == 10 and scope['delivered_under_the_products'] == 5
    assert scope['combo'] == {**combo['record'],
                              'scopes_taken': [f'P{s}' for s in combo['record']['scopes_taken']]}
    assert scope['facets']['weights'] == {'the question': [0., 0., 0., 0.]}
    assert scope['facets']['chunks_whose_nearness_changed'] == 0
    delivered = combo['order'][:5]
    assert ranking['delivered_step'] == [int(combo['step'][i]) for i in delivered]
    assert ranking['delivered_step'] == sorted(ranking['delivered_step'])
    assert ranking['delivered_in_scope'] == [bool(combo['in_scope'][i]) for i in delivered]
    assert ranking['delivered_description_nearness'] == [float(without_the_name[i]) for i in delivered]
    assert ranking['delivered_question_nearness'] == [float(cosines['question'][i]) for i in delivered]
    assert ranking['delivered_query_description_nearness'] == [float(cosines['description'][i])
                                                              for i in delivered]
    assert ranking['delivered_graph_tags'] == [
        held.graph_tags[int(held.layer['edge_tag'][combo['edge'][i]])] for i in delivered]
    diagnostics = out.meta['diagnostics']
    assert diagnostics['query_tags'] == 3 and diagnostics['named_facets'] == ['why'] * 3
    assert sum(diagnostics['delivered_on_each_step'].values()) == 5
    assert diagnostics['boundary_chunk_id_not_credited'] == held.chunk_ids[combo['order'][5]]
    assert out.meta['interpreter']['embeddings']['question_without_the_names']['text_chars'] == len(bare)
    assert out.answer == '' and out.retrieval.calls == 0
    # a question that holds no name of the tree: nothing is cut and nothing is taken out
    del texts[:]
    out = V.answer_one_question(('q', QUESTION), held, None, 50, 100)
    whole = WK.cloud_combo(held.layer, cosines['tags'], cosines['question'], np.arange(30), parent_of, 3)
    assert texts == [QUESTION, QUESTION] and out.meta['scope']['nothing_cut']
    assert out.meta['scope']['names_in_the_question'] == []
    assert out.meta['ranking']['ordered_chunk_ids'] == [held.chunk_ids[i] for i in whole['order']]
    # the name is matched as whole words, case left aside, and several names can stand there
    first, said = V.scope_by_name('about c and the Bb, then A.', held.tree, 30)
    assert said['names_in_the_question'] == ['A', 'C'] and int(first.sum()) == 20
    # each name gives way to "the" and the tree's word for its level; the sentence stays whole
    assert V._without_names('About c and the Bb, then A.', ['A', 'C']) == (
        'About the product and the Bb, then the product.')
    assert V._without_names("What is b's plan?", ['B']) == "What is the product's plan?"
    assert V._without_names(QUESTION, []) == QUESTION


def test_the_graphs_people_say_which_channel_is_apart_and_who_the_products_people_are():
    channels = [{'product': 'B', 'channel': 'ch-own', 'people': ['e1', 'e2']},
                {'product': 'B', 'channel': 'ch-more', 'people': ['e2', 'e3']},
                {'product': 'B', 'channel': 'ch-apart', 'people': ['x1', 'x2']},
                {'product': 'B', 'channel': 'ch-empty', 'people': [None]},
                {'product': 'B', 'channel': 'ch-met', 'people': ['m1']},
                {'product': 'C', 'channel': 'ch-one', 'people': ['x1']}]
    meetings = [{'product': 'B', 'people': ['m1', 'm2']}]
    persons = V.product_persons(channels, meetings)
    # ch-apart: its employees post in no other channel of B and sit in none of its meetings;
    # a channel with no employee is not apart; one whose only employee sits in a meeting is not
    assert persons['B']['apart'] == {'ch-apart'}
    assert persons['B']['people'] == {'e1', 'e2', 'e3', 'm1', 'm2'}
    # a product's one channel with employees and no meeting: nothing else to be tied to
    assert persons['C'] == {'apart': frozenset({'ch-one'}), 'people': frozenset()}


def own_work_corpus():
    """One product, B: a channel of its own with four conversations (A links to an own pull
    request, B to another project's only, C to nothing, D to another project's and to an own
    document), a channel apart, two batches of pull requests and a document."""
    day = 86400

    def message(mid, at, text='', channel='ch-own'):
        stamp = (V.datetime(2026, 1, 1) + (V.datetime(1970, 1, 2) - V.datetime(1970, 1, 1)) * (at / day))
        return {'id': mid, 'Channel': {'channelID': channel},
                'Message': {'User': {'timestamp': stamp.isoformat(), 'text': text}}}

    own_pr = {'id': 'pr1', 'user': {'login': 'e1'}, 'link': 'https://github.com/x/own/pull/1'}
    other_pr = {'id': 'pr2', 'user': {'login': 'EMP_9'}, 'link': 'https://github.com/y/other/pull/7'}
    more_pr = {'id': 'pr3', 'user': {'login': 'EMP_8'}, 'link': 'https://github.com/y/other/pull/8'}
    document = {'id': 'doc1', 'document_link': 'https://docs.example/own_doc'}
    m = [message('m1', 0, 'please check https://github.com/x/own/pull/1.'),
         message('m2', 120), message('m3', 300),
         message('m4', day, 'see https://github.com/y/other/pull/7'), message('m5', day + 180),
         message('m6', 3 * day), message('m7', 3 * day + 60), message('m8', 3 * day + 240),
         message('m9', 10 * day, 'like https://github.com/y/other/pull/8 and '
                                 '<https://docs.example/own_doc|the document>')]
    records = {'s1': m[0:2], 's2': m[2:6], 's3': m[6:9],
               's4': [message('x1', 0, channel='ch-apart'), message('x2', 60, channel='ch-apart')],
               # two channels bear one name: the graph ties this batch to both
               's5': [message('x3', 120, channel='ch-apart'), message('m10', 30 * day)],
               'p1': [own_pr, other_pr], 'p2': [more_pr], 'd1': [document]}
    kinds = {'s1': 'slack_thread_batch', 's2': 'slack_thread_batch', 's3': 'slack_thread_batch',
             's4': 'slack_thread_batch', 's5': 'slack_thread_batch', 'p1': 'pr_batch',
             'p2': 'pr_batch', 'd1': 'document'}
    channels = {'s1': ['ch-own'], 's2': ['ch-own'], 's3': ['ch-own'], 's4': ['ch-apart'],
                's5': ['ch-apart', 'ch-own']}
    ids = tuple(sorted(records))
    rows = tuple({'chunkId': c, 'kind': kinds[c], 'product': 'B', 'channels': channels.get(c, [])}
                 for c in ids)
    held = prepared(chunk_rows=rows, chunk_ids=ids, persons={
        'B': {'apart': frozenset({'ch-apart'}), 'people': frozenset({'e1', 'e2'})}})
    return held, records


def test_what_is_handed_over_is_the_products_own_work_and_conversations_whole(monkeypatch):
    held, records = own_work_corpus()
    at = {c: i for i, c in enumerate(held.chunk_ids)}
    monkeypatch.setattr(V, '_pointed_records', lambda row, cache: records[row['chunkId']])
    monkeypatch.setattr(V, '_resolve_chunk', lambda row, cache: (
        'the document as it is', [r['id'] for r in records[row['chunkId']]]))
    order = [at[c] for c in ('s2', 's4', 'p1', 'p2', 'd1', 's1', 's3', 's5')]
    book = V.own_work(order, held, {})
    assert book['apart'] == {'x1', 'x2', 'x3'}
    assert book['own'] == {'pr1': True, 'pr2': False, 'pr3': False}
    talks = [book['talk'][f'm{k}'][2] for k in range(1, 11)]
    assert talks == [0, 0, 0, 1, 1, 2, 2, 2, 3, 4]
    # B links to another project's pull request only; D links to one and to an own document
    assert {key[2] for key in book['other']} == {1}
    contexts, id_lists, context_ids, budget, delivered, handed = V._hand_over(order, held, None, 10, {})
    lines = lambda names: '\n'.join(json.dumps(r, ensure_ascii=False)       # noqa: E731
                                    for c, k in names for r in [records[c][k]])
    # s2 holds the end of A, all of B and the start of C: A and C go whole, B is left out
    assert id_lists == [['m1', 'm2', 'm3', 'm6', 'm7', 'm8'], ['pr1'], ['doc1'], ['m9'], ['m10']]
    assert contexts[0] == lines([('s1', 0), ('s1', 1), ('s2', 0), ('s2', 3), ('s3', 0), ('s3', 1)])
    assert contexts[1] == lines([('p1', 0)]) and contexts[2] == 'the document as it is'
    assert delivered == [at['s2'], at['p1'], at['d1'], at['s3'], at['s5']] and budget is None
    assert context_ids == ['m1', 'm2', 'm3', 'm6', 'm7', 'm8', 'pr1', 'doc1', 'm9', 'm10']
    assert handed['record'] == {
        'products': {'B': {'channels_apart': ['ch-apart'], 'people': 2}},
        'chunks_gone_through': 8,
        'chunks_with_nothing_handed_over': {'in_a_channel_apart': 1, 'no_own_pull_request': 1,
                                            'no_conversation_left': 1},
        'records_left_out': {'messages_of_a_channel_apart': 3,
                             'pull_requests_of_other_projects': 2,
                             'messages_about_another_projects_pull_request': 2},
        'conversations_handed_over': 4, 'conversations_reaching_into_another_chunk': 2}
    assert handed['per_chunk'] == {'delivered_records': [6, 1, 1, 1, 1],
                                   'delivered_records_of_other_chunks': [4, 0, 0, 0, 0],
                                   'delivered_records_not_handed_over': [2, 1, 0, 2, 1]}
    # the harness's cut: the text that does not fit is cut where the budget ends and not credited
    room = len(contexts[0]) + len(contexts[1]) + 5
    contexts, id_lists, context_ids, budget, delivered, handed = V._hand_over(order, held, room, 10, {})
    assert delivered == [at['s2'], at['p1']] and context_ids[-1] == 'pr1'
    assert budget == {'budget': room, 'chars': room, 'kept': 2, 'exhausted': False,
                      'boundary': {'id': 'd1', 'chars_kept': 5, 'chars_full': 21}}
    assert len(id_lists) == 3 and contexts[2] == 'the d'
    assert handed['record']['chunks_gone_through'] == 5       # the order was left where it ended
    # with no budget the first k texts
    assert V._hand_over(order, held, None, 2, {})[4] == [at['s2'], at['p1']]
    with pytest.raises(ValueError, match="graph's people were not read"):
        V.own_work(order, replace(held, persons=None), {})
    # a message in a channel the graph does not tie its chunk to is a fault in the graph
    records['s1'][0]['Channel']['channelID'] = 'ch-unknown'
    with pytest.raises(ValueError, match='the graph does not tie the chunk to'):
        V.own_work(order, held, {})


def test_the_facets_weigh_the_tags_and_the_own_work_is_handed_over(monkeypatch):
    monkeypatch.setenv('HERB_V4_K', '3')
    no_model(monkeypatch)
    held, cosines, product = toy_prepared()
    held = replace(held, graph_tags=tuple(f't{t:02d}' for t in range(20)))
    asked = 'What did B decide, and why?'
    without_the_name = np.random.default_rng(11).normal(.2, .06, size=30)
    seen = {}
    record = {'products': {}, 'chunks_gone_through': 4,
              'chunks_with_nothing_handed_over': {'in_a_channel_apart': 1, 'no_own_pull_request': 0,
                                                  'no_conversation_left': 0},
              'records_left_out': {'messages_of_a_channel_apart': 13,
                                   'pull_requests_of_other_projects': 0,
                                   'messages_about_another_projects_pull_request': 3},
              'conversations_handed_over': 2, 'conversations_reaching_into_another_chunk': 0}

    def hand_over(order, p, char_budget, k, docs):
        seen['order'], seen['budget'] = list(order), char_budget
        kept = list(order)[1:4]                       # the first chunk had nothing to hand over
        return (['one', 'two', 'thr'], [['a'], ['b'], ['c']], ['a', 'b'],
                {'budget': char_budget, 'chars': 8, 'kept': 2, 'exhausted': False,
                 'boundary': {'id': 'c', 'chars_kept': 3, 'chars_full': 9}}, kept[:2],
                {'record': record,
                 'per_chunk': {'delivered_records': [1, 1],
                               'delivered_records_of_other_chunks': [0, 0],
                               'delivered_records_not_handed_over': [3, 0]}})

    monkeypatch.setattr(V, '_interpret', lambda text, p: (
        Q.parse(text, answer('one', 'two', asked=('three',))), ModelUsage(), []))
    monkeypatch.setattr(V, '_tag_cosines', lambda description, tags, p: (
        {'tags': cosines['tags'][slice(0, 2) if tags == ['one', 'two'] else slice(2, 3)],
         'description': cosines['description'],
         'tags_to_description': cosines['tags_to_description'][
             slice(0, 2) if tags == ['one', 'two'] else slice(2, 3)]},
        ModelUsage(), {'vector_sha256': 'v'}))
    monkeypatch.setattr(V, '_query_cosines', lambda text, tags, p: (
        {'query_description_cosines': cosines['question'] if text == asked else without_the_name},
        ModelUsage(), {'vector_sha256': 'q'}))
    monkeypatch.setattr(V, '_hand_over', hand_over)
    monkeypatch.setattr(V, '_storyline_pairs', lambda chosen, chunks: [])   # no tie: the clouds' order
    # the facet net's four scores per query tag: high enough in every facet for the first two
    readings = np.array([[9., 8., 7., 6.], [9., 9., 9., 9.], [-9., -9., -9., -9.]])
    monkeypatch.setattr(V, '_query_facet_readings', lambda query, phrases: readings)
    out = V.answer_one_question(('q', asked), held, None, 50, 100)
    inside = np.flatnonzero(product == 1)
    rows = cosines['tags']
    found, _ = WK.tags_nearness(held.layer, rows)
    floors = WK.facet_levels(held.layer['raw'][:, 1:])
    weights = V._facet_weights(np.median(readings, axis=0), floors)
    assert weights == [1., 1., 1., 1.]
    dealt, _, _ = WK.facet_influenced_nearness(held.layer, rows, np.array([weights] * 3))
    combo = WK.cloud_combo(held.layer, rows, without_the_name, inside, np.arange(30) % 4, 3,
                           tags_near=dealt)
    # the query's facets weigh the tag relationship and the order follows; what is handed over
    # is the arm's own
    assert seen == {'order': combo['order'], 'budget': 100}
    ranking, scope = out.meta['ranking'], out.meta['scope']
    delivered = combo['order'][1:3]
    assert ranking['ordered_chunk_ids'] == [held.chunk_ids[i] for i in combo['order']]
    assert ranking['delivered_chunk_ids'] == [held.chunk_ids[i] for i in delivered]
    assert ranking['delivered_step'] == [int(combo['step'][i]) for i in delivered]
    assert ranking['delivered_records_not_handed_over'] == [3, 0]
    # each delivered chunk keeps, as pointers, the query tag that found it and its closeness as
    # found beside the one dealt
    phrases = ['one', 'two', 'three']
    assert ranking['delivered_query_tag_phrases'] == [phrases[int(combo['query_tag'][i])]
                                                      for i in delivered]
    assert ranking['delivered_tags_nearness'] == [float(dealt[i]) for i in delivered]
    assert ranking['delivered_tags_nearness_as_found'] == [float(found[i]) for i in delivered]
    facets = scope['facets']
    assert facets['weights'] == {'the question': [1., 1., 1., 1.]}
    assert facets['readings'] == {p: [float(r) for r in row] for p, row in zip(phrases, readings)}
    assert facets['chunks_whose_nearness_changed'] == int(sum(dealt[i] != found[i] for i in inside))
    assert scope['delivered_under_the_products'] == 2
    assert out.meta['handed_over'] == record
    assert out.contexts == ['one', 'two', 'thr'] and out.context_ids == ['a', 'b']
    assert out.meta['chunk_ids'] == [['a'], ['b'], ['c']] and out.meta['returned'] == 3
    assert out.meta['diagnostics']['boundary_chunk_id_not_credited'] == 'c'
    assert out.meta['diagnostics']['credited_delivered_rows'] == 2
    assert out.answer == '' and out.retrieval.calls == 0


def test_the_4combo_orders_the_border_by_how_strongly_each_chunk_is_tied_to_the_chosen(monkeypatch):
    monkeypatch.setenv('HERB_V4_K', '3')
    no_model(monkeypatch)
    held, cosines, product = toy_prepared()
    held = replace(held, graph_tags=tuple(f't{t:02d}' for t in range(20)))
    asked = 'What did B decide, and why?'
    without_the_name = np.random.default_rng(11).normal(.2, .06, size=30)
    seen, asked_of_the_graph = {}, []

    def hand_over(order, p, char_budget, k, docs):
        seen['order'] = list(order)
        kept = list(order)[:3]
        record = {'products': {}, 'chunks_gone_through': 3,
                  'chunks_with_nothing_handed_over': {}, 'records_left_out': {},
                  'conversations_handed_over': 0, 'conversations_reaching_into_another_chunk': 0}
        return (['a', 'b', 'c'], [['a'], ['b'], ['c']], ['a', 'b', 'c'],
                {'budget': char_budget, 'kept': 3, 'boundary': None}, kept,
                {'record': record, 'per_chunk': {}})

    monkeypatch.setattr(V, '_interpret', lambda text, p: (
        Q.parse(text, answer('one', 'two', asked=('three',))), ModelUsage(), []))
    monkeypatch.setattr(V, '_tag_cosines', lambda description, tags, p: (
        {'tags': cosines['tags'][slice(0, 2) if tags == ['one', 'two'] else slice(2, 3)],
         'description': cosines['description'],
         'tags_to_description': cosines['tags_to_description'][
             slice(0, 2) if tags == ['one', 'two'] else slice(2, 3)]},
        ModelUsage(), {'vector_sha256': 'v'}))
    monkeypatch.setattr(V, '_query_cosines', lambda text, tags, p: (
        {'query_description_cosines': cosines['question'] if text == asked else without_the_name},
        ModelUsage(), {'vector_sha256': 'q'}))
    monkeypatch.setattr(V, '_hand_over', hand_over)
    monkeypatch.setattr(V, '_query_facet_readings', lambda query, phrases: np.full((3, 4), -9.))
    inside = np.flatnonzero(product == 1)
    combo = WK.cloud_combo(held.layer, cosines['tags'], without_the_name, inside, np.arange(30) % 4, 3)
    steps = combo['step'][inside]
    chosen = [int(i) for i in combo['order'] if combo['step'][i] == steps.min()]
    others = [int(i) for i in combo['order'] if int(i) not in chosen]
    last, second_last = others[-1], others[-2]

    def pairs(chosen_ids, chunk_ids):
        asked_of_the_graph.append((list(chosen_ids), list(chunk_ids)))
        # the clouds' last chunk is tied to every chosen chunk by scope and a person; the one before
        # it to one chosen chunk by scope; nothing else is tied, and no chunk has a time
        rows = []
        for s in chosen_ids:
            for c in chunk_ids:
                rows.append({'start': s, 'chunk': c,
                             'same_parent': c == held.chunk_ids[last] or (
                                 c == held.chunk_ids[second_last] and s == chosen_ids[0]),
                             'shares_person': c == held.chunk_ids[last], 'gap': None})
        return rows

    monkeypatch.setattr(V, '_storyline_pairs', pairs)
    # the query tags' closeness is made alike for every chunk, so no pair is near in what the query
    # asks about and only the graph's ties count
    monkeypatch.setattr(WK, 'query_tag_profiles', lambda layer, on_edge: np.full((30, 3), np.nan))
    out = V.answer_one_question(('q', asked), held, None, 50, 100)
    # the graph is asked once, for the chosen chunks against every other chunk of the border
    assert asked_of_the_graph == [([held.chunk_ids[i] for i in chosen],
                                   [held.chunk_ids[i] for i in others])]
    # the chosen chunks first, then the more strongly tied, then the rest in the clouds' order
    want = chosen + [last, second_last] + [i for i in others if i not in (last, second_last)]
    assert seen['order'] == want
    assert out.meta['ranking']['ordered_chunk_ids'] == [held.chunk_ids[i] for i in want]
    story = out.meta['scope']['storyline']
    assert story['chosen_chunk_ids'] == [held.chunk_ids[i] for i in chosen]
    assert story['chunks_reached'] == 2 and story['time_near_up_to_seconds'] is None
    ranking = out.meta['ranking']
    delivered = want[:3]
    assert ranking['delivered_chosen'] == [i in chosen for i in delivered]
    strength = {last: 2 * len(chosen), second_last: 1}
    assert ranking['delivered_storyline_strength'] == [strength.get(i, 0) for i in delivered]
    assert ranking['delivered_storyline_ways']['entities'] == [len(chosen) if i == last else 0
                                                               for i in delivered]
