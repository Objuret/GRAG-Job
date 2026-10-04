"""artefact_v4's strength sort: one strength per chunk from the tags, the description and the
structure, every part in one unit.

N is the eligible graph tags, E the edges whose tag is eligible, n the chunks.

  standing     (value - bulk) / spread over a population: bulk its median, spread 1.4826 times
               its median absolute deviation from that median. A spread of zero raises.
  fit          per query tag q, the standing of cos(q, t) over the N eligible graph tags
  edge values  per eligible edge, five values in ALL_FACETS order, query-independent: topic as
               the standing of cos(tag, chunk description) over E; temporal, why, activity,
               concreteness each as a normal score, the standard normal quantile of
               (r - 1/2) / |E| with r the edge's average rank in its column over E (ties share a
               rank), so only the order of a column's values is read
  weight       w(q, e) = sum over the five of share_f(q) * value_f(e); share_f(q) q's reading
               over the sum of q's five readings, five equal shares when that sum is zero
  tag route    s(q, c) = max over c's eligible edges e = (t, c) of fit(q, t) + w(q, e)
  centrality   cos(q, query description), a negative one as zero, over the question's largest;
               no positive cosine raises
  tags         T(c) = max over q of centrality(q) * max(s(q, c), 0); 0 for a chunk with no
               eligible edge
  description  D(c), Q(c): the standing over the n chunks of cos(query description, chunk
               description) and of cos(raw question, chunk description);
               S(c) = T(c) + max(D(c), Q(c))
  structure    per node type (product, channel, file) and chunk c with another chunk under the
               same node: max(0, mean of S over the other chunks under the node - mean of S over
               all chunks); a chunk under several channels takes its largest channel boost;
               S'(c) = S(c) + the three boosts
  level        floor((max S' - S'(c)) / step), step = COS_NOISE over the median of the question's
               query tags' fit spreads
  order        level; inside a level the chunks with a winning edge first, by that edge's four
               facet normal scores, descending, in the order of the winning query tag's readings
               for temporal, why, activity, concreteness (`v4_multikey.facet_order`); then the
               chunk id

An exact tie between two edges of one chunk goes to the earlier edge, between two query tags to
the earlier query tag in the list. Nothing is read from disk and nothing is written.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import ndtri
from scipy.stats import rankdata

from artefact.v4_multikey import facet_order
from artefact.v4_rank import ADJUST_FACETS, ALL_FACETS, COS_NOISE, _check_rows, _check_text

MAD_TO_SPREAD = 1.4826
STRUCTURE_TYPES = ('product', 'channel', 'file')
TERMS = ('tags', 'description') + STRUCTURE_TYPES
FACET_COLUMNS = [ALL_FACETS.index(f) for f in ADJUST_FACETS]


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


def normal_scores(column):
    """Each value's average rank in the column (1..n, ties share a rank) as the standard normal
    quantile of (rank - 1/2) / n."""
    column = np.asarray(column, dtype=np.float64)
    if column.ndim != 1 or not np.isfinite(column).all():
        raise ValueError('Expected one finite value per edge')
    if not column.size:
        return np.zeros(0)
    return ndtri((rankdata(column, method='average') - .5) / column.size)


def shares(readings):
    """The five readings over their sum, and whether the sum was zero: five equal shares then."""
    readings = np.asarray(readings, dtype=np.float64)
    if (readings.shape != (len(ALL_FACETS),) or not np.isfinite(readings).all()
            or (readings < 0).any()):
        raise ValueError('Expected five finite non-negative readings in ALL_FACETS order')
    total = readings.sum()
    if total == 0.:
        return np.full(len(ALL_FACETS), 1. / len(ALL_FACETS)), True
    return readings / total, False


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


def leave_one_out_boost(strength, chunk, node):
    """Per chunk the largest, over the nodes it sits under, of max(0, the mean strength of the
    OTHER chunks under the node - the mean strength of all chunks); 0 for a chunk under no node
    and for a chunk alone under its node. chunk, node: the (chunk, node) pairs, each once."""
    strength = np.asarray(strength, dtype=np.float64)
    chunk = np.asarray(chunk, dtype=np.int64)
    node = np.asarray(node, dtype=np.int64)
    if strength.ndim != 1 or not strength.size or not np.isfinite(strength).all():
        raise ValueError('Expected one finite strength per chunk')
    if chunk.shape != node.shape or chunk.ndim != 1:
        raise ValueError('Expected one node per chunk membership')
    boost = np.zeros(strength.size)
    if not chunk.size:
        return boost
    if chunk.min() < 0 or chunk.max() >= strength.size or node.min() < 0:
        raise ValueError('A chunk membership is out of range')
    members = np.bincount(node)
    total = np.bincount(node, weights=strength[chunk])
    others = members[node] - 1
    shared = others > 0
    lift = ((total[node[shared]] - strength[chunk[shared]]) / others[shared]
            - strength.mean())
    np.maximum.at(boost, chunk[shared], lift)
    return boost


def level_step(spreads):
    """COS_NOISE in the unit of the standings: over the median of the query tags' fit spreads."""
    spreads = np.asarray(spreads, dtype=np.float64)
    if spreads.ndim != 1 or not spreads.size or not (spreads > 0).all():
        raise ValueError('Expected one positive fit spread per query tag')
    return COS_NOISE / float(np.median(spreads))


def level_order(chunk_ids, level, has_edge, slots):
    """The chunks by level; inside a level those with a winning edge first, by its four facet
    normal scores in slot order, descending; then by chunk id."""
    n = len(chunk_ids)
    level = np.asarray(level, dtype=np.int64)
    has_edge = np.asarray(has_edge, dtype=bool)
    slots = np.asarray(slots, dtype=np.float64)
    if (level.shape != (n,) or has_edge.shape != (n,)
            or slots.shape != (n, len(ADJUST_FACETS)) or not np.isfinite(slots).all()):
        raise ValueError('Expected one level, one edge flag and four facet scores per chunk')
    id_rank = np.empty(n, dtype=np.int64)
    id_rank[sorted(range(n), key=lambda i: chunk_ids[i])] = np.arange(n)
    keys = [id_rank] + [-slots[:, k] for k in range(len(ADJUST_FACETS) - 1, -1, -1)]
    return np.lexsort((*keys, ~has_edge, level)).tolist()


@dataclass(frozen=True)
class StrengthLayer:
    eligible: np.ndarray     # (graph tags,) the tags whose edges are read
    edges: np.ndarray        # (E,) the eligible edges, as indices into the arm's edge arrays
    edge_tag: np.ndarray     # (E,) the graph tag of each
    edge_chunk: np.ndarray   # (E,) the chunk of each
    values: np.ndarray       # (E, 5) ALL_FACETS order: topic standing, four normal scores
    topic_bulk: float
    topic_spread: float
    groups: dict             # per structure type the (chunk, node) pairs, each pair once
    chunks: int
    source: dict


def _memberships(chunk, node, n_chunks):
    chunk = np.asarray(chunk, dtype=np.int64)
    node = np.asarray(node, dtype=np.int64)
    if chunk.shape != node.shape or chunk.ndim != 1:
        raise ValueError('Expected one node per chunk membership')
    if chunk.size and (chunk.min() < 0 or chunk.max() >= n_chunks or node.min() < 0):
        raise ValueError('A chunk membership is out of range')
    pairs = np.unique(np.stack([chunk, node]), axis=1)
    pairs.setflags(write=False)
    return pairs[0], pairs[1]


def build_layer(edge_tag, edge_chunk, edge_topic, facet_scores, eligible, product, channel_ptr,
                channels, file):
    """The query-independent part, over the eligible edges.

    edge_tag, edge_chunk, edge_topic: per edge of the arm. facet_scores: (edges, 4) in
    ADJUST_FACETS order, the higher the more. eligible: per graph tag. product, file: per chunk
    the node index, -1 for none. channel_ptr, channels: CSR of each chunk's channel nodes."""
    edge_tag = np.asarray(edge_tag, dtype=np.int64)
    edge_chunk = np.asarray(edge_chunk, dtype=np.int64)
    edge_topic = np.asarray(edge_topic, dtype=np.float64)
    facet_scores = np.asarray(facet_scores, dtype=np.float64)
    eligible = np.array(eligible, dtype=bool)
    product = np.asarray(product, dtype=np.int64)
    file = np.asarray(file, dtype=np.int64)
    channel_ptr = np.asarray(channel_ptr, dtype=np.int64)
    channels = np.asarray(channels, dtype=np.int64)
    m, n = edge_tag.size, product.size
    if (not edge_tag.shape == edge_chunk.shape == edge_topic.shape == (m,)
            or facet_scores.shape != (m, len(ADJUST_FACETS))):
        raise ValueError('Expected one tag, chunk, topic and four facet scores per edge')
    if not np.isfinite(edge_topic).all() or not np.isfinite(facet_scores).all():
        raise ValueError('An edge value is not finite')
    if m and (edge_tag.min() < 0 or edge_tag.max() >= eligible.size
              or edge_chunk.min() < 0 or edge_chunk.max() >= n):
        raise ValueError('An edge endpoint is out of range')
    if file.shape != (n,):
        raise ValueError('Expected one file per chunk')
    if (channel_ptr.shape != (n + 1,) or channel_ptr[0] != 0 or channel_ptr[-1] != channels.size
            or (np.diff(channel_ptr) < 0).any()):
        raise ValueError('Expected one CSR row of channels per chunk')
    sel = np.flatnonzero(eligible[edge_tag])
    if not sel.size:
        raise ValueError('No edge carries an eligible graph tag')
    topic, topic_bulk, topic_spread = standing(edge_topic[sel])
    values = np.column_stack(
        [topic] + [normal_scores(facet_scores[sel, j]) for j in range(len(ADJUST_FACETS))])
    every = np.arange(n, dtype=np.int64)
    groups = {'product': _memberships(every[product >= 0], product[product >= 0], n),
              'channel': _memberships(np.repeat(every, np.diff(channel_ptr)), channels, n),
              'file': _memberships(every[file >= 0], file[file >= 0], n)}
    tags_sel, chunks_sel = edge_tag[sel], edge_chunk[sel]
    for array in (eligible, sel, tags_sel, chunks_sel, values):
        array.setflags(write=False)
    source = {'eligible_graph_tags': int(eligible.sum()), 'eligible_edges': int(sel.size),
              'chunks': int(n),
              'chunks_with_an_eligible_edge': int(np.unique(chunks_sel).size),
              'topic_bulk': topic_bulk, 'topic_spread': topic_spread,
              'value_columns': list(ALL_FACETS),
              'nodes': {kind: int(np.unique(groups[kind][1]).size) for kind in STRUCTURE_TYPES},
              'memberships': {kind: int(groups[kind][0].size) for kind in STRUCTURE_TYPES}}
    return StrengthLayer(eligible, sel, tags_sel, chunks_sel, values, topic_bulk, topic_spread,
                         groups, int(n), source)


def strength_order(chunk_ids, layer, query_tags, description_cosines, d_description,
                   d_question):
    """The full order and every part of each chunk's strength.

    query_tags: (cosine row over every graph tag, five readings in ALL_FACETS order) per query
    tag, both lists. description_cosines: each query tag's cosine to the query description, in
    the same order. d_description, d_question: per chunk the cosine of the query description and
    of the raw question to the chunk description."""
    n = len(chunk_ids)
    if n != layer.chunks:
        raise ValueError('Expected the layer over the same chunks')
    rows = _check_rows(query_tags, layer.eligible.size)
    if not rows:
        raise ValueError('The strength needs at least one query tag')
    cosines = np.asarray(description_cosines, dtype=np.float64)
    if cosines.shape != (len(rows),):
        raise ValueError('Expected one description cosine per query tag')
    central = centrality(cosines)
    d, d_bulk, d_spread = standing(_check_text(d_description, n))
    q, q_bulk, q_spread = standing(_check_text(d_question, n))
    reached = np.zeros(n, dtype=bool)
    reached[layer.edge_chunk] = True
    held = np.flatnonzero(reached)
    s = np.full((len(rows), n), np.nan)
    edge_of = np.full((len(rows), n), -1, dtype=np.int64)
    bulks, spreads, bests, equal = [], [], [], []
    for i, (row, readings) in enumerate(rows):
        fit, bulk, spread = standing(row[layer.eligible])
        fit_of_tag = np.full(layer.eligible.size, np.nan)
        fit_of_tag[layer.eligible] = fit
        share, was_equal = shares(readings)
        s[i], edge_of[i] = best_edges(fit_of_tag[layer.edge_tag] + layer.values @ share,
                                      layer.edge_chunk, n)
        bulks.append(bulk)
        spreads.append(spread)
        bests.append(float(fit.max()))
        equal.append(bool(was_equal))
    terms = central[:, None] * np.clip(s[:, held], 0., None)
    winner = np.full(n, -1, dtype=np.int64)
    winner[held] = np.argmax(terms, axis=0)
    tags = np.zeros(n)
    tags[held] = terms[winner[held], np.arange(held.size)]
    won = edge_of[winner[held], held]
    best_edge = np.full(n, -1, dtype=np.int64)
    best_edge[held] = layer.edges[won]
    side = np.maximum(d, q)
    base = tags + side
    boosts = {kind: leave_one_out_boost(base, *layer.groups[kind]) for kind in STRUCTURE_TYPES}
    strength = base + sum(boosts[kind] for kind in STRUCTURE_TYPES)
    step = level_step(spreads)
    level = np.floor((strength.max() - strength) / step).astype(np.int64)
    orders = np.array([facet_order(readings) for _, readings in rows],
                      dtype=np.int64).reshape(len(rows), len(ADJUST_FACETS))
    slots = np.zeros((n, len(ADJUST_FACETS)))
    slots[held] = np.take_along_axis(layer.values[won][:, FACET_COLUMNS], orders[winner[held]],
                                     axis=1)
    return {'order': level_order(chunk_ids, level, reached, slots),
            'strength': strength, 'base': base, 'tags': tags,
            'description': d, 'question': q, 'description_side': side,
            'took_question': q > d, 'boosts': boosts, 'level': level, 'step': step,
            'reached': reached, 'best_edge': best_edge, 'best_query_tag': winner,
            'slots': slots, 'route': s,
            'facet_orders': [tuple(ADJUST_FACETS[j] for j in o) for o in orders.tolist()],
            'query_tag_bulk': bulks, 'query_tag_spread': spreads,
            'query_tag_best_standing': bests, 'query_tag_centrality': central.tolist(),
            'query_tag_description_cosine': cosines.tolist(), 'query_tag_equal_shares': equal,
            'text_bulk': {'description': d_bulk, 'question': q_bulk},
            'text_spread': {'description': d_spread, 'question': q_spread},
            'eligible_graph_tags': int(layer.eligible.sum()),
            'eligible_edges': int(layer.edges.size)}


def summary(result, delivered):
    """What the strength sort did up to the cut, in numbers: the counts, each query tag's bulk,
    spread, best standing and centrality, and over the delivered rows each term's sum and its
    share of their total strength, the term with the largest absolute difference per adjacent
    pair, the rows taking D or Q, and the levels."""
    delivered = [int(i) for i in delivered]
    terms = {'tags': result['tags'], 'description': result['description_side'],
             **result['boosts']}
    sums = {name: float(terms[name][delivered].sum()) for name in TERMS}
    total = float(result['strength'][delivered].sum())
    largest = dict.fromkeys(TERMS + ('none',), 0)
    for a, b in zip(delivered, delivered[1:]):
        gaps = [abs(float(terms[name][a]) - float(terms[name][b])) for name in TERMS]
        top = max(gaps)
        largest['none' if top == 0. else TERMS[gaps.index(top)]] += 1
    levels = result['level'][delivered]
    took_question = int(result['took_question'][delivered].sum())
    return {
        'chunks': int(result['strength'].size),
        'eligible_graph_tags': result['eligible_graph_tags'],
        'eligible_edges': result['eligible_edges'],
        'chunks_with_an_eligible_edge': int(result['reached'].sum()),
        'chunks_with_a_positive_tag_strength': int((result['tags'] > 0).sum()),
        'query_tags': len(result['query_tag_bulk']),
        'query_tags_with_equal_shares': int(sum(result['query_tag_equal_shares'])),
        'query_tag_bulk': list(result['query_tag_bulk']),
        'query_tag_spread': list(result['query_tag_spread']),
        'query_tag_best_standing': list(result['query_tag_best_standing']),
        'query_tag_centrality': list(result['query_tag_centrality']),
        'query_tag_description_cosine': list(result['query_tag_description_cosine']),
        'text_bulk': dict(result['text_bulk']),
        'text_spread': dict(result['text_spread']),
        'level_step': float(result['step']),
        'delivered_term_sums': sums,
        'delivered_strength_total': total,
        'delivered_term_shares': {name: (sums[name] / total if total != 0. else None)
                                  for name in TERMS},
        'adjacent_delivered_pairs': max(len(delivered) - 1, 0),
        'adjacent_delivered_pairs_largest_difference_in': largest,
        'delivered_rows_taking_the_description': len(delivered) - took_question,
        'delivered_rows_taking_the_question': took_question,
        'largest_boost': {kind: float(result['boosts'][kind].max())
                          for kind in STRUCTURE_TYPES},
        'chunks_with_a_positive_boost': {kind: int((result['boosts'][kind] > 0).sum())
                                         for kind in STRUCTURE_TYPES},
        'levels_among_delivered_rows': int(np.unique(levels).size),
        'adjacent_delivered_pairs_in_one_level': int((levels[1:] == levels[:-1]).sum()),
    }
