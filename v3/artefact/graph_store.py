"""Materialize the artefact graph into Neo4j: `Source -[:CONTAINS]-> File
-[:CONTAINS]-> Chunk -[:HAS_TAG]-> Tag` (design §7, §14.1). A fresh, clean
database — never herb-eval (the superseded, oracle-contaminated v1 build).

References, not copies: a Chunk node carries its raw references + materialized
path + kind, never the source text — the tagger resolves text on demand. Each
persisted reference is self-resolving: it carries the resolver contract
`{file_path, sha256, scheme, address}`, so `resolver_prototype.resolve` turns
it straight back into hash-verified source content with nothing else looked up.

A Tag node IS its embedding (design §14.1: the contextual phrase IS the node,
carrying the embedding). The phrase text stays OUT of the graph — it lives in
`output/tags/Salesforce__HERB.jsonl`, re-embeddable from `embed_tags.py`. Tags
are per-chunk emissions (design §7): each (chunk, phrase-row) pair is its own
node, so `tag_id = "{chunk_id}#{position_in_chunk}"`. The full embedding vector
rides the node as a `float[]` property so the DB is self-contained for
inspection; the in-memory query engine loads vectors from the npz for speed.

A `:BuildMeta` completion sentinel carrying `chunk_count` and `tag_count` is
written LAST, after every chunk and tag is in: its presence means the ingest
finished, so a partial or crashed run is detectable instead of silently serving
a truncated graph.

Connection comes from the environment (fail loud, no silent defaults for the
secret):  NEO4J_URI (default neo4j://localhost:7687), NEO4J_USER (default
neo4j), NEO4J_PASSWORD (required).

Run the build (after `export NEO4J_PASSWORD=...`):
    python -m artefact.graph_store
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np
from neo4j import GraphDatabase
from tqdm import tqdm

from .index import TAGS_NPZ_GLOB, find_tags_npz

DB = "herb-v3"
_SAFE_DB = re.compile(r"^[A-Za-z][A-Za-z0-9.-]{2,62}$")

TAG_EMBED_BATCH = 500


def driver():
    pw = os.environ.get("NEO4J_PASSWORD")
    if not pw:
        raise RuntimeError("NEO4J_PASSWORD is not set — export it before building the graph.")
    uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    return GraphDatabase.driver(uri, auth=(user, pw))


def ensure_database(drv, name: str = DB) -> None:
    if not _SAFE_DB.match(name):
        raise ValueError(f"unsafe database name: {name!r}")
    with drv.session(database="system") as s:
        s.run(f"CREATE DATABASE `{name}` IF NOT EXISTS WAIT")


CONSTRAINTS = [
    "CREATE CONSTRAINT source_name IF NOT EXISTS FOR (s:Source) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT file_id IF NOT EXISTS FOR (f:File) REQUIRE f.file_id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
    "CREATE CONSTRAINT tag_id IF NOT EXISTS FOR (t:Tag) REQUIRE t.tag_id IS UNIQUE",
]

INGEST = """
UNWIND $rows AS row
MERGE (src:Source {name: $dataset})
MERGE (f:File {file_id: row.file_id})
  SET f.relpath = row.relpath, f.sha256 = row.sha256
MERGE (src)-[:CONTAINS]->(f)
MERGE (ch:Chunk {chunk_id: row.chunk_id})
  SET ch.path = row.path, ch.kind = row.kind,
      ch.est_tokens = row.est_tokens, ch.refs = row.refs
MERGE (f)-[:CONTAINS]->(ch)
"""

# One Tag node per (chunk, position-in-chunk). The vector rides as `embedding`
# (float[]); `embedding_row` indexes the npz matrix; `embedding_dim` is the
# vector length. The chunk is looked up by chunk_id (the npz's chunk order is
# the tags-jsonl order, not the scan order, so we MERGE rather than assume).
INGEST_TAGS = """
UNWIND $rows AS row
MATCH (ch:Chunk {chunk_id: row.chunk_id})
MERGE (t:Tag {tag_id: row.tag_id})
  SET t.embedding_row = row.embedding_row,
      t.embedding_dim = row.embedding_dim,
      t.embedding = row.embedding
MERGE (ch)-[:HAS_TAG]->(t)
"""


def _resolver_ref(c, r) -> dict:
    """A chunk reference in the resolver's self-resolving contract
    (`resolver_prototype.resolve`): the file's relpath + sha256 travel with each
    ref, so resolution hash-verifies against the chunk's own file."""
    return {
        "file_path": c.relpath,
        "sha256": c.sha256,
        "scheme": r.scheme,
        "address": r.address,
    }


def _row(c) -> dict:
    return {
        "file_id": c.file_id,
        "relpath": c.relpath,
        "sha256": c.sha256,
        "chunk_id": c.chunk_id,
        "path": list(c.path),
        "kind": c.kind,
        "est_tokens": c.est_tokens,
        # nested maps can't be node props — store each self-resolving ref as a
        # JSON string; resolving in order reproduces the chunk's source.
        "refs": [json.dumps(_resolver_ref(c, r)) for r in c.refs],
    }


def load_tags_index(npz_path: Path) -> dict:
    """Load the tags npz into the arrays the ingest needs. Returns the matrix
    as float32, the chunk-id list, and chunk_tag_rows (chunk j -> [phrase row
    indices]). Fails loud on shape mismatch."""
    z = np.load(npz_path, allow_pickle=True)
    matrix = np.ascontiguousarray(z["matrix"], dtype=np.float32)
    chunk_ids = [str(c) for c in z["chunk_ids"]]
    chunk_tag_rows = [list(r) for r in z["chunk_tag_rows"]]
    if matrix.ndim != 2:
        raise RuntimeError(f"tags matrix is not 2-D: shape {matrix.shape}")
    if len(chunk_ids) != len(chunk_tag_rows):
        raise RuntimeError(
            f"tags npz misaligned: {len(chunk_ids)} chunk_ids vs "
            f"{len(chunk_tag_rows)} chunk_tag_rows")
    return {
        "matrix": matrix,
        "chunk_ids": chunk_ids,
        "chunk_tag_rows": chunk_tag_rows,
    }


def _tag_rows(tags: dict) -> list[dict]:
    """Build one UNWIND row per (chunk, position-in-chunk) tag emission.
    `embedding` is a Python list of floats (Neo4j stores it as `float[]`).
    `tag_id` is `{chunk_id}#{position}` — unique per emission (design §7)."""
    matrix = tags["matrix"]
    out = []
    for j, cid in enumerate(tags["chunk_ids"]):
        rows = tags["chunk_tag_rows"][j]
        for pos, phrase_row in enumerate(rows):
            vec = matrix[int(phrase_row)].tolist()
            out.append({
                "chunk_id": cid,
                "tag_id": f"{cid}#{pos}",
                "embedding_row": int(phrase_row),
                "embedding_dim": int(matrix.shape[1]),
                "embedding": vec,
            })
    return out


SENTINEL = (
    "MERGE (m:BuildMeta {dataset: $dataset}) "
    "SET m.chunk_count = $chunk_count, m.tag_count = $tag_count, m.database = $db"
)


def ingest(drv, chunks, dataset: str, tags: dict | None, name: str = DB, batch: int = 1000) -> None:
    rows = [_row(c) for c in chunks]
    with drv.session(database=name) as s:
        s.run("MATCH (n) DETACH DELETE n")  # deterministic rebuild — clean slate each run
        for stmt in CONSTRAINTS:
            s.run(stmt)
        for i in range(0, len(rows), batch):
            s.run(INGEST, rows=rows[i : i + batch], dataset=dataset)
            print(f"  ingested {min(i + batch, len(rows))}/{len(rows)} chunks")

        tag_count = 0
        if tags is not None:
            tag_rows = _tag_rows(tags)
            tag_count = len(tag_rows)
            for i in tqdm(range(0, len(tag_rows), TAG_EMBED_BATCH),
                          desc="ingesting tags", unit="batch"):
                s.run(INGEST_TAGS, rows=tag_rows[i : i + TAG_EMBED_BATCH])
        # completion sentinel LAST — its presence means the ingest finished
        s.run(SENTINEL, dataset=dataset, chunk_count=len(rows),
              tag_count=tag_count, db=name)


def build(dataset_dir: Path, data_root: Path, key_path: Path, dataset: str,
          name: str = DB, tags_glob: str = TAGS_NPZ_GLOB) -> tuple[int, int]:
    from .chunk import chunk_dataset, load_key
    chunks = chunk_dataset(dataset_dir, data_root, load_key(key_path))
    npz_path = find_tags_npz(tags_glob)
    print(f"loading tag embeddings from {npz_path}…")
    tags = load_tags_index(npz_path)
    print(f"  {len(tags['chunk_ids'])} tagged chunks, "
          f"{sum(len(r) for r in tags['chunk_tag_rows'])} tag emissions, "
          f"matrix {tags['matrix'].shape}")
    # Fail loud on a stale npz: every chunk_id in the npz must match a chunk the
    # chunker produced, else INGEST_TAGS's MATCH would silently drop tag rows
    # and the sentinel would lie about the count.
    chunk_ids = {c.chunk_id for c in chunks}
    npz_cids = set(tags["chunk_ids"])
    if npz_cids != chunk_ids:
        missing = chunk_ids - npz_cids
        extra = npz_cids - chunk_ids
        raise RuntimeError(
            f"tags npz chunk set diverges from chunker: "
            f"{len(missing)} chunks missing from npz, {len(extra)} extra in npz — "
            f"re-run embed_tags.py over the current tags")
    drv = driver()
    try:
        print(f"creating database {name!r} (if absent)…")
        ensure_database(drv, name)
        print(f"ingesting {len(chunks)} chunks + tags into {name!r}…")
        ingest(drv, chunks, dataset, tags, name)
    finally:
        drv.close()
    return len(chunks), sum(len(r) for r in tags["chunk_tag_rows"])


def report_counts(drv, dataset: str, name: str = DB) -> dict:
    """Print + return node/edge counts for inspection. Fails loud if the
    sentinel is missing (the ingest did not finish). The sentinel is keyed by
    `dataset` (e.g. "Salesforce__HERB"), not the DB name."""
    with drv.session(database=name) as s:
        meta = s.run("MATCH (m:BuildMeta {dataset: $d}) RETURN m", d=dataset).single()
        if meta is None:
            raise RuntimeError(
                f"no :BuildMeta for dataset {dataset!r} in {name!r} — ingest did not complete")
        counts = {}
        for label, cy in (("Source", "MATCH (n:Source) RETURN count(n) AS c"),
                          ("File", "MATCH (n:File) RETURN count(n) AS c"),
                          ("Chunk", "MATCH (n:Chunk) RETURN count(n) AS c"),
                          ("Tag", "MATCH (n:Tag) RETURN count(n) AS c"),
                          ("CONTAINS", "MATCH ()-[r:CONTAINS]->() RETURN count(r) AS c"),
                          ("HAS_TAG", "MATCH ()-[r:HAS_TAG]->() RETURN count(r) AS c")):
            counts[label] = int(s.run(cy).single()["c"])
    print("graph counts:")
    for k, v in counts.items():
        print(f"  {k:10s} {v}")
    return counts


def report_db_size(name: str = DB) -> str:
    """Best-effort on-disk size of the Neo4j database directory (local install
    layout: <NEO4J_HOME>/data/databases/<name>). Returns a human string, or
    'unknown' if the path can't be found — size is for inspection, not a
    correctness signal."""
    home = os.environ.get("NEO4J_HOME")
    if not home:
        return "unknown (set NEO4J_HOME to enable)"
    p = Path(home) / "data" / "databases" / name
    if not p.is_dir():
        return f"unknown (no dir at {p})"
    total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return f"{total / (1 << 20):.1f} MB ({p})"


if __name__ == "__main__":
    root = Path("data/corpus")
    dataset_name = "Salesforce__HERB"
    n_chunks, n_tags = build(
        dataset_dir=root / dataset_name,
        data_root=root,
        key_path=Path("artefact/keys/Salesforce__HERB.yaml"),
        dataset=dataset_name,
    )
    print(f"done — {n_chunks} chunks, {n_tags} tags in {DB}.")
    drv = driver()
    try:
        report_counts(drv, dataset=dataset_name)
    finally:
        drv.close()
    print(f"db size: {report_db_size()}")
