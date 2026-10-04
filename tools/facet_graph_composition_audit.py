"""Topology-only audit of the serving arm's graph transfer composition.

No questions, gold, embeddings, corpus text, DB writes or model calls. Reads the
pinned prepared graph mechanically; exports counts/hashes and synthetic scores.
The numeric check is a construction check, not retrieval-quality evaluation.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from arms import artefact_facet_joint as A
from artefact.facet_joint_candidate import freeze_reference, rank_joint_candidate


def synthetic_inputs(n):
    x = np.arange(n)
    return dict(
        chunk_ids=[f'chunk-{i:05d}' for i in x], query_tag_ids=['synthetic-a', 'synthetic-b'],
        edge_ids=[f'edge-{i:05d}' for i in x], edge_tag_indices=x,
        edge_chunk_indices=x, edge_facets=np.ones((n, 5)),
        query_facet_weights=np.array([[1, .2, .4, .6, .8], [.8, .6, .4, .2, 1]]),
        query_tag_cosines=np.array([((x * 17) % 101) / 100, ((x * 31) % 103) / 102]),
        query_chunk_cosines=np.array([.2 + .8 * ((x * 7) % 97) / 96,
                                     .1 + .9 * ((x * 11) % 89) / 88]),
        query_description_cosines=.3 + .7 * ((x * 13) % 83) / 82,
        reference=freeze_reference(np.array([[0] * 5, [1] * 5])),
    )


def main():
    prepared = A.prepare_over_corpus('topology-only-audit')
    groups = prepared.groups['shared_product_channel']
    memberships = [set() for _ in prepared.chunks]
    for g, members in enumerate(groups):
        for c in members:
            memberships[c].add(g)
    counts = Counter()
    additional = []
    for a, b in prepared.adjacency_pairs:
        locator = prepared.chunks[a]['locator']
        locator = json.loads(locator) if isinstance(locator, str) else locator
        kind = locator.get('section', 'unknown')
        covered = bool(memberships[a] & memberships[b])
        counts[kind, 'total'] += 1
        counts[kind, 'covered' if covered else 'additional'] += 1
        if not covered:
            additional.append((a, b))
    args = synthetic_inputs(len(prepared.chunks))
    full = rank_joint_candidate(**args, groups=prepared.groups,
                                adjacency_pairs=prepared.adjacency_pairs)
    reduced = rank_joint_candidate(**args, groups=prepared.groups,
                                   adjacency_pairs=additional)
    checks = {key: bool(np.array_equal(full[key], reduced[key]))
              for key in ('scores', 'direct_scores', 'graph_scores', 'ranks')}
    if not all(checks.values()):
        raise AssertionError(checks)
    # A distant seed in the same channel can beat a local neighbour. Removing
    # the local link then cannot alter the target score under this max reducer.
    tiny = synthetic_inputs(3)
    tiny.update(query_tag_cosines=np.array([[1, .2, 0], [0, 0, 0]]),
                query_chunk_cosines=np.ones((2, 3)),
                query_description_cosines=np.ones(3),
                query_facet_weights=np.array([[1, 0, 0, 0, 0], [0, 0, 0, 0, 0]]))
    neighbours = rank_joint_candidate(**tiny, adjacency_pairs=[(1, 2)])
    channel = rank_joint_candidate(**tiny, groups={'shared_product_channel': [[0, 1, 2]]},
                                  adjacency_pairs=[(1, 2)])
    files = [Path(__file__), ROOT / 'test/arms/artefact_facet_joint.py',
             ROOT / 'test/arms/artefact_v3.py', ROOT / 'test/artefact/facet_joint_candidate.py']
    out = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'graph_sha256': A.PINNED_FILES['graph.json'],
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in files},
        'counts': {'chunks': len(prepared.chunks), 'product_channel_groups': len(groups),
                   'grouped_chunks': sum(bool(m) for m in memberships),
                   'adjacency_pairs': len(prepared.adjacency_pairs),
                   'additional_pairs': len(additional)},
        'by_kind': {kind: {key: counts[kind, key] for key in ('total', 'covered', 'additional')}
                    for kind in sorted({k[0] for k in counts})},
        'synthetic_full_topology_exact_checks': checks,
        'three_chunk_example': {
            'direct_scores': channel['direct_scores'][0].tolist(),
            'target_graph_support_adjacency_only': float(neighbours['graph_scores'][0, 2]),
            'target_graph_support_with_channel_group': float(channel['graph_scores'][0, 2]),
        },
        'proof': 'For every covered adjacency a-b, a and b are already members of one group. '
                 'That group offers at least the same 0.5*direct[a]*D[b] (and reverse) '
                 'under self exclusion. Max over offers cannot increase when covered '
                 'adjacency is added. This applies independently to every query tag and facet.',
        'limits': ['Equal scores can select a different provenance route label.',
                   'No retrieval-quality conclusion or coefficient choice follows.',
                   'Groups are intersections of product and channel membership, not separate product cliques.',
                   'Document and transcript adjacency is not covered by these groups.'],
    }
    path = ROOT / 'output/research/2026-09-22-graph-composition/audit.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
