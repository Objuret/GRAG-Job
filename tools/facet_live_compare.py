"""Rebase inspection fields onto an explicitly chosen graph-only construction."""
from facet_program_catalog import build


def compare(lab, payload):
    with lab.lock:
        target = lab.replay(payload)
        chosen = payload.get('comparison')
        if chosen is None:
            return target
        program = dict(chosen.get('program') or build(chosen.get('factors', {})))
        route = chosen.get('graph_route', 'product_channel')
        if route not in lab.route_graphs:
            raise ValueError('Unknown comparison graph relation projection')
        program['graph_route'] = route
        baseline = lab.replay({'case_id': payload['case_id'], 'program': program})
        previous = {row['chunk_id']: row for row in baseline['movements']}
        for row in target['movements']:
            old = previous[row['chunk_id']]
            row['old_position'] = old['new_position']
            row['old_delivered'] = old['new_delivered']
        credits = {row['source_id']: row['credited'] for row in baseline['gold_pointers']}
        for row in target['gold_pointers']:
            row['previously_credited'] = credits[row['source_id']]
        target['comparison_summary'] = baseline['summary']
        target['candidate_access']['reference'] = baseline['candidate_access']['new']
        target['comparison_program'] = program
        target['comparison_budget'] = baseline['budget']
        return target
