---
name: dual-dataset-eval-plan
description: "Thesis will evaluate the artefact on BOTH HERB and Bonnier data, with different eval regimes per dataset"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7859cd2b-6907-49de-a866-8ef474a3f090
---

**SCOPED 2026-06-13: the v2 build + eval is HERB-only for now — Bonnier is DEFERRED to a later phase** (user: "the Bonnier set will have to wait until some other time"). The dual-dataset intent below survives as the eventual plan; nothing Bonnier gets built now. Thesis is done ([[thesis-is-done]]) — read the framing below as v2-validation, not thesis work.

The original plan evaluates the same artefact/pipeline on **two** datasets, each playing a distinct role (decided 2026-05-22, "nothing set in stone" but affirmed repeatedly by the user):

- **HERB** = the quantitative, *scored* run: graph vs Lucene baseline, RAGAS with authoritative ground truth (gold-100). This is where the comparison and numbers live. Frame HERB as "an established enterprise-RAG benchmark (Salesforce)", never "one we found online" — its reproducibility is a strength.
- **Bonnier News data** = *naturalistic* evaluation: run ingestion over their real multi-system content (scrape / feed / CMS), illustrate retrieval with self-authored questions. NO comparable RAGAS-vs-baseline numbers, because there is no independent ground truth.

Validity framing the user converged on: real Bonnier data strengthens **external/ecological validity** (naturalistic eval, DSR) and **practical relevance** — NOT internal validity, NOT the quantitative results. "Bonnier is a big name" is not itself a validity argument; "access to authentic heterogeneous production data across real source systems" is.

**Why:** keeps the two datasets doing what each is good for (HERB = rigor/reproducibility, Bonnier = relevance/authenticity); the combination reads stronger than either alone for a DSR reviewer.
**How to apply:** never present Bonnier results as ground-truth-measured; never downgrade/replace HERB. Bonnier ground truth is generated/self-authored (RAGAS synthetic testset from raw docs), not supplied by Bonnier.

The Bonnier data ask is **format-first, not volume-first**: one native raw dump per ingestion pipe (scrape/feed/CMS), unchanged format, ≤150 MB total, one topic/beat/week so content overlaps across pipes. Prefer JSON/JSONL/Parquet (chunker handles these today); raw HTML/XML/RSS and CSV need a new access-layer adapter — see [[canvas-pipeline-lane-non-interactive]] for eval-arm context.
