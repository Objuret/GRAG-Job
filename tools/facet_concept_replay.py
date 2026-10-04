"""Offline replay of concept-default operators with the frozen current file layer.

This uses the intended split captures as an experimental adapter. It is not an
untouched production-default run: FACET_SOURCE=file replaces the default edge
statistics. There are no model, DB, raw-corpus or benchmark reads and no delivery.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import os
import sys
import time

for variable in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '4'
import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-21-facet-validity'
OUT = ROOT / 'output/research/2026-09-22-joint-streams/concept'
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
FOCAL = {'report': '23540be897d31a78f8ac0f39', 'sharing': '62eecebfe117e91df15db8e3'}


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def convert(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    raise TypeError(type(v).__name__)


def write(p, body):
    p.write_text(json.dumps(body, ensure_ascii=False, indent=2, allow_nan=False, default=convert) + '\n', encoding='utf-8')


def forbidden(*args, **kwargs):
    raise RuntimeError('Offline concept replay attempted a forbidden model, DB or source-resolution boundary')


class FrozenShapeSession:
    def __init__(self, arm, graph):
        self.arm, self.graph, self.calls = arm, graph, []

    def run(self, query, **parameters):
        self.calls.append({'query': query, 'parameters': parameters})
        if query == self.arm._SHAPE_CYPHER:
            return [{'chunkId': c['chunkId'],
                     'products': [x['node_id'] for x in c['scope'].get('product', [])],
                     'channels': [x['node_id'] for x in c['scope'].get('channel', [])]}
                    for c in self.graph['chunks']]
        if query == self.arm._PRODUCT_NAMES_CYPHER:
            return [{'name': name} for name in self.graph['product_names']]
        raise RuntimeError('Unexpected DB query at frozen boundary: ' + query)


def main():
    print('Offline concept assembly: freezing inputs/config before replay', flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'summary.json').exists():
        raise RuntimeError('Completed replay exists; inspect it rather than overwrite results')
    graph_path = BASE / 'route_snapshot/graph.json'
    array_path = BASE / 'route_snapshot/arrays.npz'
    vectors_path = BASE / 'route_snapshot/graph_vectors.npz'
    capture_path = BASE / 'route_capture/query_captures.json'
    snapshot_manifest = read(BASE / 'route_snapshot/manifest.json')
    graph, captures = read(graph_path), read(capture_path)
    arrays, vectors = np.load(array_path), np.load(vectors_path)
    for path in (graph_path, array_path, vectors_path):
        if sha(path) != snapshot_manifest['output_sha256'][path.name]:
            raise ValueError('Frozen snapshot hash mismatch: ' + str(path))
    overlay_path = ROOT / 'output/facet_pairs/rounds/round1/overlay.json'
    expected_overlay = snapshot_manifest['source_sha256'][str(overlay_path)]
    if sha(overlay_path) != expected_overlay:
        raise ValueError('Original full overlay changed; product-edge values cannot be guessed')
    # Process-local explicit default settings; do not inherit an unrelated run's
    # overrides. The source functions themselves remain unchanged.
    initial = {k: v for k, v in os.environ.items() if k.startswith(('HERB_V3_', 'HERB_FACET_', 'HERB_RANK_'))}
    for name in initial:
        os.environ.pop(name)
    os.environ['HERB_V3_SORT'] = 'concept'
    os.environ['HERB_FACET_SOURCE'] = 'file'
    os.environ['HERB_FACET_FILE'] = str(overlay_path)
    from arms import artefact_v3 as arm
    from arms import artefact_v2
    from graph import db
    from harness import embed, chat
    # Make prohibited boundaries fail immediately, including fallback paths.
    for owner, names in ((arm, ['_driver', '_resolve_chunk', '_budget_contexts', '_chat_json']),
                         (artefact_v2, ['_driver', '_resolve_chunk', '_load_verified_doc', '_budget_contexts', '_chat_json']),
                         (db, ['_driver']), (embed, ['_embed', '_embed_request', '_embedder'])):
        for name in names:
            setattr(owner, name, forbidden)

    prepared_names = graph['band_graph_tag_names']
    all_at = {t: i for i, t in enumerate(graph['all_graph_vector_tag_names'])}
    tag_at = {t: i for i, t in enumerate(prepared_names)}
    chunk_ids = graph['chunk_ids']
    chunk_at = {cid: i for i, cid in enumerate(chunk_ids)}
    tag_raw = vectors['tag_raw_float32'][[all_at[t] for t in prepared_names]]
    chunk_raw = vectors['chunk_raw_float32']
    full_edges = [(graph['chunk_ids'][c], graph['graph_tags'][t])
                  for t, c in zip(arrays['edge_tag'], arrays['edge_chunk'])]
    full_edges += [(r['chunkId'], r['tag']) for r in graph['excluded_product_edges']]
    full_edges.sort()
    if len(full_edges) != len(set(full_edges)) or len(full_edges) != 61018:
        raise ValueError('Full edge set failed reconstruction')
    edge_tag = np.array([tag_at[t] for c, t in full_edges], dtype=np.int32)
    edge_chunk = np.array([chunk_at[c] for c, t in full_edges], dtype=np.int32)
    edge_w, overlay_meta = arm.read_facet_file(prepared_names, chunk_ids, edge_tag, edge_chunk,
                                              tag_raw, chunk_raw)
    full_at = {cid + '::' + tag: i for i, (cid, tag) in enumerate(full_edges)}
    indexes = [full_at[e] for e in graph['edge_ids']]
    if not np.array_equal(edge_w[indexes], arrays['edge_facets']):
        raise ValueError('Reconstructed semantic edge values differ from the frozen snapshot')
    session = FrozenShapeSession(arm, graph)
    shape = arm.load_shape(session, chunk_ids, chunk_at, edge_tag, edge_chunk, prepared_names)
    adjacency = arm.file_adjacency(graph['chunks'])
    prepared = arm.Prepared(driver=None, tag_names=prepared_names,
        tag_vecs=arm._unit(tag_raw.astype(np.float64)), chunk_ids=chunk_ids,
        chunk_vecs=arm._unit(chunk_raw.astype(np.float64)), chunk_rows=graph['chunks'],
        edge_tag=edge_tag, edge_chunk=edge_chunk, edge_w=edge_w, overlay=overlay_meta,
        facets=tuple(graph['facets']), shape=shape, adjacency=adjacency)
    frozen_vectors = {}
    def add_vector(text, v):
        if text in frozen_vectors and not np.allclose(frozen_vectors[text], v, atol=1e-14, rtol=0):
            raise ValueError('Same frozen text has conflicting vectors')
        frozen_vectors[text] = v
    for i, tag in enumerate(graph['query_tags']):
        add_vector(arm._readable(tag), arrays['query_tag_vectors'][i])
    for q in graph['queries']:
        add_vector(q['description'], arrays['description_vectors'][q['description_index']])
        add_vector(q['question'], arrays['question_vectors'][q['question_index']])
    embed_calls = []
    def captured_embed(texts, input_type):
        if input_type != 'query' or any(text not in frozen_vectors for text in texts):
            raise RuntimeError('Uncaptured embedding requested; no model fallback permitted')
        embed_calls.append({'texts': texts, 'input_type': input_type, 'source': 'frozen snapshot'})
        return np.array([frozen_vectors[text] for text in texts]).tolist(), 0, 0, 0, 0.0
    arm._embed_cached = captured_embed
    knobs = ('SORT_MODE', 'FACET_SOURCE', 'LINK2', 'TAGSIDE', 'FACETADJ', 'REGION', 'TAGREL',
             'LOCALITY', 'BAND_RULE', 'RAW_PART', 'SCOPE_RULE', 'SCOPE_FIELDS', 'SCOPE_JOIN',
             'DIST_RULE', 'WEIGHT_GRAIN', 'DIST_RANGE', 'LEVEL_RULE', 'COS_NOISE')
    flags = {k: getattr(arm, k) for k in knobs}
    required = {'LINK2': 'and', 'TAGSIDE': 'all', 'FACETADJ': 'off', 'REGION': 'shape',
                'TAGREL': 'shape', 'LOCALITY': 'on', 'RAW_PART': 'off'}
    if any(flags[k] != v for k, v in required.items()):
        raise ValueError('Concept defaults do not match the inspected contract')
    sources = [Path(__file__), graph_path, array_path, vectors_path, capture_path, overlay_path,
               ROOT / 'test/arms/artefact_v3.py', ROOT / 'test/arms/artefact_v2.py']
    protocol = {'protocol': __doc__, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
        'flags': flags, 'initial_environment_overrides_removed': initial,
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sources},
        'prepared': {'tags': len(prepared_names), 'chunks': len(chunk_ids), 'edges': len(full_edges),
                     'restored_product_edges': len(graph['excluded_product_edges']),
                     'product_name_tags': int(shape['product_tag'].sum()),
                     'semantic_edge_values_equal_snapshot': True},
        'shape': {k: shape[k] for k in ('channels', 'chunk_channel_edges', 'chunks_with_channel', 'products')},
        'adjacency': {k: adjacency[k] for k in ('pairs', 'located', 'sequences', 'per_kind')},
        'adapter': 'Split description + every captured query tag; per-tag facets supplied unchanged in facets and weights. Existing facet_order fallback derives order. No gate or product name invented.',
        'boundary': {'k': len(chunk_ids), 'keep_all': True, 'char_budget': None,
                     'no_delivery': True, 'embedding': 'Exact frozen query vectors only',
                     'db': 'Frozen shape session handles only the two prepare-time shape queries'},
        'edge_order': 'Canonical (chunk_id, tag). Source Cypher has no ORDER BY; route ties within one chunk may have different equal-key provenance, while the complete key includes chunk_id.',
        'limits': ['Current static file overlay is an explicit intervention relative to default FACET_SOURCE=edge.',
                   'This diagnoses the existing combined assembly with the experimental split-input adapter, not a proposed new operator.',
                   'No independent facet stream exists in this assembly.',
                   'Full pre-delivery ranking only; no raw source documents or budget resolver.']}
    write(OUT / 'protocol.json', protocol)
    focal_indices = {chunk_at[c] for c in FOCAL.values()}
    original_grow = arm.grow_region
    summaries = []
    with threadpool_limits(limits=4):
        for capture in captures['captures']:
            for reading in capture['readings']:
                if not reading['ok']:
                    summaries.append({'run_id': reading['id'], 'status': 'missing_reading'})
                    continue
                values = {v['t']: v['facets'] for v in reading['values']}
                plan = {'description': capture['description'], 'parts': [
                    {'t': tag, 'facets': values[tag], 'weights': values[tag]} for tag in capture['clean_tags']]}
                run_id = reading['id'] + '_concept_file'
                focal_calls, growth_calls = [], []
                def profile(frame, event, arg):
                    if event != 'return' or frame.f_code.co_name != 'key_of':
                        return
                    local = frame.f_locals
                    if local.get('c') not in focal_indices or 'fpos' not in local:
                        return
                    parent = frame.f_back.f_locals
                    pi, j, c = int(local['pi']), int(local['j']), int(local['c'])
                    focal_calls.append({'call_order': len(focal_calls), 'part': pi,
                        'query_tag': plan['parts'][pi]['t'], 'graph_tag': prepared_names[edge_tag[j]],
                        'edge_id': full_edges[j][0] + '::' + full_edges[j][1], 'edge_index': j,
                        'chunk_id': chunk_ids[c], 'level': int(parent['L']),
                        'scope_pass': int(parent['walk_pass']), 'from_shape': bool(local['from_shape']),
                        'key': list(arg), 'positions_after_shape_adjustment': local['fpos'].tolist(),
                        'static_graph_facets': dict(zip(graph['facets'], edge_w[j].tolist())),
                        'query_facets': values[plan['parts'][pi]['t']]})
                def traced_grow(*args, **kwargs):
                    result = original_grow(*args, **kwargs)
                    caller = sys._getframe(1).f_locals
                    seeds, levels = args[1], args[2]
                    growth_calls.append({'part': int(caller['pi']), 'scope_pass': int(caller['walk_pass']),
                        'seed_chunk_ids': [chunk_ids[i] for i in seeds], 'seed_levels': levels.tolist(),
                        'focal_raw_growth': {label: {'level': int(result[0][chunk_at[cid]]),
                            'by_group': bool(result[1][chunk_at[cid]]), 'by_cooc': bool(result[2][chunk_at[cid]])}
                            for label, cid in FOCAL.items()}})
                    return result
                arm.grow_region = traced_grow
                print('Running ' + run_id, flush=True)
                t0 = time.perf_counter()
                sys.setprofile(profile)
                try:
                    selected, usage, meta = arm._retrieve_concept(session, prepared, plan,
                        k=len(chunk_ids), question=capture['question'], keep_all=True, char_budget=None, doc_cache={})
                finally:
                    sys.setprofile(None)
                    arm.grow_region = original_grow
                elapsed = time.perf_counter() - t0
                ordered = [r['chunkId'] for r in selected]
                if len(ordered) != len(chunk_ids) or set(ordered) != set(chunk_ids):
                    raise ValueError('Concept did not return the complete eligible chunk order')
                if usage.calls != 0:
                    raise ValueError('Offline replay reported an actual embedding/model call')
                focal = {}
                for label, cid in FOCAL.items():
                    row = selected[ordered.index(cid)]
                    candidates = [r for r in focal_calls if r['chunk_id'] == cid and r['level'] == row['fit']
                                  and r['graph_tag'] == row['tag'] and r['from_shape'] == row['grown']]
                    if not candidates:
                        raise ValueError('No captured provenance for selected focal row')
                    chosen = min(candidates, key=lambda r: (r['scope_pass'], r['level'], tuple(r['key']), r['call_order']))
                    focal[label] = {'chunk_id': cid, 'rank': ordered.index(cid) + 1, 'selected_row': row,
                                    'selected_route': chosen,
                                    'observed_candidate_routes': [r for r in focal_calls if r['chunk_id'] == cid]}
                result = {'run_id': run_id, 'seconds': elapsed, 'flags': flags,
                          'generation_id': capture['generation_id'], 'reading_id': reading['id'],
                          'question': capture['question'], 'plan': plan, 'focal': focal,
                          'chunk_order': ordered, 'source_metadata': meta, 'shape_seed_trace': growth_calls,
                          'embedding_boundary': embed_calls[-1], 'delivery': {'performed': False},
                          'trace_limit': 'All focal key calls encountered before full chunk coverage; no later redundant route is claimed inspected.'}
                write(OUT / (run_id + '.json'), result)
                summary = {'run_id': run_id, 'seconds': elapsed, 'focal_ranks': {k: v['rank'] for k, v in focal.items()},
                    'focal_query_tags': {k: v['selected_route']['query_tag'] for k, v in focal.items()},
                    'focal_graph_tags': {k: v['selected_route']['graph_tag'] for k, v in focal.items()},
                    'focal_levels': {k: v['selected_row']['fit'] for k, v in focal.items()},
                    'focal_locality': {k: meta['facet_layer']['locality']['rows'][v['rank'] - 1] for k, v in focal.items()},
                    'full_order_count': len(ordered), 'chunks_grown': meta['sort']['rows_from_shape'],
                    'concentration': meta['facet_layer']['concentration'],
                    'source_sha256': sha(OUT / (run_id + '.json'))}
                summaries.append(summary)
                print(json.dumps(summary['focal_ranks']) + f' ({elapsed:.2f}s)', flush=True)
    write(OUT / 'summary.json', {'protocol_sha256': sha(OUT / 'protocol.json'), 'runs': summaries,
        'completed_utc': datetime.now(timezone.utc).isoformat(), 'model_calls': 0, 'db_calls': 0,
        'raw_source_reads': 0, 'delivery_claim': False,
        'frozen_shape_calls': session.calls,
        'limits': protocol['limits']})
    print('All offline concept rankings complete', flush=True)


if __name__ == '__main__':
    main()
