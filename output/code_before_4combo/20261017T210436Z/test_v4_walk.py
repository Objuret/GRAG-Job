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


def test_the_chunk_cloud_and_the_tags_cloud_together_order_the_border():
    layer, cosines = two_sides()
    # the border is the first eight chunks. Through the tags 0, 1, 4, 5 are near; by the
    # descriptions 0, 1, 2, 5. The parents are pairs of chunks.
    d_near = np.array([.8, .8, .8, .1, .1, .8, .1, .1, .8, .8, .8, .8])
    scope_of = np.repeat(np.arange(6), 2)
    got = WK.cloud_combo(layer, cosines, d_near, np.arange(8), scope_of, 2)
    assert got['level']['tags'].tolist() == [1, 1, 2, 2, 1, 1, 2, 2, 0, 0, 0, 0]
    assert got['level']['description'].tolist() == [1, 1, 1, 2, 2, 1, 2, 2, 0, 0, 0, 0]
    # a chunk's step is its two levels added; outside the border there is none
    assert got['step'].tolist() == [2, 2, 3, 4, 3, 2, 4, 4, 0, 0, 0, 0]
    # the scope is gauged from the chunks on steps 2 and 3 (0, 1, 2, 4, 5): parents 0 and 2 hold
    # two each and together more than half; parent 1 holds one
    record = got['record']
    assert record == {'k': 2, 'chunks': 8, 'clouds': {'tags': 4, 'description': 4},
                      'chunks_on_each_step': {2: 3, 3: 2, 4: 3}, 'scope_gauged_from_chunks': 5,
                      'scopes_taken': [0, 2], 'chunks_in_scope': 4}
    assert got['in_scope'].tolist() == [True, True, False, False, True, True] + [False] * 6
    # the step first; inside a step the chunks in scope first (4 before 2); then the two
    # standings added, then chunk id
    assert got['order'] == [0, 1, 5, 4, 2, 3, 6, 7]
    assert got['value'][:8].tolist() == pytest.approx(
        [2 * .6745, 2 * .6745, 0., -2 * .6745, 0., 2 * .6745, -2 * .6745, -2 * .6745], abs=1e-3)
    assert (got['value'][8:] == 0.).all()
    assert got['query_tag'][:2].tolist() == [0, 1] and got['edge'].tolist() == list(range(12))
    # with nothing on the first two steps the lowest step there is gauges the scope
    flat = WK.cloud_combo(layer, np.full((1, 12), .3), np.full(12, .2), np.arange(8), scope_of, 2)
    assert flat['step'][:8].tolist() == [2] * 8 and flat['record']['scope_gauged_from_chunks'] == 8
    assert flat['order'] == list(range(8)) and (flat['value'] == 0.).all()
    with pytest.raises(ValueError, match='one finite description closeness per chunk'):
        WK.cloud_combo(layer, cosines, d_near[:5], np.arange(8), scope_of, 2)
    with pytest.raises(ValueError, match='one scope per chunk'):
        WK.cloud_combo(layer, cosines, d_near, np.arange(8), scope_of[:5], 2)
    with pytest.raises(ValueError, match='the distinct chunks of the border'):
        WK.cloud_combo(layer, cosines, d_near, np.array([0, 0, 1]), scope_of, 2)


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
    with pytest.raises(ValueError, match='four facet weights from 0 to 1'):
        WK.facet_influenced_nearness(layer, rows, np.array([[2., 0., 0., 0.]]))


def test_a_facets_levels_over_the_edges_and_a_readings_level():
    # a facet's levels over the edges, read off its values by the knees; a reading's level
    values = np.column_stack([np.r_[np.linspace(0, 1, 200), [5., 5.2, 5.1, 9., 9.3]]] * 4)
    floors = WK.facet_levels(values)
    assert len(floors) == 4 and floors[0] == sorted(floors[0], reverse=True) and floors[0]
    assert WK.facet_level(10., floors[0]) == 1 and WK.facet_level(.5, floors[0]) == 0
    with pytest.raises(ValueError, match='the four ranking facets per edge'):
        WK.facet_levels(values[:, :3])


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
