"""Freeze four existing GENERATE captures and make exactly eight unretried SCORE attempts.

Uses the existing split prompts and parsers. All generation exclusions, transport
outcomes and separate score readings are retained; no benchmark or graph is read.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact import querytagger as Q
from artefact import querytagger_split_check as S
from harness.chat import _CLAUDE_EXE

BASE = ROOT / 'output/research/2026-09-21-facet-validity'
IDS = ('analysis_0', 'analysis_1', 'sharing_0', 'sharing_1')


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf-8')).hexdigest()


def write(path, value):
    S._write(path, value)


def exclusions(raw_tags):
    seen = set()
    rows = []
    for index, raw in enumerate(raw_tags):
        clean = Q.clean_tag(raw)
        key = clean.casefold()
        reason = ('short' if len(clean) < 2 else 'filler' if key in S.FILLER
                  else 'duplicate_casefold' if key in seen else None)
        if reason:
            rows.append({'index': index, 'raw': raw, 'clean': clean, 'reason': reason})
        else:
            seen.add(key)
    return rows


def prepare(source, out):
    generation_manifest_path = source / 'manifest.json'
    generation_manifest = json.loads(generation_manifest_path.read_text(encoding='utf-8'))
    by_id = {j['id']: j for j in generation_manifest['jobs']}
    if set(by_id) != set(IDS) or generation_manifest['model'] != S.MODEL:
        raise ValueError('Unexpected generation capture set or model')
    source_paths = [ROOT / 'test/artefact/querytagger.py',
                    ROOT / 'test/artefact/querytagger_split_check.py',
                    ROOT / 'prod/harness/chat.py', Path(__file__), generation_manifest_path]
    captures, jobs = [], []
    for gid in IDS:
        job = by_id[gid]
        system, user = S.generate_prompt(job['question'])
        if (job['system'], job['user']) != (system, user):
            raise ValueError(f'{gid}: generation prompt differs from current split prompt')
        path = source / f'{gid}.json'
        transport_path = source / f'{gid}.transport.json'
        raw = json.loads(path.read_text(encoding='utf-8'))
        if raw['model'] != S.MODEL or raw['system_sha256'] != sha(system) or raw['user_sha256'] != sha(user):
            raise ValueError(f'{gid}: captured model/prompt hash mismatch')
        # This is the actual production split parser, not a parallel approximation.
        parsed = S.parse_generate(raw['answer'])
        dropped = exclusions(raw['answer']['tags'])
        hashes = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in (path, transport_path)}
        source_paths.extend((path, transport_path))
        capture = {'generation_id': gid, 'question_id': gid.rsplit('_', 1)[0],
                   'question': job['question'], 'description': parsed['description'],
                   'raw_description': raw['answer']['description'], 'raw_tags': raw['answer']['tags'],
                   'clean_tags': parsed['tags'], 'exclusions': dropped,
                   'generation_validation': {'ok': True, 'error': None},
                   'source_sha256': hashes, 'readings': []}
        captures.append(capture)
        score_system, score_user = S.score_prompt(parsed['description'], parsed['tags'])
        for repeat in (0, 1):
            jobs.append({'id': f'{gid}_score_{repeat}', 'generation_id': gid, 'repeat': repeat,
                         'system': score_system, 'user': score_user, 'tags': parsed['tags']})
    manifest = {'schema_version': 1, 'protocol': __doc__, 'model': S.MODEL,
                'facets': list(Q.SPLIT_FACETS), 'attempt_limit': 8,
                'source_sha256': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in source_paths},
                'transport_policy': 'Same tool-free CLI flags as GENERATE, default effort; one invocation per reading. No parser or transport retry. A started marker prevents duplicate invocation after interruption.',
                'captures': captures, 'jobs': jobs}
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'manifest.json'
    if path.exists() and json.loads(path.read_text(encoding='utf-8')) != manifest:
        raise ValueError('Frozen route capture manifest changed')
    write(path, manifest)
    return manifest


def as_text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value


def run_one(job, out, model):
    sig = {key + '_sha256': sha(job[key]) for key in ('system', 'user')}
    path = out / f"{job['id']}.json"
    transport_path = out / f"{job['id']}.transport.json"
    started_path = out / f"{job['id']}.started.json"
    if path.exists():
        result = json.loads(path.read_text(encoding='utf-8'))
        if result['model'] != model or any(result[k] != v for k, v in sig.items()):
            raise ValueError('Saved score reading signature differs')
        return result
    if transport_path.exists():
        transport = json.loads(transport_path.read_text(encoding='utf-8'))
        if transport['model'] != model or any(transport[k] != v for k, v in sig.items()):
            raise ValueError('Saved transport signature differs')
    elif started_path.exists():
        # An uncertain attempt must not be silently repeated.
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
            with tempfile.TemporaryDirectory(prefix='facet-route-score-') as cwd:
                process = subprocess.run([_CLAUDE_EXE, '-p', '--model', model,
                    '--output-format', 'json', '--tools', '', '--setting-sources', '',
                    '--no-session-persistence', '--system-prompt', job['system']],
                    input=job['user'], cwd=cwd, capture_output=True, text=True,
                    encoding='utf-8', timeout=300)
            transport.update(returncode=process.returncode, stdout=process.stdout, stderr=process.stderr)
        except subprocess.TimeoutExpired as exc:
            transport.update(stdout=as_text(exc.stdout) or '', stderr=as_text(exc.stderr) or '',
                             error='Collector timeout after 300 seconds; no retry')
        except Exception as exc:
            transport['error'] = f'{type(exc).__name__}: {exc}'
        transport['elapsed_s'] = time.perf_counter() - t0
        transport['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write(transport_path, transport)
    result = {'id': job['id'], 'repeat': job['repeat'], 'model': model, **sig,
              'ok': False, 'values': [], 'missing': [{'t': t, 'facets': list(Q.SPLIT_FACETS)} for t in job['tags']],
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
        parsed = S.parse_score(result['raw_answer'], job['tags'])
        result.update(ok=True, values=parsed['tags'], missing=[])
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    write(path, result)
    return result


def collect(manifest, out):
    captures = json.loads(json.dumps(manifest['captures']))
    by_id = {c['generation_id']: c for c in captures}
    for job in manifest['jobs']:
        path = out / f"{job['id']}.json"
        if path.exists():
            reading = json.loads(path.read_text(encoding='utf-8'))
        else:
            reading = {'id': job['id'], 'repeat': job['repeat'], 'ok': False, 'values': [],
                       'missing': [{'t': t, 'facets': list(Q.SPLIT_FACETS)} for t in job['tags']],
                       'error': 'Not attempted yet'}
        by_id[job['generation_id']]['readings'].append(reading)
    result = {k: manifest[k] for k in ('schema_version', 'model', 'facets', 'source_sha256')}
    result['captures'] = captures
    result['counts'] = {'generations': len(captures), 'planned_score_attempts': 8,
                        'started_score_attempts': len(list(out.glob('*.started.json'))),
                        'successful_readings': sum(r['ok'] for c in captures for r in c['readings'])}
    result['aggregation'] = 'None; readings retained separately in canonical tag and facet order.'
    write(out / 'query_captures.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=BASE / 'query_route')
    parser.add_argument('--out', type=Path, default=BASE / 'route_capture')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    manifest = prepare(args.source.resolve(), args.out.resolve())
    print('Validated four GENERATE captures; froze eight unchanged SCORE inputs.', flush=True)
    collect(manifest, args.out)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_one, j, args.out.resolve(), manifest['model']) for j in manifest['jobs']]
            for future in as_completed(futures):
                result = future.result()
                print(result['id'], 'ok' if result['ok'] else result['error'], flush=True)
                collect(manifest, args.out)
    print(json.dumps(collect(manifest, args.out)['counts']), flush=True)


if __name__ == '__main__':
    main()
