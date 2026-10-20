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
    assert layer['raw'].shape == (int(eligible.sum()), 5)
    assert layer['n_c'].tolist() == np.bincount(t['edge_chunk'][eligible], minlength=40).tolist()
    assert layer['n_c'][9] == 0
    # each chunk's place in chunk-id order and its record kind
    assert [t['chunk_ids'][i] for i in np.argsort(layer['id_rank'])] == sorted(t['chunk_ids'])
    assert [layer['kind_names'][k] for k in layer['kind']] == t['chunk_kinds']
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
    got = WK.cloud_combo(layer, t_near[None, :], d_near, np.arange(10), scope_of)
    # each cloud is the chunks before its knee, as many as the values show: three here, no number given
    assert got['level']['tags'].tolist() == [1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 0, 0]
    assert got['level']['description'].tolist() == [1, 2, 1, 1, 2, 2, 2, 2, 2, 2, 0, 0]
    # a chunk's step: 2 in both clouds, 3 in one, 4 in neither; outside the border none
    assert got['step'].tolist() == [2, 3, 2, 3, 4, 4, 4, 4, 4, 4, 0, 0]
    # the scope is gauged from the chunks in a cloud (0-3): parents 0 and 1 hold two each
    assert got['record'] == {'chunks': 10, 'clouds': {'tags': 3, 'description': 3},
                             'tags_cloud_by_the_facets': {'nearer': 0, 'farther': 0, 'changed': 0},
                             'chunks_on_each_step': {2: 2, 3: 2, 4: 6}, 'scope_gauged_from_chunks': 4,
                             'scopes_taken': [0, 1], 'chunks_in_scope': 4}
    # the step first, then in scope first, then the middle of the two sides' ranks
    assert got['order'] == [0, 2, 3, 1, 4, 5, 6, 7, 8, 9]
    assert got['rank']['description'][:10].tolist() == [3, 8.5, 1, 2, 4, 5, 6, 7, 8.5, 10]
    assert got['middle_rank'][[1, 3]].tolist() == [5.25, 3.]
    # a tags side's place made otherwise orders inside a step and leaves the clouds as they are
    placed = WK.cloud_combo(layer, t_near[None, :], d_near, np.arange(10), scope_of,
                            tags_place=np.r_[np.arange(10, 0, -1), 0, 0].astype(float))
    assert placed['step'].tolist() == got['step'].tolist() and placed['order'][:2] == [2, 0]
    # a side whose closeness does not bend has no cloud: the other side's cloud alone is lowest
    flat = WK.cloud_combo(layer, t_near[None, :], np.full(12, .2), np.arange(10), scope_of)
    assert flat['step'][:10].tolist() == [3, 3, 3] + [4] * 7
    assert flat['record']['clouds'] == {'tags': 3, 'description': 0}
    # the facets' standing: the cloud keeps the size of its knee; a chunk at its last level that
    # stands below moves one level out and the nearest chunk beyond the knee that stands above
    # moves one level in
    standing = np.zeros(12)
    standing[[2, 3]] = [-1, 1]
    moved = WK.cloud_combo(layer, t_near[None, :], d_near, np.arange(10), scope_of, standing=standing)
    assert moved['level']['tags'].tolist() == [1, 1, 2, 1, 2, 2, 2, 2, 2, 2, 0, 0]
    assert moved['record']['tags_cloud_by_the_facets'] == {'nearer': 1, 'farther': 1, 'changed': 1}
    assert moved['record']['clouds'] == {'tags': 3, 'description': 3}
    # everything one level nearer changes nothing: a level-1 chunk stays, the rest meet it there
    # and closeness decides
    every = WK.cloud_combo(layer, t_near[None, :], d_near, np.arange(10), scope_of,
                           standing=np.ones(12))
    assert every['level']['tags'].tolist() == got['level']['tags'].tolist()
    assert every['record']['tags_cloud_by_the_facets'] == {'nearer': 7, 'farther': 0, 'changed': 0}
    with pytest.raises(ValueError, match='a standing of -1, 0 or 1 per chunk'):
        WK.cloud_combo(layer, t_near[None, :], d_near, np.arange(10), scope_of,
                       standing=np.full(12, .5))
    with pytest.raises(ValueError, match='one finite description closeness per chunk'):
        WK.cloud_combo(layer, cosines, d_near[:5], np.arange(10), scope_of)
    with pytest.raises(ValueError, match='one scope per chunk'):
        WK.cloud_combo(layer, cosines, d_near, np.arange(10), scope_of[:5])
    with pytest.raises(ValueError, match='the distinct chunks of the border'):
        WK.cloud_combo(layer, cosines, d_near, np.array([0, 0, 1]), scope_of)


def test_each_query_tag_ranks_the_borders_chunks_by_closeness_and_a_chunk_takes_its_best_place():
    # four chunks, one edge each, through graph tags 0-3; by closeness to the query tag 0 > 1 > 2 > 3
    layer = {'chunks': 4, 'eligible': np.ones(4, dtype=bool), 'edge_tag': np.arange(4),
             'edge_chunk': np.arange(4), 'raw': np.zeros((4, 5)), 'id_rank': np.arange(4)}
    rows = np.array([[.9, .8, .7, .6]])
    got = WK.closeness_places(layer, rows, np.arange(4))
    assert got['place'].tolist() == [1, 2, 3, 4] and got['closeness_rank'].tolist() == [1, 2, 3, 4]
    assert got['query_tag'].tolist() == [0] * 4 and got['edge'].tolist() == [0, 1, 2, 3]
    # a second query tag that puts chunk 3 first: each chunk takes the best place a query tag gives it
    two = WK.closeness_places(layer, np.array([[.9, .8, .7, .6], [.1, .2, .3, .95]]), np.arange(4))
    assert two['place'].tolist() == [1, 2, 2, 1] and two['query_tag'].tolist() == [0, 0, 1, 1]
    # only the border's chunks are ranked
    part = WK.closeness_places(layer, rows, np.array([1, 2]))
    assert part['place'][[1, 2]].tolist() == [1, 2] and np.isinf(part['place'][[0, 3]]).all()
    with pytest.raises(ValueError, match='one cosine row over the graph tags per query tag'):
        WK.closeness_places(layer, rows[:, :3], np.arange(4))


def test_an_edges_standing_is_read_against_the_same_tags_other_edges_of_its_kind():
    assert WK.wins(np.array([3., 0., .5]), 1.).tolist() == [2., .5, .5]
    # tag 0 on chunks 0 and 1 (kind 0) and on chunk 2 (kind 1); tag 1 alone on chunk 3; tag 2 on
    # chunks 4 and 5 (kind 0), close to each other; chunk 6 lies outside the border
    facets = np.zeros((7, 4))
    facets[:, 0] = [3., 0., 9., 5., .5, 0., -9.]
    layer = {'chunks': 7, 'edge_tag': np.array([0, 0, 0, 1, 2, 2, 0]),
             'edge_chunk': np.arange(7), 'raw': np.column_stack([np.zeros(7), facets]),
             'kind': np.array([0, 0, 1, 0, 0, 0, 0])}
    got = WK.facet_standings(layer, np.arange(6), 0, 1.)
    # chunk 0 beats chunk 1 by more than the range; chunk 2 is the only one of its kind; tag 1 is
    # alone; tags 2's two edges are within the range; chunk 6 is outside: no standing
    assert got.tolist() == [1, -1, 0, 0, 0, 0, 0]
    # with chunk 6 in the border it joins tag 0's kind-0 edges and loses to both
    assert WK.facet_standings(layer, np.arange(7), 0, 1.).tolist() == [1, 0, 0, 0, 0, 0, -1]
    with pytest.raises(ValueError, match='one of the ranking facets'):
        WK.facet_standings(layer, np.arange(6), 4, 1.)
    # per chunk its closest edge's standing in the facet its query tag names; the query tag's own
    # phrase never stands below; no facet, no standing
    t_edge, query_tag = np.arange(7), np.zeros(7, dtype=np.int64)
    gaps = [1., 1., 1., 1.]
    plain = WK.closest_edge_standing(layer, np.arange(6), t_edge, query_tag, [0], gaps,
                                     np.zeros(7, dtype=bool))
    assert plain.tolist() == [1, -1, 0, 0, 0, 0, 0]
    own = np.zeros(7, dtype=bool)
    own[1] = True
    assert WK.closest_edge_standing(layer, np.arange(6), t_edge, query_tag, [0], gaps,
                                    own).tolist() == [1, 0, 0, 0, 0, 0, 0]
    assert not WK.closest_edge_standing(layer, np.arange(6), t_edge, query_tag, [-1], gaps,
                                        own).any()
    with pytest.raises(ValueError, match='one range per ranking facet'):
        WK.closest_edge_standing(layer, np.arange(6), t_edge, query_tag, [0], [1.], own)


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


def test_a_chunks_profile_over_the_query_tags_is_its_strongest_edge_for_each():
    layer, cosines = two_sides()
    on_edge = cosines[:, layer['edge_tag']]
    profiles = WK.query_tag_profiles(layer, on_edge)
    assert profiles.shape == (12, 2) and profiles[1].tolist() == pytest.approx([.3, .9])
    # a chunk with no eligible edge has no profile
    no_edge = {**layer, 'edge_tag': np.arange(11), 'edge_chunk': np.arange(11)}
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
