# Status — Built vs Planned

**Active UI:** `src/App.jsx`.

> **Verified state (2026-05-18).** The retrieval/interpret/answer service stack
> is **code in the working tree — uncommitted** (nothing since commit
> `452fa5d`). Its graph prerequisites **are present and correct on the live
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

- [x] Two-lane canvas (pipeline + usage) + Facets → Graph Query bridge
- [x] Catalog, inspector forms per node kind, edge drawer, bottom lane comparison
- [x] Themes and CSS tokens (`index.css`)
- [x] Query modules with chained `topic`, `entities`, `activity`, `temporal`, `evidence` fragments
- [x] Undo/redo and clipboard support for canvas editing

---

## Retrieval / interpret / answer stack — coded, graph layer verified on `herb`

Each step is a service module under `src/services/`, driven by
`App.jsx:runPipeline`. Code is **uncommitted** (working tree only); the graph
data it depends on is verified present on `herb` (banner above).

- [x] Browser-direct Neo4j read via `neo4j-driver` — [`services/neo4j.ts`](../../frontend/src/services/neo4j.ts)
- [x] Browser-direct two-pass interpretation via `@anthropic-ai/sdk` — [`services/interpreter.ts`](../../frontend/src/services/interpreter.ts)
- [x] In-browser prompt-tag embedding (`@xenova/transformers`, e5, symmetric `passage: <name>. <description>` — mirrors backend `_tag_embed_text`; model **bundled** in `public/models/Xenova/e5-small-v2/`, full fp32, loaded local-only — no runtime HF fetch; exact backend parity, cosine ≈ 1.0) — [`services/embeddings.ts`](../../frontend/src/services/embeddings.ts)
- [x] kNN grounding + deterministic weighted-overlap Cypher — [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts)
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

- **Uncommitted.** The entire feature (services + `materialize`/embeddings/
  gate + doc updates) is working-tree only, nothing since `452fa5d`. One
  disruption and it is gone. Commit it.
- **`frontend/public/models/` is an unmanaged dependency.** Untracked **and**
  not gitignored; with `allowRemoteModels=false`, a fresh checkout has no
  model and grounding hard-fails. Decide: commit the quantized ONNX, or
  gitignore + document a fetch step in the runbook.
- **`min_sim` is near-meaningless.** e5-small cosine on this corpus is
  compressed (~0.8 mean to random tags); default floor 0.78 barely filters
  noise — grounding leans entirely on top-k.
- **Lexical recall is a zero-result fallback, not a union.** The earlier
  year-gate lexical/tag union (and its `.slice(0, limit)` truncation bug) is
  gone. The gated `chunk_fulltext` path now runs only when tag scoring returns
  **no** chunks under the gate (or when there were no usable tags) — a recall
  fallback, warned on the plan. It does not merge with or truncate tag hits.
  Measured impact: against HERB gold answers this addresses the zero-retrieval
  failure mode; the remaining recall gap is wrong-retrieval (relevant chunks
  not ranked in), which is a grounding/precision problem, not this path.

---

## Not wired

- [ ] Persisting canvas/module state across browser sessions (optional — local-only app)
- [ ] Full browser prompt → answer UI click-through not re-verified here (graph data layer verified)

See [`plans.md`](plans.md) and the interpretation/retrieval spec at [`query_interpretation_layer.md`](query_interpretation_layer.md).

---

## Inactive / Legacy

- `frontend/updated/` — tracked static prototype files. They are not imported by `src/main.tsx`; the active app is `src/App.jsx`.
