"""Deterministic conditional correspondence controls, without outcome readers.

Edge auxiliary four-vectors move jointly only within graph-tag x record-kind
strata. Record kind is source_kind, checked against original description k.
Topic stays attached to its original edge. The caller retains the same frozen
reference CDF and topology: neither is changed or reconstructed here.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json

import numpy as np


def _seed(seed):
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)) or not 0 <= seed <= 7:
        raise ValueError('Control seed must be an integer from 0 through 7')
    return int(seed)


def _rng(namespace, seed, identity):
    payload = json.dumps([namespace, _seed(seed), identity], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    digest = hashlib.sha256(payload).digest()
    return np.random.Generator(np.random.PCG64(int.from_bytes(digest[:16], 'big')))


def _matrix(values, label):
    out = np.asarray(values)
    if out.ndim != 2 or out.shape[1] != 5 or not np.issubdtype(out.dtype, np.number) or not np.isfinite(out).all():
        raise ValueError(label + ' must be a finite numeric [rows,5] matrix')
    return out


def _indices(values, size, label):
    out = np.asarray(values)
    if out.shape != (size,) or not np.issubdtype(out.dtype, np.integer) or (out < 0).any():
        raise ValueError(label + ' must be an aligned nonnegative integer vector')
    return out


def edge_shuffle(prepared, seed):
    """Return (raw edge facets copy, coverage), retaining tag/kind marginals.

    Random permutations may retain positions or exchange equal vectors; both
    moved-row count and actually changed-vector count are reported. Singleton
    strata are untouched. No fallback across kinds or graph tags is permitted.
    """
    seed = _seed(seed)
    facets = _matrix(prepared.edge_facets, 'edge_facets')
    tags = _indices(prepared.edge_tag, len(facets), 'edge_tag')
    chunks = _indices(prepared.edge_chunk, len(facets), 'edge_chunk')
    if (chunks >= len(prepared.chunks)).any():
        raise ValueError('edge_chunk endpoint outside chunks')
    kinds = []
    for row in prepared.chunks:
        kind = row.get('source_kind')
        metadata = row.get('original_description_metadata', {})
        if not isinstance(kind, str) or not kind or metadata.get('k') != kind:
            raise ValueError('source_kind missing or inconsistent with original description metadata k')
        kinds.append(kind)
    strata = defaultdict(list)
    edge_kind_counts = Counter()
    for i, (tag, chunk) in enumerate(zip(tags, chunks)):
        kind = kinds[int(chunk)]
        strata[int(tag), kind].append(i)
        edge_kind_counts[kind] += 1
    source_rows = np.arange(len(facets))
    for key, members in sorted(strata.items()):
        if len(members) > 1:
            indices = np.asarray(members)
            source_rows[indices] = _rng('edge-tag-kind-v1', seed, key).permutation(indices)
    shuffled = facets.copy()
    shuffled[:, 1:] = facets[source_rows, 1:]
    coverage = {
        'mode': 'within_graph_tag_and_record_kind', 'seed': seed,
        'edges': len(facets), 'strata': len(strata),
        'non_singleton_edges': sum(len(x) for x in strata.values() if len(x) > 1),
        'singleton_edges': sum(len(x) == 1 for x in strata.values()),
        'moved_rows': int(np.count_nonzero(source_rows != np.arange(len(facets)))),
        'actually_changed_vectors': int(np.count_nonzero(np.any(shuffled[:, 1:] != facets[:, 1:], axis=1))),
        'chunk_kind_counts': dict(sorted(Counter(kinds).items())),
        'edge_kind_counts': dict(sorted(edge_kind_counts.items())),
        'stratum_size_histogram': {str(size): count for size, count in sorted(Counter(map(len, strata.values())).items())},
        'permutation_sha256': hashlib.sha256(source_rows.astype('<i8').tobytes()).hexdigest(),
        'topic_unchanged': bool(np.array_equal(shuffled[:, 0], facets[:, 0])),
        'reference_and_topology': 'unchanged; caller keeps original prepared reference and routes',
    }
    return shuffled, coverage


def query_shuffle(weights, question_id, seed):
    """Jointly permute auxiliary vectors across one query's tag rows.

    Topic relevance remains on its original row. RNG identity depends only on
    an opaque question ID and seed, not question text, outcomes or row values.
    """
    seed = _seed(seed)
    if not isinstance(question_id, str) or not question_id:
        raise ValueError('question_id must be a nonempty opaque string')
    values = _matrix(weights, 'weights')
    if (values < 0).any():
        raise ValueError('Query facet weights must be nonnegative')
    permutation = _rng('query-tag-aux-v1', seed, question_id).permutation(len(values))
    shuffled = values.copy()
    shuffled[:, 1:] = values[permutation, 1:]
    return shuffled, {
        'seed': seed, 'rows': len(values),
        'non_singleton_rows': len(values) if len(values) > 1 else 0,
        'moved_rows': int(np.count_nonzero(permutation != np.arange(len(values)))),
        'actually_changed_vectors': int(np.count_nonzero(np.any(shuffled[:, 1:] != values[:, 1:], axis=1))),
        'permutation_sha256': hashlib.sha256(permutation.astype('<i8').tobytes()).hexdigest(),
        'topic_unchanged': bool(np.array_equal(shuffled[:, 0], values[:, 0])),
    }
