"""Run both nomination policies through the same reusable context recovery.

Frozen route inputs only. No fitting, query calls, embeddings, DB or production
resolver. Optional character budget is explicitly for saved source text.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'test'))
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
GRAPH = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
PREVIOUS = BASE / 'need_selection/replay'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-character-budget', type=int, default=None)
    parser.add_argument('--output', type=Path, default=BASE / 'need_selection/consolidated/replay')
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise RuntimeError('Refusing to overwrite frozen replay')
    from artefact.facet_need_frontier import build_streams
    from artefact.facet_recruitment_candidate import recruit_with_record_context

    graph = read(GRAPH)
    ids, chunks = graph['chunk_ids'], graph['chunks']
    assert [c['chunkId'] for c in chunks] == ids
    assert all(hashlib.sha256(c['source_text'].encode()).hexdigest() == c['source_text_sha256'] for c in chunks)
    previous = [r for r in read(PREVIOUS / 'summary.json') if r['mode'] in ('joint', 'facets')]
    assert len(previous) == 28 and len({r['reading_id'] for r in previous}) == 14
    paths = [Path(__file__), GRAPH, PREVIOUS / 'summary.json', BASE / 'protocol.json',
             BASE / 'need_selection/content_audit/record_context_probe.json',
             ROOT / 'test/artefact/facet_recruitment_candidate.py',
             ROOT / 'test/artefact/facet_need_frontier.py',
             ROOT / 'test/artefact/facet_stream_envelope.py',
             ROOT / 'test/artefact/facet_joint_candidate.py',
             ROOT / 'test/tests/test_facet_recruitment_candidate.py']
    paths += [PREVIOUS / (rid + '_routes.npz') for rid in sorted({r['reading_id'] for r in previous})]
    paths += [PREVIOUS / r['file'] for r in previous]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    args.output.mkdir(parents=True, exist_ok=True)
    write(args.output / 'protocol.json', {
        'input_sha256': hashes, 'source_character_budget': args.source_character_budget,
        'policies': ['joint', 'facets'], 'record_context_policy': 'Exact-record contiguous ranges inherit earliest member nomination.',
        'purpose': 'Reusable composition and implementation verification across existing development readings, not fresh semantic validation.',
        'scope': 'No fitted weights, source-derived gates, new queries, embeddings, DB calls or production serialization.'})
    computed = []
    for row in previous:
        rid, mode = row['reading_id'], row['mode']
        with np.load(PREVIOUS / (rid + '_routes.npz')) as a:
            assert a['chunk_ids'].tolist() == ids
            values = np.maximum(a['direct_scores'], a['graph_scores'])
            stream_ids, scores = build_streams(values, a['Q'], {'all': list(range(values.shape[1]))}, mode)
        result = recruit_with_record_context(chunk_rows=chunks, stream_ids=stream_ids,
            stream_scores=scores, source_character_budget=args.source_character_budget)
        old = read(PREVIOUS / row['file'])
        assert result['nomination'] == {k: old[k] for k in result['nomination']}, 'Nomination drift'
        filename = rid + '_' + mode + '.json.gz'
        payload = {'reading_id': rid, 'question_id': row['question_id'], 'mode': mode, **result}
        (args.output / filename).write_bytes(gzip.compress(
            json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode(), mtime=0))
        computed.append((row, result, filename))
        print(rid, mode, 'nomination reproduced;', len(result['selected_chunk_ids']), 'selected', flush=True)

    # Source targets are used only for the subsequent descriptive join.
    targets = {t['question_id']: t for t in read(BASE / 'protocol.json')['targets']}
    prior_probe = read(BASE / 'need_selection/content_audit/record_context_probe.json')
    equivalence = 0
    summary = []
    for old, result, filename in computed:
        rows = {r['chunk_id']: r for r in result['rows']}
        target = targets[old['question_id']]
        selected = set(result['selected_chunk_ids'])
        focal_ids = target.get('required_within_selected_pair') or [target['preferred'], target['comparison']]
        focal = {cid: {**rows[cid], 'admitted': cid in selected} for cid in focal_ids}
        if old['question_id'] == prior_probe['question_id'] and args.source_character_budget == prior_probe['budget_source_characters']:
            repeat = int(old['reading_id'].rsplit('_score_', 1)[1])
            prior = next(r for r in prior_probe['runs'] if r['mode'] == old['mode'] and r['reading'] == repeat)
            assert all({k: row[k] for k in prior['rows'][0]} == earlier
                       for row, earlier in zip(result['rows'], prior['rows']))
            assert result['frontiers'] == prior['frontiers']
            assert {c['component_id']: c for c in result['components']} == {
                c['component_id']: c for c in prior_probe['components']}
            for key in ('selected_chunk_ids', 'crossing_frontier_chunk_ids', 'unsupported_chunk_ids'):
                assert result[key] == prior[key]
            assert result['selected_source_characters'] == prior['source_characters']
            equivalence += 1
        direction = None
        if target.get('preferred'):
            a, b = rows[target['preferred']]['depth'], rows[target['comparison']]['depth']
            direction = 'both_unsupported' if a is None and b is None else (
                'comparison_first' if a is None else 'preferred_first' if b is None or a < b
                else 'tie' if a == b else 'comparison_first')
        summary.append({'reading_id': old['reading_id'], 'question_id': old['question_id'],
            'mode': old['mode'], 'focal': focal, 'pair_depth_direction': direction,
            'selected_chunks': len(selected), 'source_characters': result['selected_source_characters'],
            'context_advanced_chunks': sum(r['context_added'] for r in result['rows']),
            'context_advanced_selected_chunks': sum(r['context_added'] and r['chunk_id'] in selected for r in result['rows']),
            'file': filename, 'sha256': sha(args.output / filename)})
    assert all(sha(ROOT / p) == h for p, h in hashes.items())
    write(args.output / 'summary.json', summary)
    write(args.output / 'verification.json', {'input_hashes_unchanged': True,
        'exact_nomination_matches': len(computed), 'exact_previous_record_probe_matches': equivalence,
        'summary_sha256': sha(args.output / 'summary.json'), 'all_files': {r['file']: r['sha256'] for r in summary}})
    print('Completed', len(summary), 'compositions;', equivalence, 'exact prior probe matches')


if __name__ == '__main__':
    main()
