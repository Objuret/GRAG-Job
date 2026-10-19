"""artefact_v4's arithmetic: arrays in, arrays out.

`build_layer` holds what does not depend on the question. Per question: `tags_nearness` is each
chunk's closest tag to a query tag; `facet_influenced_nearness` is the same with the query's
facets as an influence on the tag relationship; `cloud_combo` finds the tags' side's
cloud and the chunk descriptions' side's cloud, each the chunks before the knee of its own
closeness, a chunk's step is its two levels added (in a cloud or not), and the scope gauged after
that (`majority_scopes`) puts its chunks first inside a step.
`storyline` is the 4-combo: how strongly each chunk of the clouds is tied to the chosen chunks by
scope, entities, time and nearness in what the query asks about (`query_tag_profiles`), and
`storyline_order` puts the chosen chunks first, the rest of the clouds by that strength, and what
lies outside the clouds after them as the combo has it. Every near group is read off where the
upper half of its list bends (`levels_of`; the half, the median, is the agent's choice).
`conversations` cuts a channel's messages where its long gaps are, for the arm's handing over.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import rankdata

FACETS = ('topic', 'temporal', 'why', 'activity', 'concreteness')
RANKING_FACETS = FACETS[1:]
MAD_TO_SPREAD = 1.4826
CLUSTER_BINS = 1500      # the resolution of the clustering on the line: a cut falls on a bin edge


def best_edges(value, edge_chunk, n_chunks):
    """Per chunk the largest value over its edges and the edge that carries it, the earlier edge
    on an exact tie; nan and -1 for a chunk with no edge."""
    value = np.asarray(value, dtype=np.float64)
    edge_chunk = np.asarray(edge_chunk, dtype=np.int64)
    if value.shape != edge_chunk.shape or value.ndim != 1 or not np.isfinite(value).all():
        raise ValueError('Expected one finite value per edge')
    best = np.full(n_chunks, np.nan)
    edge = np.full(n_chunks, -1, dtype=np.int64)
    if not value.size:
        return best, edge
    order = np.lexsort((np.arange(value.size), -value, edge_chunk))
    chunks = edge_chunk[order]
    first = np.ones(order.size, dtype=bool)
    first[1:] = chunks[1:] != chunks[:-1]
    top = order[first]
    best[edge_chunk[top]] = value[top]
    edge[edge_chunk[top]] = top
    return best, edge


def positions(values):
    """Per column: each value's average rank (1 the smallest, ties sharing a rank) over the
    number of rows."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or not values.shape[0] or not np.isfinite(values).all():
        raise ValueError('Expected a nonempty table of finite values, one row per edge')
    ranks = [rankdata(values[:, k], method='average') for k in range(values.shape[1])]
    return np.column_stack(ranks) / values.shape[0]


def build_layer(chunk_ids, chunk_kinds, eligible, edge_tag, edge_chunk, edge_topic, edge_facets,
                pos=None):
    """The edges of the eligible graph tags with their five values and their positions, each
    chunk's edge count and record kind, and each chunk's place in chunk-id order.

    eligible per graph tag; edge_tag, edge_chunk, edge_topic per edge and edge_facets (edges, 4)
    in RANKING_FACETS order, the higher the more; pos, when given, the edges' places as premade
    over the whole graph (edges, 5), else their places among the edges given (`positions`)."""
    chunk_ids = [str(c) for c in chunk_ids]
    n = len(chunk_ids)
    eligible = np.asarray(eligible, dtype=bool)
    edge_tag = np.asarray(edge_tag, dtype=np.int64)
    edge_chunk = np.asarray(edge_chunk, dtype=np.int64)
    edge_topic = np.asarray(edge_topic, dtype=np.float64)
    edge_facets = np.asarray(edge_facets, dtype=np.float64)
    if (not edge_tag.shape == edge_chunk.shape == edge_topic.shape
            or edge_facets.shape != (edge_tag.size, len(RANKING_FACETS))):
        raise ValueError('Expected one tag, chunk, topic and four facet values per edge')
    if edge_tag.size and (edge_tag.min() < 0 or edge_tag.max() >= eligible.size
                          or edge_chunk.min() < 0 or edge_chunk.max() >= n):
        raise ValueError('An edge endpoint is out of range')
    sel = np.flatnonzero(eligible[edge_tag])
    if not sel.size:
        raise ValueError('No edge carries an eligible graph tag')
    raw = np.column_stack([edge_topic[sel], edge_facets[sel]])
    kinds = [str(k) for k in chunk_kinds]
    if len(kinds) != n:
        raise ValueError('Expected one record kind per chunk')
    kind_names = sorted(set(kinds))
    id_rank = np.empty(n, dtype=np.int64)
    id_rank[sorted(range(n), key=lambda i: chunk_ids[i])] = np.arange(n)
    if pos is not None:
        pos = np.asarray(pos, dtype=np.float64)
        if pos.shape != (edge_tag.size, len(FACETS)):
            raise ValueError('Expected five premade places per edge')
    return {'chunk_ids': chunk_ids, 'chunks': n, 'eligible': eligible, 'edges': sel,
            'edge_tag': edge_tag[sel], 'edge_chunk': edge_chunk[sel], 'raw': raw,
            'pos': positions(raw) if pos is None else pos[sel],
            'n_c': np.bincount(edge_chunk[sel], minlength=n).astype(np.int64),
            'id_rank': id_rank, 'kind_names': kind_names,
            'kind': np.array([kind_names.index(k) for k in kinds], dtype=np.int64)}


def levels(values, k):
    """The values cut into k clusters on the line, the number given and not found (his
    2026-10-09 "what if we force the n of k in the kNN instead?"): least squares, the values
    gathered into CLUSTER_BINS equal-width bins first. Returns each
    value's level, 1 the cluster of the highest values; fewer than k levels when the values
    fill fewer bins, one level when they are all alike."""
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or not x.size or not np.isfinite(x).all():
        raise ValueError('Expected a nonempty row of finite values')
    if type(k) is not int or k < 1:
        raise ValueError('Expected k, the number of clusters')
    lo, hi = float(x.min()), float(x.max())
    if hi == lo:
        return np.ones(x.size, dtype=np.int64)
    edges = np.linspace(lo, hi, CLUSTER_BINS + 1)
    which = np.clip(np.searchsorted(edges, x, side='right') - 1, 0, CLUSTER_BINS - 1)
    count = np.bincount(which, minlength=CLUSTER_BINS).astype(np.float64)
    used = np.flatnonzero(count)
    w = count[used]
    a = np.bincount(which, weights=x, minlength=CLUSTER_BINS)[used]
    q = np.bincount(which, weights=x * x, minlength=CLUSTER_BINS)[used]
    m = used.size
    k = min(k, m)
    c0, c1, c2 = (np.concatenate(([0.], np.cumsum(v))) for v in (w, a, q))
    j, i = np.meshgrid(np.arange(m), np.arange(m), indexing='ij')
    inside = i >= j
    size = np.where(inside, c0[i + 1] - c0[j], 1.)
    # cost[j, i]: the squares of one cluster holding the bins j to i
    cost = np.where(inside, np.maximum(c2[i + 1] - c2[j] - (c1[i + 1] - c1[j]) ** 2 / size, 0.),
                    np.inf)
    at = np.arange(m)
    prev = cost[0].copy()
    back = [np.zeros(m, dtype=np.int64)]
    for _ in range(2, k + 1):
        lead = np.full(m, np.inf)
        lead[1:] = prev[:-1]                  # the best with one cluster fewer, ending before j
        table = lead[:, None] + cost
        start = np.argmin(table, axis=0)
        prev = table[start, at]
        back.append(start)
    bin_level = np.zeros(m, dtype=np.int64)
    end = m - 1
    for level, g in enumerate(range(k - 1, -1, -1), 1):
        first = int(back[g][end]) if g else 0
        bin_level[first:end + 1] = level
        end = first - 1
    return bin_level[np.searchsorted(used, which)]


def tags_nearness(layer, cosines):
    """Per chunk the closeness of its closest eligible tag to a query tag, the largest over the
    query tags, and the edge that carries it (-1 with no eligible edge; such a chunk stands with
    the farthest)."""
    rows = np.asarray(cosines, dtype=np.float64)
    if rows.ndim != 2 or not rows.shape[0] or rows.shape[1] != layer['eligible'].size:
        raise ValueError('Expected one cosine row over the graph tags per query tag')
    on_edge = rows[:, layer['edge_tag']]
    if not on_edge.size or not np.isfinite(on_edge).all():
        raise ValueError('Expected finite cosines over the eligible graph tags')
    near, edge = best_edges(on_edge.max(axis=0), layer['edge_chunk'], layer['chunks'])
    has = edge >= 0
    return np.where(has, near, near[has].min()), edge


def knee(falling):
    """The knee of a falling run of values: with both axes run from 0 to 1, the index of the
    value furthest below the straight line between the first and the last. 0 when no value
    lies below that line or the run is flat or shorter than three."""
    y = np.asarray(falling, dtype=np.float64)
    if y.size < 3 or not y[0] > y[-1]:
        return 0
    below = (1. - np.linspace(0., 1., y.size)) - (y - y[-1]) / (y[0] - y[-1])
    at = int(np.argmax(below))
    return at if below[at] > 1e-12 else 0      # rounding alone is not a knee


def levels_of(values):
    """The levels one list of nearness values falls into, read off the distances themselves
    (his "knn values and get levels of n", "that curve ... decide the correct K"). The values
    above the middle, from the nearest down, are split at their knee; what lies above the knee
    is split at its own knee, and so on until three values or fewer are left. Returns each
    value's level (1 the nearest; 0 at or below the middle, or beyond the first knee) and the
    number of levels; no level at all when the first run has no knee."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or not values.size or not np.isfinite(values).all():
        raise ValueError('Expected a nonempty row of finite values')
    level = np.zeros(values.size, dtype=np.int64)
    above = np.flatnonzero(values > np.median(values))
    by = above[np.argsort(-values[above], kind='stable')]
    run = values[by]
    first = knee(run)
    if first < 1:
        return level, 0
    ends, end = [first], first
    while end > 3:
        at = knee(run[:end])
        if at < 1 or at >= end - 1:
            break
        ends.append(at)
        end = at
    ends = ends[::-1]                     # the nearest level's end first
    start = 0
    for number, stop in enumerate(ends, 1):
        level[by[start:stop]] = number
        start = stop
    return level, len(ends)


def influenced_edge_values(layer, cosines, weights, close_spread=None):
    """Per query tag and eligible edge, the edge's weight with the query's facets as an influence
    (`facet_influenced_nearness`): the tag's closeness to the query tag plus, per facet, the query
    tag's weight for it times where the edge stands in the facet's ranking, in units of the query
    tag's own spread of closeness over the graph's tags. Where the edge stands is its place less
    the middle place over the spread of places, over the whole graph when the layer carries them
    (`place_middle`, `place_spread`), else over its own edges; close_spread, when given, is each
    query tag's spread over the whole graph's tags, else it is taken over the layer's tags.
    Returns (query tags, edges)."""
    rows = np.asarray(cosines, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    place = layer['pos'][:, 1:]
    middle = layer['place_middle'] if 'place_middle' in layer else np.median(place, axis=0)
    spread_place = (layer['place_spread'] if 'place_spread' in layer
                    else MAD_TO_SPREAD * np.median(np.abs(place - middle), axis=0))
    stands = np.where(spread_place > 0, (place - middle) / np.where(spread_place > 0, spread_place, 1.), 0.)
    if close_spread is None:
        eligible = layer['eligible']
        close_spread = [MAD_TO_SPREAD * float(np.median(np.abs(r[eligible] - np.median(r[eligible]))))
                        for r in rows]
    close_spread = np.asarray(close_spread, dtype=np.float64)
    if close_spread.shape != (rows.shape[0],):
        raise ValueError('Expected one spread of closeness per query tag')
    return rows[:, layer['edge_tag']] + close_spread[:, None] * (weights @ stands.T)


def query_tag_profiles(layer, on_edge):
    """Per chunk and query tag, the weight of the chunk's strongest edge for that query tag
    (`influenced_edge_values`): the chunk's closeness to each thing the query asks about. nan for a
    chunk with no eligible edge. Returns (chunks, query tags)."""
    on_edge = np.asarray(on_edge, dtype=np.float64)
    out = np.full((layer['chunks'], on_edge.shape[0]), -np.inf)
    np.maximum.at(out, layer['edge_chunk'], on_edge.T)
    out[~np.isfinite(out).all(axis=1)] = np.nan
    return out


def storyline(n, start, pair_start, pair_chunk, same_parent, shares_person, gap, profiles):
    """The 4-combo (his 2026-10-17 "time, scope, entities, chunknearness?", "that IS the 4-combo",
    "shouldnt that enforce the relevance if its reach in many ways?", "near eachother, based on the
    query?"): how strongly each chunk is tied to the chosen chunks.

    One pair is a chosen chunk and another chunk of the border. A pair is tied in up to four ways:
    scope      the two chunks sit under the same parent
    entities   a person is tied to both
    time       the gap in time (the smallest gap between a record of the one and a record of the
               other, each at its own time) lies before the knee of the pairs' gaps sorted from
               the nearest, on the logarithm (`levels_of`); a chunk with no time is never near in
               time
    nearness   near each other in what the query asks about: the two chunks' profiles over the
               query tags (`query_tag_profiles`), each less its own mean, point the same way (their
               correlation) before the knee of the pairs' correlations sorted from the highest; a
               chunk with no eligible edge, or a profile with no spread, is never near
    Where the upper half of each list bends decides what is near (`levels_of`).
    A chunk's strength is the ways it is tied in, added over the chosen chunks: reached in more
    ways, from more chosen chunks, it is the more relevant.

    start: the chosen chunks' indices; pair_start, pair_chunk: per pair the chosen chunk and the
    other chunk; same_parent, shares_person: per pair; gap: per pair in seconds, nan without a
    time; profiles: (n, query tags). Returns per chunk the strength and the count of each way, per
    pair the four ties, and the record."""
    pair_start = np.asarray(pair_start, dtype=np.int64)
    pair_chunk = np.asarray(pair_chunk, dtype=np.int64)
    same_parent = np.asarray(same_parent, dtype=bool)
    shares_person = np.asarray(shares_person, dtype=bool)
    gap = np.asarray(gap, dtype=np.float64)
    profiles = np.asarray(profiles, dtype=np.float64)
    m = pair_start.size
    if not (pair_chunk.shape == same_parent.shape == shares_person.shape == gap.shape == (m,)):
        raise ValueError('Expected one chosen chunk, chunk, parent tie, person tie and gap per pair')
    if profiles.ndim != 2 or profiles.shape[0] != n:
        raise ValueError('Expected one profile over the query tags per chunk')
    if (gap[np.isfinite(gap)] < 0).any():
        raise ValueError('A gap in time is negative')
    time_near = np.zeros(m, dtype=bool)
    timed = np.isfinite(gap)
    time_bound = None
    if timed.any():
        lv, _ = levels_of(-np.log1p(gap[timed]))
        time_near[np.flatnonzero(timed)[lv >= 1]] = True
        time_bound = float(gap[time_near].max()) if time_near.any() else None
    # a chunk with no profile (all nan) stays nan; the mean is taken over the chunks that have one
    with np.errstate(invalid='ignore'):
        means = np.full((n, 1), np.nan)
        whole = np.isfinite(profiles).all(axis=1) if profiles.shape[1] else np.zeros(n, dtype=bool)
        means[whole, 0] = profiles[whole].mean(axis=1)
    centred = profiles - means
    norm = np.linalg.norm(centred, axis=1) if profiles.shape[1] else np.zeros(n)
    corr = np.full(m, np.nan)
    if m and profiles.shape[1]:
        a, b = centred[pair_start], centred[pair_chunk]
        na, nb = norm[pair_start], norm[pair_chunk]
        ok = np.isfinite(na) & np.isfinite(nb) & (na > 0) & (nb > 0)
        corr[ok] = np.einsum('ij,ij->i', a[ok], b[ok]) / (na[ok] * nb[ok])
    query_near = np.zeros(m, dtype=bool)
    query_bound = None
    has = np.isfinite(corr)
    if has.any():
        lv, _ = levels_of(corr[has])
        query_near[np.flatnonzero(has)[lv >= 1]] = True
        query_bound = float(corr[query_near].min()) if query_near.any() else None
    ties = {'scope': same_parent, 'entities': shares_person, 'time': time_near, 'nearness': query_near}
    ways = {name: np.bincount(pair_chunk, weights=tie.astype(np.float64), minlength=n).astype(np.int64)
            for name, tie in ties.items()}
    strength = sum(ways.values()) if ways else np.zeros(n, dtype=np.int64)
    tied_ways = sum(t.astype(np.int64) for t in ties.values())
    record = {'chosen_chunks': int(np.asarray(start).size), 'pairs': int(m),
              'pairs_tied': {name: int(t.sum()) for name, t in ties.items()},
              'pairs_by_ways': {int(w): int((tied_ways == w).sum()) for w in range(5)},
              'time_near_up_to_seconds': time_bound, 'nearness_from_correlation': query_bound,
              'chunks_reached': int(np.unique(pair_chunk[tied_ways > 0]).size)}
    return {'strength': strength, 'ways': ways, 'ties': ties, 'correlation': corr, 'record': record}


def storyline_order(combo_order, start, strength, region):
    """The chosen chunks first, in the combo's order; then the other chunks of the region (the
    clouds) by how strongly they are tied to the chosen ones, the more strongly the earlier,
    chunks equally tied in the combo's order; then every chunk outside the region in the combo's
    order: nothing is lifted from below the clouds."""
    chosen = set(int(i) for i in start)
    inside = set(int(i) for i in region)
    place = {int(i): p for p, i in enumerate(combo_order)}
    first = [int(i) for i in combo_order if int(i) in chosen]
    tied = sorted((int(i) for i in combo_order if int(i) in inside and int(i) not in chosen),
                  key=lambda i: (-int(strength[i]), place[i]))
    rest = [int(i) for i in combo_order if int(i) not in inside and int(i) not in chosen]
    return first + tied + rest


def facet_influenced_nearness(layer, cosines, weights, close_spread=None):
    """The query's facets as an influence on the tag relationship, not an order (his 2026-10-15
    "they are supposed to influence the already existing relationship for chunks and tags",
    2026-10-16 "YOU CANNOT FORCE THEM TO TRY AND CHANGE THE FUCKING ORDERS"; 2026-08-31 "the
    facetweights from the QUERY, determines how many fucks the retrieval take to each tag's
    facets"; 2026-09-18 "the main weight on a tag is the topic one, and the others adjust that
    weight").

    An edge's weight for a query tag is the tag's closeness to it, the existing relationship.
    The facets add to it: for each facet, the query tag's weight for that facet (0 when the facet
    does not matter for the tag, up to 1) times where the edge stands in that facet's ranking
    (its place less the middle, over the spread of places), in units of that query tag's own
    spread of closeness over the graph's tags. With every weight 0 nothing changes. A chunk's
    nearness through its tags is its strongest edge to any query tag after the influence.

    cosines: (query tags, graph tags); weights: (query tags, 4) in RANKING_FACETS order, each 0 to
    1. Returns per chunk the nearness, the edge and the query tag that carry it (-1 with no
    eligible edge; such a chunk stands with the farthest)."""
    rows = np.asarray(cosines, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if rows.ndim != 2 or rows.shape[1] != layer['eligible'].size:
        raise ValueError('Expected one cosine row over the graph tags per query tag')
    if weights.shape != (rows.shape[0], len(RANKING_FACETS)) or (weights < 0).any() or (weights > 1).any():
        raise ValueError('Expected four facet weights from 0 to 1 per query tag')
    tag_e, chunk_e, n = layer['edge_tag'], layer['edge_chunk'], layer['chunks']
    on_edge = influenced_edge_values(layer, rows, weights, close_spread)
    best_q = on_edge.argmax(axis=0)
    value = on_edge[best_q, np.arange(tag_e.size)]
    near, edge = best_edges(value, chunk_e, n)
    has = edge >= 0
    query_tag = np.where(has, best_q[np.maximum(edge, 0)], -1)
    return np.where(has, near, near[has].min()), edge, query_tag


def majority_scopes(hits, scope_of):
    """The scopes that hold the majority of the hit chunks (his 2026-10-09 "what the majority has
    on their scope stats", "I did sure as fuck not mean that a single scope is chosen"): the
    scopes from the one holding the most hits down, taken until they hold more than half of the
    hits, and every scope holding as many as the last one taken. hits: per chunk whether it is
    a hit; scope_of: per chunk the number of its scope. Returns the taken scopes' numbers,
    sorted; none when there is no hit."""
    hits = np.asarray(hits, dtype=bool)
    scope_of = np.asarray(scope_of, dtype=np.int64)
    if hits.shape != scope_of.shape or hits.ndim != 1:
        raise ValueError('Expected one hit flag and one scope per chunk')
    if not hits.any():
        return []
    scopes, held = np.unique(scope_of[hits], return_counts=True)
    by = np.lexsort((scopes, -held))
    total, last = 0, None
    for at in by:
        total += int(held[at])
        last = int(held[at])
        if total * 2 > int(held.sum()):
            break
    return sorted(int(s) for s, count in zip(scopes, held) if count >= last)


def cloud_combo(layer, cosines, d_near, inside, scope_of, tags_near=None):
    """The chunk cloud and the tags' cloud together, over the chunks of a border (his 2026-10-12
    "the combo should fucking work.. So, if we use the chunk-cloud, see if you can find a way to
    combo or lift with the tags", his 2026-10-10 "overlapping clouds for each step"). No
    strength is made and no facet is read.

    A chunk has a nearness on each side. Through its tags: the closeness of its closest eligible
    tag to a query tag, the largest over the query tags (`tags_nearness`). By its description:
    `d_near`, the description's closeness to what the chunk side is asked with. Each side's cloud
    is its near group over the border's chunks: the chunks before the knee of its closeness sorted
    from the nearest down, the knee looked for among the values above the median (`levels_of`), so
    a cloud holds at most half the border. A side whose closeness has no knee has no cloud.

    The level    per side 1 in its cloud, 2 outside it.
    The step     a chunk's two levels added: 2 in both clouds, 3 in one, 4 in neither.
    The scope    gauged after the steps, from the chunks in at least one cloud (with none, every
                 chunk): the scopes holding the majority of those chunks (`majority_scopes`). It
                 is weight and not a cut: inside a step the chunks in scope come first.
    The order    the step, then in scope first, then the two sides' standings added (each
                 nearness less its middle over its spread, over the border), then chunk id.

    inside: the border's chunk indices; scope_of: per chunk the number of its scope; tags_near:
    the tags side's closeness per chunk when it was made otherwise (`facet_influenced_nearness`),
    the closest tag's closeness when not given. Returns the order (the border's chunks only), what
    lies behind it per chunk, and the record."""
    n = layer['chunks']
    d_near = np.asarray(d_near, dtype=np.float64)
    inside = np.asarray(inside, dtype=np.int64)
    scope_of = np.asarray(scope_of, dtype=np.int64)
    if d_near.shape != (n,) or not np.isfinite(d_near).all():
        raise ValueError('Expected one finite description closeness per chunk')
    if scope_of.shape != (n,):
        raise ValueError('Expected one scope per chunk')
    if inside.ndim != 1 or not inside.size or inside.min() < 0 or inside.max() >= n \
            or np.unique(inside).size != inside.size:
        raise ValueError('Expected the distinct chunks of the border')
    rows = np.asarray(cosines, dtype=np.float64)
    t_near, t_edge = tags_nearness(layer, rows)
    if tags_near is not None:
        t_near = np.asarray(tags_near, dtype=np.float64)
        if t_near.shape != (n,) or not np.isfinite(t_near).all():
            raise ValueError("Expected one finite tags' closeness per chunk")
    query_tag = np.where(t_edge >= 0, rows[:, layer['edge_tag']].argmax(axis=0)[np.maximum(t_edge, 0)], -1)
    sides = {'tags': t_near, 'description': d_near}
    level = {name: np.zeros(n, dtype=np.int64) for name in sides}
    value = np.zeros(n)
    for name, x in sides.items():
        here = x[inside]
        lv, _ = levels_of(here)
        level[name][inside] = np.where(lv >= 1, 1, 2)
        bulk = float(np.median(here))
        spread = MAD_TO_SPREAD * float(np.median(np.abs(here - bulk)))
        if spread > 0.:                        # a side whose values do not spread says nothing
            value[inside] += (here - bulk) / spread
    step = np.zeros(n, dtype=np.int64)
    step[inside] = level['tags'][inside] + level['description'][inside]
    lowest = int(step[inside].min())
    gauged_from = inside[step[inside] <= max(3, lowest)]
    hits = np.zeros(n, dtype=bool)
    hits[gauged_from] = True
    taken = majority_scopes(hits[inside], scope_of[inside])
    in_scope = np.zeros(n, dtype=bool)
    in_scope[inside] = np.isin(scope_of[inside], taken)
    by = np.lexsort((layer['id_rank'][inside], -value[inside], ~in_scope[inside], step[inside]))
    steps, counts = np.unique(step[inside], return_counts=True)
    record = {'chunks': int(inside.size),
              'clouds': {name: int((level[name][inside] == 1).sum()) for name in sides},
              'chunks_on_each_step': {int(s): int(c) for s, c in zip(steps, counts)},
              'scope_gauged_from_chunks': int(gauged_from.size),
              'scopes_taken': taken, 'chunks_in_scope': int(in_scope.sum())}
    return {'order': inside[by].tolist(), 'tags_nearness': t_near, 'description_nearness': d_near,
            'edge': t_edge, 'query_tag': query_tag, 'level': level, 'step': step,
            'in_scope': in_scope, 'value': value, 'record': record}


def conversations(times):
    """One channel's messages as conversations: a new one starts where the gap to the message
    before is one of the channel's long gaps. The logarithms of the gaps are cut in two by least
    squares (`levels`) and the cluster of the larger ones is the long gaps; no length of a gap
    is given. times: the messages' times in seconds, in the order written. Returns per message
    the number of its conversation, 0 the first; one conversation when the gaps are all alike
    or there is one message."""
    t = np.asarray(times, dtype=np.float64)
    if t.ndim != 1 or not t.size or not np.isfinite(t).all() or (np.diff(t) < 0).any():
        raise ValueError("Expected one channel's message times in the order written")
    if t.size == 1:
        return np.zeros(1, dtype=np.int64)
    gaps = np.log1p(np.diff(t))
    if gaps.max() == gaps.min():
        return np.zeros(t.size, dtype=np.int64)
    return np.concatenate(([0], np.cumsum(levels(gaps, 2) == 1))).astype(np.int64)
