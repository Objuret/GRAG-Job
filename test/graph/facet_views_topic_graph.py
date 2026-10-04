"""The graph's own topic for a set of chunks: cos(Tag.emb, Chunk.desc_emb) per HAS_TAG edge, and
the stored vectors, for the facet-view check's register test. Read-only on the graph.

Writes `<out>/topic_graph.jsonl` ({chunk_id, tag, topic_graph}) and `<out>/graph_vectors.npz`
(chunk_ids, desc_emb, tags, tag_emb). The 2026-09-18 pilot's files were made by this read
(inline at the time; kept here so a successor can reproduce them).

    NEO4J_DATABASE=herb-eval-volmax python test/graph/facet_views_topic_graph.py \\
        --ids-file output/facet_neural/selection_stage2.ids.txt --out output/facet_views/pilot
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "prod", ROOT / "test"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

QUERY = """MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
WHERE c.chunk_id IN $ids AND r.run_id = $runId
RETURN c.chunk_id AS cid, t.name AS tag, c.desc_emb AS d, t.emb AS e"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="the graph's topic per edge for a chunk set")
    ap.add_argument("--ids-file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--db", default=os.environ.get("NEO4J_DATABASE", "herb-eval-volmax"))
    ap.add_argument("--run-id", default=os.environ.get("HERB_TAG_RUN_ID", "pilot_full_herb"))
    args = ap.parse_args(argv)

    from graph import db as graphdb
    ids = [l.strip() for l in open(args.ids_file, encoding="utf-8") if l.strip()]
    rows, tag_vecs, desc_vecs = [], {}, {}
    drv = graphdb._driver()
    try:
        with drv.session(database=args.db) as s:
            for r in s.run(QUERY, ids=ids, runId=args.run_id):
                d = np.asarray(r["d"], dtype=np.float32)
                e = np.asarray(r["e"], dtype=np.float32)
                desc_vecs[r["cid"]] = d
                tag_vecs[r["tag"]] = e
                cos = float(np.dot(d, e) / (np.linalg.norm(d) * np.linalg.norm(e)))
                rows.append({"chunk_id": r["cid"], "tag": r["tag"], "topic_graph": round(cos, 6)})
    finally:
        drv.close()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "topic_graph.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    np.savez(out / "graph_vectors.npz",
             chunk_ids=np.array(list(desc_vecs)),
             desc_emb=np.stack([desc_vecs[c] for c in desc_vecs]),
             tags=np.array(list(tag_vecs)),
             tag_emb=np.stack([tag_vecs[t] for t in tag_vecs]))
    v = sorted(r["topic_graph"] for r in rows)
    print(f"edges {len(rows)} chunks {len(desc_vecs)} tags {len(tag_vecs)} "
          f"topic_graph min/median/max {v[0]:.4f}/{v[len(v)//2]:.4f}/{v[-1]:.4f} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
