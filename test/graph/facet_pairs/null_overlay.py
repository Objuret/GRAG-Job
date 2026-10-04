"""The null layer: the round-1 overlay with each of the four columns permuted across edges.

Same marginals, same edge set, same file shape — only the assignment of a value to an edge is
destroyed, independently per column, under a fixed seed. An arm reading this file sees a layer
that carries exactly the distribution of the real one and none of its information, so a run
over it says what the mode's key does when the four columns mean nothing.

topic is left null, as in the real overlay: the arm fills it with the graph's
cos(Tag.emb, Chunk.desc_emb), which the permutation must not touch.

    python test/graph/facet_pairs/null_overlay.py

Writes output/facet_pairs/rounds/round1/overlay_null.json beside the overlay it permutes.
Nothing is written to the graph.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
ROUND1 = ROOT / "output" / "facet_pairs" / "rounds" / "round1"
SEED = 20260921


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def permute(body: dict, seed: int = SEED) -> dict:
    """each non-topic column permuted across the edges with its own generator stream"""
    facets = list(body["facets"])
    edges = body["edges"]
    n = len(edges)
    rng = np.random.default_rng(seed)
    cols = [i for i, f in enumerate(facets) if f != "topic"]
    if len(cols) != len(facets) - 1:
        raise ValueError(f"the overlay names its facets {facets!r}; topic is not among them")
    out = [{"tag": e["tag"], "chunkId": e["chunkId"], "weights": list(e["weights"])}
           for e in edges]
    moved = {}
    for c in cols:
        values = [edges[i]["weights"][c] for i in range(n)]
        order = rng.permutation(n)
        same = 0
        for i in range(n):
            out[i]["weights"][c] = values[int(order[i])]
            same += int(int(order[i]) == i)
        moved[facets[c]] = {"fixed_points": same}
    for row in out:
        row["weights"][facets.index("topic")] = None
    method = (
        "NULL LAYER, not a measurement of anything: the four non-topic columns of the round-1 "
        f"overlay, each permuted INDEPENDENTLY across the {n} edges at seed {seed}. Every "
        "column keeps its exact marginal distribution and loses which edge carried which "
        "value; because the four permutations are independent, the cross-column correlation "
        "the real layer has is destroyed too, so this is a null for the columns AND for their "
        "joint structure. topic is left null, as in the source, and the arm fills it with the "
        "graph's cos(Tag.emb, Chunk.desc_emb) — the topic column is NOT nulled. "
        f"Source: {body.get('_source') or 'the round-1 overlay'}.")
    return {**{k: v for k, v in body.items() if k != "edges"},
            "method": method,
            "edges": out,
            "null": {"seed": seed, "permuted": [facets[c] for c in cols],
                     "topic": "left null; the arm reads cos(Tag.emb, Chunk.desc_emb)",
                     "per_column": moved, "edge_count": n,
                     "tool": "test/graph/facet_pairs/null_overlay.py",
                     "tool_sha256": _sha(Path(__file__)),
                     "source": str(body.get("_source") or ""),
                     "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}}


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overlay", default=str(ROUND1 / "overlay.json"))
    ap.add_argument("--out", default=str(ROUND1 / "overlay_null.json"))
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)

    src = Path(args.overlay)
    print(f"null_overlay | reading {src}", flush=True)
    body = json.loads(src.read_text(encoding="utf-8"))
    body["_source"] = str(src)
    t0 = time.perf_counter()
    out = permute(body, args.seed)
    out["null"]["source_sha256"] = _sha(src)
    out.pop("_source", None)
    dst = Path(args.out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out), encoding="utf-8")
    print(f"null_overlay | {out['null']['edge_count']} edges, columns "
          f"{out['null']['permuted']} permuted at seed {args.seed} "
          f"({time.perf_counter() - t0:.1f}s)", flush=True)
    print(f"null_overlay | wrote {dst} ({dst.stat().st_size / 1e6:.1f} MB, "
          f"sha {_sha(dst)[:12]})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
