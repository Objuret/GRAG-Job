"""One prespecified scope-scheduling intervention on saved numerical traces."""
from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
from pathlib import Path
import sys

os.environ['RAGAS_DO_NOT_TRACK'] = 'true'
os.environ['RAGAS_DEBUG_TRACKING'] = 'false'
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test'), str(ROOT / 'tools')]
import numpy as np
import facet_gold_trace as T
from facet_gold90_stage_budget import cut
from artefact.facet_scope_recruitment import recruit_with_verified_area
from ragas.dataset_schema import SingleTurnSample
from ragas.metrics._context_precision import IDBasedContextPrecision
from ragas.metrics._context_recall import IDBasedContextRecall

CONDITIONS = [('equal_depth', 'joint'), ('equal_depth', 'topic'),
              ('area_first', 'joint'), ('area_first', 'topic')]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def summarize(cases, total):
    names = ['archived'] + [a + '/' + b for a, b in CONDITIONS]
    result = {'successful_cases': len(cases), 'planned_cases': total, 'conditions': {}, 'effects': {}}
    for name in names:
        rows = [c['conditions'][name] for c in cases]
        result['conditions'][name] = {
            'context_recall_id': sum(r['context_recall_id'] for r in rows) / len(rows),
            'context_precision_id': sum(r['context_precision_id'] for r in rows) / len(rows),
            'recall_missing_retrieval_zero': sum(r['context_recall_id'] for r in rows) / total,
            'source_question_hits': sum(r['gold_hits'] for r in rows),
            'retrieved_source_ids': sum(r['retrieved_ids'] for r in rows),
            'fully_delivered_chunks': sum(r['full_chunks'] for r in rows),
            'full_in_area_chars': sum(r['full_in_area_chars'] for r in rows),
            'full_outside_area_chars': sum(r['full_outside_area_chars'] for r in rows),
            'full_unscoped_chars': sum(r['full_unscoped_chars'] for r in rows),
        }
    comparisons = {
        'scope_effect_joint': ('area_first/joint', 'equal_depth/joint'),
        'scope_effect_topic': ('area_first/topic', 'equal_depth/topic'),
        'facet_effect_equal_depth': ('equal_depth/joint', 'equal_depth/topic'),
        'facet_effect_area_first': ('area_first/joint', 'area_first/topic'),
        'sponsor_repair': ('equal_depth/joint', 'archived'),
    }
    for name, (on, off) in comparisons.items():
        result['effects'][name] = {'on': on, 'off': off}
        for metric in ('context_recall_id', 'context_precision_id'):
            deltas = [c['conditions'][on][metric] - c['conditions'][off][metric] for c in cases]
            result['effects'][name][metric] = {
                'mean_delta': sum(deltas) / len(deltas), 'better': sum(d > 0 for d in deltas),
                'worse': sum(d < 0 for d in deltas), 'ties': sum(d == 0 for d in deltas),
            }
    return result


async def main(folder):
    out = folder / 'area_admission_diagnosis'
    out.mkdir(exist_ok=True)
    if (out / 'started.json').exists():
        raise ValueError('Audit already started; inspect its state, do not overwrite')
    source = folder / 'arm_outputs.jsonl'
    unit_path = T.OUT / 'chunk_delivery_index.json'
    index_path = T.OUT / 'gold_source_index.json'
    verification = T.read(T.OUT / 'verification.json')
    units = T.read(unit_path)
    assert sha(unit_path) == verification['unit_index_sha256']
    assert sha(index_path) == verification['index_sha256']
    graph = T.read(T.SNAPSHOT / 'graph.json')
    chunks = graph['chunks']
    ids = [c['chunkId'] for c in chunks]
    expected = {r['id'] for r in T.rows(folder / 'remaining90.jsonl')}
    failed = [r['id'] for r in T.rows(folder / 'failures.jsonl')]
    assert len(expected) == 90 and len(set(failed)) == len(failed) == 5
    metrics = [('context_precision_id', IDBasedContextPrecision()),
               ('context_recall_id', IDBasedContextRecall())]
    code_paths = [Path(__file__), ROOT / 'docs/2026-09-22-area-admission-protocol.md',
                  ROOT / 'tools/facet_gold90_stage_budget.py', Path(T.__file__),
                  ROOT / 'test/artefact/facet_scope_recruitment.py',
                  ROOT / 'test/artefact/facet_recruitment_candidate.py',
                  ROOT / 'test/artefact/facet_need_frontier.py',
                  ROOT / 'prod/harness/char_budget.py',
                  Path(inspect.getfile(IDBasedContextPrecision)),
                  Path(inspect.getfile(IDBasedContextRecall))]
    hashes = {str(p): sha(p) for p in code_paths + [unit_path, index_path, T.SNAPSHOT / 'graph.json']}
    expected_input_hash = T.read(folder / 'graph_route_diagnosis/route_audit.json')['input_sha256']
    plan = {'created_utc': datetime.now(timezone.utc).isoformat(), 'conditions': CONDITIONS,
            'source_hashes': hashes, 'trace_sha256': expected_input_hash,
            'ragas_version': importlib.metadata.version('ragas'), 'budget': 72000,
            'area_source': 'Saved resolved area only; no benchmark product or new resolution',
            'model_calls': 0, 'gold_join': 'After every condition has fixed its delivery'}
    T.write(out / 'plan.json', plan)
    T.write(out / 'started.json', {'pid': os.getpid(), 'plan_sha256': sha(out / 'plan.json')})
    index = T.read(index_path)
    cases, seen, scopes = [], set(), Counter()
    digest = hashlib.sha256()
    with source.open('rb') as stream, (out / 'source_movements.jsonl').open('x', encoding='utf-8') as movements:
        for raw in stream:
            digest.update(raw)
            if not raw.strip():
                continue
            saved = json.loads(raw)
            qid, meta = saved['id'], saved['meta']
            assert qid in expected and qid not in seen and qid not in failed
            seen.add(qid)
            assert meta['snapshot']['snapshot_sha256']['graph.json'] == hashes[str(T.SNAPSHOT / 'graph.json')]
            rows = {r['chunk_id']: r for r in meta['ranking']['rows']}
            assert set(rows) == set(ids)
            assert meta['ranking']['coefficients'] == [1, .25, .25, .25, .25]
            area_ids = meta['area']['area']['chunk_ids']
            area = set(area_ids) if area_ids is not None else None
            scopes['resolved' if area is not None else 'unresolved'] += 1
            archived = cut(meta['full_recovered_order'], units)
            assert archived[0] == set(saved['context_ids'])
            assert archived[2] == meta['char_budget']
            deliveries = {'archived': archived}
            for scheduling, score_name in CONDITIONS:
                values = np.array([rows[c]['score'] if score_name == 'joint' else
                    (rows[c]['provenance']['topic'] or {}).get('contribution', 0.) for c in ids])
                recruited = recruit_with_verified_area(
                    chunk_rows=chunks, joint_scores=values, area_chunk_ids=area_ids,
                    source_character_budget=None, scheduling=scheduling)
                order = recruited['recruitment']['selected_chunk_ids']
                assert len(order) == len(set(order))
                deliveries[scheduling + '/' + score_name] = cut(order, units)
            if area is None:
                for name in ('joint', 'topic'):
                    assert deliveries['equal_depth/' + name] == deliveries['area_first/' + name]
            # Gold joins only after all complete/partial delivery decisions.
            gold = set(index['questions'][qid])
            assert gold
            case = {'question_id': qid, 'area_size': None if area is None else len(area), 'conditions': {}}
            for name, (credit, kept, budget) in deliveries.items():
                hits = len(gold & credit)
                assert credit and budget['chars'] <= 72000
                sample = SingleTurnSample(retrieved_context_ids=sorted(credit), reference_context_ids=sorted(gold))
                measured = {}
                for key, metric in metrics:
                    value = float(await metric.single_turn_ascore(sample))
                    denom = len(credit) if key == 'context_precision_id' else len(gold)
                    assert math.isfinite(value) and abs(value - hits / denom) < 1e-15
                    measured[key] = value
                case['conditions'][name] = {**measured, 'gold_hits': hits, 'retrieved_ids': len(credit),
                    'full_chunks': len(kept), 'budget': budget,
                    'full_in_area_chars': sum(units[c]['serialized_chars'] for c in kept if area is not None and c in area),
                    'full_outside_area_chars': sum(units[c]['serialized_chars'] for c in kept if area is not None and c not in area),
                    'full_unscoped_chars': sum(units[c]['serialized_chars'] for c in kept) if area is None else 0}
            movements.write(json.dumps({'question_id': qid, 'gold_ids': sorted(gold),
                'conditions': {name: {'credited_ids': sorted(delivery[0]), 'full_chunk_ids': delivery[1]}
                               for name, delivery in deliveries.items()}}) + '\n')
            cases.append(case)
            if len(cases) % 10 == 0:
                print(json.dumps({'completed_saved_cases': len(cases), 'expected': 85}), flush=True)
    assert len(cases) == 85 and seen | set(failed) == expected
    assert digest.hexdigest() == expected_input_hash
    assert all(sha(Path(p)) == value for p, value in hashes.items())
    summary = summarize(cases, len(expected))
    result = {'summary': summary, 'area_counts': dict(scopes), 'questions': cases,
              'failed_question_ids': failed, 'archived_budget_and_credit_parity': len(cases),
              'ragas_version': plan['ragas_version'], 'deterministic_metric_calls': len(cases) * 10,
              'model_calls': 0, 'new_embedding_calls': 0,
              'limits': 'Reused source-ID diagnostic; no new answers, independent holdout or semantic relevance judgments.'}
    T.write(out / 'results.json', result)
    print(json.dumps({'summary': summary, 'area_counts': dict(scopes)}, indent=2))


if __name__ == '__main__':
    asyncio.run(main(Path(sys.argv[1]).resolve()))
