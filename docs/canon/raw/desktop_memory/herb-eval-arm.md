---
name: herb-eval-arm
description: "the herb_eval v3 arm — the old Neo4j herb-eval graph's retrieval, ported native to compare vs lucene/vector"
metadata: 
  node_type: memory
  type: project
  originSessionId: ad4af0a8-2d08-4823-9c8c-113d0685e595
---

`v3/pipelines/artefact_v1.py` is a fourth retrieval arm (`run.py --arm artefact_v1`)
that reproduces the **Neo4j `herb-eval` graph's** facet-grounded tag retrieval as
a native v3 arm, so the old (cleaned, post-thesis) artefact graph competes
head-to-head with the lucene + vector arms under the SAME shared generator and the
SAME RAGAS eval at k=50.

Pipeline (logic ported from the deleted v1 TS arm — `retrieval.ts` /
`interpreter.ts` / `embeddings.ts`, recoverable at git `bb60e647^`): interpret
(two NIM/qwen passes → need-description + tags + hard gate, then per-facet tag
scores; `w_query` = strength×coverage) → ground (embed prompt tags with the v3
nemotron embedder on NIM, kNN the graph's `tag_emb` vector index, top-K per prompt
tag) → weighted-overlap scoring Cypher over `HAS_TAG` edges, top-k, oracle sections
excluded → shared v3 generator writes the answer.

Decisions:
- **Entire arm runs on the v3 model stack (NIM).** Interpret + generate + judge =
  qwen; grounding embedder = nemotron (`nvidia/llama-nemotron-embed-1b-v2`, reuses
  `pipelines.vector._embed`). NO local model, NO e5.
- **The semantic layer = two nemotron vector families (the user's concept, NOT
  v1-as-built):** the tag IS its embedding (`t.emb` = the bare tag name, one
  `tag_emb` index — NO pasted-in description context, NO per-facet tag vectors),
  and the chunk description IS an embedding (`c.desc_emb`, `chunk_desc_emb`
  index; description TEXT read from herb-eval-backup as embed input only).
  v1-as-built stuffed descriptions into six per-facet tag vectors — the user
  explicitly rejected that ("never wanted that context shit"); facets are numeric
  edge/prompt values, never embedded. `v3/reembed_herb_eval.py` (idempotent,
  skips complete families) builds both families + indexes and drops legacy
  layouts. Scoring: the v1 edge chain (w_query × facet match × w_chunk × w_facet
  × relevance_to_file × grounding sim × scope) summed per chunk, then ×
  `vector.similarity.cosine(c.desc_emb, prompt-description vector)` — the
  description crosscheck channel. Grounding: bare prompt-tag names, top-K
  (`HERB_GROUNDING_K` default 10; `HERB_MIN_SIM` floor default 0).
- **herb-eval's tag vocabulary is CLEAN** — verified live 2026-07-01: 0 eid_/bare-year
  tags of 19,716. The retag-facet-analysis pollution memory describes the PRE-retag
  v1 build; never attribute that pollution to herb-eval.
- **Edge shape: ONE HAS_TAG edge per (chunk, tag)** — verified live 2026-07-01:
  67,913 edges = 67,913 pairs; each edge carries the FULL facet vector as aligned
  arrays `facets`/`w_facets` (+ `w_chunk`, `run_id`). The v1 writer code and
  graph_schema.md (one edge per facet, scalar `facet`/`w_facet`) are STALE — the
  cleanup collapsed them. Facet agreement in scoring = DOT PRODUCT of the prompt
  tag's facet values with the edge's facet weights (facet absent from edge = 0);
  no best-facet picking.
- **herb-eval is POINTERS, not copies** — verified live 2026-07-01: 0 of 4,869 chunks
  carry content or description (the v1 graph_schema.md doc is STALE on this — it
  describes the pre-cleanup build). Chunks carry `locator_json` (section/index/
  indices/field/char_range) + offsets; Files carry `rel_path`+`sha256` resolving
  against `v3/data/raw` (all 33 hashes verified matching). The arm resolves text
  from raw at answer time, hash-verified. `locator_json` carries the HERB artifact
  `id` → **context_ids are real** (gold-citation space; id metrics work for this arm).
  The v1 full-text fallback is DELETED (its substrate — stored content — is gone);
  unservable questions fail loud into failures.jsonl.
- **Chunk descriptions live ONLY in `herb-eval-backup`** (4,869/4,869, plus the
  original e5 vectors). The reembed script reads them from there (read-only) as
  embedding INPUT for the six-per-tag facet vectors; only vectors land in herb-eval.
- Neo4j creds load from `v3/.env` via `nim._load_dotenv` (same as `NVIDIA_API_KEY`).
  Run with the repo `.venv` python.
- **`context_ids` is empty:** herb-eval chunks aren't keyed by HERB record id, so the
  2 id-based context metrics read 0 for this arm. Retrieval quality is read from
  `context_precision_nonllm` / `context_recall_nonllm` (string-sim of chunk text vs
  gold citation text). 12/14 selected metrics are fully comparable; an id-map is a
  possible follow-up.
- **Gated full-text fallback kept** (when no tags / no grounding / no tag-scored
  chunks) — it's part of the v1 arm and is logged each time, not silent.

Run-time prerequisites (user owns execution): Neo4j up with the `herb-eval` DB +
`NEO4J_PASSWORD`; `NVIDIA_API_KEY` for NIM; e5 downloads on first run. Verify
against the live DB before a full run: the HAS_TAG `run_id` (arm filters on
`pilot_full_herb`; override via `HERB_TAG_RUN_ID`), the `tag_emb_*` vector indexes,
and the `File-[:HAS_CHUNK]->Chunk` relationship. See [[herb-eval-is-the-artefact]],
[[arms-share-only-corpus-and-generator]], [[v3-arm-model-stack]].
