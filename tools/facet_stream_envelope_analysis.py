"""Verify frozen outputs and attribute the facet-envelope comparison."""
from pathlib import Path
import json
import hashlib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/source_first'
OUT = BASE / 'facet_stream_envelope'
FACETS = ('topic', 'temporal', 'why', 'activity', 'concreteness')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    summary = read(OUT / 'summary.json')
    for relative, expected in read(OUT / 'protocol.json')['input_sha256'].items():
        assert sha(ROOT / relative) == expected
    output = []
    for run in summary:
        path = OUT / run['file']
        assert sha(path) == run['sha256']
        current = read(path)
        previous = read(BASE / 'joint_candidate' / run['file'])
        old = {r['chunk_id']: r for r in previous['rows']}
        assert len(current['rows']) == len({r['chunk_id'] for r in current['rows']}) == 4808
        min_increase = min(r['score'] - old[r['chunk_id']]['score'] for r in current['rows'])
        assert min_increase > -1e-12
        reconstruction_error = max(abs(r['score'] - sum(w['contribution'] for w in r['provenance'].values() if w))
                                   for r in current['rows'])
        assert reconstruction_error < 1e-12
        changed = sum(r['rank'] != old[r['chunk_id']]['rank'] for r in current['rows'])
        multi = sum(len({(w['query_tag_id'], w['edge_id'], w['seed_chunk_id'], w['route_type'])
                        for w in r['provenance'].values() if w}) > 1 for r in current['rows'])
        a, b = (current['focal'][x] for x in ('preferred', 'comparison'))
        delta = np.array([(a['provenance'][f]['contribution'] if a['provenance'][f] else 0)
                          - (b['provenance'][f]['contribution'] if b['provenance'][f] else 0)
                          for f in FACETS]) / np.array([1, .25, .25, .25, .25])
        # These are conditional bounds for a stated coefficient family, NOT
        # selected/fitted coefficients and not a definition of 'topic main'.
        maximum_with_topic_ge_each = float(delta[0] + np.maximum(delta[1:], 0).sum())
        maximum_with_topic_ge_sum = float(delta[0] + max(0, delta[1:].max()))
        output.append({'reading_id': run['reading_id'], 'condition': run['condition'],
                       'source': run['source'], 'question_id': run['question_id'],
                       'preferred_rank': a['rank'], 'comparison_rank': b['rank'],
                       'pair_correct': run['expected_pair_correct'],
                       'old_pair_correct': previous['expected_pair_correct'],
                       'changed_ranks': changed, 'multiple_facet_sponsors': multi,
                       'graph_selected_chunks': run['graph_selected_chunks'],
                       'min_score_increase': min_increase, 'max_reconstruction_error': reconstruction_error,
                       'unweighted_focal_differences': delta.tolist(),
                       'maximum_focal_gap_topic_ge_each_aux': maximum_with_topic_ge_each,
                       'maximum_focal_gap_topic_ge_sum_aux': maximum_with_topic_ge_sum})
    for r in output:
        if r['condition'] == 'intact':
            print(r['reading_id'], r['preferred_rank'], r['comparison_rank'], r['pair_correct'],
                  'mixed', r['multiple_facet_sponsors'], 'graph', r['graph_selected_chunks'],
                  'bound', r['maximum_focal_gap_topic_ge_each_aux'])
    (OUT / 'analysis.json').write_text(json.dumps({'runs': output, 'output_rows_verified': 4808 * len(output),
        'bound_contract': 'Topic coefficient fixed at 1; four auxiliary coefficients nonnegative. First bound restricts each to <=1, second their sum to <=1. Conditional on these fixed route profiles only. No weights selected.',
        'input_hashes_verified': True}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
