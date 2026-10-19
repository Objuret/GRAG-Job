"""artefact_v4's chain: one strength per chunk from its best tag, the description and the
question, and the lift of its product and its near group. Arrays in, arrays out.

`cloud_combo` is the order as it stands and makes no strength: inside the border the tags'
side and the chunk descriptions' side each cut their nearness into k clusters (`levels`), a
chunk's step is its two levels added, and the scope gauged after that (`majority_scopes`) puts
its chunks first inside a step. `facets_in_equal_closeness` lets the query's facets order the
chunks inside the tags side's equal ranges before the combo. `facet_relations` (the agent's link
roles, out of the step since 2026-10-15) ties chunks to the strongest hits by the facets of
their shared tags. `conversations` cuts a channel's messages where its long gaps are, for the
arm's handing over. `both_sides` is the 2026-10-10 build of the two sides. What
follows describes `chain`, which the older scope steps still use.

Per query tag q (a row of cosines over the graph tags, five readings, a cosine to the query
description):
  fit        the cosine's standing over the eligible graph tags, (cosine - median) / spread,
             the spread 1.4826 times the median absolute deviation; below 0 counts as 0.
  the pick   all the query tags at once: every query tag's cosine to every eligible graph tag
             is one list, and its main cluster (`main_cluster`) is the picked (query tag, graph
             tag) pairs (his 2026-10-08 "perhaps all query tags should be clustered at the same
             time?"). The picked tags' edges, each once, are clustered one facet at a time; a
             facet's main cluster is the range inside which its edges are equal (his "only take
             the top cluster for each"). q's picked edges are put in order by the four facets in
             q's order (in the facet's main cluster first), then topic's main cluster, then
             topic, then the cosine, and spread evenly between q's closest tag and the pick's
             lowest cosine in that order. Every other edge keeps its cosine.
  per chunk  the largest fit over its eligible edges, 0 with none.
T(c)   the largest over q of centrality(q) times that value. centrality is q's cosine to the
       query description over the question's largest, a negative one as 0.
S(c)   T(c) plus the larger of the description's and the question's standing over the chunks.
S'(c)  S(c) plus the product lift plus the near-group lift. A lift is the mean over the
       group's other chunks, less the reference, never below 0. Product: of S, against the mean
       of S. Near group (chunks adjacent in one file): of S less the product's mean, against
       the mean of that over the grouped chunks of the chunk's record kind.
Order  level = floor((max S' - S') / step), step = the noise over the median fit spread. Inside
       a level the chunks with a winning edge first, by that edge's four facet positions in
       the winning query tag's facet order, descending; then chunk id.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import rankdata

FACETS = ('topic', 'temporal', 'why', 'activity', 'concreteness')
RANKING_FACETS = FACETS[1:]
MAD_TO_SPREAD = 1.4826
SAME_POINT = 5           # the percent of the same-thing pairs' cosines under the level
GROUPINGS = ('product', 'near')
CLUSTER_BINS = 1500      # the resolution of the clustering on the line: a cut falls on a bin edge
CLUSTER_K_MOST = 40      # how far the curve of the fit is drawn; the bend is looked for inside it


def standing(values):
    """(value - bulk) / spread per value, with the bulk (the median) and the spread (1.4826
    times the median absolute deviation from the median) of the values given."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or not values.size or not np.isfinite(values).all():
        raise ValueError('Expected a nonempty row of finite values')
    bulk = float(np.median(values))
    spread = MAD_TO_SPREAD * float(np.median(np.abs(values - bulk)))
    if not spread > 0.:
        raise ValueError('The spread of the values is zero')
    return (values - bulk) / spread, bulk, spread


def centrality(description_cosines):
    """Each query tag's cosine to the query description, a negative one as zero, over the
    largest of the question."""
    cosines = np.asarray(description_cosines, dtype=np.float64)
    if cosines.ndim != 1 or not cosines.size or not np.isfinite(cosines).all():
        raise ValueError('Expected one finite description cosine per query tag')
    top = float(cosines.max())
    if not top > 0.:
        raise ValueError('No query tag has a positive cosine to the query description')
    return np.clip(cosines, 0., None) / top


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


def facet_order(readings):
    """The four ranking facets as indices into RANKING_FACETS, the largest reading first; equal
    readings keep RANKING_FACETS order. The topic reading is not read."""
    readings = np.asarray(readings, dtype=np.float64)
    if readings.shape != (len(FACETS),):
        raise ValueError('Expected five readings in FACETS order')
    values = readings[1:]
    return tuple(sorted(range(len(RANKING_FACETS)), key=lambda j: (-values[j], j)))


def positions(values):
    """Per column: each value's average rank (1 the smallest, ties sharing a rank) over the
    number of rows."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or not values.shape[0] or not np.isfinite(values).all():
        raise ValueError('Expected a nonempty table of finite values, one row per edge')
    ranks = [rankdata(values[:, k], method='average') for k in range(values.shape[1])]
    return np.column_stack(ranks) / values.shape[0]


def main_cluster(values):
    """The main cluster of a list of values (his 2026-10-08 "if there is an obvious main
    cluster, that is the one"): least-squares clusters on the line, the number of clusters the
    one where the curve of the fit (the within-cluster squares against the number) bends most
    (the dogleg; his 2026-10-08 "dogleg decides? That is fine"), and of those the cluster of
    the highest values. The values are gathered into CLUSTER_BINS
    equal-width bins first, so a cut falls on a bin edge. Returns the number of clusters, the
    lowest value in the main cluster and the mask of the values in it; one cluster holding
    everything when the values are fewer than three or all alike."""
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or not x.size or not np.isfinite(x).all():
        raise ValueError('Expected a nonempty row of finite values')
    lo, hi = float(x.min()), float(x.max())
    if x.size < 3 or hi == lo:
        return 1, lo, np.ones(x.size, dtype=bool)
    edges = np.linspace(lo, hi, CLUSTER_BINS + 1)
    which = np.clip(np.searchsorted(edges, x, side='right') - 1, 0, CLUSTER_BINS - 1)
    count = np.bincount(which, minlength=CLUSTER_BINS).astype(np.float64)
    used = np.flatnonzero(count)
    w = count[used]
    a = np.bincount(which, weights=x, minlength=CLUSTER_BINS)[used]
    q = np.bincount(which, weights=x * x, minlength=CLUSTER_BINS)[used]
    m = used.size
    c0, c1, c2 = (np.concatenate(([0.], np.cumsum(v))) for v in (w, a, q))
    j, i = np.meshgrid(np.arange(m), np.arange(m), indexing='ij')
    inside = i >= j
    size = np.where(inside, c0[i + 1] - c0[j], 1.)
    # cost[j, i]: the squares of one cluster holding the bins j to i
    cost = np.where(inside, np.maximum(c2[i + 1] - c2[j] - (c1[i + 1] - c1[j]) ** 2 / size, 0.),
                    np.inf)
    at = np.arange(m)
    prev = cost[0].copy()
    back, totals = [np.zeros(m, dtype=np.int64)], [float(prev[-1])]
    for _ in range(2, min(CLUSTER_K_MOST, m) + 1):
        lead = np.full(m, np.inf)
        lead[1:] = prev[:-1]                  # the best with one cluster fewer, ending before j
        table = lead[:, None] + cost
        start = np.argmin(table, axis=0)
        prev = table[start, at]
        back.append(start)
        totals.append(float(prev[-1]))
    curve = np.asarray(totals)
    if curve.size < 3 or curve[0] == curve[-1]:
        found = 1
    else:
        line = np.linspace(0., 1., curve.size)
        found = int(np.argmax((1. - line) - (curve - curve[-1]) / (curve[0] - curve[-1]))) + 1
    first = int(back[found - 1][m - 1]) if found > 1 else 0   # the main cluster's first bin
    mask = which >= used[first]
    return found, float(x[mask].min()), mask


def same_thing_pairs(names):
    """The pairs (i < j) of names that are the same thing in another spelling: equal once
    lower-cased, or equal once lower-cased and a final s dropped from every word longer than
    three letters."""
    def stem(name):
        return ' '.join(w[:-1] if w.endswith('s') and len(w) > 3 else w
                        for w in name.casefold().split())
    groups = {}
    for i, name in enumerate(names):
        groups.setdefault(stem(str(name)), []).append(i)
    return [(a, b) for group in groups.values() if len(group) > 1
            for k, a in enumerate(group) for b in group[k + 1:]]


def same_thing_level(names, vectors, eligible):
    """What two graph tags that are the same thing score against each other: the cosines of
    `same_thing_pairs` over the eligible tags' stored vectors. Returns the level (the point
    SAME_POINT percent of them lie under), their median and their number; None with no pair."""
    keep = np.flatnonzero(np.asarray(eligible, dtype=bool))
    pairs = same_thing_pairs([names[i] for i in keep])
    if not pairs:
        return None
    rows = np.asarray(vectors, dtype=np.float64)[keep]
    rows = rows / np.linalg.norm(rows, axis=1, keepdims=True)
    at = np.array(pairs, dtype=np.int64)
    scores = np.einsum('ij,ij->i', rows[at[:, 0]], rows[at[:, 1]])
    return {'level': float(np.percentile(scores, SAME_POINT)), 'median': float(np.median(scores)),
            'pairs': int(scores.size), 'point': SAME_POINT}


def spread_by_facets(cosine, best, width, facet_class, order, topic):
    """The edges of one query tag's picked tags, in order: by the classes of the four ranking
    facets in `order` (0 in the facet's main cluster, 1 outside it), then topic's class, then
    topic descending, then the cosine descending, then the edge's index. `facet_class` has one
    row per edge: the four ranking facets in RANKING_FACETS order, then topic. Returns each
    edge's place (0 first) and the cosine that place gives it: best - width * place / the
    number of edges."""
    cosine = np.asarray(cosine, dtype=np.float64)
    topic = np.asarray(topic, dtype=np.float64)
    facet_class = np.asarray(facet_class, dtype=np.int64)
    order = [int(j) for j in order]
    if cosine.ndim != 1 or topic.shape != cosine.shape or facet_class.shape != (cosine.size,
                                                                                 len(FACETS)):
        raise ValueError('Expected one cosine, one topic and five facet classes per edge')
    if sorted(order) != list(range(len(RANKING_FACETS))):
        raise ValueError('Expected every ranking facet once in the order')
    by = np.lexsort((np.arange(cosine.size), -cosine, -topic, facet_class[:, -1],
                     *(facet_class[:, j] for j in reversed(order))))
    place = np.empty(cosine.size, dtype=np.int64)
    place[by] = np.arange(cosine.size)
    return place, best - width * (place / cosine.size)


def record_groups(adjacency_ptr, adjacency):
    """Per chunk the index of its near group - its connected component in the file-adjacency
    graph - when the component holds at least two chunks, else -1."""
    ptr = np.asarray(adjacency_ptr, dtype=np.int64)
    members = np.asarray(adjacency, dtype=np.int64)
    n = ptr.size - 1
    if n < 0 or ptr[0] != 0 or ptr[-1] != members.size or (np.diff(ptr) < 0).any():
        raise ValueError('Expected one CSR row of adjacent chunks per chunk')
    graph = csr_matrix((np.ones(members.size, dtype=np.int8), members, ptr), shape=(n, n))
    _, label = connected_components(graph, directed=False)
    size = np.bincount(label, minlength=n)
    grouped = size[label] >= 2
    record = np.full(n, -1, dtype=np.int64)
    if grouped.any():
        _, record[grouped] = np.unique(label[grouped], return_inverse=True)
    return record


def kind_reference(x, grouped, kind):
    """Per chunk the mean of x over the grouped chunks of its kind, 0 for a kind with none."""
    x = np.asarray(x, dtype=np.float64)
    grouped = np.asarray(grouped, dtype=bool)
    kind = np.asarray(kind, dtype=np.int64)
    if not x.shape == grouped.shape == kind.shape:
        raise ValueError('Expected one value, one flag and one kind per chunk')
    reference = np.zeros(x.size)
    for code in np.unique(kind[grouped]).tolist():
        reference[kind == code] = float(x[grouped & (kind == code)].mean())
    return reference


def group_lift(x, chunk, node, reference):
    """Per chunk: the mean of x over the other members of its group, less its reference, never
    below 0; the largest over the chunk's groups. chunk, node: the memberships. reference: a
    number, or one per chunk. A group of one gives no lift."""
    x = np.asarray(x, dtype=np.float64)
    chunk = np.asarray(chunk, dtype=np.int64)
    node = np.asarray(node, dtype=np.int64)
    if x.ndim != 1 or not x.size or not np.isfinite(x).all():
        raise ValueError('Expected one finite value per chunk')
    if chunk.shape != node.shape or chunk.ndim != 1:
        raise ValueError('Expected one node per chunk membership')
    if chunk.size and (chunk.min() < 0 or chunk.max() >= x.size):
        raise ValueError('A chunk membership is out of range')
    reference = np.broadcast_to(np.asarray(reference, dtype=np.float64), x.shape)
    if not np.isfinite(reference).all():
        raise ValueError('Expected a finite reference')
    lift = np.zeros(x.size)
    if not chunk.size:
        return lift
    _, node = np.unique(node, return_inverse=True)
    size = np.bincount(node)
    total = np.bincount(node, weights=x[chunk])
    others = size[node] - 1
    shared = np.flatnonzero(others > 0)
    raw = ((total[node[shared]] - x[chunk[shared]]) / others[shared]
           - reference[chunk[shared]])
    best, edge = best_edges(raw, chunk[shared], x.size)
    has = edge >= 0
    lift[has] = np.maximum(best[has], 0.)
    return lift


def build_layer(chunk_ids, chunk_kinds, eligible, edge_tag, edge_chunk, edge_topic, edge_facets,
                facet_gaps, product, adjacency_ptr, adjacency):
    """What does not depend on the question: the edges of the eligible graph tags with their
    five values and their positions, each chunk's edge count, record kind and product, and the
    near groups from the file adjacency.

    eligible per graph tag; edge_tag, edge_chunk, edge_topic per edge and edge_facets (edges, 4)
    in RANKING_FACETS order, the higher the more; product per chunk; adjacency_ptr, adjacency
    the CSR of each chunk's file-adjacent chunks."""
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
    facet_gaps = np.asarray(facet_gaps, dtype=np.float64)
    if facet_gaps.shape != (len(RANKING_FACETS),) or not (facet_gaps > 0).all():
        raise ValueError('Expected one positive gap per ranking facet')
    if edge_tag.size and (edge_tag.min() < 0 or edge_tag.max() >= eligible.size
                          or edge_chunk.min() < 0 or edge_chunk.max() >= n):
        raise ValueError('An edge endpoint is out of range')
    sel = np.flatnonzero(eligible[edge_tag])
    if not sel.size:
        raise ValueError('No edge carries an eligible graph tag')
    raw = np.column_stack([edge_topic[sel], edge_facets[sel]])
    product = np.asarray(product, dtype=np.int64)
    if product.shape != (n,) or (product < 0).any():
        raise ValueError('Expected one product per chunk')
    kinds = [str(k) for k in chunk_kinds]
    if len(kinds) != n:
        raise ValueError('Expected one record kind per chunk')
    kind_names = sorted(set(kinds))
    every = np.arange(n, dtype=np.int64)
    near = record_groups(adjacency_ptr, adjacency)
    if near.shape != (n,):
        raise ValueError('Expected the file adjacency over the same chunks')
    id_rank = np.empty(n, dtype=np.int64)
    id_rank[sorted(range(n), key=lambda i: chunk_ids[i])] = np.arange(n)
    return {'chunk_ids': chunk_ids, 'chunks': n, 'eligible': eligible, 'edges': sel,
            'edge_tag': edge_tag[sel], 'edge_chunk': edge_chunk[sel], 'raw': raw,
            'pos': positions(raw), 'facet_gaps': np.asarray(facet_gaps, dtype=np.float64),
            'n_c': np.bincount(edge_chunk[sel], minlength=n).astype(np.int64),
            'product': product, 'near': near, 'id_rank': id_rank, 'kind_names': kind_names,
            'kind': np.array([kind_names.index(k) for k in kinds], dtype=np.int64),
            'groups': {'product': (every, product),
                       'near': (every[near >= 0], near[near >= 0])}}


def chain(layer, query, cos_noise, k):
    """The module's chain on one question. query: 'cosines' (query tags, graph tags),
    'named_facet' (query tags; the index in RANKING_FACETS of the facet the query tag names),
    'description_cosines' (query tags,), 'd_description' and
    'd_question' (chunks,). Returns the order and every array behind it."""
    n, eligible = layer['chunks'], layer['eligible']
    tag_e, chunk_e, pos, raw = layer['edge_tag'], layer['edge_chunk'], layer['pos'], layer['raw']
    rows = np.asarray(query['cosines'], dtype=np.float64)
    named = np.asarray(query['named_facet'], dtype=np.int64)
    count = rows.shape[0]
    if rows.ndim != 2 or not count or rows.shape[1] != eligible.size:
        raise ValueError('Expected one cosine row over the graph tags per query tag')
    if not np.isfinite(rows[:, eligible]).all():
        raise ValueError('Expected finite cosines over the eligible graph tags')
    if named.shape != (count,) or named.min() < 0 or named.max() >= len(RANKING_FACETS):
        raise ValueError('Expected one named ranking facet per query tag')
    if not (np.isfinite(cos_noise) and cos_noise > 0):
        raise ValueError('Expected a positive noise')
    if type(k) is not int or k < 1:
        raise ValueError('Expected k, the number of nearest graph tags a query tag picks')
    # The pick: per query tag its k nearest eligible graph tags (kNN; a tie at the k-th
    # closeness is in). His 2026-10-08 "remove your dogleg and clustering package then for kNN":
    # the main cluster of all the query tags' cosines in one list stood here before and is
    # switched off, `main_cluster` kept in the module:
    #   clusters, lowest, _ = main_cluster(np.unique(rows[:, eligible], axis=0).ravel())
    #   picked_edge = rows[:, tag_e] >= lowest
    kth = np.array([np.sort(row[eligible])[::-1][min(k, int(eligible.sum())) - 1] for row in rows])
    picked_edge = (rows[:, tag_e] >= kth[:, None]) & eligible[tag_e]
    pick = {'k': k, 'kth_closeness': kth.tolist(),
            'graph_tags_per_query_tag': ((rows[:, eligible] >= kth[:, None])).sum(axis=1).tolist(),
            'graph_tags': int((rows[:, eligible] >= kth[:, None]).any(axis=0).sum())}
    # The facet ranking on the edge (his 2026-10-05 "use the actual real value they have, the
    # ranking", 2026-10-09 "the facet RANKINGS on the chunk to tag edges"): per edge the four
    # ranking facets ordered by their values, 0 the strongest. A query tag names one facet; its
    # picked edges are ordered by where that facet stands in the edge's own ranking, then topic,
    # then closeness; the other three facets do not enter. The facets' main clusters (dogleg)
    # and the gap classes stood here before and are switched off.
    used = picked_edge.any(axis=0)
    rank_in_edge = np.argsort(np.argsort(-raw[:, 1:], axis=1, kind='stable'), axis=1)
    facet_top = {name: {'first_in_picked_edges': int((rank_in_edge[used, j] == 0).sum())}
                 for j, name in enumerate(RANKING_FACETS)}
    orders = np.array([[int(f)] + [j for j in range(len(RANKING_FACETS)) if j != int(f)]
                       for f in named], dtype=np.int64)
    facet_class = np.zeros((chunk_e.size, len(FACETS)), dtype=np.int64)
    bulk, spread = np.zeros(count), np.zeros(count)
    value = np.zeros((count, n))
    best_edge = np.zeros((count, n), dtype=np.int64)
    for i in range(count):
        z, bulk[i], spread[i] = standing(rows[i][eligible])
        fit_of_tag = np.zeros(eligible.size)
        fit_of_tag[eligible] = np.clip(z, 0., None)
        fit_edge = fit_of_tag[tag_e]
        edge_cosines = rows[i][tag_e]
        closest = float(rows[i][eligible].max())
        picked = np.flatnonzero(picked_edge[i])
        width = max(closest - float(kth[i]), 0.)
        if picked.size and width > 0:
            classes = np.zeros((picked.size, len(FACETS)), dtype=np.int64)
            classes[:, named[i]] = rank_in_edge[picked, named[i]]
            _, placed = spread_by_facets(edge_cosines[picked], closest,
                                         width * (1. + 1e-9) + 1e-12,
                                         classes, orders[i], raw[picked, 0])
            moved = edge_cosines.copy()
            moved[picked] = placed
            fit_edge = np.clip((moved - bulk[i]) / spread[i], 0., None)
        best, best_edge[i] = best_edges(fit_edge, chunk_e, n)
        value[i] = np.where(layer['n_c'] > 0, best, 0.)
    weight = centrality(query['description_cosines'])
    if weight.shape != (count,):
        raise ValueError('Expected one description cosine per query tag')
    terms = weight[:, None] * value
    winner = np.argmax(terms, axis=0)
    every = np.arange(n)
    tags = terms[winner, every]
    has_edge = layer['n_c'] > 0
    win_edge = np.where(has_edge, best_edge[winner, every], -1)
    slots = np.zeros((n, len(RANKING_FACETS)))
    held = np.flatnonzero(has_edge)
    slots[held] = np.take_along_axis(pos[win_edge[held]][:, 1:], orders[winner[held]], axis=1)
    d, d_bulk, d_spread = standing(query['d_description'])
    q, q_bulk, q_spread = standing(query['d_question'])
    if d.shape != (n,) or q.shape != (n,):
        raise ValueError('Expected one description cosine and one question cosine per chunk')
    text = np.maximum(d, q)
    base = tags + text
    product = layer['product']
    product_mean = np.bincount(product, weights=base) / np.bincount(product)
    left = base - product_mean[product]
    lift = {'product': group_lift(base, *layer['groups']['product'], float(base.mean())),
            'near': group_lift(left, *layer['groups']['near'],
                               kind_reference(left, layer['near'] >= 0, layer['kind']))}
    strength = base + (lift['product'] + lift['near'])
    step = float(cos_noise) / float(np.median(spread))
    level = np.floor((strength.max() - strength) / step).astype(np.int64)
    keys = [layer['id_rank']] + [-slots[:, k] for k in range(len(RANKING_FACETS) - 1, -1, -1)]
    order = np.lexsort((*keys, ~has_edge, level)).tolist()
    return {'order': order, 'strength': strength, 'level': level, 'step': step,
            'tags': tags, 'text': text, 'lift': lift, 'winner': winner, 'win_edge': win_edge,
            'has_edge': has_edge, 'picked_edge': picked_edge, 'pick': pick,
            'facet_classes': facet_top, 'facet_class': facet_class, 'rank_in_edge': rank_in_edge,
            'facet_orders': orders, 'bulk': bulk, 'spread': spread,
            'centrality': weight, 'D': d, 'Qs': q,
            'text_bulk': {'description': d_bulk, 'question': q_bulk},
            'text_spread': {'description': d_spread, 'question': q_spread}}


CLOUD_SHAPES = ('as_is', 'spread', 'unit', 'order')
PLACE_NAMES = ('tags', 'description', 'chunk_desc', 'question', 'hits', 'topic', 'tags_to_desc')


def shaped(values, shape):
    """One place's numbers per chunk in one shape. 'as_is': as they are. 'spread': the middle
    off and the spread divided out (`standing`). 'unit': the smallest to 0 and the largest to
    1. 'order': the share of the chunks below, ties sharing."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or not values.size or not np.isfinite(values).all():
        raise ValueError('Expected a nonempty row of finite values')
    if shape == 'as_is':
        return values
    if shape == 'spread':
        return standing(values)[0]
    if shape == 'unit':
        low, high = float(values.min()), float(values.max())
        if not high > low:
            raise ValueError('The values are all equal')
        return (values - low) / (high - low)
    if shape == 'order':
        return (rankdata(values, method='average') - 0.5) / values.size
    raise ValueError(f'Unknown shape {shape!r}; expected one of {CLOUD_SHAPES}')


def groups_on_the_line(totals, fixed=None):
    """The totals clustered on the line, the number of groups left to the clustering. For every
    number of groups from 2 to one less than the number of totals: the split into neighbouring
    groups with the least squared distance to the group means (exact, by dynamic programming).
    Of those splits the one with the largest mean silhouette is taken, the fewer groups on a
    tie; with `fixed` given, the split into that many groups is taken instead. Returns each
    total's group (0 the lowest) and the number of groups; one group when fewer than three
    totals differ."""
    totals = np.asarray(totals, dtype=np.float64)
    if totals.ndim != 1 or not totals.size or not np.isfinite(totals).all():
        raise ValueError('Expected a nonempty row of finite totals')
    n = totals.size
    by = np.argsort(totals, kind='stable')
    x = totals[by] - totals.mean()
    if np.unique(x).size < 3:
        return np.zeros(n, dtype=np.int64), 1
    if fixed is not None and not (type(fixed) is int and 2 <= fixed < n):
        raise ValueError('Expected a fixed number of groups from 2 to one less than the totals')
    s1 = np.concatenate(([0.], np.cumsum(x)))
    s2 = np.concatenate(([0.], np.cumsum(x * x)))
    at = np.arange(n)
    j, i = np.meshgrid(at, at, indexing='ij')
    inside = i >= j
    size = np.where(inside, i - j + 1, 1).astype(np.float64)
    cost = np.where(inside, np.maximum(s2[i + 1] - s2[j] - (s1[i + 1] - s1[j]) ** 2 / size, 0.),
                    np.inf)
    prev = cost[0].copy()
    back = [np.zeros(n, dtype=np.int64)]
    best = (-np.inf, 1, np.array([0]), np.array([n - 1]))
    for count in range(2, n):
        lead = np.full(n, np.inf)
        lead[1:] = prev[:-1]
        table = lead[:, None] + cost
        start = np.argmin(table, axis=0)
        prev = table[start, at]
        back.append(start)
        starts, end = np.empty(count, dtype=np.int64), n - 1
        for g in range(count - 1, -1, -1):
            starts[g] = back[g][end] if g else 0
            end = starts[g] - 1
        ends = np.concatenate((starts[1:] - 1, [n - 1]))
        members = ends - starts + 1
        means = (s1[ends + 1] - s1[starts]) / members
        of = np.repeat(np.arange(count), members)
        low, high, m = starts[of], ends[of], members[of]
        within = (x * (at - low) - (s1[at] - s1[low])
                  + (s1[high + 1] - s1[at + 1]) - x * (high - at))
        a = np.where(m > 1, within / np.maximum(m - 1, 1), 0.)
        left = np.where(of > 0, x - means[np.maximum(of - 1, 0)], np.inf)
        right = np.where(of < count - 1, means[np.minimum(of + 1, count - 1)] - x, np.inf)
        b = np.minimum(left, right)
        widest = np.maximum(a, b)
        silhouette = np.where((m > 1) & (widest > 0), (b - a) / np.where(widest > 0, widest, 1.),
                              0.)
        score = float(silhouette.mean())
        if fixed is not None:
            if count == fixed:
                best = (score, count, starts, ends)
                break
        elif score > best[0]:
            best = (score, count, starts, ends)
    _, count, starts, ends = best
    group = np.empty(n, dtype=np.int64)
    group[by] = np.repeat(np.arange(count), ends - starts + 1)
    return group, int(count)


def place_numbers(names, walked, layer, tags_to_chunks=None):
    """Per named place its number per chunk, from one question's `chain` result. tags: the
    chain's tag value. description: the larger of the description's and the question's
    standing. chunk_desc, question: each of those two alone. hits: 1 for a chunk that carries a
    tag picked for a query tag, else 0. topic: the largest topic value on such a link, 0 with
    none. tags_to_desc: the mean over the query tags of the tag's cosine to the chunk
    description (`tags_to_chunks`, query tags by chunks)."""
    n, edge_chunk = layer['chunks'], layer['edge_chunk']
    same = walked['picked_edge'].any(axis=0)
    out = {}
    for name in names:
        if name == 'tags':
            out[name] = walked['tags']
        elif name == 'description':
            out[name] = walked['text']
        elif name == 'chunk_desc':
            out[name] = walked['D']
        elif name == 'question':
            out[name] = walked['Qs']
        elif name == 'hits':
            out[name] = np.zeros(n)
            out[name][edge_chunk[same]] = 1.
        elif name == 'topic':
            out[name] = np.zeros(n)
            np.maximum.at(out[name], edge_chunk[same], layer['raw'][same, 0])
        elif name == 'tags_to_desc':
            rows = np.asarray(tags_to_chunks, dtype=np.float64)
            if rows.ndim != 2 or rows.shape[1] != n or not np.isfinite(rows).all():
                raise ValueError('Expected one finite cosine per query tag and chunk')
            out[name] = rows.mean(axis=0)
        else:
            raise ValueError(f'Unknown place {name!r}; expected one of {PLACE_NAMES}')
    return out


def scope_clouds(places, levels, shape, fixed=None):
    """The chunks under the scopes that hold the largest clouds. places: per place its number
    per chunk; levels: per level of the tree its scopes as (name, chunk indices); shape: one
    shape, or one per place. Per place and
    level every scope's shaped numbers are added up, the totals are clustered
    (`groups_on_the_line`, into `fixed` groups when given) and the scopes of the top group are
    kept. A chunk stays when a scope it hangs under is kept for any place at any level. Returns
    the mask and, per place and level, the number of scopes and of groups, the kept scopes and
    the chunks under them."""
    keep, record = None, {}
    for place, values in places.items():
        numbers = shaped(values, shape[place] if isinstance(shape, dict) else shape)
        if keep is None:
            keep = np.zeros(numbers.size, dtype=bool)
        if numbers.shape != keep.shape:
            raise ValueError('Expected one number per chunk in every place')
        record[place] = {}
        for level, scopes in levels.items():
            totals = np.array([float(numbers[members].sum()) for _, members in scopes])
            group, count = groups_on_the_line(totals, fixed)
            top = np.flatnonzero(group == count - 1)
            held = np.zeros(numbers.size, dtype=bool)
            for t in top:
                held[scopes[t][1]] = True
            keep |= held
            record[place][level] = {'scopes': len(scopes), 'groups': count,
                                    'kept': [scopes[t][0] for t in top],
                                    'chunks': int(held.sum())}
    if keep is None:
        raise ValueError('Expected at least one place')
    return keep, record


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


def level_relevancy(level, count):
    """A level as a number from 0 to 1: level 1 is 1, the levels step evenly down, and a value
    in no level is 0."""
    level = np.asarray(level, dtype=np.int64)
    if not count:
        return np.zeros(level.size)
    return np.where(level > 0, (count - level + 1) / count, 0.)


LEVEL_PLACES = ('tags', 'chunk_desc', 'question')


def level_places(names, cosines, layer, d_description, d_question, depth=None):
    """Per named place each chunk's 0-1 relevancy from the levels (`levels_of`,
    `level_relevancy`). tags: per query tag the eligible graph tags are levelled over its own
    cosines; a chunk takes the largest relevancy among its tags, over the query tags.
    chunk_desc, question: the chunks are levelled over the description's, the question's
    cosines to the chunk descriptions. With `depth` only that many nearest levels count as
    hit. Returns the relevancy per place and, per place, the level sizes from the nearest (per
    query tag for tags)."""
    eligible, n = layer['eligible'], layer['chunks']
    if depth is not None and not (type(depth) is int and depth >= 1):
        raise ValueError('Expected a depth of at least one level')

    def levels(row):
        level, count = levels_of(row)
        if depth is not None and count > depth:
            level, count = np.where(level > depth, 0, level), depth
        return level, count

    out, record = {}, {}
    for name in names:
        if name == 'tags':
            best, sizes = np.zeros(n), []
            for row in np.asarray(cosines, dtype=np.float64):
                level, count = levels(row[eligible])
                of_tag = np.zeros(eligible.size)
                of_tag[eligible] = level_relevancy(level, count)
                per_chunk = np.zeros(n)
                np.maximum.at(per_chunk, layer['edge_chunk'], of_tag[layer['edge_tag']])
                best = np.maximum(best, per_chunk)
                sizes.append(np.bincount(level, minlength=count + 1)[1:].tolist())
            out[name], record[name] = best, sizes
        elif name in ('chunk_desc', 'question'):
            row = np.asarray(d_description if name == 'chunk_desc' else d_question,
                             dtype=np.float64)
            level, count = levels(row)
            out[name] = level_relevancy(level, count)
            record[name] = np.bincount(level, minlength=count + 1)[1:].tolist()
        else:
            raise ValueError(f'Unknown place {name!r}; expected one of {LEVEL_PLACES}')
    return out, record


def level_clouds(relevancy, scopes):
    """The chunks under the scopes that hold the largest clouds of relevancy. relevancy: per
    chunk its 0-1 number; scopes: each chunk's own scope as (path, chunk indices), a path's
    parent being the path one step up. A cloud is a scope's relevancy added up, where that is
    above 0. The clouds, from the largest down, are split at their knee: those above it are the
    largest clouds and are kept; with no knee every cloud is. A cloud below the knee, a
    minority, is kept when it has the same parent as a largest cloud. Everything else is cut;
    with no cloud nothing is cut. Returns the mask and the clouds with their sizes, the
    largest and the minorities kept."""
    relevancy = np.asarray(relevancy, dtype=np.float64)
    if relevancy.ndim != 1 or not np.isfinite(relevancy).all() or (relevancy < 0).any():
        raise ValueError('Expected one finite non-negative relevancy per chunk')
    sizes = [(float(relevancy[members].sum()), path, members) for path, members in scopes]
    clouds = sorted((c for c in sizes if c[0] > 0.), key=lambda c: (-c[0], c[1]))
    keep = np.zeros(relevancy.size, dtype=bool)
    record = {'hit_chunks': int((relevancy > 0).sum()), 'clouds': len(clouds),
              'largest': [], 'minorities': []}
    if not clouds:
        keep[:] = True
        return keep, record
    at = knee([size for size, _, _ in clouds])
    largest = clouds[:at] if at >= 1 else clouds
    parents = {path.rsplit('/', 1)[0] for _, path, _ in largest if '/' in path}
    for size, path, members in largest:
        keep[members] = True
        record['largest'].append({'scope': path, 'relevancy': size, 'chunks': int(len(members))})
    for size, path, members in clouds[len(largest):]:
        if '/' in path and path.rsplit('/', 1)[0] in parents:
            keep[members] = True
            record['minorities'].append({'scope': path, 'relevancy': size,
                                         'chunks': int(len(members))})
    return keep, record


def top_cluster(values, above_middle=False):
    """The cluster that stands apart at the top of a list of values, by clustering on the
    distances between the values themselves: neighbours on the line are merged in the order of
    the distance between them (single linkage), and the merging is cut where the merge distances
    jump most. Returns a mask of the values in the cluster that holds the largest value; all
    False when the values do not come apart (fewer than three, or no jump), and with
    `above_middle` only the values above the middle are clustered."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError('Expected a row of finite values')
    out = np.zeros(values.size, dtype=bool)
    at = np.flatnonzero(values > np.median(values)) if above_middle else np.arange(values.size)
    if at.size < 3:
        return out
    by = at[np.argsort(-values[at], kind='stable')]
    steps = values[by][:-1] - values[by][1:]          # merge distances, nearest value first
    heights = np.sort(steps)
    jumps = np.diff(heights)
    if not jumps.size or not jumps.max() > 1e-12:
        return out
    cut = heights[int(np.flatnonzero(jumps == jumps.max())[-1]) + 1]
    apart = np.flatnonzero(steps >= cut)             # the first step that separates
    out[by[:int(apart[0]) + 1]] = True
    return out


CLUSTER_PLACES = ('relevance', 'tags', 'chunk_desc', 'question')


def cluster_hits(names, walked, layer, d_description, d_question):
    """Per named place the chunks that are hit, decided by the clustering (`main_cluster`, the
    dogleg deciding). relevance: the chunks in the main cluster of the chain's strength (his
    2026-10-07 "the clustering here is just a gauge of where the most relevance seems to
    lie"). tags: the chunks in the main cluster of the chain's tag value, among the chunks
    that carry a picked edge. chunk_desc, question: the chunks in the main cluster of the
    chunk descriptions' closeness to the query description, to the question. Returns the mask
    per place and, per place, the number of clusters and the main cluster's lowest value."""
    n = layer['chunks']
    out, record = {}, {}
    for name in names:
        if name == 'relevance':
            clusters, lowest, mask = main_cluster(walked['strength'])
        elif name == 'tags':
            carries = np.zeros(n, dtype=bool)
            carries[layer['edge_chunk'][walked['picked_edge'].any(axis=0)]] = True
            mask = np.zeros(n, dtype=bool)
            if carries.sum() >= 3:
                clusters, lowest, inside = main_cluster(walked['tags'][carries])
                mask[np.flatnonzero(carries)[inside]] = True
            else:
                clusters, lowest, mask = 1, float('nan'), carries
        elif name in ('chunk_desc', 'question'):
            row = d_description if name == 'chunk_desc' else d_question
            clusters, lowest, mask = main_cluster(row)
        else:
            raise ValueError(f'Unknown place {name!r}; expected one of {CLUSTER_PLACES}')
        out[name] = mask
        record[name] = {'clusters': clusters, 'lowest': lowest, 'chunks': int(mask.sum())}
    return out, record


def levels(values, k):
    """The values cut into k clusters on the line, the number given and not found (his
    2026-10-09 "what if we force the n of k in the kNN instead?"): least squares, the values
    gathered into CLUSTER_BINS equal-width bins first as `main_cluster` does. Returns each
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


def border_by_nearness(nearness, branches, k):
    """The border from one list of nearness values (his 2026-10-10 "What if chunk desc and their
    scope sets the first border?", "the first ... kNN clusters"): the values cut into k clusters
    (`levels`), the first is the near chunks; the branch most of them sit in is the border, and
    every branch that ties it. branches: branch -> chunk indices. Returns the mask per chunk and
    the record."""
    x = np.asarray(nearness, dtype=np.float64)
    near = levels(x, k) == 1
    names = sorted(branches)
    counts = np.array([int(near[np.asarray(branches[name], dtype=np.int64)].sum()) for name in names])
    keep = np.zeros(x.size, dtype=bool)
    kept = [name for name, count in zip(names, counts) if count and count == counts.max()]
    for name in kept:
        keep[np.asarray(branches[name], dtype=np.int64)] = True
    if not kept:
        keep[:] = True
    by = np.argsort(-counts, kind='stable')
    return keep, {'k': k, 'near_chunks': int(near.sum()), 'lowest': float(x[near].min()),
                  'branches': [{'branch': names[b], 'near_chunks': int(counts[b])}
                               for b in by if counts[b]],
                  'kept': kept, 'nothing_cut': not kept}


def in_turn(orders):
    """One chunk from each order in turn, a chunk taken once. Returns the chunks and, per chunk,
    the index of the order whose turn brought it."""
    out, source, seen = [], [], set()
    for row in zip(*orders):
        for which, i in enumerate(row):
            i = int(i)
            if i not in seen:
                seen.add(i)
                out.append(i)
                source.append(which)
    return out, source


def both_sides(layer, cosines, named_facet, d_near, scopes, branches, k):
    """The retrieval with both sides guiding (his 2026-10-10 "now i want to do the both, side by
    side, together, either cleanly, or overlapping clouds for each step"; overlapping clouds
    for each step is what stands here). No strength is made.

    A chunk has a nearness on each side. Through its tags: the closeness of its closest eligible
    tag to a query tag, the largest over the query tags. By its description: `d_near`, the
    description's closeness to the query description. A cloud is the first of the k clusters a
    list of nearness values is cut into (`levels`).

    The scope step   each side's nearness cloud over all chunks, and its scope cloud: the same
                     nearness per scope (the mean over the scope's chunks), cut the same way.
                     The scopes that both scope clouds hold, and that hold a chunk both nearness
                     clouds hold, are the main scopes; their branches with everything under them
                     are the border. With no such scope nothing is cut.
    The inside step  both sides are cut again over the chunks of the border. The chunks both
                     clouds hold come first, then the chunks one cloud holds, then the rest.
                     Inside each of the three the tags give the order: the cluster of the
                     chunk's nearness through its tags, then where the query tag's named facet
                     stands among the four facets of that edge (0 the strongest), then that
                     nearness, then chunk id.

    scopes: each chunk's own scope as (path, chunk indices), a scope's branch being the first
    part of its path; branches: branch -> chunk indices. Returns the order (the border's chunks
    only), the border, what lies behind the order per chunk, and the record of both steps."""
    n = layer['chunks']
    tag_e, chunk_e = layer['edge_tag'], layer['edge_chunk']
    rows = np.asarray(cosines, dtype=np.float64)
    named = np.asarray(named_facet, dtype=np.int64)
    d_near = np.asarray(d_near, dtype=np.float64)
    if rows.ndim != 2 or not rows.shape[0] or rows.shape[1] != layer['eligible'].size:
        raise ValueError('Expected one cosine row over the graph tags per query tag')
    if named.shape != (rows.shape[0],) or named.min() < 0 or named.max() >= len(RANKING_FACETS):
        raise ValueError('Expected one named ranking facet per query tag')
    if d_near.shape != (n,) or not np.isfinite(d_near).all():
        raise ValueError('Expected one finite description closeness per chunk')
    if not scopes:
        raise ValueError('Expected the scopes of the tree')
    on_edge = rows[:, tag_e]                               # (query tags, eligible edges)
    if not on_edge.size or not np.isfinite(on_edge).all():
        raise ValueError('Expected finite cosines over the eligible graph tags')
    edge_query = on_edge.argmax(axis=0)
    t_near, t_edge = best_edges(on_edge.max(axis=0), chunk_e, n)
    has_edge = t_edge >= 0
    # a chunk with no eligible edge stands with the farthest
    t_near = np.where(has_edge, t_near, t_near[has_edge].min())
    query_tag = np.where(has_edge, edge_query[np.maximum(t_edge, 0)], -1)
    rank_in_edge = np.argsort(np.argsort(-layer['raw'][:, 1:], axis=1, kind='stable'), axis=1)
    facet_rank = np.full(n, len(RANKING_FACETS), dtype=np.int64)
    facet_rank[has_edge] = rank_in_edge[t_edge[has_edge], named[query_tag[has_edge]]]

    sides = {'tags': t_near, 'description': d_near}
    cloud = {name: levels(x, k) == 1 for name, x in sides.items()}
    scope_cloud = {name: levels(np.array([x[members].mean() for _, members in scopes]), k) == 1
                   for name, x in sides.items()}
    in_both = cloud['tags'] & cloud['description']
    shared = np.flatnonzero(scope_cloud['tags'] & scope_cloud['description'])
    main = [int(i) for i in shared if in_both[scopes[i][1]].any()]
    kept = sorted({scopes[i][0].split('/')[0] for i in main})
    border = np.zeros(n, dtype=bool)
    for name in kept:
        border[branches[name]] = True
    if not kept:
        border[:] = True

    where = np.flatnonzero(border)
    level = {name: np.zeros(n, dtype=np.int64) for name in sides}
    for name, x in sides.items():
        level[name][where] = levels(x[where], k)
    group = np.full(n, -1, dtype=np.int64)
    group[where] = (2 - (level['tags'][where] == 1).astype(np.int64)
                    - (level['description'][where] == 1).astype(np.int64))
    by = np.lexsort((layer['id_rank'][where], -t_near[where], facet_rank[where],
                     level['tags'][where], group[where]))
    record = {
        'k': k,
        'nearness_clouds': {name: {'chunks': int(cloud[name].sum()),
                                   'lowest': float(sides[name][cloud[name]].min())}
                            for name in sides},
        'chunks_in_both_nearness_clouds': int(in_both.sum()),
        'scopes': len(scopes),
        'scope_clouds': {name: int(scope_cloud[name].sum()) for name in sides},
        'scopes_in_both_scope_clouds': int(shared.size),
        'main_scopes': [scopes[i][0] for i in main],
        'branches': kept,
        'nothing_cut': not kept,
        'inside': {'chunks': int(where.size),
                   'clouds': {name: int((level[name][where] == 1).sum()) for name in sides},
                   'in_both': int((group[where] == 0).sum()),
                   'in_one': int((group[where] == 1).sum()),
                   'in_neither': int((group[where] == 2).sum())}}
    return {'order': where[by].tolist(), 'border': border, 'tags_nearness': t_near,
            'description_nearness': d_near, 'edge': t_edge, 'query_tag': query_tag,
            'facet_rank': facet_rank, 'level': level, 'group': group, 'record': record}


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


def facets_in_equal_closeness(layer, t_near, t_edge, query_tag, orders, inside, k):
    """The query's facets on the tags side (his 2026-08-31 "the facetweights from the QUERY,
    determines how many fucks the retrieval take to each tag's facets", 2026-09-05 "multi-key
    sort", 2026-09-06 "equal if within a certain range", 2026-10-15 "influence the already
    existing relationship for chunks and tags", "its a RANKING system").

    The tags side's closeness stays the main weight: over the border it is cut into k clusters
    (`levels`), the range inside which chunks count as equal. Each query tag brings the facets that
    steer for it, most important first (an empty list when none does). Inside a cluster the chunks
    whose query tag has a steering facet are put in order by their edge's places in those facets'
    rankings, the first facet first, then the next where equal, and the closeness values they hold,
    highest first, are dealt out among them in that order. No value leaves its cluster and none is
    made. A chunk with no eligible edge, or whose query tag has no steering facet, keeps its own.

    t_near, t_edge: `tags_nearness`; query_tag: per chunk the query tag its closest tag answers
    to; orders: per query tag the steering ranking facets in their order. Returns the dealt
    closeness per chunk and the record."""
    n = layer['chunks']
    t_near = np.asarray(t_near, dtype=np.float64)
    t_edge = np.asarray(t_edge, dtype=np.int64)
    query_tag = np.asarray(query_tag, dtype=np.int64)
    inside = np.asarray(inside, dtype=np.int64)
    if t_near.shape != (n,) or t_edge.shape != (n,) or query_tag.shape != (n,):
        raise ValueError('Expected one closeness, one edge and one query tag per chunk')
    four = len(RANKING_FACETS)
    if any(len(set(int(f) for f in order)) != len(order) or any(not 0 <= int(f) < four for f in order)
           for order in orders):
        raise ValueError("Expected distinct ranking facets in each query tag's order")
    place = layer['pos'][:, 1:]
    out = t_near.copy()
    level = levels(t_near[inside], k)
    dealt = 0

    def key(c):
        steer = [-place[t_edge[c], int(f)] for f in orders[query_tag[c]]]
        return tuple(steer + [0.] * (four - len(steer))) + (-t_near[c], int(layer['id_rank'][c]))

    for lv in np.unique(level).tolist():
        members = [int(c) for c in inside[level == lv] if t_edge[c] >= 0 and orders[query_tag[c]]]
        if len(members) < 2:
            continue
        for c, value in zip(sorted(members, key=key), np.sort(t_near[members])[::-1].tolist()):
            dealt += out[c] != value
            out[c] = value
    return out, {'clusters': int(np.unique(level).size), 'chunks_dealt_another_closeness': int(dealt)}


def facet_influenced_nearness(layer, cosines, weights):
    """The query's facets as an influence on the tag relationship, not an order (his 2026-10-15
    "they are supposed to influence the already existing relationship for chunks and tags",
    2026-10-16 "YOU CANNOT FORCE THEM TO TRY AND CHANGE THE FUCKING ORDERS"; 2026-08-31 "the
    facetweights from the QUERY, determines how many fucks the retrieval take to each tag's
    facets"; 2026-09-18 "the main weight on a tag is the topic one, and the others adjust that
    weight").

    An edge's weight for a query tag is the tag's closeness to it, the existing relationship.
    The facets add to it: for each facet, the query tag's weight for that facet (0 when the facet
    does not matter for the question, up to 1) times where the edge stands in that facet's ranking
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
    place = layer['pos'][:, 1:]
    middle = np.median(place, axis=0)
    spread_place = MAD_TO_SPREAD * np.median(np.abs(place - middle), axis=0)
    stands = np.where(spread_place > 0, (place - middle) / np.where(spread_place > 0, spread_place, 1.), 0.)
    eligible = layer['eligible']
    spread_close = np.array([MAD_TO_SPREAD * float(np.median(np.abs(r[eligible] - np.median(r[eligible]))))
                             for r in rows])
    on_edge = rows[:, tag_e] + spread_close[:, None] * (weights @ stands.T)
    best_q = on_edge.argmax(axis=0)
    value = on_edge[best_q, np.arange(tag_e.size)]
    near, edge = best_edges(value, chunk_e, n)
    has = edge >= 0
    query_tag = np.where(has, best_q[np.maximum(edge, 0)], -1)
    return np.where(has, near, near[has].min()), edge, query_tag


def facet_levels(values):
    """Per ranking facet the levels its values over the graph's edges fall into, read off the
    values themselves (`levels_of`, the knees deciding how many): the lowest value of each level,
    level 1 the highest. A reading at or above a level's lowest value stands in that level; below
    all of them it stands in none (at or below the middle edge, or beyond the first knee)."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(RANKING_FACETS):
        raise ValueError('Expected the four ranking facets per edge')
    out = []
    for f in range(values.shape[1]):
        level, count = levels_of(values[:, f])
        out.append([float(values[level == lv, f].min()) for lv in range(1, count + 1)])
    return out


def facet_level(reading, floors):
    """The level a reading stands in among one facet's levels (`facet_levels`); 0 for none."""
    for lv, floor in enumerate(floors, 1):
        if reading >= floor:
            return lv
    return 0


def cloud_combo(layer, cosines, d_near, inside, scope_of, k, tags_near=None):
    """The chunk cloud and the tags' cloud together, over the chunks of a border (his 2026-10-12
    "the combo should fucking work.. So, if we use the chunk-cloud, see if you can find a way to
    combo or lift with the tags", his 2026-10-10 "overlapping clouds for each step"). No
    strength is made and no facet is read.

    A chunk has a nearness on each side. Through its tags: the closeness of its closest eligible
    tag to a query tag, the largest over the query tags (`tags_nearness`). By its description:
    `d_near`, the description's closeness to what the chunk side is asked with. Over the
    border's chunks each list is cut into k clusters (`levels`, 1 the nearest).

    The step     a chunk's two levels added: 2 where both sides put it in their first cluster,
                 then 3, and so on down.
    The scope    gauged after the steps, from the chunks on the first two of them (step 2 and
                 3; with none there, the lowest step there is): the scopes holding the majority
                 of those chunks (`majority_scopes`). It is weight and not a cut: inside a step
                 the chunks in scope come first.
    The order    the step, then in scope first, then the two sides' standings added (each
                 nearness less its middle over its spread, over the border), then chunk id.

    inside: the border's chunk indices; scope_of: per chunk the number of its scope; tags_near:
    the tags side's closeness per chunk when it was made otherwise (`facets_in_equal_closeness`),
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
        level[name][inside] = levels(here, k)
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
    record = {'k': k, 'chunks': int(inside.size),
              'clouds': {name: int((level[name][inside] == 1).sum()) for name in sides},
              'chunks_on_each_step': {int(s): int(c) for s, c in zip(steps, counts)},
              'scope_gauged_from_chunks': int(gauged_from.size),
              'scopes_taken': taken, 'chunks_in_scope': int(in_scope.sum())}
    return {'order': inside[by].tolist(), 'tags_nearness': t_near, 'description_nearness': d_near,
            'edge': t_edge, 'query_tag': query_tag, 'level': level, 'step': step,
            'in_scope': in_scope, 'value': value, 'record': record}


def facet_relations(layer, combo, inside):
    """The facets on the tag relations between chunks, used inside the combo's step (his
    2026-10-15 "they are supposed to influence the already existing relationship for chunks and
    tags" and "its a RANKING system"; the abstract's "weighted graph relations"; thesis 6.4: one
    tag name can have a different function depending on context). No number is made.

    Inside the border a tag's chunks are ranked against each other in each of the four ranking
    facets, by the places their edges have in the facets' rankings. An edge's role is the facet
    in which its chunk ranks best among the tag's chunks, the first of RANKING_FACETS on a tie.
    A tag ties two chunks only where its role is the same on both edges. A chunk tied that way to
    one of the strongest hits (the chunks the scope is gauged from: the first two steps) comes
    first inside its step and its side of the scope; then the two standings added, then chunk
    id.

    combo: `cloud_combo`'s answer over the border's chunks `inside`. Returns the order (the
    border's chunks), per chunk whether it is tied, per tied chunk the hit, the tag and the facet
    that tie it (the first found, the hits taken in the combo's order), and the record."""
    n = layer['chunks']
    inside = np.asarray(inside, dtype=np.int64)
    step, in_scope, value = combo['step'], combo['in_scope'], combo['value']
    if step.shape != (n,) or in_scope.shape != (n,) or value.shape != (n,):
        raise ValueError("Expected the combo's step, scope and value per chunk")
    member = np.zeros(n, dtype=bool)
    member[inside] = True
    tag_e, chunk_e, place = layer['edge_tag'], layer['edge_chunk'], layer['pos'][:, 1:]
    by_tag, by_chunk = {}, {}
    for e in np.flatnonzero(member[chunk_e]).tolist():
        by_tag.setdefault(int(tag_e[e]), []).append(e)
        by_chunk.setdefault(int(chunk_e[e]), []).append(e)
    roles = {}

    def role_of(t):
        if t not in roles:
            edges = np.array(by_tag[t])
            ranks = np.column_stack([rankdata(-place[edges, f]) for f in range(place.shape[1])])
            roles[t] = dict(zip(edges.tolist(), np.argmin(ranks, axis=1).tolist()))
        return roles[t]

    lowest = int(step[inside].min())
    hits = [i for i in combo['order'] if step[i] <= max(3, lowest)]
    tied = np.zeros(n, dtype=bool)
    path = {}
    for h in hits:
        for e1 in by_chunk.get(h, []):
            t = int(tag_e[e1])
            if len(by_tag[t]) < 2:
                continue
            role = role_of(t)
            for e2 in by_tag[t]:
                c = int(chunk_e[e2])
                if c != h and role[e2] == role[e1] and not tied[c]:
                    tied[c] = True
                    path[c] = (int(h), t, int(role[e1]))
    by = np.lexsort((layer['id_rank'][inside], -value[inside], ~tied[inside], ~in_scope[inside],
                     step[inside]))
    facets = [f for _, _, f in path.values()]
    record = {'strongest_hits': len(hits), 'chunks_tied': int(tied[inside].sum()),
              'tied_by_facet': {name: facets.count(j) for j, name in enumerate(RANKING_FACETS)}}
    return {'order': inside[by].tolist(), 'tied': tied, 'path': path, 'record': record}


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


def scope_by_tags(picked_edge, cosines, facet_class, orders, layer, scopes, depth=0,
                  majority=False):
    """The scope read off the picked tags after the facets have judged their edges (his
    2026-10-08 "first tags, then clustering on them, THEN check the scope on all tags ... we
    only have relevant tags meaning we only have relevant scope, so we can take the scopes of
    the greatest cluster(s)? and then after that, we do the facets sorting"). Per query tag,
    its picked edges that lie in the top class of its first `depth` facets (`facet_class` 0 in
    the column, the facets in the query tag's `orders`); `depth` 0 is every picked edge, the
    step as it stands (his 2026-10-09 "Is this correct?": the facet cut in front of the scope
    was the agent's and is off). A scope's value: with `majority` its picked edges counted
    (his 2026-10-09 "if majority of something, BRANCH is chosen"); otherwise the tags of those
    edges, each tag once with its closeness (the largest over the query tags), added up; the
    scopes' values in one list, the main cluster (`main_cluster`, the dogleg deciding) is the
    greatest cluster of scopes and its chunks are kept, the others cut. The depth and the
    adding up are the agent's choice. Returns the mask per chunk and the record: how many
    edges survive each depth, the scopes with a surviving tag, the number of clusters, the
    kept scopes with their value and their tags."""
    picked_edge = np.asarray(picked_edge, dtype=bool)
    cosines = np.asarray(cosines, dtype=np.float64)
    facet_class = np.asarray(facet_class, dtype=np.int64)
    orders = np.asarray(orders, dtype=np.int64)
    edge_tag, edge_chunk = layer['edge_tag'], layer['edge_chunk']
    closeness = cosines.max(axis=0)                         # per graph tag, over the query tags
    keep = np.zeros(layer['chunks'], dtype=bool)
    record = {'picked_edges': int(picked_edge.any(axis=0).sum()), 'depth': int(depth),
              'edges_surviving_by_depth': [], 'scopes_with_a_tag': 0, 'clusters': 0,
              'lowest': None, 'kept': []}
    survive = {}
    for d in range(1, orders.shape[1] + 1):
        inside = picked_edge.copy()
        for i in range(orders.shape[0]):
            for j in orders[i, :d]:
                inside[i] &= facet_class[:, j] == 0
        survive[d] = inside.any(axis=0)
        record['edges_surviving_by_depth'].append(int(survive[d].sum()))
    chosen = survive[int(depth)] if depth else picked_edge.any(axis=0)
    if not chosen.any():
        keep[:] = True
        return keep, record
    chunk_scope = np.full(layer['chunks'], -1, dtype=np.int64)
    for k, (_, members) in enumerate(scopes):
        chunk_scope[members] = k
    held = {}
    for e in np.flatnonzero(chosen):
        k = int(chunk_scope[edge_chunk[e]])
        if k >= 0:
            held.setdefault(k, set()).add(int(edge_tag[e]))
    if not held:
        keep[:] = True
        return keep, record
    names = sorted(held)
    if majority:
        where = chunk_scope[edge_chunk[chosen]]
        counts = np.bincount(where[where >= 0], minlength=len(scopes))
        values = np.array([float(counts[k]) for k in names])
    else:
        values = np.array([closeness[list(held[k])].sum() for k in names])
    clusters, lowest, main = main_cluster(values)
    record.update({'scopes_with_a_tag': len(names), 'clusters': clusters, 'lowest': lowest})
    for k, value, inside in zip(names, values, main):
        if inside:
            keep[scopes[k][1]] = True
            record['kept'].append({'scope': scopes[k][0], 'value': float(value),
                                   'tags': len(held[k])})
    record['kept'].sort(key=lambda r: -r['value'])
    return keep, record


def scope_clusters(hit, scopes, formed):
    """The chunks under the largest clouds of the hit chunks, clustered by scope. hit: a mask
    per chunk; scopes: each chunk's own scope as (path, chunk indices), a path's parent being
    the path one step up. Two readings. `formed` False: the scopes are the clusters; a cloud is
    one scope's hit chunks; the largest clouds are the main cluster of the clouds' sizes
    (`main_cluster`, the dogleg deciding how many clusters); a cloud outside it, a minority,
    is kept when it has the same parent as a largest cloud. `formed` True: the
    clustering forms the clouds: scopes that hold hit chunks and have the same parent are one
    cloud, and the largest clouds are told the same way, whole. Everything else is cut; with no
    hit nothing is cut. Returns the mask and the clouds, the largest and the minorities."""
    hit = np.asarray(hit, dtype=bool)
    held = [(int(hit[members].sum()), path, members) for path, members in scopes]
    held = [c for c in held if c[0]]
    keep = np.zeros(hit.size, dtype=bool)
    record = {'hit_chunks': int(hit.sum()), 'hit_scopes': len(held), 'clouds': 0,
              'largest': [], 'minorities': []}
    if not held:
        keep[:] = True
        return keep, record

    def parent(path):
        return path.rsplit('/', 1)[0] if '/' in path else path

    if formed:
        groups = {}
        for size, path, members in held:
            groups.setdefault(parent(path), []).append((size, path, members))
        clouds = [(sum(s for s, _, _ in group), name, group) for name, group in groups.items()]
    else:
        clouds = [(size, path, [(size, path, members)]) for size, path, members in held]
    clouds.sort(key=lambda c: (-c[0], c[1]))
    record['clouds'] = len(clouds)
    record['size_clusters'], _, top = main_cluster([size for size, _, _ in clouds])
    parents = set()
    for (size, name, group), large in zip(clouds, top):
        if large:
            parents.add(parent(name))
            record['largest'].append({'cloud': name, 'hit_chunks': size,
                                      'scopes': [path for _, path, _ in group]})
            for _, _, members in group:
                keep[members] = True
    if not formed:
        for (size, name, group), large in zip(clouds, top):
            if not large and '/' in name and parent(name) in parents:
                record['minorities'].append({'cloud': name, 'hit_chunks': size})
                keep[group[0][2]] = True
    return keep, record


def tree_scan(hits, places, n, draws, seed):
    """The tree-based scan statistic (Kulldorff, Fang & Walsh 2003) of the hit chunks over the
    places of the tree. hits: chunk indices; places: (path, chunk indices) for every place at
    every level; n: the chunks in the pool. Per place: the hits it holds, the hits its share
    of the pool gives (hits in all times its chunks over n), and the log likelihood ratio
    c ln(c / e) + (C - c) ln((C - c) / (C - e)), 0 where it holds no more than its share. The
    same number of hits is then scattered over the pool at random `draws` times; of each
    scatter the largest ratio over the places is kept. Returns the three per place and the
    scatters' largest ratios."""
    hits = np.unique(np.asarray(hits, dtype=np.int64))
    if hits.size and (hits.min() < 0 or hits.max() >= n):
        raise ValueError('A hit chunk is out of range')
    if not places:
        raise ValueError('Expected the places of the tree')
    rows = np.concatenate([np.full(len(members), k, dtype=np.int64)
                           for k, (_, members) in enumerate(places)])
    cols = np.concatenate([np.asarray(members, dtype=np.int64) for _, members in places])
    under = csr_matrix((np.ones(rows.size), (rows, cols)), shape=(len(places), n))
    size = np.asarray(under.sum(axis=1)).ravel()
    total = float(hits.size)
    expected = total * size / n

    def ratio(held):
        e = expected if held.ndim == 1 else expected[:, None]
        out = np.zeros(held.shape)
        more = (held > e) & (e < total)
        c = held[more]
        e = np.broadcast_to(e, held.shape)[more]
        rest = total - c
        with np.errstate(divide='ignore', invalid='ignore'):
            out[more] = c * np.log(c / e) + np.where(rest > 0,
                                                     rest * np.log(rest / (total - e)), 0.)
        return out

    mark = np.zeros(n)
    mark[hits] = 1.
    held = under @ mark
    if not hits.size:
        return held, expected, np.zeros(len(places)), np.zeros(draws)
    rng = np.random.default_rng(seed)
    drawn = np.argpartition(rng.random((draws, n)), hits.size - 1, axis=1)[:, :hits.size]
    scatter = np.zeros((n, draws))
    scatter[drawn.ravel(), np.repeat(np.arange(draws), hits.size)] = 1.
    return held, expected, ratio(held), ratio(under @ scatter).max(axis=0)


def scan_clouds(hits, places, n, draws, seed):
    """The chunks under the places where the hit chunks gather (`tree_scan`). A place is a
    cloud when its ratio is larger than the largest ratio of every scatter; the clouds are
    taken from the largest ratio down, and a place that holds or lies under one already taken
    is left out. A deepest place that holds a hit and has the same parent as a taken place is
    kept beside them (a minority). Everything else is cut; with no cloud nothing is cut.
    Returns the mask and the record: the hits, the scatters' largest ratio, the clouds with
    their hits, expected hits and ratio, and the minorities kept."""
    held, expected, ratios, scatters = tree_scan(hits, places, n, draws, seed)
    bar = float(scatters.max()) if scatters.size else 0.
    paths = [path for path, _ in places]
    taken = []
    for k in np.argsort(-ratios, kind='stable'):
        if not ratios[k] > bar:
            break
        if any(paths[k] == t or paths[k].startswith(paths[t] + '/')
               or paths[t].startswith(paths[k] + '/') for t in taken):
            continue
        taken.append(int(k))
    record = {'hits': int(np.unique(np.asarray(hits, dtype=np.int64)).size),
              'scatters': int(scatters.size), 'largest_scatter_ratio': bar,
              'clouds': [{'place': paths[k], 'hits': int(held[k]),
                          'expected': float(expected[k]), 'ratio': float(ratios[k])}
                         for k in taken], 'minorities': []}
    keep = np.zeros(n, dtype=bool)
    if not taken:
        keep[:] = True
        return keep, record
    inner = {path.rsplit('/', 1)[0] for path in paths if '/' in path}
    parents = {paths[k].rsplit('/', 1)[0] for k in taken if '/' in paths[k]}
    for k in taken:
        keep[np.asarray(places[k][1], dtype=np.int64)] = True
    for k, path in enumerate(paths):
        if (held[k] > 0 and path not in inner and '/' in path
                and path.rsplit('/', 1)[0] in parents and not keep[places[k][1]].all()):
            keep[np.asarray(places[k][1], dtype=np.int64)] = True
            record['minorities'].append({'place': path, 'hits': int(held[k])})
    return keep, record
