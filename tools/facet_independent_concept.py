"""Replay frozen independent-source readings through the unchanged concept runner.

Only read/np.load input boundaries and diagnostic focal IDs are adapted. Static
graph, current file facets, source concept defaults and all operators stay fixed.
Query scope is not inferred from source labels. No source resolution or delivery
is run. Original tools and previous results remain immutable.
"""
from datetime import datetime, timezone
from pathlib import Path

import facet_concept_replay as replay

ROOT = replay.ROOT
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
OUT = BASE / 'concept_baseline'
QUERY = BASE / 'query_snapshot'
CAPTURE = BASE / 'query_capture/query_captures.json'
STATIC = replay.BASE / 'route_snapshot'
OLD_CAPTURE = replay.BASE / 'route_capture/query_captures.json'


def focal_ids(targets):
    """Collect unique diagnostic endpoints, without passing preferences to ranking."""
    ids = set()
    for target in targets:
        pair = [target.get('preferred'), target.get('comparison')]
        required = target.get('required_within_selected_pair') or []
        if not (all(pair) or len(required) >= 2):
            raise ValueError('Target has no complete diagnostic pair: ' + target['question_id'])
        ids.update(cid for cid in pair + required if cid)
    return {'chunk_' + cid: cid for cid in sorted(ids)}


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError('Baseline output already exists; do not overwrite frozen evidence')
    original_read, original_load, original_write = replay.read, replay.np.load, replay.write
    original_out, original_focal = replay.OUT, replay.FOCAL
    graph = original_read(STATIC / 'graph.json')
    query = original_read(QUERY / 'queries.json')
    manifest = original_read(QUERY / 'manifest.json')
    captures = original_read(CAPTURE)
    cases = original_read(BASE / 'protocol.json')
    questions = original_read(BASE / 'questions.json')
    if replay.sha(STATIC / 'graph.json') != cases['source_snapshot_sha256']:
        raise ValueError('Source-case static graph hash mismatch')
    if replay.sha(BASE / 'questions.json') != cases['questions_sha256']:
        raise ValueError('Frozen question file hash mismatch')
    for name, expected in manifest['output_sha256'].items():
        if replay.sha(QUERY / name) != expected:
            raise ValueError('Query snapshot hash mismatch: ' + name)
    if not manifest['generation_fields']:
        raise ValueError('Query snapshot has no generation fields')
    fields = [{k: c[k] for k in manifest['generation_fields'][0]} for c in captures['captures']]
    if fields != manifest['generation_fields']:
        raise ValueError('Query generation fields changed since the vector snapshot')
    for key in ('graph_tags', 'band_graph_tag_names', 'chunk_ids'):
        if graph[key] != query[key]:
            raise ValueError('Static/query snapshot population mismatch: ' + key)
    question_by_id = {q['id']: q['question'] for q in questions}
    target_ids = [t['question_id'] for t in cases['targets']]
    captured_ids = [c['question_id'] for c in captures['captures']]
    if (len(question_by_id) != len(questions) or len(set(target_ids)) != len(target_ids)
            or len(set(captured_ids)) != len(captured_ids)
            or set(target_ids) != set(question_by_id) or set(captured_ids) != set(target_ids)):
        raise ValueError('Expected exactly one capture per frozen question and target')
    for capture in captures['captures']:
        if capture['question'] != question_by_id[capture['question_id']]:
            raise ValueError('Captured question differs from frozen input')
        if capture['generation_id'] != capture['question_id'] + '_0':
            raise ValueError('Expected one generation per question, with suffix _0')
        if len(capture['readings']) != 2 or not all(r['ok'] for r in capture['readings']):
            raise ValueError('Each generation needs exactly two successful SCORE readings')
    run_ids = [r['id'] for c in captures['captures'] for r in c['readings']]
    if len(set(run_ids)) != len(run_ids):
        raise ValueError('Duplicate reading IDs')
    if {q['generation_id'] for q in query['queries']} != {c['generation_id'] for c in captures['captures']}:
        raise ValueError('Snapshot query generations do not match captures')
    focal = focal_ids(cases['targets'])
    if not set(focal.values()).issubset(graph['chunk_ids']):
        raise ValueError('Diagnostic focal chunk is absent from the eligible static population')
    adapted_graph = {**graph, **{k: query[k] for k in ('query_tags', 'questions', 'queries')}}
    with original_load(STATIC / 'arrays.npz') as static_arrays:
        adapted_arrays = {k: static_arrays[k] for k in static_arrays.files}
    with original_load(QUERY / 'arrays.npz') as query_arrays:
        changed_arrays = list(query_arrays.files)
        adapted_arrays.update({k: query_arrays[k] for k in query_arrays.files})
    if any(k.startswith('edge_') or k == 'candidate_tag' for k in changed_arrays):
        raise ValueError('Query adapter attempted to change static graph arrays')
    sources = [Path(__file__), Path(replay.__file__), CAPTURE, BASE / 'protocol.json', BASE / 'questions.json',
               QUERY / 'queries.json', QUERY / 'arrays.npz', QUERY / 'manifest.json', QUERY / 'protocol.json']
    contract = {'protocol': __doc__, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
                'source_sha256': {str(p.relative_to(ROOT)): replay.sha(p) for p in sources},
                'read_overrides': {
                    str(STATIC / 'graph.json'): 'Static graph with query_tags/questions/queries replaced by query_snapshot/queries.json fields.',
                    str(OLD_CAPTURE): 'Replaced entirely by independent_sources/query_capture/query_captures.json.'},
                'np_load_override': {str(STATIC / 'arrays.npz'): 'Static arrays retained; only listed query arrays replaced by independent_sources/query_snapshot/arrays.npz.'},
                'query_array_keys_replaced': changed_arrays,
                'focal_ids': focal,
                'focal_selection_use': 'Diagnostic tracing only. Preferred/comparison/required roles remain in the external case protocol and never enter routing or keys.',
                'question_ids': captured_ids, 'generation_count': len(captured_ids),
                'runs': run_ids, 'expected_run_count': 2 * len(target_ids),
                'static_graph_unchanged': True,
                'operators': 'Same source concept defaults + current file facet overlay + split-input adapter as the previous baseline.',
                'scope_policy': 'No gate supplied; no product or source scope inferred from diagnostic targets.',
                'delivery': False, 'model_calls': 0, 'db_calls': 0, 'source_corpus_reads': 0}
    OUT.mkdir(parents=True, exist_ok=True)
    original_write(OUT / 'adapter_contract.json', contract)

    def adapted_read(path):
        if Path(path) == STATIC / 'graph.json':
            return adapted_graph
        if Path(path) == OLD_CAPTURE:
            return captures
        return original_read(path)

    def adapted_load(path, *args, **kwargs):
        if isinstance(path, (str, Path)) and Path(path) == STATIC / 'arrays.npz':
            return adapted_arrays
        return original_load(path, *args, **kwargs)

    def adapted_write(path, body):
        if Path(path) == OUT / 'protocol.json':
            body = {**body,
                    'input_boundary_intervention': contract,
                    'adapter_contract_sha256': replay.sha(OUT / 'adapter_contract.json'),
                    'source_manifest_note': 'Original source hashes below identify the base files before boundary adaptation; input_boundary_intervention records effective query inputs and adapter hashes.'}
        original_write(path, body)

    replay.read, replay.np.load, replay.write = adapted_read, adapted_load, adapted_write
    replay.OUT, replay.FOCAL = OUT, focal
    try:
        replay.main()
    finally:
        replay.read, replay.np.load, replay.write = original_read, original_load, original_write
        replay.OUT, replay.FOCAL = original_out, original_focal
    summary = original_read(OUT / 'summary.json')
    verification = {'adapter_contract_sha256': replay.sha(OUT / 'adapter_contract.json'),
                    'protocol_sha256_matches': replay.sha(OUT / 'protocol.json') == summary['protocol_sha256'],
                    'effective_sources_unchanged': {k: replay.sha(ROOT / k) == v for k, v in contract['source_sha256'].items()},
                    'run_count_matches': len(summary['runs']) == len(run_ids),
                    'runs': []}
    for row in summary['runs']:
        path = OUT / (row['run_id'] + '.json')
        result = original_read(path)
        ids = result['chunk_order']
        verification['runs'].append({'run_id': row['run_id'], 'result_hash_matches': replay.sha(path) == row['source_sha256'],
                                      'chunk_count': len(ids), 'unique_chunk_count': len(set(ids)),
                                      'full_population': set(ids) == set(graph['chunk_ids']),
                                      'focal_ids_match': {v['chunk_id'] for v in result['focal'].values()} == set(focal.values())})
    original_write(OUT / 'verification.json', verification)
    if (not verification['protocol_sha256_matches'] or not verification['run_count_matches']
            or not all(verification['effective_sources_unchanged'].values())
            or not all(r['result_hash_matches'] and r['full_population'] and r['focal_ids_match']
                       and r['chunk_count'] == r['unique_chunk_count'] for r in verification['runs'])):
        raise ValueError('Completed baseline failed integrity checks; see verification.json')
    print('Independent-source concept baseline complete: ' + str(OUT), flush=True)


if __name__ == '__main__':
    main()
