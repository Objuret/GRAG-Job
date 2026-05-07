# Prompts

**TL;DR.** Two LLM prompts are in active use: [`extract_chunk.md`](../prompts/extract_chunk.md) (Stage 1) and [`file_descriptor.md`](../prompts/file_descriptor.md) (Stage 2). Both return a single JSON object validated by a pydantic model in [`agents/schemas.py`](../agents/schemas.py). When you edit a prompt's JSON shape, you **must** update the matching pydantic model in the same change.

**When to read this.** Before editing any file under [`prompts/`](../prompts/). Also before changing [`agents/schemas.py`](../agents/schemas.py).

**Last updated:** 2026-05-07.

## Touched paths

`prompts/`, `agents/schemas.py`, `indexing/orchestrator.py`, `indexing/extraction_writer.py`, `indexing/file_writer.py`.

## Common ground

- **One LLM call per prompt invocation.** The agent client is configured for `response_format=json_object`. Output must be a single JSON object — no markdown, no prose, no code fences.
- **Failure handling lives in the orchestrator.** [`agents/client.py`](../agents/client.py) catches httpx and pydantic errors and returns a typed `error_class`. [`indexing/orchestrator.py`](../indexing/orchestrator.py) marks the WorkItem `failed` with that class. Auto-retry-all on next run picks it up.
- **Schemas are the contract.** Edit the prompt and the pydantic model together — never one without the other.

## `prompts/extract_chunk.md`

### Purpose

Per-chunk extraction. Called for every `chunk_extraction` WorkItem in [`Orchestrator._process_chunk`](../indexing/orchestrator.py). Returns a five-cluster tag set, a 1-3 sentence chunk description, and an optional empty verdict.

### Inputs the orchestrator injects (in the user message)

Built by [`Orchestrator._render_chunk_user_message`](../indexing/orchestrator.py):

- `File: {dataset_id}/{rel_path}  (format={format_family})`
- `Chunk ordinal: {ordinal}, kind: {kind}, end_offset: {end_offset}`
- The canonical-vocab block (one line per cluster: `- {cluster}: label1, label2, ...`). Built once per run by `_load_canonical_vocab`. The cluster order is fixed: `theme, object_entity, event_process, time_relevance, information_need`.
- For sequential-mode files (PDF/HTML/DOCX/MD/TXT), if a previous chunk exists, its last 240 characters are included as: `Previous chunk ended with: "...{tail}"` (constant `PREV_TAIL_CHARS = 240`).
- The chunk content itself, fenced by `---` separators.
- A trailing line: `Output JSON. Set chunk_end_offset = {end_offset}.`

The system message is the prompt file's body verbatim.

### Output schema

[`ChunkExtraction`](../agents/schemas.py):

```python
class ChunkExtraction(BaseModel):
    chunk_end_offset: int = Field(ge=0)
    empty: bool = False
    empty_reason: str | None = None
    description: str | null = None
    tags: list[Tag] = Field(default_factory=list)
```

`Tag` requires either `canonical` set (mapped to a known canonical) **or** `propose=True` with a `gloss`. See the model validators in [`agents/schemas.py`](../agents/schemas.py).

### Validation / retry behaviour

The orchestrator marks the WorkItem `failed` when:

- The agent client returns `error_class != "ok"`. Most cases bubble up directly (`http_429`, `http_5xx`, `timeout`, `network`, `http_auth`, `http_quota_exceeded`, `http_other`, `schema_invalid`). The breaker observes every error class.
- `error_class == "ok"` but `parsed.chunk_end_offset != graph.end_offset`. Marked `failed` with `error_class="schema_validation"` and a message of the form `chunk_end_offset mismatch: agent=X graph=Y`. The breaker is **not** invoked for this synthetic class — it's only reflected in the WorkItem table.

A `schema_invalid` rate of ≥ 20% over 50 calls trips the breaker and aborts the run.

### Editing guidelines

- **Never** change the JSON shape without updating `ChunkExtraction` / `Tag` in [`agents/schemas.py`](../agents/schemas.py) in the same commit.
- **Never** rename a cluster string without updating the `Cluster` Literal and the canonical seed YAML and the user-message renderer's `CLUSTER_ORDER`.
- The chunk_end_offset echo check is the orchestrator's only way to detect "the model hallucinated a different chunk". Keep the prompt explicit about copying it verbatim.
- The empty-vs-content invariant is enforced by `ChunkExtraction._validate_empty_vs_content`. Don't add a third state.
- Proposal tags must set `canonical=null`; never show examples or wording where `propose=true` appears with a non-null canonical.
- Keep tag count guidance ("3-10 typical") in sync with what the breaker can absorb. A surge of 30+ tags per chunk inflates token cost without improving retrieval.

## `prompts/file_descriptor.md`

### Purpose

Per-file orchestration. Called for every `file_orchestration` WorkItem in [`Orchestrator._process_file`](../indexing/orchestrator.py). Returns a 3-5 sentence file description and a `chunk_relevance` map covering **every** non-empty chunk_id.

### Inputs the orchestrator injects

Built by [`Orchestrator._render_file_user_message`](../indexing/orchestrator.py):

- `File: {dataset_id}/{rel_path}  (format={format_family})`
- `Chunks (non-empty): N`
- An `Inventory:` line per chunk in ordinal order:
  - `chunk_id={cid}, ordinal={n}, kind={kind}: "{description (truncated to FILE_INVENTORY_DESC_MAX=400 chars)}", tags=[{name(cluster):weight, ...}]`
- A trailing instruction: `Output JSON: a 3-5 sentence file description plus a chunk_relevance map covering EVERY chunk_id above.`

The model **does not see raw chunk content** — only the descriptions and tag summaries that Stage 1 produced. This bounds prompt size and forces the model to use Stage 1 outputs as the unit of evidence.

### Output schema

[`FileOrchestrationOutput`](../agents/schemas.py):

```python
class FileOrchestrationOutput(BaseModel):
    description: str = Field(min_length=1)
    chunk_relevance: dict[str, float] = Field(default_factory=dict)
```

`chunk_relevance` values are validated to be in [0, 1] by `_validate_relevance_range`.

### Validation / retry behaviour

In addition to the standard `error_class` handling, the orchestrator validates that **every** non-empty chunk_id of the file appears as a key in `chunk_relevance` exactly once. Otherwise the WorkItem is marked `failed` with `error_class="schema_validation"` and a message of the form `chunk_relevance must cover every chunk_id exactly once; missing=[...] extra=[...]`.

This guarantees the rollup at Stage 3 has a relevance value for every chunk that contributed tags. (Files where the orchestrator hasn't run yet still get a sensible default of 0.5 in [`indexing/file_rollup.py`](../indexing/file_rollup.py), but the orchestrated path requires full coverage.)

### Editing guidelines

- Don't change the chunk_relevance key shape (must be a string `chunk_id`). The orchestrator does set-equality on the keys; renaming would silently break every file.
- The "use the full 0..1 range" guidance is necessary because models tend to bunch scores around 0.5 when not pushed. Keep that wording.
- The model **must not** invent or omit chunk_ids. The orchestrator detects both.
- Don't widen the description beyond ~5 sentences — it lands directly on `:File.description` and is meant to be human-scannable.

## Editing checklist

When you change any prompt:

- [ ] Pydantic model in [`agents/schemas.py`](../agents/schemas.py) matches the JSON shape, including required vs optional fields and value bounds.
- [ ] Orchestrator's user-message renderer (`_render_chunk_user_message` or `_render_file_user_message`) injects all the variables the prompt expects.
- [ ] The chunk_end_offset echo (Stage 1) and chunk_relevance key set (Stage 2) checks still hold.
- [ ] Cluster names in the prompt match the `Cluster` Literal in [`agents/schemas.py`](../agents/schemas.py).
- [ ] `prompts.md` (this doc) and any cross-linked sections in [`agent_brief.md`](agent_brief.md) / [`architecture.md`](architecture.md) are updated.
