# Architecture

## Overview

**Entry:** `src/main.tsx` -> `src/App.jsx`.

The app is a local-only React workbench. The browser talks directly to Neo4j
via `neo4j-driver` and Anthropic via `@anthropic-ai/sdk`; there is no HTTP
server between the UI and either service. The Python backend builds the graph
offline and is not part of serving the frontend.

## Canvas

The Pipeline lane is an offline illustration of the backend HERB build path.
It is not executed by the browser.

The Usage lane is the real executable DAG:

```text
prompt -> interpret -> build_input -> ground -> retrieve_tags -> answer
                             \-> retrieve_baseline -> answer -> compare
```

`services/pipeline.ts` maps each node kind to one async executor and runs the
wired Usage nodes in topological order. Wire order is run order. Per-step
parameters live on node data: model, dataset, active facets, `k`, `min_sim`,
thresholds, and retrieval limit. Cycles, missing terminal `compare`, invalid
contracts, and unknown datasets/gates fail loudly.

## Query Modules

A `queryGroup` wired onto `ground -> [Query module] -> retrieve_tags` becomes
Lane A's executed Cypher. `composeModuleCypher` composes the module header,
ordered fragments, and footer; `runModuleCypher` executes it. No module wired
means Lane A uses the fixed `scoreCypher` path in `scoreGroundedChunks`.

The default module header/footer is the canonical weighted-overlap query. A
module must return `chunkId`, `fileId`, `content`, `description`,
`relevanceToFile`, and `score`. Dataset, hard gate, and RAG-eval exclusions
are validated; a custom module that returns excluded QA/oracle chunks fails.

## Run Builder

The canvas A/B fork answers "tags vs one baseline, once". The **Run Builder**
tab (bottom panel) makes a *Run* a first-class, comparable object: a config
snapshot of every lever the canvas spreads across its nodes, collapsed into one
`RunSpec`. Build N runs, press **Run all** (one shared prompt), and the answers
plus real metrics show side by side with pairwise chunk overlap.

`RunSpec` fields map 1:1 to the node that owns the lever; the form renders one
section per node so this stays legible:

| Node | Levers |
|---|---|
| `prompt` | answer `mode` (`raw`/`context`/`hybrid`) |
| `interpret` | model, dataset |
| `build_input` | maxChunks, weightThreshold, minRelevanceToFile, groundingK, minSim, activeFacets, runId |
| route | `tags` (Lane-A grounded overlap) · `baseline` (enriched relevance, gated) · `content` (RQ2 conventional Lucene control, no interpret/ground/gate) · `module` (composed Query-module Cypher) · `sql_agent` (headless LLM+SQL baseline; export only) |
| `answer` | model, temperature |
| Neo4j | database (`herb` vs pruned `herb-eval`) — was a global |
| `sql_agent` | maxToolCalls, maxRowsPerQuery, maxCellChars (0 = no limit; shown when route is `sql_agent`) |

**Ceiling defaults:** new RunSpecs ship with graph caps at 0 (`maxChunks`,
`groundingK`) and SQL caps at 0 (`maxToolCalls`, `maxRowsPerQuery`,
`maxCellChars`). Quality floors (`minSim`, weight/relevance thresholds) still
apply on graph routes. See [`../../backend/eval/README.md`](../../backend/eval/README.md)
for the full comparison contract.

`services/pipeline.ts:runRunSpec` executes one route end-to-end by calling the
same service functions the canvas executors call — no synthetic graph, no
required `compare` node — so each run is independent and a per-run database is
honoured. `compareRuns` computes pairwise Jaccard. The A/B `runUsageGraph` path
is unchanged; the Run Builder is an additional surface. A run's failure is
reported loudly (its card + History + Logs) and does not abort the others. Each
run is recorded in History with its full `RunSpec` and is RAGAS-exportable per
run.

## Retrieval

The live service path is:

1. `interpret` -> `services/interpreter.ts`: two-pass Anthropic plan with tags,
   five-facet weights, answer job, and hard gate.
2. `build_input` -> `services/retrieval.ts:buildRetrievalInput`: plan + graph
   scope + controls + eval exclusions + hard gate.
3. `ground` -> `groundRetrieval`: validate dataset/gate, embed prompt tag
   facets with bundled e5, and kNN against `:Tag.emb_*` vector indexes.
4. `retrieve_tags` -> `scoreGroundedChunks`: weighted `HAS_TAG` overlap.
5. `retrieve_baseline` -> `retrieveBaseline`: the UI's enriched
   `relevance_to_file` baseline.
6. `answer` -> `services/answer.ts`; `compare` joins both answers and computes
   real run metrics.

For thesis RQ2, the headless harness also exposes `retrieveBaselineContent`:
plain full-text over raw `c.content` only. That is the clean direct-content
baseline; the UI baseline is enriched and should not be treated as the final
RQ2 comparator.

## RAGAS

RAGAS runs offline. The preferred thesis path is:

- `frontend/scripts/ragas-export.ts`: headless graph, direct-content baseline,
  or SQL-agent batch runner. It writes JSONL with `user_input`,
  `retrieved_contexts`, `response`, `reference`, and `meta`.
- `backend/baselines/sql_agent.py`: LLM agent with a SQL tool over a local
  HERB SQLite store (independent of the graph artefact). Invoked by
  `ragas:export --mode sql_agent` or a RunSpec export with
  `route='sql_agent'`.
- `backend/evaluation/build_gold_set.py`: extracts HERB gold questions and
  references from the full `herb` graph.
- `backend/evaluation/ragas_eval.py`: scores faithfulness plus reference
  metrics such as context recall and context precision.

Graph and SQL exports share the same ceiling-default contract (0 = no count cap
unless set). See [`../../backend/eval/README.md`](../../backend/eval/README.md).

The History tab's **Export RAGAS** button remains a lightweight UI smoke path
for `backend/eval/ragas_eval.py`.

## State

State is local React state in `App.jsx`. There is no workspace persistence in
the current entrypoint.
