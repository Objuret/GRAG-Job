# Thesis corrections (EN) — Thesis2026VT.pdf vs repository

**Purpose:** English parallel to [`Thesis2026VT_korrigeringar.md`](Thesis2026VT_korrigeringar.md). Use for supervisor meetings, abstract, or bilingual thesis sections. **Results use placeholders** until RAGAS export is complete.

**Last updated:** 2026-05-20.

---

## Placeholders (fill when RAGAS is done)

| Placeholder | Meaning |
|-------------|---------|
| `[N_GOLD]` | Number of gold questions (e.g. 100) |
| `[N_GRAPH_OK]` | Graph arm rows answered without `meta.error` |
| `[N_BASE_OK]` | Baseline arm rows answered without `meta.error` |
| `[MEDIAN_*]` / `[IQR_*]` | From `A_tags.report.json`, `B_baseline.report.json` |
| `[PILOT_NOTE]` | Export failures, timeouts, permanent skips |

---

## Quick reference: thesis claim vs reality

| Topic | Thesis often implies | Actual implementation |
|-------|----------------------|------------------------|
| Domain | Bonnier articles, journalists | **Salesforce HERB** (products, Slack, PRs, docs, QA) |
| Data | Multiple databases | **One** corpus → Neo4j (`herb`, eval: `herb-eval`) |
| Tagging | One LLM call: description + tags | **Two-pass** Anthropic `extract` + `describe` + `score` |
| Vectors | Out of scope | **e5** on `:Tag.emb_*` — **required** for graph retrieval |
| Graph retrieval | Graph traversal, multi-hop | **Tag kNN** + weighted **`HAS_TAG`** + gate; optional fulltext fallback |
| Eval baseline | Direct DB / raw data | **Lucene** on `Chunk.content` (export `mode: baseline`) |
| UI | Non-operational mockup | **Operational** local workbench (browser → Neo4j + LLM) |
| Ground truth | Manual double review | Dataset **`ground_truth`** via `build_gold_set.py` |
| Ch. 7 | Reported outcomes | PDF has **`[X]`** — narrative before numbers is **invalid** |

---

## Chapter 1 — Introduction

### [ERR-1.1] Domain

**Add after problem statement:**

> The implemented evaluation uses the **HERB** benchmark corpus (Salesforce): structured enterprise JSON (product documents, Slack, pull requests, meeting transcripts, QA pairs) materialised in **Neo4j**. Collaboration with Bonnier News motivates traceability requirements; **examples should be read against HERB**, not a specific Bonnier data model.

### [ERR-1.2] “General method”

> The pipeline supports multiple file formats, but **tagging and evaluation in this study are limited to `Salesforce__HERB`**. Generalisability is a **design goal**, not an empirically tested claim across corpora.

---

## Chapter 2 — Purpose and RQs

### [ERR-2.1] Baseline (purpose / RQ2)

**Replace closing paragraph of §2:**

> Evaluation compares (i) a **graph-enriched path**: query interpretation, vector grounding against a tag vocabulary in Neo4j, and chunk selection via weighted `HAS_TAG` edges under a structural gate, with (ii) a **conventional text baseline**: full-text search (Lucene) over chunk **raw text** without tags or gate. Both paths serialize retrieved segments into the same kind of context package for the **same** answer model.

**RQ2 footnote:**

> “Direct retrieval” means the baseline defined in §5.4 and §6.5 (Lucene on chunk content), **not** SQL against source databases.

### [ERR-2.2] Multi-hop

> Questions may require multiple segments or products, but **implemented retrieval does not perform explicit multi-hop graph traversal** (e.g. chained Cypher). Relational complexity is handled via tag overlap, facet weights, and optional lexical fallback. Multi-hop is a **question type**, not a guaranteed algorithmic property.

---

## Chapter 5 — Method

### [ERR-5.1] §5.2 Data

> Data: **HERB** (`Salesforce__HERB`) → Neo4j database **`herb`**. Full semantic run: **`pilot_full_herb`** (~5843 chunks per project docs). Eval database **`herb-eval`** excludes QA/oracle sections to reduce leakage.

### [ERR-5.2] §5.3 Graph retrieval

> - Query interpretation (two-pass LLM + gate).
> - Tag grounding: e5 embeddings + kNN on `Tag.emb_<facet>`.
> - Chunk ranking: weighted `HAS_TAG` + `relevance_to_file` + gate.
> - Fallback: fulltext on `chunk_fulltext` if tag scoring returns nothing under gate.

### [ERR-5.3] §5.4 Baseline — **replace entire section**

> **Baseline (evaluation export):** user question as plain text → Neo4j fulltext index **`chunk_content_ft`** on `Chunk.content` (Lucene), same dataset scope and section exclusions as graph arm on `herb-eval`. Default export cap **150 chunks** when limit is unset (uncapped Lucene can return thousands of hits and break the answer API). Same answer model, prompt mode, temperature 0.
>
> **Workbench alternative:** relevance baseline ranks by `relevance_to_file` under gate — used for interactive A/B, **not** primary gold-100 export unless configured.
>
> **Optional:** SQL-agent baseline (SQLite over raw HERB JSON, LLM + SQL tool) — independent of Neo4j; report separately if included.

### [ERR-5.4] §5.5 Scenarios

> **A (graph-enriched):** interpret → ground tags → weighted retrieval → LLM.  
> **B (text baseline):** Lucene on raw chunk text → LLM.  
> **Not compared:** raw JSON files fed directly to the LLM (unless SQL-agent arm is explicit).

### [ERR-5.5] §5.7 Ground truth

> Gold references come from HERB **`ground_truth`** in `qa_record` chunks via `python -m evaluation.build_gold_set` (read-only Neo4j). **Authoritative dataset labels**, not ground-up manual authoring.
>
> **Remove** mandatory “second reviewer double-check” unless documented outside the repo.

### [ERR-5.6] §5.6 Hallucination metrics

> Primary operationalisation: **RAGAS faithfulness**, **context recall/precision** vs `reference`. The four manual categories in §4.2 are for optional qualitative review unless separately coded.

---

## Chapter 6 — System design (copy-paste block)

See Swedish one-pager: [`Thesis2026VT_kap6_ersattningstext.md`](Thesis2026VT_kap6_ersattningstext.md).

**English equivalent — §6.3.2 Transformation layer (core fix):**

> **Semantic enrichment (offline, Anthropic).** Stage `extract` runs **two model calls** per chunk: (1) description + tag strings; (2) facet scores for five dimensions. Edge weight **`w_chunk`** is computed in code from facet vectors. Per file: **`describe`** (summary) and **`score`** (comparative `relevance_to_file`, one batched call per file). Then **`materialize`** (structural fields on chunks) and **`embed-tags`** (e5 vectors on `:Tag`, vector indexes `tag_emb_<facet>`).

**Delete:** “vectors out of scope”; “UI illustrative only”; “description and tags in the same call”; “aggregated TAGGED edges on files” (legacy path, not HERB pilot).

---

## Chapter 7 — Results (template)

### §7.1 Overview

> Evaluation on **`[N_GOLD]`** questions from `ragas-questions.herb-gold100.jsonl` on **`herb-eval`**. Graph arm: interpretation + tag grounding + weighted `HAS_TAG` retrieval. Baseline arm: Lucene on `Chunk.content` (export cap 150 if limit unset). Answer model **[ANSWER_MODEL]**, judge **[JUDGE_MODEL]**, temperature 0. Answered before RAGAS: graph `[N_GRAPH_OK]/[N_GOLD]`, baseline `[N_BASE_OK]/[N_GOLD]`. `[PILOT_NOTE]`

**[PILOT_NOTE] example (from repo docs):**

> Pilot export: API errors on large contexts (Slack text); graph arm had more initial failures than baseline on uncapped retrieval; one permanent gate failure (`gold_personalizeforce_34`); RAGAS judge timeouts possible under concurrency — use `--timeout 600`.

### Tables (fill from `.report.json`)

| Metric | Baseline | Graph |
|--------|----------|-------|
| Answered (export) | `[N_BASE_OK]/[N_GOLD]` | `[N_GRAPH_OK]/[N_GOLD]` |
| Faithfulness median (IQR) | `[MEDIAN_FA_BASE] ([IQR_FA_BASE])` | `[MEDIAN_FA_GRAPH] ([IQR_FA_GRAPH])` |
| Context recall median (IQR) | `[MEDIAN_CR_BASE] ([IQR_CR_BASE])` | `[MEDIAN_CR_GRAPH] ([IQR_CR_GRAPH])` |
| Context precision median (IQR) | `[MEDIAN_CP_BASE] ([IQR_CP_BASE])` | `[MEDIAN_CP_GRAPH] ([IQR_CP_GRAPH])` |

### §7.6 Summary (write only after filling)

> On `[N_GOLD]` HERB gold questions, preliminary results show **[SUMMARY_AFTER_NUMBERS]**, subject to export cohort and `[PILOT_NOTE]`. No statistical generalisation beyond HERB/`herb-eval`.

---

## Chapter 8 — Discussion (bullets)

**RQ1:** Transformation layer = segmentation + offline two-pass tagging + tag vectors + query-time grounding + weighted `HAS_TAG` — **hybrid graph–vector RAG**, not pure multi-hop traversal.

**RQ2:** Interpret only after `[MEDIAN_*]` filled. Graph may win on context recall; baseline may win on “answered count” or simplicity — both can be true.

**Limitations:** single corpus, single eval graph, model-dependent, export/RAGAS in progress.

---

## Chapter 9 — Conclusion (template)

> We designed and implemented a transformation layer for HERB in Neo4j: deterministic chunking, two-pass semantic tagging, tag embedding, and query-time retrieval via tag grounding and weighted `HAS_TAG` edges. Against a **full-text baseline on raw chunk content**, we evaluated `[N_GOLD]` gold questions; claims about superiority on correctness, precision, and hallucination rate **require completed RAGAS tables** (Chapter 7). Contribution: reproducible pipeline and a clear separation between enriched graph retrieval and uncontrolled text search.

---

## Three “baselines” (do not conflate)

| Name | What it does | Used in gold-100 export? |
|------|----------------|---------------------------|
| Thesis “direct DB” | Not implemented as stated | No |
| Run Builder “B · baseline” | `relevance_to_file` + gate | No (unless you export that spec) |
| RAGAS `mode: baseline` | Lucene on `chunk_content_ft` | **Yes** (`B_baseline.jsonl`) |
| SQL agent | SQLite + LLM SQL | Separate optional arm |

---

## Reproducibility commands

See Appendix A in [`Thesis2026VT_korrigeringar.md`](Thesis2026VT_korrigeringar.md).

---

## Error catalog (EN)

| ID | Severity | Issue |
|----|----------|--------|
| ERR-6.2a | High | Vectors claimed out of scope — **false** |
| ERR-6.2b | High | UI non-operational — **false** |
| ERR-6.3 | High | Single LLM call — **two-pass extract** |
| ERR-5.4 | High | SQL/direct DB baseline — **Lucene** |
| ERR-5.3 | Medium | Traversal — **tag scoring** |
| ERR-5.7 | Medium | Manual double review — **dataset GT** |
| ERR-7 | High | Chapter 7 narrative without numbers |
| ERR-1.1 | Medium | Bonnier examples vs HERB data |

---

*English parallel — pair with Swedish source `Thesis2026VT_korrigeringar.md` and copy-paste `Thesis2026VT_kap6_ersattningstext.md`.*
