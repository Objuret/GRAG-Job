"""Matched-encoder description diagnostic after documented hosted/local mismatch."""
import ast
from collections import defaultdict
import json
from pathlib import Path
import numpy as np

from facet_description_intervention import (
    ROOT, STATIC, BASE, QUESTION, IDS, read, write, sha, unit,
    FACETS, freeze_reference, rank_facet_stream_envelope,
)

OUT = BASE / 'description_matched'
PREVIOUS = BASE / 'description_intervention'


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError('Refusing to overwrite frozen matched diagnostic')
    previous = read(PREVIOUS / 'protocol.json')
    for p, h in previous['input_sha256'].items():
        assert sha(ROOT / p) == h
    assert not (PREVIOUS / 'summary.json').exists(), 'Previous control should have stopped before ranking'
    graph = read(STATIC / 'graph.json')
    static = dict(np.load(STATIC / 'arrays.npz'))
    vectors = dict(np.load(STATIC / 'graph_vectors.npz'))
    encoded = np.load(PREVIOUS / 'vectors.npz')['encoded']
    assert encoded.shape == (4, 2048)
    assert np.max(np.abs(np.linalg.norm(encoded, axis=1) - 1)) < 1e-12
    queries = read(BASE / 'query_snapshot/queries.json')
    arrays = dict(np.load(BASE / 'query_snapshot/arrays.npz'))
    query = next(q for q in queries['queries'] if q['question_id'] == QUESTION)
    capture = next(c for c in read(BASE / 'query_capture/query_captures.json')['captures'] if c['question_id'] == QUESTION)
    assert query['tags'] == capture['clean_tags']
    assert queries['chunk_ids'] == graph['chunk_ids']
    at = [graph['chunk_ids'].index(cid) for cid in IDS]
    all_tag_at = {t:i for i,t in enumerate(graph['all_graph_vector_tag_names'])}
    semantic_vectors = unit(vectors['tag_raw_float32'][[all_tag_at[t] for t in graph['graph_tags']]])
    affected_edges = np.flatnonzero(np.isin(static['edge_chunk'], at))
    chunk_local = {ci:i for i,ci in enumerate(at)}
    original_chunk_vectors = unit(vectors['chunk_raw_float32'][at])
    topic_check = np.einsum('ij,ij->i', semantic_vectors[static['edge_tag'][affected_edges]],
                          original_chunk_vectors[[chunk_local[ci] for ci in static['edge_chunk'][affected_edges]]])
    assert np.max(np.abs(topic_check - static['edge_facets'][affected_edges, 0])) < 1e-12
    expected_texts = [graph['chunks'][i]['original_description'] for i in at] + [graph['chunks'][i]['source_text'] for i in at]
    assert [r['text'] for r in previous['embedding_texts']] == expected_texts
    source_paths = [Path(__file__), PREVIOUS / 'protocol.json', PREVIOUS / 'vectors.npz',
                    PREVIOUS / 'embedding_verification.json', ROOT / 'docs/ENVIRONMENT.md']
    hashes = {**previous['input_sha256'], **{str(p.relative_to(ROOT)):sha(p) for p in source_paths}}
    protocol = {
        'status': 'frozen_before_any_matched_ranking', 'input_sha256': hashes,
        'question_id': QUESTION, 'chunk_ids': IDS,
        'selection': 'Post-hoc single complementary case. No held-out or population claim.',
        'amendment': 'Prior endpoint-only protocol stopped before ranking because hosted stored vectors did not equal local controls. Reuse the four saved local vectors; compare source texts to original descriptions under the same encoder.',
        'conditions': ['current_description', 'full_source'],
        'changed_together': 'Only these two chunk representations: query-tag→chunk cosine D, query-description→chunk cosine Q, and graph-tag→chunk cosine topic for their actual HAS_TAG edges.',
        'unchanged': 'All generated query fields and vectors, query facet values, graph tag vectors, other chunks, four learned auxiliary edge columns, fixed original 57204-edge CDF, coefficients, graph relations and operator.',
        'reference_policy': 'Same original graph CDF for both conditions. Do not shift other edges by refitting normalization.',
        'outcomes': 'Focal route sponsors, direct and graph facet/query profiles, topic edges, D/Q, full ranks and scores. Compare conditions and report stored baseline only as a serving-provenance sensitivity check.',
        'limits': 'Updates only two chunks in an otherwise frozen index. Multiple text details and length change together. No proof that a specific omission alone causes changes, no changed query coverage rule, no production recommendation from one case.',
        'new_embedding_calls': 0, 'new_generation_calls': 0, 'db_calls': 0,
        'affected_edges': len(affected_edges),
    }
    OUT.mkdir(parents=True)
    write(OUT / 'protocol.json', protocol)
    groups = defaultdict(list)
    for ci,c in enumerate(graph['chunks']):
        for p in c['scope'].get('product', []):
            for ch in c['scope'].get('channel', []):
                groups[(p['node_id'],ch['node_id'])].append(ci)
    tree = ast.parse((ROOT / 'test/arms/artefact_v3.py').read_text(encoding='utf-8'))
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'_csr','file_adjacency'}]
    assert len(funcs) == 2
    ns = {'np':np, 'json':json}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), 'frozen_adjacency', 'exec'),ns)
    adj = ns['file_adjacency'](graph['chunks'])
    pairs = [(i,int(j)) for i in range(len(graph['chunks'])) for j in adj['members'][adj['ptr'][i]:adj['ptr'][i+1]] if i<j]
    reference = freeze_reference(static['edge_facets'])
    indices = query['query_tag_indices']
    records = []
    for reading in capture['readings']:
        by_tag = {v['t']:v['facets'] for v in reading['values']}
        weights = np.array([[by_tag[t][f] for f in FACETS] for t in query['tags']])
        for condition, replacement in [('current_description', encoded[:2]), ('full_source',encoded[2:])]:
            d = arrays['query_tag_chunk_cos'][indices].copy()
            q = arrays['description_chunk_cos'][query['description_index']].copy()
            ef = static['edge_facets'].copy()
            d[:,at] = arrays['query_tag_vectors'][indices] @ replacement.T
            q[at] = arrays['description_vectors'][query['description_index']] @ replacement.T
            ef[affected_edges,0] = np.einsum('ij,ij->i',semantic_vectors[static['edge_tag'][affected_edges]],
                                 replacement[[chunk_local[ci] for ci in static['edge_chunk'][affected_edges]]])
            mask = np.ones(len(graph['chunks']),bool);mask[at]=False
            edge_mask = np.ones(len(ef),bool);edge_mask[affected_edges]=False
            assert np.array_equal(ef[:,1:],static['edge_facets'][:,1:])
            assert np.array_equal(ef[edge_mask],static['edge_facets'][edge_mask])
            assert np.array_equal(d[:,mask],arrays['query_tag_chunk_cos'][indices][:,mask])
            assert np.array_equal(q[mask],arrays['description_chunk_cos'][query['description_index']][mask])
            result = rank_facet_stream_envelope(chunk_ids=graph['chunk_ids'],query_tag_ids=query['tags'],
                edge_ids=graph['edge_ids'],edge_tag_indices=static['edge_tag'],edge_chunk_indices=static['edge_chunk'],
                edge_facets=ef,query_facet_weights=weights,query_tag_cosines=arrays['query_tag_graph_cos'][indices],
                query_chunk_cosines=d,query_description_cosines=q,reference=reference,
                groups={'shared_product_channel':list(groups.values())},adjacency_pairs=pairs)
            assert len(result['rows']) == 4808
            assert max(abs(r['score']-sum(w['contribution'] for w in r['provenance'].values() if w)) for r in result['rows'])<1e-12
            focal = {r['chunk_id']:r for r in result['rows'] if r['chunk_id'] in IDS}
            record = {'reading_id':reading['id'],'condition':condition,'focal':focal,
                'query_tags':query['tags'],'chunk_ids':IDS,'D':d[:,at].tolist(),'Q':q[at].tolist(),
                'topic_edges':[{'edge_id':graph['edge_ids'][e],'topic':float(ef[e,0]),
                                'F_topic':float(result['facet_percentiles'][e,0])} for e in affected_edges],
                'focal_direct_per_facet_query_chunk':result['direct_scores'][:,:,at].tolist(),
                'focal_graph_per_facet_query_chunk':result['graph_scores'][:,:,at].tolist()}
            name=reading['id']+'_'+condition+'.json'
            write(OUT/name,{**record,'rows':[{k:r[k] for k in ('rank','chunk_id','score')} for r in result['rows']],
                'graph_witnesses':[r for r in result['rows'] if any(w and w['route_type']!='direct' for w in r['provenance'].values())]})
            records.append({**record,'file':name,'sha256':sha(OUT/name)})
            print(reading['id'],condition,[(c,r['rank']) for c,r in focal.items()],flush=True)
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    write(OUT/'summary.json',records)
    write(OUT/'verification.json',{'inputs_unchanged':True,'conditions':len(records),'summary_sha256':sha(OUT/'summary.json')})


if __name__ == '__main__':
    main()
