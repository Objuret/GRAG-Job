# Architecture

## Overview

**Entry:** `src/main.tsx` → **`src/App.jsx`**.

Single-file workbench: React Flow canvas, inline catalog, inspector, query-module editor, edge drawer, and resizable bottom result console. Demo copy and registry live in **`src/data/workbenchData.ts`**.

The app is **local-only**. The browser talks directly to:

- **Neo4j** via [`neo4j-driver`](https://www.npmjs.com/package/neo4j-driver) (bolt-ws to localhost) as a **read-only** Neo4j user.
- **Anthropic** via [`@anthropic-ai/sdk`](https://www.npmjs.com/package/@anthropic-ai/sdk) with `dangerouslyAllowBrowser: true`. API key in `.env.local` as `VITE_ANTHROPIC_API_KEY`.

There is no HTTP server in the middle. The Python `backend/` is an **offline pipeline** that builds the Neo4j graph; it is not part of running the app.

---

## Canvas: two lanes

**Pipeline (offline illustration, not executed):** Dataset → Access Layer → Index Layer → Tags → Facets — how the Python pipeline built the graph. Toggling these nodes does nothing; they carry no run controls.

**Usage (the real executable DAG):**

```
prompt → interpret → build_input → ground → retrieve_tags → answer ┐
                                 └────────→ retrieve_baseline → answer ┘→ compare
```

The Usage lane **is** the executor. `services/pipeline.ts` maps each node kind to one async executor; `runUsageGraph` topologically orders the wired `lane_usage` nodes/edges and threads a typed context — **wire order = run order**, A/B is a real fork joined at `compare`. Per-step params live on the node (`node.data`): model on `interpret`/`answer`; dataset, facets, k, min_sim, thresholds, limit on `build_input`. A node’s `disabled` toggle removes it from the run; a cycle, missing terminal `compare`, or contract mismatch is a loud error.

**Modules:** a **Probe** (`MODULE_NODES`) is a typed passthrough — splice it on any matching wire to log what flows through without changing the run.

Registry splits: `PIPELINE_NODES`, `USAGE_NODES`, `MODULE_NODES`, combined as `NODE_TYPES`.

**Query modules — the executed Lane-A Cypher.** A `queryGroup` wired onto the
grounded wire (`ground → [Query module] → retrieve_tags`) **is** the query
`retrieve_tags` runs: `querymodule` composes the module's header + ordered
fragment chain + footer (`composeModuleCypher`) and `retrieve_tags` executes
that via `runModuleCypher`. No module wired → the fixed `scoreCypher`
(`scoreGroundedChunks`). The default module header/footer is the *canonical
weighted-overlap query itself* (same semantics as `scoreCypher`), so editing
fragments/weights/order/structure are real experiments. Bindings: `$plan`,
`$queryTags` (grounded corpus tags + sim + facet weights), `$activeFacets`,
`$datasetId`, `$runId`, `$minWChunk`, `$minRelevanceToFile`, `$limit`, and the
null-tolerant gate (`$g_product/$g_section/$g_channel/$g_employee_id/$g_years`).
The module **must** `RETURN chunkId, fileId, content, description,
relevanceToFile, score` — a missing column is a loud error. Dataset + hard
gate are still validated loudly before the module runs. The inspector keeps
the plain-language story plus the technical Cypher view.

**RAGAS (offline).** No server, so RAGAS isn't wired in. History →
**Export RAGAS** writes one JSONL record per (run, lane) with the real
`question` / `answer` / retrieved `contexts`; `backend/eval/ragas_eval.py`
scores faithfulness + answer_relevancy per lane and the A−B delta. See
[`../../backend/eval/README.md`](../../backend/eval/README.md).

**Result console:** the bottom panel is resizable and has real Comparison,
Logs, and History tabs. Comparison shows lane answers, retrieved chunks,
retrieval input, copy actions, chunk filtering, and chunk detail. Logs are
populated by the live prompt → interpretation → retrieval → answer run.
History records finished/failed runs and can restore a previous successful run
into the comparison view. Pipeline errors keep the compact header warning but
also expose a paper-list popover with deduplicated full error lines; clicking a
line copies that complete error.

---

## Module map

```
src/
├── main.tsx
├── App.jsx                    # UI composition + runPipeline wrapper
├── services/pipeline.ts       # Executor-per-node engine + graph runner + real metrics
├── data/workbenchData.ts      # Node registry + pre-run demo (PRESET_RESULTS, SAMPLE_CHUNKS)
├── query/queryModuleSyntax.ts # Query fragment defaults and composition helpers
├── types/index.ts
└── index.css
```

---

## Data flow

```
workbenchData.ts       ──imports──▶  App.jsx  (registry + demo lane results)
queryModuleSyntax.ts   ──imports──▶  App.jsx  (query module composition)
```

The live path: `App.jsx:runPipeline` (key precheck, lane status, logs/history)
calls `services/pipeline.ts:runUsageGraph`, which executes the wired Usage
nodes in topological order. The node executors call the service modules:

1. `interpret` → `services/interpreter.ts` (two-pass plan + hard gate; see [`query_interpretation_layer.md`](query_interpretation_layer.md)).
2. `build_input` → `services/retrieval.ts:buildRetrievalInput` (`plan` + scope + controls + gate).
3. `ground` → `groundRetrieval` (validate dataset+gate, e5 embed + kNN onto corpus `:Tag`s).
4. `retrieve_tags` → `scoreGroundedChunks` (Lane A weighted overlap); `retrieve_baseline` → `retrieveBaseline` (Lane B).
5. `answer` → `services/answer.ts`; `compare` joins A/B and computes the real metrics.

The query plan, retrieval input, grounding and metrics are shown beside the retrieved results so the user sees what the model inferred and what retrieval actually consumed.

Field-name discipline: the HERB graph uses `facet`, `w_chunk`, `w_facet`, `relevance_to_file`; the frontend read path should use those names.

---

## State

Local React state in `App.jsx` only (`useState` / `useMemo` / refs for undo, redo, and clipboard). No workspace persistence in the current entrypoint.
