# Status - Built vs Planned

**Active UI:** `src/App.jsx`.

> **Verified state (2026-05-19).** The retrieval/interpret/answer service stack
> is implemented in `src/services/*` and `App.jsx`; the retrieval lane receives
> a named `RetrievalInput` object. For thesis eval, the default target is the
> physical `herb-eval` database: 4,869 chunks, 0 QA/oracle chunks, 229,249
> `HAS_TAG` edges, 24,781 tags, 96,790 `:Tag.emb_*` grounding vectors
> (72,009 facet + 24,781 `all`), and ONLINE `chunk_fulltext` plus
> `tag_emb_<facet>` vector indexes. The full `herb` graph remains available for
> exploration, but it contains QA/oracle sections and should not be used for
> thesis RAG scoring.
>
> Not re-verified here: a full browser prompt-to-answer click-through and a
> live headless RAGAS run against Neo4j/Anthropic.

---

## UI shell - built

- [x] Canvas: executable Usage fork/join DAG (prompt → interpret → retrieve A/B → compare)
- [x] Catalog and inspector side panels — collapsible rails, folded in on first load; inspector auto-opens when a node is selected
- [x] Initial canvas: Usage lane only (query modules added from the catalog)
- [x] **Run Builder** tab: N first-class `RunSpec`s (every node lever + per-run database + route `tags`/`baseline`/`content`/`module`/`sql_agent`), **Run all** on one shared prompt, side-by-side answers/metrics + pairwise chunk overlap, per-run History + RAGAS export. Graph routes run in-browser; `sql_agent` is export-only (headless). Ceiling defaults: `maxChunks=0`, `groundingK=0`, SQL caps `0/0/0`. `pipeline.ts:runRunSpec`/`compareRuns`; the A/B `runUsageGraph` path is unchanged.
- [x] Compare node output toggles: lanes, panel views, metrics summary, and export rows (Comparison tab + RAGAS JSONL)
- [x] Canvas levers aligned with Run Builder on Interpret (dataset, temperature), Build input (database, run id, 0=unlimited caps). Canvas + Run Builder answer steps use explicit `NO_EVIDENCE_CAP` (no hidden 1800-char / 200-chunk / scrub defaults).
- [x] Canvas comparison: **Export comparison** JSONL + **Export lane A/B config** (`.ragas.json`; lane A→`graph`/tags, lane B→`relevance`/baseline). History stores `canvasSnap`; export rows carry route/database/levers in `meta`.
- [x] Undo/redo and clipboard support for canvas editing

**Node-driven execution.** The canvas is the real executor. `services/pipeline.ts`
holds one async executor per node kind; `runUsageGraph` topologically orders the
wired `lane_usage` nodes/edges and threads a typed context, so wire order is run
order and A/B is a real fork (`retrieve_tags` vs `retrieve_baseline`) joined at
`compare`. Offline graph construction (`python -m tagging`, etc.) is documented
in [`../backend/architecture.md`](../backend/architecture.md), not on the canvas.

**Real metrics, no mock.** Fabricated stage payloads, preset comparison answers, and sample chunk placeholders were removed. Metrics shown in the Inspector are computed from the actual run:
grounding quality, retrieval comparison, citation grounding, and per-stage
latency.

---

## Retrieval / interpret / answer stack - built

- [x] Browser-direct Neo4j read via `neo4j-driver` - [`services/neo4j.ts`](../../frontend/src/services/neo4j.ts)
- [x] Browser-direct interpretation via `@anthropic-ai/sdk` - [`services/interpreter.ts`](../../frontend/src/services/interpreter.ts)
- [x] In-browser e5 tag/facet embedding, bundled local-only - [`services/embeddings.ts`](../../frontend/src/services/embeddings.ts)
- [x] kNN prompt grounding + weighted-overlap HERB retrieval - [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts)
- [x] Named `RetrievalInput` contract (`plan`, `scope`, `controls`, `gate`) - [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts), [`App.jsx`](../../frontend/src/App.jsx)
- [x] Pass-1 hard-gate extraction (`product`, `section`, `channel`, `employee_id`, `years`) + gated lexical path
- [x] RAG-eval leakage exclusions (`answerable_questions`, `unanswerable_questions`, `product_profile`) by default
- [x] Answer call over retrieved chunks per `answer_job` - [`services/answer.ts`](../../frontend/src/services/answer.ts)
- [x] HERB field-name discipline: `facet`, `w_chunk`, `w_facet`, `relevance_to_file`

Prompt-tag to corpus-tag/facet mapping is vector-kNN grounding against the
per-facet `tag_emb_<facet>` `:Tag` vector indexes. If no tags survive grounding,
semantic retrieval fails loudly. If grounded tags exist but the weighted tag
score returns zero chunks under the hard gate, the current retrieval code falls
back to the gated `chunk_fulltext` lexical path and records a warning; this is a
recall rescue, not the primary semantic method.

The hard gate is deterministic and validated before retrieval. A selected
`product`, `section`, `channel`, `employee_id`, or `year` that matches zero
chunks is a loud error with valid values, never a silent scan-everything skip.

---

## Evaluation - built

- [x] UI export: Run Builder **Export RAGAS run** and History **Export RAGAS** open a save dialog (editable file name + subfolder under `ragas_exports/`, overwrite confirm). JSONL uses `selectEvidenceChunks` (same slice the answer LLM saw). Config export maps routes 1:1 (`tags`→`graph`, `baseline`→`relevance`, `content`→`content`); legacy `mode: baseline` in old files → Lucene content.
- [x] Headless thesis harness: `npm --workspace frontend run ragas:export` runs questions through the current service stack and writes RAGAS-compatible JSONL.
- [x] Ground-truth scoring runner: `backend/evaluation/ragas_eval.py` scores exported JSONL with RAGAS faithfulness, answer relevancy, context recall, and context precision when references are present.
- [x] Gold-set builder: `backend/evaluation/build_gold_set.py` converts HERB QA/oracle records into JSONL question sets.
- [x] Direct content baseline for RQ2-style comparison: `retrieveBaselineContent` queries `chunk_content_ft` over `Chunk.content` only. This is intentionally separate from the UI Lane B baseline, which still uses enriched `relevance_to_file` ranking for workbench comparison.

The eval-safe graph is `herb-eval`, created by `backend/scripts/create_herb_eval_db.py`.
It removes QA/oracle/product-profile chunks while preserving already computed
tag and relevance fields. See [`backend/eval/README.md`](../../backend/eval/README.md)
for the current runbook.

---

## Retrieval improvement plan

- [Retrieval orchestration](retrieval_orchestration.md) — pain map, research × solution matrix, implementation waves 0–4.

## Known issues

- `min_sim` is near-meaningless on e5-small for this corpus; cosine scores are compressed, so grounding quality mostly depends on top-k.
- The live headless harness still needs to be run end-to-end and its result recorded.
- Deterministic thesis metrics such as exact answer/entity F1, citation hit@k, retrieval gold-hit@k, and refusal accuracy are still missing.
- Persisting canvas/module state across browser sessions remains optional and unwired.

---

## Inactive / Legacy

- `frontend/updated/` - tracked static prototype files. They are not imported by `src/main.tsx`; the active app is `src/App.jsx`.
