"""Frozen coefficient sensitivity and query-facet binding experiment; no LLMs."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import itertools
import json
from math import gcd
from functools import reduce
from pathlib import Path
import time
import facet_retrieval_lab as L
import numpy as np

OUT = L.BASE / 'weights'
_lab = None


def designs():
    old = L.read(L.BASE / 'batch/plan.json')['configurations']
    structures = [dict(name='canonical', policy=L.DEFAULT),
                  dict(name='recall_leader', policy=old[3664]),
                  dict(name='f1_leader', policy=old[2628])]
    vectors, seen = [], set()
    # Put the actual current coefficients first; ties retain them.
    raw = [(4, 1, 1, 1, 1)]
    raw += [(4, *bits) for bits in itertools.product((0, 1), repeat=4)]
    raw += [v for v in itertools.product(range(9), repeat=5) if sum(v) == 8]
    for v in raw:
        divisor = reduce(gcd, v)
        key = tuple(x // divisor for x in v)
        if key not in seen:
            seen.add(key)
            vectors.append({'units': list(v), 'coefficients': [x / 4 for x in v],
                            'topic_largest': v[0] >= max(v[1:]), 'topic_present': v[0] > 0})
    controls = ['aux_row_mean', 'aux_rows_roll1', 'aux_rows_reverse']
    controls += ['perm:' + ','.join(map(str, p)) for p in itertools.permutations(range(1, 5)) if p != (1, 2, 3, 4)]
    return structures, vectors, controls


def initialize():
    global _lab
    _lab = L.Lab()


def query_control(weights, label):
    out = weights.copy()
    if label == 'aux_row_mean':
        out[:, 1:] = weights[:, 1:].mean(axis=1, keepdims=True)
    elif label == 'aux_rows_roll1':
        out[:, 1:] = np.roll(weights[:, 1:], 1, axis=0)
    elif label == 'aux_rows_reverse':
        out[:, 1:] = weights[::-1, 1:]
    else:
        out[:, 1:] = weights[:, [int(x) for x in label[5:].split(',')]]
    return out


def run_case(record):
    from facet_weight_channels import query_channels
    start = time.perf_counter()
    lab = _lab
    case = lab.case(record['case_id'])
    structures, vectors, controls = designs()
    with np.load(L.INPUTS / record['npz'], allow_pickle=False) as data:
        matrices = {k: data[k].copy() for k in ('query_tag_cosines', 'query_chunk_cosines', 'query_description_cosines')}
        weights = data['query_facet_weights'].copy()
    def measure(z, coefficients, policy):
        # Never reuse depth_cache across different coefficients or controls.
        streams = np.sum(z * np.asarray(coefficients)[:, None], axis=0, keepdims=True)
        order, _, _, _ = L.schedule(streams, case['q'], policy, case['area_mask'], lab.components, lab.id_order)
        credit, full, budget = L.cut((lab.ids[i] for i in order), lab.units)
        metric = lab.evaluate(case, {'credit': credit, 'full': full, 'budget': budget})
        r, p = metric['recall_id'], metric['precision_id']
        f1 = 2*r*p/(r+p) if p is not None and r+p else 0.
        return [r, np.nan if p is None else p, f1], order
    values = np.empty((len(structures), len(vectors), 3))
    control_values = np.empty((len(structures), len(controls), 3))
    parity = []
    for s, structure in enumerate(structures):
        policy = structure['policy']
        key = tuple(policy[k] for k in ('match', 'topology', 'graph_join')) + ('separate_facet_streams',)
        z = case['families'][key] / np.asarray([1, .25, .25, .25, .25])[:, None]
        for j, vector in enumerate(vectors):
            values[s, j], order = measure(z, vector['coefficients'], policy)
            if j == 0:
                original = lab.retrieve(case, policy)
                assert np.array_equal(order, original['order']), 'Default coefficient order parity failed'
                parity.append(True)
        reusable = query_channels(lab.prepared, matrices, policy)
        actual = (reusable * weights.T[:, :, None]).max(axis=1)
        np.testing.assert_allclose(actual, z, rtol=2e-14, atol=1e-16)
        _, factored_order = measure(actual, (1, .25, .25, .25, .25), policy)
        assert np.array_equal(factored_order, original['order']), 'Factored query channel order parity failed'
        for j, control in enumerate(controls):
            altered = (reusable * query_control(weights, control).T[:, :, None]).max(axis=1)
            control_values[s, j], _ = measure(altered, (1, .25, .25, .25, .25), policy)
    path = OUT / (record['case_id'] + '.npz')
    with path.open('xb') as stream:
        np.savez_compressed(stream, metrics=values, control_metrics=control_values)
    meta = {k: record[k] for k in ('case_id', 'question_id', 'cohort')}
    meta.update(npz_sha256=L.digest(path), input_npz_sha256=L.digest(L.INPUTS / record['npz']),
                default_order_parity=parity, query_tags=len(weights),
                control_changed_cells={c: int(np.count_nonzero(query_control(weights, c) != weights)) for c in controls},
                elapsed_s=time.perf_counter()-start)
    L.atomic(OUT / (record['case_id'] + '.json'), meta)
    return {k: meta[k] for k in ('case_id', 'elapsed_s')}


def main(workers):
    structures, vectors, controls = designs()
    manifest = L.read(L.INPUTS / 'cases_manifest.json')
    paths = [Path(__file__), L.ROOT/'tools/facet_weight_channels.py', Path(L.__file__),
             L.ROOT/'test/artefact/facet_operator_matrix.py', L.INPUTS/'cases_manifest.json',
             L.BASE/'batch/plan.json', L.POINTERS/'gold_source_index.json', L.POINTERS/'chunk_delivery_index.json']
    paths += [L.ROOT/p for p in L.A.SMOKE_PROVENANCE_PATHS]
    hashes = {str(p.relative_to(L.ROOT)): L.digest(p) for p in dict.fromkeys(paths)}
    plan = dict(created_utc=datetime.now(timezone.utc).isoformat(), structures=structures,
                vectors=vectors, controls=controls, input_sha256=hashes,
                cases=95, metrics=['recall_id', 'precision_id', 'f1_id'], model_calls=0,
                hypotheses=['fixed coefficient attenuation', 'query-specific auxiliary label binding', 'structure interaction'],
                interpretation='Exploratory eighth-simplex resolution, not exact continuous optimum; topic-zero and non-topic-dominant weights are diagnostic alternatives, not production decisions.',
                controls_note='All 24 global auxiliary label permutations including identity; exhaustive label sensitivity, not a statistical permutation test. Row mean preserves each query tag auxiliary mass. Row roll and reversal reassign complete auxiliary vectors across query tags. Topic is untouched in every control; changed cell counts record no-op cases.',
                limits='No edge-value shuffle here; edge construct validity remains unresolved. Reused cases and outcome-selected structures; grouped coefficient selection is retrospective robustness only.')
    L.write_new(OUT/'plan.json', plan)
    errors = []
    with ProcessPoolExecutor(max_workers=workers, initializer=initialize) as pool:
        futures = {pool.submit(run_case, rec): rec['case_id'] for rec in manifest['cases']}
        for future in as_completed(futures):
            try:
                print(json.dumps(future.result()), flush=True)
            except Exception as exc:
                errors.append({'case_id': futures[future], 'error': repr(exc)})
                print(json.dumps(errors[-1]), flush=True)
    unchanged = all(L.digest(L.ROOT/p) == h for p, h in hashes.items())
    completed = len(list(OUT.glob('case_*.json')))
    status = dict(status='completed' if not errors and unchanged and completed == 95 else 'failed',
                  errors=errors, source_hashes_unchanged=unchanged, completed_cases=completed)
    L.write_new(OUT/'completed.json', status)
    print(json.dumps(status), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=3)
    main(parser.parse_args().workers)
