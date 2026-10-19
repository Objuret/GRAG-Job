"""The structure nodes' names in the graph (his 2026-10-19 "if it's "easy" to find when creating the
graph from the dataset, then its reasonable to use, like the "filestructure" etc"; "well build
this, go on").

Every Product, Channel, Employee, Customer and Company node gets `name`, the name the dataset gives
it, and `name_keys`, the forms a question is matched against: the name, and for an employee or a
customer also its id, each in the arm's plain form (`artefact_v4._plain`: lower case, everything
but letters and digits one space, a space at each end). A channel's, an employee's and a
customer's name is read through the node's own pointer into its file; a product's is its `name`,
a company's its `value`. No model call.

    write    reads the names, prints them per label, and sets the two properties
    verify   counts the nodes that carry them
    remove   takes the two properties off (a product keeps its own name)

    NEO4J_DATABASE=herb-eval-volmax .venv/Scripts/python.exe test/graph/build_structure_names.py write
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / 'prod', ROOT / 'test'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from arms.artefact_v4 import _plain  # noqa: E402
from graph.db import _driver  # noqa: E402

DATABASE = os.environ.get('NEO4J_DATABASE', 'herb-eval-volmax')
CORPUS = ROOT / 'data' / 'corpus'
LABELS = ('Product', 'Channel', 'Employee', 'Customer', 'Company')
# The nodes whose name lives in their file, with the property that is their id in a question
POINTED = {'Channel': None, 'Employee': 'eid', 'Customer': 'id'}


def _pointer(doc, pointer):
    """The part of a JSON document a pointer names (RFC 6901)."""
    node = doc
    for raw in pointer.lstrip('/').split('/') if pointer not in ('', '/') else ():
        token = raw.replace('~1', '/').replace('~0', '~')
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def keys_of(name, ident=None):
    """The forms a question is matched against: the name, and the id when the node has one."""
    return [_plain(name)] + ([_plain(ident)] if ident is not None else [])


def names(session):
    """Per node (element id): its label, its name and its match keys."""
    files = {r['file_id']: r['rel_path'] for r in session.run(
        'MATCH (f:File) RETURN f.file_id AS file_id, f.rel_path AS rel_path')}
    docs, out = {}, {}
    for label, id_prop in POINTED.items():
        rows = session.run(f'MATCH (n:{label}) RETURN elementId(n) AS node, n.file_id AS file_id, '
                           f'n.pointer AS pointer' + (f', n.{id_prop} AS ident' if id_prop else '')).data()
        for row in rows:
            rel = files[row['file_id']]
            if rel not in docs:
                docs[rel] = json.loads((CORPUS / rel).read_text(encoding='utf-8'))
            name = _pointer(docs[rel], row['pointer'])['name']
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f'{label} {row["node"]} has no name at its pointer')
            out[row['node']] = (label, name, keys_of(name, row['ident'] if id_prop else None))
    for row in session.run('MATCH (n:Product) RETURN elementId(n) AS node, n.name AS name').data():
        out[row['node']] = ('Product', row['name'], keys_of(row['name']))
    for row in session.run('MATCH (n:Company) RETURN elementId(n) AS node, n.value AS name').data():
        out[row['node']] = ('Company', row['name'], keys_of(row['name']))
    empty = [node for node, (_, _, keys) in out.items() if not all(k.strip() for k in keys)]
    if empty:
        raise ValueError(f'{len(empty)} nodes have a name or id with no letter or digit')
    return out


def write(session):
    found = names(session)
    by_label = Counter(label for label, _, _ in found.values())
    keys = Counter(k for _, _, ks in found.values() for k in ks)
    print('named nodes per label:', dict(sorted(by_label.items())))
    print(f'match keys: {sum(keys.values())}, distinct {len(keys)}, '
          f'borne by more than one node {sum(1 for n in keys.values() if n > 1)}')
    rows = [{'node': node, 'name': name, 'keys': ks} for node, (_, name, ks) in sorted(found.items())]
    session.run('UNWIND $rows AS row MATCH (n) WHERE elementId(n) = row.node '
                'SET n.name = row.name, n.name_keys = row.keys', rows=rows)
    print(f'write: name and name_keys set on {len(rows)} nodes of {DATABASE}')
    verify(session)


def verify(session):
    for label in LABELS:
        r = session.run(f'MATCH (n:{label}) RETURN count(n) AS n, count(n.name_keys) AS keyed').single()
        print(f'verify: {label} {r["keyed"]} of {r["n"]} carry name_keys')


def remove(session):
    n = session.run('MATCH (n) WHERE n.name_keys IS NOT NULL REMOVE n.name_keys RETURN count(n) AS n'
                    ).single()['n']
    m = session.run('MATCH (n) WHERE (n:Channel OR n:Employee OR n:Customer OR n:Company) '
                    'AND n.name IS NOT NULL REMOVE n.name RETURN count(n) AS n').single()['n']
    print(f'remove: name_keys taken off {n} nodes, name off {m}')


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
