# HERB Tagging Frames

**Last updated:** 2026-05-13.

## Purpose

HERB tagging should not ask the model to infer how to read a chunk from internal
pipeline labels. The chunker and tagging harness know the source shape; they
must choose the right interpretation frame before making the model call.

For the exact model-facing input/output contract and weight semantics, see
[`herb_tagging_schema.md`](herb_tagging_schema.md).

The model should receive only information that helps it describe and tag the
evidence. Internal IDs, chunk refs, file paths, and chunk-kind names are kept in
`run.json`, Neo4j properties, and analysis reports for operator traceability.
They are not part of the semantic extraction request unless the value itself is
content evidence.

## Why

The first HERB tagging pilots (`pilot_001`, `pilot_002`) proved the mechanics of
graph-native tagging, but they ran on the old HERB chunk shape where most chunks
were single JSON records. That made the model overfit to record structure:
structured rows often produced repeated tags such as `raw_data`, and weights
anchored to a few round values.

The new HERB chunker produces different evidence shapes:

- thin directory batches
- product profiles
- org-tree records
- conversation batches
- product documents and document parts
- meeting transcripts and transcript parts
- pull request batches
- answerable QA records
- QA citation overflow chunks
- URL/reference lists
- unanswerable question batches

Those should not all be read with the same model input. A thin table is mostly
headers plus lookup rows. A document part is prose evidence. A QA record has a
question intent, an answer, and citations. A citation overflow chunk is not the
question itself; it is supporting evidence for a known question.

## Rule

The pipeline uses source shape as routing state:

```text
Chunk.kind / locator / section
        -> deterministic frame renderer
        -> agent receives task-specific source evidence
        -> agent returns description + facet tags + weights
```

The agent should not receive raw internal labels such as:

- `Chunk kind`
- `Chunk reference`
- `Parent reference`
- `Chunk type`
- `Source file`
- `chunk_id`

Those are useful for debugging and traceability, but they are not semantic
evidence for the extraction task.

## Frame Examples

### Thin Directory Batch

Input shape:

```text
Source: personnel directory table
Headers: employee_id, name, role, location, org

Rows:
{"employee_id": "...", "name": "...", "role": "...", ...}
```

Interpretation:

- use headers to understand what the table represents
- use values for people, roles, organizations, locations, and lookup keys
- do not treat each row as an article
- do not tag generic field names as concepts

### Rich Document Or Document Part

Input shape:

```text
Source: product document excerpt from SearchForce
Metadata:
{...}

Text field: content
---
...
---
```

Interpretation:

- use metadata only as context
- tag the actual document text
- do not let repeated field names dominate the tags
- for parts, describe only the excerpt, not the full document

### QA Record

Input shape:

```text
Source: answerable question record from AnomalyForce
Use the question as the retrieval intent and the answer/citations as evidence.

Question record:
{...}
```

Interpretation:

- the question expresses retrieval intent
- the answer and citations are evidence
- tags should preserve answerable facts and lookup handles

### QA Citation Part

Input shape:

```text
Source: citation evidence for an answerable question from ActionGenie
Use the question/answer as context and the citations as supporting evidence.

Question and answer:
{...}

Citations:
...
```

Interpretation:

- the chunk is supporting evidence, not a full QA record
- use the question and answer to frame the citation list
- tag cited artefacts, identifiers, products, and answer-supporting evidence

### Conversation Batch

Input shape:

```text
Source: conversation messages from ConnectForce
Use message text, participants, timestamps, links, decisions, and requests.

Messages:
...
```

Interpretation:

- read as a conversation, not as polished prose
- tag decisions, requests, discussed artefacts, linked evidence, people, dates,
  and products when present

## Current Implementation

`backend/tagging/pipeline.py` contains the pilot implementation:

- `stage_verify_chunks()` checks that the current HERB graph exposes the new
  chunk format.
- `choose_chunks()` defaults to one representative chunk per HERB evidence
  shape for format-smoke pilots.
- `render_chunk_user_message()` maps internal chunk shape to an agent-facing
  frame.
- `stage_extract()` sends only that rendered frame to the model.
- `stage_describe()` and `stage_score()` send only descriptions/summaries to the
  model.
- `stage_analyze()` keeps refs/kinds for operator reporting, not as model
  evidence.

The current clean HERB graph has no tag outputs. A tagging pilot should start
with:

```powershell
py -3.12 -m tagging verify-chunks
py -3.12 -m tagging select
```

Only after inspecting the selected frame coverage should the operator run:

```powershell
py -3.12 -m tagging extract
py -3.12 -m tagging describe
py -3.12 -m tagging score
py -3.12 -m tagging analyze
```

## Open Design Questions

- Whether thin table batches should produce chunk-level tags only, or also
  section/file-level tags later.
- Whether `evidence` should be suppressed or redefined for thin structured
  tables where every row is inherently structured evidence.
- Whether the current ordinal rank buckets and deterministic numeric mappings
  need calibration after the smoke run.
- Whether file descriptions should be generated only after all chunks in a file
  are extracted, instead of from pilot samples.
