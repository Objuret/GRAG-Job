# v3 — HERB evaluation

> **Interpretation, not intent.** This file is agents' claims about how this harness should
> work, written over months; being written here is not the user's approval of it. Intent — what
> was supposed to be built — lives only in the user's own typed turns
> (`docs/canon/raw/user_turns*`). State — what exists — lives in the git history and the code,
> and is evidence of drift from intent, never justification for it.
> `docs/canon/CANON_AUDIT.md` checks 117 prescriptive claims across the repo's instruction
> surfaces against the record — 65 grounded in a user quote, 17 agent-origin, 11 contradicting
> the record, 24 stale — of which 12 come from this file. That audit is interpretation too, and
> unreviewed: one more opinion, not a ruling. Both files are listed `unreviewed` in
> `docs/canon/REVIEW_REGISTER.md`, with the rest of the pile. Check a claim against intent
> before acting on it.

This is the eval harness for comparing the artefact against baselines on HERB.

## Goal

Run the chosen HERB questions through the arms, get an answer from each, score
those answers with RAGAS.

**Baseline means lucene and vector** — the comparison arms:
- **lucene** — BM25 baseline. Its own index over the corpus.
- **vector** — dense / naive-RAG baseline. Its own index over the corpus.
- **hybrid** — a third comparison arm, late fusion of those two (`pipelines/hybrid.py`).

The system under test is the modified v1 artefact, querying the `herb-eval` graph:
`pipelines/artefact_v1.py` plans with a model, `pipelines/artefact_v1_det.py` plans
deterministically. They are two configurations of it, not baselines, and both are
reported — neither is the artefact's single result, and every figure names its leg. The
ruling and what it forbids are in `CLAUDE.md` §"Artefact arm", the numbers under it in
`output/DATA_README.md`.

Every arm answers with the **same generator** (built once in the orchestrator and
injected), so any difference is retrieval, not the LLM. Beyond that generator and
the **corpus on disk**, the arms share **nothing** — each reads, indexes and ranks
the corpus with its own code (how it does so is what the comparison measures); they
share no retrieval code with each other, and nothing with the artefact.

## Scoring with RAGAS

- **RAGAS** (`eval/ragas.py`) — the scorer. The full RAGAS metric
  menu lives in `eval/ragas_catalog.py`; every judge-free (deterministic) metric
  always runs (it costs nothing), and `SELECTED` adds the judged ones. The
  deterministic backbone is **ID-based** context precision/recall against the gold
  citations (`IDBasedContextPrecision` / `IDBasedContextRecall`, no judge); the
  judged picks are **faithfulness, answer correctness, and context recall**.
  `context_precision_llm_ref` stays commented out because it is ~k judge calls per
  question and turns the slow lane into the whole run. Faithfulness needs no
  reference, so it transfers to a no-gold set later; the other judged metrics lean
  on the gold answer / citations.

RAGAS emits raw per-question records (`EvalResult`, tidy long format) — nothing
pre-aggregated — so paired tests, CIs, per-type splits and judge calibration are
all possible downstream. Each run writes a `RunManifest` (arm, generator model,
top-k, questions file, n, timestamp, build stats, and — for a Neo4j-querying
arm — the graph identity: database name plus the graph build's
`removed_tags_sha256`, timestamp and parent `source_database` when
`output/graph_build/<db>/` records one; a resumed run whose answers span two
builds of the database records them all under `mixed_builds`) and an
`EvalManifest` (scorer,
judge model, backend, reasoning effort, aggregate judge usage including
reasoning tokens, source run, arm, timestamp) for reproducibility.
GPT judge runs use the signed-in Codex CLI (the same subscription-authenticated
pattern as the Claude judge), not `OPENAI_API_KEY`. Gemini judge runs use the
signed-in Gemini CLI, not an API key. Their manifests contain provider-reported
input, cached-input, output, and reasoning-token usage, aggregate request time,
and eval wall time.

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
- `char_budget.py` — fill-to-budget consumption of a ranked context stream
  (`run.py --char-budget N`): whole retrieval units — a baseline's artifact, an
  artefact leg's chunk — in rank order, the crossing unit cut mid-text so the
  context text totals exactly N chars, the cut recorded per question in
  `meta.char_budget` and the budget in the run manifest; shared harness
  plumbing, not retrieval code. Budget runs' folders carry `cb<N>`.
- `pipelines/` — `artefact_v1.py` and `artefact_v1_det.py` (the arm under test and its
  interpreter-free leg), `lucene.py`, `vector.py`, `hybrid.py`, and `artefact.py` (the
  native rebuild's arm entry).
- `eval/` — `ragas.py` and `ragas_catalog.py` (the full RAGAS metric menu:
  deterministic metrics always run, judged ones via the `SELECTED` toggle).
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
- `CONSTANTS.md` — every hard-coded constant and tunable in this tree, with where its
  value came from. `check_constants.py` holds the table to the source and
  `test_constants_inventory.py` fails the suite on drift. A new constant is a new row.
- `output/DATA_README.md` — the run record: what every run in `output/` is, what it
  scores, and what it may be used to claim. Every number recomputed from the folders.
  No number is quoted anywhere else.

## Decided

- RAGAS is the only scorer, and nothing it reports is leaderboard-comparable against
  HERB's published figures — accepted, not a gap to close.
- One shared generator across every arm, and one k. **k is shared; the retrieval budget
  it buys is not** — an artefact context is a graph chunk carrying ~10 artifact ids, a
  baseline context is one artifact carrying one, so at a common k the artefact arms hold
  ~10× the ids and the scoring ceiling differs too. `output/DATA_README.md` carries that
  rule and governs every cross-arm number under it.
- **Generation and scoring are separate phases** (`questions` / `evals` / `full`), so
  iterating a scorer never re-runs the generator. The `questions` record is **oracle-free**;
  `evals` re-joins `type` + `ground_truth` + `citations` by id from `data/questions.jsonl`.
- **RAGAS selection**: deterministic (judge-free) metrics always run because they cost
  nothing; the judged ones are opted in via `SELECTED` in `eval/ragas_catalog.py`.
  Deterministic context precision/recall = the **ID-based** variants against the gold citations.
  Computed with the **RAGAS library** (validated/citable); the judged metrics use the default haiku judge (`claude-haiku-4-5`).
- **Per-question telemetry is split**: `ArmOutput.generator` (the shared answer-writer,
  identical across arms) vs `ArmOutput.retrieval` (the arm's OWN retrieval-time model cost —
  vector's query embed; zero for lucene).
- **Provenance** is two manifests — `RunManifest` (generation side) + `EvalManifest`
  (scoring side); no seed, no git-sha.
- Oracle read in place from raw; pipelines blind to it.
- **One LLM — generator, one judge by default**: `qwen/qwen3.5-397b-a17b` on NVIDIA
  NIM is still the shared generator injected into all three arms (so the only variable
  is retrieval). The judge defaults to haiku (`claude-haiku-4-5`) through the headless
  Claude CLI, but `--judge` can swap in another Claude, GPT-5.4 mini, or Gemini model
  for cross-checks; the judge backend and aggregate usage are recorded in the eval
  manifest. Multilingual, so HERB now and the deferred Swedish
  Bonnier set run on the same generator, no swap. Not GPT-4o, so HERB's published
  baselines get re-run, not cited.
- **Generation contract — a thin, fixed RAG pipe.** It sends the model one fixed system
  instruction — *"Answer the question using only the provided documents. Be concise."* —
  then the question exactly as posed in the set plus the arm's retrieved passages as a
  labelled user turn, and takes back a structured `{answer}`. The instruction is generic
  grounding, not retrieval engineering, and is held byte-identical across all three arms,
  so the only variable remains the retrieval. Any advanced handling of thin or empty
  context is an individual arm's own concern, never the shared harness.
- **lucene arm built**: bm25s `method="lucene"` — the Lucene / Elasticsearch BM25
  variant (bm25s's default; k1=0.9 / b=0.4 are the BEIR reference values). It reproduces
  Lucene's *scoring* exactly; the analysis (EN stopwords + Snowball/Porter2 stem) is
  Lucene-*like*, not Lucene's Java analyzer. One document per artifact; artifacts-only
  index. Justified: all 17,087 gold citations resolve to an artifact `id`, so context_ids
  share the citation id space and metadata would only add never-relevant distractors.
  Returns `ArmOutput`; prepare attaches `BuildStats` (model = ModelUsage(), no model at build).
- **vector arm built**: embedder `nvidia/llama-nemotron-embed-1b-v2` on NIM
  (multilingual incl. Swedish, English-strong, 8192-token context). It reads the corpus with its
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

- **Orchestrator split** into the three `questions` / `evals` / `full` modes, with a
  per-run-folder run identity (so a gold-100 run and a full run don't clobber).
- **A matched-character-budget comparison at n=100.** The only one that exists is the
  `__b72000` family on 10smoke (n=10), and it binds the artefact arm alone. The 500-id
  runs match ids exactly and characters not at all.
- **Which set to run** — gold-100 (built; seeded stratified draw) vs the full 815 + 699.
- **Judge calibration** subset size (to validate the judged RAGAS metrics).

## One caveat worth remembering

Answer-level scoring measures the whole pipeline, not retrieval alone — a strong
generator can mask retrieval quality. The deterministic context precision/recall
is what keeps an endpoint pointed directly at retrieval, which is the artefact's
actual claim.
