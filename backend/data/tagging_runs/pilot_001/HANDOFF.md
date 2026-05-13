# HERB Semantic Tagging Pilot — Handoff

This is the full record of pilot run `pilot_001`. An agent picking this up in
a fresh chat with no other context should be able to read this document and
continue the work without asking the user clarifying questions. If a question
is unavoidable, it should at least be a precise question.

---

## 0. Quick start for the new agent

**Read order:** §1 (what this is for), §3 (where we landed and what's open),
§4–6 (design and code), §7 (results), §8 (the load-bearing finding), §9 (your
next steps), §10 (gotchas you'd otherwise hit).

**Most likely primary task for you:** address the weight-anchoring finding in
§8, then propose / run pilot_002 with a fix and compare. Do NOT start the full
968-chunk run until weight anchoring is resolved — see §9 item 1.

**Before you write any code:** there is an existing backend pipeline in
`backend/indexing/` (different vocabulary, canonical-tag mapping, different
weights). The new tagging code is in a SEPARATE package `backend/tagging/`
and writes to a SEPARATE Neo4j database (`herb`). Do not conflate the two.
See §4.

**Conventions the user has been emphatic about** (§11) — read those before
proposing prompt or code changes.

---

## 1. Goal

A thesis-stage data-indexing pipeline for retrieval. Four source datasets;
HERB is dataset 1 of 4. Each dataset is chunked into a Neo4j graph; an LLM
adds semantic tags and descriptions so chunks can be retrieved by concept.

This pilot validates ONE design (the "five-facet, two-weight" design — §2.2,
§2.3) on a 10-chunk sample of HERB before committing to it at scale.

HERB Neo4j state at start of pilot (database `herb`):
- 1 `:Source` node
- 33 `:File` nodes
- 968 `:Chunk` nodes, all with `kind="record"`
- 935 `:NEXT` edges (ordinal-ordered chunk linked list within each file)
- Chunks carry their text content. No descriptions / tags / scores yet.

Chunks are structured records. Most of HERB is JSON-record-per-chunk
(employees, customers); one file (`CollaborateForce.json`) is a long Slack
conversation that chunked into prose-style records.

---

## 2. Design decisions, locked in before any code

These are not up for casual re-litigation. They explain why the pipeline is
the shape it is. Each item gives the decision + why + what was rejected.

### 2.1 Three stages run in sequence, separate process per stage

```
select   → pick N random chunks, save IDs (reproducible)        [no API calls]
extract  → per-chunk: description + 5 facets of weighted tags   [N calls]
describe → per-file: 2-3 sentence file description              [F calls; F = unique files in sample]
score    → per-chunk: representativeness vs its file            [N calls]
analyze  → rolls everything up into a human-readable report     [no API calls]
```

Each stage is a separate `python -m backend.tagging <stage>` invocation. Stages
gate on the previous one being recorded as done in `run.json`. Why: lets the
operator inspect the disk artefacts between stages, abort cheaply, and
re-run a single stage without redoing earlier ones. Rejected alternative: one
big script with a `--stage` flag (still tries to be monolithic, harder to
inspect intermediate state).

### 2.2 Facet vocabulary — five, named per the brief

| Facet    | Captures                                                                                    |
|----------|---------------------------------------------------------------------------------------------|
| topic    | Subject matter                                                                              |
| entities | Named people, organisations, products, systems, places                                      |
| activity | Actions, processes, events                                                                  |
| temporal | Dates and time expressions present verbatim in the text                                     |
| evidence | Kind of information: definition, example, metric, argument, procedure, case_study, raw_data |

These deliberately do NOT reuse the older codebase's cluster names
(`theme`, `object_entity`, `event_process`, `time_relevance`,
`information_need` in `backend/indexing/`). The new design also discards
canonical-tag mapping entirely. Tags are just labels, normalised in code.

### 2.3 Two weights per tag + one per-chunk score

- `w_chunk` — float[0,1] — centrality of this tag to this chunk (1.0 core, 0.1 passing mention)
- `w_facet` — float[0,1] — fit of this tag to its facet (1.0 unambiguous, 0.1 forced)
- `w_chunk_file` — float[0,1] — how representative this chunk is of the file (1.0 core example, 0.0 off-topic). One value per chunk, NOT per tag.

### 2.4 Storage shape — Option A, graph-native, NOT JSON blobs on Chunk

After explicit discussion, the user chose graph-native storage. The new
design extends the existing Tag/HAS_TAG structure with its OWN field names
(not bent versions of the old property names):

```
Chunk.description            string         (existing nullable field; from stage extract)
Chunk.relevance_to_file      float[0,1]     (existing nullable field; from stage score — this IS w_chunk_file)
File.description             string         (existing nullable field; from stage describe — this IS file_summary)

(:Tag {name})                MERGE on name; globally unique tag name across the graph

(Chunk)-[:HAS_TAG]->(Tag)    one edge per (chunk, facet, tag_name) cleaned tuple
    facet    string          (one of "topic" "entities" "activity" "temporal" "evidence")
    w_chunk  float[0,1]      (rounded to 2 decimals before write)
    w_facet  float[0,1]      (rounded to 2 decimals before write)
    run_id   string          (e.g. "pilot_001"; lets you find what a run wrote)
```

The new edge properties (`facet`, `w_chunk`, `w_facet`, `run_id`) do NOT reuse
the old edge properties (`cluster`, `weight_local`, `canonical_id`). The herb
database is empty of HAS_TAG edges to start, so no schema collision. Trying
to shoehorn the new design into old field names was explicitly rejected as
muddying the semantics.

### 2.5 Cleaning is done in code, not in the prompt

Rejected: putting "use snake_case", "lowercase", "no spaces" rules in the
prompt. Reason: that's a normalisation step a deterministic Python pass does
better and cheaper. The agent produces whatever string it wants; the cleaner
in `pipeline.py` does:

```python
def clean_tag_name(raw: str) -> str:
    s = raw.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s
```

Plus, per tag in extract:
- Drop if cleaned name is empty.
- Drop if cleaned name is in FILLER = `{"data", "information", "content", "record", "text", "chunk", "item"}`.
- Round `w_chunk`, `w_facet` to 2 decimals.
- Dedupe within (chunk, facet) by cleaned name; keep the entry with max `w_chunk`.

### 2.6 The final prompts (lean, no formatting rules, no meta-instructions)

These are stored as Python constants in `backend/tagging/pipeline.py`
(no separate `.md` prompt files — keeps surface tight).

**Extract** (per chunk):

```
## Description

Describe the chunk's content in 1–3 sentences.

## Five facets

| Facet    | Captures                                                                                    |
|----------|---------------------------------------------------------------------------------------------|
| topic    | Subject matter                                                                              |
| entities | Named people, organisations, products, systems, places                                      |
| activity | Actions, processes, events                                                                  |
| temporal | Dates and time expressions present verbatim in the text                                     |
| evidence | Kind of information: definition, example, metric, argument, procedure, case_study, raw_data |

## Tags

Concept labels used as search handles. Keep proper names whole.

## Weights

- **w_chunk** — centrality of this tag to this chunk (1.0 = core, 0.1 = passing mention)
- **w_facet** — fit of this tag to its facet (1.0 = unambiguous, 0.1 = forced)

A facet may have zero tags. No filler: `data`, `information`, `content`, `record`.
```

**Describe** (per file):

```
Describe the file's central concerns in 2–3 sentences, based on the chunk
descriptions provided.
```

**Score** (per chunk):

```
Score how representative this chunk is of the file (1.0 = core example,
0.0 = off-topic). Return w_chunk_file as a float in [0, 1] with 2 decimals.
```

Word-choice notes that came out of the iteration and you should respect:
- "Describe" not "summarise". Summarising compresses an existing source.
  Stage 2 produces an original characterisation of the file using chunk
  descriptions as input — that is describing, not summarising.
- The `temporal` facet definition contains its own constraint ("present
  verbatim in the text"). Do NOT add a separate Rule line about temporal —
  that creates a weird single-facet exception in the prompt structure.
- No snake_case / lowercase / "be specific" / "do not pad" instructions in
  the prompt. Those are either code (formatting) or noise (meta).

### 2.7 Reproducibility model

`select` writes the chosen chunk IDs to `run.json`. Every later stage reads
from there. Re-running a later stage uses the same chunks. To make a sibling
pilot with the same chunks but a different prompt:

```bash
mkdir -p backend/data/tagging_runs/pilot_002
cp backend/data/tagging_runs/pilot_001/run.json backend/data/tagging_runs/pilot_002/
# edit the pipeline (or git branch it) to change prompts, then:
PILOT_NAME=pilot_002 python -m backend.tagging extract
PILOT_NAME=pilot_002 python -m backend.tagging describe
PILOT_NAME=pilot_002 python -m backend.tagging score
PILOT_NAME=pilot_002 python -m backend.tagging analyze
```

(`PILOT_NAME` is read by `pipeline.py` and selects the run directory; default
is `pilot_001`.)

### 2.8 Provider — what was specified vs what we used

Brief specified Groq `openai/gpt-oss-120b` with `reasoning_format: "parsed"`
and `reasoning_effort: "high"`. The motivation was the "format tax" hypothesis
— open-weight models reason worse when forced into structured JSON output;
Groq's separate reasoning channel lets the model reason freeform first, then
format.

In practice: every Groq API key value in `backend/.env` came back 401
"Invalid API Key" from Groq's own auth layer (verified via raw curl with real
`x-request-id` headers from Cloudflare). The user's Groq playground worked
(proving the account was active) but the API keys created never authenticated.
Root cause never resolved during the pilot.

We fell back to **Anthropic `claude-haiku-4-5`** with structured output via
**forced tool-use** (`tool_choice={"type": "tool", "name": <schema_name>}`).
The schema lives in the tool's `input_schema`. This gives reliable structured
output with strict schema validation.

Important constraint that decided the design: Anthropic's extended-thinking
mode is INCOMPATIBLE with forced `tool_choice`. You can have a separate
reasoning channel OR forced structured output, not both. We chose forced
structured output for reliability (zero schema-violation failures across all
23 calls).

Consequence: this pilot does NOT test the brief's "reasoning before format"
hypothesis. The `response_reasoning` field in `io.jsonl` is `null` throughout.

---

## 3. Where we are right now

- Pipeline built, runs end-to-end on Anthropic Haiku 4.5.
- Pilot 1 done (10 chunks, 3 files, 23 API calls, 45 seconds, ~$0.01).
- Pilot output landed in Neo4j `herb` database and on disk under
  `backend/data/tagging_runs/pilot_001/`.
- Tag *content* is good — sensible, snake_cased, useful for retrieval.
- Tag *weights* are anchoring to a few round values and are not differentiating
  meaningfully — this is the load-bearing finding. See §8.
- We have NOT scaled to the full 968 chunks because of the anchoring issue.
- The Groq path remains broken; brief's reasoning-channel hypothesis untested.

---

## 4. Code layout

```
backend/
  tagging/                                # NEW package — this work
    __init__.py
    __main__.py                           # CLI: python -m backend.tagging <stage>
    pipeline.py                           # everything: config, prompts as constants,
                                          # JSON schemas, Pydantic models, ClaudeCaller,
                                          # the five stage functions, cleaners, analysis report
  indexing/                               # PRE-EXISTING different pipeline. Do not modify
                                          # while working on this; it writes to a different
                                          # Neo4j database (`bonnier`, not `herb`) and uses
                                          # different vocabulary.
  data/
    tagging_runs/
      pilot_001/                          # the pilot output
        run.json                          # config + 10 selected chunk_ids + stages_done + analysis stats
        io.jsonl                          # ONE LINE PER API CALL across all stages, schema:
                                          #   {ts, stage, target_id, attempt, provider, model,
                                          #    request: {system, user},
                                          #    response_tool_input,         # the parsed JSON
                                          #    response_text,               # any text blocks
                                          #    response_reasoning,          # null on Anthropic
                                          #    stop_reason,
                                          #    usage: {prompt_tokens, completion_tokens, total_tokens},
                                          #    duration_ms}
        errors.jsonl                      # only created if any failure occurs (empty after pilot_001)
        analysis.md                       # human-readable report
        HANDOFF.md                        # THIS FILE
  .env                                    # see §10 for the keys layout and the override quirk
```

Three source files in `tagging/`, ~700 lines of Python total.

---

## 5. How to run (reproducible from scratch)

```bash
# 0) prereqs (one-time):
pip install anthropic neo4j python-dotenv pydantic

# 1) env. backend/.env must contain at minimum:
#       ANTHROPIC_API_KEY=sk-ant-...
#       NEO4J_URI=neo4j://localhost:7687
#       NEO4J_USER=neo4j
#       NEO4J_PASSWORD=...
#    Note: NEO4J_DATABASE in .env is IGNORED by this pipeline — the database
#    is hardcoded to "herb" in pipeline.py (the constant NEO4J_DATABASE).

# 2) ensure herb database exists and is populated with chunks:
#    A separate preflight (not part of this work) produced the 33 files / 968 chunks.

# 3) run stages in order from the repo root:
cd <repo root>
python -m backend.tagging select        # picks 10 random chunks, writes run.json
python -m backend.tagging extract       # ~45s, 10 API calls (concurrency 4)
python -m backend.tagging describe      # ~10s, F calls (F = unique files in sample)
python -m backend.tagging score         # ~30s, 10 API calls
python -m backend.tagging analyze       # 0 API calls, writes analysis.md

# 4) inspect
cat backend/data/tagging_runs/pilot_001/analysis.md
```

Stage gates:
- `extract` requires `select` to have run (chunk_ids in `run.json`).
- `describe` requires `extract` to be in `stages_done`.
- `score` requires `describe` to be in `stages_done`.
- `analyze` requires `score` to be in `stages_done`.

Re-running `extract` wipes existing HAS_TAG edges for the sampled chunks
(via `MATCH (c:Chunk)-[r:HAS_TAG]->() WHERE c.chunk_id IN $ids DELETE r`)
before writing fresh ones. Safe to re-run.

To reset stages (e.g. force a re-extract), edit `run.json` and clear
`stages_done` to `[]`.

---

## 6. Schemas — what comes back from the API

These are the JSON schemas sent in the tool's `input_schema`. They are
enforced strictly by Anthropic when `tool_choice` forces the tool.

### Extract output (per chunk)

```json
{
  "type": "object",
  "required": ["description", "tags"],
  "additionalProperties": false,
  "properties": {
    "description": {"type": "string", "minLength": 1},
    "tags": {
      "type": "object",
      "required": ["topic", "entities", "activity", "temporal", "evidence"],
      "additionalProperties": false,
      "properties": {
        "topic":    {"type": "array", "items": {"$ref": "#/$defs/tag"}},
        "entities": {"type": "array", "items": {"$ref": "#/$defs/tag"}},
        "activity": {"type": "array", "items": {"$ref": "#/$defs/tag"}},
        "temporal": {"type": "array", "items": {"$ref": "#/$defs/tag"}},
        "evidence": {"type": "array", "items": {"$ref": "#/$defs/tag"}}
      }
    }
  },
  "$defs": {
    "tag": {
      "type": "object",
      "required": ["t", "w_chunk", "w_facet"],
      "additionalProperties": false,
      "properties": {
        "t":       {"type": "string", "minLength": 1},
        "w_chunk": {"type": "number", "minimum": 0, "maximum": 1},
        "w_facet": {"type": "number", "minimum": 0, "maximum": 1}
      }
    }
  }
}
```

### Describe output (per file)

```json
{"type":"object","required":["file_summary"],"additionalProperties":false,
 "properties":{"file_summary":{"type":"string","minLength":1}}}
```

### Score output (per chunk)

```json
{"type":"object","required":["w_chunk_file"],"additionalProperties":false,
 "properties":{"w_chunk_file":{"type":"number","minimum":0,"maximum":1}}}
```

### User-message templates

Extract: raw chunk content, no wrapping.

Describe:
```
File: {rel_path}

Chunk descriptions (in file order):
1. {desc_1}
2. {desc_2}
...
```

Score:
```
File summary:
{file_description}

Chunk description:
{chunk_description}
```

---

## 7. Pilot results — the numbers

Run: 2026-05-13, `pilot_001`, model `claude-haiku-4-5-20251001`, db `herb`.

### Sample composition

10 random chunks → 3 files:
- `Salesforce__HERB/metadata/employee.json` — 7 chunks (each a single employee record)
- `Salesforce__HERB/metadata/customers_data.json` — 2 chunks (each a single customer record)
- `Salesforce__HERB/products/CollaborateForce.json` — 1 chunk (a long Slack conversation)

### Mechanics

| Metric | Value |
|---|---|
| Chunks tagged | 10/10 |
| Files described | 3/3 |
| Chunks scored | 10/10 |
| Total API calls | 23 |
| Retries used | 0 |
| Schema-violation failures | 0 |
| Wall time | 45 s (concurrency 4) |
| Input tokens | ~29,000 |
| Output tokens | ~5,300 |
| Approx cost (Haiku 4.5) | ~$0.01 |

### Tag counts

84 total `:HAS_TAG` edges; 58 unique tag names across the five facets.

| Facet    | Edges | Chunks with ≥1 tag |
|----------|-------|--------------------|
| topic    | 22    | 10/10              |
| entities | 31    | 10/10              |
| activity | 14    | 10/10              |
| temporal | 3     | **1/10** (correctly — only the Slack chunk had verbatim dates) |
| evidence | 14    | 10/10 (but degenerate, see §8.2) |

### Most common tags

| facet | name | count |
|---|---|---|
| evidence | `raw_data` | 9 |
| topic | `employee_profile` | 6 |
| entities | `salesforce` | 3 |
| activity | `software_engineering` | 3 |
| entities | `sydney`, `seattle`, `mulesoft`, `london` | 2 each |
| topic | `quality_assurance`, `customer_profile`, `organizational_structure` | 2 each |

### Cost projection to full HERB (968 chunks)

Linear extrapolation: 968 extract + 33 describe + 968 score = 1969 calls,
~75–90 min wall time at concurrency 4, ~$0.40 at Haiku 4.5 pricing. Add 5–10×
output tokens if a reasoning-channel model is used.

---

## 8. The finding — weight anchoring is severe

The user, before the run, asked whether the model would actually use the
float range or anchor to round values. The analyze stage was instrumented
specifically to make this visible. The verdict:

### 8.1 Weight resolution by stage

| Weight | n | distinct values used at 2dp (out of 100 possible) | mean | stdev | dominant anchors |
|---|---|---|---|---|---|
| `w_chunk` | 84 | **9** | 0.833 | 0.168 | 0.8/0.9/1.0 carry ~75% of mass |
| `w_facet` | 84 | **3** | 0.973 | 0.047 | 1.0 = 74%, 0.9 = 25%. Effectively binary. |
| `w_chunk_file` | 10 | **3** (0.75 / 0.85 / 0.95) | 0.870 | 0.060 | offset to ".x5" anchors |

Histograms (0.1 bins), from `analysis.md`:

`w_chunk`:
```
[0.0,0.1)  0   [0.5,0.6)  3
[0.1,0.2)  0   [0.6,0.7)  5
[0.2,0.3)  0   [0.7,0.8) 10
[0.3,0.4)  2   [0.8,0.9) 20
[0.4,0.5)  1   [0.9,1.0] 43
```

`w_facet` (one value at 0.8; 83 of 84 values ≥0.9):
```
[0.8,0.9)  1
[0.9,1.0] 83
```

`w_chunk_file` (10 chunks total, 3 distinct values):
```
[0.7,0.8)  1   ← 0.75 (one chunk)
[0.8,0.9)  6   ← all 0.85
[0.9,1.0]  3   ← all 0.95
```

Two specific patterns to notice:
- 7 of 7 employee-record chunks got `w_chunk_file = 0.85`. Identical score
  despite being clearly different records (different people, roles, locations,
  orgs).
- `w_facet` distinguishing "unambiguous fit" from "forced fit" was the
  pilot's only signal for facet quality. 83/84 ≥0.9 means that signal is dead.

### 8.2 The `evidence` facet collapses on structured data

9/10 chunks tagged `raw_data` as their evidence-facet tag. For JSON record
files every chunk is "raw_data" — the facet adds no retrieval signal on this
dataset shape. It has substance on prose: the one Slack chunk produced five
distinct evidence tags (different suggestions to add to a market research
report).

### 8.3 The pilot cannot say anything cross-file

We sampled 10 chunks from 968. Each file's description was generated from
only the sampled chunks of that file (1, 2, or 7 chunks of however-many it
really has). The `w_chunk_file` score is therefore against a partial, biased
file description. The pilot validates pipeline mechanics, not cross-file
scoring quality.

### 8.4 What works

- Tag content is sensible: `fiona_smith`, `tableau`, `seattle`,
  `employee_profile`, `ux_research`, `market_research_report`, etc.
- The code-side cleaner does its job:
  `"Charlie [eid_94fb5d84]"` → `charlie_eid_94fb5d84`.
- The Slack chunk produced 22 distinct, useful tags across all 5 facets,
  including 3 temporal tags from actual date references in the text. The
  extraction prompt scales to prose without modification.
- Tool-use forced structured output: zero schema-violation failures across
  23 calls. No retries needed.
- Reproducibility works: same `run.json` → same 10 chunks on rerun.

---

## 9. Open items, prioritised

### 9.1 [PRIMARY] Address weight anchoring before scaling

Four candidate interventions, in roughly increasing order of design impact.
Pick one, run pilot_002, compare to pilot_001 analysis.md.

1. **Prompt nudge.** Add ONE line to the extract prompt forcing
   differentiation, e.g. "Use distinct values; do not assign identical weights
   to multiple tags in the same facet." Cheap to try. Risk: prompt bloat the
   user has been explicit about cutting. Verify analyze.md shows higher
   "distinct values" count.
2. **Structural schema constraint.** Modify the JSON schema in §6 so that
   tag weights cannot be equal within a (facet) group. JSON Schema can't
   express this directly — implement as a post-validation rejection in code
   and retry once with the prior response as a counter-example in the user
   message.
3. **Drop floats, use ordinal ranks.** Change `w_chunk` from float[0,1] to
   integer rank (1 = most central, 2 = next, ...). Tag at rank 1 is "the
   core tag for this chunk" in that facet. Same for w_chunk_file across the
   file's chunks. Forces strict ordering, no anchoring possible. Schema
   change is local to the extract/score schemas.
4. **Comparison run with a reasoning-channel model.** Test the brief's actual
   hypothesis: does giving the model a separate reasoning channel produce
   more differentiated weights? Requires fixing Groq (see §9.2) OR using
   OpenAI `gpt-5` / `o3` with `reasoning_effort: high` via the OpenAI SDK.

The user's stated instinct (paraphrased from the conversation that produced
this design): "force uneven weights" — i.e. option 2 above. They said "maybe
we just test it and see" — i.e. observe first. Pilot_001 IS that observation;
the data now supports moving to option 2 or 3.

### 9.2 Resolve the Groq key (independently of 9.1)

`backend/.env` has `GROQ_API_KEY=REDACTED_GROQ_API_KEY`
and `GROQ_MODEL=openai/gpt-oss-120b`. Every value the user generated returned
401 from Groq's auth layer (verified via curl — request reaches Groq, real
`x-request-id` returned, key rejected). The user's Groq playground worked,
proving account-level features are active.

Possible causes never pinned down:
- Free tier might require additional verification before API keys
  authenticate, even though they display.
- Workspace / organisation mismatch between key creation and API auth.
- A stale key in the dashboard UI not matching the active one.

If a future agent gets a working Groq key, the pipeline's `pipeline.py`
needs minor changes: swap `AsyncAnthropic` back to `AsyncGroq`, restore the
`reasoning_format="parsed"` + `reasoning_effort="high"` params, restore the
JSON-schema `response_format` shape, restore the strict-mode probe. The
git history of this file at the time of writing will show the Groq version
(it was rewritten in place — check `git log -p backend/tagging/pipeline.py`).

### 9.3 Decide what to do about `evidence` on structured data

Three options:
- Drop the facet entirely for `kind="record"` chunks (cheap; reduces
  per-chunk API output).
- Redefine the facet so it captures something more discriminating on JSON
  records (e.g. "kind of entity this record represents").
- Keep as-is and treat the redundancy as diagnostic — "this chunk is
  structured data" is a useful retrievable property.

The user has not indicated a preference; raise it as a question with a
proposed default.

### 9.4 Plan the cross-file production run before doing it

In pilot mode, `describe` only saw sampled chunks per file. In a production
run, `describe` should run AFTER `extract` has produced descriptions for
EVERY chunk in the file, not just a sample. The current pipeline does this
naturally if you run `select` to pick all 968 chunks, but it's worth being
explicit. Add a `select-all` mode (or a `--all` flag to `select`) that picks
every chunk, not a sample.

### 9.5 Decide on overwrite vs append for re-extraction at scale

Currently `extract` wipes existing HAS_TAG edges for the sampled chunks
before writing fresh ones. Right for pilots. For a production run, decide
whether re-extracting a chunk should be an explicit operator action
(`--reset` flag), or whether the default should keep prior runs' edges
distinguished by `run_id`. Both work; the question is whether
multi-run tag history is useful or just clutter.

---

## 10. Environment / harness gotchas

### 10.1 `load_dotenv` needs `override=True`

The harness this code runs under pre-sets `ANTHROPIC_API_KEY=""` in the
process environment. Plain `load_dotenv(...)` does NOT overwrite existing env
vars — it would leave the empty value in place. `pipeline.py` already uses
`override=True`. If you split this into multiple files or rewrite, keep
that flag, or you'll see:

```
TypeError: Could not resolve authentication method. Expected one of
api_key, auth_token, or credentials to be set...
```

### 10.2 `NEO4J_DATABASE` in .env is ignored

`backend/.env` ships with `NEO4J_DATABASE=bonnier` (a different dataset's
database). The tagging pipeline hardcodes `NEO4J_DATABASE = "herb"` at the
top of `pipeline.py` because herb is the only database this design has been
validated on. To run against a different dataset's database, change the
constant — don't trust the env var.

### 10.3 Anthropic-specific constraints we hit

- `tool_choice={"type": "tool", "name": ...}` (forced tool) is incompatible
  with extended thinking. Pick one. We picked forced tool for reliability.
- `temperature` is restricted when extended thinking is enabled (must be 1
  or omitted). Doesn't apply to our current code since thinking is off, but
  if you turn thinking on you must drop `temperature=0.3`.
- `max_tokens` is required on every Anthropic call. We use 4096 throughout;
  none of our calls came close.

### 10.4 Model ID

`ANTHROPIC_MODEL=claude-4-5-haiku` in `.env` is non-canonical. `pipeline.py`
includes an alias table that maps it to `claude-haiku-4-5`, which Anthropic
resolves to the dated `claude-haiku-4-5-20251001`. If you point at a
different Claude model, either use the canonical form or extend the alias
table.

---

## 11. Conventions the user has been emphatic about — read before extending

In order of how much the user pushed back when these were violated:

1. **Lean prompts. Doubt every line.** Each line of a prompt has to earn its
   place. Words like "summarise" when you mean "describe", redundant length
   hints ("write 1–3 sentences" when the table definition already constrains
   the answer), instructions for formatting (snake_case, lowercase),
   meta-instructions ("be specific", "do not pad") — all bloat. When in
   doubt: cut.
2. **Clean data in code, not in the prompt.** Anything a deterministic Python
   pass can do — lowercasing, snake_casing, deduping, rounding, filtering
   filler — does NOT go in the prompt. The model is for semantic decisions
   only.
3. **Don't single out one facet (e.g. `temporal`) with rules elsewhere in
   the prompt.** If the facet's own definition is right, you don't need a
   rules-section reminder. Duplicate rules create weird single-facet
   exceptions in the prompt structure.
4. **Fewer files, not more.** The pipeline started as a proposed 11-file
   package; the user pushed back on "17 files" (including the runtime output
   files) and we collapsed to 3 source files. Don't split prompts into
   `.md` files, don't split client and schemas into separate modules.
5. **Show before you build.** When you propose a prompt or schema change,
   show the exact text first, get sign-off, then write code. Don't propose
   a change and a prompt in the same breath as the code that implements it.
6. **Reproducibility.** Random samples get saved (chunk_ids in run.json).
   Don't introduce stochastic state that isn't recorded.

---

## 12. Artefact pointers (all relative to repo root)

| Artefact | Path |
|---|---|
| Pipeline source (everything in one file) | `backend/tagging/pipeline.py` |
| CLI entry | `backend/tagging/__main__.py` |
| Selected chunks + run state + final stats | `backend/data/tagging_runs/pilot_001/run.json` |
| Every API call's full I/O | `backend/data/tagging_runs/pilot_001/io.jsonl` |
| Failures (empty after pilot_001) | `backend/data/tagging_runs/pilot_001/errors.jsonl` |
| Human-readable analysis | `backend/data/tagging_runs/pilot_001/analysis.md` |
| This handoff | `backend/data/tagging_runs/pilot_001/HANDOFF.md` |
| Original brief (paraphrased into this doc; if you need the raw user-supplied brief, check the conversation that produced pilot_001) | — |

### What `pilot_001` wrote into Neo4j (`herb` database)

- 10 `Chunk.description` strings
- 10 `Chunk.relevance_to_file` floats (each is the chunk's `w_chunk_file` score)
- 3 `File.description` strings
- 58 `:Tag` nodes (or merged into existing ones if any tag name pre-existed)
- 84 `(:Chunk)-[:HAS_TAG {facet, w_chunk, w_facet, run_id="pilot_001"}]->(:Tag)` edges

### Useful Cypher

**Verify pilot writes:**
```cypher
// counts
MATCH (c:Chunk) WHERE c.description IS NOT NULL RETURN count(c) AS chunks_with_desc;
MATCH (f:File) WHERE f.description IS NOT NULL RETURN count(f) AS files_with_desc;
MATCH ()-[r:HAS_TAG {run_id: "pilot_001"}]->() RETURN count(r) AS pilot_edges;

// inspect a chunk and its tags
MATCH (c:Chunk {chunk_id: $cid})-[r:HAS_TAG]->(t:Tag)
RETURN r.facet AS facet, t.name AS tag, r.w_chunk AS w_chunk, r.w_facet AS w_facet
ORDER BY facet, w_chunk DESC;
```

**Find chunks by tag (the whole point of doing this):**
```cypher
// chunks where 'salesforce' appears as an entity with reasonable weight
MATCH (c:Chunk)-[r:HAS_TAG {facet: "entities"}]->(t:Tag {name: "salesforce"})
WHERE r.w_chunk >= 0.5
RETURN c.chunk_id, c.description, r.w_chunk
ORDER BY r.w_chunk DESC;
```

**Clean pilot_001 writes for a fresh start:**
```cypher
MATCH ()-[r:HAS_TAG {run_id: "pilot_001"}]->() DELETE r;
// then remove orphan Tag nodes if you want a fully clean slate:
MATCH (t:Tag) WHERE NOT (t)<-[:HAS_TAG]-() DELETE t;
// and clear the descriptions / scores written by the pilot:
//  (you'd need the chunk_id list from run.json — easier to just rerun the pilot,
//   since extract wipes the chunk's HAS_TAG edges before re-writing)
```

---

## 13. One-line summary

The pipeline works end-to-end. Tag content is good. Tag weights collapse to
3–9 distinct values out of 100 possible — the model anchors hard to round
numbers. That is the finding the next iteration must address before scaling
to the full 968-chunk run. Most likely intervention: force structural weight
differentiation (option 2 or 3 in §9.1).
