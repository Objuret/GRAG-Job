"""One frozen consistent query repair; independent score/embed stages then replay."""
import argparse
import ast
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
import os
from pathlib import Path
import sys

for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '4'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from facet_query_reconstruction_replay import read, write, sha
import facet_route_capture as R

BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
PARENT = BASE / 'query_interpretation_intervention'
OUT = PARENT / 'repair'
STATIC = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
QID = 'independent_sensor_pivot_reason'
TAGS = ['sensor protocol support', 'strategy reconsideration', 'business rationale']
DESCRIPTION = 'An explanation of the reasons that prompted EdgeForce to reconsider its already-merged support for new sensor protocols.'
BETA = np.array([1., .25, .25, .25, .25])


def prepare():
    if OUT.exists():
        raise RuntimeError('Inspect existing repair before preparing')
    query, = [q for q in read(BASE / 'query_snapshot/queries.json')['queries'] if q['question_id'] == QID]
    parsed = R.S.parse_generate({'description': DESCRIPTION, 'tags': TAGS})
    system, user = R.S.score_prompt(parsed['description'], parsed['tags'])
    old_model = read(BASE / 'query_capture/query_captures.json')['model']
    assert R.S.MODEL == old_model
    jobs = [{'id': f'repaired_sensor_score_{i}', 'repeat': i, 'system': system,
             'user': user, 'tags': TAGS} for i in (0, 1)]
    dependencies = [Path(__file__), PARENT / 'REPAIR_PROTOCOL.md',
        ROOT / 'tools/facet_route_capture.py', ROOT / 'tools/facet_query_reconstruction_replay.py',
        ROOT / 'test/artefact/querytagger.py', ROOT / 'test/artefact/querytagger_split_check.py',
        ROOT / 'prod/harness/chat.py', ROOT / 'prod/harness/embed.py',
        ROOT / 'test/artefact/facet_joint_candidate.py', ROOT / 'test/artefact/facet_stream_envelope.py',
        ROOT / 'test/artefact/facet_scope_recruitment.py', ROOT / 'test/artefact/facet_recruitment_candidate.py',
        ROOT / 'test/artefact/facet_need_frontier.py', ROOT / 'test/arms/artefact_v3.py',
        STATIC / 'graph.json', STATIC / 'arrays.npz', STATIC / 'graph_vectors.npz',
        BASE / 'query_snapshot/queries.json', BASE / 'query_snapshot/arrays.npz',
        BASE / 'query_snapshot/manifest.json', BASE / 'query_capture/query_captures.json',
        BASE / 'scope_recruitment/run/summary.json', BASE / 'scope_recruitment/run/manifest.json']
    OUT.mkdir()
    write(OUT / 'protocol.json', {'question_id': QID, 'question': query['question'],
        'old_query': query, 'description': DESCRIPTION, 'tags': TAGS, 'model': old_model,
        'jobs': jobs, 'embedding_texts': [query['description'], DESCRIPTION],
        'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in dependencies},
        'attempt_limit': 2, 'numerical_embedding_tolerance': 1e-5,
        'status': 'Manual source-wording-free correction, not an automatic GENERATE output'})


def verify_inputs(protocol):
    assert all(sha(ROOT / p) == h for p, h in protocol['input_sha256'].items())


def score(protocol):
    out = OUT / 'score'
    out.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(R.run_one, job, out, protocol['model']) for job in protocol['jobs']]
        results = [f.result() for f in futures]
    write(OUT / 'readings.json', results)
    print(json.dumps([{'id': r['id'], 'ok': r['ok'], 'error': r['error'],
                      'cost_usd_reported': r['cost_usd_reported']} for r in results]), flush=True)
    assert all(r['ok'] for r in results), 'Retain failed outcomes; no automatic retries'


def embed(protocol):
    if (OUT / 'embedding_started.json').exists():
        raise RuntimeError('Embedding attempt exists; inspect its process and files')
    from harness import embed as E
    import torch
    old = read(BASE / 'query_snapshot/manifest.json')['embedding']
    assert E.EMBED_MODEL == old['model'] and E.EMBED_REVISION == old['revision']
    assert E.EMBED_PREFIX == old['prefixes']
    write(OUT / 'embedding_started.json', {'pid': os.getpid(), 'input_type': 'query',
          'texts': protocol['embedding_texts'], 'model': E.EMBED_MODEL, 'revision': E.EMBED_REVISION})
    torch.set_num_threads(4)
    raw, calls, tokens, _, seconds = E._embed(protocol['embedding_texts'], 'query', bar=False)
    unit = np.asarray(raw, dtype=np.float64)
    unit /= np.linalg.norm(unit, axis=1, keepdims=True)
    with np.load(BASE / 'query_snapshot/arrays.npz') as a:
        previous = a['description_vectors'][protocol['old_query']['description_index']]
    delta = float(np.max(np.abs(unit[0] - previous)))
    np.savez_compressed(OUT / 'description_vectors.npz', raw=raw, unit=unit)
    write(OUT / 'embedding_verification.json', {'old_vector_max_abs_delta': delta,
          'passed': delta <= protocol['numerical_embedding_tolerance'],
          'calls': calls, 'tokens': tokens, 'seconds': seconds})
    assert delta <= protocol['numerical_embedding_tolerance']
    print('Description embeddings saved; original control difference', delta, flush=True)


def replay(protocol):
    from artefact.facet_joint_candidate import FACETS, freeze_reference
    from artefact.facet_stream_envelope import rank_facet_stream_envelope
    from artefact.facet_scope_recruitment import recruit_with_verified_area
    run = OUT / 'run'
    if run.exists():
        raise RuntimeError('Existing replay; inspect rather than overwrite')
    readings = read(OUT / 'readings.json')
    assert len(readings) == 2 and all(r['ok'] for r in readings)
    assert read(OUT / 'embedding_verification.json')['passed']
    graph = read(STATIC / 'graph.json')
    static = dict(np.load(STATIC / 'arrays.npz'))
    arrays = dict(np.load(BASE / 'query_snapshot/arrays.npz'))
    query = protocol['old_query']
    keep = [query['tags'].index(t) for t in TAGS]
    ix = [query['query_tag_indices'][i] for i in keep]
    cv = np.asarray(np.load(STATIC / 'graph_vectors.npz')['chunk_raw_float32'], dtype=np.float64)
    cv /= np.linalg.norm(cv, axis=1, keepdims=True)
    new_description = np.load(OUT / 'description_vectors.npz')['unit'][1]
    new_Q = np.maximum(new_description @ cv.T, 0)
    relations = defaultdict(list)
    for ci, chunk in enumerate(graph['chunks']):
        for p in chunk['scope'].get('product', []):
            for ch in chunk['scope'].get('channel', []):
                relations[(p['node_id'], ch['node_id'])].append(ci)
    source = ROOT / 'test/arms/artefact_v3.py'
    nodes = [n for n in ast.parse(source.read_text(encoding='utf-8')).body
             if isinstance(n, ast.FunctionDef) and n.name in {'_csr', 'file_adjacency'}]
    ns = {'np': np, 'json': json}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), ns)
    adj = ns['file_adjacency'](graph['chunks'])
    pairs = [(i, int(j)) for i in range(len(graph['chunks']))
             for j in adj['members'][adj['ptr'][i]:adj['ptr'][i+1]] if i < j]
    common = dict(chunk_ids=graph['chunk_ids'], query_tag_ids=TAGS, edge_ids=graph['edge_ids'],
        edge_tag_indices=static['edge_tag'], edge_chunk_indices=static['edge_chunk'],
        edge_facets=static['edge_facets'], query_tag_cosines=arrays['query_tag_graph_cos'][ix],
        query_chunk_cosines=arrays['query_tag_chunk_cos'][ix], reference=freeze_reference(static['edge_facets']),
        groups={'shared_product_channel': list(relations.values())}, adjacency_pairs=pairs)
    original, = [c for c in read(BASE / 'query_capture/query_captures.json')['captures'] if c['question_id'] == QID]
    exact = []
    dependencies = [OUT / 'protocol.json', OUT / 'readings.json', OUT / 'description_vectors.npz', OUT / 'embedding_verification.json']
    for old in original['readings']:
        by_tag = {v['t']: v['facets'] for v in old['values']}
        weights = np.array([[by_tag[t][f] for f in FACETS] for t in TAGS])
        result = rank_facet_stream_envelope(**common, query_facet_weights=weights,
                    query_description_cosines=arrays['description_chunk_cos'][query['description_index']])
        path = BASE / 'need_selection/replay' / (old['id'] + '_routes.npz')
        dependencies.append(path)
        saved = np.load(path)
        for key in ('direct_scores', 'graph_scores'):
            assert np.array_equal(result[key], saved[key][:, keep, :]), key
        exact.append(old['id'])
    scopes = [s for s in read(BASE / 'scope_recruitment/run/summary.json') if s['question_id'] == QID]
    scope_path = BASE / 'scope_recruitment/run' / scopes[0]['file']
    assert sha(scope_path) == scopes[0]['sha256']
    archive = json.loads(gzip.decompress(scope_path.read_bytes()))
    dependencies.append(scope_path)
    initial = {str(p.relative_to(ROOT)): sha(p) for p in dependencies}
    run.mkdir()
    outputs = []
    for reading in readings:
        by_tag = {v['t']: v['facets'] for v in reading['values']}
        weights = np.array([[by_tag[t][f] for f in FACETS] for t in TAGS])
        result = rank_facet_stream_envelope(**common, query_facet_weights=weights, query_description_cosines=new_Q)
        values = np.maximum(result['direct_scores'], result['graph_scores'])
        np.savez_compressed(run / (reading['id'] + '_routes.npz'), direct_scores=result['direct_scores'],
            graph_scores=result['graph_scores'], Q=new_Q, query_facet_weights=weights, chunk_ids=graph['chunk_ids'])
        for mode in ('max', 'equal'):
            profile = values.max(axis=1) if mode == 'max' else values.mean(axis=1)
            scores = new_Q * (profile.T @ BETA)
            recruit = recruit_with_verified_area(chunk_rows=graph['chunks'], joint_scores=scores,
                area_chunk_ids=archive['area_chunk_ids'], area_provenance=archive['area'], source_character_budget=72000)
            payload = {'reading_id': reading['id'], 'aggregation': mode, 'joint_scores': scores.tolist(),
                'facet_profiles': profile.tolist(), 'recruitment': recruit['recruitment'],
                'max_route_rows': result['rows'] if mode == 'max' else None}
            name = reading['id'] + '_' + mode + '.json.gz'
            (run / name).write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode(), mtime=0))
            outputs.append((name, payload))
        print(reading['id'], 'both complete repaired selections saved', flush=True)
    target_path = BASE / 'protocol.json'
    target, = [t for t in read(target_path)['targets'] if t['question_id'] == QID]
    pref, comp = target['preferred'], target['comparison']
    pi, ci = graph['chunk_ids'].index(pref), graph['chunk_ids'].index(comp)
    summary = []
    for name, payload in outputs:
        rows = {r['chunk_id']: r for r in payload['recruitment']['rows']}
        selected = set(payload['recruitment']['selected_chunk_ids'])
        summary.append({'reading_id': payload['reading_id'], 'aggregation': payload['aggregation'],
            'preferred_depth': rows[pref]['depth'], 'comparison_depth': rows[comp]['depth'],
            'margin': payload['joint_scores'][pi] - payload['joint_scores'][ci],
            'preferred_selected': pref in selected, 'comparison_selected': comp in selected,
            'selected_chunks': len(selected), 'file': name, 'sha256': sha(run / name)})
    write(run / 'summary.json', summary)
    assert all(sha(ROOT / p) == h for p, h in initial.items())
    initial[str(target_path.relative_to(ROOT))] = sha(target_path)
    verify_inputs(protocol)
    write(run / 'manifest.json', {'input_sha256': initial, 'output_sha256': {p.name:sha(p) for p in run.iterdir()},
          'original_subset_route_arrays_exact': exact, 'selections': 4})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'score', 'embed', 'replay'])
    args = parser.parse_args()
    if args.stage == 'prepare':
        prepare()
    else:
        protocol = read(OUT / 'protocol.json')
        verify_inputs(protocol)
        {'score': score, 'embed': embed, 'replay': replay}[args.stage](protocol)
