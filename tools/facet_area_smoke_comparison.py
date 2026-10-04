"""Compare smoke inputs and aggregate metrics without exposing benchmark text."""
from pathlib import Path
import json
import sys

import numpy as np
import facet_joint_gold_smoke as W


OLD = W.RUN_ROOT / ('artefact_facet_joint__10smoke__cb72000__20260922T071854164747Z'
                    '__format-retry1')


def signature(value):
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def numerical_record(row):
    m = row['meta']
    return {
        'interpretation_signature': signature({k: m['interpreter'][k] for k in ('description', 'tags')}),
        'scores': {r['chunk_id']: r['score'] for r in m['ranking']['rows']},
        'area': m['area']['area']['chunk_ids'],
        'budget': m['char_budget'],
        'graph_hashes': m['snapshot']['snapshot_sha256'],
        'context_ids': set(row['context_ids']),
        'cache_hits': [s['cache_hit'] for s in m['interpreter']['stages']],
    }


def main(folder):
    done = W.read_json(folder / 'completed.json')
    if done['phase'] not in ('completed', 'completed_with_metric_errors'):
        raise ValueError('Smoke must finish before comparison')
    old = {row['id']: numerical_record(row) for row in W.json_rows(OLD / 'arm_outputs.jsonl')}
    cases = []
    for row in W.json_rows(folder / 'arm_outputs.jsonl'):
        a, b = old.pop(row['id']), numerical_record(row)
        assert a['scores'].keys() == b['scores'].keys()
        difference = np.array([b['scores'][cid] - a['scores'][cid] for cid in a['scores']])
        cases.append({
            'question_id': row['id'],
            'same_interpretation': a['interpretation_signature'] == b['interpretation_signature'],
            'same_graph_inputs': a['graph_hashes'] == b['graph_hashes'],
            'identical_scores': bool((difference == 0).all()),
            'maximum_absolute_score_change': float(np.max(np.abs(difference))),
            'same_area': a['area'] == b['area'],
            'old_area_size': None if a['area'] is None else len(a['area']),
            'new_area_size': None if b['area'] is None else len(b['area']),
            'new_interpretation_cache_hits': sum(b['cache_hits']),
            'budget_unchanged': a['budget']['budget'] == b['budget']['budget'] == 72000,
            'context_id_intersection': len(a['context_ids'] & b['context_ids']),
            'old_context_ids': len(a['context_ids']), 'new_context_ids': len(b['context_ids']),
        })
    assert not old and len(cases) == 10
    metrics = W.read_json(folder / 'resume_plan.json')['metrics']
    old_metrics = W.aggregate_metrics(OLD.with_name(OLD.name + W.JUDGE_SUFFIX), metrics)
    new_metrics = W.aggregate_metrics(folder.with_name(folder.name + W.JUDGE_SUFFIX), metrics)
    result = {
        'cases': cases,
        'integrity': {key: sum(bool(c[key]) for c in cases) for key in
                      ('same_interpretation', 'same_graph_inputs', 'identical_scores', 'same_area', 'budget_unchanged')},
        'maximum_absolute_score_change': max(c['maximum_absolute_score_change'] for c in cases),
        'metrics': {name: {'old': old_metrics['metrics'][name], 'area': new_metrics['metrics'][name],
            'mean_delta': (new_metrics['metrics'][name]['mean'] - old_metrics['metrics'][name]['mean'])
                if new_metrics['metrics'][name]['mean'] is not None and old_metrics['metrics'][name]['mean'] is not None
                else None} for name in metrics},
        'input_sha256': {str(p): W.sha(p) for p in [Path(__file__), OLD / 'arm_outputs.jsonl',
                          folder / 'arm_outputs.jsonl', folder / 'aggregate_report.json']},
        'limits': ['Ten reused smoke questions; not an independent holdout.',
                   'Answer and LLM-judged metrics include generation/judge variability.',
                   'The scope policy, structural resolver and sponsor-first recovery differ from the old arm.'],
    }
    W.write_new(folder / 'smoke_comparison.json', result)
    W.emit({k: v for k, v in result.items() if k not in ('cases', 'input_sha256')})


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
