"""Summarize the frozen weight grid and fixed-weight binding interventions."""
from collections import Counter
import json
import numpy as np
import facet_retrieval_lab as L
from facet_matrix_analyze import select, summary, paired
from facet_weight_experiment import OUT


def main():
    done = L.read(OUT/'completed.json')
    assert done['status'] == 'completed' and done['source_hashes_unchanged'] and not done['errors']
    plan = L.read(OUT/'plan.json')
    records = L.read(L.INPUTS/'cases_manifest.json')['cases']
    values, controls, metas = [], [], []
    for record in records:
        meta = L.read(OUT/(record['case_id']+'.json'))
        path = OUT/(record['case_id']+'.npz')
        assert L.digest(path) == meta['npz_sha256']
        with np.load(path, allow_pickle=False) as data:
            values.append(data['metrics'])
            controls.append(data['control_metrics'])
        metas.append(meta)
    values, controls = np.asarray(values), np.asarray(controls)
    groups = np.asarray([m['question_id'].split('::')[0] for m in metas])
    report = dict(cases=len(records), coefficient_settings=len(plan['vectors']), controls=len(plan['controls']),
                  original_interpretation_failures=5, structures={}, limits=plan['limits'])
    for s, structure in enumerate(plan['structures']):
        base = values[:, s, 0]
        entry = dict(original=summary(base), selections={}, controls=[])
        for subset in ('unrestricted', 'topic_present', 'topic_largest'):
            indices = np.asarray([i for i,v in enumerate(plan['vectors']) if subset == 'unrestricted' or v[subset]])
            block = values[:, s, indices]
            chosen = {}
            for metric, name in enumerate(('recall_id','precision_id','f1_id')):
                best = int(indices[select(block, metric)])
                held = np.empty((len(records), 3))
                folds = []
                for group in sorted(set(groups)):
                    test = groups == group
                    selected = int(indices[select(block[~test], metric)])
                    held[test] = values[test, s, selected]
                    folds.append(dict(group=group, coefficient_index=selected, heldout_cases=int(test.sum())))
                chosen[name] = dict(coefficient_index=best, vector=plan['vectors'][best],
                    metrics=summary(values[:,s,best]), difference_from_original=paired(values[:,s,best],base),
                    grouped_selection=summary(held), grouped_difference=paired(held,base), folds=folds,
                    fold_coefficient_counts=dict(Counter(f['coefficient_index'] for f in folds)))
            entry['selections'][subset] = chosen
        for j, label in enumerate(plan['controls']):
            entry['controls'].append(dict(label=label, metrics=summary(controls[:,s,j]),
                difference_from_real=paired(controls[:,s,j],base),
                changed_cases=sum(m['control_changed_cells'][label] > 0 for m in metas)))
        report['structures'][structure['name']] = entry
    L.write_new(OUT/'analysis.json', report)
    lines = ['# Coefficient and query-binding replay results', '',
             '95 saved queries, three frozen structures, 509 coefficient settings and 26 fixed-weight query interventions. No new model calls.', '',
             '| Structure | Original recall | Best topic-largest recall | Group-selected recall | Best coefficients (topic, temporal, why, activity, concreteness) |',
             '|---|---:|---:|---:|---|']
    for name, entry in report['structures'].items():
        best = entry['selections']['topic_largest']['recall_id']
        lines.append(f"| {name} | {100*entry['original']['recall_id']:.2f}% | {100*best['metrics']['recall_id']:.2f}% | {100*best['grouped_selection']['recall_id']:.2f}% | {best['vector']['coefficients']} |")
    lines += ['', 'Grouped selection excludes every query from the evaluated product-prefix group during coefficient selection. The structures and dataset were previously inspected, so this remains retrospective evidence.', '',
              '## Fixed-weight query interventions', '', '| Structure | Control | Recall | Change from real |', '|---|---|---:|---:|']
    for name, entry in report['structures'].items():
        for control in entry['controls']:
            if not control['label'].startswith('perm:'):
                lines.append(f"| {name} | {control['label']} | {100*control['metrics']['recall_id']:.2f}% | {100*control['difference_from_real']['recall_id']['mean_delta']:+.2f} pp |")
        permutation = [c['metrics']['recall_id'] for c in entry['controls'] if c['label'].startswith('perm:')]
        lines.append(f"| {name} | 23 nonidentity facet-label permutations (range) | {100*min(permutation):.2f}–{100*max(permutation):.2f}% | — |")
    lines += ['', 'These controls retain topic and do not retune coefficients. Label permutations test named facet alignment; row reassignment tests assigning auxiliary vectors to particular query tags. These are deterministic sensitivities, not permutation-test p-values. Edge construct validity and controls at selected coefficients remain unverified.', '',
              'All precision/F1 values, paired gains/losses, unrestricted diagnostics, fold choices and changed-cell counts are retained in `analysis.json` and case metadata.']
    (OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
