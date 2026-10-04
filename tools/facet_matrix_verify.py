"""Independent cached-delivery/RAGAS checks with predeclared policy choices.

No inference, embeddings or benchmark language export. Actual corpus text is
processed solely to verify serialization and prefix delivery mechanically.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path

os.environ['RAGAS_DO_NOT_TRACK'] = 'true'
os.environ['RAGAS_DEBUG_TRACKING'] = 'false'

import numpy as np
import facet_retrieval_lab as L
from ragas.dataset_schema import SingleTurnSample
from ragas.metrics._context_precision import IDBasedContextPrecision
from ragas.metrics._context_recall import IDBasedContextRecall


# Fixed by the verification task, before reading condition outcomes.
POLICIES = [
    ('canonical', dict(L.DEFAULT)),
    ('area_first', {**L.DEFAULT, 'scope': 'area_first'}),
    ('separate_facet_streams', {**L.DEFAULT, 'facet': 'separate_facet_streams'}),
    ('tag_only', {**L.DEFAULT, 'match': 'tag_only'}),
    ('description_union', {**L.DEFAULT, 'description': 'independent_union'}),
    ('graph_only', {**L.DEFAULT, 'graph_join': 'graph_only'}),
]
CASES = [f'case_{i:03d}' for i in range(1, 11)]
TEXT_CASES = set(CASES[:2])
TEXT_POLICIES = {'canonical', 'area_first'}
METRICS = ['recall_id', 'precision_id', 'hits', 'gold_count', 'retrieved_ids', 'delivered_chars', 'full_chunks']


def same_float(a, b):
    return bool((np.isnan(a) and np.isnan(b)) or abs(a - b) < 1e-15)


async def main():
    out = L.BASE / 'verification/metric_delivery.json'
    if out.exists():
        raise ValueError('Verification already exists; refusing overwrite')
    batch = L.BASE / 'batch'
    plan_path = batch / 'plan.json'
    plan = L.read(plan_path)
    for path, expected in plan['input_sha256'].items():
        assert L.digest(L.ROOT / path) == expected, 'Frozen matrix input changed'
    condition_indices = {name: plan['configurations'].index(policy) for name, policy in POLICIES}
    paths = [Path(__file__), Path(inspect.getfile(IDBasedContextPrecision)),
             Path(inspect.getfile(IDBasedContextRecall)), plan_path]
    for case_id in CASES:
        paths += [batch / (case_id + '.json'), batch / (case_id + '.npz'),
                  L.INPUTS / (case_id + '.json'), L.INPUTS / (case_id + '.npz')]
    hashes = {str(path.relative_to(L.ROOT)) if path.is_relative_to(L.ROOT) else str(path): L.digest(path)
              for path in paths}
    lab = L.Lab()
    recall, precision = IDBasedContextRecall(), IDBasedContextPrecision()
    checks, text_checks = [], []
    for case_id in CASES:
        meta = L.read(batch / (case_id + '.json'))
        assert meta['npz_sha256'] == L.digest(batch / (case_id + '.npz'))
        assert meta['input_meta_sha256'] == L.digest(L.INPUTS / (case_id + '.json'))
        assert meta['input_npz_sha256'] == L.digest(L.INPUTS / (case_id + '.npz'))
        with np.load(batch / (case_id + '.npz'), allow_pickle=False) as z:
            recorded = z['metrics'].copy()
        case = lab.case(case_id)
        for name, policy in POLICIES:
            result = lab.retrieve(case, policy)
            # Evaluation inputs enter only after ordering and delivery complete.
            gold = set(lab.gold['questions'][case['meta']['question_id']])
            credit = result['credit']
            sample = SingleTurnSample(retrieved_context_ids=sorted(credit), reference_context_ids=sorted(gold))
            r = float(await recall.single_turn_ascore(sample))
            p = float(await precision.single_turn_ascore(sample))
            independent = [r, p, len(gold & credit), len(gold), len(credit),
                           result['budget']['chars'], len(result['full'])]
            assert all(same_float(a, b) for a, b in zip(independent, recorded[condition_indices[name]])), 'Batch metric mismatch'
            checks.append({'case_id': case_id, 'policy': name, 'condition_index': condition_indices[name],
                           'metrics_match': True, 'precision_defined': bool(np.isfinite(p))})
            if case_id in TEXT_CASES and name in TEXT_POLICIES:
                ordered = [lab.prepared.chunks[i] for i in result['order']]
                docs = {}
                contexts, id_lists, actual_credit, actual_budget = L.A._budget_contexts(ordered, 72000, docs)
                assert actual_budget == result['budget'] and set(actual_credit) == credit, 'Actual resolver/budget mismatch'
                expected_contexts, expected_ids = [], []
                count = actual_budget['kept'] + int(actual_budget['boundary'] is not None)
                for i, row in enumerate(ordered[:count]):
                    text, ids = L.A._resolve_chunk(row, docs)
                    unit = lab.units[row['chunkId']]
                    assert len(text) == unit['serialized_chars'] and ids == unit['artifact_ids'], 'Unit index mismatch'
                    if i == actual_budget['kept']:
                        text = text[:actual_budget['boundary']['chars_kept']]
                    expected_contexts.append(text)
                    expected_ids.append(ids)
                assert contexts == expected_contexts and id_lists == expected_ids, 'Full context serialization mismatch'
                assert result['full'] == [r['chunkId'] for r in ordered[:actual_budget['kept']]]
                expected_credit = set().union(*(set(v) for v in id_lists[:actual_budget['kept']]))
                assert credit == expected_credit, 'Partial boundary incorrectly credited'
                text_checks.append({'case_id': case_id, 'policy': name, 'exact_text_and_ids_match': True,
                    'context_count': len(contexts), 'serialized_characters': sum(map(len, contexts)),
                    'partial_boundary': actual_budget['boundary'] is not None,
                    'text_payload_sha256': hashlib.sha256(json.dumps(contexts, ensure_ascii=False).encode()).hexdigest()})
        print(json.dumps({'verified_cases': len(checks) // len(POLICIES), 'policy_checks': len(checks)}), flush=True)
    for path, expected in plan['input_sha256'].items():
        assert L.digest(L.ROOT / path) == expected, 'Frozen matrix input changed during check'
    for path, expected in hashes.items():
        assert L.digest(L.ROOT / path) == expected, 'Verified artifact changed during check'
    report = {'status': 'pass', 'ragas_version': importlib.metadata.version('ragas'),
        'hashes': hashes, 'predeclared_cases': CASES,
        'predeclared_policies': [{'name': name, 'policy': policy} for name, policy in POLICIES],
        'policy_metric_checks': checks, 'actual_resolver_budget_checks': text_checks,
        'ragas_metric_calls': 2 * len(checks), 'exact_text_delivery_checks': len(text_checks),
        'language_model_calls': 0, 'embedding_calls': 0, 'text_exported': False,
        'scope': 'Selected conditions on ten completed cases; not exhaustive verification of every matrix cell or semantic validity.'}
    L.write_new(out, report)
    print(json.dumps({'status': 'pass', 'policy_checks': len(checks), 'ragas_calls': 2 * len(checks),
                      'exact_text_delivery_checks': len(text_checks)}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
