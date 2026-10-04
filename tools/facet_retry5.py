"""Explicit same-prompt retry of the five original interpreter failures.

Private question and interpreter content is never printed. Original caches,
the 95 numeric inputs, and the active retrieval run are never modified.
"""
from pathlib import Path
from dataclasses import asdict
from types import SimpleNamespace
import contextlib
import hashlib
import json
import re
import sys
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'prod'), str(ROOT/'test'), str(ROOT/'tools')]
OUT = ROOT/'output/research/2026-09-22-retrieval-retry5'
PARENT = ROOT/'output/k=chars/artefact_facet_joint__gold90__cb72000__20260922T090621382244Z'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_new(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def emit(value):
    print(json.dumps(value), flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'private/interpreted').mkdir(parents=True, exist_ok=True)
    with (OUT/'private/interpreter.log').open('a', encoding='utf-8') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            from arms import artefact_facet_joint as A
    old_manifest = ROOT/'output/research/2026-09-22-retrieval-matrix/inputs/cases_manifest.json'
    failed = [json.loads(s) for s in (PARENT/'failures.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    assert len(failed) == 5 and {r['id'] for r in failed} == set(read(old_manifest)['failed_question_ids'])
    wanted = {r['id'] for r in failed}
    questions = {}
    with (ROOT/'data/questions.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['id'] in wanted:
                questions[row['id']] = row['question']
    assert set(questions) == wanted
    originals, records = [], []
    for i, failure in enumerate(failed, 96):
        match = re.search(r'(generate|score).*?key=([a-f0-9]{64})', failure['error'])
        assert match and match[1] == 'generate'
        original = PARENT/'private/interpreter_cache/generate'/(match[2]+'.json')
        saved = read(original)
        system, user = A.S.generate_prompt(questions[failure['id']])
        signature = dict(cache_version=1, stage='generate', model=A.INTERPRET_MODEL,
                         system=system, user=user, max_tries=1)
        assert saved['signature'] == signature and saved['ok'] is False
        assert A._sha(json.dumps(signature, sort_keys=True, ensure_ascii=False)) == match[2]
        originals.append(original)
        records.append(dict(question_id=failure['id'], case_id=f'case_{i:03d}', original_key=match[2]))
    paths = [Path(__file__), old_manifest, PARENT/'failures.jsonl', ROOT/'data/questions.jsonl', *originals]
    paths += [ROOT/p for p in A.SMOKE_PROVENANCE_PATHS]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    plan = dict(cases=records, model=A.INTERPRET_MODEL, input_sha256=hashes,
                original_generate_signatures_matched=5, max_new_calls=10,
                policy='One explicitly authorized fresh GENERATE/SCORE attempt per failed question; original caches preserved. No generator or judge calls.')
    if (OUT/'plan.json').exists():
        assert read(OUT/'plan.json') == plan, 'Frozen retry plan changed'
    else:
        write_new(OUT/'plan.json', plan)
    prepared = SimpleNamespace(cache_dir=OUT/'private/interpreter_cache')
    successes, failures = [], []
    for rec in records:
        target = OUT/'private/interpreted'/(rec['case_id']+'.json')
        if target.exists():
            held = read(target)
            assert held['question_id'] == rec['question_id']
            successes.append(rec['case_id'])
            emit(dict(phase='verified_existing', case_id=rec['case_id']))
            continue
        emit(dict(phase='interpreting', case_id=rec['case_id'], question_id=rec['question_id']))
        try:
            with (OUT/'private/interpreter.log').open('a', encoding='utf-8') as log:
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    generation, weights, usage, interpreter = A._interpret(questions[rec['question_id']], prepared)
            write_new(target, dict(**rec, question=questions[rec['question_id']],
                generation=generation, weights=weights.tolist(), usage=asdict(usage), interpreter=interpreter))
            successes.append(rec['case_id'])
            emit(dict(phase='interpreted', case_id=rec['case_id'], model_calls=usage.calls,
                      tokens_in=usage.tokens_in, tokens_out=usage.tokens_out))
        except Exception as exc:
            with (OUT/'private/errors.log').open('a', encoding='utf-8') as log:
                traceback.print_exc(file=log)
            failures.append(dict(case_id=rec['case_id'], error_type=type(exc).__name__))
            emit(dict(phase='failed', **failures[-1]))
    assert all(sha(ROOT/p) == value for p, value in hashes.items()), 'Frozen source changed during retry'
    result = dict(status='complete' if not failures else 'incomplete', successful_cases=successes,
                  failed_cases=failures, original_inputs_unchanged=True)
    write_new(OUT/'interpretation_completed.json', result)
    emit(result)


if __name__ == '__main__':
    main()
