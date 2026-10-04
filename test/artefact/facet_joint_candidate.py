"""Disposable, unfitted joint-route hypothesis; no retrieval or external calls.

Facet order is topic, temporal, why, activity, concreteness. Topic receives one
coefficient unit; four auxiliary facets together receive one unit. The 1/4
coefficient and 1/2 extra-hop discount are engineering conventions, not inferred
utilities. Freeze the reference over all eligible semantic HAS_TAG edges before
ranking any candidate pool. Neither query weights nor reference values are
normalized against the candidate pool.
"""

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np


FACETS = ("topic", "temporal", "why", "activity", "concreteness")


@dataclass(frozen=True)
class FrozenFacetReference:
    """Immutable sorted reference columns for an empirical midrank CDF."""

    columns: tuple[tuple[float, ...], ...]

    def transform(self, values):
        values = _matrix(values, "edge_facets", 5)
        result = np.empty_like(values)
        for f, column in enumerate(self.columns):
            ordered = np.asarray(column)
            left = np.searchsorted(ordered, values[:, f], side="left")
            right = np.searchsorted(ordered, values[:, f], side="right")
            result[:, f] = (left + right) / (2.0 * len(ordered))
        return result


def _matrix(values, name, width):
    result = np.asarray(values, dtype=float)
    if result.ndim != 2 or result.shape[1] != width:
        raise ValueError(f"{name} must have shape [N,{width}]")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite")
    return result


def freeze_reference(edge_facets) -> FrozenFacetReference:
    """Call once with the full, eligible graph reference, never a query pool."""
    values = _matrix(edge_facets, "reference edge_facets", 5)
    if not len(values):
        raise ValueError("The frozen reference must contain at least one edge")
    return FrozenFacetReference(tuple(tuple(np.sort(values[:, f])) for f in range(5)))


def rank_joint_candidate(
    *, chunk_ids: Sequence[str], query_tag_ids: Sequence[str],
    edge_ids: Sequence[str], edge_tag_indices, edge_chunk_indices, edge_facets,
    query_facet_weights, query_tag_cosines, query_chunk_cosines,
    query_description_cosines, reference: FrozenFacetReference,
    groups: Mapping[str, Sequence[Sequence[int]]] | None = None,
    adjacency_pairs: Sequence[tuple[int, int]] = (), facets_enabled: bool = True,
):
    """Return full ranks and route components using supplied graph relations.

    All indices refer to explicit input arrays. ``groups`` maps relation names
    to lists of chunk-index groups; callers must construct these from actual
    shared-channel/same-product memberships, not a product oracle. Adjacency
    pairs are undirected actual file-neighbor relations. Empty relations disable
    graph shape. ``facets_enabled=False`` zeros auxiliary query weights only.
    No groups, candidates or tag sponsors are truncated.
    """
    chunk_ids, query_tag_ids, edge_ids = map(list, (chunk_ids, query_tag_ids, edge_ids))
    n, nq, ne = len(chunk_ids), len(query_tag_ids), len(edge_ids)
    if len(set(chunk_ids)) != n or not nq:
        raise ValueError("chunk_ids must be unique and query_tag_ids nonempty")
    weights = _matrix(query_facet_weights, "query_facet_weights", 5).copy()
    if weights.shape[0] != nq or (weights < 0).any():
        raise ValueError("query weights must be nonnegative and match query tags")
    if not facets_enabled:
        weights[:, 1:] = 0
    d = np.maximum(_matrix(query_chunk_cosines, "query_chunk_cosines", n), 0)
    m = np.asarray(query_tag_cosines, dtype=float)
    q = np.asarray(query_description_cosines, dtype=float)
    if d.shape[0] != nq or m.ndim != 2 or m.shape[0] != nq:
        raise ValueError("query cosine arrays must match query tags")
    if q.shape != (n,) or not np.isfinite(q).all() or not np.isfinite(m).all():
        raise ValueError("query description and tag cosines must be finite and aligned")
    m, q = np.maximum(m, 0), np.maximum(q, 0)
    et = np.asarray(edge_tag_indices, dtype=int)
    ec = np.asarray(edge_chunk_indices, dtype=int)
    if et.shape != (ne,) or ec.shape != (ne,):
        raise ValueError("edge indices must match edge_ids")
    if ((et < 0) | (et >= m.shape[1])).any() or ((ec < 0) | (ec >= n)).any():
        raise ValueError("edge endpoint outside supplied graph")
    f = reference.transform(edge_facets)
    if len(f) != ne:
        raise ValueError("edge facets must match edge_ids")

    # Max reducers prevent repeated equivalent sponsors from becoming votes.
    topic = weights[:, :1] * f[None, :, 0]
    auxiliary = weights[:, 1:] @ f[:, 1:].T / 4.0
    alignment = topic + auxiliary
    route = m[:, et] * alignment * d[:, ec]
    direct = np.zeros((nq, n))
    direct_edge = np.full((nq, n), -1, dtype=int)
    for e in sorted(range(ne), key=lambda k: (edge_ids[k], k)):
        c = ec[e]
        better = route[:, e] > direct[:, c]
        direct[better, c] = route[better, e]
        direct_edge[better, c] = e

    graph = np.zeros((nq, n))
    seeds = np.full((nq, n), -1, dtype=int)
    relation_types = [[None] * n for _ in range(nq)]

    def offer(i, c, seed, kind):
        if seed == c:
            return
        value = 0.5 * direct[i, seed] * d[i, c]
        previous = seeds[i, c]
        key = (chunk_ids[seed], kind)
        previous_key = (chunk_ids[previous], relation_types[i][c]) if previous >= 0 else None
        if value > graph[i, c] or (
            value > 0 and value == graph[i, c] and (previous_key is None or key < previous_key)
        ):
            graph[i, c], seeds[i, c], relation_types[i][c] = value, seed, kind

    def checked(indices):
        members = sorted(set(int(c) for c in indices), key=lambda c: chunk_ids[c] if 0 <= c < n else "")
        if any(c < 0 or c >= n for c in members):
            raise ValueError("relation endpoint outside supplied graph")
        return members

    # The best two distinct seeds suffice to find each group's maximum with
    # self exclusion; this retains every group member without materializing a clique.
    for kind, relation_groups in sorted((groups or {}).items()):
        for members_input in relation_groups:
            members = checked(members_input)
            for i in range(nq):
                best = sorted(members, key=lambda c: (-direct[i, c], chunk_ids[c]))[:2]
                for c in members:
                    seed = next((s for s in best if s != c), None)
                    if seed is not None:
                        offer(i, c, seed, kind)
    for pair in adjacency_pairs:
        if len(pair) != 2:
            raise ValueError("adjacency pairs require two endpoints")
        members = checked(pair)
        if len(members) == 2:
            a, b = members
            for i in range(nq):
                offer(i, a, b, "file_adjacency")
                offer(i, b, a, "file_adjacency")

    rows = []
    for c in range(n):
        best_i = min(range(nq), key=lambda i: (-max(direct[i, c], graph[i, c]), query_tag_ids[i], i))
        use_graph = graph[best_i, c] > direct[best_i, c]
        seed = int(seeds[best_i, c]) if use_graph else c
        edge = int(direct_edge[best_i, seed])
        value = max(direct[best_i, c], graph[best_i, c])
        provenance = None
        if value > 0 and edge >= 0:
            provenance = {
                "query_tag_id": query_tag_ids[best_i], "query_tag_index": best_i,
                "edge_id": edge_ids[edge], "edge_index": edge,
                "graph_tag_index": int(et[edge]), "seed_chunk_id": chunk_ids[seed],
                "route_type": relation_types[best_i][c] if use_graph else "direct",
                "M": float(m[best_i, et[edge]]), "D_seed": float(d[best_i, seed]),
                "D_target": float(d[best_i, c]), "Q": float(q[c]),
                "topic_component": float(topic[best_i, edge]),
                "auxiliary_component": float(auxiliary[best_i, edge]),
                "facet_components": (weights[best_i] * f[edge] * np.array([1, .25, .25, .25, .25])).tolist(),
                "A": float(alignment[best_i, edge]),
                "seed_direct": float(direct[best_i, seed]),
                "hop_discount": 0.5 if use_graph else 1.0,
                "route_before_Q": float(value),
            }
        rows.append({"chunk_id": chunk_ids[c], "score": float(q[c] * value), "provenance": provenance})
    order = sorted(range(n), key=lambda c: (-rows[c]["score"], chunk_ids[c]))
    ranks = np.empty(n, dtype=int)
    for rank, c in enumerate(order, 1):
        ranks[c] = rank
        rows[c]["rank"] = rank
    return {
        "ranked_chunk_ids": [chunk_ids[c] for c in order],
        "rows": [rows[c] for c in order], "ranks": ranks,
        "scores": np.array([row["score"] for row in rows]),
        "direct_scores": direct, "graph_scores": graph,
        "facet_percentiles": f,
    }
