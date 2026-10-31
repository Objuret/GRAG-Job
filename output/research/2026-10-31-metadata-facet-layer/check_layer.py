"""Scratch check (not in the repo): the facet layer as a graph carries it, read the way the arm
reads it at start (`artefact_v4.prepare_over_corpus`): EDGE_CYPHER and LAYER_CYPHER into
graph_layer.read, COUNTS_CYPHER's topic check against TOPIC_TOLERANCE. Then a digest of every
HAS_TAG edge of the run and of the FacetLayer node, and with --backup every edge against a backup
entry, split by product / metadata section.

CHECK_REPO: the repo whose prod/ and test/ are imported; CHECK_MIRROR (optional): a folder whose
test/ is searched first (a copy of the arm beside a clone). NEO4J_DATABASE names the graph.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CHECK_REPO", r"C:\Coding\exjobbet\GRAG-Job"))
paths = [str(ROOT / "prod"), str(ROOT / "test")]
if os.environ.get("CHECK_MIRROR"):
    paths.insert(0, str(Path(os.environ["CHECK_MIRROR"]) / "test"))
sys.path[:0] = paths
from artefact import graph_layer as GL  # noqa: E402
from arms import artefact_v4 as A  # noqa: E402
from graph.db import DATABASE, RUN_ID, _driver  # noqa: E402

ALL = """
MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag) WHERE r.run_id = $run
RETURN c.chunk_id AS chunk_id, t.name AS tag, r.facets AS facets, r.w_facets AS w_facets,
       r.w_chunk AS w_chunk, c.metadata_section AS section, EXISTS { (c)-[:product]->() } AS product
ORDER BY chunk_id, tag
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    d = _driver()
    with d.session(database=DATABASE, default_access_mode="READ") as s:
        products = sorted({r["name"].lower() for r in s.run(A.PRODUCT_CYPHER)})
        edge_rows = [dict(r) for r in s.run(A.EDGE_CYPHER, run=RUN_ID)]
        layer_rows = [dict(r) for r in s.run(A.LAYER_CYPHER, run=RUN_ID)]
        counts = s.run(A.COUNTS_CYPHER, run=RUN_ID, products=products).single().data()
        every = s.run(ALL, run=RUN_ID).data()
    d.close()
    report = {"uri": os.environ.get("NEO4J_URI", "neo4j://localhost:7687"), "database": DATABASE,
              "arm_file": A.__file__, "pool": A.POOL, "counts": counts,
              "topic_check_passes": counts["topic_apart"] <= A.TOPIC_TOLERANCE}
    try:
        layer = GL.read(edge_rows, layer_rows)
        report["graph_layer_read"] = {"passes": True, "edges": len(layer.endpoints),
                                      "gaps": layer.gaps, "pooled_gap": layer.pooled_gap}
    except ValueError as exc:
        report["graph_layer_read"] = {"passes": False, "error": str(exc),
                                      "pool_edges": len(edge_rows)}
    h = hashlib.sha256()
    for r in every:
        h.update(json.dumps([r["chunk_id"], r["tag"], r["facets"], r["w_facets"], r["w_chunk"]],
                            ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
    node = dict(layer_rows[0]["properties"]) if layer_rows else {}
    written = node.pop("written", None)
    report["all_edges"] = {"edges": len(every), "sha256": h.hexdigest()}
    report["node"] = {"written": written, "sha256": hashlib.sha256(json.dumps(
        node, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "properties": node}
    if a.backup:
        kept = {}
        with open(a.backup, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                kept[(r["chunk_id"], r["tag"])] = (r["facets"], r["w_facets"], r["w_chunk"])
        groups = {}
        for r in every:
            g = "product" if r["product"] else (r["section"] or "other")
            k = groups.setdefault(g, {"edges": 0, "equal_to_backup": 0, "not_in_backup": 0})
            k["edges"] += 1
            old = kept.get((r["chunk_id"], r["tag"]))
            if old is None:
                k["not_in_backup"] += 1
            elif old == (r["facets"], r["w_facets"], r["w_chunk"]):
                k["equal_to_backup"] += 1
        report["against_backup"] = {"backup": a.backup, "backup_edges": len(kept),
                                    "groups": groups}
    text = json.dumps(report, indent=1, default=str)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
