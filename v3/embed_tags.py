"""embed_tags.py — precompute the artefact arm's tag-embedding index.

The lean graph: the tag node IS its embedding (no phrase text in the graph —
the phrase lives in the tags jsonl, re-embeddable from here). One matrix row per
unique phrase; a phrase that recurs on several chunks embeds once and maps to
all of them.

Run once after tagging (and again only if the embedder or tags change):

    python embed_tags.py            # -> output/artefact_index/tags.npz

Embeds every unique phrase as input_type="passage" in batched NIM calls and
writes one npz: aligned `phrases` + L2-normalised `matrix` (row i = phrase i) +
`chunk_ids` + `chunk_tag_rows` (chunk j -> [phrase rows]) + `phrase_to_chunks`
(phrase i -> [chunk positions in chunk_ids]). Content-addressed: a re-run over
unchanged tags loads instead of re-embedding.

linked to: pipelines.artefact.prepare_over_corpus (the consumer)
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import os
import time
from pathlib import Path

import numpy as np

import nim
from pipelines.vector import EMBED_MODEL, _embed

TAGS_PATH = Path("output/tags/Salesforce__HERB.jsonl")
INDEX_DIR = Path("output/artefact_index")


def _load_tags(path: Path) -> list[dict]:
    """Read the tags jsonl -> records [{chunk_id, kind, tags: [...]}]."""
    recs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        recs.append(json.loads(line))
    return recs


def _cache_path(tags_path: Path, phrases: list[str]) -> Path:
    """Content-addressed cache: any change to the model, the tags file, or the
    deduped phrase set yields a new key and forces a re-embed."""
    h = hashlib.sha256(EMBED_MODEL.encode())
    h.update(len(phrases).to_bytes(8, "big"))
    for p in phrases:
        b = p.encode()
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return INDEX_DIR / f"tags_{EMBED_MODEL.split('/')[-1]}_{h.hexdigest()[:16]}.npz"


def main() -> None:
    nim.require_key()
    recs = _load_tags(TAGS_PATH)
    print(f"loaded {len(recs)} tagged chunks from {TAGS_PATH}")

    # Dedup phrases: one row per unique phrase (whitespace-stripped, case kept).
    phrase_to_row: dict[str, int] = {}
    chunk_ids: list[str] = []
    chunk_kinds: list[str] = []
    chunk_tag_rows: list[list[int]] = []
    phrase_to_chunks: list[list[int]] = []
    for r in recs:
        cid = r["chunk_id"]
        rows: list[int] = []
        for tag in r.get("tags", []):
            t = tag.strip()
            if not t:
                continue
            if t not in phrase_to_row:
                phrase_to_row[t] = len(phrase_to_row)
                phrase_to_chunks.append([])
            row = phrase_to_row[t]
            rows.append(row)
            phrase_to_chunks[row].append(len(chunk_ids))
        chunk_ids.append(cid)
        chunk_kinds.append(r.get("kind", ""))
        chunk_tag_rows.append(rows)

    phrases = list(phrase_to_row.keys())
    n_unique = len(phrases)
    total_tags = sum(len(r) for r in chunk_tag_rows)
    print(f"  {n_unique} unique phrases ({total_tags} tag instances across {len(chunk_ids)} chunks)")

    cache = _cache_path(TAGS_PATH, phrases)
    if cache.is_file():
        z = np.load(cache, allow_pickle=True)
        print(f"cache hit -> {cache}")
        print(f"  matrix {z['matrix'].shape}, phrases {len(z['phrases'])}, chunks {len(z['chunk_ids'])}")
        return

    t0 = time.perf_counter()
    matrix, calls, tokens_in, tokens_out, secs = _embed(phrases, "passage")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=INDEX_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            np.savez(
                f,
                matrix=matrix,
                phrases=np.array(phrases, dtype=object),
                chunk_ids=np.array(chunk_ids, dtype=object),
                chunk_kinds=np.array(chunk_kinds, dtype=object),
                chunk_tag_rows=np.array(chunk_tag_rows, dtype=object),
                phrase_to_chunks=np.array(phrase_to_chunks, dtype=object),
                model=np.array(EMBED_MODEL),
                tags_path=np.array(str(TAGS_PATH)),
            )
        os.replace(tmp, cache)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    print(f"embedded {n_unique} phrases ({EMBED_MODEL}) -> {cache}")
    print(f"  matrix {matrix.shape}, {calls} request(s), in={tokens_in} out={tokens_out} tokens, {secs:.1f}s")
    print(f"  build wall {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
