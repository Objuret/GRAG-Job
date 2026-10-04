"""Capture structural landings from Volmax using an explicit read transaction.

No question, gold, model, legacy name cache, or database write is used. Corpus
JSON is parsed mechanically only to follow structural pointers to name fields.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
SNAPSHOT = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
OUT = ROOT / 'output/research/2026-09-22-structural-landings'
DATABASE = 'herb-eval-volmax'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / 'structural_snapshot.json'
    if target.exists():
        raise RuntimeError('Snapshot already exists; refusing to overwrite')
    from artefact import landing
    from graph.db import _driver
    graph_path, manifest_path = SNAPSHOT / 'graph.json', SNAPSHOT / 'manifest.json'
    graph = json.loads(graph_path.read_text(encoding='utf-8'))
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['database'] == DATABASE
    eligible = set(map(str, graph['chunk_ids']))
    assert len(eligible) == len(graph['chunk_ids']) == 4808
    params = dict(datasetId=manifest['dataset_id'], runId=manifest['run_id'],
                  excludedSections=manifest['excluded_sections'])
    eligible_query = manifest['query_strings']['chunks'].split('RETURN', 1)[0] + 'RETURN c.chunk_id AS chunk_id ORDER BY chunk_id'
    scope_query = '''MATCH (c:Chunk)-[r:product|channel]->(n)
        WHERE c.chunk_id IN $ids
        RETURN c.chunk_id AS chunk_id, type(r) AS relation,
               labels(n) AS labels, n.name AS name, elementId(n) AS node_id'''

    def read(tx):
        live_ids = [str(r['chunk_id']) for r in tx.run(eligible_query, **params)]
        scopes = [dict(r) for r in tx.run(scope_query, ids=sorted(eligible))]
        named = landing._read_nodes(tx)
        routes = {}
        for route in landing.DEFAULT_ROUTES:
            label, query = landing.ROUTES[route]
            ids = [r['node_id'] for r in named['rows'][label]]
            routes[route] = [dict(r) for r in tx.run(query, ids=ids)]
        return live_ids, scopes, named, routes

    with _driver() as driver:
        with driver.session(database=DATABASE, default_access_mode='READ') as session:
            live_ids, scopes, named, route_rows = session.execute_read(read)
    frozen_scopes = set()
    for chunk in graph['chunks']:
        for relation in ('product', 'channel'):
            for node in chunk['scope'].get(relation, []):
                frozen_scopes.add((str(chunk['chunk_id']), relation, str(node['node_id']), node['name'], tuple(sorted(node['labels']))))
    live_scopes = {(str(r['chunk_id']), r['relation'], str(r['node_id']), r['name'], tuple(sorted(r['labels']))) for r in scopes}
    validation = {
        'eligible_population_matches': set(live_ids) == eligible,
        'eligible_rows_unique': len(live_ids) == len(set(live_ids)),
        'live_eligible_count': len(set(live_ids)),
        'frozen_eligible_count': len(eligible),
        'live_only_eligible_count': len(set(live_ids) - eligible),
        'frozen_only_eligible_count': len(eligible - set(live_ids)),
        'product_channel_memberships_match': live_scopes == frozen_scopes,
        'live_scope_count': len(live_scopes),
        'frozen_scope_count': len(frozen_scopes),
        'live_only_scope_count': len(live_scopes - frozen_scopes),
        'frozen_only_scope_count': len(frozen_scopes - live_scopes),
    }
    if not all(validation[k] for k in ('eligible_population_matches', 'eligible_rows_unique', 'product_channel_memberships_match')):
        write(args.out / 'validation_failed.json', validation)
        print(json.dumps(validation), flush=True)
        raise RuntimeError('Live structural graph does not align with frozen eligibility/scope')

    docs, source_hashes, nodes = {}, {}, {}
    corpus = landing.CORPUS.resolve()
    for label, rows in named['rows'].items():
        for row in rows:
            if row['node_id'] is None:
                raise ValueError('Structural node lacks stable ID')
            key = (label, str(row['node_id']))
            if key in nodes:
                raise ValueError('Duplicate normalized structural node ID')
            if label in ('Employee', 'Customer', 'Channel'):
                rel = named['files'].get(row['file_id'])
                if rel is None:
                    raise ValueError('Structural node points to missing File')
                path = (corpus / rel).resolve()
                if not path.is_relative_to(corpus):
                    raise ValueError('Structural File path is outside corpus root')
                if rel not in docs:
                    raw = path.read_bytes()
                    source_hashes[rel] = hashlib.sha256(raw).hexdigest()
                    docs[rel] = json.loads(raw)
                record = landing._pointer(docs[rel], row['pointer'])
                names = landing._names_of(record, label)
            else:
                if not isinstance(row['name'], str) or not row['name'].strip():
                    raise ValueError('Direct structural name is empty')
                names = [(row['name'], landing.PRODUCT if label == 'Product' else landing.COMPANY)]
            nodes[key] = {'label': label, 'node_id': key[1],
                          'names': [{'name': n, 'kind': k} for n, k in names],
                          'routes': {r: [] for r in landing.DEFAULT_ROUTES if landing.ROUTES[r][0] == label},
                          'route_counts': {}}
    route_counts = {}
    for route, rows in route_rows.items():
        label = landing.ROUTES[route][0]
        by_node = {key: set() for key in nodes if key[0] == label}
        for row in rows:
            key = (label, str(row['node']))
            if key not in by_node or row['chunk'] is None:
                raise ValueError('Route contains unknown structural node or null chunk ID')
            by_node[key].add(str(row['chunk']))
        for key, ids in by_node.items():
            nodes[key]['routes'][route] = sorted(ids & eligible)
            nodes[key]['route_counts'][route] = {'full': len(ids), 'eligible': len(ids & eligible), 'outside': len(ids - eligible)}
        route_counts[route] = {kind: sum(n['route_counts'].get(route, {}).get(kind, 0) for n in nodes.values()) for kind in ('full', 'eligible', 'outside')}
    # Detect concurrent corpus changes before committing the artifact.
    assert all(sha(corpus / rel) == digest for rel, digest in source_hashes.items())
    source_files = ('test/artefact/landing.py', 'test/graph/db.py')
    payload = {
        'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'graph_sha256': sha(graph_path), 'database': DATABASE,
        'eligible_chunk_ids': sorted(eligible),
        'nodes': [nodes[k] for k in sorted(nodes)],
        'validation': validation,
        'provenance': {
            'access_mode': 'READ', 'transaction': 'single explicit read transaction',
            'manifest_sha256': sha(manifest_path),
            'source_file_sha256': {p: sha(ROOT / p) for p in source_files},
            'capture_tool_sha256': sha(__file__),
            'corpus_file_sha256': dict(sorted(source_hashes.items())),
            'route_definitions': {r: {'label': landing.ROUTES[r][0], 'cypher': landing.ROUTES[r][1]} for r in landing.DEFAULT_ROUTES},
            'eligible_query': eligible_query, 'scope_query': scope_query,
            'parameters': params, 'node_id_normalization': 'str of original scalar ID; routes queried with original scalar',
            'legacy_name_cache_used': False,
        },
        'counts': {
            'nodes': len(nodes), 'by_label': dict(Counter(n['label'] for n in nodes.values())),
            'names': sum(len(n['names']) for n in nodes.values()),
            'nodes_without_route_definitions': sum(not n['routes'] for n in nodes.values()),
            'nodes_without_eligible_route_endpoints': sum(not any(n['routes'].values()) for n in nodes.values()),
            'corpus_files': len(source_hashes), 'routes': route_counts,
        },
    }
    write(target, payload)
    result = {'artifact': str(target), 'sha256': sha(target), 'validation': validation, 'counts': payload['counts']}
    write(args.out / 'capture_verification.json', result)
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
