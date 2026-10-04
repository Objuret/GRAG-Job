"""Finish a failed post-selection join from frozen outputs; never rerank/refit."""
from pathlib import Path
import gzip

from facet_query_reconstruction_replay import ROOT, BASE, OUT, SCOPE, ROUTES, read, sha, write
import json


def main():
    for filename in ('source_comparisons.json', 'content_join.json', 'manifest.json', 'recovery.json'):
        if (OUT / filename).exists():
            raise RuntimeError('Refusing to overwrite completed recovery evidence: ' + filename)
    backup = OUT / 'runner_before_join_fix.py'
    if not backup.exists():
        raise RuntimeError('Original runner must be preserved before recovery')
    summary_path = OUT / 'selection_summary.json'
    summary = read(summary_path)
    assert len(summary) == 42
    assert len({(r['reading_id'], r['mode']) for r in summary}) == 42
    assert {r['mode'] for r in summary} == {'max', 'equal', 'reconstruction'}
    initial_hashes = {p.name: sha(p) for p in [summary_path, OUT / 'query_fits.json', backup]}
    computed = []
    for row in summary:
        path = OUT / row['file']
        assert sha(path) == row['sha256'], 'Saved selection output changed'
        initial_hashes[path.name] = row['sha256']
        payload = json.loads(gzip.decompress(path.read_bytes()))
        assert all(payload[k] == row[k] for k in ('reading_id', 'question_id', 'mode'))
        computed.append((row, payload['recruitment']))
    scope_manifest = read(SCOPE / 'manifest.json')
    for path, expected in scope_manifest['output_sha256'].items():
        assert sha(SCOPE / path) == expected
    # Original pre-loop dependencies, with both original and corrected runner retained.
    paths = [ROOT / 'tools/facet_query_reconstruction_replay.py', backup, Path(__file__),
             ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot/graph.json',
             BASE / 'query_snapshot/queries.json', BASE / 'query_snapshot/arrays.npz',
             SCOPE / 'manifest.json', SCOPE / 'summary.json', SCOPE / 'live_membership.json',
             BASE / 'query_reconstruction/PROTOCOL.md',
             ROOT / 'test/artefact/facet_query_reconstruction.py',
             ROOT / 'test/artefact/facet_scope_recruitment.py',
             ROOT / 'test/artefact/facet_recruitment_candidate.py',
             ROOT / 'test/artefact/facet_need_frontier.py',
             ROOT / 'test/artefact/facet_stream_envelope.py']
    for old in read(SCOPE / 'summary.json'):
        old_path = SCOPE / old['file']
        route_path = ROUTES / (old['reading_id'] + '_routes.npz')
        assert sha(old_path) == old['sha256']
        relative = str(route_path.relative_to(ROOT))
        assert sha(route_path) == scope_manifest['input_sha256'][relative]
        paths.extend([old_path, route_path])
    # Exactly the original post-selection join, corrected only for null preferred.
    targets_path = BASE / 'protocol.json'
    targets = {t['question_id']: t for t in read(targets_path)['targets']}
    audit = BASE / 'need_selection/content_audit'
    alias_paths = [audit / 'private_manifest.json', audit / 'record_context_probe.json']
    aliases = {**read(alias_paths[0])['aliases'], **read(alias_paths[1])['additional_reader_aliases']}
    reader_paths = [audit / (r+s+'.json') for r in ('reader_one', 'reader_two') for s in ('', '_additional')]
    readers = {r: {e['passage_id']: e for s in ('', '_additional')
                   for e in read(audit / (r+s+'.json'))['entries']}
               for r in ('reader_one', 'reader_two')}
    comparisons, content = [], []
    for row, recruitment in computed:
        target = targets[row['question_id']]
        by_id = {r['chunk_id']: r for r in recruitment['rows']}
        metadata = {k: row[k] for k in ('reading_id', 'question_id', 'mode')}
        if target.get('preferred') is not None:
            a, b = (by_id[target[k]]['depth'] for k in ('preferred', 'comparison'))
            aa, bb = float('inf') if a is None else a, float('inf') if b is None else b
            comparisons.append({**metadata, 'preferred_depth': a, 'comparison_depth': b,
                'direction': 'preferred_first' if aa < bb else 'comparison_first' if bb < aa else 'tie'})
        else:
            assert target.get('required_within_selected_pair'), 'Null target needs explicit complementary sources'
            chosen = set(recruitment['selected_chunk_ids'])
            known = chosen & set(aliases)
            content.append({**metadata, 'unjudged_chunk_ids': sorted(chosen-known),
                'direct_support': {r: {f: sorted(cid for cid in known
                    if entries[aliases[cid]]['scope'] == 'supports_requested_system'
                    and entries[aliases[cid]]['components'][f]['category'] == 'direct')
                    for f in ('durability', 'model_updates', 'refresh_frequency')}
                    for r, entries in readers.items()}})
    assert len(comparisons) == 36 and len(content) == 6
    paths += [targets_path, *alias_paths, *reader_paths]
    for path, expected in initial_hashes.items():
        assert sha(OUT / path) == expected, 'Recovery changed an original output'
    write(OUT / 'source_comparisons.json', comparisons)
    write(OUT / 'content_join.json', content)
    write(OUT / 'recovery.json', {
        'initial_failure': 'Post-selection source-label join tested key presence; complementary target has preferred=None, so by_id[None] failed after all42 compositions and selection_summary were saved.',
        'correction': 'Use target.get("preferred") is not None. Original runner source saved before this one-line edit.',
        'executed_ranking_runner_source': backup.name,
        'executed_ranking_runner_sha256': sha(backup),
        'corrected_future_runner_sha256': sha(ROOT / 'tools/facet_query_reconstruction_replay.py'),
        'finisher_sha256': sha(Path(__file__)),
        'preserved_original_output_sha256': initial_hashes,
        'saved_compositions_verified': 42, 'recomputed_rankings': 0, 'refitted_queries': 0,
        'new_model_calls': 0, 'new_db_calls': 0,
        'provenance_limit': 'Final dependency manifest was completed during recovery, not emitted before the original ranking run; original ranking source and all saved selections remain intact.',
    })
    write(OUT / 'manifest.json', {
        'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(paths))},
        'output_sha256': {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        'baseline_exact': 14, 'compositions': 42,
        'completion': 'Recovered post-selection joins from saved outputs; see recovery.json. No reranking or refitting.',
        'limits': 'Geometry weights, not calibrated facet utility. Existing development questions and model source readings; no new generalization claim.',
    })
    print('Verified42 saved outputs; completed36 pair comparisons and6 content joins without reranking/refitting.')


if __name__ == '__main__':
    main()
