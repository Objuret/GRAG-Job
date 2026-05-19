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

- `frontend/scripts/ragas-export.ts`: headless graph or direct-content baseline
  batch runner. It writes JSONL with `user_input`, `retrieved_contexts`,
  `response`, `reference`, and `meta`.
- `backend/evaluation/build_gold_set.py`: extracts HERB gold questions and
  references from the full `herb` graph.
- `backend/evaluation/ragas_eval.py`: scores faithfulness plus reference
  metrics such as context recall and context precision.

The History tab's **Export RAGAS** button remains a lightweight UI smoke path
for `backend/eval/ragas_eval.py`.

## State

State is local React state in `App.jsx`. There is no workspace persistence in
the current entrypoint.
