"""Portable cached retrieval CLI; no model inference or database calls.

All new runs live under output/research/retrieval-harness-runs/NAME. Completed
case-by-policy shards are immutable and verified on resume. If a process dies
with writer.lock present, verify that recorded PID is no longer running before
manually removing that lock; this CLI never guesses that a lock is stale.
The live server displays the existing laboratory, not these new run reports.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile

import numpy as np

with contextlib.redirect_stdout(sys.stderr):
    import facet_retrieval_lab as L
    from facet_weighted_lab import WeightedLab, coefficients, DEFAULT_COEFFICIENTS

RUNS = L.ROOT / 'output/research/retrieval-harness-runs'
METRICS = ('recall_id', 'precision_id', 'f1_id')
_lab = None
_checked_cases = set()


def run_path(name):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name or ''):
        raise ValueError('Run name must be one lowercase name, using letters, digits, underscores or hyphens')
    if name in {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}:
        raise ValueError('Reserved Windows run name')
    parent = RUNS.resolve()
    path = (parent / name).resolve()
    if path.parent != parent:
        raise ValueError('Run directory must stay directly inside the harness run root')
    return path


def atomic_json(path, value):
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.json.partial')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def verify_sources(plan):
    runtime = {'python': sys.version.split()[0], 'implementation': sys.implementation.name, 'numpy': np.__version__}
    if plan['runtime'] != runtime:
        raise ValueError('Python or NumPy runtime differs from initialized plan')
    for name, expected in plan['input_sha256'].items():
        if L.digest(Path(name)) != expected:
            raise ValueError('Frozen input changed: ' + name)


def load_plan(name):
    out = run_path(name)
    plan = L.read(out / 'plan.json')
    seal = L.read(out / 'plan.sha256.json')
    if L.digest(out / 'plan.json') != seal['sha256']:
        raise ValueError('Run plan hash differs from its initialization seal')
    return out, plan


def _validate_policy(raw):
    if not isinstance(raw, dict) or set(raw) != set(L.FACTORS):
        raise ValueError('Each explicit policy must contain exactly every factor')
    return L.Lab.validate(None, raw)


def normalize_spec(spec):
    allowed = {'case_ids', 'policies', 'policy_filters', 'coefficients', 'coefficient_grid'}
    if not isinstance(spec, dict) or set(spec) - allowed:
        raise ValueError('Unknown or invalid specification fields')
    if ('policies' in spec) == ('policy_filters' in spec):
        raise ValueError('Supply exactly one of policies or policy_filters')
    if 'coefficients' in spec and 'coefficient_grid' in spec:
        raise ValueError('coefficients and coefficient_grid are mutually exclusive')
    extra_paths = []
    if 'policies' in spec:
        if not isinstance(spec['policies'], list):
            raise ValueError('policies must be a nonempty list')
        policies = [_validate_policy(p) for p in spec['policies']]
    else:
        filters = spec['policy_filters']
        if not isinstance(filters, dict) or set(filters) - set(L.FACTORS):
            raise ValueError('Unknown policy filter')
        for factor, values in filters.items():
            allowed_values = L.FACTORS[factor] + (L.LEXICAL if factor == 'facet' else [])
            if not isinstance(values, list) or not values or any(v not in allowed_values for v in values):
                raise ValueError('Invalid allowed values for policy filter ' + factor)
        policies = [p for p in L.policies() if all(p[k] in values for k, values in filters.items())]
    if not policies or len({L.policy_key(p) for p in policies}) != len(policies):
        raise ValueError('Policies must be nonempty and distinct')
    if 'coefficient_grid' in spec:
        if spec['coefficient_grid'] != 'recorded_509':
            raise ValueError('Only coefficient_grid recorded_509 is supported')
        grid_path = L.BASE / 'weights/plan.json'
        raw_betas = [v['coefficients'] for v in L.read(grid_path)['vectors']]
        extra_paths.append(grid_path)
        if len(raw_betas) != 509:
            raise ValueError('Recorded coefficient grid no longer has 509 vectors')
    else:
        raw_betas = spec.get('coefficients', [DEFAULT_COEFFICIENTS.tolist()])
    if not isinstance(raw_betas, list) or not raw_betas:
        raise ValueError('coefficients must be a nonempty list of vectors')
    if any(not isinstance(v, list) or len(v) != 5 or
           any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in v)
           for v in raw_betas):
        raise ValueError('Each coefficient vector must contain exactly five JSON numbers')
    betas = [coefficients(v, {'facet': 'separate_facet_sum'}).tolist() for v in raw_betas]
    if len({tuple(v) for v in betas}) != len(betas):
        raise ValueError('Coefficient vectors must be distinct')
    if any(p['facet'] != 'separate_facet_sum' for p in policies) and any(not np.array_equal(b, DEFAULT_COEFFICIENTS) for b in betas):
        raise ValueError('Every policy must use separate_facet_sum when custom coefficients are supplied; no combinations are silently skipped')
    manifest = L.read(L.INPUTS / 'cases_manifest.json')
    known = {c['case_id']: c for c in manifest['cases']}
    selected = spec.get('case_ids', list(known))
    if not isinstance(selected, list) or not selected or any(not isinstance(c, str) or c not in known for c in selected):
        raise ValueError('case_ids must be a nonempty list of captured case IDs')
    if len(set(selected)) != len(selected):
        raise ValueError('case_ids must be distinct')
    return [known[c] for c in selected], policies, betas, extra_paths


def initialize_run(name, spec_path):
    out = run_path(name)
    if out.exists():
        raise FileExistsError('Run directory already exists; choose a new name or resume it')
    spec_path = Path(spec_path).resolve()
    spec = L.read(spec_path)
    cases, policies, betas, extras = normalize_spec(spec)
    files = {Path(__file__).resolve(), Path(L.__file__).resolve(), spec_path,
             L.ROOT / 'tools/facet_weighted_lab.py', L.ROOT / 'tools/facet_gold90_stage_budget.py',
             L.ROOT / 'test/artefact/facet_operator_matrix.py', L.INPUTS / 'cases_manifest.json',
             L.POINTERS / 'chunk_delivery_index.json', L.POINTERS / 'gold_source_index.json',
             L.POINTERS / 'verification.json'}
    files.update(L.ROOT / p for p in L.A.SMOKE_PROVENANCE_PATHS)
    files.update(extras)
    for case in cases:
        metadata_path, numeric_path = L.INPUTS / case['meta'], L.INPUTS / case['npz']
        if L.digest(numeric_path) != L.read(metadata_path)['npz_sha256']:
            raise ValueError('Captured numerical input does not match completion marker')
        files.update((metadata_path, numeric_path))
    manifest = L.read(L.INPUTS / 'cases_manifest.json')
    plan = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
            'run': name, 'spec': spec, 'case_ids': [c['case_id'] for c in cases], 'cases': cases,
            'runtime': {'python': sys.version.split()[0], 'implementation': sys.implementation.name, 'numpy': np.__version__},
            'policies': policies, 'coefficients': betas, 'metrics': list(METRICS),
            'expected_shards': len(cases) * len(policies),
            'expected_retrievals': len(cases) * len(policies) * len(betas),
            'original_failed_question_ids': manifest.get('failed_question_ids', []),
            'input_sha256': {str(p.resolve()): L.digest(p) for p in sorted(files)},
            'language_model_calls': 0, 'database_calls': 0,
            'contract': 'Cached frozen query readings and graph. Retrieve and cut before reference-ID evaluation. Macro metrics on selected successful captured cases only; original failed cases recorded separately.',
            'lock_recovery': 'If writer.lock survives a crash, confirm its recorded host/PID is not running before manually removing the lock. No automatic stale-lock recovery.',
            'scope': 'Only named finite operator and coefficient combinations; exploratory reused cases, not held-out validation.'}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()
    (out / 'shards').mkdir()
    atomic_json(out / 'plan.json', plan)
    atomic_json(out / 'plan.sha256.json', {'sha256': L.digest(out / 'plan.json')})
    return {'status': 'initialized', 'run': name, 'path': str(out),
            'cases': len(cases), 'policies': len(policies), 'coefficients': len(betas),
            'expected_shards': plan['expected_shards'], 'expected_retrievals': plan['expected_retrievals']}


def shard_name(case_id, policy_index):
    return f'{case_id}__policy_{policy_index:05d}'


def verify_completed(out, plan):
    complete = set()
    allowed_cases = set(plan['case_ids'])
    plan_hash = L.digest(out / 'plan.json')
    for marker in sorted((out / 'shards').glob('*.json')):
        meta = L.read(marker)
        cid, pi = meta['case_id'], meta['policy_index']
        if cid not in allowed_cases or not isinstance(pi, int) or not 0 <= pi < len(plan['policies']):
            raise ValueError('Completed shard is outside requested plan')
        stem = shard_name(cid, pi)
        if marker.stem != stem or meta['plan_sha256'] != plan_hash:
            raise ValueError('Shard name or plan provenance mismatch')
        data_path = out / 'shards' / (stem + '.npz')
        if L.digest(data_path) != meta['npz_sha256']:
            raise ValueError('Completed shard hash mismatch: ' + stem)
        with np.load(data_path, allow_pickle=False) as data:
            if data.files != ['metrics'] or data['metrics'].shape != (len(plan['coefficients']), 3) or np.isinf(data['metrics']).any():
                raise ValueError('Completed shard metric schema mismatch')
        if (cid, pi) in complete:
            raise ValueError('Duplicate completed shard')
        complete.add((cid, pi))
    return complete


def worker_init():
    global _lab
    with contextlib.redirect_stdout(sys.stderr):
        _lab = WeightedLab()


def worker_job(out_name, case_id, policy_index, policy, betas, plan_hash):
    out = Path(out_name)
    with contextlib.redirect_stdout(sys.stderr):
        case = _lab.case(case_id)
    if case_id not in _checked_cases:
        default = _lab.retrieve(case, L.DEFAULT)
        weighted = _lab.weighted_retrieve(case, L.DEFAULT, DEFAULT_COEFFICIENTS)
        if not np.array_equal(default['order'], weighted['order']):
            raise ValueError('Default weighted route differs from original route')
        # Captured baseline_order belongs to the older run's recovery behavior.
        # Use the same current-helper parity contract as the frozen matrix batch.
        from artefact.facet_scope_recruitment import recruit_with_verified_area
        reference = recruit_with_verified_area(
            chunk_rows=_lab.prepared.chunks,
            joint_scores=np.asarray(case['meta']['expected_scores']),
            area_chunk_ids=case['meta']['area']['chunk_ids'],
            source_character_budget=None, scheduling='equal_depth')
        if [_lab.ids[i] for i in default['order']] != reference['recruitment']['selected_chunk_ids']:
            raise ValueError('Default order differs from current verified helper')
        _checked_cases.add(case_id)
    metrics = np.empty((len(betas), 3), dtype=float)
    for wi, beta in enumerate(betas):
        retrieved = _lab.weighted_retrieve(case, policy, np.asarray(beta, dtype=float))
        measured = _lab.evaluate(case, retrieved)
        r, p = measured['recall_id'], measured['precision_id']
        f1 = (None if r is None else 0. if p is None or p + r == 0 else 2 * p * r / (p + r))
        metrics[wi] = [np.nan if v is None else v for v in (r, p, f1)]
    stem = shard_name(case_id, policy_index)
    numeric = out / 'shards' / (stem + '.npz')
    marker = numeric.with_suffix('.json')
    if marker.exists():
        raise FileExistsError('Refusing to overwrite a completed shard')
    # An interrupted pre-marker write is incomplete. Recomputed equal data is
    # adopted; differing orphan data is rejected rather than silently erased.
    if numeric.exists():
        with np.load(numeric, allow_pickle=False) as old:
            if old.files != ['metrics'] or not np.array_equal(old['metrics'], metrics, equal_nan=True):
                raise ValueError('Orphan shard differs from recomputed metrics')
    else:
        fd, temp = tempfile.mkstemp(dir=numeric.parent, suffix='.npz.partial')
        try:
            with os.fdopen(fd, 'wb') as stream:
                np.savez_compressed(stream, metrics=metrics)
            os.replace(temp, numeric)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    atomic_json(marker, {'case_id': case_id, 'policy_index': policy_index,
        'plan_sha256': plan_hash, 'npz_sha256': L.digest(numeric),
        'coefficient_count': len(betas), 'default_order_parity': True,
        'score_parity_error': case['score_parity_error'], 'language_model_calls': 0})
    return {'case_id': case_id, 'policy_index': policy_index}


def execute_run(name, workers=1, max_jobs=None):
    if not 1 <= workers <= 4 or (max_jobs is not None and max_jobs < 1):
        raise ValueError('workers must be 1..4 and max-jobs must be positive')
    out, plan = load_plan(name)
    lock = out / 'writer.lock'
    with lock.open('x', encoding='utf-8') as stream:
        json.dump({'pid': os.getpid(), 'host': socket.gethostname(), 'started_utc': datetime.now(timezone.utc).isoformat()}, stream)
    try:
        verify_sources(plan)
        completed = verify_completed(out, plan)
        before = len(completed)
        pending = ((cid, pi) for cid in plan['case_ids'] for pi in range(len(plan['policies'])) if (cid, pi) not in completed)
        plan_hash = L.digest(out / 'plan.json')
        active, submitted, errors = {}, 0, []
        exhausted = False
        with ProcessPoolExecutor(max_workers=workers, initializer=worker_init) as pool:
            while active or not exhausted:
                while len(active) < workers and not exhausted:
                    if max_jobs is not None and submitted >= max_jobs:
                        exhausted = True
                        break
                    job = next(pending, None)
                    if job is None:
                        exhausted = True
                        break
                    cid, pi = job
                    active[pool.submit(worker_job, str(out), cid, pi, plan['policies'][pi], plan['coefficients'], plan_hash)] = job
                    submitted += 1
                if not active:
                    break
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    job = active.pop(future)
                    try:
                        future.result()
                        completed.add(job)
                    except Exception as exc:
                        errors.append({'case_id': job[0], 'policy_index': job[1], 'error': str(exc)})
                        exhausted = True  # Preserve other already-running jobs; stop dispatching.
                    print(json.dumps({'phase': 'progress', 'completed_shards': len(completed), 'expected_shards': plan['expected_shards'], 'errors': len(errors)}), flush=True)
        verify_sources(plan)
        verified = verify_completed(out, plan)
        result = {'status': 'failed' if errors else 'complete' if len(verified) == plan['expected_shards'] else 'partial',
                  'run': name, 'completed_shards': len(verified), 'new_shards': len(verified) - before,
                  'expected_shards': plan['expected_shards'], 'errors': errors, 'language_model_calls': 0}
        atomic_json(out / 'status.json', result)
        if errors:
            raise RuntimeError(json.dumps(result))
        return result
    finally:
        lock.unlink()


def report_run(name, metric='recall_id'):
    if metric not in METRICS:
        raise ValueError('Unsupported metric')
    out, plan = load_plan(name)
    verify_sources(plan)
    complete = verify_completed(out, plan)
    shape = (len(plan['policies']), len(plan['coefficients']), 3)
    sums, counts = np.zeros(shape), np.zeros(shape, dtype=np.int32)
    cases_done = np.zeros(shape[0], dtype=np.int32)
    for cid, pi in sorted(complete):
        with np.load(out / 'shards' / (shard_name(cid, pi) + '.npz'), allow_pickle=False) as data:
            values = data['metrics']
            sums[pi] += np.nan_to_num(values, nan=0.)
            counts[pi] += np.isfinite(values)
        cases_done[pi] += 1
    eligible = np.flatnonzero(cases_done == len(plan['cases']))
    leaders = []
    if len(eligible):
        means = np.divide(sums[eligible], counts[eligible], out=np.full_like(sums[eligible], np.nan), where=counts[eligible] > 0)
        flat = means.reshape(-1, 3)
        metric_index = METRICS.index(metric)
        selected = np.flatnonzero(np.isfinite(flat[:, metric_index]))
        order = np.lexsort((selected, -np.nan_to_num(flat[selected, 0], nan=-1.), -np.nan_to_num(flat[selected, 1], nan=-1.), -flat[selected, metric_index]))
        for idx in selected[order[:25]]:
            local_pi, wi = divmod(int(idx), len(plan['coefficients']))
            pi = int(eligible[local_pi])
            leaders.append({'policy_index': pi, 'coefficient_index': wi,
                'policy': plan['policies'][pi], 'coefficients': plan['coefficients'][wi],
                **{key: float(flat[idx, j]) if np.isfinite(flat[idx, j]) else None for j, key in enumerate(METRICS)},
                'defined_metric_cases': {key: int(counts[pi, wi, j]) for j, key in enumerate(METRICS)}})
    return {'run': name, 'status': 'complete' if len(complete) == plan['expected_shards'] else 'partial',
            'ranking_metric': metric, 'requested_cases': len(plan['cases']),
            'completed_shards': len(complete), 'expected_shards': plan['expected_shards'],
            'fully_covered_policies': len(eligible), 'fully_covered_settings': len(eligible) * len(plan['coefficients']),
            'leaders': leaders,
            'metric_note': 'Macro source-ID metrics on every requested case. Undefined precision excluded with counts; empty retrieval has F1 zero. Only settings completed for all requested cases can rank.',
            'original_failed_cases_in_capture': len(plan['original_failed_question_ids']),
            'limits': 'Exploratory reused-case comparisons; these are not answer-quality judgments or independent validation.'}


def status(name=None):
    if name is not None:
        out, plan = load_plan(name)
        count = len(list((out / 'shards').glob('*.json')))
        return {'run': name, 'completion_markers': count, 'expected_shards': plan['expected_shards'],
                'expected_retrievals': plan['expected_retrievals'], 'writer_lock': L.read(out / 'writer.lock') if (out / 'writer.lock').exists() else None,
                'note': 'Status counts markers only; run/report verify hashes.'}
    runs = sorted(p.name for p in RUNS.glob('*') if p.is_dir() and (p / 'plan.json').exists()) if RUNS.exists() else []
    manifest = L.read(L.INPUTS / 'cases_manifest.json')
    return {'captured_cases': sum((L.INPUTS / c['meta']).exists() for c in manifest['cases']),
            'expected_cases': manifest['expected_cases'],
            'existing_matrix_completed_cases': len(list((L.BASE / 'batch').glob('case_*.json'))),
            'existing_weight_completed_cases': len(list((L.BASE / 'weights').glob('case_*.json'))),
            'harness_runs': [status(n) for n in runs]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('status'); p.add_argument('--run')
    p = sub.add_parser('serve'); p.add_argument('--port', type=int, default=8770)
    p = sub.add_parser('init'); p.add_argument('--run', required=True); p.add_argument('--spec', type=Path, required=True)
    p = sub.add_parser('run'); p.add_argument('--run', required=True); p.add_argument('--workers', type=int, default=1); p.add_argument('--max-jobs', type=int)
    p = sub.add_parser('report'); p.add_argument('--run', required=True); p.add_argument('--metric', choices=METRICS, default='recall_id')
    args = parser.parse_args()
    if args.command == 'serve':
        if not 1 <= args.port <= 65535:
            raise ValueError('Port outside valid range')
        from facet_retrieval_lab_ranked import serve
        serve(args.port)
        return
    if args.command == 'status':
        result = status(args.run)
    elif args.command == 'init':
        result = initialize_run(args.run, args.spec)
    elif args.command == 'run':
        result = execute_run(args.run, args.workers, args.max_jobs)
    else:
        result = report_run(args.run, args.metric)
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
