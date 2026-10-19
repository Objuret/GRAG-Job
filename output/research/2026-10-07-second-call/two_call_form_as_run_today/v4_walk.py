"""artefact_v4's chain: one strength per chunk from its best tag, the description and the
question, and the lift of its product and its near group. Arrays in, arrays out.

Per query tag q (a row of cosines over the graph tags, five readings, a cosine to the query
description):
  fit        the cosine's standing over the eligible graph tags, (cosine - median) / spread,
             the spread 1.4826 times the median absolute deviation; below 0 counts as 0.
  the same   the graph tags at or above the same-thing level (`same_thing_level`) are the same
             thing as q. Their edges are put in order by the four facets in q's order (each
             facet in classes one gap wide), then topic, then the cosine, and spread evenly
             between q's closest tag and the level in that order. Every other edge keeps its
             cosine.
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


def facet_classes(values, gaps):
    """Per edge and facet column: floor((the column's largest - value) / the column's gap)."""
    values = np.asarray(values, dtype=np.float64)
    gaps = np.asarray(gaps, dtype=np.float64)
    if values.ndim != 2 or not values.shape[0] or gaps.shape != (values.shape[1],):
        raise ValueError('Expected one gap per facet column')
    if not np.isfinite(values).all() or not np.isfinite(gaps).all() or not (gaps > 0).all():
        raise ValueError('Expected finite facet values and positive gaps')
    return np.floor((values.max(axis=0) - values) / gaps).astype(np.int64)


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
    """The edges of one query tag's same-thing tags, in order: by the facet classes in `order`,
    then topic descending, then the cosine descending, then the edge's index. Returns each
    edge's place (0 first) and the cosine that place gives it: best - width * place / the
    number of edges."""
    cosine = np.asarray(cosine, dtype=np.float64)
    topic = np.asarray(topic, dtype=np.float64)
    facet_class = np.asarray(facet_class, dtype=np.int64)
    order = [int(j) for j in order]
    if cosine.ndim != 1 or topic.shape != cosine.shape or facet_class.shape[0] != cosine.size:
        raise ValueError('Expected one cosine, one topic and one row of facet classes per edge')
    if sorted(order) != list(range(facet_class.shape[1])):
        raise ValueError('Expected every facet column once in the order')
    by = np.lexsort((np.arange(cosine.size), -cosine, -topic,
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
                facet_gaps, same_level, product, adjacency_ptr, adjacency):
    """What does not depend on the question: the edges of the eligible graph tags with their
    five values, their positions and their facet classes, each chunk's edge count, record kind
    and product, and the near groups from the file adjacency.

    eligible per graph tag; edge_tag, edge_chunk, edge_topic per edge and edge_facets (edges, 4)
    in RANKING_FACETS order, the higher the more; facet_gaps the four columns' gaps; product
    per chunk; adjacency_ptr, adjacency the CSR of each chunk's file-adjacent chunks."""
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
    if not (np.isfinite(same_level) and same_level > 0):
        raise ValueError('Expected a positive same-thing level')
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
            'pos': positions(raw), 'facet_class': facet_classes(raw[:, 1:], facet_gaps),
            'same_level': float(same_level),
            'n_c': np.bincount(edge_chunk[sel], minlength=n).astype(np.int64),
            'product': product, 'near': near, 'id_rank': id_rank, 'kind_names': kind_names,
            'kind': np.array([kind_names.index(k) for k in kinds], dtype=np.int64),
            'groups': {'product': (every, product),
                       'near': (every[near >= 0], near[near >= 0])}}


def chain(layer, query, cos_noise):
    """The module's chain on one question. query: 'cosines' (query tags, graph tags),
    'readings' (query tags, 5), 'description_cosines' (query tags,), 'd_description' and
    'd_question' (chunks,). Returns the order and every array behind it."""
    n, eligible = layer['chunks'], layer['eligible']
    tag_e, chunk_e, pos = layer['edge_tag'], layer['edge_chunk'], layer['pos']
    same = layer['same_level']
    rows = np.asarray(query['cosines'], dtype=np.float64)
    readings = np.asarray(query['readings'], dtype=np.float64)
    count = rows.shape[0]
    if rows.ndim != 2 or not count or rows.shape[1] != eligible.size:
        raise ValueError('Expected one cosine row over the graph tags per query tag')
    if (readings.shape != (count, len(FACETS)) or not np.isfinite(readings).all()
            or (readings < 0).any()):
        raise ValueError('Expected five finite non-negative readings per query tag')
    if not (np.isfinite(cos_noise) and cos_noise > 0):
        raise ValueError('Expected a positive noise')
    bulk, spread = np.zeros(count), np.zeros(count)
    value = np.zeros((count, n))
    best_edge = np.zeros((count, n), dtype=np.int64)
    same_edge = np.zeros((count, chunk_e.size), dtype=bool)
    orders = np.array([facet_order(r) for r in readings], dtype=np.int64)
    for i in range(count):
        z, bulk[i], spread[i] = standing(rows[i][eligible])
        fit_of_tag = np.zeros(eligible.size)
        fit_of_tag[eligible] = np.clip(z, 0., None)
        fit_edge = fit_of_tag[tag_e]
        edge_cosines = rows[i][tag_e]
        closest = float(rows[i][eligible].max())
        picked = np.flatnonzero(edge_cosines >= same)
        same_edge[i, picked] = True
        width = max(closest - same, 0.)
        if picked.size and width > 0:
            _, placed = spread_by_facets(edge_cosines[picked], closest,
                                         width * (1. + 1e-9) + 1e-12,
                                         layer['facet_class'][picked], orders[i],
                                         layer['raw'][picked, 0])
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
            'has_edge': has_edge, 'same_edge': same_edge, 'bulk': bulk, 'spread': spread,
            'centrality': weight, 'D': d, 'Qs': q,
            'text_bulk': {'description': d_bulk, 'question': q_bulk},
            'text_spread': {'description': d_spread, 'question': q_spread}}
