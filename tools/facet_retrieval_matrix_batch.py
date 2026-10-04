"""Exhaustive declared retrieval matrix; inputs frozen, outcomes joined afterward."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import facet_retrieval_lab as L
import numpy as np

OUT = L.BASE / 'batch'
METRICS = ['recall_id', 'precision_id', 'hits', 'gold_count', 'retrieved_ids', 'delivered_chars', 'full_chunks']
_lab = None


def initialize():
    global _lab
    _lab = L.Lab()


def freeze():
    configurations = list(L.policies())
    paths = [Path(__file__), Path(L.__file__), L.ROOT / 'test/artefact/facet_operator_matrix.py',
             L.INPUTS / 'cases_manifest.json', L.POINTERS / 'gold_source_index.json',
             L.POINTERS / 'chunk_delivery_index.json']
    # Dependency hashes bind this numerical implementation to the validated sources.
    paths += [L.ROOT / p for p in L.A.SMOKE_PROVENANCE_PATHS]
    plan = {'created_utc': datetime.now(timezone.utc).isoformat(),
            'configurations': configurations, 'configuration_count': len(configurations),
            'input_sha256': {str(p.relative_to(L.ROOT)): L.digest(p) for p in dict.fromkeys(paths)},
            'question_population': 'All 95 successful saved queries: smoke10 plus remaining85; five original failures retained.',
            'score_contract': 'Fixed query readings, graph, CDF, coefficients and 0.5 hop discount. Only declared composition operators vary.',
            'matrix': '6400 complete factorial combinations plus 3840 lexical-order conditions at canonical product/both/union routes.',
            'scope_contract': 'Saved resolved areas fixed. area_only excludes outside even after recovery; unresolved area preserves global fallback.',
            'gold_join': 'Ordering and actual 72000-character prefix are fixed before consulting reference source IDs.',
            'metrics': METRICS, 'metric_implementation': 'Exact set-intersection formula; crosschecked against installed RAGAS ID metrics.',
            'output': 'All per-condition per-case metrics and order equivalence classes retained. Live app recomputes pointer movements from same inputs.',
            'interpretation': 'Exploratory mechanism comparison on reused cases, not coefficient training or independent validation.',
            'language_model_calls': 0}
    if (OUT / 'plan.json').exists():
        old = L.read(OUT / 'plan.json')
        assert old['configurations'] == configurations and old['input_sha256'] == plan['input_sha256']
        return old
    L.write_new(OUT / 'plan.json', plan)
    return plan


def run_case(case_id):
    start = time.perf_counter()
    case = _lab.case(case_id)
    configurations = list(L.policies())
    expected = np.asarray(case['meta']['expected_scores'])
    from artefact.facet_scope_recruitment import recruit_with_verified_area
    parity = {}
    for scope in ('equal_depth', 'area_first'):
        reference = recruit_with_verified_area(chunk_rows=_lab.prepared.chunks, joint_scores=expected,
            area_chunk_ids=case['meta']['area']['chunk_ids'], source_character_budget=None, scheduling=scope)
        candidate = _lab.retrieve(case, {**L.DEFAULT, 'scope': scope})
        assert [_lab.ids[i] for i in candidate['order']] == reference['recruitment']['selected_chunk_ids'], 'Actual helper order mismatch'
        parity[scope] = True
    data = np.empty((len(configurations), len(METRICS)), dtype=float)
    order_classes = np.empty(len(configurations), dtype=np.int32)
    classes = {}
    reference_credit = set(case['meta']['baseline_context_ids'])
    for i, policy in enumerate(configurations):
        result = _lab.retrieve(case, policy)
        # Fingerprint full order, not just its gold hits or delivered set.
        order_hash = hashlib.sha256(result['order'].astype('<i4').tobytes()).hexdigest()
        if order_hash not in classes:
            classes[order_hash] = len(classes)
        order_classes[i] = classes[order_hash]
        metrics = _lab.evaluate(case, result)
        data[i] = [np.nan if metrics[k] is None else metrics[k] for k in METRICS]
    npz = OUT / (case_id + '.npz')
    with npz.open('xb') as stream:
        np.savez_compressed(stream, metrics=data, order_classes=order_classes)
    meta = {'case_id': case_id, 'question_id': case['meta']['question_id'], 'cohort': case['cohort'],
            'configurations': len(configurations), 'distinct_full_orders': len(classes),
            'score_parity_error': case['score_parity_error'], 'current_helper_order_parity': parity,
            'input_meta_sha256': L.digest(L.INPUTS / (case_id + '.json')),
            'input_npz_sha256': case['meta']['npz_sha256'], 'npz_sha256': L.digest(npz),
            'elapsed_s': time.perf_counter() - start, 'language_model_calls': 0}
    L.write_new(OUT / (case_id + '.json'), meta)
    return {k: meta[k] for k in ('case_id', 'configurations', 'distinct_full_orders', 'elapsed_s')}


def summarize(plan):
    manifest = L.read(L.INPUTS / 'cases_manifest.json')
    records = [c for c in manifest['cases'] if (OUT / (c['case_id'] + '.json')).exists()]
    if not records:
        return None
    stacks, cohorts = [], []
    for record in records:
        with np.load(OUT / (record['case_id'] + '.npz'), allow_pickle=False) as arrays:
            stacks.append(arrays['metrics'])
        cohorts.append(record['cohort'])
    values = np.asarray(stacks)
    policies = plan['configurations']
    default_index = next(i for i, p in enumerate(policies) if p == L.DEFAULT)
    means = np.nanmean(values, axis=0)
    conditions = []
    for i, policy in enumerate(policies):
        delta = values[:, i, 0] - values[:, default_index, 0]
        conditions.append({'condition': i, 'policy': policy,
            'recall_id': float(means[i, 0]),
            'precision_id': float(means[i, 1]) if np.isfinite(means[i, 1]) else None,
            'recall_better': int((delta > 0).sum()), 'recall_worse': int((delta < 0).sum()),
            'recall_tied': int((delta == 0).sum())})
    # Full table is retained. Ordered listing is descriptive, never promoted automatically.
    ordered = sorted(conditions, key=lambda c: (-c['recall_id'], -(c['precision_id'] or 0), c['condition']))
    cohorts_out = {}
    for cohort in sorted(set(cohorts)):
        subset = values[np.asarray(cohorts) == cohort]
        avg = np.nanmean(subset, axis=0)
        cohorts_out[cohort] = {'cases': len(subset), 'canonical_recall_id': float(avg[default_index, 0]),
            'canonical_precision_id': float(avg[default_index, 1]),
            'recall_range': [float(np.nanmin(avg[:, 0])), float(np.nanmax(avg[:, 0]))]}
    report = {'status': 'complete' if len(records) == manifest['expected_cases'] else 'partial',
        'completed_cases': len(records), 'expected_cases': manifest['expected_cases'],
        'configurations_per_case': len(policies), 'retrievals_completed': len(records) * len(policies),
        'canonical': conditions[default_index], 'top_by_id_recall': ordered[:20],
        'all_conditions': conditions, 'cohorts': cohorts_out,
        'failed_original_cases': len(manifest['failed_question_ids']),
        'limits': 'Reused data, exploratory comparisons; score ranking is not independent semantic validation. Precision may be undefined for empty retrieval.'}
    L.atomic(OUT / 'summary.json', report)
    return report


def main(workers):
    plan = freeze()
    manifest = L.read(L.INPUTS / 'cases_manifest.json')
    pending = [c for c in manifest['cases'] if not (OUT / (c['case_id'] + '.json')).exists()]
    errors = []
    L.write_new(OUT / ('launch-' + str(os.getpid()) + '.json'), {'pid': os.getpid(), 'workers': workers, 'pending': len(pending)})
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers, initializer=initialize) as pool:
        active = {}
        while pending or active:
            ready = [c for c in pending if (L.INPUTS / c['meta']).exists()]
            for record in ready[:max(0, workers - len(active))]:
                pending.remove(record)
                active[pool.submit(run_case, record['case_id'])] = record
            if active:
                done, _ = wait(active, timeout=10, return_when=FIRST_COMPLETED)
                for future in done:
                    record = active.pop(future)
                    try:
                        result = future.result()
                        print(json.dumps({'phase': 'case_completed', **result}), flush=True)
                    except Exception as exc:
                        errors.append({'case_id': record['case_id'], 'error': str(exc)})
                        print(json.dumps({'phase': 'case_error', **errors[-1]}), flush=True)
                if done:
                    summarize(plan)
            else:
                # Input capture is a separate verified process; never regenerate here.
                time.sleep(5)
            completed = len(manifest['cases']) - len(pending) - len(active) - len(errors)
            L.atomic(OUT / 'status.json', {'status': 'running', 'completed_cases': completed,
                'expected_cases': manifest['expected_cases'], 'active_cases': [r['case_id'] for r in active.values()],
                'waiting_input_cases': len(pending), 'errors': errors, 'elapsed_s': time.perf_counter() - started,
                'configurations_per_case': len(plan['configurations'])})
    for path, expected in plan['input_sha256'].items():
        assert L.digest(L.ROOT / path) == expected, 'Frozen source changed: ' + path
    result = summarize(plan)
    L.write_new(OUT / 'completed.json', {'status': 'completed_with_errors' if errors else 'completed',
        'errors': errors, 'elapsed_s': time.perf_counter() - started, 'source_hashes_unchanged': True})
    L.atomic(OUT / 'status.json', {k: v for k, v in L.read(OUT / 'completed.json').items()})
    print(json.dumps({'phase': 'completed', 'errors': errors,
                      'completed_cases': result['completed_cases'] if result else 0}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError('Use one to four CPU workers')
    main(args.workers)
