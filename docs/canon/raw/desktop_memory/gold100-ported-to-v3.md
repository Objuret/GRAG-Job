---
name: gold100-ported-to-v3
description: where the v3 gold-100 scored set lives and how it was derived
metadata: 
  node_type: memory
  type: project
  originSessionId: 1c57bbf8-1ab6-485e-a353-dcf9c1acafa9
---

The gold-100 scored set now lives in v3 at `v3/data/gold100.jsonl` — 100 lines of
`{"id": "<Stem>::a::<index>"}`, the format `orchestrator._read_ids` consumes. No header
comment (the loader is strict JSON-per-line).

It was ported from the authoritative v1 selection
`v1/frontend/scripts/ragas-questions.herb-gold100.jsonl` (v1's round-robin pick, ids
`gold_<product>_<index>`). Clean mechanical re-key: lowercase-stem→v3-file-stem, same
index (v1 `item_index` == v3 array position). Every id was verified present in
`v3/data/questions.jsonl` with an exact question-text match before writing — no guessing.

The set is 100 entries; the [[gold100-effective-n99]] note is about a v1 runtime abort on
one question, not the set size.
