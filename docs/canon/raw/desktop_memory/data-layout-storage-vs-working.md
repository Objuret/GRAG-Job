---
name: data-layout-storage-vs-working
description: "HARD RULE: A:\\exjobbet\\data\\raw = cold storage, NEVER touch/write; v3/data = the working copy (corpus + raw the harness reads)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 076080ac-fe35-473e-9116-ef7fc6727670
---

**A:\exjobbet\data\raw is cold storage — do not touch it AT ALL** (user directive:
"do not touch A:\exjobbet\data\raw at all, that is the storage"). No writes, no
derived views placed next to it, no "working with" it. Reads to verify byte-identity
are fine; writes never are.

**The working area is `v3/data`:** `v3/data/raw/<dataset>` is the full data the
evaluators read truth from in place; `v3/data/corpus/<dataset>` is the oracle-stripped
RAG-safe split the pipelines retrieve over. Both are re-derivable / re-copyable from
cold storage.

**Why:** storage is the recovery point; everything under `v3/data` can be regenerated.

**How to apply:** any tool/script that derives, splits, or rewrites dataset files
targets `v3/data`; never `A:\exjobbet\data\raw`. Same pattern as
[[neo4j-data-location]] (A:\ holds the DB backups/dumps).
