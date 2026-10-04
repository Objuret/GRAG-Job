"""One explicitly requested recovery of a missing-JSON interpreter failure.

Preserves the first attempt and its nine answers, then uses standard harness
resume and rejudge. Prints only aggregate telemetry; no benchmark content.
"""
from pathlib import Path
import json
import os
import re
import shutil
import sys
import time
import traceback

import facet_joint_gold_smoke as W


def recover(parent):
    parent = parent.resolve()
    plan = W.read_json(parent / W.PLAN)
    if parent.parent != W.RUN_ROOT.resolve():
        raise W.SafeStop('invalid_parent')
    if W.sha(parent / W.PLAN) != W.read_json(parent / 'prepared.json')['plan_sha256']:
        raise W.SafeStop('parent_plan_changed')
    if W.frozen_inputs()[0] != plan['input_sha256']:
        raise W.SafeStop('frozen_inputs_changed')
    first = W.aggregate_answers(parent)
    if (first['answers'], first['unique_answers'], first['failures']) != (9, 9, 1):
        raise W.SafeStop('not_the_expected_single_failure')
    failures = list(W.json_rows(parent / 'failures.jsonl'))
    match = re.search(r'Facet interpreter generate failed; key=([a-f0-9]{64}); no retry', failures[0]['error'])
    if not match:
        raise W.SafeStop('different_failure')
    failed_cache = W.ROOT / 'output/private/facet_joint_cache/generate' / (match[1] + '.json')
    failed = W.read_json(failed_cache)
    if failed.get('ok') is not False or not failed.get('error', '').startswith('ValueError: no JSON object'):
        raise W.SafeStop('different_interpreter_failure')
    folder = parent.with_name(parent.name + '__format-retry1')
    folder.mkdir(exist_ok=False)
    (folder / 'private').mkdir()
    cache = folder / 'private/interpreter_cache'
    before = (parent / 'arm_outputs.jsonl').read_bytes()
    shutil.copy2(parent / 'arm_outputs.jsonl', folder / 'arm_outputs.jsonl')
    shutil.copy2(parent / 'run_manifest.json', folder / 'run_manifest.json')
    commands = W.commands(folder)
    recovery_plan = {
        'parent': str(parent), 'parent_plan_sha256': W.sha(parent / W.PLAN),
        'parent_answers_sha256': W.sha(parent / 'arm_outputs.jsonl'),
        'parent_failures_sha256': W.sha(parent / 'failures.jsonl'),
        'recovery_code_sha256': W.sha(Path(__file__)),
        'original_input_sha256': plan['input_sha256'], 'commands': commands,
        'cache': str(cache), 'models': plan['models'], 'metrics': plan['metrics'],
        'policy': 'One explicit retry of the sole missing-JSON GENERATE failure. Same prompts, models and retrieval policy. Nine answers copied byte-for-byte; standard harness resumes the missing ID. Original failure remains in parent. No further retry.',
    }
    W.write_new(folder / 'recovery_plan.json', recovery_plan)
    W.write_new(folder / 'started.json', {'at': W.utc(), 'pid': os.getpid()})
    report = {'phase': 'started', 'first_attempt': first,
              'explicit_format_retries': 1, 'reused_answers': 9,
              'failed_interpreter_usage': W.usage_only({
                  'calls': 1, 'tokens_in': failed['response']['usage'].get('prompt_tokens', 0),
                  'tokens_out': failed['response']['usage'].get('completion_tokens', 0),
                  'cached_input_tokens': failed['response']['usage'].get('cached_input_tokens', 0),
                  'time_s': failed.get('elapsed_s', 0)})}
    W.emit({'phase': 'recovery_started', 'folder': str(folder), 'reused_answers': 9})
    started = time.monotonic()
    old_cache = os.environ.get('HERB_FACET_JOINT_CACHE')
    os.environ['HERB_FACET_JOINT_CACHE'] = str(cache)
    code = 1
    try:
        report['generation'] = W.run_child(folder, 'generation', commands['generation'])
        report['answers'] = W.aggregate_answers(folder)
        W.emit({'phase': 'generation_audit', **report['answers']})
        if not (folder / 'arm_outputs.jsonl').read_bytes().startswith(before):
            raise W.SafeStop('prior_answers_changed')
        if report['generation']['return_code'] or not report['answers']['ready_for_judge']:
            raise W.SafeStop('recovery_generation_incomplete_no_further_retry')
        if W.frozen_inputs()[0] != plan['input_sha256']:
            raise W.SafeStop('frozen_inputs_changed_before_judge')
        report['evaluation'] = W.run_child(folder, 'judge', commands['judge'])
        judge_folder = folder.with_name(folder.name + W.JUDGE_SUFFIX)
        report['ragas'] = metrics = W.aggregate_metrics(judge_folder, plan['metrics'])
        W.emit({'phase': 'ragas_audit', **metrics})
        if report['evaluation']['return_code']:
            raise W.SafeStop('judge_process_failed')
        if metrics['unknown_metric_cells'] or metrics['duplicate_cells'] or metrics['missing_cells'] or not metrics['judge_model_matches']:
            raise W.SafeStop('evaluation_shape_incomplete')
        report['phase'] = 'completed_with_metric_errors' if metrics['error_cells'] else 'completed'
        code = 0
    except W.SafeStop as exc:
        report.update(phase='stopped', reason_code=str(exc))
    except BaseException:
        with (folder / 'private/wrapper_error.log').open('a', encoding='utf-8') as handle:
            traceback.print_exc(file=handle)
        report.update(phase='stopped', reason_code='wrapper_exception_private_log')
    finally:
        if old_cache is None:
            os.environ.pop('HERB_FACET_JOINT_CACHE', None)
        else:
            os.environ['HERB_FACET_JOINT_CACHE'] = old_cache
        report['elapsed_s'] = round(time.monotonic() - started, 3)
        W.write_new(folder / 'aggregate_report.json', report)
        W.write_new(folder / 'completed.json', {'at': W.utc(), 'phase': report['phase'], 'exit_code': code})
        W.emit({'phase': report['phase'], 'exit_code': code, 'elapsed_s': report['elapsed_s'], 'reason_code': report.get('reason_code')})
    return code


if __name__ == '__main__':
    try:
        result = recover(Path(sys.argv[1]))
    except W.SafeStop as exc:
        W.emit({'phase': 'refused', 'reason_code': str(exc)})
        result = 1
    except Exception:
        W.emit({'phase': 'refused', 'reason_code': 'preflight_failed'})
        result = 1
    raise SystemExit(result)
