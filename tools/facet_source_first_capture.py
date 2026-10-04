"""Freeze four source-grounded questions; optionally run 4 GENERATE + up to 8 SCORE calls.

Uses unchanged split prompts/parsers and the existing unretried tool-free CLI
transport. Only question text enters GENERATE; only its validated description and
tags enter SCORE. No source passage, expected chunk, benchmark or graph is read.
Default invocation freezes inputs and collects existing results without model calls.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

import facet_route_capture as R

ROOT, Q, S = R.ROOT, R.Q, R.S
BASE = ROOT / 'output/research/2026-09-22-joint-streams/source_first'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def freeze(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError(f'Frozen input changed: {path}')
    else:
        R.write(path, value)
    return value


def prepare(questions_path, out):
    questions = read(questions_path)['questions']
    if not isinstance(questions, list) or len(questions) != 4:
        raise ValueError('Exactly four frozen source-grounded questions are required')
    ids, jobs = set(), []
    for item in questions:
        qid, question = item['id'], item['question']
        if not isinstance(qid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', qid) or qid in ids:
            raise ValueError('Question IDs must be distinct safe file-name identifiers')
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f'{qid}: question must be nonempty text')
        ids.add(qid)
        system, user = S.generate_prompt(question)
        jobs.append({'id': qid + '_0', 'question_id': qid, 'question': question,
                     'repeat': 0, 'system': system, 'user': user,
                     'system_sha256': R.sha(system), 'user_sha256': R.sha(user)})
    paths = [Path(__file__), Path(R.__file__), ROOT / 'test/artefact/querytagger.py',
             ROOT / 'test/artefact/querytagger_split_check.py', ROOT / 'prod/harness/chat.py',
             questions_path]
    manifest = {'schema_version': 1, 'protocol': __doc__, 'model': S.MODEL,
                'facets': list(Q.SPLIT_FACETS), 'generation_attempt_limit': 4,
                'score_attempt_limit': 8, 'total_attempt_limit': 12,
                'source_sha256': {str(p.relative_to(ROOT)): R.sha(p.read_bytes()) for p in paths},
                'prompt_sha256': {'generate_system': R.sha(Q.GENERATE_SYSTEM),
                                  'generate_user_template': R.sha(Q.GENERATE_USER_TEMPLATE),
                                  'score_system': R.sha(Q.SCORE_SYSTEM),
                                  'score_user_template': R.sha(Q.SCORE_USER_TEMPLATE)},
                'transport_policy': 'Exactly one tool-free CLI invocation per job, default effort; no parser or transport retry. Started markers prevent ambiguous attempts being repeated.',
                'score_freeze_policy': 'Two SCORE jobs frozen only after successful GENERATE parsing; unchanged description and all surviving tags, readings kept separately.',
                'jobs': jobs}
    out.mkdir(parents=True, exist_ok=True)
    return freeze(out / 'manifest.json', manifest)


def run_generate(job, out, model):
    """Same started-marker, timeout and transport flags as R.run_one; GENERATE parser."""
    sig = {key + '_sha256': R.sha(job[key]) for key in ('system', 'user')}
    path = out / f"{job['id']}.json"
    transport_path = out / f"{job['id']}.transport.json"
    started_path = out / f"{job['id']}.started.json"
    if path.exists():
        result = read(path)
        if result['model'] != model or any(result[k] != v for k, v in sig.items()):
            raise ValueError('Saved generation signature differs')
        return result
    if transport_path.exists():
        transport = read(transport_path)
        if transport['model'] != model or any(transport[k] != v for k, v in sig.items()):
            raise ValueError('Saved transport signature differs')
    elif started_path.exists():
        transport = {'model': model, **sig, 'returncode': None, 'stdout': '', 'stderr': '',
                     'error': 'Started marker exists without completed transport; attempt is uncertain and will not be repeated.'}
    else:
        started = {'id': job['id'], 'model': model, **sig,
                   'started_utc': datetime.now(timezone.utc).isoformat()}
        with started_path.open('x', encoding='utf-8') as fh:
            json.dump(started, fh, indent=2)
        t0 = time.perf_counter()
        transport = {**started, 'returncode': None, 'stdout': '', 'stderr': '', 'error': None}
        try:
            with tempfile.TemporaryDirectory(prefix='facet-source-first-generate-') as cwd:
                process = subprocess.run([R._CLAUDE_EXE, '-p', '--model', model,
                    '--output-format', 'json', '--tools', '', '--setting-sources', '',
                    '--no-session-persistence', '--system-prompt', job['system']],
                    input=job['user'], cwd=cwd, capture_output=True, text=True,
                    encoding='utf-8', timeout=300)
            transport.update(returncode=process.returncode, stdout=process.stdout, stderr=process.stderr)
        except subprocess.TimeoutExpired as exc:
            transport.update(stdout=R.as_text(exc.stdout) or '', stderr=R.as_text(exc.stderr) or '',
                             error='Collector timeout after 300 seconds; no retry')
        except Exception as exc:
            transport['error'] = f'{type(exc).__name__}: {exc}'
        transport['elapsed_s'] = time.perf_counter() - t0
        transport['finished_utc'] = datetime.now(timezone.utc).isoformat()
        R.write(transport_path, transport)
    result = {'id': job['id'], 'repeat': 0, 'model': model, **sig, 'ok': False,
              'description': None, 'clean_tags': [], 'exclusions': [],
              'error': None, 'raw_answer': None, 'raw_content': None,
              'transport_path': str(transport_path.relative_to(ROOT)),
              'usage': None, 'cost_usd_reported': None}
    try:
        if transport.get('error'):
            raise ValueError(transport['error'])
        envelope = json.loads(transport['stdout'])
        result.update(usage=envelope.get('usage'), cost_usd_reported=envelope.get('total_cost_usd'))
        result['raw_content'] = envelope.get('result')
        if transport['returncode'] or envelope.get('is_error'):
            raise ValueError(f"CLI exit {transport['returncode']}; API error={envelope.get('is_error')}")
        result['raw_answer'] = Q.extract_json(envelope['result'])
        parsed = S.parse_generate(result['raw_answer'])
        result.update(ok=True, description=parsed['description'], clean_tags=parsed['tags'],
                      exclusions=R.exclusions(result['raw_answer']['tags']))
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    R.write(path, result)
    return result


def score_jobs(job, generation, out, model):
    if not generation['ok']:
        return []
    # Revalidate with the actual parser before freezing any dependent jobs.
    parsed = S.parse_generate(generation['raw_answer'])
    system, user = S.score_prompt(parsed['description'], parsed['tags'])
    jobs = [{'id': f"{job['id']}_score_{repeat}", 'generation_id': job['id'],
             'repeat': repeat, 'system': system, 'user': user, 'tags': parsed['tags']}
            for repeat in (0, 1)]
    manifest = {'model': model, 'generation_id': job['id'],
                'generation_sha256': R.sha((out / f"{job['id']}.json").read_bytes()),
                'system_sha256': R.sha(system), 'user_sha256': R.sha(user), 'jobs': jobs}
    freeze(out / f"{job['id']}.score_jobs.json", manifest)
    return jobs


def collect(manifest, out):
    captures, all_score_jobs = [], []
    for job in manifest['jobs']:
        path = out / f"{job['id']}.json"
        generation = read(path) if path.exists() else None
        capture = {'generation_id': job['id'], 'question_id': job['question_id'],
                   'question': job['question'], 'description': None, 'raw_description': None,
                   'raw_tags': [], 'clean_tags': [], 'exclusions': [],
                   'generation_validation': {'ok': False, 'error': 'Not attempted yet'},
                   'source_sha256': {}, 'readings': []}
        if generation is not None:
            if generation['model'] != manifest['model'] or any(generation[k + '_sha256'] != R.sha(job[k]) for k in ('system', 'user')):
                raise ValueError('Captured GENERATE input signature differs')
            raw = generation.get('raw_answer')
            capture.update(description=generation['description'], clean_tags=generation['clean_tags'],
                exclusions=generation['exclusions'], generation_validation={'ok': generation['ok'], 'error': generation['error']},
                generation_result=generation)
            if isinstance(raw, dict):
                capture.update(raw_description=raw.get('description'), raw_tags=raw.get('tags'))
            for p in (path, out / f"{job['id']}.transport.json"):
                if p.exists():
                    capture['source_sha256'][str(p.relative_to(ROOT))] = R.sha(p.read_bytes())
            jobs = score_jobs(job, generation, out, manifest['model'])
            all_score_jobs.extend(jobs)
            for score in jobs:
                score_path = out / f"{score['id']}.json"
                reading = read(score_path) if score_path.exists() else {
                    'id': score['id'], 'repeat': score['repeat'], 'ok': False, 'values': [],
                    'missing': [{'t': t, 'facets': list(Q.SPLIT_FACETS)} for t in score['tags']],
                    'error': 'Not attempted yet'}
                if score_path.exists() and (reading['model'] != manifest['model'] or any(reading[k + '_sha256'] != R.sha(score[k]) for k in ('system', 'user'))):
                    raise ValueError('Captured SCORE input signature differs')
                capture['readings'].append(reading)
        captures.append(capture)
    result = {k: manifest[k] for k in ('schema_version', 'model', 'facets', 'source_sha256')}
    result['captures'] = captures
    result['counts'] = {'generations': 4, 'successful_generations': sum(c['generation_validation']['ok'] for c in captures),
                        'started_generation_attempts': sum((out / f"{j['id']}.started.json").exists() for j in manifest['jobs']),
                        'planned_score_attempts': len(all_score_jobs),
                        'started_score_attempts': sum((out / f"{j['id']}.started.json").exists() for j in all_score_jobs),
                        'successful_readings': sum(r['ok'] for c in captures for r in c['readings'])}
    if result['counts']['started_generation_attempts'] > 4 or result['counts']['started_score_attempts'] > 8:
        raise ValueError('Declared invocation budget exceeded')
    result['aggregation'] = 'None; readings retained separately in canonical tag and facet order.'
    R.write(out / 'query_captures.json', result)
    return result, all_score_jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--questions', type=Path, default=BASE / 'questions.json')
    parser.add_argument('--out', type=Path, default=BASE / 'query_capture')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    manifest = prepare(args.questions.resolve(), out)
    print('Frozen four unchanged GENERATE jobs; model calls require --run.', flush=True)
    collect(manifest, out)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_generate, job, out, manifest['model']) for job in manifest['jobs']]
            for future in as_completed(futures):
                result = future.result()
                print(result['id'], 'ok' if result['ok'] else result['error'], flush=True)
                collect(manifest, out)
        _, jobs = collect(manifest, out)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(R.run_one, job, out, manifest['model']) for job in jobs]
            for future in as_completed(futures):
                result = future.result()
                print(result['id'], 'ok' if result['ok'] else result['error'], flush=True)
                collect(manifest, out)
    result, _ = collect(manifest, out)
    print(json.dumps(result['counts']), flush=True)


if __name__ == '__main__':
    main()
