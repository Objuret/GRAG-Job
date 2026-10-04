"""Read-only structure landing/reach capture for two frozen diagnostic questions.

Check the existing name cache against graph corpus provenance and node IDs.
A corpus-hash mismatch is retained on every cached-name diagnostic, never
treated as freshly verified names. Never invoke the corpus-parsing refresh.
The existing intersection policy is recorded, not endorsed as the joint rule.
"""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from dataclasses import asdict
from collections import Counter
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
BASE = ROOT / 'output/research/2026-09-21-facet-validity'
OUT = ROOT / 'output/research/2026-09-22-joint-streams/structure'
DATABASE = 'herb-eval-volmax'
DATASET = 'Salesforce__HERB'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, body):
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def graph_tree_digest(files):
    rows = sorted(files, key=lambda r: PurePosixPath(r['rel_path']).relative_to(DATASET).as_posix())
    h = hashlib.sha256()
    for row in rows:
        rel = PurePosixPath(row['rel_path']).relative_to(DATASET).as_posix()
        h.update(rel.encode('utf-8'))
        h.update(b'\0')
        h.update(row['sha256'].encode('utf-8'))
        h.update(b'\n')
    return {'sha256': h.hexdigest(), 'n_files': len(rows)}


class RecordedSession:
    def __init__(self, session):
        self.session, self.calls = session, []

    def run(self, cypher, **params):
        rows = [dict(r) for r in self.session.run(cypher, **params)]
        self.calls.append({'cypher': cypher, 'parameters': params, 'rows': rows})
        return rows


def main():
    print('Capturing existing structure landings and graph paths: READ only, no models', flush=True)
    from artefact import landing
    from graph.db import _driver
    graph_path = BASE / 'route_snapshot/graph.json'
    graph = read(graph_path)
    eligible = set(graph['chunk_ids'])
    cache_path = ROOT / 'output/landing_names.json'
    cache = read(cache_path)
    cached = [landing.Landing(**row) for row in cache['landings']]
    questions = list(dict.fromkeys(q['question'] for q in graph['queries']))
    if len(questions) != 2:
        raise ValueError('This capture is limited to the two existing raw questions')
    OUT.mkdir(parents=True, exist_ok=True)
    with _driver() as driver:
        with driver.session(database=DATABASE, default_access_mode='READ') as session:
            live = landing._read_nodes(session)
            files = [dict(r) for r in session.run(
                'MATCH (f:File) WHERE f.dataset_id=$dataset RETURN f.file_id AS file_id, '
                'f.rel_path AS rel_path,f.sha256 AS sha256 ORDER BY rel_path', dataset=DATASET)]
            recorded_tree = graph_tree_digest(files)
            errors = []
            for name, expected in [('database', DATABASE), ('dataset_id', DATASET),
                                   ('corpus_sha256', recorded_tree['sha256']), ('n_files', recorded_tree['n_files'])]:
                if cache.get(name) != expected:
                    errors.append({'field': name, 'cached': cache.get(name), 'live_graph_recorded': expected})
            live_ids = {(label, row['node_id']) for label, rows in live['rows'].items() for row in rows}
            cache_ids = {(l.label, l.node_id) for l in cached}
            missing_live = sorted(cache_ids - live_ids)
            uncached_live = sorted(live_ids - cache_ids)
            if missing_live or uncached_live:
                errors.append({'cached_nodes_missing_live': missing_live, 'live_nodes_missing_cache': uncached_live})
            # Product/company names are available directly in the graph. Names
            # behind pointers are accepted only under the verified cached corpus hash.
            direct = {(label, r['node_id']): r['name'] for label in ('Product', 'Company') for r in live['rows'][label]}
            bad_direct = [asdict(l) for l in cached if (l.label, l.node_id) in direct and l.name != direct[l.label, l.node_id]]
            if bad_direct:
                errors.append({'direct_graph_name_mismatches': bad_direct})
            verification = {'cache_path': str(cache_path), 'cache_sha256': sha(cache_path),
                'cache_metadata': {k: v for k, v in cache.items() if k != 'landings'},
                'live_graph_recorded_tree': recorded_tree, 'graph_file_hashes': files,
                'cached_names': len(cached), 'cached_nodes': len(cache_ids), 'live_nodes': len(live_ids),
                'errors': errors, 'verified_against_graph_recorded_corpus': not errors,
                'source_files_opened': False, 'cache_refresh_called': False,
                'limitation': 'Graph File hashes verify the corpus version recorded by Neo4j; this does not rehash current raw files. No raw corpus files or benchmark sections are opened.'}
            write(OUT / 'name_cache_verification.json', verification)
            if any(error.get('field') != 'corpus_sha256' for error in errors):
                write(OUT / 'capture.json', {'status': 'unavailable_name_cache_mismatch', 'questions': questions,
                    'errors': errors, 'no_fallback': 'No whole-file corpus parsing or invented product mapping.'})
                print('Name-cache provenance mismatch captured; no replacement names invented', flush=True)
                return
            if errors:
                print('Corpus hash mismatch: retaining explicitly unverified cached-name diagnostics', flush=True)
            results = []
            for qi, question in enumerate(questions):
                hits = landing.land(question, cached)
                recorder = RecordedSession(session)
                reached = landing.areas(recorder, hits)
                combined = landing.combine(reached, hits)
                by_node = []
                for key in sorted({(h.label, h.node_id) for h in hits}):
                    chunks = set(reached.by_node.get(key, ()))
                    by_node.append({'label': key[0], 'node_id': key[1], 'chunks_all': sorted(chunks),
                        'chunks_eligible': sorted(chunks & eligible), 'chunks_outside_snapshot': sorted(chunks - eligible)})
                by_name = []
                if combined is not None:
                    for name, chunks in sorted(combined.landings.items()):
                        by_name.append({'kind': name[0], 'name': name[1], 'nodes': [list(x) for x in combined.nodes[name]],
                            'chunks_all': sorted(chunks), 'chunks_eligible': sorted(chunks & eligible),
                            'chunks_outside_snapshot': sorted(chunks - eligible)})
                all_union = set(reached.by_chunk)
                meet = None if combined is None else set(combined.chunks)
                row = {'question_index': qi, 'question': question,
                    'name_source_status': 'unverified_corpus_hash_mismatch' if errors else 'graph_recorded_corpus_verified',
                    'capture_ids': [q['id'] for q in graph['queries'] if q['question'] == question],
                    'hits': [asdict(h) for h in hits], 'by_node': by_node, 'by_name': by_name,
                    'route_calls': recorder.calls,
                    'route_counts': [{'route': r, 'node_id': n, 'chunk_count': count} for (r, n), count in sorted(reached.by_route.items())],
                    'union_area_all': sorted(all_union), 'union_area_eligible': sorted(all_union & eligible),
                    'combined_area_all': None if meet is None else sorted(meet),
                    'combined_area_eligible': None if meet is None else sorted(meet & eligible),
                    'unmet_landings': [] if combined is None else [list(x) for x in combined.unmet],
                    'by_chunk': [{'chunk_id': cid, 'landed_nodes': [list(x) for x in sorted(nodes)],
                                  'eligible': cid in eligible} for cid, nodes in sorted(reached.by_chunk.items())],
                    'status': 'no_landings' if not hits else 'empty_intersection' if not meet else 'nonempty_intersection',
                    'unresolved_is_not_global_scope': True}
                results.append(row)
                print(f'Question {qi}: {len(hits)} hits, {len(all_union)} union chunks, ' +
                      ('no area' if meet is None else str(len(meet)) + ' intersection chunks'), flush=True)
    write(OUT / 'landings.json', {'source_cache_sha256': sha(cache_path), 'landings': [asdict(l) for l in cached]})
    output = {'protocol': __doc__, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'captured_with_name_cache_provenance_mismatch' if errors else 'captured',
        'name_source_errors': errors,
        'database': DATABASE, 'dataset_id': DATASET, 'eligible_chunk_count': len(eligible),
        'results': results, 'default_routes': list(landing.DEFAULT_ROUTES),
        'path_templates': {name: {'node_label': label, 'cypher': query, 'used_by_default': name in landing.DEFAULT_ROUTES}
                           for name, (label, query) in landing.ROUTES.items()},
        'existing_combine_policy': 'Union across nodes for the same (kind,lowercase name); intersection across distinct landing groups. No hits means None; an empty intersection remains empty.',
        'policy_status': 'Captured existing implementation, not asserted as intended joint-stream combination.',
        'artefact_scope_observation': {'source': 'test/arms/artefact_scope.py:262-328',
            'reads_product_from': 'plan.gate.product, not raw question or graph landing',
            'scope_mask': 'Exact products/<product>.json filename match',
            'missing_product': 'No in_scope chunks; tiers then distinguish tag area from remainder.',
            'this_capture': 'No gate synthesized. Existing land/areas/combine evaluated independently on raw questions.'},
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), graph_path, cache_path,
                           ROOT / 'test/artefact/landing.py', ROOT / 'test/arms/artefact_scope.py']},
        'limits': ['Structure names are from the existing name cache; its corpus provenance status is explicit, not assumed.',
            'Only default path templates execute; optional product_kind template is recorded but not enabled.',
            'No inferred WorkFlowGenie gate, no alias generation, no new matching threshold.',
            'An absent landing measures this resolver on these questions, not absence of useful graph structure.']}
    write(OUT / 'capture.json', output)
    print('Structure capture complete: ' + str(OUT), flush=True)


if __name__ == '__main__':
    main()
