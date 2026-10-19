import math
import numpy as np
import pytest

from artefact import v4_walk as WK

NOISE = 0.002
K = 3


def toy(seed, chunks=40, tags=30, query_tags=4):
    """A small random graph and question; tags 0 and 1 are not eligible, and three graph tags
    stand far above the rest for the first two query tags."""
    rng = np.random.default_rng(seed)
    eligible = np.ones(tags, dtype=bool)
    eligible[:2] = False
    pairs = {(0, 5), (1, 5), (2, 6), (3, 7), (4, 0)}
    for c in range(chunks):
        if c == 9:
            continue  # a chunk with no edge
        for t in rng.choice(tags, size=int(rng.integers(0, 5)), replace=False):
            pairs.add((c, int(t)))
    pairs = sorted(pairs - {(9, t) for t in range(tags)})
    edge_chunk = np.array([c for c, _ in pairs])
    edge_tag = np.array([t for _, t in pairs])
    adjacent = {0: [1], 1: [0, 2], 2: [1], 5: [6], 6: [5], 20: [21], 21: [20]}
    ptr, members = [0], []
    for c in range(chunks):
        members += adjacent.get(c, [])
        ptr.append(len(members))
    cosines = rng.normal(.7, .06, size=(query_tags, tags))
    cosines[0, 5], cosines[0, 6], cosines[1, 7] = .97, .93, .95
    return {
        'chunk_ids': [f'c{c:03d}' for c in rng.permutation(chunks)],
        'chunk_kinds': rng.choice(['document', 'slack_thread_batch'], size=chunks).tolist(),
        'eligible': eligible, 'edge_tag': edge_tag, 'edge_chunk': edge_chunk,
        'edge_topic': rng.uniform(-.1, .6, size=edge_tag.size),
        'edge_facets': rng.normal(0., 1.5, size=(edge_tag.size, 4)),
        'facet_gaps': (.8, 1.1, .9, 1.3),
        'product': rng.integers(0, 3, size=chunks),
        'adjacency_ptr': np.array(ptr), 'adjacency': np.array(members, dtype=np.int64),
        'query': {'cosines': cosines,
                  'named_facet': rng.integers(0, 4, size=query_tags),
                  'description_cosines': rng.uniform(.2, .9, size=query_tags),
                  'd_description': rng.normal(.2, .06, size=chunks),
                  'd_question': rng.normal(.18, .06, size=chunks)}}


def layer_of(t):
    return WK.build_layer(t['chunk_ids'], t['chunk_kinds'], t['eligible'], t['edge_tag'],
                          t['edge_chunk'], t['edge_topic'], t['edge_facets'], t['facet_gaps'],
                          t['product'], t['adjacency_ptr'], t['adjacency'])


def spread_of(values):
    middle = float(np.median(values))
    return middle, 1.4826 * float(np.median([abs(v - middle) for v in values]))


def by_hand(t):
    """The module docstring's chain with plain loops, one chunk and one edge at a time."""
    q = t['query']
    n, tags = len(t['chunk_ids']), t['eligible'].size
    edges = [e for e in range(t['edge_tag'].size) if t['eligible'][t['edge_tag'][e]]]
    tag_of = [int(t['edge_tag'][e]) for e in edges]
    chunk_of = [int(t['edge_chunk'][e]) for e in edges]
    topic = [float(t['edge_topic'][e]) for e in edges]
    facets = [t['edge_facets'][e] for e in edges]
    # the pick: per query tag its K nearest eligible tags (a tie at the K-th is in); then the
    # picked edges' facet classes, the measured gaps counted down from the picked edges' largest
    kth = [sorted((float(row[x]) for x in range(tags) if t['eligible'][x]), reverse=True)[K - 1]
           for row in q['cosines']]
    used = sorted({j for i, row in enumerate(q['cosines']) for j in range(len(edges))
                   if row[tag_of[j]] >= kth[i]})
    # per edge the rank of each facet among the edge's four (0 the strongest)
    ranks = [[sorted(range(4), key=lambda k: (-facets[j][k], k)).index(k) for k in range(4)]
             for j in range(len(edges))]
    value = np.zeros((len(q['cosines']), n))
    spreads, facet_orders, best_edge = [], [], np.full((len(q['cosines']), n), -1)
    for i, row in enumerate(q['cosines']):
        middle, spread = spread_of([row[x] for x in range(tags) if t['eligible'][x]])
        spreads.append(spread)
        named = int(q['named_facet'][i])
        order = [named] + [k for k in range(4) if k != named]
        facet_orders.append(order)
        cosine = [float(row[x]) for x in tag_of]
        closest = max(row[x] for x in range(tags) if t['eligible'][x])
        same = [j for j in range(len(edges)) if cosine[j] >= kth[i]]
        if same and closest > kth[i]:
            width = (closest - kth[i]) * (1. + 1e-9) + 1e-12
            ranked = sorted(same, key=lambda j: (ranks[j][named], -topic[j], -cosine[j], j))
            for place, j in enumerate(ranked):
                cosine[j] = closest - width * (place / len(same))
        fit = [max((c - middle) / spread, 0.) for c in cosine]
        for j, c in enumerate(chunk_of):
            if best_edge[i, c] < 0 or fit[j] > value[i, c]:
                value[i, c], best_edge[i, c] = fit[j], j
    top = max(q['description_cosines'])
    central = [max(d, 0.) / top for d in q['description_cosines']]
    tag_term, winner = np.zeros(n), np.zeros(n, dtype=int)
    for c in range(n):
        products = [central[i] * value[i, c] for i in range(len(central))]
        winner[c] = int(np.argmax(products))
        tag_term[c] = products[winner[c]]
    d_middle, d_spread = spread_of(q['d_description'])
    q_middle, q_spread = spread_of(q['d_question'])
    text = np.array([max((q['d_description'][c] - d_middle) / d_spread,
                         (q['d_question'][c] - q_middle) / q_spread) for c in range(n)])
    base = tag_term + text
    product = t['product']
    product_lift, left = np.zeros(n), np.zeros(n)
    for c in range(n):
        members = [o for o in range(n) if product[o] == product[c]]
        left[c] = base[c] - np.mean(base[members])
        others = [o for o in members if o != c]
        if others:
            product_lift[c] = max(np.mean(base[others]) - np.mean(base), 0.)
    group = {}
    for c in range(n):  # the connected groups of file-adjacent chunks
        group.setdefault(c, {c})
        for o in t['adjacency'][t['adjacency_ptr'][c]:t['adjacency_ptr'][c + 1]]:
            merged = group[c] | group.setdefault(int(o), {int(o)})
            for member in merged:
                group[member] = merged
    grouped = [c for c in range(n) if len(group[c]) > 1]
    near_lift = np.zeros(n)
    for c in grouped:
        of_kind = [o for o in grouped if t['chunk_kinds'][o] == t['chunk_kinds'][c]]
        others = [o for o in group[c] if o != c]
        near_lift[c] = max(np.mean(left[others]) - np.mean(left[of_kind]), 0.)
    strength = base + product_lift + near_lift
    has_edge = np.array([any(c == x for x in chunk_of) for c in range(n)])
    return {'strength': strength, 'tags': tag_term, 'text': text, 'product': product_lift,
            'near': near_lift, 'winner': winner, 'has_edge': has_edge,
            'step': NOISE / float(np.median(spreads)), 'facet_orders': facet_orders,
            'kth': kth, 'used': used,
            'best_edge': best_edge}


@pytest.mark.parametrize('seed', range(6))
def test_the_chain_equals_the_chain_done_by_hand(seed):
    t = toy(seed)
    layer = layer_of(t)
    got = WK.chain(layer, t['query'], NOISE, K)
    want = by_hand(t)
    for name, mine in (('strength', got['strength']), ('tags', got['tags']),
                       ('text', got['text']), ('product', got['lift']['product']),
                       ('near', got['lift']['near'])):
        np.testing.assert_allclose(mine, want[name], rtol=1e-10, atol=1e-12, err_msg=name)
    assert got['step'] == pytest.approx(want['step'])
    assert got['has_edge'].tolist() == want['has_edge'].tolist()
    assert (got['lift']['product'] >= 0).all() and (got['lift']['near'] >= 0).all()
    won = got['has_edge'] & (got['tags'] > 0)
    assert got['winner'][won].tolist() == want['winner'][won].tolist()
    # the pick is each query tag's K nearest tags: an edge is picked for a query tag exactly
    # when its tag's cosine reaches the K-th closeness of that query tag
    cosines = t['query']['cosines'][:, layer['edge_tag']]
    assert got['pick']['k'] == K and got['pick']['kth_closeness'] == pytest.approx(want['kth'])
    assert (got['picked_edge'] == (cosines >= np.array(want['kth'])[:, None])).all()
    assert got['picked_edge'][0].any() and got['picked_edge'][1].any()
    assert np.flatnonzero(got['picked_edge'].any(axis=0)).tolist() == want['used']
    assert all(c >= K for c in got['pick']['graph_tags_per_query_tag'])
    assert set(got['facet_classes']) == set(WK.RANKING_FACETS)
    # the order: level, then the chunks with an edge by the winning edge's facet positions in
    # the winning query tag's order, then chunk id; every chunk once
    n = len(t['chunk_ids'])
    assert sorted(got['order']) == list(range(n))
    level = np.floor((got['strength'].max() - got['strength']) / got['step']).astype(int)
    assert got['level'].tolist() == level.tolist()

    def key(c):
        if not got['has_edge'][c]:
            return (level[c], 1, (), t['chunk_ids'][c])
        positions = layer['pos'][got['win_edge'][c]][1:]
        slots = tuple(-positions[k] for k in want['facet_orders'][got['winner'][c]])
        return (level[c], 0, slots, t['chunk_ids'][c])

    assert got['order'] == sorted(range(n), key=key)
    assert not got['has_edge'][9] and got['tags'][9] == 0


def test_the_picked_edges_are_spread_by_the_query_tags_facet_order():
    # four picked edges: the four ranking facets' classes decide first, in the order given, then
    # topic's class, then topic, then the cosine; the places run from the closest tag down
    classes = np.array([[1, 0, 0, 0, 0], [0, 1, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0]])
    cosine = np.array([.97, .96, .93, .95])
    topic = np.array([.5, .5, .2, .2])
    place, placed = WK.spread_by_facets(cosine, .97, .08, classes, (0, 1, 2, 3), topic)
    assert place.tolist() == [3, 2, 1, 0]      # edge 3 before 2: same classes and topic, closer
    assert placed.tolist() == pytest.approx([.97 - .08 * 3 / 4, .97 - .08 * 2 / 4,
                                             .97 - .08 / 4, .97])
    place, _ = WK.spread_by_facets(cosine, .97, .08, classes, (1, 0, 2, 3), topic)
    assert place.tolist() == [2, 3, 1, 0]      # the second facet first: edge 1 falls last
    place, _ = WK.spread_by_facets(cosine, .97, .08, classes, (0, 1, 2, 3),
                                   np.array([.5, .5, .9, .2]))
    assert place.tolist() == [3, 2, 0, 1]      # the higher topic first among equal classes
    outside = classes.copy()
    outside[2, 4] = 1                          # edge 2 outside topic's main cluster
    place, _ = WK.spread_by_facets(cosine, .97, .08, outside, (0, 1, 2, 3),
                                   np.array([.5, .5, .9, .2]))
    assert place.tolist() == [3, 2, 1, 0]      # topic's class before the topic value
    with pytest.raises(ValueError, match='five facet classes'):
        WK.spread_by_facets(cosine, .97, .08, classes[:, :4], (0, 1, 2, 3), topic)


def test_the_main_cluster_is_the_cluster_of_the_highest_values():
    rng = np.random.default_rng(1)
    x = np.concatenate([rng.normal(.1, .02, 200), rng.normal(.5, .02, 20), rng.normal(.9, .01, 5)])
    count, low, mask = WK.main_cluster(x)
    assert count == 3 and mask.tolist() == (x >= .8).tolist()
    assert low == pytest.approx(x[x >= .8].min())
    count, low, mask = WK.main_cluster([2., 2., 2.])      # all alike: one cluster of everything
    assert count == 1 and low == 2. and mask.all()
    count, low, mask = WK.main_cluster([.1, .9])          # fewer than three: the same
    assert count == 1 and low == .1 and mask.all()
    with pytest.raises(ValueError, match='nonempty row of finite values'):
        WK.main_cluster([.1, float('nan')])


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
    """Twelve chunks in three branches of two scopes of two chunks; one tag and one edge a chunk.
    Two query tags: the first names facet 0, the second facet 2."""
    scopes = [(f'{b}/{s}', np.array([4 * i + 2 * j, 4 * i + 2 * j + 1]))
              for i, b in enumerate('ABC') for j, s in enumerate('xy')]
    branches = {b: np.arange(4 * i, 4 * i + 4) for i, b in enumerate('ABC')}
    facets = np.zeros((12, 4))
    facets[0], facets[1] = [1., 5., 0., 0.], [0., 1., 9., 2.]
    facets[4], facets[5] = [9., 0., 0., 0.], [0., 0., 0., 9.]
    layer = {'chunks': 12, 'eligible': np.ones(12, dtype=bool), 'edge_tag': np.arange(12),
             'edge_chunk': np.arange(12), 'raw': np.column_stack([np.zeros(12), facets]),
             'id_rank': np.arange(12)}
    # through the tags: chunks 0, 1 (A/x) and 4, 5 (B/x) are near; chunk 1 by the second query tag
    cosines = np.full((2, 12), .1)
    cosines[0, [0, 4, 5]], cosines[1, [0, 4, 5]] = .9, .2
    cosines[0, 1], cosines[1, 1] = .3, .9
    return layer, cosines, np.array([0, 2]), scopes, branches


def test_both_sides_overlap_at_the_scope_step_and_inside_the_border():
    layer, cosines, named, scopes, branches = two_sides()
    # by the descriptions: chunks 0, 1 (A/x), 2 (A/y) and 8, 9 (C/x) are near
    d_near = np.array([.8, .8, .8, .1, .1, .1, .1, .1, .8, .8, .1, .1])
    got = WK.both_sides(layer, cosines, named, d_near, scopes, branches, 2)
    record = got['record']
    # the nearness clouds: tags {0, 1, 4, 5}, descriptions {0, 1, 2, 8, 9}; both hold 0 and 1
    assert record['nearness_clouds']['tags']['chunks'] == 4
    assert record['nearness_clouds']['description']['chunks'] == 5
    assert record['nearness_clouds']['tags']['lowest'] == pytest.approx(.9)
    assert record['chunks_in_both_nearness_clouds'] == 2
    # the scope clouds: tags {A/x, B/x}; descriptions {A/x, A/y, C/x}; both hold A/x, and A/x
    # holds chunks of both nearness clouds: branch A is the border
    assert record['scope_clouds'] == {'tags': 2, 'description': 3}
    assert record['scopes_in_both_scope_clouds'] == 1 and record['main_scopes'] == ['A/x']
    assert record['branches'] == ['A'] and not record['nothing_cut']
    assert got['border'].tolist() == [True] * 4 + [False] * 8
    # inside A both sides are cut again: 0 and 1 in both clouds, 2 in the descriptions' alone,
    # 3 in neither. Among 0 and 1 the tags decide: chunk 1's query tag names the strongest facet
    # of its edge, chunk 0's names the second strongest
    assert record['inside'] == {'chunks': 4, 'clouds': {'tags': 2, 'description': 3},
                                'in_both': 2, 'in_one': 1, 'in_neither': 1}
    assert got['order'] == [1, 0, 2, 3]
    assert got['group'][:4].tolist() == [0, 0, 1, 2] and (got['group'][4:] == -1).all()
    assert got['query_tag'][:2].tolist() == [0, 1] and got['facet_rank'][:2].tolist() == [1, 0]
    assert got['level']['tags'][:4].tolist() == [1, 1, 2, 2]
    assert got['level']['description'][:4].tolist() == [1, 1, 1, 2]


def test_with_no_scope_in_both_scope_clouds_nothing_is_cut():
    layer, cosines, named, scopes, branches = two_sides()
    d_near = np.array([.1] * 8 + [.8, .8, .1, .1])           # the descriptions point at C/x alone
    got = WK.both_sides(layer, cosines, named, d_near, scopes, branches, 2)
    record = got['record']
    assert record['scopes_in_both_scope_clouds'] == 0 and record['main_scopes'] == []
    assert record['branches'] == [] and record['nothing_cut'] and got['border'].all()
    assert record['inside'] == {'chunks': 12, 'clouds': {'tags': 4, 'description': 2},
                                'in_both': 0, 'in_one': 6, 'in_neither': 6}
    # the chunks one cloud holds first, the tags' cloud before the descriptions' (the cluster of
    # the nearness through the tags), then the named facet's rank on the edge, then chunk id
    assert got['order'] == [1, 4, 0, 5, 8, 9, 2, 3, 6, 7, 10, 11]
    with pytest.raises(ValueError, match='one cosine row over the graph tags'):
        WK.both_sides(layer, cosines[:, :5], named, d_near, scopes, branches, 2)
    with pytest.raises(ValueError, match='one named ranking facet'):
        WK.both_sides(layer, cosines, named + 4, d_near, scopes, branches, 2)
    with pytest.raises(ValueError, match='one finite description closeness per chunk'):
        WK.both_sides(layer, cosines, named, d_near[:5], scopes, branches, 2)


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
    layer, cosines, _, _, _ = two_sides()
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


def test_the_query_facets_order_the_chunks_inside_the_tags_sides_equal_ranges():
    # eight chunks, one edge each; the tags side's closeness falls into two clusters: 0-3 near,
    # 4-7 far. The edges' places in the four facets' rankings (topic first, then the four).
    pos = np.array([[0., .1, .9, .5, .5], [0., .9, .1, .5, .5], [0., .5, .5, .5, .5], [0., .3, .3, .5, .5],
                    [0., .2, .8, .5, .5], [0., .8, .2, .5, .5], [0., .5, .5, .5, .5], [0., .5, .5, .5, .5]])
    layer = {'chunks': 8, 'edge_tag': np.arange(8), 'edge_chunk': np.arange(8), 'pos': pos,
             'id_rank': np.arange(8)}
    t_near = np.array([.95, .94, .93, .92, .41, .40, .39, .38])
    t_edge = np.arange(8)
    query_tag = np.array([0, 0, 0, 1, 0, 0, 0, 1])
    # query tag 0: temporal steers, then why; query tag 1: nothing steers
    got, record = WK.facets_in_equal_closeness(layer, t_near, t_edge, query_tag, [[0, 1], []],
                                               np.arange(8), 2)
    # near cluster: chunks 0, 1, 2 steer by temporal (1 .9, 2 .5, 0 .1) and are dealt .95, .94, .93;
    # chunk 3 has no steering facet and keeps its own. Far cluster: 5, 6, 4 by temporal
    assert got.tolist() == pytest.approx([.93, .95, .94, .92, .39, .41, .40, .38])
    assert record == {'clusters': 2, 'chunks_dealt_another_closeness': 6}
    # no value leaves its cluster, and with no steering facet nothing moves
    assert sorted(got[:4]) == sorted(t_near[:4])
    still, _ = WK.facets_in_equal_closeness(layer, t_near, t_edge, query_tag, [[], []], np.arange(8), 2)
    assert still.tolist() == t_near.tolist()
    with pytest.raises(ValueError, match='distinct ranking facets'):
        WK.facets_in_equal_closeness(layer, t_near, t_edge, query_tag, [[0, 0], []], np.arange(8), 2)
    # a facet's levels over the edges, read off its values by the knees; a reading's level
    values = np.column_stack([np.r_[np.linspace(0, 1, 200), [5., 5.2, 5.1, 9., 9.3]]] * 4)
    floors = WK.facet_levels(values)
    assert len(floors) == 4 and floors[0] == sorted(floors[0], reverse=True) and floors[0]
    assert WK.facet_level(10., floors[0]) == 1 and WK.facet_level(.5, floors[0]) == 0


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


def test_the_facets_tie_chunks_to_the_strongest_hits_inside_a_step():
    # six chunks; tag 0 on chunks 0, 1, 2; tag 1 on 0 and 3; tag 2 on 4 and 5. The places in the
    # facets' rankings (topic, temporal, why, activity, concreteness) make chunk 0's role on tag 0
    # temporal, chunk 1's temporal (a tie at its best rank: the first facet), chunk 2's why; on
    # tag 1 chunk 0's role is why and chunk 3's activity; on tag 2 both are temporal (all tie)
    pos = np.array([[0., .9, .2, .1, .5], [0., .8, .1, .2, .5], [0., .1, .9, .3, .5],
                    [0., .5, .9, .1, .5], [0., .5, .1, .9, .5],
                    [0., .4, .4, .4, .4], [0., .4, .4, .4, .4]])
    layer = {'chunks': 6, 'edge_tag': np.array([0, 0, 0, 1, 1, 2, 2]),
             'edge_chunk': np.array([0, 1, 2, 0, 3, 4, 5]), 'pos': pos, 'id_rank': np.arange(6)}
    combo = {'step': np.array([2, 4, 4, 4, 3, 5]), 'in_scope': np.ones(6, dtype=bool),
             'value': np.array([1., .1, .9, .5, .8, .2]), 'order': [0, 4, 2, 3, 1, 5]}
    got = WK.facet_relations(layer, combo, np.arange(6))
    # the strongest hits are 0 and 4 (steps 2 and 3). Chunk 1 shares tag 0 with chunk 0 in the
    # same role; chunk 2 shares it in another role; chunk 3 shares tag 1 in another role;
    # chunk 5 shares tag 2 with chunk 4 in the same role
    assert got['tied'].tolist() == [False, True, False, False, False, True]
    assert got['path'] == {1: (0, 0, 0), 5: (4, 2, 0)}
    # inside step 4 the tied chunk 1 goes first, then the standings (2 before 3)
    assert got['order'] == [0, 4, 1, 2, 3, 5]
    assert got['record'] == {'strongest_hits': 2, 'chunks_tied': 2,
                             'tied_by_facet': {'temporal': 2, 'why': 0, 'activity': 0,
                                               'concreteness': 0}}
    # the scope stays before the tie: a tied chunk out of scope waits for those in scope
    out_of_scope = {**combo, 'in_scope': np.array([True, False, True, True, True, True])}
    assert WK.facet_relations(layer, out_of_scope, np.arange(6))['order'] == [0, 4, 2, 3, 1, 5]
    # outside the border nothing is ranked or tied: without chunk 5 tag 2 holds one chunk
    assert WK.facet_relations(layer, combo, np.arange(5))['tied'].tolist() == [
        False, True, False, False, False, False]
    with pytest.raises(ValueError, match="combo's step, scope and value per chunk"):
        WK.facet_relations(layer, {**combo, 'step': combo['step'][:5]}, np.arange(6))


def test_the_border_is_the_branch_most_of_the_near_chunks_sit_in():
    branches = {'A': np.arange(0, 4), 'B': np.arange(4, 8), 'C': np.arange(8, 12)}
    near = np.array([.9, .1, .1, .1, .9, .9, .1, .1, .1, .1, .1, .1])
    keep, record = WK.border_by_nearness(near, branches, 2)
    assert record['near_chunks'] == 3 and record['lowest'] == pytest.approx(.9)
    assert record['branches'] == [{'branch': 'B', 'near_chunks': 2}, {'branch': 'A', 'near_chunks': 1}]
    assert record['kept'] == ['B'] and keep.tolist() == [False] * 4 + [True] * 4 + [False] * 4
    near[1] = .9                                             # a tie keeps both branches
    keep, record = WK.border_by_nearness(near, branches, 2)
    assert record['kept'] == ['A', 'B'] and keep.tolist() == [True] * 8 + [False] * 4
    assert not record['nothing_cut']


def test_a_chunks_nearness_through_its_tags_and_the_routes_in_turn():
    layer, cosines, _, _, _ = two_sides()
    near, edge = WK.tags_nearness(layer, cosines)
    assert near.tolist() == pytest.approx([.9, .9, .1, .1, .9, .9] + [.1] * 6)
    assert edge.tolist() == list(range(12))
    with pytest.raises(ValueError, match='one cosine row over the graph tags'):
        WK.tags_nearness(layer, cosines[:, :5])
    # one chunk from each order in turn, a chunk once, and whose turn brought it
    order, source = WK.in_turn([[3, 1, 2], [1, 0, 3], [2, 3, 0]])
    assert order == [3, 1, 2, 0] and source == [0, 1, 2, 1]


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


def test_the_small_steps():
    values, bulk, spread = WK.standing([1., 2., 3., 4., 100.])
    assert bulk == 3. and spread == pytest.approx(1.4826) and values[0] == pytest.approx(-2 / 1.4826)
    with pytest.raises(ValueError, match='spread of the values is zero'):
        WK.standing([1., 1., 1.])
    assert WK.centrality([.2, -.1, .4]).tolist() == pytest.approx([.5, 0., 1.])
    with pytest.raises(ValueError, match='No query tag has a positive cosine'):
        WK.centrality([-.2, 0.])
    best, edge = WK.best_edges([.3, .9, .9, .1], [0, 0, 0, 2], 3)
    assert best[0] == .9 and edge.tolist() == [1, -1, 3] and np.isnan(best[1])
    # the largest reading first, equal readings in the facets' own order, topic not read
    assert WK.facet_order([1., .2, .9, .2, .5]) == (1, 3, 0, 2)
    assert WK.same_thing_pairs(['Cache', 'cache', 'caches', 'caching', 'API keys', 'api key']) == [
        (0, 1), (0, 2), (1, 2), (4, 5)]
    # a lift is the mean of the group's others less the reference, never below 0
    lift = WK.group_lift(np.array([1., 3., 8., 2.]), [0, 1, 2, 3], [7, 7, 7, 9], 4.)
    assert lift.tolist() == pytest.approx([1.5, .5, 0., 0.])


def test_a_layer_needs_an_eligible_edge():
    t = toy(0)
    with pytest.raises(ValueError, match='No edge carries an eligible graph tag'):
        layer_of({**t, 'eligible': np.zeros(30, dtype=bool)})
    layer = layer_of(t)
    with pytest.raises(ValueError, match='one cosine row over the graph tags'):
        WK.chain(layer, {**t['query'], 'cosines': t['query']['cosines'][:, :5]}, NOISE, K)
    with pytest.raises(ValueError, match='one named ranking facet'):
        WK.chain(layer, {**t['query'], 'named_facet': t['query']['named_facet'] + 4}, NOISE, K)
