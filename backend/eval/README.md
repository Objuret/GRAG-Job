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

## Thesis Harness

Preferred path for thesis results:

1. Build a gold set from the full `herb` database:

   ```powershell
   cd backend
   python -m evaluation.build_gold_set --database herb --count 100
   ```

2. Run graph and baseline exports from the repo root:

   ```powershell
   npm --workspace frontend run ragas:export -- --mode graph --questions frontend/scripts/ragas-questions.herb-gold100.jsonl --out backend/evaluation/graph.jsonl --fresh
   npm --workspace frontend run ragas:export -- --mode baseline --questions frontend/scripts/ragas-questions.herb-gold100.jsonl --out backend/evaluation/baseline.jsonl --fresh
   ```

3. Score each JSONL:

   ```powershell
   cd backend
   pip install -r requirements-eval.txt
   python -m evaluation.ragas_eval --input evaluation/graph.jsonl --metrics faithfulness,context_recall,context_precision --report evaluation/graph.report.json
   python -m evaluation.ragas_eval --input evaluation/baseline.jsonl --metrics faithfulness,context_recall,context_precision --report evaluation/baseline.report.json
   ```

The headless exporter writes `user_input`, `retrieved_contexts`, `response`,
`reference`, and a `meta` block with mode, timing, chunk ids, file ids,
grounding, gate, controls, warnings, and errors.

## UI Smoke Export

The workbench History tab still has **Export RAGAS**. It writes one JSONL
record per `(run, lane)` with `question`, `answer`, and `contexts`. The legacy
smoke scorer remains at `backend/eval/ragas_eval.py` and reports only
reference-free `faithfulness` + `answer_relevancy` per lane.

Use this for quick UI sanity checks, not final thesis tables.

## No Silent Fallback

Missing dependencies, missing judge keys, empty input, records missing required
fields, and invalid zero-context cases fail loudly. Fix the input/environment
and re-run.
