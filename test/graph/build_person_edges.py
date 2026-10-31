"""The graph's people tied to the chunks they are in (his 2026-10-17 "so, perhaps persons edges
shouldnt go to scope directly, but to chunks instead?" and "my point just is, stop adding shit
beside node -> chunk").

One edge `(:Employee)-[:chunk]->(:Chunk)` for every pool chunk whose records name the employee in
the fields the graph's own build spec reads people from (`build_corpus_graph.ARCHITECTURE` and
`REGISTRIES`): a Slack message's `userId`, a pull request's `user.login` and its reviews'
`user.login`, a document's `author`, a meeting transcript's `participants`, an employee record's
`employee_id`. The pool is the chunks with a product edge and the chunks of employee.json and
customers_data.json (`record_text.METADATA_TYPES`), as the arm's. The records are read from the
dataset through each chunk's pointer, by the arm's own reader (`artefact_v4._pointed_records`).
The edge carries nothing. No model call.

    backup   writes the person edges to a channel or product (`slack`, `meeting_transcripts`,
             `documents`) to a file, so they can be put back (`restore`)
    write    computes the pairs, prints what was found and what matched no employee, and writes
             the edges (MERGE, so a second run adds nothing)
    compare  the product's people and its channels apart as the arm reads them
             (`artefact_v4.product_persons`), from the old edges and from the new, product by
             product
    verify   counts of the new edges

    NEO4J_DATABASE=herb-eval-volmax .venv/Scripts/python.exe test/graph/build_person_edges.py write
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / 'prod', ROOT / 'test'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from arms.artefact_v4 import _pointed_records  # noqa: E402
from graph.db import _driver  # noqa: E402
from harness.record_text import METADATA_TYPES  # noqa: E402

DATABASE = os.environ.get('NEO4J_DATABASE', 'herb-eval-volmax')
OUT = ROOT / 'output' / 'graph_build' / DATABASE
OLD_TYPES = ('slack', 'meeting_transcripts', 'documents')
BATCH = 2000

POOL_CYPHER = f'''
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE (c)-[:product]->() OR c.metadata_section IN {json.dumps(sorted(METADATA_TYPES))}
RETURN c.chunk_id AS chunk, c.kind AS kind, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256
'''

OLD_CHANNEL_PEOPLE = '''
MATCH (p:Product)-[:slack]->(ch:Channel)
OPTIONAL MATCH (e:Employee)-[:slack]->(ch)
RETURN p.name AS product, ch.id AS channel, collect(DISTINCT e.eid) AS people
'''
OLD_MEETING_PEOPLE = '''
MATCH (e:Employee)-[:meeting_transcripts]->(p:Product)
RETURN p.name AS product, collect(DISTINCT e.eid) AS people
'''
NEW_CHANNEL_PEOPLE = '''
MATCH (p:Product)-[:slack]->(ch:Channel)
OPTIONAL MATCH (e:Employee)-[:chunk]->(:Chunk)-[:channel]->(ch)
RETURN p.name AS product, ch.id AS channel, collect(DISTINCT e.eid) AS people
'''
NEW_MEETING_PEOPLE = '''
MATCH (e:Employee)-[:chunk]->(c:Chunk)-[:product]->(p:Product)
WHERE c.kind IN ['meeting_transcript', 'meeting_transcript_part']
RETURN p.name AS product, collect(DISTINCT e.eid) AS people
'''


def people_of(kind, record):
    """The person ids a record names in the build spec's person fields, with the field."""
    if kind == 'slack_thread_batch':
        return [('userId', record['Message']['User']['userId'])]
    if kind == 'pr_batch':
        out = [('user.login', record['user']['login'])]
        out += [('reviews.user.login', r['user']['login']) for r in record.get('reviews') or []]
        return out
    if kind in ('document', 'document_part'):
        return [('author', record['author'])]
    if kind in ('meeting_transcript', 'meeting_transcript_part'):
        return [('participants', p) for p in record.get('participants') or []]
    if kind == 'employee':
        return [('employee_id', record['employee_id'])]
    return []


def pairs(session):
    """(eid, chunk id) pairs over the pool, the counts of what was found, and the ids that match
    no employee. A chunk of a metadata file is read as that file's kind (employee,
    customers_data)."""
    eids = {r['eid'] for r in session.run('MATCH (e:Employee) RETURN e.eid AS eid')}
    docs, out = {}, set()
    found, unmatched = Counter(), Counter()
    for row in session.run(POOL_CYPHER).data():
        kind = json.loads(row['locator']).get('metadata') or row['kind']
        for record in _pointed_records(dict(row, chunkId=row['chunk']), docs):
            for field, pid in people_of(kind, record):
                found[(kind, field)] += 1
                if pid in eids:
                    out.add((pid, row['chunk']))
                else:
                    unmatched[(kind, field)] += 1
    return sorted(out), found, unmatched


def backup(session):
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path = OUT / f'person_edges_to_scope_{stamp}.jsonl'
    n = 0
    with path.open('w', encoding='utf-8') as f:
        for t in OLD_TYPES:
            for r in session.run(f'MATCH (e:Employee)-[:{t}]->(x) RETURN e.eid AS eid, labels(x)[0] AS label, '
                                 'coalesce(x.id, x.name) AS target'):
                f.write(json.dumps({'type': t, 'eid': r['eid'], 'label': r['label'], 'target': r['target']}) + '\n')
                n += 1
    print(f'backup: {n} person edges to a channel or product -> {path}')


def restore(session, path):
    n = 0
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        key = 'id' if r['label'] == 'Channel' else 'name'
        session.run(f"MATCH (e:Employee {{eid: $eid}}), (x:{r['label']} {{{key}: $target}}) "
                    f"MERGE (e)-[:{r['type']}]->(x)", eid=r['eid'], target=r['target'])
        n += 1
    print(f'restore: {n} edges merged from {path}')


def write(session):
    found_pairs, found, unmatched = pairs(session)
    print('person ids in the build spec\'s person fields of the pool\'s records, by kind and field: found | '
          'matching no employee')
    for key in sorted(found):
        print(f'   {key[0]} {key[1]}: {found[key]} | {unmatched[key]}')
    session.run('CREATE INDEX employee_eid IF NOT EXISTS FOR (e:Employee) ON (e.eid)')
    session.run('CREATE INDEX chunk_chunk_id IF NOT EXISTS FOR (c:Chunk) ON (c.chunk_id)')
    for start in range(0, len(found_pairs), BATCH):
        batch = [{'eid': e, 'chunk': c} for e, c in found_pairs[start:start + BATCH]]
        session.run('UNWIND $rows AS row MATCH (e:Employee {eid: row.eid}) '
                    'MATCH (c:Chunk {chunk_id: row.chunk}) MERGE (e)-[:chunk]->(c)', rows=batch)
    print(f'write: {len(found_pairs)} person-chunk pairs merged into {DATABASE}')
    verify(session)


def verify(session):
    r = session.run('MATCH (e:Employee)-[:chunk]->(c:Chunk) RETURN count(*) AS edges, count(DISTINCT e) AS people, '
                    'count(DISTINCT c) AS chunks').single()
    print(f"verify: {r['edges']} edges (:Employee)-[:chunk]->(:Chunk), {r['people']} employees, {r['chunks']} chunks")


def compare(session):
    from arms.artefact_v4 import product_persons
    old = product_persons(session.run(OLD_CHANNEL_PEOPLE).data(), session.run(OLD_MEETING_PEOPLE).data())
    new = product_persons(session.run(NEW_CHANNEL_PEOPLE).data(), session.run(NEW_MEETING_PEOPLE).data())
    same = 0
    for product in sorted(set(old) | set(new)):
        a, b = old.get(product), new.get(product)
        if a == b:
            same += 1
            continue
        a = a or {'apart': frozenset(), 'people': frozenset()}
        b = b or {'apart': frozenset(), 'people': frozenset()}
        print(f'   {product}: channels apart old {sorted(a["apart"])} new {sorted(b["apart"])}; people only old '
              f'{len(a["people"] - b["people"])}, only new {len(b["people"] - a["people"])}')
    print(f'compare: the product\'s people and channels apart are the same from both edge sets for {same} of '
          f'{len(set(old) | set(new))} products')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('step', choices=('backup', 'write', 'compare', 'verify', 'restore'))
    ap.add_argument('--file', help='the backup file, for restore')
    args = ap.parse_args(argv)
    driver = _driver()
    try:
        with driver.session(database=DATABASE) as session:
            if args.step == 'restore':
                restore(session, args.file)
            else:
                {'backup': backup, 'write': write, 'compare': compare, 'verify': verify}[args.step](session)
    finally:
        driver.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
