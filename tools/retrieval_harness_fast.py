"""Grouped, resumable retrieval-harness runner: same experiments as
`retrieval_harness.py`, one shard per (case, match, topology, graph_join)
family instead of one per (case, policy). No model inference, no database.

Runs live under output/research/retrieval-harness-runs/NAME beside the
per-policy runner's; a run initialised here is read only by this file. Shard
files: shards/<case>__family_<index>.npz with `metrics` of shape
(policies in family, coefficients, 3) and `policy_indices`. The plan freezes
the same inputs as the per-policy runner plus this file and
facet_weighted_fast.py. The gate subcommand compares this path with the
per-policy path: every policy of a family on named cases through
`WeightedLab.weighted_retrieve`, and every shard a per-policy run has completed.

Lock: writer.lock as in the per-policy runner; this file never removes a lock
it did not create. tools/retrieval_harness_keepalive.py handles relaunch.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time

import numpy as np

with contextlib.redirect_stdout(sys.stderr):
    import retrieval_harness as H
    import facet_retrieval_lab as L
    from facet_weighted_lab import WeightedLab, DEFAULT_COEFFICIENTS
    import facet_weighted_fast as F

METRICS = H.METRICS
_lab = None
_fast = None
_checked_cases = set()


def shard_name(case_id, family_index):
    return f'{case_id}__family_{family_index:03d}'


def initialize_run(name, spec_path):
    out = H.run_path(name)
    if out.exists():
        raise FileExistsError('Run directory already exists; choose a new name or resume it')
    spec_path = Path(spec_path).resolve()
    spec = L.read(spec_path)
    cases, policies, betas, extras = H.normalize_spec(spec)
    groups = F.families(policies)
    family_list = [{'family': list(key), 'policy_indices': indices} for key, indices in groups.items()]
    files = {Path(__file__).resolve(), Path(F.__file__).resolve(), Path(H.__file__).resolve(), Path(L.__file__).resolve(),
             spec_path, L.ROOT / 'tools/facet_weighted_lab.py', L.ROOT / 'tools/facet_gold90_stage_budget.py',
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
    plan = {'schema_version': 2, 'runner': 'retrieval_harness_fast', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'run': name, 'spec': spec, 'case_ids': [c['case_id'] for c in cases], 'cases': cases,
            'runtime': {'python': sys.version.split()[0], 'implementation': sys.implementation.name, 'numpy': np.__version__},
            'policies': policies, 'coefficients': betas, 'metrics': list(METRICS),
            'families': family_list, 'prefix': F.PREFIX,
            'expected_shards': len(cases) * len(family_list),
            'expected_retrievals': len(cases) * len(policies) * len(betas),
            'original_failed_question_ids': manifest.get('failed_question_ids', []),
            'input_sha256': {str(p.resolve()): L.digest(p) for p in sorted(files)},
            'language_model_calls': 0, 'database_calls': 0,
            'contract': 'Cached frozen query readings and graph. Retrieve and cut before reference-ID evaluation. One shard per case and (match, topology, graph_join) family; every policy of the family and every coefficient vector inside it. Metrics identical to the per-policy runner by construction and by gate.',
            'lock_recovery': 'writer.lock names host and PID. This runner never removes a lock it did not create; retrieval_harness_keepalive.py removes one only when it names this host and a PID that is not a running python process.',
            'scope': 'Only named finite operator and coefficient combinations; exploratory reused cases, not held-out validation.'}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()
    (out / 'shards').mkdir()
    H.atomic_json(out / 'plan.json', plan)
    H.atomic_json(out / 'plan.sha256.json', {'sha256': L.digest(out / 'plan.json')})
    return {'status': 'initialized', 'run': name, 'path': str(out), 'cases': len(cases), 'policies': len(policies),
            'families': len(family_list), 'coefficients': len(betas),
            'expected_shards': plan['expected_shards'], 'expected_retrievals': plan['expected_retrievals']}


def load_plan(name):
    out, plan = H.load_plan(name)
    if plan.get('runner') != 'retrieval_harness_fast':
        raise ValueError('Run was not initialised by retrieval_harness_fast')
    return out, plan


def verify_completed(out, plan):
    complete = set()
    allowed_cases = set(plan['case_ids'])
    plan_hash = L.digest(out / 'plan.json')
    for marker in sorted((out / 'shards').glob('*.json')):
        meta = L.read(marker)
        cid, fi = meta['case_id'], meta['family_index']
        if cid not in allowed_cases or not isinstance(fi, int) or not 0 <= fi < len(plan['families']):
            raise ValueError('Completed shard is outside requested plan')
        stem = shard_name(cid, fi)
        if marker.stem != stem or meta['plan_sha256'] != plan_hash:
            raise ValueError('Shard name or plan provenance mismatch')
        data_path = out / 'shards' / (stem + '.npz')
        if L.digest(data_path) != meta['npz_sha256']:
            raise ValueError('Completed shard hash mismatch: ' + stem)
        expected_shape = (len(plan['families'][fi]['policy_indices']), len(plan['coefficients']), 3)
        with np.load(data_path, allow_pickle=False) as data:
            if sorted(data.files) != ['metrics', 'policy_indices'] or data['metrics'].shape != expected_shape \
                    or np.isinf(data['metrics']).any() or data['policy_indices'].tolist() != plan['families'][fi]['policy_indices']:
                raise ValueError('Completed shard schema mismatch: ' + stem)
        if (cid, fi) in complete:
            raise ValueError('Duplicate completed shard')
        complete.add((cid, fi))
    return complete


def worker_init():
    global _lab, _fast
    with contextlib.redirect_stdout(sys.stderr):
        _lab = WeightedLab()
        _fast = F.FastLab(_lab)


def check_case(case_id, case):
    """The per-policy runner's once-per-case parity check, verbatim in substance."""
    if case_id in _checked_cases:
        return
    default = _lab.retrieve(case, L.DEFAULT)
    weighted = _lab.weighted_retrieve(case, L.DEFAULT, DEFAULT_COEFFICIENTS)
    if not np.array_equal(default['order'], weighted['order']):
        raise ValueError('Default weighted route differs from original route')
    from artefact.facet_scope_recruitment import recruit_with_verified_area
    reference = recruit_with_verified_area(
        chunk_rows=_lab.prepared.chunks,
        joint_scores=np.asarray(case['meta']['expected_scores']),
        area_chunk_ids=case['meta']['area']['chunk_ids'],
        source_character_budget=None, scheduling='equal_depth')
    if [_lab.ids[i] for i in default['order']] != reference['recruitment']['selected_chunk_ids']:
        raise ValueError('Default order differs from current verified helper')
    _checked_cases.add(case_id)


def worker_job(out_name, case_id, family_index, family, policy_indices, policies, betas, plan_hash):
    out = Path(out_name)
    with contextlib.redirect_stdout(sys.stderr):
        case = _lab.case(case_id)
    check_case(case_id, case)
    started = time.perf_counter()
    results = _fast.family_metrics(case, tuple(family), [(pi, policies[pi]) for pi in policy_indices], betas)
    metrics = np.stack([results[pi] for pi in policy_indices])
    stem = shard_name(case_id, family_index)
    numeric = out / 'shards' / (stem + '.npz')
    marker = numeric.with_suffix('.json')
    if marker.exists():
        raise FileExistsError('Refusing to overwrite a completed shard')
    if numeric.exists():
        with np.load(numeric, allow_pickle=False) as old:
            if sorted(old.files) != ['metrics', 'policy_indices'] or not np.array_equal(old['metrics'], metrics, equal_nan=True):
                raise ValueError('Orphan shard differs from recomputed metrics')
    else:
        fd, temp = tempfile.mkstemp(dir=numeric.parent, suffix='.npz.partial')
        try:
            with os.fdopen(fd, 'wb') as stream:
                np.savez_compressed(stream, metrics=metrics, policy_indices=np.asarray(policy_indices, dtype=np.int64))
            os.replace(temp, numeric)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    H.atomic_json(marker, {'case_id': case_id, 'family_index': family_index, 'family': list(family),
        'plan_sha256': plan_hash, 'npz_sha256': L.digest(numeric), 'coefficient_count': len(betas),
        'policy_count': len(policy_indices), 'default_order_parity': True,
        'score_parity_error': case['score_parity_error'], 'seconds': round(time.perf_counter() - started, 3),
        'language_model_calls': 0})
    return {'case_id': case_id, 'family_index': family_index}


def execute_run(name, workers=1, max_jobs=None):
    if not 1 <= workers <= 4 or (max_jobs is not None and max_jobs < 1):
        raise ValueError('workers must be 1..4 and max-jobs must be positive')
    out, plan = load_plan(name)
    lock = out / 'writer.lock'
    with lock.open('x', encoding='utf-8') as stream:
        json.dump({'pid': os.getpid(), 'host': socket.gethostname(), 'started_utc': datetime.now(timezone.utc).isoformat()}, stream)
    try:
        H.verify_sources(plan)
        completed = verify_completed(out, plan)
        before = len(completed)
        pending = ((cid, fi) for cid in plan['case_ids'] for fi in range(len(plan['families'])) if (cid, fi) not in completed)
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
                    cid, fi = job
                    fam = plan['families'][fi]
                    active[pool.submit(worker_job, str(out), cid, fi, fam['family'], fam['policy_indices'],
                                       plan['policies'], plan['coefficients'], plan_hash)] = job
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
                        errors.append({'case_id': job[0], 'family_index': job[1], 'error': str(exc)})
                        exhausted = True
                    print(json.dumps({'phase': 'progress', 'completed_shards': len(completed), 'expected_shards': plan['expected_shards'], 'errors': len(errors)}), flush=True)
        H.verify_sources(plan)
        verified = verify_completed(out, plan)
        result = {'status': 'failed' if errors else 'complete' if len(verified) == plan['expected_shards'] else 'partial',
                  'run': name, 'completed_shards': len(verified), 'new_shards': len(verified) - before,
                  'expected_shards': plan['expected_shards'], 'errors': errors, 'language_model_calls': 0}
        H.atomic_json(out / 'status.json', result)
        if errors:
            raise RuntimeError(json.dumps(result))
        return result
    finally:
        lock.unlink()


def load_means(out, plan, complete):
    """Per (policy, coefficient) sums and counts over completed shards, plus cases done per policy."""
    P, W = len(plan['policies']), len(plan['coefficients'])
    sums, counts = np.zeros((P, W, 3)), np.zeros((P, W, 3), dtype=np.int32)
    cases_done = np.zeros(P, dtype=np.int32)
    for cid, fi in sorted(complete):
        with np.load(out / 'shards' / (shard_name(cid, fi) + '.npz'), allow_pickle=False) as data:
            values, indices = data['metrics'], data['policy_indices']
        sums[indices] += np.nan_to_num(values, nan=0.)
        counts[indices] += np.isfinite(values)
        cases_done[indices] += 1
    return sums, counts, cases_done


def report_run(name, metric='recall_id'):
    if metric not in METRICS:
        raise ValueError('Unsupported metric')
    out, plan = load_plan(name)
    H.verify_sources(plan)
    complete = verify_completed(out, plan)
    sums, counts, cases_done = load_means(out, plan, complete)
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


def gate(name, against=None, full_cases=2):
    """Compare this path with the per-policy path. Exact equality of metrics (NaN == NaN) or it raises."""
    out, plan = load_plan(name)
    worker_init()
    betas = plan['coefficients']
    policies = plan['policies']
    report = {'run': name, 'families': len(plan['families']), 'full_policy_checks': [], 'against': None}
    # 1. Every policy of every family, on cases chosen to cover an area case and a no-area case.
    chosen = []
    for cid in plan['case_ids']:
        with contextlib.redirect_stdout(sys.stderr):
            case = _lab.case(cid)
        kind = 'no-area' if case['area_mask'] is None else 'area'
        if kind not in {k for _, k in chosen}:
            chosen.append((cid, kind))
        if len(chosen) == 2:
            break
    for cid, kind in chosen:
        with contextlib.redirect_stdout(sys.stderr):
            case = _lab.case(cid)
        check_case(cid, case)
        checked = 0
        started = time.perf_counter()
        for fi, fam in enumerate(plan['families']):
            fast = _fast.family_metrics(case, tuple(fam['family']), [(pi, policies[pi]) for pi in fam['policy_indices']], betas)
            for pi in fam['policy_indices']:
                slow = np.empty((len(betas), 3))
                for wi, beta in enumerate(betas):
                    r = _lab.weighted_retrieve(case, policies[pi], np.asarray(beta, dtype=float))
                    e = _lab.evaluate(case, r)
                    rr, p = e['recall_id'], e['precision_id']
                    f1 = None if rr is None else 0. if p is None or p + rr == 0 else 2 * p * rr / (p + rr)
                    slow[wi] = [np.nan if v is None else v for v in (rr, p, f1)]
                if not np.array_equal(fast[pi], slow, equal_nan=True):
                    raise AssertionError(f'gate: metrics differ on case {cid} policy {pi} {policies[pi]}')
                checked += 1
            if fi + 1 == full_cases * 0 + len(plan['families']) or (fi + 1) % 10 == 0:
                print(json.dumps({'phase': 'gate', 'case': cid, 'kind': kind, 'families_checked': fi + 1, 'policies_checked': checked}), flush=True)
        report['full_policy_checks'].append({'case_id': cid, 'kind': kind, 'policies': checked, 'seconds': round(time.perf_counter() - started, 1)})
    # 2. Every shard the per-policy run has completed.
    if against is not None:
        old_out, old_plan = H.load_plan(against)
        if old_plan['policies'] != policies or old_plan['coefficients'] != betas or old_plan['case_ids'] != plan['case_ids']:
            raise ValueError('The per-policy run does not define the same experiment')
        old_complete = H.verify_completed(old_out, old_plan)
        by_case = {}
        for cid, pi in old_complete:
            by_case.setdefault(cid, set()).add(pi)
        family_of = {pi: fi for fi, fam in enumerate(plan['families']) for pi in fam['policy_indices']}
        compared = 0
        started = time.perf_counter()
        for cid in plan['case_ids']:
            if cid not in by_case:
                continue
            with contextlib.redirect_stdout(sys.stderr):
                case = _lab.case(cid)
            needed = {family_of[pi] for pi in by_case[cid]}
            for fi in sorted(needed):
                fam = plan['families'][fi]
                fast = _fast.family_metrics(case, tuple(fam['family']), [(pi, policies[pi]) for pi in fam['policy_indices']], betas)
                for pi in fam['policy_indices']:
                    if pi not in by_case[cid]:
                        continue
                    with np.load(old_out / 'shards' / (H.shard_name(cid, pi) + '.npz'), allow_pickle=False) as data:
                        old = data['metrics']
                    if not np.array_equal(fast[pi], old, equal_nan=True):
                        raise AssertionError(f'gate: metrics differ from {against} on case {cid} policy {pi}')
                    compared += 1
            print(json.dumps({'phase': 'gate', 'against': against, 'case': cid, 'shards_compared': compared, 'of': len(old_complete)}), flush=True)
        report['against'] = {'run': against, 'shards_compared': compared, 'retrievals_compared': compared * len(betas),
                             'seconds': round(time.perf_counter() - started, 1)}
    report['status'] = 'passed'
    H.atomic_json(out / f'gate.{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.json', report)
    return report


def status(name):
    out, plan = load_plan(name)
    return {'run': name, 'completion_markers': len(list((out / 'shards').glob('*.json'))),
            'expected_shards': plan['expected_shards'], 'expected_retrievals': plan['expected_retrievals'],
            'writer_lock': L.read(out / 'writer.lock') if (out / 'writer.lock').exists() else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('init'); p.add_argument('--run', required=True); p.add_argument('--spec', type=Path, required=True)
    p = sub.add_parser('run'); p.add_argument('--run', required=True); p.add_argument('--workers', type=int, default=1); p.add_argument('--max-jobs', type=int)
    p = sub.add_parser('report'); p.add_argument('--run', required=True); p.add_argument('--metric', choices=METRICS, default='recall_id')
    p = sub.add_parser('gate'); p.add_argument('--run', required=True); p.add_argument('--against')
    p = sub.add_parser('status'); p.add_argument('--run', required=True)
    args = parser.parse_args()
    if args.command == 'init':
        result = initialize_run(args.run, args.spec)
    elif args.command == 'run':
        result = execute_run(args.run, args.workers, args.max_jobs)
    elif args.command == 'report':
        result = report_run(args.run, args.metric)
    elif args.command == 'gate':
        result = gate(args.run, args.against)
    else:
        result = status(args.run)
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
