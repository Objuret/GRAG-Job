# Offline RAGAS evaluation

The workbench is browser-only and the architecture has no server, so RAGAS
(a Python library) runs **offline** on exported run data — it is not wired
into the app.

## Flow

1. In the workbench, run prompts (Usage lane). Each run is recorded in the
   **History** tab with both lanes' answers and retrieved chunks.
2. History → **Export RAGAS** → downloads `ragas_runs_<ts>.jsonl`, one record
   per (run, lane): `question`, `answer`, `contexts` (real retrieved chunk
   text — no fabricated/ground-truth fields).
3. Score it offline:

   ```bash
   pip install -r backend/eval/requirements-eval.txt
   export OPENAI_API_KEY=...          # RAGAS default judge LLM + embeddings
   python -m backend.eval.ragas_eval ragas_runs_<ts>.jsonl
   ```

## What it reports

Two reference-free metrics (no ground truth is exported):

- **faithfulness** — is the answer grounded in the retrieved contexts?
- **answer_relevancy** — does the answer address the question?

Output is per-lane means plus the **A − B** delta, i.e. HERB tag-grounded
retrieval (Lane A) vs the relevance-only baseline (Lane B) — the thesis
comparison.

## No silent fallback

Missing dependency, missing `OPENAI_API_KEY`, empty input, a record missing
required fields, or a run with zero retrieved contexts is a **loud error**,
not a skipped/zero score. Fix the input or environment and re-run.
