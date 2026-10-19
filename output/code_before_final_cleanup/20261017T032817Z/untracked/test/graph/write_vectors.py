"""Write vectors from a side file onto the graph: the tags' `Tag.emb` or the chunk descriptions'
`Chunk.desc_emb`.

    python write_vectors.py plan   tags|descriptions <vectors.npz>
    python write_vectors.py write  tags|descriptions <vectors.npz> --keep <folder>
    python write_vectors.py verify tags|descriptions <vectors.npz>

<vectors.npz> holds `ids` (the tag names, or the chunk ids) and `matrix` (float32, one unit row
an id), as `embed_job.py` writes it. `write` first saves what the graph carries now, exactly as
stored (float64), into <folder>/<property>_as_stored.npz with a manifest, reads that file back
against the graph, and only then sets the property on every node, in batches. `verify` compares
every node's vector on the graph with the file: two sums over each vector, computed in the
database, and a seeded sample of whole vectors read back.

`NEO4J_DATABASE` names the graph. Nothing here calls a model. The facet layer's topic is the
cosine of the tag vectors and the chunk description vectors, so `write_facet_layer.py write`
has to follow a write here.
"""
from __future__ import annotations

if __name__ == "__main__":
    print("write_vectors: loading neo4j …", flush=True)

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]

from graph.db import DATABASE, _driver

TARGETS = {"tags": ("Tag", "name", "emb"), "descriptions": ("Chunk", "chunk_id", "desc_emb")}
WRITE_BATCH = 500
READ_BATCH = 1000
SAMPLE, SAMPLE_SEED = 200, 20261008
SUM_TOLERANCE = 1e-9


def cypher(label: str, key: str, prop: str) -> dict:
    return {
        "names": f"MATCH (n:{label}) WHERE n.{prop} IS NOT NULL RETURN n.{key} AS id ORDER BY id",
        "all": f"MATCH (n:{label}) RETURN count(n) AS nodes, count(n.{prop}) AS vectors",
        "read": f"UNWIND $ids AS id MATCH (n:{label} {{{key}: id}}) RETURN n.{key} AS id, n.{prop} AS vector",
        "sums": f"""
MATCH (n:{label}) WHERE n.{prop} IS NOT NULL
RETURN n.{key} AS id, size(n.{prop}) AS size,
       reduce(s = 0.0, x IN n.{prop} | s + x) AS total,
       reduce(s = 0.0, i IN range(0, size(n.{prop}) - 1) | s + (i + 1) * n.{prop}[i]) AS weighted
""",
        "write": f"UNWIND $rows AS row MATCH (n:{label} {{{key}: row.id}}) SET n.{prop} = row.vector "
                 f"RETURN count(n) AS n",
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> tuple:
    z = np.load(path, allow_pickle=True)
    ids = [str(i) for i in z["ids"]]
    matrix = np.asarray(z["matrix"])
    if matrix.dtype != np.float32 or matrix.ndim != 2 or matrix.shape[0] != len(ids):
        raise SystemExit(f"{path}: expected float32 [ids, dim] with one row an id")
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{path}: an id occurs twice")
    lengths = np.linalg.norm(matrix.astype(np.float64), axis=1)
    if not np.isfinite(matrix).all() or np.abs(lengths - 1).max() > 1e-5:
        raise SystemExit(f"{path}: a row is not finite or not of unit length")
    return ids, matrix


def sums_of(matrix: np.ndarray) -> tuple:
    m = matrix.astype(np.float64)
    return m.sum(axis=1), m @ np.arange(1, m.shape[1] + 1, dtype=np.float64)


def read_vectors(session, q: dict, ids: list) -> np.ndarray:
    """The stored vectors of `ids`, in that order, as the doubles the graph holds."""
    rows = {}
    for i in range(0, len(ids), READ_BATCH):
        for record in session.run(q["read"], ids=ids[i:i + READ_BATCH]):
            rows[record["id"]] = record["vector"]
        print(f"  read {min(i + READ_BATCH, len(ids))} of {len(ids)}", flush=True)
    missing = [i for i in ids if i not in rows]
    if missing:
        raise SystemExit(f"{len(missing)} nodes have no vector on the graph")
    return np.asarray([rows[i] for i in ids], dtype=np.float64)


def compare(session, q: dict, ids: list, matrix: np.ndarray) -> dict:
    """Every node's two sums on the graph against the file's, and a seeded sample read whole."""
    at = {name: i for i, name in enumerate(ids)}
    total, weighted = sums_of(matrix)
    worst, differ, sizes = 0.0, 0, set()
    for record in session.run(q["sums"]):
        i = at[record["id"]]
        sizes.add(record["size"])
        gap = max(abs(record["total"] - total[i]),
                  abs(record["weighted"] - weighted[i]) / matrix.shape[1])
        worst = max(worst, gap)
        differ += gap > SUM_TOLERANCE
    picks = sorted(np.random.default_rng(SAMPLE_SEED).choice(len(ids), min(SAMPLE, len(ids)),
                                                             replace=False).tolist())
    stored = read_vectors(session, q, [ids[i] for i in picks])
    exact = int((stored.astype(np.float32) == matrix[picks]).all(axis=1).sum())
    return {"nodes": len(ids), "vector_sizes_on_the_graph": sorted(sizes),
            "nodes_whose_sums_differ": int(differ), "largest_sum_difference": worst,
            "sample": len(picks), "sample_rows_equal_as_float32": exact}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("plan", "write", "verify"))
    ap.add_argument("target", choices=sorted(TARGETS))
    ap.add_argument("vectors", type=Path)
    ap.add_argument("--keep", type=Path, help="folder for what the graph carries before a write")
    args = ap.parse_args()
    if args.mode == "write" and args.keep is None:
        raise SystemExit("write needs --keep <folder>")
    label, key, prop = TARGETS[args.target]
    q = cypher(label, key, prop)
    started = time.perf_counter()
    ids, matrix = load(args.vectors)
    print(f"{args.mode} {label}.{prop}: {DATABASE!r}, {args.vectors} {matrix.shape} {matrix.dtype} "
          f"sha256 {sha256_file(args.vectors)[:16]}", flush=True)
    driver = _driver()
    try:
        access = "WRITE" if args.mode == "write" else "READ"
        with driver.session(database=DATABASE, default_access_mode=access) as session:
            counts = session.run(q["all"]).single()
            names = [r["id"] for r in session.run(q["names"])]
            print(f"  graph: {counts['nodes']} {label} nodes, {counts['vectors']} with a vector", flush=True)
            if sorted(names) != sorted(ids):
                raise SystemExit(f"the file's ids are not the graph's {label} nodes with a vector "
                                 "— nothing written")
            state = compare(session, q, ids, matrix)
            print("  the graph against the file: " + json.dumps(state), flush=True)
            if state["vector_sizes_on_the_graph"] != [matrix.shape[1]]:
                raise SystemExit("the graph's vectors are not of the file's size — nothing written")
            carried = (state["nodes_whose_sums_differ"] == 0
                       and state["sample_rows_equal_as_float32"] == state["sample"])
            if args.mode == "verify":
                if not carried:
                    raise SystemExit("the graph does not carry the file's vectors")
                print(f"  every one of the {len(ids)} nodes carries the file's vector", flush=True)
            elif args.mode == "write":
                if carried:
                    print("  the graph already carries the file's vectors; nothing to write", flush=True)
                else:
                    args.keep.mkdir(parents=True, exist_ok=True)
                    kept = args.keep / f"{label.lower()}_{prop}_as_stored.npz"
                    if kept.exists():
                        raise SystemExit(f"{kept} exists — nothing is overwritten, nothing written")
                    stored = read_vectors(session, q, names)
                    np.savez(kept, ids=np.array(names, dtype=object), matrix=stored)
                    back = np.load(kept, allow_pickle=True)
                    if list(back["ids"]) != names or not np.array_equal(back["matrix"], stored):
                        raise SystemExit("the kept file does not read back equal — nothing written")
                    manifest = {"database": DATABASE, "property": f"{label}.{prop}", "n": len(names),
                                "matrix_shape": list(stored.shape), "matrix_dtype": str(stored.dtype),
                                "matrix_sha256": hashlib.sha256(stored.tobytes()).hexdigest(),
                                "file_sha256": sha256_file(kept),
                                "replaced_by": str(args.vectors).replace("\\", "/"),
                                "replaced_by_sha256": sha256_file(args.vectors),
                                "read_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                    kept.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2),
                                                                  encoding="utf-8")
                    print(f"  kept what the graph carried: {kept} {stored.shape} {stored.dtype} "
                          f"sha256 {manifest['matrix_sha256'][:16]}", flush=True)
                    written = 0
                    for i in range(0, len(ids), WRITE_BATCH):
                        rows = [{"id": name, "vector": row.tolist()} for name, row in
                                zip(ids[i:i + WRITE_BATCH], matrix[i:i + WRITE_BATCH].astype(np.float64))]
                        n = session.run(q["write"], rows=rows).single()["n"]
                        if n != len(rows):
                            raise SystemExit(f"batch at row {i}: {len(rows)} rows set {n} nodes — "
                                             f"stopped; run write again")
                        written += n
                        print(f"  {written} of {len(ids)} nodes set", flush=True)
                    session.run("CALL db.awaitIndexes()").consume()
                    after = compare(session, q, ids, matrix)
                    print("  after: " + json.dumps(after), flush=True)
                    if (after["nodes_whose_sums_differ"]
                            or after["sample_rows_equal_as_float32"] != after["sample"]):
                        raise SystemExit("the graph does not carry the file's vectors after the write")
    finally:
        driver.close()
    print(f"done ({time.perf_counter() - started:.0f}s).", flush=True)


if __name__ == "__main__":
    main()
