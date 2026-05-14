# Query Interpretation Layer

**Last updated:** 2026-05-14.

## Purpose

This is the planned contract between a user prompt, the frontend workbench, and
the live HERB graph. It should mirror the tagging method that actually produced
`pilot_full_herb`: two-pass interpretation, five-facet scoring, and derived
centrality from a facet vector.

The goal is not to let the model write Cypher. The model interprets the prompt
into a small structured query plan; deterministic code maps that plan to Neo4j
queries.

## Ground Truth From HERB

The current HERB graph was built by [`tagging/pipeline.py`](../tagging/pipeline.py)
and documented in [`herb_tagging_schema.md`](herb_tagging_schema.md) and
[`pilot_full_herb_report.md`](pilot_full_herb_report.md).

Important facts for retrieval:

- `(:Chunk)-[:HAS_TAG]->(:Tag)` edges carry `facet`, `w_chunk`, `w_facet`, and
  `run_id`.
- The model did not emit `w_chunk`; the pipeline derived it from five facet
  scores.
- A tag can appear on multiple facet edges for the same chunk.
- `Chunk.relevance_to_file` is a comparative file-representativeness score.
- There are no HERB `cluster`, `canonical_id`, or `weight_local` fields in the
  current pilot graph contract.

## Principle

Query interpretation should use the same base shape as chunk interpretation:

1. Extract flat retrieval handles from the user prompt.
2. Score each handle against the same five facets.
3. Derive query-side centrality from the five-facet vector.
4. Add filters and answer instructions separately.

This keeps retrieval as a comparison between two similar semantic objects:

```text
query tag vector  <->  chunk tag vector
```

## Stage 1: Prompt Tag Extraction

The model receives the user prompt and returns a short description plus flat
retrieval-handle tags. No facets, no weights.

Example output:

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

Use the same cleaning rule as HERB tagging:

```text
lowercase -> non-alnum to underscores -> strip underscores
```

Drop empty tags and filler tags such as `data`, `information`, `content`,
`record`, `text`, `chunk`, and `item`.

## Stage 2: Prompt Tag Facet Scoring

For each cleaned prompt tag, the model scores fit to every facet:

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

The model should not emit query centrality directly. Code derives it from the
facet vector using the same formula as HERB `compute_w_chunk`, but the semantic
name is different:

```text
w_query = strength * coverage_bonus
```

`w_query` means "how important this tag is to the user's information need";
`w_chunk` means "how central this tag is to a chunk."

## Query Plan Shape

The `/api/query-plan` endpoint should return a complete, inspectable object:

```json
{
  "description": "Find unapproved pull request links related to expanding security measures in AnomalyForce.",
  "tags": [
    {
      "t": "anomalyforce",
      "facets": {
        "topic": 0.8,
        "entities": 1.0,
        "activity": 0.1,
        "temporal": 0.0,
        "evidence": 0.1
      },
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

`filters` and `answer_job` are not tags. They control what the retrieval code
is allowed to search and what the answer model should do after retrieval.

## Retrieval Scoring

The first practical retrieval scorer can be deterministic weighted overlap:

```text
score += query_tag.w_query
       * query_tag.facets[facet]
       * chunk_edge.w_chunk
       * chunk_edge.w_facet
       * coalesce(chunk.relevance_to_file, 1.0)
```

Only compare a prompt tag to a chunk edge when the cleaned tag names match, or
when a later tag-expansion step has explicitly linked them.

Because HERB currently has many tags per chunk, retrieval should start with
conservative limits and visible thresholds. Broad prompts should return a plan
the user can inspect before running a large search.

## Answer Job

The answer job is separate from graph retrieval. It tells the downstream LLM
what to do with retrieved chunks:

- `direct_answer`: answer the question from retrieved evidence.
- `list`: return matching items such as PR links or employees.
- `compare`: compare entities or products across retrieved evidence.
- `aggregate`: count, rank, or group evidence.
- `summarize`: synthesize a short overview.

For thesis-safe behavior, the default should be:

```text
evidence_policy = retrieved_only
missing_evidence_policy = say_insufficient_evidence
```

## Implementation Notes

- Keep `/api/query-plan` and `/api/retrieval` separate.
- The frontend should display the query plan before or beside retrieved
  results, so the user can see what the model thought the prompt meant.
- Do not use old frontend assumptions such as `cluster`, `canonical_id`, or
  `weightLocal` for HERB retrieval.
- Add tag lookup/autocomplete after the first API exists. The model's prompt
  tags will often need grounding against the live `:Tag` vocabulary.
