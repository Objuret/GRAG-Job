"""Capture complete, factorized diagnostic routes from READ-only Volmax.

The graph facet measurements remain query independent. Query embeddings use the
existing pinned embedder once; original query-tag embeddings are reused. No
candidate cap, first-arrival reduction, benchmark read, or database write occurs.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
BASE = ROOT / 'output/research/2026-09-21-facet-validity'
FACETS = ['topic', 'temporal', 'why', 'activity', 'concreteness']
ARCHIVE_REF = 'bcc3156:backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def unit(a):
    a = np.asarray(a, dtype=np.float64)
    norm = np.linalg.norm(a, axis=1, keepdims=True)
    if not np.isfinite(a).all() or (norm == 0).any():
        raise ValueError('Nonfinite or zero embedding')
    return a / norm


def write_json(path, body):
    Path(path).write_text(json.dumps(body, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=BASE / 'query_route')
    ap.add_argument('--out', type=Path, default=BASE / 'route_snapshot')
    args = ap.parse_args()
    print('Capturing complete diagnostic graph routes (READ only)', flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    if (args.out / 'manifest.json').exists():
        raise RuntimeError('Completed snapshot already exists; use it rather than recapturing silently')

    overlay_path = ROOT / 'output/facet_pairs/rounds/round1/overlay.json'
    export_path = ROOT / 'output/facet_neural/rows_export.jsonl'
    source_manifest = json.loads((args.source / 'manifest.json').read_text(encoding='utf-8'))
    matching = json.loads((args.source / 'route_matches.json').read_text(encoding='utf-8'))
    old = np.load(args.source / 'tag_matching_scores.npz')
    tags, query_tags = matching['graph_tags'], matching['query_tags']
    tag_at = {t: i for i, t in enumerate(tags)}
    qtag_at = {t: i for i, t in enumerate(query_tags)}
    query_vectors = unit(old['query_vectors'])
    saved_tag_cos = old['scores'].copy()
    queries, questions = [], []
    for job in source_manifest['jobs']:
        reading = json.loads((args.source / (job['id'] + '.json')).read_text(encoding='utf-8'))['answer']
        if job['question'] not in questions:
            questions.append(job['question'])
        queries.append({'id': job['id'], 'question': job['question'],
                        'question_index': questions.index(job['question']),
                        'description': reading['description'], 'tags': reading['tags'],
                        'query_tag_indices': [qtag_at[t] for t in reading['tags']],
                        'source_sha256': sha(args.source / (job['id'] + '.json'))})

    # Configure only this disposable process to expose the exact forum helpers.
    initial_knobs = {k: v for k, v in os.environ.items() if k.startswith('HERB_V3_')}
    os.environ['HERB_FACET_SOURCE'] = 'file'
    os.environ['HERB_FACET_FILE'] = str(overlay_path)
    os.environ['HERB_V3_SORT'] = 'multirank'
    from arms import artefact_v3 as arm
    from graph.db import _driver
    if arm.DATABASE != 'herb-eval-volmax':
        raise ValueError('The task names Volmax; environment points to another database')
    params = {'runId': arm.RUN_ID, 'datasetId': arm.DATASET_ID,
              'excludedSections': arm._EXCLUDED_PARAM}
    edge_query = arm._ALL_EDGES_CYPHER.replace('r.w_facets AS w',
        'r.w_facets AS w, r.facets AS legacy_facets, elementId(r) AS relation_id')
    with _driver() as driver:
        with driver.session(database=arm.DATABASE, default_access_mode='READ') as session:
            products = sorted({r['name'] for r in session.run('MATCH (p:Product) RETURN p.name AS name') if r['name']})
            all_tags = [dict(r) for r in session.run('MATCH (t:Tag) RETURN t.name AS name,t.emb AS emb ORDER BY name')]
            prepared_names = [r['name'] for r in session.run(arm._ALL_TAGS_CYPHER, **params)]
            chunks = [dict(r) for r in session.run(arm._ALL_CHUNKS_CYPHER, **params)]
            edges = [dict(r) for r in session.run(edge_query, **params)]
            scope_rows = [dict(r) for r in session.run('''
                MATCH (c:Chunk)-[r]->(n) WHERE type(r) <> 'HAS_TAG'
                RETURN c.chunk_id AS chunk_id,type(r) AS relation,labels(n) AS labels,
                       n.name AS name,elementId(n) AS node_id
                ORDER BY chunk_id,relation,node_id''')]
    print(f'Read {len(chunks)} eligible chunks, {len(edges)} edges; assembling static measurements', flush=True)
    all_tag_at = {r['name']: i for i, r in enumerate(all_tags)}
    all_tag_raw64 = np.asarray([r['emb'] for r in all_tags], dtype=np.float64)
    semantic_raw = all_tag_raw64[[all_tag_at[t] for t in tags]]
    if array_sha(semantic_raw) != matching['graph_vector_sha256_float64_before_normalization']:
        raise ValueError('Live semantic tag vectors differ from the saved matching capture')
    if saved_tag_cos.shape != (len(query_tags), len(tags)):
        raise ValueError('Saved score matrix shape differs from capture ordering')
    if not np.allclose(saved_tag_cos, query_vectors @ unit(semantic_raw).T, rtol=0, atol=1e-12):
        raise ValueError('Saved score matrix does not reconstruct from captured vectors')
    # Arm preparation first casts stored embeddings to float32, then normalizes
    # those values in float64. Keep that precision path for topic and links.
    all_tag_raw32 = all_tag_raw64.astype(np.float32)
    all_tag_vectors = unit(all_tag_raw32)
    semantic_vectors = all_tag_vectors[[all_tag_at[t] for t in tags]]
    chunk_raw32 = np.asarray([r.pop('emb') for r in chunks], dtype=np.float32)
    chunk_vectors = unit(chunk_raw32)
    chunk_ids = [r['chunkId'] for r in chunks]
    chunk_at = {c: i for i, c in enumerate(chunk_ids)}
    products_fold = {p.casefold() for p in products}
    prepared_set = set(prepared_names)
    candidate_tag = np.asarray([t in prepared_set and t.casefold() not in products_fold for t in tags])
    band_indices = [all_tag_at[t] for t in prepared_names]
    band_vectors = all_tag_vectors[band_indices]
    overlay = json.loads(overlay_path.read_text(encoding='utf-8'))
    if overlay['database'] != arm.DATABASE or overlay['run_id'] != arm.RUN_ID or overlay['facets'] != FACETS:
        raise ValueError('Overlay source or facet schema mismatch')
    overlay_by = {(r['chunkId'], r['tag']): r['weights'] for r in overlay['edges']}
    if len(overlay_by) != len(overlay['edges']):
        raise ValueError('Duplicate overlay edges')
    live_keys = {(r['chunkId'], r['tag']) for r in edges}
    if len(live_keys) != len(edges) or live_keys != set(overlay_by):
        raise ValueError('Live eligible HAS_TAG edge set differs from the frozen overlay')
    edges.sort(key=lambda r: (r['chunkId'], r['tag']))
    selected, excluded = [], []
    for row in edges:
        if row['tag'].casefold() in products_fold:
            excluded.append(row)
        else:
            if row['tag'] not in tag_at or not candidate_tag[tag_at[row['tag']]]:
                raise ValueError('Eligible route edge missing from semantic candidate vocabulary')
            selected.append(row)
    edge_tag = np.array([tag_at[r['tag']] for r in selected], dtype=np.int32)
    edge_chunk = np.array([chunk_at[r['chunkId']] for r in selected], dtype=np.int32)
    edge_facet = np.asarray([[np.nan if v is None else v for v in overlay_by[(r['chunkId'], r['tag'])]]
                             for r in selected], dtype=np.float64)
    topic = np.einsum('ij,ij->i', semantic_vectors[edge_tag], chunk_vectors[edge_chunk])
    null_topic = np.isnan(edge_facet[:, 0])
    edge_facet[null_topic, 0] = topic[null_topic]
    legacy = np.asarray([r['w'] for r in selected], dtype=np.float64)
    legacy_schemas = sorted({tuple(r['legacy_facets'] or []) for r in selected})
    if edge_facet.shape != (len(selected), 5) or legacy.shape != edge_facet.shape:
        raise ValueError('Invalid facet matrix dimensions')

    texts = {}
    with export_path.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('chunk_id') in chunk_at:
                texts[row['chunk_id']] = row
    archive = subprocess.check_output(['git', 'show', ARCHIVE_REF], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        member, = [n for n in zipped.namelist() if n.endswith('neo4j_chunks_final.jsonl')]
        descriptions_bytes = zipped.read(member)
    descriptions = {r['cid']: r for r in map(json.loads, descriptions_bytes.splitlines())}
    if set(texts) != set(chunk_ids) or not set(chunk_ids) <= set(descriptions):
        raise ValueError('Eligible chunks lack exported text or original description')
    scopes = {cid: {} for cid in chunk_ids}
    for row in scope_rows:
        if row['chunk_id'] in scopes:
            scopes[row['chunk_id']].setdefault(row['relation'], []).append(
                {k: row[k] for k in ('name', 'node_id', 'labels')})
    for chunk in chunks:
        cid = chunk['chunkId']
        src = texts[cid]
        chunk.update({'chunk_id': cid, 'scope': scopes[cid], 'source_text': src['text'],
                      'source_text_sha256': hashlib.sha256(src['text'].encode()).hexdigest(),
                      'source_kind': src['kind'], 'source_product': src['product'],
                      'source_export_tags': src['tags'], 'original_description': descriptions[cid]['d'],
                      'original_description_metadata': {k: v for k, v in descriptions[cid].items() if k != 'd'}})

    print('Embedding four descriptions and two questions in one pinned CPU model load', flush=True)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import torch
    torch.set_num_threads(4)
    from harness.embed import _embed, EMBED_MODEL, EMBED_REVISION, EMBED_PREFIX
    inputs = [q['description'] for q in queries] + questions
    vectors, calls, tokens_in, tokens_out, seconds = _embed(inputs, 'query', bar=False)
    vectors = unit(vectors)
    description_vectors = vectors[:len(queries)]
    question_vectors = vectors[len(queries):]
    d_graph = description_vectors @ semantic_vectors.T
    q_graph = question_vectors @ semantic_vectors.T
    d_chunk = description_vectors @ chunk_vectors.T
    q_chunk = question_vectors @ chunk_vectors.T
    band_d_graph = description_vectors @ band_vectors.T
    band_q_graph = question_vectors @ band_vectors.T
    centrality = description_vectors @ query_vectors.T
    bands = arm.load_retrain_bands()
    band_meta = {k: v for k, v in bands.items() if not k.startswith('_')}
    for i, query in enumerate(queries):
        qi = query['question_index']
        query['description_index'] = i
        query['tag_band'] = max(float(np.median(np.abs(band_d_graph[i] - band_q_graph[qi]))), arm.COS_NOISE)
        query['desc_band'] = max(float(np.median(np.abs(d_chunk[i] - q_chunk[qi]))), arm.COS_NOISE)
        query['scope_policy'] = 'No inferred gate. Membership captured; replay must declare any externally supplied scope.'

    arrays = dict(edge_tag=edge_tag, edge_chunk=edge_chunk, edge_facets=edge_facet,
                  edge_legacy_facets=legacy, candidate_tag=candidate_tag,
                  query_tag_graph_cos=saved_tag_cos,
                  query_tag_graph_cos_forum_precision=query_vectors @ semantic_vectors.T,
                  query_tag_chunk_cos=query_vectors @ chunk_vectors.T,
                  description_graph_cos=d_graph, question_graph_cos=q_graph,
                  description_chunk_cos=d_chunk, question_chunk_cos=q_chunk,
                  centrality=centrality, query_tag_vectors=query_vectors,
                  description_vectors=description_vectors, question_vectors=question_vectors,
                  band_description_graph_cos=band_d_graph, band_question_graph_cos=band_q_graph)
    np.savez_compressed(args.out / 'arrays.npz', **arrays)
    # Original DB vectors use the arm's float32 storage path; normalized float64
    # vectors can be reconstructed without another database read.
    np.savez_compressed(args.out / 'graph_vectors.npz', tag_raw_float32=all_tag_raw32,
                        chunk_raw_float32=chunk_raw32)
    graph = {'facets': FACETS, 'legacy_db_facet_schemas': [list(s) for s in legacy_schemas],
             'graph_tags': tags, 'query_tags': query_tags, 'chunks': chunks,
             'chunk_ids': chunk_ids, 'queries': queries, 'questions': questions,
             'edge_ids': [r['chunkId'] + '::' + r['tag'] for r in selected],
             'edge_relation_ids': [r['relation_id'] for r in selected],
             'excluded_product_edges': excluded, 'product_names': products,
             'all_graph_vector_tag_names': [r['name'] for r in all_tags],
             'band_graph_tag_names': prepared_names,
             'operator_defaults': {'topic_band': arm._topic_band_value(), 'facet_band': bands['facet_band'],
                'r_band': arm.COS_NOISE, 'betas': {f: 1.0 for f in FACETS[1:]},
                'adjust': 'bounded', 'topic_key': 'ordered', 'desc_place': 'after',
                'band_rule': 'paraphrase', 'weights': 'supplied per query tag; no hidden fallback',
                'scope': 'no inferred query scope; all chunks in one pass unless explicitly supplied'},
             'band_source': band_meta}
    write_json(args.out / 'graph.json', graph)
    source_paths = [Path(__file__), ROOT / 'test/arms/artefact_v3.py', ROOT / 'test/arms/artefact_v2.py',
                    ROOT / 'prod/harness/embed.py', overlay_path, export_path,
                    args.source / 'manifest.json', args.source / 'route_matches.json',
                    args.source / 'tag_matching_scores.npz']
    manifest = {'protocol': __doc__, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'database': arm.DATABASE, 'run_id': arm.RUN_ID, 'dataset_id': arm.DATASET_ID,
                'excluded_sections': arm._EXCLUDED_PARAM,
                'query_strings': {'tags': arm._ALL_TAGS_CYPHER, 'chunks': arm._ALL_CHUNKS_CYPHER, 'edges': edge_query},
                'counts': {'chunks': len(chunks), 'eligible_edges_including_product': len(edges),
                    'semantic_route_edges': len(selected), 'excluded_product_edges': len(excluded),
                    'matching_vocabulary_tags': len(tags), 'eligible_candidate_tags': int(candidate_tag.sum()),
                    'matching_tags_without_eligible_routes': int((~candidate_tag).sum()),
                    'band_tags_including_products': len(prepared_names), 'query_tags': len(query_tags),
                    'route_count_per_all_17_tags': len(selected) * len(query_tags)},
                'reconciliation': {'overlay_keys_equal_live_eligible_edges': True,
                    'eligible_texts_complete': True, 'original_descriptions_complete': True,
                    'saved_tag_scores_reconstructed_max_abs_delta': float(np.max(np.abs(saved_tag_cos - query_vectors @ unit(semantic_raw).T))),
                    'forum_precision_tag_scores_max_abs_delta': float(np.max(np.abs(saved_tag_cos - arrays['query_tag_graph_cos_forum_precision'])))},
                'graph_facet_source': {'topic': 'cos(Tag.emb,Chunk.desc_emb), DB vectors cast float32 then unit normalized float64 as read_facet_file',
                    'topic_overlay_null_rows': int(null_topic.sum()), 'four_others': str(overlay_path),
                    'legacy_db_facets': [list(s) for s in legacy_schemas],
                    'legacy_used_by_forum': False,
                    'note': 'Legacy entities/evidence are not renamed why/concreteness. Legacy array retained for audit only.'},
                'description_source': {'git_ref': ARCHIVE_REF, 'archive_sha256': hashlib.sha256(archive).hexdigest(),
                    'member': member, 'member_sha256': hashlib.sha256(descriptions_bytes).hexdigest(),
                    'note': 'Original historical tagger description text; DB description vectors were not regenerated.'},
                'embedding': {'model': EMBED_MODEL, 'revision': EMBED_REVISION, 'prefixes': EMBED_PREFIX,
                    'new_inputs': inputs, 'input_type': 'query', 'calls': calls, 'tokens_in': tokens_in,
                    'tokens_out': tokens_out, 'seconds': seconds, 'cpu_threads': 4, 'loads': 1,
                    'query_tag_vectors': 'reused from tag_matching_scores.npz'},
                'source_sha256': {str(p): sha(p) for p in source_paths},
                'output_sha256': {name: sha(args.out / name) for name in ('arrays.npz', 'graph_vectors.npz', 'graph.json')},
                'arrays': {k: {'shape': list(v.shape), 'dtype': str(v.dtype), 'sha256': array_sha(v)} for k, v in arrays.items()},
                'initial_v3_environment': initial_knobs,
                'limits': ['Only four diagnostic generated readings and two questions.',
                    'No relevance preference labels, route aggregation, rank validation or context selection in this capture.',
                    'Membership is recorded without inferring query scope.',
                    'Cosine boundaries reproduce the forum instrument, not a validated tag relevance threshold.']}
    write_json(args.out / 'manifest.json', manifest)
    print(json.dumps(manifest['counts']), flush=True)
    print('Snapshot complete: ' + str(args.out), flush=True)


if __name__ == '__main__':
    main()
