"""artefact/index.py — the in-memory query engine's view of the lean graph.

Holds the tag-embedding matrix (mean-centered for corpus-relative geometry,
plus the original L2-normalized matrix for comparison) and the chunk-id → Chunk
map (references + attributes + on-demand text resolution). The phrase text
itself is NOT loaded here — it lives in `output/tags/Salesforce__HERB.jsonl`,
re-embeddable from `embed_tags.py`; the index carries phrase row → chunk
mappings so the engine never needs the string to route.

Mean-centering is pass 1 of the corpus-relative geometry transform (design
§13): subtract the matrix's mean vector, re-L2-normalize. The original matrix
is retained alongside so ablations can compare centered vs raw.

linked to: embed_tags (writes the npz); graph_store (writes the DB);
pipelines.artifact (the future query-engine consumer)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .chunk import Chunk, chunk_dataset, load_key
from .resolver_prototype import resolve as _resolve_ref

TAGS_NPZ_GLOB = "output/artefact_index/tags_*.npz"


@dataclass
class PreparedIndex:
    """The in-memory artefact index: tag embeddings + chunk metadata + the
    chunk-id → Chunk map for reference resolution. Tag embeddings are kept in
    two forms — `matrix` (mean-centered, re-L2-normalized) for corpus-relative
    retrieval, and `matrix_raw` (the original L2-normalized embeddings) for
    comparison / ablation."""

    matrix: "np.ndarray"              # [n_phrases, d] float32, mean-centered + re-normalized
    matrix_raw: "np.ndarray"          # [n_phrases, d] float32, L2-normalized (un-centered)
    mean_vector: "np.ndarray"         # [d] float32 — the center subtracted
    phrases: list = field(default_factory=list)           # row i -> phrase text
    chunk_ids: list = field(default_factory=list)         # chunk j -> chunk_id
    chunk_kinds: list = field(default_factory=list)       # chunk j -> kind
    chunk_tag_rows: list = field(default_factory=list)    # chunk j -> [phrase row indices]
    phrase_to_chunks: list = field(default_factory=list)  # phrase i -> [chunk positions]
    chunks_by_id: dict = field(default_factory=dict)      # chunk_id -> Chunk
    embed_dim: int = 0
    load_time_s: float = 0.0

    def __repr__(self) -> str:
        return (
            f"PreparedIndex(phrases={len(self.phrases)}, chunks={len(self.chunk_ids)}, "
            f"tag_emissions={sum(len(r) for r in self.chunk_tag_rows)}, "
            f"dim={self.embed_dim}, matrix={self.matrix.shape}, "
            f"chunks_by_id={len(self.chunks_by_id)}, "
            f"load={self.load_time_s:.2f}s)"
        )


def find_tags_npz(glob: str = TAGS_NPZ_GLOB) -> Path:
    """Locate the tags embedding npz. Fails loud if absent or ambiguous."""
    matches = sorted(Path(".").glob(glob))
    if not matches:
        raise FileNotFoundError(
            f"no tags npz matching {glob!r} — run `python embed_tags.py` (from v3/) first")
    if len(matches) > 1:
        raise RuntimeError(
            f"ambiguous tags npz: {len(matches)} matches {glob!r}: "
            + ", ".join(str(m) for m in matches)
            + " — remove the stale one")
    return matches[0]


def _load_tags_npz(npz_path: Path) -> dict:
    z = np.load(npz_path, allow_pickle=True)
    matrix = np.ascontiguousarray(z["matrix"], dtype=np.float32)
    if matrix.ndim != 2:
        raise RuntimeError(f"tags matrix is not 2-D: shape {matrix.shape}")
    return {
        "matrix": matrix,
        "phrases": list(z["phrases"]),
        "chunk_ids": [str(c) for c in z["chunk_ids"]],
        "chunk_kinds": [str(k) for k in z["chunk_kinds"]],
        "chunk_tag_rows": [list(r) for r in z["chunk_tag_rows"]],
        "phrase_to_chunks": [list(c) for c in z["phrase_to_chunks"]],
    }


def _mean_center(matrix: "np.ndarray") -> tuple["np.ndarray", "np.ndarray"]:
    """Subtract the corpus mean vector, re-L2-normalize. Returns
    (centered_matrix, mean_vector). A zero-norm row after centering is left at
    zero (the phrase sat exactly on the mean — no direction to point in)."""
    mean = matrix.mean(axis=0, keepdims=True).astype(np.float32)
    centered = matrix - mean
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    centered = centered / norms
    return centered.astype(np.float32), mean.reshape(-1).astype(np.float32)


def load_artefact_index(
    data_root: Path,
    key_path: Path,
    tags_npz_glob: str = TAGS_NPZ_GLOB,
) -> PreparedIndex:
    """Build the in-memory index: load the tags npz, mean-center the tag
    matrix, and load the chunk-id → Chunk map via `chunk_dataset`. Fails loud
    on a missing npz, a missing key, or a chunk-dataset/npz chunk-id
    mismatch."""
    t0 = time.perf_counter()
    npz_path = find_tags_npz(tags_npz_glob)
    tags = _load_tags_npz(npz_path)

    # Verify the npz's chunk set matches the chunker's output — a stale npz
    # built against a different corpus would otherwise route against the wrong
    # chunks silently.
    chunks = chunk_dataset(Path(data_root) / "Salesforce__HERB", Path(data_root),
                           load_key(Path(key_path)))
    chunks_by_id = {c.chunk_id: c for c in chunks}
    npz_cids = set(tags["chunk_ids"])
    ds_cids = set(chunks_by_id)
    if npz_cids != ds_cids:
        missing = ds_cids - npz_cids
        extra = npz_cids - ds_cids
        raise RuntimeError(
            f"tags npz chunk set diverges from chunker: "
            f"{len(missing)} chunks missing from npz, {len(extra)} extra in npz — "
            f"re-run embed_tags.py over the current tags")

    centered, mean = _mean_center(tags["matrix"])

    return PreparedIndex(
        matrix=centered,
        matrix_raw=tags["matrix"],
        mean_vector=mean,
        phrases=tags["phrases"],
        chunk_ids=tags["chunk_ids"],
        chunk_kinds=tags["chunk_kinds"],
        chunk_tag_rows=tags["chunk_tag_rows"],
        phrase_to_chunks=tags["phrase_to_chunks"],
        chunks_by_id=chunks_by_id,
        embed_dim=int(tags["matrix"].shape[1]),
        load_time_s=time.perf_counter() - t0,
    )


def resolve_chunk_text(chunk: Chunk, data_root: Path) -> str:
    """Resolve a chunk's references in order, hash-verified, and concatenate
    them into the chunk's source view. Each Ref rides as the resolver's
    self-resolving contract `{file_path, sha256, scheme, address}`; the
    resolver fails loud on a hash mismatch or a bad pointer. Non-string
    resolved values (impossible for declared content leaves, possible if a
    pointer lands on a scalar) raise — content refs are text."""
    parts: list[str] = []
    for r in chunk.refs:
        ref = {
            "file_path": chunk.relpath,
            "sha256": chunk.sha256,
            "scheme": r.scheme,
            "address": r.address,
        }
        val = _resolve_ref(ref, data_root=Path(data_root))
        if not isinstance(val, str):
            raise TypeError(
                f"chunk {chunk.chunk_id} ref {r!r} resolved to non-string "
                f"({type(val).__name__}) — content refs must land on text")
        parts.append(val)
    return "\n".join(parts)


# Cypher snippets for Neo4j Browser inspection of the built graph.
CYPHER_INSPECT = {
    "node_counts": "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label",
    "edge_counts": "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY type",
    "tag_count": "MATCH (t:Tag) RETURN count(t) AS tags",
    "tags_per_kind": (
        "MATCH (c:Chunk)-[:HAS_TAG]->(t:Tag) "
        "RETURN c.kind AS kind, count(t) AS tags ORDER BY kind"
    ),
    "tags_per_chunk_top": (
        "MATCH (c:Chunk)-[:HAS_TAG]->(t:Tag) "
        "RETURN c.chunk_id AS chunk_id, c.kind AS kind, count(t) AS tags "
        "ORDER BY tags DESC LIMIT 10"
    ),
    "sample_chunk_with_tags": (
        "MATCH (c:Chunk)-[:HAS_TAG]->(t:Tag) "
        "RETURN c.chunk_id AS chunk_id, c.kind AS kind, c.est_tokens AS tokens, "
        "       collect(t.tag_id)[..5] AS sample_tags, count(t) AS tag_count "
        "LIMIT 5"
    ),
    "spine_sample": (
        "MATCH (s:Source)-[:CONTAINS]->(f:File)-[:CONTAINS]->(c:Chunk)-[:HAS_TAG]->(t:Tag) "
        "RETURN s.name AS source, f.relpath AS file, c.chunk_id AS chunk, "
        "       c.kind AS kind, count(t) AS tags "
        "LIMIT 10"
    ),
    "build_meta": "MATCH (m:BuildMeta) RETURN m",
    "tag_dim_check": (
        "MATCH (t:Tag) RETURN t.embedding_dim AS dim, count(t) AS count "
        "ORDER BY dim"
    ),
}


if __name__ == "__main__":
    root = Path("data/corpus")
    idx = load_artefact_index(root, Path("artefact/keys/Salesforce__HERB.yaml"))
    print(idx)
    print(f"matrix centered: {idx.matrix.shape}, dtype={idx.matrix.dtype}, "
          f"|mean|={float(np.linalg.norm(idx.mean_vector)):.4f}")
    # sanity: a centered row should be unit norm
    sample_norm = float(np.linalg.norm(idx.matrix[0]))
    print(f"centered row 0 norm: {sample_norm:.6f} (should be ~1.0)")
    # sanity: resolve one chunk's text
    first_cid = idx.chunk_ids[0]
    chunk = idx.chunks_by_id[first_cid]
    text = resolve_chunk_text(chunk, root)
    print(f"chunk {first_cid} text: {len(text)} chars, head={text[:80]!r}")
