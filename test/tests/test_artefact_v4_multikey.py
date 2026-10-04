"""artefact_v4's multikey sort on toy arrays, the arm run on it with no model call, and the
stored round-1 files it reads (skipped where they are not on this machine).

No live graph, no model call, no question text, no gold.
"""
import inspect
import json

import numpy as np
import pytest

from harness.contract import BuildStats, ModelUsage
from arms import artefact_v4 as V
from artefact import query_content as Q
from artefact import v4_multikey as MK
from artefact import v4_rank as R4

# Graph tags ProductX (a product name), a, b, c; chunks c0..c4.
# Edges (P,c3) (a,c0) (a,c1) (b,c1) (c,c2): c3 carries only the product-name edge, c4 no edge.
TAGS = ('ProductX', 'a', 'b', 'c')
CHUNKS = ('c0', 'c1', 'c2', 'c3', 'c4')
EDGE_TAG = np.array([0, 1, 1, 2, 3])
EDGE_CHUNK = np.array([3, 0, 1, 1, 2])
TOPIC = np.array([.5, .4, .3, .2, .6])
ELIGIBLE = np.array([False, True, True, True])
DD = np.array([.1, .2, .3, .4, .5])
DQ = np.array([.5, .5, .5, .5, .5])
GAPS = (1., 1., 1., 1.)
# Facet values per edge in ADJUST_FACETS order (temporal, why, activity, concreteness).
# On the eligible edges temporal puts c0, c1, c2 within one gap of the column's best (4.0);
# why separates them c1 (3.0), c2 (2.0), c0 (1.0). The product-name edge carries 4.5 on
# temporal: were it an edge of the question, c2 (3.2) would drop a temporal level below c0.
SCORES = np.array([[4.5, 9., 9., 9.],
                   [3.9, 1., 0., 0.],
                   [4.0, 3., 0., 0.],
                   [0., 0., 0., 0.],
                   [3.2, 2., 0., 0.]])
TEMPORAL_THEN_WHY = (0., 1., .5, 0., 0.)


def layer(scores=SCORES, gaps=GAPS):
    return MK.build_layer(scores, gaps, {'column': 'test'}, {'value': 'test'})


def run(query_tags, scores=SCORES, topic=TOPIC, eligible=ELIGIBLE, dd=DD, dq=DQ,
        fit_step=V.COS_NOISE):
    return MK.multikey_order(CHUNKS, EDGE_TAG, EDGE_CHUNK, topic, layer(scores), eligible,
                             query_tags, dd, dq, fit_step=fit_step)


def names(order):
    return [CHUNKS[i] for i in order]


def decided(result, delivered):
    return V.multikey_meta(result, delivered)['adjacent_pairs_in_the_window_separated_by']


# --- the facet order -------------------------------------------------------------

def test_the_facet_order_follows_the_query_tags_own_values():
    # temporal .2, why .9, activity .5, concreteness .9: why and concreteness tie and keep the
    # listed order, then activity, then temporal
    assert MK.facet_order((0., .2, .9, .5, .9)) == (1, 3, 2, 0)
    assert MK.facet_order((0., 0., 0., 0., 0.)) == (0, 1, 2, 3)
    scores = SCORES.copy()
    scores[1, 0:2] = (4.0, 1.)      # (a,c0): temporal 4.0 level 0, why level 2
    scores[2, 0:2] = (2.5, 3.)      # (a,c1): temporal level 1, why level 0
    scores[4, 0:2] = (1.2, 2.)      # (c,c2): temporal level 2, why level 1
    fit = np.array([0., .8, .1, .8])
    temporal_first = run([(fit, (0., 1., 0., 0., 0.))], scores)
    why_first = run([(fit, (0., 0., 1., 0., 0.))], scores)
    assert names(temporal_first['order'])[:3] == ['c0', 'c1', 'c2']
    assert names(why_first['order'])[:3] == ['c1', 'c2', 'c0']
    assert temporal_first['facet_orders'] == [('temporal', 'why', 'activity', 'concreteness')]
    assert why_first['facet_orders'] == [('why', 'temporal', 'activity', 'concreteness')]


def test_topic_never_appears_in_the_facet_order():
    assert MK.facet_order((1., 0., 0., 0., 0.)) == (0, 1, 2, 3)
    assert MK.facet_order((1., .2, .4, .1, .3)) == (1, 3, 0, 2)
    fit = np.array([0., .8, .1, .8])
    high = run([(fit, (1., .2, .4, .1, .3))])
    low = run([(fit, (0., .2, .4, .1, .3))])
    assert high['order'] == low['order'] and high['keys'].tolist() == low['keys'].tolist()
    assert all('topic' not in order for order in high['facet_orders'])
    assert all(len(order) == 4 for order in high['facet_orders'])
    # the layer holds the four facets and nothing for topic
    assert layer().values.shape == (len(EDGE_TAG), len(R4.ADJUST_FACETS))
    with pytest.raises(ValueError):
        MK.build_layer(np.zeros((5, 5)), GAPS, {}, {})


# --- the keys --------------------------------------------------------------------

def test_two_edges_within_one_gap_on_facet_1_fall_through_to_facet_2():
    fit = np.array([.99, .8, .1, .8])          # the product-name tag fits best and is no edge
    result = run([(fit, TEMPORAL_THEN_WHY)])
    assert result['fit_best'] == pytest.approx(.8)
    assert result['facet_column_best']['temporal'] == 4.0
    # temporal 4.0, 3.9 and 3.2 share level 0: why decides c1 (3.0), c2 (2.0), c0 (1.0)
    assert [result['keys'][i][2] for i in (0, 1, 2)] == [0, 0, 0]
    assert names(result['order'])[:3] == ['c1', 'c2', 'c0']
    counts = decided(result, result['order'][:3])
    assert counts['facet2'] == 2 and sum(counts.values()) == 2
    # one step further down temporal, c2 falls below c0 on facet 1
    apart = SCORES.copy()
    apart[4, 0] = 2.9
    result = run([(fit, TEMPORAL_THEN_WHY)], apart)
    assert names(result['order'])[:3] == ['c1', 'c0', 'c2']
    counts = decided(result, result['order'][:3])
    assert counts['facet2'] == 1 and counts['facet1'] == 1


def test_the_facet_level_counts_whole_gaps_below_the_column_best():
    fit = np.array([0., .8, .1, .8])
    half = MK.multikey_order(CHUNKS, EDGE_TAG, EDGE_CHUNK, TOPIC, layer(SCORES, (.5, 1., 1., 1.)),
                             ELIGIBLE, [(fit, TEMPORAL_THEN_WHY)], DD, DQ, fit_step=V.COS_NOISE)
    # temporal at a gap of .5: 4.0 -> 0, 3.9 -> 0, 3.2 -> floor(.8 / .5) = 1
    assert [half['keys'][i][2] for i in (1, 0, 2)] == [0, 0, 1]
    assert names(half['order'])[:3] == ['c1', 'c0', 'c2']


def test_topic_then_description_then_question_then_id_decide_after_the_facets():
    fit = np.array([0., .8, .1, .8])
    flat = SCORES.copy()
    flat[1:, :] = 0.                            # every facet level ties
    topic = np.array([.5, .4, .4, .2, .4])      # c0, c1, c2 tie on topic
    dd = np.array([.3, .3, .5, .0, .0])         # c2 leads on the description
    dq = np.array([.1, .2, .2, .0, .0])         # c1 before c0 on the question
    result = run([(fit, TEMPORAL_THEN_WHY)], flat, topic, dd=dd, dq=dq)
    assert names(result['order'])[:3] == ['c2', 'c1', 'c0']
    counts = decided(result, result['order'][:3])
    assert counts['description'] == 1 and counts['question'] == 1
    same = run([(fit, TEMPORAL_THEN_WHY)], flat, topic, dd=np.zeros(5), dq=np.zeros(5))
    assert names(same['order'])[:3] == ['c0', 'c1', 'c2']
    assert decided(same, same['order'][:3])['id'] == 2
    topic = np.array([.5, .4, .41, .2, .39])    # now topic splits them: c1, c0, c2
    result = run([(fit, TEMPORAL_THEN_WHY)], flat, topic, dd=np.zeros(5), dq=np.zeros(5))
    assert names(result['order'])[:3] == ['c1', 'c0', 'c2']
    assert decided(result, result['order'][:3])['topic'] == 2


def test_the_fit_anchor_is_the_questions_one_best_and_the_width_is_the_knob():
    strong = (np.array([0., .8, .1, .1]), TEMPORAL_THEN_WHY)
    weak = (np.array([0., .1, .1, .5]), TEMPORAL_THEN_WHY)
    result = run([strong, weak])
    # the weak tag's best match (c, .5) sits floor(.3 / .002) levels below the question's .8
    assert result['fit_best'] == pytest.approx(.8)
    assert result['keys'][2][1] == int(np.floor((.8 - .5) / V.COS_NOISE))
    assert result['best_query_tag'][2] == 1
    close = np.array([0., .80, .1, .79])
    noise = run([(close, TEMPORAL_THEN_WHY)], fit_step=V.BANDS['noise'])
    paraphrase = run([(close, TEMPORAL_THEN_WHY)], fit_step=V.BANDS['paraphrase'])
    # .01 apart: apart under noise, one level under paraphrase, where why decides
    assert names(noise['order'])[:3] == ['c1', 'c0', 'c2']
    assert names(paraphrase['order'])[:3] == ['c1', 'c2', 'c0']
    with pytest.raises(ValueError):
        run([(close, TEMPORAL_THEN_WHY)], fit_step=0.)


# --- chunks and edges ------------------------------------------------------------

def test_no_chunk_is_cut():
    fit = np.array([.99, .8, .1, .8])
    result = run([(fit, TEMPORAL_THEN_WHY)])
    assert sorted(result['order']) == list(range(len(CHUNKS)))
    # c3 carries only the product-name edge and c4 no edge: both follow, by description level
    assert names(result['order'])[-2:] == ['c4', 'c3']
    assert result['reached'].tolist() == [True, True, True, False, False]
    assert result['keys'][3][:7].tolist() == [1, -1, -1, -1, -1, -1, -1]
    for eligible in (np.zeros(4, dtype=bool), ELIGIBLE):
        for query_tags in ([], [(fit, TEMPORAL_THEN_WHY)]):
            out = run(query_tags, eligible=eligible)
            assert sorted(out['order']) == list(range(len(CHUNKS)))
    nothing = run([], eligible=np.zeros(4, dtype=bool))
    assert names(nothing['order']) == ['c4', 'c3', 'c2', 'c1', 'c0']
    assert nothing['edges_sorted'] == 0 and nothing['fit_best'] is None


def test_a_chunk_takes_its_best_edges_position():
    fit = np.array([0., .5, .9, .7])
    result = run([(fit, TEMPORAL_THEN_WHY)])
    # c1 is reached through (a,c1) deep and through (b,c1) at the question's best fit: it
    # stands where (b,c1) stands, first
    assert names(result['order'])[:3] == ['c1', 'c2', 'c0']
    assert result['best_edge'][1] == 3 and result['keys'][1][1] == 0
    # the order is the per-chunk keys sorted: each chunk sits at its best edge's key
    keys = result['keys']
    assert result['order'] == np.lexsort(keys.T[::-1]).tolist()
    # more edges do not lift a chunk: a second query tag reaching c0 and c1 again, deeper,
    # moves nothing
    again = run([(fit, TEMPORAL_THEN_WHY), (np.array([0., .3, 0., 0.]), TEMPORAL_THEN_WHY)])
    assert again['order'] == result['order']
    assert again['keys'].tolist() == result['keys'].tolist()


def test_both_tag_lists_contribute_edges(monkeypatch):
    raw = {'description': 'Sought content',
           'tags': [{'t': 'described', 'facets': dict(zip(Q.FACETS, (0., 1., .5, 0., 0.)))}],
           'query_tags': [{'t': 'asked', 'facets': dict(zip(Q.FACETS, (0., 0., 1., 0., 0.)))}]}
    query = Q.parse('placeholder question', raw)
    fits = {'described': [0., .5, .1, .1], 'asked': [0., .1, .1, .9]}
    seen = arm(monkeypatch, query, fits)
    out = seen['out']
    interp = out.meta['interpreter']
    assert interp['description_side_tags'] == 1 and interp['question_side_tags_read'] == 1
    assert interp['query_tags'] == 2
    assert out.meta['diagnostics']['edges_sorted'] == 2 * int(ELIGIBLE[EDGE_TAG].sum())
    # c2 is reached through c, and c fits the question-side tag best of all
    ranking = out.meta['ranking']
    assert ranking['delivered_chunk_ids'][0] == 'c2'
    assert ranking['delivered_query_tags'][0] == 1 and ranking['delivered_graph_tags'][0] == 'c'
    assert [row['side'] for row in ranking['query_facet_orders']] == ['description', 'question']
    assert ranking['query_facet_orders'][1]['order'] == ['why', 'temporal', 'activity',
                                                         'concreteness']


# --- the structure keys ----------------------------------------------------------

def test_the_structure_keys_never_cut():
    fit = np.array([.99, .8, .1, .8])
    plain = run([(fit, TEMPORAL_THEN_WHY)])
    for place in MK.STRUCT_PLACES:
        for landed in ((1, 0, 1, 0, 1), (0, 0, 0, 0, 0), (1, 1, 1, 1, 1)):
            out = run_struct([(fit, TEMPORAL_THEN_WHY)], landed, struct_at=place)
            assert sorted(out['order']) == sorted(plain['order']) == list(range(len(CHUNKS)))
            assert out['reached'].tolist() == plain['reached'].tolist()
            assert out['best_edge'].tolist() == plain['best_edge'].tolist()


def test_no_landing_leaves_the_landed_key_inert():
    fit = np.array([.99, .8, .1, .8])
    for place in MK.STRUCT_PLACES:
        zeros = run_struct([(fit, TEMPORAL_THEN_WHY)], (0,) * 5, struct_at=place)
        ones = run_struct([(fit, TEMPORAL_THEN_WHY)], (1,) * 5, struct_at=place)
        assert zeros['order'] == ones['order']
        assert decided(zeros, zeros['order'])['landed'] == 0
        assert zeros['landed_chunks'] == 5 and ones['landed_chunks'] == 0
    # with the seed distance constant as well, the order is the plain sort's
    flat = toy_structure(channels=(), product=(0, 0, 0, 0, 0))
    unreached_first = np.array([.1, .2, .3, .5, .4])       # c3 before c4 either way
    plain = run([(fit, TEMPORAL_THEN_WHY)], dd=unreached_first)
    inert = run_struct([(fit, TEMPORAL_THEN_WHY)], (0,) * 5, structure=flat, dd=unreached_first)
    assert inert['order'] == plain['order']


def test_seed_distance_on_a_toy_graph():
    # chunks 0 and 7 are seeds. 1 shares channel 10 with seed 0; 2 is file-adjacent to seed 0
    # (another product); 3 shares seed 0's product A; 8 shares seed 7's product D; 4 sits in
    # product C, 5 in none, 6 on channel 11 in product B: none of them near a seed.
    A, B, C, D = 0, 1, 2, 3
    structure = toy_structure(adjacent=[(0, 2), (4, 5)],
                              channels=[(0, 10), (1, 10), (6, 11), (4, 11)],
                              product=(A, A, B, A, C, -1, B, D, D))
    seed = np.zeros(9, dtype=bool)
    seed[[0, 7]] = True
    assert MK.seed_distance(seed, structure).tolist() == [0, 1, 1, 2, 3, 3, 3, 0, 2]
    assert MK.seed_distance(np.zeros(9, dtype=bool), structure).tolist() == [3] * 9


def test_the_seeds_are_the_chunks_at_fit_level_zero():
    # a and c at the question's best fit reach c0, c1 and c2; b sits deep. With c3 sharing
    # c1's channel and c4 in product 1 alone, c3 is at 1 and c4 at 3.
    structure = toy_structure(channels=((1, 0), (3, 0)), product=(0, 0, 0, 1, 1))
    out = run_struct([(np.array([0., .8, .1, .8]), TEMPORAL_THEN_WHY)], (0,) * 5, structure)
    assert out['seeds'] == 3
    assert out['keys'][:, list(out['key_names']).index('seed')].tolist() == [0, 0, 0, 1, 3]
    assert out['seed_distance_histogram'] == {'0': 3, '1': 1, '2': 0, '3': 1}
    # under paraphrase b's .1 is still far below .8: the seeds stay three
    wide = run_struct([(np.array([0., .8, .1, .8]), TEMPORAL_THEN_WHY)], (0,) * 5, structure,
                      fit_step=V.BANDS['paraphrase'])
    assert wide['seeds'] == 3


def test_the_structure_reuses_artefact_v3s_file_adjacency():
    from arms.artefact_v3 import file_adjacency
    rows = [{'relpath': 'p.json', 'locator': json.dumps(loc)} for loc in (
        {'section': 'documents', 'parent_ref': 'd', 'id': 'r1', 'char_range': [0, 99]},
        {'section': 'documents', 'parent_ref': 'd', 'id': 'r1', 'char_range': [100, 199]},
        {'section': 'documents', 'parent_ref': 'd', 'id': 'r2', 'char_range': [200, 299]},
        {'section': 'prs', 'parent_ref': 'p', 'index': 4},
        {'section': 'prs', 'parent_ref': 'p', 'index': 5})]
    adjacency = file_adjacency(rows)
    structure = MK.build_structure(adjacency, {'chunk_group_ptr': np.zeros(6, dtype=np.int64),
                                               'chunk_groups': np.zeros(0),
                                               'product': np.zeros(5)})
    seed = np.array([True, False, False, True, False])
    # two parts of one document record touch; another record and the next PR do not
    assert MK.seed_distance(seed, structure).tolist() == [0, 1, 2, 0, 2]


def test_the_placement_knob_orders_the_keys():
    assert MK.key_names('after_facets') == (
        'reached', 'fit', 'facet1', 'facet2', 'facet3', 'facet4', 'landed', 'seed', 'topic',
        'description', 'question', 'id')
    assert MK.key_names('after_fit') == (
        'reached', 'fit', 'landed', 'seed', 'facet1', 'facet2', 'facet3', 'facet4', 'topic',
        'description', 'question', 'id')
    with pytest.raises(ValueError):
        MK.key_names('first')
    fit = np.array([.99, .8, .1, .8])
    landed = (0, 1, 1, 1, 1)                                  # c0 in the landed area
    after_facets = run_struct([(fit, TEMPORAL_THEN_WHY)], landed, struct_at='after_facets')
    after_fit = run_struct([(fit, TEMPORAL_THEN_WHY)], landed, struct_at='after_fit')
    # why separates c1, c2, c0 before landed is read; after fit, landed lifts c0 first
    assert names(after_facets['order'])[:3] == ['c1', 'c2', 'c0']
    assert names(after_fit['order'])[:3] == ['c0', 'c1', 'c2']
    assert decided(after_fit, after_fit['order'][:3]) == {**dict.fromkeys(
        MK.key_names('after_fit'), 0), 'landed': 1, 'facet2': 1}
    # the seed key: b alone sits at fit level 0, so c1 is the one seed; a and c share a deeper
    # fit level. c2 shares c1's channel (seed distance 1), c0 is in another product (3); why
    # puts c0 before c2.
    structure = toy_structure(channels=((1, 0), (2, 0)), product=(0, 1, 1, 1, 1))
    scores = SCORES.copy()
    scores[1, 1], scores[4, 1] = 3., 1.                       # why: c0 level 0, c2 level 2
    fit = np.array([0., .79, .8, .79])
    for place, expected, second in (('after_facets', ['c1', 'c0', 'c2'], 'facet2'),
                                    ('after_fit', ['c1', 'c2', 'c0'], 'seed')):
        out = run_struct([(fit, TEMPORAL_THEN_WHY)], (0,) * 5, structure, struct_at=place,
                         scores=scores)
        assert out['seeds'] == 1
        assert out['keys'][:3, list(out['key_names']).index('seed')].tolist() == [3, 0, 1]
        assert names(out['order'])[:3] == expected
        assert decided(out, out['order'][:3]) == {**dict.fromkeys(out['key_names'], 0),
                                                  'fit': 1, second: 1}


def test_struct_at_off_is_the_plain_sort_and_reads_no_landing(monkeypatch):
    raw = {'description': 'Sought content',
           'tags': [{'t': 'described', 'facets': dict(zip(Q.FACETS, TEMPORAL_THEN_WHY))}]}
    query = Q.parse('placeholder question', raw)
    fits = {'described': [.99, .8, .1, .8]}
    seen = arm(monkeypatch, query, fits, {'HERB_V4_STRUCT_AT': 'off'}, landed=(0, 1, 1, 1, 1))
    out = seen['out']
    assert 'area_mode' not in seen
    assert out.meta['area'] == {'mode': 'not read (HERB_V4_STRUCT_AT=off)'}
    assert out.meta['policy']['struct_at'] == 'off'
    assert out.meta['ranking']['key_names'] == list(MK.key_names(None))
    plain = run([(np.array(fits['described']), TEMPORAL_THEN_WHY)])
    assert seen['rows'] == [CHUNKS[i] for i in plain['order']]
    d = out.meta['diagnostics']
    assert d['seeds'] == 3 and 'landed_chunks' not in d and 'seed_distance_histogram' not in d


def _landing_prepared(monkeypatch):
    from contextlib import contextmanager

    class Driver:
        @contextmanager
        def session(self, **kwargs):
            yield None

    names = (V.LAND.Landing('Product', 'EdgeForce', 'EdgeForce', V.LAND.PRODUCT),
             V.LAND.Landing('Employee', 'eid_9', 'Jack', V.LAND.FIRST),
             V.LAND.Landing('Customer', 'cu-1', 'Acme', V.LAND.COMPANY))
    table = {('Product', 'EdgeForce'): {'c0', 'c1'}, ('Employee', 'eid_9'): {'c2'}}

    def fake_areas(session, hits):
        by_node = {(h.label, h.node_id): set(table[(h.label, h.node_id)]) for h in hits
                   if (h.label, h.node_id) in table}
        by_chunk = {}
        for node, chunks in by_node.items():
            for chunk in chunks:
                by_chunk.setdefault(chunk, set()).add(node)
        return V.LAND.Areas(by_node=by_node, by_chunk=by_chunk, by_route={})

    monkeypatch.setattr(V.LAND, 'areas', fake_areas)
    return V.Prepared(**{**prepared().__dict__, 'landings': names, 'driver': Driver(),
                         'corpus_words': frozenset({'slack', 'team', 'said', 'about', 'for'})})


def test_the_landed_area_skips_corpus_words_and_drops_empty_landings(monkeypatch):
    p = _landing_prepared(monkeypatch)
    question = 'what the Slack team said about EdgeForce for Acme'
    rank, meta = V._area_rank(p, question, 'landed')
    # "Slack" is a corpus word and lands nothing; Acme reaches no chunk and is dropped
    assert rank.tolist() == [0, 0, 1, 1, 1]
    assert meta['area'] == 2 and meta['dropped'] == ['company:Acme']
    assert meta['landings'] == {'product:EdgeForce': 2}
    # the old reading: Slack lands the nearest name and Acme empties the meet
    rank, meta = V._area_rank(p, question, 'first')
    assert rank.tolist() == [1, 1, 1, 1, 1] and meta['area'] == 0
    assert sorted(meta['landings']) == ['company:Acme', 'first:Jack', 'product:EdgeForce']
    # every landing dropped: no area, the key inert
    rank, meta = V._area_rank(p, 'what about Acme', 'landed')
    assert rank.tolist() == [0, 0, 0, 0, 0] and meta['area'] is None
    assert meta['dropped'] == ['company:Acme']
    with pytest.raises(ValueError):
        V._area_rank(V.Prepared(**{**p.__dict__, 'corpus_words': None}), question, 'landed')


def test_the_arm_reads_the_landing_and_the_placement(monkeypatch):
    raw = {'description': 'Sought content',
           'tags': [{'t': 'described', 'facets': dict(zip(Q.FACETS, TEMPORAL_THEN_WHY))}]}
    query = Q.parse('placeholder question', raw)
    fits = {'described': [.99, .8, .1, .8]}
    facets_first = arm(monkeypatch, query, fits, landed=(0, 1, 1, 1, 1))['out']
    fit_first = arm(monkeypatch, query, fits, {'HERB_V4_STRUCT_AT': 'after_fit'},
                    landed=(0, 1, 1, 1, 1))['out']
    assert facets_first.meta['ranking']['delivered_chunk_ids'] == ['c1', 'c2', 'c0']
    assert fit_first.meta['ranking']['delivered_chunk_ids'] == ['c0', 'c1', 'c2']
    assert fit_first.meta['policy']['struct_at'] == 'after_fit'
    assert fit_first.meta['ranking']['key_names'] == list(MK.key_names('after_fit'))
    d = fit_first.meta['diagnostics']
    assert d['landed_chunks'] == 1 and d['landing_inert'] is False and d['seeds'] == 3
    assert d['seed_distance_histogram'] == {'0': 3, '1': 0, '2': 0, '3': 2}
    assert d['adjacent_pairs_in_the_window_separated_by']['landed'] == 1


# --- the arm ---------------------------------------------------------------------

def prepared():
    return V.Prepared(
        chunk_rows=tuple({'chunkId': c} for c in CHUNKS), chunk_ids=CHUNKS,
        chunk_kinds=('pr',) * 5, graph_tags=TAGS, product_tags=('ProductX',),
        nonscope_eligible=ELIGIBLE, tag_vectors=np.eye(4), chunk_vectors=np.eye(5),
        edge_tag=EDGE_TAG, edge_chunk=EDGE_CHUNK, edge_topic=TOPIC, edge_pos=np.zeros((5, 5)),
        landings=(), driver=None, cache_dir=None, provenance={},
        build_stats=BuildStats(0., ModelUsage(), []), casefold_eligible=ELIGIBLE,
        multikey_layer=layer(), structure=toy_structure())


def _csr(pairs, rows):
    ptr, members = np.zeros(rows + 1, dtype=np.int64), []
    for i in range(rows):
        mine = sorted(v for k, v in pairs if k == i)
        members += mine
        ptr[i + 1] = ptr[i] + len(mine)
    return ptr, np.array(members, dtype=np.int64)


def toy_structure(adjacent=(), channels=((1, 0), (2, 0)), product=(0, 0, 0, 1, 1)):
    """adjacent: (chunk, chunk) pairs; channels: (chunk, channel) pairs; product per chunk."""
    both = list(adjacent) + [(b, a) for a, b in adjacent]
    a_ptr, a_members = _csr(both, len(product))
    c_ptr, c_members = _csr(list(channels), len(product))
    return MK.build_structure({'ptr': a_ptr, 'members': a_members},
                              {'chunk_group_ptr': c_ptr, 'chunk_groups': c_members,
                               'product': np.array(product)}, {'toy': True})


def run_struct(query_tags, landed, structure=None, struct_at='after_facets', scores=SCORES,
               fit_step=V.COS_NOISE, dd=DD):
    return MK.multikey_order(CHUNKS, EDGE_TAG, EDGE_CHUNK, TOPIC, layer(scores), ELIGIBLE,
                             query_tags, dd, DQ, fit_step=fit_step,
                             landed=np.asarray(landed), structure=structure or toy_structure(),
                             struct_at=struct_at)


def arm(monkeypatch, query, fits, env=None, kept=3, landed=(0, 0, 0, 0, 0)):
    def fake_cosines(text, tags, prep):
        return ({'query_tag_cosines': np.array([fits[t] for t in tags]).reshape(len(tags), 4),
                 'query_description_cosines': DD if text == query.description else DQ},
                ModelUsage(), {'vector_sha256': 'x'})

    seen = {}

    def fake_budget(rows, budget, doc_cache):
        seen['rows'] = [r['chunkId'] for r in rows]
        return (['x'] * kept, [[]] * kept, [], {'budget': budget, 'chars': budget, 'kept': kept,
                                                'boundary': None, 'exhausted': False})

    def fake_area(prep, text, mode):
        seen['area_mode'] = mode
        rank = np.asarray(landed, dtype=np.int64)
        return rank, {'mode': mode, 'area': (int((rank == 0).sum()) if rank.any() else None)}

    monkeypatch.setattr(V, '_interpret', lambda t, prep: (query, ModelUsage(), []))
    monkeypatch.setattr(V, '_query_cosines', fake_cosines)
    monkeypatch.setattr(V, '_budget_contexts', fake_budget)
    monkeypatch.setattr(V, '_area_rank', fake_area)
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    for name, value in {'HERB_V4_SORT': 'multikey', **(env or {})}.items():
        monkeypatch.setenv(name, value)
    seen['out'] = V.answer_one_question(('q', 'placeholder question'), prepared(), None, 50, 100)
    return seen


def test_multikey_is_chosen_by_its_knob_and_reads_its_own_knobs(monkeypatch):
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HERB_V4_SORT', 'multikey')
    assert V.knobs()['sort'] == 'multikey' and V.knobs()['fiteq'] == 'noise'
    assert V.RETRIEVAL_FLAGS['defaults']['HERB_V4_FITEQ'] == 'noise'
    assert V.RETRIEVAL_FLAGS['defaults']['HERB_V4_STRUCT_AT'] == 'after_facets'
    record = V.knob_record(V.knobs())
    assert record['read_by_active_sort'] == ['HERB_V4_SORT', 'HERB_V4_FITEQ', 'HERB_V4_STRUCT_AT',
                                             'HERB_V4_OFFLINE']
    assert record['product_name_tags_excluded_by_the_sort'] is True
    raw = {'description': 'Sought content',
           'tags': [{'t': 'described', 'facets': dict(zip(Q.FACETS, TEMPORAL_THEN_WHY))}]}
    seen = arm(monkeypatch, Q.parse('placeholder question', raw),
               {'described': [.99, .8, .1, .8]})
    out = seen['out']
    assert out.meta['policy']['knobs_recorded']['active']['HERB_V4_SORT'] == 'multikey'
    assert seen['rows'] == ['c1', 'c2', 'c0', 'c4', 'c3']    # the whole order reaches the cut
    assert out.meta['ranking']['delivered_chunk_ids'] == ['c1', 'c2', 'c0']
    assert seen['area_mode'] == 'landed'
    assert out.meta['area'] == {'mode': 'landed', 'area': None}
    assert out.meta['ranking']['key_names'] == list(MK.key_names('after_facets'))
    assert out.meta['diagnostics']['landing_inert'] is True


def test_the_arm_records_the_width_the_gaps_and_the_facet_orders(monkeypatch):
    raw = {'description': 'Sought content',
           'tags': [{'t': 'described', 'facets': dict(zip(Q.FACETS, (.9, .1, .2, .3, .4)))}],
           'query_tags': [{'t': 'asked', 'facets': dict(zip(Q.FACETS, TEMPORAL_THEN_WHY))}]}
    query = Q.parse('placeholder question', raw)
    fits = {'described': [0., .80, .1, .1], 'asked': [0., .1, .1, .79]}
    for width in ('noise', 'paraphrase'):
        out = arm(monkeypatch, query, fits, {'HERB_V4_FITEQ': width})['out']
        policy = out.meta['policy']
        assert policy['knobs_recorded']['active']['HERB_V4_FITEQ'] == width
        assert policy['fit_equal_width'] == V.BANDS[width]
        assert policy['facet_gaps'] == dict(zip(R4.ADJUST_FACETS, GAPS))
        assert policy['facet_value_source'] == {'value': 'test'}
        assert policy['flip_gap'] is None                   # the pooled gap multikey never reads
        assert policy['product_named_tags_excluded'] == 1  # the casefold mask the sort used
        orders = out.meta['ranking']['query_facet_orders']
        assert orders[0]['order'] == ['concreteness', 'activity', 'why', 'temporal']
        assert orders[0]['readings'] == {'temporal': .1, 'why': .2, 'activity': .3,
                                         'concreteness': .4}
        assert orders[1]['order'] == ['temporal', 'why', 'activity', 'concreteness']
        d = out.meta['diagnostics']
        assert d['adjacent_pairs_in_the_window'] == 2
        assert sum(d['adjacent_pairs_in_the_window_separated_by'].values()) == 2
        assert len(out.meta['ranking']['delivered_keys']) == 3
        assert out.meta['ranking']['key_names'] == list(MK.key_names('after_facets'))
        assert policy['struct_at'] == 'after_facets'


def test_the_key_decider_counts_sum_to_the_pairs():
    rng = np.random.default_rng(0)
    n_chunks, n_tags = 80, 30
    chunk_ids = tuple(f'k{i:03d}' for i in range(n_chunks))
    edge_chunk = np.concatenate([np.arange(n_chunks), rng.integers(0, n_chunks, 60)])
    edge_tag = rng.integers(0, n_tags, edge_chunk.size)
    scores = rng.normal(0., 2., (edge_chunk.size, 4))
    topic = rng.uniform(-.1, .6, edge_chunk.size)
    query_tags = [(rng.uniform(-.2, .9, n_tags), tuple(rng.uniform(0., 1., 5))) for _ in range(3)]
    structure = toy_structure(
        adjacent=[(i, i + 1) for i in range(0, n_chunks - 1, 3)],
        channels=[(i, i % 7) for i in range(0, n_chunks, 2)],
        product=tuple(rng.integers(0, 4, n_chunks)))
    landed = rng.integers(0, 2, n_chunks)
    runs = [dict()] + [dict(landed=landed, structure=structure, struct_at=place)
                       for place in MK.STRUCT_PLACES]
    for extra in runs:
        result = MK.multikey_order(chunk_ids, edge_tag, edge_chunk, topic,
                                   MK.build_layer(scores, (1.01, 1.38, 1.06, 1.30), {}, {}),
                                   np.ones(n_tags, dtype=bool), query_tags,
                                   rng.uniform(0., .6, n_chunks), rng.uniform(0., .6, n_chunks),
                                   fit_step=V.BANDS['paraphrase'], **extra)
        assert sorted(result['order']) == list(range(n_chunks))
        for delivered in (result['order'], result['order'][:7], result['order'][:1], []):
            meta = V.multikey_meta(result, delivered)
            window = min(len(delivered), V.DECIDER_WINDOW)
            assert meta['decider_window_rows'] == window
            assert meta['adjacent_pairs_in_the_window'] == max(window - 1, 0)
            counts = meta['adjacent_pairs_in_the_window_separated_by']
            assert set(counts) == set(result['key_names'])
            assert ({'landed', 'seed'} <= set(counts)) == ('structure' in extra)
            assert sum(counts.values()) == meta['adjacent_pairs_in_the_window']
    assert V.DECIDER_WINDOW == 50


def test_the_run_knobs_go_into_the_retrieval_flags_the_manifest_carries(monkeypatch):
    monkeypatch.setattr(V, 'RETRIEVAL_FLAGS', dict(V.RETRIEVAL_FLAGS))
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HERB_V4_FITEQ', 'paraphrase')
    V.record_run_knobs()
    recorded = V.RETRIEVAL_FLAGS['knobs_at_prepare']
    assert recorded['active']['HERB_V4_FITEQ'] == 'paraphrase'
    assert recorded['active']['HERB_V4_SORT'] == 'strength'
    assert 'record_run_knobs()' in inspect.getsource(V.prepare_over_corpus)


# --- the stored files ------------------------------------------------------------

def test_read_facet_gaps_reads_each_facet_by_column_name(tmp_path):
    table = ['# bands', '', '## per column', '',
             '| column | gap (any) | gap (same chunk) |', '|---|---|---|',
             '| why | 2.0 | 1.5 |', '| temporal | 1.0 | 0.5 |', '| activity | 3.0 | 2.5 |',
             '| concreteness | 4.0 | 3.5 |', '| **pooled** | 9.0 | 9.5 |', '', '## next',
             '| temporal | 7.0 | 7.5 |']
    path = tmp_path / 'BANDS.md'
    path.write_text('\n'.join(table) + '\n', encoding='utf-8')
    gaps, source = MK.read_facet_gaps(path)
    assert gaps == (1., 2., 3., 4.) and source['column'] == 'gap (any)'
    assert source['lines'] == {'temporal': 8, 'why': 7, 'activity': 9, 'concreteness': 10}
    assert MK.read_facet_gaps(path, 'gap (same chunk)')[0] == (.5, 1.5, 2.5, 3.5)
    with pytest.raises(ValueError):
        MK.read_facet_gaps(path, 'gap (none)')
    path.write_text('\n'.join(table[:8]) + '\n', encoding='utf-8')
    with pytest.raises(ValueError):
        MK.read_facet_gaps(path)


def test_read_refit_means_matches_edges_by_id_and_takes_the_mean_over_the_draws(tmp_path):
    scores = np.arange(3 * 4 * 2, dtype=np.float32).reshape(3, 4, 2)
    path = tmp_path / 'refits.npz'
    np.savez(path, edge_ids=np.array(['c1::a', 'c0::a', 'c1::b']),
             facets=np.array(['why', 'temporal', 'activity', 'concreteness']), scores=scores,
             seeds=np.array([7, 8]))
    values, source = MK.read_refit_means(path, [('b', 'c1'), ('a', 'c0')])
    # (b, c1) is row 2, (a, c0) row 1; columns read by name into temporal, why, activity, concreteness
    for out, row in ((0, 2), (1, 1)):
        means = scores[row].astype(np.float64).mean(axis=1)
        assert values[out].tolist() == [means[1], means[0], means[2], means[3]]
    assert source['draws'] == 2 and source['seeds'] == [7, 8] and len(source['sha256']) == 64
    with pytest.raises(ValueError):
        MK.read_refit_means(path, [('z', 'c9')])


def test_the_stored_layer_the_gaps_and_the_direction_of_the_values():
    scores_path = V.LEARNED_DIR / 'scores.jsonl'
    eval_path = V.LEARNED_DIR / 'eval.json'
    if not all(p.exists() for p in (scores_path, eval_path, V.BANDS_FILE, V.REFITS_FILE)):
        pytest.skip('round1 layer not on this machine')
    from scipy.stats import spearmanr
    gaps, source = MK.read_facet_gaps(V.BANDS_FILE)
    assert gaps == (1.01, 1.38, 1.06, 1.30)
    assert source['column'] == 'gap (any)'
    assert [source['lines'][f] for f in R4.ADJUST_FACETS] == [11, 12, 13, 14]
    # a higher base score is the edge the judge called stronger: the head's held-out agreement,
    # counted as score(first) > score(second) when the first was chosen, is above a coin
    agreement = json.loads(eval_path.read_text(encoding='utf-8'))['probe']['A']['per_facet']
    for facet in R4.ADJUST_FACETS:
        assert agreement[facet]['agreement'] > .5
    endpoints, base = [], []
    with scores_path.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            endpoints.append((row['tag'], row['chunk_id']))
            base.append([row[f] for f in R4.ADJUST_FACETS])
    base = np.asarray(base)
    means, refits = MK.read_refit_means(V.REFITS_FILE, endpoints)
    assert refits['draws'] == 24
    stored = MK.build_layer(means, gaps, source, refits)
    level = np.floor((stored.values.max(axis=0) - stored.values) / stored.gaps)
    sample = np.arange(0, len(base), 97)
    for j in range(len(R4.ADJUST_FACETS)):
        # the refit means keep the base head's direction
        assert spearmanr(base[:, j], stored.values[:, j]).statistic > .9
        assert level[int(np.argmax(stored.values[:, j])), j] == 0
        down = sample[np.argsort(-stored.values[sample, j], kind='stable')]
        assert (np.diff(level[down, j]) >= 0).all()      # a lower value, never a higher level


# --- the offline guard -----------------------------------------------------------

def _signature(text):
    system, user = Q.request(text)
    return {'cache_version': 1, 'stage': 'querytag', 'model': V.INTERPRET_MODEL,
            'system': system, 'user': user, 'max_tries': 1}


def _cache_file(tmp_path, text, saved):
    signature = _signature(text)
    key = V._sha(json.dumps(signature, sort_keys=True, ensure_ascii=False))
    path = tmp_path / 'querytag' / (key + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'signature': signature, **saved}), encoding='utf-8')
    return key, path


def _no_model(monkeypatch):
    from harness import chat

    def refuse(*args, **kwargs):
        raise AssertionError('a model call under HERB_V4_OFFLINE=on')

    monkeypatch.setattr(chat, 'post', refuse)
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)


def test_offline_raises_before_any_model_call_when_the_answer_is_not_cached(monkeypatch,
                                                                             tmp_path):
    _no_model(monkeypatch)
    monkeypatch.setattr(V, '_cached_stage', lambda *a, **k: (_ for _ in ()).throw(
        AssertionError('the cached stage is not reached on a miss')))
    monkeypatch.setenv('HERB_V4_OFFLINE', 'on')
    p = V.Prepared(**{**prepared().__dict__, 'cache_dir': tmp_path})
    with pytest.raises(RuntimeError, match='no model call made'):
        V._interpret('placeholder question', p)
    # a cached failure is not asked again: it raises and the file stays
    _, path = _cache_file(tmp_path, 'placeholder question', {'ok': False})
    with pytest.raises(RuntimeError, match='no model call made'):
        V._interpret('placeholder question', p)
    assert path.exists()


def test_offline_reads_a_good_cached_answer_and_calls_no_model(monkeypatch, tmp_path):
    _no_model(monkeypatch)
    raw = {'description': 'Sought content',
           'tags': [{'t': 'described', 'facets': dict(zip(Q.FACETS, TEMPORAL_THEN_WHY))}]}
    key, _ = _cache_file(tmp_path, 'placeholder question',
                         {'ok': True, 'raw': raw, 'usage': {}})
    monkeypatch.setenv('HERB_V4_OFFLINE', 'on')
    p = V.Prepared(**{**prepared().__dict__, 'cache_dir': tmp_path})
    query, usage, stages = V._interpret('placeholder question', p)
    assert [t.text for t in query.tags] == ['described']
    assert stages[0]['cache_hit'] is True and stages[0]['key'] == key
    assert stages[0]['offline'] is True and usage.calls == 0
