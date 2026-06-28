"""Smoke over the real HERB corpus (design §16: full pipeline on the whole
corpus is free — no LLM — so run it and look). Prints the prose-vs-short
classification, chunk counts by kind, the est-token distribution, and asserts
the two invariants: no record-chunk glues two distinct prose documents, and the
acceptance classification holds. Run from v3/:  python -m artefact.tests.smoke_chunk
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

from artefact.chunk import chunk_dataset, load_key
from artefact.probe import prose_leaf_pointers
from artefact.resolver_prototype import resolve
from artefact.scan import scan_dataset

DATA_ROOT = Path("data/corpus")
DATASET_DIR = DATA_ROOT / "Salesforce__HERB"
KEY_PATH = Path("artefact/keys/Salesforce__HERB.yaml")

# Piece 1 acceptance (real HERB): these classify prose vs short.
EXPECT_PROSE = {"/documents/*/content", "/meeting_transcripts/*/transcript"}
EXPECT_SHORT = {"/prs/*/summary", "/prs/*/reviews/*/comment", "/urls/*/description", "/meeting_chats/*/text"}


def _pct(vals, q):
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def main() -> None:
    key = load_key(KEY_PATH)
    records = scan_dataset(DATASET_DIR, DATA_ROOT)
    json_paths = [DATA_ROOT / fr.relpath for fr in records if fr.format == "json"]

    prose = prose_leaf_pointers(json_paths)
    print("=== prose-vs-short classification (per content leaf) ===")
    for ptr in sorted(set(key["content"])):
        cls = "PROSE" if ptr in prose else "short"
        print(f"  {ptr:38s} -> {cls}")
    assert EXPECT_PROSE <= prose, f"expected prose leaves missing: {EXPECT_PROSE - prose}"
    assert not (EXPECT_SHORT & prose), f"short leaves wrongly classed prose: {EXPECT_SHORT & prose}"
    print("  acceptance OK: documents/content + transcript = prose; prs/urls/chats = short\n")

    chunks = chunk_dataset(DATASET_DIR, DATA_ROOT, key)
    by_kind = Counter(c.kind for c in chunks)
    print("=== chunks ===")
    print(f"  total: {len(chunks)}")
    for kind in sorted(by_kind):
        print(f"    {kind:14s} {by_kind[kind]}")

    toks = [c.est_tokens for c in chunks]
    print("\n=== est_tokens distribution ===")
    print(f"  median={int(statistics.median(toks))}  p90={_pct(toks, 0.90)}  max={max(toks)}  cap=3000")
    assert max(toks) <= 3000, f"a chunk exceeds the cap: {max(toks)}"

    # invariant: no prose chunk glues two distinct documents/transcripts. Each
    # prose chunk's refs must all sit in the SAME record (same /collection/index).
    print("\n=== no-doc-gluing check (prose chunks) ===")
    glued = 0
    for c in chunks:
        if c.kind != "prose":
            continue
        records_touched = set()
        for r in c.refs:
            ptr = r.address if r.scheme == "json_pointer" else r.address[0]
            toks_p = ptr.strip("/").split("/")
            records_touched.add((toks_p[0], toks_p[1]))
        if len(records_touched) > 1:
            glued += 1
    print(f"  prose chunks spanning >1 record: {glued}")
    assert glued == 0, "a prose chunk merged two distinct documents/transcripts"
    print("  OK: every prose chunk stays within one document/transcript")

    # references-not-copies: a sample of chunks round-trips through the resolver
    # contract against the on-disk raw, hash-verified.
    print("\n=== resolver round-trip (sample) ===")
    checked = 0
    for c in chunks[:: max(1, len(chunks) // 200)]:
        for r in c.refs:
            ref = {"file_path": c.relpath, "sha256": c.sha256, "scheme": r.scheme, "address": r.address}
            val = resolve(ref, data_root=DATA_ROOT)
            assert isinstance(val, str)
            checked += 1
    print(f"  {checked} references resolved + hash-verified against raw -- OK")
    print("\nsmoke OK")


if __name__ == "__main__":
    main()
