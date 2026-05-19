# Plans — Next Steps

> **State (2026-05-18):** the stack below is **code in the working tree,
> uncommitted**. Its graph prerequisites (`materialize`, `embed-tags`) are
> **verified done on the live `herb` graph** (5843 chunks gated, 25,896 `:Tag`
> embedded, all indexes ONLINE — see [`status.md`](status.md)). The
> `pilot_format_smoke/run.json` ledger is stale; trust the graph.

## Coded, graph layer verified on `herb`

1. Browser-direct Neo4j read (`neo4j-driver`) — [`services/neo4j.ts`](../../frontend/src/services/neo4j.ts).
2. Browser-direct two-pass Anthropic interpretation — [`services/interpreter.ts`](../../frontend/src/services/interpreter.ts).
3. Retrieval scoring in Cypher (weighted overlap) — [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts), grounded by [`services/embeddings.ts`](../../frontend/src/services/embeddings.ts). Grounding mandatory; no exact-name fallback.
4. Answer call per `answer_job` — [`services/answer.ts`](../../frontend/src/services/answer.ts).
5. Replace demo state — live calls drive the lanes.
6. Field-name pass — HERB names (`facet`, `w_chunk`, `w_facet`, `relevance_to_file`) throughout.
7. Hard-gate + lexical recall — Pass-1 `gate` in [`services/interpreter.ts`](../../frontend/src/services/interpreter.ts); deterministic pre-tag gate on materialized `:Chunk` fields, fail-loud validation, gated `chunk_fulltext` lexical path in [`services/retrieval.ts`](../../frontend/src/services/retrieval.ts); backend `python -m tagging materialize` (see [`../graph_schema.md`](../graph_schema.md)). Hard fields + `chunk_fulltext` confirmed present on `herb`.

## Required to call this shippable

- **Commit the feature.** Currently working-tree only — one disruption and it is gone.
- **Resolve `frontend/public/models/` tracking.** Untracked and not gitignored; with `allowRemoteModels=false` a fresh checkout has no model and grounding hard-fails. Commit the quantized ONNX, or gitignore + document a fetch step.
- **Click through the browser prompt → answer loop on `herb`** and record the actual result in [`status.md`](status.md) (only the graph data layer was verified, not a full UI run).

## Known quality issues (acknowledged, not fixed)

- **`min_sim` is near-meaningless.** e5-small cosine on this corpus is compressed (~0.8 mean to random tags); default floor 0.78 barely filters noise — grounding leans entirely on top-k.
- **Wrong-retrieval, not zero-retrieval, is now the recall gap.** Tag scoring returning zero chunks under the gate now falls back to the gated full-text path instead of returning nothing (warned), closing the zero-retrieval hole the gold run exposed. The remaining gap is relevant chunks not being ranked in (grounding/precision) — see the e5 `min_sim` issue above.

## RAGAS evaluation

The eval target is the **real browser pipeline**, not a Python re-implementation
or the legacy clustering layer. Producer/consumer split:

- **Built — headless export harness.** [`frontend/scripts/ragas-export.ts`](../../frontend/scripts/ragas-export.ts)
  drives the same path as `App.jsx:runPipeline` (main lane only):
  `interpretPrompt` → `retrieveChunks` → `generateAnswer` against the live
  `herb` graph + Anthropic, in Node via `tsx`. It repoints transformers.js at
  the on-disk `frontend/public/models` (fails loud if the e5 onnx is not
  assembled) and writes one JSONL row per question with `user_input`,
  `retrieved_contexts`, `response`, plus a `meta` block. Run:
  `npm --workspace frontend run ragas:export -- --questions <file> --out <file>`.
  Config comes from the app's `VITE_*` env (frontend `.env.local`) or plain
  env. Starter questions: `frontend/scripts/ragas-questions.example.jsonl`.
  Verified end-to-end against the live `herb` graph (grounding, hard gate, and
  chunk retrieval all exercised; the Windows/Node transformers.js model-path
  question is resolved — the e5 onnx loads from disk).
- **Built — Python RAGAS runner.** [`backend/evaluation/ragas_eval.py`](../../backend/evaluation/ragas_eval.py)
  (`python -m evaluation.ragas_eval`) consumes the harness JSONL only — no
  Neo4j, no pipeline, no legacy clustering. Reference-free. Judge LLM is
  Anthropic (key resolved from env / backend `.env` / frontend `.env.local`).
  `faithfulness` is the default and works with no extra deps. `answer_relevancy`
  is opt-in: this venv is Python 3.14 with no torch wheels, so a local
  embeddings model is intentionally not a dependency — it needs `OPENAI_API_KEY`
  (OpenAI embeddings) or a torch-capable env. Deps: `backend/requirements-eval.txt`.
- **Built — curated HERB question set.** [`frontend/scripts/ragas-questions.herb.jsonl`](../../frontend/scripts/ragas-questions.herb.jsonl)
  (~30 questions). Grounded in the live `herb` graph: real products, sections,
  channels, employee_ids, years, and per-facet top tags were verified to hit
  data before authoring (e.g. product `CollaborationForce`, not the starter's
  guessed `CollaborateForce`). `id` prefixes encode the retrieval path each
  question exercises (`tag_`, `gate_prod_`, `gate_prodsec_`, `gate_sec_`,
  `gate_year_`, `gate_chan_`, `gate_eid_`, `facet_`, `lex_`, `ctrl_`) so RAGAS
  results can be sliced by path. The `ragas-questions.example.jsonl` starter
  stays as the minimal smoke set. Reference-free.
- **Built — ground-truth reference evaluation.** Authoritative, not LLM-guessed:
  [`backend/evaluation/build_gold_set.py`](../../backend/evaluation/build_gold_set.py)
  extracts HERB's own `qa_record` question/`ground_truth` pairs (greedy
  distinct question-type selection across products) into
  [`frontend/scripts/ragas-questions.herb-gold.jsonl`](../../frontend/scripts/ragas-questions.herb-gold.jsonl).
  The harness now passes a `reference` field through; `retrieval.ts` gained an
  eval-only `excludeSections` option (default none — app byte-identical) so the
  reference run can `--exclude-sections answerable_questions,unanswerable_questions`
  and force the pipeline to answer from real evidence, not the gold record.
  `ragas_eval.py` adds `context_recall` + `context_precision` (LLM-only,
  reference-based) and `answer_correctness` (opt-in, needs embeddings);
  zero-context rows are kept so `context_recall` scores them ~0 — the recall
  hole reference-free faithfulness hid. `build_gold_set --count N` scales the
  set with a product round-robin (every distinct question type, then balanced
  product instances): a 100-pair set is 88 distinct stems over 30 products.
- **Result (n=99, gold, QA excluded, judge=sonnet, recall fix live):**
  faithfulness **0.86**, context_recall **0.33**, context_precision **0.087**.
  The n=15 set overstated recall (0.41) — small-sample instability; report
  n≈100. The system is faithful but retrieval is the bottleneck: recall is
  bimodal (54/99 = 0, 35/99 ≥ 0.5), split by question TYPE — "changes
  suggested by [role]" r≈0.69, but entity/aggregate lookup ("find employee
  IDs of…", "find all unresolved issues…") r≈0–0.2. Topical/semantic
  retrieval cannot do exact-fact lookup over scattered structured metadata;
  the next lever is grounding/ranking precision, not more recall.
- **Not built yet (optional):** an embeddings backend if `answer_relevancy` /
  `answer_correctness` are wanted (Python 3.14 has no torch wheels — needs
  `OPENAI_API_KEY`).

## Optional

- **Persistence.** Save canvas/module state to `localStorage`, or skip — the app is local-only.
