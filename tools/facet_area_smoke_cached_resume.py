"""Complete one cached-failure case using its already successful interpretation.

Preserve the first area run and all nine new answers. This is not an interpreter
retry: the exact successful GENERATE/SCORE responses already exist from the
previous joint-arm smoke recovery. Only the missing new-arm answer is generated.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import sys
import time
import traceback

import facet_joint_gold_smoke as W


def main(parent):
    W.ARM = 'artefact_facet_area'
    W.PREFIX = W.ARM + '__10smoke__cb72000__'
    parent = parent.resolve()
    if parent.parent != W.RUN_ROOT.resolve() or not parent.name.startswith(W.PREFIX):
        raise W.SafeStop('invalid_parent')
    finished = W.read_json(parent / 'completed.json')
    report = W.read_json(parent / 'aggregate_report.json')
    if finished['phase'] != 'stopped' or report.get('reason_code') != 'generation_gate_failed':
        raise W.SafeStop('parent_not_terminal_expected_gate')
    plan = W.read_json(parent / W.PLAN)
    if W.sha(parent / W.PLAN) != W.read_json(parent / 'prepared.json')['plan_sha256']:
        raise W.SafeStop('parent_plan_changed')
    if W.frozen_inputs()[0] != plan['input_sha256']:
        raise W.SafeStop('frozen_inputs_changed')
    first = W.aggregate_answers(parent)
    if (first['answers'], first['unique_answers'], first['failures']) != (9, 9, 1):
        raise W.SafeStop('not_exactly_one_missing_case')
    failures = list(W.json_rows(parent / 'failures.jsonl'))
    match = re.search(r'Facet interpreter cached generate failed; key=([a-f0-9]{64})', failures[0]['error'])
    if not match:
        raise W.SafeStop('not_expected_cached_failure')
    cache = W.RUN_ROOT / ('artefact_facet_joint__10smoke__cb72000__20260922T071854164747Z'
                         '__format-retry1/private/interpreter_cache')
    source = cache / 'generate' / (match[1] + '.json')
    old_failure = W.ROOT / 'output/private/facet_joint_cache/generate' / source.name
    recovered, failed = W.read_json(source), W.read_json(old_failure)
    if not recovered['ok'] or failed['ok'] or recovered['signature'] != failed['signature']:
        raise W.SafeStop('cache_signature_mismatch')
    signature_key = hashlib.sha256(json.dumps(recovered['signature'], sort_keys=True,
                                              ensure_ascii=False).encode('utf-8')).hexdigest()
    if signature_key != match[1]:
        raise W.SafeStop('cache_key_mismatch')
    score_files = list((cache / 'score').glob('*.json'))
    score_files = [p for p in score_files if not p.name.endswith('.started.json')]
    if len(score_files) != 1 or not W.read_json(score_files[0])['ok']:
        raise W.SafeStop('successful_score_cache_missing')
    folder = parent.with_name(parent.name + '__cached-resume')
    folder.mkdir(exist_ok=False)
    (folder / 'private').mkdir()
    before = (parent / 'arm_outputs.jsonl').read_bytes()
    shutil.copy2(parent / 'arm_outputs.jsonl', folder / 'arm_outputs.jsonl')
    shutil.copy2(parent / 'run_manifest.json', folder / 'run_manifest.json')
    cache_hashes = {str(p): W.sha(p) for p in [source, old_failure, *score_files]}
    resume_plan = {'parent': str(parent), 'parent_plan_sha256': W.sha(parent / W.PLAN),
        'parent_answers_sha256': W.sha(parent / 'arm_outputs.jsonl'),
        'parent_failures_sha256': W.sha(parent / 'failures.jsonl'),
        'resume_code_sha256': W.sha(Path(__file__)), 'input_sha256': plan['input_sha256'],
        'cache': str(cache), 'cache_sha256': cache_hashes, 'commands': W.commands(folder),
        'models': plan['models'], 'metrics': plan['metrics'],
        'policy': 'Preserve nine new-arm answers; reuse exact successful prior interpreter cache; '
                  'standard harness generates only missing answer, then judges all ten.'}
    W.write_new(folder / 'resume_plan.json', resume_plan)
    W.write_new(folder / 'started.json', {'at': W.utc(), 'pid': os.getpid()})
    W.emit({'phase': 'cached_resume_started', 'folder': str(folder), 'reused_new_answers': 9,
            'additional_interpreter_calls_planned': 0})
    previous_cache = os.environ.get('HERB_FACET_JOINT_CACHE')
    os.environ['HERB_FACET_JOINT_CACHE'] = str(cache)
    result = {'phase': 'started', 'first_attempt': first, 'reused_new_answers': 9,
              'interpreter_source': 'Existing successful same-signature recovery cache'}
    started, code = time.monotonic(), 1
    try:
        result['generation'] = W.run_child(folder, 'generation', resume_plan['commands']['generation'])
        result['answers'] = W.aggregate_answers(folder)
        if not (folder / 'arm_outputs.jsonl').read_bytes().startswith(before):
            raise W.SafeStop('copied_answers_changed')
        if result['generation']['return_code'] or not result['answers']['ready_for_judge']:
            raise W.SafeStop('generation_incomplete')
        new_rows = list(W.json_rows(folder / 'arm_outputs.jsonl'))
        missing = [row for row in new_rows if row['id'] == failures[0]['id']]
        if len(missing) != 1:
            raise W.SafeStop('missing_case_identity_mismatch')
        # The arm records both cache-hit booleans; inspect aggregate booleans only.
        interpreter = missing[0]['meta']['interpreter']
        hits = [stage['cache_hit'] for stage in interpreter['stages']]
        if hits != [True, True]:
            raise W.SafeStop('interpreter_cache_reuse_not_proven')
        result['interpreter_cache_hits_for_missing_case'] = len(hits)
        if W.frozen_inputs()[0] != plan['input_sha256']:
            raise W.SafeStop('frozen_inputs_changed_before_judge')
        if any(W.sha(Path(p)) != value for p, value in cache_hashes.items()):
            raise W.SafeStop('source_cache_changed')
        W.emit({'phase': 'generation_audit', **result['answers'], 'missing_case_cache_hits': len(hits)})
        result['evaluation'] = W.run_child(folder, 'judge', resume_plan['commands']['judge'])
        judge_folder = folder.with_name(folder.name + W.JUDGE_SUFFIX)
        result['ragas'] = metrics = W.aggregate_metrics(judge_folder, plan['metrics'])
        W.emit({'phase': 'ragas_audit', **metrics})
        if result['evaluation']['return_code']:
            raise W.SafeStop('judge_process_failed')
        if metrics['unknown_metric_cells'] or metrics['duplicate_cells'] or metrics['missing_cells'] or not metrics['judge_model_matches']:
            raise W.SafeStop('evaluation_incomplete')
        result['phase'] = 'completed_with_metric_errors' if metrics['error_cells'] else 'completed'
        code = 0
    except W.SafeStop as exc:
        result.update(phase='stopped', reason_code=str(exc))
    except BaseException:
        with (folder / 'private/resume_error.log').open('a', encoding='utf-8') as handle:
            traceback.print_exc(file=handle)
        result.update(phase='stopped', reason_code='private_resume_exception')
    finally:
        if previous_cache is None:
            os.environ.pop('HERB_FACET_JOINT_CACHE', None)
        else:
            os.environ['HERB_FACET_JOINT_CACHE'] = previous_cache
        result['elapsed_s'] = time.monotonic() - started
        W.write_new(folder / 'aggregate_report.json', result)
        W.write_new(folder / 'completed.json', {'at': W.utc(), 'phase': result['phase'], 'exit_code': code})
        W.emit({'phase': result['phase'], 'reason_code': result.get('reason_code'), 'exit_code': code})
    return code


if __name__ == '__main__':
    try:
        sys.exit(main(Path(sys.argv[1])))
    except W.SafeStop as exc:
        W.emit({'phase': 'refused', 'reason_code': str(exc)})
        sys.exit(1)
