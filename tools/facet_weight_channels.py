"""Five unweighted facet channels for one declared structural construction.

These are exactly the operator matrix's separate_facet_streams before beta.
Query-tag facet relevance remains included. Global query-description Q, facet
coefficients, scope, recovery and delivery are deliberately not applied here.
No models, database, corpus, benchmark or outcome reader is used.
"""
from __future__ import annotations

import numpy as np

from artefact.facet_operator_matrix import _checked_relations, _graph_primitives, _reducer


SUPPORTED = frozenset({('product', 'both', 'union'),
                       ('maximum', 'both', 'intersection'),
                       ('maximum', 'none', 'union')})


def _weighted_query_channels(prepared, matrices, weights, policy):
    key = tuple(policy[k] for k in ('match', 'topology', 'graph_join'))
    if key not in SUPPORTED:
        raise ValueError('Unsupported structural construction')
    match, topology, join = key
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
    alignment = edge_m * edge_d if match == 'product' else np.maximum(edge_m, edge_d)
    reduce_edges = _reducer(ec, n)
    groups, source, target = _checked_relations(prepared, n)
    direct = np.empty((5, len(u), n), dtype=float)
    for facet in range(5):
        direct[facet] = reduce_edges(alignment * u[:, facet, None] * f[None, :, facet])
    if topology == 'none':
        return direct
    adjacent, grouped = _graph_primitives(direct, d, groups, source, target, _reducer(target, n))
    graph = np.maximum(adjacent, grouped)
    combined = np.maximum(direct, graph) if join == 'union' else np.minimum(direct, graph)
    return combined


def channels(prepared, matrices, weights, policy):
    """Return [5, chunk] with query relevance, without beta or global Q.

    Retains the original engine's multiplication order for exact comparisons.
    Only policy's match/topology/graph_join are consulted. Input arrays are never
    mutated; the result owns its values.
    """
    return _weighted_query_channels(prepared, matrices, weights, policy).max(axis=1)


def query_channels(prepared, matrices, policy):
    """Return [5, query, chunk] with unit query weights, no beta or global Q.

    Nonnegative query relevance is constant within each facet/query route, so
    it distributes over all route maxima, graph joins and endpoint reductions.
    Many weight controls can reuse this result as
    ``(result * weights.T[:, :, None]).max(axis=1)``. Moving multiplication can
    introduce roundoff relative to ``channels``; callers should verify ranking
    parity where exact tied positions matter.
    """
    m = np.asarray(matrices['query_tag_cosines'])
    if m.ndim != 2 or not len(m):
        raise ValueError('query similarity matrices must have nonempty query rows')
    return _weighted_query_channels(prepared, matrices, np.ones((len(m), 5)), policy)
