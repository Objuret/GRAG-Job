# Offline RAGAS evaluation

## RAG-safe HERB graph

HERB's raw product files contain evaluation and oracle surfaces that must not
be retrieved for RAG results:

- `answerable_questions` contains the eval question, `ground_truth`, and
  `citations`.
- `unanswerable_questions` contains the negative eval prompts.
- `product_profile` is derived from product-level `team` / `customers`, which
  is oracle-like for RAG evaluation.

Build a separate eval database from the full `herb` graph:

```powershell
cd backend
python scripts/create_herb_eval_db.py --source-db herb --target-db herb-eval --dry-run
python scripts/create_herb_eval_db.py --source-db herb --target-db herb-eval
$env:NEO4J_DATABASE='herb-eval'; python -m tagging embed-tags
```

The builder copies safe chunks and existing `HAS_TAG` edge weights. It does
not re-run extraction/scoring, does not mutate `herb`, and refuses to overwrite
a non-empty target database unless `--replace` is passed. File-level LLM
descriptions and old embeddings are deliberately not copied; regenerate
facet-aware `:Tag.emb_*` grounding vectors on `herb-eval`.

`python -m tagging materialize` also creates both full-text indexes used by
retrieval: `chunk_fulltext` for graph lexical fallback and `chunk_content_ft`
for the direct content baseline.

## Comparison contract (ceiling runs)

Thesis exports default to **minimum-strangle**: count caps stay at **0 = no
limit** unless you set them. Quality filters (graph: `minSim`, weight/relevance
floors; SQL: similarity is N/A) still apply.

| Arm | Run Builder route | Export `mode` | Headless execution |
|---|---|---|---|
| HERB tags | `tags` | `graph` | interpret → ground → tag overlap |
| Lucene (thesis RQ2 control) | `content` | `content` | Lucene on `c.content`, no interpret |
| Relevance baseline (Lane B) | `baseline` | `relevance` | interpret → `relevance_to_file` order, no tags |
| SQL agent | `sql_agent` | `sql_agent` | Python `backend/baselines/sql_agent.py` |

**0 semantics:** `limit=0`, `grounding_k=0`, `answer_max_chunks=0`, and
`answer_max_chunk_chars=0` mean **no cap** — the exporter does not substitute
hidden defaults. Legacy configs with `"mode": "baseline"` and no `route_origin`
still map to Lucene **content** (old label).

| Cap field | 0 means |
|---|---|
| `limit` / `grounding_k` / `answer_max_chunks` / SQL caps | No count cap |
| `answer_max_chunk_chars` | No per-chunk truncation |
| `answer_scrub` | `false` unless explicitly `true` in export |

SQL tool-call budget `0` still has a hard **200-iteration** sanity ceiling in
`backend/baselines/sql_agent.py`. Graph grounding `0` still queries the vector
index top-**1000** neighbors per prompt tag before `minSim` filtering (Neo4j
kNN behaviour, not an export override).

Set **`prompt_mode: context`** on graph/content/relevance RAG arms (never `raw`
for eval).

**Thesis limitations (export errors, judge timeouts, cohort sizes):**
[`docs/backend/ragas_eval_report.md`](../../docs/backend/ragas_eval_report.md).

## Thesis Harness

Preferred path for thesis results:

1. Build a gold set from the full `herb` database:

   ```powershell
   cd backend
   python -m evaluation.build_gold_set --database herb --count 100
   ```

2. Run graph, baseline, and/or SQL-agent exports from the repo root:

   ```powershell
   npm --workspace frontend run ragas:export -- --mode graph --questions frontend/scripts/ragas-questions.herb-gold100.jsonl --out backend/evaluation/graph.jsonl --fresh
   npm --workspace frontend run ragas:export -- --mode content --questions frontend/scripts/ragas-questions.herb-gold100.jsonl --out backend/evaluation/content.jsonl --fresh
   npm --workspace frontend run ragas:export -- --mode sql_agent --questions frontend/scripts/ragas-questions.herb-gold100.jsonl --out backend/evaluation/sql_agent.jsonl --fresh --model deepseek-chat
```

   (`--mode baseline` is legacy alias for **content** Lucene. Use Run Builder
   export with route **Baseline** for `mode: relevance`.)

   Or export RunSpec cards from the workbench (see below) and pass
   `--config path/to/run.ragas.json`.

3. Score (you pass the export path — nothing is hardcoded):

   ```powershell
   cd backend
   pip install -r requirements-eval.txt
   python -m evaluation.ragas_eval --input ../ragas_exports/YOUR_EXPORT.jsonl --thesis --report ../ragas_exports/YOUR_EXPORT.report.json
   python -m evaluation.aggregate_scores --input ../ragas_exports/YOUR_EXPORT.scored.jsonl --report ../ragas_exports/YOUR_EXPORT.report.json
   ```

   `ragas_eval` writes `<input>.scored.jsonl`: every export row preserved, plus
   `ragas`, `deterministic` (token F1), and `score_meta`. Failed export rows get
   `ragas: null` and `skip_reason` — no judge API spend. `retrieved_contexts`
   in the export is the same evidence slice the answer model saw; the scorer
   does not trim by default (`--judge-max-contexts 0`).

   Use `aggregate_scores` for means/medians and cohort filtering — not the scorer.

### Unified export contract (all arms)

Every headless `ragas:export` run uses the same JSONL shape regardless of arm
(`graph`, `content`, `relevance`, `sql_agent`):

| Layer | TS | Python |
|---|---|---|
| Cohort | `scripts/ragas/cohort.ts` | `evaluation/ragas_io.py` |
| Run audit (line 0) | `scripts/ragas/frame.ts` + `src/rag/exportContract.ts` | `ragas_io.write_run_frame` |
| Question rows | `baseQuestionRow()` | `question_row_shell()` |
| Prompt audit | `src/rag/pipelinePrompts.ts` | (SQL system prompt live per run) |
| Scorer input | — | `ragas_eval._load_rows` skips `kind=run_frame` |

**Line 0 — `run_frame`:** resolved config (models, caps, database, arm),
invocation flags, cohort **id list + metadata** (no question text; links optional
`*.manifest.json` from `build_gold_set`), and interpret/answer system prompts.

**Lines 1..N — `kind: question`:** `id`, `user_input`, `response`,
`retrieved_contexts`, `reference`, plus per-row `meta` only (plan, grounding,
tokens, timing, SQL queries, errors).

Only the **arm runner** differs (tag graph vs Lucene vs relevance order vs
Python SQL agent). Cohort file, RAGAS scorer hook-up, resume/skip ids, and
output schema are shared modules — not four bespoke pipelines.

### From the workbench Run Builder

Each RunSpec card has an **Export RAGAS run** button that writes a
`<label>.ragas.json` config under **`ragas_exports/`** at the repo root (Run Builder
**Save to** field; optional subfolder). Feed it to the exporter with `--config`:

```powershell
npm --workspace frontend run ragas:export -- --config ragas_exports/myrun.ragas.json --questions frontend/scripts/ragas-questions.herb-gold100.jsonl --out ragas_exports/myrun.jsonl --fresh
```

The CLI reads `mode` (graph/baseline/sql_agent), `database`, `model`,
`interpreter_model`, `prompt_mode`, `dataset_id`, `temperature`, graph caps
(`limit`, `grounding_k`, `min_sim`, `min_w_chunk`, `min_relevance_to_file`,
`active_facets`, `exclude_sections`), and SQL-agent caps (`max_tool_calls`,
`max_rows_per_query`, `max_cell_chars`) from the file. Any explicit CLI flag
overrides the config; the config overrides env/defaults.

RunSpec `route='module'` (composed Cypher) cannot be exported — the headless
exporter has no batch path for it. The button is disabled in that case.

RunSpec `route='sql_agent'` cannot execute in the browser; configure caps on
the card and export for headless `ragas:export`.

## UI Smoke Export

The workbench History tab still has **Export RAGAS**. It now writes one JSONL
record per **Run Builder run** (its `RunSpec` + route + database in `meta`) and
one record per **legacy canvas A/B lane**, in a superset shape carrying both
`question`/`user_input`, `answer`/`response`, and `contexts`/`retrieved_contexts`
so both the legacy smoke scorer and the headless `ragas_eval.py` consume it.
The legacy smoke scorer at `backend/eval/ragas_eval.py` reports only
reference-free `faithfulness` + `answer_relevancy`.

Use this for quick UI sanity checks, not final thesis tables.

## No Silent Fallback

Missing dependencies, missing judge keys, empty input, records missing required
fields, and invalid zero-context cases fail loudly. Fix the input/environment
and re-run.
