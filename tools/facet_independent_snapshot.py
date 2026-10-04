"""Embed frozen independent-source query fields against the original frozen graph.

Only new query tags, generated descriptions and raw questions reach the pinned
offline serving embedder. No DB connection, raw corpus, passage embedding, tagger,
ranking or candidate truncation is used. SCORE readings are not embedding inputs.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '4'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
SNAPSHOT = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
sys.path.insert(0, str(ROOT / 'prod'))


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def array_sha(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n',
                    encoding='utf-8')


def source_helper(path, name):
    """Execute only a standalone numerical/text helper, never module imports."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node, = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    namespace = {'np': np}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


def unit(value):
    value = np.asarray(value, dtype=np.float64)
    norm = np.linalg.norm(value, axis=1, keepdims=True)
    if not np.isfinite(value).all() or (norm == 0).any():
        raise ValueError('Nonfinite or zero embedding')
    return value / norm


def generation_fields(captures):
    """Validated embedding fields; no fixed query-count assumption."""
    rows = []
    for capture in captures['captures']:
        if not capture['generation_validation']['ok']:
            raise ValueError('Every GENERATE must validate before embedding')
        tags = capture['clean_tags']
        texts = [capture['description'], capture['question'], *tags]
        if (not tags or len(tags) != len(set(tags)) or
                any(not isinstance(t, str) or not t.strip() for t in texts)):
            raise ValueError('Empty/invalid generation fields or duplicate tags')
        rows.append({k: capture[k] for k in ('generation_id', 'question_id', 'question',
                     'description', 'clean_tags', 'generation_validation', 'source_sha256')})
    if not rows or len({r['generation_id'] for r in rows}) != len(rows):
        raise ValueError('Distinct nonempty validated generations required')
    return rows


def build_arrays(query_vectors, description_vectors, question_vectors, semantic, chunks, prepared):
    q_graph = query_vectors @ semantic.T
    return {
        'query_tag_vectors': query_vectors,
        'description_vectors': description_vectors,
        'question_vectors': question_vectors,
        'query_tag_graph_cos': q_graph,
        'query_tag_graph_cos_forum_precision': q_graph.copy(),
        'query_tag_chunk_cos': query_vectors @ chunks.T,
        'description_graph_cos': description_vectors @ semantic.T,
        'question_graph_cos': question_vectors @ semantic.T,
        'description_chunk_cos': description_vectors @ chunks.T,
        'question_chunk_cos': question_vectors @ chunks.T,
        'centrality': description_vectors @ query_vectors.T,
        'band_description_graph_cos': description_vectors @ prepared.T,
        'band_question_graph_cos': question_vectors @ prepared.T,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, default=BASE / 'query_capture/query_captures.json')
    parser.add_argument('--questions', type=Path, default=BASE / 'questions.json')
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT)
    parser.add_argument('--out', type=Path, default=BASE / 'query_snapshot')
    parser.add_argument('--validate-only', action='store_true', help='Verify inputs and math without a model load')
    args = parser.parse_args()
    if not args.capture.is_file():
        raise FileNotFoundError('Create query_captures.json before invoking this sidecar')
    if (args.out / 'manifest.json').exists():
        raise RuntimeError('Completed sidecar exists; do not silently re-embed')
    captures = read(args.capture)
    generations = generation_fields(captures)
    declared = read(args.questions)
    declared_by_id = {row['id']: row['question'] for row in declared}
    if not declared or len(declared_by_id) != len(declared):
        raise ValueError('Declared raw questions must have unique nonempty IDs')
    generated_by_id = {row['question_id']: row['question'] for row in generations}
    if len(generated_by_id) != len(generations) or generated_by_id != declared_by_id:
        raise ValueError('Require exactly one validated generation per declared raw question')
    if any(not capture.get('readings') or
           any(not reading.get('ok') for reading in capture['readings'])
           for capture in captures['captures']):
        raise ValueError('Completed valid SCORE readings required before embedding')
    capture_sha = sha(args.capture)
    generation_sha = json_sha(generations)
    for row in generations:
        for name, expected in row['source_sha256'].items():
            if sha(ROOT / name) != expected:
                raise ValueError('Captured GENERATE provenance changed: ' + name)
    manifest_path = args.snapshot / 'manifest.json'
    original = read(manifest_path)
    inputs = [args.snapshot / name for name in ('graph.json', 'arrays.npz', 'graph_vectors.npz')]
    for path in inputs:
        if sha(path) != original['output_sha256'][path.name]:
            raise ValueError('Frozen snapshot hash mismatch: ' + str(path))
    source_paths = [ROOT / 'prod/harness/embed.py', ROOT / 'test/arms/artefact_v2.py',
                    ROOT / 'test/arms/artefact_v3.py']
    for path in source_paths:
        if sha(path) != original['source_sha256'][str(path)]:
            raise ValueError('Serving source differs from original snapshot: ' + str(path))
    readable = source_helper(source_paths[1], '_readable')
    source_unit = source_helper(source_paths[1], '_unit')
    paraphrase_band = source_helper(source_paths[2], 'paraphrase_band')
    graph = read(inputs[0])
    original_arrays = np.load(inputs[1], allow_pickle=False)
    vectors = np.load(inputs[2], allow_pickle=False)
    all_names = graph['all_graph_vector_tag_names']
    all_at = {name: i for i, name in enumerate(all_names)}
    if len(all_at) != len(all_names):
        raise ValueError('Duplicate graph vector names')
    all_vectors = unit(vectors['tag_raw_float32'])
    semantic = all_vectors[[all_at[name] for name in graph['graph_tags']]]
    prepared = all_vectors[[all_at[name] for name in graph['band_graph_tag_names']]]
    chunks = unit(vectors['chunk_raw_float32'])
    if (len(semantic), len(prepared), len(chunks)) != (16669, 16654, 4808):
        raise ValueError('Original reference populations differ')
    if not np.array_equal(all_vectors, source_unit(vectors['tag_raw_float32'].astype(np.float64))):
        raise ValueError('Normalization differs from original source helper')
    noise = graph['operator_defaults']['r_band']
    source_ast = ast.parse(source_paths[2].read_text(encoding='utf-8'))
    source_noise, = [ast.literal_eval(n.value) for n in source_ast.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'COS_NOISE' for t in n.targets)]
    if noise != source_noise:
        raise ValueError('Frozen noise differs from source COS_NOISE')
    with threadpool_limits(limits=4):
        reconstructed = build_arrays(original_arrays['query_tag_vectors'], original_arrays['description_vectors'],
                                     original_arrays['question_vectors'], semantic, chunks, prepared)
        deltas = {}
        for name, matrix in reconstructed.items():
            if name == 'query_tag_graph_cos':
                continue  # Original raw float64 matching vectors are not in graph_vectors.npz.
            deltas[name] = float(np.max(np.abs(matrix - original_arrays[name])))
            if deltas[name] > 1e-12:
                raise ValueError('Original matrix failed numerical reconstruction: ' + name)
        for query in graph['queries']:
            di, qi = query['description_index'], query['question_index']
            tb = max(float(np.median(np.abs(reconstructed['band_description_graph_cos'][di] -
                                           reconstructed['band_question_graph_cos'][qi]))), noise)
            db = max(paraphrase_band(chunks, reconstructed['description_vectors'][di],
                                     reconstructed['question_vectors'][qi]), noise)
            if abs(tb - query['tag_band']) > 1e-12 or abs(db - query['desc_band']) > 1e-12:
                raise ValueError('Original band failed numerical reconstruction')
    tags = sorted({tag for row in generations for tag in row['clean_tags']})
    tag_at = {tag: i for i, tag in enumerate(tags)}
    questions = list(dict.fromkeys(row['question'] for row in generations))
    descriptions = [row['description'] for row in generations]
    embedding_texts = [readable(tag) for tag in tags] + descriptions + questions
    # Exact duplicate text has one embedding in the serving query role.
    unique_texts = list(dict.fromkeys(embedding_texts))
    from harness import embed
    if (embed.EMBED_MODEL != original['embedding']['model'] or
            embed.EMBED_REVISION != original['embedding']['revision'] or
            embed.EMBED_PREFIX != original['embedding']['prefixes']):
        raise ValueError('Pinned serving model/revision/prefix changed')
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in
                     [Path(__file__), ROOT / 'tools/facet_source_first_snapshot.py', args.questions,
                      args.capture, manifest_path, *inputs, *source_paths]}
    protocol = {
        'schema_version': 1, 'protocol': __doc__, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
        'generation_fields_sha256': generation_sha, 'generation_fields': generations,
        'capture_path': str(args.capture.relative_to(ROOT)),
        'capture_hash_policy': 'Full completed capture is hashed; only validated GENERATE fields enter embedding inputs.',
        'completed_capture_sha256': capture_sha,
        'declared_questions_sha256': sha(args.questions),
        'source_sha256': source_hashes, 'original_reconstruction_max_abs_delta': deltas,
        'old_bands_reconstructed': True,
        'reference_populations': {'semantic_tags': len(semantic), 'prepared_tags': len(prepared), 'chunks': len(chunks)},
        'embedding': {'model': embed.EMBED_MODEL, 'revision': embed.EMBED_REVISION,
                      'prefixes': embed.EMBED_PREFIX, 'input_type': 'query',
                      'device': embed.EMBED_DEVICE, 'dtype': embed.EMBED_DTYPE,
                      'batch_size': embed.EMBED_BATCH, 'cpu_threads': 4,
                      'offline': {'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'},
                      'inputs': unique_texts, 'tag_inputs': [readable(t) for t in tags],
                      'description_inputs': descriptions, 'question_inputs': questions,
                      'text_deduplication': 'Exact text across all query roles; every role retains its index'},
        'precision': 'Frozen graph float32 vectors normalized in float64, matching serving preparation. Both query_tag_graph_cos variants use this path. Historical raw-float64 matching vectors were not recaptured.',
        'band_rule': 'max(median(abs(cos(reference,description)-cos(reference,raw_question))),COS_NOISE); all16654 prepared tags for tag_band, all4808 chunks for desc_band',
        'cos_noise': noise, 'new_passage_embeddings': 0, 'database_calls': 0,
    }
    if args.validate_only:
        print(json.dumps({'validated': True, 'unique_embedding_inputs': len(unique_texts),
                          'query_tags': len(tags), 'reconstruction_max_abs_delta': max(deltas.values()),
                          'generation_fields_sha256': generation_sha}), flush=True)
        return
    args.out.mkdir(parents=True, exist_ok=True)
    protocol_path = args.out / 'protocol.json'
    if protocol_path.exists():
        raise RuntimeError('Embedding protocol already frozen; inspect interrupted attempt before restarting')
    write(protocol_path, protocol)
    import torch
    torch.set_num_threads(4)
    if embed._model is not None:
        raise RuntimeError('Fresh process required to establish one model load')
    print(f'Embedding {len(unique_texts)} new query texts; one offline pinned model load', flush=True)
    embedded, calls, tokens_in, tokens_out, seconds = embed._embed(unique_texts, 'query', bar=False)
    embedded = unit(embedded)
    index = {text: i for i, text in enumerate(unique_texts)}
    qv = embedded[[index[readable(t)] for t in tags]]
    dv = embedded[[index[t] for t in descriptions]]
    rv = embedded[[index[t] for t in questions]]
    with threadpool_limits(limits=4):
        arrays = build_arrays(qv, dv, rv, semantic, chunks, prepared)
        queries = []
        for di, row in enumerate(generations):
            qi = questions.index(row['question'])
            tb = max(float(np.median(np.abs(arrays['band_description_graph_cos'][di] -
                                           arrays['band_question_graph_cos'][qi]))), noise)
            db = max(paraphrase_band(chunks, dv[di], rv[qi]), noise)
            queries.append({'id': row['generation_id'], 'generation_id': row['generation_id'],
                            'question_id': row['question_id'], 'question': row['question'],
                            'description': row['description'], 'tags': row['clean_tags'],
                            'query_tag_indices': [tag_at[t] for t in row['clean_tags']],
                            'description_index': di, 'question_index': qi,
                            'tag_band': tb, 'desc_band': db, 'source_sha256': row['source_sha256'],
                            'scope_policy': 'No inferred scope; graph memberships remain frozen.'})
    if json_sha(generation_fields(read(args.capture))) != generation_sha:
        raise ValueError('GENERATE fields changed during embedding')
    if any(sha(ROOT / name) != expected for name, expected in source_hashes.items()):
        raise ValueError('Frozen source changed during embedding')
    queries_doc = {'schema_version': 1, 'query_tags': tags, 'questions': questions, 'queries': queries,
                   'generation_fields_sha256': generation_sha,
                   'graph_tags': graph['graph_tags'], 'band_graph_tag_names': graph['band_graph_tag_names'],
                   'chunk_ids': graph['chunk_ids']}
    write(args.out / 'queries.json', queries_doc)
    np.savez_compressed(args.out / 'arrays.npz', **arrays)
    completed = {**protocol, 'completed_utc': datetime.now(timezone.utc).isoformat(),
                 'embedding': {**protocol['embedding'], 'loads': 1, 'calls': calls,
                               'tokens_in': tokens_in, 'tokens_out': tokens_out, 'seconds': seconds},
                 'counts': {'queries': len(queries), 'questions': len(questions), 'query_tags': len(tags),
                            'unique_embedding_inputs': len(unique_texts)},
                 'arrays': {k: {'shape': list(v.shape), 'dtype': str(v.dtype), 'sha256': array_sha(v)}
                            for k, v in arrays.items()},
                 'output_sha256': {n: sha(args.out / n) for n in ('queries.json', 'arrays.npz', 'protocol.json')}}
    write(args.out / 'manifest.json', completed)
    print(json.dumps(completed['counts']), flush=True)


if __name__ == '__main__':
    main()
