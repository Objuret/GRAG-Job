"""One extra stored relation, unchanged propagation and aggregation arithmetic."""
from collections import defaultdict
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact.facet_scope_recruitment import recruit_with_verified_area
from artefact.facet_query_reconstruction import aggregate_route_profiles
from facet_query_reconstruction_replay import read, write, sha

BASE = ROOT / 'output/research/2026-09-22-joint-streams/independent_sources'
STATIC = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
OUT = BASE / 'product_connectivity/run'
QIDS = ('sentiment_intended_use', 'sentiment_review_observations')
BETA = np.array([1., .25, .25, .25, .25])


def product_proposals(direct, d, groups, ids):
    """Best other seed per actual Product; duplicate paths do not add votes."""
    values = np.zeros_like(direct)
    seeds = np.full(direct.shape, -1, dtype=int)
    for pid, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        for f in range(direct.shape[0]):
            for i in range(direct.shape[1]):
                best = sorted(members, key=lambda c: (-direct[f, i, c], ids[c]))[:2]
                for c in members:
                    seed = next(s for s in best if s != c)
                    value = .5 * direct[f, i, seed] * d[i, c]
                    previous = seeds[f, i, c]
                    if value > values[f, i, c] or (value > 0 and value == values[f, i, c]
                            and (previous < 0 or ids[seed] < ids[previous])):
                        values[f, i, c], seeds[f, i, c] = value, seed
    return values, seeds


def profiles(values, fit):
    equal = deepcopy(fit)
    equal['coefficients'] = np.ones(len(equal['groups'])) / len(equal['groups'])
    return {'max': values.max(axis=1), 'equal': aggregate_route_profiles(values, equal)['profiles'],
            'reconstruction': aggregate_route_profiles(values, fit)['profiles']}


def scores(profile, q, mode):
    return q * (profile.T @ BETA) if mode == 'max' else q * (BETA @ profile)


def inclusion(recruitment, cid):
    row = next(r for r in recruitment['rows'] if r['chunk_id'] == cid)
    frontier = next((f for f in recruitment['frontiers'] if cid in f['chunk_ids']), None)
    return {'depth': row['depth'], 'selected': cid in recruitment['selected_chunk_ids'],
            'acquisition_source_characters': None if frontier is None else frontier['cumulative_source_characters']}


def main():
    if OUT.exists():
        raise RuntimeError('Existing Product intervention; inspect rather than overwrite')
    graph = read(STATIC / 'graph.json')
    ids, chunks = graph['chunk_ids'], graph['chunks']
    queries = {q['question_id']:q for q in read(BASE / 'query_snapshot/queries.json')['queries']}
    arrays = np.load(BASE / 'query_snapshot/arrays.npz')
    fits = read(BASE / 'query_reconstruction/run/query_fits.json')['queries']
    scope_rows = [r for r in read(BASE / 'scope_recruitment/run/summary.json') if r['question_id'] in QIDS]
    assert len(scope_rows) == 4
    scope_manifest = read(BASE / 'scope_recruitment/run/manifest.json')
    old_manifest = read(BASE / 'query_reconstruction/run/manifest.json')
    groups = defaultdict(list)
    for c, chunk in enumerate(chunks):
        for p in chunk['scope'].get('product', []):
            groups[p['node_id']].append(c)
    paths = [Path(__file__), OUT.parent / 'PROTOCOL.md', STATIC / 'graph.json',
        BASE / 'query_snapshot/queries.json', BASE / 'query_snapshot/arrays.npz',
        BASE / 'query_reconstruction/run/query_fits.json', BASE / 'query_reconstruction/run/manifest.json',
        BASE / 'scope_recruitment/run/summary.json', BASE / 'scope_recruitment/run/manifest.json',
        ROOT / 'tools/facet_query_reconstruction_replay.py',
        ROOT / 'test/artefact/facet_scope_recruitment.py', ROOT / 'test/artefact/facet_recruitment_candidate.py',
        ROOT / 'test/artefact/facet_need_frontier.py', ROOT / 'test/artefact/facet_query_reconstruction.py',
        ROOT / 'test/artefact/facet_stream_envelope.py', ROOT / 'test/artefact/facet_joint_candidate.py']
    captures = []
    for row in scope_rows:
        rid, qid = row['reading_id'], row['question_id']
        sp = BASE / 'scope_recruitment/run' / row['file']
        rp = BASE / 'need_selection/replay' / (rid + '_routes.npz')
        assert sha(sp) == row['sha256']
        assert sha(rp) == scope_manifest['input_sha256'][str(rp.relative_to(ROOT))]
        archive = json.loads(gzip.decompress(sp.read_bytes()))
        assert not archive['area_chunk_ids'], 'Both original areas must remain unresolved'
        old_outputs = {}
        for mode in ('max', 'equal', 'reconstruction'):
            p = BASE / 'query_reconstruction/run' / (rid + '_' + mode + '.json.gz')
            assert sha(p) == old_manifest['output_sha256'][p.name]
            old_outputs[mode] = json.loads(gzip.decompress(p.read_bytes()))
            paths.append(p)
        captures.append((row, rp, old_outputs))
        paths.extend([sp, rp])
    initial = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    OUT.mkdir(parents=True)
    write(OUT / 'inputs.json', {'input_sha256':initial, 'Product_groups':{k:[ids[i] for i in v] for k,v in groups.items()},
          'question_ids':QIDS, 'beta':BETA, 'hop_discount':.5})
    all_outputs, diagnostics, exact = [], [], 0
    for row, rp, old_outputs in captures:
        rid, qid = row['reading_id'], row['question_id']
        query = queries[qid]
        old = np.load(rp)
        assert old['chunk_ids'].tolist() == ids
        direct, old_graph, q = old['direct_scores'], old['graph_scores'], old['Q']
        d = np.maximum(arrays['query_tag_chunk_cos'][query['query_tag_indices']], 0)
        old_values = np.maximum(direct, old_graph)
        fit = fits[qid]['fit']
        old_profiles = profiles(old_values, fit)
        for mode, p in old_profiles.items():
            s = scores(p, q, mode)
            assert np.array_equal(s, old_outputs[mode]['joint_scores'])
            r = recruit_with_verified_area(chunk_rows=chunks, joint_scores=s, source_character_budget=72000)['recruitment']
            assert r == old_outputs[mode]['recruitment']
            exact += 1
        prop, seeds = product_proposals(direct, d, groups, ids)
        graph_scores = np.maximum(old_graph, prop)
        values = np.maximum(direct, graph_scores)
        assert np.all(values >= old_values)
        np.savez_compressed(OUT / (rid + '_routes.npz'), product_scores=prop, product_seed_indices=seeds,
            graph_scores=graph_scores, direct_scores=direct, D=d, Q=q, chunk_ids=ids)
        diagnostics.append({'reading_id':rid, 'changed_graph_cells':int(np.count_nonzero(graph_scores != old_graph)),
            'changed_combined_cells':int(np.count_nonzero(values != old_values)),
            'changed_combined_chunks':int(np.any(values != old_values, axis=(0,1)).sum())})
        for mode, p in profiles(values, fit).items():
            s = scores(p, q, mode)
            r = recruit_with_verified_area(chunk_rows=chunks, joint_scores=s, source_character_budget=72000)['recruitment']
            name = rid + '_' + mode + '.json.gz'
            payload = {'reading_id':rid, 'question_id':qid, 'aggregation':mode, 'joint_scores':s.tolist(),
                       'facet_profiles':p.tolist(), 'recruitment':r}
            (OUT / name).write_bytes(gzip.compress(json.dumps(payload, separators=(',', ':'), allow_nan=False).encode(), mtime=0))
            all_outputs.append((name, payload, old_outputs[mode]))
        print(rid, 'three Product-connected selections saved', flush=True)
    assert exact == len(all_outputs) == 12
    target_path = BASE / 'protocol.json'
    targets = {t['question_id']:t for t in read(target_path)['targets']}
    summary = []
    for name, payload, baseline in all_outputs:
        target = targets[payload['question_id']]
        ns = set(payload['recruitment']['selected_chunk_ids'])
        bs = set(baseline['recruitment']['selected_chunk_ids'])
        summary.append({k:payload[k] for k in ('reading_id','question_id','aggregation')} |
            {'focal':{role:{'chunk_id':target[role], 'old':inclusion(baseline['recruitment'],target[role]),
                'new':inclusion(payload['recruitment'],target[role]),
                'old_score':baseline['joint_scores'][ids.index(target[role])],
                'new_score':payload['joint_scores'][ids.index(target[role])]} for role in ('preferred','comparison')},
             'selected_chunks':len(ns), 'added_chunk_ids':sorted(ns-bs), 'removed_chunk_ids':sorted(bs-ns),
             'changed_chunk_scores':int(np.count_nonzero(np.asarray(payload['joint_scores']) != baseline['joint_scores'])),
             'file':name, 'sha256':sha(OUT/name)})
    write(OUT/'summary.json',summary)
    write(OUT/'diagnostics.json',diagnostics)
    assert all(sha(ROOT/p)==h for p,h in initial.items())
    initial[str(target_path.relative_to(ROOT))]=sha(target_path)
    write(OUT/'manifest.json',{'input_sha256':initial,'output_sha256':{p.name:sha(p) for p in OUT.iterdir()},
                             'baselines_exact':exact,'selections':len(all_outputs),'new_model_calls':0,'db_calls':0})


if __name__ == '__main__':
    main()
