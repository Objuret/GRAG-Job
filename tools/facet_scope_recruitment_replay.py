"""One frozen structural-recruitment intervention; read-only Volmax verification."""
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
STATIC = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
PREVIOUS = BASE / 'need_selection/consolidated/replay'
ROUTES = BASE / 'need_selection/replay'
OUT = BASE / 'scope_recruitment/run'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_membership(graph):
    from graph.db import _driver
    eligible = set(graph['chunk_ids'])
    query = ('MATCH (c:Chunk)-[:product]->(p:Product) '
             'WHERE c.chunk_id IN $ids RETURN DISTINCT c.chunk_id AS chunk_id, '
             'p.name AS name, elementId(p) AS node_id ORDER BY chunk_id,name,node_id')
    with _driver() as driver:
        with driver.session(database='herb-eval-volmax', default_access_mode='READ') as session:
            rows = [dict(r) for r in session.run(query, ids=sorted(eligible))]
    live, saved = defaultdict(set), defaultdict(set)
    for row in rows:
        live[row['chunk_id']].add((row['name'], row['node_id']))
    for chunk in graph['chunks']:
        saved[chunk['chunkId']].update((p['name'], p['node_id']) for p in chunk['scope'].get('product', []))
    errors = [cid for cid in sorted(eligible) if live[cid] != saved[cid]]
    if errors:
        raise RuntimeError(f'Live membership differs from frozen snapshot: {len(errors)} chunks; first {errors[:3]}')
    return {'database': 'herb-eval-volmax', 'verified_at': datetime.now(timezone.utc).isoformat(),
            'query': query, 'eligible_chunks': len(eligible), 'membership_rows': rows,
            'result': 'All eligible chunk Product names and node IDs exactly match frozen snapshot.'}


def main():
    from artefact.facet_need_frontier import build_streams
    from artefact.facet_recruitment_candidate import recruit_with_record_context
    from artefact.facet_scope_recruitment import recruit_with_verified_area
    if OUT.exists():
        raise RuntimeError('Refusing to overwrite structural recruitment output')
    graph = read(STATIC / 'graph.json')
    chunks, ids = graph['chunks'], graph['chunk_ids']
    assert [c['chunkId'] for c in chunks] == ids
    assert all(hashlib.sha256(c['source_text'].encode()).hexdigest() == c['source_text_sha256'] for c in chunks)
    verified = verify_membership(graph)
    questions = {q['id']: q['question'] for q in read(BASE / 'questions.json')}
    previous = [r for r in read(PREVIOUS / 'summary.json') if r['mode'] == 'joint']
    assert len(previous) == 14
    names = sorted({r['name'] for r in verified['membership_rows']})
    members = {name: {r['chunk_id'] for r in verified['membership_rows'] if r['name'] == name} for name in names}
    resolutions = {}
    for qid, question in questions.items():
        hits = [name for name in names if re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', question, re.IGNORECASE)]
        resolutions[qid] = {'question': question, 'matched_product_names': hits,
                            'used_area': hits[0] if len(hits) == 1 else None,
                            'status': 'single_literal_product' if len(hits) == 1 else 'unresolved_or_multiple'}
    OUT.mkdir(parents=True)
    write(OUT / 'live_membership.json', verified)
    write(OUT / 'resolutions.json', resolutions)
    paths = [Path(__file__), STATIC / 'graph.json', BASE / 'questions.json',
             BASE / 'scope_recruitment/PROTOCOL.md', PREVIOUS / 'summary.json',
             ROOT / 'test/artefact/facet_scope_recruitment.py',
             ROOT / 'test/artefact/facet_recruitment_candidate.py',
             ROOT / 'test/artefact/facet_need_frontier.py']
    summary = []
    for old in previous:
        rid, qid = old['reading_id'], old['question_id']
        archive_path = ROUTES / (rid + '_routes.npz')
        old_path = PREVIOUS / old['file']
        paths.extend([archive_path, old_path])
        assert sha(old_path) == old['sha256']
        archived = json.loads(gzip.decompress(old_path.read_bytes()))
        with np.load(archive_path) as a:
            assert a['chunk_ids'].tolist() == ids
            stream_ids, scores = build_streams(np.maximum(a['direct_scores'], a['graph_scores']),
                                              a['Q'], {'all': list(range(a['direct_scores'].shape[1]))}, 'joint')
        baseline = recruit_with_record_context(chunk_rows=chunks, stream_ids=stream_ids,
                                               stream_scores=scores, source_character_budget=72000)
        assert baseline == {k: archived[k] for k in baseline}, 'Baseline integration mismatch'
        name = resolutions[qid]['used_area']
        area = members[name] if name else None
        result = recruit_with_verified_area(chunk_rows=chunks, joint_scores=scores[0],
                    area_chunk_ids=area, area_provenance=resolutions[qid] if area else None,
                    source_character_budget=72000)
        recruitment = result['recruitment']
        assert recruitment['unsupported_chunk_ids'] == baseline['unsupported_chunk_ids']
        if area is None:
            assert recruitment == baseline, 'Unresolved scope changed retrieval'
        before, after = set(baseline['selected_chunk_ids']), set(recruitment['selected_chunk_ids'])
        lengths = {c['chunkId']: len(c['source_text']) for c in chunks}
        def counts(selected):
            return {'chunks': len(selected), 'characters': sum(lengths[c] for c in selected),
                    'inside_chunks': None if area is None else len(selected & area),
                    'outside_chunks': None if area is None else len(selected - area),
                    'inside_characters': None if area is None else sum(lengths[c] for c in selected & area),
                    'outside_characters': None if area is None else sum(lengths[c] for c in selected - area)}
        payload = {'reading_id': rid, 'question_id': qid, 'area': resolutions[qid],
                   'area_chunk_ids': sorted(area) if area else [],
                   'stream_ids': result['stream_ids'], 'stream_scores': result['stream_scores'].tolist(),
                   'recruitment': recruitment}
        filename = rid + '.json.gz'
        (OUT / filename).write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode(), mtime=0))
        summary.append({'reading_id': rid, 'question_id': qid, 'area': name,
                        'baseline_exact': True, 'supported_population_unchanged': True,
                        'before': counts(before), 'after': counts(after),
                        'added_chunk_ids': sorted(after-before), 'displaced_chunk_ids': sorted(before-after),
                        'context_advanced_selected': sum(r['context_added'] for r in recruitment['rows'] if r['chunk_id'] in after),
                        'unused_capacity': recruitment['unused_capacity'],
                        'file': filename, 'sha256': sha(OUT / filename)})
        print(rid, 'area', name, counts(before), '->', counts(after), flush=True)
    write(OUT / 'summary.json', summary)
    write(OUT / 'manifest.json', {'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(paths))},
          'verified_baselines': len(summary), 'no_area_unchanged': sum(r['area'] is None for r in summary),
          'output_sha256': {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
          'limits': 'Development structural intervention; membership counts are not relevance. No score or coefficient changes.'})


if __name__ == '__main__':
    main()
