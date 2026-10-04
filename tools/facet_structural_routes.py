"""Shared-entity chunk relations projected from the pinned structural graph.

This is retrieval over graph relationships, not query matching to private names.
Each group implements a chunk -> shared entity -> chunk path; projected groups
are symmetric hypotheses. Directed traversal is not claimed by this projection.
"""
from collections import Counter
import json
import hashlib
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'test'), str(ROOT/'tools'), str(ROOT/'prod')]
from artefact.facet_graph_input import GraphInput

SNAPSHOT = ROOT/'output/research/2026-09-22-structural-landings/structural_snapshot.json'
EXPECTED_SHA = '9c9e9ff8415002cdc6203ecfdc29ef6a933d9eaf8859e3d1cf8d6678037f33ce'


def unique_groups(groups):
    """Duplicate membership sets cannot create extra independent evidence."""
    return tuple(sorted({tuple(sorted(set(g))) for g in groups if len(set(g)) > 1}))


def projections(graph, payload):
    at = {c: i for i,c in enumerate(graph.chunk_ids)}
    if set(payload['eligible_chunk_ids']) != set(at):
        raise ValueError('Structural graph population mismatch')
    groups = {name: [] for name in ('channel','product','employee_channel','employee_product',
                                  'employee_union','employee_intersection')}
    for row in payload['nodes']:
        routes = {k: set(v) for k,v in row['routes'].items()}
        if any(not s <= set(at) for s in routes.values()):
            raise ValueError('Route outside graph')
        selected = {}
        if row['label'] == 'Channel':
            selected['channel'] = routes.get('channel_chunk', set())
        elif row['label'] == 'Product':
            selected['product'] = routes.get('product_chunk', set())
        elif row['label'] == 'Employee':
            channel = routes.get('employee_channel', set()); product = routes.get('employee_product', set())
            selected.update(employee_channel=channel, employee_product=product,
                            employee_union=channel|product, employee_intersection=channel&product)
        for name, ids in selected.items():
            groups[name].append(tuple(at[c] for c in ids))
    groups = {k: unique_groups(v) for k,v in groups.items()}
    groups['product_channel'] = unique_groups(g for collection in graph.groups.values() for g in collection)
    groups['product_channel_plus_employee'] = unique_groups(groups['product_channel'] + groups['employee_union'])
    result = {}
    for name, members in groups.items():
        result[name] = GraphInput(graph.chunk_ids, graph.edge_tag, graph.edge_chunk,
                                 graph.facet_readings, {name: members}, graph.adjacency_pairs, graph.product_groups)
    return result


def load_projections(graph):
    data = SNAPSHOT.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA:
        raise ValueError('Structural snapshot changed')
    return projections(graph, json.loads(data))


def inventory(projected):
    result = {}
    for name, graph in projected.items():
        groups = next(iter(graph.groups.values()))
        reached = set(c for g in groups for c in g)
        result[name] = {'distinct_groups':len(groups), 'chunks_with_a_route':len(reached),
                        'memberships':sum(map(len,groups)), 'largest_group':max(map(len,groups),default=0)}
    return result


if __name__ == '__main__':
    from facet_program_lab import ProgramLab
    print(json.dumps(inventory(load_projections(ProgramLab().graph))))
