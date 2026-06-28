"""artefact/index.py — the in-memory query engine's view of the lean graph.

Holds the tag-embedding matrix (mean-centered for corpus-relative geometry,
plus the original L2-normalized matrix for comparison) and the chunk-id → Chunk
map (references + attributes + on-demand text resolution). The phrase text is
loaded (row i -> phrase) for inspection/display, but is not used by routing —
the index carries phrase row → chunk mappings so the engine never needs the
string to route. The phrase text itself lives in `output/tags/Salesforce__HERB.jsonl`,
re-embeddable from `embed_tags.py`.

Mean-centering is pass 1 of the corpus-relative geometry transform (design
§13): subtract the matrix's mean vector, re-L2-normalize. The original matrix
is retained alongside so ablations can compare centered vs raw.

linked to: embed_tags (writes the npz); graph_store (writes the DB);
pipelines.artefact (the future query-engine consumer)
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .chunk import Chunk, chunk_dataset, load_key

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

    # Verify the npz's chunk set AND per-chunk kind match the chunker's output
    # — a stale npz built against a different corpus or a divergent kind
    # vocabulary would otherwise route against the wrong chunks silently.
    chunks = chunk_dataset(Path(data_root) / "Salesforce__HERB", Path(data_root),
                           load_key(Path(key_path)))
    chunks_by_id = {c.chunk_id: c for c in chunks}
    npz_cids = list(tags["chunk_ids"])
    ds_cids = set(chunks_by_id)
    npz_cid_set = set(npz_cids)
    if npz_cid_set != ds_cids:
        missing = ds_cids - npz_cid_set
        extra = npz_cid_set - ds_cids
        raise RuntimeError(
            f"tags npz chunk set diverges from chunker: "
            f"{len(missing)} chunks missing from npz, {len(extra)} extra in npz — "
            f"re-run embed_tags.py over the current tags")
    for j, cid in enumerate(npz_cids):
        c = chunks_by_id.get(cid)
        if c is not None and c.kind != tags["chunk_kinds"][j]:
            raise RuntimeError(
                f"tags npz kind diverges from chunker at chunk {cid!r}: "
                f"npz={tags['chunk_kinds'][j]!r} chunker={c.kind!r} — "
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


def _load_verified_doc(relpath: str, sha256: str, data_root: Path,
                       cache: dict | None = None) -> dict:
    """Read + hash-verify + parse a product JSON once, memoized in `cache` so
    the per-question loop over k chunks (each with multiple refs into the same
    file) reads each file at most once. Fails loud on a hash mismatch — the
    graph was built against `sha256`; a drifted file is refused, never served.
    A `cache` of None allocates a fresh dict, so callers without one still
    behave correctly (just without cross-call reuse)."""
    c = cache if cache is not None else {}
    key = (relpath, sha256)
    doc = c.get(key)
    if doc is not None:
        return doc
    path = Path(data_root) / relpath
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != sha256:
        raise RuntimeError(
            f"HASH MISMATCH for {relpath}: graph built against "
            f"{sha256[:12]}…, on-disk is {actual[:12]}…. "
            f"Refusing to serve drifted content.")
    doc = json.loads(path.read_text(encoding="utf-8"))
    c[key] = doc
    if cache is not None:
        cache.update(c)
    return doc


def _pointer_get(doc, pointer: str):
    """RFC 6901 get into `doc` (loud on a miss) — a local copy so the per-ref
    hot path doesn't round-trip through the resolver prototype's per-call
    file read."""
    cur = doc
    if pointer == "":
        return cur
    for raw in pointer.split("/")[1:]:
        tok = raw.replace("~1", "/").replace("~0", "~")
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


def resolve_chunk_text(chunk: Chunk, data_root: Path, cache: dict | None = None) -> str:
    """Resolve a chunk's references in order, hash-verified, and concatenate
    them into the chunk's source view. The containing file is read + hashed +
    parsed once (memoized in `cache`) and each ref is sliced in-memory, so a
    chunk with N refs into one file costs one file read, not N. Non-string
    resolved values (impossible for declared content leaves, possible if a
    pointer lands on a scalar) raise — content refs are text.

    A chunk's refs are scheme-homogeneous (chunk.py: `_refs_json` emits all
    `json_pointer`; `_split_leaves`'s char_span branch emits all `char_span`).
    char_span fragments tile their leaf exactly (lossless) — joining with a
    separator would corrupt offsets, so char_span chunks join with the empty
    string; json_pointer chunks (records, conversation, prose-leaf records)
    join with "\n"."""
    doc = _load_verified_doc(chunk.relpath, chunk.sha256, data_root, cache)
    sep = "" if chunk.refs and chunk.refs[0].scheme == "char_span" else "\n"
    parts: list[str] = []
    for r in chunk.refs:
        if r.scheme == "json_pointer":
            val = _pointer_get(doc, r.address)
        elif r.scheme == "char_span":
            ptr, start, end = r.address
            leaf = _pointer_get(doc, ptr)
            if not isinstance(leaf, str):
                raise TypeError(
                    f"chunk {chunk.chunk_id} char_span target {ptr!r} is not a string")
            val = leaf[start:end]
        else:
            raise ValueError(f"unknown ref scheme: {r.scheme!r}")
        if not isinstance(val, str):
            raise TypeError(
                f"chunk {chunk.chunk_id} ref {r!r} resolved to non-string "
                f"({type(val).__name__}) — content refs must land on text")
        parts.append(val)
    return sep.join(parts)


def _record_pointer(ref) -> str:
    """The `/collection/index` pointer to the record a ref lives in. A ref's
    address is either a json_pointer (`/slack/0/Message/User/text`) or a
    char_span `(pointer, start, end)` whose pointer is a leaf
    (`/documents/0/content`). The record is always the first two path
    components — the collection root and the record index — so slicing back to
    them lands on the record dict that carries the artifact `id`."""
    addr = ref.address
    ptr = addr if isinstance(addr, str) else addr[0]
    toks = ptr.strip("/").split("/")
    if len(toks) < 2:
        raise ValueError(
            f"ref pointer {ptr!r} has no collection/record prefix — "
            f"chunk covers a leaf that is not inside a record array")
    return f"/{toks[0]}/{toks[1]}"


def chunk_artifact_ids(chunk: Chunk, data_root: Path, cache: dict | None = None) -> list[str]:
    """The deduped artifact `id` strings for every record a chunk covers. For
    each ref, walk its pointer back to the containing record (`/collection/
    index`), resolve that record from the raw file (hash-verified, memoized in
    `cache`), and read its top-level `id` field. Fails loud on a missing `id`
    (a chunk covers records that should carry ids) or a hash/pointer mismatch.

    The ids land in the same space the gold citations and the other arms'
    context_ids use, so RAGAS's citation-based context precision/recall compare
    like-for-like."""
    doc = _load_verified_doc(chunk.relpath, chunk.sha256, data_root, cache)
    ids: list[str] = []
    seen: set[str] = set()
    for r in chunk.refs:
        rec_ptr = _record_pointer(r)
        rec = _pointer_get(doc, rec_ptr)
        if not isinstance(rec, dict):
            raise TypeError(
                f"chunk {chunk.chunk_id} record {rec_ptr!r} resolved to "
                f"{type(rec).__name__}, not a record dict — cannot read `id`")
        aid = rec.get("id")
        if aid is None:
            raise RuntimeError(
                f"chunk {chunk.chunk_id} record {rec_ptr!r} has no `id` field — "
                f"every artifact record carries an id")
        if aid not in seen:
            seen.add(aid)
            ids.append(str(aid))
    return ids


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
