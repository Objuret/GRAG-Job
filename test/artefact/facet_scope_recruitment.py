"""Experimental equal-depth or optional area-first structural nomination.

The caller resolves one unambiguous structural area. This module neither infers
scope nor combines uncertain landings. Area membership changes which list can
nominate a chunk, never its joint score or underlying facet measurements.
"""
from copy import deepcopy

import numpy as np

from artefact.facet_recruitment_candidate import recruit_with_record_context, recover_from_nomination
from artefact.facet_need_frontier import merge_frontiers


def _area_first_nomination(ids, stream_ids, stream_scores):
    """Concatenate positive-score phase ranks without manufacturing new scores."""
    nomination = merge_frontiers(ids, stream_ids, stream_scores)
    area_count = int(np.count_nonzero(stream_scores[0] > 0))
    for row in nomination['rows']:
        phase = next(iter(row['stream_ranks']), None)  # phases are disjoint
        row['phase'] = phase
        row['phase_rank'] = row['stream_ranks'].get(phase)
        row['depth'] = (row['phase_rank'] + (area_count if phase == 'outside_area' else 0)
                        if phase is not None else None)
    grouped = {}
    for row in nomination['rows']:
        if row['depth'] is not None:
            grouped.setdefault(row['depth'], []).append(row)
    frontiers, cumulative = [], 0
    for depth, rows in sorted(grouped.items()):
        first = cumulative + 1
        cumulative += len(rows)
        for row in rows:
            row['first_position'], row['last_position'] = first, cumulative
        frontiers.append({'depth': depth, 'size': len(rows), 'cumulative_size': cumulative})
    nomination['rows'].sort(key=lambda row: (row['depth'] is None, row['depth'] or 0, row['chunk_id']))
    nomination['frontier_sizes'] = frontiers
    nomination['scheduling'] = 'area_first'
    nomination['phase_order'] = list(stream_ids)
    return nomination


def recruit_with_verified_area(
    *, chunk_rows, joint_scores, area_chunk_ids=None, area_provenance=None,
    source_character_budget, scheduling='equal_depth',
):
    """Recruit globally plus one optional verified area, then recover records.

    ``joint_scores`` aligns with chunk_rows and must be finite/nonnegative.
    None means no resolved area and uses exactly one global stream. An explicitly
    empty area is rejected; unresolved/ambiguous landings are handled upstream.
    Repeated area IDs are set membership, not votes. A supplied area's provenance
    is copied for inspection; this function does not independently verify it.

    Equal-depth union is an explicit experimental scheduling convention, not a
    calibrated scope boost or validated final policy. Outside chunks retain the
    global route. Context recovery may admit otherwise unsupported siblings;
    their original stream support is not fabricated. Budget semantics are those
    of recruit_with_record_context: whole-frontier source-character prefixes.

    Optional ``area_first`` concatenates positive in-area and outside nominations,
    each ordered by unchanged scores with ties preserved. Recovery follows this
    schedule and may advance an outside sibling. This is an unvalidated strict
    scope-priority hypothesis; the default remains ``equal_depth``.
    """
    chunks = list(chunk_rows)
    ids = [c['chunkId'] for c in chunks]
    scores = np.asarray(joint_scores, dtype=float)
    if scheduling not in ('equal_depth', 'area_first'):
        raise ValueError('scheduling must be equal_depth or area_first')
    if scores.shape != (len(chunks),) or not np.isfinite(scores).all() or (scores < 0).any():
        raise ValueError('joint_scores must be an aligned finite nonnegative vector')
    stream_ids, streams = ['all'], [scores.copy()]
    area = None
    if area_chunk_ids is not None:
        if isinstance(area_chunk_ids, (str, bytes)):
            raise ValueError('area_chunk_ids must be a collection of chunk IDs')
        try:
            area = set(area_chunk_ids)
        except TypeError as exc:
            raise ValueError('area_chunk_ids must contain hashable chunk IDs') from exc
        if not area:
            raise ValueError('explicit area must be nonempty; use None for no resolved area')
        if not area <= set(ids):
            raise ValueError('area_chunk_ids must be a subset of supplied chunk IDs')
        stream_ids.append('verified_area')
        streams.append(np.where([cid in area for cid in ids], scores, 0.0))
    stream_scores = np.asarray(streams)
    if scheduling == 'area_first' and area is not None:
        mask = np.asarray([cid in area for cid in ids])
        stream_ids = ['verified_area', 'outside_area']
        stream_scores = np.asarray([np.where(mask, scores, 0.0), np.where(~mask, scores, 0.0)])
        recruitment = recover_from_nomination(chunk_rows=chunks,
            nomination=_area_first_nomination(ids, stream_ids, stream_scores),
            source_character_budget=source_character_budget)
    else:
        recruitment = recruit_with_record_context(
            chunk_rows=chunks, stream_ids=stream_ids, stream_scores=stream_scores,
            source_character_budget=source_character_budget,
        )
    return {
        'recruitment': recruitment, 'stream_ids': stream_ids, 'stream_scores': stream_scores,
        'area': {'chunk_ids': None if area is None else sorted(area),
                 'provenance': deepcopy(area_provenance)},
        'policy': {
            'scope': 'One caller-verified area; no inferred names, union, or intersection.',
            'scheduling': scheduling,
            'recruitment': ('Positive in-area nominations first, then positive outside nominations; unchanged score order within each phase.'
                            if scheduling == 'area_first' and area is not None else
                            'Equal-depth union of unchanged joint scores globally and within the area; no duplicate votes.'),
            'outside_area': ('Retains all positive outside nominations; no hard exclusion.'
                             if scheduling == 'area_first' and area is not None else
                             'Retains global nomination; no hard exclusion.'),
            'status': 'Experimental scheduling convention, not validated final scope or facet-weight policy.',
        },
    }
