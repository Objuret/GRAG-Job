"""Post-hoc causal diagnostic of two passage-description endpoints, not a new method."""
import ast
from collections import defaultdict
import os
from pathlib import Path
import sys

for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '4'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import numpy as np
from facet_source_first_snapshot import read, write, sha, unit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'test'))
from artefact.facet_joint_candidate import FACETS, freeze_reference
from artefact.facet_stream_envelope import rank_facet_stream_envelope

STATIC = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
OUT = BASE / 'description_intervention'
QUESTION = 'independent_durable_messages_current_models'
IDS = ['1c982e912346f77d7e155393', '3b4c077ffb1c30ea0b293fb1']


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError('Existing diagnostic output; inspect instead of overwriting')
    graph = read(STATIC / 'graph.json')
    static = dict(np.load(STATIC / 'arrays.npz'))
    vectors = dict(np.load(STATIC / 'graph_vectors.npz'))
    queries = read(BASE / 'query_snapshot/queries.json')
    arrays = dict(np.load(BASE / 'query_snapshot/arrays.npz'))
    capture = next(c for c in read(BASE / 'query_capture/query_captures.json')['captures']
                   if c['question_id'] == QUESTION)
    query = next(q for q in queries['queries'] if q['question_id'] == QUESTION)
    assert queries['chunk_ids'] == graph['chunk_ids']
    assert query['tags'] == capture['clean_tags']
    assert len(capture['readings']) == 2 and all(r['ok'] for r in capture['readings'])
    at = [graph['chunk_ids'].index(cid) for cid in IDS]
    chunks = [graph['chunks'][i] for i in at]
    texts = [c['original_description'] for c in chunks] + [c['source_text'] for c in chunks]
    source_paths = [Path(__file__), ROOT / 'prod/harness/embed.py',
        ROOT / 'tools/facet_source_first_snapshot.py', ROOT / 'test/arms/artefact_v3.py',
        ROOT / 'test/artefact/facet_joint_candidate.py', ROOT / 'test/artefact/facet_stream_envelope.py',
        STATIC / 'graph.json', STATIC / 'arrays.npz', STATIC / 'graph_vectors.npz',
        BASE / 'query_snapshot/queries.json', BASE / 'query_snapshot/arrays.npz',
        BASE / 'query_snapshot/manifest.json', BASE / 'query_capture/query_captures.json']
    for r in capture['readings']:
        source_paths.append(BASE / 'facet_stream_envelope' / (r['id'] + '_intact.json'))
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    from harness import embed
    old_embedding = read(BASE / 'query_snapshot/manifest.json')['embedding']
    assert embed.EMBED_MODEL == old_embedding['model']
    assert embed.EMBED_REVISION == old_embedding['revision']
    assert embed.EMBED_PREFIX == old_embedding['prefixes']
    protocol = {
        'status': 'frozen_before_new_embedding_or_intervention_outcomes',
        'question_id': QUESTION, 'chunk_ids': IDS, 'input_sha256': hashes,
        'selection': 'Post-hoc diagnostic of the two previously identified complementary passages; not held-out evaluation.',
        'replacement': 'Exact original source_text for BOTH chunks, no query-tailored summary, edits, truncation or selected snippets.',
        'conditions': {
            'fulltext_D_only': 'Replace only query-tag-to-description cosines at these two chunk endpoints.',
            'fulltext_D_and_Q': 'Also replace whole-query-description-to-chunk-description cosines at the same endpoints.'},
        'fixed': 'All query fields, query facet readings, graph tags, graph edge facet values including topic, reference CDF, coefficients, graph membership/adjacency, candidate population, and scoring operators.',
        'limits': 'Endpoint intervention only. Does not rebuild a self-consistent corpus index or claim a production fix. Fulltext changes length and many details; it cannot isolate one omitted phrase. Source-pair ranks are not global relevance or delivery.',
        'measurements': 'Original-description reproduction; D/Q changes; facet sponsors; per-query-tag route values; ranks of both sources; graph witnesses. No parameter selection.',
        'encoder': {'model': embed.EMBED_MODEL, 'revision': embed.EMBED_REVISION,
                    'input_type': 'passage', 'device': embed.EMBED_DEVICE, 'dtype': embed.EMBED_DTYPE},
        'embedding_texts': [{'role': 'original_description_control' if i < 2 else 'source_text_replacement',
                             'chunk_id': IDS[i % 2], 'text': t} for i, t in enumerate(texts)],
        'control_tolerance': 1e-5, 'model_loads': 1, 'generation_calls': 0, 'db_calls': 0}
    OUT.mkdir(parents=True)
    write(OUT / 'protocol.json', protocol)
    import torch
    torch.set_num_threads(4)
    assert embed._model is None
    encoded, calls, tokens_in, _, seconds = embed._embed(texts, 'passage', bar=False)
    encoded = unit(encoded)
    original = unit(vectors['chunk_raw_float32'][at])
    delta = float(np.max(np.abs(encoded[:2] - original)))
    np.savez_compressed(OUT / 'vectors.npz', encoded=encoded)
    control = {'maximum_original_vector_difference': delta, 'passed': delta <= 1e-5,
               'embedding_calls': calls, 'tokens_in': tokens_in, 'seconds': seconds}
    write(OUT / 'embedding_verification.json', control)
    if not control['passed']:
        raise ValueError('Original description embedding did not reproduce; do not interpret replacement')
    indices = query['query_tag_indices']
    new_d = arrays['query_tag_vectors'][indices] @ encoded[2:].T
    new_q = arrays['description_vectors'][query['description_index']] @ encoded[2:].T
    assert np.max(np.abs(arrays['query_tag_vectors'][indices] @ encoded[:2].T -
                         arrays['query_tag_chunk_cos'][indices][:, at])) <= 1e-5
    relations = defaultdict(list)
    for ci, chunk in enumerate(graph['chunks']):
        for p in chunk['scope'].get('product', []):
            for ch in chunk['scope'].get('channel', []):
                relations[(p['node_id'], ch['node_id'])].append(ci)
    tree = ast.parse((ROOT / 'test/arms/artefact_v3.py').read_text(encoding='utf-8'))
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'_csr', 'file_adjacency'}]
    assert len(funcs) == 2
    import json
    ns = {'np': np, 'json': json}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), 'frozen_adjacency', 'exec'), ns)
    adj = ns['file_adjacency'](graph['chunks'])
    pairs = [(i, int(j)) for i in range(len(graph['chunks']))
             for j in adj['members'][adj['ptr'][i]:adj['ptr'][i+1]] if i < j]
    reference = freeze_reference(static['edge_facets'])
    records = []
    for reading in capture['readings']:
        by_tag = {v['t']: v['facets'] for v in reading['values']}
        weights = np.array([[by_tag[t][f] for f in FACETS] for t in query['tags']])
        baseline = read(BASE / 'facet_stream_envelope' / (reading['id'] + '_intact.json'))
        for condition in protocol['conditions']:
            d = arrays['query_tag_chunk_cos'][indices].copy()
            q = arrays['description_chunk_cos'][query['description_index']].copy()
            d[:, at] = new_d
            if condition == 'fulltext_D_and_Q':
                q[at] = new_q
            result = rank_facet_stream_envelope(
                chunk_ids=graph['chunk_ids'], query_tag_ids=query['tags'], edge_ids=graph['edge_ids'],
                edge_tag_indices=static['edge_tag'], edge_chunk_indices=static['edge_chunk'],
                edge_facets=static['edge_facets'], query_facet_weights=weights,
                query_tag_cosines=arrays['query_tag_graph_cos'][indices], query_chunk_cosines=d,
                query_description_cosines=q, reference=reference,
                groups={'shared_product_channel': list(relations.values())}, adjacency_pairs=pairs)
            assert len(result['rows']) == 4808
            assert max(abs(r['score'] - sum(w['contribution'] for w in r['provenance'].values() if w))
                       for r in result['rows']) < 1e-12
            focal = {r['chunk_id']: r for r in result['rows'] if r['chunk_id'] in IDS}
            record = {'reading_id': reading['id'], 'condition': condition, 'focal': focal,
                      'baseline_focal': baseline['focal'],
                      'query_tags': query['tags'], 'chunk_ids': IDS,
                      'old_D': arrays['query_tag_chunk_cos'][indices][:, at].tolist(), 'new_D': new_d.tolist(),
                      'old_Q': arrays['description_chunk_cos'][query['description_index']][at].tolist(),
                      'used_Q': q[at].tolist(), 'fulltext_Q': new_q.tolist(),
                      'focal_direct_per_facet_query_chunk': result['direct_scores'][:, :, at].tolist(),
                      'focal_graph_per_facet_query_chunk': result['graph_scores'][:, :, at].tolist()}
            name = reading['id'] + '_' + condition + '.json'
            write(OUT / name, {**record,
                'rows': [{k:r[k] for k in ('rank', 'chunk_id', 'score')} for r in result['rows']],
                'graph_witnesses': [r for r in result['rows'] if any(w and w['route_type'] != 'direct'
                                      for w in r['provenance'].values())]})
            records.append({**record, 'file': name, 'sha256': sha(OUT / name)})
            print(reading['id'], condition, [(c, r['rank']) for c,r in focal.items()], flush=True)
    assert all(sha(ROOT / p) == h for p,h in hashes.items())
    write(OUT / 'summary.json', records)
    write(OUT / 'verification.json', {'inputs_unchanged': True, 'conditions': len(records),
          'description_control_passed': True, 'summary_sha256': sha(OUT / 'summary.json')})


if __name__ == '__main__':
    main()
