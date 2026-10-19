"""The facet layer's question-independent values, premade in the graph so the arm can ask for them
per question (his 2026-08-11 "everything that doesnt need to be ran in querytime should be
premade!"; 2026-10-07 "it MUST be asked of the DB").

Over the eligible pool edges (a HAS_TAG edge of the run whose tag is not a product's name, into a
chunk of the pool), as `artefact_v4` reads them:
    w_pos           on each eligible edge: its place in each of the five facets' rankings
                    (`v4_walk.positions`: the average rank over the number of edges)
    place_middle    on the FacetLayer node: per ranking facet the middle place
    place_spread    on the FacetLayer node: per ranking facet the spread of the places (the median
                    distance from the middle times 1.4826)
No model call.

    write    computes the values from the graph's edges and sets them (facet_floors, which an
             earlier version set on the node and nothing reads, is taken off)
    verify   counts the edges that carry w_pos and shows the node's values
    remove   takes them off

    NEO4J_DATABASE=herb-eval-volmax .venv/Scripts/python.exe test/graph/build_edge_places.py write
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / 'prod', ROOT / 'test'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from artefact import graph_layer as GL  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from arms.artefact_v4 import EDGE_CYPHER, LAYER_CYPHER, PRODUCT_CYPHER, RUN_ID  # noqa: E402
from graph.db import _driver  # noqa: E402

DATABASE = os.environ.get('NEO4J_DATABASE', 'herb-eval-volmax')
BATCH = 2000


def placed(endpoints, values, product_names):
    """The eligible edges (a tag that is not a product's name, case left aside) as (tag, chunk id),
    their places over those edges, and the node's two values. values: per edge its five facet
    values, topic first."""
    folded = {str(name).lower() for name in product_names}
    eligible = np.array([str(tag).lower() not in folded for tag, _ in endpoints], dtype=bool)
    raw = np.asarray(values, dtype=np.float64)[eligible]
    pos = WK.positions(raw)
    place = pos[:, 1:]
    middle = np.median(place, axis=0)
    spread = WK.MAD_TO_SPREAD * np.median(np.abs(place - middle), axis=0)
    kept = [e for e, ok in zip(endpoints, eligible) if ok]
    return kept, pos, {'place_middle': [float(x) for x in middle],
                       'place_spread': [float(x) for x in spread]}


def places(session):
    """The graph's edges, checked whole against the FacetLayer node (`graph_layer.read`), placed."""
    edges = [dict(r) for r in session.run(EDGE_CYPHER, run=RUN_ID)]
    node = [dict(r) for r in session.run(LAYER_CYPHER, run=RUN_ID)]
    layer = GL.read(edges, node)
    return placed(layer.endpoints, layer.values, [r['name'] for r in session.run(PRODUCT_CYPHER)])


def write(session):
    endpoints, pos, node = places(session)
    rows = [{'tag': t, 'chunk': c, 'pos': [float(x) for x in p]} for (t, c), p in zip(endpoints, pos)]
    for start in range(0, len(rows), BATCH):
        session.run('UNWIND $rows AS row MATCH (c:Chunk {chunk_id: row.chunk})-[r:HAS_TAG]->'
                    '(t:Tag {name: row.tag}) WHERE r.run_id = $run SET r.w_pos = row.pos',
                    rows=rows[start:start + BATCH], run=RUN_ID)
    session.run('MATCH (l:FacetLayer {run_id: $run}) SET l.place_middle = $middle, '
                'l.place_spread = $spread REMOVE l.facet_floors', run=RUN_ID,
                middle=node['place_middle'], spread=node['place_spread'])
    print(f'write: w_pos on {len(rows)} eligible edges; place_middle and place_spread on the '
          f'FacetLayer node of {DATABASE}')
    verify(session)


def verify(session):
    n = session.run('MATCH ()-[r:HAS_TAG]->() WHERE r.run_id = $run AND r.w_pos IS NOT NULL '
                    'RETURN count(r) AS n', run=RUN_ID).single()['n']
    node = session.run('MATCH (l:FacetLayer {run_id: $run}) RETURN l.place_middle AS middle, '
                       'l.place_spread AS spread, l.facet_floors IS NOT NULL AS old_floors',
                       run=RUN_ID).single()
    print(f'verify: {n} edges carry w_pos; middle {node["middle"]}; spread {node["spread"]}; '
          f'the old facet_floors still on the node: {node["old_floors"]}')


def remove(session):
    n = session.run('MATCH ()-[r:HAS_TAG]->() WHERE r.w_pos IS NOT NULL REMOVE r.w_pos '
                    'RETURN count(r) AS n').single()['n']
    session.run('MATCH (l:FacetLayer) REMOVE l.facet_floors, l.place_middle, l.place_spread')
    print(f'remove: w_pos taken off {n} edges, and the node\'s values off the FacetLayer node')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('step', choices=('write', 'verify', 'remove'))
    args = ap.parse_args(argv)
    driver = _driver()
    try:
        with driver.session(database=DATABASE) as session:
            {'write': write, 'verify': verify, 'remove': remove}[args.step](session)
    finally:
        driver.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
