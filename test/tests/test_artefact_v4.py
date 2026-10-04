"""artefact_v4's score, pick, order, knobs and diagnostics on tiny synthetic arrays.

No live graph, no model call, no corpus read.
"""
from contextlib import contextmanager
import inspect
import json

import numpy as np
import pytest

from harness.contract import BuildStats, ModelUsage
from arms import artefact_v4 as V
from artefact import query_content as Q


CHUNK_IDS = ('c0', 'c1', 'c2')
GRAPH_TAGS = ('ActionGenie', 't1', 't2', 't3')   # the first name is also a Product name
# Edges: (tag, chunk) = (t0,c0), (t1,c0), (t1,c1), (t2,c2), (t3,c2)
EDGE_TAG = np.array([0, 1, 1, 2, 3])
EDGE_CHUNK = np.array([0, 0, 1, 2, 2])
EDGE_TOPIC = np.array([.5, .25, 1., -.5, .75])
EDGE_POS = np.array([
    [.1, .2, .3, .4, .5],
    [1., 0., 0., 0., 0.],
    [0., 0., 0., 0., 1.],
    [.5, .5, .5, .5, .5],
    [.2, .2, .2, .2, .2],
])


def prepared(chunk_kinds=('slack', 'pr', 'pr'), products=('ActionGenie',)):
    rows = tuple({'chunkId': cid} for cid in CHUNK_IDS)
    product_tags = tuple(t for t in GRAPH_TAGS if t in set(products))
    return V.Prepared(
        chunk_rows=rows, chunk_ids=CHUNK_IDS, chunk_kinds=chunk_kinds, graph_tags=GRAPH_TAGS,
        product_tags=product_tags,
        nonscope_eligible=np.array([t not in set(products) for t in GRAPH_TAGS], dtype=bool),
        tag_vectors=np.eye(4), chunk_vectors=np.eye(3), edge_tag=EDGE_TAG, edge_chunk=EDGE_CHUNK,
        edge_topic=EDGE_TOPIC, edge_pos=EDGE_POS, landings=(), driver=None,
        cache_dir=None, provenance={}, build_stats=BuildStats(0., ModelUsage(), []))


# --- the stored facet layer -------------------------------------------------

def test_read_positions_maps_the_five_columns_by_name_in_facets_order(tmp_path):
    values = {'topic_pos': .11, 'temporal_pos': .22, 'why_pos': .33,
              'activity_pos': .44, 'concreteness_pos': .55}
    straight = {'tag': 'a', 'chunk_id': 'x', 'kind': 'pr', **values}
    # The same row with its columns written in a different order.
    permuted = {'tag': 'b', 'chunk_id': 'y', 'kind': 'slack',
                **{k: values[k] for k in reversed(list(values))}}
    path = tmp_path / 'scores.jsonl'
    path.write_text(json.dumps(straight) + '\n' + json.dumps(permuted) + '\n', encoding='utf-8')
    pos, kind = V._read_positions(path)
    assert V.POS_COLUMNS == ('topic_pos', 'temporal_pos', 'why_pos',
                             'activity_pos', 'concreteness_pos')
    assert pos[('a', 'x')] == (.11, .22, .33, .44, .55)
    assert pos[('b', 'y')] == (.11, .22, .33, .44, .55)
    assert kind == {'x': 'pr', 'y': 'slack'}


def test_read_positions_refuses_a_value_outside_the_unit_interval(tmp_path):
    row = {'tag': 'a', 'chunk_id': 'x', 'kind': 'pr', 'topic_pos': 1.5, 'temporal_pos': 0.,
           'why_pos': 0., 'activity_pos': 0., 'concreteness_pos': 0.}
    path = tmp_path / 'scores.jsonl'
    path.write_text(json.dumps(row) + '\n', encoding='utf-8')
    with pytest.raises(ValueError):
        V._read_positions(path)


def test_topic_takes_the_tag_vector_of_the_edge_and_the_chunk_vector_of_the_edge():
    tags = np.array([[1., 0.], [0., 1.], [.6, .8]])
    chunks = np.array([[.28, .96], [.96, .28], [.5, .866]])
    edge_tag = np.array([0, 2])
    edge_chunk = np.array([2, 1])
    right = np.einsum('ij,ij->i', tags[edge_tag], chunks[edge_chunk])
    swapped = np.einsum('ij,ij->i', tags[edge_chunk], chunks[edge_tag])
    assert right.tolist() == pytest.approx([.5, .8])
    assert swapped.tolist() == pytest.approx([.936, .866])
    assert right.tolist() != pytest.approx(swapped.tolist())
    # The arm computes exactly the first of those two.
    source = inspect.getsource(V.prepare_over_corpus)
    assert "np.einsum('ij,ij->i', tag_vectors[edge_tag], chunk_vectors[edge_chunk])" in source


# --- the pick ---------------------------------------------------------------

def test_pick_band_takes_every_tag_within_the_band_of_the_best_fit():
    fit = np.array([.40, .39, .30, -.10])
    assert V.pick(fit, .002).tolist() == [0]
    assert V.pick(fit, .01).tolist() == [0, 1]
    assert V.pick(fit, .11).tolist() == [0, 1, 2]
    with pytest.raises(ValueError):
        V.pick(np.array([np.nan, .1]), .01)


def test_each_probe_picks_against_its_own_best_fit():
    p = prepared()
    a = np.array([.90, .89, .10, .10])
    b = np.array([.20, .10, .199, .10])
    parts = V.score(p, [(a, (1., 0., 0., 0., 0.)), (b, (1., 0., 0., 0., 0.))],
                    [], band=.02, facets_on=True)
    assert parts['picked_counts'] == [2, 2]
    assert V.pick(a, .02).tolist() == [0, 1]
    assert V.pick(b, .02).tolist() == [0, 2]


def test_tagside_nonscope_drops_the_product_named_tag_before_the_best_fit_is_taken():
    p = prepared()
    fit = np.array([.90, .50, .10, .10])
    assert V.pick(fit, .002, p.nonscope_eligible).tolist() == [1]
    assert V.pick(fit, .002).tolist() == [0]
    allmode = V.score(p, [(fit, (1., 0., 0., 0., 0.))], [], band=.002, facets_on=True,
                      tagside='all')
    nonscope = V.score(p, [(fit, (1., 0., 0., 0., 0.))], [], band=.002, facets_on=True,
                       tagside='nonscope')
    # 'all' reaches c0 through the product tag only; 'nonscope' reaches c0 and c1 through t1.
    assert allmode['tag_part'][1] == 0. and nonscope['tag_part'][1] != 0.
    assert nonscope['picked_counts'] == [1]
    with pytest.raises(ValueError):
        V.score(p, [], [], band=.002, facets_on=True, tagside='sometimes')


# --- the score --------------------------------------------------------------

def test_score_formula_on_the_toy_graph():
    p = prepared()
    fit = np.array([.8, .6, .0, .0])
    readings = (1., 0., 0., 0., 1.)          # topic and concreteness, sum 2
    parts = V.score(p, [(fit, readings)], [], band=.25, facets_on=True)
    assert parts['picked_counts'] == [2]
    adj = EDGE_POS[[0, 1, 2]] @ np.array(readings) / 2.
    assert adj.tolist() == pytest.approx([(.1 + .5) / 2, .5, .5])
    expect_c0 = .8 * .5 * (1 + adj[0]) + .6 * .25 * (1 + adj[1])
    expect_c1 = .6 * 1. * (1 + adj[2])
    assert parts['tag_part'].tolist() == pytest.approx([expect_c0, expect_c1, 0.])
    assert parts['tag_part_plain'].tolist() == pytest.approx([.8 * .5 + .6 * .25, .6, 0.])
    assert parts['text_part'].tolist() == [0., 0., 0.]


def test_readings_that_distinguish_all_five_columns_give_the_exact_weighted_mean():
    p = prepared()
    readings = (.1, .2, .3, .4, .5)          # sum 1.5, every column its own weight
    fit = np.array([.0, .0, .9, .0])         # picks t2 alone: edge 3, values .5 each
    parts = V.score(p, [(fit, readings)], [], band=.002, facets_on=True)
    assert parts['picked_counts'] == [1]
    assert parts['adjust'].tolist() == pytest.approx([.5])
    fit = np.array([.9, .0, .0, .0])         # picks the first tag: edge 0, five distinct values
    parts = V.score(p, [(fit, readings)], [], band=.002, facets_on=True)
    expect = (.1 * .1 + .2 * .2 + .3 * .3 + .4 * .4 + .5 * .5) / 1.5
    assert parts['adjust'].tolist() == pytest.approx([expect])
    assert parts['tag_part'][0] == pytest.approx(.9 * .5 * (1 + expect))
    # Every column pulls its own way: a different reading gives a different adjust.
    other = V.score(p, [(fit, (.5, .4, .3, .2, .1))], [], band=.002, facets_on=True)
    assert other['adjust'].tolist() != pytest.approx(parts['adjust'].tolist())


def test_adjust_is_zero_when_every_reading_is_zero():
    p = prepared()
    fit = np.array([.8, .6, .0, .0])
    parts = V.score(p, [(fit, (0., 0., 0., 0., 0.))], [], band=.25, facets_on=True)
    assert parts['tag_part'].tolist() == pytest.approx(parts['tag_part_plain'].tolist())
    assert parts['adjust'].tolist() == [0., 0., 0.]


def test_facets_off_is_the_multiplicative_identity():
    p = prepared()
    fit = np.array([.8, .6, .0, .0])
    readings = (1., 1., 1., 1., 1.)
    on = V.score(p, [(fit, readings)], [], band=.25, facets_on=True)
    off = V.score(p, [(fit, readings)], [], band=.25, facets_on=False)
    assert off['tag_part'].tolist() == pytest.approx(off['tag_part_plain'].tolist())
    assert off['tag_part'].tolist() == pytest.approx(on['tag_part_plain'].tolist())
    assert on['tag_part'].tolist() != pytest.approx(on['tag_part_plain'].tolist())


def test_text_probes_add_their_cosine_per_chunk_and_the_knobs_separate_them():
    p = prepared()
    fit = np.array([.8, .0, .0, .0])
    parts = V.score(p, [(fit, (1., 0., 0., 0., 0.))],
                    [np.array([.1, .2, .3]), np.array([.05, .0, .0])],
                    band=.002, facets_on=True)
    assert parts['text_part'].tolist() == pytest.approx([.15, .2, .3])
    allp = V.combine_parts(parts, probes='all', facets_on=True)
    tags = V.combine_parts(parts, probes='tags', facets_on=True)
    text = V.combine_parts(parts, probes='text', facets_on=True)
    assert allp.tolist() == pytest.approx((tags + text).tolist())
    assert tags.tolist() == pytest.approx(parts['tag_part'].tolist())
    assert text.tolist() == pytest.approx([.15, .2, .3])
    with pytest.raises(ValueError):
        V.combine_parts(parts, probes='none', facets_on=True)


# --- the order --------------------------------------------------------------

def test_full_order_is_every_chunk_and_ties_break_on_chunk_id():
    total = np.array([1., 3., 1.])
    flat = np.zeros(3, dtype=np.int64)
    order = V.order_keys(CHUNK_IDS, total, flat)
    assert order == [1, 0, 2]
    assert len(order) == len(CHUNK_IDS)


def test_area_first_sorts_in_area_chunks_before_a_higher_scoring_outsider():
    total = np.array([1., 3., 1.])
    rank = np.array([1, 1, 0], dtype=np.int64)
    assert V.order_keys(CHUNK_IDS, total, rank) == [2, 1, 0]


def test_area_off_gives_a_flat_rank_and_area_first_reads_the_meet(monkeypatch):
    p = prepared()
    rank, meta = V._area_rank(p, 'any question', 'off')
    assert rank.tolist() == [0, 0, 0] and meta == {'mode': 'off'}

    class Stub:
        @contextmanager
        def session(self, **kwargs):
            yield None

    p = V.Prepared(**{**p.__dict__, 'driver': Stub()})
    monkeypatch.setattr(V.LAND, 'land', lambda text, landings: ['hit'])
    monkeypatch.setattr(V.LAND, 'areas', lambda session, hits: V.LAND.Areas(
        by_node={('Product', 'P'): {'c1'}}, by_chunk={'c1': {('Product', 'P')}}, by_route={}))
    monkeypatch.setattr(V.LAND, 'combine', lambda reached, hits: V.LAND.Area(
        chunks=frozenset({'c1'}), landings={('product', 'P'): frozenset({'c1'})},
        nodes={('product', 'P'): (('Product', 'P'),)}, by_chunk={}, unmet=()))
    rank, meta = V._area_rank(p, 'any question', 'first')
    assert rank.tolist() == [1, 0, 1] and meta['area'] == 1 and meta['mode'] == 'first'


# --- the probes -------------------------------------------------------------

def toy_query():
    raw = {'description': 'Sought content',
           'tags': [{'t': 'shared phrase', 'facets': dict(zip(V.FACETS, [0, 1, 0, 1, 0]))},
                    {'t': 'other phrase', 'facets': dict(zip(V.FACETS, [1, 0, 1, 0, 1]))}]}
    return Q.parse('Original question?', raw)


def test_one_call_gives_two_tags_with_their_readings():
    query = toy_query()
    assert query.question == 'Original question?'
    assert query.description == 'Sought content'
    assert [t.text for t in query.tags] == ['shared phrase', 'other phrase']
    assert query.tags[0].readings != query.tags[1].readings


def test_answer_one_question_delivers_the_full_order_and_credits_only_the_kept_rows(monkeypatch):
    p = prepared()
    monkeypatch.setattr(V, '_interpret', lambda text, prep: (toy_query(), ModelUsage(), []))

    def fake_cosines(text, tags, prep):
        fit = np.array([[.9, .89, .1, .1]] * len(tags))
        return ({'query_tag_cosines': fit,
                 'query_description_cosines': np.array([.30, .20, .10])},
                ModelUsage(), {'vector_sha256': 'deadbeef'})

    monkeypatch.setattr(V, '_query_cosines', fake_cosines)
    seen = {}

    def fake_budget(rows, budget, doc_cache):
        seen['rows'] = [r['chunkId'] for r in rows]
        # Two whole rows credited, the third delivered as a truncated boundary.
        return (['one', 'two', 'thr'], [['a'], ['b'], ['c']], ['a', 'b'],
                {'budget': budget, 'chars': budget, 'kept': 2,
                 'boundary': {'id': rows[2]['chunkId'], 'chars_kept': 3, 'chars_full': 9},
                 'exhausted': False})

    monkeypatch.setattr(V, '_budget_contexts', fake_budget)
    for name in ('HERB_V4_BAND', 'HERB_V4_PROBES', 'HERB_V4_FACETS', 'HERB_V4_AREA',
                 'HERB_V4_TAGSIDE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HERB_V4_SORT', 'sum')
    out = V.answer_one_question(('q1', 'Original question?'), p, None, 50, 100)
    # The old summed numbers: band 0.002 picks the first tag alone for both query tags;
    # c0 = 2 x (.9 * .5 * 1.3) from the tag part + 2 x .30 from the two text probes.
    assert out.meta['ranking']['delivered_scores'] == pytest.approx([1.77, .40])
    assert out.meta['ranking']['delivered_chunk_ids'] == ['c0', 'c1']
    # The whole order reaches the budget, not a k cut.
    assert seen['rows'] == list(CHUNK_IDS) or sorted(seen['rows']) == sorted(CHUNK_IDS)
    assert len(seen['rows']) == len(CHUNK_IDS)
    d = out.meta['diagnostics']
    assert out.meta['returned'] == 3
    assert d['credited_delivered_rows'] == 2
    assert len(out.meta['ranking']['delivered_chunk_ids']) == 2
    assert d['boundary_chunk_id_not_credited'] == seen['rows'][2]
    assert len(d['text_share_of_delivered_score']) == 2
    assert all(0. <= s <= 1. for s in d['text_share_of_delivered_score'] if s is not None)
    assert len(d['tag_part_of_delivered_score']) == 2
    assert len(d['text_part_of_delivered_score']) == 2
    assert len(out.meta['ranking']['ordered_chunk_ids']) == len(CHUNK_IDS)
    assert out.meta['policy']['resolved']['tagside'] == 'all'
    assert out.meta['interpreter']['model'] == V.INTERPRET_MODEL


def test_text_probe_flip_diagnostic_is_none_when_only_text_probes_run(monkeypatch):
    p = prepared()
    monkeypatch.setattr(V, '_interpret', lambda text, prep: (toy_query(), ModelUsage(), []))
    monkeypatch.setattr(V, '_query_cosines', lambda text, tags, prep: (
        {'query_tag_cosines': np.array([[.9, .89, .1, .1]] * len(tags)),
         'query_description_cosines': np.array([.30, .20, .10])},
        ModelUsage(), {'vector_sha256': 'deadbeef'}))
    monkeypatch.setattr(V, '_budget_contexts', lambda rows, budget, cache: (
        ['a', 'b'], [[], []], [], {'budget': budget, 'chars': 2, 'kept': 2,
                                   'boundary': None, 'exhausted': False}))
    for name in ('HERB_V4_BAND', 'HERB_V4_FACETS', 'HERB_V4_AREA', 'HERB_V4_TAGSIDE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HERB_V4_SORT', 'sum')
    monkeypatch.setenv('HERB_V4_PROBES', 'text')
    out = V.answer_one_question(('q1', 'Original question?'), p, None, 50, 100)
    d = out.meta['diagnostics']
    assert d['flip_fraction_text_probes_off'] is None
    assert d['flip_fraction_facets_off'] is None
    assert d['boundary_chunk_id_not_credited'] is None
    assert d['tag_part_of_delivered_score'] == [0., 0.]


# --- the rest ---------------------------------------------------------------

def test_stored_facet_positions_are_never_recomputed_or_written():
    p = prepared()
    before = p.edge_pos.copy()
    fit = np.array([.8, .8, .8, .8])
    V.score(p, [(fit, (1., 1., 1., 1., 1.))], [np.zeros(3)], band=.002, facets_on=True)
    V.score(p, [(fit, (0., 0., 0., 1., 0.))], [], band=.002, facets_on=True)
    assert p.edge_pos.tolist() == before.tolist()
    a = V.score(p, [(fit, (1., 0., 0., 0., 0.))], [], band=.002, facets_on=True)
    b = V.score(p, [(fit, (1., 0., 0., 0., 0.))], [], band=.002, facets_on=True)
    assert a['tag_part'].tolist() == b['tag_part'].tolist()
    assert a['adjust'].tolist() == pytest.approx(EDGE_POS[:, 0].tolist())


def test_knobs_default_and_reject_an_unknown_value(monkeypatch):
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    assert V.knobs() == {'sort': 'strength', 'fiteq': 'noise', 'structat': 'after_facets',
                         'qtopic': 'off', 'edgecomb': 'sum', 'descjoin': 'key', 'join': 'adjust',
                         'band': 'noise', 'probes': 'all', 'facets': 'on', 'area': 'off',
                         'tagside': 'all', 'offline': 'off'}
    monkeypatch.setenv('HERB_V4_FITEQ', 'wide')
    with pytest.raises(ValueError):
        V.knobs()
    monkeypatch.delenv('HERB_V4_FITEQ')
    monkeypatch.setenv('HERB_V4_STRUCT_AT', 'first')
    with pytest.raises(ValueError):
        V.knobs()
    monkeypatch.delenv('HERB_V4_STRUCT_AT')
    monkeypatch.setenv('HERB_V4_OFFLINE', 'yes')
    with pytest.raises(ValueError):
        V.knobs()
    monkeypatch.delenv('HERB_V4_OFFLINE')
    monkeypatch.setenv('HERB_V4_JOIN', 'max')
    with pytest.raises(ValueError):
        V.knobs()
    monkeypatch.delenv('HERB_V4_JOIN')
    monkeypatch.setenv('HERB_V4_SORT', 'summed')
    with pytest.raises(ValueError):
        V.knobs()
    monkeypatch.delenv('HERB_V4_SORT')
    assert V.BANDS == {'noise': .002, 'paraphrase': .028}
    monkeypatch.setenv('HERB_V4_BAND', 'wide')
    with pytest.raises(ValueError):
        V.knobs()
    monkeypatch.setenv('HERB_V4_BAND', 'noise')
    monkeypatch.setenv('HERB_V4_TAGSIDE', 'scope')
    with pytest.raises(ValueError):
        V.knobs()


def test_eta_squared_and_flip_fraction():
    values = np.array([1., 1., 3., 3.])
    kinds = np.array(['a', 'a', 'b', 'b'], dtype=object)
    assert V._eta_squared(values, kinds) == pytest.approx(1.)
    assert V._eta_squared(np.array([2., 2.]), np.array(['a', 'b'], dtype=object)) is None
    flat = np.zeros(3, dtype=np.int64)
    delivered = [1, 0, 2]
    assert V._flip_fraction(delivered, np.array([1., 3., 1.]), flat) == 0.
    assert V._flip_fraction(delivered, np.array([9., 0., 0.]), flat) == pytest.approx(.5)
    # An exact tie under the alternative is not a flip.
    assert V._flip_fraction(delivered, np.zeros(3), flat) == 0.
    assert V._flip_fraction([0], np.zeros(3), flat) is None


def test_prepared_exposes_close():
    closed = []

    class Stub:
        def close(self):
            closed.append(True)

    V.Prepared(**{**prepared().__dict__, 'driver': Stub()}).close()
    assert closed == [True]
    V.Prepared(**{**prepared().__dict__, 'driver': None}).close()


# --- the chain --------------------------------------------------------------
# Graph tags ProductX (a product name), a, b, c; chunks c0..c4, c4 carrying no edge at all.
CH_TAGS = ('ProductX', 'a', 'b', 'c')
CH_CHUNKS = ('c0', 'c1', 'c2', 'c3', 'c4')
CH_EDGE_TAG = np.array([0, 1, 1, 2, 3])          # (P,c3) (a,c0) (a,c1) (b,c1) (c,c2)
CH_EDGE_CHUNK = np.array([3, 0, 1, 1, 2])
CH_TOPIC = np.array([.5, .4005, .4005, .3, .4])
CH_D = np.array([.1, .2, .3, .9, .95])


def chain_prepared(pos=None):
    return V.Prepared(
        chunk_rows=tuple({'chunkId': c} for c in CH_CHUNKS), chunk_ids=CH_CHUNKS,
        chunk_kinds=('pr',) * 5, graph_tags=CH_TAGS, product_tags=('ProductX',),
        nonscope_eligible=np.array([False, True, True, True]),
        tag_vectors=np.eye(4), chunk_vectors=np.eye(5), edge_tag=CH_EDGE_TAG,
        edge_chunk=CH_EDGE_CHUNK, edge_topic=CH_TOPIC,
        edge_pos=np.zeros((5, 5)) if pos is None else pos, landings=(), driver=None,
        cache_dir=None, provenance={}, build_stats=BuildStats(0., ModelUsage(), []))


def test_fit_levels_are_whole_noise_steps_below_the_given_best_floored():
    best = .5
    fit = np.array([best, best - .002, best - .0039, best - .004, best - .0061, best - .014])
    assert V.fit_levels(fit, best).tolist() == [0, 1, 1, 2, 3, 7]
    for b in (.5, .4, .37, .61):
        k = np.arange(8)
        assert V.fit_levels(b - k * V.COS_NOISE, b).tolist() == k.tolist()
    # A tag given no level is -1; the best is taken over the rest.
    mask = np.array([False, True, True, True, True, True])
    assert V.best_fit_all([fit], mask) == best - .002
    assert V.fit_levels(fit, V.best_fit_all([fit], mask), mask).tolist() == [-1, 0, 0, 1, 2, 6]
    assert V.COS_NOISE == .002


def test_best_fit_all_is_the_highest_fit_over_every_query_tag():
    assert V.best_fit_all([np.array([.1, .3]), np.array([.45, .2])]) == .45
    assert V.best_fit_all([np.array([.9, .3])], np.array([False, True])) == .3
    assert V.best_fit_all([np.array([.9, .3])], np.array([False, False])) is None


Q1 = (np.array([.500, .4990, .4950, .3001]), (1., 1., 1., 1., 1.))
Q2 = (np.array([0., 0., .4491, 0.]), (1., 1., 1., 1., 1.))
Q_WEAK = (np.array([.1, .1, .1, .2]), (1., 1., 1., 1., 1.))


def test_each_chunk_takes_its_best_key_and_the_description_breaks_the_tie():
    chain = V.chain_order(chain_prepared(), [Q1, Q2], CH_D, facets_on=True)
    # One scale, anchored at Q1's .5: ProductX and a at fit level 0, b at 2, c at 99; Q2's
    # b sits at floor(.0509 / .002) = 25. At level 0 the top rel is (ProductX,c3) .5, so
    # (a,c0) and (a,c1) sit at floor(.0995 / .002) = 49. c1 is also reached through b at
    # levels 2 and 25; its best stays (0, 49).
    assert chain['best_fit_level'].tolist() == [0, 0, 99, 0, -1]
    assert chain['best_rel_level'].tolist() == [49, 49, 0, 0, -1]
    # c0 and c1 tie on both tag keys: the description decides (c1 .2 before c0 .1).
    # c4 has no edge: it follows every reached chunk.
    assert [CH_CHUNKS[i] for i in chain['order']] == ['c3', 'c1', 'c0', 'c2', 'c4']
    assert chain['query_tags_at_best_key'].tolist() == [1, 1, 1, 1, 0]


def test_more_query_tags_reaching_a_chunk_do_not_lift_it():
    one = V.chain_order(chain_prepared(), [Q1], CH_D, facets_on=True)
    two = V.chain_order(chain_prepared(), [Q1, Q2], CH_D, facets_on=True)
    assert one['order'] == two['order']
    assert one['best_fit_level'].tolist() == two['best_fit_level'].tolist()


def test_the_facet_adjust_moves_the_relevance_level_and_facets_off_removes_it():
    pos = np.zeros((5, 5))
    pos[1] = 1.                                   # (a,c0): adjust 1, rel .801
    on = V.chain_order(chain_prepared(pos), [Q1], CH_D, facets_on=True)
    off = V.chain_order(chain_prepared(pos), [Q1], CH_D, facets_on=False)
    assert [CH_CHUNKS[i] for i in on['order']][:3] == ['c0', 'c3', 'c1']
    assert on['best_rel_level'].tolist()[:2] == [0, 200]      # floor((.801 - .4005) / .002)
    assert [CH_CHUNKS[i] for i in off['order']][:3] == ['c3', 'c1', 'c0']
    zero = V.chain_order(chain_prepared(pos), [(Q1[0], (0., 0., 0., 0., 0.))], CH_D,
                         facets_on=True)
    assert zero['order'] == off['order']


def test_a_weak_query_tag_lands_deeper_on_the_one_scale():
    p = chain_prepared()
    alone = V.chain_order(p, [Q_WEAK], CH_D, facets_on=True)
    beside = V.chain_order(p, [Q1, Q_WEAK], CH_D, facets_on=True)
    # Alone, the weak tag's nearest graph tag (c, .2) is its own level 0.
    assert alone['best_fit_level'][2] == 0
    # Beside Q1 the question's best is .5: the weak tag's .2 match sinks to
    # floor(.3 / .002) and c2 keeps Q1's deeper-but-better (c, .3001) level 99.
    assert V.fit_levels(Q_WEAK[0], .5)[3] == int(np.floor((.5 - .2) / V.COS_NOISE))
    assert V.fit_levels(Q_WEAK[0], .5)[3] > 99
    assert beside['best_fit_level'][2] == 99
    assert beside['best_fit_all'] == .5


def test_the_key_base_keeps_the_deepest_relevance_of_one_level_above_the_next_level():
    tags = ('a', 'b')
    chunks = ('c0', 'c1', 'c2')
    prep = V.Prepared(
        chunk_rows=tuple({'chunkId': c} for c in chunks), chunk_ids=chunks,
        chunk_kinds=('pr',) * 3, graph_tags=tags, product_tags=(),
        nonscope_eligible=np.array([True, True]), tag_vectors=np.eye(2),
        chunk_vectors=np.eye(3), edge_tag=np.array([0, 0, 1]), edge_chunk=np.array([0, 1, 2]),
        edge_topic=np.array([.5, .3001, .4]), edge_pos=np.zeros((3, 5)), landings=(),
        driver=None, cache_dir=None, provenance={},
        build_stats=BuildStats(0., ModelUsage(), []))
    # a at fit level 0 reaches c0 (rel .5, rl 0) and c1 (rel .3001, rl 99); b at fit level 1
    # reaches c2 (rl 0). c2 has the highest description: were the base rl.max() = 99, the
    # keys (0, 99) and (1, 0) would collide and c2 would jump ahead of c1.
    chain = V.chain_order(prep, [(np.array([.5, .498]), (0., 0., 0., 0., 0.))],
                          np.array([.1, .2, .9]), facets_on=True)
    assert chain['best_rel_level'].tolist() == [0, 99, 0]
    assert chain['best_fit_level'].tolist() == [0, 0, 1]
    assert chain['key_base'] == 100
    assert [chunks[i] for i in chain['order']] == ['c0', 'c1', 'c2']


def test_unreached_chunks_follow_in_description_order():
    chain = V.chain_order(chain_prepared(), [Q1], CH_D, facets_on=True, tagside='nonscope')
    # Without the product tag c3 is reached by nothing; c4 never is. Both trail, by d.
    assert chain['reached'].tolist() == [True, True, True, False, False]
    assert [CH_CHUNKS[i] for i in chain['order']][-2:] == ['c4', 'c3']
    assert len(chain['order']) == len(CH_CHUNKS)


def test_chain_meta_counts_what_the_cut_saw():
    p = chain_prepared()
    chain = V.chain_order(p, [Q1, Q2], CH_D, facets_on=True)
    order = chain['order']
    meta = V.chain_meta(p, chain, order[:3])
    assert meta['last_credited_fit_level'] == 0
    assert meta['last_credited_rel_level'] == 49
    assert meta['credited_rows_decided_by_description'] == 2      # c1 and c0
    assert meta['credited_rows_decided_by_chunk_id'] == 0
    assert meta['credited_unreached_rows'] == 0
    assert meta['graph_tags_at_fit_level_0'] == 2                   # ProductX and a, both Q1
    assert meta['product_named_graph_tags_at_fit_level_0'] == 1
    assert [row['fit_level'] for row in meta['fit_levels_opened']] == [0]
    assert meta['fit_levels_opened'][0]['query_tag_graph_tag_pairs'] == 2
    assert meta['fit_levels_opened'][0]['chunks_reached'] == 3
    assert meta['fit_levels_opened'][0]['chunks_whose_best_is_here'] == 3
    tail = V.chain_meta(p, chain, order)
    assert tail['credited_unreached_rows'] == 1


def test_the_description_counts_only_ties_inside_the_credited_list():
    p = chain_prepared()
    chain = V.chain_order(p, [Q1], CH_D, facets_on=True)
    order = chain['order']                                           # c3, c1, c0, c2, c4
    # Cut after c1: c1's tie partner c0 lies past the cut, so nothing is decided by d.
    cut = V.chain_meta(p, chain, order[:2])
    assert cut['credited_rows_decided_by_description'] == 0
    assert cut['credited_rows_decided_by_chunk_id'] == 0
    # Equal descriptions: the tie inside the credited list is decided by the chunk id.
    same = V.chain_order(p, [Q1], np.array([.2, .2, .3, .9, .95]), facets_on=True)
    meta = V.chain_meta(p, same, same['order'][:3])
    assert [CH_CHUNKS[i] for i in same['order']][:3] == ['c3', 'c0', 'c1']
    assert meta['credited_rows_decided_by_description'] == 0
    assert meta['credited_rows_decided_by_chunk_id'] == 2


def test_answer_one_question_runs_the_chain_when_asked_and_records_the_knobs(monkeypatch):
    monkeypatch.setenv('HERB_V4_SORT', 'chain')
    p = chain_prepared()
    monkeypatch.setattr(V, '_interpret', lambda text, prep: (toy_query(), ModelUsage(), []))

    def fake_cosines(text, tags, prep):
        d = CH_D if text == 'Sought content' else np.array([.9, .8, .7, .0, .0])
        return ({'query_tag_cosines': np.array([Q1[0]] * len(tags)),
                 'query_description_cosines': d},
                ModelUsage(), {'vector_sha256': 'deadbeef'})

    monkeypatch.setattr(V, '_query_cosines', fake_cosines)
    seen = {}

    def fake_budget(rows, budget, doc_cache):
        seen['rows'] = [r['chunkId'] for r in rows]
        return (['x'] * 4, [[]] * 4, [], {'budget': budget, 'chars': budget, 'kept': 3,
                'boundary': {'id': rows[3]['chunkId'], 'chars_kept': 1, 'chars_full': 2},
                'exhausted': False})

    monkeypatch.setattr(V, '_budget_contexts', fake_budget)
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HERB_V4_SORT', 'chain')
    out = V.answer_one_question(('q1', 'Original question?'), p, None, 50, 100)
    # The raw question's description cosines are never read by the chain: only the
    # interpreted branch's description orders ties (c1 before c0, not c0 before c1).
    assert seen['rows'] == ['c3', 'c1', 'c0', 'c2', 'c4']
    m = out.meta
    assert m['diagnostics']['credited_delivered_rows'] == 3
    assert m['diagnostics']['boundary_chunk_id_not_credited'] == 'c2'
    assert m['ranking']['delivered_chunk_ids'] == ['c3', 'c1', 'c0']
    assert m['ranking']['delivered_fit_levels'] == [0, 0, 0]
    assert 'text_share_of_delivered_score' not in m['diagnostics']
    assert m['interpreter']['text_probes'] == 0
    recorded = m['policy']['knobs_recorded']
    assert recorded['active'] == {'HERB_V4_SORT': 'chain', 'HERB_V4_JOIN': 'adjust',
                                  'HERB_V4_BAND': 'noise', 'HERB_V4_PROBES': 'all',
                                  'HERB_V4_FACETS': 'on', 'HERB_V4_AREA': 'off',
                                  'HERB_V4_TAGSIDE': 'all', 'HERB_V4_QTOPIC': 'off',
                                  'HERB_V4_EDGECOMB': 'sum', 'HERB_V4_DESCJOIN': 'key',
                                  'HERB_V4_FITEQ': 'noise', 'HERB_V4_OFFLINE': 'off',
                                  'HERB_V4_STRUCT_AT': 'after_facets'}
    assert set(recorded['ignored_by_active_sort']) == {'HERB_V4_JOIN', 'HERB_V4_BAND',
                                                        'HERB_V4_PROBES', 'HERB_V4_AREA',
                                                        'HERB_V4_QTOPIC', 'HERB_V4_EDGECOMB',
                                                        'HERB_V4_DESCJOIN', 'HERB_V4_FITEQ',
                                                        'HERB_V4_STRUCT_AT'}
    assert m['policy']['band_value'] is None
    assert m['policy']['fit_equal_width'] is None
    monkeypatch.setenv('HERB_V4_SORT', 'sum')
    out = V.answer_one_question(('q1', 'Original question?'), p, None, 50, 100)
    recorded = out.meta['policy']['knobs_recorded']
    assert recorded['active']['HERB_V4_SORT'] == 'sum'
    assert recorded['ignored_by_active_sort'] == ['HERB_V4_FITEQ', 'HERB_V4_STRUCT_AT',
                                                  'HERB_V4_QTOPIC', 'HERB_V4_EDGECOMB',
                                                  'HERB_V4_DESCJOIN', 'HERB_V4_JOIN']


def test_duplicate_tags_from_the_querytagger_are_collapsed_not_fatal():
    raw = {'description': 'Sought content',
           'tags': [{'t': 'Churn rate', 'facets': dict(zip(V.FACETS, [1, 0, 0, 0, 0]))},
                    {'t': 'churn rate', 'facets': dict(zip(V.FACETS, [0, 1, 0, 0, 0]))},
                    {'t': 'other', 'facets': dict(zip(V.FACETS, [0, 0, 1, 0, 0]))}]}
    cleaned, dropped = V._collapse_duplicate_tags(raw)
    assert dropped == 1
    query = Q.parse('Original question?', cleaned)
    assert [t.text for t in query.tags] == ['Churn rate', 'other']
    assert query.tags[0].readings == (1, 0, 0, 0, 0)
    assert V._collapse_duplicate_tags('not a dict') == ('not a dict', 0)


# --- the concept sort -------------------------------------------------------
# On the chain toy: ProductX reaches only c3, so under concept c3 has no eligible edge;
# c4 has no edge at all. Two query tags; readings zero so the adjust is off unless set.
QA = (np.array([.9, .5, .8, .1]), (0., 0., 0., 0., 0.))
QB = (np.array([0., .2, .1, .9]), (0., 0., 0., 0., 0.))
DQ = np.array([.5, .5, .5, .5, .5])
DD = np.array([.1, .2, .3, .4, .5])


def test_concept_keeps_the_best_edge_per_query_tag_not_the_sum_of_its_edges():
    one = V.concept_order(chain_prepared(), [QA], DQ, DD, facets_on=True)
    # c1 has (a,c1) .5 * .4005 = .20025 and (b,c1) .8 * .3 = .24 from QA: it keeps .24.
    assert one['S'][1] == pytest.approx(.24)
    assert one['S'][1] != pytest.approx(.20025 + .24)
    assert one['winners'][0][1] == 2                       # through b


def test_concept_sums_the_tag_terms_over_query_tags():
    both = V.concept_order(chain_prepared(), [QA, QB], DQ, DD, facets_on=True)
    assert both['S'].tolist() == pytest.approx([.20025 + .0801, .24 + .0801, .04 + .36, 0., 0.])
    assert both['D'].tolist() == pytest.approx([.6, .7, .8, .9, 1.])


def test_concept_excludes_the_product_name_tags_whatever_tagside_says(monkeypatch):
    monkeypatch.setenv('HERB_V4_TAGSIDE', 'all')
    concept = V.concept_order(chain_prepared(), [QA], DQ, DD, facets_on=True)
    # ProductX fits QA best (.9) and is the only tag on c3, yet c3 gets nothing.
    assert concept['S'][3] == 0.
    assert concept['reached'].tolist() == [True, True, True, False, False]
    assert concept['top_tags'] == [2]                     # b, not ProductX
    assert V.knob_record(V.knobs() | {'sort': 'concept'})[
        'product_name_tags_excluded_by_the_sort'] is True


def test_concept_mul_and_add_joins():
    mul = V.concept_order(chain_prepared(), [QA, QB], DQ, DD, facets_on=True, join='mul')
    add = V.concept_order(chain_prepared(), [QA, QB], DQ, DD, facets_on=True, join='add')
    assert mul['score'].tolist() == pytest.approx((mul['S'] * mul['D']).tolist())
    assert add['score'].tolist() == pytest.approx((add['S'] + add['D']).tolist())
    # mul: the two unreached chunks score 0 and tie, broken by chunk id.
    assert [CH_CHUNKS[i] for i in mul['order']] == ['c2', 'c1', 'c0', 'c3', 'c4']
    # add: the text factor lifts c4 (D 1.0) and c3 (D .9) above c0 (S .28 + D .6).
    assert [CH_CHUNKS[i] for i in add['order']] == ['c2', 'c1', 'c4', 'c3', 'c0']
    assert len(mul['order']) == len(add['order']) == len(CH_CHUNKS)
    with pytest.raises(ValueError):
        V.concept_order(chain_prepared(), [QA], DQ, DD, facets_on=True, join='max')


def test_concept_facets_scale_the_edge_and_facets_off_leaves_fit_times_topic():
    pos = np.zeros((5, 5))
    pos[3] = 1.                                            # (b,c1)
    readings = (1., 1., 1., 1., 1.)
    on = V.concept_order(chain_prepared(pos), [(QA[0], readings)], DQ, DD, facets_on=True)
    off = V.concept_order(chain_prepared(pos), [(QA[0], readings)], DQ, DD, facets_on=False)
    zero = V.concept_order(chain_prepared(pos), [(QA[0], (0., 0., 0., 0., 0.))], DQ, DD,
                           facets_on=True)
    assert on['S'][1] == pytest.approx(.24 * 2)
    assert off['S'][1] == pytest.approx(.24)
    assert zero['S'][1] == pytest.approx(.24)


def test_concept_meta_counts_hub_tags_and_names_where_each_query_tag_landed(monkeypatch):
    from scipy.stats import spearmanr
    p = chain_prepared()
    concept = V.concept_order(p, [QA, QB], DQ, DD, facets_on=True)
    monkeypatch.setattr(V, 'HUB_EDGES', 2)                 # only a has two edges
    meta = V.concept_meta(p, concept, concept['order'][:3])
    assert meta['query_tags'] == 2
    assert meta['hub_tags_used'] == ['a']
    assert meta['delivered_chunks_with_a_best_edge_through_a_hub_tag'] == 2   # c1, c0
    assert meta['top_graph_tag_by_fit_per_query_tag'] == ['b', 'c']
    assert meta['delivered_S'] == pytest.approx([.4, .3201, .28035])
    assert meta['delivered_D'] == pytest.approx([.8, .7, .6])
    assert meta['spearman_S_D_all_chunks'] == pytest.approx(
        spearmanr(concept['S'], concept['D']).statistic)
    assert meta['chunks_without_an_eligible_edge'] == 2


def test_answer_one_question_runs_the_concept_sort_when_asked(monkeypatch):
    p = chain_prepared()
    monkeypatch.setattr(V, '_interpret', lambda text, prep: (toy_query(), ModelUsage(), []))

    def fake_cosines(text, tags, prep):
        fits = np.array([QA[0], QB[0]][:len(tags)]).reshape(len(tags), 4)
        d = DD if text == 'Sought content' else DQ
        return ({'query_tag_cosines': fits, 'query_description_cosines': d},
                ModelUsage(), {'vector_sha256': 'deadbeef'})

    monkeypatch.setattr(V, '_query_cosines', fake_cosines)
    seen = {}

    def fake_budget(rows, budget, doc_cache):
        seen['rows'] = [r['chunkId'] for r in rows]
        return (['x'] * 3, [[]] * 3, [], {'budget': budget, 'chars': budget, 'kept': 2,
                'boundary': {'id': rows[2]['chunkId'], 'chars_kept': 1, 'chars_full': 2},
                'exhausted': False})

    monkeypatch.setattr(V, '_budget_contexts', fake_budget)
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HERB_V4_SORT', 'concept')
    out = V.answer_one_question(('q1', 'Original question?'), p, None, 50, 100)
    assert seen['rows'] == ['c2', 'c1', 'c0', 'c3', 'c4']
    m = out.meta
    assert m['ranking']['delivered_chunk_ids'] == ['c2', 'c1']
    assert m['diagnostics']['boundary_chunk_id_not_credited'] == 'c0'
    assert m['diagnostics']['delivered_S'] == pytest.approx([.4, .3201])
    recorded = m['policy']['knobs_recorded']
    assert recorded['active']['HERB_V4_SORT'] == 'concept'
    assert recorded['active']['HERB_V4_JOIN'] == 'adjust'
    assert recorded['product_name_tags_excluded_by_the_sort'] is True
    # adjust: S * (1 + D) = .4 * 1.8 and .3201 * 1.7.
    assert m['ranking']['delivered_scores'] == pytest.approx([.4 * 1.8, .3201 * 1.7])
    assert set(recorded['ignored_by_active_sort']) == {'HERB_V4_BAND', 'HERB_V4_PROBES',
                                                        'HERB_V4_AREA', 'HERB_V4_TAGSIDE',
                                                        'HERB_V4_QTOPIC', 'HERB_V4_EDGECOMB',
                                                        'HERB_V4_DESCJOIN', 'HERB_V4_FITEQ',
                                                        'HERB_V4_STRUCT_AT'}
    assert m['policy']['product_named_tags_excluded'] == 1



def test_the_adjust_is_the_mean_of_four_facets_and_keeps_the_size_of_the_readings():
    pos = np.zeros((5, 5))
    pos[3] = [.9, .2, .4, .6, .8]                          # (b,c1): topic_pos .9 is never read
    fit = QA[0]
    small = V.concept_order(chain_prepared(pos), [(fit, (1., .1, .1, .1, .1))], DQ, DD,
                            facets_on=True)
    full = V.concept_order(chain_prepared(pos), [(fit, (0., 1., 1., 1., 1.))], DQ, DD,
                           facets_on=True)
    topic_only = V.concept_order(chain_prepared(pos), [(fit, (1., 0., 0., 0., 0.))], DQ, DD,
                                 facets_on=True)
    # (b,c1) rel = .8 * .3 * (1 + adjust); a reading of .1 on each of the four facets keeps
    # a tenth of the adjust a reading of 1.0 gives; the topic reading moves nothing.
    assert small['S'][1] == pytest.approx(.24 * (1 + (.2 + .4 + .6 + .8) * .1 / 4))
    assert full['S'][1] == pytest.approx(.24 * (1 + (.2 + .4 + .6 + .8) / 4))
    assert topic_only['S'][1] == pytest.approx(.24)
    assert V.ADJUST_FACETS == ('temporal', 'why', 'activity', 'concreteness')


def test_a_negative_closeness_is_no_closeness():
    topic = np.array([.5, .4005, .4005, .3, -.4])          # (c,c2) now negative
    prep = V.Prepared(**{**chain_prepared().__dict__, 'edge_topic': topic})
    # c's fit is negative too: unclipped, -.5 * -.4 = +.2 would reach c2.
    concept = V.concept_order(prep, [(np.array([0., 0., 0., -.5]), (0., 0., 0., 0., 0.))],
                              np.array([-.3, .1, .2, .0, .0]), np.array([.1, -.2, .3, .0, .0]),
                              facets_on=True)
    assert concept['S'][2] == 0.
    assert concept['D'].tolist() == pytest.approx([.1, .1, .5, 0., 0.])


def test_the_adjust_join_moves_the_tag_score_by_at_most_one_plus_d():
    both = V.concept_order(chain_prepared(), [QA, QB], DQ, DD, facets_on=True)
    assert both['score'].tolist() == pytest.approx((both['S'] * (1 + both['D'])).tolist())
    # c4 has the highest D and no tag: under adjust it stays at 0, last with c3 by id.
    assert [CH_CHUNKS[i] for i in both['order']] == ['c2', 'c1', 'c0', 'c3', 'c4']


def test_concept_meta_records_the_relative_spreads():
    p = chain_prepared()
    concept = V.concept_order(p, [QA, QB], DQ, DD, facets_on=True)
    meta = V.concept_meta(p, concept, concept['order'][:3])
    spread_d = meta['relative_spread_1_plus_D_all_chunks']
    low, high = np.percentile(1 + concept['D'], [5, 95])
    assert spread_d['p5'] == pytest.approx(low) and spread_d['p95'] == pytest.approx(high)
    assert spread_d['p95_over_p5'] == pytest.approx(high / low)
    # Two chunks have S = 0, so S's fifth percentile is 0 and the ratio is undefined.
    assert meta['relative_spread_S_all_chunks']['p5'] == 0.
    assert meta['relative_spread_S_all_chunks']['p95_over_p5'] is None
