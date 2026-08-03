---
name: herb-eval-is-the-artefact
description: "herb-eval is the canonical artefact DB; herb has gold QA/oracle baked in (an ingestion error) and must not be referenced as \"the real graph\""
metadata: 
  node_type: memory
  type: project
  originSessionId: 4f97e452-4e72-42d8-8205-39b98fa75d71
---

`herb-eval` is the **prior (v1/thesis) artefact build** under the superseded design — a contrast/forensic baseline for v3, NOT the v3 artefact (which rebuilds from raw natively in `v3/artefact/` — [[v3-artefact-subsystem]]). Do not treat `herb` as "the full DB" and `herb-eval` as "the eval-safe copy" — that framing (used in [[project_overview]], `docs/system_map.md`, and `docs/graph_schema.md`) is wrong. `herb` has the `answerable_questions`, `unanswerable_questions`, and oracle `product_profile` sections ingested, which is contaminated state from an ingestion error.

**Why:** Those QA/oracle sections were never supposed to be part of the retrievable corpus. They're the gold answers. Their presence in `herb` makes any retrieval or stats reading from `herb` misleading.

**How to apply:**
- For any live-graph query, distribution, count, or eval, target `herb-eval` only.
- When reading docs that describe the artefact, mentally substitute `herb-eval` for `herb` unless the doc is specifically discussing the construction error.
- If asked to verify schema/stats/distribution, run against `herb-eval`.
- `Chunk.section IN {answerable_questions, unanswerable_questions, product_profile}` is the contamination marker — those rows do not exist in `herb-eval`.

**Sharpened 2026-06-12:** the v1 build chunked AND tagged the full oracle — 815 answerable (with ground_truth + citation copies) and 699 unanswerable (batched chunks), both fed to the tagger as knowledge (v1/backend/indexing/chunker.py HERB handlers; tagging/pipeline.py source labels). And `herb-eval` is a **filter, not a rebuild** (v1/backend/scripts/create_herb_eval_db.py): it excludes those chunks but *preserves* chunk descriptions, relevance scores, and tag weights produced by the contaminated tagging run, re-embedding tags as the only mitigation — so second-order residue (tag vocabulary minted partly from oracle text) was filtered around, never eliminated (.work/verify_orphan_tags.py forensics). This is the standing argument for v2's derive-corpus stage 0 ([[v2-mapping-key]]): no run ever sees the oracle, so the residue class can't exist.

**Confirmed 2026-06-15 (live read-only inventory):** herb-eval has 0 oracle chunks (no qa_record/qa_batch/qa_record_part/unanswerable_question_batch/product_profile kinds) and 0 orphan tags right now; 4869 chunks / 33 files / 24804 tags. So the oracle CHUNK removal is already done — what the filter left is the model-output residue (preserved descriptions/weights/tag-vocab), not deletable nodes. See [[herb-eval-graph-deletion-chain]] for the verified topology.
