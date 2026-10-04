"""Compose query-grounded structural routes without corpus content or gold.

Landings contain only graph node identity, label and route-to-chunk pointers.
Matching query text to graph names is upstream; these operators do not parse OR
or infer which ambiguous entity was intended.
"""
from itertools import product


SCOPE_FACTORS = {
    'route_filter': ('all', 'channel', 'product'),
    'route_join': ('union', 'intersection'),
    'binding_join': ('union', 'intersection'),
    'name_join': ('intersection', 'union'),
    'unrouted': ('veto', 'abstain'),
    'empty': ('abstain', 'veto'),
}
SCOPE_DEFAULT = {k: v[0] for k, v in SCOPE_FACTORS.items()}


def combine(sets, method):
    if not sets:
        return frozenset()
    if method == 'union':
        return frozenset.union(*sets)
    return frozenset.intersection(*sets)


def form_scope(landings, eligible, raw=None):
    """None abstains from scope; an empty set explicitly vetoes scope access.

    Route filtering excludes a type of path, not a graph node with an inferred
    negative relevance. With abstention, unrouted bindings/names do not vote;
    with veto they supply an empty set to their join. All unresolved means no
    scope for abstention and an empty scope for veto. There is no top-k cutoff.
    """
    p = {**SCOPE_DEFAULT, **(raw or {})}
    if set(p) != set(SCOPE_FACTORS) or any(p[k] not in vs for k, vs in SCOPE_FACTORS.items()):
        raise ValueError('Unknown scope construction')
    eligible = frozenset(eligible)
    names = []; witnesses = []
    for li, landing in enumerate(landings):
        bindings = []
        for binding in landing['node_bindings']:
            routes = []
            for name, ids in binding['routes'].items():
                members = frozenset(ids)
                if not members <= eligible:
                    raise ValueError('Structural route leaves the graph')
                if p['route_filter'] != 'all' and p['route_filter'] not in name:
                    continue
                if members or p['unrouted'] == 'veto':
                    routes.append(members)
            reached = combine(routes, p['route_join'])
            if reached or p['unrouted'] == 'veto':
                bindings.append(reached)
            witnesses.append({'landing': li, 'label': binding['label'],
                              'node_id': binding['node_id'], 'selected_routes': len(routes),
                              'reachable_chunks': len(reached)})
        reached = combine(bindings, p['binding_join'])
        if reached or p['unrouted'] == 'veto':
            names.append(reached)
    if not landings:
        return None, {'status': 'no_landing', 'witnesses': witnesses, 'policy': p}
    area = combine(names, p['name_join'])
    status = 'resolved' if area else 'empty_abstain' if p['empty'] == 'abstain' else 'empty_veto'
    return (area if area or p['empty'] == 'veto' else None), {
        'status': status, 'landings': len(landings), 'active_names': len(names),
        'witnesses': witnesses, 'policy': p}


def scope_catalog():
    return [dict(zip(SCOPE_FACTORS, values)) for values in product(*SCOPE_FACTORS.values())]
