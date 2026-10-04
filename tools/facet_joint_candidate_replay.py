"""Run the predeclared joint candidate on frozen inputs; no external calls."""
from pathlib import Path
import ast
import hashlib
import json
import sys
from collections import defaultdict

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'test'))
from artefact.facet_joint_candidate import FACETS, freeze_reference, rank_joint_candidate

OLD = ROOT / 'output/research/2026-09-21-facet-validity'
NEW = ROOT / 'output/research/2026-09-22-joint-streams/source_first'
OUT = NEW / 'joint_candidate'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    if (OUT / 'summary.json').exists():
        raise RuntimeError('Completed run exists; refusing overwrite')
    OUT.mkdir(parents=True, exist_ok=True)
    graph_path = OLD / 'route_snapshot/graph.json'
    graph = read(graph_path)
    static_path = OLD / 'route_snapshot/arrays.npz'
    static = dict(np.load(static_path))
    assert tuple(graph['facets']) == FACETS
    ids = graph['chunk_ids']
    ref = freeze_reference(static['edge_facets'])
    groups = defaultdict(list)
    for ci, chunk in enumerate(graph['chunks']):
        scope = chunk['scope']
        for p in scope.get('product', []):
            for c in scope.get('channel', []):
                groups[(p['node_id'], c['node_id'])].append(ci)
    relation_groups = {'shared_product_channel': list(groups.values())}
    arm_path = ROOT / 'test/arms/artefact_v3.py'
    tree = ast.parse(arm_path.read_text(encoding='utf-8'))
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'_csr', 'file_adjacency'}]
    assert len(funcs) == 2
    ns = {'np': np, 'json': json}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(arm_path), 'exec'), ns)
    adj = ns['file_adjacency'](graph['chunks'])
    pairs = [(i, int(j)) for i in range(len(ids))
             for j in adj['members'][adj['ptr'][i]:adj['ptr'][i + 1]] if i < j]
    protocol = read(NEW / 'case_protocol.json')
    expectations = {x['question_id']: x for x in protocol['expected_pair_preferences']}
    report, chat = '23540be897d31a78f8ac0f39', '62eecebfe117e91df15db8e3'
    expectations.update(analysis={'preferred': report, 'comparison': chat},
                        sharing={'preferred': chat, 'comparison': report})
    inputs = [graph_path, static_path, arm_path, NEW / 'CANDIDATE.md', NEW / 'case_protocol.json',
              Path(__file__), ROOT / 'test/artefact/facet_joint_candidate.py']
    sources = [
        ('source_first', NEW / 'query_snapshot/queries.json', NEW / 'query_snapshot/arrays.npz', NEW / 'query_capture/query_captures.json'),
        ('original_contrast', graph_path, static_path, OLD / 'route_capture/query_captures.json'),
    ]
    inputs.extend(p for _, *paths in sources for p in paths)
    before = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    write(OUT / 'protocol.json', {'input_sha256': before, 'groups': len(groups),
          'adjacency_pairs': len(pairs), 'reference_edges': len(static['edge_facets']),
          'scope': 'Unfitted candidate and predeclared controls; full frozen graph, no oracle scope.',
          'conditions': ['intact', 'aux_facets_off', 'shape_off']})
    summary = []
    for label, meta_path, arrays_path, capture_path in sources:
        meta, arrays, captures = read(meta_path), dict(np.load(arrays_path)), read(capture_path)
        assert meta['chunk_ids'] == ids and meta['graph_tags'] == graph['graph_tags']
        queries = {q['id']: q for q in meta['queries']}
        for capture in captures['captures']:
            query = queries[capture['generation_id']]
            indices = query['query_tag_indices']
            tags = query['tags']
            assert [meta['query_tags'][i] for i in indices] == tags
            expected = expectations[capture['question_id']]
            for reading in capture['readings']:
                assert reading['ok']
                by_tag = {v['t']: v['facets'] for v in reading['values']}
                weights = np.array([[by_tag[t][f] for f in FACETS] for t in tags])
                for condition in ('intact', 'aux_facets_off', 'shape_off'):
                    result = rank_joint_candidate(
                        chunk_ids=ids, query_tag_ids=tags, edge_ids=graph['edge_ids'],
                        edge_tag_indices=static['edge_tag'], edge_chunk_indices=static['edge_chunk'],
                        edge_facets=static['edge_facets'], query_facet_weights=weights,
                        query_tag_cosines=arrays['query_tag_graph_cos'][indices],
                        query_chunk_cosines=arrays['query_tag_chunk_cos'][indices],
                        query_description_cosines=arrays['description_chunk_cos'][query['description_index']],
                        reference=ref, groups=relation_groups if condition != 'shape_off' else {},
                        adjacency_pairs=pairs if condition != 'shape_off' else (),
                        facets_enabled=condition != 'aux_facets_off')
                    rows = {r['chunk_id']: r for r in result['rows']}
                    focal = {role: rows[expected[role]] for role in ('preferred', 'comparison')}
                    record = {'source': label, 'generation_id': capture['generation_id'],
                              'reading_id': reading['id'], 'condition': condition,
                              'question_id': capture['question_id'], 'focal': focal,
                              'expected_pair_correct': focal['preferred']['score'] > focal['comparison']['score'],
                              'graph_selected_chunks': sum(bool(r['provenance'] and r['provenance']['route_type'] != 'direct') for r in result['rows'])}
                    assert len(result['ranked_chunk_ids']) == len(set(result['ranked_chunk_ids'])) == 4808
                    filename = f"{reading['id']}_{condition}.json"
                    write(OUT / filename, {**record, 'rows': result['rows']})
                    summary.append({**record, 'file': filename, 'sha256': digest(OUT / filename)})
                print(label, reading['id'], 'completed', flush=True)
    assert all(digest(ROOT / p) == h for p, h in before.items())
    write(OUT / 'summary.json', summary)
    write(OUT / 'verification.json', {'inputs_unchanged': True, 'full_rankings': len(summary),
          'chunks_per_ranking': len(ids), 'summary_sha256': digest(OUT / 'summary.json')})
    for r in summary:
        f = r['focal']
        print(r['reading_id'], r['condition'], f['preferred']['rank'], f['comparison']['rank'], r['expected_pair_correct'])


if __name__ == '__main__':
    main()
