"""Increase one query facet, first within its ordinal slot, then across slots.

Fixed sharing_1 first reading: market research report/activity .35 -> .50 or .70.
No inference calls. Compare inside each frozen assembly, never across assemblies
as a retrieval-quality claim. Values and comparisons selected before outcomes.
"""
import copy
from pathlib import Path
import json
import numpy as np
import facet_concept_replay as replay

ROOT = replay.ROOT
BASE = ROOT / 'output/research/2026-09-21-facet-validity'
CONCEPT = ROOT / 'output/research/2026-09-22-joint-streams/concept'
OUT = CONCEPT / 'increase_control'
CAPTURE = BASE / 'route_capture/query_captures.json'


def main():
    if (OUT / 'comparison.json').exists():
        raise RuntimeError('Completed increase control exists')
    OUT.mkdir(parents=True, exist_ok=True)
    raw = replay.read(CAPTURE)
    cap = next(c for c in raw['captures'] if c['generation_id'] == 'sharing_1')
    first = cap['readings'][0]
    target = next(v for v in first['values'] if v['t'] == 'market research report')
    assert target['facets']['activity'] == .35
    facets = raw['facets']
    order = lambda f: sorted(facets, key=lambda k: (-f[k], facets.index(k)))
    contract = {'protocol': __doc__, 'query_tag': 'market research report', 'facet': 'activity',
                'original_value': .35, 'increases': [.50, .70],
                'capture_sha256': replay.sha(CAPTURE), 'script_sha256': replay.sha(Path(__file__)),
                'runner_sha256': replay.sha(Path(replay.__file__)),
                'expectation': 'Concept unchanged when all facet priorities preserved; crossing priorities may change it. Weighted can change under relative coefficient increases even without an order crossing. Neither predicts usefulness.'}
    replay.write(OUT / 'control_contract.json', contract)
    original_read = replay.read
    original = original_read(CONCEPT / 'sharing_1_score_0_concept_file.json')
    graph = original_read(BASE / 'route_snapshot/graph.json')
    arrays = np.load(BASE / 'route_snapshot/arrays.npz', allow_pickle=False)
    from artefact.facet_route_rank import ForumConfig, replay_forum
    query = next(q for q in graph['queries'] if q['id'] == 'sharing_1')
    parts = [graph['query_tags'].index(t) for t in cap['clean_tags']]
    di, defaults = query['description_index'], graph['operator_defaults']
    config = ForumConfig(mode='weighted', tag_band=query['tag_band'], description_band=query['desc_band'],
                         topic_band=defaults['topic_band'], facet_band=defaults['facet_band'], r_band=defaults['r_band'],
                         betas=tuple(defaults['betas'][f] for f in facets[1:]), topic_key=defaults['topic_key'],
                         description_place=defaults['desc_place'], adjust=defaults['adjust'])

    def weighted(reading):
        values = {v['t']: v['facets'] for v in reading['values']}
        qf = np.array([[values[t][f] for f in facets] for t in cap['clean_tags']])
        result = replay_forum(edge_tag=arrays['edge_tag'], edge_chunk=arrays['edge_chunk'],
            edge_facets=arrays['edge_facets'], chunk_ids=graph['chunk_ids'],
            tag_cos=arrays['query_tag_graph_cos_forum_precision'][parts],
            part_chunk_cos=arrays['query_tag_chunk_cos'][parts], description_chunk_cos=arrays['description_chunk_cos'][di],
            centrality=arrays['centrality'][di, parts], query_facets=qf,
            facet_orders=[tuple(order(values[t])) for t in cap['clean_tags']], config=config,
            candidate_tag=arrays['candidate_tag'], in_scope=None)
        return result, [graph['chunk_ids'][i] for i in result.chunk_order]

    wbase, wbase_order = weighted(first)
    saved_weighted = original_read(BASE / 'route_replay/sharing_1_score_0_weighted_real.json')
    assert wbase_order == saved_weighted['chunk_order']
    results = []
    for value in (.50, .70):
        adapted = copy.deepcopy(raw)
        c = copy.deepcopy(cap)
        c['readings'] = [copy.deepcopy(first)]
        row = next(v for v in c['readings'][0]['values'] if v['t'] == 'market research report')
        row['facets']['activity'] = value
        adapted['captures'] = [c]
        dest = OUT / ('activity_' + str(value).replace('.', '_'))
        dest.mkdir(exist_ok=True)
        replay.write(dest / 'adapted_capture.json', adapted)
        replay.read = lambda path: adapted if Path(path) == CAPTURE else original_read(path)
        replay.OUT = dest
        replay.main()
        replay.read = original_read
        changed = original_read(dest / 'sharing_1_score_0_concept_file.json')
        wrun, worder = weighted(c['readings'][0])
        common = np.isfinite(wbase.adjusted_topic) & np.isfinite(wrun.adjusted_topic)
        delta = np.abs(wbase.adjusted_topic[common] - wrun.adjusted_topic[common])
        result = {'activity_value': value, 'old_order': order(target['facets']), 'new_order': order(row['facets']),
                  'concept_changed_positions': sum(a != b for a, b in zip(original['chunk_order'], changed['chunk_order'])),
                  'weighted_changed_positions': sum(a != b for a, b in zip(wbase_order, worder)),
                  'weighted_routes_adjustment_changed_over_1e_12': int(np.count_nonzero(delta > 1e-12)),
                  'weighted_max_adjustment_difference': float(delta.max()),
                  'concept_result_sha256': replay.sha(dest / 'sharing_1_score_0_concept_file.json')}
        if value == .50:
            assert result['old_order'] == result['new_order'] and result['concept_changed_positions'] == 0
        results.append(result)
        replay.write(dest / 'weighted_order.json', {'chunk_order': worder, 'query_facets': c['readings'][0]['values']})
        print(json.dumps(result), flush=True)
    replay.write(OUT / 'comparison.json', {'contract_sha256': replay.sha(OUT / 'control_contract.json'),
                 'runs': results, 'limits': 'One fixed input and two specified increases; functional sensitivity, not utility calibration or corpus-wide quality.'})


if __name__ == '__main__':
    main()
