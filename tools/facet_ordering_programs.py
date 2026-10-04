"""Structural programs varying reduction placement and traversal dependencies.

Finite depths are explicit hypotheses, not a search stopping rule or candidate
limit. This module does not alter any sealed engine or earlier catalog.
"""
from itertools import product
from facet_program_catalog import build


def transform(factors, *, reduction='after_graph', description_gate='each_step',
              rounds=1, feedback='latest', graph_route='product_channel'):
    if reduction not in ('before_edges', 'before_graph', 'after_graph'):
        raise ValueError('Unknown reduction placement')
    if description_gate not in ('each_step', 'after_walk', 'off'):
        raise ValueError('Unknown description gate')
    if rounds not in (1, 2, 4) or feedback not in ('latest', 'retain_seed'):
        raise ValueError('Unknown walk hypothesis')
    base = build(factors)
    # These contexts retain separate facets and one group relation so that each
    # change has a precise interpretation; route projection remains swappable.
    if base['factors']['facet_binding'] != 'separate' or base['factors']['path'] != 'groups':
        raise ValueError('Ordering contexts require separate facets and group paths')
    if base['factors']['recruitment'] not in ('joint', 'facets'):
        raise ValueError('Early query reduction cannot retain query recruitment')
    nodes = []
    method = base['factors']['query']

    def add(name, op, inputs, **params):
        nodes.append(dict(id=name, op=op, inputs=list(inputs), params=params))
        return name

    for original in base['nodes']:
        node = {**original, 'inputs': list(original['inputs']), 'params': dict(original['params'])}
        if node['id'] == 'direct' and reduction == 'before_edges':
            node['inputs'][0] = add('query_before_edges', 'reduce', node['inputs'], axis='query', method=method)
        if node['id'] == 'graph':
            seed = node['inputs'][0]
            if reduction == 'before_graph':
                seed = add('query_before_graph', 'reduce', [seed], axis='query', method=method)
                # Direct/graph joining must compare evidence at the same level.
            gate = 'query_description'
            if reduction != 'after_graph':
                gate = add('reduced_query_gate', 'reduce', [gate], axis='query', method=method)
            previous = seed
            for step in range(1, rounds + 1):
                args = [previous, gate] if description_gate == 'each_step' else [previous]
                previous = add('walk_' + str(step), 'propagate', args, **node['params'])
                if feedback == 'retain_seed' and step < rounds:
                    previous = add('seed_feedback_' + str(step), 'maximum', [seed, previous])
            if description_gate == 'after_walk':
                previous = add('walk_description_gate', 'multiply', [previous, gate])
            add('graph', 'maximum', [previous])
            continue
        if reduction == 'before_graph' and node['id'] in ('joined', 'direct_gate'):
            node['inputs'] = ['query_before_graph' if x == 'direct' else x for x in node['inputs']]
        # Existing final query reductions become identity reductions on one row.
        # Keeping their names retains stage inspection and the original interface.
        nodes.append(node)
    return {**base, 'nodes': nodes, 'graph_route': graph_route,
            'ordering': dict(reduction=reduction, description_gate=description_gate,
                             rounds=rounds, feedback=feedback)}


def catalog():
    programs = []
    for matching, recruitment, route, reduction, gate, rounds, feedback in product(
        ('product', 'maximum'), ('joint', 'facets'),
        ('product_channel', 'employee_intersection'),
        ('before_edges', 'before_graph', 'after_graph'),
        ('each_step', 'after_walk', 'off'), (1, 2, 4), ('latest', 'retain_seed')):
        if rounds == 1 and feedback == 'retain_seed':
            continue  # No second iteration at which feedback can act.
        p = transform(dict(matching=matching, recruitment=recruitment, query='mean',
                           path='groups', join='intersection', admission='area_first'),
                      reduction=reduction, description_gate=gate, rounds=rounds,
                      feedback=feedback, graph_route=route)
        p['id'] = 'ordering_' + str(len(programs)).zfill(4)
        programs.append(p)
    return programs
