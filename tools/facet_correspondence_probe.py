"""One frozen graph/query auxiliary-coordinate correspondence control."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '4'
import numpy as np
from threadpoolctl import threadpool_limits
import facet_retrieval_demo as D

ROOT, BASE, STATIC = D.ROOT, D.BASE, D.STATIC
FRESH = BASE/'fresh_smoke'
OUT = FRESH/'correspondence'
QIDS = ('independent_durable_messages_current_models',
        'sentiment_intended_use', 'sentiment_review_observations')
PERM = [0, 2, 3, 4, 1]
BETA = [1., .25, .25, .25, .25]
sys.path.insert(0, str(ROOT/'test'))
from artefact.facet_joint_candidate import freeze_reference, FrozenFacetReference
from artefact.facet_retrieval_pipeline import retrieve_prepared_query
from artefact.facet_scope_recruitment import recruit_with_verified_area


def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(gzip.decompress(p.read_bytes()))
def write(p, value):
    with p.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')
def hashes(paths): return {str(p.relative_to(ROOT)): sha(p) for p in set(paths)}
def verify(mapping):
    for name, value in mapping.items():
        if sha(ROOT/name) != value:
            raise ValueError('Frozen input changed: '+name)


def run():
    if (OUT/'manifest.json').exists():
        raise RuntimeError('Existing probe; do not repeat or overwrite')
    graph = read(STATIC/'graph.json')
    chunks, ids = graph['chunks'], graph['chunk_ids']
    assert [c['chunkId'] for c in chunks] == ids
    sm = read(STATIC/'manifest.json')
    for name in ('graph.json', 'arrays.npz'):
        assert sha(STATIC/name) == sm['output_sha256'][name]
    with np.load(STATIC/'arrays.npz', allow_pickle=False) as a:
        edge_facets, et, ec = (a[k].copy() for k in ('edge_facets', 'edge_tag', 'edge_chunk'))
    assert len(edge_facets) == 57204
    reference = freeze_reference(edge_facets)
    permuted_reference = FrozenFacetReference(tuple(reference.columns[i] for i in PERM))
    assert np.array_equal(permuted_reference.transform(edge_facets[:, PERM]),
                          reference.transform(edge_facets)[:, PERM])
    groups = defaultdict(list)
    for i, chunk in enumerate(chunks):
        for product in chunk['scope'].get('product', []):
            for channel in chunk['scope'].get('channel', []):
                groups[product['node_id'], channel['node_id']].append(i)
    pairs = D.source_adjacency(chunks, np)
    paths = [Path(__file__), Path(D.__file__), OUT/'PROTOCOL.md',
             STATIC/'manifest.json', STATIC/'graph.json', STATIC/'arrays.npz',
             ROOT/'test/arms/artefact_v3.py', BASE/'query_reconstruction/run/selection_summary.json']
    paths += [ROOT/'test/artefact'/n for n in (
        'facet_joint_candidate.py', 'facet_stream_envelope.py', 'facet_retrieval_pipeline.py',
        'facet_scope_recruitment.py', 'facet_recruitment_candidate.py', 'facet_need_frontier.py')]
    old_index = {(r['question_id'], r['reading_id']): r for r in
                 read(BASE/'query_reconstruction/run/selection_summary.json') if r['mode'] == 'max'}
    cases = []
    for origin, bundle in (('old', BASE), ('fresh', FRESH)):
        cp = bundle/'query_capture/query_captures.json'
        qm = read(bundle/'query_snapshot/manifest.json')
        assert sha(cp) == qm['completed_capture_sha256']
        for name in ('queries.json', 'arrays.npz'):
            assert sha(bundle/'query_snapshot'/name) == qm['output_sha256'][name]
        paths += [cp, *[bundle/'query_snapshot'/n for n in ('manifest.json', 'queries.json', 'arrays.npz')]]
        metadata = read(bundle/'query_snapshot/queries.json')
        assert metadata['chunk_ids'] == ids and metadata['graph_tags'] == graph['graph_tags']
        captures = {c['question_id']: c for c in read(cp)['captures']}
        with np.load(bundle/'query_snapshot/arrays.npz', allow_pickle=False) as a:
            for qid in QIDS:
                cap = captures[qid]
                assert cap['generation_validation']['ok']
                query = next(q for q in metadata['queries'] if q['id'] == cap['generation_id'])
                tags, indices = query['tags'], query['query_tag_indices']
                assert tags == cap['clean_tags'] and query['description'] == cap['description']
                for reading in sorted(cap['readings'], key=lambda r: r['repeat']):
                    assert reading['ok'] and reading['repeat'] in (0, 1)
                    by_tag = {v['t']: v['facets'] for v in reading['values']}
                    assert set(by_tag) == set(tags)
                    weights = np.array([[by_tag[t][f] for f in D.FACETS] for t in tags])
                    area, provenance, area_paths = D.frozen_area(cap, reading)
                    paths += area_paths
                    if origin == 'old':
                        row = old_index[qid, reading['id']]
                        saved_path = BASE/'query_reconstruction/run'/row['file']
                        assert sha(saved_path) == row['sha256']
                        saved = load(saved_path)
                        expected_scores = np.asarray(saved['joint_scores'])
                    else:
                        saved_path = FRESH/'retrieval'/reading['id']/'retrieval.json'
                        saved = read(saved_path)
                        ap = saved_path.parent/'ranking_arrays.npz'
                        assert sha(ap) == saved['ranking_arrays_sha256']
                        with np.load(ap, allow_pickle=False) as aa:
                            assert aa['chunk_ids'].tolist() == ids
                            expected_scores = aa['scores'].copy()
                        paths.append(ap)
                    paths.append(saved_path)
                    cases.append(dict(origin=origin, question_id=qid, reading_id=reading['id'],
                        repeat=reading['repeat'], tags=tags, weights=weights, area=area,
                        area_provenance=provenance, expected_scores=expected_scores,
                        expected_recruitment=saved['recruitment'],
                        M=a['query_tag_graph_cos'][indices].copy(),
                        D=a['query_tag_chunk_cos'][indices].copy(),
                        Q=a['description_chunk_cos'][query['description_index']].copy()))
    assert len(cases) == 12 and len({(c['origin'], c['reading_id']) for c in cases}) == 12
    frozen = hashes(paths)
    write(OUT/'manifest.json', {'input_sha256': frozen, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'permutation_new_column_from_old': PERM, 'facets': list(D.FACETS), 'beta': BETA,
        'budget': 72000, 'reference_edges': len(edge_facets), 'cpu_threads': 4,
        'cases': [{k: c[k] for k in ('origin', 'question_id', 'reading_id', 'repeat', 'tags', 'area')}
                  for c in cases], 'label_join_policy': 'Numerical outputs frozen before support labels are read.'})
    results = []
    with threadpool_limits(limits=4):
        for case in cases:
            baseline = None
            for condition in ('baseline', 'joint_symmetry', 'graph_only'):
                permuted = condition != 'baseline'
                weights = case['weights'][:, PERM] if condition == 'joint_symmetry' else case['weights']
                started = time.perf_counter()
                result = retrieve_prepared_query(chunk_rows=chunks, coefficients=BETA,
                    source_character_budget=72000, query_tag_ids=case['tags'], edge_ids=graph['edge_ids'],
                    edge_tag_indices=et, edge_chunk_indices=ec,
                    edge_facets=edge_facets[:, PERM] if permuted else edge_facets,
                    query_facet_weights=weights, query_tag_cosines=case['M'], query_chunk_cosines=case['D'],
                    query_description_cosines=case['Q'], reference=permuted_reference if permuted else reference,
                    groups={'shared_product_channel': list(groups.values())}, adjacency_pairs=pairs)
                ranking = result['ranking']
                rec = recruit_with_verified_area(chunk_rows=chunks, joint_scores=ranking['scores'],
                    area_chunk_ids=case['area'], area_provenance=case['area_provenance'],
                    source_character_budget=72000)['recruitment']
                if condition == 'baseline':
                    error = float(np.max(np.abs(ranking['scores']-case['expected_scores'])))
                    assert error < 1e-12 and rec == case['expected_recruitment']
                    baseline = (ranking['scores'].copy(), ranking['per_facet_scores'].copy(), rec)
                elif condition == 'joint_symmetry':
                    error = float(np.max(np.abs(ranking['scores']-baseline[0])))
                    assert error < 1e-12 and rec == baseline[2]
                    assert np.array_equal(ranking['per_facet_scores'], baseline[1][:, PERM])
                else:
                    error = None
                stem = case['origin']+'__'+case['reading_id']+'__'+condition
                np.savez_compressed(OUT/(stem+'.npz'), chunk_ids=ids, scores=ranking['scores'],
                    per_facet_scores=ranking['per_facet_scores'], query_facet_weights=weights)
                payload = {k: case[k] for k in ('origin', 'question_id', 'reading_id', 'repeat', 'tags', 'area')}
                payload.update(condition=condition, recruitment=rec, ranking_rows=ranking['rows'],
                    score_control_max_abs_error=error, seconds=time.perf_counter()-started)
                with (OUT/(stem+'.json.gz')).open('xb') as f:
                    f.write(gzip.compress(json.dumps(payload, separators=(',', ':'), allow_nan=False).encode(), mtime=0))
                results.append({k: payload[k] for k in ('origin', 'question_id', 'reading_id', 'repeat',
                    'condition', 'score_control_max_abs_error', 'seconds')} | {'file': stem+'.json.gz',
                    'arrays': stem+'.npz', 'sha256': sha(OUT/(stem+'.json.gz')),
                    'arrays_sha256': sha(OUT/(stem+'.npz'))})
                print(stem, 'complete', flush=True)
    verify(frozen)
    assert len(results) == 36
    write(OUT/'numerical_outputs.json', {'input_sha256': frozen, 'runs': results,
        'baseline_controls_exact': 12, 'symmetry_recruitment_controls_exact': 12,
        'symmetry_score_tolerance': 1e-12, 'frozen_before_label_join': True})


def join():
    # Only this separate post-output phase reads existing support judgments.
    numerical_path = OUT/'numerical_outputs.json'
    numerical = read(numerical_path)
    verify(numerical['input_sha256'])
    assert len(numerical['runs']) == 36
    for r in numerical['runs']:
        assert sha(OUT/r['file']) == r['sha256'] and sha(OUT/r['arrays']) == r['arrays_sha256']
    graph = read(STATIC/'graph.json')
    chunks = {c['chunkId']: c for c in graph['chunks']}
    sizes = {cid: len(c['source_text']) for cid, c in chunks.items()}
    paths = [numerical_path, OUT/'manifest.json', OUT/'PROTOCOL.md', Path(__file__), STATIC/'graph.json']
    support, pools, events = {}, {}, {}
    action, sent = BASE/'need_selection/content_audit', BASE/'crossed_content'
    prior = BASE/'query_interpretation_intervention/content_cost.json'
    paths.append(prior)
    expected = read(prior)['input_sha256']
    action_paths = [action/'private_manifest.json', action/'record_context_probe.json']
    action_paths += [action/(r+s+'.json') for r in ('reader_one', 'reader_two') for s in ('', '_additional')]
    for p in action_paths:
        assert sha(p) == expected[str(p.relative_to(ROOT))]
    paths += action_paths
    aliases = read(action_paths[0])['aliases'] | read(action_paths[1])['additional_reader_aliases']
    support[QIDS[0]] = {}
    quote_counts = {}
    for reader in ('reader_one', 'reader_two'):
        entries = {e['passage_id']: e for suffix in ('', '_additional')
                   for e in read(action/(reader+suffix+'.json'))['entries']}
        assert set(entries) == set(aliases.values())
        support[QIDS[0]][reader] = {comp: {cid for cid, alias in aliases.items()
            if entries[alias]['scope'] == 'supports_requested_system'
            and entries[alias]['components'][comp]['category'] == 'direct'}
            for comp in ('durability', 'model_updates', 'refresh_frequency')}
        quotes = [q for cid, alias in aliases.items() for v in entries[alias]['components'].values()
                  for q in v['quotes'] if isinstance(q, str) and q and q in chunks[cid]['source_text']]
        assert len(quotes) == sum(len(v['quotes']) for e in entries.values() for v in e['components'].values())
        quote_counts[reader] = len(quotes)
    pools[QIDS[0]] = set(aliases)
    for p, key_path in ((sent/'join.json', ('input_sha256',)),
                        (sent/'verification.json', ('supplement', 'input_sha256'))):
        paths.append(p)
        expected = read(p)
        for key in key_path: expected = expected[key]
        verify(expected)
    paths += [sent/'private_manifest.json', sent/'supplement_manifest.json']
    aliases = read(sent/'private_manifest.json')['aliases'] | read(sent/'supplement_manifest.json')['aliases']
    reverse = {alias: cid for cid, alias in aliases.items()}
    sentiment_readers = {}
    for reader in ('reader_a', 'reader_b'):
        reader_paths = [sent/(reader+s+'.json') for s in ('', '_supplement')]
        paths += reader_paths
        entries = {e['passage_id']: e for p in reader_paths for e in read(p)['entries']}
        assert set(entries) == set(aliases.values())
        for cid, alias in aliases.items():
            for v in entries[alias]['components'].values():
                assert all(isinstance(q, str) and q and q in chunks[cid]['source_text'] for q in v['quotes'])
        quote_counts[reader] = sum(len(v['quotes']) for e in entries.values() for v in e['components'].values())
        sentiment_readers[reader] = entries
    for qid, comps in ((QIDS[1], ('offering', 'tailoring')),
                       (QIDS[2], ('accuracy', 'tests', 'documentation'))):
        support[qid] = {reader: {comp: {cid for cid, alias in aliases.items()
            if entries[alias]['components'][comp]['scope'] == 'supported'
            and entries[alias]['components'][comp]['category'] == 'direct'} for comp in comps}
            for reader, entries in sentiment_readers.items()}
        pools[qid] = set(aliases)
        events[qid] = {'PR6': {reverse['item_048'], reverse['item_060']}, 'PR10': {reverse['item_058']}}
    for readers in support.values():
        a, b = list(readers.values())
        readers['intersection'] = {c: a[c] & b[c] for c in a}
    frozen = hashes(paths)
    rows = []
    baselines = {}
    for run in numerical['runs']:
        d = load(OUT/run['file'])
        rec, qid = d['recruitment'], d['question_id']
        chosen = set(rec['selected_chunk_ids'])
        cumulative, costs, prefix, crossed = 0, {}, set(), False
        for frontier in rec['frontiers']:
            cumulative += sum(sizes[c] for c in frontier['chunk_ids'])
            assert cumulative == frontier['cumulative_source_characters']
            costs.update({cid: cumulative for cid in frontier['chunk_ids']})
            if cumulative > 72000: crossed = True
            if not crossed: prefix.update(frontier['chunk_ids'])
        assert chosen == prefix
        reader_results = {}
        for reader, comps in support[qid].items():
            details = {}
            for comp, witnesses in comps.items():
                finite = {cid: costs[cid] for cid in witnesses if cid in costs}
                minimum = min(finite.values()) if finite else None
                details[comp] = {'selected_witness_ids': sorted(chosen & witnesses),
                    'known_acquisition_cost': minimum,
                    'first_known_witness_ids': sorted(cid for cid, value in finite.items() if value == minimum)}
            minima = [x['known_acquisition_cost'] for x in details.values()]
            reader_results[reader] = {'components': details,
                'all_components_selected': all(x['selected_witness_ids'] for x in details.values()),
                'known_complete_acquisition_cost': max(minima) if all(x is not None for x in minima) else None}
        key = d['origin'], d['reading_id']
        if d['condition'] == 'baseline': baselines[key] = chosen
        baseline = baselines[key]
        rows.append({k: d[k] for k in ('origin', 'question_id', 'reading_id', 'repeat', 'condition')} | {
            'readers': reader_results, 'events': {event: {'selected': bool(chosen & witnesses),
                'selected_witness_ids': sorted(chosen & witnesses),
                'known_acquisition_cost': min((costs[c] for c in witnesses if c in costs), default=None)}
                for event, witnesses in events.get(qid, {}).items()},
            'selected_chunks': len(chosen), 'selected_source_characters': rec['selected_source_characters'],
            'unjudged_selected_chunk_ids': sorted(chosen-pools[qid]),
            'added_vs_baseline': sorted(chosen-baseline), 'removed_vs_baseline': sorted(baseline-chosen)})
    verify(frozen)
    write(OUT/'joined.json', {'input_sha256': frozen, 'quote_occurrences': quote_counts, 'runs': rows,
        'limits': 'One fixed correspondence control on inspected development inputs. No calibrated semantics, human gold, permutation search or generalization estimate. Unjudged content remains unknown.'})
    for row in rows:
        if row['condition'] == 'joint_symmetry': continue
        print(json.dumps({k: row[k] for k in ('origin', 'question_id', 'repeat', 'condition')} | {
            'cost': row['readers']['intersection']['known_complete_acquisition_cost'],
            'covered': row['readers']['intersection']['all_components_selected'], 'events': row['events'],
            'unjudged': len(row['unjudged_selected_chunk_ids'])}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'join'))
    args = parser.parse_args()
    {'run': run, 'join': join}[args.action]()
