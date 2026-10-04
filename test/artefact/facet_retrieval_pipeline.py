"""Experimental prepared-query integration; no interpreter, model, or DB access.

Explicit coefficients are a provisional caller policy, not learned utilities.
Scores nominate chunks; exact-record recovery supplies context without imputing
facet evidence to siblings. The budget counts saved source characters and keeps
whole frontiers, not production-resolved payloads or partial boundary texts.
"""
from copy import deepcopy

import numpy as np

from artefact.facet_joint_candidate import FACETS
from artefact.facet_recruitment_candidate import recruit_with_record_context
from artefact.facet_stream_envelope import rank_facet_stream_envelope


def retrieve_prepared_query(
    *, chunk_rows, coefficients, source_character_budget,
    query_tag_ids, edge_ids, edge_tag_indices, edge_chunk_indices, edge_facets,
    query_facet_weights, query_tag_cosines, query_chunk_cosines,
    query_description_cosines, reference, groups=None, adjacency_pairs=(),
    facets_enabled=True,
):
    """Compose magnitude-preserving nomination with structural context recovery.

    All chunk-indexed arrays must align with ``chunk_rows``. Query tags and their
    weights retain the supplied order. Coefficients are REQUIRED, ordered as
    FACETS, finite, with topic strictly positive and auxiliaries nonnegative.
    ``source_character_budget`` is also explicit; None means no character cut.

    ``ranking`` retains each original facet winner and raw query relevance u;
    only its final coefficient/contribution and combined score are recomputed.
    Ranking rank is a deterministic score-order position, including zero scores;
    supported nomination depths live in ``recruitment['nomination']`` instead.
    ``contexts`` carry their own original facet evidence separately from the
    recovery trigger. A recovered sibling never inherits the trigger's score or
    facet witness. No query interpretation or scope assignment is performed.
    """
    beta = np.asarray(coefficients, dtype=float)
    if (beta.shape != (len(FACETS),) or not np.isfinite(beta).all()
            or beta[0] <= 0 or (beta[1:] < 0).any()):
        raise ValueError("coefficients require five finite values: topic > 0, auxiliaries >= 0")
    if source_character_budget is not None and (
        type(source_character_budget) is not int or source_character_budget < 0
    ):
        raise ValueError("source_character_budget must be None or a nonnegative integer")
    chunks = list(chunk_rows)
    ids = [c['chunkId'] for c in chunks]
    tags = list(query_tag_ids)
    envelope = rank_facet_stream_envelope(
        chunk_ids=ids, query_tag_ids=tags, edge_ids=edge_ids,
        edge_tag_indices=edge_tag_indices, edge_chunk_indices=edge_chunk_indices,
        edge_facets=edge_facets, query_facet_weights=query_facet_weights,
        query_tag_cosines=query_tag_cosines, query_chunk_cosines=query_chunk_cosines,
        query_description_cosines=query_description_cosines, reference=reference,
        groups=groups, adjacency_pairs=adjacency_pairs, facets_enabled=facets_enabled,
    )
    q = np.maximum(np.asarray(query_description_cosines, dtype=float), 0)
    scores = q * (envelope['per_facet_scores'] @ beta)
    at = {cid: c for c, cid in enumerate(ids)}
    rows = deepcopy(envelope['rows'])
    for row in rows:
        c = at[row['chunk_id']]
        row['score'] = float(scores[c])
        for f, facet in enumerate(FACETS):
            witness = row['provenance'][facet]
            if witness is not None:
                witness['coefficient'] = float(beta[f])
                witness['contribution'] = float(q[c] * beta[f] * witness['Z'])
    rows.sort(key=lambda row: (-row['score'], row['chunk_id']))
    ranks = np.empty(len(ids), dtype=int)
    for rank, row in enumerate(rows, 1):
        row['rank'] = rank
        ranks[at[row['chunk_id']]] = rank
    ranking = {
        **envelope, 'rows': rows, 'scores': scores, 'ranks': ranks,
        'ranked_chunk_ids': [row['chunk_id'] for row in rows],
        'coefficients': beta.tolist(), 'facets': list(FACETS), 'query_tag_ids': tags,
    }
    recruitment = recruit_with_record_context(
        chunk_rows=chunks, stream_ids=['joint'], stream_scores=scores[None, :],
        source_character_budget=source_character_budget,
    )
    by_id = {row['chunk_id']: row for row in rows}
    recovery = {row['chunk_id']: row for row in recruitment['rows']}
    contexts = []
    for cid in recruitment['selected_chunk_ids']:
        chunk = chunks[at[cid]]
        contexts.append({
            'chunk_id': cid, 'source_text': chunk['source_text'],
            'relpath': chunk['relpath'], 'locator': deepcopy(chunk['locator']),
            'nomination_score': by_id[cid]['score'],
            'facet_provenance': deepcopy(by_id[cid]['provenance']),
            'recovery': deepcopy(recovery[cid]),
        })
    return {'ranking': ranking, 'recruitment': recruitment, 'contexts': contexts,
            'policy': {
                'input': 'Prepared query arrays; no raw-query interpretation or inferred scope.',
                'coefficients': beta.tolist(),
                'coefficient_status': 'Explicit provisional caller policy; not learned or validated utilities.',
                'nomination': 'Whole-query-description factor times coefficient-weighted facet maxima over all supplied query tags and routes.',
                'context_recovery': 'Contiguous exact-record parts inherit earliest supported nomination depth; scores and facet witnesses remain unchanged.',
                'source_character_budget': source_character_budget,
                'budget_contract': 'Complete-frontier prefix using saved source_text characters per unique chunk; overlap counted, no truncation or production-serialization claim.',
            }}
