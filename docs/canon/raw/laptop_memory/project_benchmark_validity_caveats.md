---
name: benchmark-validity-caveats
description: "What is and isn't valid to compare across arms in the HERB gold-100 eval — audited flaws"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3b10041c-68f0-4aa1-a959-730ed70f5cc7
---

Deep audit of the gold-100 benchmark/eval (2026-07-20). All also in `v3/output/DATA_README.md`.

**Cross-arm VALID:** context_recall_id (exact, gold-set denominator), and the judged trio
under one judge (faithfulness, answer_correctness, context_recall_llm).

**NOT cross-arm comparable — do not let analysts compare these across arms:**
- `context_precision_id`: denominator is every id carried by retrieved chunks; artefact
  chunks pack ~500 ids/question vs baselines' ~50, so it measures id-density, not quality.
- `context_precision_nonllm` / `context_recall_nonllm`: string-sim of context text; punishes
  the artefact's raw-JSON context format regardless of content (recall_id≥0.8 on 33 Qs whose
  recall_nonllm averages 0.046).
- `exact_match` (0.000 all arms), `string_presence`, bleu/rouge/semantic_similarity: entity-list
  golds vs prose answers — noise floors here.

**Benchmark construction facts:**
- `gold100.jsonl` is 22 person / 55 content / 17 pr / 5 company / 1 url — NOT the equal 20-per-type
  draw `build_question_sets.py` produces; its real draw predates the current question file.
  company n=5 and url n=1 are anecdotes.
- **Company questions are two-hop joins.** products/ names customers only as CUST- ids;
  `metadata/customers_data.json` maps CUST→company. lucene+vector ingest `products/` ONLY
  (baked in since the arms' first commit a45292f — not a deliberate decision) so they
  structurally cannot answer them; artefact ingests metadata but retrieved no mapping chunk
  for any of the 5. All arms ≈0 on company judged-recall. These are a query-time bridge case
  (CUST-ids discovered at retrieval, never in the question) — the tag layer's pre-join misses it.
- Gold citations average 39/question (max 254): questions with >50 citations can't reach
  recall 1.0 at k=50. Same ceiling every arm.

**Artefact system bottleneck is extraction, not retrieval:** its contexts hold 87% of gold
employee-ids; its answers surface 26%. answer_correctness 0.24 is a generator/prompt problem,
not a graph problem — highest-leverage fix left.

**Baselines abstain a lot:** "not in the documents" — lucene 38/100, vector 35/100, artefact 6/100.
Within-arm, abstentions and non-abstentions score ~equal faithfulness, so the cross-arm
faithfulness gap is substantive, not judge policy. See [[gold100-results-and-judge]].
