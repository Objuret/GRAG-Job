"""The shapes, the clustering of the scopes' totals and the cloud filter of `v4_walk`."""
import itertools

import numpy as np
import pytest

from artefact import v4_walk as WK


def test_the_four_shapes_of_one_row():
    row = np.array([1., 2., 2., 10.])
    assert WK.shaped(row, 'as_is').tolist() == [1., 2., 2., 10.]
    assert WK.shaped(row, 'unit').tolist() == [0., 1. / 9., 1. / 9., 1.]
    assert WK.shaped(row, 'order').tolist() == [0.125, 0.5, 0.5, 0.875]
    assert np.allclose(WK.shaped(row, 'spread'), WK.standing(row)[0])
    with pytest.raises(ValueError, match='Unknown shape'):
        WK.shaped(row, 'other')
    with pytest.raises(ValueError, match='all equal'):
        WK.shaped(np.ones(3), 'unit')


def _silhouette(sorted_row, label):
    """The mean silhouette by its definition, a group of one counting 0."""
    out = []
    for i, value in enumerate(sorted_row):
        own = sorted_row[label == label[i]]
        if own.size == 1:
            out.append(0.)
            continue
        a = np.abs(own - value).sum() / (own.size - 1)
        b = min(np.abs(sorted_row[label == other] - value).mean()
                for other in np.unique(label) if other != label[i])
        out.append((b - a) / max(a, b) if max(a, b) > 0 else 0.)
    return float(np.mean(out))


def test_the_clustering_is_the_best_split_by_silhouette_over_every_number_of_groups():
    rng = np.random.default_rng(1)
    for _ in range(200):
        n = int(rng.integers(4, 9))
        row = rng.normal(size=n) * rng.choice([1., 5.]) + rng.choice([0., 3.], size=n)
        ordered = np.sort(row)
        best = -np.inf
        for count in range(2, n):
            splits = []
            for cuts in itertools.combinations(range(1, n), count - 1):
                edges = (0, *cuts, n)
                spread = sum(((ordered[a:b] - ordered[a:b].mean()) ** 2).sum()
                             for a, b in zip(edges[:-1], edges[1:]))
                splits.append((spread, edges))
            _, edges = min(splits)
            best = max(best, _silhouette(ordered, np.repeat(np.arange(count), np.diff(edges))))
        group, count = WK.groups_on_the_line(row)
        assert 2 <= count < n
        got = group[np.argsort(row, kind='stable')]
        assert (np.diff(got) >= 0).all() and got[0] == 0 and got[-1] == count - 1
        assert _silhouette(ordered, got) == pytest.approx(best, abs=1e-9)


def test_two_far_totals_are_the_top_group_and_equal_totals_are_one_group():
    rng = np.random.default_rng(2)
    row = np.r_[rng.normal(0., 1., 28), 40., 41.]
    group, count = WK.groups_on_the_line(row)
    assert count == 2 and np.flatnonzero(group == 1).tolist() == [28, 29]
    group, count = WK.groups_on_the_line(np.array([3., 3., 3.]))
    assert count == 1 and not group.any()
    assert WK.groups_on_the_line(np.array([1., 2., 1., 2.]))[1] == 1


def test_a_chunk_stays_when_a_scope_it_hangs_under_is_kept_in_any_place_at_any_level():
    # Six products of two chunks; the last product's chunks are far above in the first place,
    # one chunk of the first product is far above in the second.
    first = np.r_[np.linspace(0., 1., 10), 30., 31.]
    second = np.r_[50., np.linspace(0., 1., 11)]
    products = [(f'P{k}', np.array([2 * k, 2 * k + 1])) for k in range(6)]
    halves = [(f'P{k}/a', np.array([2 * k])) for k in range(6)] + [
        (f'P{k}/b', np.array([2 * k + 1])) for k in range(6)]
    keep, record = WK.scope_clouds({'first': first, 'second': second},
                                   {'product': products, 'half': halves}, 'as_is')
    assert record['first']['product']['kept'] == ['P5']
    assert record['second']['product']['kept'] == ['P0']
    assert record['second']['half']['kept'] == ['P0/a']
    assert record['first']['product'] == {'scopes': 6, 'groups': 2, 'kept': ['P5'], 'chunks': 2}
    assert np.flatnonzero(keep).tolist() == [0, 1, 10, 11]
    with pytest.raises(ValueError, match='one number per chunk'):
        WK.scope_clouds({'first': first, 'second': second[:5]}, {'product': products}, 'as_is')


def test_the_places_and_their_numbers():
    # Three chunks, four links: chunk 0 has two links, the first a picked link of query tag 1.
    walked = {'tags': np.array([3., 1., 2.]), 'text': np.array([.5, .4, .3]),
              'D': np.array([.5, -1., .3]), 'Qs': np.array([0., .4, -2.]),
              'picked_edge': np.array([[False, False, False, False], [True, False, False, True]])}
    layer = {'chunks': 3, 'edge_chunk': np.array([0, 0, 1, 2]),
             'raw': np.array([[.2, 0], [.9, 0], [.5, 0], [-.1, 0]])}
    got = WK.place_numbers(WK.PLACE_NAMES, walked, layer, np.array([[.1, .2, .3], [.3, .4, .5]]))
    assert got['tags'] is walked['tags'] and got['description'] is walked['text']
    assert got['chunk_desc'] is walked['D'] and got['question'] is walked['Qs']
    assert got['hits'].tolist() == [1., 0., 1.]
    assert got['topic'].tolist() == [.2, 0., 0.]
    assert got['tags_to_desc'] == pytest.approx([.2, .3, .4])
    with pytest.raises(ValueError, match='Unknown place'):
        WK.place_numbers(('other',), walked, layer)
    products = [('A', np.array([0])), ('B', np.array([1])), ('C', np.array([2]))]
    keep, record = WK.scope_clouds({'tags': walked['tags'], 'hits': got['hits'] * [5., 1., 1.]},
                                   {'product': products}, {'tags': 'unit', 'hits': 'as_is'}, 2)
    assert record['tags']['product']['kept'] == ['A', 'C']
    assert record['hits']['product']['kept'] == ['A'] and keep.tolist() == [True, False, True]


def test_the_knee_and_the_levels_it_reads_off_a_list():
    assert WK.knee([10., 9., 2., 1., 0.]) == 2          # furthest below the straight line
    assert WK.knee([4., 3., 2., 1., 0.]) == 0           # a straight run has none
    assert WK.knee([5., 5., 5.]) == 0 and WK.knee([3., 1.]) == 0
    # Ten ordinary values, then a near group of four and two nearest of all.
    row = np.r_[np.linspace(0., .2, 21), .50, .51, .52, .53, .90, .91]
    level, count = WK.levels_of(row)
    assert count >= 2 and level[-2:].tolist() == [1, 1]
    assert (level[21:25] == level[21]).all() and 1 < level[21] <= count
    assert (level[:11] == 0).all()                      # at or below the middle: no level
    relevancy = WK.level_relevancy(level, count)
    assert relevancy[-1] == 1. and relevancy[0] == 0. and 0. < relevancy[21] < 1.
    assert WK.levels_of(np.linspace(0., 1., 9))[1] == 0  # a straight run: nothing is hit
    assert not WK.level_relevancy(np.zeros(4, dtype=int), 0).any()


def test_the_largest_clouds_are_kept_with_the_minorities_of_the_same_parent():
    scopes = [(f'{p}/{k}', np.array([4 * i + j, 4 * i + j + 2]))
              for i, p in enumerate('ABC') for j, k in enumerate(('x', 'y'))]
    relevancy = np.zeros(12)
    relevancy[[0, 2]] = 1.          # A/x: a cloud of 2
    relevancy[1] = .2               # A/y: a small cloud, same parent as A/x
    relevancy[8] = .1               # C/x: a small cloud under another parent
    relevancy[4] = .15              # B/x: another small one
    keep, record = WK.level_clouds(relevancy, scopes)
    assert [c['scope'] for c in record['largest']] == ['A/x']
    assert [c['scope'] for c in record['minorities']] == ['A/y']
    assert record['hit_chunks'] == 5 and record['clouds'] == 4
    assert np.flatnonzero(keep).tolist() == [0, 1, 2, 3]
    keep, record = WK.level_clouds(np.zeros(12), scopes)
    assert keep.all() and record['clouds'] == 0
    with pytest.raises(ValueError, match='non-negative'):
        WK.level_clouds(-np.ones(12), scopes)


def test_the_cluster_that_stands_apart_at_the_top():
    row = np.r_[np.linspace(0., .2, 21), .50, .51, .52, .53, .90, .91]
    assert np.flatnonzero(WK.top_cluster(row)).tolist() == [25, 26]         # the largest jump
    assert np.flatnonzero(WK.top_cluster(row, above_middle=True)).tolist() == [25, 26]
    assert not WK.top_cluster(np.linspace(0., 1., 9)).any()                 # no jump: none
    assert not WK.top_cluster(np.array([5., 1.])).any()                     # fewer than three
    assert np.flatnonzero(WK.top_cluster(np.array([1., 8., 3., 2., 1., 1.]))).tolist() == [1]
    assert np.flatnonzero(WK.top_cluster(np.array([3., 1., 3., 1., 1.]))).tolist() == [0, 2]


def test_the_two_readings_of_cluster_by_scope():
    # Three products of three scopes, four chunks a scope. Hits: A/x 4, A/y 1, A/z 1, B/x 3, C/x 1.
    scopes = [(f'{p}/{k}', np.arange(12 * i + 4 * j, 12 * i + 4 * j + 4))
              for i, p in enumerate('ABC') for j, k in enumerate('xyz')]
    hit = np.zeros(36, dtype=bool)
    hit[[0, 1, 2, 3, 4, 8, 12, 13, 14, 24]] = True
    keep, record = WK.scope_clusters(hit, scopes, formed=False)
    assert [c['cloud'] for c in record['largest']] == ['A/x', 'B/x']          # the main cluster: 4, 3
    assert record['size_clusters'] == 2
    assert sorted(c['cloud'] for c in record['minorities']) == ['A/y', 'A/z']  # same parent
    assert np.flatnonzero(keep).tolist() == list(range(12)) + [12, 13, 14, 15]  # C/x is cut
    keep, record = WK.scope_clusters(hit, scopes, formed=True)
    assert [c['cloud'] for c in record['largest']] == ['A']                    # 6 against 3 and 1
    assert record['largest'][0]['scopes'] == ['A/x', 'A/y', 'A/z'] and record['clouds'] == 3
    assert np.flatnonzero(keep).tolist() == list(range(12))
    # two sizes only: the dogleg finds no bend, one cluster, every hit scope is a largest cloud
    hit[:] = False
    hit[[0, 1, 12, 24]] = True
    keep, record = WK.scope_clusters(hit, scopes, formed=False)
    assert record['size_clusters'] == 1 and len(record['largest']) == 3
    assert np.flatnonzero(keep).tolist() == [0, 1, 2, 3, 12, 13, 14, 15, 24, 25, 26, 27]
    keep, record = WK.scope_clusters(np.zeros(36, dtype=bool), scopes, formed=True)
    assert keep.all() and record['hit_chunks'] == 0


def test_the_main_cluster_of_the_relevance_decides_what_is_hit():
    # Four chunks; the strength .9 stands alone above .2, .21 and .22. Chunks 0 and 1 carry a
    # picked edge; among them the tag value 1. stands above .1.
    layer = {'chunks': 4, 'edge_chunk': np.array([0, 1, 2])}
    walked = {'strength': np.array([.2, .21, .9, .22]), 'tags': np.array([.1, 1., .5, 0.]),
              'picked_edge': np.array([[True, False, False], [False, True, False]]),
              'pick': {'clusters': 6, 'lowest': .3}}
    hits, record = WK.cluster_hits(('relevance', 'tags', 'chunk_desc'), walked, layer,
                                   np.array([.2, .21, .9, .2]), np.array([.1, .1, .1, .1]))
    assert hits['relevance'].tolist() == [False, False, True, False]
    assert record['relevance']['clusters'] == 2 and record['relevance']['chunks'] == 1
    assert hits['tags'].tolist() == [True, True, False, False]           # two carriers: both kept
    assert hits['chunk_desc'].tolist() == [False, False, True, False]
    with pytest.raises(ValueError, match='Unknown place'):
        WK.cluster_hits(('other',), walked, layer, np.zeros(4), np.zeros(4))


def test_the_scope_is_read_off_the_picked_tags_the_facets_judged():
    # Six chunks in three scopes of two. Edges: tag 0 in chunks 0, 1, 2; tag 1 in chunk 0; tag 2
    # in chunk 4; tag 3 in chunk 5. Picked: tags 0, 1 and 2 (not 3). Closeness: .9, .8, .3, .95.
    # The first facet of both query tags is column 0; edge 2 (tag 0 in chunk 2) is outside it.
    layer = {'chunks': 6, 'edge_tag': np.array([0, 0, 0, 1, 2, 3]),
             'edge_chunk': np.array([0, 1, 2, 0, 4, 5])}
    scopes = [('A/x', np.array([0, 1])), ('A/y', np.array([2, 3])), ('B/x', np.array([4, 5]))]
    picked_edge = np.array([[True, True, True, True, False, False],
                            [False, False, False, False, True, False]])
    cosines = np.array([[.9, .8, .1, .95], [.2, .1, .3, .2]])
    facet_class = np.zeros((6, 5), dtype=np.int64)
    facet_class[2, 0] = 1
    facet_class[4, 1] = 1                                  # edge 4 is outside the second facet
    orders = np.array([[0, 1, 2, 3], [0, 1, 2, 3]])
    keep, record = WK.scope_by_tags(picked_edge, cosines, facet_class, orders, layer, scopes, 1)
    assert record['edges_surviving_by_depth'] == [4, 3, 3, 3]
    # A/x: tags 0 and 1 once each, 1.7; B/x: tag 2, .3; A/y lost its edge. Two values: the
    # dogleg finds no bend, one cluster, both scopes are kept
    assert record['scopes_with_a_tag'] == 2 and record['clusters'] == 1
    assert [r['scope'] for r in record['kept']] == ['A/x', 'B/x']
    assert record['kept'][0]['value'] == pytest.approx(1.7) and record['kept'][0]['tags'] == 2
    assert keep.tolist() == [True, True, False, False, True, True]
    keep, record = WK.scope_by_tags(np.zeros((2, 6), dtype=bool), cosines, facet_class, orders,
                                    layer, scopes)
    assert keep.all() and record['picked_edges'] == 0


def _small_tree():
    """Four products of two kinds, ten chunks a kind: 80 chunks, 12 places."""
    places = []
    for p, product in enumerate('ABCD'):
        places.append((product, np.arange(20 * p, 20 * p + 20)))
        places.append((f'{product}/x', np.arange(20 * p, 20 * p + 10)))
        places.append((f'{product}/y', np.arange(20 * p + 10, 20 * p + 20)))
    return places


def test_the_scan_holds_expects_and_rates_each_place():
    places = _small_tree()
    hits = [0, 1, 2, 3, 4, 5, 6, 10, 40]          # seven in A/x, one in A/y, one in C/x
    held, expected, ratios, scatters = WK.tree_scan(hits, places, 80, 200, 7)
    at = [path for path, _ in places].index
    assert held[at('A/x')] == 7 and held[at('A')] == 8 and held[at('C/x')] == 1
    assert expected[at('A/x')] == pytest.approx(9 * 10 / 80)
    assert ratios[at('A/x')] == pytest.approx(7 * np.log(7 / 1.125) + 2 * np.log(2 / 7.875))
    assert ratios[at('B')] == 0. and ratios[at('C/x')] == 0.     # no more than its share
    assert scatters.shape == (200,) and (scatters >= 0).all()
    assert (WK.tree_scan(hits, places, 80, 200, 7)[3] == scatters).all()   # the seed fixes it


def test_the_places_where_the_hits_gather_are_kept_with_their_minorities():
    places = _small_tree()
    keep, record = WK.scan_clouds([0, 1, 2, 3, 4, 5, 6, 10, 40], places, 80, 999, 7)
    assert [c['place'] for c in record['clouds']] == ['A/x']        # A holds A/x: left out
    assert record['clouds'][0]['hits'] == 7 and record['hits'] == 9
    assert record['minorities'] == [{'place': 'A/y', 'hits': 1}]    # same parent as A/x
    assert np.flatnonzero(keep).tolist() == list(range(20))          # C/x is cut
    assert record['clouds'][0]['ratio'] > record['largest_scatter_ratio'] > 0


def test_scattered_hits_or_no_hits_cut_nothing():
    places = _small_tree()
    keep, record = WK.scan_clouds([0, 10, 20, 30, 40, 50, 60, 70], places, 80, 999, 7)
    assert record['clouds'] == [] and keep.all()
    keep, record = WK.scan_clouds([], places, 80, 999, 7)
    assert record['clouds'] == [] and record['hits'] == 0 and keep.all()
    with pytest.raises(ValueError, match='out of range'):
        WK.scan_clouds([80], places, 80, 10, 7)


def test_a_fixed_two_is_the_least_squares_split_in_two():
    row = np.array([0., 1., 2., 10., 11., 30.])
    group, count = WK.groups_on_the_line(row, 2)
    assert count == 2 and group.tolist() == [0, 0, 0, 0, 0, 1]
    with pytest.raises(ValueError, match='fixed number of groups'):
        WK.groups_on_the_line(row, 6)
    products = [(f'P{k}', np.array([k])) for k in range(6)]
    keep, record = WK.scope_clouds({'only': row}, {'product': products}, 'as_is', 2)
    assert record['only']['product']['kept'] == ['P5'] and keep.tolist() == [False] * 5 + [True]
