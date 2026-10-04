"""Offline observable decomposition of captured query-tag routes.

No new weights, aggregate score, semantic clustering, model call, or graph read.
Exact best-route identity is reported as observable overlap, not independence.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import hashlib
import json

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/research/2026-09-21-facet-validity'
OUT = ROOT / 'output/research/2026-09-22-route-aggregation'
FOCAL = {'report': '23540be897d31a78f8ac0f39', 'sharing': '62eecebfe117e91df15db8e3'}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def summarize_q(readings, facets):
    valid = [r['values'] for r in readings if r['values'] is not None]
    return {'readings': readings,
            'observed_min': {f: min(v[f] for v in valid) for f in facets} if valid else None,
            'observed_max': {f: max(v[f] for v in valid) for f in facets} if valid else None,
            'range_meaning': 'Observed repeated readings only; not statistical confidence bounds.'}


def main():
    print('Decomposing frozen routes and exact best-tag overlap; no model or DB calls', flush=True)
    graph_path = BASE / 'route_snapshot/graph.json'
    array_path = BASE / 'route_snapshot/arrays.npz'
    capture_path = BASE / 'route_capture/query_captures.json'
    fresh_path = BASE / 'fresh_corpus/manifest.json'
    graph, captures, fresh = read(graph_path), read(capture_path), read(fresh_path)
    z = np.load(array_path)
    facets = graph['facets']
    ti = {t: i for i, t in enumerate(graph['query_tags'])}
    ci = {cid: i for i, cid in enumerate(graph['chunk_ids'])}
    edge_by_id = {eid: i for i, eid in enumerate(graph['edge_ids'])}
    query_by_id = {q['id']: q for q in graph['queries']}
    edge_tag, edge_chunk = z['edge_tag'], z['edge_chunk']
    cosine = z['query_tag_graph_cos_forum_precision']
    candidate = z['candidate_tag']
    rows = []

    def edge_record(e):
        return {'edge_index': int(e), 'edge_id': graph['edge_ids'][e],
                'graph_tag': graph['graph_tags'][edge_tag[e]],
                'graph_tag_index': int(edge_tag[e]),
                'chunk_id': graph['chunk_ids'][edge_chunk[e]],
                'static_graph_facets': dict(zip(facets, z['edge_facets'][e].tolist()))}

    def best_routes(qi, cid):
        es = np.flatnonzero(edge_chunk == ci[cid])
        scores = cosine[qi, edge_tag[es]]
        best = float(scores.max())
        winners = es[scores == best]
        return {'best_tag_cosine': best,
                'best_routes': [edge_record(e) for e in winners],
                'all_attached_semantic_edges': len(es),
                'eligible_global_tag_rank_competition': 1 + int(np.sum(cosine[qi, candidate] > best)),
                'query_tag_facet_values_do_not_enter_best_tag_selection': True}

    for capture in captures['captures']:
        q = query_by_id[capture['generation_id']]
        tag_rows = []
        for tag in capture['clean_tags']:
            qi = ti[tag]
            readings = []
            for reading in capture['readings']:
                found = next((r['facets'] for r in reading.get('values', []) if r['t'] == tag), None)
                readings.append({'reading_id': reading['id'], 'ok': reading['ok'], 'values': found})
            by_chunk = {label: best_routes(qi, cid) for label, cid in FOCAL.items()}
            tag_rows.append({'query_tag': tag, 'query_tag_index': qi,
                'query_embedding_vector': z['query_tag_vectors'][qi].tolist(),
                'query_embedding_source': 'route_snapshot/arrays.npz:query_tag_vectors; existing query prefix',
                'query_facet_vector': summarize_q(readings, facets),
                'query_description_centrality': float(z['centrality'][q['description_index'], qi]),
                'best_routes_by_chunk': by_chunk,
                'report_minus_sharing_best_tag_cosine': by_chunk['report']['best_tag_cosine'] - by_chunk['sharing']['best_tag_cosine']})
        overlap = {}
        for label in FOCAL:
            groups = defaultdict(list)
            for row in tag_rows:
                signature = tuple(r['edge_id'] for r in row['best_routes_by_chunk'][label]['best_routes'])
                groups[signature].append(row['query_tag'])
            overlap[label] = [{'best_edge_ids': list(key), 'query_tags': value,
                               'multiple_query_tags_share_exact_best_route': len(value) > 1}
                              for key, value in groups.items()]
        signature_groups = defaultdict(list)
        for row in tag_rows:
            signature = tuple(tuple(r['edge_id'] for r in row['best_routes_by_chunk'][label]['best_routes']) for label in FOCAL)
            signature_groups[signature].append(row['query_tag'])
        rows.append({'generation_id': capture['generation_id'], 'question': capture['question'],
                     'description': capture['description'], 'tags': tag_rows,
                     'exact_best_route_overlap_by_chunk': overlap,
                     'exact_best_route_pair_signatures': [
                         {'best_edge_ids_by_chunk': dict(zip(FOCAL, [list(v) for v in sig])),
                          'query_tags': names} for sig, names in signature_groups.items()],
                     'observational_limit': 'Distinct routes do not establish independent requested relations. Same best route records exact overlap without imposing a semantic similarity threshold.'})

    # Existing fresh cases are fixed-tag prompts, not generated complete query
    # tag sets. Keep their captured readings/static edges but never replace a
    # missing query embedding with the graph tag passage-prefix embedding.
    fresh_readings = [(path, read(path)) for path in (BASE / 'fresh_corpus/query_0.json', BASE / 'fresh_corpus/query_1.json')]
    extra = []
    for domain in fresh['cases']['domains']:
        tag = domain['tag']
        item = {'id': domain['id'], 'fixed_query_tag': tag,
                'source_chunks': domain['source_chunks'], 'source_kinds': domain['source_kinds'],
                'query_tag_embeddings_present_in_route_snapshot': tag in ti,
                'complete_generated_query_tag_sets_available': False,
                'fixed_tag_static_edges': [edge_record(edge_by_id[e]) for e in domain['source_edges']],
                'existing_fixed_tag_query_readings': []}
        for k, description in enumerate(domain['descriptions']):
            cid = f"{domain['id']}_{k}"
            item['existing_fixed_tag_query_readings'].append({'case_id': cid, 'description': description,
                'facet_vector': summarize_q([
                    {'reading_id': data['id'], 'values': data['answer'].get(cid)} for _, data in fresh_readings], facets)})
        if tag in ti:
            item['best_routes_by_chunk'] = {cid: best_routes(ti[tag], cid) for cid in domain['source_chunks']}
        else:
            item['gap'] = ('No captured query-prefix embedding for this fixed tag in the frozen route snapshot or fresh-corpus artifacts. '
                           'Cannot compute query-tag/graph-tag matches offline from these artifacts. The graph tag embedding is not substituted. '
                           'Complete intended query-tag generation and its repetitions are also absent.')
        extra.append(item)
    used = [Path(__file__), graph_path, array_path, capture_path, fresh_path,
            BASE / 'route_replay/RESULTS.md', *(p for p, _ in fresh_readings)]
    result = {'protocol': __doc__, 'created_utc': datetime.now(timezone.utc).isoformat(), 'facets': facets,
              'focal_chunks': {label: {'chunk_id': cid, 'kind': graph['chunks'][ci[cid]]['source_kind'],
                                     'source_text_sha256': graph['chunks'][ci[cid]]['source_text_sha256']}
                               for label, cid in FOCAL.items()},
              'cosine_source': 'route_snapshot/arrays.npz:query_tag_graph_cos_forum_precision',
              'best_rule': 'Maximum query-tag/graph-tag cosine among all semantic HAS_TAG edges on the specified chunk. Preserve all exact ties. No query or graph facet enters this local diagnostic selection.',
              'captures': rows, 'fresh_source_pairs': extra,
              'fresh_embedding_gap_count': sum(not x['query_tag_embeddings_present_in_route_snapshot'] for x in extra),
              'limits': ['Best-route overlap is not proof of semantic independence or redundancy.',
                         'These are component observations, not a new retrieval aggregate or learned weights.',
                         'The two focal questions and previously inspected corpus pairs are diagnostic data, not held-out validation.',
                         'Fresh fixed-tag query values came from the old numeric experiment, not the current split SCORE captures.'],
              'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in used}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'decomposition.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    for capture in rows:
        print(capture['generation_id'], flush=True)
        for row in capture['tags']:
            a, b = row['best_routes_by_chunk']['report'], row['best_routes_by_chunk']['sharing']
            print(f"  {row['query_tag']}: report {a['best_tag_cosine']:.6f} {','.join(x['graph_tag'] for x in a['best_routes'])}; "
                  f"sharing {b['best_tag_cosine']:.6f} {','.join(x['graph_tag'] for x in b['best_routes'])}", flush=True)
    print('Fresh source pairs lacking captured query-tag embeddings:', result['fresh_embedding_gap_count'], flush=True)


if __name__ == '__main__':
    main()
