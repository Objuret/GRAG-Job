import numpy as np
from facet_ordering_programs import transform, catalog
from facet_program_catalog import build
from artefact.facet_construction_fast import run_program
from artefact.facet_graph_input import GraphInput
from test_facet_construction_program import fixture


def test_baseline_transform_preserves_exact_order_and_signal():
    f = dict(path='groups', query='mean', matching='maximum', join='intersection', admission='area_first')
    args = fixture()
    a = run_program(build(f), *args)
    b = run_program(transform(f), *args)
    assert np.array_equal(a['order'], b['order'])
    assert np.array_equal(a['states']['graph'].values, b['states']['graph'].values)


def test_catalog_executes_and_early_reduction_stays_collapsed():
    args = fixture()
    changed = set()
    for p in catalog():
        r = run_program(p, *args)
        if p['ordering']['reduction'] != 'after_graph':
            assert r['states']['graph'].values.shape[1] == 1
        changed.add(r['states']['graph'].values.tobytes())
    assert len(changed) > 10


def test_reduction_and_gate_positions_are_not_commuting_aliases():
    args = list(fixture())
    g = args[0]
    args[0] = GraphInput(g.chunk_ids, g.edge_tag, g.edge_chunk,
                         np.ones_like(g.facet_readings), g.groups,
                         g.adjacency_pairs, g.product_groups)
    args[1]['query_tag_cosines'] = np.array([[1., 0.], [0., 1.]])
    f = dict(path='groups', query='mean', matching='tag_only', join='intersection')
    results = [run_program(transform(f, reduction=where), *args)['states']['graph'].values
               for where in ('before_edges', 'before_graph', 'after_graph')]
    assert not np.allclose(results[0], results[1])
    assert not np.allclose(results[1], results[2].mean(axis=1, keepdims=True))
    gated = run_program(transform(f, rounds=2, description_gate='each_step'), *args)
    final = run_program(transform(f, rounds=2, description_gate='after_walk'), *args)
    assert not np.allclose(gated['states']['graph'].values, final['states']['graph'].values)
