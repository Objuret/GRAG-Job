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

| Arm | Default caps | RAGAS evidence |
|---|---|---|
| Graph (`mode=graph`) | `limit=0`, `grounding_k=0` | Full retrieved chunk texts |
| Baseline (`mode=baseline`) | `limit=0` | Full retrieved chunk texts |
| SQL agent (`mode=sql_agent`) | `max_tool_calls=0`, `max_rows_per_query=0`, `max_cell_chars=0` | All SQL rows the agent saw (flattened), same truncation rules as the LLM tool output |

**0 semantics:** omitting a cap removes it. SQL tool-call budget `0` still has
a hard **200-iteration** sanity ceiling in `backend/baselines/sql_agent.py`.
Graph grounding `0` still queries the vector index top-**1000** neighbors per
prompt tag before `minSim` filtering.

Headless **baseline** export scrubs chunk text only when building the answer
API request (malformed HERB bytes); retrieval and RAGAS `retrieved_contexts`
are unchanged.

Set **`prompt_mode: context`** on graph/baseline RAG arms (never `raw` for eval).

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
   npm --workspace frontend run ragas:export -- --mode baseline --questions frontend/scripts/ragas-questions.herb-gold100.jsonl --out backend/evaluation/baseline.jsonl --fresh
   npm --workspace frontend run ragas:export -- --mode sql_agent --questions frontend/scripts/ragas-questions.herb-gold100.jsonl --out backend/evaluation/sql_agent.jsonl --fresh --model deepseek-chat
   ```

   Or export RunSpec cards from the workbench (see below) and pass
   `--config path/to/run.ragas.json`.

3. Score each JSONL:

   ```powershell
   cd backend
   pip install -r requirements-eval.txt
   python -m evaluation.ragas_eval --input evaluation/graph.jsonl --metrics faithfulness,context_recall,context_precision --report evaluation/graph.report.json
   python -m evaluation.ragas_eval --input evaluation/baseline.jsonl --metrics faithfulness,context_recall,context_precision --report evaluation/baseline.report.json
   python -m evaluation.ragas_eval --input evaluation/sql_agent.jsonl --metrics faithfulness,context_recall,context_precision --report evaluation/sql_agent.report.json
   ```

The headless exporter writes `user_input`, `retrieved_contexts`, `response`,
`reference`, and a `meta` block with mode, timing, chunk ids, file ids,
grounding, gate, controls, warnings, and errors. SQL-agent rows also record
`max_tool_calls`, `max_rows_per_query`, and `max_cell_chars` in `meta`.

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
