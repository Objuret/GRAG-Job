"""artefact_v4's strength sort on toy arrays, and the arm run on it with no model call.

No live graph, no model call, no question text, no gold.
"""
from dataclasses import asdict
import inspect
import json
from statistics import NormalDist

import numpy as np
import pytest

from harness import chat
from harness.contract import BuildStats, ModelUsage
from arms import artefact_v4 as V
from artefact import query_content as Q
from artefact import v4_multikey as MK
from artefact import v4_rank as R4
from artefact import v4_strength as ST

INV = NormalDist().inv_cdf

# Graph tags ProductX (a product name), a, b, c, d, e; chunks c0..c5.
# Edges (P,c3) (a,c0) (a,c1) (b,c1) (c,c2) (d,c4) (e,c4) (b,c5): c3 carries only the
# product-name edge, so no eligible edge reaches it.
TAGS = ('ProductX', 'a', 'b', 'c', 'd', 'e')
CHUNKS = ('c0', 'c1', 'c2', 'c3', 'c4', 'c5')
EDGE_TAG = np.array([0, 1, 1, 2, 3, 4, 5, 2])
EDGE_CHUNK = np.array([3, 0, 1, 1, 2, 4, 4, 5])
TOPIC = np.array([.5, .40, .30, .20, .60, .25, .35, .10])
# Head scores per edge in ADJUST_FACETS order (temporal, why, activity, concreteness).
SCORES = np.array([[9., 9., 9., 9.],
                   [3.9, 1., 0., 0.],
                   [4.0, 3., 0., 0.],
                   [0., 0., 0., 0.],
                   [3.2, 2., 0., 0.],
                   [1., 5., 2., 1.],
                   [2., 4., 1., 3.],
                   [5., .5, 3., 2.]])
ELIGIBLE = np.array([False, True, True, True, True, True])
PRODUCT = np.array([0, 0, 0, 1, 1, 1])
CHANNEL_PAIRS = ((0, 0), (1, 0), (4, 1))        # (chunk, channel): c4 is alone on its channel
FILE = np.array([0, 0, 1, 1, 2, 2])
DD = np.array([.1, .2, .3, .4, .5, .25])
DQ = np.array([.5, .1, .2, .3, .4, .45])
# QA fits a (c0, c1) and leaves b below its bulk; QP fits b (c1, c5) and reads no facet.
QA = (np.array([.9, .8, .1, .2, .3, .15]), (1., .5, 1., 0., 0.))
QP = (np.array([.1, .1, .9, .2, .1, .3]), (0., 0., 0., 0., 0.))
UNIT = 1.4826 * .1                               # the spread of TOPIC over E, of QA's and QP's row


def _csr(pairs, rows):
    ptr, members = np.zeros(rows + 1, dtype=np.int64), []
    for i in range(rows):
        mine = sorted(v for k, v in pairs if k == i)
        members += mine
        ptr[i + 1] = ptr[i] + len(mine)
    return ptr, np.array(members, dtype=np.int64)


def layer(scores=SCORES, topic=TOPIC, eligible=ELIGIBLE, product=PRODUCT,
          channels=CHANNEL_PAIRS, file=FILE):
    ptr, members = _csr(list(channels), len(CHUNKS))
    return ST.build_layer(EDGE_TAG, EDGE_CHUNK, topic, scores, eligible, product, ptr, members,
                          file)


def run(query_tags, central=None, lay=None, dd=DD, dq=DQ):
    central = [.5] * len(query_tags) if central is None else central
    return ST.strength_order(CHUNKS, lay or layer(), query_tags, central, dd, dq)


def edge_values_by_hand(lay, row, readings):
    """fit(q, t) + w(q, e) per eligible edge, from the standing and the shares."""
    fit, _, _ = ST.standing(np.asarray(row)[ELIGIBLE])
    of_tag = dict(zip(np.flatnonzero(ELIGIBLE).tolist(), fit.tolist()))
    share, _ = ST.shares(readings)
    return [of_tag[int(t)] + float(v @ share) for t, v in zip(lay.edge_tag, lay.values)]


# --- the unit --------------------------------------------------------------------

def test_a_standing_counts_spreads_above_the_bulk():
    values = np.array([1., 2., 3., 4., 10.])
    out, bulk, spread = ST.standing(values)
    # median 3; absolute deviations 2, 1, 0, 1, 7, their median 1
    assert bulk == 3. and spread == pytest.approx(1.4826)
    assert out.tolist() == pytest.approx(((values - 3.) / 1.4826).tolist())
    # the unit is the population's own: the same values wider, or moved, stand the same
    assert ST.standing(values * 10.)[0].tolist() == pytest.approx(out.tolist())
    assert ST.standing(values + 5.)[0].tolist() == pytest.approx(out.tolist())
    assert ST.MAD_TO_SPREAD == 1.4826


def test_the_fit_is_the_standing_over_the_eligible_graph_tags():
    out = run([QA])
    # the product-name tag's .9 is no part of the population: bulk .2 over a..e, deviations
    # .6, .1, 0, .1, .05 with median .1
    assert out['query_tag_bulk'] == pytest.approx([.2])
    assert out['query_tag_spread'] == pytest.approx([UNIT])
    assert out['query_tag_best_standing'] == pytest.approx([(.8 - .2) / UNIT])
    assert out['eligible_graph_tags'] == 5 and out['eligible_edges'] == 7


def test_normal_scores_are_monotone_symmetric_and_read_the_order_only():
    column = np.array([.3, -1.2, 5., .31, 2.])
    scores = ST.normal_scores(column)
    assert scores.tolist() == pytest.approx([INV((r - .5) / 5) for r in (2, 1, 5, 3, 4)])
    assert np.argsort(scores).tolist() == np.argsort(column).tolist()
    assert ST.normal_scores(-column).tolist() == pytest.approx((-scores).tolist())
    assert scores.sum() == pytest.approx(0.)
    # any increasing rescaling of the column gives the same scores
    assert ST.normal_scores(np.exp(column)).tolist() == scores.tolist()
    assert ST.normal_scores(column * 1000. - 7.).tolist() == scores.tolist()


def test_ties_share_a_rank():
    scores = ST.normal_scores(np.array([1., 2., 2., 3.]))
    # ranks 1, 2.5, 2.5, 4
    assert scores.tolist() == pytest.approx([INV(.125), 0., 0., INV(.875)])
    assert scores[1] == scores[2]
    assert ST.normal_scores(np.zeros(3)).tolist() == pytest.approx([0., 0., 0.])
    assert ST.normal_scores(np.zeros(0)).shape == (0,)


def test_shares_divide_by_the_sum_and_fall_back_to_equal_shares():
    share, equal = ST.shares((1., .5, 1., 0., 0.))
    assert share.tolist() == pytest.approx([.4, .2, .4, 0., 0.]) and equal is False
    # the size of the readings is not kept: the same readings ten times smaller weigh the same
    assert ST.shares((.1, .05, .1, 0., 0.))[0].tolist() == pytest.approx([.4, .2, .4, 0., 0.])
    share, equal = ST.shares((0., 0., 0., 0., 0.))
    assert share.tolist() == [.2] * 5 and equal is True
    out = run([QA, QP])
    assert out['query_tag_equal_shares'] == [False, True]
    assert ST.summary(out, out['order'])['query_tags_with_equal_shares'] == 1


# --- the edge values -------------------------------------------------------------

def test_the_layer_reads_the_eligible_edges_and_puts_five_values_in_one_unit():
    lay = layer()
    assert lay.edges.tolist() == [1, 2, 3, 4, 5, 6, 7]          # the product-name edge is out
    assert lay.edge_tag.tolist() == EDGE_TAG[1:].tolist()
    assert lay.edge_chunk.tolist() == EDGE_CHUNK[1:].tolist()
    # topic over the seven eligible edges: median .30, the deviations' median .10
    assert lay.topic_bulk == pytest.approx(.30) and lay.topic_spread == pytest.approx(UNIT)
    assert lay.values[:, 0].tolist() == pytest.approx(((TOPIC[1:] - .30) / UNIT).tolist())
    # temporal 3.9, 4.0, 0, 3.2, 1, 2, 5 holds the ranks 5, 6, 1, 4, 2, 3, 7 over E; the
    # product-name edge's 9 takes no rank
    assert lay.values[:, 1].tolist() == pytest.approx(
        [INV((r - .5) / 7) for r in (5, 6, 1, 4, 2, 3, 7)])
    for j in range(len(R4.ADJUST_FACETS)):
        assert lay.values[:, 1 + j].tolist() == ST.normal_scores(SCORES[1:, j]).tolist()
    # activity 0, 0, 0, 0, 2, 1, 3: four edges share the rank 2.5
    assert lay.values[:4, 3].tolist() == pytest.approx([INV(2. / 7)] * 4)
    assert lay.source['eligible_edges'] == 7 and lay.source['eligible_graph_tags'] == 5
    assert lay.source['chunks'] == 6 and lay.source['chunks_with_an_eligible_edge'] == 5
    assert lay.source['nodes'] == {'product': 2, 'channel': 2, 'file': 3}
    assert lay.source['memberships'] == {'product': 6, 'channel': 3, 'file': 6}
    assert lay.source['value_columns'] == list(R4.ALL_FACETS)
    assert not lay.values.flags.writeable and not lay.eligible.flags.writeable


def test_only_the_order_of_a_facet_column_is_read():
    stretched = SCORES.copy()
    stretched[:, 0] = np.exp(SCORES[:, 0])
    stretched[:, 1] = SCORES[:, 1] * 100. - 3.
    assert layer(scores=stretched).values.tolist() == layer().values.tolist()


def test_a_chunk_counts_once_under_a_node():
    twice = layer(channels=((0, 0), (0, 0), (1, 0), (4, 1)))
    assert twice.source['memberships']['channel'] == 3
    for mine, plain in zip(twice.groups['channel'], layer().groups['channel']):
        assert mine.tolist() == plain.tolist()
    assert run([QA], lay=twice)['strength'].tolist() == run([QA])['strength'].tolist()


# --- the tag route ---------------------------------------------------------------

def test_the_weight_adds_the_five_values_by_the_query_tags_shares():
    out = run([QA])
    # (a,c0): fit (.8 - .2) / spread; shares .4 topic, .2 temporal, .4 why on the standing of
    # topic .40 and the normal scores of rank 5 (temporal 3.9) and rank 3 (why 1.0) of seven
    fit = (.8 - .2) / UNIT
    weight = .4 * (.40 - .30) / UNIT + .2 * INV(4.5 / 7) + .4 * INV(2.5 / 7)
    assert out['route'][0, 0] == pytest.approx(fit + weight)
    # a reading of zero on every facet weighs the five equally
    equal = run([(QA[0], (0., 0., 0., 0., 0.))])
    lay = layer()
    assert equal['route'][0, 0] == pytest.approx(fit + lay.values[0].mean())
    # the topic reading is read: without it the weight is the temporal and why scores alone
    no_topic = run([(QA[0], (0., .5, 1., 0., 0.))])
    assert no_topic['route'][0, 0] == pytest.approx(
        fit + INV(4.5 / 7) / 3. + 2. * INV(2.5 / 7) / 3.)


def test_a_chunk_takes_its_best_edge_not_the_sum_of_its_edges():
    lay = layer()
    out = run([QA], lay=lay)
    value = edge_values_by_hand(lay, *QA)
    # c1 hangs on (a,c1) and (b,c1): it stands where the better of the two stands
    assert out['route'][0, 1] == pytest.approx(max(value[1], value[2]))
    assert out['route'][0, 1] != pytest.approx(value[1] + value[2])
    assert out['best_edge'][1] == 2                       # (a,c1), in the arm's edge order
    assert out['route'][0, 4] == pytest.approx(max(value[4], value[5]))
    # c3 has no eligible edge: no s, no winning edge, no tag strength
    assert np.isnan(out['route'][0, 3]) and out['best_edge'][3] == -1
    assert out['best_query_tag'][3] == -1 and out['tags'][3] == 0.
    assert out['reached'].tolist() == [True, True, True, False, True, True]
    # a second, weaker edge on a chunk moves nothing
    best, edge = ST.best_edges(np.array([3., 1., 2.]), np.array([0, 0, 1]), 3)
    assert best[:2].tolist() == [3., 2.] and np.isnan(best[2]) and edge.tolist() == [0, 2, -1]
    assert ST.best_edges(np.array([3., 2.]), np.array([0, 1]), 3)[0][:2].tolist() == [3., 2.]
    # an exact tie goes to the earlier edge
    assert ST.best_edges(np.array([1., 1.]), np.array([0, 0]), 1)[1].tolist() == [0]


# --- the query tags --------------------------------------------------------------

def test_centrality_is_relative_to_the_questions_largest_and_never_negative():
    assert ST.centrality([.5, .2, -.1]).tolist() == pytest.approx([1., .4, 0.])
    assert ST.centrality([.05]).tolist() == [1.]
    out = run([QA, QP], [.5, .2])
    assert out['query_tag_centrality'] == pytest.approx([1., .4])
    assert out['query_tag_description_cosine'] == [.5, .2]


def test_a_peripheral_query_tag_cannot_lift_a_chunk_above_a_central_tags_positive_one():
    # c5 hangs on b alone: below its bulk under QA, high under QP
    peripheral = run([QA, QP], [.5, .05])
    route = peripheral['route']
    assert route[0, 5] < 0. < route[0, 0] < route[1, 5]
    assert peripheral['tags'][0] == pytest.approx(route[0, 0])
    assert peripheral['tags'][5] == pytest.approx(.1 * route[1, 5])
    assert peripheral['tags'][5] < peripheral['tags'][0]
    assert peripheral['best_query_tag'].tolist() == [0, 0, 0, -1, 0, 1]
    assert peripheral['best_edge'][5] == 7
    # the same two query tags equally central: c5 stands on QP's s, above c0
    level = run([QA, QP], [.5, .5])
    assert level['tags'][5] == pytest.approx(route[1, 5]) and level['tags'][5] > level['tags'][0]
    # a negative cosine to the description counts as none
    assert run([QA, QP], [.5, -.3])['tags'][5] == 0.


def test_the_tag_strength_takes_the_positive_part_and_the_best_query_tag():
    alone = run([QA])
    # c5 is below the background under QA: its tag strength is 0, never negative
    assert alone['route'][0, 5] < 0. and alone['tags'][5] == 0.
    assert (alone['tags'] >= 0.).all()
    # nothing positive under any query tag: the earlier query tag is recorded
    assert run([QA, QA])['best_query_tag'][5] == 0
    # the same query tag twice adds nothing
    twice = run([QA, QA])
    assert twice['tags'].tolist() == alone['tags'].tolist()
    assert twice['strength'].tolist() == alone['strength'].tolist()
    # a second query tag lifts only the chunks it reaches better
    both = run([QA, QP], [.5, .5])
    assert both['tags'][:3].tolist() == pytest.approx(alone['tags'][:3].tolist())
    assert (both['tags'] >= alone['tags']).all()


# --- the description side --------------------------------------------------------

def test_the_description_side_is_the_better_of_the_description_and_the_question():
    out = run([QA])
    # description: median .275, deviations' median .1; question: median .35, .125
    d = (DD - .275) / UNIT
    q = (DQ - .35) / (1.4826 * .125)
    assert out['description'].tolist() == pytest.approx(d.tolist())
    assert out['question'].tolist() == pytest.approx(q.tolist())
    assert out['description_side'].tolist() == pytest.approx(np.maximum(d, q).tolist())
    assert out['took_question'].tolist() == [True, False, False, False, False, True]
    assert out['base'].tolist() == pytest.approx((out['tags'] + np.maximum(d, q)).tolist())
    assert out['text_bulk'] == pytest.approx({'description': .275, 'question': .35})
    # the two are not added: the same row for both is that row once
    same = run([QA], dq=DD)
    assert same['description_side'].tolist() == same['description'].tolist()
    assert not same['took_question'].any()
    # c3, with no eligible edge, stands on the description side alone
    assert out['base'][3] == pytest.approx(d[3])


# --- the structure ---------------------------------------------------------------

def test_the_boost_is_the_other_chunks_mean_above_the_mean_of_all():
    strength = np.array([5., 3., 1., 0., 2., 1.])        # mean 2
    boost = ST.leave_one_out_boost(strength, np.arange(6), np.array([0, 0, 0, 1, 1, 2]))
    # node 0 holds chunks 0, 1, 2: the others' means are 2, 3, 4; node 1 holds 3 and 4: the
    # other is 2 and 0; chunk 5 is alone under node 2
    assert boost.tolist() == pytest.approx([0., 1., 2., 0., 0., 0.])
    assert (boost >= 0.).all()
    # a chunk under two nodes takes the larger boost; a chunk under no node takes none
    several = ST.leave_one_out_boost(np.array([0., 5., 9., 0.]), np.array([0, 1, 0, 2]),
                                     np.array([0, 0, 1, 1]))
    assert several.tolist() == pytest.approx([5.5, 0., 0., 0.])
    assert ST.leave_one_out_boost(strength, np.zeros(0), np.zeros(0)).tolist() == [0.] * 6


def test_the_structure_strengthens_and_never_lowers_or_removes():
    out = run([QA])
    base, mean = out['base'], out['base'].mean()

    def lift(*others):
        return max(0., float(np.mean([base[i] for i in others])) - mean)

    assert out['boosts']['product'].tolist() == pytest.approx(
        [lift(1, 2), lift(0, 2), lift(0, 1), lift(4, 5), lift(3, 5), lift(3, 4)])
    # c0 and c1 share a channel; c4 is alone on its own
    assert out['boosts']['channel'].tolist() == pytest.approx([lift(1), lift(0), 0., 0., 0., 0.])
    assert out['boosts']['file'].tolist() == pytest.approx(
        [lift(1), lift(0), lift(3), lift(2), lift(5), lift(4)])
    assert out['boosts']['channel'][4] == 0.
    total = sum(out['boosts'][kind] for kind in ST.STRUCTURE_TYPES)
    assert out['strength'].tolist() == pytest.approx((base + total).tolist())
    assert (out['strength'] >= base).all()
    assert all((out['boosts'][kind] >= 0.).all() for kind in ST.STRUCTURE_TYPES)
    assert sorted(out['order']) == list(range(len(CHUNKS)))
    # no structure at all: the strength is the base
    none = np.full(len(CHUNKS), -1)
    bare = run([QA], lay=layer(product=none, channels=(), file=none))
    assert bare['strength'].tolist() == bare['base'].tolist() == base.tolist()
    assert sorted(bare['order']) == list(range(len(CHUNKS)))


# --- the levels and the order ----------------------------------------------------

def test_the_level_step_is_the_embedder_noise_in_spreads():
    assert ST.level_step([.1, .2, .4]) == pytest.approx(V.BANDS['noise'] / .2)
    assert ST.level_step([.1, .3]) == pytest.approx(.002 / .2)
    out = run([QA, QP])
    assert out['step'] == pytest.approx(.002 / UNIT)
    expected = np.floor((out['strength'].max() - out['strength']) / out['step'])
    assert out['level'].tolist() == expected.tolist()
    assert out['level'][out['order'][0]] == 0
    assert (np.diff(out['level'][out['order']]) >= 0).all()


def test_inside_a_level_the_facets_sort_then_the_chunk_id():
    ids = ('k3', 'k1', 'k2', 'k0')
    every = np.ones(4, dtype=bool)
    slots = np.array([[9., 9., 9., 9.],      # a level deeper: last whatever its facets
                      [.5, .1, 0., 0.],
                      [.5, .7, 0., 0.],      # level with k1 on slot 1, ahead on slot 2
                      [.2, 9., 9., 9.]])
    assert ST.level_order(ids, np.array([1, 0, 0, 0]), every, slots) == [2, 1, 3, 0]
    # equal slots: the chunk id decides
    flat = np.zeros((4, 4))
    assert ST.level_order(ids, np.zeros(4), every, flat) == [3, 1, 2, 0]
    # inside a level a chunk with no winning edge follows those that have one
    assert ST.level_order(ids, np.zeros(4), np.array([True, True, True, False]), flat) == [
        1, 2, 0, 3]
    # and a better level still comes first
    assert ST.level_order(ids, np.array([1, 1, 1, 0]), np.array([True, True, True, False]),
                          flat) == [3, 1, 2, 0]


def test_near_equal_chunks_sort_by_the_winning_query_tags_facet_order():
    # x hangs on t0 and y on t1, equally close and equal on topic; x is high on temporal and low
    # on why, y the reverse; y stands a little higher on the description.
    ids = tuple(f'k{i}' for i in range(7))
    none = np.full(7, -1)
    lay = ST.build_layer(
        np.arange(7), np.arange(7), np.array([.30, .30, .10, .20, .30, .40, .50]),
        np.array([[5., 1., 0., 0.], [1., 5., 0., 0.], [3., 3., 0., 0.], [2., 2., 0., 0.],
                  [4., 4., 0., 0.], [0., 0., 0., 0.], [6., 6., 0., 0.]]),
        np.ones(7, dtype=bool), none, np.zeros(8, dtype=np.int64), np.zeros(0), none)
    dd = np.array([.30, .303, .10, .12, .14, .16, .18])
    dq = np.array([.10, .10, .30, .12, .14, .16, .18])
    narrow = np.array([.50, .50, .10, .11, .12, .13, .14])     # spread .0297: a wide step
    wide = np.array([.50, .50, .10, .20, .30, .40, .45])       # spread .148: a narrow step
    temporal_first, why_first = (1., .002, .001, 0., 0.), (1., .001, .002, 0., 0.)

    out = ST.strength_order(ids, lay, [(narrow, temporal_first)], [.5], dd, dq)
    assert out['strength'][1] > out['strength'][0]
    assert out['strength'][1] - out['strength'][0] < out['step']
    assert out['level'][:2].tolist() == [0, 0]
    assert out['facet_orders'] == [('temporal', 'why', 'activity', 'concreteness')]
    assert out['slots'][0].tolist() == pytest.approx([INV(5.5 / 7), INV(1.5 / 7), 0., 0.])
    assert out['order'][:2] == [0, 1]             # x leads on temporal, the first facet

    out = ST.strength_order(ids, lay, [(narrow, why_first)], [.5], dd, dq)
    assert out['level'][:2].tolist() == [0, 0]
    assert out['facet_orders'] == [('why', 'temporal', 'activity', 'concreteness')]
    assert out['slots'][0].tolist() == pytest.approx([INV(1.5 / 7), INV(5.5 / 7), 0., 0.])
    assert out['order'][:2] == [1, 0]             # y leads on why

    # more than a step apart, the strength decides whatever the facets say
    for readings in (temporal_first, why_first):
        out = ST.strength_order(ids, lay, [(wide, readings)], [.5], dd, dq)
        assert out['level'][1] == 0 < out['level'][0]
        assert out['order'][:2] == [1, 0]


# --- the whole -------------------------------------------------------------------

def test_the_order_is_deterministic_and_reads_its_inputs_only():
    lay = layer()
    before = lay.values.copy()
    first = run([QA, QP], [.5, .2], lay=lay)
    again = run([QA, QP], [.5, .2], lay=lay)
    rebuilt = run([QA, QP], [.5, .2])
    for other in (again, rebuilt):
        assert other['order'] == first['order']
        for name in ('strength', 'base', 'tags', 'level', 'best_edge', 'best_query_tag',
                     'slots'):
            assert other[name].tolist() == first[name].tolist()
        assert np.array_equal(other['route'], first['route'], equal_nan=True)
    assert lay.values.tolist() == before.tolist()
    assert sorted(first['order']) == list(range(len(CHUNKS)))
    with pytest.raises(ValueError):
        lay.values[0, 0] = 1.


def _leaves(value):
    if isinstance(value, dict):
        for inner in value.values():
            yield from _leaves(inner)
    elif isinstance(value, (list, tuple)):
        for inner in value:
            yield from _leaves(inner)
    else:
        yield value


def test_the_summary_adds_up_and_holds_numbers_only():
    out = run([QA, QP], [.5, .2])
    delivered = out['order'][:4]
    d = ST.summary(out, delivered)
    assert ST.TERMS == ('tags', 'description', 'product', 'channel', 'file')
    assert set(d['delivered_term_sums']) == set(d['delivered_term_shares']) == set(ST.TERMS)
    assert sum(d['delivered_term_sums'].values()) == pytest.approx(d['delivered_strength_total'])
    assert d['delivered_strength_total'] == pytest.approx(out['strength'][delivered].sum())
    assert sum(d['delivered_term_shares'].values()) == pytest.approx(1.)
    assert d['delivered_term_sums']['tags'] == pytest.approx(out['tags'][delivered].sum())
    assert d['delivered_term_sums']['channel'] == pytest.approx(
        out['boosts']['channel'][delivered].sum())
    terms = {'tags': out['tags'], 'description': out['description_side'], **out['boosts']}
    expected = dict.fromkeys(ST.TERMS + ('none',), 0)
    for a, b in zip(delivered, delivered[1:]):
        expected[max(ST.TERMS, key=lambda name: abs(terms[name][a] - terms[name][b]))] += 1
    assert d['adjacent_delivered_pairs'] == 3
    assert d['adjacent_delivered_pairs_largest_difference_in'] == expected
    assert d['delivered_rows_taking_the_question'] == int(out['took_question'][delivered].sum())
    assert (d['delivered_rows_taking_the_description']
            + d['delivered_rows_taking_the_question']) == 4
    assert d['largest_boost'] == {kind: pytest.approx(out['boosts'][kind].max())
                                  for kind in ST.STRUCTURE_TYPES}
    assert d['chunks_with_a_positive_boost'] == {
        kind: int((out['boosts'][kind] > 0).sum()) for kind in ST.STRUCTURE_TYPES}
    levels = out['level'][delivered]
    assert d['levels_among_delivered_rows'] == len(set(levels.tolist()))
    assert d['adjacent_delivered_pairs_in_one_level'] == int((levels[1:] == levels[:-1]).sum())
    assert d['chunks'] == 6 and d['chunks_with_an_eligible_edge'] == 5
    assert d['eligible_graph_tags'] == 5 and d['eligible_edges'] == 7
    assert d['query_tags'] == 2 and d['query_tags_with_equal_shares'] == 1
    assert d['query_tag_centrality'] == pytest.approx([1., .4])
    assert d['query_tag_bulk'] == pytest.approx([.2, .2])
    assert d['query_tag_spread'] == pytest.approx([UNIT, UNIT])
    assert d['level_step'] == pytest.approx(.002 / UNIT)
    assert all(type(v) in (int, float) or v is None for v in _leaves(d))
    # the same row twice in a pair differs in no term
    assert ST.summary(out, [delivered[0], delivered[0]])[
        'adjacent_delivered_pairs_largest_difference_in']['none'] == 1
    empty = ST.summary(out, [])
    assert empty['delivered_strength_total'] == 0.
    assert set(empty['delivered_term_shares'].values()) == {None}
    assert empty['adjacent_delivered_pairs'] == 0 and empty['levels_among_delivered_rows'] == 0


# --- every raise -----------------------------------------------------------------

def test_the_arithmetic_refuses_what_it_cannot_read():
    for bad in ([], [1., np.nan], [[1., 2.]], [1., 1., 1., 2.]):      # the last: a zero spread
        with pytest.raises(ValueError):
            ST.standing(bad)
    for bad in ([1., np.inf], [[1., 2.]]):
        with pytest.raises(ValueError):
            ST.normal_scores(bad)
    for bad in ((1., 1., 1., 1.), (1., 1., 1., 1., -1.), (1., 1., 1., 1., np.nan)):
        with pytest.raises(ValueError):
            ST.shares(bad)
    with pytest.raises(ValueError):
        ST.best_edges(np.array([1., 2.]), np.array([0]), 2)
    with pytest.raises(ValueError):
        ST.best_edges(np.array([1., np.nan]), np.array([0, 1]), 2)
    for bad in ([], [.1, np.nan], [0., -.2]):                         # the last: none positive
        with pytest.raises(ValueError):
            ST.centrality(bad)
    for strength, chunk, node in (([], [0], [0]), ([1., np.nan], [0], [0]), ([1., 2.], [0, 1], [0]),
                                  ([1., 2.], [0, 2], [0, 0]), ([1., 2.], [0, 1], [0, -1])):
        with pytest.raises(ValueError):
            ST.leave_one_out_boost(np.array(strength), np.array(chunk), np.array(node))
    for bad in ([], [.1, 0.], [.1, -.2]):
        with pytest.raises(ValueError):
            ST.level_step(bad)
    with pytest.raises(ValueError):
        ST.level_order(('a', 'b'), np.zeros(2), np.ones(2, dtype=bool), np.zeros((2, 3)))
    with pytest.raises(ValueError):
        ST.level_order(('a', 'b'), np.zeros(3), np.ones(2, dtype=bool), np.zeros((2, 4)))


def test_the_layer_refuses_what_it_cannot_read():
    ptr, members = _csr(list(CHANNEL_PAIRS), len(CHUNKS))
    good = dict(edge_tag=EDGE_TAG, edge_chunk=EDGE_CHUNK, edge_topic=TOPIC, facet_scores=SCORES,
                eligible=ELIGIBLE, product=PRODUCT, channel_ptr=ptr, channels=members, file=FILE)
    ST.build_layer(**good)
    nan_topic = TOPIC.copy()
    nan_topic[2] = np.nan
    flat_topic = np.full(TOPIC.size, .3)
    for change in (dict(edge_topic=TOPIC[:-1]),                       # one topic short
                   dict(facet_scores=SCORES[:, :3]),                  # three facet columns
                   dict(edge_topic=nan_topic),
                   dict(edge_tag=EDGE_TAG + 5),                       # a tag out of range
                   dict(edge_chunk=EDGE_CHUNK + 5),                   # a chunk out of range
                   dict(file=FILE[:-1]),
                   dict(channel_ptr=ptr[:-1]),
                   dict(channels=members[:-1]),
                   dict(channels=np.array([0, 0, -1])),               # a channel out of range
                   dict(eligible=np.zeros(len(TAGS), dtype=bool)),    # no eligible edge
                   dict(edge_topic=flat_topic)):                      # a zero topic spread
        with pytest.raises(ValueError):
            ST.build_layer(**{**good, **change})


def test_the_order_refuses_what_it_cannot_read():
    lay = layer()
    with pytest.raises(ValueError):
        ST.strength_order(CHUNKS[:-1], lay, [QA], [.5], DD[:-1], DQ[:-1])     # other chunks
    with pytest.raises(ValueError):
        run([])                                                               # no query tag
    with pytest.raises(ValueError):
        run([QA], [.5, .2])                                                   # two cosines, one tag
    with pytest.raises(ValueError):
        run([QA, QP], [0., -.1])                                              # no positive centrality
    with pytest.raises(ValueError):
        run([(QA[0][:-1], QA[1])])                                            # a short fit row
    with pytest.raises(ValueError):
        run([(QA[0], (1., 1., 1., 1., -1.))])                                 # a negative reading
    with pytest.raises(ValueError):
        run([(np.array([.9, .2, .2, .2, .2, .7]), QA[1])])                    # a zero fit spread
    with pytest.raises(ValueError):
        run([QA], dd=np.full(len(CHUNKS), .3))                                # a zero description spread
    with pytest.raises(ValueError):
        run([QA], dq=np.array([.1, .2, np.nan, .4, .5, .6]))


# --- the arm ---------------------------------------------------------------------

def structure():
    ptr, members = _csr(list(CHANNEL_PAIRS), len(CHUNKS))
    empty = np.zeros(len(CHUNKS) + 1, dtype=np.int64)
    return MK.build_structure({'ptr': empty, 'members': np.zeros(0)},
                              {'chunk_group_ptr': ptr, 'chunk_groups': members,
                               'product': PRODUCT}, {'toy': True})


def chunk_rows():
    return tuple({'chunkId': c, 'relpath': f'products/f{FILE[i]}.json'}
                 for i, c in enumerate(CHUNKS))


def prepared(**changes):
    fields = dict(
        chunk_rows=chunk_rows(), chunk_ids=CHUNKS, chunk_kinds=('pr',) * len(CHUNKS),
        graph_tags=TAGS, product_tags=('ProductX',), nonscope_eligible=ELIGIBLE,
        tag_vectors=np.eye(len(TAGS)), chunk_vectors=np.eye(len(CHUNKS)), edge_tag=EDGE_TAG,
        edge_chunk=EDGE_CHUNK, edge_topic=TOPIC, edge_pos=np.zeros((len(EDGE_TAG), 5)),
        landings=(), driver=None, cache_dir=None, provenance={},
        build_stats=BuildStats(0., ModelUsage(), []), casefold_eligible=ELIGIBLE,
        multikey_layer=MK.build_layer(SCORES, (1., 1., 1., 1.), {}, {}), structure=structure(),
        strength_layer=V._strength_layer(chunk_rows(), EDGE_TAG, EDGE_CHUNK, TOPIC, SCORES,
                                         ELIGIBLE, structure()))
    return V.Prepared(**{**fields, **changes})


def toy_query():
    raw = {'description': 'Sought content',
           'tags': [{'t': 'described', 'facets': dict(zip(Q.FACETS, QA[1]))}],
           'query_tags': [{'t': 'asked', 'facets': dict(zip(Q.FACETS, QP[1]))}]}
    return Q.parse('placeholder question', raw)


FITS = {'described': QA[0], 'asked': QP[0]}
CENTRAL = {'described': .5, 'asked': .2}


def arm(monkeypatch, env=None, kept=3, prep=None):
    seen = {'tag_calls': [], 'text_calls': []}

    def fake_tag_cosines(text, tags, prepared_):
        seen['tag_calls'].append((text, tuple(tags)))
        return ({'query_tag_cosines': np.array([FITS[t] for t in tags]).reshape(len(tags),
                                                                               len(TAGS)),
                 'query_description_cosines': DD,
                 'query_tag_description_cosines': np.array([CENTRAL[t] for t in tags])},
                ModelUsage(), {'vector_sha256': 'x'})

    def fake_cosines(text, tags, prepared_):
        seen['text_calls'].append((text, tuple(tags)))
        return ({'query_tag_cosines': np.array([FITS[t] for t in tags]).reshape(len(tags),
                                                                               len(TAGS)),
                 'query_description_cosines': DD if text == 'Sought content' else DQ},
                ModelUsage(), {'vector_sha256': 'y'})

    def fake_budget(rows, budget, doc_cache):
        seen['rows'] = [r['chunkId'] for r in rows]
        return (['x'] * kept, [[]] * kept, [], {'budget': budget, 'chars': budget, 'kept': kept,
                                                'boundary': None, 'exhausted': False})

    def refuse(*args, **kwargs):
        raise AssertionError('a model call in a strength test')

    def no_landing(*args, **kwargs):
        raise AssertionError('the strength sort reads no landing')

    monkeypatch.setattr(chat, 'post', refuse)
    monkeypatch.setattr(V, '_interpret', lambda t, prepared_: (toy_query(), ModelUsage(), []))
    monkeypatch.setattr(V, '_query_cosines_and_centrality', fake_tag_cosines)
    monkeypatch.setattr(V, '_query_cosines', fake_cosines)
    monkeypatch.setattr(V, '_budget_contexts', fake_budget)
    monkeypatch.setattr(V, '_area_rank', no_landing)
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)
    seen['out'] = V.answer_one_question(('q', 'placeholder question'), prep or prepared(), None,
                                        50, 100)
    return seen


def test_the_default_sort_is_strength(monkeypatch):
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    assert V.knobs()['sort'] == 'strength'
    assert V.SORT_MODES == ('strength', 'multikey', 'adjust_lower', 'multirank', 'concept',
                            'chain', 'sum')
    assert V.RETRIEVAL_FLAGS['defaults']['HERB_V4_SORT'] == 'strength'
    assert 'strength' in V.RETRIEVAL_FLAGS and set(V.READ_BY) == set(V.SORT_MODES)
    record = V.knob_record(V.knobs())
    assert record['read_by_active_sort'] == ['HERB_V4_SORT', 'HERB_V4_OFFLINE']
    assert record['product_name_tags_excluded_by_the_sort'] is True
    # every older mode is still chosen by its name
    for sort in V.SORT_MODES:
        monkeypatch.setenv('HERB_V4_SORT', sort)
        assert V.knobs()['sort'] == sort


def test_the_arm_sorts_by_strength_and_hands_the_whole_order_to_the_cut(monkeypatch):
    seen = arm(monkeypatch)
    out = seen['out']
    assert out.meta['policy']['knobs_recorded']['active']['HERB_V4_SORT'] == 'strength'
    direct = ST.strength_order(CHUNKS, layer(), [QA, QP], [.5, .2], DD, DQ)
    assert seen['rows'] == [CHUNKS[i] for i in direct['order']]
    assert sorted(seen['rows']) == sorted(CHUNKS)             # nothing is cut before the budget
    top = direct['order'][:3]
    ranking = out.meta['ranking']
    assert ranking['ordered_chunk_ids'] == seen['rows']
    assert ranking['delivered_chunk_ids'] == [CHUNKS[i] for i in top]
    assert ranking['delivered_strength'] == pytest.approx(direct['strength'][top].tolist())
    assert ranking['delivered_levels'] == direct['level'][top].tolist()
    assert ranking['delivered_query_tags'] == direct['best_query_tag'][top].tolist()
    assert set(ranking['delivered_terms']) == set(ST.TERMS)
    assert [sum(ranking['delivered_terms'][name][i] for name in ST.TERMS)
            for i in range(3)] == pytest.approx(ranking['delivered_strength'])
    # both tag lists are query tags, each embedded beside the description; the question alone
    assert seen['tag_calls'] == [('Sought content', ('described',)),
                                 ('Sought content', ('asked',))]
    assert seen['text_calls'] == [('placeholder question', ())]
    interp = out.meta['interpreter']
    assert interp['description_side_tags'] == 1 and interp['question_side_tags_read'] == 1
    assert interp['query_tags'] == 2
    assert out.meta['area'] == {'mode': 'not read by the strength sort'}
    assert out.meta['policy']['product_named_tags_excluded'] == 1
    assert out.meta['policy']['fit_equal_width'] is None and out.meta['policy']['flip_gap'] is None
    d = out.meta['diagnostics']
    assert d['credited_delivered_rows'] == 3 and d['product_named_tags_excluded_casefold'] == 1
    expected = ST.summary(direct, top)
    for name, value in expected.items():
        assert d[name] == (pytest.approx(value) if isinstance(value, float) else value)
    assert out.meta['returned'] == 3 and out.answer == ''
    # the row serialises as the harness writes it
    assert json.loads(json.dumps(asdict(out), ensure_ascii=False))['meta']['diagnostics'][
        'query_tags'] == 2


def test_the_arm_needs_the_prepared_strength_layer(monkeypatch):
    with pytest.raises(ValueError, match='strength needs the prepared strength layer'):
        arm(monkeypatch, prep=prepared(strength_layer=None))


def test_the_older_sorts_run_beside_strength(monkeypatch):
    seen = arm(monkeypatch, {'HERB_V4_SORT': 'concept'})
    out = seen['out']
    assert out.meta['policy']['knobs_recorded']['active']['HERB_V4_SORT'] == 'concept'
    # concept reads the description-side list only, through the plain cosines
    assert seen['tag_calls'] == []
    assert seen['text_calls'] == [('Sought content', ('described',)),
                                  ('placeholder question', ())]
    assert 'delivered_term_shares' not in out.meta['diagnostics']


def test_the_strength_layer_takes_the_file_from_the_relpath():
    rows = chunk_rows()
    built = V._strength_layer(rows, EDGE_TAG, EDGE_CHUNK, TOPIC, SCORES, ELIGIBLE, structure())
    plain = layer()
    assert built.values.tolist() == plain.values.tolist()
    assert built.edges.tolist() == plain.edges.tolist()
    for kind in ST.STRUCTURE_TYPES:
        for mine, theirs in zip(built.groups[kind], plain.groups[kind]):
            assert mine.tolist() == theirs.tolist()
    assert built.source['nodes'] == {'product': 2, 'channel': 2, 'file': 3}
    # the file is the path, whatever order the paths come in
    renamed = tuple({**row, 'relpath': f'z{9 - FILE[i]}.json'} for i, row in enumerate(rows))
    other = V._strength_layer(renamed, EDGE_TAG, EDGE_CHUNK, TOPIC, SCORES, ELIGIBLE,
                              structure())
    assert run([QA], lay=other)['strength'].tolist() == run([QA])['strength'].tolist()
    for bad in ({'chunkId': 'c0'}, {'chunkId': 'c0', 'relpath': ''},
                {'chunkId': 'c0', 'relpath': None}):
        with pytest.raises(ValueError, match='no file path'):
            V._strength_layer((bad,) + rows[1:], EDGE_TAG, EDGE_CHUNK, TOPIC, SCORES, ELIGIBLE,
                              structure())


def test_prepare_builds_the_strength_layer_and_records_its_source():
    source = inspect.getsource(V.prepare_over_corpus)
    assert '_strength_layer(' in source and 'multikey_layer.values, casefold_eligible' in source
    assert "ROOT / 'test/artefact/v4_strength.py'" in source
    assert "'strength_layer': {**strength_counts" in source
    assert 'corpus_words, strength_layer)' in source


def test_the_centrality_cosines_come_from_the_tags_own_embedding_call(monkeypatch):
    rng = np.random.default_rng(3)
    dim = 5

    def unit(matrix):
        return matrix / np.linalg.norm(matrix, axis=-1, keepdims=True)

    vectors = {name: unit(rng.normal(size=dim))
               for name in ('first tag', 'second tag', 'the description')}
    prep = prepared(tag_vectors=unit(rng.normal(size=(len(TAGS), dim))),
                    chunk_vectors=unit(rng.normal(size=(len(CHUNKS), dim))))
    calls = []

    def embedded(description, tags, axes):
        """`_query_cosines`' three products, on the toy vectors."""
        calls.append(axes)
        tag_vectors = np.array([vectors[t] for t in tags]).reshape(len(tags), dim)
        return ({'query_tag_cosines': tag_vectors @ axes.tag_vectors.T,
                 'query_chunk_cosines': tag_vectors @ axes.chunk_vectors.T,
                 'query_description_cosines': vectors[description] @ axes.chunk_vectors.T},
                ModelUsage(calls=1), {'vector_sha256': 'x'})

    monkeypatch.setattr(V, '_query_cosines', embedded)
    tags = ['first tag', 'second tag']
    matrices, used, recipe = V._query_cosines_and_centrality('the description', tags, prep)
    assert len(calls) == 1 and used.calls == 1 and recipe == {'vector_sha256': 'x'}
    assert calls[0].tag_vectors is prep.tag_vectors
    assert calls[0].chunk_vectors.tolist() == np.eye(dim).tolist()
    plain = embedded('the description', tags, prep)[0]
    assert matrices['query_tag_cosines'].tolist() == plain['query_tag_cosines'].tolist()
    assert matrices['query_description_cosines'].tolist() == pytest.approx(
        plain['query_description_cosines'].tolist())
    assert matrices['query_tag_description_cosines'].tolist() == pytest.approx(
        [float(vectors[t] @ vectors['the description']) for t in tags])
    alone = V._query_cosines_and_centrality('the description', [], prep)[0]
    assert alone['query_tag_description_cosines'].shape == (0,)
    assert alone['query_description_cosines'].shape == (len(CHUNKS),)
    monkeypatch.setattr(V, '_query_cosines', lambda description, tags, axes: (
        {'query_tag_cosines': np.zeros((len(tags), len(TAGS))),
         'query_chunk_cosines': np.zeros((len(tags), dim + 1)),
         'query_description_cosines': np.zeros(dim)}, ModelUsage(), {}))
    with pytest.raises(ValueError):
        V._query_cosines_and_centrality('the description', tags, prep)
