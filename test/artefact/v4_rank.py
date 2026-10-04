"""The stored rank layer and artefact_v4's two orders that carry no number of the arm's own.

Layer (query-independent, computed once from the stored round-1 scores and the graph's topic
cosines, never written anywhere):
  - pct_f(t, c) for temporal, why, activity, concreteness: the percentile rank of the edge's
    stored score over all edges, r / n with r the average rank (1..n, ties shared). It is read
    from the stored `_pos` column, pos = (r - 1) / (n - 1), as (pos (n - 1) + 1) / n, so it
    lies in [1/n, 1] and is never 0.
  - facet levels: floor((column max - score) / gap) on the stored score, gap the retrain flip
    gap read from `bootstrap/BANDS.md` (the pooled same-chunk gap, the value SPEC-v2 names).
    The gap is in score units; its conversion to percentile per column is the share of edges
    each level holds, recorded in `conversion`.
  - topic: the graph cosine cos(tag, chunk description); its percentile rank over all edges
    and its level floor((max cosine - cosine) / COS_NOISE).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np
from scipy.stats import rankdata

COS_NOISE = 0.002
ALL_FACETS = ('topic', 'temporal', 'why', 'activity', 'concreteness')
ADJUST_FACETS = ('temporal', 'why', 'activity', 'concreteness')
QTOPIC_MODES = ('off', 'exp')
EDGECOMB_MODES = ('sum', 'max', 'best')
DESCJOIN_MODES = ('mul', 'key')
_POOLED_ROW = re.compile(r'^\|\s*\*\*pooled[^|]*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|')


@dataclass(frozen=True)
class RankLayer:
    pct: np.ndarray            # (edges, 4) in ADJUST_FACETS order, in [1/n, 1]
    facet_levels: np.ndarray   # (edges, 4) in ADJUST_FACETS order, 0 = the column's top
    topic_pct: np.ndarray      # (edges,)
    topic_levels: np.ndarray   # (edges,)
    gap: float
    conversion: dict


def read_flip_gap(path):
    """The pooled same-chunk retrain flip gap from BANDS.md, with where it was read."""
    path = Path(path)
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        found = _POOLED_ROW.match(line)
        if found:
            return float(found.group(3)), {'path': str(path), 'line': number,
                                           'column': 'gap (same chunk)', 'row': 'pooled'}
    raise ValueError(f'No pooled flip-gap row in {path}')


def percentile_from_positions(pos, n):
    """r / n from the stored (r - 1) / (n - 1)."""
    pos = np.asarray(pos, dtype=np.float64)
    if n < 2:
        raise ValueError('A percentile needs at least two edges')
    return (pos * (n - 1) + 1.) / n


def levels(values, step):
    """floor((best - value) / step): 0 at the best, one level per whole step below it."""
    values = np.asarray(values, dtype=np.float64)
    return np.floor((values.max() - values) / step).astype(np.int64)


def _level_widths(levels):
    counts = np.bincount(levels)
    counts = counts[counts > 0] / levels.size
    return {'levels': int(counts.size),
            'percentile_width_min': float(counts.min()),
            'percentile_width_median': float(np.median(counts)),
            'percentile_width_max': float(counts.max())}


def build_layer(edge_pos, edge_score, edge_topic, gap):
    """edge_pos, edge_score: (edges, 5) in ALL_FACETS order; edge_topic: the graph cosine."""
    edge_pos = np.asarray(edge_pos, dtype=np.float64)
    edge_score = np.asarray(edge_score, dtype=np.float64)
    edge_topic = np.asarray(edge_topic, dtype=np.float64)
    n = edge_topic.size
    if edge_pos.shape != (n, 5) or edge_score.shape != (n, 5):
        raise ValueError('Expected five stored columns per edge')
    if not gap > 0:
        raise ValueError('The flip gap must be positive')
    cols = [ALL_FACETS.index(f) for f in ADJUST_FACETS]
    pct = percentile_from_positions(edge_pos[:, cols], n)
    facet_levels = np.stack([levels(edge_score[:, j], gap) for j in cols], axis=1)
    topic_pct = rankdata(edge_topic, method='average') / n
    topic_levels = levels(edge_topic, COS_NOISE)
    conversion = {'edges': int(n), 'gap_score_units': float(gap),
                  'percentile': 'r/n, r the average rank 1..n, from the stored _pos',
                  'percentile_min': {f: float(pct[:, i].min()) for i, f in enumerate(ADJUST_FACETS)},
                  'facet_levels': {f: _level_widths(facet_levels[:, i])
                                   for i, f in enumerate(ADJUST_FACETS)},
                  'topic_levels': {'step_cosine': COS_NOISE, **_level_widths(topic_levels)}}
    for array in (pct, facet_levels, topic_pct, topic_levels):
        array.setflags(write=False)
    return RankLayer(pct, facet_levels, topic_pct, topic_levels, float(gap), conversion)


def _check_rows(query_tags, n_tags):
    rows = []
    for fit, readings in query_tags:
        fit = np.asarray(fit, dtype=np.float64)
        readings = np.asarray(readings, dtype=np.float64)
        if fit.shape != (n_tags,) or not np.isfinite(fit).all():
            raise ValueError('Expected one finite fit row per graph tag')
        if readings.shape != (5,) or not np.isfinite(readings).all() or (readings < 0).any():
            raise ValueError('Expected five finite non-negative readings per query tag')
        rows.append((fit, readings))
    return rows


def _check_text(row, n):
    row = np.asarray(row, dtype=np.float64)
    if row.shape != (n,) or not np.isfinite(row).all():
        raise ValueError('Expected one finite description cosine per chunk')
    return row


def _check_area(area_rank, n):
    rank = np.zeros(n, dtype=np.int64) if area_rank is None else np.asarray(area_rank, np.int64)
    if rank.shape != (n,):
        raise ValueError('Expected one area rank per chunk')
    return rank


def adjust_lower_scores(edge_tag, edge_chunk, edge_topic, pct, eligible, query_tags, n_chunks,
                        *, qtopic='off', edgecomb='sum', facets_on=True):
    """S(c) over the eligible edges, with what went negative counted.

    rel(q, t, c) = fit(q, t) * T(t, c) * prod_f pct_f(t, c) ** (q_f / sum_f q_f)
    over temporal, why, activity, concreteness: the weighted geometric mean of the four
    percentiles, the query tag's own readings normalised by their sum (the orchestrator's
    normalisation). It lies in [min pct, max pct] of the edge, never below the edge's own
    lowest percentile; sum_f q_f = 0, or facets off, makes it 1.
    fit and topic enter as they are, negative included. T = topic under qtopic off; under
    exp T = max(topic, 0) ** q_topic where q_topic > 0 (the clip only there, a fractional
    power of a negative cosine being undefined), and T = topic where q_topic = 0.
    edgecomb sum: every (q, t) reaching c adds; max: per query tag the best graph tag,
    summed over query tags; best: the single largest (q, t) term over every query tag and
    every graph tag reaching c, nothing added to it.
    """
    if qtopic not in QTOPIC_MODES:
        raise ValueError(f'qtopic must be one of {QTOPIC_MODES}, got {qtopic!r}')
    if edgecomb not in EDGECOMB_MODES:
        raise ValueError(f'edgecomb must be one of {EDGECOMB_MODES}, got {edgecomb!r}')
    eligible = np.asarray(eligible, dtype=bool)
    rows = _check_rows(query_tags, eligible.size)
    sel = np.flatnonzero(eligible[edge_tag])
    tags_sel, chunks_sel = edge_tag[sel], edge_chunk[sel]
    topic_sel = np.asarray(edge_topic, dtype=np.float64)[sel]
    log_pct = np.log(np.asarray(pct, dtype=np.float64)[sel])
    facet_cols = [ALL_FACETS.index(f) for f in ADJUST_FACETS]
    total = np.zeros(n_chunks)
    reached = np.zeros(n_chunks, dtype=bool)
    reached[chunks_sel] = True
    best = np.full(n_chunks, -np.inf)
    negative_rel = two_negative = 0
    for fit, readings in rows:
        q_topic = readings[0]
        if qtopic == 'exp' and q_topic > 0:
            ceiling = np.clip(topic_sel, 0., None) ** q_topic
        else:
            ceiling = topic_sel
        weights = readings[facet_cols]
        mass = weights.sum()
        if facets_on and mass > 0:
            factor = np.exp(log_pct @ (weights / mass))
        else:
            factor = np.ones(sel.size)
        f = fit[tags_sel]
        rel = f * ceiling * factor
        negative_rel += int((rel < 0).sum())
        two_negative += int(((f < 0) & (ceiling < 0)).sum())
        if edgecomb == 'sum':
            np.add.at(total, chunks_sel, rel)
        elif edgecomb == 'max':
            term = np.full(n_chunks, -np.inf)
            np.maximum.at(term, chunks_sel, rel)
            total[reached] += term[reached]
        else:
            np.maximum.at(best, chunks_sel, rel)
    if edgecomb == 'best' and rows:
        total[reached] = best[reached]
    stats = {'edge_terms_negative': negative_rel,
             'edge_terms_from_negative_fit_and_negative_topic': two_negative,
             'reached_chunks_with_negative_score': int((total[reached] < 0).sum())}
    return total, reached, stats


def adjust_lower_order(chunk_ids, tag_score, reached, d_description, d_question, area_rank=None,
                       *, descjoin='key'):
    """The full order: every reached chunk before every unreached one; inside each, the score
    descending, continuous; on an exact tie of the score, under key, cos(description, chunk
    desc) then cos(question, chunk desc), each levelled at COS_NOISE below its best; then the
    landing meet first; then chunk id.
    mul: the score is tag score * max(cos(description), 0) * max(cos(question), 0).
    """
    if descjoin not in DESCJOIN_MODES:
        raise ValueError(f'descjoin must be one of {DESCJOIN_MODES}, got {descjoin!r}')
    n = len(chunk_ids)
    s = _check_text(tag_score, n)
    reached = np.asarray(reached, dtype=bool)
    if reached.shape != (n,):
        raise ValueError('Expected one reached flag per chunk')
    dd, dq = _check_text(d_description, n), _check_text(d_question, n)
    area = _check_area(area_rank, n)
    if descjoin == 'mul':
        score = s * np.clip(dd, 0., None) * np.clip(dq, 0., None)
        order = sorted(range(n), key=lambda i: (not reached[i], -score[i], area[i], chunk_ids[i]))
    else:
        score = s
        ld, lq = levels(dd, COS_NOISE), levels(dq, COS_NOISE)
        order = sorted(range(n), key=lambda i: (not reached[i], -score[i], ld[i], lq[i],
                                                area[i], chunk_ids[i]))
    return {'order': order, 'score': score}


def facet_column_order(readings):
    """The five columns, largest reading first; equal readings keep ALL_FACETS order."""
    readings = np.asarray(readings, dtype=np.float64)
    return tuple(sorted(range(5), key=lambda j: (-readings[j], j)))


def multirank_order(chunk_ids, edge_tag, edge_chunk, edge_topic, layer, eligible, query_tags,
                    d_description, d_question, area_rank=None):
    """Per chunk its best (q, t) edge by strength = fit * topic (as they are); the outermost key
    is that same strength's level, floor((best strength of the question - strength) /
    COS_NOISE) - one quantity chooses the edge and keys it; then that edge's five levels in
    the query tag's column order -> description level -> question level -> landing -> id.
    Chunks no eligible edge reaches follow every reached chunk, by description level,
    question level, landing, id."""
    n = len(chunk_ids)
    eligible = np.asarray(eligible, dtype=bool)
    rows = _check_rows(query_tags, eligible.size)
    dd, dq = _check_text(d_description, n), _check_text(d_question, n)
    area = _check_area(area_rank, n)
    ld, lq = levels(dd, COS_NOISE), levels(dq, COS_NOISE)
    sel = np.flatnonzero(eligible[edge_tag])
    tags_sel, chunks_sel = edge_tag[sel], edge_chunk[sel]
    topic_sel = np.asarray(edge_topic, dtype=np.float64)[sel]
    best_strength = np.full(n, -np.inf)
    best_edge = np.full(n, -1, dtype=np.int64)
    best_q = np.full(n, -1, dtype=np.int64)
    for qi, (fit, _) in enumerate(rows):
        strength = fit[tags_sel] * topic_sel
        # per chunk the strongest edge of this query tag; the first edge wins a tie
        order = np.lexsort((np.arange(sel.size), -strength, chunks_sel))
        first = np.ones(order.size, dtype=bool)
        first[1:] = chunks_sel[order][1:] != chunks_sel[order][:-1]
        top = order[first]
        c = chunks_sel[top]
        better = strength[top] > best_strength[c]   # an earlier query tag wins a tie
        c, top = c[better], top[better]
        best_strength[c] = strength[top]
        best_edge[c] = sel[top]
        best_q[c] = qi
    reached = best_edge >= 0
    anchor = float(best_strength[reached].max()) if reached.any() else None
    fit_level = np.full(n, -1, dtype=np.int64)
    if anchor is not None:
        fit_level[reached] = np.floor(
            (anchor - best_strength[reached]) / COS_NOISE).astype(np.int64)
    columns = {}
    edge_levels = np.full((n, 5), -1, dtype=np.int64)
    for c in np.flatnonzero(reached):
        e = best_edge[c]
        edge_levels[c] = (layer.topic_levels[e], *layer.facet_levels[e])
        columns[c] = facet_column_order(rows[best_q[c]][1])

    def key(i):
        if reached[i]:
            return (0, fit_level[i], *(edge_levels[i, j] for j in columns[i]),
                    ld[i], lq[i], area[i], chunk_ids[i])
        return (1, ld[i], lq[i], area[i], chunk_ids[i])

    return {'order': sorted(range(n), key=key), 'reached': reached, 'best_edge': best_edge,
            'best_query_tag': best_q, 'fit_level': fit_level, 'best_strength_all': anchor,
            'best_strength': best_strength,
            'edge_levels': edge_levels, 'columns': columns}
