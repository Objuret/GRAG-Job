# HERB Tagging Schema

**Last updated:** 2026-05-14.

## Purpose

This is the contract for the HERB tagging pilot model calls. It documents the
complete model-facing input shape, the forced structured output schemas, the
code-side processing applied to model output, and the analysis report
produced by the analyze stage.

This file is normative for `backend/tagging/pipeline.py`. If the model-facing
input, output schema, weight semantics, or analysis surface change, update
this document in the same change.

## Non-Contamination Rule

The model receives only information that is semantically relevant to the task
it is doing. Internal pipeline machinery is never sent as model evidence:

- `chunk_id`, `file_id`, `locator_json`, `kind`, `chunk_ref`, `parent_ref`
- raw file paths
- operator-only notes
- implementation labels such as "Chunk kind" or "Chunk reference"

Those values stay in Neo4j, `run.json`, `io.jsonl`, and `analysis.md` for
traceability.

**Scope of this rule (important).** Non-Contamination governs only what is
sent to the *tagging model as evidence*. It does **not** mean hard structured
fields are kept out of the graph as queryable data. They are deliberately
materialized as indexed `:Chunk` properties by the `materialize` stage so
retrieval can hard-gate on them *before* tagging — see the `materialize`
section below and [`graph_schema.md`](graph_schema.md). Keeping field names out
of the model prompt and exposing them as a query surface are independent
goals; both hold. A single irrelevant word in repeated prompt context can become
a repeated semantic feature, so the default is to exclude it unless it is
actual source evidence.

## Provider And API Envelope

- Provider: Anthropic Messages API
- Default model: `claude-haiku-4-5`
- Code path: `backend/tagging/pipeline.py`
- Wrapper: `ClaudeCaller`
- Output mode: forced Anthropic `tool_use`
- `max_tokens`: 8192 (large enough to hold the batched score-stage output for
  the largest HERB file at ~240 chunks)

API envelope:

```json
{
  "model": "claude-haiku-4-5",
  "max_tokens": 8192,
  "system": "<stage-specific system prompt>",
  "messages": [
    {"role": "user", "content": "<stage-specific rendered evidence>"}
  ],
  "tools": [
    {
      "name": "<schema_name>",
      "description": "Return the structured result for this task.",
      "input_schema": "<stage-specific JSON schema>"
    }
  ],
  "tool_choice": {"type": "tool", "name": "<schema_name>"},
  "temperature": 0.3
}
```

`response_reasoning` is null on this provider. The diagnostic surface is the
returned structured data plus `analysis.md`.

## Stages

```text
select -> extract -> describe -> score -> embed-tags -> materialize -> analyze
```

`materialize` is deterministic and makes no LLM calls. It has two parts with
**different dependencies** — do not pretend it is purely pre-tagging:

- **Scalars** (locator-derived) depend only on chunking and could run any time.
- **`years`** is projected from each chunk's `temporal`-facet tag names, so it
  depends on `extract`. Running `materialize` after `extract` (shown above)
  populates both in one pass. If run before `extract`, scalars are written and
  `years` is simply empty until a later re-run — the stage says so and is safe
  to repeat.

It processes the whole HERB graph, not the `select` sample.

`extract` is **two-pass internally** — see Stage 1 below. `describe` and
`score` are single-call per file. `embed-tags` and `analyze` make no LLM API
calls. `embed-tags` is independent of `describe`/`score`; it only needs
`extract` to have written `:Tag` nodes and `Chunk.description`.

## Stage 1: Extract — two-pass

### Pass 1: tag extraction

Model emits a flat list of retrieval-handle tag strings plus a 1–3 sentence
chunk description. No weights, no facets.

System prompt (`EXTRACT_PROMPT`):

```
## Description

Describe the chunk's content in 1-3 sentences.

## Tags

List the retrieval handles present in the chunk: people, organisations,
products, places, dated events, decisions, document subjects, evidence types.

Keep proper names whole. Include central concepts and peripheral lookup
handles.

A retrieval handle is NOT a common verb, preposition, transitional word,
sentence fragment, or generic category like "report" or "discussion".

Do not invent concepts the text does not contain.
```

User message: `render_chunk_user_message(row)` — a deterministic kind-specific
frame from `Chunk.kind` + `Chunk.content`. No internal labels.

Output schema (tool `chunk_extraction`):

```json
{
  "type": "object",
  "required": ["description", "tags"],
  "additionalProperties": false,
  "properties": {
    "description": {"type": "string", "minLength": 1},
    "tags": {"type": "array", "items": {"type": "string", "minLength": 1}}
  }
}
```

After pass 1 the pipeline cleans (`clean_tag_name`) and dedupes the tag list
before pass 2 sees it.

### Pass 2: tag scoring

For each tag from pass 1, the model returns its fit to each of five facets.
The model does NOT emit a `w_chunk`; `w_chunk` is derived in code from the
facet vector (see "Code-Side Processing" below).

System prompt (`SCORE_TAGS_PROMPT`):

```
For each tag, weight its fit to every facet.

## Facets

| Facet    | Captures                                                                                    |
|----------|---------------------------------------------------------------------------------------------|
| topic    | Subject matter                                                                              |
| entities | Named people, organisations, products, systems, places                                      |
| activity | Actions, processes, events                                                                  |
| temporal | Dates and time expressions present verbatim in the text                                     |
| evidence | Kind of information: definition, example, metric, argument, procedure, case_study, raw_data |

## Weights

- `facets.<name>` — fit of this tag to that facet (1.00 = unambiguous, 0.00 = does not belong).
```

User message:

```
Chunk:
<the same frame from pass 1>

Tags:
- t1
- t2
- ...
```

Output schema (tool `tag_scoring`):

```json
{
  "type": "object",
  "required": ["scores"],
  "additionalProperties": false,
  "properties": {
    "scores": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["t", "facets"],
        "additionalProperties": false,
        "properties": {
          "t": {"type": "string", "minLength": 1},
          "facets": {
            "type": "object",
            "required": ["topic", "entities", "activity", "temporal", "evidence"],
            "additionalProperties": false,
            "properties": {
              "topic":    {"type": "number", "minimum": 0, "maximum": 1},
              "entities": {"type": "number", "minimum": 0, "maximum": 1},
              "activity": {"type": "number", "minimum": 0, "maximum": 1},
              "temporal": {"type": "number", "minimum": 0, "maximum": 1},
              "evidence": {"type": "number", "minimum": 0, "maximum": 1}
            }
          }
        }
      }
    }
  }
}
```

## Stage 2: Describe

System prompt (`DESCRIBE_PROMPT`):

```
Describe the file's central concerns in 2-3 sentences, based on the chunk
descriptions provided.
```

User message:

```
Evidence summaries from this file, in source order:
1. <chunk description>
2. <chunk description>
...
```

Output schema (tool `file_description`):

```json
{"type":"object","required":["file_summary"],"additionalProperties":false,
 "properties":{"file_summary":{"type":"string","minLength":1}}}
```

## Stage 3: Score — batched per file

All chunks of a file are scored in one call so the model has to differentiate
representativeness comparatively, not in isolation. The model returns a list
of `(i, w_chunk_file)` pairs where `i` is the 1-based index into the chunk
list it received.

System prompt (`SCORE_PROMPT`):

```
For each numbered chunk, score how representative it is of the file. 1.00 =
core example, 0.00 = off-topic.
```

User message:

```
File summary:
<file description>

Chunks:
1. <chunk description>
2. <chunk description>
...
```

Output schema (tool `chunk_file_score`):

```json
{
  "type": "object",
  "required": ["scores"],
  "additionalProperties": false,
  "properties": {
    "scores": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["i", "w_chunk_file"],
        "additionalProperties": false,
        "properties": {
          "i": {"type": "integer", "minimum": 1},
          "w_chunk_file": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    }
  }
}
```

The 1-based index maps back to chunk_id locally; the model never sees
chunk_id.

## Code-Side Processing

### `clean_tag_name(raw)`

```python
s = raw.strip().lower()
s = re.sub(r"[^a-z0-9]+", "_", s)
return s.strip("_")
```

Drop if cleaned name is empty.
Drop if cleaned name in `FILLER = {"data", "information", "content", "record", "text", "chunk", "item"}`.

### `compute_w_chunk(facets)` — derived chunk centrality

`w_chunk` is NOT emitted by the model. It is computed from the 5 facet
scores returned by Stage 1 pass 2:

```text
w_chunk = strength × coverage_bonus

strength       = sqrt(sum(f²) / N)
coverage_bonus = ((sum(f))² / (N × sum(f²))) ^ α

with N = 5  (number of facets)
     α = 0.25  (coverage sensitivity)
```

If `sum(f²) == 0` the function returns 0.

Why this formula:

- `strength` is the raw semantic force of the tag across all facets.
- `coverage_bonus` measures how spread the force is. `(sum(f))² / sum(f²)` is
  the effective number of active facets — 1 when the force is concentrated in
  one facet, N when spread evenly across all N. Dividing by N normalises to
  [0, 1]. `α = 0.25` softens the spread bonus so it complements strength
  rather than dominates it.
- A tag scoring `1.00` in two facets scores higher than a tag scoring `1.00`
  in one facet, by design. This is the property the smoke pilot's analysis
  validated.

### Multi-facet emission

For each tag, the pipeline writes a `HAS_TAG` edge for the **primary facet**
(`argmax(facets)`) plus one edge per other facet with `facets[other] >=
MULTI_FACET_THRESHOLD = 0.50`. So a tag that genuinely plays multiple roles
contributes multiple edges; a tag that only fits one facet contributes one.

### Score rounding and dedup

`w_chunk`, `w_facet`, and `w_chunk_file` are rounded to 2 decimal places
before writing to Neo4j. Within a `(chunk, facet)` group, tags are deduped by
cleaned name, keeping the entry with max `w_chunk`.

## Neo4j Writes (database `herb`)

```cypher
SET c.description = <pass-1 description>
SET f.description = <describe output>
SET c.relevance_to_file = <round(w_chunk_file, 2)>

MERGE (t:Tag {name: <cleaned_name>})
CREATE (c)-[:HAS_TAG {
  facet:    <"topic"|"entities"|"activity"|"temporal"|"evidence">,
  w_chunk:  <float in [0,1], derived>,
  w_facet:  <float in [0,1], from model>,
  run_id:   <pilot_name>
}]->(t)
```

Re-extracting a chunk wipes its existing `HAS_TAG` edges before writing fresh
ones. The same `(chunk, tag)` pair may have multiple edges — one per
`(chunk, tag, facet)` tuple — when the tag is multi-facet.

## Disk Persistence

`io.jsonl` (one line per API call, all stages):

```json
{
  "ts": "...",
  "stage": "extract|score_tags|describe|score",
  "target_id": "<chunk_id or file_id>",
  "attempt": 1,
  "provider": "anthropic",
  "model": "claude-haiku-4-5",
  "request": {"system": "...", "user": "..."},
  "response_tool_input": {...},
  "response_text": null,
  "response_reasoning": null,
  "stop_reason": "tool_use",
  "usage": {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N},
  "duration_ms": N
}
```

`errors.jsonl` is only created when an API call fails.
`run.json` holds pilot metadata, the selected chunk IDs, and `stages_done`.

## Stage: Materialize — hard structured fields (no LLM)

`python -m tagging materialize`. Lifts the structured keys the chunker already
parsed into `locator_json` into typed, indexed `:Chunk` properties, plus a
best-effort `years` list parsed from the chunk body. This is the user's
intended design: hard fields exist as a queryable, deterministic gate **before**
tagging — retrieval filters on them before any tag/embedding work
([`../frontend/query_interpretation_layer.md`](../frontend/query_interpretation_layer.md)).

- Reads every `:Chunk` under `File.dataset_id = Salesforce__HERB` plus its
  `temporal`-facet tag names. No sampling, no API.
- `derive_chunk_fields(locator)` → the locator scalars in the `:Chunk`
  "Hard fields" table in [`graph_schema.md`](graph_schema.md). Every key is
  always written (value or `null`); a `null` in `SET c += map` **removes** the
  property, so a re-run after re-chunking clears fields that no longer apply.
- `years_from_tag_names(names)` → sorted unique literal 4-digit tokens
  (`1800–2099`) in the temporal tag names, capped 64, **`None` when empty**
  (so the property is absent — same sparse rule as every scalar, no empty-list
  sentinel). No range expansion: `2023_2028` → `[2023, 2028]`.
- `SET c += row.fields` in 500-row batches.
- `ensure_hard_field_indexes` creates indexes only for the four gated scalars
  (`product`, `section`, `channel`, `employee_id`) + `kind` + the
  `chunk_fulltext` index, and **drops** the obsolete `chunk_parent_ref`/
  `chunk_chunk_ref`/`chunk_metadata_section`/`chunk_subsection`/
  `chunk_doc_field` indexes a prior version created but nothing queries.
  Mirrors [`../../backend/schema/indexes.cypher`](../../backend/schema/indexes.cypher).
- Idempotent (verified: two consecutive live runs produced identical
  coverage). Prints per-field coverage and records `materialize` in
  `run.json` `stages_done`.

## Stage: Embed-tags — tag grounding bridge (no LLM)

`python -m tagging embed-tags`. Embeds every observed `(tag, facet)` plus one
broad `(tag, all)` record so free-form prompt tags can be matched to corpus
tag uses by vector similarity instead of exact string equality (see
[`query_interpretation_layer.md`](../frontend/query_interpretation_layer.md)).

- Model: `EMBEDDING_MODEL` env (default `intfloat/e5-small-v2`, 384-d), run
  locally via `sentence-transformers`. No API key, reproducible. The browser
  embeds prompt tags with the **same** model id so vectors are comparable.
- Input text per tag/facet scope (e5 passage convention):
  `passage: {name_with_spaces}. {facet scope}. {up to EMBED_CONTEXT_CHUNKS
  chunk descriptions where the tag occurs in that scope, highest occurrence
  strength first}`. Occurrence strength for choosing representative context is
  `w_chunk * w_facet`; it is not a global tag/facet weight. Retrieval scoring
  still joins back to each individual `HAS_TAG` edge and uses that edge's own
  `w_chunk` and `w_facet`. The bare snake_case name carries little signal;
  grounding quality comes from real corpus context.
- Writes the vectors as `:Tag` properties: `emb_topic … emb_evidence` (one per
  HERB facet where the tag occurs) plus `emb_all`, and `embedding_model`. There
  are no companion embedding nodes. Existing `HAS_TAG` edges and weights are not
  changed — this is a tag-vocabulary lookup index, not graph semantics.
- Creates one native vector index per facet (also in
  [`schema/vector_indexes.cypher`](../../backend/schema/vector_indexes.cypher)):

```cypher
CREATE VECTOR INDEX tag_emb_<facet> IF NOT EXISTS
FOR (t:Tag) ON (t.emb_<facet>)
OPTIONS { indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
} }
-- one each for facet ∈ {topic, entities, activity, temporal, evidence, all}
```

Re-running the stage first clears every stale `emb_*` vector (a tag that lost a
facet must not keep an old vector for it), then rebuilds them for the target
database. If the embedding model changes, re-run this stage and rebuild the
indexes if dimensions change.

## Stage 4: Analyze — `analysis.md`

No API calls. Reads Neo4j and `io.jsonl` and writes `analysis.md` with:

- Header (run name, model, dataset, sample size, kinds covered)
- Per-chunk dump (description + tags grouped by facet, sorted by w_chunk)
- Per-file dump (rel_path + file summary + sampled chunks)
- Tag stats: edge count, unique tag names, edges per facet, top occurrences,
  tags appearing in ≥2 facets, tags-per-chunk distribution, telegram-mode flag
- Weight distributions per axis (n, range, mean, stdev, distinct values @ 2dp,
  0.05-bin histogram)
- Round-anchoring check per axis
- Cross-tab: `w_chunk` mean and distinct count by evidence kind
- Cost / perf (calls per stage, tokens, summed duration)
- Verdict markers (distinct values, anchoring rate, low-range fraction,
  telegram-mode trigger, multi-facet tag rate)
