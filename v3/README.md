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
injected), so any difference is retrieval, not the LLM. Beyond that generator and
the **corpus on disk**, the arms share **nothing** — each reads, indexes and ranks
the corpus with its own code (how it does so is what the comparison measures); they
share no retrieval code with each other, and nothing with the artefact.

## Two scorers, on purpose

- **HERB** (`eval/herb.py`) — the dataset's own scoring: per-type set-F1
  (person/url/pr/company), a 0–100 judge for content, abstention for
  unanswerables. Exact, leaderboard-comparable. **The anchor.**
- **RAGAS** (`eval/ragas.py`) — the multidimensional lens. The full RAGAS metric
  menu lives in `eval/ragas_catalog.py`; every judge-free (deterministic) metric
  always runs (it costs nothing), and `SELECTED` adds the judged ones. The
  deterministic backbone is **ID-based** context precision/recall against the gold
  citations (`IDBasedContextPrecision` / `IDBasedContextRecall`, no judge); the
  judged picks are faithfulness + **response relevancy**. RAGAS is the part that
  transfers to a no-gold set later (faithfulness + response relevancy need no reference).

Both emit raw per-question records (`EvalResult`, tidy long format) — nothing
pre-aggregated — so paired tests, CIs, per-type splits and judge calibration are
all possible downstream. Each run writes a `RunManifest` (arm, generator model,
top-k, questions file, n, timestamp, build stats) and an `EvalManifest` (scorer,
judge model, source run, arm, timestamp) for reproducibility.

## Data split (the quarantine)

- `data/corpus/` — oracle stripped out. **Pipelines see only this**, and only via
  a truth-free prompt.
- `data/raw/` — full HERB; the ~1514 questions + ground_truth + citations live
  inside the product files. **Evaluators read truth from here, in place.**
- `metadata/` (employee / customer / team directories) stays on both sides — it's
  legitimate retrieval data, not oracle.

## Run flow — two separate phases

Generation and scoring are split, so iterating a scorer never re-runs the LLM.
Three modes: `questions`, `evals`, and `full` (the two back to back).

**`questions`** — one arm answers the chosen questions:
```
load chosen questions (truth from raw) → open corpus → build the shared generator
  → prepare the arm once (→ BuildStats), then per question:
        (id + text only) → arm.answer_one_question
            → ArmOutput(answer, contexts, context_ids, search_time_s, generator, retrieval)
  → a per-run folder: records.jsonl (one oracle-free row per question) + run_manifest.json
```
Rows append as they go (a crash keeps what finished); a hard error fails loud and stops.

**`evals`** — one scorer reads a run folder and scores it:
```
read records.jsonl → re-join truth (type, ground_truth, citations) by id from
    data/questions.jsonl → score_outputs → one EvalResult per (question × metric)
  → eval_results.jsonl + eval_manifest.json
```

The run record carries no oracle, so you can read it and see the quarantine held.
(The orchestrator currently runs a single combined path; splitting it into the
three modes is the pending step — see Still open.)

## Files

- `contract.py` — the shared shapes everything imports (QuestionWithTruth,
  ModelUsage, ArmOutput, BuildStats, EvalResult, RunManifest, EvalManifest).
- `nim.py` — the one NVIDIA NIM REST transport (generator, embedder and judge all
  POST through it); shared harness plumbing, not retrieval code.
- `pipelines/` — `artifact.py`, `lucene.py`, `vector.py`.
- `eval/` — `herb.py`, `ragas.py`, and `ragas_catalog.py` (the full RAGAS metric
  menu: deterministic metrics always run, judged ones via the `SELECTED` toggle).
- `orchestrator.py` — owns the shared generator; runs an arm through generation and
  a scorer through evaluation; writes the manifests.
- `build_questions.py` / `questions.py` / `build_question_sets.py` — HERB ships no
  question id, so `build_questions.py` mints `<product>::a|u::<index>` and writes the
  full set (`{id, question, type, ground_truth, citations}`, a/u lives only in the id)
  to `data/questions.jsonl`; `questions.py` loads it. `build_question_sets.py` writes
  the `{id, type, question}` id-set views to `output/`: full / answerable / unanswerable
  (1514 / 815 / 699) plus `question_ids.gold100.jsonl` — the **gold-100**, a balanced
  answerable subset drawn by seeded round-robin over the HERB types (equal allocation,
  ~20/type). Equal allocation keeps every type usable per-type; it does not match HERB's
  natural mix, so report per-type and don't compare the gold-100 aggregate to HERB's
  published average. Point the orchestrator's ids-file at whichever view you run.
- `smoke.py` — tiny wiring check.
- `data/` — `corpus/`, `raw/`.  `output/` — results (per-run folders; `smoke/` for checks).

## Decided

- Both scorers (HERB anchor + RAGAS lens). Three arms, one shared generator, and a top-k budget shared across arms (that it's *shared* is decided; the value itself is still open — see below).
- **Generation and scoring are separate phases** (`questions` / `evals` / `full`), so
  iterating a scorer never re-runs the generator. The `questions` record is **oracle-free**;
  `evals` re-joins `type` + `ground_truth` + `citations` by id from `data/questions.jsonl`.
- **RAGAS selection**: deterministic (judge-free) metrics always run because they cost
  nothing; the judged ones are opted in via `SELECTED` in `eval/ragas_catalog.py`.
  Deterministic context precision/recall = the **ID-based** variants against the gold citations.
- **Per-question telemetry is split**: `ArmOutput.generator` (the shared answer-writer,
  identical across arms) vs `ArmOutput.retrieval` (the arm's OWN retrieval-time model cost —
  vector's query embed; zero for lucene).
- **Provenance** is two manifests — `RunManifest` (generation side) + `EvalManifest`
  (scoring side); no seed, no git-sha.
- Oracle read in place from raw; pipelines blind to it.
- **Shared generator**: `mistralai/mistral-large-3-675b-instruct-2512` on NVIDIA NIM —
  one generator injected into all three arms, so the only variable is retrieval. It's
  multilingual, so HERB now and the deferred Swedish Bonnier set later run on the SAME
  generator with no swap.
- **lucene arm built**: bm25s `method="lucene"` — the Lucene / Elasticsearch BM25
  variant (bm25s's default; k1=0.9 / b=0.4 are the BEIR reference values). It reproduces
  Lucene's *scoring* exactly; the analysis (EN stopwords + Snowball/Porter2 stem) is
  Lucene-*like*, not Lucene's Java analyzer. One document per artifact; artifacts-only
  index. Justified: all 17,087 gold citations resolve to an artifact `id`, so context_ids
  share the citation id space and metadata would only add never-relevant distractors.
  Returns `ArmOutput`; prepare attaches `BuildStats` (model = ModelUsage(), no model at build).
- **vector arm built**: embedder `nvidia/llama-3.2-nv-embedqa-1b-v2` on NIM
  (multilingual, English-strong, 8192-token context). It reads the corpus with its
  OWN reader (no code shared with another arm) into one document per artifact,
  embedded **whole** — the 8192-token context covers every HERB artifact (longest
  ~1.5k tokens), so no truncation and no chunking (this arm's own unit choice);
  **exact brute-force cosine** (no ANN — the ~38.6k-artifact corpus is too small to
  need one). Each artifact keeps its native `id`, so `context_ids` land in the
  gold-citation id space (a property of the data, not of shared code). A deliberate
  *capable multilingual dense baseline*, NOT the English-only, 256-token `all-MiniLM`
  "textbook naive-RAG" default. Returns `ArmOutput`; `BuildStats` records the
  embedder's build-time work.
- **Question ids minted deterministically** (HERB ships no native id): `<product>::a|u::<index>`
  from (product file, array, position) — 815 answerable + 699 unanswerable = 1514, unique,
  the paired-test join key. `questions.load_questions` hydrates `QuestionWithTruth` from raw;
  the id filter is exact (an unmatched id raises).

## Still open

- **RAGAS computation** — the `ragas` library (every metric for ~free, heavier, more
  opaque) vs hand-implemented (transparent; the deterministic ones are a few lines each,
  the judged ones need prompts). Decides how legible the eval is.
- **Orchestrator split** into the three `questions` / `evals` / `full` modes, with a
  per-run-folder run identity (so a gold-100 run and a full run don't clobber).
- **Generation contract** — the generator's answer prompt, its abstention string, and
  the empty-context behavior — pending sign-off.
- **Judge** model(s) — if it's not GPT-4o, the HERB baselines must be **re-run**, not cited from the paper.
- **top-k** budget.
- **Which set to run** — gold-100 (built; seeded stratified draw) vs the full 815 + 699.
- **Judge calibration** subset size (to validate the judged RAGAS metrics).

## One caveat worth remembering

Answer-level scoring measures the whole pipeline, not retrieval alone — a strong
generator can mask retrieval quality. The deterministic context precision/recall
(and, if wanted, HERB's oracle setting) is what keeps an endpoint pointed
directly at retrieval, which is the artefact's actual claim.
