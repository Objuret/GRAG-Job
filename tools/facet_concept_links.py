"""Trace the two description/tag links in the frozen concept assembly.

No calls or new retrieval rule. Extract the existing pure link functions and
verify their levels against the executed focal traces before interpreting them.
"""
import ast
import hashlib
import json
import os
from pathlib import Path

os.environ['OPENBLAS_NUM_THREADS'] = '4'
os.environ['OMP_NUM_THREADS'] = '4'
import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
OUT = ROOT / 'output/research/2026-09-22-joint-streams/concept'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pure(path, names):
    tree = ast.parse(path.read_text(encoding='utf8'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in nodes} != set(names):
        raise ValueError('Required source functions missing')
    space = {'np': np}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), space)
    return space


def main():
    v3 = ROOT / 'test/arms/artefact_v3.py'
    v2 = ROOT / 'test/arms/artefact_v2.py'
    unit = pure(v2, ['_unit'])['_unit']
    funcs = pure(v3, ['band_steps', 'paraphrase_band'])
    steps = funcs['band_steps']
    protocol = read(OUT / 'protocol.json')
    for path in (v3, v2, BASE / 'graph.json', BASE / 'arrays.npz', BASE / 'graph_vectors.npz'):
        if sha(path) != protocol['source_sha256'][str(path.relative_to(ROOT))]:
            raise ValueError('Executed replay input/source changed: ' + str(path))
    graph = read(BASE / 'graph.json')
    arrays = np.load(BASE / 'arrays.npz', allow_pickle=False)
    vecs = np.load(BASE / 'graph_vectors.npz', allow_pickle=False)
    names = graph['band_graph_tag_names']
    all_at = {v: i for i, v in enumerate(graph['all_graph_vector_tag_names'])}
    tags = unit(vecs['tag_raw_float32'][[all_at[t] for t in names]].astype(np.float64))
    chunks = unit(vecs['chunk_raw_float32'].astype(np.float64))
    chunk_at = {v: i for i, v in enumerate(graph['chunk_ids'])}
    tag_at = {v: i for i, v in enumerate(names)}
    query_at = {v: i for i, v in enumerate(graph['query_tags'])}
    edges = [(graph['chunk_ids'][c], graph['graph_tags'][t])
             for t, c in zip(arrays['edge_tag'], arrays['edge_chunk'])]
    edges += [(r['chunkId'], r['tag']) for r in graph['excluded_product_edges']]
    by_chunk = {}
    for cid, tag in edges:
        by_chunk.setdefault(cid, []).append(tag)
    results = []
    with threadpool_limits(limits=4):
        for query in graph['queries']:
            run_path = OUT / (query['id'] + '_score_0_concept_file.json')
            run = read(run_path)
            desc = unit(arrays['description_vectors'][query['description_index']].astype(np.float64))
            raw = unit(arrays['question_vectors'][query['question_index']].astype(np.float64))
            tb = max(float(np.median(np.abs(tags @ desc - tags @ raw))), 0.002)
            db = max(funcs['paraphrase_band'](chunks, desc, raw), 0.002)
            focal = {label: {'chunk_id': item['chunk_id'], 'parts': []}
                     for label, item in run['focal'].items()}
            for part in run['plan']['parts']:
                q = unit(arrays['query_tag_vectors'][query_at[part['t']]].astype(np.float64))
                ts, ds = tags @ q, chunks @ q
                tl, dl = steps(ts, tb), steps(ds, db)
                for label, item in focal.items():
                    cid = item['chunk_id']
                    c = chunk_at[cid]
                    routes = [{'graph_tag': tag, 'tag_cosine': float(ts[tag_at[tag]]),
                               'tag_level': int(tl[tag_at[tag]]),
                               'part_description_cosine': float(ds[c]),
                               'description_level': int(dl[c]),
                               'combined_level': max(int(tl[tag_at[tag]]), int(dl[c]))}
                              for tag in sorted(by_chunk[cid])]
                    item['parts'].append({'query_tag': part['t'], 'routes': routes,
                        'best_tag_level': min(r['tag_level'] for r in routes),
                        'description_level': int(dl[c]),
                        'best_combined_level': min(r['combined_level'] for r in routes)})
            for label, item in focal.items():
                observed = run['focal'][label]['selected_route']
                matches = [r for p in item['parts'] if p['query_tag'] == observed['query_tag']
                           for r in p['routes'] if r['graph_tag'] == observed['graph_tag']]
                assert len(matches) == 1 and not observed['from_shape']
                assert matches[0]['combined_level'] == observed['level']
                item['selected_link_trace'] = matches[0]
                item['selected_query_tag'] = observed['query_tag']
                item['best_tag_level'] = min(p['best_tag_level'] for p in item['parts'])
                item['best_direct_combined_level'] = min(p['best_combined_level'] for p in item['parts'])
                item['channel_memberships'] = graph['chunks'][chunk_at[item['chunk_id']]]['scope'].get('channel', [])
                assert item['best_direct_combined_level'] == observed['level']
            levels = {k: v['best_direct_combined_level'] for k, v in focal.items()}
            row = {'generation_id': query['id'], 'tag_band': tb, 'description_band': db,
                   'focal': focal, 'different_earliest_levels': len(set(levels.values())) == 2,
                   'earlier_before_within_level_facets': min(levels, key=levels.get),
                   'replay_sha256': sha(run_path)}
            results.append(row)
            print(query['id'], levels, 'selected', {k: v['selected_link_trace'] for k, v in focal.items()})
    result = {'protocol': __doc__, 'runs': results,
              'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in
                               (Path(__file__), v3, v2, BASE / 'graph.json', BASE / 'arrays.npz', BASE / 'graph_vectors.npz')},
              'limits': ['Causal decomposition of existing focal routes; no new ranking or utility coefficients.',
                         'Source max(tag level, description level) is an implementation, not an endorsed rule.',
                         'Different earliest levels settle these pairs before within-level facets or locality can act.',
                         'This does not establish that facets are useless on other chunk comparisons.']}
    (OUT / 'link_decomposition.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
