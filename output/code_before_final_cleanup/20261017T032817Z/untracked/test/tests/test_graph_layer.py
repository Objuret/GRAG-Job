"""The facet layer as the graph carries it: `artefact.graph_layer.read` on toy rows, and the
writer's comparison of a graph against a layer. No database, no file, no model call."""
import numpy as np
import pytest

from artefact import graph_layer as GL
from graph import write_facet_layer as WFL


def layer(edges=None, **node):
    """Edge rows as the arm's read returns them, in no order, and the node written with them."""
    edges = edges or [('beta', 'k1', [.2, 1., 2., 3., 4.]), ('alpha', 'k1', [.1, -1., 0., 1., 2.]),
                      ('alpha', 'k0', [.3, .5, .5, .5, .5])]
    rows = [{'tag': tag, 'chunkId': chunk, 'facets': list(GL.FACETS), 'values': values}
            for tag, chunk, values in edges]
    held = {'run_id': 'r', 'name': 'a layer', 'facets': list(GL.FACETS),
            'equal_gap_facets': list(GL.ADJUST), 'equal_gap': [1., 2., 3., 4.],
            'equal_gap_column': 'gap (any)', 'pooled_flip_gap': 1.5, 'refits': 24,
            'edges': len(rows),
            'rows_sha256': GL.digest((chunk, tag, values) for tag, chunk, values in edges)}
    held.update(node)
    return rows, [{'properties': held}]


def test_the_facets_are_topic_and_the_four_the_arm_adjusts_by():
    assert GL.FACETS == ('topic', 'temporal', 'why', 'activity', 'concreteness')
    assert GL.ADJUST == GL.FACETS[1:] == WFL.FACETS[1:]
    assert WFL.FACETS == GL.FACETS


def test_read_lists_the_edges_by_chunk_then_tag_whatever_order_they_come_in():
    rows, node = layer()
    got = GL.read(rows, node)
    assert got.endpoints == (('alpha', 'k0'), ('alpha', 'k1'), ('beta', 'k1'))
    assert got.values.tolist() == [[.3, .5, .5, .5, .5], [.1, -1., 0., 1., 2.],
                                   [.2, 1., 2., 3., 4.]]
    assert got.gaps == (1., 2., 3., 4.) and got.pooled_gap == 1.5
    assert got.node['name'] == 'a layer'
    again = GL.read(rows[::-1], node)
    assert again.endpoints == got.endpoints and again.values.tolist() == got.values.tolist()
    # the values cannot be written to
    assert not got.values.flags.writeable
    with pytest.raises(ValueError):
        got.values.setflags(write=True)


def test_the_digest_does_not_depend_on_the_order_of_the_rows_and_does_on_every_value():
    rows = [('k1', 'beta', [.2, 1.]), ('k0', 'alpha', [.3, .5])]
    assert GL.digest(rows) == GL.digest(rows[::-1])
    assert GL.digest(rows) != GL.digest([('k1', 'beta', [.2, 1.]), ('k0', 'alpha', [.3, .6])])
    assert GL.digest(rows) != GL.digest([('k1', 'beta', [.2, 1.]), ('k0', 'alphb', [.3, .5])])
    assert GL.digest(iter(rows)) == GL.digest(rows)


@pytest.mark.parametrize('change, message', [
    (lambda rows, node: node.clear(), 'Expected one FacetLayer node, found 0'),
    (lambda rows, node: node.append(node[0]), 'Expected one FacetLayer node, found 2'),
    (lambda rows, node: node[0]['properties'].update(facets=['topic']),
     'names other facets'),
    (lambda rows, node: node[0]['properties'].update(equal_gap_facets=list(GL.ADJUST[::-1])),
     'gives its gaps for other facets'),
    (lambda rows, node: rows.clear(), 'holds no pool edge'),
    (lambda rows, node: rows[0].update(facets=['topic', 'entities', 'activity', 'temporal',
                                               'evidence']),
     '1 of 3 pool edges do not carry the facet layer'),
    (lambda rows, node: rows[1].update(facets=None), '1 of 3 pool edges do not carry'),
    (lambda rows, node: rows.append(dict(rows[0])), 'Two edges join one tag and one chunk'),
    (lambda rows, node: rows[0].update(values=[.2, 1., 2., 3.]), 'five facet values per edge'),
    (lambda rows, node: rows[0].update(values=[.2, 1., 2., 3., float('nan')]), 'not finite'),
    (lambda rows, node: node[0]['properties'].update(edges=4), 'records 4 edges, the pool holds 3'),
    (lambda rows, node: rows[0].update(values=[.2, 1., 2., 3., 4.5]),
     'not the ones the FacetLayer node was written with'),
    (lambda rows, node: node[0]['properties'].update(equal_gap=[1., 2., 3.]),
     'one positive gap per facet'),
    (lambda rows, node: node[0]['properties'].update(equal_gap=[1., 0., 3., 4.]),
     'one positive gap per facet'),
    (lambda rows, node: node[0]['properties'].update(pooled_flip_gap=None),
     'positive pooled flip gap'),
])
def test_read_refuses_a_graph_that_does_not_carry_the_layer_whole(change, message):
    rows, node = layer()
    change(rows, node)
    with pytest.raises(ValueError, match=message):
        GL.read(rows, node)


def test_the_writer_counts_how_the_graph_stands_against_the_layer():
    rows = [{'chunk_id': 'k0', 'tag': 'alpha', 'values': [.3, .5, .5, .5, .5]},
            {'chunk_id': 'k1', 'tag': 'alpha', 'values': [.1, -1., 0., 1., 2.]},
            {'chunk_id': 'k1', 'tag': 'beta', 'values': [.2, 1., 2., 3., 4.]}]
    old = ['topic', 'entities', 'activity', 'temporal', 'evidence']
    edges = {('k0', 'alpha'): (list(GL.FACETS), [.3, .5, .5, .5, .5], True),   # carries it
             ('k1', 'alpha'): (old, [.1, .1, .1, .1, .1], True),               # old values
             ('k1', 'beta'): (list(GL.FACETS), [.2, 1., 2., 3., 4.0001], True),  # another value
             ('m0', 'beta'): (old, [.1, .1, .1, .1, .1], False)}               # outside the pool
    assert WFL.compare(rows, edges) == {
        'layer_rows': 3, 'distinct_rows': 3, 'graph_edges': 4, 'graph_edges_in_the_pool': 3,
        'rows_with_no_edge': 0, 'rows_the_graph_already_carries': 1,
        'graph_edges_outside_the_layer': 1, 'of_them_in_the_pool': 0,
        'of_them_carrying_the_layer_facets': 0}
    gone = {key: value for key, value in edges.items() if key != ('k1', 'beta')}
    assert WFL.compare(rows, gone)['rows_with_no_edge'] == 1
    assert WFL.compare(rows + [dict(rows[0])], edges)['distinct_rows'] == 3
