"""Replay eight source-first readings through the unchanged frozen concept runner.

Only read/np.load input boundaries and diagnostic focal IDs are adapted. Static
graph, current file facets, source concept defaults and all operators stay fixed.
The original runner and previous results remain immutable. No delivery is run.
"""
from pathlib import Path
from datetime import datetime, timezone

import facet_concept_replay as replay

ROOT = replay.ROOT
BASE = ROOT / 'output/research/2026-09-22-joint-streams/source_first'
OUT = BASE / 'concept_baseline'
QUERY = BASE / 'query_snapshot'
CAPTURE = BASE / 'query_capture/query_captures.json'
STATIC = replay.BASE / 'route_snapshot'
OLD_CAPTURE = replay.BASE / 'route_capture/query_captures.json'


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError('Baseline output already exists; do not overwrite frozen evidence')
    original_read, original_load, original_write = replay.read, replay.np.load, replay.write
    graph = original_read(STATIC / 'graph.json')
    query = original_read(QUERY / 'queries.json')
    manifest = original_read(QUERY / 'manifest.json')
    captures = original_read(CAPTURE)
    cases = original_read(BASE / 'case_protocol.json')
    for name, expected in manifest['output_sha256'].items():
        if replay.sha(QUERY / name) != expected:
            raise ValueError('Query snapshot hash mismatch: ' + name)
    fields = [{k: c[k] for k in manifest['generation_fields'][0]} for c in captures['captures']]
    if fields != manifest['generation_fields']:
        raise ValueError('Query generation fields changed since the vector snapshot')
    for key in ('graph_tags', 'band_graph_tag_names', 'chunk_ids'):
        if graph[key] != query[key]:
            raise ValueError('Static/query snapshot population mismatch: ' + key)
    if len(captures['captures']) != 4 or any(len(c['readings']) != 2 or not all(r['ok'] for r in c['readings']) for c in captures['captures']):
        raise ValueError('Exactly four successful generations with two valid readings each are required')
    focal = {case['question_id']: case['preferred'] for case in cases['expected_pair_preferences']}
    if len(focal) != 4 or len(set(focal.values())) != 4:
        raise ValueError('Expected exactly four distinct source focal IDs')
    adapted_graph = {**graph, **{k: query[k] for k in ('query_tags', 'questions', 'queries')}}
    with original_load(STATIC / 'arrays.npz') as static_arrays:
        adapted_arrays = {k: static_arrays[k] for k in static_arrays.files}
    with original_load(QUERY / 'arrays.npz') as query_arrays:
        changed_arrays = list(query_arrays.files)
        adapted_arrays.update({k: query_arrays[k] for k in query_arrays.files})
    if any(k.startswith('edge_') or k == 'candidate_tag' for k in changed_arrays):
        raise ValueError('Query adapter attempted to change static graph arrays')
    sources = [Path(__file__), Path(replay.__file__), CAPTURE, BASE / 'case_protocol.json',
               QUERY / 'queries.json', QUERY / 'arrays.npz', QUERY / 'manifest.json', QUERY / 'protocol.json']
    contract = {'protocol': __doc__, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
                'source_sha256': {str(p.relative_to(ROOT)): replay.sha(p) for p in sources},
                'read_overrides': {
                    str(STATIC / 'graph.json'): 'Static graph with query_tags/questions/queries replaced by query_snapshot/queries.json fields.',
                    str(OLD_CAPTURE): 'Replaced entirely by source_first/query_capture/query_captures.json.'},
                'np_load_override': {str(STATIC / 'arrays.npz'): 'Static arrays retained; only listed query arrays replaced by source_first/query_snapshot/arrays.npz.'},
                'query_array_keys_replaced': changed_arrays,
                'focal_ids': focal,
                'focal_selection_use': 'Diagnostic tracing only; expected preferences never enter routing or keys.',
                'runs': [r['id'] for c in captures['captures'] for r in c['readings']],
                'static_graph_unchanged': True,
                'operators': 'Same source concept defaults + current file facet overlay + split-input adapter as the previous baseline.',
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
    summary = original_read(OUT / 'summary.json')
    verification = {'adapter_contract_sha256': replay.sha(OUT / 'adapter_contract.json'),
                    'protocol_sha256_matches': replay.sha(OUT / 'protocol.json') == summary['protocol_sha256'],
                    'effective_sources_unchanged': {k: replay.sha(ROOT / k) == v for k, v in contract['source_sha256'].items()},
                    'runs': []}
    for row in summary['runs']:
        path = OUT / (row['run_id'] + '.json')
        result = original_read(path)
        ids = result['chunk_order']
        verification['runs'].append({'run_id': row['run_id'], 'result_hash_matches': replay.sha(path) == row['source_sha256'],
                                      'chunk_count': len(ids), 'unique_chunk_count': len(set(ids)),
                                      'full_population': set(ids) == set(graph['chunk_ids'])})
    original_write(OUT / 'verification.json', verification)
    print('Source-first concept baseline complete: ' + str(OUT), flush=True)


if __name__ == '__main__':
    main()
