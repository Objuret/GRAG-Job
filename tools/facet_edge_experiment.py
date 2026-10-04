"""Paired conditional edge/query controls, frozen before reading outcomes."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import facet_retrieval_lab as L
import numpy as np
from facet_weight_channels import query_channels
from facet_edge_controls import edge_shuffle, query_shuffle

OUT = L.BASE/'edge-controls'
WEIGHTS = L.BASE/'weights'
SEEDS = list(range(8))
CELLS = ['RR', 'RS', 'SR', 'SS']
REGIMES = ['original', 'group_selected_topic_largest', 'topic_only']
_lab = None
_prepared = None
_coverage = None
_plan = None


def initialize():
    global _lab, _prepared, _coverage, _plan
    _lab = L.Lab()
    _plan = L.read(OUT/'plan.json')
    _prepared, _coverage = [], []
    for seed in SEEDS:
        facets, coverage = edge_shuffle(_lab.prepared, seed)
        _prepared.append(replace(_lab.prepared, edge_facets=facets))
        _coverage.append(coverage)


def run_case(record):
    start = time.perf_counter()
    lab, plan = _lab, _plan
    case = lab.case(record['case_id'])
    group = record['question_id'].split('::')[0]
    with np.load(L.INPUTS/record['npz'], allow_pickle=False) as data:
        matrices = {k:data[k].copy() for k in ('query_tag_cosines','query_chunk_cosines','query_description_cosines')}
        weights = data['query_facet_weights'].copy()
    query_variants = [query_shuffle(weights, record['question_id'], seed) for seed in SEEDS]
    metrics = np.empty((3,3,8,4,3))
    movement = np.zeros((3,3,8,4,2), dtype=np.int32)
    exact_baseline_checks = []
    selected_indices = []
    with np.load(WEIGHTS/(record['case_id']+'.npz'), allow_pickle=False) as data:
        prior = data['metrics'].copy()
    def measure(z, beta, policy):
        stream = np.sum(z*np.asarray(beta)[:,None], axis=0, keepdims=True)
        order, _, _, _ = L.schedule(stream, case['q'], policy, case['area_mask'], lab.components, lab.id_order)
        credit, full, budget = L.cut((lab.ids[i] for i in order), lab.units)
        m = lab.evaluate(case, dict(credit=credit, full=full, budget=budget))
        r,p = m['recall_id'],m['precision_id']
        values = [r, np.nan if p is None else p, 2*r*p/(r+p) if p is not None and r+p else 0.]
        rank = np.full(lab.n, lab.n+1, dtype=np.int32)
        rank[order] = np.arange(len(order))
        return values, rank, set(full)
    for s, structure in enumerate(plan['structures']):
        policy = structure['policy']
        index = plan['selected_coefficients'][structure['name']][group]
        selected_indices.append(index)
        betas = [(1,.25,.25,.25,.25),plan['vectors'][index]['coefficients'],(1,0,0,0,0)]
        real_channels = query_channels(lab.prepared, matrices, policy)
        real_z = (real_channels*weights.T[:,:,None]).max(axis=1)
        baseline = [measure(real_z, beta, policy) for beta in betas]
        for r, prior_index in [(0,0),(1,index)]:
            np.testing.assert_allclose(baseline[r][0],prior[s,prior_index],rtol=0,atol=1e-15,equal_nan=True)
        exact_baseline_checks.append(True)
        for k, seed in enumerate(SEEDS):
            altered_channels = query_channels(_prepared[k], matrices, policy)
            np.testing.assert_array_equal(real_channels[0],altered_channels[0])
            shuffled_weights = query_variants[k][0]
            zs = [real_z, (real_channels*shuffled_weights.T[:,:,None]).max(axis=1),
                  (altered_channels*weights.T[:,:,None]).max(axis=1),
                  (altered_channels*shuffled_weights.T[:,:,None]).max(axis=1)]
            for c,z in enumerate(zs):
                for r,beta in enumerate(betas):
                    value, rank, full = baseline[r] if c == 0 else measure(z,beta,policy)
                    metrics[s,r,k,c] = value
                    movement[s,r,k,c] = [np.count_nonzero(rank != baseline[r][1]),len(full ^ baseline[r][2])]
                    if r == 2:
                        np.testing.assert_array_equal(rank,baseline[r][1])
                        assert full == baseline[r][2]
    path = OUT/(record['case_id']+'.npz')
    with path.open('xb') as stream:
        np.savez_compressed(stream, metrics=metrics, movement=movement)
    meta = {k:record[k] for k in ('case_id','question_id','cohort')}
    meta.update(npz_sha256=L.digest(path),input_npz_sha256=L.digest(L.INPUTS/record['npz']),
        prior_weight_npz_sha256=L.digest(WEIGHTS/(record['case_id']+'.npz')),
        prior_metric_parity=exact_baseline_checks, topic_only_all_cells_invariant=True,
        selected_coefficient_indices=selected_indices, query_shuffle_coverage=[c for _,c in query_variants],
        edge_coverage_sha256=plan['edge_coverage_sha256'],elapsed_s=time.perf_counter()-start)
    L.atomic(OUT/(record['case_id']+'.json'),meta)
    return {k:meta[k] for k in ('case_id','elapsed_s')}


def freeze():
    done = L.read(WEIGHTS/'completed.json')
    assert done['status'] == 'completed' and not done['errors'] and done['source_hashes_unchanged']
    weight_plan = L.read(WEIGHTS/'plan.json')
    results = L.read(WEIGHTS/'analysis.json')
    selected = {name:{f['group']:f['coefficient_index'] for f in entry['selections']['topic_largest']['recall_id']['folds']}
                for name,entry in results['structures'].items()}
    # Coverage is determined entirely from graph metadata/values, with no outcome join.
    lab = L.Lab()
    coverage = [edge_shuffle(lab.prepared,seed)[1] for seed in SEEDS]
    L.write_new(OUT/'edge-coverage.json',coverage)
    paths = [Path(__file__),L.ROOT/'tools/facet_edge_controls.py',L.ROOT/'tools/facet_weight_channels.py',Path(L.__file__),
             L.ROOT/'test/artefact/facet_operator_matrix.py',L.INPUTS/'cases_manifest.json',
             WEIGHTS/'plan.json',WEIGHTS/'analysis.json',WEIGHTS/'completed.json',
             L.POINTERS/'gold_source_index.json',L.POINTERS/'chunk_delivery_index.json']
    paths += [L.ROOT/p for p in L.A.SMOKE_PROVENANCE_PATHS]
    plan = dict(created_utc=datetime.now(timezone.utc).isoformat(), structures=weight_plan['structures'],
        vectors=weight_plan['vectors'],selected_coefficients=selected,seeds=SEEDS,cells=CELLS,regimes=REGIMES,
        input_sha256={str(p.relative_to(L.ROOT)):L.digest(p) for p in dict.fromkeys(paths)},
        edge_coverage_sha256=L.digest(OUT/'edge-coverage.json'),metrics=['recall_id','precision_id','f1_id'],
        movement=['changed_full_order_positions','full_chunk_symmetric_difference'], cases=95,model_calls=0,
        actual_deliveries=21375, metric_cells_including_repeated_RR=27360,
        pairing='Same corpus edge permutation per seed across every query/structure/regime; same query row permutation per question/seed in RS and SS.',
        hypothesis='Useful within-tag/kind auxiliary placement and query-tag binding should improve source-ID delivery over paired shuffles.',
        measurement='RR-SR=edge placement effect; RR-RS=query binding effect; RR-RS-SR+SS=interaction; report seed means/ranges and paired case changes.',
        limits='Conditional shuffle also breaks relationships with topic strength, product and graph position. It is retrieval sensitivity, not proof of correct facet semantics. Eight seeds are repeated interventions on 95 cases, not independent question samples. Structures and coefficient selection are retrospective.')
    L.write_new(OUT/'plan.json',plan)
    return plan


def main(workers):
    plan = freeze()
    records = L.read(L.INPUTS/'cases_manifest.json')['cases']
    errors = []
    with ProcessPoolExecutor(max_workers=workers, initializer=initialize) as pool:
        futures = {pool.submit(run_case,record):record['case_id'] for record in records}
        for future in as_completed(futures):
            try:
                print(json.dumps(future.result()),flush=True)
            except Exception as exc:
                errors.append(dict(case_id=futures[future],error=repr(exc)))
                print(json.dumps(errors[-1]),flush=True)
    unchanged = all(L.digest(L.ROOT/p)==h for p,h in plan['input_sha256'].items())
    count = len(list(OUT.glob('case_*.json')))
    status = dict(status='completed' if not errors and unchanged and count==95 else 'failed',errors=errors,
                  source_hashes_unchanged=unchanged,completed_cases=count)
    L.write_new(OUT/'completed.json',status)
    print(json.dumps(status),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=3)
    main(parser.parse_args().workers)
