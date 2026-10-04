"""Prepare one disclosed GENERATE addition; --run makes at most 7 GEN + 14 SCORE attempts.

No module constants are changed. Explicit frozen job.system strings override only
the GENERATE system text handed to the existing unretried transport. The existing
split parsers, SCORE builder, collection and transport functions are reused.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import difflib
import json
from pathlib import Path
import re

import facet_independent_capture as C

ROOT, R, Q, S = C.ROOT, C.R, C.Q, C.S
BASE = C.BASE
OUT = BASE / 'fresh_smoke/phrase_preservation'
ANCHOR = 'Keep phrases whole. Include central concepts and peripheral lookup handles.'
ADDITION = ('When the question explicitly names a compound subject, retain that subject as a '
            'complete semantic phrase. Shorter supported concepts may supplement it, but '
            'must not replace it with disconnected modifiers.')


def freeze_text(path, value):
    if path.exists():
        if path.read_bytes() != value.encode('utf-8'):
            raise ValueError(f'Frozen text changed: {path}')
    else:
        with path.open('xb') as stream:
            stream.write(value.encode('utf-8'))


def prepare():
    questions_path = BASE / 'questions.json'
    questions = C.read(questions_path)
    if not isinstance(questions, list) or len(questions) != 7:
        raise ValueError('Exactly the seven existing development questions are required')
    original = Q.GENERATE_SYSTEM
    if original != S.GENERATE_SYSTEM or original.count(ANCHOR) != 1:
        raise ValueError('Original prompt imports or single insertion anchor differ')
    if Q.SCORE_SYSTEM != S.SCORE_SYSTEM or Q.SCORE_USER_TEMPLATE != S.SCORE_USER_TEMPLATE:
        raise ValueError('SCORE prompt imports differ')
    patched = original.replace(ANCHOR, ANCHOR + '\n' + ADDITION, 1)
    prompt_record = {
        'override_boundary': 'Explicit generation job.system only; no Q/S constant mutation.',
        'anchor': ANCHOR, 'addition': ADDITION,
        'original_generate_system': original, 'trial_generate_system': patched,
        'generate_user_template': Q.GENERATE_USER_TEMPLATE,
        'score_system': Q.SCORE_SYSTEM, 'score_user_template': Q.SCORE_USER_TEMPLATE,
    }
    prompt_record['sha256'] = {key: R.sha(prompt_record[key]) for key in
        ('original_generate_system', 'trial_generate_system', 'generate_user_template',
         'score_system', 'score_user_template')}
    jobs, seen = [], set()
    for item in questions:
        qid, question = item['id'], item['question']
        if not isinstance(qid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', qid) or qid in seen:
            raise ValueError('Question IDs must be distinct safe identifiers')
        if not isinstance(question, str) or not question.strip():
            raise ValueError('Question must be nonempty')
        seen.add(qid)
        system, user = S.generate_prompt(question)
        if system != original or user != Q.GENERATE_USER_TEMPLATE.format(question=question):
            raise ValueError('Original GENERATE builder differs from recorded templates')
        jobs.append({'id': qid + '_0', 'question_id': qid, 'question': question,
                     'repeat': 0, 'system': patched, 'user': user,
                     'system_sha256': R.sha(patched), 'user_sha256': R.sha(user)})
    OUT.mkdir(parents=True, exist_ok=True)
    protocol = OUT / 'PROTOCOL.md'
    if not protocol.is_file():
        raise ValueError('Protocol must exist before preparing jobs')
    C.freeze(OUT / 'prompts.json', prompt_record)
    diff = ''.join(difflib.unified_diff(original.splitlines(keepends=True),
        patched.splitlines(keepends=True), fromfile='original/GENERATE_SYSTEM',
        tofile='trial/GENERATE_SYSTEM'))
    freeze_text(OUT / 'generate_prompt.diff', diff)
    # Immutable byte copy of existing questions, with no source facts or labels.
    freeze_text(OUT / 'questions.json', questions_path.read_text(encoding='utf-8'))
    sources = [Path(__file__), Path(C.__file__), Path(R.__file__),
               ROOT / 'test/artefact/querytagger.py',
               ROOT / 'test/artefact/querytagger_split_check.py',
               ROOT / 'prod/harness/chat.py', ROOT / 'test/arms/artefact_v2.py']
    sources += [protocol, questions_path, OUT / 'questions.json', OUT / 'prompts.json',
                OUT / 'generate_prompt.diff', ROOT / 'tools/facet_independent_snapshot.py',
                ROOT / 'tools/facet_retrieval_demo.py',
                ROOT / 'test/artefact/facet_retrieval_pipeline.py',
                ROOT / 'test/artefact/facet_scope_recruitment.py']
    manifest = {
        'schema_version': 1, 'protocol': __doc__, 'model': S.MODEL,
        'facets': list(Q.SPLIT_FACETS), 'generation_attempt_limit': 7,
        'score_attempt_limit': 14, 'total_attempt_limit': 21,
        'max_concurrent_cli_processes': 2,
        'source_sha256': {str(p.relative_to(ROOT)): R.sha(p.read_bytes()) for p in sources},
        'prompt_sha256': {'generate_system': R.sha(patched),
                         'original_generate_system': R.sha(original),
                         'generate_user_template': R.sha(Q.GENERATE_USER_TEMPLATE),
                         'score_system': R.sha(Q.SCORE_SYSTEM),
                         'score_user_template': R.sha(Q.SCORE_USER_TEMPLATE)},
        'runtime_override': prompt_record['override_boundary'],
        'model_input_policy': 'Raw question only to GENERATE; generated description and all clean tags only to SCORE. No sources, labels, expected phrases or retrieval results.',
        'transport_policy': 'Reuse independent_capture.run_generate and route_capture.run_one unchanged. One attempt per job, started markers, no transport/parser retries.',
        'score_freeze_policy': 'Reuse independent_capture.score_jobs: two exact SCORE jobs frozen after each valid generation; readings separate.',
        'evaluation': {'coefficients': [1, .25, .25, .25, .25],
                       'source_character_budget': 72000, 'verified_area': True,
                       'query_bundle': str(OUT.relative_to(ROOT)),
                       'downstream_gate': 'All seven generations and fourteen SCORE readings must validate; otherwise preserve failures and stop downstream stages.',
                       'reading_ids': [f"{j['id']}_score_{i}" for j in jobs for i in (0, 1)]},
        'jobs': jobs,
    }
    capture_out = OUT / 'query_capture'
    capture_out.mkdir(exist_ok=True)
    return C.freeze(capture_out / 'manifest.json', manifest), capture_out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Execute the frozen capped trial; omitted means prepare only')
    args = parser.parse_args()
    manifest, capture_out = prepare()
    print('Frozen explicit GENERATE addition; existing parsers/SCORE/transport unchanged.', flush=True)
    C.collect(manifest, capture_out)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(C.run_generate, job, capture_out, manifest['model'])
                       for job in manifest['jobs']]
            for future in as_completed(futures):
                result = future.result()
                print(result['id'], 'ok' if result['ok'] else result['error'], flush=True)
                C.collect(manifest, capture_out)
        _, jobs = C.collect(manifest, capture_out)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(R.run_one, job, capture_out, manifest['model']) for job in jobs]
            for future in as_completed(futures):
                result = future.result()
                print(result['id'], 'ok' if result['ok'] else result['error'], flush=True)
                C.collect(manifest, capture_out)
    result, _ = C.collect(manifest, capture_out)
    print(json.dumps(result['counts']), flush=True)


if __name__ == '__main__':
    main()
