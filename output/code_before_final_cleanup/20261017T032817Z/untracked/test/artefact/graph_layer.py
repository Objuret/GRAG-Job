"""The facet layer as the graph carries it. No ranking formula, no file access.

Per HAS_TAG edge of the product-linked pool five values in FACETS order on `w_facets` (topic the
cosine of the tag vector and the chunk description vector, the four others the edge's mean over
the bootstrap refits of the round-1 head), and one FacetLayer node with the four per-facet
retrain gaps, the pooled flip gap and the sha256 of the rows it was written with.
`test/graph/write_facet_layer.py` writes it; an arm reads it here.

The edges come back in one order, sorted by (chunk id, tag): a graph's edges have none of their
own, and where two edges tie the listing order decides.
"""
from dataclasses import dataclass
import hashlib
import json

import numpy as np

FACETS = ('topic', 'temporal', 'why', 'activity', 'concreteness')
ADJUST = FACETS[1:]


@dataclass(frozen=True)
class GraphLayer:
    endpoints: tuple
    values: np.ndarray
    gaps: tuple
    pooled_gap: float
    node: dict


def digest(rows):
    """sha256 over (chunk id, tag, values) rows sorted by (chunk id, tag), one JSON line each."""
    found = hashlib.sha256()
    for chunk, tag, values in sorted(rows, key=lambda row: (row[0], row[1])):
        found.update(json.dumps([chunk, tag, list(values)], ensure_ascii=False,
                                separators=(',', ':')).encode('utf-8'))
        found.update(b'\n')
    return found.hexdigest()


def read(edge_rows, node_rows):
    """The pool's edges ((tag, chunk id), sorted by (chunk id, tag)) with their five values, and
    the node's gaps. edge_rows: dicts with tag, chunkId, facets, values; node_rows: dicts with
    properties. Refuses a graph whose edges or node do not carry this layer whole."""
    if len(node_rows) != 1:
        raise ValueError(f'Expected one FacetLayer node, found {len(node_rows)}; the layer is '
                         'written by test/graph/write_facet_layer.py')
    node = dict(node_rows[0]['properties'])
    if tuple(node.get('facets') or ()) != FACETS:
        raise ValueError('The FacetLayer node names other facets than ' + ', '.join(FACETS))
    if tuple(node.get('equal_gap_facets') or ()) != ADJUST:
        raise ValueError('The FacetLayer node gives its gaps for other facets than '
                         + ', '.join(ADJUST))
    rows = sorted(((row['chunkId'], row['tag'], row['facets'], row['values'])
                   for row in edge_rows), key=lambda row: (row[0], row[1]))
    if not rows:
        raise ValueError('The graph holds no pool edge')
    stale = sum(1 for row in rows if tuple(row[2] or ()) != FACETS)
    if stale:
        raise ValueError(f'{stale} of {len(rows)} pool edges do not carry the facet layer')
    endpoints = tuple((tag, chunk) for chunk, tag, _, _ in rows)
    if len(set(endpoints)) != len(endpoints):
        raise ValueError('Two edges join one tag and one chunk')
    if any(len(row[3] or ()) != len(FACETS) for row in rows):
        raise ValueError('Expected five facet values per edge')
    values = np.asarray([row[3] for row in rows], dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError('A facet value on an edge is not finite')
    if node.get('edges') != len(rows):
        raise ValueError(f'The FacetLayer node records {node.get("edges")} edges, the pool '
                         f'holds {len(rows)}')
    if node.get('rows_sha256') != digest((chunk, tag, held) for chunk, tag, _, held in rows):
        raise ValueError('The edges\' values are not the ones the FacetLayer node was written '
                         'with')
    gaps = tuple(float(gap) for gap in node.get('equal_gap') or ())
    if len(gaps) != len(ADJUST) or not all(np.isfinite(gap) and gap > 0 for gap in gaps):
        raise ValueError('Expected one positive gap per facet on the FacetLayer node')
    pooled = node.get('pooled_flip_gap')
    if not isinstance(pooled, (int, float)) or not np.isfinite(pooled) or pooled <= 0:
        raise ValueError('Expected a positive pooled flip gap on the FacetLayer node')
    # Immutable storage; a caller cannot switch WRITEABLE back on.
    values = np.frombuffer(values.tobytes(), dtype=values.dtype).reshape(values.shape)
    return GraphLayer(endpoints, values, gaps, float(pooled), node)
