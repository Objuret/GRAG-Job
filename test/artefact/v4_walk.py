"""artefact_v4's arithmetic: arrays in, arrays out.

`build_layer` holds what does not depend on the question. Per question: `tags_nearness` is each
chunk's closest tag to a query tag; `closeness_places` ranks each query tag's chunks by closeness;
`closest_edge_standing` reads each chunk's closest edge in the facet named for its query tag
against the same tag's other edges (`facet_standings`); `cloud_combo` finds the tags' side's cloud
and the chunk descriptions' side's cloud, each the chunks before the knee of its own closeness, the
facets moving a chunk one level at the tags' cloud's edge, a chunk's step is its two levels added
(in a cloud or not), the scope gauged after that (`majority_scopes`) puts its chunks first inside a
step, and inside a step the two sides' ranks decide.
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


def build_layer(chunk_ids, chunk_kinds, eligible, edge_tag, edge_chunk, edge_topic, edge_facets):
    """The edges of the eligible graph tags with their five values, each chunk's edge count and
    record kind, and each chunk's place in chunk-id order.

    eligible per graph tag; edge_tag, edge_chunk, edge_topic per edge and edge_facets (edges, 4)
    in RANKING_FACETS order, the higher the more."""
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
    return {'chunk_ids': chunk_ids, 'chunks': n, 'eligible': eligible, 'edges': sel,
            'edge_tag': edge_tag[sel], 'edge_chunk': edge_chunk[sel], 'raw': raw,
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


def query_tag_profiles(layer, on_edge):
    """Per chunk and query tag, the closeness of the chunk's strongest edge for that query tag
    (on_edge: (query tags, edges), each edge's graph tag's closeness to the query tag): the chunk's
    closeness to each thing the query asks about. nan for a chunk with no eligible edge. Returns
    (chunks, query tags)."""
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


def closeness_places(layer, cosines, inside):
    """Per query tag the border's chunks ranked by their closeness to it, each through its closest
    eligible tag, then chunk id; a chunk with no eligible edge stands last. Each chunk then takes
    the best place any query tag gives it (taking the best, counting no tags, is the agent's
    choice); every query tag's list holds the same chunks.

    cosines: (query tags, graph tags); inside: the border's chunk indices. Returns per chunk (inf
    outside the border) its place, 1 the first, the query tag and the edge that give it, and its
    rank by closeness under that query tag."""
    rows = np.asarray(cosines, dtype=np.float64)
    inside = np.asarray(inside, dtype=np.int64)
    n = layer['chunks']
    if rows.ndim != 2 or not rows.shape[0] or rows.shape[1] != layer['eligible'].size:
        raise ValueError('Expected one cosine row over the graph tags per query tag')
    if inside.ndim != 1 or not inside.size or inside.min() < 0 or inside.max() >= n             or np.unique(inside).size != inside.size:
        raise ValueError('Expected the distinct chunks of the border')
    tag_e, chunk_e = layer['edge_tag'], layer['edge_chunk']
    q_count, m = rows.shape[0], inside.size
    place = np.full((q_count, n), np.inf)
    by_closeness = np.full((q_count, n), np.nan)
    carried = np.full((q_count, n), -1, dtype=np.int64)
    ids = layer['id_rank'][inside]
    for q in range(q_count):
        near, edge = best_edges(rows[q, tag_e], chunk_e, n)
        near, edge = near[inside], edge[inside]
        has = edge >= 0
        s = np.full(m, float(has.sum() + 1))
        s[has] = rankdata(-near[has], method='average')
        place[q, inside[np.lexsort((ids, s))]] = np.arange(1, m + 1)
        by_closeness[q, inside], carried[q, inside] = s, edge
    best = np.argmin(place, axis=0)
    at = np.arange(n)
    query_tag = np.where(np.isfinite(place[best, at]), best, -1)
    return {'place': place[best, at], 'query_tag': query_tag, 'edge': carried[best, at],
            'closeness_rank': by_closeness[best, at]}


def wins(value, gap=0.):
    """Per item its wins over the others: the higher value wins when it is higher by more than gap,
    the same within it counts a half. Counted by sorting, not by pairs."""
    value = np.asarray(value, dtype=np.float64)
    v = np.sort(value)
    below = np.searchsorted(v, value - gap, side='left')
    within = np.searchsorted(v, value + gap, side='right') - below
    return below + .5 * (within - 1)


def facet_standings(layer, inside, facet, gap):
    """Per edge its standing in one facet, read only against the same graph tag's other edges on
    chunks of the same record kind inside the border (his 2026-10-19 "ok, but can we make them
    adaptive easily deterministically?"; the tag's own level and the kind, which the structure
    gives, stay out): +1 when it beats more of them than it loses to, -1 when it loses more, 0
    otherwise, alone, or outside the border. One edge beats another when its value is higher by
    more than gap, the facet's range (the difference the net's 24 refits agree on)."""
    if not 0 <= facet < len(RANKING_FACETS):
        raise ValueError('Expected one of the ranking facets')
    tag_e, chunk_e, raw, kind = layer['edge_tag'], layer['edge_chunk'], layer['raw'], layer['kind']
    in_border = np.zeros(layer['chunks'], dtype=bool)
    in_border[np.asarray(inside, dtype=np.int64)] = True
    keep = np.flatnonzero(in_border[chunk_e])
    out = np.zeros(tag_e.size)
    group = tag_e[keep].astype(np.int64) * (int(kind.max()) + 1) + kind[chunk_e[keep]]
    order = np.argsort(group, kind='stable')
    for members in np.split(keep[order], np.flatnonzero(np.diff(group[order])) + 1):
        if members.size > 1:
            out[members] = np.sign(wins(raw[members, 1 + facet], gap) - (members.size - 1) / 2.)
    return out


def closest_edge_standing(layer, inside, t_edge, query_tag, facet_of, gaps, own):
    """Per chunk the standing (`facet_standings`) of its edge to its closest tag, in the facet the
    first call named for the query tag that gives that closeness; 0 where that facet does not
    matter or the chunk has no edge. own: per chunk, whether that closest tag is the query tag's
    own phrase; such an edge never stands below (his 2026-10-19 "ok, do that and run a smoke?":
    the chunks the facets pushed out held gold most often when their tag was the query tag)."""
    facet_of = np.asarray(facet_of, dtype=np.int64)
    gaps = np.asarray(gaps, dtype=np.float64)
    if gaps.shape != (len(RANKING_FACETS),):
        raise ValueError('Expected one range per ranking facet')
    standing = np.zeros(layer['chunks'])
    by_facet = {int(f): facet_standings(layer, inside, int(f), gaps[f])
                for f in np.unique(facet_of[facet_of >= 0])}
    for c in np.asarray(inside, dtype=np.int64):
        e, q = int(t_edge[c]), int(query_tag[c])
        if e < 0 or q < 0 or facet_of[q] < 0:
            continue
        standing[c] = by_facet[int(facet_of[q])][e]
        if own[c] and standing[c] < 0:
            standing[c] = 0.
    return standing


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


def cloud_combo(layer, cosines, d_near, inside, scope_of, tags_place=None, standing=None):
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
    With the facets (`standing`, per chunk +1, 0 or -1, `closest_edge_standing`), the tags' cloud
    keeps the size its knee gives and takes the chunks first by their level of closeness moved one
    nearer for +1 and one farther for -1 (everything beyond the knee one level after the last),
    then by closeness: the facets decide who is in it at its edge (his 2026-10-19 "what if we just
    moved something 1 step per thing?", "they are the RELEVANCE MODIFIER OF THE TAGS TO THE
    CHUNKS").

    The level    per side 1 in its cloud, 2 outside it.
    The step     a chunk's two levels added: 2 in both clouds, 3 in one, 4 in neither.
    The scope    gauged after the steps, from the chunks in at least one cloud (with none, every
                 chunk): the scopes holding the majority of those chunks (`majority_scopes`). It
                 is weight and not a cut: inside a step the chunks in scope come first.
    The order    the step, then in scope first, then the two sides' ranks over the border
                 counted equally (each chunk at the middle of its tags side's rank and its
                 description side's rank; ranks against ranks, no cosine added to a rank), then
                 chunk id.

    inside: the border's chunk indices; scope_of: per chunk the number of its scope; tags_place:
    the tags side's place per chunk when it was made otherwise (`closeness_places`), its closeness
    when not given; standing: per chunk, or none for the clouds by closeness alone. Returns the
    order (the border's chunks only), what lies behind it per chunk, and the record."""
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
    if tags_place is not None:
        tags_place = np.asarray(tags_place, dtype=np.float64)
        if tags_place.shape != (n,) or not np.isfinite(tags_place[inside]).all():
            raise ValueError("Expected one finite tags' place per chunk of the border")
    query_tag = np.where(t_edge >= 0, rows[:, layer['edge_tag']].argmax(axis=0)[np.maximum(t_edge, 0)], -1)
    sides = {'tags': t_near, 'description': d_near}
    level = {name: np.zeros(n, dtype=np.int64) for name in sides}
    by_closeness = set()
    moved_record = {'nearer': 0, 'farther': 0, 'changed': 0}
    for name, x in sides.items():
        lv, count = levels_of(x[inside])
        level[name][inside] = np.where(lv >= 1, 1, 2)
        if name == 'tags':
            by_closeness = set(inside[lv >= 1].tolist())
            if standing is not None and count:
                standing = np.asarray(standing, dtype=np.float64)
                if standing.shape != (n,) or not np.isin(standing[inside], (-1., 0., 1.)).all():
                    raise ValueError('Expected a standing of -1, 0 or 1 per chunk')
                at = np.where(lv >= 1, lv, count + 1).astype(np.float64)
                moved = np.clip(at - standing[inside], 1., count + 1.)
                by = np.lexsort((layer['id_rank'][inside], -x[inside], moved))
                level['tags'][inside] = 2
                level['tags'][inside[by[:len(by_closeness)]]] = 1
                moved_record = {'nearer': int((moved < at).sum()), 'farther': int((moved > at).sum()),
                                'changed': len(set(inside[by[:len(by_closeness)]].tolist())
                                               - by_closeness)}
    rank = {name: np.full(n, np.nan) for name in sides}
    rank['tags'][inside] = rankdata(tags_place[inside] if tags_place is not None
                                    else -t_near[inside], method='average')
    rank['description'][inside] = rankdata(-d_near[inside], method='average')
    middle = np.full(n, np.nan)
    middle[inside] = (rank['tags'][inside] + rank['description'][inside]) / 2.
    step = np.zeros(n, dtype=np.int64)
    step[inside] = level['tags'][inside] + level['description'][inside]
    lowest = int(step[inside].min())
    gauged_from = inside[step[inside] <= max(3, lowest)]
    hits = np.zeros(n, dtype=bool)
    hits[gauged_from] = True
    taken = majority_scopes(hits[inside], scope_of[inside])
    in_scope = np.zeros(n, dtype=bool)
    in_scope[inside] = np.isin(scope_of[inside], taken)
    by = np.lexsort((layer['id_rank'][inside], middle[inside], ~in_scope[inside], step[inside]))
    steps, counts = np.unique(step[inside], return_counts=True)
    record = {'chunks': int(inside.size),
              'clouds': {name: int((level[name][inside] == 1).sum()) for name in sides},
              'tags_cloud_by_the_facets': moved_record,
              'chunks_on_each_step': {int(s): int(c) for s, c in zip(steps, counts)},
              'scope_gauged_from_chunks': int(gauged_from.size),
              'scopes_taken': taken, 'chunks_in_scope': int(in_scope.sum())}
    return {'order': inside[by].tolist(), 'tags_nearness': t_near, 'description_nearness': d_near,
            'edge': t_edge, 'query_tag': query_tag, 'level': level, 'step': step,
            'in_scope': in_scope, 'rank': rank, 'middle_rank': middle, 'record': record}


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
