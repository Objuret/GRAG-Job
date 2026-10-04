"""Read-only rankings of the declared matrix, including per-query best observed."""
from __future__ import annotations
import threading
import json
import numpy as np
import facet_retrieval_lab as L

OUT = L.BASE / 'batch'
_cache = None
_lock = threading.Lock()


def _data():
    global _cache
    markers = tuple(sorted(p.name for p in OUT.glob('case_*.json')))
    if _cache is not None and _cache[0] == markers:
        return _cache[1]
    if not markers:
        return None
    plan = L.read(OUT / 'plan.json')
    arrays, metas, order_classes, accepted_markers = [], [], [], []
    for name in markers:
        try:
            meta = L.read(OUT / name)
        except json.JSONDecodeError:
            # The frozen producer closes this tiny completion record shortly.
            # Do not cache its filename until the record is fully readable.
            continue
        path = OUT / (meta['case_id'] + '.npz')
        assert L.digest(path) == meta['npz_sha256']
        with np.load(path, allow_pickle=False) as data:
            arrays.append(data['metrics'])
            order_classes.append(data['order_classes'])
        metas.append(meta)
        accepted_markers.append(name)
    if not arrays:
        return None
    values = np.asarray(arrays)
    recall, precision = values[:, :, 0], values[:, :, 1]
    p = np.nan_to_num(precision)
    f1 = np.divide(2 * recall * p, recall + p, out=np.zeros_like(recall), where=(recall + p) > 0)
    metric_arrays = {'recall_id': recall, 'precision_id': precision, 'f1_id': f1}
    means = {k: np.divide(np.nansum(a, axis=0), np.isfinite(a).sum(axis=0),
                        out=np.full(a.shape[1], np.nan), where=np.isfinite(a).sum(axis=0) > 0)
             for k, a in metric_arrays.items()}
    canonical = next(i for i, policy in enumerate(plan['configurations']) if policy == L.DEFAULT)
    result = {'plan': plan, 'metas': metas, 'values': metric_arrays, 'means': means, 'canonical': canonical,
              'order_classes': np.asarray(order_classes)}
    _cache = (tuple(accepted_markers), result)
    return result


def leaderboard(metric='recall_id', limit=25, cohort='all'):
    if metric not in ('recall_id', 'precision_id', 'f1_id'):
        raise ValueError('Unsupported leaderboard metric')
    if cohort not in ('all', 'smoke10', 'remaining90'):
        raise ValueError('Unsupported cohort')
    limit = min(max(int(limit), 1), 200)
    with _lock:
        data = _data()
        manifest = L.read(L.INPUTS / 'cases_manifest.json')
        expected = sum(cohort == 'all' or c['cohort'] == cohort for c in manifest['cases'])
        if data is None:
            return {'status': 'pending', 'completed_cases': 0, 'expected_cases': expected, 'leaders': []}
        indices = np.asarray([i for i, m in enumerate(data['metas']) if cohort == 'all' or m['cohort'] == cohort])
        if not len(indices):
            return {'status': 'pending', 'completed_cases': 0, 'expected_cases': expected, 'leaders': []}
        values = {k: a[indices] for k, a in data['values'].items()}
        means = {k: np.divide(np.nansum(a, axis=0), np.isfinite(a).sum(axis=0),
                            out=np.full(a.shape[1], np.nan), where=np.isfinite(a).sum(axis=0) > 0)
                 for k, a in values.items()}
        canon = data['canonical']
        n = len(data['plan']['configurations'])
        clean = lambda a: np.nan_to_num(a, nan=-1.)
        order = np.lexsort((np.arange(n), -means['recall_id'], -clean(means['precision_id']), -clean(means[metric])))
        scalar = lambda v: float(v) if np.isfinite(v) else None
        classes = data['order_classes'][indices]
        signatures = [classes[:, i].tobytes() for i in range(n)]
        counts = {}
        for signature in signatures:
            counts[signature] = counts.get(signature, 0) + 1
        leaders, seen = [], set()
        for i in order:
            signature = signatures[i]
            if signature in seen:
                continue
            seen.add(signature)
            delta = values['recall_id'][:, i] - values['recall_id'][:, canon]
            leaders.append({'condition': int(i), 'policy': data['plan']['configurations'][i],
                'equivalent_configurations': counts[signature],
                **{k: scalar(a[i]) for k, a in means.items()},
                'recall_better': int((delta > 0).sum()), 'recall_worse': int((delta < 0).sum()),
                'recall_tied': int((delta == 0).sum())})
            if len(leaders) >= limit:
                break
        # Choose a coherent entire configuration per query, not separate maxima per metric.
        chosen = np.asarray([np.lexsort((np.arange(n), -values['recall_id'][q],
            -clean(values['precision_id'][q]), -clean(values[metric][q])))[0] for q in range(len(indices))])
        best = {k: scalar(np.nanmean(a[np.arange(len(indices)), chosen])) for k, a in values.items()}
        best.update(label='Per-query best observed; uses reference outcomes to choose, not a deployable selector',
                    selection_metric=metric, distinct_chosen_configurations=len(set(map(int, chosen))))
        return {'status': 'complete' if len(indices) == expected else 'partial',
            'completed_cases': len(indices), 'expected_cases': expected, 'cohort': cohort,
            'configurations_per_case': n, 'ranking_metric': metric,
            'distinct_constructions_by_full_orders': len(counts),
            'canonical': {k: scalar(a[canon]) for k, a in means.items()}, 'best_per_query': best,
            'leaders': leaders, 'original_failed_cases': len(manifest['failed_question_ids']) if cohort != 'smoke10' else 0,
            'metric_note': 'Macro source-ID recall, precision and per-query F1; no new answer generation or LLM judging.'}
