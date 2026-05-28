# RAGAS evaluation report (thesis notes)

Methodology and known limitations for the HERB gold-100 comparison
(**A · tags** graph vs **B · baseline** Lucene). Use this section verbatim or
adapted in the thesis methods/limitations chapter.

## Setup

### Primary run (thesis table — matched @k)

| Item | Value |
|---|---|
| Gold set | `frontend/scripts/ragas-questions.herb-gold100.jsonl` (100 questions) |
| Graph DB | `herb-eval` (QA/oracle sections excluded) |
| Answer model | `deepseek-chat` (both arms) |
| **Matched retrieval cap** | **`limit=40`** (graph + Lucene baseline) |
| Graph grounding | **`grounding_k=20`**, `minSim=0.78`, all five facets, `min_w_chunk=0`, `min_relevance_to_file=0` |
| Baseline retrieval | Lucene `chunk_content_ft` on raw `content`, **same k=40** |
| Answer + judge cap | **`answer_max_chunks=40`**, RAGAS **`--judge-max-contexts 40`**, `1800` chars/chunk |
| RAGAS judge | `deepseek-chat` (OpenAI-compatible), temperature 0 |
| RAGAS metrics | `faithfulness`, `context_recall`, `context_precision`, `answer_correctness` (@40) |
| Export concurrency | 8 (graph) / 10 (baseline) parallel questions |
| Scorer concurrency | 8 parallel RAGAS jobs (`RunConfig.max_workers`) |

**Rationale (declared before run):** k=40 is a fixed evidence budget (~40×1800 chars),
below uncapped pilot median (~120 chunks/question), with finite tag grounding (not
`grounding_k=0`). Not grid-searched on gold-100.

Config: `ragas_exports/A_tags.ragas.json`, `ragas_exports/B_baseline.ragas.json`.  
Exports: `ragas_exports/A_tags_k40.jsonl`, `ragas_exports/B_baseline_k40.jsonl`.  
Reports: `ragas_exports/A_tags_k40.report.json`, `ragas_exports/B_baseline_k40.report.json`.

### Pilot run (stress / appendix — uncapped)

| Item | Value |
|---|---|
| Graph retrieval | `limit=0`, `grounding_k=0`, `minSim=0.78` |
| Baseline retrieval | Lucene, **top 150** when RunSpec `limit=0` |
| Answer + judge cap | 200 chunks (API survival) |
| Observed | graph median ~120 chunks, ~13k grounded tag matches/question, precision @200 ~0.04–0.06 |

Artifacts: `ragas_exports/A_tags.jsonl`, `B_baseline.jsonl`, `*.report.json` (completed).

Visualize: workbench → **RAGAS Reports** → **Browse ragas_exports/** (pick files; nothing autoloads).

## Token and chunk cohort (export JSONL)

Full tables: [`ragas_export_token_stats.md`](ragas_export_token_stats.md).

Each export row records `meta.tokens.answer_in` / `answer_out` (answer LLM only),
`meta.n_chunks`, and full `retrieved_contexts` (RAGAS audit). Dedupe by `id`,
prefer rows without `meta.error` and with non-empty `response`.

**Primary k=40** (`A_tags_k40.jsonl`, `B_baseline_k40.jsonl`; paired n=99):

| Metric | Graph median | Baseline median | Ratio (graph/baseline) |
|--------|-------------:|----------------:|-----------------------:|
| `answer_in` tokens | 9 422 | 24 289 | **0,39** |
| `answer_out` tokens | 112 | 174 | 0,64 |
| Retrieved chunks | 15 | 40 | **0,38** |
| Context chars (sum) | 45 499 | 132 948 | **0,34** |

Graph tag grounding + gate often returns **fewer than k=40** segments; Lucene
baseline **fills the cap**. Faithfulness medians stay similar (§ Results); lower
context recall aligns with smaller evidence bags.

**Pilot uncapped** (`A_tags.jsonl`, `B_baseline.jsonl`): `answer_in` ratio ~0,84,
chunks ~0,82 — appendix only; graph retrieval can exceed baseline breadth.

Reproduce: `python ragas_exports/_token_stats.py` or export commands below.

## Answer-generation cohort

After deduplicating resume duplicates (same `id` kept once, preferring rows
without `meta.error`):

| Arm | Answered (initial) | Permanent skip | Retriable errors |
|---|---:|---:|---:|
| **A · tags (graph)** | 90 | 1 | 9 |
| **B · baseline** | 95 | 0 | 5 |

After `--retry-errors` with scrub + answer cap, report final counts from
`.report.json` `overall_n`.

**API JSON body rejection (14 questions on initial run)**  
DeepSeek returned `400 … unexpected end of hex escape` when building the answer
request. HERB **Slack-export chunk text** plus large evidence payloads caused
failures. Retry uses scrub + `--answer-max-chunks 200` for the answer API only.

**Permanent skip (1 graph question)**  
`gold_personalizeforce_34` — employee `eid_bac7c6c4` absent from `herb-eval`.

**Retry protocol (export failures)**  
Re-run failed rows with scrub + high answer cap (retrieval unchanged):

```bash
npm --workspace frontend run ragas:export -- --config ragas_exports/A_tags.ragas.json \
  --questions frontend/scripts/ragas-questions.herb-gold100.jsonl \
  --out ragas_exports/A_tags.jsonl --retry-errors --answer-max-chunks 200
```

- **`--retry-errors`**: only rows with `meta.error` are re-run; successes kept.
- **`--answer-max-chunks 200`**: top-200 chunks by score go to the **answer API
  only**; `retrieved_contexts` in JSONL stay complete for RAGAS.
- **`scrubForApi`**: strips bytes that break OpenAI-compatible JSON bodies.
- JSONL is **deduped by id** on write (no duplicate resume lines).

Initial run failures (before retry):  
DeepSeek returned `400 … unexpected end of hex escape` when building the answer
request. HERB **Slack-export chunk text** can contain bytes that break the
OpenAI-compatible JSON parser when large evidence payloads are sent. The answer
step truncates each chunk to 1,800 chars for the LLM, but many chunks still
compose a large message.

- **Graph (9):** `gold_contextforce_1`, `gold_contextforce_0`, `gold_pitchforce_6`,
  `gold_pitchforce_25`, `gold_pitchforce_27`, `gold_actiongenie_5`,
  `gold_actiongenie_7`, `gold_searchflow_12` (**1,092 chunks**),
  `gold_securityforce_7` (**1,464 chunks**).
- **Baseline (5):** `gold_contextforce_1`, `gold_contextforce_0`,
  `gold_contextforce_22`, `gold_coachforce_11`, `gold_actiongenie_1`.

The two **>1k-chunk** graph failures are dominated by **oversized retrieval**
at `limit=0` on broad product queries. The others fail at moderate chunk counts
(~130–170) and implicate **corpus text quality**, not retrieval breadth alone.
Retry applies scrub on the answer API for both arms. RAGAS `retrieved_contexts`
remain the full retrieved set.

**Invalid hard gate (same permanent skip)**  
`gold_personalizeforce_34` references employee `eid_bac7c6c4`, which is not
present in `herb-eval`. The interpreter emits a hard gate the corpus cannot
satisfy; retrieval aborts before the answer LLM.

### Interpretation for the paper

These are **infrastructure / corpus artefacts**, not evidence that the graph
method is worse on those topics. They bound the **evaluated n** and should be
reported alongside aggregate metrics. Re-running failed ids after scrubbing or
capping answer evidence would change the cohort; the current run is intentionally
unscrubbed on the graph arm (same retrieval contract as the workbench).

## RAGAS scoring: timeouts

RAGAS judge input is **capped at 200 contexts × 1800 chars** (matches export
answer API). Full retrieval stays in JSONL for audit.

With `--concurrency 10` and short timeouts, the progress bar may show:

```text
Exception raised in Job[N]: TimeoutError()
```

This means a single judge sub-job exceeded the timeout (often under parallel
load or on large context rows). RAGAS retries (`max_retries=10`); persistent
timeouts yield **NA** for that metric on that sample. The run continues; check
`.report.json` per-sample scores and `overall_n`.

Mitigation for re-runs: `--timeout 600` and/or lower `--concurrency` (e.g. 5).
The scorer defaults were raised to `--timeout 600` after the first pilot run.

## Duplicate JSONL lines

Resume and parallel export can append multiple lines per question `id`. The
scorer dedupes by id (preferring successful rows). Raw JSONL line count can
exceed 100; unique ids remain 100.

## Results (2026-05-20)

Scored with `python -m evaluation.ragas_eval` (`--timeout 600`, judge caps
200 contexts × 1800 chars). Reports live locally under `ragas_exports/` (gitignored).

**Export cohort (deduped JSONL by `id`, no `meta.error`):**

| Arm | Answered | RAGAS-scored (`n_samples`) |
|-----|----------|----------------------------|
| **A · tags (graph)** | 92/100 | 92 (faithfulness), 91 (context_recall) |
| **B · baseline (Lucene)** | 95/100 | 95 |

**RAGAS medians (per-sample; use these in thesis tables, not `overall` means):**

| Metric | Baseline median (IQR) | Graph median (IQR) | Δ graph − baseline |
|--------|----------------------|----------------------|--------------------|
| faithfulness | 0,80 (0,61–1,00) | 0,81 (0,58–1,00) | +0,01 |
| context_recall | 1,00 (0,00–1,00) | 0,86 (0,00–1,00) | −0,14 |
| context_precision | 0,00 (0,00–0,05) | 0,00 (0,00–0,03) | ≈0 |

`overall` in `.report.json` is the **arithmetic mean** over scored samples (e.g.
graph faithfulness mean 0,74) — do not confuse with median.

**Interpretation (short):** baseline recalls gold evidence more often on this
cohort (higher context_recall median) while faithfulness is similar. Very low
context_precision medians reflect noisy Lucene/graph context bags and judge
strictness — discuss limitations, not “precision = 0” as a product bug.
`answer_correctness` requires `OPENAI_API_KEY` (embeddings). Until that is set, run
`python -m evaluation.answer_token_score --merge-report …` on the same JSONL for
deterministic HERB `eid_*` answer F1 (free; merged into the report JSON).

## Suggested thesis wording (short)

> We evaluated 100 HERB gold questions on `herb-eval` with DeepSeek as both
> answer model and RAGAS judge. After export dedupe, the graph arm produced
> 92/100 answers and the Lucene baseline 95/100. RAGAS faithfulness (median)
> was similar (graph 0,81 vs baseline 0,80); context_recall median was lower
> on the graph arm (0,86 vs 1,00) on the scored subsets. Failures and partial
> cohorts are due to oversized graph retrieval, Slack-derived text breaking the
> answer API, one invalid hard gate, and judge timeouts — see sections above.

## Commands (reproduce)

```bash
# Smoke (5 questions) before full primary run
npm --workspace frontend run ragas:export -- --config ragas_exports/A_tags.ragas.json \
  --questions frontend/scripts/ragas-questions.herb-gold100.jsonl \
  --out ragas_exports/_smoke_k40.jsonl --fresh --max 5

# Primary export (k=40 — configs in *.ragas.json)
npm --workspace frontend run ragas:export -- --config ragas_exports/A_tags.ragas.json \
  --questions frontend/scripts/ragas-questions.herb-gold100.jsonl \
  --out ragas_exports/A_tags_k40.jsonl --fresh --concurrency 8
npm --workspace frontend run ragas:export -- --config ragas_exports/B_baseline.ragas.json \
  --questions frontend/scripts/ragas-questions.herb-gold100.jsonl \
  --out ragas_exports/B_baseline_k40.jsonl --fresh --concurrency 10

# Score (@40) — full thesis metrics (answer_correctness needs OPENAI_API_KEY)
cd backend
python -m evaluation.ragas_eval --input ../ragas_exports/A_tags_k40.jsonl \
  --thesis \
  --report ../ragas_exports/A_tags_k40.report.json --judge-max-contexts 40 --concurrency 4 --timeout 600
python -m evaluation.ragas_eval --input ../ragas_exports/B_baseline_k40.jsonl \
  --thesis \
  --report ../ragas_exports/B_baseline_k40.report.json --judge-max-contexts 40 --concurrency 4 --timeout 600

# Answer correctness without OpenAI (HERB eid_* token F1) — merge into report:
python -m evaluation.answer_token_score --input ../ragas_exports/A_tags_k40.jsonl \
  --merge-report ../ragas_exports/A_tags_k40.report.json
python -m evaluation.answer_token_score --input ../ragas_exports/B_baseline_k40.jsonl \
  --merge-report ../ragas_exports/B_baseline_k40.report.json

# RAGAS answer_correctness only (needs OPENAI_API_KEY), merge into existing report:
python -m evaluation.ragas_eval --input ../ragas_exports/A_tags_k40.jsonl \
  --metrics answer_correctness --merge-report ../ragas_exports/A_tags_k40.report.json \
  --judge-max-contexts 40 --concurrency 4 --timeout 600
```
