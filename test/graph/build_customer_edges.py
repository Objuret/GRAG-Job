"""The graph's customers tied to the chunks that name them (his 2026-10-19 "well build this, go on";
the same shape as the person edges, a node to a chunk with nothing on the edge).

One edge `(:Customer)-[:chunk]->(:Chunk)` for every pool chunk whose records carry the customer's
id (`CUST-0019`) as a whole word anywhere in their fields. The pool is the chunks with a product
edge and the chunks of employee.json and customers_data.json (`record_text.METADATA_TYPES`), as
the arm's. The records are read from the dataset through each chunk's pointer, by the arm's own
reader (`artefact_v4._pointed_records`). Ids only: in this dataset a customer's name never stands
in a record except where an employee carries the same name, so a name would tie the wrong node.
No model call.

    write    computes the pairs, prints them per record kind, and writes the edges (MERGE)
    verify   counts of the edges
    remove   takes every customer-to-chunk edge out

    NEO4J_DATABASE=herb-eval-volmax .venv/Scripts/python.exe test/graph/build_customer_edges.py write
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / 'prod', ROOT / 'test'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from arms.artefact_v4 import _pointed_records  # noqa: E402
from graph.db import _driver  # noqa: E402
from harness.record_text import METADATA_TYPES  # noqa: E402

DATABASE = os.environ.get('NEO4J_DATABASE', 'herb-eval-volmax')
BATCH = 2000

POOL_CYPHER = f'''
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE (c)-[:product]->() OR c.metadata_section IN {json.dumps(sorted(METADATA_TYPES))}
RETURN c.chunk_id AS chunk, c.kind AS kind, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256
'''


def id_pattern(ids):
    """A match of any of the ids as a whole word (no letter or digit on either side)."""
    return re.compile(r'(?<![A-Za-z0-9])(' + '|'.join(map(re.escape, sorted(ids))) + r')(?![A-Za-z0-9])')


def customers_in(record, pattern):
    """The customer ids a record carries as whole words, anywhere in its fields."""
    return set(pattern.findall(json.dumps(record, ensure_ascii=False)))


def pairs(session):
    """(customer id, chunk id) pairs over the pool and the count per record kind."""
    pattern = id_pattern(r['id'] for r in session.run('MATCH (c:Customer) RETURN c.id AS id'))
    docs, out, found = {}, set(), Counter()
    for row in session.run(POOL_CYPHER).data():
        kind = json.loads(row['locator']).get('metadata') or row['kind']
        for record in _pointed_records(dict(row, chunkId=row['chunk']), docs):
            for cid in customers_in(record, pattern):
                found[kind] += 1
                out.add((cid, row['chunk']))
    return sorted(out), found


def write(session):
    found_pairs, found = pairs(session)
    print('records naming a customer by id, by record kind:', dict(sorted(found.items())))
    for start in range(0, len(found_pairs), BATCH):
        batch = [{'id': c, 'chunk': k} for c, k in found_pairs[start:start + BATCH]]
        session.run('UNWIND $rows AS row MATCH (cu:Customer {id: row.id}) '
                    'MATCH (c:Chunk {chunk_id: row.chunk}) MERGE (cu)-[:chunk]->(c)', rows=batch)
    print(f'write: {len(found_pairs)} customer-chunk pairs merged into {DATABASE}')
    verify(session)


def verify(session):
    r = session.run('MATCH (cu:Customer)-[:chunk]->(c:Chunk) RETURN count(*) AS edges, '
                    'count(DISTINCT cu) AS customers, count(DISTINCT c) AS chunks').single()
    print(f"verify: {r['edges']} edges (:Customer)-[:chunk]->(:Chunk), {r['customers']} customers, "
          f"{r['chunks']} chunks")


def remove(session):
    n = session.run('MATCH (:Customer)-[r:chunk]->(:Chunk) DELETE r RETURN count(r) AS n').single()['n']
    print(f'remove: {n} customer-chunk edges deleted')


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
