"""Explain existing failed candidate paths, without changing or tuning the rule."""
import json
import numpy as np
from facet_joint_candidate_replay import NEW, OLD, OUT, ROOT, read, write
from artefact.facet_joint_candidate import FACETS, freeze_reference


def main():
    graph = read(OLD / 'route_snapshot/graph.json')
    arrays = dict(np.load(OLD / 'route_snapshot/arrays.npz'))
    meta = read(NEW / 'query_snapshot/queries.json')
    qa = dict(np.load(NEW / 'query_snapshot/arrays.npz'))
    captures = read(NEW / 'query_capture/query_captures.json')['captures']
    expectations = {x['question_id']: x for x in read(NEW / 'case_protocol.json')['expected_pair_preferences']}
    f = freeze_reference(arrays['edge_facets']).transform(arrays['edge_facets'])
    result = []
    for capture, query in zip(captures, meta['queries']):
        assert query['id'] == capture['generation_id']
        if capture['question_id'] not in {'revert_reason', 'processing_design'}:
            continue
        reading = capture['readings'][0]
        weights = {v['t']: v['facets'] for v in reading['values']}
        for role in ('preferred', 'comparison'):
            cid = expectations[capture['question_id']][role]
            ci = graph['chunk_ids'].index(cid)
            es = np.flatnonzero(arrays['edge_chunk'] == ci)
            routes = []
            for tag, qi in zip(query['tags'], query['query_tag_indices']):
                u = np.array([weights[tag][facet] for facet in FACETS])
                components = f[es] * u * np.array([1, .25, .25, .25, .25])
                m = np.maximum(qa['query_tag_graph_cos'][qi, arrays['edge_tag'][es]], 0)
                d = max(qa['query_tag_chunk_cos'][qi, ci], 0)
                q = max(qa['description_chunk_cos'][query['description_index'], ci], 0)
                scores = m * d * q * components.sum(axis=1)
                best = max(range(len(es)), key=lambda j: (scores[j], -int(es[j])))
                routes.append({'query_tag': tag, 'edge_id': graph['edge_ids'][es[best]],
                               'score': float(scores[best]), 'M': float(m[best]), 'D': float(d),
                               'Q': float(q), 'query_values': u.tolist(),
                               'components': components[best].tolist()})
            result.append({'question_id': capture['question_id'], 'role': role, 'chunk_id': cid,
                           'routes': sorted(routes, key=lambda r: -r['score'])})
    write(OUT / 'failed_pair_routes.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
