# v3 — HERB evaluation

This is the eval harness for comparing the artefact against baselines on HERB.

## Goal

Run the chosen HERB questions through three arms, get an answer from each, score
those answers two ways.

Three arms:
- **artifact** — the v2 graph (interpreter → facet retrieval → answer). The system under test.
- **lucene** — BM25 baseline. Its own index over the corpus.
- **vector** — dense / naive-RAG baseline. Its own index over the corpus.

All three answer with the **same generator** (built once in the orchestrator and
injected), so any difference is retrieval, not the LLM. The baselines share
nothing with the artefact.

## Two scorers, on purpose

- **HERB** (`eval/herb.py`) — the dataset's own scoring: per-type set-F1
  (person/url/pr/company), a 0–100 judge for content, abstention for
  unanswerables. Exact, leaderboard-comparable. **The anchor.**
- **RAGAS** (`eval/ragas.py`) — faithfulness + answer-relevance (judged), and
  context precision/recall computed **deterministically against the gold
  citations** (no judge). The multidimensional lens, and the part that transfers
  to a no-gold set later.

Both emit raw per-question records (`MetricScore`, tidy long format) — nothing
pre-aggregated — so paired tests, CIs, per-type splits and judge calibration are
all possible downstream. Each run also writes a `RunManifest` (models, top-k,
seed, git sha) for reproducibility.

## Data split (the quarantine)

- `data/corpus/` — oracle stripped out. **Pipelines see only this**, and only via
  a truth-free prompt.
- `data/raw/` — full HERB; the ~1514 questions + ground_truth + citations live
  inside the product files. **Evaluators read truth from here, in place.**
- `metadata/` (employee / customer / team directories) stays on both sides — it's
  legitimate retrieval data, not oracle.

## Run flow

```
orchestrator.run(pipeline, evaluator, ids, config)
  load questions (truth from raw) + open corpus + build shared generator
  → run_one_pipeline: prepare arm once, then per question:
        truth-free prompt → arm.answer_one_question → PipelineOutput(answer, contexts, ids)
  → run_one_evaluator: score_outputs → Report[ MetricScore… ]
  → save_run → output/        (smoke.py = same path, few questions → output/smoke/)
```

## Files

- `contract.py` — the shapes + the two interfaces everything imports.
- `pipelines/` — `artifact.py`, `lucene.py`, `vector.py`.
- `eval/` — `herb.py`, `ragas.py`.
- `orchestrator.py` — wires one arm + one scorer; owns the shared generator.
- `smoke.py` — tiny wiring check.
- `data/` — `corpus/`, `raw/`.  `output/` — results (`smoke/` for checks).

## Decided

- Both scorers (HERB anchor + RAGAS lens). Three arms, shared generator, shared top-k.
- Deterministic citation-based context precision/recall (not the judged variants).
- Oracle read in place from raw; pipelines blind to it.

## Still open

- **Generator** model (one, shared).
- **Judge** model(s) — if it's not GPT-4o, the HERB baselines must be **re-run**, not cited from the paper.
- **top-k** budget.
- **Question set** — gold-100 vs the full 815 + 699.
- **Judge calibration** subset size (to validate the judged RAGAS metrics).

## One caveat worth remembering

Answer-level scoring measures the whole pipeline, not retrieval alone — a strong
generator can mask retrieval quality. The deterministic context precision/recall
(and, if wanted, HERB's oracle setting) is what keeps an endpoint pointed
directly at retrieval, which is the artefact's actual claim.
