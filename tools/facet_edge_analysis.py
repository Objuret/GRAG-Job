"""Paired effects of conditional edge placement and query-tag binding."""
from pathlib import Path
import numpy as np
import facet_retrieval_lab as L
from facet_matrix_analyze import summary
from facet_edge_experiment import OUT


def effect(values, groups):
    case_means = np.nanmean(values,axis=1)
    seed_means = np.nanmean(values,axis=0)
    output = {}
    for m,name in enumerate(('recall_id','precision_id','f1_id')):
        v = case_means[:,m]
        output[name] = dict(mean=float(np.nanmean(v)),
            seed_mean_min=float(np.nanmin(seed_means[:,m])), seed_mean_max=float(np.nanmax(seed_means[:,m])),
            seed_means=seed_means[:,m].tolist(), positive_effect_cases=int((v>1e-12).sum()),
            negative_effect_cases=int((v < -1e-12).sum()),tied_cases=int((np.abs(v)<=1e-12).sum()),
            equal_product_mean=float(np.nanmean([np.nanmean(v[groups==g]) for g in sorted(set(groups))])))
    return output


def main():
    done = L.read(OUT/'completed.json')
    assert done['status']=='completed' and not done['errors'] and done['source_hashes_unchanged']
    plan = L.read(OUT/'plan.json')
    records = L.read(L.INPUTS/'cases_manifest.json')['cases']
    metrics,movements,metas = [],[],[]
    for record in records:
        meta = L.read(OUT/(record['case_id']+'.json'))
        path = OUT/(record['case_id']+'.npz')
        assert L.digest(path)==meta['npz_sha256']
        assert all(meta['prior_metric_parity']) and meta['topic_only_all_cells_invariant']
        with np.load(path,allow_pickle=False) as data:
            metrics.append(data['metrics']); movements.append(data['movement'])
        metas.append(meta)
    values, movement = np.asarray(metrics),np.asarray(movements)
    assert values.shape == (95,3,3,8,4,3)
    groups = np.asarray([m['question_id'].split('::')[0] for m in metas])
    report = dict(cases=95, product_groups=len(set(groups)), seeds=plan['seeds'],
        source_hashes_unchanged=True,edge_coverage=L.read(OUT/'edge-coverage.json'),structures={},limits=plan['limits'],
        analysis_sha256=L.digest(Path(__file__)))
    for s,structure in enumerate(plan['structures']):
        regimes = {}
        for r,name in enumerate(plan['regimes']):
            v = values[:,s,r]
            rr,rs,sr,ss = (v[:,:,c,:] for c in range(4))
            regimes[name] = dict(cells={label:summary(np.nanmean(v[:,:,c,:],axis=1)) for c,label in enumerate(plan['cells'])},
                edge_placement=effect(rr-sr,groups), query_binding=effect(rr-rs,groups),
                interaction=effect(rr-rs-sr+ss,groups),
                movement={label:dict(mean_changed_rank_positions=float(movement[:,s,r,:,c,0].mean()),
                    mean_full_chunk_symmetric_difference=float(movement[:,s,r,:,c,1].mean()),
                    cases_with_any_full_chunk_set_change=int(np.any(movement[:,s,r,:,c,1]>0,axis=1).sum()))
                    for c,label in enumerate(plan['cells'])})
            if name=='topic_only':
                assert not movement[:,s,r].any()
                np.testing.assert_array_equal(rr,rs); np.testing.assert_array_equal(rr,sr); np.testing.assert_array_equal(rr,ss)
        report['structures'][structure['name']] = regimes
    L.write_new(OUT/'analysis.json',report)
    lines=['# Conditional edge placement and query-tag binding', '',
        '95 saved queries; eight paired shuffle seeds; three structures; original, group-selected and topic-only coefficient regimes. No model calls.', '',
        'Positive edge-placement and query-binding effects favor real assignments. Positive interaction means the two real assignments help more together on the metric scale; it does not imply either main effect is positive. Effects are paired source-ID recall differences, averaged over seeds and queries; seeds are repeated interventions, not additional independent queries.', '',
        '| Structure | Coefficients | Real recall | Edge placement effect | Query binding effect | Interaction |',
        '|---|---|---:|---:|---:|---:|']
    for structure,regimes in report['structures'].items():
        for name,entry in regimes.items():
            if name=='topic_only':
                continue
            effects=[entry[k]['recall_id']['mean'] for k in ('edge_placement','query_binding','interaction')]
            lines.append(f"| {structure} | {name} | {100*entry['cells']['RR']['recall_id']:.2f}% | "+' | '.join(f'{100*x:+.2f} pp' for x in effects)+' |')
    lines += ['', 'All topic-only full orders and delivered chunk sets remain exactly invariant across cells and seeds. Real-condition original/group-selected metrics match the previous weight-grid results for every case and structure.', '',
        'Edge vectors are shuffled jointly within graph tag × source kind. This preserves the conditional vector distribution but also breaks associations with topic strength, products and graph position. A positive effect establishes useful placement under these conditions, not semantic validity by itself. Low sensitivity cannot prove irrelevance when movable coverage or downstream delivery changes are limited.', '',
        'Coverage, seed ranges, precision/F1 effects, per-case signs, equal-product averages and ranking/full-chunk-set movement are retained in `analysis.json`. Full-chunk-set movement does not measure changes to the final partial chunk. Existing structures and coefficient choices are retrospective.']
    (OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))


if __name__=='__main__':
    main()
