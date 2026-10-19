"""Write the facet layer the artefact reads onto the graph's HAS_TAG edges (his 2026-10-06
"yeah make the db current before anything else").

Per edge of the product-linked pool (the edges of rounds/round1/scores.jsonl) five values in
the order topic, temporal, why, activity, concreteness:
  topic        cos(tag vector, chunk description vector), the graph's own stored vectors,
               normalised and multiplied as the arm does it (`artefact_facet_joint._unit`,
               float64), so the stored number is the arm's own;
  the four     the edge's mean over the bootstrap refits of the round-1 head
               (rounds/round1/bootstrap/scores_b24.npz), the numbers the arm ranks with.
They replace `facets` / `w_facets` on those edges. Once, on a `FacetLayer` node: the layer's
name, the four per-facet retrain gaps (`bootstrap/BANDS.md`, the column the arm reads), the
pooled flip gap, the number of refits and the sha256 of every source file. Edges outside the
pool (the chunks with no product) are not touched.

    python write_facet_layer.py plan     # read everything, print what would be written
    python write_facet_layer.py write    # needs a backup entry that equals the live graph
    python write_facet_layer.py verify   # the graph's edges against the layer, value by value

`NEO4J_DATABASE` names the graph. Nothing here calls a model."""
from __future__ import annotations

if __name__ == "__main__":
    print("write_facet_layer: loading the arm's own readers and neo4j …", flush=True)

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]

from artefact import graph_layer as GL
from artefact import learned_relations as L
from arms.artefact_facet_joint import _unit
from graph import backup_facet_weights as BK
from graph.db import DATABASE, RUN_ID, _driver

LAYER_NAME = "pairwise-round1-refit-mean"
FACETS = GL.FACETS
LEARNED_DIR = ROOT / "output/facet_pairs/rounds/round1"
BANDS_FILE = LEARNED_DIR / "bootstrap/BANDS.md"
REFITS_FILE = LEARNED_DIR / "bootstrap/scores_b24.npz"
WRITE_BATCH = 1000
ADJUST_FACETS = GL.ADJUST
GAP_TABLE = '## per column'
GAP_COLUMN = 'gap (any)'
_POOLED_ROW = re.compile(r'^\|\s*\*\*pooled[^|]*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|')


def read_refit_means(path, endpoints):
    """Each edge's mean score over the bootstrap refits, per facet, in the order of `endpoints`
    ((tag, chunk id) pairs), matched by the archive's edge id "chunk id::tag"."""
    path = Path(path)
    data = path.read_bytes()
    with np.load(path, allow_pickle=False) as archive:
        edge_ids = archive['edge_ids'].tolist()
        facets = archive['facets'].tolist()
        scores = archive['scores']
        seeds = archive['seeds'].tolist()
    if scores.ndim != 3 or scores.shape[:2] != (len(edge_ids), len(facets)):
        raise ValueError(f'Expected scores [edges, facets, draws] in {path}')
    if set(ADJUST_FACETS) - set(facets):
        raise ValueError(f'{path} lacks a facet of {ADJUST_FACETS}')
    at = {edge: i for i, edge in enumerate(edge_ids)}
    if len(at) != len(edge_ids):
        raise ValueError(f'Duplicate edge id in {path}')
    wanted = [f'{chunk}::{tag}' for tag, chunk in endpoints]
    missing = [edge for edge in wanted if edge not in at]
    if missing:
        raise ValueError(f'{len(missing)} edges have no refit scores in {path}')
    rows = np.array([at[edge] for edge in wanted], dtype=np.int64)
    columns = [facets.index(f) for f in ADJUST_FACETS]
    values = scores[rows][:, columns, :].astype(np.float64).mean(axis=2)
    if not np.isfinite(values).all():
        raise ValueError(f'A refit mean in {path} is not finite')
    return values, {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
                    'draws': int(scores.shape[2]), 'seeds': seeds,
                    'value': 'per-edge mean over the draws of each facet column'}


def read_facet_gaps(path, column=GAP_COLUMN):
    """Each facet's own retrain flip gap from BANDS.md's per-column table, read by column name,
    with the line each value was read from."""
    path = Path(path)
    lines = path.read_text(encoding='utf-8').splitlines()
    if GAP_TABLE not in lines:
        raise ValueError(f'No per-column table in {path}')
    header, found = None, {}
    for number in range(lines.index(GAP_TABLE) + 1, len(lines)):
        line = lines[number].strip()
        if line.startswith('## '):
            break
        if not line.startswith('|'):
            continue
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if header is None:
            if column not in cells:
                raise ValueError(f'No column {column!r} in the per-column table of {path}')
            header = cells
        elif cells[0] in ADJUST_FACETS:
            found[cells[0]] = (float(cells[header.index(column)]), number + 1)
    missing = [f for f in ADJUST_FACETS if f not in found]
    if missing:
        raise ValueError(f'No {column!r} gap for {missing} in {path}')
    gaps = tuple(found[f][0] for f in ADJUST_FACETS)
    if not all(np.isfinite(g) and g > 0 for g in gaps):
        raise ValueError('A facet gap must be a positive number')
    return gaps, {'path': str(path), 'table': 'per column', 'column': column,
                  'lines': {f: found[f][1] for f in ADJUST_FACETS}}


def read_flip_gap(path):
    """The pooled same-chunk retrain flip gap from BANDS.md, with where it was read."""
    path = Path(path)
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        found = _POOLED_ROW.match(line)
        if found:
            return float(found.group(3)), {'path': str(path), 'line': number,
                                           'column': 'gap (same chunk)', 'row': 'pooled'}
    raise ValueError(f'No pooled flip-gap row in {path}')

_TAG_CYPHER = """
MATCH (t:Tag) WHERE t.emb IS NOT NULL AND EXISTS {
    MATCH (t)<-[r:HAS_TAG]-(c:Chunk)
    WHERE r.run_id = $run AND (c)-[:product]->() }
RETURN t.name AS id, t.emb AS vector ORDER BY id
"""

_CHUNK_CYPHER = """
MATCH (c:Chunk) WHERE c.desc_emb IS NOT NULL AND EXISTS {
    MATCH (c)-[r:HAS_TAG]->() WHERE r.run_id = $run }
    AND (c)-[:product]->()
RETURN c.chunk_id AS chunkId, c.desc_emb AS vector ORDER BY chunkId
"""

_EDGE_CYPHER = """
MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $run
RETURN c.chunk_id AS chunk_id, t.name AS tag, r.facets AS facets, r.w_facets AS w_facets,
       EXISTS { (c)-[:product]->() } AS pooled
"""

_WRITE_CYPHER = """
UNWIND $rows AS row
MATCH (c:Chunk {chunk_id: row.chunk_id})-[r:HAS_TAG]->(t:Tag {name: row.tag})
WHERE r.run_id = $run
SET r.facets = $facets, r.w_facets = row.values
RETURN count(r) AS n
"""

_LAYER_CYPHER = """
MERGE (l:FacetLayer {run_id: $run})
SET l = $properties
RETURN count(l) AS n
"""

_READ_LAYER_CYPHER = "MATCH (l:FacetLayer {run_id: $run}) RETURN properties(l) AS properties"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def layer_rows(session) -> tuple:
    """The rows to write, in the order of the layer's own file, and the layer node's values."""
    learned = L.load(LEARNED_DIR)
    endpoints = learned.endpoints
    means, refit_source = read_refit_means(REFITS_FILE, endpoints)
    gaps, gap_source = read_facet_gaps(BANDS_FILE)
    pooled, pooled_source = read_flip_gap(BANDS_FILE)
    tag_rows = list(session.run(_TAG_CYPHER, run=RUN_ID))
    chunk_rows = list(session.run(_CHUNK_CYPHER, run=RUN_ID))
    tags = [r["id"] for r in tag_rows]
    chunks = [r["chunkId"] for r in chunk_rows]
    at = {name: i for i, name in enumerate(tags)}
    ci = {name: i for i, name in enumerate(chunks)}
    missing = [e for e in endpoints if e[0] not in at or e[1] not in ci]
    if missing:
        raise SystemExit(f"{len(missing)} layer edges have no tag or chunk in {DATABASE!r}")
    # the arm's own arithmetic (artefact_v4.prepare_over_corpus): the stored float32 rows
    # normalised in float64 by `artefact_facet_joint._unit`, one dot product per edge
    tag_vectors = _unit(np.asarray([r["vector"] for r in tag_rows], dtype=np.float32))
    chunk_vectors = _unit(np.asarray([r["vector"] for r in chunk_rows], dtype=np.float32))
    edge_tag = np.array([at[t] for t, _ in endpoints], dtype=np.int64)
    edge_chunk = np.array([ci[c] for _, c in endpoints], dtype=np.int64)
    topic = np.einsum("ij,ij->i", tag_vectors[edge_tag], chunk_vectors[edge_chunk])
    values = np.column_stack([np.asarray(topic, dtype=np.float64), means])
    if values.shape != (len(endpoints), len(FACETS)) or not np.isfinite(values).all():
        raise SystemExit("the layer does not give five finite values per edge")
    rows = [{"chunk_id": chunk, "tag": tag, "values": [float(v) for v in row]}
            for (tag, chunk), row in zip(endpoints, values)]
    rows_sha256 = GL.digest((row["chunk_id"], row["tag"], row["values"]) for row in rows)
    properties = {
        "run_id": RUN_ID, "name": LAYER_NAME, "facets": list(FACETS),
        "value_topic": "cos(tag vector, chunk description vector), the graph's stored vectors",
        "value_others": "the edge's mean over the bootstrap refits of the round-1 head score",
        "refits": int(refit_source["draws"]),
        "equal_gap_facets": list(ADJUST_FACETS), "equal_gap": [float(g) for g in gaps],
        "equal_gap_column": gap_source["column"],
        "pooled_flip_gap": float(pooled),
        "pooled_flip_gap_column": pooled_source["column"],
        "edges": len(rows), "rows_sha256": rows_sha256,
        "source_scores_sha256": learned.source_sha256,
        "source_refits_sha256": refit_source["sha256"],
        "source_bands_sha256": _sha(BANDS_FILE),
        "source_dir": str(LEARNED_DIR.relative_to(ROOT)).replace("\\", "/"),
    }
    return rows, properties


def graph_edges(session) -> dict:
    return {(r["chunk_id"], r["tag"]): (r["facets"], r["w_facets"], r["pooled"])
            for r in session.run(_EDGE_CYPHER, run=RUN_ID)}


def compare(rows: list, edges: dict) -> dict:
    """How the graph's edges stand against the layer's rows."""
    current = sum(1 for row in rows
                  if edges.get((row["chunk_id"], row["tag"]), (None, None, None))[:2]
                  == (list(FACETS), row["values"]))
    absent = sum(1 for row in rows if (row["chunk_id"], row["tag"]) not in edges)
    keys = {(row["chunk_id"], row["tag"]) for row in rows}
    pooled = sum(1 for key, value in edges.items() if value[2])
    outside = [key for key in edges if key not in keys]
    outside_pooled = sum(1 for key in outside if edges[key][2])
    carrying = sum(1 for key in outside if edges[key][0] == list(FACETS))
    return {"layer_rows": len(rows), "distinct_rows": len(keys), "graph_edges": len(edges),
            "graph_edges_in_the_pool": pooled, "rows_with_no_edge": absent,
            "rows_the_graph_already_carries": current,
            "graph_edges_outside_the_layer": len(outside),
            "of_them_in_the_pool": outside_pooled,
            "of_them_carrying_the_layer_facets": carrying}


def write(session, rows: list, properties: dict) -> int:
    """Every edge and the layer node in one transaction: all of it lands or none of it."""
    written = 0
    stamped = {**properties,
               "written": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with session.begin_transaction() as tx:
        for i in range(0, len(rows), WRITE_BATCH):
            batch = rows[i:i + WRITE_BATCH]
            n = tx.run(_WRITE_CYPHER, rows=batch, run=RUN_ID,
                       facets=list(FACETS)).single()["n"]
            if n != len(batch):
                tx.rollback()
                raise RuntimeError(f"batch at row {i}: {len(batch)} rows set {n} edges — "
                                   f"rolled back, nothing written")
            written += n
            if (i // WRITE_BATCH) % 10 == 9 or i + WRITE_BATCH >= len(rows):
                print(f"  {written} of {len(rows)} edges set", flush=True)
        if tx.run(_LAYER_CYPHER, run=RUN_ID, properties=stamped).single()["n"] != 1:
            tx.rollback()
            raise RuntimeError("the FacetLayer node was not written — rolled back")
        tx.commit()
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("plan", "write", "verify"))
    args = ap.parse_args()
    started = time.perf_counter()
    print(f"{args.mode}: {DATABASE!r} (run_id={RUN_ID!r}), layer {LAYER_NAME!r} from "
          f"{LEARNED_DIR.relative_to(ROOT)} …", flush=True)
    driver = _driver()
    try:
        access = "WRITE" if args.mode == "write" else "READ"
        with driver.session(database=DATABASE, default_access_mode=access) as session:
            rows, properties = layer_rows(session)
            edges = graph_edges(session)
            state = compare(rows, edges)
            print("  " + json.dumps(state), flush=True)
            print("  layer node: " + json.dumps(properties), flush=True)
            if state["rows_with_no_edge"] or state["distinct_rows"] != state["layer_rows"]:
                raise SystemExit("a layer row has no edge in the graph, or two rows name one "
                                 "edge — nothing written")
            if args.mode == "write":
                manifest = BK.require_backup()
                stored = BK.load_backup(BK.entry_dir(), manifest)
                live = {(key[0], key[1]): (value[0], value[1]) for key, value in edges.items()}
                kept = {(r["chunk_id"], r["tag"]): (r["facets"], r["w_facets"]) for r in stored}
                if kept != live:
                    raise SystemExit("the backup entry does not equal the live graph — run "
                                     "`python backup_facet_weights.py backup` first; nothing "
                                     "written")
                print(f"  backup {manifest['sha256'][:12]}… equals the live graph on "
                      f"{len(live)} edges; writing", flush=True)
                written = write(session, rows, properties)
                after = compare(rows, graph_edges(session))
                print("  after: " + json.dumps(after), flush=True)
                if after["rows_the_graph_already_carries"] != len(rows):
                    raise SystemExit(f"{written} edges written, but the graph carries the "
                                     f"layer on {after['rows_the_graph_already_carries']}")
            elif args.mode == "verify":
                node = session.run(_READ_LAYER_CYPHER, run=RUN_ID).single()
                if node is None:
                    raise SystemExit("no FacetLayer node in the graph")
                held = dict(node["properties"])
                held.pop("written", None)
                if held != properties:
                    differing = sorted(k for k in set(held) | set(properties)
                                       if held.get(k) != properties.get(k))
                    raise SystemExit(f"the FacetLayer node differs from the layer on {differing}")
                if state["rows_the_graph_already_carries"] != len(rows):
                    raise SystemExit(
                        f"the graph carries the layer on "
                        f"{state['rows_the_graph_already_carries']} of {len(rows)} edges")
                print(f"  every one of the {len(rows)} edges carries the layer's five values, "
                      f"and the FacetLayer node equals the layer", flush=True)
    finally:
        driver.close()
    print(f"done ({time.perf_counter() - started:.0f}s).", flush=True)


if __name__ == "__main__":
    main()
