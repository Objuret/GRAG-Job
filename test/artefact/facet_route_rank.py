"""Pure, disposable replay of artefact_v3's two forum route operators.

No interpreter, embedding, graph, cache or context-budget work occurs here. Inputs
and their populations must be captured by the caller. The default arm is not a
forum mode, and supplying split-querytagger readings is an experimental adapter,
not a claim that the serving arm already consumes them.

Reference: test/arms/artefact_v3.py pool_steps, weighted_g, bounded_r,
mode_key_columns, pool_key_tuples, and _retrieve_forum. The full staged walk is
equivalent to sorting its complete tuple globally before first-per-chunk reduction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

FACETS = ("topic", "temporal", "why", "activity", "concreteness")


@dataclass(frozen=True)
class ForumConfig:
    """Bands are explicit captured instruments, not fitted utility coefficients."""

    mode: str
    tag_band: float
    description_band: float
    topic_band: float
    facet_band: float
    r_band: float
    betas: tuple[float, float, float, float] = (1., 1., 1., 1.)
    topic_key: str = "ordered"
    description_place: str = "after"
    adjust: str = "bounded"
    cached_zero_fallback: bool = True

    def __post_init__(self):
        if self.mode not in ("weighted", "multirank"):
            raise ValueError("mode must be weighted or multirank")
        for name in ("tag_band", "description_band", "topic_band", "facet_band", "r_band"):
            if not getattr(self, name) > 0:
                raise ValueError(f"{name} must be positive (infinity disables its level column)")
        if self.topic_key not in ("ordered", "first"):
            raise ValueError("invalid topic_key")
        if self.description_place not in ("after", "before"):
            raise ValueError("invalid description_place")
        if self.adjust not in ("bounded", "level"):
            raise ValueError("invalid adjust")
        if len(self.betas) != 4 or not np.isfinite(self.betas).all():
            raise ValueError("betas must contain four finite coefficients")


def pool_steps(values, band: float) -> np.ndarray:
    """Source rule: NaN is worst+1; all missing or infinite band gives one level."""
    v = np.asarray(values, dtype=float).ravel()
    if not band > 0:
        raise ValueError("band must be positive")
    if np.isinf(v).any():
        raise ValueError("values may be finite or NaN, not infinite")
    levels = np.zeros(v.size, dtype=np.int64)
    ok = ~np.isnan(v)
    if not ok.any() or not np.isfinite(band):
        return levels
    levels[ok] = np.floor((v[ok].max() - v[ok]) / band + 1e-12).astype(np.int64)
    if not ok.all():
        levels[~ok] = levels[ok].max() + 1
    return levels


def weighted_values(topic, strengths, weights, betas, topic_band):
    """Return source g and adjusted topic r; missing terms are dropped unrescaled."""
    topic = np.asarray(topic, dtype=float)
    strengths = np.asarray(strengths, dtype=float)
    weights = np.asarray(weights, dtype=float)
    betas = np.asarray(betas, dtype=float)
    g = np.zeros(len(topic), dtype=float)
    used = np.zeros(len(topic), dtype=np.int64)
    for f in range(4):
        ok = ~np.isnan(strengths[:, f])
        if ok.any():
            g[ok] += weights[f] * betas[f] * (strengths[ok, f] - np.median(strengths[ok, f]))
            used[ok] += 1
    g[used == 0] = np.nan
    adjustment = np.zeros(len(topic), dtype=float)
    ok = ~np.isnan(g)
    if ok.any() and np.isfinite(topic_band) and topic_band > 0:
        low, high = g[ok].min(), g[ok].max()
        if high > low:
            adjustment[ok] = topic_band * (g[ok] - low) / (high - low)
    return g, topic + adjustment


def pool_keys(edge_facets, query_facets, facet_order, part_rank, link2, link6,
              tag_cos, chunk_lexical_ranks, config: ForumConfig, *,
              zeroed_facets=False, g_band=None):
    """Pool-local keys, names and raw diagnostics. Four-facet ablation keeps topic.

    The ablation replaces the four graph columns by zero, preserving all query
    readings and topic. Merely setting query readings to zero would NOT remove
    their columns in multirank. In weighted mode the source cached-reading adapter
    even falls back to equal coefficients when ALL FIVE query values are zero;
    cached_zero_fallback reproduces that behavior and can isolate its correction.
    The supplied facet order is explicit. This function does not invent a rule
    for tied query readings or rename those readings facet importance.
    """
    s = np.asarray(edge_facets, dtype=float)
    q = np.asarray(query_facets, dtype=float)
    if s.ndim != 2 or s.shape[1] != 5 or q.shape != (5,):
        raise ValueError("expect edge facets [E,5] and query facets [5]")
    if not np.isfinite(q).all() or np.isinf(s).any():
        raise ValueError("query readings must be finite; graph readings finite or NaN")
    if zeroed_facets:
        s = s.copy()
        s[:, 1:] = 0.
    if tuple(sorted(facet_order)) != tuple(sorted(FACETS)):
        raise ValueError("facet_order must contain every facet exactly once")
    diagnostics = {}
    if config.mode == "multirank":
        names = list(facet_order)
        if config.topic_key == "first":
            names = ["topic"] + [f for f in names if f != "topic"]
        columns = {"topic": pool_steps(s[:, 0], config.topic_band)}
        for i, f in enumerate(FACETS[1:], 1):
            columns[f] = pool_steps(s[:, i], config.facet_band)
        mode = [(f, columns[f]) for f in names]
    else:
        w = np.ones(4) if config.cached_zero_fallback and not q.any() else q[1:]
        g, adjusted = weighted_values(s[:, 0], s[:, 1:], w, config.betas, config.topic_band)
        diagnostics = {"g": g, "adjusted_topic": adjusted,
                       "missing_terms": np.isnan(s[:, 1:]).sum(axis=1)}
        if config.adjust == "bounded":
            mode = [("adjusted topic", pool_steps(adjusted, config.r_band))]
        else:
            if g_band is None:
                raise ValueError("level adjustment requires an explicit captured g_band")
            mode = [("topic", pool_steps(s[:, 0], config.topic_band)),
                    ("g", np.zeros(len(g), dtype=np.int64) if not g_band else pool_steps(g, g_band))]
    desc = [("link2", pool_steps(link2, config.description_band)),
            ("link6", pool_steps(link6, config.description_band))]
    middle = mode + desc if config.description_place == "after" else desc + mode
    names = ["part rank"] + [n for n, _ in middle] + ["tag cosine", "chunk id"]
    matrix = np.column_stack([np.full(len(s), part_rank), *[v for _, v in middle],
                              -np.asarray(tag_cos), chunk_lexical_ranks])
    return matrix, names, diagnostics


@dataclass
class RouteReplay:
    """Arrays use route index = local query-tag index * edge_count + edge index.

    keys include scope/pick prefixes and pool-local key values. All route keys
    remain available, including routes discarded by first-per-chunk reduction.
    chunk-id key values are lexical ranks; trace() resolves their strings.
    """

    edge_count: int
    edge_chunk: np.ndarray
    chunk_ids: tuple[str, ...]
    keys: np.ndarray
    key_names_by_part: tuple[tuple[str, ...], ...]
    order: np.ndarray
    selected_routes: np.ndarray
    selected_by_chunk: np.ndarray
    part_priority: np.ndarray
    raw_g: np.ndarray | None
    adjusted_topic: np.ndarray | None

    @property
    def chunk_order(self):
        return self.edge_chunk[self.selected_routes % self.edge_count]

    def trace(self, route: int) -> dict:
        p, e = divmod(int(route), self.edge_count)
        names = self.key_names_by_part[p]
        values = self.keys[route].tolist()
        values[-1] = self.chunk_ids[self.edge_chunk[e]]
        out = {"route": int(route), "part": p, "edge": e,
               "chunk": self.chunk_ids[self.edge_chunk[e]],
               "key": dict(zip(names, values)),
               "selected": bool(self.selected_by_chunk[self.edge_chunk[e]] == route)}
        if self.raw_g is not None:
            out["g"] = float(self.raw_g[route])
            out["adjusted_topic"] = float(self.adjusted_topic[route])
        return out

    def deciding_key(self, a: int, b: int) -> dict:
        """First unequal complete-key field. Exact ties have no semantic winner."""
        positions = np.flatnonzero(self.keys[a] != self.keys[b])
        if not len(positions):
            return {"field": None, "reason": "exact full-key tie; source iteration retains provenance"}
        i = int(positions[0])
        pa, pb = a // self.edge_count, b // self.edge_count
        return {"field": self.key_names_by_part[pa][i],
                "other_field": self.key_names_by_part[pb][i],
                "a": float(self.keys[a, i]), "b": float(self.keys[b, i]),
                "earlier": int(a if self.keys[a, i] < self.keys[b, i] else b)}


def first_per_chunk(route_order, edge_chunk, edge_count):
    """Reduce a declared route order; do not confuse arbitrary arrival with sorted walk."""
    order = np.asarray(route_order, dtype=np.int64)
    chunks = np.asarray(edge_chunk)[order % edge_count]
    _, first = np.unique(chunks, return_index=True)
    return order[np.sort(first)]


def replay_forum(*, edge_tag, edge_chunk, edge_facets, chunk_ids: Sequence[str],
                 tag_cos, part_chunk_cos, description_chunk_cos, centrality,
                 query_facets, facet_orders, config: ForumConfig,
                 candidate_tag=None, in_scope=None, zeroed_facets=False,
                 g_bands=None) -> RouteReplay:
    """Replay all captured eligible routes; never cut to top-N or context budget.

    tag_cos[P,T] can include graph tags without eligible edges. candidate_tag[T]
    states the exact pick-best population, separate from the band instrument.
    in_scope=None gives one pass; a bool[C] mask gives in/out passes. The caller
    must handle the arm's scope naming/no-match fallback before passing a mask.
    g_bands[P] is required only for the nondefault weighted level variant.
    """
    et, ec = np.asarray(edge_tag, dtype=np.int64), np.asarray(edge_chunk, dtype=np.int64)
    s = np.asarray(edge_facets, dtype=float)
    tc, pc = np.asarray(tag_cos, dtype=float), np.asarray(part_chunk_cos, dtype=float)
    dc, ce = np.asarray(description_chunk_cos, dtype=float), np.asarray(centrality, dtype=float)
    q = np.asarray(query_facets, dtype=float)
    ids = tuple(chunk_ids)
    if tc.ndim != 2:
        raise ValueError("tag_cos must be [parts,tags]")
    p, t = tc.shape
    e, c = len(et), len(ids)
    if not e or not p or not t:
        raise ValueError("at least one part, tag and eligible edge is required")
    if ec.shape != (e,) or s.shape != (e, 5) or pc.shape != (p, c) or dc.shape != (c,) or ce.shape != (p,) or q.shape != (p, 5):
        raise ValueError("misaligned factorized route arrays")
    if len(set(ids)) != c or not all(isinstance(x, str) for x in ids):
        raise ValueError("chunk IDs must be unique strings")
    if et.min() < 0 or et.max() >= t or ec.min() < 0 or ec.max() >= c:
        raise ValueError("edge index outside captured populations")
    if not all(np.isfinite(x).all() for x in (tc, pc, dc, ce, q)) or np.isinf(s).any():
        raise ValueError("links/query readings must be finite; only graph facets may be NaN")
    candidate = np.ones(t, dtype=bool) if candidate_tag is None else np.asarray(candidate_tag, dtype=bool)
    if candidate.shape != (t,) or not candidate.any() or not candidate[et].all():
        raise ValueError("candidate_tag must include every captured eligible edge tag")
    if len(facet_orders) != p:
        raise ValueError("one explicit facet order is required per query tag")
    scope = np.zeros(c, dtype=np.int64)
    if in_scope is not None:
        inside = np.asarray(in_scope, dtype=bool)
        if inside.shape != (c,):
            raise ValueError("in_scope must align with chunks")
        scope = (~inside).astype(np.int64)
    priority = np.empty(p, dtype=np.int64)
    priority[np.lexsort((np.arange(p), -ce))] = np.arange(p)
    lexical = np.empty(c, dtype=np.int64)
    lexical[sorted(range(c), key=ids.__getitem__)] = np.arange(c)
    names_by_part = []
    key_matrix = None
    raw_g = np.full(p * e, np.nan) if config.mode == "weighted" else None
    adjusted = np.full(p * e, np.nan) if config.mode == "weighted" else None
    # Each pool includes already-delivered chunks: source code does not remove
    # them before its medians, maxima, ranges or bins are computed.
    for pi in range(p):
        best = tc[pi, candidate].max()
        pick = np.floor((best - tc[pi, et]) / config.tag_band + 1e-12).astype(np.int64)
        for sp in np.unique(scope[ec]):
            at_scope = np.flatnonzero(scope[ec] == sp)
            levels = pick[at_scope]
            pool_order = np.argsort(levels, kind="stable")
            sorted_edges = at_scope[pool_order]
            sorted_levels = levels[pool_order]
            boundaries = np.r_[0, np.flatnonzero(np.diff(sorted_levels)) + 1, len(sorted_edges)]
            for lo, hi in zip(boundaries[:-1], boundaries[1:]):
                at = sorted_edges[lo:hi]
                k, names, detail = pool_keys(s[at], q[pi], facet_orders[pi], int(priority[pi]),
                    pc[pi, ec[at]], dc[ec[at]], tc[pi, et[at]], lexical[ec[at]], config,
                    zeroed_facets=zeroed_facets,
                    g_band=None if g_bands is None else g_bands[pi])
                if key_matrix is None:
                    key_matrix = np.empty((p * e, k.shape[1] + 2), dtype=float)
                route = pi * e + at
                key_matrix[route, 0] = sp
                key_matrix[route, 1] = sorted_levels[lo]
                key_matrix[route, 2:] = k
                if raw_g is not None:
                    raw_g[route], adjusted[route] = detail["g"], detail["adjusted_topic"]
        names_by_part.append(tuple(["scope pass", "pick level"] + names))
    # np.lexsort is stable for exact tuple ties, matching source part/edge order.
    order = np.lexsort(key_matrix[:, ::-1].T)
    chosen = first_per_chunk(order, ec, e)
    by_chunk = np.full(c, -1, dtype=np.int64)
    by_chunk[ec[chosen % e]] = chosen
    return RouteReplay(e, ec, ids, key_matrix, tuple(names_by_part), order,
                       chosen, by_chunk, priority, raw_g, adjusted)
