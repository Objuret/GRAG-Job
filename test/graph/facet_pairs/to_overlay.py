"""round1 scores.jsonl -> a per-edge facet overlay the arm can read (HERB_FACET_SOURCE=file).

Per edge the weights are [null, temporal, why, activity, concreteness] — the RAW head scores,
not the `_pos` columns: a position column is uniform on [0, 1] by construction, and the arm's
clump rule finds no gap in a uniform column, so every edge would land in one level. topic is
null so the arm fills it with its own cos(Tag.emb, Chunk.desc_emb), as the stats overlay does.

Nothing is written to the graph. Run:
    NEO4J_DATABASE=herb-eval-volmax python test/graph/facet_pairs/to_overlay.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(_ROOT / "test"), str(_ROOT / "prod")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FACETS = ("topic", "temporal", "why", "activity", "concreteness")
WRITTEN = ("temporal", "why", "activity", "concreteness")
DEFAULT_SCORES = _ROOT / "output" / "facet_pairs" / "rounds" / "round1" / "scores.jsonl"
DEFAULT_OUT = _ROOT / "output" / "facet_pairs" / "rounds" / "round1" / "overlay.json"
DEFAULT_CONFIG = _ROOT / "output" / "facet_pairs" / "rounds" / "round1" / "model" / "config.json"

METHOD = ("temporal, why, activity, concreteness: the round-1 linear head's score per edge on "
          "the frozen gte-reranker-modernbert-base cache, trained on Opus's pairwise choices; "
          "topic null, so the arm reads cosine(Tag.emb, Chunk.desc_emb)")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_scores(path: Path) -> list:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            weights = [None]
            for f in WRITTEN:
                v = float(row[f])
                if not math.isfinite(v):
                    raise ValueError(f"{path}:{n}: {f} is {row[f]!r}, not finite")
                weights.append(v)
            rows.append({"tag": row["tag"], "chunkId": row["chunk_id"], "weights": weights})
            if n % 20000 == 0:
                print(f"to_overlay: {n} rows read", flush=True)
    return rows


def check_against_graph(rows: list, database: str, run_id: str) -> dict:
    from graph.db import _driver      # noqa: E402

    cypher = """
    MATCH (t:Tag)<-[r:HAS_TAG]-(c:Chunk)
    WHERE r.run_id = $runId AND (c)-[:product]->()
    RETURN t.name AS tag, c.chunk_id AS chunkId
    """
    drv = _driver()
    with drv.session(database=database) as s:
        live = {(rec["tag"], rec["chunkId"]) for rec in s.run(cypher, runId=run_id)}
    drv.close()
    mine = {(r["tag"], r["chunkId"]) for r in rows}
    return {"graph_edges": len(live), "overlay_edges": len(mine),
            "in_graph": len(mine & live), "not_in_graph": len(mine - live),
            "graph_only": len(live - mine)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scores", default=str(DEFAULT_SCORES))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--database", default=os.environ.get("NEO4J_DATABASE") or "herb-eval-volmax")
    ap.add_argument("--run-id", default=os.environ.get("HERB_TAG_RUN_ID") or "pilot_full_herb")
    ap.add_argument("--no-graph-check", action="store_true",
                    help="skip the live-graph membership check (no database needed)")
    args = ap.parse_args()

    scores = Path(args.scores)
    print(f"to_overlay: reading {scores}", flush=True)
    rows = read_scores(scores)
    print(f"to_overlay: {len(rows)} edges, four columns each", flush=True)

    config = json.loads(Path(args.config).read_text(encoding="utf-8")) if Path(args.config).is_file() else None
    body = {
        "database": args.database,
        "run_id": args.run_id,
        "facets": list(FACETS),
        "method": METHOD,
        "tool": "test/graph/facet_pairs/to_overlay.py",
        "tool_sha256": _sha256(Path(__file__)),
        "source": str(scores),
        "source_sha256": _sha256(scores),
        "round": (config or {}).get("round"),
        "head_config": config,
        "columns": ["topic (null)", *WRITTEN],
        "edge_count": len(rows),
        "edges": rows,
    }
    if not args.no_graph_check:
        check = check_against_graph(rows, args.database, args.run_id)
        body["graph_check"] = check
        print(f"to_overlay: graph check {check}", flush=True)
        if check["not_in_graph"]:
            raise SystemExit(f"{check['not_in_graph']} overlay edges are not product-linked "
                             f"HAS_TAG edges of {args.database}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body), encoding="utf-8")
    print(f"to_overlay: wrote {out} ({out.stat().st_size} bytes, sha {_sha256(out)[:12]})",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
