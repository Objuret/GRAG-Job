# Post-Cap LLM Smoke Run - 2026-05-07

## Purpose

Verify the current graph after the JSON/JSONL/parquet chunk content cap by running one small file through:

1. chunk extraction LLM calls,
2. file orchestration LLM call,
3. deterministic rollup.

This is not a full-corpus run. It is a smoke test against one Salesforce product file.

## Important Limitation

Raw LLM response JSON is not persisted by the current `AgentClient` / orchestrator. The durable results are the parsed/written Neo4j values: `Chunk.description`, `HAS_TAG` edges, `File.description`, `Chunk.relevance_to_file`, `TAGGED` edges, `Run`, and `WorkItem` metadata. This plan records those persisted results and the exact terminal output from the run.

## Environment

- Repo root: `A:\exjobbet\repo`
- Git commit: `5330ba0f38276a5e46b305b4608f89890b4fd60b`
- Branch state before run: `## main...origin/main`
- Neo4j database: configured `bonnier`
- Model from `Run`: `gpt-4o-mini`
- Concurrency from `Run`: `2`
- Local timestamp after inspection: `2026-05-07T15:28:33.9912156+02:00`

## Pre-Run Target Check

Command:

```powershell
.\.venv\Scripts\python.exe - <<graph target inspection script>>
```

Output:

```text
{'file_id': '960f223de786daa74a7d0f70', 'dataset_id': 'Salesforce__HERB', 'rel_path': 'Salesforce__HERB/products/ActionGenie.json', 'format_family': 'json', 'chunks': 10, 'work_statuses': [{'status': 'unrun', 'kind': 'chunk_extraction'}, {'status': 'unrun', 'kind': 'file_orchestration'}]}
```

## Run Command

Command:

```powershell
.\.venv\Scripts\python.exe scripts\run_index.py --file-id 960f223de786daa74a7d0f70 --chunk-limit 10 --file-limit 1 --concurrency 2
```

Exact terminal output:

```text
Run started: 2026-05-07T13-26-16Z-9598ed
[orchestrator] no failed items to reset
[orchestrator] canonical vocab loaded; dataset_id filter = None; file_id filter = '960f223de786daa74a7d0f70'
[orchestrator] chunk stage: processed=10 done=8 failed=2
[orchestrator] file stage: processed=1 done=1 failed=0
[orchestrator] rollup wrote 48 (:File)-[:TAGGED]->(:Tag) edges
Run finished: ok
  chunks_done=8, chunks_failed=2
  files_done=1, files_failed=0
  tokens in/out = 20225/3519, duration_ms = 88805
```

## Persisted Run Result

```json
{
  "run_id": "2026-05-07T13-26-16Z-9598ed",
  "status": "ok",
  "started_at": "2026-05-07T13:26:16Z",
  "finished_at": "2026-05-07T13:27:13Z",
  "git_commit": "5330ba0f38276a5e46b305b4608f89890b4fd60b",
  "agent_model": "gpt-4o-mini",
  "agent_max_concurrency": 2,
  "chunks_done": 8,
  "chunks_failed": 2,
  "files_done": 1,
  "files_failed": 0,
  "total_in_tokens": 20225,
  "total_out_tokens": 3519,
  "total_duration_ms": 88805,
  "abort_reason": ""
}
```

## Persisted File Result

```json
{
  "file_id": "960f223de786daa74a7d0f70",
  "dataset_id": "Salesforce__HERB",
  "rel_path": "Salesforce__HERB/products/ActionGenie.json",
  "format_family": "json",
  "description_run_id": "2026-05-07T13-26-16Z-9598ed",
  "description": "The file contains metadata and discussions surrounding the ActionGenie product, particularly focusing on the onForceX project. It includes identifiers for team members and customers, market research on the integration of Slack with AI functionalities, meeting chat records discussing product vision and technical documentation, as well as queries related to employee IDs and document authorship. Additionally, it covers pull request details regarding real-time data processing and AI integration methodologies."
}
```

## WorkItem Results For Target File

Summary:

- `chunk_extraction`: 8 done, 2 failed
- `file_orchestration`: 1 done, 0 failed

Failed chunk WorkItems:

```json
[
  {
    "kind": "chunk_extraction",
    "status": "failed",
    "target_id": "005497699f70e06a17dceac9",
    "run_id": "2026-05-07T13-26-16Z-9598ed",
    "in_tokens": 0,
    "out_tokens": 0,
    "duration_ms": 8391,
    "error_class": "schema_invalid",
    "error_message": "2 validation errors for ChunkExtraction\ntags.2\n  Value error, propose=True is incompatible with a non-null canonical. [type=value_error, input_value={'name': 'product_vision_...s specific discussion.'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/value_error\ntags.4\n  Value error, propose=True is incompatible with a non-null canonical. [type=value_error, input_value={'name': 'competitive_ana...quest for information.'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/value_error"
  },
  {
    "kind": "chunk_extraction",
    "status": "failed",
    "target_id": "1eff2a43f34dddfbd2a9fbe9",
    "run_id": "2026-05-07T13-26-16Z-9598ed",
    "in_tokens": 0,
    "out_tokens": 0,
    "duration_ms": 8408,
    "error_class": "schema_invalid",
    "error_message": "1 validation error for ChunkExtraction\ntags.4\n  Value error, propose=True is incompatible with a non-null canonical. [type=value_error, input_value={'name': 'employee_identi...cal fits this context.'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/value_error"
  }
]
```

## Chunk-Level Written Results

Successful chunk ordinals and descriptions:

| Ordinal | Chunk ID | Relevance | Tag edges | Description |
|---:|---|---:|---:|---|
| 0 | `41f94ee80a3b23cd1517db28` | 0.4 | 1 | This chunk contains a list of team member identifiers, represented as unique IDs. |
| 1 | `032c4ca28d9f0f6ad34af945` | 0.7 | 1 | This chunk contains a list of customer identifiers, possibly related to the ActionGenie product. |
| 2 | `1c495711230df5cdb2074e3c` | 0.9 | 6 | This chunk contains messages from a Slack channel discussing a project named onForceX, including planning details and feedback on documents shared within the team. |
| 3 | `7c06021fb642cee14a3530a1` | 0.9 | 5 | This chunk includes a market research report on the onForceX Smart Actions for Slack, detailing its features, target audience, and market potential. |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.7 | 12 | This chunk contains chat records from a meeting discussing various documents related to the onForceX project, including market research and product vision. |
| 6 | `2960d8e4619ac86535c7f888` | 0.6 | 7 | This chunk contains a list of URLs with descriptions related to AI integration in communication platforms and productivity enhancement tools. |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 11 | This chunk lists several pull requests related to integrating various APIs and systems for real-time data processing and event handling across different applications. |
| 8 | `6da4c297bca324a46ee67759` | 0.8 | 5 | This chunk contains a series of questions related to employee IDs of authors and reviewers for various documents associated with the ActionGenie product, along with features related to integration with third-party Slack apps. |

Failed chunk ordinals:

| Ordinal | Chunk ID | Relevance written by file stage | Note |
|---:|---|---:|---|
| 4 | `005497699f70e06a17dceac9` | 0.0 | Chunk extraction failed schema validation before writing tags/description. |
| 9 | `1eff2a43f34dddfbd2a9fbe9` | 0.0 | Chunk extraction failed schema validation before writing tags/description. |

## File-Level Rollup

- `HAS_TAG` edges after run: 48
- `TAGGED` edges after run: 48
- Top rolled-up tags by cluster/weight included:
  - `onforcex_smart_actions` / `theme=technology` / `weight_global=0.81`
  - `planning_onForceX` / `theme=technology` / `weight_global=0.81`
  - `market_analysis` / `information_need=summary` / `weight_global=0.81`
  - `2026-06-09` / `time_relevance=active` / `weight_global=0.81`
  - `slack_channel_creation` / `event_process=launch` / `weight_global=0.72`
  - `slack` / `object_entity=product` / `weight_global=0.72`

## Global Graph State After Run

```json
{
  "workitems": [
    {"kind": "chunk_extraction", "status": "done", "n": 8},
    {"kind": "chunk_extraction", "status": "failed", "n": 2},
    {"kind": "chunk_extraction", "status": "unrun", "n": 157671},
    {"kind": "file_orchestration", "status": "done", "n": 1},
    {"kind": "file_orchestration", "status": "unrun", "n": 40}
  ],
  "edges": [
    {"has_tag": 48, "tagged": 48}
  ],
  "chunk_size": [
    {
      "chunks": 157681,
      "max_chars": 6029,
      "max_tokens": 1507,
      "p95_chars": 4549,
      "p95_tokens": 1137
    }
  ]
}
```

## Interpretation

This smoke confirms that the capped graph no longer has oversized chunk content and the file orchestration stage can run on the capped chunks. It was not green enough to scale yet: two chunk calls failed schema validation because the old prompt/schema used the ambiguous `propose` field and the model emitted `propose=true` with a non-null `canonical`.

Follow-up decision after reviewing the failure:

Raw tag names are expected to be specific and often new. The proposal concept only applies when the broad canonical vocabulary is missing a fitting label. The schema/prompt should therefore use `canonical_missing`, not `propose`.

At that point, the next step was to retry the two failed chunk WorkItems under the `canonical_missing` schema/prompt, then rerun the file orchestration WorkItem so file relevance would cover all non-empty chunks. The follow-up retry below completed that step.

## Follow-Up Retry After Schema Rename

The schema and prompt were changed so raw tag novelty is represented by `name`, while missing canonical vocabulary is represented by `canonical_missing`.

Before retrying, the file orchestration WorkItem for `960f223de786daa74a7d0f70` was reset to `unrun`, and stale `File.description` / `Chunk.relevance_to_file` values for that file were cleared so the file step could be rerun after the failed chunks passed.

Retry command:

```powershell
.\.venv\Scripts\python.exe scripts\run_index.py --file-id 960f223de786daa74a7d0f70 --chunk-limit 2 --file-limit 1 --concurrency 2
```

Exact terminal output:

```text
Run started: 2026-05-07T13-52-46Z-7ec1b8
[orchestrator] reset 2 failed work items to unrun
[orchestrator] canonical vocab loaded; dataset_id filter = None; file_id filter = '960f223de786daa74a7d0f70'
[orchestrator] chunk stage: processed=2 done=2 failed=0
[orchestrator] file stage: processed=1 done=1 failed=0
[orchestrator] rollup wrote 56 (:File)-[:TAGGED]->(:Tag) edges
Run finished: ok
  chunks_done=2, chunks_failed=0
  files_done=1, files_failed=0
  tokens in/out = 5594/1343, duration_ms = 24490
```

Persisted retry run:

Note: the retry was executed from a working tree that already contained the `canonical_missing` schema/prompt changes, before those edits were committed. Therefore `Run.git_commit` records the previously committed SHA, not the final commit that documents this fix.

```json
{
  "run_id": "2026-05-07T13-52-46Z-7ec1b8",
  "status": "ok",
  "chunks_done": 2,
  "chunks_failed": 0,
  "files_done": 1,
  "files_failed": 0,
  "total_in_tokens": 5594,
  "total_out_tokens": 1343,
  "total_duration_ms": 24490,
  "git_commit": "78ad0b9de64cf75bb49c6de569b04f3ea3089b1e",
  "agent_model": "gpt-4o-mini",
  "agent_max_concurrency": 2
}
```

Final target-file state:

```json
{
  "target_workitems": [
    {"kind": "chunk_extraction", "status": "done", "n": 10},
    {"kind": "file_orchestration", "status": "done", "n": 1}
  ],
  "target_file_edges": {
    "has_tag": 62,
    "tagged": 56
  },
  "target_relevance": {
    "chunks": 10,
    "relevance_set": 10,
    "min_rel": 0.4,
    "max_rel": 0.9
  },
  "global_failed_workitems": 0
}
```

Canonical proposals observed during the retry:

```json
[
  {"label": "employee_role_in_review", "cluster": "information_need", "observed_count": 1},
  {"label": "user_education", "cluster": "information_need", "observed_count": 1}
]
```

Interpretation after retry: the file-scoped post-cap smoke is now green for this file. The new `canonical_missing` path works, and all non-empty chunks have file relevance.

## Complete Persisted Target Results After Retry

This is the complete persisted result for `Salesforce__HERB/products/ActionGenie.json` after the retry. The raw model response bodies are not available because the current pipeline parses them and writes only graph state. Everything below was read back from Neo4j.

Final file description:

```text
The JSON file contains comprehensive data relating to the ActionGenie product, particularly focusing on market research, team collaboration, and integration with communication platforms like Slack. It includes identifiers for team members and customers, discussions from Slack channels about the onForceX project, meeting transcripts reviewing key documents, and resources related to AI integration. Additionally, it lists various integrations and pulls requests crucial for real-time data processing, along with inquiries about document authors and roles. The content serves to support the development and marketing strategies for the onForceX product.
```

### Final Chunk Descriptions

| Ord | Chunk ID | Rel | Tokens | Chars | Description |
|---:|---|---:|---:|---:|---|
| 0 | `41f94ee80a3b23cd1517db28` | 0.4 | 261 | 1046 | This chunk contains a list of team member identifiers, represented as unique IDs. |
| 1 | `032c4ca28d9f0f6ad34af945` | 0.7 | 116 | 465 | This chunk contains a list of customer identifiers, possibly related to the ActionGenie product. |
| 2 | `1c495711230df5cdb2074e3c` | 0.8 | 1507 | 6029 | This chunk contains messages from a Slack channel discussing a project named onForceX, including planning details and feedback on documents shared within the team. |
| 3 | `7c06021fb642cee14a3530a1` | 0.9 | 1507 | 6029 | This chunk includes a market research report on the onForceX Smart Actions for Slack, detailing its features, target audience, and market potential. |
| 4 | `005497699f70e06a17dceac9` | 0.9 | 1507 | 6029 | The chunk contains meeting transcripts discussing feedback on the Market Research Report and Product Vision Document for a product called onForceX, including sections on AI technologies, competitive analysis, and user education strategies. |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | This chunk contains chat records from a meeting discussing various documents related to the onForceX project, including market research and product vision. |
| 6 | `2960d8e4619ac86535c7f888` | 0.5 | 1271 | 5086 | This chunk contains a list of URLs with descriptions related to AI integration in communication platforms and productivity enhancement tools. |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | This chunk lists several pull requests related to integrating various APIs and systems for real-time data processing and event handling across different applications. |
| 8 | `6da4c297bca324a46ee67759` | 0.7 | 1507 | 6029 | This chunk contains a series of questions related to employee IDs of authors and reviewers for various documents associated with the ActionGenie product, along with features related to integration with third-party Slack apps. |
| 9 | `1eff2a43f34dddfbd2a9fbe9` | 0.4 | 432 | 1729 | This chunk contains a list of unanswerable questions related to the ActionGenie product, focusing on various employee roles and documentation. |

### Final Chunk HAS_TAG Edges

This is every raw tag emitted for the ten chunks and written as `(:Chunk)-[:HAS_TAG]->(:Tag)`.

| Ord | Chunk | Rel | Tok | Chars | Tag | Cluster | Canonical | Local W | Tag Run |
|---:|---|---:|---:|---:|---|---|---|---:|---|
| 0 | `41f94ee80a3b23cd1517db28` | 0.4 | 261 | 1046 | `team_identifiers` | `object_entity` | `dataset` | 0.8 | `2026-05-07T13-26-16Z-9598ed` |
| 1 | `032c4ca28d9f0f6ad34af945` | 0.7 | 116 | 465 | `customer_identifiers` | `object_entity` | `dataset` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 2 | `1c495711230df5cdb2074e3c` | 0.8 | 1507 | 6029 | `slack_channel_creation` | `event_process` | `launch` | 0.8 | `2026-05-07T13-26-16Z-9598ed` |
| 2 | `1c495711230df5cdb2074e3c` | 0.8 | 1507 | 6029 | `user_engagement` | `event_process` | `change` | 0.6 | `2026-05-07T13-26-16Z-9598ed` |
| 2 | `1c495711230df5cdb2074e3c` | 0.8 | 1507 | 6029 | `ai_growth_statistics` | `information_need` | `number` | 0.6 | `2026-05-07T13-26-16Z-9598ed` |
| 2 | `1c495711230df5cdb2074e3c` | 0.8 | 1507 | 6029 | `market_research_report` | `object_entity` | `document` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 2 | `1c495711230df5cdb2074e3c` | 0.8 | 1507 | 6029 | `planning_onForceX` | `theme` | `technology` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 2 | `1c495711230df5cdb2074e3c` | 0.8 | 1507 | 6029 | `2026-06-09` | `time_relevance` | `active` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 3 | `7c06021fb642cee14a3530a1` | 0.9 | 1507 | 6029 | `ai_integration` | `event_process` | `launch` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 3 | `7c06021fb642cee14a3530a1` | 0.9 | 1507 | 6029 | `market_analysis` | `information_need` | `summary` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 3 | `7c06021fb642cee14a3530a1` | 0.9 | 1507 | 6029 | `slack` | `object_entity` | `product` | 0.8 | `2026-05-07T13-26-16Z-9598ed` |
| 3 | `7c06021fb642cee14a3530a1` | 0.9 | 1507 | 6029 | `onforcex_smart_actions` | `theme` | `technology` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 3 | `7c06021fb642cee14a3530a1` | 0.9 | 1507 | 6029 | `2026-06-10` | `time_relevance` | `future` | 0.8 | `2026-05-07T13-26-16Z-9598ed` |
| 4 | `005497699f70e06a17dceac9` | 0.9 | 1507 | 6029 | `feedback_session` | `event_process` | `decision` | 0.8 | `2026-05-07T13-52-46Z-7ec1b8` |
| 4 | `005497699f70e06a17dceac9` | 0.9 | 1507 | 6029 | `competitive_analysis` | `information_need` | `comparison` | 0.7 | `2026-05-07T13-52-46Z-7ec1b8` |
| 4 | `005497699f70e06a17dceac9` | 0.9 | 1507 | 6029 | `user_education` | `information_need` | `null` | 0.6 | `2026-05-07T13-52-46Z-7ec1b8` |
| 4 | `005497699f70e06a17dceac9` | 0.9 | 1507 | 6029 | `market_research_report` | `object_entity` | `document` | 0.9 | `2026-05-07T13-52-46Z-7ec1b8` |
| 4 | `005497699f70e06a17dceac9` | 0.9 | 1507 | 6029 | `product_vision_document` | `object_entity` | `document` | 0.9 | `2026-05-07T13-52-46Z-7ec1b8` |
| 4 | `005497699f70e06a17dceac9` | 0.9 | 1507 | 6029 | `onforceX` | `object_entity` | `product` | 0.8 | `2026-05-07T13-52-46Z-7ec1b8` |
| 4 | `005497699f70e06a17dceac9` | 0.9 | 1507 | 6029 | `2026_06_13` | `time_relevance` | `future` | 0.9 | `2026-05-07T13-52-46Z-7ec1b8` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `meeting_chats` | `event_process` | `decision` | 0.5 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `market_research_document` | `object_entity` | `document` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `product_requirements_document` | `object_entity` | `document` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `product_vision_document` | `object_entity` | `document` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `system_design_document` | `object_entity` | `document` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `technical_specifications_document` | `object_entity` | `document` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `onforcex_project` | `theme` | `technology` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `2026-06-13` | `time_relevance` | `future` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `2026-06-22` | `time_relevance` | `future` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `2026-07-04` | `time_relevance` | `future` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `2026-07-17` | `time_relevance` | `future` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 5 | `4437bb6daf1e9501a553dc5d` | 0.6 | 244 | 976 | `2026-07-30` | `time_relevance` | `future` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 6 | `2960d8e4619ac86535c7f888` | 0.5 | 1271 | 5086 | `ai_integration_productivity` | `information_need` | `summary` | 0.6 | `2026-05-07T13-26-16Z-9598ed` |
| 6 | `2960d8e4619ac86535c7f888` | 0.5 | 1271 | 5086 | `ActionGenie_demo_video` | `object_entity` | `document` | 0.8 | `2026-05-07T13-26-16Z-9598ed` |
| 6 | `2960d8e4619ac86535c7f888` | 0.5 | 1271 | 5086 | `TensorFlow_repository` | `object_entity` | `dataset` | 0.5 | `2026-05-07T13-26-16Z-9598ed` |
| 6 | `2960d8e4619ac86535c7f888` | 0.5 | 1271 | 5086 | `spaCy_repository` | `object_entity` | `dataset` | 0.5 | `2026-05-07T13-26-16Z-9598ed` |
| 6 | `2960d8e4619ac86535c7f888` | 0.5 | 1271 | 5086 | `integrating_ai_in_communication_platforms` | `theme` | `technology` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 6 | `2960d8e4619ac86535c7f888` | 0.5 | 1271 | 5086 | `ai_task_management_tools` | `theme` | `technology` | 0.6 | `2026-05-07T13-26-16Z-9598ed` |
| 6 | `2960d8e4619ac86535c7f888` | 0.5 | 1271 | 5086 | `2023` | `time_relevance` | `recent` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `integration_completed` | `event_process` | `change` | 0.8 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `pull_request_approval` | `event_process` | `decision` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `pull_request_summary` | `information_need` | `summary` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `mattermost_webhook_integration` | `object_entity` | `document` | 0.6 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `rocket_chat_event_api_integration` | `object_entity` | `document` | 0.6 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `slack_events_api_integration` | `object_entity` | `document` | 0.6 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `zulip_bot_event_handling` | `object_entity` | `document` | 0.6 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `data_pipeline_for_model_training` | `object_entity` | `document` | 0.5 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `real_time_data_processing` | `theme` | `technology` | 0.8 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `2025_completed` | `time_relevance` | `completed` | 0.5 | `2026-05-07T13-26-16Z-9598ed` |
| 7 | `e301f7e9611efb661c396761` | 0.7 | 1507 | 6029 | `2026_future` | `time_relevance` | `future` | 0.5 | `2026-05-07T13-26-16Z-9598ed` |
| 8 | `6da4c297bca324a46ee67759` | 0.7 | 1507 | 6029 | `document_authors_reviewers` | `event_process` | `publication` | 0.8 | `2026-05-07T13-26-16Z-9598ed` |
| 8 | `6da4c297bca324a46ee67759` | 0.7 | 1507 | 6029 | `employee_id_query` | `information_need` | `number` | 0.8 | `2026-05-07T13-26-16Z-9598ed` |
| 8 | `6da4c297bca324a46ee67759` | 0.7 | 1507 | 6029 | `actiongenie_product_documents` | `theme` | `technology` | 0.9 | `2026-05-07T13-26-16Z-9598ed` |
| 8 | `6da4c297bca324a46ee67759` | 0.7 | 1507 | 6029 | `third_party_integration_features` | `theme` | `technology` | 0.7 | `2026-05-07T13-26-16Z-9598ed` |
| 8 | `6da4c297bca324a46ee67759` | 0.7 | 1507 | 6029 | `future_scenarios_integration` | `time_relevance` | `future` | 0.6 | `2026-05-07T13-26-16Z-9598ed` |
| 9 | `1eff2a43f34dddfbd2a9fbe9` | 0.4 | 432 | 1729 | `bug_reporting` | `event_process` | `incident` | 0.7 | `2026-05-07T13-52-46Z-7ec1b8` |
| 9 | `1eff2a43f34dddfbd2a9fbe9` | 0.4 | 432 | 1729 | `employee_role_in_review` | `information_need` | `null` | 0.6 | `2026-05-07T13-52-46Z-7ec1b8` |
| 9 | `1eff2a43f34dddfbd2a9fbe9` | 0.4 | 432 | 1729 | `actiongenie` | `object_entity` | `product` | 0.9 | `2026-05-07T13-52-46Z-7ec1b8` |
| 9 | `1eff2a43f34dddfbd2a9fbe9` | 0.4 | 432 | 1729 | `market_research_report` | `object_entity` | `document` | 0.5 | `2026-05-07T13-52-46Z-7ec1b8` |
| 9 | `1eff2a43f34dddfbd2a9fbe9` | 0.4 | 432 | 1729 | `product_vision_document` | `object_entity` | `document` | 0.5 | `2026-05-07T13-52-46Z-7ec1b8` |
| 9 | `1eff2a43f34dddfbd2a9fbe9` | 0.4 | 432 | 1729 | `system_design_document` | `object_entity` | `document` | 0.5 | `2026-05-07T13-52-46Z-7ec1b8` |
| 9 | `1eff2a43f34dddfbd2a9fbe9` | 0.4 | 432 | 1729 | `technical_specifications_document` | `object_entity` | `document` | 0.5 | `2026-05-07T13-52-46Z-7ec1b8` |

### Final File TAGGED Rollup Edges

This is every `(:File)-[:TAGGED]->(:Tag)` edge after deterministic rollup.

| Tag | Cluster | Canonical | Global W | Chunks | Run |
|---|---|---|---:|---:|---|
| `feedback_session` | `event_process` | `decision` | 0.72 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `slack_channel_creation` | `event_process` | `launch` | 0.64 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `ai_integration` | `event_process` | `launch` | 0.63 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `document_authors_reviewers` | `event_process` | `publication` | 0.56 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `integration_completed` | `event_process` | `change` | 0.56 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `pull_request_approval` | `event_process` | `decision` | 0.49 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `user_engagement` | `event_process` | `change` | 0.48 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `meeting_chats` | `event_process` | `decision` | 0.3 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `bug_reporting` | `event_process` | `incident` | 0.28 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `market_analysis` | `information_need` | `summary` | 0.81 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `competitive_analysis` | `information_need` | `comparison` | 0.63 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `employee_id_query` | `information_need` | `number` | 0.56 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `user_education` | `information_need` | `null` | 0.54 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `pull_request_summary` | `information_need` | `summary` | 0.49 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `ai_growth_statistics` | `information_need` | `number` | 0.48 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `ai_integration_productivity` | `information_need` | `summary` | 0.3 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `employee_role_in_review` | `information_need` | `null` | 0.24 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `onforceX` | `object_entity` | `product` | 0.72 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `slack` | `object_entity` | `product` | 0.72 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `customer_identifiers` | `object_entity` | `dataset` | 0.63 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `market_research_report` | `object_entity` | `document` | 0.523 | 3 | `2026-05-07T13-52-46Z-7ec1b8` |
| `product_vision_document` | `object_entity` | `document` | 0.477 | 3 | `2026-05-07T13-52-46Z-7ec1b8` |
| `market_research_document` | `object_entity` | `document` | 0.42 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `mattermost_webhook_integration` | `object_entity` | `document` | 0.42 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `product_requirements_document` | `object_entity` | `document` | 0.42 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `rocket_chat_event_api_integration` | `object_entity` | `document` | 0.42 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `slack_events_api_integration` | `object_entity` | `document` | 0.42 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `zulip_bot_event_handling` | `object_entity` | `document` | 0.42 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `ActionGenie_demo_video` | `object_entity` | `document` | 0.4 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `actiongenie` | `object_entity` | `product` | 0.36 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `data_pipeline_for_model_training` | `object_entity` | `document` | 0.35 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `team_identifiers` | `object_entity` | `dataset` | 0.32 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `system_design_document` | `object_entity` | `document` | 0.31 | 2 | `2026-05-07T13-52-46Z-7ec1b8` |
| `technical_specifications_document` | `object_entity` | `document` | 0.31 | 2 | `2026-05-07T13-52-46Z-7ec1b8` |
| `TensorFlow_repository` | `object_entity` | `dataset` | 0.25 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `spaCy_repository` | `object_entity` | `dataset` | 0.25 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `onforcex_smart_actions` | `theme` | `technology` | 0.81 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `planning_onForceX` | `theme` | `technology` | 0.72 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `actiongenie_product_documents` | `theme` | `technology` | 0.63 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `real_time_data_processing` | `theme` | `technology` | 0.56 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `third_party_integration_features` | `theme` | `technology` | 0.49 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `onforcex_project` | `theme` | `technology` | 0.42 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `integrating_ai_in_communication_platforms` | `theme` | `technology` | 0.35 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `ai_task_management_tools` | `theme` | `technology` | 0.3 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2026_06_13` | `time_relevance` | `future` | 0.81 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2026-06-09` | `time_relevance` | `active` | 0.72 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2026-06-10` | `time_relevance` | `future` | 0.72 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2026-06-13` | `time_relevance` | `future` | 0.54 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2026-06-22` | `time_relevance` | `future` | 0.54 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2026-07-04` | `time_relevance` | `future` | 0.54 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2026-07-17` | `time_relevance` | `future` | 0.54 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2026-07-30` | `time_relevance` | `future` | 0.54 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2023` | `time_relevance` | `recent` | 0.45 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `future_scenarios_integration` | `time_relevance` | `future` | 0.42 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2025_completed` | `time_relevance` | `completed` | 0.35 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |
| `2026_future` | `time_relevance` | `future` | 0.35 | 1 | `2026-05-07T13-52-46Z-7ec1b8` |

### Final WorkItems

The initial failed schema-invalid state is recorded above under "WorkItem Results For Target File". After the retry, the current WorkItems for this target are all `done`:

| Kind | Target | Ord | Status | Run | In | Out | Ms | Error |
|---|---|---:|---|---|---:|---:|---:|---|
| `chunk_extraction` | `41f94ee80a3b23cd1517db28` | 0 | `done` | `2026-05-07T13-26-16Z-9598ed` | 1737 | 111 | 3614 | `null` |
| `chunk_extraction` | `032c4ca28d9f0f6ad34af945` | 1 | `done` | `2026-05-07T13-26-16Z-9598ed` | 1473 | 103 | 3533 | `null` |
| `chunk_extraction` | `1c495711230df5cdb2074e3c` | 2 | `done` | `2026-05-07T13-26-16Z-9598ed` | 2994 | 365 | 6912 | `null` |
| `chunk_extraction` | `7c06021fb642cee14a3530a1` | 3 | `done` | `2026-05-07T13-26-16Z-9598ed` | 2302 | 365 | 7162 | `null` |
| `chunk_extraction` | `005497699f70e06a17dceac9` | 4 | `done` | `2026-05-07T13-52-46Z-7ec1b8` | 2385 | 505 | 10205 | `null` |
| `chunk_extraction` | `4437bb6daf1e9501a553dc5d` | 5 | `done` | `2026-05-07T13-26-16Z-9598ed` | 1569 | 674 | 11925 | `null` |
| `chunk_extraction` | `2960d8e4619ac86535c7f888` | 6 | `done` | `2026-05-07T13-26-16Z-9598ed` | 2585 | 479 | 11688 | `null` |
| `chunk_extraction` | `e301f7e9611efb661c396761` | 7 | `done` | `2026-05-07T13-26-16Z-9598ed` | 2855 | 727 | 13928 | `null` |
| `chunk_extraction` | `6da4c297bca324a46ee67759` | 8 | `done` | `2026-05-07T13-26-16Z-9598ed` | 3215 | 378 | 6397 | `null` |
| `chunk_extraction` | `1eff2a43f34dddfbd2a9fbe9` | 9 | `done` | `2026-05-07T13-52-46Z-7ec1b8` | 1500 | 497 | 8921 | `null` |
| `file_orchestration` | `960f223de786daa74a7d0f70` |  | `done` | `2026-05-07T13-52-46Z-7ec1b8` | 1709 | 341 | 5364 | `null` |

### Final Canonical Proposals

These came from `canonical_missing=true`, meaning the model emitted a raw tag but did not find a suitable broad canonical in the seed vocabulary.

| Label | Cluster | Ord | Observed | Run | Gloss | Rationale |
|---|---|---|---:|---|---|---|
| `employee_role_in_review` | `information_need` | `9` | 1 | `2026-05-07T13-52-46Z-7ec1b8` | Role of employees in the review process of documents. | No broad evidence canonical captures employee roles in document reviews. |
| `user_education` | `information_need` | `4` | 1 | `2026-05-07T13-52-46Z-7ec1b8` | Strategies for educating users about the product. | No broad evidence canonical captures educational strategy. |
