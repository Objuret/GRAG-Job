# HTTP API (planned)

The workbench UI (`src/App.jsx`) currently reads the **node registry and demo
samples** from `src/data/workbenchData.ts` and does not call a server.

When a thin query service exists, it should expose live HERB graph state and a
prompt interpretation layer. The interpretation contract should mirror the
actual `pilot_full_herb` method: flat prompt retrieval handles first, then
five-facet scoring, then code-derived query centrality. See
[`../../backend/docs/query_interpretation_layer.md`](../../backend/docs/query_interpretation_layer.md).

---

## Shape (sketch)

| Method | Route | Purpose |
|--------|--------|--------|
| `GET` | `/api/health` | Liveness |
| `GET` | `/api/datasets` | List `(:Source)` with counts |
| `GET` | `/api/datasets/:id/files` | Files for a source, optional format filter |
| `GET` | `/api/files/:id/chunks` | Chunks + `HAS_TAG` for a file |
| `GET` | `/api/files/:id/tags` | File/chunk tag summaries from `HAS_TAG` |
| `POST` | `/api/query-plan` | Prompt to two-pass-style query interpretation plan |
| `POST` | `/api/retrieval` | Execute a query plan against Neo4j and return ranked chunks |

Response JSON should match updated interfaces in `src/types/index.ts`.

Retrieval/query-plan payloads should use the current HERB facet names:
`topic`, `entities`, `activity`, `temporal`, `evidence`. Current HERB tag edges
use `HAS_TAG { facet, w_chunk, w_facet, run_id }`; do not use older frontend
fields such as `cluster`, `canonicalId`, or `weightLocal` for the HERB path.

---

## Query plan sketch

`POST /api/query-plan` returns:

```json
{
  "description": "What the prompt is asking for.",
  "tags": [
    {
      "t": "cleaned_tag_name",
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
    "products": [],
    "chunk_kinds": [],
    "date_from": null,
    "date_to": null,
    "must_have_tags": [],
    "must_not_have_tags": []
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
    "output_format": "plain",
    "citation_policy": "cite_chunks",
    "evidence_policy": "retrieved_only",
    "missing_evidence_policy": "say_insufficient_evidence"
  }
}
```

---

## CORS

Allow the Vite dev origin (`http://localhost:5173`) when the API runs on
another port.

---

## UI integration

1. Add a small `fetch` client module, for example `src/api/client.ts`, with
   typed methods.
2. Replace reads of `workbenchData.ts` for live paths such as datasets,
   chunks, query plans, and retrieval with that client.
3. Keep `workbenchData.ts` for node metadata, query-fragment registry, and
   static workbench structure.
4. Keep `queryModuleSyntax.ts` only as a UI/template aid unless the API returns
   server-owned query templates.

No HTTP client is present today; add `src/api/client.ts` when the query service
exists.
