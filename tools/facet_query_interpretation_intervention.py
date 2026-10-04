"""A frozen factorial intervention on two query-interpretation entry points."""
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact.facet_scope_recruitment import recruit_with_verified_area
from facet_query_reconstruction_replay import read, sha, write

BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
OUT = BASE / 'query_interpretation_intervention/run'
QID = 'independent_sensor_pivot_reason'
BETA = np.array([1., .25, .25, .25, .25])


def main():
    if OUT.exists():
        raise RuntimeError('Existing intervention output; inspect rather than overwrite')
    graph_path = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
    query_path = BASE / 'query_snapshot/queries.json'
    arrays_path = BASE / 'query_snapshot/arrays.npz'
    scope = BASE / 'scope_recruitment/run'
    reconstruction = BASE / 'query_reconstruction/run'
    scope_manifest = read(scope / 'manifest.json')
    recon_manifest = read(reconstruction / 'manifest.json')
    paths = [Path(__file__), OUT.parent / 'PROTOCOL.md', graph_path, query_path, arrays_path,
             scope / 'manifest.json', scope / 'summary.json', reconstruction / 'manifest.json',
             ROOT / 'tools/facet_query_reconstruction_replay.py',
             ROOT / 'test/artefact/facet_scope_recruitment.py',
             ROOT / 'test/artefact/facet_recruitment_candidate.py',
             ROOT / 'test/artefact/facet_need_frontier.py',
             ROOT / 'test/artefact/facet_stream_envelope.py',
             ROOT / 'test/artefact/facet_joint_candidate.py']
    graph = read(graph_path)
    chunks, ids = graph['chunks'], graph['chunk_ids']
    assert [c['chunkId'] for c in chunks] == ids
    queries = read(query_path)
    query, = [q for q in queries['queries'] if q['question_id'] == QID]
    assert queries['chunk_ids'] == ids
    tags = query['tags']
    assert tags == ['sensor protocol support', 'merger', 'strategy reconsideration',
                    'business rationale', 'post-merger integration']
    subsets = {'all': list(range(len(tags))), 'remove_contested': [0, 2, 3]}
    with np.load(arrays_path, allow_pickle=False) as arrays:
        q_options = {'description': np.maximum(arrays['description_chunk_cos'][query['description_index']], 0),
                     'raw_question': np.maximum(arrays['question_chunk_cos'][query['question_index']], 0)}
    old_rows = [r for r in read(scope / 'summary.json') if r['question_id'] == QID]
    assert len(old_rows) == 2
    captures = []
    for old in old_rows:
        rid = old['reading_id']
        archive_path = scope / old['file']
        routes_path = BASE / 'need_selection/replay' / (rid + '_routes.npz')
        assert sha(archive_path) == old['sha256'] == scope_manifest['output_sha256'][old['file']]
        assert sha(routes_path) == scope_manifest['input_sha256'][str(routes_path.relative_to(ROOT))]
        archive = json.loads(gzip.decompress(archive_path.read_bytes()))
        baselines = {}
        for mode in ('max', 'equal'):
            p = reconstruction / (rid + '_' + mode + '.json.gz')
            assert sha(p) == recon_manifest['output_sha256'][p.name]
            baselines[mode] = json.loads(gzip.decompress(p.read_bytes()))
            paths.append(p)
        with np.load(routes_path, allow_pickle=False) as a:
            assert a['chunk_ids'].tolist() == ids
            values = np.maximum(a['direct_scores'], a['graph_scores'])
            assert np.array_equal(a['Q'], q_options['description'])
        assert values.shape == (5, 5, len(ids))
        paths.extend([archive_path, routes_path])
        captures.append((rid, archive, values, baselines))
    input_hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    OUT.mkdir(parents=True)
    write(OUT / 'inputs.json', {'input_sha256': input_hashes, 'question': query['question'],
          'description': query['description'], 'tags': tags, 'subsets': subsets,
          'fixed_beta': BETA, 'source_character_budget': 72000})
    results, exact = [], 0
    for rid, archive, values, baselines in captures:
        for subset, indices in subsets.items():
            active = values[:, indices, :]
            for q_name, q in q_options.items():
                for mode in ('max', 'equal'):
                    # Match the archived geometry runner's equal arithmetic and
                    # canonical group order exactly, without calling its solver.
                    if mode == 'max':
                        profile = active.max(axis=1)
                        scores = q * (profile.T @ BETA)
                    else:
                        with np.load(arrays_path, allow_pickle=False) as a:
                            tag_vectors = a['query_tag_vectors'][query['query_tag_indices']][indices]
                        _, inv = np.unique(tag_vectors, axis=0, return_inverse=True)
                        assert len(set(inv.tolist())) == len(indices)
                        profile = np.zeros((5, len(ids)))
                        for gi in range(len(indices)):
                            ti, = np.flatnonzero(inv == gi)
                            profile += (1.0 / len(indices)) * active[:, ti, :]
                        scores = q * (BETA @ profile)
                    result = recruit_with_verified_area(chunk_rows=chunks, joint_scores=scores,
                        area_chunk_ids=archive['area_chunk_ids'], area_provenance=archive['area'],
                        source_character_budget=72000)
                    if subset == 'all' and q_name == 'description':
                        assert np.array_equal(scores, baselines[mode]['joint_scores'])
                        assert result['recruitment'] == baselines[mode]['recruitment']
                        exact += 1
                    name = f'{rid}_{subset}_{q_name}_{mode}.json.gz'
                    payload = {'reading_id': rid, 'tag_condition': subset, 'Q_condition': q_name,
                        'aggregation': mode, 'joint_scores': scores.tolist(),
                        'facet_profiles': profile.tolist(), 'recruitment': result['recruitment']}
                    (OUT / name).write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False,
                        separators=(',', ':'), allow_nan=False).encode(), mtime=0))
                    results.append((name, payload))
        print(rid, 'eight complete selections saved', flush=True)
    assert exact == 4 and len(results) == 16
    # Outcomes already saved. Source identifiers do not enter intervention choice.
    targets_path = BASE / 'protocol.json'
    target, = [t for t in read(targets_path)['targets'] if t['question_id'] == QID]
    pref, comp = target['preferred'], target['comparison']
    pi, ci = ids.index(pref), ids.index(comp)
    summary = []
    for name, payload in results:
        rows = {r['chunk_id']: r for r in payload['recruitment']['rows']}
        selected = set(payload['recruitment']['selected_chunk_ids'])
        base = next(p for _, p in results if p['reading_id'] == payload['reading_id']
                    and p['aggregation'] == payload['aggregation']
                    and p['tag_condition'] == 'all' and p['Q_condition'] == 'description')
        old_selected = set(base['recruitment']['selected_chunk_ids'])
        profile = np.asarray(payload['facet_profiles'])
        q_delta = q_options['raw_question'] - q_options['description']
        endpoint_delta = float(q_delta[pi] * (BETA @ profile[:, pi]) -
                               q_delta[ci] * (BETA @ profile[:, ci]))
        summary.append({k: payload[k] for k in ('reading_id', 'tag_condition', 'Q_condition', 'aggregation')} |
            {'preferred': pref, 'comparison': comp,
             'preferred_depth': rows[pref]['depth'], 'comparison_depth': rows[comp]['depth'],
             'preferred_score': payload['joint_scores'][pi], 'comparison_score': payload['joint_scores'][ci],
             'margin': payload['joint_scores'][pi] - payload['joint_scores'][ci],
             'Q_endpoint_margin_delta': endpoint_delta,
             'preferred_selected': pref in selected, 'comparison_selected': comp in selected,
             'selected_chunks': len(selected),
             'source_characters': sum(len(chunks[i]['source_text']) for i, cid in enumerate(ids) if cid in selected),
             'added_vs_own_baseline': sorted(selected - old_selected),
             'removed_vs_own_baseline': sorted(old_selected - selected),
             'file': name, 'sha256': sha(OUT / name)})
    sponsors = []
    for rid, _, values, _ in captures:
        for subset, ix in subsets.items():
            winners = np.asarray(ix)[values[:, ix, :].argmax(axis=1)]
            sponsors.append({'reading_id': rid, 'tag_condition': subset,
                'focal': {cid: [tags[t] for t in winners[:, at]] for cid, at in ((pref, pi), (comp, ci))},
                'all_chunk_facet_winners_by_tag': {tag: int((winners == ti).sum()) for ti, tag in enumerate(tags)},
                'values_equal_to_all_tags_everywhere': bool(np.array_equal(values[:, ix, :].max(axis=1), values.max(axis=1)))})
    write(OUT / 'summary.json', summary)
    write(OUT / 'max_sponsors.json', sponsors)
    assert all(sha(ROOT / p) == h for p, h in input_hashes.items())
    input_hashes[str(targets_path.relative_to(ROOT))] = sha(targets_path)
    write(OUT / 'manifest.json', {'input_sha256': input_hashes,
        'output_sha256': {p.name: sha(p) for p in OUT.iterdir() if p.is_file()},
        'baseline_exact': exact, 'selections': len(results), 'new_model_calls': 0,
        'new_embeddings': 0, 'database_calls': 0})


if __name__ == '__main__':
    main()
