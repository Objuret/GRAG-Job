"""Freeze numeric query inputs from saved retrievals; local embeddings only.

Streams each saved JSONL once, hashing bytes as they are consumed. Completed
case markers are immutable and permit verified resume without re-embedding.
No gold reader, language-model call, DB read or source-text export is used.
"""
from __future__ import annotations
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '4'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from arms import artefact_facet_joint as A

OUT = ROOT / 'output/research/2026-09-22-retrieval-matrix/inputs'
SMOKE = ROOT / 'output/k=chars/artefact_facet_joint__10smoke__cb72000__20260922T071854164747Z__format-retry1'
LARGE = ROOT / 'output/k=chars/artefact_facet_joint__gold90__cb72000__20260922T090621382244Z'
CACHED = ROOT / 'output/research/2026-09-22-gold-source-trace/correspondence'
MATRIX_KEYS = ('query_tag_cosines', 'query_chunk_cosines', 'query_description_cosines')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def write_new(path, value):
    if path.exists():
        raise FileExistsError('Preserve existing output')
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.json.partial')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write('\n')
        # On this Windows host rename refuses an existing destination.
        os.rename(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def stat(path):
    s = path.stat()
    return {'size': s.st_size, 'mtime_ns': s.st_mtime_ns}


def verify_hashes(hashes):
    for p, expected in hashes.items():
        if sha(ROOT / p) != expected:
            raise ValueError('Frozen dependency changed')


def saved_ids(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line)['id'] for line in stream if line.strip()]


def capture(out):
    prepared = A.prepare_over_corpus(ROOT / 'data/corpus/Salesforce__HERB')
    numerical = read(CACHED / 'numerical_outputs.json')
    baseline = sorted((r for r in numerical['records'] if r['condition'] == 'baseline'), key=lambda r: r['case'])
    assert len(baseline) == 10 and all(r['embedding_vector_hash_matched'] for r in baseline)
    cached = {r['question_id']: CACHED / 'private' / f"case_{r['case']:02d}.npz" for r in baseline}
    failed = saved_ids(LARGE / 'failures.jsonl')
    ninety = saved_ids(LARGE / 'remaining90.jsonl')
    assert len(failed) == len(set(failed)) == 5
    assert len(ninety) == len(set(ninety)) == 90 and set(failed) <= set(ninety)
    cohorts = [('smoke10', [r['question_id'] for r in baseline]), ('remaining90', [q for q in ninety if q not in set(failed)])]
    cases = []
    for cohort, ids in cohorts:
        for qid in ids:
            cid = f'case_{len(cases) + 1:03d}'
            cases.append({'case_id': cid, 'question_id': qid, 'cohort': cohort,
                          'npz': cid + '.npz', 'meta': cid + '.json'})
    assert len({c['question_id'] for c in cases}) == len(cases) == 95
    files = {Path(__file__), CACHED / 'numerical_outputs.json', LARGE / 'remaining90.jsonl', LARGE / 'failures.jsonl'}
    files.update(ROOT / p for p in prepared.provenance['source_sha256'])
    files.update(A.SNAPSHOT / p for p in A.PINNED_FILES)
    files.update(cached.values())
    hashes = {relative(p): sha(p) for p in sorted(files)}
    sources = {'smoke10': SMOKE / 'arm_outputs.jsonl', 'remaining90': LARGE / 'arm_outputs.jsonl'}
    source_stats = {relative(p): stat(p) for p in sources.values()}
    manifest = {'schema_version': 1, 'cases': cases, 'expected_cases': 95,
                'failed_question_ids': failed, 'failed_cohort': 'remaining90',
                'input_sha256': hashes, 'source_stats': source_stats,
                'source_sha256_policy': 'Accumulate exact byte hash during one streaming pass; final hashes in source_verification.json.',
                'chunk_ids': [c['chunkId'] for c in prepared.chunks],
                'facets': list(A.FACETS), 'language_model_calls': 0,
                'local_embedding_reconstructions_expected': 85,
                'cached_matrix_reuses_expected': 10, 'gold_read': False}
    manifest_path = out / 'cases_manifest.json'
    if manifest_path.exists():
        if read(manifest_path) != manifest:
            raise ValueError('Resume inputs differ from frozen manifest')
    else:
        write_new(manifest_path, manifest)
    print(json.dumps({'status': 'manifest_ready', 'cases': 95, 'preserved_failures': 5}), flush=True)
    by_id = {c['question_id']: c for c in cases}
    seen, source_hashes, completed = set(), {}, 0
    chunk_ids = manifest['chunk_ids']
    for cohort, source in sources.items():
        hasher = hashlib.sha256()
        with source.open('rb') as stream:
            for raw in stream:
                hasher.update(raw)
                if not raw.strip():
                    continue
                record_sha = hashlib.sha256(raw).hexdigest()
                row = json.loads(raw)
                qid = row['id']
                case = by_id[qid]
                assert qid not in seen and case['cohort'] == cohort
                seen.add(qid)
                marker, npz = out / case['meta'], out / case['npz']
                if marker.exists():
                    held = read(marker)
                    assert held['question_id'] == qid and held['source_record_sha256'] == record_sha
                    assert held['npz_sha256'] == sha(npz)
                    completed += 1
                    print(json.dumps({'status': 'verified_existing', 'complete': completed, 'expected': 95}), flush=True)
                    continue
                meta = row['meta']
                assert meta['snapshot']['snapshot_sha256'] == prepared.provenance['snapshot_sha256']
                interp = meta['interpreter']
                weights = np.array([[t['facets'][f] for f in A.FACETS] for t in interp['tags']], dtype=np.float64)
                if cohort == 'smoke10':
                    with np.load(cached[qid], allow_pickle=False) as held:
                        matrices = {k: held[k].copy() for k in MATRIX_KEYS}
                        assert np.array_equal(held['query_facet_weights'], weights)
                    mode = 'verified_cached_correspondence'
                    recipe_hash = meta['embedding']['vector_sha256']
                else:
                    with (out / 'private_embedding.log').open('a', encoding='utf-8') as log:
                        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                            matrices, usage, recipe = A._query_cosines(interp['description'], [t['t'] for t in interp['tags']], prepared)
                    assert recipe['vector_sha256'] == meta['embedding']['vector_sha256'], 'Local embedding hash differs'
                    mode = 'exact_local_embedding_reconstruction'
                    recipe_hash = recipe['vector_sha256']
                assert matrices['query_tag_cosines'].shape == (len(weights), len(prepared.tag_vectors))
                assert matrices['query_chunk_cosines'].shape == (len(weights), len(chunk_ids))
                assert matrices['query_description_cosines'].shape == (len(chunk_ids),)
                arrays = {**matrices, 'query_facet_weights': weights}
                assert all(np.isfinite(v).all() for v in arrays.values())
                scores = {r['chunk_id']: r['score'] for r in meta['ranking']['rows']}
                assert set(scores) == set(chunk_ids)
                payload = {
                    'question_id': qid, 'case_id': case['case_id'], 'cohort': cohort,
                    'area': meta['area']['area'],
                    'expected_scores': [scores[cid] for cid in chunk_ids],
                    'baseline_order': meta['full_recovered_order'],
                    'baseline_ranked_chunk_ids': meta['ranking']['ranked_chunk_ids'],
                    'baseline_delivered_chunk_ids': meta['delivered_chunk_ids'],
                    'baseline_context_ids': row['context_ids'],
                    'baseline_chunk_context_ids': meta['chunk_ids'],
                    'baseline_budget': meta['char_budget'],
                    'embedding_hash': recipe_hash, 'embedding_mode': mode,
                    'source_record_sha256': record_sha, 'source_file': relative(source),
                    'manifest_sha256': sha(manifest_path), 'language_model_calls': 0,
                }
                # NPZ is committed before its JSON completion marker. An orphan
                # NPZ after interruption may be adopted only if all arrays match.
                if npz.exists():
                    with np.load(npz, allow_pickle=False) as orphan:
                        assert set(orphan.files) == set(arrays)
                        assert all(np.array_equal(orphan[k], v) for k, v in arrays.items())
                else:
                    fd, tmp = tempfile.mkstemp(dir=out, suffix='.npz.partial')
                    try:
                        with os.fdopen(fd, 'wb') as handle:
                            np.savez_compressed(handle, **arrays)
                        os.rename(tmp, npz)
                    finally:
                        if os.path.exists(tmp):
                            os.unlink(tmp)
                payload['npz_sha256'] = sha(npz)
                write_new(marker, payload)
                completed += 1
                print(json.dumps({'status': 'captured', 'complete': completed, 'expected': 95, 'cohort': cohort, 'embedding_hash_matched': True}), flush=True)
        assert stat(source) == source_stats[relative(source)], 'Source changed during capture'
        source_hashes[relative(source)] = hasher.hexdigest()
        if cohort == 'smoke10':
            assert source_hashes[relative(source)] == numerical['input_sha256'][relative(source)]
    assert seen == set(by_id)
    verify_hashes(hashes)
    verification = {'source_sha256': source_hashes, 'completed_cases': completed,
                    'frozen_dependency_hashes_verified': True, 'language_model_calls': 0,
                    'expected_failures_preserved': len(failed)}
    path = out / 'source_verification.json'
    if path.exists():
        assert read(path) == verification
    else:
        write_new(path, verification)
    print(json.dumps({'status': 'complete', 'complete': completed, 'expected': 95}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    lock = args.out / 'capture.lock'
    write_new(lock, {'pid': os.getpid(), 'started_utc': datetime.now(timezone.utc).isoformat()})
    try:
        capture(args.out)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
