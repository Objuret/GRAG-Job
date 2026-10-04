"""Frozen facet-path envelope on independent source cases; no external calls."""
from pathlib import Path
import ast
from collections import defaultdict
import hashlib
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'test'))
from artefact.facet_joint_candidate import FACETS, freeze_reference
from artefact.facet_stream_envelope import rank_facet_stream_envelope

STATIC = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
OUT = BASE / 'facet_stream_envelope'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError('Output exists; refusing to overwrite frozen evidence')
    graph = read(STATIC / 'graph.json')
    static = dict(np.load(STATIC / 'arrays.npz'))
    meta = read(BASE / 'query_snapshot/queries.json')
    arrays = dict(np.load(BASE / 'query_snapshot/arrays.npz'))
    captures = read(BASE / 'query_capture/query_captures.json')
    cases = read(BASE / 'protocol.json')
    manifest = read(BASE / 'query_snapshot/manifest.json')
    for name, expected in manifest['output_sha256'].items():
        assert sha(BASE / 'query_snapshot' / name) == expected
    for key in ('graph_tags', 'chunk_ids'):
        assert meta[key] == graph[key]
    assert tuple(graph['facets']) == FACETS
    ids = graph['chunk_ids']
    assert [c['chunkId'] for c in graph['chunks']] == ids
    for e, ti, ci in zip(graph['edge_ids'], static['edge_tag'], static['edge_chunk']):
        assert e == ids[ci] + '::' + graph['graph_tags'][ti]
    reference = freeze_reference(static['edge_facets'])
    groups = defaultdict(list)
    for ci, chunk in enumerate(graph['chunks']):
        for p in chunk['scope'].get('product', []):
            for ch in chunk['scope'].get('channel', []):
                groups[(p['node_id'], ch['node_id'])].append(ci)
    relations = {'shared_product_channel': list(groups.values())}
    arm_path = ROOT / 'test/arms/artefact_v3.py'
    tree = ast.parse(arm_path.read_text(encoding='utf-8'))
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'_csr', 'file_adjacency'}]
    assert len(funcs) == 2
    ns = {'np': np, 'json': json}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(arm_path), 'exec'), ns)
    adj = ns['file_adjacency'](graph['chunks'])
    pairs = [(i, int(j)) for i in range(len(ids))
             for j in adj['members'][adj['ptr'][i]:adj['ptr'][i + 1]] if i < j]
    targets = {q['question_id']: q for q in cases['targets']}
    queries = {q['id']: q for q in meta['queries']}
    assert len(queries) == len(captures['captures']) == len(targets) == 7
    source_files = [Path(__file__), arm_path, STATIC / 'graph.json', STATIC / 'arrays.npz',
        BASE / 'protocol.json', BASE / 'EVALUATION.md', BASE / 'query_capture/query_captures.json',
        BASE / 'query_snapshot/queries.json', BASE / 'query_snapshot/arrays.npz',
        BASE / 'query_snapshot/manifest.json', ROOT / 'test/artefact/facet_joint_candidate.py',
        ROOT / 'test/artefact/facet_stream_envelope.py',
        BASE.parent / 'source_first/FACET_STREAM_COMPARISON.md']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in source_files}
    OUT.mkdir(parents=True)
    write(OUT / 'protocol.json', {'input_sha256': hashes, 'conditions': ['intact', 'aux_facets_off', 'shape_off'],
          'groups': len(groups), 'adjacency_pairs': len(pairs), 'reference_edges': len(static['edge_facets']),
          'model_calls': 0, 'db_calls': 0, 'scope': 'No answer-derived scope. All frozen eligible routes.',
          'persistence': 'Full ranks/scores, full focal witnesses, full graph-selected witnesses; other direct witnesses reconstructible from frozen arrays/code.'})
    summary = []
    for capture in captures['captures']:
        query = queries[capture['generation_id']]
        indices, tags = query['query_tag_indices'], query['tags']
        assert [meta['query_tags'][i] for i in indices] == tags == capture['clean_tags']
        assert query['description'] == capture['description']
        target = targets[capture['question_id']]
        for reading in capture['readings']:
            if not reading['ok']:
                summary.append({'reading_id': reading['id'], 'skipped': True, 'error': reading['error']})
                continue
            by_tag = {v['t']: v['facets'] for v in reading['values']}
            weights = np.array([[by_tag[t][f] for f in FACETS] for t in tags])
            for condition in ('intact', 'aux_facets_off', 'shape_off'):
                result = rank_facet_stream_envelope(
                    chunk_ids=ids, query_tag_ids=tags, edge_ids=graph['edge_ids'],
                    edge_tag_indices=static['edge_tag'], edge_chunk_indices=static['edge_chunk'],
                    edge_facets=static['edge_facets'], query_facet_weights=weights,
                    query_tag_cosines=arrays['query_tag_graph_cos'][indices],
                    query_chunk_cosines=arrays['query_tag_chunk_cos'][indices],
                    query_description_cosines=arrays['description_chunk_cos'][query['description_index']],
                    reference=reference, groups=relations if condition != 'shape_off' else {},
                    adjacency_pairs=pairs if condition != 'shape_off' else (),
                    facets_enabled=condition != 'aux_facets_off')
                rows = {r['chunk_id']: r for r in result['rows']}
                focal_ids = target.get('required_within_selected_pair') or [target['preferred'], target['comparison']]
                focal = {cid: rows[cid] for cid in focal_ids}
                graph_rows = [r for r in result['rows'] if any(w and w['route_type'] != 'direct' for w in r['provenance'].values())]
                assert len(rows) == len(result['rows']) == 4808
                assert max(abs(r['score'] - sum(w['contribution'] for w in r['provenance'].values() if w))
                           for r in result['rows']) < 1e-12
                record = {'reading_id': reading['id'], 'generation_id': capture['generation_id'],
                    'question_id': capture['question_id'], 'source_group': target['source_group'],
                    'condition': condition, 'focal': focal, 'graph_selected_chunks': len(graph_rows),
                    'pair_correct': (rows[target['preferred']]['score'] > rows[target['comparison']]['score'])
                        if target.get('preferred') else None,
                    'prefix_containing_selected_sources': max(r['rank'] for r in focal.values()),
                    'interpretation': 'Local pair comparison or selected-pair coverage only; not global relevance/delivery.'}
                filename = reading['id'] + '_' + condition + '.json'
                write(OUT / filename, {**record, 'rows': [{k: r[k] for k in ('rank', 'chunk_id', 'score')}
                    for r in result['rows']], 'graph_witnesses': graph_rows})
                summary.append({**record, 'file': filename, 'sha256': sha(OUT / filename)})
            print(reading['id'], 'completed', flush=True)
    assert all(sha(ROOT / p) == h for p, h in hashes.items())
    write(OUT / 'summary.json', summary)
    write(OUT / 'verification.json', {'inputs_unchanged': True,
          'full_rankings': sum(not r.get('skipped') for r in summary), 'chunks_per_ranking': len(ids),
          'summary_sha256': sha(OUT / 'summary.json')})
    for r in summary:
        if r.get('condition') == 'intact':
            print(r['reading_id'], [(cid, row['rank']) for cid, row in r['focal'].items()], r['pair_correct'])


if __name__ == '__main__':
    main()
