import numpy as np
import pytest

from artefact import v4_walk as WK


def toy(seed, chunks=40, tags=30):
    """A small random graph; tags 0 and 1 are not eligible, and chunk 9 carries no edge."""
    rng = np.random.default_rng(seed)
    eligible = np.ones(tags, dtype=bool)
    eligible[:2] = False
    pairs = {(0, 5), (1, 5), (2, 6), (3, 7), (4, 0)}
    for c in range(chunks):
        if c == 9:
            continue
        for t in rng.choice(tags, size=int(rng.integers(0, 5)), replace=False):
            pairs.add((c, int(t)))
    pairs = sorted(pairs - {(9, t) for t in range(tags)})
    edge_chunk = np.array([c for c, _ in pairs])
    edge_tag = np.array([t for _, t in pairs])
    return {
        'chunk_ids': [f'c{c:03d}' for c in rng.permutation(chunks)],
        'chunk_kinds': rng.choice(['document', 'slack_thread_batch'], size=chunks).tolist(),
        'eligible': eligible, 'edge_tag': edge_tag, 'edge_chunk': edge_chunk,
        'edge_topic': rng.uniform(-.1, .6, size=edge_tag.size),
        'edge_facets': rng.normal(0., 1.5, size=(edge_tag.size, 4))}


def layer_of(t):
    return WK.build_layer(t['chunk_ids'], t['chunk_kinds'], t['eligible'], t['edge_tag'],
                          t['edge_chunk'], t['edge_topic'], t['edge_facets'])


def test_the_layer_holds_the_eligible_edges_and_what_does_not_depend_on_the_question():
    t = toy(0)
    layer = layer_of(t)
    eligible = t['eligible'][t['edge_tag']]
    # only the edges of eligible graph tags, with topic and the four facets, and their places
    assert layer['edges'].tolist() == np.flatnonzero(eligible).tolist()
    assert layer['edge_tag'].tolist() == t['edge_tag'][eligible].tolist()
    assert layer['raw'][:, 0].tolist() == t['edge_topic'][eligible].tolist()
    assert layer['raw'].shape == layer['pos'].shape == (int(eligible.sum()), 5)
    assert ((layer['pos'] > 0) & (layer['pos'] <= 1)).all()
    assert layer['n_c'].tolist() == np.bincount(t['edge_chunk'][eligible], minlength=40).tolist()
    assert layer['n_c'][9] == 0
    # each chunk's place in chunk-id order and its record kind
    assert [t['chunk_ids'][i] for i in np.argsort(layer['id_rank'])] == sorted(t['chunk_ids'])
    assert [layer['kind_names'][k] for k in layer['kind']] == t['chunk_kinds']
    # places premade over the whole graph are kept as given, for the eligible edges
    premade = np.random.default_rng(1).uniform(size=(t['edge_tag'].size, 5))
    given = WK.build_layer(t['chunk_ids'], t['chunk_kinds'], t['eligible'], t['edge_tag'],
                           t['edge_chunk'], t['edge_topic'], t['edge_facets'], pos=premade)
    assert given['pos'].tolist() == premade[eligible].tolist()
    with pytest.raises(ValueError, match='five premade places per edge'):
        WK.build_layer(t['chunk_ids'], t['chunk_kinds'], t['eligible'], t['edge_tag'],
                       t['edge_chunk'], t['edge_topic'], t['edge_facets'], pos=premade[:, :4])
    with pytest.raises(ValueError, match='No edge carries an eligible graph tag'):
        layer_of({**t, 'eligible': np.zeros(30, dtype=bool)})
    with pytest.raises(ValueError, match='four facet values per edge'):
        layer_of({**t, 'edge_facets': t['edge_facets'][:, :3]})
    with pytest.raises(ValueError, match='one record kind per chunk'):
        layer_of({**t, 'chunk_kinds': t['chunk_kinds'][:5]})


def test_the_levels_are_k_clusters_on_the_line_the_highest_first():
    rng = np.random.default_rng(2)
    x = np.concatenate([rng.normal(.1, .02, 200), rng.normal(.5, .02, 20), rng.normal(.9, .01, 5)])
    assert WK.levels(x, 3).tolist() == np.where(x >= .8, 1, np.where(x >= .3, 2, 3)).tolist()
    assert (WK.levels(x, 1) == 1).all()                    # one cluster holds everything
    assert (WK.levels(x, 2) == 1).tolist() == (x >= .3).tolist()   # the least squares split in two
    assert WK.levels([2., 2., 2.], 4).tolist() == [1, 1, 1]        # all alike: one level
    assert WK.levels([.1, .9], 5).tolist() == [2, 1]               # fewer values than clusters
    with pytest.raises(ValueError, match='nonempty row of finite values'):
        WK.levels([.1, float('nan')], 2)
    with pytest.raises(ValueError, match='the number of clusters'):
        WK.levels([.1, .2], 0)


def two_sides():
    """Twelve chunks, one tag and one edge a chunk; two query tags."""
    facets = np.zeros((12, 4))
    facets[0], facets[1] = [1., 5., 0., 0.], [0., 1., 9., 2.]
    facets[4], facets[5] = [9., 0., 0., 0.], [0., 0., 0., 9.]
    layer = {'chunks': 12, 'eligible': np.ones(12, dtype=bool), 'edge_tag': np.arange(12),
             'edge_chunk': np.arange(12), 'raw': np.column_stack([np.zeros(12), facets]),
             'id_rank': np.arange(12)}
    # through the tags: chunks 0, 1, 4 and 5 are near; chunk 1 by the second query tag
    cosines = np.full((2, 12), .1)
    cosines[0, [0, 4, 5]], cosines[1, [0, 4, 5]] = .9, .2
    cosines[0, 1], cosines[1, 1] = .3, .9
    return layer, cosines


def test_a_chunks_nearness_through_its_tags():
    layer, cosines = two_sides()
    near, edge = WK.tags_nearness(layer, cosines)
    assert near.tolist() == pytest.approx([.9, .9, .1, .1, .9, .9] + [.1] * 6)
    assert edge.tolist() == list(range(12))
    with pytest.raises(ValueError, match='one cosine row over the graph tags'):
        WK.tags_nearness(layer, cosines[:, :5])


def test_the_majority_of_the_hits_names_the_scopes():
    scope_of = np.array([0, 0, 0, 1, 1, 2, 2, 3])
    # three hits in scope 0, two in scope 1, one in scope 2: scope 0 holds half and not more,
    # with scope 1 they hold five of six
    assert WK.majority_scopes(np.array([1, 1, 1, 1, 1, 1, 0, 0], dtype=bool), scope_of) == [0, 1]
    # three of four hits in scope 0: it alone holds more than half
    assert WK.majority_scopes(np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=bool), scope_of) == [0]
    # one hit each in three scopes: two of them hold more than half, and the third holds as many
    # as the last one taken
    assert WK.majority_scopes(np.array([1, 0, 0, 1, 0, 1, 0, 0], dtype=bool), scope_of) == [0, 1, 2]
    assert WK.majority_scopes(np.zeros(8, dtype=bool), scope_of) == []
    with pytest.raises(ValueError, match='one hit flag and one scope per chunk'):
        WK.majority_scopes(np.ones(7, dtype=bool), scope_of)


def test_each_sides_cloud_is_its_near_group_and_the_clouds_order_the_border():
    layer, cosines = two_sides()
    cosines = cosines[:1]
    # the border is the first ten chunks. Through the tags three chunks stand far above the rest,
    # by the descriptions three others overlap two of them; the parents are pairs of chunks
    t_near = np.array([.95, .93, .91, .60, .58, .57, .55, .54, .53, .52, .5, .5])
    d_near = np.array([.80, .20, .82, .81, .30, .25, .22, .21, .20, .19, .5, .5])
    scope_of = np.repeat(np.arange(6), 2)
    got = WK.cloud_combo(layer, cosines, d_near, np.arange(10), scope_of, tags_near=t_near)
    # each cloud is the chunks before its knee, as many as the values show: three here, no number given
    assert got['level']['tags'].tolist() == [1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 0, 0]
    assert got['level']['description'].tolist() == [1, 2, 1, 1, 2, 2, 2, 2, 2, 2, 0, 0]
    # a chunk's step: 2 in both clouds, 3 in one, 4 in neither; outside the border none
    assert got['step'].tolist() == [2, 3, 2, 3, 4, 4, 4, 4, 4, 4, 0, 0]
    # the scope is gauged from the chunks in a cloud (0-3): parents 0 and 1 hold two each
    assert got['record'] == {'chunks': 10, 'clouds': {'tags': 3, 'description': 3},
                             'chunks_on_each_step': {2: 2, 3: 2, 4: 6}, 'scope_gauged_from_chunks': 4,
                             'scopes_taken': [0, 1], 'chunks_in_scope': 4}
    # the step first, then in scope first, then the two standings added
    assert got['order'] == [0, 2, 3, 1, 4, 5, 6, 7, 8, 9]
    # a side whose closeness does not bend has no cloud: the other side's cloud alone is lowest
    flat = WK.cloud_combo(layer, cosines, np.full(12, .2), np.arange(10), scope_of, tags_near=t_near)
    assert flat['step'][:10].tolist() == [3, 3, 3] + [4] * 7
    assert flat['record']['clouds'] == {'tags': 3, 'description': 0}
    with pytest.raises(ValueError, match='one finite description closeness per chunk'):
        WK.cloud_combo(layer, cosines, d_near[:5], np.arange(10), scope_of)
    with pytest.raises(ValueError, match='one scope per chunk'):
        WK.cloud_combo(layer, cosines, d_near, np.arange(10), scope_of[:5])
    with pytest.raises(ValueError, match='the distinct chunks of the border'):
        WK.cloud_combo(layer, cosines, d_near, np.array([0, 0, 1]), scope_of)


def test_the_query_facets_influence_the_tag_relationship_and_force_nothing():
    # four chunks, one edge each, all through eligible graph tags 0-3; one query tag
    pos = np.array([[0., .9, .5, .5, .5], [0., .1, .5, .5, .5], [0., .5, .5, .5, .5], [0., .5, .5, .5, .5]])
    layer = {'chunks': 4, 'edge_tag': np.arange(4), 'edge_chunk': np.arange(4), 'pos': pos,
             'eligible': np.ones(4, dtype=bool)}
    rows = np.array([[.80, .81, .50, .20]])
    plain, edge, query_tag = WK.facet_influenced_nearness(layer, rows, np.zeros((1, 4)))
    # with every weight 0 the nearness is the closeness as it is
    assert plain.tolist() == pytest.approx(rows[0].tolist()) and edge.tolist() == [0, 1, 2, 3]
    assert query_tag.tolist() == [0, 0, 0, 0]
    # temporal matters fully: chunk 0 stands high in temporal, chunk 1 low; both move by their
    # place, in the query tag's own spread of closeness; the ones in the middle do not move
    moved, _, _ = WK.facet_influenced_nearness(layer, rows, np.array([[1., 0., 0., 0.]]))
    assert moved[0] > rows[0, 0] and moved[1] < rows[0, 1] and moved[2:].tolist() == pytest.approx([.5, .2])
    # the influence did not have to change the order of 2 and 3, and it did not
    assert moved[2] > moved[3]
    # a border's edges carrying the whole graph's middle and spread of places, and the query tag's
    # spread over the whole graph's tags, move as they do over the whole graph
    whole = WK.influenced_edge_values(layer, rows, np.array([[1., 0., 0., 0.]]))
    place = pos[:, 1:]
    middle = np.median(place, axis=0)
    spread = WK.MAD_TO_SPREAD * np.median(np.abs(place - middle), axis=0)
    close = WK.MAD_TO_SPREAD * np.median(np.abs(rows[0] - np.median(rows[0])))
    border = {'chunks': 2, 'edge_tag': np.arange(2), 'edge_chunk': np.arange(2), 'pos': pos[:2],
              'eligible': np.ones(2, dtype=bool), 'place_middle': middle, 'place_spread': spread}
    part = WK.influenced_edge_values(border, rows[:, :2], np.array([[1., 0., 0., 0.]]),
                                     close_spread=[close])
    assert part[0].tolist() == pytest.approx(whole[0, :2].tolist())
    with pytest.raises(ValueError, match='one spread of closeness per query tag'):
        WK.influenced_edge_values(border, rows[:, :2], np.zeros((1, 4)), close_spread=[1., 2.])
    with pytest.raises(ValueError, match='four facet weights from 0 to 1'):
        WK.facet_influenced_nearness(layer, rows, np.array([[2., 0., 0., 0.]]))


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
    assert WK.levels_of(np.linspace(0., 1., 9))[1] == 0  # a straight run: nothing is hit


def test_a_channels_messages_fall_into_conversations_at_its_long_gaps():
    # minutes inside a conversation, a day or more between two; no length of a gap is given
    day = 86400.
    times = [0., 120., 300., day, day + 180., 3 * day, 3 * day + 60., 3 * day + 240., 10 * day]
    assert WK.conversations(times).tolist() == [0, 0, 0, 1, 1, 2, 2, 2, 3]
    # the same messages an hour apart each are one conversation, and so is one message
    assert WK.conversations([0., 3600., 7200.]).tolist() == [0, 0, 0]
    assert WK.conversations([5.]).tolist() == [0]
    with pytest.raises(ValueError, match='in the order written'):
        WK.conversations([10., 5.])
    with pytest.raises(ValueError, match='in the order written'):
        WK.conversations([])


def test_the_best_edge_of_each_chunk():
    best, edge = WK.best_edges([.3, .9, .9, .1], [0, 0, 0, 2], 3)
    assert best[0] == .9 and edge.tolist() == [1, -1, 3] and np.isnan(best[1])
    # each value's average rank over the rows, ties sharing a rank
    assert WK.positions(np.array([[1.], [3.], [3.], [2.]]))[:, 0].tolist() == [.25, .875, .875, .5]


def test_a_chunks_profile_over_the_query_tags_is_its_strongest_edge_for_each():
    layer, cosines = two_sides()
    layer = {**layer, 'pos': np.column_stack([np.zeros(12), np.full((12, 4), .5)])}
    on_edge = WK.influenced_edge_values(layer, cosines, np.zeros((2, 4)))
    # with every facet weight 0 an edge's weight is the tag's closeness as it is
    np.testing.assert_allclose(on_edge, cosines)
    profiles = WK.query_tag_profiles(layer, on_edge)
    assert profiles.shape == (12, 2) and profiles[1].tolist() == pytest.approx([.3, .9])
    # a chunk with no eligible edge has no profile
    no_edge = {**layer, 'edge_tag': np.arange(11), 'edge_chunk': np.arange(11), 'pos': layer['pos'][:11]}
    assert np.isnan(WK.query_tag_profiles(no_edge, on_edge[:, :11])[11]).all()


def test_the_4combo_ties_each_chunk_to_the_chosen_and_adds_the_ways():
    # chunk 0 is chosen; chunks 1-13 are the others of the clouds
    n = 14
    gap = np.array([0., 0., 10., 60., 3e6, 4e6, 5e6, 6e6, 7e6, 8e6, 9e6, 1e7, np.nan])
    profiles = np.array([[.9, .1, .5, .3]] * 4 + [
        [.1, .9, .5, .3], [.5, .5, .9, .1], [.3, .5, .1, .9], [.2, .2, .9, .1], [.6, .4, .1, .2],
        [.1, .3, .8, .9], [.9, .9, .1, .1], [.4, .1, .9, .6], [np.nan] * 4, [.5, .5, .5, .5]])
    same_parent = np.zeros(13, dtype=bool)
    same_parent[[0, 4]] = True
    shares_person = np.zeros(13, dtype=bool)
    shares_person[[0, 1, 5]] = True
    got = WK.storyline(n, [0], np.zeros(13, dtype=int), np.arange(1, 14), same_parent, shares_person,
                       gap, profiles)
    ties = got['ties']
    # time: the gaps before the knee of the pairs' gaps (0 s, 0 s, 10 s, a minute), not the months
    # after them; a chunk with no time is never near in time
    assert ties['time'].astype(int).tolist() == [1, 1, 1, 1] + [0] * 9
    assert got['record']['time_near_up_to_seconds'] == 60.
    # nearness: the profiles pointing the same way as the chosen chunk's, before the knee; a flat
    # profile or none is never near
    assert ties['nearness'].astype(int).tolist() == [1, 1, 1] + [0] * 10
    # the strength adds the ways, over the chosen chunks
    assert got['strength'].tolist() == [0, 4, 3, 2, 1, 1, 1] + [0] * 7
    assert got['ways']['entities'].tolist() == [0, 1, 1, 0, 0, 0, 1] + [0] * 7
    assert got['record']['chunks_reached'] == 6 and got['record']['pairs_by_ways'][4] == 1
    # the chosen first, then the clouds' other chunks by strength (equals in the given order), then
    # the chunks outside the clouds as given, however strongly they would be tied
    assert WK.storyline_order([3, 0, 5, 1, 2, 4, 6, 7], [0], got['strength'], [0, 1, 2, 3, 5]) == [
        0, 1, 2, 3, 5, 4, 6, 7]
    # a second chosen chunk adds its own ties
    two = WK.storyline(n, [0, 3], np.array([0, 3]), np.array([1, 1]), [True, True], [False, True],
                       np.array([np.nan, np.nan]), profiles)
    assert two['strength'][1] == 3 + int(two['ties']['nearness'].sum())
    with pytest.raises(ValueError, match='one chosen chunk, chunk, parent tie'):
        WK.storyline(n, [0], [0], [1, 2], [True], [True], [0.], profiles)
    with pytest.raises(ValueError, match='negative'):
        WK.storyline(n, [0], [0], [1], [True], [True], [-1.], profiles)
