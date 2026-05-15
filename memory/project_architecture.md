---
name: GRAG project architecture (browser-direct, no HTTP backend)
description: Frontend is the whole app, runs locally, talks directly to Neo4j and Anthropic; backend is offline pipeline; any doc describing /api/* routes is stale and should be removed/rewritten
type: project
---

## Reality

**Frontend (`A:\exjobbet\repo\frontend\`)** = the entire user-facing app. Vite + React + `@xyflow/react`. Runs **local-only**:
- Browser → Neo4j directly via `neo4j-driver` (bolt-ws to localhost) using a read-only Neo4j user.
- Browser → Anthropic directly via `@anthropic-ai/sdk` with `dangerouslyAllowBrowser: true`. API key in `.env.local` as `VITE_ANTHROPIC_API_KEY`.
- **No HTTP server in the middle. None planned.** Credentials in the bundle are acceptable because the app is local-only and not deployed publicly.

**Backend (`A:\exjobbet\repo\backend\`)** = offline Python pipeline that **builds** the Neo4j graph (HERB tagging pilot via `tagging/pipeline.py`). It is not part of running the app; users run it only to (re)build the graph artefact.

## Stale fictions to delete/rewrite on sight

- Any `frontend/docs/api.md`-style HTTP route table. Junk.
- Any "add `src/api/client.ts`" fetch-client guidance. Junk.
- Any reference to `/api/datasets`, `/api/query-plan`, `/api/retrieval` as **endpoints**. The JSON shapes are real (they're the data contract); the HTTP transport is fiction.
- `backend/api/__pycache__/` orphan bytecode for `server.py`, `routes.py`, `deps.py` — never committed, source deleted. Delete the directory.
- Empty placeholder dirs in `frontend/src/`: `api/`, `store/`, `components/{layout,nodes,panels}/`.
- The "agent put all those docs in the backend so something is seriously off" — confirmed: a prior agent built scaffolding (orphan FastAPI, planned-HTTP docs) for an architecture that was never going to ship. Treat any planned-HTTP language as that agent's misunderstanding, not as design.

## Algorithmic content that survives (real thesis work)

The two-pass prompt-interpretation method documented in (formerly) `backend/docs/query_interpretation_layer.md` is **good** and belongs to the frontend now:
1. LLM pass 1: prompt → `{description, flat tags[]}` (same prompt-cleaning rule as HERB extract)
2. LLM pass 2: each tag → 5-facet vector (`topic, entities, activity, temporal, evidence`)
3. Code derives `w_query` from facets using same `compute_w_chunk` formula as HERB
4. Retrieval scoring: `score += query_tag.w_query × query_tag.facets[facet] × chunk_edge.w_chunk × chunk_edge.w_facet × coalesce(chunk.relevance_to_file, 1.0)`
5. Plan shape: `{description, tags[], filters, ranking, answer_job, warnings}`
6. Answer-job modes: `direct_answer | list | compare | aggregate | summarize`, defaults `evidence_policy=retrieved_only`, `missing_evidence_policy=say_insufficient_evidence`
7. UI rule: show the plan beside retrieved results

## How to apply

When user mentions docs, the frontend, or "the architecture":
1. Don't propose backend HTTP routes. Don't propose a FastAPI server.
2. If a doc you're reading describes `/api/*` routes as endpoints, treat the routes as stale and the JSON shapes (if any) as content to extract.
3. Frontend = whole app. Backend = offline pipeline. That's it.
4. Field-name discipline: HERB graph uses `facet`, `w_chunk`, `w_facet`, `relevance_to_file`. Legacy `cluster`, `canonical_id`, `weight_local`, `weight_global` are old generic-tagger fields — do not use for HERB retrieval.

## User pain point worth remembering

User explicitly complained: *"i fucking cant understand why the agents always just 'kinda clean up' but leave the framework, documentation, scaffolding, some paint on the walls etc.. it's such a sloppy fucking mess"*. When cleaning up: actually delete the dead stuff. Don't leave empty placeholder dirs, contradictory docs, or orphan caches. Be thorough.
