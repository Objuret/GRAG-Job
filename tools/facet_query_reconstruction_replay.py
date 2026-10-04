"""Frozen query-geometry aggregation experiment on existing route tensors."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
OUT = BASE / 'query_reconstruction/run'
SCOPE = BASE / 'scope_recruitment/run'
ROUTES = BASE / 'need_selection/replay'
BETA = np.array([1., .25, .25, .25, .25])


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def serial(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def write(path, value):
    path.write_text(json.dumps(value, default=serial, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    from artefact.facet_query_reconstruction import reconstruct_query_description, aggregate_route_profiles
    from artefact.facet_scope_recruitment import recruit_with_verified_area
    if OUT.exists():
        raise RuntimeError('Refusing to overwrite query reconstruction outputs')
    graph_path = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot/graph.json'
    graph = read(graph_path)
    chunks, ids = graph['chunks'], graph['chunk_ids']
    assert [c['chunkId'] for c in chunks] == ids
    meta_path = BASE / 'query_snapshot/queries.json'
    vectors_path = BASE / 'query_snapshot/arrays.npz'
    queries = {q['question_id']: q for q in read(meta_path)['queries']}
    with np.load(vectors_path) as a:
        tv, dv = a['query_tag_vectors'], a['description_vectors']
    previous = read(SCOPE / 'summary.json')
    scope_manifest = read(SCOPE / 'manifest.json')
    assert all(sha(SCOPE / p) == h for p, h in scope_manifest['output_sha256'].items())
    paths = [Path(__file__), graph_path, meta_path, vectors_path, SCOPE / 'manifest.json',
             SCOPE / 'summary.json', SCOPE / 'live_membership.json',
             BASE / 'query_reconstruction/PROTOCOL.md',
             ROOT / 'test/artefact/facet_query_reconstruction.py',
             ROOT / 'test/artefact/facet_scope_recruitment.py',
             ROOT / 'test/artefact/facet_recruitment_candidate.py',
             ROOT / 'test/artefact/facet_need_frontier.py',
             ROOT / 'test/artefact/facet_stream_envelope.py']
    OUT.mkdir(parents=True)
    fits = {}
    for qid, query in queries.items():
        fit = reconstruct_query_description(tv[query['query_tag_indices']], dv[query['description_index']])
        fits[qid] = fit
    write(OUT / 'query_fits.json', {'queries': {qid: {'tags': queries[qid]['tags'], 'fit': fit} for qid, fit in fits.items()}})
    computed, summary = [], []
    lengths = {c['chunkId']: len(c['source_text']) for c in chunks}
    for old in previous:
        rid, qid = old['reading_id'], old['question_id']
        old_path, routes_path = SCOPE / old['file'], ROUTES / (rid + '_routes.npz')
        paths += [old_path, routes_path]
        assert sha(old_path) == old['sha256']
        archived = json.loads(gzip.decompress(old_path.read_bytes()))
        area = set(archived['area_chunk_ids']) if archived['area_chunk_ids'] else None
        with np.load(routes_path) as a:
            assert a['chunk_ids'].tolist() == ids
            values, q = np.maximum(a['direct_scores'], a['graph_scores']), a['Q']
        geometry = aggregate_route_profiles(values, fits[qid])
        equal_fit = deepcopy(fits[qid])
        equal_fit['coefficients'] = np.ones(len(equal_fit['groups'])) / len(equal_fit['groups'])
        for group, coefficient in zip(equal_fit['groups'], equal_fit['coefficients']):
            group['coefficient'] = float(coefficient)
        equal = aggregate_route_profiles(values, equal_fit)
        profiles = {'max': values.max(axis=1), 'equal': equal['profiles'], 'reconstruction': geometry['profiles']}
        for mode, profile in profiles.items():
            scores = q * (BETA @ profile)
            # Use the baseline's archived arithmetic order for bit-exact reproduction.
            if mode == 'max':
                scores = q * (profile.T @ BETA)
            result = recruit_with_verified_area(chunk_rows=chunks, joint_scores=scores,
                        area_chunk_ids=area, area_provenance=archived['area'] if area else None,
                        source_character_budget=72000)
            recruitment = result['recruitment']
            if mode == 'max':
                assert np.array_equal(scores, np.asarray(archived['stream_scores'])[0])
                assert recruitment == archived['recruitment'], 'Baseline mismatch'
            filename = rid + '_' + mode + '.json.gz'
            payload = {'reading_id': rid, 'question_id': qid, 'mode': mode,
                       'joint_scores': scores.tolist(), 'facet_profiles': profile.tolist(),
                       'recruitment': recruitment}
            (OUT / filename).write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode(), mtime=0))
            selected = set(recruitment['selected_chunk_ids'])
            summary.append({'reading_id': rid, 'question_id': qid, 'mode': mode,
                'selected_chunks': len(selected), 'source_characters': sum(lengths[c] for c in selected),
                'inside_chunks': None if area is None else len(selected & area),
                'outside_chunks': None if area is None else len(selected - area),
                'unsupported_chunks': len(recruitment['unsupported_chunk_ids']),
                'file': filename, 'sha256': sha(OUT / filename)})
            computed.append((summary[-1], recruitment))
        print(rid, 'all three compositions saved', flush=True)
    write(OUT / 'selection_summary.json', summary)
    # Source labels are deliberately read only after every composition is saved.
    targets_path = BASE / 'protocol.json'
    targets = {t['question_id']: t for t in read(targets_path)['targets']}
    audit = BASE / 'need_selection/content_audit'
    alias_paths = [audit / 'private_manifest.json', audit / 'record_context_probe.json']
    aliases = {**read(alias_paths[0])['aliases'], **read(alias_paths[1])['additional_reader_aliases']}
    reader_paths = [audit / (r+s+'.json') for r in ('reader_one','reader_two') for s in ('','_additional')]
    readers = {r: {e['passage_id']: e for s in ('','_additional') for e in read(audit / (r+s+'.json'))['entries']}
               for r in ('reader_one','reader_two')}
    comparisons, content = [], []
    for row, recruitment in computed:
        qid = row['question_id']
        target = targets[qid]
        by_id = {r['chunk_id']: r for r in recruitment['rows']}
        if target.get('preferred') is not None:
            a, b = (by_id[target[k]]['depth'] for k in ('preferred','comparison'))
            aa, bb = float('inf') if a is None else a, float('inf') if b is None else b
            comparisons.append({**{k: row[k] for k in ('reading_id','question_id','mode')},
                'preferred_depth': a, 'comparison_depth': b,
                'direction': 'preferred_first' if aa < bb else 'comparison_first' if bb < aa else 'tie'})
        else:
            chosen = set(recruitment['selected_chunk_ids'])
            known = chosen & set(aliases)
            content.append({**{k: row[k] for k in ('reading_id','question_id','mode')},
                'unjudged_chunk_ids': sorted(chosen-known),
                'direct_support': {r: {f: sorted(cid for cid in known
                    if entries[aliases[cid]]['scope']=='supports_requested_system'
                    and entries[aliases[cid]]['components'][f]['category']=='direct')
                    for f in ('durability','model_updates','refresh_frequency')} for r,entries in readers.items()}})
    paths += [targets_path, *alias_paths, *reader_paths]
    write(OUT / 'source_comparisons.json', comparisons)
    write(OUT / 'content_join.json', content)
    write(OUT / 'manifest.json', {'input_sha256': {str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))},
        'output_sha256': {p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        'baseline_exact':14, 'compositions':len(computed),
        'limits':'Geometry weights, not calibrated facet utility. Existing development questions and model source readings; no new generalization claim.'})


if __name__ == '__main__':
    main()
