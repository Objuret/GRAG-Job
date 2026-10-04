"""Pure numerical operator matrix; no scope, delivery, gold, models or Q factor.

Scores are experimental combinations, not calibrated relevance probabilities.
Inputs share the frozen joint arm's alignment. Each yielded array is independent
of subsequent yields and keeps its original scale; streams are never normalized.
"""
from __future__ import annotations

import numpy as np

from artefact.facet_stream_envelope import COEFFICIENTS


MATCHES = ('product', 'minimum', 'maximum', 'tag_only', 'description_only')
TOPOLOGIES = ('none', 'adjacency', 'groups', 'both')
FACET_MODES = ('topic_only', 'same_path_sum', 'separate_facet_sum', 'separate_facet_streams')
GRAPH_JOINS = ('union', 'intersection', 'graph_only')


def _reducer(targets, size):
    """Precompute segment maxima into chunk columns, including empty chunks."""
    order = np.argsort(targets, kind='stable')
    sorted_targets = targets[order]
    starts = np.flatnonzero(np.r_[True, sorted_targets[1:] != sorted_targets[:-1]]) if len(targets) else []
    unique = sorted_targets[starts] if len(targets) else np.empty(0, dtype=int)

    def reduce(values):
        out = np.zeros((*values.shape[:-1], size), dtype=float)
        if len(targets):
            out[..., unique] = np.maximum.reduceat(values[..., order], starts, axis=-1)
        return out
    return reduce


def _checked_relations(prepared, n):
    groups = []
    for relation_groups in prepared.groups.values():
        for group in relation_groups:
            members = np.asarray(sorted(set(int(i) for i in group)), dtype=int)
            if ((members < 0) | (members >= n)).any():
                raise ValueError('group endpoint outside supplied graph')
            if len(members) > 1:
                groups.append(members)
    pairs = set()
    for pair in prepared.adjacency_pairs:
        if len(pair) != 2:
            raise ValueError('adjacency pair needs two endpoints')
        a, b = map(int, pair)
        if not (0 <= a < n and 0 <= b < n):
            raise ValueError('adjacency endpoint outside supplied graph')
        if a != b:
            pairs.add((min(a, b), max(a, b)))
    directed = sorted([(a, b) for a, b in pairs] + [(b, a) for a, b in pairs])
    source = np.asarray([a for a, _ in directed], dtype=int)
    target = np.asarray([b for _, b in directed], dtype=int)
    return groups, source, target


def _graph_primitives(direct, description, groups, source, target, adjacency_reduce):
    """Six channels: five isolated facets and one same-path weighted sum."""
    shape = direct.shape
    flat = direct.reshape(-1, shape[-1])
    d = np.broadcast_to(description, shape).reshape(flat.shape)
    adjacent = adjacency_reduce(0.5 * flat[:, source] * d[:, target])
    grouped = np.zeros_like(flat)
    row = np.arange(len(flat))
    for members in groups:
        block = flat[:, members]
        best_at = block.argmax(axis=1)
        best = block[row, best_at]
        second = np.partition(block, -2, axis=1)[:, -2]
        # The best two distinct seeds implement the self-exclusion rule even
        # when multiple seeds have equal scores; only values are required here.
        seeds = np.broadcast_to(best[:, None], block.shape).copy()
        seeds[row, best_at] = second
        offer = 0.5 * seeds * d[:, members]
        grouped[:, members] = np.maximum(grouped[:, members], offer)
    return adjacent.reshape(shape), grouped.reshape(shape)


def score_families(prepared, matrices, weights):
    """Yield 200 (key, streams) variants without whole-description multiplier.

    Main union matrix: 5 matches x 4 topologies x 4 facet modes = 80.
    Supplemental intersection/graph-only: 5 x 3 non-none topologies x 4 x 2
    = 120. Empty supplied relations remain explicit zero graph support. For an
    intersection this can eliminate direct support; no fallback is invented.

    Required prepared fields: chunks, edge_tag, edge_chunk, edge_facets,
    reference, groups and adjacency_pairs. Required matrices: query_tag_cosines
    [query,graph_tag] and query_chunk_cosines [query,chunk]. Query-description Q
    is deliberately unused. Weights are [query,5], finite and nonnegative.
    """
    n = len(prepared.chunks)
    u = np.asarray(weights, dtype=float)
    m = np.asarray(matrices['query_tag_cosines'], dtype=float)
    d = np.asarray(matrices['query_chunk_cosines'], dtype=float)
    if u.ndim != 2 or u.shape[1] != 5 or not len(u) or n < 1:
        raise ValueError('weights must have nonempty shape [query,5] and chunks must be nonempty')
    if m.ndim != 2 or m.shape[0] != len(u) or d.shape != (len(u), n):
        raise ValueError('query similarity matrices must align with weights and chunks')
    if any(not np.isfinite(a).all() for a in (u, m, d)) or (u < 0).any():
        raise ValueError('finite matrices and nonnegative query weights required')
    et, ec = np.asarray(prepared.edge_tag, dtype=int), np.asarray(prepared.edge_chunk, dtype=int)
    if et.ndim != 1 or ec.shape != et.shape:
        raise ValueError('edge endpoint arrays must be aligned vectors')
    if ((et < 0) | (et >= m.shape[1])).any() or ((ec < 0) | (ec >= n)).any():
        raise ValueError('edge endpoint outside supplied arrays')
    f = np.asarray(prepared.reference.transform(prepared.edge_facets), dtype=float)
    if f.shape != (len(et), 5) or not np.isfinite(f).all() or (f < 0).any():
        raise ValueError('reference facets must be aligned, finite and nonnegative')
    m, d = np.maximum(m, 0), np.maximum(d, 0)
    edge_m, edge_d = m[:, et], d[:, ec]
    reduce_edges = _reducer(ec, n)
    groups, source, target = _checked_relations(prepared, n)
    reduce_adjacent = _reducer(target, n)
    beta = np.asarray(COEFFICIENTS)
    # Match-independent alignment retains the joint primitive's arithmetic.
    same_path_alignment = u[:, :1] * f[None, :, 0] + u[:, 1:] @ f[:, 1:].T / 4.0
    for match in MATCHES:
        if match == 'product':
            alignment = edge_m * edge_d
        elif match == 'minimum':
            alignment = np.minimum(edge_m, edge_d)
        elif match == 'maximum':
            alignment = np.maximum(edge_m, edge_d)
        elif match == 'tag_only':
            alignment = edge_m
        else:
            alignment = edge_d
        direct = np.empty((6, len(u), n), dtype=float)
        for facet in range(5):
            direct[facet] = reduce_edges(alignment * u[:, facet, None] * f[None, :, facet])
        direct[5] = reduce_edges(alignment * same_path_alignment)
        adjacent, grouped = _graph_primitives(direct, d, groups, source, target, reduce_adjacent)
        for topology in TOPOLOGIES:
            graph = (np.zeros_like(direct) if topology == 'none' else
                     adjacent if topology == 'adjacency' else
                     grouped if topology == 'groups' else np.maximum(adjacent, grouped))
            for join in (('union',) if topology == 'none' else GRAPH_JOINS):
                combined = (np.maximum(direct, graph) if join == 'union' else
                            np.minimum(direct, graph) if join == 'intersection' else graph)
                winners = combined.max(axis=1)
                contributions = beta[:, None] * winners[:5]
                values = (winners[:1], winners[5:6], contributions.sum(axis=0, keepdims=True), contributions)
                for facet_mode, streams in zip(FACET_MODES, values):
                    yield {'match': match, 'topology': topology, 'facet': facet_mode,
                           'graph_join': join}, streams.copy()
