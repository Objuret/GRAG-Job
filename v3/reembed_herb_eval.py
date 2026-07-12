"""Embed the herb-eval graph's semantic layer with the v3 embedder (nemotron).

The graph holds no content — structure, weights, and embeddings only. Two vector
families make up the semantic layer, both nemotron ("passage" side):

  1. Tag embeddings — the tag IS its embedding: each `:Tag` name, bare (no
     context), as `t.emb` under the `tag_emb` cosine index.
  2. Chunk-description embeddings — each chunk's short description as
     `c.desc_emb` under the `chunk_desc_emb` cosine index. The description TEXT
     lives only in the pre-cleanup sibling `herb-eval-backup` (read-only); it is
     used solely as embedding input, so no text enters the live graph.

At question time the arm mirrors both on the "query" side: prompt tags kNN the
tag index (grounding), the prompt's need description is scored against
`desc_emb` (the description-similarity weight in the chunk score chain).

Idempotent + resumable: a family whose vectors are already complete is skipped
(no NIM calls re-burned); indexes are dropped and recreated so a dimension
change always rebuilds them. Legacy layouts (the per-facet `emb_<facet>` props /
`tag_emb_<facet>` indexes from the e5 build) are removed if present.

Run with Neo4j up and NVIDIA_API_KEY + NEO4J_PASSWORD in v3/.env:

    python reembed_herb_eval.py
    python run.py --arm artefact_v1 --set gold -k 50

Targets NEO4J_DATABASE (default herb-eval); description text comes from
HERB_BACKUP_DATABASE (default herb-eval-backup).
"""
from __future__ import annotations

import os
import time

from pipelines.artefact_v1 import DATABASE, RUN_ID, _driver, _readable
from pipelines.vector import EMBED_MODEL, _embed

BACKUP_DATABASE = os.environ.get("HERB_BACKUP_DATABASE", "herb-eval-backup")
WRITE_BATCH = 500

LEGACY_FACET_INDEXES = (
    "tag_emb_topic", "tag_emb_entities", "tag_emb_activity",
    "tag_emb_temporal", "tag_emb_evidence", "tag_emb_all",
)
LEGACY_FACET_PROPS = (
    "emb_topic", "emb_entities", "emb_activity",
    "emb_temporal", "emb_evidence", "emb_all", "embedding_model",
)


def _vector_index(s, name: str, label: str, prop: str, dim: int) -> None:
    """Drop + recreate one cosine vector index — a re-run after a dimension
    change must rebuild, never silently keep a stale-dim index."""
    s.run(f"DROP INDEX {name} IF EXISTS").consume()
    s.run(
        f"CREATE VECTOR INDEX {name} FOR (n:{label}) ON (n.{prop}) "
        f"OPTIONS {{ indexConfig: {{ `vector.dimensions`: {dim}, "
        f"`vector.similarity_function`: 'cosine' }} }}").consume()


def _write_vectors(s, cypher: str, rows: list) -> None:
    for i in range(0, len(rows), WRITE_BATCH):
        s.run(cypher, rows=rows[i:i + WRITE_BATCH]).consume()


def embed_tags(s) -> int:
    """Tag names, bare, one vector per tag reachable through the arm's tagging
    run -> `t.emb` + the `tag_emb` index. Skipped when already complete."""
    names = [r["name"] for r in s.run(
        "MATCH (:Chunk)-[r:HAS_TAG]->(t:Tag) WHERE r.run_id = $runId "
        "RETURN DISTINCT t.name AS name", runId=RUN_ID)]
    if not names:
        raise SystemExit(f"no :Tag reachable via HAS_TAG run_id={RUN_ID!r} in {DATABASE!r}")
    done = s.run("MATCH (t:Tag) WHERE t.emb IS NOT NULL RETURN count(t) AS c").single()["c"]
    if done == len(names):
        dim = s.run("MATCH (t:Tag) WHERE t.emb IS NOT NULL "
                    "RETURN size(t.emb) AS d LIMIT 1").single()["d"]
        print(f"tags: {done} vectors already present (dim={dim}) — skipping embed")
        _vector_index(s, "tag_emb", "Tag", "emb", int(dim))
        return int(dim)

    print(f"embedding {len(names)} tag names with {EMBED_MODEL} …")
    mat, calls, tokens, secs = _embed([_readable(n) for n in names], "passage")
    dim = int(mat.shape[1])
    print(f"  dim={dim}, {calls} calls, {tokens} tokens, {secs:.0f}s")
    _write_vectors(s, "UNWIND $rows AS row MATCH (t:Tag {name: row.name}) SET t.emb = row.emb",
                   [{"name": n, "emb": mat[i].tolist()} for i, n in enumerate(names)])
    _vector_index(s, "tag_emb", "Tag", "emb", dim)
    return dim


def embed_chunk_descriptions(s, backup) -> int:
    """Each chunk's description (text read from the backup, embedding input
    only) -> `c.desc_emb` + the `chunk_desc_emb` index. Every live chunk must
    have a description in the backup — a chunk without one would be invisible
    to the description channel, so that fails loud."""
    live_ids = {r["cid"] for r in s.run("MATCH (c:Chunk) RETURN c.chunk_id AS cid")}
    rows = [dict(r) for r in backup.run(
        "MATCH (c:Chunk) WHERE c.description IS NOT NULL "
        "RETURN c.chunk_id AS cid, c.description AS description")]
    by_id = {r["cid"]: r["description"] for r in rows}
    missing = sorted(live_ids - set(by_id))
    if missing:
        raise SystemExit(
            f"{len(missing)} live chunk(s) have no description in {BACKUP_DATABASE!r} "
            f"(e.g. {missing[:5]}) — they would be invisible to the description channel")

    done = s.run("MATCH (c:Chunk) WHERE c.desc_emb IS NOT NULL RETURN count(c) AS c").single()["c"]
    if done == len(live_ids):
        dim = s.run("MATCH (c:Chunk) WHERE c.desc_emb IS NOT NULL "
                    "RETURN size(c.desc_emb) AS d LIMIT 1").single()["d"]
        print(f"chunk descriptions: {done} vectors already present (dim={dim}) — skipping embed")
        _vector_index(s, "chunk_desc_emb", "Chunk", "desc_emb", int(dim))
        return int(dim)

    cids = sorted(live_ids)
    print(f"embedding {len(cids)} chunk descriptions with {EMBED_MODEL} …")
    mat, calls, tokens, secs = _embed([by_id[c] for c in cids], "passage")
    dim = int(mat.shape[1])
    print(f"  dim={dim}, {calls} calls, {tokens} tokens, {secs:.0f}s")
    _write_vectors(s, "UNWIND $rows AS row MATCH (c:Chunk {chunk_id: row.cid}) "
                      "SET c.desc_emb = row.emb",
                   [{"cid": c, "emb": mat[i].tolist()} for i, c in enumerate(cids)])
    _vector_index(s, "chunk_desc_emb", "Chunk", "desc_emb", dim)
    return dim


def drop_legacy(s) -> None:
    for idx in LEGACY_FACET_INDEXES:
        s.run(f"DROP INDEX {idx} IF EXISTS").consume()
    s.run("MATCH (t:Tag) REMOVE t." + ", t.".join(LEGACY_FACET_PROPS)).consume()


def main() -> None:
    t0 = time.perf_counter()
    drv = _driver()
    try:
        with drv.session(database=BACKUP_DATABASE) as backup, \
                drv.session(database=DATABASE) as s:
            tag_dim = embed_tags(s)
            desc_dim = embed_chunk_descriptions(s, backup)
            if tag_dim != desc_dim:
                raise SystemExit(
                    f"dimension mismatch: tag_emb dim={tag_dim} vs chunk_desc_emb "
                    f"dim={desc_dim} — re-run after clearing the stale family")
            drop_legacy(s)
            s.run("CALL db.awaitIndexes()").consume()
        print(f"done — tag_emb + chunk_desc_emb ready (dim={tag_dim}, "
              f"{time.perf_counter() - t0:.0f}s).")
    finally:
        drv.close()


if __name__ == "__main__":
    main()
