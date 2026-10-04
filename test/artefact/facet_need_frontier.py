"""Disposable recruitment frontiers over existing, unchanged route scores.

This is an equal-access scheduler, not a calibrated relevance score or a final
evidence selector. A frontier is the union of complete positive-score prefixes
at the same competition rank. Zero support never recruits a chunk. No budget,
quota, pool normalization, or vote for repeated routes is introduced here.
"""

from typing import Mapping, Sequence

import numpy as np

from artefact.facet_stream_envelope import COEFFICIENTS
from artefact.facet_joint_candidate import FACETS


MODES = ("joint", "facets", "needs", "need_facets")


def build_streams(route_scores, q, groups: Mapping[str, Sequence[int]], mode: str):
    """Keep the old route values; vary only where they collapse into a list.

    route_scores is max(direct, graph) with axes [facet, query tag, chunk].
    q is the existing nonnegative whole-query-description factor. All original
    query tags must occur in at least one group. Callers explicitly assign any
    common context tags; this module never guesses needs from source answers.

    Facet-list modes retain beta in saved scores but it cannot affect ranks
    within a facet. Those modes therefore do NOT preserve topic's priority.
    """
    values = np.asarray(route_scores, dtype=float)
    q = np.asarray(q, dtype=float)
    if values.ndim != 3 or values.shape[0] != len(FACETS) or not values.shape[1]:
        raise ValueError("route_scores must have shape [5, nonempty query tags, chunks]")
    if q.shape != (values.shape[2],):
        raise ValueError("q must align with chunks")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("route scores must be finite and nonnegative")
    if not np.isfinite(q).all() or (q < 0).any():
        raise ValueError("q must be finite and nonnegative")
    if mode not in MODES:
        raise ValueError("unknown frontier mode")
    if not groups or any(not isinstance(k, str) or not k for k in groups):
        raise ValueError("need IDs must be nonempty strings")
    checked = {}
    for name, indices in groups.items():
        if any(not isinstance(i, (int, np.integer)) for i in indices):
            raise ValueError("query tag indices must be integers")
        members = sorted(set(int(i) for i in indices))
        if not members or min(members) < 0 or max(members) >= values.shape[1]:
            raise ValueError("each need must name valid query tag indices")
        checked[name] = members
    if set().union(*(set(v) for v in checked.values())) != set(range(values.shape[1])):
        raise ValueError("every original query tag must be retained")
    selections = checked if mode in ("needs", "need_facets") else {
        "all": list(range(values.shape[1]))
    }
    ids, scores = [], []
    for need, indices in sorted(selections.items()):
        profile = values[:, indices, :].max(axis=1)
        if mode in ("facets", "need_facets"):
            for f, (facet, beta) in enumerate(zip(FACETS, COEFFICIENTS)):
                ids.append(f"{need}/{facet}")
                scores.append(q * beta * profile[f])
        else:
            ids.append(need)
            scores.append(q * (profile.T @ np.asarray(COEFFICIENTS)))
    return ids, np.asarray(scores)


def merge_frontiers(chunk_ids, stream_ids, scores):
    """Return complete deduplicated frontiers; no arbitrary within-tie order.

    Each supported rank is 1 + number of strictly higher scoring chunks in that
    list. A chunk enters at its minimum supported rank across lists. Rank is
    calculated BEFORE deduplication; duplicates never cause lists to advance.
    first_position/last_position bound the whole tied frontier. Unsupported
    chunks are explicitly terminal and have no finite depth or positions.
    """
    chunk_ids, stream_ids = list(chunk_ids), list(stream_ids)
    values = np.asarray(scores, dtype=float)
    if len(set(chunk_ids)) != len(chunk_ids) or len(set(stream_ids)) != len(stream_ids):
        raise ValueError("chunk and stream IDs must be unique")
    if values.shape != (len(stream_ids), len(chunk_ids)):
        raise ValueError("scores must have shape [stream, chunk]")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("scores must be finite and nonnegative")
    n = len(chunk_ids)
    ranks = np.full(values.shape, n + 1, dtype=np.int64)
    for s, score in enumerate(values):
        supported = score > 0
        ordered = np.sort(-score[supported])
        ranks[s, supported] = 1 + np.searchsorted(ordered, -score[supported], side="left")
    depth = ranks.min(axis=0) if len(stream_ids) else np.full(n, n + 1, dtype=np.int64)
    frontiers, intervals = [], {}
    cumulative = 0
    for d in sorted(set(int(d) for d in depth if d <= n)):
        size = int(np.count_nonzero(depth == d))
        intervals[d] = (cumulative + 1, cumulative + size)
        cumulative += size
        frontiers.append({"depth": d, "size": size, "cumulative_size": cumulative})
    rows = []
    for c in sorted(range(n), key=lambda c: (depth[c], chunk_ids[c])):
        supported = depth[c] <= n
        d = int(depth[c]) if supported else None
        first, last = intervals[d] if supported else (None, None)
        rows.append({
            "chunk_id": chunk_ids[c], "depth": d,
            "first_position": first, "last_position": last,
            "stream_ranks": {stream_ids[s]: int(ranks[s, c]) for s in range(len(stream_ids))
                             if ranks[s, c] <= n},
            "winning_streams": sorted(stream_ids[s] for s in range(len(stream_ids))
                                      if supported and ranks[s, c] == depth[c]),
        })
    return {"rows": rows, "supported_count": cumulative, "frontier_sizes": frontiers,
            "unsupported_chunk_ids": sorted(chunk_ids[c] for c in range(n) if depth[c] > n)}
