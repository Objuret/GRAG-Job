"""Replay frozen intended query readings through current forum operators, offline.

No benchmark, model, embedding, graph, or production modification. This is an
experimental split-query adapter: the serving arm still uses its old interpreter.
"""
from pathlib import Path
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'prod'), str(ROOT / 'test')]
from artefact.facet_route_rank import FACETS, ForumConfig, replay_forum
from harness.char_budget import cut_at_budget

BASE = ROOT / 'output/research/2026-09-21-facet-validity'
FOCAL = {'report': '23540be897d31a78f8ac0f39', 'sharing': '62eecebfe117e91df15db8e3'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def write(path, value):
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=BASE)
    args = ap.parse_args()
    base = args.base
    out = base / 'route_replay'
    out.mkdir(exist_ok=True)
    capture_path = base / 'route_capture/query_captures.json'
    graph_path = base / 'route_snapshot/graph.json'
    array_path = base / 'route_snapshot/arrays.npz'
    captures, graph = read(capture_path), read(graph_path)
    arrays = np.load(array_path, allow_pickle=False)
    if captures['facets'] != list(FACETS) or graph['facets'] != list(FACETS):
        raise ValueError('Facet schema mismatch')
    defaults = graph['operator_defaults']
    queries = {q['id']: q for q in graph['queries']}
    chunk_ids = graph['chunk_ids']
    ci = {c: i for i, c in enumerate(chunk_ids)}
    ti = {t: i for i, t in enumerate(graph['query_tags'])}
    edge_tag, edge_chunk = arrays['edge_tag'], arrays['edge_chunk']
    edge_count = len(edge_tag)
    completed, skipped, comparisons = [], [], []
    resolved_path = base / 'route_snapshot/resolved_contexts.json'
    resolved = read(resolved_path) if resolved_path.exists() else None
    # Resolver sidecar contract: contexts maps chunk ID to {text, ids}; failures explicit.
    contexts = (resolved or {}).get('contexts', {})
    for capture in captures['captures']:
        generation = capture['generation_id']
        query = queries[generation]
        if capture['description'] != query['description'] or capture['clean_tags'] != query['tags']:
            raise ValueError('Snapshot and parsed generation do not match exactly')
        part_names = capture['clean_tags']
        parts = [ti[t] for t in part_names]
        di = query['description_index']
        for reading in capture['readings']:
            if not reading.get('ok'):
                skipped.append({'id': reading['id'], 'error': reading.get('error')})
                continue
            by_tag = {v['t']: v['facets'] for v in reading['values']}
            qf = np.array([[by_tag[t][f] for f in FACETS] for t in part_names])
            # Actual facet_order fallback for split tags with no explicit order:
            # descending per-tag readings, canonical layout breaks exact ties.
            orders = [tuple(sorted(FACETS, key=lambda f: (-row[FACETS.index(f)], FACETS.index(f)))) for row in qf]
            for mode in ('weighted', 'multirank'):
                config = ForumConfig(mode=mode, tag_band=query['tag_band'],
                    description_band=query['desc_band'], topic_band=defaults['topic_band'],
                    facet_band=defaults['facet_band'], r_band=defaults['r_band'],
                    betas=tuple(defaults['betas'][f] for f in FACETS[1:]),
                    topic_key=defaults['topic_key'], description_place=defaults['desc_place'],
                    adjust=defaults['adjust'])
                pair_runs = []
                for zero in (False, True):
                    run_id = reading['id'] + '_' + mode + ('_zero' if zero else '_real')
                    started = time.perf_counter()
                    replay = replay_forum(edge_tag=edge_tag, edge_chunk=edge_chunk,
                        edge_facets=arrays['edge_facets'], chunk_ids=chunk_ids,
                        tag_cos=arrays['query_tag_graph_cos_forum_precision'][parts],
                        part_chunk_cos=arrays['query_tag_chunk_cos'][parts],
                        description_chunk_cos=arrays['description_chunk_cos'][di],
                        centrality=arrays['centrality'][di, parts], query_facets=qf,
                        facet_orders=orders, config=config, candidate_tag=arrays['candidate_tag'],
                        in_scope=None, zeroed_facets=zero)
                    ordered = [chunk_ids[i] for i in replay.chunk_order]
                    ranks = {cid: i + 1 for i, cid in enumerate(ordered)}

                    def trace(route):
                        detail = replay.trace(int(route))
                        pi, ei = divmod(int(route), edge_count)
                        detail.update(query_tag=part_names[pi], graph_tag=graph['graph_tags'][edge_tag[ei]],
                            edge_id=graph['edge_ids'][ei], query_facets=dict(zip(FACETS, qf[pi].tolist())),
                            graph_facets_captured=dict(zip(FACETS, arrays['edge_facets'][ei].tolist())),
                            graph_facets_used=dict(zip(FACETS, [float(arrays['edge_facets'][ei, 0]),
                                *([0.] * 4 if zero else arrays['edge_facets'][ei, 1:].tolist())])),
                            tag_cosine=float(arrays['query_tag_graph_cos_forum_precision'][parts[pi], edge_tag[ei]]),
                            part_chunk_cosine=float(arrays['query_tag_chunk_cos'][parts[pi], edge_chunk[ei]]),
                            description_chunk_cosine=float(arrays['description_chunk_cos'][di, edge_chunk[ei]]))
                        return detail

                    focal = {}
                    for name, cid in FOCAL.items():
                        edges = np.flatnonzero(edge_chunk == ci[cid])
                        focal[name] = {'chunk_id': cid, 'rank': ranks.get(cid),
                            'chosen': trace(replay.selected_by_chunk[ci[cid]]),
                            'all_routes': [trace(p * edge_count + e) for p in range(len(parts)) for e in edges]}
                    report_route = replay.selected_by_chunk[ci[FOCAL['report']]]
                    sharing_route = replay.selected_by_chunk[ci[FOCAL['sharing']]]
                    decision = replay.deciding_key(report_route, sharing_route)
                    tally = Counter(replay.deciding_key(a, b)['field'] or 'exact tie'
                        for a, b in zip(replay.selected_routes[:-1], replay.selected_routes[1:]))
                    budget = {'available': False, 'reason': 'Exact resolved contexts absent or incomplete; no delivery claim.'}
                    if all(cid in contexts for cid in ordered):
                        cut = cut_at_budget(((cid, contexts[cid]['text']) for cid in ordered), 72000)
                        budget = {'available': True, 'chars': cut.chars, 'kept': cut.kept,
                            'boundary': cut.boundary, 'exhausted': cut.exhausted,
                            'fully_delivered_chunk_ids': ordered[:cut.kept],
                            'focal_fully_delivered': {name: cid in ordered[:cut.kept] for name, cid in FOCAL.items()}}
                    correct = ranks[FOCAL['report']] < ranks[FOCAL['sharing']] if capture['question_id'] == 'analysis' else ranks[FOCAL['sharing']] < ranks[FOCAL['report']]
                    summary = {'id': run_id, 'generation': generation, 'reading': reading['id'], 'mode': mode,
                        'zeroed_non_topic_graph_facets': zero, 'matches_source_pair_expectation': bool(correct),
                        'expected_earlier_chunk': FOCAL['report' if capture['question_id'] == 'analysis' else 'sharing'],
                        'focal_ranks': {name: row['rank'] for name, row in focal.items()},
                        'pair_deciding_rule': decision, 'deciding_key_counts_full_order': dict(tally),
                        'budget': budget, 'seconds': time.perf_counter() - started}
                    write(out / (run_id + '.json'), {**summary, 'config': asdict(config),
                        'part_tags': part_names, 'part_priority': replay.part_priority.tolist(),
                        'facet_orders': orders, 'focal': focal, 'chunk_order': ordered})
                    completed.append(summary)
                    pair_runs.append(ordered)
                    print(run_id, summary['focal_ranks'], decision['field'], flush=True)
                real, zero_order = pair_runs
                zr = {cid: i for i, cid in enumerate(zero_order)}
                comparisons.append({'reading': reading['id'], 'mode': mode,
                    'chunks_changing_position': sum(zr[cid] != i for i, cid in enumerate(real)),
                    'max_absolute_position_change': max(abs(zr[cid] - i) for i, cid in enumerate(real))})
    sources = [Path(__file__), ROOT / 'test/artefact/facet_route_rank.py', capture_path, graph_path, array_path,
               base / 'route_check_protocol.md']
    if resolved_path.exists():
        sources.append(resolved_path)
    write(out / 'summary.json', {'protocol': __doc__, 'source_sha256': {str(p): sha(p) for p in sources},
        'scope': 'No inferred gate; one pass. Split querytagger does not produce structural scope.',
        'adapter': 'Per-tag facet relevance supplied unchanged; descending relevance with canonical ties supplies multikey order.',
        'limits': ['Two constructed diagnostic questions; no corpus-wide relevance judgment.',
            'Default source operators, not a validated weight recommendation.',
            'Generation variation and SCORE variation retained separately.'],
        'runs': completed, 'skipped_readings': skipped, 'ablations': comparisons})


if __name__ == '__main__':
    main()
