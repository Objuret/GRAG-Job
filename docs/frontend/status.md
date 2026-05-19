# Status — Built vs Planned

**Active UI:** `src/App.jsx`.

> **Verified state (2026-05-19).** The retrieval/interpret/answer service stack
> is implemented in `src/services/*` and `App.jsx`; the retrieval lane now
> receives a named `RetrievalInput` object. Its graph prerequisites **are present and correct on the live
> `herb` graph**, independently re-verified 2026-05-18 by direct Cypher:
> 5843 chunks (product 5782, section 5782, channel 2669, years≥1 4799,
> employee_id 30); gate `product=CollaborateForce AND section=slack` → 124;
> corpus year range 1801–2048; 25,896/26,023 `:Tag` embedded; all `chunk_*`
> RANGE + `chunk_fulltext` FULLTEXT + `tag_embedding` VECTOR indexes ONLINE.
> The `pilot_format_smoke/run.json` `stages_done` ledger is stale — **trust the
> graph, not the ledger.** Not separately re-verified here: a full click-through
> of the browser prompt → answer UI loop (only its data layer was checked).

---

## UI shell — built (no graph dependency)

- [x] Two-lane canvas: Pipeline (offline illustration) + Usage (executable fork/join DAG)
- [x] Catalog, inspector forms per node kind, edge drawer, bottom lane comparison
- [x] Resizable result console with live Comparison / Logs / History tabs, copy actions, chunk filtering/detail inspection, run restore, and a paper-list error popover whose rows copy full errors
- [x] Themes and CSS tokens (`index.css`)
- [x] Query modules with chained `topic`, `entities`, `activity`, `temporal`, `evidence` fragments
- [x] Undo/redo and clipboard support for canvas editing

> **Node-driven execution (2026-05-19).** The Usage canvas is now the real
> executor, not an illustration. `services/pipeline.ts` holds one async
> executor per node kind; `runUsageGraph` topologically orders the wired
> `lane_usage` nodes/edges and threads a typed context, so **wire order = run
> order** and A/B is a real fork (`retrieve_tags` vs `retrieve_baseline`)
> joined at `compare`. The startup canvas is that real DAG:
> `prompt → interpret → build_input → ground → retrieve_tags → answer ↘`
> `                              └→ retrieve_baseline → answer ↗ → compare`.
> Per-step params live on the node (`node.data`, edited in its Config tab):
> model on `interpret`/`answer`; dataset, facets, k, min_sim, thresholds,
> limit on `build_input`. A node’s `disabled` toggle removes it from the run;
> a cycle / missing `compare` / contract mismatch is a loud error, never a
> silent partial run. A **Probe** module is a typed passthrough — splice it on
> any matching wire to log what flows through without changing the run.
> `runPipeline` is now just the React wrapper (key precheck, lane status,
> logs/history) around `runUsageGraph`. The **Pipeline lane** stays a
> non-executable illustration (it is genuinely offline Python); toggling its
> nodes does nothing and they expose no run controls.

> **Real metrics, no mock (2026-05-19).** All fabricated per-node payloads
> (`STAGE_PAYLOADS`, `SAMPLE_FILES`, the "412ms / bolt://neo4j-mock / cache
> warm" Runtime panel, the node-face `in/out` counts, the edge Drawer's
> Records/Latency/Sample) were deleted. The Inspector now has **Config** +
> **Metrics** tabs; Metrics shows only values computed by the engine
> (`compare` node) from the actual run: grounding quality (prompt tags, grounded corpus tags, cosine
> min/μ/max, zero-grounded prompt tags), A/B retrieval comparison (per-lane
> chunk count, score & relevance min/μ/max, distinct files, **A∩B overlap +
> Jaccard**), citation grounding (parsed `[n]` cites → distinct chunks, % of
> retrieved actually used), and **per-stage latency** (interpret / ground /
> retrieve-A / retrieve-B / answer-A / answer-B; the single reused `elapsed`
> for both lanes is gone). Nodes with no in-browser instrumentation say so
> plainly; pre-run state shows an explicit "no run yet", never sample data.
> A selected dataset matching zero `:File`s now fails loud (valid ids listed),
> like the hard gate.

> **Query module = the executed query; RAGAS export (2026-05-19).** A Query
> module spliced `ground → module → retrieve_tags` becomes Lane A's real
> Cypher (`composeModuleCypher` → `runModuleCypher`); no module wired keeps the
> fixed `scoreCypher`. The default module header/footer now *is* the canonical
> weighted-overlap query (parametric gate, `$queryTags`), so weight/facet/order/
> query experiments are real and the result contract is enforced loudly
> (required RETURN columns; dataset+gate validated first). RAGAS runs offline:
> History **Export RAGAS** → JSONL of real (question, answer, contexts) per
> lane → `backend/eval/ragas_eval.py` (faithfulness + answer_relevancy, A−B
> delta). No silent fallback anywhere in that path.

---

## Retrieval / interpret / answer stack — coded, graph layer verified on `herb`

Each step is a service module under `src/services/`, driven by
`App.jsx:runPipeline`. The graph data it depends on is verified present on
`herb` (banner above).

- [x] Browser-direct Neo4j read via `neo4j-driver` — [`services/neo4j.ts`](../../frontend/src/services/neo4j.ts)
- [x] Browser-direct two-pass interpretation via `@anthropic-ai/sdk` — [`services/interpreter.ts`](../../frontend/src/services/interpreter.ts)
- [x] In-browser prompt-tag embedding (`@xenova/transformers`, e5, symmetric `passage: <name>. <description>` — mirrors backend `_tag_embed_text`; model **bundled** in `public/models/Xenova/e5-small-v2/`, full fp32, loaded local-only — no runtime HF fetch; exact backend parity, cosine ≈ 1.0; local asset preflight validates JSON files + `onnx/model.onnx`, clears stale `transformers-cache` JSON entries, and disables `transformers-cache` for this local bundle) — [`services/embeddings.ts`](../../frontend/src/services/embeddings.ts)
- [x] kNN grounding + deterministic weighted-overlap Cypher — [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts)
- [x] Named `RetrievalInput` contract (`plan` + `scope` + `controls` + `gate`) passed into semantic and baseline retrieval — [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts), [`App.jsx`](../../frontend/src/App.jsx)
- [x] Pass-1 hard-gate extraction (`product`, `section`, `channel`, `employee_id`, `years`) + deterministic pre-tag gate + fail-loud gate validation + gated `chunk_fulltext` lexical path — [`services/interpreter.ts`](../../frontend/src/services/interpreter.ts), [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts)
- [x] Answer call over retrieved chunks per `answer_job` — [`services/answer.ts`](../../frontend/src/services/answer.ts)
- [x] Field-name discipline: HERB `facet`, `w_chunk`, `w_facet`, `relevance_to_file`

---

## Grounding is mandatory — no fallback

Prompt-tag → corpus-tag mapping is **only** vector-kNN grounding against the
`tag_embedding` index. The legacy exact-cleaned-name path and the silent
"embeddings missing → degrade to string equality" fallback were deleted
(`retrieval.ts`, `App.jsx`): no `toExactParams`, no `groundTags` option, no
`interpreterStrategy` selector. If embeddings are absent or grounding returns
nothing above `min_sim`, `retrieveChunks` throws a loud, actionable error
(`run python -m tagging embed-tags`). On `herb` the embeddings are present
(25,896 `:Tag`), so this path is live.

## Hard gate — validated, no silent skip

Pass 1 extracts a `gate` (`product`, `section`, `channel`, `employee_id`,
`years`) **only** when the query explicitly names the constraint. Retrieval
applies it as a deterministic WHERE filter on the materialized `:Chunk` hard
fields (written by `python -m tagging materialize`, see
[`../graph_schema.md`](../graph_schema.md)) **before** any tag/embedding
scoring. Every set value is validated against the live corpus first: a
constraint matching zero chunks is a loud error listing valid values — never a
silent "scan everything". On `herb` the hard fields and `chunk_fulltext` index
exist (banner above), so the gate and lexical paths are live.

---

## Known issues (real, not fixed)

- **`min_sim` is near-meaningless.** e5-small cosine on this corpus is
  compressed (~0.8 mean to random tags); default floor 0.78 barely filters
  noise — grounding leans entirely on top-k.
- **Full UI click-through still unrecorded.** Build/lint pass and graph
  prerequisites are verified, but the browser prompt → answer loop still needs
  an observed result written here.

---

## Not wired

- [ ] Persisting canvas/module state across browser sessions (optional — local-only app)
- [ ] Full browser prompt → answer UI click-through not re-verified here (graph data layer verified)

See [`plans.md`](plans.md) and the interpretation/retrieval spec at [`query_interpretation_layer.md`](query_interpretation_layer.md).

---

## Inactive / Legacy

- `frontend/updated/` — tracked static prototype files. They are not imported by `src/main.tsx`; the active app is `src/App.jsx`.
