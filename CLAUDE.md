# CLAUDE.md

> **Interpretation, not intent.** This file is agents' claims about how this project should
> work, written over months; being written here is not the user's approval of it. Intent — what
> was supposed to be built — lives only in the user's own typed turns
> (`docs/canon/raw/user_turns*`). State — what exists — lives in the git history and the code,
> and is evidence of drift from intent, never justification for it.
> `docs/canon/CANON_AUDIT.md` checks 117 prescriptive claims across the repo's instruction
> surfaces against the record — 65 grounded in a user quote, 17 agent-origin, 11 contradicting
> the record, 22 stale, 2 since fixed — of which 20 come from this file. **Those figures are a
> snapshot of 2026-08-03, not a live count**: they include claims already corrected, among them
> eight of the audit's own ten worst. Read them as where to look, never as the state of the repo.
> That audit is interpretation too, and unreviewed: one more opinion, not a ruling. Both files are
> listed `unreviewed` in `docs/canon/REVIEW_REGISTER.md`, with the rest of the pile. Check a claim
> against intent before acting on it.

## Repo layout

- **`v3/`** — the work: a lean HERB evaluation harness (three arms — artefact /
  lucene / vector — scored with RAGAS). Self-contained. Design
  reference: `v3/README.md`. Every hard-coded constant and tunable in the tree,
  with where its value came from, is inventoried in `v3/CONSTANTS.md`; run
  results live in `v3/output/`, described by `v3/output/DATA_README.md`.
- **`docs/ENVIRONMENT.md`** — the two machines: paths, python, the Neo4j start
  recipe, graphify, NIM, the headless claude CLI, where the state-transfer docs
  sit. Machine facts belong here, never in an agent's memory.
- **`docs/canon/`** — the committed record: what the user specified, how the system was
  built, and where the repo's own claims diverge from either. Regenerate the underlying
  corpus with `tools/canon_extract.py`.
- **`CLAUDE.md`, `README.md`** — this repo's working instructions, written by agents.
  The gitignored state docs under `docs/state/` hold the per-session detail.

## Session entry point — read this first

1. **`docs/canon/raw/user_turns_all.md`** — the user's own 1,304 typed turns,
   2026-05-14 → 2026-08-13, and the `.jsonl` twin holds the same 1,304. The only
   evidence of what he asked for. Any claim about his intent cites a turn
   (`turns:L<n>`); no turn, no claim. **Line numbers drift**: the `.md` is a
   chronological rendering, so every union moves the lines after its earliest new
   turn, and citations written against older renderings now sit tens of lines low.
   Find a citation by its quoted words, not by its number.
2. **`docs/canon/CONTRADICTION_MAP.md`** — where his rulings and the system disagree.
   Each collision is layered, cited, and carries what fixing it takes: an engine
   change, a graph rebuild, a doc correction, or a ruling only he can give.
3. **The rest of `docs/canon/`** — `USER_CANON.md`, `DESIGN_HISTORY.md`,
   `CANON_AUDIT.md`, `OPEN_DECISIONS.md`, the git and desktop-doc records, the review
   apparatus. Reference material, opened when a specific claim is in dispute. Not
   required reading.

Working notes sit beside that: `docs/state/` (gitignored, machine-local, newest first).
Each is dated and describes its own moment.

**Trust ordering:** his words outrank every doc, memory entry and agent output. Where a
doc conflicts with the record, the record wins and the conflict goes to him as a
question — never resolved silently.

## Codebase navigation graph (graphify)

A graphify navigation graph for the `v3/` code — a search tool.

- **Graph — `graphify-out/graph.json`:** the v3 source tree, minus the benchmark
  dataset (`v3/data`) and the run outputs (`v3/output`). Code only — no docs.

How to use it:

- **Answering questions about the code:** query the graph FIRST, before grepping —
  `graphify query "<question>"`, `graphify explain "<node>"`, `graphify path "A" "B"`.
- **Rebuilding:** run `python refresh_graph.py` (repo root) when the code has moved,
  at the end of a work burst. It reads the AST — seconds, no model calls. It is the
  ONLY rebuild path; never run `graphify --update`, which rescopes the graph to the
  whole repo.

Details: `graphify-out/REFRESH.md`.

## Hard rules

- **An agent's own output is not canon:** producing a document, a report or a run does
  not make its contents decided. A design claim is attributed to the user only when a
  turn in `docs/canon/raw/user_turns_all.md` carries the quote, cited by line;
  otherwise it is a proposal, and says so.
- **A correction lands in the file, in the same turn.** When the user corrects
  something, the artefact it affects is updated before the reply — never acknowledged in
  conversation and left for later, where it washes away with the context.
- **So does a ruling, and the record includes his own words.** Anything he decides,
  reverses, or rules out is written where that thing lives before the reply goes out —
  and `docs/canon/raw/user_turns*` is extended so it carries the turn itself, not just an
  agent's paraphrase of it. **Check the corpus's last timestamp before citing it as the
  record.** A corpus that stops before today cannot be "the only evidence of what he
  asked for", and a ruling that exists only in an interpretation doc has no source behind
  it. The canon-mining order (08-02) exists because agents built on their own claims
  instead of his; a record that stops being extended recreates exactly that.
- **The corpus is extended by union, never replaced.** `tools/canon_extract.py` reads
  Claude Code transcripts, and Claude Code deletes old ones: a re-run on 2026-08-05
  gained 106 turns and *lost* one whose session file no longer exists. The committed
  corpus is the only surviving copy of anything whose transcript has aged out, so a fresh
  extraction is unioned into it and every dropped turn is accounted for before the file
  is written. Overwriting it destroys evidence that cannot be re-derived.
- **He rules, you propose.** Nothing is marked settled, no file is rewritten, no `v3/`
  code is touched and nothing is deleted without him saying so. Where the contradiction
  map says a fix needs his ruling, ask — one question, when the work reaches it.
- **Design before build:** no pipeline code until the relevant stage's design is
  explicitly signed off by the user. Present decided-vs-open, get the sign-off.
- **Gold-blindness — whoever designs retrieval never sees the questions or the
  gold.** *"you should not have the questions/gold available to you, there is 0%
  good that can come out of taht"* / *"can we make sure 'you' never see them?
  that you only get the variable/pointer to it?"* (08-02,
  `docs/canon/raw/user_turns_all.md`:4253, :4257). retrieval-scientist,
  maths-algorithmist and v3-coder do not open `v3/data/questions.jsonl` or any
  run's `arm_outputs.jsonl` (question text and retrieved contexts); they specify
  runs by pointer and read results from `eval_results.jsonl` — per-question
  metric values keyed by question id and type — plus the manifests. Recall is
  read from those records, never recomputed against gold. results-analyst and
  eval-statistician read everything: reporting is their job and they design
  nothing.
- **You report the statistics; you do not interpret them.** *"framing? just the
  fucking stats, YOU DONTY INTERPRET THE RESULTS"* (08-05). A measured quantity is
  reported as measured, with the conditions it was measured under and what it may be
  compared against. Choosing which number leads, which of two descriptions of one
  measurement is the better story, or what a result means for the work is his, and it
  is never offered to him as a menu — presenting a reading as a decision he must make
  is the same act as making it. Where two figures describe one measurement, both are
  recorded and neither is promoted.
- **Talk to the user in plain spoken English, short answers** — no jargon walls, no
  spec-sheet dumps. Verify claims against the real system/data before asserting.
- **Heed the user's intent — never "correct" it with stale context.** When the user
  names something they want, it's the spec; build to it. Don't use older notes to
  argue a current requirement away. Surface a genuine conflict as a question, not a
  correction.
- **Docs track reality:** when a decision closes, update the design doc + memory in
  the same pass, by removal of dead content, not banners. Dated state docs
  are frozen — they describe that moment.
- **Every constant in `v3/` is a row in `v3/CONSTANTS.md`:** `check_constants.py`
  holds the table to the source, and `v3/test_constants_inventory.py` fails the
  suite on drift.
- **No historical or defensive comments:** code, docs and commit messages state only
  the present — what the code is and does now, as if written correctly the first
  time. Never narrate a past mistake, a change, or a review finding — no
  "previously/now", "no longer", "NOT because", "do not factor out", no
  review-finding labels. Remove the mistake and write the correct version plainly;
  comments feed the graph and memory, so scar tissue pollutes every future session.
- **Refresh the navigation graph when the code has moved:** run
  `python refresh_graph.py` (repo root) at the end of a work burst, covering every
  edit to `v3/` since the last one. It is the ONLY rebuild path (never
  `graphify --update`).
- **Every runnable shows life instantly and progress continuously:** the user runs
  scripts in their own terminal, and that terminal experience is the product. Print
  the banner before any heavy import (announce slow stages like the eval stack),
  `flush=True`, and drive the harness progress bars (`v3/progress.py`) for anything
  long-running. A silent terminal — or a run buried where the user can't watch it —
  is a bug, full stop.
- **Critical-review logic changes only:** after changing real logic in `v3/`, run
  `/critical-review` on the changed file(s) — in the background, one batched review
  per work burst, findings resolved until the code converges. Config flips, default
  changes, renames, comments, help text, and doc lines get no review.

## Agent roster — orchestrator routing

The main-chat Claude is the orchestrator: it talks to the user and routes every job
to a specialist agent; it does no hands-on work itself. Plain questions get direct
conversational answers — no agents, no tool calls. Agents always run in the
background — a foreground agent freezes the conversation. Prompts are scoped to the
change: a two-line change gets a two-line prompt, never a tree-wide audit unless the
user asks for one. Long runs still happen in the user's terminal: agents prepare,
the user runs. Definitions live in `.claude/agents/`. Route by task:

- **v3-coder** — any code change in `v3/`.
- **critical-reviewer** — post-change review of `v3/` code (the hard rule above).
- **code-optimizer** — performance work; profiles first, benchmarks before/after.
- **maths-algorithmist** — mathematical algorithm design and verification.
- **order-of-operations** — sequencing/data-flow correctness of pipelines and algorithms.
- **logician** — invariants, boolean/set logic, proof-or-counterexample checks.
- **retrieval-scientist** — retrieval design and experiment proposals.
- **eval-statistician** — significance, sample size, judge reliability, judge-run cost math.
- **results-analyst** — reading `v3/output/`, reporting numbers (metric validity binding).
- **graph-refresher** — `python refresh_graph.py`.

## Artefact arm — the modified v1 artefact

**Baseline means lucene and vector** — the comparison arms, and nothing else.
`artefact_v1.py` and `artefact_v1_det.py` are two configurations of the system
under test; neither is a baseline, and a measurement of either is never a
pass-bar: *"until decided upon, there is no 'baseline' artefact, a comparable
baseline are the vector and lucene arms, no?"* (08-05,
`docs/canon/raw/user_turns_all.md`:4814). **Both legs are reported and neither is
the artefact's single result** — his prompt-box answer, 08-05 11:35: *"Report both, decide
nothing"* (recovered 08-09, in `docs/canon/raw/user_turns_all.md`). No surface may name one as *the* artefact number, and every figure quoted
for one names its leg.

The system under test is the modified v1 artefact: `v3/pipelines/artefact_v1.py` and
`v3/pipelines/artefact_v1_det.py`, retrieval code written inside the v3 harness,
querying the `herb-eval` Neo4j graph (`DATABASE` defaults to `herb-eval`,
`artefact_v1.py:117`). Every artefact number the project reports comes from that pair.
The graph is the v1 build: content stripped, the semantic layer re-embedded with the
v3 embedder (`v3/reembed_herb_eval.py`), never retagged — its chunking, tag vocabulary
and baked `w_chunk` / `w_facets` / `relevance_to_file` values are fixed unless it is
rebuilt or retagged. Never query `herb`: that is the oracle-contaminated pilot
database, a different DB.

`v3/artefact/` holds the native rebuild — the user's own next generation, after the
benchmarks. Its stages and tests live there (`python -m pytest artefact/tests` from
`v3/`): `scan.py` (file catalog → sha256/file_id), `probe.py` (shape recovery, RFC
6901 pointers), `chunk.py`, `tag.py`, `derive_corpus.py` (oracle strip),
`resolver_prototype.py` (reference resolution, hash-verified), `index.py`,
`graph_store.py`, `interpreter.py`, the HERB mapping key
(`keys/Salesforce__HERB.yaml`) and the design references (`DESIGN.md`,
`MODEL_CONTRACTS.md`); `pipelines/artefact.py` is its arm entry. The design it carries:

- **The graph spine is closed canon:** `Source → File → Chunk → Tag` are the only
  nodes. Hard fields are chunk attributes. The graph is references into untouched
  raw source, never copies — never put values, inventories, or mirrors of metadata
  directories into it.
- **The model emits no numbers, ever** (tagger and interpreter). The chunk
  description is dead. Tags are per-chunk contextual phrases.
