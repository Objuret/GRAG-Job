"""Rank completed construction and coefficient experiments on identical cases.

Reads numeric evaluation artifacts only. Selection is explicitly retrospective;
reference outcomes never enter the retrieval implementation.
"""
from functools import lru_cache
import threading
import numpy as np
import facet_retrieval_lab as L
import facet_matrix_leaderboard as M

METRICS = ('recall_id', 'precision_id', 'f1_id')
BETA = [1., .25, .25, .25, .25]
LOCK = threading.Lock()


def setting_key(policy, coefficients):
    return (tuple(sorted(policy.items())), tuple(coefficients))


@lru_cache(maxsize=1)
def completed_data():
    """Only publish the union once both experiments completed without errors."""
    weights = L.BASE / 'weights'
    for folder in (M.OUT, weights):
        done = L.read(folder / 'completed.json')
        if done['status'] != 'completed' or done['errors'] or not done['source_hashes_unchanged']:
            raise ValueError('Combined rankings require both verified completed experiments')
    with M._lock:
        original = M._data()
    plan = L.read(weights / 'plan.json')
    metas = original['metas']
    arrays = []
    for meta in metas:
        record = L.read(weights / (meta['case_id'] + '.json'))
        if any(record[k] != meta[k] for k in ('case_id', 'question_id', 'cohort')):
            raise ValueError('Experiment cases are not aligned')
        path = weights / (meta['case_id'] + '.npz')
        if L.digest(path) != record['npz_sha256']:
            raise ValueError('Coefficient result hash mismatch')
        with np.load(path, allow_pickle=False) as arr:
            arrays.append(arr['metrics'])
    coefficients = np.asarray(arrays)
    settings = [dict(condition=f'matrix:{i}', label=f'Construction {i}', source='construction',
                     policy=p, coefficients=BETA, topic_present=True, topic_largest=True)
                for i, p in enumerate(original['plan']['configurations'])]
    values = [np.stack([original['values'][k] for k in METRICS], axis=-1)]
    seen = {setting_key(s['policy'], s['coefficients']): i for i, s in enumerate(settings)}
    extras = []
    for s, structure in enumerate(plan['structures']):
        for v, vector in enumerate(plan['vectors']):
            key = setting_key(structure['policy'], vector['coefficients'])
            if key in seen:
                # The duplicated defaults must reproduce the original experiment.
                np.testing.assert_allclose(coefficients[:, s, v], values[0][:, seen[key]],
                                           rtol=0, atol=1e-12, equal_nan=True)
                continue
            seen[key] = len(settings)
            settings.append(dict(condition=f'weights:{s}:{v}',
                label=f"{structure['name']} · weights {v}", source='coefficients',
                policy=structure['policy'], **vector))
            extras.append(coefficients[:, s, v])
    if extras:
        values.append(np.stack(extras, axis=1))
    return metas, settings, np.concatenate(values, axis=1), original['canonical']


def means(values):
    counts = np.isfinite(values).sum(axis=0)
    return np.divide(np.nansum(values, axis=0), counts,
                     out=np.full(counts.shape, np.nan, dtype=float), where=counts > 0)


def ranked(values, metric):
    clean = np.nan_to_num(values, nan=-1.)
    return np.lexsort((np.arange(len(values)), -clean[:, 0], -clean[:, 1], -clean[:, metric]))


def metrics(row):
    return {k: float(v) if np.isfinite(v) else None for k, v in zip(METRICS, row)}


def leaderboard(metric='recall_id', limit=25, cohort='all', subset='all'):
    if metric not in METRICS or cohort not in ('all', 'smoke10', 'remaining90'):
        raise ValueError('Unsupported metric or cohort')
    if subset not in ('all', 'topic_present', 'topic_largest'):
        raise ValueError('Unsupported coefficient subset')
    with LOCK:
        metas, settings, all_values, canonical = completed_data()
    cases = np.asarray([i for i, m in enumerate(metas) if cohort == 'all' or m['cohort'] == cohort])
    cols = np.asarray([i for i, s in enumerate(settings) if subset == 'all' or s[subset]])
    values = all_values[cases][:, cols]
    average = means(values)
    base = all_values[cases, canonical]
    primary = METRICS.index(metric)
    order = ranked(average, primary)
    leaders = []
    for local in order[:min(max(int(limit), 1), 200)]:
        delta = values[:, local, 0] - base[:, 0]
        leaders.append({**settings[int(cols[local])], **metrics(average[local]),
            'recall_better': int((delta > 0).sum()), 'recall_worse': int((delta < 0).sum()),
            'recall_tied': int((delta == 0).sum())})
    chosen = np.asarray([ranked(v, primary)[0] for v in values])
    best_values = values[np.arange(len(cases)), chosen]
    best_cases = [{**settings[int(cols[local])], 'case_id': metas[int(case)]['case_id'],
                   'question_id': metas[int(case)]['question_id'], **metrics(row)}
                  for case, local, row in zip(cases, chosen, best_values)]
    manifest = L.read(L.INPUTS / 'cases_manifest.json')
    expected = sum(cohort == 'all' or c['cohort'] == cohort for c in manifest['cases'])
    return dict(status='complete' if len(cases) == expected else 'partial',
        completed_cases=len(cases), expected_cases=expected, cohort=cohort, subset=subset,
        configurations_per_case=len(cols), ranking_metric=metric,
        canonical=metrics(means(base)), leaders=leaders,
        best_per_query={**metrics(means(best_values)), 'cases': best_cases,
            'selection_metric': metric, 'distinct_chosen_configurations': len(set(chosen.tolist())),
            'label': 'Best observed per question across tested settings, chosen using reference outcomes; not a deployable selector or a proven optimum.'},
        original_failed_cases=len(manifest['failed_question_ids']) if cohort != 'smoke10' else 0,
        selection_space_note='10,240 constructions plus 509 coefficient settings on three constructions; duplicate policy/weight settings removed. Equal-scoring settings remain separate. The full cross-product was not tested.',
        metric_note='Macro source-ID recall, precision and per-question F1 at 72,000 characters. No new generated answers or LLM judging.')
