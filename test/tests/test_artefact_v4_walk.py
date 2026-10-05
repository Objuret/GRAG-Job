"""artefact_v4's walk sort: the chain of `v4_walk` on toy arrays, the arm run on it with no
model call, prepare on a faked graph, and one live test - the arm's order against the
walk-through's on the live graph - that runs only with HERB_LIVE_TESTS=1.

No question set, no gold, no chunk text.
"""
from dataclasses import asdict
from fractions import Fraction
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import socket
import time
from types import SimpleNamespace

import numpy as np
import pytest

from harness import chat
from harness.contract import BuildStats, ModelUsage
from arms import artefact_v4 as V
from artefact import query_content as Q
from artefact import v4_multikey as MK
from artefact import v4_walk as WK


# ------------------------------------------------------------------ M2, M3

def test_positions_are_average_ranks_over_the_row_count():
    column = np.array([[3.], [1.], [2.], [2.]])
    assert WK.positions(column)[:, 0].tolist() == [1., .25, .625, .625]


def test_positions_lie_in_0_1_and_average_to_n_plus_1_over_2n():
    rng = np.random.default_rng(1)
    values = rng.integers(0, 7, size=(50, 5)).astype(float)
    pos = WK.positions(values)
    assert (pos > 0).all() and (pos <= 1).all()
    assert np.allclose(pos.mean(axis=0), 51 / 100)
    assert WK.positions(np.arange(10.)[:, None]).max() == 1.


def test_positions_refuse_an_empty_or_non_finite_table():
    with pytest.raises(ValueError):
        WK.positions(np.zeros((0, 5)))
    with pytest.raises(ValueError):
        WK.positions(np.array([[np.nan]]))


def test_equal_shares_give_the_mean_of_the_five_positions():
    rng = np.random.default_rng(2)
    pos = WK.positions(rng.normal(size=(30, 5)))
    for readings in ((0., 0., 0., 0., 0.), (.7, .7, .7, .7, .7)):
        share, _ = WK.shares(readings)
        assert np.allclose(WK.relevance(pos, share), pos.mean(axis=1))


def test_relevance_is_the_share_weighted_position():
    pos = np.array([[.2, .4, .6, .8, 1.]])
    share, was_equal = WK.shares((1., 0., 1., 0., 0.))
    assert not was_equal
    assert WK.relevance(pos, share)[0] == pytest.approx(.5 * .2 + .5 * .6)
    with pytest.raises(ValueError):
        WK.relevance(pos, np.array([.5, .5, .5, 0., 0.]))


# ------------------------------------------------------------------ M4

def brute(w, edge_chunk, n_chunks):
    """v* by exact fractions, straight from the definition."""
    total = len(w)
    descending = sorted(w, reverse=True)
    out = []
    for c in range(n_chunks):
        mine = [w[i] for i in range(total) if edge_chunk[i] == c]
        if not mine:
            out.append(0.)
            continue
        v = max(mine)
        tail = Fraction(sum(x >= v for x in w), total)
        p = 1 - (1 - tail) ** len(mine)
        k = min(max(math.ceil(p * total), 1), total)
        out.append(descending[k - 1])
    return out


def test_one_edge_per_chunk_leaves_the_value_unchanged():
    # nine edges: the size at which ceil((1 - (1 - 1/9)) * 9) is 2 in floating point
    w = np.array([.9, .1, .5, .5, .3, .7, .2, .8, .4])
    got = WK.chance_corrected_best(w, np.arange(9), 9)
    assert got['v_star'].tolist() == w.tolist()
    assert got['v'].tolist() == w.tolist()
    assert got['k'].tolist() == got['count'].tolist()
    assert math.ceil((1 - (1 - 1 / 9) ** 1) * 9) == 2


def test_one_edge_per_chunk_at_the_size_of_the_graph():
    rng = np.random.default_rng(3)
    w = np.round(rng.random(57204), 3)
    got = WK.chance_corrected_best(w, np.arange(w.size), w.size)
    assert np.array_equal(got['v_star'], w)


def test_a_chunk_with_many_edges_is_lowered():
    # chunk 0 holds the best edge and two more; chunk 1 holds the second best alone
    w = np.array([1.0, .05, .04, .9, .8, .7, .6, .5, .4, .3])
    edge_chunk = np.array([0, 0, 0, 1, 2, 3, 4, 5, 6, 7])
    got = WK.chance_corrected_best(w, edge_chunk, 8)
    assert got['n_c'][0] == 3 and got['count'][0] == 1
    assert got['k'][0] == 3                      # ceil((1 - 0.9^3) * 10) = ceil(2.71)
    assert got['v_star'][0] == .8 < got['v'][0] == 1.0
    assert got['v_star'][1] == got['v'][1] == .9
    assert got['p'][0] == pytest.approx(1 - .9 ** 3)
    assert got['tail'][0] == pytest.approx(.1)


def test_the_corrected_value_never_exceeds_the_best_and_matches_the_definition():
    rng = np.random.default_rng(4)
    for _ in range(20):
        total, n_chunks = int(rng.integers(5, 60)), int(rng.integers(2, 12))
        w = np.round(rng.random(total), 1)       # one decimal: many ties
        edge_chunk = rng.integers(0, n_chunks, size=total)
        got = WK.chance_corrected_best(w, edge_chunk, n_chunks)
        assert got['v_star'].tolist() == brute(w.tolist(), edge_chunk.tolist(), n_chunks)
        held = got['n_c'] > 0
        assert (got['v_star'][held] <= got['v'][held]).all()
        assert (got['k'][held] >= got['count'][held]).all()
        assert (got['k'][held] <= total).all()


def test_more_edges_never_raise_the_corrected_value():
    w = np.array([.9, .8, .7, .6, .5, .4, .3, .2, .1, .05, .04, .03])
    values = []
    for extra in range(0, 4):                    # chunk 0: the .8 edge and `extra` low ones
        edge_chunk = np.array([1, 0, 2, 3, 4, 5, 6, 7, 8] + [0] * extra + [9] * (3 - extra))
        values.append(WK.chance_corrected_best(w, edge_chunk, 10)['v_star'][0])
    assert values == sorted(values, reverse=True) and values[0] == .8 and values[-1] < .8


def test_a_chunk_without_an_edge_takes_zero_and_all_zero_weights_stay_zero():
    got = WK.chance_corrected_best(np.array([.5, .2]), np.array([0, 0]), 3)
    assert got['v_star'].tolist()[1:] == [0., 0.] and got['edge'].tolist()[1:] == [-1, -1]
    assert np.isnan(got['v'][1]) and got['k'][1] == 0
    zero = WK.chance_corrected_best(np.zeros(6), np.array([0, 0, 1, 1, 1, 2]), 3)
    assert zero['v_star'].tolist() == [0., 0., 0.] and zero['p'].tolist() == [1., 1., 1.]


def test_a_tie_at_the_best_counts_every_tied_edge():
    w = np.array([.9, .9, .9, .1])
    got = WK.chance_corrected_best(w, np.array([0, 1, 2, 3]), 4)
    assert got['count'].tolist() == [3, 3, 3, 4]
    assert got['v_star'].tolist() == w.tolist()


def test_tag_value_takes_the_largest_term_or_the_sum():
    values = np.array([[1., 0., 2.], [3., 0., 1.]])
    central = np.array([1., .5])
    total, winner, terms = WK.tag_value(values, central)
    assert total.tolist() == [1.5, 0., 2.] and winner.tolist() == [1, 0, 0]
    assert terms.tolist() == [[1., 0., 2.], [1.5, 0., .5]]
    summed, winner, _ = WK.tag_value(values, central, 'sum')
    assert summed.tolist() == [2.5, 0., 2.5] and winner.tolist() == [1, 0, 0]
    with pytest.raises(ValueError):
        WK.tag_value(values, central, 'mean')


def test_reaching_counts_the_fits_whose_product_reaches_the_target():
    rng = np.random.default_rng(11)
    for _ in range(30):
        fits = np.round(rng.random(int(rng.integers(1, 40))), 2)
        factor = rng.uniform(.05, 2., size=25)
        target = np.round(rng.random(25), 2) * rng.choice([0., .5, 1., 2.], size=25)
        got = WK.reaching(fits, factor, target)
        assert got.tolist() == [sum(f * a >= t for f in fits.tolist())
                                for a, t in zip(factor.tolist(), target.tolist())]
    # a fit counts for the product it gives itself, whatever the division rounds to
    fits = rng.random(2000)
    factor = rng.uniform(.05, 2., size=2000)
    own = WK.reaching(fits, factor, fits * factor)
    assert own.tolist() == [int((fits >= f).sum()) for f in fits.tolist()]
    with pytest.raises(ValueError):
        WK.reaching(fits, np.zeros(3), np.ones(3))


def brute_per_edge(fit, factor, fits, edge_chunk, n_chunks):
    """The per-edge v* by exact fractions, straight from the definition."""
    size = len(fits)
    descending = sorted(fits, reverse=True)
    out = []
    for c in range(n_chunks):
        mine = [i for i in range(len(fit)) if edge_chunk[i] == c]
        if not mine:
            out.append(0.)
            continue
        v = max(fit[i] * factor[i] for i in mine)
        keep = Fraction(1)
        for i in mine:
            keep *= 1 - Fraction(sum(f * factor[i] >= v for f in fits), size)
        k = min(max(math.ceil((1 - keep) * size), 1), size)
        out.append(descending[k - 1])
    return out


def test_the_per_edge_form_at_one_edge_per_chunk_returns_the_fit():
    rng = np.random.default_rng(12)
    fit = np.concatenate([np.zeros(50), np.round(rng.random(150), 2), rng.random(800) * 12])
    factor = rng.uniform(.05, 2., size=fit.size)
    got = WK.per_edge_corrected_best(fit, factor, fit, np.arange(fit.size), fit.size)
    assert np.array_equal(got['v_star'], fit)             # the fit, not fit x factor
    assert np.array_equal(got['v'], fit * factor)
    assert got['k'].tolist() == [int((fit >= f).sum()) for f in fit.tolist()]
    # the population of the graph: 16,609 fits, one edge per chunk on a part of them
    fits = np.clip(rng.normal(size=16609), 0., None)
    pick = rng.choice(16609, size=3000, replace=False)
    factor = rng.uniform(.05, 2., size=3000)
    got = WK.per_edge_corrected_best(fits[pick], factor, fits, np.arange(3000), 3000)
    assert np.array_equal(got['v_star'], fits[pick])


def test_the_per_edge_form_matches_the_definition():
    rng = np.random.default_rng(13)
    for _ in range(20):
        size, total, n_chunks = (int(rng.integers(5, 40)), int(rng.integers(5, 60)),
                                 int(rng.integers(2, 12)))
        fits = np.round(rng.random(size), 1)               # one decimal: many ties
        fit = rng.choice(fits, size=total)
        factor = np.round(rng.uniform(.1, 2., size=total), 1)
        edge_chunk = rng.integers(0, n_chunks, size=total)
        got = WK.per_edge_corrected_best(fit, factor, fits, edge_chunk, n_chunks)
        assert got['v_star'].tolist() == brute_per_edge(fit.tolist(), factor.tolist(),
                                                        fits.tolist(), edge_chunk.tolist(),
                                                        n_chunks)
        held = got['n_c'] > 0
        assert (got['k'][held] >= 1).all() and (got['k'][held] <= size).all()
        assert ((got['p'][held] >= 0) & (got['p'][held] <= 1)).all()


def test_the_per_edge_form_reads_the_other_edges_factors():
    fits = np.array([0., 1., 2., 3., 4., 5., 6., 7., 8., 9.])
    # chunk 0: fit 8 at factor 1 (v = 8) and a second edge of fit 0
    def star(second_factor):
        return WK.per_edge_corrected_best(np.array([8., 0.]), np.array([1., second_factor]),
                                         fits, np.array([0, 0]), 1)['v_star'][0]
    alone = WK.per_edge_corrected_best(np.array([8.]), np.array([1.]), fits, np.array([0]), 1)
    assert alone['v_star'][0] == 8. and alone['k'][0] == 2
    assert star(.5) == 8.               # the second edge cannot reach 8 with any fit: 9 x .5
    assert star(1.) == 6.               # it reaches 8 with 2 of 10 fits: k = 10 - floor(64/10)
    assert star(2.) == 3.               # with 6 of 10: k = 10 - floor(8 x 4 / 10) = 7
    none = WK.per_edge_corrected_best(np.array([8.]), np.array([1.]), fits, np.array([0]), 2)
    assert none['v_star'].tolist() == [8., 0.] and none['edge'].tolist() == [0, -1]
    assert np.isnan(none['v'][1]) and none['k'][1] == 0


def test_chunk_values_are_the_four_ways():
    rng = np.random.default_rng(14)
    fits = np.clip(rng.normal(size=60), 0., None)
    tag = rng.integers(0, 60, size=200)
    edge_chunk = rng.integers(0, 30, size=200)
    factor = rng.uniform(.2, 1.8, size=200)
    got = WK.chunk_values(fits[tag], factor, fits, edge_chunk, 31)
    w = fits[tag] * factor
    assert np.array_equal(got['w'], w)
    for c in range(31):
        mine = w[edge_chunk == c]
        assert got['best'][c] == (mine.max() if mine.size else 0.)
        assert got['total'][c] == pytest.approx(mine.sum())
    assert np.array_equal(got['pooled']['v_star'],
                          WK.chance_corrected_best(w, edge_chunk, 31)['v_star'])
    assert np.array_equal(got['per_edge']['edge'], got['pooled']['edge'])
    assert got['best'][30] == 0. and got['per_edge']['v_star'][30] == 0.


# ------------------------------------------------------------------ M5

def test_text_side_is_the_larger_standing_and_is_not_clipped():
    d = np.array([.1, .2, .3, .4, .5])
    q = np.array([.5, .1, .3, .2, .4])
    got = WK.text_side(d, q)
    spread = 1.4826 * .1
    assert got['bulk'] == {'description': .3, 'question': .3}
    assert got['spread']['description'] == pytest.approx(spread)
    assert np.allclose(got['D'], (d - .3) / spread)
    assert np.allclose(got['side'], np.maximum(got['D'], got['Qs']))
    assert got['side'].min() < 0
    assert np.allclose(WK.text_side(d, q, 'description')['side'], got['D'])
    assert WK.text_side(d, q, 'clipped')['side'].min() == 0.
    assert not WK.text_side(d, q, 'none')['side'].any()
    with pytest.raises(ValueError):
        WK.text_side(np.ones(5), q)               # a zero spread


# ------------------------------------------------------------------ M6

def csr(rows):
    ptr = np.zeros(len(rows) + 1, dtype=np.int64)
    members = []
    for i, row in enumerate(rows):
        members += list(row)
        ptr[i + 1] = len(members)
    return ptr, np.array(members, dtype=np.int64)


def test_record_groups_are_the_components_of_two_or_more():
    ptr, members = csr([[1], [0, 2], [1], [], [5], [4]])
    assert WK.record_groups(ptr, members).tolist() == [0, 0, 0, -1, 1, 1]
    ptr, members = csr([[], [], []])
    assert WK.record_groups(ptr, members).tolist() == [-1, -1, -1]


def test_memberships_are_distinct_pairs():
    chunk, node = WK.memberships(np.array([0, 0, 1, 0]), np.array([3, 3, 3, 4]))
    assert sorted(zip(chunk.tolist(), node.tolist())) == [(0, 3), (0, 4), (1, 3)]


def test_group_lift_by_hand():
    # two groups of three: means 1 and 5, the same within-group spread
    x = np.array([0., 1., 2., 4., 5., 6.])
    chunk, node = np.arange(6), np.array([0, 0, 0, 1, 1, 1])
    got = WK.group_lift(x, chunk, node, 3.)
    assert got['sigma2'] == pytest.approx(4 / 4)             # SSW 4 over 6 - 2
    assert got['between'] == pytest.approx(4.)                # (3*4 + 3*4) / 6
    assert got['noise'] == pytest.approx(2 * 1. / 6)
    assert got['tau2'] == pytest.approx(4. - 1 / 3)
    trust = got['tau2'] / (got['tau2'] + 1. / 2)
    assert np.allclose(got['trust'], trust)
    assert np.allclose(got['raw'], [1.5 - 3, 1. - 3, .5 - 3, 5.5 - 3, 5. - 3, 4.5 - 3])
    assert np.allclose(got['lift'], [0., 0., 0., trust * 2.5, trust * 2., trust * 1.5])


def test_lifts_are_never_negative_and_a_group_of_one_gives_none():
    rng = np.random.default_rng(6)
    x = rng.normal(size=40)
    chunk = np.arange(40)
    node = np.concatenate([rng.integers(0, 6, size=39), [99]])   # chunk 39 alone in group 99
    for shrink in (True, False):
        got = WK.group_lift(x, chunk, node, float(x.mean()), shrink=shrink)
        assert (got['lift'] >= 0).all() and got['lift'][39] == 0. and got['pick'][39] == -1
        assert got['trust'][-1] == 0.


def test_trust_goes_to_one_for_a_huge_group_and_is_zero_without_between_group_variance():
    rng = np.random.default_rng(7)
    sizes = [5000, 5000, 3]
    node = np.repeat(np.arange(3), sizes)
    x = rng.normal(size=node.size) + np.array([0., 1., .5])[node]
    got = WK.group_lift(x, np.arange(node.size), node, 0.)
    assert got['tau2'] > 0 and got['trust'][0] > .999 and got['trust'][2] < got['trust'][0]
    assert got['trust'][0] == pytest.approx(got['tau2'] / (got['tau2'] + got['sigma2'] / 4999))
    assert got['trust'][2] == pytest.approx(got['tau2'] / (got['tau2'] + got['sigma2'] / 2))
    # the same values in every group: the group means do not differ, tau2 is 0
    x = np.tile([1., 2., 3.], 4)
    flat = WK.group_lift(x, np.arange(12), np.repeat(np.arange(4), 3), 0.)
    assert flat['tau2'] == 0. and not flat['trust'].any() and not flat['lift'].any()
    # no spread at all: sigma2 and tau2 both 0, the trust is 0 and not 0 / 0
    still = WK.group_lift(np.ones(6), np.arange(6), np.repeat(np.arange(2), 3), 0.)
    assert still['sigma2'] == 0. and still['tau2'] == 0. and not still['lift'].any()


def test_without_shrinkage_the_lift_is_the_positive_raw():
    x = np.array([0., 1., 2., 4., 5., 6.])
    got = WK.group_lift(x, np.arange(6), np.array([0, 0, 0, 1, 1, 1]), 3., shrink=False)
    assert got['trust'].tolist() == [1., 1.]
    assert np.allclose(got['lift'], [0., 0., 0., 2.5, 2., 1.5])


def test_a_chunk_in_several_groups_takes_its_largest_lift():
    x = np.array([0., 10., 10., -10., -10., 0., 0.])
    chunk = np.array([0, 1, 2, 0, 3, 4, 5, 6])
    node = np.array([0, 0, 0, 1, 1, 1, 2, 2])
    got = WK.group_lift(x, chunk, node, 0., shrink=False)
    assert got['lift'][0] == 10.                  # group 0's others: 10 and 10; group 1's: -10
    assert got['node'][got['pick'][0]] == 0


def test_only_groups_of_one_give_no_variance_and_no_lift():
    got = WK.group_lift(np.array([1., 2., 3.]), np.arange(3), np.arange(3), 0.)
    assert got['sigma2'] is None and got['tau2'] is None and not got['lift'].any()
    none = WK.group_lift(np.array([1., 2.]), np.zeros(0, int), np.zeros(0, int), 0.)
    assert none['groups'] == 0 and not none['lift'].any()


def test_the_anova_between_group_variance():
    x = np.array([0., 0., 2., 2.])
    chunk, node = np.arange(4), np.array([0, 0, 1, 1])
    assert WK.group_lift(x, chunk, node, 1., tau='anova')['tau2'] == 2.0
    assert WK.group_lift(x, chunk, node, 1.)['tau2'] == 1.0
    # by hand: two groups of three, means 1 and 5, sigma2 1
    x = np.array([0., 1., 2., 4., 5., 6.])
    got = WK.group_lift(x, np.arange(6), np.array([0, 0, 0, 1, 1, 1]), 3., tau='anova')
    assert got['ssb'] == pytest.approx(24.) and got['sum_sq_over_m'] == pytest.approx(3.)
    assert got['tau2'] == pytest.approx((24. - 1 * 1.) / (6 - 3.))
    trust = got['tau2'] / (got['tau2'] + 1. / 2)
    assert np.allclose(got['lift'], [0., 0., 0., trust * 2.5, trust * 2., trust * 1.5])
    # one group: nothing to estimate the between-group variance from
    one = WK.group_lift(x, np.arange(6), np.zeros(6, int), 3., tau='anova')
    assert one['tau2'] == 0. and not one['lift'].any()
    with pytest.raises(ValueError):
        WK.group_lift(x, np.arange(6), np.zeros(6, int), 3., tau='other')


def test_the_variances_are_taken_on_x_less_a_reference_per_chunk():
    # two kinds of two groups each; inside a kind the group means differ by 2
    x = np.array([10., 12., 12., 14., 0., 2., 2., 4.])
    node = np.array([0, 0, 1, 1, 2, 2, 3, 3])
    reference = np.array([12.] * 4 + [2.] * 4)
    got = WK.group_lift(x, np.arange(8), node, reference, tau='anova')
    # on y = x - reference the group means are -1, 1, -1, 1 and their mean 0
    assert got['ssb'] == pytest.approx(8.) and got['sigma2'] == pytest.approx(2.)
    assert got['tau2'] == pytest.approx((8. - 3 * 2.) / (8 - 2.))
    flat = WK.group_lift(x, np.arange(8), node, 7., tau='anova')
    assert flat['ssb'] == pytest.approx(2 * (4 ** 2 + 6 ** 2 + 4 ** 2 + 6 ** 2))
    assert np.allclose(got['raw'], [12 - 12, 10 - 12, 14 - 12, 12 - 12, 2 - 2, 0 - 2, 4 - 2, 2 - 2])


def test_kind_reference_is_the_mean_over_the_grouped_chunks_of_the_kind():
    x = np.array([1., 3., 100., 10., 20., 7.])
    grouped = np.array([True, True, False, True, True, False])
    kind = np.array([0, 0, 0, 1, 1, 2])
    reference, table = WK.kind_reference(x, grouped, kind)
    assert reference.tolist() == [2., 2., 2., 15., 15., 0.]
    assert table == {0: {'reference': 2., 'chunks': 2}, 1: {'reference': 15., 'chunks': 2}}


def toy_structure():
    """One product: channel A (S 3.0, 3.2, 2.8, 3.0) and channel B (2.0, 2.2, 1.8, 2.0), each
    channel's chunks one near group, both of one kind; four documents at -2.5 with no group."""
    strength = np.array([3.0, 3.2, 2.8, 3.0, 2.0, 2.2, 1.8, 2.0, -2.5, -2.5, -2.5, -2.5])
    chunk, node = np.arange(8), np.array([0, 0, 0, 0, 1, 1, 1, 1])
    near = np.array([0] * 4 + [1] * 4 + [-1] * 4)
    layer = {'product': np.zeros(12, dtype=int), 'near': near,
             'kind': np.array([1] * 8 + [0] * 4),
             'groups': {'product': (np.arange(12), np.zeros(12, dtype=int)),
                        'channel': (chunk, node), 'near': (chunk, node)}}
    return strength, layer


def lifting_sets(parts, c):
    """The member sets of the groups that give chunk c a lift above 0."""
    out = []
    for part in parts.values():
        m = int(part['pick'][c])
        if m >= 0 and part['lift'][c] > 0:
            g = part['node'][m]
            out.append(frozenset(part['chunk'][part['node'] == g].tolist()))
    return out


def test_near_with_the_kind_reference_lifts_the_higher_of_two_groups_only():
    strength, layer = toy_structure()
    parts, lifts = WK.structure_lifts(strength, layer)
    assert set(parts) == set(lifts) == {'product', 'near'}
    table = parts['near']['kind_reference']
    assert table[1]['chunks'] == 8 and table[1]['reference'] == pytest.approx(2.5 - 5 / 6)
    assert (lifts['near'][:4] > 0).all() and not lifts['near'][4:].any()
    assert np.allclose(parts['near']['raw'][:4], np.array([3.0, 2.9333333, 3.0666667, 3.0])
                       - 2.5, atol=1e-6)
    assert not lifts['product'].any()            # one product: no between-product variance
    zero, lifted = WK.structure_lifts(strength, layer, 'near_zero')
    assert (lifted['near'][:8] > 0).all()        # with reference 0 the lower channel is lifted too
    assert zero['near']['kind_reference'] == {}


def test_a_chunk_never_gets_two_lifts_from_one_group():
    strength, layer = toy_structure()
    parts, lifts = WK.structure_lifts(strength, layer)
    for c in range(12):
        sets = lifting_sets(parts, c)
        assert len(sets) == len(set(sets)) <= 1
    first, old = WK.structure_lifts(strength, layer, 'first')
    assert set(first) == set(old) == {'product', 'channel', 'record'}
    twice = lifting_sets(first, 0)
    assert len(twice) == 2 and twice[0] == twice[1] == frozenset({0, 1, 2, 3})
    assert old['channel'][0] == old['record'][0] > 0
    # the same on the toy graph through the chain
    inputs = toy_inputs(seed=9)
    layer, query = WK.build_layer(inputs), toy_query(inputs)
    run = WK.chain(layer, query, .002)
    assert set(run['lift']) == {'product', 'near'}
    for c in range(layer['chunks']):
        sets = lifting_sets(run['groups'], c)
        assert len(sets) == len(set(sets))
    assert np.allclose(run['S_prime'], run['S'] + run['lift']['product'] + run['lift']['near'])


def test_the_first_form_is_kept_as_it_was():
    strength, layer = toy_structure()
    first, lifts = WK.structure_lifts(strength, layer, 'first')
    left = strength - strength.mean()
    by_hand = WK.group_lift(left, *layer['groups']['channel'], 0.)
    assert first['channel']['tau'] == 'weighted'
    assert np.array_equal(lifts['channel'], by_hand['lift'])
    assert first['channel']['tau2'] == pytest.approx(.24333333)
    assert lifts['channel'][0] == pytest.approx(2.0903, abs=1e-4)
    loose, free = WK.structure_lifts(strength, layer, 'first_unshrunk')
    assert set(loose['channel']['trust'].tolist()) == {1.}
    assert (free['channel'] >= lifts['channel']).all()
    whole, _ = WK.structure_lifts(strength, layer, 'first_overall')
    assert np.array_equal(whole['record']['x'], strength)
    assert whole['record']['reference'] == pytest.approx(strength.mean())
    assert WK.structure_lifts(strength, layer, 'none') == ({}, {})
    with pytest.raises(ValueError):
        WK.structure_lifts(strength, layer, 'other')


# ------------------------------------------------------------------ M7

def test_levels_and_order():
    ids = ['d', 'c', 'b', 'a']
    strength = np.array([10., 9.99, 9.0, 9.99])
    slots = np.array([[.1, 0, 0, 0], [.2, 0, 0, 0], [.9, 0, 0, 0], [.2, 0, 0, 0.]])
    step, level, order = WK.levels_and_order(ids, strength, np.array([.02, .04, .06]), .002,
                                            np.array([True, True, True, True]), slots)
    assert step == pytest.approx(.05)
    assert level.tolist() == [0, 0, 20, 0]
    assert order == [3, 1, 0, 2]                  # level 0: slot .2 (a before c by id), then .1
    _, _, order = WK.levels_and_order(ids, strength, np.array([.04]), .002,
                                     np.array([False, True, True, True]), slots)
    assert order == [3, 1, 0, 2]                  # the chunk without a winning edge is last
    with pytest.raises(ValueError):
        WK.levels_and_order(ids, strength, np.array([0.]), .002, np.ones(4, bool), slots)


# ------------------------------------------------------------------ the chain on a toy graph

def toy_inputs(seed=0, chunks=80, tags=50, products=4):
    """A toy graph and one toy query: 80 chunks under 4 products, 50 graph tags of which tag 0
    is a product name, 8 channels of 5 Slack chunks and one of a single chunk, 6 near groups;
    three description-side query tags and one question-side."""
    rng = np.random.default_rng(seed)
    edge_tag, edge_chunk = [], []
    for c in range(chunks):
        mine = rng.choice(np.arange(1, tags), size=int(rng.integers(1, 7)), replace=False)
        edge_tag += mine.tolist()
        edge_chunk += [c] * mine.size
    edge_tag += [0, 0]                           # tag 0 is a product name: not eligible
    edge_chunk += [0, 1]
    edge_tag, edge_chunk = np.array(edge_tag), np.array(edge_chunk)
    eligible = np.ones(tags, dtype=bool)
    eligible[0] = False
    product = np.arange(chunks) % products
    channel_rows = [[c // 5] if c < 40 else [] for c in range(chunks)]
    channel_rows[3] = [0, 7]                     # one chunk in two channels
    channel_rows[39] = [50]                      # a channel of one chunk
    adjacency_rows = [[] for _ in range(chunks)]
    for a in list(range(0, 20)) + list(range(50, 60)):
        if a % 5 != 4:
            adjacency_rows[a].append(a + 1)
            adjacency_rows[a + 1].append(a)
    channel_ptr, channels = csr(channel_rows)
    adjacency_ptr, adjacency = csr(adjacency_rows)
    query_tags = 4
    readings = np.array([[1., .5, 1., 0., 0.], [0., 0., 0., 0., 0.], [.9, .2, .2, .8, .8],
                         [.5, .5, .5, .5, .5]])
    return {
        'query_texts': ['described 0', 'described 1', 'described 2', 'asked'],
        'query_readings': readings,
        'query_tag_cosines': rng.normal(.1, .03, size=(query_tags, tags)),
        'query_tag_description_cosines': np.array([.6, .3, .45, -.1]),
        'd_description': rng.normal(.2, .06, size=chunks),
        'd_question': rng.normal(.18, .06, size=chunks),
        'chunk_ids': [f'{(c * 7919) % 1000:04d}' for c in range(chunks)],
        'chunk_kinds': ['slack_thread_batch' if c < 40 else 'document_part'
                        for c in range(chunks)],
        'graph_tags': ['ProductA'] + [f'tag {t}' for t in range(1, tags)],
        'eligible': eligible, 'edge_tag': edge_tag, 'edge_chunk': edge_chunk,
        'edge_topic': rng.normal(.22, .07, size=edge_tag.size),
        'edge_facets': rng.normal(size=(edge_tag.size, 4)),
        'product': product, 'channel_ptr': channel_ptr, 'channels': channels,
        'adjacency_ptr': adjacency_ptr, 'adjacency': adjacency}


def toy_query(inputs):
    return {'cosines': inputs['query_tag_cosines'], 'readings': inputs['query_readings'],
            'description_cosines': inputs['query_tag_description_cosines'],
            'd_description': inputs['d_description'], 'd_question': inputs['d_question']}


def test_the_layer_reads_only_the_eligible_edges():
    inputs = toy_inputs()
    layer = WK.build_layer(inputs)
    assert layer['edges'].size == inputs['edge_tag'].size - 2
    assert (layer['edge_tag'] != 0).all()
    assert layer['pos'].shape == (layer['edges'].size, 5)
    assert layer['n_c'].sum() == layer['edges'].size and layer['n_c'].min() >= 1
    assert sorted(set(layer['near'].tolist())) == list(range(-1, 6))
    chunk, node = layer['groups']['channel']
    assert chunk.size == 41 and len(set(node.tolist())) == 9
    assert layer['kind_names'] == ['document_part', 'slack_thread_batch']
    assert layer['kind'].tolist() == [1] * 40 + [0] * 40
    assert np.array_equal(layer['groups']['near'][1], layer['near'][layer['near'] >= 0])


def test_every_order_is_a_permutation_of_all_chunks():
    inputs = toy_inputs()
    layer, query = WK.build_layer(inputs), toy_query(inputs)
    for switch in [{}] + list(WK.ALTERNATIVES.values()):
        run = WK.chain(layer, query, .002, **switch)
        assert sorted(run['order']) == list(range(layer['chunks']))


def test_the_chain_s_parts_add_up():
    inputs = toy_inputs(seed=3)
    layer, query = WK.build_layer(inputs), toy_query(inputs)
    run = WK.chain(layer, query, .002)
    n = layer['chunks']
    assert (run['T'] >= 0).all()
    assert np.allclose(run['S'], run['T'] + np.maximum(run['D'], run['Qs']))
    lifts = sum(run['lift'][kind] for kind in WK.GROUPINGS)
    assert (lifts >= 0).all() and np.allclose(run['S_prime'], run['S'] + lifts)
    assert (run['S_prime'] >= run['S']).all()
    # T is the winning query tag's centrality times the chunk's best w, no correction
    c = np.arange(n)
    assert np.allclose(run['T'], run['centrality'][run['winner']] * run['v'][run['winner'], c])
    assert np.array_equal(run['value'], run['v'])
    assert run['centrality'].tolist() == [1., .5, .75, 0.]
    # the winning edge belongs to the chunk and carries v
    e = run['win_edge']
    assert (layer['edge_chunk'][e] == c).all()
    assert np.allclose(run['w'][run['winner'], e], run['v'][run['winner'], c])
    # w = fit x R / 0.5, fit the standing clipped at 0
    q = 2
    fit = np.clip(run['z'][q], 0., None)[layer['edge_tag']]
    assert np.allclose(run['w'][q], fit * run['R'][q] / .5)
    assert run['equal_shares'].tolist() == [False, True, False, False]
    assert np.allclose(run['R'][1], layer['pos'].mean(axis=1))
    assert np.allclose(run['R'][3], layer['pos'].mean(axis=1))
    assert np.array_equal(run['w'][q], run['fit'][q][layer['edge_tag']] * (run['R'][q] / .5))
    assert np.array_equal(run['fit'][q], np.nan_to_num(np.clip(run['z'][q], 0., None)))
    # one eligible edge: the pooled tail returns the value, the per-edge form the fit
    single = layer['n_c'] == 1
    assert single.any() and np.array_equal(run['v_star'][:, single], run['v'][:, single])
    assert (run['v_star'] <= run['v']).all()
    tag_of = layer['edge_tag'][run['edge'][:, single]]
    assert np.array_equal(run['pe_v_star'][:, single],
                          np.take_along_axis(run['fit'], tag_of, axis=1))
    assert run['level'].min() == 0 and run['level'][run['order'][0]] == 0
    assert (np.diff(run['level'][run['order']]) >= 0).all()


def test_each_alternative_changes_its_own_step():
    inputs = toy_inputs(seed=4)
    layer, query = WK.build_layer(inputs), toy_query(inputs)
    base = WK.chain(layer, query, .002)
    c = np.arange(layer['chunks'])
    a1 = WK.chain(layer, query, .002, fit='cosine')
    assert np.allclose(a1['w'][0], query['cosines'][0][layer['edge_tag']] * a1['R'][0] / .5)
    a3 = WK.chain(layer, query, .002, share='equal')
    assert np.allclose(a3['R'], layer['pos'].mean(axis=1)[None, :])
    a3b = WK.chain(layer, query, .002, share='none')
    assert np.array_equal(a3b['w'], a3b['fit'][:, layer['edge_tag']])
    assert np.array_equal(a3b['fit'], base['fit'])
    plain = np.nan_to_num(base['v'])
    assert np.allclose(base['T'], (base['centrality'][:, None] * plain).max(axis=0))
    a4a = WK.chain(layer, query, .002, chunk='pooled')
    assert np.allclose(a4a['T'], (a4a['centrality'][:, None] * base['v_star']).max(axis=0))
    assert np.array_equal(a4a['v_star'], base['v_star'])
    a4e = WK.chain(layer, query, .002, chunk='per_edge')
    assert np.allclose(a4e['T'], (a4e['centrality'][:, None] * base['pe_v_star']).max(axis=0))
    a4b = WK.chain(layer, query, .002, chunk='sum')
    sums = np.array([np.bincount(layer['edge_chunk'], weights=w, minlength=c.size)
                     for w in a4b['w']])
    assert np.allclose(a4b['T'], (a4b['centrality'][:, None] * sums).max(axis=0))
    a4c = WK.chain(layer, query, .002, central='equal')
    assert np.allclose(a4c['T'], plain.max(axis=0))
    a4d = WK.chain(layer, query, .002, tags='sum')
    assert np.allclose(a4d['T'], (base['centrality'][:, None] * plain).sum(axis=0))
    a5a = WK.chain(layer, query, .002, side='none')
    assert np.array_equal(a5a['S'], a5a['T'])
    a5b = WK.chain(layer, query, .002, side='description')
    assert np.allclose(a5b['S'], base['T'] + base['D'])
    a5c = WK.chain(layer, query, .002, side='clipped')
    assert np.allclose(a5c['S'], base['T'] + np.clip(base['side'], 0., None))
    a6a = WK.chain(layer, query, .002, structure='none')
    assert np.array_equal(a6a['S_prime'], a6a['S']) and np.array_equal(a6a['S'], base['S'])
    assert a6a['lift'] == {} and a6a['groups'] == {}
    a6b = WK.chain(layer, query, .002, structure='unshrunk')
    for kind in WK.GROUPINGS:
        part = a6b['groups'][kind]
        assert set(part['trust'][part['size'] >= 2].tolist()) == {1.}
        assert (a6b['lift'][kind] >= base['lift'][kind] - 1e-12).all()
    a6c = WK.chain(layer, query, .002, structure='near_zero')
    assert np.allclose(a6c['lift']['product'], base['lift']['product'])
    assert not np.asarray(a6c['groups']['near']['reference']).any()
    assert np.ptp(base['groups']['near']['reference']) > 0
    a6d = WK.chain(layer, query, .002, structure='first')
    assert set(a6d['lift']) == set(WK.FIRST_GROUPINGS)
    assert np.allclose(a6d['S_prime'], base['S'] + sum(a6d['lift'].values()))
    a7 = WK.chain(layer, query, .002, order='plain')
    assert np.array_equal(a7['S_prime'], base['S_prime'])
    assert a7['order'] == np.lexsort((layer['id_rank'], -base['S_prime'])).tolist()
    assert (np.diff(base['S_prime'][a7['order']]) <= 0).all()
    for bad in ({'fit': 'other'}, {'share': 'other'}, {'chunk': 'corrected'},
                {'order': 'other'}, {'structure': 'overall'}):
        with pytest.raises(ValueError):
            WK.chain(layer, query, .002, **bad)


def test_the_structure_reads_what_is_left_after_the_product():
    inputs = toy_inputs(seed=5)
    layer, query = WK.build_layer(inputs), toy_query(inputs)
    run = WK.chain(layer, query, .002)
    product = layer['product']
    mean = np.bincount(product, weights=run['S']) / np.bincount(product)
    left = run['S'] - mean[product]
    assert np.allclose(run['groups']['near']['x'], left)
    assert np.array_equal(run['groups']['product']['x'], run['S'])
    assert run['groups']['product']['reference'] == pytest.approx(run['S'].mean())
    assert run['groups']['product']['tau'] == run['groups']['near']['tau'] == 'anova'
    # the near reference: per record kind the mean of x over the kind's chunks in near groups
    grouped = layer['near'] >= 0
    for code, row in run['groups']['near']['kind_reference'].items():
        members = grouped & (layer['kind'] == code)
        assert row['reference'] == pytest.approx(left[members].mean())
        assert np.allclose(run['groups']['near']['reference'][layer['kind'] == code],
                           row['reference'])
    part = run['groups']['near']
    for m in range(part['chunk'].size):
        c, g = int(part['chunk'][m]), int(part['node'][m])
        others = [i for i in part['chunk'][part['node'] == g].tolist() if i != c]
        assert part['raw'][m] == pytest.approx(left[others].mean() - part['reference'][c])


# ------------------------------------------------------------------ C3r and C4n

TOY_GAPS = (.8, 1.1, .9, 1.3)
TOY_WIDTH = .02


def ranked_inputs(seed=0):
    """The toy graph with what C3r reads beside it: the four facet gaps and the width of
    "equally close"."""
    return {**toy_inputs(seed=seed), 'facet_gaps': TOY_GAPS, 'self_difference': TOY_WIDTH}


def same(a, b):
    return np.array_equal(np.asarray(a), np.asarray(b), equal_nan=True)


def same_run(a, b):
    """Every array, number and nested part of two results of `chain` is the same."""
    if isinstance(a, dict):
        return (isinstance(b, dict) and set(a) == set(b)
                and all(same_run(a[key], b[key]) for key in a))
    if isinstance(a, (list, tuple)):
        return (isinstance(b, (list, tuple)) and len(a) == len(b)
                and all(same_run(x, y) for x, y in zip(a, b)))
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return same(a, b)
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def test_the_facet_classes_count_whole_gaps_below_the_column_s_largest():
    values = np.array([[3., 10.], [2.5, 10.], [2., 7.], [1., 7.], [3., 4.]])
    classes = WK.facet_classes(values, (1., 3.))
    # floor((the column's largest - value) / the column's gap): the largest is class 0 and a
    # value one whole gap below it class 1
    assert classes.tolist() == [[0, 0], [0, 0], [1, 1], [2, 1], [0, 2]]
    assert classes.dtype == np.int64
    # a column's classes follow its own gap and its own largest, whatever the other holds
    halved = WK.facet_classes(values, (.5, 3.))
    assert halved[:, 0].tolist() == [0, 1, 2, 4, 0] and same(halved[:, 1], classes[:, 1])
    assert WK.facet_classes(values + [100., -7.], (1., 3.)).tolist() == classes.tolist()
    assert WK.facet_classes(values[:, :1], (1.,)).tolist() == [[0], [0], [1], [2], [0]]
    assert WK.facet_classes(values[:1], (1., 3.)).tolist() == [[0, 0]]
    for bad_values, bad_gaps in ((values[:, 0], (1.,)), (values[:0], (1., 3.)),
                                 (values, (1.,)), (values, (1., 3., 2.)),
                                 (values, (1., 0.)), (values, (1., -3.)),
                                 (values, (1., np.inf)), (values, (np.nan, 3.)),
                                 (np.where(values == 4., np.nan, values), (1., 3.)),
                                 (np.where(values == 4., np.inf, values), (1., 3.))):
        with pytest.raises(ValueError):
            WK.facet_classes(bad_values, bad_gaps)


def test_the_self_difference_is_how_far_each_probe_lands_from_its_own_tag():
    cosines = np.array([[.2, .1, .99, .3, .0, .1],
                        [.97, .5, .1, .2, .3, .4],
                        [.1, .2, .3, .4, .5, .995],
                        [.1, .95, .2, .9, .1, .0]])
    tags = np.array([2, 0, 5, 3])
    got = WK.self_difference(cosines, tags)
    assert list(got) == ['largest', 'median', 'smallest', 'probes', 'own_tag_closest']
    # per probe 1 - its cosine to its own tag: .01, .03, .005 and .1
    assert got['largest'] == 1. - .9 and got['smallest'] == 1. - .995
    assert got['median'] == pytest.approx(.02)
    # the fourth probe lands closer to tag 1 than to its own tag 3
    assert got['probes'] == 4 and got['own_tag_closest'] == 3
    assert all(type(got[name]) is float for name in ('largest', 'median', 'smallest'))
    assert type(got['probes']) is int and type(got['own_tag_closest']) is int
    # the own tag is the one named for the probe, not the one it lands closest to
    moved = WK.self_difference(cosines, np.array([2, 0, 5, 1]))
    assert moved['largest'] == 1. - .95 and moved['own_tag_closest'] == 4
    one = WK.self_difference(cosines[:1], tags[:1])
    assert one['largest'] == one['median'] == one['smallest'] == 1. - .99
    assert one['probes'] == 1 and one['own_tag_closest'] == 1
    for bad_cosines, bad_tags in ((cosines[0], tags[:1]), (cosines, tags[:3]),
                                  (cosines[:0], tags[:0]), (cosines, tags.reshape(2, 2)),
                                  (np.where(cosines == .5, np.nan, cosines), tags),
                                  (np.where(cosines == .5, np.inf, cosines), tags),
                                  # a probe on its own stored vector exactly, and beyond it
                                  (np.where(cosines == .99, 1., cosines), tags),
                                  (np.where(cosines == .99, 1.0000001, cosines), tags)):
        with pytest.raises(ValueError):
            WK.self_difference(bad_cosines, bad_tags)


def test_the_probes_are_a_seeded_sorted_draw_of_eligible_tags_and_the_tool_s_own(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'tools'))
    import walkthrough as TOOL
    assert WK.PROBE_SEED == TOOL.SHUFFLE_SEED == 20261005 and WK.PROBES == TOOL.PROBES == 100
    assert inspect.signature(WK.draw_probes).parameters['seed'].default == 20261005
    assert inspect.signature(WK.draw_probes).parameters['size'].default == 100
    eligible = np.ones(400, dtype=bool)
    eligible[::7] = False
    picked = WK.draw_probes(eligible)
    # a hundred eligible tags, each once, in index order, the same every time
    assert picked.size == 100 == len(set(picked.tolist()))
    assert (np.diff(picked) > 0).all() and eligible[picked].all()
    assert WK.draw_probes(eligible).tolist() == picked.tolist()
    assert WK.draw_probes(eligible.astype(int)).tolist() == picked.tolist()
    assert WK.draw_probes(eligible, seed=1).tolist() != picked.tolist()
    # one generator from the seed choosing among the eligible indices
    pool = np.flatnonzero(eligible)
    drawn = np.random.default_rng(20261005).choice(pool, size=100, replace=False)
    assert picked.tolist() == np.sort(drawn).tolist() and drawn.tolist() != picked.tolist()
    # the tool's own draw with its defaults picks the same tags
    names = [f' tag_{i}' for i in range(400)]
    tool_picked, tool_names = TOOL.draw_probes(eligible, names,
                                               lambda name: name.replace('_', ' ').strip())
    assert tool_picked.tolist() == picked.tolist()
    assert tool_names == [f'tag {i}' for i in picked.tolist()]
    # fewer eligible tags than probes: every one of them, once
    few = np.zeros(60, dtype=bool)
    few[[3, 9, 10, 44]] = True
    assert WK.draw_probes(few).tolist() == [3, 9, 10, 44]
    assert WK.draw_probes(eligible, size=5).size == 5


def by_hand(cosine, best, width, facet_class, order, topic):
    """`ranked_closeness` spelled out edge by edge: the class of each edge, then per class its
    edges sorted by their key, each given its place and the cosine of that place."""
    cls = [math.floor((best - c) / width) for c in cosine]
    place, placed = [0] * len(cosine), [0.] * len(cosine)
    for k in set(cls):
        members = sorted((e for e in range(len(cosine)) if cls[e] == k),
                         key=lambda e: (tuple(int(facet_class[e][j]) for j in order),
                                        -topic[e], -cosine[e], e))
        for at, e in enumerate(members):
            place[e] = at
            placed[e] = best - width * (k + at / len(members))
    return cls, place, placed


def ranked_toy(seed=5, edges=60):
    """Sixty edges over seven classes below a best cosine of .5, the width one thirty-second:
    coarse facet classes and topics, so every key of the order has ties to break."""
    rng = np.random.default_rng(seed)
    best, width = .5, .03125
    cosine = best - rng.uniform(0., 6.5 * width, size=edges)
    cosine[:3] = [best, best - width, best - 2.5 * width]     # two of them on a band's edge
    cosine[10:14] = cosine[10]                                # equal cosines
    facet_class = rng.integers(0, 3, size=(edges, 4))
    topic = rng.choice([.1, .2, .3], size=edges)
    return cosine, best, width, facet_class, topic


def test_the_ranked_closeness_orders_inside_a_class_and_keeps_every_edge_in_its_band():
    cosine, best, width, facet_class, topic = ranked_toy()
    orders = {}
    for order in ((0, 1, 2, 3), (3, 1, 0, 2), (2, 3, 1, 0)):
        cls, place, placed = WK.ranked_closeness(cosine, best, width, facet_class, order, topic)
        assert cls.dtype == place.dtype == np.int64 and placed.dtype == np.float64
        # the classes: whole widths below the best cosine, whatever the facet order; an edge
        # one whole width below the best is the first of class 1's band, not the last of 0's
        assert cls.tolist() == np.floor((best - cosine) / width).astype(int).tolist()
        assert cls[:3].tolist() == [0, 1, 2]
        assert sorted(set(cls.tolist())) == list(range(7)) and np.bincount(cls).min() >= 2
        want_cls, want_place, want_placed = by_hand(cosine, best, width, facet_class, order,
                                                    topic)
        assert cls.tolist() == want_cls and place.tolist() == want_place
        assert placed.tolist() == want_placed
        for k in range(7):
            members = np.flatnonzero(cls == k)
            # the places 0 .. size - 1, each once
            assert sorted(place[members].tolist()) == list(range(members.size))
            # every edge inside its class's band, the first of the class on its upper edge
            assert (placed[members] > best - width * (k + 1)).all()
            assert (placed[members] <= best - width * k).all()
            assert placed[members[place[members] == 0]].tolist() == [best - width * k]
            # place by place the cosine falls by the width over the class's size
            by_place = placed[members[np.argsort(place[members])]]
            assert np.allclose(np.diff(by_place), -width / members.size, rtol=0, atol=1e-15)
        # over all edges the placed cosine falls with the class, then with the place
        assert (np.diff(placed[np.lexsort((place, cls))]) < 0).all()
        # and no edge leaves its own band: it moves by less than one width
        assert (np.abs(placed - cosine) < width).all()
        orders[order] = place.tolist()
    # the three facet orders place the edges three ways
    assert len({tuple(places) for places in orders.values()}) == 3


def test_the_ranked_closeness_follows_the_facet_order_then_topic_cosine_and_index():
    best, width = .5, .03125

    def places(cosine, facet_class, order, topic):
        return WK.ranked_closeness(np.array(cosine), best, width, np.array(facet_class), order,
                                   np.array(topic))[1].tolist()

    # two edges of one class whose facet classes differ in two columns: the column the order
    # names first decides, the lower facet class ahead
    apart = [[0, 1, 0, 0], [1, 0, 0, 0]]
    assert places([.49, .49], apart, (0, 1, 2, 3), [.2, .2]) == [0, 1]
    assert places([.49, .49], apart, (1, 0, 2, 3), [.2, .2]) == [1, 0]
    assert places([.49, .49], apart, (2, 3, 0, 1), [.2, .2]) == [0, 1]
    assert places([.49, .49], apart, (3, 2, 1, 0), [.2, .2]) == [1, 0]
    # every column of the order is read, each after the ones before it
    deep = [[0, 0, 0, 1], [0, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]]
    assert places([.49] * 4, deep, (0, 1, 2, 3), [.2] * 4) == [1, 0, 2, 3]
    assert places([.49] * 4, deep, (3, 2, 1, 0), [.2] * 4) == [3, 0, 2, 1]
    assert places([.49] * 4, deep, (1, 3, 2, 0), [.2] * 4) == [2, 0, 1, 3]
    # equal facet classes: the higher topic ahead, whatever the cosine
    alike = [[1, 1, 1, 1]] * 3
    assert places([.49, .485, .48], alike, (0, 1, 2, 3), [.1, .3, .2]) == [2, 0, 1]
    # equal topics too: the higher cosine ahead
    assert places([.48, .49, .485], alike, (0, 1, 2, 3), [.2, .2, .2]) == [2, 0, 1]
    # and equal cosines: the earlier edge ahead
    assert places([.49, .49, .49], alike, (0, 1, 2, 3), [.2, .2, .2]) == [0, 1, 2]
    # a facet class goes before the topic, the topic before the cosine
    assert places([.49, .48], [[0, 0, 0, 1], [0, 0, 0, 0]], (0, 1, 2, 3), [.9, .1]) == [1, 0]
    assert places([.49, .48], [[0, 0, 0, 0]] * 2, (0, 1, 2, 3), [.1, .9]) == [1, 0]
    # and the class before everything: the closer class is never placed behind
    cls, place, placed = WK.ranked_closeness(
        np.array([.44, .49]), best, width, np.array([[0, 0, 0, 0], [2, 2, 2, 2]]), (0, 1, 2, 3),
        np.array([.9, .1]))
    assert cls.tolist() == [1, 0] and place.tolist() == [0, 0]
    assert placed.tolist() == [best - width, best]


def test_the_ranked_closeness_refuses_what_it_cannot_place():
    cosine, best, width, facet_class, topic = ranked_toy()
    good = (cosine, best, width, facet_class, (0, 1, 2, 3), topic)
    WK.ranked_closeness(*good)
    for at, bad in ((0, cosine.reshape(2, -1)), (5, topic[:-1]), (3, facet_class[:-1]),
                    (4, (0, 1, 2)), (4, (0, 1, 2, 2)), (4, (0, 1, 2, 4)), (4, (1, 2, 3, 4)),
                    (2, 0.), (2, -width), (2, np.inf), (2, np.nan), (1, np.inf), (1, np.nan),
                    (1, cosine.max() - 1e-9)):      # an edge closer than the closest tag
        with pytest.raises(ValueError):
            WK.ranked_closeness(*good[:at], bad, *good[at + 1:])
    # no edge: nothing to place
    cls, place, placed = WK.ranked_closeness(cosine[:0], best, width, facet_class[:0],
                                             (0, 1, 2, 3), topic[:0])
    assert cls.size == place.size == placed.size == 0 and cls.dtype == place.dtype == np.int64
    # the classes count from the best cosine handed over, not from the closest edge: a closest
    # tag with no edge leaves the first classes empty
    far = best + 2.5 * width
    cls, place, placed = WK.ranked_closeness(cosine, far, width, facet_class, (0, 1, 2, 3),
                                             topic)
    assert cls.min() == 2 and placed.max() == far - 2 * width
    assert cls.tolist() == np.floor((far - cosine) / width).astype(int).tolist()


def test_the_layer_holds_the_facet_classes_and_the_width_only_when_given():
    inputs = toy_inputs()
    plain = WK.build_layer(inputs)
    assert plain['facet_class'] is None and plain['self_difference'] is None
    # the two edges of the product-name tag carry the largest facet values of all: the classes
    # count from the largest over the eligible edges
    inputs['edge_facets'] = inputs['edge_facets'].copy()
    inputs['edge_facets'][-2:] = 50.
    layer = WK.build_layer({**inputs, 'facet_gaps': TOY_GAPS, 'self_difference': TOY_WIDTH})
    assert layer['self_difference'] == TOY_WIDTH and type(layer['self_difference']) is float
    facets = layer['raw'][:, WK.FACET_COLUMNS]
    assert same(facets, inputs['edge_facets'][layer['edges']]) and facets.max() < 50.
    assert same(layer['facet_class'], WK.facet_classes(facets, TOY_GAPS))
    assert layer['facet_class'].shape == (layer['edges'].size, 4)
    assert layer['facet_class'].min(axis=0).tolist() == [0, 0, 0, 0]
    assert (layer['facet_class'].max(axis=0) >= 3).all()
    # either of the two alone, and the rest of the layer as without them
    gaps_only = WK.build_layer({**inputs, 'facet_gaps': TOY_GAPS})
    width_only = WK.build_layer({**inputs, 'self_difference': TOY_WIDTH})
    assert gaps_only['self_difference'] is None
    assert same(gaps_only['facet_class'], layer['facet_class'])
    assert width_only['facet_class'] is None and width_only['self_difference'] == TOY_WIDTH
    base = WK.build_layer(inputs)
    assert set(layer) == set(base)
    assert all(same_run(layer[name], base[name]) for name in base
               if name not in ('facet_class', 'self_difference'))
    for bad in ({'self_difference': 0.}, {'self_difference': -.02}, {'self_difference': np.inf},
                {'self_difference': np.nan}, {'facet_gaps': (1., 1., 1.)},
                {'facet_gaps': (1., 1., 1., 0.)}, {'facet_gaps': (1., 1., -1., 1.)},
                {'facet_gaps': (1., np.nan, 1., 1.)}):
        with pytest.raises(ValueError):
            WK.build_layer({**inputs, 'facet_gaps': TOY_GAPS, 'self_difference': TOY_WIDTH,
                            **bad})


def test_rank_picked_is_refused_without_the_gaps_or_the_width_and_rank_none_reads_neither():
    inputs = toy_inputs(seed=6)
    query = toy_query(inputs)
    plain = WK.build_layer(inputs)
    full = WK.build_layer({**inputs, 'facet_gaps': TOY_GAPS, 'self_difference': TOY_WIDTH})
    for layer in (plain, WK.build_layer({**inputs, 'facet_gaps': TOY_GAPS}),
                  WK.build_layer({**inputs, 'self_difference': TOY_WIDTH})):
        with pytest.raises(ValueError, match='needs a layer built with the facet gaps'):
            WK.chain(layer, query, .002, rank='picked')
        WK.chain(layer, query, .002)
    for bad in ('on', 'off', 'C3r', True):
        with pytest.raises(ValueError, match='rank must be one of'):
            WK.chain(full, query, .002, rank=bad)
    # with rank none the layer's gaps and width are not read: the PROPOSAL and every
    # alternative give on the layer that holds them what they give on the one that does not
    for name, switches in [('PROPOSAL', {})] + list(WK.ALTERNATIVES.items()):
        without = WK.chain(plain, query, .002, **switches)
        with_them = WK.chain(full, query, .002, **switches)
        assert with_them['edge_class'] is None and with_them['edge_place'] is None
        assert 'edge_class' in without and without['edge_class'] is None
        assert same_run(with_them, without), name
        assert same_run(WK.chain(full, query, .002, rank='none', **switches), without), name
    # rank picked gives another order on this toy, every chunk once
    ranked = WK.chain(full, query, .002, rank='picked')
    assert ranked['order'] != WK.chain(full, query, .002)['order']
    assert sorted(ranked['order']) == list(range(full['chunks']))
    assert not same_run(ranked, WK.chain(full, query, .002))


def test_rank_picked_places_each_edge_from_its_query_tag_s_closest_eligible_tag_and_order():
    inputs = ranked_inputs(seed=7)
    # the product-name tag is by far the closest tag to the first query tag: it is not
    # eligible, and the classes do not count from it
    inputs['query_tag_cosines'] = inputs['query_tag_cosines'].copy()
    inputs['query_tag_cosines'][0, 0] = .9
    # an eligible tag with no edge is the closest to the second query tag: the classes count
    # from it all the same, and that query tag's closest classes hold no edge
    edgeless = 9
    kept = inputs['edge_tag'] != edgeless
    for name in ('edge_tag', 'edge_chunk', 'edge_topic', 'edge_facets'):
        inputs[name] = inputs[name][kept]
    inputs['query_tag_cosines'][1, edgeless] = .5
    layer, query = WK.build_layer(inputs), toy_query(inputs)
    base = WK.chain(layer, query, .002)
    run = WK.chain(layer, query, .002, rank='picked')
    tag_e, eligible, topic = layer['edge_tag'], layer['eligible'], layer['raw'][:, 0]
    assert eligible[edgeless] and edgeless not in tag_e.tolist() and not kept.all()
    assert run['edge_class'][1].min() == math.floor(
        (.5 - query['cosines'][1][tag_e].max()) / TOY_WIDTH) > 10
    assert same(topic, np.asarray(inputs['edge_topic'])[layer['edges']])
    assert run['edge_class'].shape == run['edge_place'].shape == (4, layer['edges'].size)
    orders = [MK.facet_order(r) for r in query['readings']]
    assert run['facet_orders'].tolist() == [list(o) for o in orders]
    assert orders == [(1, 0, 2, 3), (0, 1, 2, 3), (2, 3, 0, 1), (0, 1, 2, 3)]

    def placed_by(layer_, q, row):
        return WK.ranked_closeness(row[tag_e], float(row[eligible].max()),
                                   layer_['self_difference'], layer_['facet_class'], orders[q],
                                   topic)

    for q in range(4):
        cls, place, placed = placed_by(layer, q, query['cosines'][q])
        assert run['edge_class'][q].tolist() == cls.tolist()
        assert run['edge_place'][q].tolist() == place.tolist()
        # the edge's fit is the standing of its placed cosine in the query tag's own list,
        # clipped at 0, and w that fit times the factor
        fit = np.clip((placed - run['bulk'][q]) / run['spread'][q], 0., None)
        assert same(run['w'][q], fit * (run['R'][q] / .5)) and (fit > 0).any()
    eligible_best = query['cosines'][0][eligible].max()
    assert eligible_best < .9 and run['edge_class'][0].tolist() == np.floor(
        (eligible_best - query['cosines'][0][tag_e]) / TOY_WIDTH).astype(int).tolist()
    # what stands before the ranking is as without it: each list's bulk, spread and standing,
    # the fit per tag, the shares, the edge's relevance
    for name in ('bulk', 'spread', 'z', 'fit', 'shares', 'equal_shares', 'R', 'facet_orders',
                 'centrality', 'D', 'Qs', 'side'):
        assert same(run[name], base[name]), name
    assert not same(run['w'], base['w'])
    # under A1 the edge's fit is its placed cosine itself
    raw = WK.chain(layer, query, .002, rank='picked', fit='cosine')
    for q in range(4):
        placed = placed_by(layer, q, query['cosines'][q])[2]
        assert same(raw['w'][q], placed * (raw['R'][q] / .5))
    assert same(raw['edge_class'], run['edge_class'])
    assert same(raw['edge_place'], run['edge_place'])
    # the query tag's own facet order places its edges: with the third query tag's readings
    # the first one's places change, and no other's
    other = WK.chain(layer, dict(query, readings=query['readings'][[2, 1, 2, 3]]), .002,
                     rank='picked')
    assert not same(other['edge_place'][0], run['edge_place'][0])
    assert same(other['edge_place'][1:], run['edge_place'][1:])
    assert same(other['edge_class'], run['edge_class'])
    # gaps wider than every column: the facets tie everywhere and the edge's topic, then its
    # cosine, orders each class
    wide = WK.build_layer({**inputs, 'facet_gaps': (50., 50., 50., 50.)})
    assert not wide['facet_class'].any()
    tied = WK.chain(wide, query, .002, rank='picked')
    for q in range(4):
        cls, place, placed = placed_by(wide, q, query['cosines'][q])
        assert tied['edge_place'][q].tolist() == place.tolist()
        for k in np.unique(cls).tolist():
            members = np.flatnonzero(cls == k)
            by_place = members[np.argsort(place[members])]
            assert (np.diff(topic[by_place]) <= 0).all()
    assert not same(tied['edge_place'], run['edge_place'])
    assert same(tied['edge_class'], run['edge_class'])


def test_rank_picked_moves_T_by_less_than_a_width_and_the_best_placed_edge_wins():
    for seed in (8, 9):
        inputs = ranked_inputs(seed=seed)
        layer, query = WK.build_layer(inputs), toy_query(inputs)
        n, chunk_e, size = layer['chunks'], layer['edge_chunk'], layer['edges'].size
        assert layer['n_c'].min() >= 1
        for fit in ('standing', 'cosine'):
            base = WK.chain(layer, query, .002, share='none', fit=fit)
            run = WK.chain(layer, query, .002, share='none', fit=fit, rank='picked')
            # one width in the fit's unit: over the list's spread under the standing
            unit = TOY_WIDTH / run['spread'] if fit == 'standing' else np.full(4, TOY_WIDTH)
            # per query tag an edge's fit, and so the chunk's best, moves by less than that
            assert (np.abs(run['w'] - base['w']) < unit[:, None]).all()
            assert (np.abs(run['value'] - base['value']) < unit[:, None]).all()
            # and T by less than the centrality times it, of the query tag that wins
            moved = run['T'] - base['T']
            assert (moved < run['centrality'][run['winner']] * unit[run['winner']] + 1e-15).all()
            assert (-moved
                    < base['centrality'][base['winner']] * unit[base['winner']] + 1e-15).all()
            agree = run['winner'] == base['winner']
            assert agree.sum() > n // 2
            assert (np.abs(moved[agree]) < unit[run['winner'][agree]]).all()
            assert (np.abs(moved) < unit.max()).all() and (moved != 0).any()
            # a query tag's edge of a chunk is the chunk's best placed one: the lowest class,
            # then the lowest place
            key = run['edge_class'] * (size + 1) + run['edge_place']
            best_placed = np.full((4, n), -1)
            for q in range(4):
                by = np.lexsort((key[q], chunk_e))
                first = np.r_[True, chunk_e[by][1:] != chunk_e[by][:-1]]
                best_placed[q, chunk_e[by][first]] = by[first]
                counts = run['v'][q] > 0 if fit == 'standing' else np.ones(n, dtype=bool)
                assert counts.sum() > n // 4
                assert (run['edge'][q][counts] == best_placed[q][counts]).all()
            # and the chunk's winning edge that edge of its winning query tag
            won = run['T'] > 0 if fit == 'standing' else np.ones(n, dtype=bool)
            assert won.sum() > n // 4
            assert (run['win_edge'][won] == best_placed[run['winner'], np.arange(n)][won]).all()
            assert (run['edge_place'][run['winner'], run['win_edge']][won] >= 0).all()
            # it is not always the chunk's closest edge: inside a class the facets decide
            closest = np.array([WK.best_edges(query['cosines'][q][layer['edge_tag']], chunk_e,
                                              n)[1] for q in range(4)])
            assert (run['edge'] != closest).any()


def test_chunk_none_leaves_the_text_and_the_structure_alone():
    # the toy with a structure for the description to find
    inputs = {**arm_inputs(), 'facet_gaps': TOY_GAPS, 'self_difference': TOY_WIDTH}
    layer, query = WK.build_layer(inputs), toy_query(inputs)
    n = layer['chunks']
    base = WK.chain(layer, query, .002)
    run = WK.chain(layer, query, .002, chunk='none')
    # no chunk takes anything from a tag and none has a winning edge
    assert not run['value'].any() and not run['terms'].any() and not run['T'].any()
    assert not run['has_edge'].any() and (run['win_edge'] == -1).all()
    assert not run['slots'].any()
    assert layer['n_c'].min() >= 1 and base['has_edge'].all() and (base['T'] > 0).any()
    # the strength is the text's side and the structure's lifts on that side
    text = WK.text_side(query['d_description'], query['d_question'])
    assert same(run['S'], text['side']) and same(run['side'], base['side'])
    groups, lifts = WK.structure_lifts(text['side'], layer, 'near')
    assert same(run['S_prime'], text['side'] + sum(lifts.values()))
    assert all(same(run['lift'][kind], lifts[kind]) for kind in WK.GROUPINGS)
    assert any(lifts[kind].any() for kind in WK.GROUPINGS)
    # the order: the levels of that strength, their step from the spreads of the two texts in
    # the side (no tag's spread is read), then the chunk id
    spreads = np.array([text['spread'][name] for name in ('description', 'question')])
    step, level, order = WK.levels_and_order(layer['chunk_ids'], run['S_prime'], spreads,
                                             .002, np.zeros(n, dtype=bool), np.zeros((n, 4)))
    assert run['order'] == order and same(run['level'], level) and run['step'] == step
    assert run['order'] == np.lexsort((layer['id_rank'], run['level'])).tolist()
    assert run['order'] != base['order'] and sorted(run['order']) == list(range(n))
    # other tags, other readings, other centralities: the same strength, the same step and
    # the same order, with the levels and without
    others = dict(query, readings=query['readings'][::-1],
                  description_cosines=np.array([.1, .9, .2, .4]),
                  cosines=np.random.default_rng(1).normal(.1, .03, size=query['cosines'].shape))
    again = WK.chain(layer, others, .002, chunk='none')
    assert same(again['S_prime'], run['S_prime'])
    assert again['step'] == run['step'] and again['order'] == run['order']
    # with the description alone in the side the step reads its spread alone
    alone = WK.chain(layer, query, .002, chunk='none', side='description')
    assert alone['step'] == pytest.approx(.002 / text['spread']['description'])
    plain = np.lexsort((layer['id_rank'], -run['S_prime'])).tolist()
    assert WK.chain(layer, query, .002, chunk='none', order='plain')['order'] == plain
    assert WK.chain(layer, others, .002, chunk='none', order='plain')['order'] == plain
    # the sum over the query tags adds nothing either
    assert not WK.chain(layer, query, .002, chunk='none', tags='sum')['T'].any()
    # with the text off too nothing enters the strength: refused
    with pytest.raises(ValueError):
        WK.chain(layer, query, .002, chunk='none', side='none')
    # beside the ranking the tags still leave
    both = WK.chain(layer, query, .002, chunk='none', rank='picked')
    assert not both['T'].any() and both['edge_class'] is not None
    assert same(both['S_prime'], run['S_prime']) and not both['has_edge'].any()


# ------------------------------------------------------------------ the arm

CHAIN = WK.chain
WALK_VALUES = {'HERB_V4_WALK_FIT': ('standing', 'raw'),
               'HERB_V4_WALK_SHARES': ('readings', 'equal', 'off'),
               'HERB_V4_WALK_RANK': ('off', 'picked', 'percent', 'same'),
               'HERB_V4_WALK_TAGS': ('best', 'pooled', 'peredge', 'sum', 'off'),
               'HERB_V4_WALK_QTAGS': ('central', 'equal', 'sum'),
               'HERB_V4_WALK_TEXT': ('better', 'off', 'description', 'clipped'),
               'HERB_V4_WALK_STRUCT': ('near', 'off', 'trust1', 'ref0', 'double'),
               'HERB_V4_WALK_EQUAL': ('levels', 'off')}
WALK_STEPS = {'HERB_V4_WALK_FIT': 'M1', 'HERB_V4_WALK_SHARES': 'M3', 'HERB_V4_WALK_RANK': 'M3',
              'HERB_V4_WALK_TAGS': 'M4, within a query tag',
              'HERB_V4_WALK_QTAGS': 'M4, across the query tags', 'HERB_V4_WALK_TEXT': 'M5',
              'HERB_V4_WALK_STRUCT': 'M6', 'HERB_V4_WALK_EQUAL': 'M7'}
# The two knob values built after the walk-through and the change of `v4_walk.CHANGES` each
# names. Neither is a PROPOSAL of the walk-through and neither is one of its alternatives.
CHANGE_OF = {('HERB_V4_WALK_RANK', 'picked'): 'C3r',
             ('HERB_V4_WALK_RANK', 'percent'): 'C3p',
             ('HERB_V4_WALK_RANK', 'same'): 'C3s',
             ('HERB_V4_WALK_TAGS', 'off'): 'C4n'}
# Each other knob value off its default and the alternative of the walk-through it names.
ALTERNATIVE_OF = {('HERB_V4_WALK_FIT', 'raw'): 'A1',
                  ('HERB_V4_WALK_SHARES', 'equal'): 'A3',
                  ('HERB_V4_WALK_SHARES', 'off'): 'A3b',
                  ('HERB_V4_WALK_TAGS', 'pooled'): 'A4a',
                  ('HERB_V4_WALK_TAGS', 'peredge'): 'A4e',
                  ('HERB_V4_WALK_TAGS', 'sum'): 'A4b',
                  ('HERB_V4_WALK_QTAGS', 'equal'): 'A4c',
                  ('HERB_V4_WALK_QTAGS', 'sum'): 'A4d',
                  ('HERB_V4_WALK_TEXT', 'off'): 'A5a',
                  ('HERB_V4_WALK_TEXT', 'description'): 'A5b',
                  ('HERB_V4_WALK_TEXT', 'clipped'): 'A5c',
                  ('HERB_V4_WALK_STRUCT', 'off'): 'A6a',
                  ('HERB_V4_WALK_STRUCT', 'trust1'): 'A6b',
                  ('HERB_V4_WALK_STRUCT', 'ref0'): 'A6c',
                  ('HERB_V4_WALK_STRUCT', 'double'): 'A6d',
                  ('HERB_V4_WALK_EQUAL', 'off'): 'A7'}
# Per knob the arrays of the chain that stand before its step: an alternative leaves them as
# the PROPOSAL has them.
BEFORE_THE_STEP = {'HERB_V4_WALK_FIT': ('bulk', 'spread', 'z'),
                   'HERB_V4_WALK_SHARES': ('z', 'fit'),
                   'HERB_V4_WALK_TAGS': ('fit', 'R', 'w'),
                   'HERB_V4_WALK_QTAGS': ('w', 'value'),
                   'HERB_V4_WALK_TEXT': ('value', 'centrality', 'T', 'winner', 'D', 'Qs'),
                   'HERB_V4_WALK_STRUCT': ('T', 'side', 'S'),
                   'HERB_V4_WALK_EQUAL': ('S', 'S_prime', 'level')}
# The first array each alternative's own step writes.
ITS_OWN_STEP = {'A1': 'fit', 'A3': 'R', 'A3b': 'w', 'A4a': 'value', 'A4e': 'value',
                'A4b': 'value', 'A4c': 'centrality', 'A4d': 'T', 'A5a': 'side', 'A5b': 'side',
                'A5c': 'side', 'A6a': 'S_prime', 'A6b': 'S_prime', 'A6c': 'S_prime',
                'A6d': 'S_prime', 'A7': 'order'}


def arm_inputs(seed=11):
    """The toy graph with a structure to find: the chunks of one near group and of one product
    stand higher on the description."""
    inputs = toy_inputs(seed=seed)
    inputs['d_description'] = inputs['d_description'].copy()
    inputs['d_description'][:5] += .3
    inputs['d_description'][inputs['product'] == 1] += .1
    # the query side as the embedder's other role gives it: other cosines for the same texts
    rng = np.random.default_rng(seed + 1000)
    inputs['passage_tag_cosines'] = rng.normal(.1, .03, size=inputs['query_tag_cosines'].shape)
    inputs['passage_d_description'] = rng.normal(.2, .06, size=80)
    inputs['passage_d_description'][:5] += .3
    inputs['passage_d_description'][inputs['product'] == 1] += .1
    inputs['passage_tag_description_cosines'] = np.array([.2, .7, .35, .5])
    inputs['passage_d_question'] = rng.normal(.18, .06, size=80)
    # each graph tag's own name in the passage role against the stored tag vectors: 1 less
    # .004 to .019 to its own tag, .98 for tag 5, the furthest; tag 7's name lands closer to
    # tag 8 than to its own
    probes = rng.uniform(.3, .9, size=(50, 50))
    probes[np.arange(50), np.arange(50)] = 1. - rng.uniform(.004, .019, size=50)
    probes[5, 5], probes[7, 8] = .98, .999
    inputs['probe_cosines'] = probes
    return inputs


# Per embedder role the toy's tag cosines to the graph tags, description cosines to the chunk
# descriptions, tag cosines to the description, and question cosines to the chunk descriptions.
ROLE_KEYS = {'query': ('query_tag_cosines', 'd_description', 'query_tag_description_cosines',
                       'd_question'),
             'passage': ('passage_tag_cosines', 'passage_d_description',
                         'passage_tag_description_cosines', 'passage_d_question')}
ROLES = ('passage', 'query')
# The tags' and the description's role, and with the question's the eight combinations of the
# three role knobs.
ROLE_PAIRS = (('passage', 'query'), ('passage', 'passage'), ('query', 'query'),
              ('query', 'passage'))
ROLE_TRIPLES = tuple((tagrole, descrole, questrole) for tagrole in ROLES for descrole in ROLES
                     for questrole in ROLES)
ROLE_ENVS = ('HERB_V4_WALK_TAGROLE', 'HERB_V4_WALK_DESCROLE', 'HERB_V4_WALK_QUESTROLE')
ROLE_KNOBS = ('walktagrole', 'walkdescrole', 'walkquestrole')


def role_env(tagrole, descrole, questrole):
    return dict(zip(ROLE_ENVS, (tagrole, descrole, questrole)))


def role_flags(tagrole, descrole, questrole):
    return dict(zip(ROLE_KNOBS, (tagrole, descrole, questrole)))


def role_query(inputs, tagrole='passage', descrole='passage', questrole='passage'):
    """The chain's query for the toy under the three role knobs: the tags' cosines from the
    tags' role, the description's from the description's, the question's from the question's,
    and the centrality from one role for both - passage when the tags' and the description's
    knobs both say passage, query otherwise."""
    central = 'passage' if tagrole == descrole == 'passage' else 'query'
    return {'cosines': inputs[ROLE_KEYS[tagrole][0]], 'readings': inputs['query_readings'],
            'description_cosines': inputs[ROLE_KEYS[central][2]],
            'd_description': inputs[ROLE_KEYS[descrole][1]],
            'd_question': inputs[ROLE_KEYS[questrole][3]]}


def direct(inputs, tagrole='passage', descrole='passage', questrole='passage', **switches):
    """The chain as tools/walkthrough.py runs it: the layer from the inputs, then `chain`, on
    the query the three role knobs give (their defaults unless named)."""
    return CHAIN(WK.build_layer(inputs), role_query(inputs, tagrole, descrole, questrole),
                 V.COS_NOISE, **switches)


def arm_structure(inputs):
    return MK.build_structure(
        {'ptr': inputs['adjacency_ptr'], 'members': inputs['adjacency']},
        {'chunk_group_ptr': inputs['channel_ptr'], 'chunk_groups': inputs['channels'],
         'product': inputs['product']}, {'toy': True})


def toy_prepared(inputs, **changes):
    """The toy graph as the arm's prepare hands it over: the walk layer with the multikey
    layer's four facet gaps and no self-difference, which the first question that ranks
    measures."""
    tags, chunks = tuple(inputs['graph_tags']), tuple(inputs['chunk_ids'])
    structure = arm_structure(inputs)
    multikey_layer = MK.build_layer(inputs['edge_facets'], TOY_GAPS, {}, {})
    fields = dict(
        chunk_rows=tuple({'chunkId': c} for c in chunks), chunk_ids=chunks,
        chunk_kinds=tuple(inputs['chunk_kinds']), graph_tags=tags, product_tags=(tags[0],),
        nonscope_eligible=inputs['eligible'], tag_vectors=np.eye(len(tags)),
        chunk_vectors=np.eye(len(chunks)), edge_tag=inputs['edge_tag'],
        edge_chunk=inputs['edge_chunk'], edge_topic=inputs['edge_topic'],
        edge_pos=np.zeros((inputs['edge_tag'].size, 5)), landings=(), driver=None,
        cache_dir=None, provenance={}, build_stats=BuildStats(0., ModelUsage(), []),
        casefold_eligible=inputs['eligible'], multikey_layer=multikey_layer,
        structure=structure,
        walk_layer=V._walk_layer(chunks, inputs['chunk_kinds'], inputs['edge_tag'],
                                 inputs['edge_chunk'], inputs['edge_topic'],
                                 multikey_layer.values, inputs['eligible'], structure,
                                 multikey_layer.gaps))
    return V.Prepared(**{**fields, **changes})


def toy_answer(inputs):
    """The querytagger answer of the toy query: three description-side tags, one question-side."""
    def rows(texts, readings):
        return [{'t': text, 'facets': dict(zip(Q.FACETS, (float(v) for v in row)))}
                for text, row in zip(texts, readings)]

    texts, readings = inputs['query_texts'], inputs['query_readings']
    return {'description': 'Sought content', 'tags': rows(texts[:3], readings[:3]),
            'query_tags': rows(texts[3:], readings[3:])}


# The three knobs whose arm default left the walked-through PROPOSAL on 2026-10-05, at their
# PROPOSAL values: `arm` runs the PROPOSAL unless a test sets one of them.
PROPOSAL_ENV = {'HERB_V4_WALK_SHARES': 'readings', 'HERB_V4_WALK_RANK': 'off',
                'HERB_V4_WALK_STRUCT': 'near'}
# The raw question's role these tests were written under; the arm's default is query since
# 2026-10-05 night. `arm` runs with the question in the passage role unless a test sets it.
QUESTION_ROLE_ENV = {'HERB_V4_WALK_QUESTROLE': 'passage'}


def arm(monkeypatch, inputs, env=None, kept=12, prep=None, interpret=True, embedder=False,
        area=None, seen=None, on_width=None):
    """The arm on the toy graph under `walk` and the knobs given, every outside call replaced:
    the two cosine functions by the toy's cosines of the role they are called in, the cut by a
    recorder, the model by a refusal. Each cosine call is recorded with its role, per function
    and in `calls` in the order made, and with the number of arguments it came with. The
    measurement of the width under HERB_V4_WALK_RANK=picked is answered from the toy's probe
    cosines and recorded apart, in `width_calls`, with how many cosine calls and
    interpretations stood before it; on_width is called when it is made. embedder: leave the
    two cosine functions as they are. area: what the landing returns to a sort that reads one;
    without it a landing read fails. seen: the record to fill, for a run that raises."""
    texts = list(inputs['query_texts'])
    width = len(inputs['graph_tags'])
    readable = [name.replace('_', ' ').strip() for name in inputs['graph_tags']]
    seen = {} if seen is None else seen
    seen.update({'tag_calls': [], 'text_calls': [], 'calls': [], 'chain_calls': [],
                 'arguments': [], 'width_calls': [], 'interpreted': 0})

    def fake_tag_cosines(*args):
        text, tags, prepared_ = args[:3]
        role = args[3] if len(args) > 3 else 'query'
        seen['tag_calls'].append((text, tuple(tags), role))
        seen['calls'].append((text, tuple(tags), role))
        seen['arguments'].append(len(args))
        cosines, d_description, central, _ = (inputs[key] for key in ROLE_KEYS[role])
        at = [texts.index(t) for t in tags]
        return ({'query_tag_cosines': cosines[at].reshape(len(tags), width),
                 'query_description_cosines': d_description,
                 'query_tag_description_cosines': central[at]},
                ModelUsage(tokens_in=1), {'vector_sha256': f'{role} with the description'})

    def fake_cosines(*args):
        text, tags, prepared_ = args[:3]
        role = args[3] if len(args) > 3 else 'query'
        if isinstance(prepared_, V._QueryAxes):
            seen['width_calls'].append({
                'text': text, 'tags': tuple(tags), 'role': role, 'axes': prepared_,
                'arguments': len(args), 'cosine_calls_before': len(seen['calls']),
                'interpreted_before': seen['interpreted']})
            if on_width is not None:
                on_width()
            return ({'query_tag_cosines': inputs['probe_cosines'][[readable.index(t)
                                                                   for t in tags]]},
                    ModelUsage(calls=len(tags), tokens_in=700, time_s=1000.),
                    {'vector_sha256': f'the probes in the {role} role'})
        seen['text_calls'].append((text, tuple(tags), role))
        seen['calls'].append((text, tuple(tags), role))
        seen['arguments'].append(len(args))
        cosines, d_description, _, d_question = (inputs[key] for key in ROLE_KEYS[role])
        at = [texts.index(t) for t in tags]
        return ({'query_tag_cosines': cosines[at].reshape(len(tags), width),
                 'query_description_cosines': (d_description if text == 'Sought content'
                                               else d_question)},
                ModelUsage(tokens_in=1), {'vector_sha256': f'{role} alone'})

    def fake_budget(rows, budget, doc_cache):
        seen['rows'] = [r['chunkId'] for r in rows]
        return (['x'] * kept, [[]] * kept, [], {'budget': budget, 'chars': budget, 'kept': kept,
                                                'boundary': None, 'exhausted': False})

    def recorded_chain(layer, query, cos_noise, **switches):
        got = CHAIN(layer, query, cos_noise, **switches)
        seen['chain_calls'].append({'layer': layer, 'query': query, 'cos_noise': cos_noise,
                                    'switches': switches, 'run': got})
        return got

    def refuse(*args, **kwargs):
        raise AssertionError('a model call in a walk test')

    def no_landing(*args, **kwargs):
        if area is None:
            raise AssertionError('the walk sort reads no landing')
        return area

    def interpreted(text, prepared_):
        seen['interpreted'] += 1
        return Q.parse('placeholder question', toy_answer(inputs)), ModelUsage(), []

    monkeypatch.setattr(chat, 'post', refuse)
    if interpret:
        monkeypatch.setattr(V, '_interpret', interpreted)
    if not embedder:
        monkeypatch.setattr(V, '_query_cosines_and_centrality', fake_tag_cosines)
        monkeypatch.setattr(V, '_query_cosines', fake_cosines)
    monkeypatch.setattr(V, '_budget_contexts', fake_budget)
    monkeypatch.setattr(V, '_area_rank', no_landing)
    monkeypatch.setattr(WK, 'chain', recorded_chain)
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    for name, value in {'HERB_V4_SORT': 'walk', **PROPOSAL_ENV, **QUESTION_ROLE_ENV,
                        **(env or {})}.items():
        monkeypatch.setenv(name, value)
    seen['out'] = V.answer_one_question(('q', 'placeholder question'),
                                        prep or toy_prepared(inputs), None, 50, 100)
    return seen


ARM_DEFAULTS = {'HERB_V4_WALK_SHARES': 'off', 'HERB_V4_WALK_RANK': 'same',
                'HERB_V4_WALK_STRUCT': 'trust1'}


def test_walk_is_the_arm_s_default_with_three_knobs_off_the_proposal(monkeypatch):
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    assert V.knobs()['sort'] == 'walk'
    assert V.RETRIEVAL_FLAGS['defaults']['HERB_V4_SORT'] == 'walk'
    # the arm's own defaults: the facets rank the picked tags and do not multiply, and the
    # structure step does not read the size of the group; every other step at its PROPOSAL
    assert set(ARM_DEFAULTS) == set(PROPOSAL_ENV)
    assert {env: V.RETRIEVAL_FLAGS['defaults'][env] for env in ARM_DEFAULTS} == ARM_DEFAULTS
    by_env = {env: knob for knob, env in V.KNOB_ENV.items()}
    assert {by_env[env]: value for env, value in PROPOSAL_ENV.items()} == {
        knob: V.WALK_PROPOSAL[knob] for knob in ('walkshares', 'walkrank', 'walkstruct')}
    assert V.walk_switches(V.knobs()) == (
        {'share': 'none', 'rank': 'same', 'structure': 'unshrunk'},
        {'HERB_V4_WALK_SHARES': 'A3b', 'HERB_V4_WALK_RANK': 'C3s',
         'HERB_V4_WALK_STRUCT': 'A6b'})
    for env, value in PROPOSAL_ENV.items():
        monkeypatch.setenv(env, value)
    assert V.SORT_MODES == ('strength', 'multikey', 'adjust_lower', 'multirank', 'concept',
                            'chain', 'sum', 'walk')
    assert 'walk' in V.RETRIEVAL_FLAGS and set(V.READ_BY) == set(V.SORT_MODES)
    # with those three at their PROPOSAL values every marked step is at its PROPOSAL
    assert V.walk_switches(V.knobs()) == ({}, {})
    monkeypatch.setenv('HERB_V4_SORT', 'walk')
    assert V.knobs()['sort'] == 'walk'
    record = V.knob_record(V.knobs())
    assert record['read_by_active_sort'] == ['HERB_V4_SORT', *WALK_VALUES,
                                             'HERB_V4_WALK_TAGROLE', 'HERB_V4_WALK_DESCROLE',
                                             'HERB_V4_WALK_QUESTROLE', 'HERB_V4_OFFLINE']
    assert record['ignored_by_active_sort'] == [
        'HERB_V4_FITEQ', 'HERB_V4_STRUCT_AT', 'HERB_V4_QTOPIC', 'HERB_V4_EDGECOMB',
        'HERB_V4_DESCJOIN', 'HERB_V4_JOIN', 'HERB_V4_BAND', 'HERB_V4_PROBES', 'HERB_V4_FACETS',
        'HERB_V4_AREA', 'HERB_V4_TAGSIDE']
    assert record['product_name_tags_excluded_by_the_sort'] is True
    # every older mode is still chosen by its name
    for sort in V.SORT_MODES:
        monkeypatch.setenv('HERB_V4_SORT', sort)
        assert V.knobs()['sort'] == sort


def test_every_walk_knob_defaults_to_its_proposal_and_rejects_an_unknown_value(monkeypatch):
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    # the knobs in the arm's order, each with its values, its default first, and its step
    assert [env for env, _, _ in V.WALK_KNOBS.values()] == list(WALK_VALUES)
    assert {env: tuple(values) for env, _, values in V.WALK_KNOBS.values()} == WALK_VALUES
    assert {env: step for env, step, _ in V.WALK_KNOBS.values()} == WALK_STEPS
    defaults = V.knobs()
    by_env = {env: knob for knob, env in V.KNOB_ENV.items()}
    for env, values in WALK_VALUES.items():
        # the first value is the walked-through PROPOSAL; three knobs default off it
        assert defaults[by_env[env]] == ARM_DEFAULTS.get(env, values[0])
        assert V.RETRIEVAL_FLAGS['defaults'][env] == ARM_DEFAULTS.get(env, values[0])
        assert V.WALK_PROPOSAL[by_env[env]] == values[0]
        assert env in V.RETRIEVAL_FLAGS['knobs']
        assert V.RETRIEVAL_FLAGS['walk']['knobs'][env]['values'][values[0]] == 'PROPOSAL'
        for value in values:
            monkeypatch.setenv(env, value)
            assert V.knobs()[by_env[env]] == value
        for bad in ('other', values[0].upper(), 'A1', 'C3r'):
            monkeypatch.setenv(env, bad)
            with pytest.raises(ValueError, match=env):
                V.knobs()
        monkeypatch.delenv(env)
    # what the run manifest records per knob: its step, and per value the PROPOSAL, the
    # alternative of the walk-through or the later change it names
    named = {**ALTERNATIVE_OF, **CHANGE_OF}
    assert V.RETRIEVAL_FLAGS['walk']['knobs'] == {
        env: {'step': WALK_STEPS[env],
              'values': {value: named.get((env, value), 'PROPOSAL') for value in values}}
        for env, values in WALK_VALUES.items()}
    assert V.RETRIEVAL_FLAGS['walk']['knobs']['HERB_V4_WALK_RANK'] == {
        'step': 'M3', 'values': {'off': 'PROPOSAL', 'picked': 'C3r', 'percent': 'C3p',
                                 'same': 'C3s'}}
    assert V.RETRIEVAL_FLAGS['walk']['knobs']['HERB_V4_WALK_TAGS']['values'] == {
        'best': 'PROPOSAL', 'pooled': 'A4a', 'peredge': 'A4e', 'sum': 'A4b', 'off': 'C4n'}
    # every knob of the arm is recorded with the default `knobs` gives it
    assert set(V.RETRIEVAL_FLAGS['knobs']) == set(V.KNOB_ENV.values())
    assert V.RETRIEVAL_FLAGS['defaults'] == {V.KNOB_ENV[k]: v for k, v in defaults.items()}


def test_each_knob_value_names_one_alternative_of_the_walk_through_or_one_later_change(
        monkeypatch):
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    # the sixteen alternatives of the walk-through, each behind exactly one knob value, and the
    # four changes built after it, each behind one more; no name and no knob value in both
    assert sorted(ALTERNATIVE_OF.values()) == sorted(WK.ALTERNATIVES)
    assert len(WK.ALTERNATIVES) == 16
    assert sorted(CHANGE_OF.values()) == sorted(WK.CHANGES) == ['C3p', 'C3r', 'C3s', 'C4n']
    assert WK.CHANGES == {'C3r': {'rank': 'picked'}, 'C3p': {'rank': 'percent'},
                          'C3s': {'rank': 'same'}, 'C4n': {'chunk': 'none'}}
    assert not set(WK.ALTERNATIVES) & set(WK.CHANGES)
    assert not set(ALTERNATIVE_OF) & set(CHANGE_OF)
    assert len(ALTERNATIVE_OF) + len(CHANGE_OF) == sum(
        len(values) - 1 for values in WALK_VALUES.values()) == 20
    # from the PROPOSAL: the three knobs the arm defaults off it are set back to it
    for env, value in PROPOSAL_ENV.items():
        monkeypatch.setenv(env, value)
    for table, names in ((ALTERNATIVE_OF, WK.ALTERNATIVES), (CHANGE_OF, WK.CHANGES)):
        for (env, value), name in table.items():
            monkeypatch.setenv(env, value)
            assert V.walk_switches(V.knobs()) == (names[name], {env: name})
            assert V.RETRIEVAL_FLAGS['walk']['knobs'][env]['values'][value] == name
            if env in PROPOSAL_ENV:
                monkeypatch.setenv(env, PROPOSAL_ENV[env])
            else:
                monkeypatch.delenv(env)
    # no two knobs set the same switch of the chain, and together they set every one
    switches_of = {env: set() for env in WALK_VALUES}
    for (env, _), name in {**ALTERNATIVE_OF, **CHANGE_OF}.items():
        switches_of[env] |= set({**WK.ALTERNATIVES, **WK.CHANGES}[name])
    every = [name for names in switches_of.values() for name in names]
    assert len(every) == len(set(every)) == 9
    assert set(every) == set(inspect.signature(WK.chain).parameters) - {'layer', 'query',
                                                                        'cos_noise'}
    assert switches_of['HERB_V4_WALK_RANK'] == {'rank'}
    assert switches_of['HERB_V4_WALK_TAGS'] == {'chunk'}
    # the default of each knob selects nothing
    for env, values in WALK_VALUES.items():
        monkeypatch.setenv(env, values[0])
    assert V.walk_switches(V.knobs()) == ({}, {})
    # two steps exchanged at once
    monkeypatch.setenv('HERB_V4_WALK_TAGS', 'pooled')
    monkeypatch.setenv('HERB_V4_WALK_EQUAL', 'off')
    assert V.walk_switches(V.knobs()) == (
        {'chunk': 'pooled', 'order': 'plain'},
        {'HERB_V4_WALK_TAGS': 'A4a', 'HERB_V4_WALK_EQUAL': 'A7'})
    # the two later changes beside an alternative, named in the knobs' order
    monkeypatch.delenv('HERB_V4_WALK_EQUAL')
    monkeypatch.setenv('HERB_V4_WALK_TAGS', 'off')
    monkeypatch.setenv('HERB_V4_WALK_RANK', 'picked')
    monkeypatch.setenv('HERB_V4_WALK_SHARES', 'off')
    switches, selected = V.walk_switches(V.knobs())
    assert switches == {'share': 'none', 'rank': 'picked', 'chunk': 'none'}
    assert list(selected.items()) == [('HERB_V4_WALK_SHARES', 'A3b'),
                                      ('HERB_V4_WALK_RANK', 'C3r'),
                                      ('HERB_V4_WALK_TAGS', 'C4n')]


def test_the_arm_sorts_by_the_chain_and_hands_every_chunk_to_the_cut_once(monkeypatch):
    inputs = arm_inputs()
    run = direct(inputs)
    seen = arm(monkeypatch, inputs)
    out, chunks = seen['out'], inputs['chunk_ids']
    assert out.meta['policy']['knobs_recorded']['active']['HERB_V4_SORT'] == 'walk'
    # the whole order reaches the cut: every chunk, each once, in the chain's order
    assert seen['rows'] == [chunks[i] for i in run['order']]
    assert len(seen['rows']) == len(set(seen['rows'])) == len(chunks) == 80
    assert set(seen['rows']) == set(chunks)
    # one chain call, on the prepared layer, every step at its PROPOSAL
    (call,) = seen['chain_calls']
    assert call['switches'] == {} and call['cos_noise'] == V.COS_NOISE == .002
    for name in ('T', 'D', 'Qs', 'side', 'S', 'S_prime', 'level', 'winner', 'w'):
        assert same(call['run'][name], run[name])
    top = run['order'][:12]
    ranking = out.meta['ranking']
    assert ranking['ordered_chunk_ids'] == seen['rows']
    assert ranking['delivered_chunk_ids'] == [chunks[i] for i in top]
    assert ranking['delivered_strength'] == run['S_prime'][top].tolist()
    assert ranking['delivered_levels'] == run['level'][top].tolist()
    assert 'delivered_unused_levels' not in ranking
    assert (run['T'][top] > 0).all()
    assert ranking['delivered_query_tags'] == run['winner'][top].tolist()
    assert list(ranking['delivered_terms']) == ['tags', 'description', 'product', 'near']
    assert ranking['delivered_terms']['tags'] == run['T'][top].tolist()
    assert ranking['delivered_terms']['description'] == run['side'][top].tolist()
    assert ranking['delivered_terms']['product'] == run['lift']['product'][top].tolist()
    assert ranking['delivered_terms']['near'] == run['lift']['near'][top].tolist()
    assert [sum(ranking['delivered_terms'][name][i] for name in ranking['delivered_terms'])
            for i in range(12)] == pytest.approx(ranking['delivered_strength'], abs=1e-12)
    # both tag lists are query tags. Under the default roles everything is embedded in the
    # passage role, each text once per call: each list beside the description, the question
    # alone between them
    listed = ('described 0', 'described 1', 'described 2')
    assert seen['calls'] == [('Sought content', listed, 'passage'),
                             ('placeholder question', (), 'passage'),
                             ('Sought content', ('asked',), 'passage')]
    assert seen['tag_calls'] == [seen['calls'][0], seen['calls'][2]]
    assert seen['text_calls'] == [seen['calls'][1]]
    assert seen['arguments'] == [4, 4, 4]
    assert out.retrieval.tokens_in == 3                       # the three embedding calls
    assert same(call['query']['cosines'], inputs['passage_tag_cosines'])
    assert same(call['query']['d_description'], inputs['passage_d_description'])
    assert same(call['query']['d_question'], inputs['passage_d_question'])
    assert same(call['query']['description_cosines'], inputs['passage_tag_description_cosines'])
    assert same(call['query']['readings'], inputs['query_readings'])
    assert out.meta['diagnostics']['embedding_roles'] == {
        'tags': 'passage', 'description': 'passage', 'question': 'passage',
        'centrality': 'passage'}
    texts_meta = out.meta['interpreter']['texts']
    assert texts_meta['description']['embedding'] == 'passage with the description'
    assert texts_meta['description']['embedding_by_role'] == {
        'passage': 'passage with the description'}
    assert texts_meta['question_side_tags']['embedding_by_role'] == {
        'passage': 'passage with the description'}
    assert texts_meta['question'] == {'tags': 0, 'text_chars': len('placeholder question'),
                                      'embedding': 'passage alone'}
    interp = out.meta['interpreter']
    assert interp['description_side_tags'] == 3 and interp['question_side_tags_read'] == 1
    assert interp['query_tags'] == 4
    # both texts enter the strength
    assert interp['text_probes'] == 2
    assert out.meta['area'] == {'mode': 'not read by the walk sort'}
    policy = out.meta['policy']
    assert policy['product_named_tags_excluded'] == 1
    assert policy['fit_equal_width'] is None and policy['flip_gap'] is None
    d = out.meta['diagnostics']
    assert d['credited_delivered_rows'] == 12 and d['product_named_tags_excluded_casefold'] == 1
    assert d['chain_switches'] == {} and d['alternatives_selected'] == {}
    assert d['query_tag_description_cosine'] == [.2, .7, .35, .5]
    assert d['phrases_standing_in_both_tag_lists'] == 0
    assert d['not_read'] == [] and d['levels_order_the_rows'] is True
    assert d['texts_in_the_strength'] == ['description', 'question']
    expected = V.walk_meta(WK.build_layer(inputs), run, top, {})
    for name, value in expected.items():
        assert d[name] == value
    assert out.meta['returned'] == 12 and out.answer == ''
    # the row serialises as the harness writes it
    row = json.loads(json.dumps(asdict(out), ensure_ascii=False, allow_nan=False))
    assert row['meta']['diagnostics']['query_tags'] == 4


def test_each_knob_s_alternative_changes_the_order_through_its_own_step_only(monkeypatch):
    inputs = arm_inputs()
    base = direct(inputs)
    chunks = inputs['chunk_ids']
    orders = {'PROPOSAL': tuple(base['order'])}
    for (env, value), alternative in ALTERNATIVE_OF.items():
        expected = direct(inputs, **WK.ALTERNATIVES[alternative])
        seen = arm(monkeypatch, inputs, {env: value})
        out = seen['out']
        # the chain ran once with that one step exchanged and every other at its PROPOSAL
        (call,) = seen['chain_calls']
        assert call['switches'] == WK.ALTERNATIVES[alternative] and len(call['switches']) == 1
        # what stands before the step is as the PROPOSAL has it; the step's own output is not
        for name in BEFORE_THE_STEP[env]:
            assert same(call['run'][name], base[name]), (alternative, name)
        own = ITS_OWN_STEP[alternative]
        assert not same(call['run'][own], base[own]), alternative
        # and the order handed to the cut is that chain's
        assert seen['rows'] == [chunks[i] for i in expected['order']], alternative
        assert same(call['run']['S_prime'], expected['S_prime'])
        d = out.meta['diagnostics']
        assert d['alternatives_selected'] == {env: alternative}
        assert d['chain_switches'] == WK.ALTERNATIVES[alternative]
        active = out.meta['policy']['knobs_recorded']['active']
        assert active[env] == value
        assert [e for e in WALK_VALUES if active[e] != WALK_VALUES[e][0]] == [env]
        # the terms of the credited rows add up to their strength under every alternative:
        # T, the side unless no text is read, a lift per grouping read
        ranking = out.meta['ranking']
        groupings = {'A6a': [], 'A6d': ['product', 'channel', 'record']}.get(
            alternative, ['product', 'near'])
        names = ['tags'] + ([] if alternative == 'A5a' else ['description']) + groupings
        assert list(ranking['delivered_terms']) == names == list(d['delivered_term_sums'])
        assert list(d['groupings']) == groupings
        top = expected['order'][:12]
        assert ranking['delivered_strength'] == expected['S_prime'][top].tolist()
        assert [sum(ranking['delivered_terms'][name][i] for name in names)
                for i in range(12)] == pytest.approx(ranking['delivered_strength'], abs=1e-12)
        json.dumps(asdict(out), ensure_ascii=False, allow_nan=False)
        orders[alternative] = tuple(expected['order'])
    # on this toy graph the PROPOSAL and the sixteen alternatives give seventeen orders
    assert len(orders) == 17 and len(set(orders.values())) == 17


def test_several_knobs_off_their_proposal_exchange_several_steps(monkeypatch):
    inputs = arm_inputs()
    env = {'HERB_V4_WALK_TAGS': 'pooled', 'HERB_V4_WALK_STRUCT': 'off',
           'HERB_V4_WALK_EQUAL': 'off'}
    expected = direct(inputs, chunk='pooled', structure='none', order='plain')
    seen = arm(monkeypatch, inputs, env)
    (call,) = seen['chain_calls']
    assert call['switches'] == {'chunk': 'pooled', 'structure': 'none', 'order': 'plain'}
    assert seen['rows'] == [inputs['chunk_ids'][i] for i in expected['order']]
    d = seen['out'].meta['diagnostics']
    assert d['alternatives_selected'] == {'HERB_V4_WALK_TAGS': 'A4a',
                                          'HERB_V4_WALK_STRUCT': 'A6a',
                                          'HERB_V4_WALK_EQUAL': 'A7'}
    # no levels: the strength alone orders, the chunk id on an exact tie
    strength = expected['S_prime']
    assert (np.diff(strength[expected['order']]) <= 0).all()
    assert same(strength, expected['S'])


def test_the_arm_s_meta_and_its_print_record_what_the_run_left_unread(monkeypatch, capsys):
    inputs = arm_inputs()

    def run(env):
        capsys.readouterr()
        out = arm(monkeypatch, inputs, env)['out']
        said = capsys.readouterr().out
        json.dumps(out.meta, ensure_ascii=False, allow_nan=False)
        return out.meta, out.meta['diagnostics'], out.meta['ranking'], said

    # every knob at its default: both texts, the levels, the structure
    m, d, ranking, said = run({})
    assert m['interpreter']['text_probes'] == 2 and d['not_read'] == []
    assert 'texts in the strength description, question, rows with Qs above D' in said
    assert '; levels ' in said and 'no levels order the rows' not in said
    assert 'equal shares on 1' in said and 'phrases in both lists 0' in said
    assert 'alternatives none, the PROPOSAL' in said
    # no text read: no text term, no Qs against D, no text probe
    m, d, ranking, said = run({'HERB_V4_WALK_TEXT': 'off'})
    assert m['interpreter']['text_probes'] == 0 and d['texts_in_the_strength'] == []
    assert list(ranking['delivered_terms']) == ['tags', 'product', 'near']
    assert d['text_bulk'] is None and d['text_spread'] is None
    assert d['delivered_rows_with_Qs_above_D'] is None
    assert d['not_read'] == [V.WALK_NOT_READ[('side', 'none')]]
    assert 'texts in the strength none;' in said and 'Qs above D' not in said
    # the description alone: one text probe, no Qs against D
    m, d, ranking, said = run({'HERB_V4_WALK_TEXT': 'description'})
    assert m['interpreter']['text_probes'] == 1
    assert list(d['text_bulk']) == ['description'] and list(d['text_spread']) == ['description']
    assert d['delivered_rows_with_Qs_above_D'] is None
    assert 'texts in the strength description;' in said and 'Qs above D' not in said
    # the clipped side reads both texts
    m, d, ranking, said = run({'HERB_V4_WALK_TEXT': 'clipped'})
    assert m['interpreter']['text_probes'] == 2 and d['not_read'] == []
    assert type(d['delivered_rows_with_Qs_above_D']) is int
    # equal shares: every query tag took them
    m, d, ranking, said = run({'HERB_V4_WALK_SHARES': 'equal'})
    assert d['query_tags'] == 4 and d['query_tags_with_equal_shares'] == 4
    assert 'equal shares on 4' in said
    m, d, ranking, said = run({'HERB_V4_WALK_SHARES': 'off'})
    assert d['query_tags_with_equal_shares'] is None and 'shares not read' in said
    assert 'equal shares on' not in said
    # every query tag weighing 1: no cosine to the description is recorded as read
    m, d, ranking, said = run({'HERB_V4_WALK_QTAGS': 'equal'})
    assert d['query_tag_description_cosine'] is None
    assert d['query_tag_centrality'] == [1., 1., 1., 1.]
    # no structure
    m, d, ranking, said = run({'HERB_V4_WALK_STRUCT': 'off'})
    assert d['groupings'] == {} and 'no structure read' in said
    assert list(ranking['delivered_terms']) == ['tags', 'description']
    # no levels: the level numbers are kept under names that say they did not order
    m, d, ranking, said = run({'HERB_V4_WALK_EQUAL': 'off'})
    assert d['levels_order_the_rows'] is False
    assert 'delivered_levels' not in ranking and len(ranking['delivered_unused_levels']) == 12
    assert 'level_step' not in d and 'levels_among_delivered_rows' not in d
    assert 'unused_level_step' in d and 'unused_levels_among_delivered_rows' in d
    assert d['not_read'] == [V.WALK_NOT_READ[('order', 'plain')]]
    assert 'no levels order the rows' in said and 'adjacent pairs in one level' not in said
    assert (np.diff(ranking['delivered_strength']) <= 0).all()


def test_a_phrase_standing_in_both_tag_lists_is_two_query_tags_and_is_counted(monkeypatch,
                                                                              capsys):
    inputs = arm_inputs()
    # the question-side tag is the second description-side tag in another case: the same
    # cosines and the same cosine to the description, its own readings
    inputs['query_texts'] = ['described 0', 'described 1', 'described 2', 'Described 1']
    for key in ('query_tag_cosines', 'passage_tag_cosines'):
        inputs[key] = inputs[key].copy()
        inputs[key][3] = inputs[key][1]
    inputs['query_tag_description_cosines'] = np.array([.6, .3, .45, .3])
    inputs['passage_tag_description_cosines'] = np.array([.2, .7, .35, .7])
    run = direct(inputs)
    seen = arm(monkeypatch, inputs)
    out = seen['out']
    d = out.meta['diagnostics']
    assert d['phrases_standing_in_both_tag_lists'] == 1
    assert 'phrases in both lists 1' in capsys.readouterr().out
    # it enters twice, as the walk-through has it: four query-tag rows, the chain's order
    assert out.meta['interpreter']['query_tags'] == 4 and d['query_tags'] == 4
    (call,) = seen['chain_calls']
    assert call['run']['bulk'].size == 4 and call['run']['bulk'][1] == call['run']['bulk'][3]
    assert seen['rows'] == [inputs['chunk_ids'][i] for i in run['order']]
    # under the sum over the query tags both rows are added
    summed = arm(monkeypatch, inputs, {'HERB_V4_WALK_QTAGS': 'sum'})
    (call,) = summed['chain_calls']
    terms = call['run']['terms']
    assert same(call['run']['T'], terms.sum(axis=0)) and terms.shape[0] == 4
    assert (terms[1] > 0).any() and (terms[3] > 0).any()


def test_a_chunk_with_no_eligible_edge_or_with_T_0_has_no_winning_query_tag(monkeypatch):
    inputs = arm_inputs()
    inputs['edge_tag'] = inputs['edge_tag'].copy()
    inputs['passage_tag_cosines'] = inputs['passage_tag_cosines'].copy()
    inputs['edge_tag'][inputs['edge_chunk'] == 7] = 0       # chunk 7: product-name edges only
    inputs['edge_tag'][inputs['edge_chunk'] == 9] = 49      # chunk 9: one graph tag only,
    inputs['passage_tag_cosines'][:, 49] = -1.              # far below every query tag's bulk
    run = direct(inputs)
    assert not run['has_edge'][7] and run['T'][7] == 0. and run['win_edge'][7] == -1
    # chunk 9 has an eligible edge and no pair above 0: the chain keeps the first query tag
    # and its edge for the order inside the level, and nothing won
    assert run['has_edge'][9] and run['T'][9] == 0.
    assert run['winner'][9] == 0 and run['win_edge'][9] >= 0
    none_won = np.flatnonzero(~run['has_edge'] | (run['T'] == 0.)).tolist()
    assert {7, 9} <= set(none_won)
    seen = arm(monkeypatch, inputs, kept=80)
    ranking = seen['out'].meta['ranking']
    chunk_of = {cid: c for c, cid in enumerate(inputs['chunk_ids'])}
    recorded = {chunk_of[cid]: q for cid, q in zip(ranking['delivered_chunk_ids'],
                                                   ranking['delivered_query_tags'])}
    tags_term = {chunk_of[cid]: t for cid, t in zip(ranking['delivered_chunk_ids'],
                                                    ranking['delivered_terms']['tags'])}
    assert len(recorded) == 80
    for c in range(80):
        if c in none_won:
            assert recorded[c] == -1 and tags_term[c] == 0.
        else:
            assert recorded[c] == run['winner'][c] and tags_term[c] > 0.
    at = ranking['delivered_chunk_ids'].index(inputs['chunk_ids'][7])
    assert ranking['delivered_strength'][at] == pytest.approx(
        run['side'][7] + run['lift']['product'][7] + run['lift']['near'][7])
    d = seen['out'].meta['diagnostics']
    assert d['chunks'] == 80 and d['chunks_with_an_eligible_edge'] == 79
    assert d['chunks_with_a_positive_tag_strength'] == 80 - len(none_won)
    assert len(seen['rows']) == len(set(seen['rows'])) == 80
    assert V.walk_winners(run, [7, 9]) == [-1, -1]


def test_the_arm_needs_the_prepared_walk_layer_over_its_own_chunks(monkeypatch):
    inputs = arm_inputs()
    with pytest.raises(ValueError, match='walk needs the prepared walk layer'):
        arm(monkeypatch, inputs, prep=toy_prepared(inputs, walk_layer=None))
    other = dict(toy_prepared(inputs).walk_layer)
    other['chunk_ids'] = other['chunk_ids'][::-1]
    with pytest.raises(ValueError, match='the walk layer over the same chunks'):
        arm(monkeypatch, inputs, prep=toy_prepared(inputs, walk_layer=other))


def test_the_older_sorts_run_beside_walk_and_ignore_its_knobs(monkeypatch):
    inputs = arm_inputs()
    off_proposal = {env: values[1] for env, values in WALK_VALUES.items()}
    # and each role knob off its default
    off_proposal.update(role_env('query', 'query', 'query'))
    for sort in ('concept', 'chain'):
        plain = arm(monkeypatch, inputs, {'HERB_V4_SORT': sort})
        moved = arm(monkeypatch, inputs, {'HERB_V4_SORT': sort, **off_proposal})
        for seen in (plain, moved):
            assert seen['chain_calls'] == [] and seen['tag_calls'] == []
            assert 'alternatives_selected' not in seen['out'].meta['diagnostics']
            assert 'embedding_roles' not in seen['out'].meta['diagnostics']
            # the cosine calls are the three-argument ones: no role is handed over
            assert seen['arguments'] == [3, 3] and {c[2] for c in seen['text_calls']} == {'query'}
            assert 'embedding_by_role' not in seen['out'].meta['interpreter']['texts'][
                'description']
        assert moved['text_calls'] == plain['text_calls']
        # the order and the credited rows are the same whatever the walk knobs say
        assert moved['rows'] == plain['rows'] and len(set(plain['rows'])) == 80
        assert moved['out'].meta['ranking'] == plain['out'].meta['ranking']
        record = moved['out'].meta['policy']['knobs_recorded']
        assert record['active']['HERB_V4_SORT'] == sort
        assert set(off_proposal) <= set(record['ignored_by_active_sort'])
        assert not set(off_proposal) & set(record['read_by_active_sort'])
        assert {env: record['active'][env] for env in off_proposal} == off_proposal
    # an unknown value of a walk knob is refused under every sort
    with pytest.raises(ValueError, match='HERB_V4_WALK_STRUCT'):
        arm(monkeypatch, inputs, {'HERB_V4_SORT': 'concept', 'HERB_V4_WALK_STRUCT': 'far'})


def test_the_walk_layer_is_the_chain_s_layer_on_the_arm_s_arrays_and_is_read_only():
    inputs = arm_inputs()
    built = toy_prepared(inputs).walk_layer
    # the layer as prepare builds it: with the four facet gaps, the self-difference not yet
    # measured
    plain = WK.build_layer({**inputs, 'facet_gaps': TOY_GAPS})
    assert set(built) == set(plain) and built['self_difference'] is None
    assert same(built['facet_class'], WK.facet_classes(plain['raw'][:, WK.FACET_COLUMNS],
                                                       TOY_GAPS))
    assert not built['facet_class'].flags.writeable
    for name, value in plain.items():
        if name == 'groups':
            assert set(built[name]) == set(value) == {'product', 'channel', 'near'}
            for kind in value:
                for mine, theirs in zip(built[name][kind], value[kind]):
                    assert same(mine, theirs) and not mine.flags.writeable
        elif isinstance(value, np.ndarray):
            assert same(built[name], value) and not built[name].flags.writeable
        else:
            assert built[name] == value
    with pytest.raises(ValueError):
        built['pos'][0, 0] = 1.
    # the edge values are read from the arm's edge order: the product-name edges take no rank
    assert built['edges'].tolist() == np.flatnonzero(inputs['edge_tag'] != 0).tolist()
    assert built['pos'].max() == 1. and built['pos'].min() == pytest.approx(1 / built['edges'].size)
    # a question leaves the layer as it was
    before = {name: value.copy() for name, value in built.items()
              if isinstance(value, np.ndarray)}
    run = CHAIN(built, role_query(inputs), V.COS_NOISE)
    for name, value in before.items():
        assert same(built[name], value)
    assert run['order'] == direct(inputs)['order']
    assert V._walk_counts(built) == {
        'eligible_graph_tags': 49, 'eligible_edges': int(inputs['edge_tag'].size) - 2,
        'chunks': 80,
        'chunks_with_an_eligible_edge': 80,
        'position_columns': ['topic', 'temporal', 'why', 'activity', 'concreteness'],
        'record_kinds': {'document_part': 40, 'slack_thread_batch': 40}, 'products': 4,
        'chunks_with_a_channel': 40, 'near_groups': 6, 'chunks_in_a_near_group': 30}


def test_the_layer_refuses_an_edge_endpoint_out_of_range():
    inputs = arm_inputs()
    for name, value in (('edge_tag', -1), ('edge_tag', 50), ('edge_chunk', -1),
                        ('edge_chunk', 80)):
        bad = dict(inputs)
        bad[name] = inputs[name].copy()
        bad[name][3] = value
        with pytest.raises(ValueError, match='An edge endpoint is out of range'):
            WK.build_layer(bad)


class _FakeTx:
    def __init__(self, answers):
        self.answers = answers

    def run(self, cypher, **params):
        for known, rows in self.answers:
            if cypher is known:
                return list(rows)
        raise AssertionError('a graph read this test does not know')


class _FakeSession:
    def __init__(self, answers):
        self.answers = answers

    def __enter__(self):
        return self

    def __exit__(self, *failure):
        return False

    def execute_read(self, work):
        return work(_FakeTx(self.answers))


class _FakeDriver:
    def __init__(self, answers):
        self.answers, self.sessions, self.closed = answers, [], False

    def session(self, **how):
        self.sessions.append(how)
        return _FakeSession(self.answers)

    def close(self):
        self.closed = True


FAKE_GAPS = (.5, 1., 2., 4.)


def fake_graph(monkeypatch, tmp_path):
    """A graph of six tags, six chunks and twelve edges behind `prepare_over_corpus`, every
    read from the database and from the learned layer's files answered here. Two tags are the
    product name EdgeForce, one in its own case and one in another."""
    import graph.db
    from arms import artefact_v3 as A3

    rng = np.random.default_rng(21)
    tags = ['EdgeForce', 'alpha', 'beta', 'delta', 'edgeforce', 'gamma']
    chunks = [f'k{i}' for i in range(6)]

    def slack(i):
        return json.dumps({'section': 'slack', 'parent_ref': 'p', 'channel': 'c1',
                           'index_start': i, 'index_end': i})

    def part(lo, hi):
        return json.dumps({'section': 'documents', 'parent_ref': 'p', 'id': 'd1',
                           'char_range': [lo, hi]})

    locators = [slack(0), slack(1), slack(2), part(0, 10), part(10, 20), None]
    endpoints = [('EdgeForce', 'k0'), ('edgeforce', 'k1'), ('alpha', 'k0'), ('alpha', 'k1'),
                 ('beta', 'k1'), ('beta', 'k2'), ('gamma', 'k3'), ('gamma', 'k4'),
                 ('delta', 'k4'), ('delta', 'k5'), ('alpha', 'k5'), ('beta', 'k3')]
    refit = rng.normal(size=(len(endpoints), 4))
    kinds = dict(zip(chunks, ['slack_thread_batch'] * 3 + ['document_part'] * 2 + ['pr_batch']))
    products = [{'name': 'EdgeForce'}, {'name': 'Other'}]
    answers = [
        (V.TAG_CYPHER, [{'id': t, 'vector': rng.normal(size=4).tolist()} for t in tags]),
        (V.CHUNK_CYPHER, [{'chunkId': c, 'vector': rng.normal(size=4).tolist(),
                           'locator': locators[i], 'relpath': 'products/f.json', 'sha256': 'x'}
                          for i, c in enumerate(chunks)]),
        (V.PRODUCT_CYPHER, products),
        (A3._SHAPE_CYPHER, [{'chunkId': c, 'products': ['EdgeForce' if i < 3 else 'Other'],
                             'channels': ['c1'] if i < 3 else []}
                            for i, c in enumerate(chunks)]),
        (A3._PRODUCT_NAMES_CYPHER, products)]
    driver = _FakeDriver(answers)
    learned = SimpleNamespace(endpoints=endpoints, raw_scores=rng.normal(size=(len(endpoints), 5)),
                              source_sha256='s', overlay_sha256='o')
    positions = {edge: tuple(rng.uniform(size=5).tolist()) for edge in endpoints}
    gap_lines = dict.fromkeys(('temporal', 'why', 'activity', 'concreteness'), 1)
    monkeypatch.setattr(graph.db, '_driver', lambda: driver)
    monkeypatch.setattr(V.L, 'load', lambda folder: learned)
    monkeypatch.setattr(V, '_read_positions', lambda path: (positions, kinds))
    monkeypatch.setattr(V.LAND, 'resolve_names', lambda session, cache: ())
    monkeypatch.setattr(V, '_corpus_words', lambda rows: frozenset({'word'}))
    monkeypatch.setattr(V.R4, 'read_flip_gap', lambda path: (1., {'line': 1}))
    monkeypatch.setattr(V.MK, 'read_facet_gaps', lambda path: (
        FAKE_GAPS, {'column': 'gap (any)', 'lines': gap_lines}))
    monkeypatch.setattr(V.MK, 'read_refit_means', lambda path, edges: (refit, {'draws': 24}))
    monkeypatch.setattr(V, 'BANDS_FILE', V.ROOT / 'pytest.ini')
    monkeypatch.setattr(V, 'RETRIEVAL_FLAGS', dict(V.RETRIEVAL_FLAGS))
    monkeypatch.setenv('HERB_V4_CACHE', str(tmp_path))
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    return SimpleNamespace(driver=driver, tags=tags, chunks=chunks, endpoints=endpoints,
                           refit=refit, kinds=kinds)


def test_prepare_hands_the_walk_layer_the_casefolded_mask_and_the_refit_means(monkeypatch,
                                                                              tmp_path):
    graph = fake_graph(monkeypatch, tmp_path)
    from harness import embed

    def no_embedding(*args, **kwargs):
        raise AssertionError('prepare embeds nothing and measures no width')

    monkeypatch.setattr(embed, '_embed', no_embedding)
    monkeypatch.setattr(V, '_query_cosines', no_embedding)
    monkeypatch.setattr(V, '_self_difference', no_embedding)
    prepared = V.prepare_over_corpus('a corpus that is not read')
    assert prepared.graph_tags == tuple(graph.tags) and prepared.chunk_ids == tuple(graph.chunks)
    # the two masks differ on this graph: the exact-case one keeps the tag `edgeforce`
    exact = [name != 'EdgeForce' for name in graph.tags]
    folded = [name.casefold() != 'edgeforce' for name in graph.tags]
    assert prepared.nonscope_eligible.tolist() == exact
    assert prepared.casefold_eligible.tolist() == folded and folded != exact
    layer = prepared.walk_layer
    # the mask handed to the walk layer is the casefolded one
    assert layer['eligible'].tolist() == folded
    sel = np.flatnonzero(np.asarray(folded)[prepared.edge_tag])
    assert layer['edges'].tolist() == sel.tolist() and sel.size == 10
    assert sel.size < int(np.asarray(exact)[prepared.edge_tag].sum()) == 11
    # the facet values handed are the multikey layer's, each edge's mean over the refits
    assert same(prepared.multikey_layer.values, graph.refit)
    assert same(layer['raw'][:, 1:], graph.refit[sel])
    assert same(layer['raw'][:, 0], np.asarray(prepared.edge_topic, dtype=np.float64)[sel])
    assert same(layer['pos'], WK.positions(layer['raw']))
    # the multikey layer's four facet gaps are handed too, each to its own column: the layer
    # holds every eligible edge's facet classes, read-only; the width of "equally close" is
    # not measured here but at the first question that ranks
    assert prepared.multikey_layer.gaps.tolist() == list(FAKE_GAPS)
    assert same(layer['facet_class'],
                WK.facet_classes(graph.refit[sel], FAKE_GAPS))
    assert not same(layer['facet_class'], WK.facet_classes(graph.refit[sel], FAKE_GAPS[::-1]))
    assert not layer['facet_class'].flags.writeable
    assert layer['self_difference'] is None and 'self_difference_measured' not in layer
    # the chunks, their kinds and the structure are the prepared ones
    assert layer['chunk_ids'] == graph.chunks
    assert layer['kinds'] == [graph.kinds[c] for c in graph.chunks] == list(prepared.chunk_kinds)
    assert same(layer['product'], prepared.structure.product)
    assert layer['product'].tolist() == [0, 0, 0, 1, 1, 1]
    assert layer['near'].tolist() == [0, 0, 0, 1, 1, -1]
    assert not layer['pos'].flags.writeable
    # the layer is the one `_walk_layer` builds from the prepared arrays, and its counts and
    # its source file are recorded
    again = V._walk_layer(prepared.chunk_ids, prepared.chunk_kinds, prepared.edge_tag,
                          prepared.edge_chunk, prepared.edge_topic,
                          prepared.multikey_layer.values, prepared.casefold_eligible,
                          prepared.structure, prepared.multikey_layer.gaps)
    assert same(again['pos'], layer['pos']) and same(again['near'], layer['near'])
    assert same(again['facet_class'], layer['facet_class'])
    record = prepared.provenance['walk_layer']
    assert 'HERB_V4_WALK_RANK=picked' in record['self_difference']
    assert '_walk_width' in record['self_difference']
    assert record['eligible_edges'] == 10 and record['eligible_graph_tags'] == 4
    assert record['near_groups'] == 2 and record['chunks_in_a_near_group'] == 5
    assert record['products'] == 2 and record['chunks_with_a_channel'] == 3
    assert any(Path(path).name == 'v4_walk.py' for path in prepared.provenance['source_sha256'])
    assert V.Prepared.__dataclass_fields__['walk_layer'].default is None
    assert all(how == {'database': V.DATABASE, 'default_access_mode': 'READ'}
               for how in graph.driver.sessions) and len(graph.driver.sessions) == 2
    assert not graph.driver.closed
    prepared.close()
    assert graph.driver.closed


def _leaves(value):
    if isinstance(value, dict):
        for inner in value.values():
            yield from _leaves(inner)
    elif isinstance(value, (list, tuple)):
        for inner in value:
            yield from _leaves(inner)
    else:
        yield value


def test_the_walk_meta_adds_up_and_holds_no_array():
    inputs = arm_inputs()
    layer, run = WK.build_layer(inputs), direct(inputs)
    delivered = run['order'][:9]
    d = V.walk_meta(layer, run, delivered, {})
    assert list(V.walk_terms(run, {})) == ['tags', 'description', 'product', 'near']
    assert d['not_read'] == [] and d['levels_order_the_rows'] is True
    assert d['texts_in_the_strength'] == ['description', 'question']
    assert d['text_bulk'] == run['text_bulk'] and d['text_spread'] == run['text_spread']
    assert not any(name.startswith('unused_') for name in d)
    assert sum(d['delivered_term_sums'].values()) == pytest.approx(d['delivered_strength_total'])
    assert d['delivered_strength_total'] == pytest.approx(run['S_prime'][delivered].sum())
    assert sum(d['delivered_term_shares'].values()) == pytest.approx(1.)
    assert d['delivered_term_sums']['tags'] == pytest.approx(run['T'][delivered].sum())
    assert d['delivered_term_sums']['near'] == pytest.approx(run['lift']['near'][delivered].sum())
    assert d['delivered_rows_with_Qs_above_D'] == int(
        (run['Qs'][delivered] > run['D'][delivered]).sum())
    levels = run['level'][delivered]
    assert d['levels_among_delivered_rows'] == len(set(levels.tolist()))
    assert d['adjacent_delivered_pairs'] == 8
    assert d['adjacent_delivered_pairs_in_one_level'] == int((levels[1:] == levels[:-1]).sum())
    assert d['chunks'] == 80 and d['chunks_with_an_eligible_edge'] == 80
    assert d['eligible_graph_tags'] == 49 and d['eligible_edges'] == layer['edges'].size
    assert d['query_tags'] == 4 and d['query_tags_with_equal_shares'] == 1
    assert d['query_tag_centrality'] == pytest.approx([.2 / .7, 1., .35 / .7, .5 / .7])
    # the query role's cosines to the description hold a negative one: a centrality of 0
    asked = direct(inputs, 'query', 'query', 'query')
    assert V.walk_meta(layer, asked, asked['order'][:9], {})['query_tag_centrality'] == [
        1., .5, .75, 0.]
    assert d['query_tag_bulk'] == run['bulk'].tolist()
    assert d['level_step'] == pytest.approx(.002 / np.median(run['spread']))
    assert set(d['groupings']) == {'product', 'near'}
    for kind, group in d['groupings'].items():
        part = run['groups'][kind]
        assert group == {'groups': part['groups'], 'memberships': part['memberships'],
                         'sigma2': part['sigma2'], 'tau2': part['tau2'],
                         'chunks_with_a_lift_above_0': int((run['lift'][kind] > 0).sum()),
                         'largest_lift': float(run['lift'][kind].max())}
        assert group['tau2'] > 0 and group['chunks_with_a_lift_above_0'] > 0
    assert d['groupings']['product']['groups'] == 4 and d['groupings']['near']['groups'] == 6
    assert all(type(v) in (int, float, bool, str) or v is None for v in _leaves(d))
    json.dumps(d, allow_nan=False)
    empty = V.walk_meta(layer, run, [], {})
    assert empty['delivered_strength_total'] == 0.
    assert set(empty['delivered_term_shares'].values()) == {None}
    assert empty['adjacent_delivered_pairs'] == 0 and empty['levels_among_delivered_rows'] == 0


def test_the_walk_meta_records_what_the_run_left_unread():
    inputs = arm_inputs()
    layer = WK.build_layer(inputs)
    base = direct(inputs)

    def meta(**switches):
        run = direct(inputs, **switches)
        rows = run['order'][:9]
        return V.walk_meta(layer, run, rows, switches), run, rows

    # the default reads everything
    d, run, rows = meta()
    assert d['not_read'] == [] and d['query_tags_with_equal_shares'] == 1
    # no text: no text term, no bulk, no spread, no Qs against D
    d, run, rows = meta(side='none')
    assert d['texts_in_the_strength'] == [] and d['text_bulk'] is None
    assert d['text_spread'] is None and d['delivered_rows_with_Qs_above_D'] is None
    assert list(d['delivered_term_sums']) == ['tags', 'product', 'near']
    assert list(V.walk_terms(run, {'side': 'none'})) == ['tags', 'product', 'near']
    assert sum(d['delivered_term_sums'].values()) == pytest.approx(run['S_prime'][rows].sum())
    assert d['not_read'] == [V.WALK_NOT_READ[('side', 'none')]]
    # the description alone: the question's bulk and spread are left out, and no Qs count
    d, run, rows = meta(side='description')
    assert d['texts_in_the_strength'] == ['description']
    assert d['text_bulk'] == {'description': run['text_bulk']['description']}
    assert d['text_spread'] == {'description': run['text_spread']['description']}
    assert d['delivered_rows_with_Qs_above_D'] is None
    assert list(d['delivered_term_sums']) == ['tags', 'description', 'product', 'near']
    assert d['not_read'] == [V.WALK_NOT_READ[('side', 'description')]]
    # the clipped side reads both texts
    d, run, rows = meta(side='clipped')
    assert d['texts_in_the_strength'] == ['description', 'question'] and d['not_read'] == []
    assert d['delivered_rows_with_Qs_above_D'] == int((run['Qs'][rows] > run['D'][rows]).sum())
    # equal shares: every query tag took them; the chain's own flag still says one had no reading
    d, run, rows = meta(share='equal')
    assert int(run['equal_shares'].sum()) == 1 and d['query_tags_with_equal_shares'] == 4
    assert d['not_read'] == [V.WALK_NOT_READ[('share', 'equal')]]
    # no shares at all
    d, run, rows = meta(share='none')
    assert d['query_tags_with_equal_shares'] is None
    assert d['not_read'] == [V.WALK_NOT_READ[('share', 'none')]]
    # centrality 1 for every query tag
    d, run, rows = meta(central='equal')
    assert d['query_tag_centrality'] == [1., 1., 1., 1.]
    assert d['not_read'] == [V.WALK_NOT_READ[('central', 'equal')]]
    # no structure: no grouping, and the strength is T and the side alone
    d, run, rows = meta(structure='none')
    assert d['groupings'] == {} and list(d['delivered_term_sums']) == ['tags', 'description']
    assert d['not_read'] == [V.WALK_NOT_READ[('structure', 'none')]]
    # no levels: the numbers the chain still computes stand under names that say so
    d, run, rows = meta(order='plain')
    assert d['levels_order_the_rows'] is False
    assert d['not_read'] == [V.WALK_NOT_READ[('order', 'plain')]]
    for name in ('level_step', 'levels_among_delivered_rows',
                 'adjacent_delivered_pairs_in_one_level'):
        assert name not in d and 'unused_' + name in d
    assert d['unused_level_step'] == pytest.approx(base['step'])
    assert d['adjacent_delivered_pairs'] == 8
    # the switches that exchange a calculation and leave nothing unread
    for switches in ({'fit': 'cosine'}, {'chunk': 'pooled'}, {'chunk': 'per_edge'},
                     {'chunk': 'sum'}, {'tags': 'sum'}, {'structure': 'unshrunk'},
                     {'structure': 'near_zero'}, {'structure': 'first'}):
        assert meta(**switches)[0]['not_read'] == []
    # several at once, each named
    d, run, rows = meta(side='none', structure='none', order='plain')
    assert len(d['not_read']) == 3 and list(d['delivered_term_sums']) == ['tags']
    assert set(V.WALK_NOT_READ) <= {
        (name, value) for switches in {**WK.ALTERNATIVES, **WK.CHANGES}.values()
        for name, value in switches.items()}


# --- the embedder's two roles ----------------------------------------------------

def test_the_role_knobs_default_to_passage_the_question_s_to_query(monkeypatch):
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    knobs = {'walktagrole': 'HERB_V4_WALK_TAGROLE', 'walkdescrole': 'HERB_V4_WALK_DESCROLE',
             'walkquestrole': 'HERB_V4_WALK_QUESTROLE'}
    assert tuple(knobs) == ROLE_KNOBS and tuple(knobs.values()) == ROLE_ENVS
    default = {'walktagrole': 'passage', 'walkdescrole': 'passage', 'walkquestrole': 'query'}
    assert V.WALK_ROLE_KNOBS == {knob: (env, ('passage', 'query'), default[knob])
                                 for knob, env in knobs.items()}
    flags = V.knobs()
    assert {knob: flags[knob] for knob in knobs} == default
    assert V.walk_roles(flags) == {'tags': 'passage', 'description': 'passage',
                                   'question': 'query', 'centrality': 'passage'}
    assert {knob: V.KNOB_ENV[knob] for knob in knobs} == knobs
    assert V.RETRIEVAL_FLAGS['walk']['role_knobs'] == {
        'HERB_V4_WALK_TAGROLE': {'values': ['passage', 'query'], 'default': 'passage'},
        'HERB_V4_WALK_DESCROLE': {'values': ['passage', 'query'], 'default': 'passage'},
        'HERB_V4_WALK_QUESTROLE': {'values': ['passage', 'query'], 'default': 'query'}}
    for knob, env in knobs.items():
        assert V.RETRIEVAL_FLAGS['defaults'][env] == default[knob]
        assert env in V.RETRIEVAL_FLAGS['knobs']
        for value in ('passage', 'query'):
            monkeypatch.setenv(env, value)
            assert V.knobs()[knob] == value
            # one knob moves its own role and neither of the other two
            assert {k: V.knobs()[k] for k in knobs if k != knob} == {
                k: default[k] for k in knobs if k != knob}
        for bad in ('document', 'Passage', 'both'):
            monkeypatch.setenv(env, bad)
            with pytest.raises(ValueError, match=env):
                V.knobs()
        monkeypatch.delenv(env)
    # read by walk, ignored by every other sort
    for sort in V.SORT_MODES:
        monkeypatch.setenv('HERB_V4_SORT', sort)
        record = V.knob_record(V.knobs())
        where, elsewhere = (('read_by_active_sort', 'ignored_by_active_sort') if sort == 'walk'
                            else ('ignored_by_active_sort', 'read_by_active_sort'))
        assert set(ROLE_ENVS) <= set(record[where])
        assert not set(ROLE_ENVS) & set(record[elsewhere])
        assert {env: record['active'][env] for env in ROLE_ENVS} == {
            env: default[knob] for knob, env in knobs.items()}
    # the roles are no step of the chain: no role knob sets a switch
    monkeypatch.setenv('HERB_V4_SORT', 'walk')
    before = V.walk_switches(V.knobs())
    for env in ROLE_ENVS:
        monkeypatch.setenv(env, 'query')
    assert V.walk_switches(V.knobs()) == before
    for env, value in PROPOSAL_ENV.items():
        monkeypatch.setenv(env, value)
    assert V.walk_switches(V.knobs()) == ({}, {})


def test_the_centrality_is_in_one_role_for_both_in_all_eight_combinations():
    # the tags', the description's and the question's knob -> the centrality's role: passage
    # only when the tags' and the description's knobs both say passage
    central = {('passage', 'passage', 'passage'): 'passage',
               ('passage', 'passage', 'query'): 'passage',
               ('passage', 'query', 'passage'): 'query',
               ('passage', 'query', 'query'): 'query',
               ('query', 'passage', 'passage'): 'query',
               ('query', 'passage', 'query'): 'query',
               ('query', 'query', 'passage'): 'query',
               ('query', 'query', 'query'): 'query'}
    assert set(central) == set(ROLE_TRIPLES) and len(set(ROLE_TRIPLES)) == 8
    for (tagrole, descrole, questrole), role in central.items():
        assert V.walk_roles(role_flags(tagrole, descrole, questrole)) == {
            'tags': tagrole, 'description': descrole, 'question': questrole,
            'centrality': role}
    # the question's knob sets the question's role and moves no other
    for tagrole, descrole in ROLE_PAIRS:
        plans = [V.walk_roles(role_flags(tagrole, descrole, questrole)) for questrole in ROLES]
        assert [plan.pop('question') for plan in plans] == list(ROLES)
        assert plans[0] == plans[1]


def test_one_tag_list_is_embedded_once_per_role_its_comparisons_need(monkeypatch):
    inputs = arm_inputs()
    seen = arm(monkeypatch, inputs)            # installs the recording cosine functions
    prep = toy_prepared(inputs)
    listed = ['described 0', 'described 1', 'described 2']
    together, alone = 'with the description', 'alone'
    expected = {
        # the tags alone in the passage role, and beside the description in the query role
        ('passage', 'query'): ([('Sought content', tuple(listed), 'query')],
                               [('described 0', tuple(listed), 'passage')],
                               {'query': f'query {together}', 'passage': f'passage {alone}'}),
        ('passage', 'passage'): ([('Sought content', tuple(listed), 'passage')], [],
                                 {'passage': f'passage {together}'}),
        ('query', 'query'): ([('Sought content', tuple(listed), 'query')], [],
                             {'query': f'query {together}'}),
        # the description alone in the passage role, and beside the tags in the query role
        ('query', 'passage'): ([('Sought content', tuple(listed), 'query')],
                               [('Sought content', (), 'passage')],
                               {'query': f'query {together}', 'passage': f'passage {alone}'})}
    assert set(expected) == set(ROLE_PAIRS)
    for (tagrole, descrole), (tag_calls, text_calls, by_role) in expected.items():
        # the question is no text of a tag list: its role embeds nothing here, either way
        for questrole in ROLES:
            del seen['tag_calls'][:], seen['text_calls'][:]
            roles = V.walk_roles(role_flags(tagrole, descrole, questrole))
            matrices, used, recipe = V._walk_cosines('Sought content', listed, prep, roles)
            assert seen['tag_calls'] == tag_calls and seen['text_calls'] == text_calls
            assert used.tokens_in == len(tag_calls) + len(text_calls)
            wanted = role_query(inputs, tagrole, descrole, questrole)
            assert same(matrices['query_tag_cosines'], wanted['cosines'][:3])
            assert same(matrices['query_description_cosines'], wanted['d_description'])
            assert same(matrices['query_tag_description_cosines'],
                        wanted['description_cosines'][:3])
            assert recipe == {'vector_sha256': by_role[tagrole],
                              'vector_sha256_by_role': by_role}
    # no tag in the list: nothing to embed in the tags' own role
    del seen['tag_calls'][:], seen['text_calls'][:]
    roles = V.walk_roles(role_flags('passage', 'query', 'passage'))
    matrices, used, recipe = V._walk_cosines('Sought content', [], prep, roles)
    assert seen['tag_calls'] == [('Sought content', (), 'query')] and seen['text_calls'] == []
    assert matrices['query_tag_cosines'].shape == (0, 50)


def test_the_arm_hands_the_chain_each_comparison_from_its_role(monkeypatch):
    inputs = arm_inputs()
    chunks = inputs['chunk_ids']
    orders = {}
    for tagrole, descrole, questrole in ROLE_TRIPLES:
        where = (tagrole, descrole, questrole)
        env = role_env(*where)
        seen = arm(monkeypatch, inputs, env)
        (call,) = seen['chain_calls']
        wanted = role_query(inputs, *where)
        for name, value in wanted.items():
            assert same(call['query'][name], value), (where, name)
        # the raw question is embedded once, alone, in the role its knob says; under query with
        # no role named, the three-argument call
        asked = ('placeholder question', (), questrole)
        assert [c for c in seen['calls'] if 'placeholder question' in (c[0],) + c[1]] == [asked]
        assert asked in seen['text_calls']
        assert seen['arguments'][seen['calls'].index(asked)] == (3 if questrole == 'query'
                                                                 else 4)
        texts_meta = seen['out'].meta['interpreter']['texts']
        assert texts_meta['question']['embedding'] == f'{questrole} alone'
        assert 'embedding_by_role' not in texts_meta['question']
        # every other call is the one the tags' and the description's knobs give, whatever the
        # question's knob says
        other_role = {'passage': 'query', 'query': 'passage'}[questrole]
        other = arm(monkeypatch, inputs, role_env(tagrole, descrole, other_role))
        assert [c for c in seen['calls'] if c != asked] == [
            c for c in other['calls'] if c != ('placeholder question', (), other_role)]
        expected = direct(inputs, *where)
        assert seen['rows'] == [chunks[i] for i in expected['order']]
        d = seen['out'].meta['diagnostics']
        assert d['embedding_roles'] == V.walk_roles(role_flags(*where))
        active = seen['out'].meta['policy']['knobs_recorded']['active']
        assert {name: active[name] for name in ROLE_ENVS} == env
        assert d['chain_switches'] == {} and d['alternatives_selected'] == {}
        orders[where] = tuple(expected['order'])
    # on this toy graph the eight role combinations give eight orders
    assert len(orders) == 8 and len(set(orders.values())) == 8
    # with no role knob set the arm runs the three at passage
    unset = arm(monkeypatch, inputs)
    assert unset['rows'] == [chunks[i] for i in orders['passage', 'passage', 'passage']]
    assert unset['out'].meta['diagnostics']['embedding_roles'] == V.walk_roles(
        role_flags('passage', 'passage', 'passage'))


def served(role, text, dim=12):
    """The toy embedder's float32 unit row for a text in a role. Every row leans on one shared
    direction, so any two texts have a positive cosine."""
    seed = int.from_bytes(hashlib.sha256(f'{role}|{text}'.encode('utf-8')).digest()[:8], 'big')
    raw = np.random.default_rng(seed).normal(size=dim) + 2. * np.eye(dim)[0]
    return (raw / np.linalg.norm(raw)).astype(np.float32)


def embedded(role, text):
    """That row as `_query_cosines` holds it: normalised again in float64."""
    row = served(role, text).astype(np.float64)
    return row / np.linalg.norm(row)


def toy_embedder(monkeypatch):
    """`harness.embed._embed` replaced by `served`, every call logged as (role, texts)."""
    from harness import embed
    log = []

    def _embed(texts, input_type, batch=1, bar=True):
        if input_type not in embed.EMBED_PREFIX:
            raise ValueError(f'input_type must be one of {sorted(embed.EMBED_PREFIX)}')
        log.append((input_type, tuple(texts)))
        return (np.array([served(input_type, t) for t in texts], dtype=np.float32),
                len(texts), 0, 0, 0.)

    monkeypatch.setattr(embed, '_embed', _embed)
    for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'OMP_NUM_THREADS',
                 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        monkeypatch.setenv(name, os.environ.get(name, '4'))
    return log


def vector_prepared(inputs, **changes):
    """The toy prepared with tag and chunk description vectors of the toy embedder's size."""
    rng = np.random.default_rng(31)

    def unit(matrix):
        return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)

    return toy_prepared(inputs, tag_vectors=unit(rng.normal(size=(50, 12))),
                        chunk_vectors=unit(rng.normal(size=(80, 12))), **changes)


def every_sort_prepared(inputs):
    """`vector_prepared` with the layers the sorts other than walk read, and what the landing
    returns to a sort that reads one."""
    rows = tuple({'chunkId': c, 'relpath': f'products/f{i % 4}.json'}
                 for i, c in enumerate(inputs['chunk_ids']))
    prep = vector_prepared(inputs, chunk_rows=rows)
    scores = np.random.default_rng(41).normal(size=(inputs['edge_tag'].size, 5))
    prep = V.Prepared(**{
        **prep.__dict__,
        'rank_layer': V.R4.build_layer(prep.edge_pos, scores, prep.edge_topic, 1.),
        'strength_layer': V._strength_layer(rows, prep.edge_tag, prep.edge_chunk,
                                            prep.edge_topic, prep.multikey_layer.values,
                                            prep.casefold_eligible, prep.structure)})
    return prep, (np.zeros(80, dtype=np.int64), {'mode': 'a test area'})


TEXTS = {'description': 'Sought content', 'question': 'placeholder question',
         'listed': ('described 0', 'described 1', 'described 2'), 'asked': ('asked',)}
# The embedder's calls of a sort that reads both tag lists with no role knob: each list beside
# the description, the question alone between them, everything in the query role.
QUERY_ROLE_CALLS = [('query', (*TEXTS['listed'], TEXTS['description'])),
                    ('query', (TEXTS['question'],)),
                    ('query', (*TEXTS['asked'], TEXTS['description']))]


def test_the_shared_cosine_function_embeds_in_the_query_role_unless_a_role_is_named(
        monkeypatch):
    from arms import artefact_facet_joint as J
    log = toy_embedder(monkeypatch)
    prep = vector_prepared(arm_inputs())
    listed = list(TEXTS['listed'])
    plain, used, recipe = J._query_cosines('Sought content', listed, prep)
    named, _, same_recipe = J._query_cosines('Sought content', listed, prep, 'query')
    other, _, passage_recipe = J._query_cosines('Sought content', listed, prep, 'passage')
    assert log == [('query', (*listed, 'Sought content')), ('query', (*listed, 'Sought content')),
                   ('passage', (*listed, 'Sought content'))]
    assert recipe == same_recipe
    assert recipe['input_type'] == 'query' and recipe['prefix'] == 'query: '
    assert passage_recipe['input_type'] == 'passage' and passage_recipe['prefix'] == 'passage: '
    assert recipe['vector_sha256'] != passage_recipe['vector_sha256']
    for name in plain:
        assert same(plain[name], named[name]) and not same(plain[name], other[name])
    tags = np.array([embedded('query', t) for t in listed])
    assert np.allclose(plain['query_tag_cosines'], tags @ prep.tag_vectors.T, atol=1e-12)
    assert np.allclose(other['query_description_cosines'],
                       embedded('passage', 'Sought content') @ prep.chunk_vectors.T, atol=1e-12)
    with pytest.raises(ValueError):
        J._query_cosines('Sought content', listed, prep, 'document')
    # the centrality wrapper: the query role with no role named, through a three-argument call
    del log[:]
    V._query_cosines_and_centrality('Sought content', listed, prep)
    V._query_cosines_and_centrality('Sought content', listed, prep, 'passage')
    assert [role for role, _ in log] == ['query', 'passage']
    assert inspect.signature(J._query_cosines).parameters['role'].default == 'query'
    assert inspect.signature(V._query_cosines_and_centrality).parameters['role'].default == 'query'
    # the toy embedder is a stand-in: none of its rows is kept on the side or read from there
    assert recipe['kept_on_the_side'] is None and passage_recipe['kept_on_the_side'] is None


def test_a_row_kept_on_the_side_is_served_to_its_own_role_only(monkeypatch, tmp_path):
    from arms import artefact_facet_joint as J
    from harness import embed
    log = toy_embedder(monkeypatch)
    # the rows of the harness's own embedder are the ones kept: the toy stands as it here
    monkeypatch.setattr(embed._embed, '__module__', 'harness.embed')
    monkeypatch.setattr(J, 'EMBED_KEEP', tmp_path)
    texts = ['described 0', 'Sought content']

    def name(role, text):
        prefixed = embed.EMBED_PREFIX[role] + text
        return hashlib.sha256(prefixed.encode('utf-8')).hexdigest() + '.npy'

    first = J._embed_kept(embed, texts, 'passage')
    assert log == [('passage', tuple(texts))]
    assert first[1] == 2 and first[5] == {'served': 0, 'embedded': 2}
    (folder,) = tmp_path.iterdir()
    assert folder.name == (f'{embed.EMBED_MODEL.replace("/", "__")}@{embed.EMBED_REVISION[:12]}'
                           f'__{embed.EMBED_DTYPE}__{embed.EMBED_DEVICE}')
    # one file a text, named by the role's prefix and the text, the text not in it
    assert {p.name for p in folder.iterdir()} == {name('passage', t) for t in texts}
    assert all(b'described' not in p.read_bytes() and b'Sought' not in p.read_bytes()
               for p in folder.iterdir())
    # the same texts in the other role: no row of the passage role is served for them
    other = J._embed_kept(embed, texts, 'query')
    assert log[-1] == ('query', tuple(texts)) and other[5] == {'served': 0, 'embedded': 2}
    assert {p.name for p in folder.iterdir()} == {name(role, t) for role in ROLES for t in texts}
    assert not np.allclose(first[0], other[0], atol=1e-3)
    # asked again each role is served its own rows, bit for bit, and nothing is embedded
    del log[:]
    for role, rows in (('passage', first[0]), ('query', other[0])):
        again = J._embed_kept(embed, texts, role)
        assert again[0].dtype == np.float32 and np.array_equal(again[0], rows)
        assert again[1:5] == (0, 0, 0, 0.) and again[5] == {'served': 2, 'embedded': 0}
        assert np.array_equal(again[0], [served(role, t) for t in texts])
    assert log == []
    # a new text beside a kept one: the new one alone reaches the embedder
    mixed = J._embed_kept(embed, ['asked', 'described 0'], 'passage')
    assert log == [('passage', ('asked',))] and mixed[5] == {'served': 1, 'embedded': 1}
    assert np.array_equal(mixed[0], [served('passage', 'asked'), served('passage', 'described 0')])
    # a file that holds no unit float32 row is embedded again and written again
    kept = folder / name('passage', 'asked')
    for damaged in (b'not an array', None):
        if damaged is None:
            np.save(kept, np.ones(12, dtype=np.float32))
        else:
            kept.write_bytes(damaged)
        del log[:]
        again = J._embed_kept(embed, ['asked'], 'passage')
        assert log == [('passage', ('asked',))] and again[5] == {'served': 0, 'embedded': 1}
        assert np.array_equal(np.load(kept), served('passage', 'asked'))
    assert not [p for p in folder.iterdir() if p.suffix != '.npy']
    # through the shared cosine function each role's cosines come from its own kept rows
    prep = vector_prepared(arm_inputs())
    del log[:]
    by_role = {role: J._query_cosines('Sought content', ['described 0'], prep, role)
               for role in ROLES}
    assert log == []
    for role, (matrices, used, recipe) in by_role.items():
        assert recipe['input_type'] == role and used.calls == 0
        assert recipe['kept_on_the_side'] == {'served': 2, 'embedded': 0}
        assert np.allclose(matrices['query_tag_cosines'],
                           embedded(role, 'described 0') @ prep.tag_vectors.T, atol=1e-12)
        assert np.allclose(matrices['query_description_cosines'],
                           embedded(role, 'Sought content') @ prep.chunk_vectors.T, atol=1e-12)
    assert not np.allclose(by_role['passage'][0]['query_tag_cosines'],
                           by_role['query'][0]['query_tag_cosines'], atol=1e-6)
    # another process has a row's file open while this one writes it: nothing is raised, what
    # is on disk stays, a file that is not a whole row is not served, no half-written file stays
    kept = folder / name('passage', 'asked')
    row = served('passage', 'asked')

    def held(source, target):
        raise PermissionError(13, 'the file is open in another process', str(target))

    with monkeypatch.context() as patch:
        patch.setattr(J.os, 'replace', held)
        J._keep_row(kept, served('query', 'asked'))
        assert np.array_equal(np.load(kept), row)
        J._keep_row(folder / name('passage', 'held and never whole'), row)
        assert not (folder / name('passage', 'held and never whole')).exists()
        kept.write_bytes(b'half a row')
        J._keep_row(kept, row)
        assert kept.read_bytes() == b'half a row' and J._kept_row(kept) is None
        kept.write_bytes(b'')
        assert J._kept_row(kept) is None
        assert not [p for p in folder.iterdir() if p.suffix != '.npy']
    J._keep_row(kept, row)
    assert np.array_equal(np.load(kept), row)
    assert not (folder / name('passage', 'held and never whole')).exists()
    # a stand-in embedder is called as it is: nothing read, nothing written
    monkeypatch.setattr(embed._embed, '__module__', __name__)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    plain = J._embed_kept(embed, ['described 0', 'never kept'], 'passage')
    assert log == [('passage', ('described 0', 'never kept'))] and plain[5] is None
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def test_each_role_reaches_the_embedder_for_its_own_comparison_and_no_other(monkeypatch):
    inputs = arm_inputs()
    log = toy_embedder(monkeypatch)
    prep = vector_prepared(inputs)
    description, question = TEXTS['description'], TEXTS['question']
    listed, asked = TEXTS['listed'], TEXTS['asked']
    # per the tags' and the description's role, the embedder's calls before and after the
    # question's own
    around = {
        ('query', 'query'): ([('query', (*listed, description))],
                             [('query', (*asked, description))]),
        # the tags twice: beside the description in the query role, alone in the passage role
        ('passage', 'query'): ([('query', (*listed, description)), ('passage', listed)],
                               [('query', (*asked, description)), ('passage', asked)]),
        ('passage', 'passage'): ([('passage', (*listed, description))],
                                 [('passage', (*asked, description))]),
        # the description twice: beside the tags in the query role, alone in the passage role
        ('query', 'passage'): ([('query', (*listed, description)), ('passage', (description,))],
                               [('query', (*asked, description)), ('passage', (description,))])}
    assert set(around) == set(ROLE_PAIRS)
    other = {'passage': 'query', 'query': 'passage'}
    for tagrole, descrole, questrole in ROLE_TRIPLES:
        where = (tagrole, descrole, questrole)
        before, after = around[tagrole, descrole]
        del log[:]
        seen = arm(monkeypatch, inputs, role_env(*where), prep=prep, embedder=True)
        # the question's text reaches the embedder once, alone, in the role its knob says; every
        # other text in the roles the two other knobs give it, whatever the question's knob says
        assert log == before + [(questrole, (question,))] + after, where
        assert [role for role, texts in log if question in texts] == [questrole]
        in_role = {role: {t for r, texts in log if r == role for t in texts} for role in ROLES}
        if where == ('passage', 'query', 'query'):
            # the passage role reaches the embedder for the tags and for nothing else
            assert in_role['passage'] == set(listed + asked)
        if where == ('query', 'passage', 'query'):
            # here for the description and for nothing else
            assert in_role['passage'] == {description}
        if where == ('query', 'query', 'passage'):
            # here for the question and for nothing else
            assert in_role['passage'] == {question}
        if where == ('passage', 'passage', 'query'):
            # and here the query role for the question and for nothing else
            assert in_role['query'] == {question}
        if where == ('passage', 'passage', 'passage'):
            assert in_role['query'] == set()
            assert in_role['passage'] == set(listed + asked) | {description, question}
        if where == ('query', 'query', 'query'):
            assert in_role['passage'] == set() and log == QUERY_ROLE_CALLS
        central = 'passage' if tagrole == descrole == 'passage' else 'query'
        (call,) = seen['chain_calls']
        query = call['query']
        tags = listed + asked
        assert np.allclose(query['cosines'], np.array([embedded(tagrole, t) for t in tags])
                           @ prep.tag_vectors.T, atol=1e-12)
        assert np.allclose(query['d_description'],
                           embedded(descrole, description) @ prep.chunk_vectors.T, atol=1e-12)
        assert np.allclose(query['d_question'],
                           embedded(questrole, question) @ prep.chunk_vectors.T, atol=1e-12)
        assert np.allclose(query['description_cosines'],
                           [embedded(central, t) @ embedded(central, description)
                            for t in tags], atol=1e-12)
        # no comparison is fed from the other role's vectors
        assert not np.allclose(query['cosines'],
                               np.array([embedded(other[tagrole], t) for t in tags])
                               @ prep.tag_vectors.T, atol=1e-6)
        assert not np.allclose(query['d_description'],
                               embedded(other[descrole], description) @ prep.chunk_vectors.T,
                               atol=1e-6)
        assert not np.allclose(query['d_question'],
                               embedded(other[questrole], question) @ prep.chunk_vectors.T,
                               atol=1e-6)
        assert not np.allclose(query['description_cosines'],
                               [embedded(other[central], t)
                                @ embedded(other[central], description) for t in tags],
                               atol=1e-6)
        roles = seen['out'].meta['diagnostics']['embedding_roles']
        assert roles == {'tags': tagrole, 'description': descrole, 'question': questrole,
                         'centrality': central}
        by_role = seen['out'].meta['interpreter']['texts']['description']['embedding_by_role']
        assert set(by_role) == {tagrole, descrole, central}


def test_every_other_sort_embeds_in_the_query_role_whatever_the_role_knobs_say(monkeypatch):
    inputs = arm_inputs()
    log = toy_embedder(monkeypatch)
    prep, area = every_sort_prepared(inputs)
    both = QUERY_ROLE_CALLS
    one = both[:2]
    wanted = {'strength': both, 'multikey': both, 'adjust_lower': both, 'multirank': one,
              'concept': one, 'chain': one, 'sum': one}
    assert set(wanted) == set(V.SORT_MODES) - {'walk'}
    # no role knob set, and the eight combinations of the three
    settings = [{}] + [role_env(*where) for where in ROLE_TRIPLES]
    for sort, expected in wanted.items():
        runs = []
        for roles in settings:
            del log[:]
            seen = arm(monkeypatch, inputs, {'HERB_V4_SORT': sort, 'HERB_V4_STRUCT_AT': 'off',
                                             **roles}, prep=prep, embedder=True, area=area)
            # every text in the query role, the question's among them
            assert log == expected, (sort, roles)
            assert {role for role, _ in log} == {'query'}
            assert 'embedding_roles' not in seen['out'].meta['diagnostics']
            runs.append(seen['rows'])
        assert len(runs) == 9 and all(run == runs[0] for run in runs)
        assert len(set(runs[0])) == 80


def test_the_tool_embeds_the_query_as_the_arm_does_in_every_role_combination(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'tools'))
    import walkthrough as TOOL
    inputs = arm_inputs()
    log = toy_embedder(monkeypatch)
    prep = vector_prepared(inputs)
    query = Q.parse('placeholder question', toy_answer(inputs))
    for where in ROLE_TRIPLES:
        env = role_env(*where)
        del log[:]
        seen = arm(monkeypatch, inputs, env, prep=prep, embedder=True)
        (call,) = seen['chain_calls']
        by_the_arm = list(log)
        del log[:]
        # the knobs the arm ran under are still set: the tool reads the same three
        roles, arrays, calls = TOOL.embed_query_side(V, query, prep)
        assert log == by_the_arm, where
        assert [role for role, texts in log if TEXTS['question'] in texts] == [where[2]]
        assert roles == seen['out'].meta['diagnostics']['embedding_roles']
        assert same(arrays['query_tag_cosines'], call['query']['cosines'])
        assert same(arrays['query_tag_description_cosines'], call['query']['description_cosines'])
        assert same(arrays['d_description'], call['query']['d_description'])
        assert same(arrays['d_question'], call['query']['d_question'])
        assert calls == sum(len(texts) for _, texts in by_the_arm) == seen['out'].retrieval.calls
        assert TOOL.knobs_read(V) == {'HERB_V4_OFFLINE': 'off', **env}


def test_the_three_role_knobs_at_query_run_the_walk_of_the_runs_before_it_had_them(monkeypatch):
    inputs = arm_inputs()
    chunks = inputs['chunk_ids']
    at_query = role_env('query', 'query', 'query')
    layer = WK.build_layer(inputs)
    # the chain's query from the query-role cosines alone, under the names they had before a
    # role was read: no role builds it
    old_query = toy_query(inputs)
    listed = ('described 0', 'described 1', 'described 2')
    variants = [('PROPOSAL', {}, {})] + [
        (alternative, {env: value}, WK.ALTERNATIVES[alternative])
        for (env, value), alternative in ALTERNATIVE_OF.items()]
    orders = {}
    for name, env, switches in variants:
        old = CHAIN(layer, old_query, V.COS_NOISE, **switches)
        seen = arm(monkeypatch, inputs, {**at_query, **env})
        # the three cosine calls of a sort that reads both tag lists, each in the query role,
        # the question's the three-argument call with no role named
        assert seen['calls'] == [('Sought content', listed, 'query'),
                                 ('placeholder question', (), 'query'),
                                 ('Sought content', ('asked',), 'query')], name
        assert seen['tag_calls'] == [seen['calls'][0], seen['calls'][2]]
        assert seen['text_calls'] == [seen['calls'][1]] and seen['arguments'][1] == 3
        assert seen['out'].retrieval.tokens_in == 3
        (call,) = seen['chain_calls']
        assert call['switches'] == switches
        assert set(call['query']) == set(old_query)
        for key, value in old_query.items():
            assert same(call['query'][key], value), (name, key)
        # the whole order and every chunk's strength are that chain's
        assert seen['rows'] == [chunks[i] for i in old['order']], name
        assert len(seen['rows']) == len(set(seen['rows'])) == 80
        assert same(call['run']['S_prime'], old['S_prime']), name
        top = old['order'][:12]
        ranking = seen['out'].meta['ranking']
        assert ranking['delivered_chunk_ids'] == [chunks[i] for i in top]
        assert ranking['delivered_strength'] == old['S_prime'][top].tolist()
        d = seen['out'].meta['diagnostics']
        assert d['embedding_roles'] == {'tags': 'query', 'description': 'query',
                                        'question': 'query', 'centrality': 'query'}
        assert d['chain_switches'] == switches
        texts_meta = seen['out'].meta['interpreter']['texts']
        assert texts_meta['description']['embedding'] == 'query with the description'
        assert texts_meta['description']['embedding_by_role'] == {
            'query': 'query with the description'}
        assert texts_meta['question']['embedding'] == 'query alone'
        orders[name] = tuple(old['order'])
    # the PROPOSAL and the sixteen alternatives: seventeen orders on the query-role cosines,
    # and the default roles give another than the PROPOSAL's
    assert len(orders) == 17 and len(set(orders.values())) == 17
    assert orders['PROPOSAL'] == tuple(direct(inputs, 'query', 'query', 'query')['order'])
    assert orders['PROPOSAL'] != tuple(direct(inputs)['order'])
    # the centrality is the query role's, a negative cosine to the description as 0
    d = arm(monkeypatch, inputs, at_query)['out'].meta['diagnostics']
    assert d['query_tag_description_cosine'] == [.6, .3, .45, -.1]
    assert d['query_tag_centrality'] == pytest.approx([1., .5, .75, 0.])
    # one knob left at its default is enough to leave that walk
    for env in ROLE_ENVS:
        partly = {name: value for name, value in at_query.items() if name != env}
        assert tuple(arm(monkeypatch, inputs, partly)['rows']) != tuple(
            chunks[i] for i in orders['PROPOSAL'])


def test_at_query_the_walk_s_embedder_calls_are_those_of_a_sort_with_no_role_knob(monkeypatch):
    inputs = arm_inputs()
    log = toy_embedder(monkeypatch)
    prep, area = every_sort_prepared(inputs)
    # strength reads both tag lists and each tag's cosine to the description, as walk does, and
    # has no role knob: the calls walk made before it had one
    arm(monkeypatch, inputs, {'HERB_V4_SORT': 'strength'}, prep=prep, embedder=True, area=area)
    by_strength = list(log)
    assert by_strength == QUERY_ROLE_CALLS
    for alternative, env in [('PROPOSAL', {})] + [
            (a, {e: v}) for (e, v), a in ALTERNATIVE_OF.items()]:
        del log[:]
        seen = arm(monkeypatch, inputs, {**role_env('query', 'query', 'query'), **env},
                   prep=prep, embedder=True)
        # the texts, their order, their role and the number of calls, under every alternative
        assert log == by_strength, alternative
        assert seen['out'].retrieval.calls == sum(len(texts) for _, texts in by_strength)
    # and with no role knob set the walk embeds the same texts in the same order, in the
    # passage role
    del log[:]
    arm(monkeypatch, inputs, prep=prep, embedder=True)
    assert log == [('passage', texts) for _, texts in by_strength]


# --- the two changes built after the walk-through, in the arm --------------------

def toy_width(inputs):
    """The toy graph's probes and its self-difference as the arm measures it."""
    probes = WK.draw_probes(inputs['eligible'])
    return probes, WK.self_difference(inputs['probe_cosines'][probes], probes)


def ranked_direct(inputs, width, **switches):
    """The chain with the ranking on the layer the arm holds once the width is measured: the
    toy's facet gaps and that width, the query in the default roles."""
    layer = WK.build_layer({**inputs, 'facet_gaps': TOY_GAPS, 'self_difference': width})
    return CHAIN(layer, role_query(inputs), V.COS_NOISE, rank='picked', **switches)


def test_rank_picked_needs_the_tags_in_the_passage_role_and_refuses_before_anything_is_read(
        monkeypatch):
    inputs = arm_inputs()
    for descrole in ROLES:
        for questrole in ROLES:
            seen, prep = {}, toy_prepared(inputs)
            with pytest.raises(ValueError, match='HERB_V4_WALK_RANK=picked needs '
                                                 'HERB_V4_WALK_TAGROLE=passage'):
                arm(monkeypatch, inputs, {'HERB_V4_WALK_RANK': 'picked',
                                          **role_env('query', descrole, questrole)},
                    prep=prep, seen=seen)
            # nothing was interpreted, embedded, measured or sorted, and the layer has no width
            assert seen['interpreted'] == 0 and seen['calls'] == [] == seen['width_calls']
            assert seen['chain_calls'] == [] and 'out' not in seen and 'rows' not in seen
            assert prep.walk_layer['self_difference'] is None
            assert 'self_difference_measured' not in prep.walk_layer
            # with the tags in the passage role the same two roles run
            ran = arm(monkeypatch, inputs, {'HERB_V4_WALK_RANK': 'picked',
                                            **role_env('passage', descrole, questrole)},
                      prep=prep)
            assert len(ran['width_calls']) == 1 and len(ran['rows']) == 80
    # the knob is the walk sort's: under another sort nothing is refused and nothing measured
    other = arm(monkeypatch, inputs, {'HERB_V4_SORT': 'concept', 'HERB_V4_WALK_RANK': 'picked',
                                      **role_env('query', 'query', 'query')})
    assert other['width_calls'] == [] and len(other['rows']) == 80


def test_the_width_is_measured_once_before_the_first_ranked_question_s_clock(monkeypatch):
    inputs = arm_inputs()
    # the graph's tag names with underscores, as the graph holds them
    stored = tuple(name.replace(' ', '_') for name in inputs['graph_tags'])
    prep = toy_prepared(inputs, graph_tags=stored)
    probes, measured = toy_width(inputs)
    assert probes.tolist() == list(range(1, 50))
    assert measured == {'largest': 1. - .98, 'median': measured['median'],
                        'smallest': measured['smallest'], 'probes': 49, 'own_tag_closest': 48}
    assert .004 < measured['smallest'] < measured['median'] < .019
    late = [0.]

    class Clock:
        """The arm's clock, a thousand seconds later for every measurement of the width."""
        @staticmethod
        def perf_counter():
            return time.perf_counter() + late[0]

        def __getattr__(self, name):
            return getattr(time, name)

    def measuring():
        late[0] += 1000.

    monkeypatch.setattr(V, 'time', Clock())
    env = {'HERB_V4_WALK_RANK': 'picked'}
    # a walk question that does not rank measures nothing
    plain = arm(monkeypatch, inputs, prep=prep, on_width=measuring)
    assert plain['width_calls'] == [] and prep.walk_layer['self_difference'] is None
    assert 'self_difference_measured' not in prep.walk_layer
    assert plain['out'].meta['diagnostics']['rank'] is None
    first = arm(monkeypatch, inputs, env, prep=prep, on_width=measuring)
    (call,) = first['width_calls']
    # through the shared cosine function, in the passage role, on the probes' readable names
    # against the prepared tag vectors, before the question is interpreted or embedded
    names = tuple(inputs['graph_tags'][i] for i in probes.tolist())
    assert call['tags'] == names and call['text'] == names[0] and call['role'] == 'passage'
    assert all('_' not in name for name in names) and stored[1] == 'tag_1'
    assert call['arguments'] == 4 and type(call['axes']) is V._QueryAxes
    assert call['axes'].tag_vectors is prep.tag_vectors
    assert call['axes'].chunk_vectors is prep.chunk_vectors
    assert call['cosine_calls_before'] == 0 and call['interpreted_before'] == 0
    assert first['interpreted'] == 1 and len(first['calls']) == 3
    # the layer keeps the largest as the width and the whole measurement beside it
    layer = prep.walk_layer
    recorded = {**measured, 'role': 'passage', 'seed': 20261005,
                'embedding': 'the probes in the passage role', 'embedded_now': 49,
                'embedding_seconds': 1000.}
    assert layer['self_difference'] == measured['largest'] == 1. - .98
    assert layer['self_difference_measured'] == recorded
    # the measurement is no part of the question: not in its usage, not in its search time
    out = first['out']
    assert late[0] == 1000. and out.search_time_s < 500.
    assert out.retrieval.tokens_in == 3 and out.retrieval.time_s < 500.
    assert out.meta['diagnostics']['rank']['self_difference'] == recorded
    # the second question measures nothing and ranks inside the same width
    second = arm(monkeypatch, inputs, env, prep=prep, on_width=measuring)
    assert second['width_calls'] == [] and late[0] == 1000.
    assert layer['self_difference_measured'] == recorded and second['rows'] == first['rows']
    assert second['out'].meta['diagnostics']['rank'] == out.meta['diagnostics']['rank']
    assert second['rows'] != plain['rows']
    # asked for again the kept measurement is handed back
    assert V._walk_width(prep) is layer['self_difference_measured']
    assert late[0] == 1000.
    with pytest.raises(ValueError, match='walk needs the prepared walk layer'):
        V._walk_width(toy_prepared(inputs, walk_layer=None))


def test_the_arm_ranks_inside_the_measured_width_and_records_the_ranking(monkeypatch):
    inputs = arm_inputs()
    chunks = inputs['chunk_ids']
    probes, measured = toy_width(inputs)
    width = measured['largest']
    seen = arm(monkeypatch, inputs, {'HERB_V4_WALK_RANK': 'picked'})
    out = seen['out']
    expected = ranked_direct(inputs, width)
    (call,) = seen['chain_calls']
    # the chain ran once, the ranking its one exchanged step, on the prepared layer with the
    # four gaps of prepare and the measured width
    assert call['switches'] == {'rank': 'picked'}
    assert call['layer']['self_difference'] == width
    assert same(call['layer']['facet_class'],
                WK.build_layer({**inputs, 'facet_gaps': TOY_GAPS})['facet_class'])
    assert seen['rows'] == [chunks[i] for i in expected['order']]
    assert len(set(seen['rows'])) == 80
    for name in ('S_prime', 'T', 'w', 'edge_class', 'edge_place', 'winner', 'win_edge'):
        assert same(call['run'][name], expected[name]), name
    # another order than without the ranking, the question's own calls the same three
    unranked = arm(monkeypatch, inputs)
    assert seen['rows'] != unranked['rows'] and seen['calls'] == unranked['calls']
    assert unranked['out'].meta['diagnostics']['rank'] is None
    d = out.meta['diagnostics']
    assert d['chain_switches'] == {'rank': 'picked'}
    assert d['alternatives_selected'] == {'HERB_V4_WALK_RANK': 'C3r'}
    active = out.meta['policy']['knobs_recorded']['active']
    assert active['HERB_V4_WALK_RANK'] == 'picked' and active['HERB_V4_WALK_TAGROLE'] == 'passage'
    # the row records the width, its measurement, each query tag's edges in its closest class
    # and where each credited row's winning edge stood
    top = expected['order'][:12]
    rank = d['rank']
    assert list(rank) == ['equal_width_per_query_tag', 'equal_share_of_the_closest',
                          'same_thing_level', 'self_difference', 'picked_edges_per_query_tag',
                          'delivered_winning_edge_class', 'delivered_winning_edge_place']
    assert rank['equal_width_per_query_tag'] == [width] * 4 and width == 1. - .98
    assert rank['equal_share_of_the_closest'] is None and rank['same_thing_level'] is None
    assert rank['self_difference'] == {
        **measured, 'role': 'passage', 'seed': 20261005,
        'embedding': 'the probes in the passage role', 'embedded_now': 49,
        'embedding_seconds': 1000.}
    assert rank['picked_edges_per_query_tag'] == (expected['edge_class'] == 0).sum(
        axis=1).tolist()
    assert len(rank['picked_edges_per_query_tag']) == 4
    winner, edge = expected['winner'], expected['win_edge']
    assert (edge[top] >= 0).all()
    assert rank['delivered_winning_edge_class'] == [
        int(expected['edge_class'][winner[c], edge[c]]) for c in top]
    assert rank['delivered_winning_edge_place'] == [
        int(expected['edge_place'][winner[c], edge[c]]) for c in top]
    assert len(set(zip(rank['delivered_winning_edge_class'],
                       rank['delivered_winning_edge_place']))) > 1
    assert rank == V.walk_meta(call['layer'], expected, top, {'rank': 'picked'})['rank']
    assert V.walk_meta(call['layer'], direct(inputs), top, {})['rank'] is None
    json.dumps(asdict(out), ensure_ascii=False, allow_nan=False)
    # the terms still add up to the strength
    ranking = out.meta['ranking']
    assert ranking['delivered_strength'] == expected['S_prime'][top].tolist()
    assert [sum(ranking['delivered_terms'][name][i] for name in ranking['delivered_terms'])
            for i in range(12)] == pytest.approx(ranking['delivered_strength'], abs=1e-12)
    # beside the shares off the four facets are that ranking and nothing else
    off = arm(monkeypatch, inputs, {'HERB_V4_WALK_RANK': 'picked', 'HERB_V4_WALK_SHARES': 'off'})
    (call,) = off['chain_calls']
    assert call['switches'] == {'share': 'none', 'rank': 'picked'}
    assert off['rows'] == [chunks[i] for i in ranked_direct(inputs, width, share='none')['order']]
    assert off['rows'] != seen['rows']
    assert off['out'].meta['diagnostics']['alternatives_selected'] == {
        'HERB_V4_WALK_SHARES': 'A3b', 'HERB_V4_WALK_RANK': 'C3r'}
    # a walk layer built without the facet gaps cannot rank
    prep = toy_prepared(inputs)
    bare = V._walk_layer(prep.chunk_ids, prep.chunk_kinds, prep.edge_tag, prep.edge_chunk,
                         prep.edge_topic, prep.multikey_layer.values, prep.casefold_eligible,
                         prep.structure)
    assert bare['facet_class'] is None
    with pytest.raises(ValueError, match='the ranking needs a layer built with the facet gaps'):
        arm(monkeypatch, inputs, {'HERB_V4_WALK_RANK': 'picked'},
            prep=toy_prepared(inputs, walk_layer=bare))


def test_the_width_reaches_the_embedder_once_as_the_probes_names_in_the_passage_role(
        monkeypatch):
    inputs = arm_inputs()
    log = toy_embedder(monkeypatch)
    stored = tuple(name.replace(' ', '_') for name in inputs['graph_tags'])
    prep = vector_prepared(inputs, graph_tags=stored)
    env = {'HERB_V4_WALK_RANK': 'picked'}
    # the tags' role at query: refused before the embedder is reached
    with pytest.raises(ValueError, match='needs HERB_V4_WALK_TAGROLE=passage'):
        arm(monkeypatch, inputs, {**env, 'HERB_V4_WALK_TAGROLE': 'query'}, prep=prep,
            embedder=True)
    assert log == [] and prep.walk_layer['self_difference'] is None
    seen = arm(monkeypatch, inputs, env, prep=prep, embedder=True)
    probes = WK.draw_probes(inputs['eligible'])
    names = tuple(inputs['graph_tags'][i] for i in probes.tolist())
    own_calls = [('passage', texts) for _, texts in QUERY_ROLE_CALLS]
    # first the probes' readable names, once, in the passage role; then the question's own
    # three calls
    assert log == [('passage', names)] + own_calls
    assert stored[1] == 'tag_1' and names[0] == 'tag 1'
    # each probe against the stored vector of its own tag
    cosines = np.array([embedded('passage', name) for name in names]) @ prep.tag_vectors.T
    short = 1. - cosines[np.arange(49), probes]
    measured = prep.walk_layer['self_difference_measured']
    assert measured['largest'] == pytest.approx(float(short.max()), rel=0, abs=1e-12)
    assert measured['median'] == pytest.approx(float(np.median(short)), rel=0, abs=1e-12)
    assert measured['smallest'] == pytest.approx(float(short.min()), rel=0, abs=1e-12)
    assert measured['own_tag_closest'] == int((cosines.argmax(axis=1) == probes).sum())
    assert measured['probes'] == 49 and measured['role'] == 'passage'
    assert measured['seed'] == 20261005 and measured['embedded_now'] == 49
    assert prep.walk_layer['self_difference'] == measured['largest']
    # the measurement's embedding calls are not the question's
    assert seen['out'].retrieval.calls == sum(len(texts) for _, texts in own_calls) == 7
    # the second question embeds its own texts only and gives the same order, the chain's on
    # the layer with that width
    del log[:]
    again = arm(monkeypatch, inputs, env, prep=prep, embedder=True)
    assert log == own_calls and again['rows'] == seen['rows']
    (call,) = again['chain_calls']
    layer = WK.build_layer({**inputs, 'facet_gaps': TOY_GAPS,
                            'self_difference': measured['largest']})
    ranked = CHAIN(layer, call['query'], V.COS_NOISE, rank='picked')
    assert again['rows'] == [inputs['chunk_ids'][i] for i in ranked['order']]
    assert same(call['run']['edge_place'], ranked['edge_place'])


def test_tags_off_orders_by_the_text_and_the_structure_alone_and_no_tag_wins(monkeypatch):
    inputs = arm_inputs()
    chunks = inputs['chunk_ids']
    expected = direct(inputs, chunk='none')
    seen = arm(monkeypatch, inputs, {'HERB_V4_WALK_TAGS': 'off'})
    out = seen['out']
    (call,) = seen['chain_calls']
    assert call['switches'] == {'chunk': 'none'}
    assert seen['rows'] == [chunks[i] for i in expected['order']] and len(set(seen['rows'])) == 80
    # the strength is the text's side and the structure's lifts on it
    text = WK.text_side(inputs['passage_d_description'], inputs['passage_d_question'])
    assert same(call['run']['S'], text['side']) and not call['run']['T'].any()
    d = out.meta['diagnostics']
    assert d['chain_switches'] == {'chunk': 'none'}
    assert d['alternatives_selected'] == {'HERB_V4_WALK_TAGS': 'C4n'}
    assert d['rank'] is None and seen['width_calls'] == []
    # no credited row has a tag term or a winning query tag
    top = expected['order'][:12]
    ranking = out.meta['ranking']
    assert ranking['delivered_terms']['tags'] == [0.] * 12
    assert ranking['delivered_query_tags'] == [-1] * 12
    assert ranking['delivered_strength'] == expected['S_prime'][top].tolist()
    assert [sum(ranking['delivered_terms'][name][i] for name in ('description', 'product',
                                                                 'near'))
            for i in range(12)] == pytest.approx(ranking['delivered_strength'], abs=1e-12)
    assert d['delivered_term_sums']['tags'] == 0.
    assert d['chunks_with_a_positive_tag_strength'] == 0
    json.dumps(asdict(out), ensure_ascii=False, allow_nan=False)
    # the question's texts are embedded as without the knob, and the order is another
    with_tags = arm(monkeypatch, inputs)
    assert seen['calls'] == with_tags['calls'] and seen['rows'] != with_tags['rows']
    # beside the ranking the width is measured and the tags still leave
    both = arm(monkeypatch, inputs, {'HERB_V4_WALK_TAGS': 'off', 'HERB_V4_WALK_RANK': 'picked'})
    assert len(both['width_calls']) == 1 and both['rows'] == seen['rows']
    d = both['out'].meta['diagnostics']
    assert d['alternatives_selected'] == {'HERB_V4_WALK_RANK': 'C3r',
                                          'HERB_V4_WALK_TAGS': 'C4n'}
    assert d['rank']['delivered_winning_edge_class'] == [None] * 12
    assert d['rank']['delivered_winning_edge_place'] == [None] * 12


# --- the interpretation, read from the cache only --------------------------------

def _cached_answer(folder, text, saved):
    system, user = Q.request(text)
    signature = {'cache_version': 1, 'stage': 'querytag', 'model': V.INTERPRET_MODEL,
                 'system': system, 'user': user, 'max_tries': 1}
    key = V._sha(json.dumps(signature, sort_keys=True, ensure_ascii=False))
    path = folder / 'querytag' / (key + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'signature': signature, **saved}), encoding='utf-8')
    return key


def test_walk_offline_reads_the_cached_answer_and_makes_no_model_call(monkeypatch, tmp_path):
    inputs = arm_inputs()
    prep = toy_prepared(inputs, cache_dir=tmp_path)
    # nothing cached: the question is refused before any model call
    with pytest.raises(RuntimeError, match='no model call made'):
        arm(monkeypatch, inputs, {'HERB_V4_OFFLINE': 'on'}, prep=prep, interpret=False)
    key = _cached_answer(tmp_path, 'placeholder question',
                         {'ok': True, 'raw': toy_answer(inputs), 'usage': {}})
    seen = arm(monkeypatch, inputs, {'HERB_V4_OFFLINE': 'on'}, prep=prep, interpret=False)
    out = seen['out']
    (stage,) = out.meta['interpreter']['stages']
    assert stage['cache_hit'] is True and stage['key'] == key and stage['offline'] is True
    assert out.retrieval.calls == 0 and out.generator.calls == 0
    assert seen['rows'] == [inputs['chunk_ids'][i] for i in direct(inputs)['order']]
    record = out.meta['policy']['knobs_recorded']
    assert record['active']['HERB_V4_OFFLINE'] == 'on'
    assert record['read_by_active_sort'][-1] == 'HERB_V4_OFFLINE'


# --- the arm against the walk-through, on the live graph -------------------------

LIVE_TESTS = 'HERB_LIVE_TESTS'


def _neo4j_answers():
    try:
        with socket.create_connection(('127.0.0.1', 7687), timeout=2):
            return True
    except OSError:
        return False


def _live_gate(question):
    """Skips unless HERB_LIVE_TESTS=1 asks for the live tests. With it set nothing skips: a
    querytag cache that does not hold the question's answer fails, and so does a Neo4j that
    does not answer."""
    if os.environ.get(LIVE_TESTS) != '1':
        pytest.skip(f'a live test: set {LIVE_TESTS}=1 to run it. It reads Neo4j on '
                    '127.0.0.1:7687 and the cached querytagger answer of the walk-through\'s '
                    'made-up question, loads the embedder and takes about five minutes; no '
                    'model is asked')
    try:
        V._require_cached_answer(*Q.request(question), V.cache_root())
    except RuntimeError as missing:
        pytest.fail(f'{LIVE_TESTS}=1 and the querytag cache does not hold the question: '
                    f'{missing}')
    if not _neo4j_answers():
        pytest.fail(f'{LIVE_TESTS}=1 and Neo4j does not answer on 127.0.0.1:7687')


def test_the_live_test_runs_only_when_asked_and_then_fails_instead_of_skipping(monkeypatch,
                                                                               tmp_path):
    monkeypatch.delenv(LIVE_TESTS, raising=False)
    with pytest.raises(pytest.skip.Exception, match='HERB_LIVE_TESTS=1'):
        _live_gate('placeholder question')
    monkeypatch.setenv(LIVE_TESTS, 'yes')
    with pytest.raises(pytest.skip.Exception):
        _live_gate('placeholder question')
    # asked for, and the cache does not hold the question: a failure, not a skip
    monkeypatch.setenv(LIVE_TESTS, '1')
    monkeypatch.setenv('HERB_V4_CACHE', str(tmp_path))
    with pytest.raises(pytest.fail.Exception, match='does not hold the question'):
        _live_gate('placeholder question')
    # a cached failure is no answer either
    _cached_answer(tmp_path, 'placeholder question', {'ok': False})
    with pytest.raises(pytest.fail.Exception, match='does not hold the question'):
        _live_gate('placeholder question')


def test_the_arm_s_order_for_the_made_up_question_is_the_walk_through_s(monkeypatch):
    """The made-up question of tools/walkthrough.py through the tool's own loading and
    `v4_walk.chain`, against the arm under `walk` over one prepare: every knob at its default,
    and HERB_V4_WALK_TEXT=description, the variant in which the two text cosine lists are not
    interchangeable. The whole order and every chunk's S'. Runs only with HERB_LIVE_TESTS=1;
    no model is asked."""
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'tools'))
    import walkthrough as TOOL
    for name in V.KNOB_ENV.values():
        monkeypatch.delenv(name, raising=False)
    _live_gate(TOOL.QUESTION)

    def refuse(*args, **kwargs):
        raise AssertionError('a model call in the walk live test')

    monkeypatch.setattr(chat, 'post', refuse)
    monkeypatch.setattr(V, 'RETRIEVAL_FLAGS', dict(V.RETRIEVAL_FLAGS))
    monkeypatch.setenv('HERB_V4_SORT', 'walk')
    monkeypatch.setenv('HERB_V4_OFFLINE', 'on')
    inputs, prepared, provenance = TOOL.load_live(TOOL.QUESTION)
    ids = inputs['chunk_ids']
    layer = WK.build_layer(inputs)
    query = {'cosines': inputs['query_tag_cosines'], 'readings': inputs['query_readings'],
             'description_cosines': inputs['query_tag_description_cosines'],
             'd_description': inputs['d_description'], 'd_question': inputs['d_question']}
    swapped = {**query, 'd_description': query['d_question'],
               'd_question': query['d_description']}
    variants = {'PROPOSAL': ({}, {}),
                'A5b': ({'HERB_V4_WALK_TEXT': 'description'}, {'side': 'description'})}
    try:
        outs = {}
        for name, (env, _) in variants.items():
            for knob, value in env.items():
                monkeypatch.setenv(knob, value)
            outs[name] = V.answer_one_question(('made-up', TOOL.QUESTION), prepared, None,
                                               len(ids))
    finally:
        prepared.close()
    assert provenance['model_calls_through_chat_post'] == 0 and provenance['cache_hit'] is True
    orders = {}
    for name, (env, switches) in variants.items():
        walked = WK.chain(layer, query, inputs['cos_noise'], **switches)
        out = outs[name]
        (stage,) = out.meta['interpreter']['stages']
        assert stage['cache_hit'] is True and stage['offline'] is True
        assert out.meta['diagnostics']['chain_switches'] == switches
        ranking = out.meta['ranking']
        # the whole order, every chunk once, and every chunk's S'
        assert ranking['ordered_chunk_ids'] == [ids[i] for i in walked['order']], name
        assert len(set(ranking['ordered_chunk_ids'])) == len(ids)
        assert ranking['delivered_chunk_ids'] == ranking['ordered_chunk_ids']
        assert ranking['delivered_strength'] == pytest.approx(
            walked['S_prime'][walked['order']].tolist(), rel=0, abs=1e-9), name
        orders[name] = walked['order']
        other = WK.chain(layer, swapped, inputs['cos_noise'], **switches)
        if name == 'PROPOSAL':
            # max(D, Qs) reads the two text lists alike: swapped, the strength is the same
            assert same(other['S_prime'], walked['S_prime'])
        else:
            # the description alone does not: swapped lists give another order than the arm's
            assert other['order'] != walked['order']
    assert orders['A5b'] != orders['PROPOSAL']




def test_the_corrections_of_the_2026_10_05_review_stand():
    inputs = {**arm_inputs(), 'facet_gaps': TOY_GAPS, 'self_difference': TOY_WIDTH}
    layer, query = WK.build_layer(inputs), toy_query(inputs)
    # the ranking places each edge and the per-edge correction draws from the unplaced tag fits
    with pytest.raises(ValueError):
        WK.chain(layer, query, .002, rank='picked', chunk='per_edge')
    # a layer handed its width answers without a measurement
    holder = SimpleNamespace(walk_layer={'self_difference': TOY_WIDTH})
    assert V._walk_width(holder) == {'largest': TOY_WIDTH, 'given_to_the_layer': True}
    # with the tags off the row still counts the chunks that hold an eligible edge, names the
    # tags as unread, and gives no class or place to a row no tag carries
    run = WK.chain(layer, query, .002, chunk='none', rank='picked')
    delivered = run['order'][:8]
    d = V.walk_meta(layer, run, delivered, {'chunk': 'none', 'rank': 'picked'})
    assert d['chunks_with_an_eligible_edge'] == int((layer['n_c'] > 0).sum()) > 0
    assert d['chunks_with_a_positive_tag_strength'] == 0
    assert d['not_read'] == [V.WALK_NOT_READ[('chunk', 'none')]]
    assert d['rank']['delivered_winning_edge_class'] == [None] * 8
    assert d['rank']['delivered_winning_edge_place'] == [None] * 8


def test_rank_percent_takes_its_class_from_the_closest_tag_s_own_score():
    inputs = {**arm_inputs(), 'facet_gaps': TOY_GAPS}
    layer, query = WK.build_layer(inputs), toy_query(inputs)
    eligible = layer['eligible']
    assert WK.EQUAL_SHARE == .95 and WK.CHANGES['C3p'] == {'rank': 'percent'}
    run = WK.chain(layer, query, .002, rank='percent', share='none')
    plain = WK.chain(layer, query, .002, share='none')
    cosines = np.asarray(query['cosines'], dtype=np.float64)
    for i in range(cosines.shape[0]):
        closest = cosines[i][eligible].max()
        # the width is the share of the closest tag's own score that is left, per query tag
        assert run['rank_width'][i] == pytest.approx((1. - WK.EQUAL_SHARE) * closest)
        edge_cosines = cosines[i][layer['edge_tag']]
        if closest > 0:
            assert same(run['edge_class'][i],
                        np.floor((closest - edge_cosines) / run['rank_width'][i]).astype(np.int64))
            # class 0 is every edge whose tag scores more than 95% of the closest one
            assert ((run['edge_class'][i] == 0) == (edge_cosines > WK.EQUAL_SHARE * closest)).all()
    # it needs the gaps and no measured width; without the gaps it is refused
    assert layer['self_difference'] is None
    with pytest.raises(ValueError, match='the ranking needs a layer built with the facet gaps'):
        WK.chain(WK.build_layer(arm_inputs()), query, .002, rank='percent')
    with pytest.raises(ValueError):
        WK.chain(layer, query, .002, rank='percent', chunk='per_edge')
    # the order differs from the unranked chain and is still every chunk once
    assert sorted(run['order']) == list(range(layer['chunks']))
    assert run['order'] != plain['order'] and plain['rank_width'] is None
    # a query tag whose closest tag does not score above 0 is left unranked
    low = dict(query, cosines=-np.abs(cosines))
    lowered = WK.chain(layer, low, .002, rank='percent', share='none', fit='cosine')
    unranked = WK.chain(layer, low, .002, share='none', fit='cosine')
    assert not lowered['rank_width'].any() and same(lowered['w'], unranked['w'])


def test_the_same_thing_level_is_read_off_the_tags_that_differ_in_spelling_only():
    names = ['Rollback process', 'rollback process', 'rollback processes', 'cache', 'Cache',
             'caching', 'api', 'apis', 'gas', 'ga']
    # equal once lower-cased, or once a final s is dropped from a word longer than three letters
    # (one s: 'processes' is not 'process' by this rule, and 'gas' is too short to lose its s)
    assert sorted(WK.same_thing_pairs(names)) == [(0, 1), (3, 4), (6, 7)]
    assert WK.same_thing_pairs(['alpha', 'beta']) == []
    rng = np.random.default_rng(5)
    vectors = rng.normal(size=(len(names), 6))
    eligible = np.ones(len(names), dtype=bool)
    unit = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    scores = [float(unit[a] @ unit[b]) for a, b in WK.same_thing_pairs(names)]
    got = WK.same_thing_level(names, vectors, eligible)
    assert got == {'level': pytest.approx(float(np.percentile(scores, WK.SAME_POINT))),
                   'median': pytest.approx(float(np.median(scores))), 'pairs': 3,
                   'point': WK.SAME_POINT}
    # a tag that is not eligible takes its pairs with it; with no pair there is no level
    eligible[1] = False
    assert WK.same_thing_level(names, vectors, eligible)['pairs'] == 2
    assert WK.same_thing_level(['alpha', 'beta'], vectors[:2], np.ones(2, dtype=bool)) is None


def test_rank_same_ranks_only_the_edges_of_the_tags_at_the_level_or_above():
    inputs = {**arm_inputs(), 'facet_gaps': TOY_GAPS}
    query = toy_query(inputs)
    cosines = np.asarray(query['cosines'], dtype=np.float64)
    assert WK.CHANGES['C3s'] == {'rank': 'same'}
    plain_layer = WK.build_layer(inputs)
    eligible = plain_layer['eligible']
    # a level two of the four query tags reach and two do not
    best = np.sort(cosines[:, eligible].max(axis=1))
    level = float((best[1] + best[2]) / 2.)
    layer = WK.build_layer({**inputs, 'same_level': level})
    assert layer['same_level'] == level and plain_layer['same_level'] is None
    with pytest.raises(ValueError, match='rank same needs a layer built with the same-thing level'):
        WK.chain(plain_layer, query, .002, rank='same')
    run = WK.chain(layer, query, .002, rank='same', share='none', fit='cosine')
    plain = WK.chain(layer, query, .002, share='none', fit='cosine')
    reached = 0
    for i in range(cosines.shape[0]):
        edge_cosines = cosines[i][layer['edge_tag']]
        closest = cosines[i][eligible].max()
        picked = edge_cosines >= level
        assert same(run['edge_class'][i] == 0, picked)
        if not picked.any():
            # no graph tag at the level: the query tag is left as it is
            assert same(run['w'][i], plain['w'][i])
            continue
        reached += 1
        # every other edge keeps its cosine; the picked ones lie between the level and the closest
        assert same(run['w'][i][~picked], plain['w'][i][~picked])
        placed = run['w'][i][picked]
        assert (placed > level).all() and (placed <= closest + 1e-12).all()
        assert placed.max() == pytest.approx(closest)
        # each picked edge has its own place, 0 first, and a later place a lower cosine
        places = run['edge_place'][i][picked]
        assert sorted(places.tolist()) == list(range(int(picked.sum())))
        assert same(np.argsort(places), np.argsort(-placed, kind='stable'))
        # the place follows the facet classes in the query tag's order, then topic, then cosine
        order = run['facet_orders'][i]
        keys = layer['facet_class'][picked][:, order]
        by = np.lexsort((np.flatnonzero(picked), -edge_cosines[picked], -layer['raw'][picked, 0],
                         keys[:, 3], keys[:, 2], keys[:, 1], keys[:, 0]))
        assert same(places[by], np.arange(int(picked.sum())))
    assert 0 < reached < cosines.shape[0]
    assert sorted(run['order']) == list(range(layer['chunks']))
