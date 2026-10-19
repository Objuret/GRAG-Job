"""The people the records of a chunk name, over the whole pool: how many people a chunk names, in
how many chunks of the product a person is named, and in how many of a channel's chunks. From the
graph (chunk, product, parent) and the dataset files; no question and no gold read.

People in a record: a Slack message's user, a document's author, a meeting's participants, a
pull request's author and its reviewers.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/people_in_the_chunks.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from graph.db import _driver  # noqa: E402

CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)-[:product]->(p:Product) WHERE c.desc_emb IS NOT NULL
RETURN c.chunk_id AS chunk, c.kind AS kind, c.locator_json AS locator, c.parent_ref AS parent,
       f.rel_path AS relpath, f.sha256 AS sha256, p.name AS product
"""


def people_of(record):
    found = set()
    user = ((record.get("Message") or {}).get("User") or {}).get("userId")
    if user:
        found.add(str(user))
    if record.get("author"):
        found.add(str(record["author"]))
    for who in record.get("participants") or []:
        found.add(str(who))
    login = (record.get("user") or {}).get("login") if isinstance(record.get("user"), dict) else None
    if login:
        found.add(str(login))
    for review in record.get("reviews") or []:
        login = (review.get("user") or {}).get("login")
        if login:
            found.add(str(login))
    return found


def spread_of(values):
    q1, mid, q3 = np.percentile(np.asarray(values, dtype=np.float64), [25, 50, 75])
    return f"{mid:.0f} ({q1:.0f}-{q3:.0f})"


def share_of(values):
    q1, mid, q3 = np.percentile(np.asarray(values, dtype=np.float64), [25, 50, 75])
    return f"{mid:.2f} ({q1:.2f}-{q3:.2f})"


driver = _driver()
with driver.session(database=V.DATABASE) as session:
    rows = session.execute_read(lambda tx: [dict(r) for r in tx.run(CYPHER)])
driver.close()
docs = {}
by_kind = defaultdict(list)
in_product, product_chunks = defaultdict(lambda: defaultdict(set)), defaultdict(set)
in_parent, parent_chunks = defaultdict(lambda: defaultdict(set)), defaultdict(set)
none_named = defaultdict(int)
for row in rows:
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    people = set()
    for k in (loc["indices"] if "indices" in loc else [loc["index"]]):
        people |= people_of(arr[k])
    by_kind[row["kind"]].append(len(people))
    none_named[row["kind"]] += int(not people)
    product_chunks[row["product"]].add(row["chunk"])
    parent_chunks[row["parent"]].add(row["chunk"])
    for who in people:
        in_product[row["product"]][who].add(row["chunk"])
        in_parent[row["parent"]][who].add(row["chunk"])
print(f"pool chunks read: {len(rows)}")
print("== people a chunk's records name, by kind: chunks | people, the middle (a quarter - three quarters) | chunks "
      "that name nobody ==")
for kind in sorted(by_kind):
    print(f"  {kind}: {len(by_kind[kind])} | {spread_of(by_kind[kind])} | {none_named[kind]}")
people_per_product = [len(v) for v in in_product.values()]
share_in_product = [len(chunks) / len(product_chunks[p]) for p, people in in_product.items() for chunks in people.values()]
count_in_product = [len(chunks) for people in in_product.values() for chunks in people.values()]
print("\n== inside a product ==")
print(f"  people named in a product's chunks: {spread_of(people_per_product)}")
print(f"  chunks of the product that name one given person: {spread_of(count_in_product)}; as a share of the "
      f"product's chunks: {share_of(share_in_product)}")
big = {parent: chunks for parent, chunks in parent_chunks.items() if len(chunks) > 1}
people_per_parent = [len(in_parent[parent]) for parent in big]
share_in_parent = [len(chunks) / len(big[parent]) for parent in big for chunks in in_parent[parent].values()]
print("\n== inside a parent that holds more than one chunk (a channel or a file) ==")
print(f"  parents: {len(big)}; chunks in a parent: {spread_of([len(c) for c in big.values()])}")
print(f"  people named in a parent's chunks: {spread_of(people_per_parent)}")
print(f"  share of the parent's chunks that name one given person: {share_of(share_in_parent)}")
print("done")
