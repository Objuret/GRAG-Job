"""Analyze the completed construction matrix without new retrieval/model calls."""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import numpy as np
import facet_retrieval_lab as L

OUT = L.BASE / 'analysis'
BATCH = L.BASE / 'batch'


def mean_finite(values):
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    return float(x.mean()) if len(x) else None


def select(values, metric):
    counts = np.isfinite(values).sum(axis=0)
    means = np.divide(np.nansum(values, axis=0), counts,
                      out=np.full(counts.shape, -1., dtype=float), where=counts > 0)
    return int(np.lexsort((np.arange(len(means)), -means[:, 0], -means[:, 1], -means[:, metric]))[0])


def summary(values):
    return {**dict(zip(('recall_id', 'precision_id', 'f1_id'), [mean_finite(values[:, i]) for i in range(3)])),
            'cases': len(values), 'defined_precision_cases': int(np.isfinite(values[:, 1]).sum()),
            'empty_retrieval_cases': int((~np.isfinite(values[:, 1])).sum())}


def paired(a, b):
    out = {}
    for i, name in enumerate(('recall_id', 'precision_id', 'f1_id')):
        d = a[:, i] - b[:, i]
        valid = np.isfinite(d)
        out[name] = {'mean_delta': mean_finite(d), 'better': int((d[valid] > 0).sum()),
                     'worse': int((d[valid] < 0).sum()), 'ties': int((d[valid] == 0).sum()),
                     'defined_cases': int(valid.sum())}
    return out


def main():
    done = L.read(BATCH / 'completed.json')
    assert done['status'] == 'completed' and not done['errors'] and done['source_hashes_unchanged']
    plan = L.read(BATCH / 'plan.json')
    manifest = L.read(L.INPUTS / 'cases_manifest.json')
    L.write_new(OUT / 'protocol.json', {
        'input_sha256': {str(p.relative_to(L.ROOT)): L.digest(p) for p in [Path(__file__), BATCH / 'plan.json', BATCH / 'completed.json']},
        'analyses': ['best complete configuration separately by macro recall/precision/per-query F1',
            'coherent per-query best configuration for each metric',
            'one-factor neighbours of best recall construction, no extra retrieval',
            'leave-one-product-prefix-out whole-configuration selection for each metric',
            'fixed topic-only counterpart on each held-out group and equal-product-weight reporting'],
        'selection_tiebreak': 'primary metric, precision, recall, earliest frozen configuration index',
        'limits': 'All data reused; grouped selection is retrospective robustness evidence, not a fresh independent validation.'})
    data, metas = [], []
    for record in manifest['cases']:
        meta = L.read(BATCH / (record['case_id'] + '.json'))
        path = BATCH / (record['case_id'] + '.npz')
        assert L.digest(path) == meta['npz_sha256']
        with np.load(path, allow_pickle=False) as arr:
            metric = arr['metrics'][:, :2]
            r, p = metric.T
            p0 = np.nan_to_num(p)
            f1 = np.divide(2*r*p0, r+p0, out=np.zeros_like(r), where=(r+p0)>0)
            data.append(np.column_stack((r, p, f1)))
        metas.append(meta)
    values = np.asarray(data)
    assert len(metas) == manifest['expected_cases'] == 95
    configs = plan['configurations']
    at = {L.policy_key(p): i for i, p in enumerate(configs)}
    canonical = at[L.policy_key(L.DEFAULT)]
    area = at[L.policy_key({**L.DEFAULT, 'scope': 'area_first'})]
    groups = np.asarray([m['question_id'].split('::')[0] for m in metas])
    results = {'cases': len(metas), 'original_failures': len(manifest['failed_question_ids']),
               'configurations': len(configs), 'product_groups': len(set(groups)),
               'canonical': summary(values[:, canonical]), 'area_first': summary(values[:, area]),
               'selected': {}, 'cohorts': {}, 'neighbours': []}
    for col, name in enumerate(('recall_id', 'precision_id', 'f1_id')):
        best = select(values, col)
        oracle = np.array([select(v[None, :, :], col) for v in values])
        oracle_values = values[np.arange(len(values)), oracle]
        heldout = np.empty((len(values), 3))
        heldout_topic = np.empty_like(heldout)
        folds = []
        for group in sorted(set(groups)):
            test = groups == group
            chosen = select(values[~test], col)
            heldout[test] = values[test, chosen]
            topic_counterpart = at[L.policy_key({**configs[chosen], 'facet': 'topic_only'})]
            heldout_topic[test] = values[test, topic_counterpart]
            folds.append({'group': group, 'training_cases': int((~test).sum()),
                          'heldout_cases': int(test.sum()), 'configuration': chosen,
                          'heldout_metrics': summary(values[test, chosen]),
                          'topic_only_configuration': topic_counterpart,
                          'heldout_topic_only_metrics': summary(values[test, topic_counterpart])})
        results['selected'][name] = {
            'configuration': best, 'policy': configs[best], 'metrics': summary(values[:, best]),
            'versus_canonical': paired(values[:, best], values[:, canonical]),
            'versus_area_first': paired(values[:, best], values[:, area]),
            'failure_inclusive_recall_100': float(values[:, best, 0].sum()/100),
            'per_query_best': summary(oracle_values),
            'per_query_best_configuration_counts': dict(Counter(map(int, oracle))),
            'grouped_selection': summary(heldout),
            'grouped_selection_topic_only': summary(heldout_topic),
            'grouped_auxiliary_effect': paired(heldout, heldout_topic),
            'equal_product_weight_metrics': {key: mean_finite([mean_finite(heldout[groups == g, i]) for g in sorted(set(groups))])
                for i, key in enumerate(('recall_id', 'precision_id', 'f1_id'))},
            'grouped_selection_vs_canonical': paired(heldout, values[:, canonical]),
            'folds': folds}
    best = results['selected']['recall_id']['configuration']
    for field, options in L.FACTORS.items():
        for option in options:
            if option == configs[best][field]:
                continue
            changed = {**configs[best], field: option}
            index = at.get(L.policy_key(changed))
            if index is not None:
                results['neighbours'].append({'changed_factor': field, 'value': option, 'configuration': index,
                    'metrics': summary(values[:, index]), 'difference_from_leader': paired(values[:, index], values[:, best])})
    cohorts = np.asarray([m['cohort'] for m in metas])
    for cohort in sorted(set(cohorts)):
        mask = cohorts == cohort
        results['cohorts'][cohort] = {'cases': int(mask.sum()), 'canonical': summary(values[mask, canonical]),
            'area_first': summary(values[mask, area]), 'overall_recall_leader': summary(values[mask, best])}
    L.write_new(OUT / 'results.json', results)
    lines = ['# Completed retrieval construction matrix', '',
        f"{len(configs):,} configurations across 95 successful saved queries: {len(configs)*95:,} retrievals. Five original interpretation failures retained. Zero new language-model calls.", '',
        '| Construction | Source-ID recall | Precision | F1 |', '|---|---:|---:|---:|']
    for label, scores in [('Canonical', results['canonical']), ('Area-first only', results['area_first'])] + [(f'Best single by {k}', v['metrics']) for k,v in results['selected'].items()]:
        lines.append('| '+label+' | '+' | '.join(f'{100*scores[k]:.2f}%' if scores[k] is not None else 'undefined' for k in ('recall_id','precision_id','f1_id'))+' |')
    lines += ['', '## Highest-recall construction', '', '`'+L.policy_key(configs[best])+'`', '',
        'A complete policy selected by observed macro recall on all reused cases. Its neighbours below change only one declared factor. No additional retrieval or coefficient fitting is involved.', '',
        '| Changed factor | Alternative | Recall | Change from leader |', '|---|---|---:|---:|']
    for item in results['neighbours']:
        lines.append(f"| {item['changed_factor']} | {item['value']} | {100*item['metrics']['recall_id']:.2f}% | {100*item['difference_from_leader']['recall_id']['mean_delta']:+.2f} pp |")
    lines += ['', '## Observed potential and selection stability', '',
        '| Selection by | Best single recall | Per-query best recall | Grouped selection recall |', '|---|---:|---:|---:|']
    for name,v in results['selected'].items():
        lines.append(f"| {name} | {100*v['metrics']['recall_id']:.2f}% | {100*v['per_query_best']['recall_id']:.2f}% | {100*v['grouped_selection']['recall_id']:.2f}% |")
    lines += ['', 'Per-query best uses reference outcomes to choose a different complete policy for every query; it is a diagnostic, not a deployable selector. Grouped selection chooses one configuration using all other product-prefix groups and applies it unchanged to the held-out group, repeating across groups. It is retrospective selection-robustness evidence; the data and construction space have already been inspected, so this is not independent final validation.', '',
        'All means use the same available query population. Precision excludes undefined empty-retrieval values; per-query F1 is zero for empty retrieval. Full outcomes, losses, cohort splits and group selections are in `results.json`. The live view exposes the same frozen conditions and source movements.']
    with (OUT / 'RESULTS.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines)+'\n')
    print(json.dumps({k:results[k] for k in ('cases','configurations','product_groups','canonical','area_first')}, indent=2))
    print(json.dumps({'leaders':{k:{'configuration':v['configuration'],'policy':v['policy'],'metrics':v['metrics'],
        'per_query_best':v['per_query_best'],'grouped_selection':v['grouped_selection']} for k,v in results['selected'].items()}},indent=2))


if __name__ == '__main__':
    main()
