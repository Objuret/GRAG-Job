# Thesis PDF vs repository — full comparison

**Document:** `Thesis2026VT.pdf` (Examensarbete, Högskolan Dalarna, VT 2026)  
**Compared to:** `A:/exjobbet/repo` (code, `docs/`, `ragas_exports/`)  
**Date:** 2026-05-20  

**Related:** [`repo_truth_comprehensive.md`](repo_truth_comprehensive.md) (what the code is), [`Thesis2026VT_korrigeringar.md`](Thesis2026VT_korrigeringar.md) (replacement text + placeholders).

---

## How to read this document

| Marker | Meaning |
|--------|---------|
| **[FEL]** | Contradicts implementation or repo evidence |
| **[MISSVISANDE]** | Partially true; misleading without clarification |
| **[PLATSHÅLLARE]** | Thesis claims outcomes but PDF uses `[X]` or empty tables |
| **[OK]** | Aligns with code/docs |
| **[EJ I REPO]** | May be true locally; not verifiable in this clone |

---

## Part A — What the thesis claims vs what exists

### A.1 Stated thesis scope (from PDF)

| Thesis claims | Reality |
|---------------|---------|
| Grafbaserad RAG för heterogena databaser | **[OK]** in spirit — Neo4j + tag RAG on HERB JSON |
| Bonnier News operational context | **[MISSVISANDE]** partner framing; **data is Salesforce HERB**, not Bonnier article DBs |
| Baseline = direkt databashämtning utan graf | **[FEL]** eval baseline = **Lucene on chunk text**; not SQL, not raw files to LLM |
| Multi-hop-frågor central | **[MISSVISANDE]** questions can be complex; **no multi-hop traversal** in code |
| Transformationslager utan vektorer | **[FEL]** e5 tag embeddings are **required** for graph arm |
| UI illustrerar endast | **[FEL]** operational workbench with live Neo4j + LLM |
| Semantisk berikning i ett LLM-anrop | **[FEL]** two-pass `extract` + separate `describe`/`score` |
| Filnivå TAGGED rollup | **[FEL]** HERB pilot does not write `TAGGED` edges |
| Ground truth manuellt + dubbelgranskning | **[FEL]** `build_gold_set.py` reads dataset `ground_truth` |
| Kap. 7 resultat redovisade | **[PLATSHÅLLARE]** all values `[X]` but narrative assumes outcomes |

### A.2 What was actually built (timeline)

**Phase 1 — Graph construction (backend)**

1. Sync **HERB** → `backend/data/raw/Salesforce__HERB/` (`python -m data_access.raw sync`).
2. `bootstrap_schema.py` — constraints, indexes, vector index definitions.
3. `run_preflight.py --dataset-id Salesforce__HERB` — `:Source`, `:File`, `:Chunk` (HERB chunker), worklist seed (legacy only).
4. `python -m tagging` with **`PILOT_NAME=pilot_full_herb`**, **`TAGGING_SELECTION_MODE=all`** (not default 14-chunk smoke):
   - **select** → all ~5843 chunks
   - **extract** → two Anthropic passes per chunk → `HAS_TAG` (`facet`, `w_chunk`, `w_facet`)
   - **describe** → `File.description`
   - **score** → `Chunk.relevance_to_file`
   - **materialize** → hard gate fields + fulltext indexes
   - **embed-tags** → e5 on `:Tag`, `tag_emb_*` indexes
5. Archive referenced: `pilot_full_herb_snapshot_20260514T052226Z.zip` (often absent from git clone).

**Phase 2 — Eval-safe graph**

1. `create_herb_eval_db.py` → **`herb-eval`** (excludes QA/oracle/product_profile sections).
2. `NEO4J_DATABASE=herb-eval python -m tagging embed-tags`.

**Phase 3 — Query path (frontend)**

1. Workbench: live Neo4j + multi-provider LLM in browser.
2. Usage canvas (`runUsageGraph`) + Run Builder (`runRunSpec`).
3. Interpret → e5 tag grounding → weighted `HAS_TAG` retrieval (not multi-hop Cypher).

**Phase 4 — Evaluation (in progress)**

1. `build_gold_set.py` → `ragas-questions.herb-gold100.jsonl` (dataset `ground_truth`, not manual authoring).
2. Export `A_tags.jsonl` (graph) / `B_baseline.jsonl` (Lucene on chunk text).
3. `evaluation/ragas_eval.py` — scoring started; **PDF chapter 7 tables still `[X]`**.

**Not done** despite thesis framing: Bonnier production integration, multi-dataset delivery, multi-hop traversal algorithm, manual double-reviewed gold, filled RAGAS tables in PDF.

---

## Part B — Chapter-by-chapter error catalog

### B.1 Front matter (s. 6–7)

| ID | Issue |
|----|--------|
| P-ABS | Abstract/sammanfattning empty — not submission-ready |

### B.2 Chapter 1 — Inledning

| ID | Marker | Thesis says | Reality |
|----|--------|-------------|---------|
| 1.1a | [MISSVISANDE] | Bonnier: artiklar, journalister, flera databassystem | HERB: produkter, Slack, PR, eid_*, QA |
| 1.1b | [MISSVISANDE] | Generell metod oberoende av dataorganisation | HERB hard-coded in `tagging/pipeline.py` |
| 1.2 | [OK] | Problem: platt hämtning, hallucinationer | Reasonable; solution is tag-graph RAG not classic KG traversal |

**Examples that must change:** §4.2 multi-hop example with "journalist X" → use HERB product/employee examples.

### B.3 Chapter 2 — Syfte & RQ

| ID | Marker | Issue |
|----|--------|-------|
| 2.1 | [FEL] | RQ2 baseline "direkt databashämtning" | See **three baselines table** below |
| 2.2 | [MISSVISANDE] | Multi-hop as algorithmic guarantee | Frågetyp only |

### B.4 Chapter 4 — Theory

| ID | Marker | Issue |
|----|--------|-------|
| 4.2 | [FEL] | Journalist/ämne examples | HERB domain |
| 4.7 | [MISSVISANDE] | Graph vs vector as either/or | Implementation is **hybrid** |

### B.5 Chapter 5 — Method

| ID | § | Marker | Issue |
|----|---|--------|-------|
| 5.1 | 5.2 | [MISSVISANDE] | "Flera databaskällor" → one HERB corpus → Neo4j |
| 5.2 | 5.3 | [FEL] | "Traversal mellan informationsobjekt" → tag kNN + HAS_TAG score |
| 5.3 | 5.4 | [FEL] | "Direkta databasfrågesvar" → Lucene baseline in export |
| 5.4 | 5.5 | [MISSVISANDE] | Scenario 1 "obearbetad rådata" → chunked Lucene, not raw JSON |
| 5.5 | 5.7 | [FEL] | Manual double-reviewed ground truth |
| 5.6 | — | [MISSVISANDE] | Four hallucination categories not auto-scored unless manual |

### B.6 Chapter 6 — System design (highest density of errors)

| ID | § | Marker | Issue |
|----|---|--------|-------|
| 6.1 | 6.2 | [FEL] | "Vektorer utanför scope" |
| 6.2 | 6.2 | [FEL] | UI not connected to Neo4j |
| 6.3 | 6.3.2 | [FEL] | Description + tags in same call |
| 6.4 | 6.3.2 | [FEL] | TAGGED file-level rollup |
| 6.5 | 6.3.2 | [MISSVISANDE] | "kluster" → use **facet** for HERB |
| 6.6 | 6.4 | [MISSVISANDE] | empty segments — legacy path, not HERB tagging |
| 6.7 | 6.4 | [FEL] | "Inga vektorindex" repeated |
| 6.8 | 6.5 | [MISSVISANDE] | Baseline described as raw/minimal vs Lucene |

**Full replacement text:** [`Thesis2026VT_kap6_ersattningstext.md`](Thesis2026VT_kap6_ersattningstext.md)

### B.7 Chapter 7 — Results

| ID | Marker | Issue |
|----|--------|-------|
| 7.0 | [PLATSHÅLLARE] | All tables `[X]` |
| 7.1 | [FEL] | Narrative claims better performance without numbers |
| 7.2 | [FEL] | "Färre tokens" in transformerat — graph at limit=0 can be huge |
| 7.3 | [EJ I REPO] | `.report.json` not in clone; `.score.log` suggests partial run |

**Pilot facts** (`docs/backend/ragas_eval_report.md`, scored 2026-05-20):

| Fact | Value |
|------|-------|
| Gold questions | 100 |
| Graph answered (deduped export) | **92/100** |
| Baseline answered (deduped export) | **95/100** |
| RAGAS scored (faithfulness) | graph 92, baseline 94 |
| Median faithfulness | graph **0,81**, baseline **0,80** |
| Median context_recall | graph **0,86**, baseline **1,00** |
| Permanent skip | 1 (`gold_personalizeforce_34`, invalid gate) |
| Initial API errors (pre-retry) | 9 graph, 5 baseline |

### B.8 Chapters 8–9

| ID | Marker | Issue |
|----|--------|-------|
| 8.x | [FEL] | Discusses concrete outcomes as if measured in Ch. 7 |
| 9 | [FEL] | Conclusion states superiority without filled metrics |

---

## Part C — Three different "baselines"

The thesis uses one word for three implementations:

| Name in thesis/UI | Code path | Used in gold-100 RAGAS export? |
|-------------------|-----------|--------------------------------|
| "Direkt databashämtning" (kap 5–6) | Not implemented | No |
| Run Builder **"B · baseline"** | `retrieveBaseline` → `relevance_to_file` + gate | No (unless you export that spec) |
| RAGAS **`mode: baseline`** | `retrieveBaselineContent` → Lucene `chunk_content_ft`, cap 150 | **Yes** → `B_baseline.jsonl` |
| **SQL agent** (not in thesis §5.4) | SQLite + LLM SQL tool | Optional separate arm |

**[FEL]** to defend thesis without explicitly defining which baseline was evaluated.

---

## Part D — "Grafbaserad retrieval" — what code actually does

Thesis and RQ1 imply **graph traversal / multi-hop**. Actual graph arm:

```
User question
  → interpretPrompt (2-pass LLM: description, tags, gate)
  → embedPromptTagFacets (e5 passage:)
  → db.index.vector.queryNodes(tag_emb_<facet>)  // kNN per facet + all
  → scoreCypher: weighted HAS_TAG overlap × sim × relevance_to_file
  → optional: chunk_fulltext fallback if zero hits
  → serialize chunk.content → generateAnswer
```

**[FEL]** to describe only as "graftraversal".  
**[OK]** to call it graph-based RAG if defined as: structured Neo4j artefact + tag relations + optional lexical fallback (hybrid with vectors).

---

## Part E — Domain mismatch (Bonnier vs HERB)

| Thesis examples | HERB reality |
|-----------------|--------------|
| Journalister, artiklar, ämnen | Produkter (ActionGenie, PitchForce, …) |
| Händelsedata, publicering | Slack, PRs, meeting transcripts |
| Flera databassystem | Single JSON corpus → Neo4j |

Collaboration with Bonnier can remain as **motivation**; **implementation and evaluation must name HERB**.

---

## Part F — What is NOT done (thesis may imply otherwise)

- Multi-hop Cypher chains as retrieval algorithm  
- Manual double-reviewed gold set (in repo)  
- Completed numeric results in PDF  
- Production deployment  
- `clustering/queries/*.cypher`  
- True calendar date filtering (only `years` from temporal tag tokens)  
- Vectors "out of scope" while using them centrally  
- TAGGED rollup on HERB pilot  
- Other datasets (DocVQA, FEVEROUS) end-to-end  

---

## Part G — What IS done (cite these in thesis)

| Deliverable | Evidence |
|-------------|----------|
| HERB-aware chunking (~5843 chunks) | `chunker.py`, `docs/backend/status.md` |
| Full pilot `pilot_full_herb` | `pilot_full_herb_report.md`, snapshot zip ref |
| Two-pass tagging + w_chunk in code | `tagging/pipeline.py` |
| materialize + embed-tags | pipeline stages, status |
| herb-eval | `create_herb_eval_db.py` |
| Operational workbench | `App.jsx`, `pipeline.ts` |
| RAGAS harness | `ragas-export.ts`, `evaluation/ragas_eval.py` |
| SQL baseline (optional RQ2 arm) | `baselines/sql_agent.py` |

---

## Part H — Documentation trustworthiness

| Trust | Documents |
|-------|-----------|
| High (cross-check code) | `graph_schema.md`, `backend/status.md`, `pilot_full_herb_report.md`, `ragas_eval_report.md` |
| Medium | `system_map.md`, `frontend/status.md` |
| Low / stale | Root `README.md` (install, Anthropic-only), `pyproject.toml`, `.env.example` DB name, thesis Ch.6 "no vectors" |

---

## Part I — Suggested honest thesis narrative (before numbers)

> We implemented a transformation layer that materialises the HERB corpus in Neo4j, enriches chunks with a two-pass tagging pipeline, indexes tags with e5 embeddings, and retrieves evidence at query time via tag grounding and weighted HAS_TAG edges under a structural gate. We compared this graph-enriched path to a Lucene full-text baseline on raw chunk content using 100 dataset gold questions on an eval-safe graph (`herb-eval`). Export and RAGAS scoring were ongoing at writing time; aggregate metrics are reported only where export completed successfully, with explicit discussion of API and retrieval-scale failures.

---

## Part J — File index for supervisors

| Question | Read first |
|----------|------------|
| What did we build? | `repo_truth_comprehensive.md` |
| What is wrong in the PDF? | This file + `Thesis2026VT_korrigeringar.md` |
| What text to paste into Word? | `Thesis2026VT_kap6_ersattningstext.md` |
| English summary? | `Thesis2026VT_corrections_EN.md` |
| How to reproduce? | `Thesis2026VT_korrigeringar.md` Appendix A |

---

## Part J2 — Internal thesis contradictions (fix together)

| § | Contradiction |
|---|----------------|
| 4.8 | Modern GraphRAG uses embeddings for entry points |
| 6.2 / 6.4 | Vectors explicitly out of scope |
| 6.3.2 | Description + tags in same LLM call |
| 5.3 | Traversal-based retrieval |
| 6.3.3–6.3.4 | Graph as index only (partially true without tag vectors) |

After corrections, **§4.8 and §6 must agree**: hybrid tag-grounding + structural graph.

---

## Part K — Master error list (quick lookup)

| ID | Severity | Topic |
|----|----------|--------|
| E1 | Critical | Vectors out of scope (thesis) vs required (code) |
| E2 | Critical | UI non-operational (thesis) vs operational (code) |
| E3 | Critical | One LLM call (thesis) vs two-pass extract (code) |
| E4 | Critical | Baseline = direct DB (thesis) vs Lucene (eval) |
| E5 | Critical | Ch.7 narrative without `[X]` filled |
| E6 | High | Graph traversal / multi-hop (thesis) vs tag score (code) |
| E7 | High | Manual ground truth (thesis) vs dataset (code) |
| E8 | Medium | Bonnier examples vs HERB data |
| E9 | Medium | TAGGED rollup (thesis) vs not in HERB pilot |
| E10 | Medium | Three baselines conflated |

---

*End of thesis PDF vs reality comparison.*
