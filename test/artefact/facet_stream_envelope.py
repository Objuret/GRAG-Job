"""Isolated multi-route, single-chunk reference: facet maxima before the sum.

This reuses the frozen max-route primitive separately for each facet. It is not
an independent-probability vote, a search scheduler, or complete retrieval/scope.
The original candidate is unchanged; its coefficients and hop discount are kept.
"""

from typing import Mapping, Sequence

import numpy as np

from artefact.facet_joint_candidate import (
    FACETS, FrozenFacetReference, _matrix, rank_joint_candidate,
)


COEFFICIENTS = (1.0, 0.25, 0.25, 0.25, 0.25)


def rank_facet_stream_envelope(
    *, chunk_ids: Sequence[str], query_tag_ids: Sequence[str],
    edge_ids: Sequence[str], edge_tag_indices, edge_chunk_indices, edge_facets,
    query_facet_weights, query_tag_cosines, query_chunk_cosines,
    query_description_cosines, reference: FrozenFacetReference,
    groups: Mapping[str, Sequence[Sequence[int]]] | None = None,
    adjacency_pairs: Sequence[tuple[int, int]] = (), facets_enabled: bool = True,
):
    """Return Q times the coefficient-weighted sum of per-facet best paths.

    Inputs use the joint candidate's explicit indexing and graph-relation API.
    ``per_facet_scores`` has shape [chunk, facet] and contains unweighted Z,
    before Q. ``direct_scores``/``graph_scores`` have shape [facet, query, chunk].
    Every row's ``provenance`` maps each facet to its distinct winner (or None
    when Z is zero). A winner's contribution includes its coefficient and Q.
    """
    chunk_ids, query_tag_ids, edge_ids = map(list, (chunk_ids, query_tag_ids, edge_ids))
    weights = _matrix(query_facet_weights, "query_facet_weights", len(FACETS)).copy()
    if weights.shape[0] != len(query_tag_ids) or (weights < 0).any():
        raise ValueError("query weights must be nonnegative and match query tags")
    if not facets_enabled:
        weights[:, 1:] = 0
    q = np.maximum(np.asarray(query_description_cosines, dtype=float), 0)
    z = np.zeros((len(chunk_ids), len(FACETS)))
    provenance = [{facet: None for facet in FACETS} for _ in chunk_ids]
    direct, graph = [], []
    percentiles = None
    at = {cid: c for c, cid in enumerate(chunk_ids)}
    for f, (facet, coefficient) in enumerate(zip(FACETS, COEFFICIENTS)):
        isolated = np.zeros_like(weights)
        # Cancel the primitive's coefficient so its single-facet result is B/Z.
        # The same coefficient is applied once, after the facet-wise maxima.
        isolated[:, f] = weights[:, f] / coefficient
        result = rank_joint_candidate(
            chunk_ids=chunk_ids, query_tag_ids=query_tag_ids, edge_ids=edge_ids,
            edge_tag_indices=edge_tag_indices, edge_chunk_indices=edge_chunk_indices,
            edge_facets=edge_facets, query_facet_weights=isolated,
            query_tag_cosines=query_tag_cosines, query_chunk_cosines=query_chunk_cosines,
            query_description_cosines=query_description_cosines, reference=reference,
            groups=groups, adjacency_pairs=adjacency_pairs, facets_enabled=True,
        )
        direct.append(result["direct_scores"])
        graph.append(result["graph_scores"])
        z[:, f] = np.maximum(direct[-1], graph[-1]).max(axis=0)
        percentiles = result["facet_percentiles"]
        for row in result["rows"]:
            witness = row["provenance"]
            if witness is None:
                continue
            c = at[row["chunk_id"]]
            i, e = witness["query_tag_index"], witness["edge_index"]
            provenance[c][facet] = {
                key: witness[key] for key in (
                    "query_tag_id", "query_tag_index", "edge_id", "edge_index",
                    "graph_tag_index", "seed_chunk_id", "route_type", "M",
                    "D_seed", "D_target", "Q", "hop_discount", "seed_direct",
                )
            }
            provenance[c][facet].update(
                u=float(weights[i, f]), F=float(percentiles[e, f]),
                coefficient=coefficient, Z=float(z[c, f]),
                contribution=float(q[c] * coefficient * z[c, f]),
            )
    scores = q * (z @ np.asarray(COEFFICIENTS))
    order = sorted(range(len(chunk_ids)), key=lambda c: (-scores[c], chunk_ids[c]))
    ranks = np.empty(len(chunk_ids), dtype=int)
    rows = []
    for rank, c in enumerate(order, 1):
        ranks[c] = rank
        rows.append({"rank": rank, "chunk_id": chunk_ids[c],
                     "score": float(scores[c]), "provenance": provenance[c]})
    return {
        "ranked_chunk_ids": [chunk_ids[c] for c in order], "rows": rows,
        "ranks": ranks, "scores": scores, "per_facet_scores": z,
        "direct_scores": np.asarray(direct), "graph_scores": np.asarray(graph),
        "facet_percentiles": percentiles,
    }
