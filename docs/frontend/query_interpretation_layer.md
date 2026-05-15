# Prompt Interpretation Method

**Status:** algorithmic spec; runs in the browser as part of the local-only workbench. No HTTP layer.

**Last updated:** 2026-05-14.

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

## Pass 1: Prompt tag extraction

Anthropic call. Input: the user prompt. Output:

```json
{
  "description": "Find unapproved pull request links related to expanding security measures in AnomalyForce.",
  "tags": [
    "AnomalyForce",
    "security measures expansion",
    "pull requests",
    "not approved",
    "GitHub links"
  ]
}
```

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
    "products": ["AnomalyForce"],
    "chunk_kinds": [],
    "date_from": null,
    "date_to": null,
    "must_have_tags": [],
    "must_not_have_tags": ["approved"]
  },
  "ranking": {
    "facets": ["topic", "entities", "activity", "temporal", "evidence"],
    "min_w_chunk": 0.0,
    "min_w_facet": 0.0,
    "min_relevance_to_file": 0.0,
    "limit": 20
  },
  "answer_job": {
    "mode": "direct_answer",
    "output_format": "links_with_short_explanation",
    "citation_policy": "cite_chunks",
    "evidence_policy": "retrieved_only",
    "missing_evidence_policy": "say_insufficient_evidence"
  },
  "warnings": []
}
```

`filters` and `answer_job` are not tags. They control what the retrieval code is allowed to search and what the answer model should do after retrieval.

## Retrieval scoring

Deterministic weighted overlap, executed in Cypher directly from the browser:

```text
score += query_tag.w_query
       * query_tag.facets[facet]
       * chunk_edge.w_chunk
       * chunk_edge.w_facet
       * coalesce(chunk.relevance_to_file, 1.0)
```

Only compare a prompt tag to a chunk edge when the cleaned tag names match (a later tag-expansion step may explicitly link related tags).

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
- The UI must display the query plan beside the retrieved results.
- Field-name discipline: HERB graph uses `facet`, `w_chunk`, `w_facet`, `relevance_to_file`.
- Tag lookup/autocomplete against the live `:Tag` vocabulary is a useful next step — the model's prompt tags will often need grounding against real corpus tag names.
