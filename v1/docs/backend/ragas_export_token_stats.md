# RAGAS export — token, chunk, and context cohort stats

Computed **2026-05-20** from local JSONL under `ragas_exports/` (gitignored).
Producer: `frontend/scripts/ragas-export.ts` — each row’s `meta` block includes
`tokens.answer_in`, `tokens.answer_out`, `n_chunks`, `answer_chunks`,
`elapsed_ms`; `retrieved_contexts` holds full segment text for RAGAS.

**Dedup rule:** one row per `id`; prefer rows without `meta.error` and with
non-empty `response` (same as export resume logic).

**Answered cohort:** rows that produced an answer (no `meta.error`).

---

## Primary thesis run — matched k = 40

**Files:** `A_tags_k40.jsonl`, `B_baseline_k40.jsonl`  
**RunSpec:** `limit=40`, `grounding_k=20`, `answer_max_chunks=40` (both arms),
`deepseek-chat`, `herb-eval`, gold-100.

| Metric | Graph median (p25–p75) | Baseline median (p25–p75) | Ratio graph/baseline (medians) |
|---|---:|---:|---:|
| `meta.tokens.answer_in` | 9 422 (4 832–14 818) | 24 289 (23 074–26 090) | **0,39** |
| `meta.tokens.answer_out` | 112 (70–172) | 174 (118–250) | **0,64** |
| `meta.n_chunks` / contexts | 15 (8–23) | 40 (40–40) | **0,38** |
| Sum chars in `retrieved_contexts` | 45 499 (23 456–75 152) | 132 948 (128 944–141 390) | **0,34** |
| `meta.elapsed_ms` | 6 744 (5 920–8 526) | 3 559 (2 942–4 458) | 1,89 |

**Answered:** graph 99/100, baseline 99/100 (one graph id permanently skipped in
eval corpus: `gold_personalizeforce_34`).

### Paired comparison (n = 99)

Ids with successful answers in **both** arms at k = 40:

| Metric | Graph median | Baseline median | Median of per-id ratios (graph/baseline) |
|---|---:|---:|---:|
| `answer_in` | 9 422 | 24 289 | 0,39 |
| `answer_out` | 112 | 174 | 0,73 |
| `n_chunks` | 15 | 40 | 0,38 |
| Context chars | 45 499 | 132 948 | 0,35 |

**Interpretation:** Tag grounding + gate often return **fewer than 40** segments
(graph median 15); Lucene baseline **fills the cap** (median 40). Answer prompt
tokens scale with evidence sent to the answer API (`answer_max_chunks=40` on
both arms). At similar median faithfulness (0,81 vs 0,80 on RAGAS-scored
subsets), the graph arm used roughly **two fifths** of baseline answer-input
tokens and **one third** of retrieved character volume.

---

## Pilot / appendix — uncapped retrieval

**Files:** `A_tags.jsonl`, `B_baseline.jsonl`  
**RunSpec:** graph `limit=0`, `grounding_k=0`; baseline Lucene **top 150**;
`answer_max_chunks=200` (API survival).

| Metric | Graph median (p25–p75) | Baseline median (p25–p75) | Ratio graph/baseline |
|---|---:|---:|---:|
| `answer_in` | 74 802 (16 796–85 967) | 89 542 (86 011–95 342) | **0,84** |
| `answer_out` | 131 (86–213) | 197 (128–274) | **0,67** |
| `n_chunks` | 122 (32–141) | 150 (150–150) | **0,82** |
| Context chars | 388 198 (94 365–447 678) | 494 703 (483 383–519 870) | **0,80** |

**Answered:** graph 92, baseline 95. **Paired n = 89.**

Ocapped graph retrieval can exceed baseline chunk counts on broad queries
(max observed 1 330 chunks); answer API was capped at 200 chunks while JSONL
retained full contexts for RAGAS. Do **not** use pilot ratios as the primary
efficiency claim — use k = 40.

---

## Reproduce

```bash
cd a:/exjobbet/repo
python ragas_exports/_token_stats.py   # optional; or re-run inline script from git history
```

Or aggregate manually:

```bash
# Export (if missing)
npm --workspace frontend run ragas:export -- --config ragas_exports/A_tags.ragas.json \
  --questions frontend/scripts/ragas-questions.herb-gold100.jsonl \
  --out ragas_exports/A_tags_k40.jsonl --fresh
npm --workspace frontend run ragas:export -- --config ragas_exports/B_baseline.ragas.json \
  --questions frontend/scripts/ragas-questions.herb-gold100.jsonl \
  --out ragas_exports/B_baseline_k40.jsonl --fresh
```

`meta.tokens` is written in `ragas-export.ts` after `generateAnswer()` returns
`tokensIn` / `tokensOut` for the scrubbed evidence actually sent to the answer
LLM (subject to `answer_max_chunks`).
