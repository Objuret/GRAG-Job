"""Exact structural landings over a versioned graph capture, without model calls.

One lexical name may bind several nodes. Their reachable chunks are alternatives
and are unioned; distinct names are intersected as in the recorded area contract.
This does not interpret natural-language Boolean operators or settle scheduling.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class StructuralIndex:
    nodes: dict
    by_name: dict
    eligible: frozenset
    provenance: dict


def structural_index(payload, *, graph_sha256, eligible_chunk_ids):
    """Validate the capture at the arm boundary; retain nodes with no routes."""
    if payload.get('schema_version') != 1 or payload.get('graph_sha256') != graph_sha256:
        raise ValueError('Structural capture does not match the pinned graph')
    eligible = frozenset(eligible_chunk_ids)
    recorded = payload.get('eligible_chunk_ids', [])
    if len(recorded) != len(set(recorded)) or frozenset(recorded) != eligible:
        raise ValueError('Structural capture has a different eligible chunk universe')
    nodes, by_name = {}, {}
    for row in payload['nodes']:
        key = (row['label'], row['node_id'])
        if not all(isinstance(v,str) and v for v in key) or key in nodes:
            raise ValueError('Structural node identities must be unique nonempty strings')
        routes = {route:frozenset(ids) for route,ids in row['routes'].items()}
        if any(not reached <= eligible for reached in routes.values()):
            raise ValueError('Structural route leaves the eligible chunk universe')
        reached = frozenset().union(*routes.values())
        names = []
        for alias in row['names']:
            name, kind = alias['name'], alias['kind']
            if not isinstance(name,str) or not name.strip() or not isinstance(kind,str) or not kind:
                raise ValueError('Structural names and kinds must be nonempty strings')
            name = name.strip()
            names.append((name,kind))
            by_name.setdefault(name.casefold(),set()).add(key)
        nodes[key] = {'names':tuple(sorted(set(names))), 'routes':routes,
                      'chunks':reached, 'route_counts':row.get('route_counts',{})}
    return StructuralIndex(nodes=nodes,
        by_name={name:tuple(sorted(keys)) for name,keys in sorted(by_name.items())},
        eligible=eligible, provenance={'graph_sha256':graph_sha256,
            'database':payload.get('database'), 'capture':payload.get('provenance',{}),
            'created_utc':payload.get('created_utc'), 'validation':payload.get('validation',{}),
            'historical_limit':'Later structural capture; eligible IDs and Product/Channel memberships checked against original snapshot, not historical Employee edges.'})


def load_structural_index(path, *, sha256, graph_sha256, eligible_chunk_ids):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError('Structural capture hash mismatch')
    result = structural_index(json.loads(data), graph_sha256=graph_sha256,
                              eligible_chunk_ids=eligible_chunk_ids)
    result.provenance['structural_capture_sha256'] = sha256
    return result


def resolve_structural_area(text, index):
    """Return an optional nomination area and explicit, inspectable match state.

    Unknown words do not become nearest-name matches. A short alias contained in
    a longer name occurrence is suppressed, but a separate occurrence survives.
    Empty/nonexistent areas yield no extra nomination stream; global access stays
    available. This is abstention from area nomination, never an evidence veto.
    """
    if not isinstance(text,str):
        raise ValueError('Structural landing expects question text')
    # Match with the same casefold equivalence used to group node aliases.
    # Keep original offsets even when a character expands (for example ß -> ss).
    folded_parts, origins = [], []
    for position,char in enumerate(text):
        folded = char.casefold()
        folded_parts.append(folded)
        origins.extend([position]*len(folded))
    folded_text = ''.join(folded_parts)
    occurrences = []
    for name in index.by_name:
        pattern = r'(?<!\w)' + re.escape(name) + r'(?!\w)'
        for match in re.finditer(pattern,folded_text):
            first,last = match.span()
            # Never match only part of an expanded original character.
            if first and origins[first-1]==origins[first]:
                continue
            if last<len(origins) and origins[last-1]==origins[last]:
                continue
            occurrences.append((origins[first],origins[last-1]+1,name))
    kept = [(a,b,name) for a,b,name in occurrences
            if not any(c<=a and b<=d and (c<a or b<d) for c,d,_ in occurrences)]
    spans = {}
    for a,b,name in kept:
        spans.setdefault(name,set()).add((a,b))
    landings = []
    reached_sets = []
    for name,positions in sorted(spans.items()):
        keys = index.by_name[name]
        reached = frozenset().union(*(index.nodes[key]['chunks'] for key in keys))
        reached_sets.append(reached)
        bindings = []
        for key in keys:
            node = index.nodes[key]
            bindings.append({'label':key[0],'node_id':key[1],
                'routes':{route:sorted(ids) for route,ids in sorted(node['routes'].items())},
                'reachable_chunks':len(node['chunks']),
                'has_enabled_route':bool(node['routes'])})
        landings.append({'name':name,'spans':[list(pair) for pair in sorted(positions)],
                         'node_bindings':bindings,'multiple_nodes':len(keys)>1,
                         'chunk_ids':sorted(reached)})
    combined = frozenset.intersection(*reached_sets) if reached_sets else None
    if not landings:
        status = 'no_landing'
    elif any(not reached for reached in reached_sets):
        status = 'unreachable_landing'
    elif not combined:
        status = 'empty_intersection'
    else:
        status = 'resolved_multiple_nodes' if any(l['multiple_nodes'] for l in landings) else 'resolved'
    area = combined if combined else None
    return area, {
        'status':status,'landings':landings,
        'combined_chunk_ids':None if combined is None else sorted(combined),
        'nomination_area_used':area is not None,
        'match_policy':'Exact whole-name under Unicode casefold; original spans retained; contained occurrences suppressed; no fuzzy guesses.',
        'combination_policy':'Union nodes behind each lexical name; intersect distinct names.',
        'outside_area':'Global nomination remains available; empty intersections are not a corpus exclusion.',
        'limitations':'No interpretation of OR/comparisons; distinct names with disjoint areas retain global fallback.',
        'snapshot':index.provenance,
    }
