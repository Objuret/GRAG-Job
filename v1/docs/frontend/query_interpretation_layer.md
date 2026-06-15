# Prompt Interpretation Method

**Status:** implemented in the browser (`src/services/*` + `src/App.jsx`).
No HTTP layer. The retrieval lane now receives a first-class
`RetrievalInput` object instead of a loose mix of plan fields and UI knobs.
Graph prerequisites are **verified present on the live `herb-eval` graph**
(2026-05-19: 4,869 eval-safe chunks, 229,249 `HAS_TAG` edges,
`chunk_fulltext` + the six `tag_emb_<facet>` vector indexes ONLINE, 96,790
`:Tag.emb_*` grounding vectors (72,009 facet + 24,781 `all`) — see
[`status.md`](status.md)). Not separately
re-verified: a full browser prompt → answer click-through.

**Last updated:** 2026-05-20.

## Purpose

The contract between a user prompt and the live HERB graph. Mirrors the tagging method that produced `pilot_full_herb`: two-pass interpretation, five-facet scoring, derived centrality from a facet vector.

The goal is not to let the LLM write Cypher. The LLM interprets the prompt into a small structured query plan; deterministic code maps that plan to Neo4j queries.

## Where this runs

The workbench is local-only. The browser:

- Calls Anthropic directly via `@anthropic-ai/sdk` with `dangerouslyAllowBrowser: true`.
- Calls Neo4j directly via `neo4j-driver` (bolt-ws to localhost) as a read-only user.

Pass 1, Pass 2, retrieval scoring, and answer generation are all browser code. There is no HTTP server in front of either Anthropic or Neo4j.

## Ground truth from HERB

Built by [`tagging/pipeline.py`](../../backend/tagging/pipeline.py), documented in [`herb_tagging_schema.md`](../backend/herb_tagging_schema.md) and [`pilot_full_herb_report.md`](../backend/pilot_full_herb_report.md).

Important facts for retrieval:

- `(:Chunk)-[:HAS_TAG]->(:Tag)` edges carry `facet`, `w_chunk`, `w_facet`, and `run_id`.
- The model did not emit `w_chunk`; the pipeline derived it from the five-facet vector.
- A tag can appear on multiple facet edges for the same chunk.
- `Chunk.relevance_to_file` is a comparative file-representativeness score.
- The current pilot graph contract uses the HERB names only. **Do not use legacy generic-tagger field names** for HERB retrieval.

## Principle

Query interpretation reuses the same base shape as chunk interpretation:

1. Extract flat retrieval handles from the user prompt.
2. Score each handle against the same five facets.
3. Derive query-side centrality from the five-facet vector.
4. Add filters and answer instructions separately.

Retrieval becomes a comparison between two similar semantic objects:

```text
query tag vector  <->  chunk tag vector
```

## Pass 1: Describe, then extract

Anthropic call. Input: the user prompt. The model works in three steps in one
call: **(1)** write `description` — a concise, self-contained statement of the
underlying information need (not a restatement of the question); **(2)** derive
`tags` *from that description*; **(3)** extract `gate` — hard structured
constraints, **only** when the query explicitly names them (else `null` / `[]`;
the model must not guess). Description first is deliberate: it is the
prompt-side embedding context (the analogue of corpus chunk descriptions in
grounding), so it must be faithful and self-contained, not incidental.

```json
{
  "description": "The user wants links to GitHub pull requests in AnomalyForce that expand security measures and have not been approved.",
  "tags": [
    "AnomalyForce",
    "security measures expansion",
    "pull requests",
    "not approved",
    "GitHub links"
  ],
  "gate": {
    "product": "AnomalyForce",
    "section": "prs",
    "channel": null,
    "employee_id": null,
    "years": []
  }
}
```

`gate` maps to the materialized `:Chunk` hard fields (see
[`../graph_schema.md`](../graph_schema.md), "Hard fields"). `section` is
normalised to the corpus enum (`slack`, `documents`, `meeting_transcripts`,
`meeting_chats`, `prs`, `urls`, `answerable_questions`,
`unanswerable_questions`, `product_profile`); synonyms like "pull requests" →
`prs`, "chat" → `slack` are mapped, unknown sections dropped to `null`.

No facets, no weights — just handles. Cleaning rule (same as HERB):

```text
lowercase -> non-alnum to underscores -> strip underscores
```

Drop empty tags and filler tags such as `data`, `information`, `content`, `record`, `text`, `chunk`, `item`.

## Pass 2: Prompt tag facet scoring

For each cleaned prompt tag, Anthropic returns a fit score per facet:

```json
{
  "scores": [
    {
      "t": "anomalyforce",
      "facets": {
        "topic": 0.8,
        "entities": 1.0,
        "activity": 0.1,
        "temporal": 0.0,
        "evidence": 0.1
      }
    }
  ]
}
```

The facets are identical to the HERB chunk facets:

| Facet | Meaning |
|---|---|
| `topic` | Subject matter. |
| `entities` | Named people, organisations, products, systems, places. |
| `activity` | Actions, processes, events. |
| `temporal` | Dates and time expressions. |
| `evidence` | Information kind: definition, example, metric, argument, procedure, case study, raw data, citation, link, etc. |

The model does not emit query centrality directly. Code derives it from the facet vector using the same formula as HERB `compute_w_chunk`, but the semantic name differs:

```text
w_query = strength * coverage_bonus
```

`w_query` means "how important this tag is to the user's information need"; `w_chunk` means "how central this tag is to a chunk."

## Plan shape

The interpreter returns one complete, inspectable object. The UI must display it beside the retrieved results so the user can see what the model thought the prompt meant.

```json
{
  "description": "Find unapproved pull request links related to expanding security measures in AnomalyForce.",
  "tags": [
    {
      "t": "anomalyforce",
      "facets": {"topic": 0.8, "entities": 1.0, "activity": 0.1, "temporal": 0.0, "evidence": 0.1},
      "w_query": 0.54
    }
  ],
  "filters": {
    "dataset_id": "Salesforce__HERB",
    "file_ids": [],
    "min_w_chunk": 0.0,
    "min_relevance_to_file": 0.0,
    "limit": 20,
    "gate": {
      "product": "AnomalyForce",
      "section": "prs",
      "channel": null,
      "employee_id": null,
      "years": []
    }
  },
  "answer_job": {
    "mode": "direct_answer",
    "evidence_policy": "retrieved_only",
    "missing_evidence_policy": "say_insufficient_evidence"
  },
  "warnings": []
}
```

`filters` and `answer_job` are not tags. They control what the retrieval code is allowed to search and what the answer model should do after retrieval.

## RetrievalInput shape

Before graph retrieval runs, the `build_input` node turns the query plan plus
its own params into one inspectable object:

```json
{
  "plan": "{QueryPlan}",
  "scope": {
    "datasetId": "Salesforce__HERB",
    "runId": "pilot_full_herb"
  },
  "controls": {
    "strategy": "weighted",
    "activeFacets": ["topic", "entities", "activity", "temporal", "evidence"],
    "tagsEnabled": true,
    "limit": 20,
    "minWChunk": 0.0,
    "minRelevanceToFile": 0.0,
    "groundingK": 10,
    "minSim": 0.78,
    "excludedSections": ["answerable_questions", "unanswerable_questions", "product_profile"]
  },
  "gate": {
    "product": "AnomalyForce",
    "section": "prs",
    "channel": null,
    "employee_id": null,
    "years": []
  }
}
```

This is the actual input to retrieval. The `interpret` node owns `plan`; the
`build_input` node owns `scope` + `controls` (its `node.data` params); the hard
gate comes from the plan. `scoreGroundedChunks` (Lane A, after `ground`) and
`retrieveBaseline` (Lane B) both consume this same object so semantic and
baseline runs use identical scope, limit, and hard gate.

For RAG evaluation, `excludedSections` is part of the retrieval contract, not a
UI convenience. The default excludes HERB QA records and oracle product profiles
so retrieved evidence cannot contain evaluation answers or product-level
`team`/`customers` shortcuts. The physical eval database `herb-eval` should
remove those chunks entirely; this browser-side exclusion is a second guard.

## Retrieval scoring

All steps execute from the browser. Retrieval scoring consumes the
`RetrievalInput`; it does not read scattered UI state after that object is
built.

**0. Eval exclusion + hard gate (deterministic, pre-scoring).** Before any tag or embedding
work, the plan's `gate` is compiled to a Cypher `WHERE` fragment ANDed onto
the `:Chunk` — equality on the materialized scalar hard fields (`product`,
`section`, `channel`, `employee_id`) and `any(year ∈ gate.years ∈ c.years)`.
Every set value is first validated against the live corpus: a constraint that
matches zero chunks raises a loud error listing the valid values (or, for
years, the corpus year range) — it is never silently dropped to "scan
everything". If the prompt explicitly gates to a section in `excludedSections`,
retrieval fails loudly. The exclusion and gate are then applied to every
retrieval path below, including lexical recall and the default Query-module
Cypher; custom Query modules are post-checked for forbidden returned chunks.

**1. Grounding (vector kNN).** Each prompt tag is embedded once for every active
facet where the prompt-side facet score is positive, plus one broad `all`
embedding. The text is **symmetric with the corpus side**:
`passage: <readable tag name>. <facet scope>. <prompt description>`,
whitespace-collapsed and capped at 900 chars, via `@xenova/transformers`
running the same `intfloat/e5-small-v2` weights the backend `embed-tags` stage
used. The model is **bundled into the app** at
`frontend/public/models/Xenova/e5-small-v2/` (the ONNX port of the same
weights) and loaded **local-only** — `services/embeddings.ts` sets
`env.allowRemoteModels = false`, `env.localModelPath = '/models'`, so there is
no runtime Hugging Face fetch (the browser analogue of the backend's on-disk
HF cache). It loads the **full fp32** `onnx/model.onnx` with `quantized: false`,
not the int8 default, so browser vectors match the backend's fp32
sentence-transformers vectors exactly — verified: cosine `1.00000000`,
max per-dimension diff `~1e-7` on an identical `passage:` input. The backend
embeds a `:Tag` as `passage: <name>. <its most-central chunk
descriptions>`; the prompt side substitutes the Pass-1 prompt description for
those chunk descriptions, so both vectors are the same kind of object (name +
description prose, same prefix). The earlier asymmetric `query:`-vs-`passage:`
form is gone — comparing a 2-word query string against context-laden passage
vectors collapsed cosine similarities into a narrow, non-discriminative band.
The backend embeds each tag/facet scope as
`passage: <name>. <facet scope>. <its strongest safe occurrence descriptions>`
and stores the vector as a `:Tag.emb_<facet>` (or `emb_all`) property. There is
no separate embedding node; the meaningful chunk graph remains
`(:Chunk)-[:HAS_TAG]->(:Tag)`. The prompt side substitutes the Pass-1
prompt description for chunk descriptions, so both vectors are the same kind of
object. The earlier asymmetric `query:`-vs-`passage:` form is gone — comparing
a 2-word query string against context-laden passage vectors collapsed cosine
similarities into a narrow, non-discriminative band.

Before loading the extractor, the browser verifies the bundled JSON assets
(`config.json`, `tokenizer.json`, `tokenizer_config.json`,
`special_tokens_map.json`, `generation_config.json`) plus `onnx/model.onnx`.
This catches the common Vite fallback failure where a missing JSON path returns
`index.html` and later appears as an opaque `JSON.parse` error. It also clears
the model JSON keys from `transformers-cache` and disables that CacheStorage
layer for this local bundle, because a prior missing-file run can otherwise
cache that HTML fallback under the model asset URL.
`db.index.vector.queryNodes('tag_emb_<facet>', k, vec)` (the per-facet `:Tag`
vector index) returns nearest corpus `(tag, facet)` uses with cosine `sim`. Facet-specific matches can only
score same-facet `HAS_TAG` edges; `all` matches may score any active facet and
carry a lower scope weight. `k` (grounding depth) and `min_sim` are user
controls on the `build_input` node ("effort"). Note `min_sim` is a coarse
floor: e5-small cosine on this corpus is compressed (~0.8 mean to random
tags), so grounding leans on top-k ranking, not the absolute threshold.

Grounding is the **only** path. In legacy mode there is no exact-name shortcut
and no silent fallback: if the `tag_emb_<facet>` indexes or the `:Tag.emb_*`
vectors are missing, or grounding yields no match above `min_sim`, retrieval
throws a loud error telling the operator to run `python -m tagging embed-tags`.
Link-only mode adds an exact `:Tag` name probe before kNN (see §2 below).

**2. Deterministic weighted overlap**, in Cypher, over the grounded tags:

```text
edgeContrib = w_query × facetScore × w_chunk × w_facet × relevance_to_file × scopeWeight
              [× grounding_sim in legacy mode only]

perPromptBest(c, promptTag) = max(edgeContrib) over that prompt tag's grounded links on c
score(c) = Σ perPromptBest(c, promptTag)   // sum across prompt tags
```

Each **prompt tag** contributes at most one term per chunk (its best matching
`HAS_TAG` edge among the corpus tags kNN linked to it). Scores then **sum
across prompt tags**. This stops a chunk from piling up score because many
generic corpus tags (linked from a wide kNN pool) each hit the same chunk.

A grounded corpus tag inherits its prompt tag's facet vector and `w_query`.
Link-only mode (`--link-only` / `link_only_scoring`) uses kNN only to **link**
prompt tags to corpus `:Tag` names (`groundingK` typically 40); ranking uses
the HERB weight product above **without** `× grounding_sim`. Exact corpus tag
name match is tried before kNN.

**3. Lexical recall (gated full-text).** Tag scoring caps recall at tagger
coverage: a chunk whose body literally states a term is unreachable if no
matching tag was ever minted. The current code only uses the `chunk_fulltext`
index (`content`, `description`, `question`) when the prompt produced a usable
hard gate but no usable tags. That path carries a plan warning and runs under
the same gate. The older semantic-hit + lexical-hit union path is gone; year
constraints are enforced through `c.years` in the hard gate.

The full grounding map (prompt tag → matched corpus tags + sims) is attached
to the plan as `grounding` and shown beside the results.

HERB has many tags per chunk, so retrieval starts with conservative limits and visible thresholds. Broad prompts should return a plan the user can inspect before running a large search.

## Answer job

Separate from graph retrieval. Tells the downstream LLM what to do with retrieved chunks:

- `direct_answer` — answer the question from retrieved evidence.
- `list` — return matching items such as PR links or employees.
- `compare` — compare entities or products across retrieved evidence.
- `aggregate` — count, rank, or group evidence.
- `summarize` — synthesize a short overview.

Thesis-safe defaults:

```text
evidence_policy = retrieved_only
missing_evidence_policy = say_insufficient_evidence
```

## Implementation notes

- Pass 1, Pass 2, and the answer call are three separate Anthropic calls in the browser. Keep them separate so the plan stays inspectable between steps.
- The UI must display the query plan and `RetrievalInput` beside the retrieved results.
- Field-name discipline: HERB graph uses `facet`, `w_chunk`, `w_facet`, `relevance_to_file`.
- Prompt-tag grounding against the live `:Tag.emb_*` vocabulary vectors is implemented via the per-facet vector indexes (see Retrieval scoring). Embedding model id must be identical backend (`sentence-transformers`) and browser (`@xenova/transformers`), enforced by `:Tag.embedding_model`. The browser model is bundled (`frontend/public/models/Xenova/e5-small-v2/`, full fp32, loaded local-only — no runtime HF fetch); fp32 + identical `passage:` construction give exact backend parity (cosine ≈ 1.0).
