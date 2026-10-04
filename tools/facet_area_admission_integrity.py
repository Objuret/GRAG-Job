"""Bind saved resolver provenance and all eligible delivery units, without models.

Private traces and corpus documents are processed mechanically. Only aggregate
counts and hashes are exported; no question, answer, source or context text.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import facet_gold_trace as T


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main(folder):
    target = folder / 'area_admission_diagnosis/integrity.json'
    if target.exists():
        raise ValueError('Integrity output already exists; refusing overwrite')
    paths = {
        'index': T.OUT / 'gold_source_index.json',
        'units': T.OUT / 'chunk_delivery_index.json',
        'verification': T.OUT / 'verification.json',
        'graph': T.SNAPSHOT / 'graph.json',
        'resolver': T.ROOT / 'test/arms/artefact_v2.py',
        'trace_helper': Path(T.__file__),
        'verifier': Path(__file__),
        'remaining_ids': folder / 'remaining90.jsonl',
        'failures': folder / 'failures.jsonl',
    }
    hashes = {key: sha(path) for key, path in paths.items()}
    verification = T.read(paths['verification'])
    assert hashes['index'] == verification['index_sha256']
    assert hashes['units'] == verification['unit_index_sha256']
    index, units, graph = (T.read(paths[k]) for k in ('index', 'units', 'graph'))
    assert hashes['graph'] == index['provenance']['graph_sha256']
    assert hashes['resolver'] == index['provenance']['resolver_sha256']
    eligible = set(graph['chunk_ids'])
    assert len(eligible) == len(graph['chunks']) == 4808
    assert {c['chunkId'] for c in graph['chunks']} == eligible == set(units)
    raw_root = (T.ROOT / 'data/raw').resolve()
    raw_hashes = {}
    for row in index['provenance']['raw_files_verified']:
        path = (raw_root / row['relpath']).resolve()
        assert path.is_relative_to(raw_root)
        assert sha(path) == row['sha256']
        raw_hashes[path] = row['sha256']
    assert len(raw_hashes) == len(index['provenance']['raw_files_verified'])
    expected = {r['id'] for r in T.rows(paths['remaining_ids'])}
    failures = [r['id'] for r in T.rows(paths['failures'])]
    assert len(expected) == 90 and len(set(failures)) == len(failures) == 5
    expected_trace_sha = T.read(folder / 'graph_route_diagnosis/route_audit.json')['input_sha256']
    trace_hash = hashlib.sha256()
    seen = set()
    with (folder / 'arm_outputs.jsonl').open('rb') as stream:
        for raw in stream:
            trace_hash.update(raw)
            if not raw.strip():
                continue
            record = json.loads(raw)
            qid, meta = record['id'], record['meta']
            assert qid in expected and qid not in seen and qid not in failures
            seen.add(qid)
            saved = {key.replace('\\', '/'): value
                     for key, value in meta['snapshot']['source_sha256'].items()}
            assert saved['test/arms/artefact_v2.py'] == hashes['resolver']
            assert meta['snapshot']['snapshot_sha256']['graph.json'] == hashes['graph']
            ranked = [r['chunk_id'] for r in meta['ranking']['rows']]
            assert len(ranked) == len(eligible) and set(ranked) == eligible
            assert set(meta['full_recovered_order']) <= eligible
    assert len(seen) == 85 and seen | set(failures) == expected
    assert trace_hash.hexdigest() == expected_trace_sha
    print(json.dumps({'saved_records_bound': len(seen), 'eligible_units_to_resolve': len(eligible)}), flush=True)
    # Re-resolve ALL eligible units, covering any counterfactual newly delivered
    # unit as well as archived deliveries. Never export the resolved text.
    resolve, cache = T.resolver(), {}
    total_chars = 0
    for n, chunk in enumerate(graph['chunks'], 1):
        text, artifact_ids = resolve(chunk, cache)
        indexed = units[chunk['chunkId']]
        assert len(text) == indexed['serialized_chars']
        assert artifact_ids == indexed['artifact_ids']
        total_chars += len(text)
        if n % 1000 == 0:
            print(json.dumps({'resolved_units_verified': n}), flush=True)
    # Compare resolved paths rather than Windows backslashes versus the stored
    # corpus-relative forward-slash spelling.
    assert set(raw_hashes.items()) == {((raw_root / rel).resolve(), digest)
                                     for rel, digest in cache}
    assert all(sha(path) == digest for path, digest in raw_hashes.items())
    assert all(sha(paths[key]) == digest for key, digest in hashes.items())
    result = {
        'status': 'pass', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'hashes': hashes, 'trace_sha256': trace_hash.hexdigest(),
        'saved_records_resolver_bound': len(seen), 'planned_questions': len(expected),
        'preserved_failures': len(failures), 'eligible_units_verified': len(eligible),
        'raw_files_verified': len(raw_hashes), 'total_serialized_characters': total_chars,
        'all_units_actual_resolver_lengths_and_artifact_ids_match': True,
        'coverage': 'All eligible units, including any newly delivered counterfactual units.',
        'model_calls': 0, 'embedding_calls': 0, 'text_exported': False,
        'limits': 'Integrity of serialization and IDs only, not semantic relevance or answer quality.',
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
