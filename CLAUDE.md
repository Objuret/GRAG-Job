# CLAUDE.md

## Repo layout

- **`v3/`** — the work: a lean HERB evaluation harness (three arms — artefact /
  lucene / vector — scored with RAGAS). Self-contained. Design
  reference: `v3/README.md`.
- Root canon (`CLAUDE.md`, `README.md`) + the gitignored state/handoff docs under
  `docs/` complete the picture.

## Session entry point — read this first

Work continues across sessions via **state-transfer documents in `docs/state/`**.
These are gitignored (present in the working tree, never committed), so a fresh
clone starts empty — they live on the machine where the work happened.

1. **Current entry state docs (read before doing anything else):**
   - **V1 curve walk, facets verdict, cluster-K (current):**
     `docs/state/2026-07-22-v1-curve-walk-facets-and-cluster-k.md` — the user's
     cluster-K concept, the measured facet/value-knee/curve-walk results, the open
     design question (walk and best-fit judged not mutually helping; global-frontier
     re-reading awaiting the user's verdict), and the queued decisions (stated scope
     vs K, flag rename). **Read this first for any artefact_v1 retrieval work.**
     Its predecessor `docs/state/2026-07-20-v1-query-relative-areas.md` holds the
     pre-walk definitions and probes.
   - Two older live threads retained for their narrower build/eval context:
   - **Artefact tag-facet design:** `docs/state/2026-06-25-artefact-facets-guide-link-and-content-profile.md`
     — complete reconciled facet design (content-profile + guide-link); facets = weight+direction
     measured by geometry (sibling comparison), one edge per tag carrying the full facet vector;
     supersedes `artefact-tag-facets-vs-routing.md` (same date, earlier) and DESIGN.md §13–14 /
     MODEL_CONTRACTS §1. **Do not re-derive from DESIGN.md/MODEL_CONTRACTS.md — those are stale.**
   - **Eval harness:** `docs/state/2026-06-25-v3-vector-eval-k-vs-topk-ragas-ops.md` — vector
     arm + RAGAS-only eval: k-vs-top-k, the judged metrics (faithfulness, answer_correctness,
     context_recall_llm), k=50 / gold-100, structured-output
     generator, NIM-throttle run ops.
2. **State doc folder (dated; newest = entry point):** `docs/state/`
3. **Canon design reference (in-repo):** `v3/README.md`.
4. **Persistent memory (auto-loads in Claude Code; other agents read it manually):**
   `C:\Users\Djuret\.claude\projects\a--exjobbet-repo\memory\MEMORY.md`
5. **Frozen historical handoffs (do not edit):** `docs/handoff/`

When a newer state doc supersedes the entry point, update line 1 here in the same pass.

## Codebase navigation graph (graphify)

A graphify navigation graph for the codebase — a search tool.

- **Graph — `graphify-out/graph.json`:** covers v3/ + the in-repo (gitignored)
  state/handoff docs in `docs/state` + `docs/handoff` + root canon (CLAUDE.md,
  README.md), wired by bridge edges.

How to use it:

- **Answering questions about the code:** query the graph FIRST, before grepping —
  `graphify query "<question>"`, `graphify explain "<node>"`, `graphify path "A" "B"`.
- **After changing files:** run `python refresh_graph.py` (repo root) to rebuild the
  graph. It is the ONLY rebuild path; never run `graphify --update` (drops the
  external-doc bridges). If it prints a worklist, a doc needs model extraction:
  process `graphify-out/.refresh_worklist.json` — extract each listed doc, bridging
  into the existing concepts in `graphify-out/.concept_index.txt`; write committed
  repo docs to graphify's semantic cache and the gitignored state/handoff docs as
  sidecar fragments in `graphify-out/.external_cache/`
  (`{source_file,hash,nodes,edges}`) — then re-run `python refresh_graph.py`.

Details: `graphify-out/REFRESH.md`.

## Hard rules

- **Design before build:** no pipeline code until the relevant stage's design is
  explicitly signed off by the user. Present decided-vs-open, get the sign-off.
- **Talk to the user in plain spoken English, short answers** — no jargon walls, no
  spec-sheet dumps. Verify claims against the real system/data before asserting.
- **Heed the user's intent — never "correct" it with stale context.** When the user
  names something they want, it's the spec; build to it. Don't use older notes to
  argue a current requirement away. Surface a genuine conflict as a question, not a
  correction.
- **Docs track reality:** when a decision closes, update the design doc + memory in
  the same pass, by removal of dead content, not banners. Dated state/handoff docs
  are frozen — they describe that moment.
- **No historical or defensive comments:** code, docs and commit messages state only
  the present — what the code is and does now, as if written correctly the first
  time. Never narrate a past mistake, a change, or a review finding — no
  "previously/now", "no longer", "NOT because", "do not factor out", no
  review-finding labels. Remove the mistake and write the correct version plainly;
  comments feed the graph and memory, so scar tissue pollutes every future session.
- **Always refresh the navigation graph after changing files:** after any edit to
  `v3/`, root canon, or the external state/handoff docs, run
  `python refresh_graph.py` (repo root). It is the ONLY rebuild path (never
  `graphify --update`). If it prints a worklist, process it before the change is done
  (full procedure above).
- **Every runnable shows life instantly and progress continuously:** the user runs
  scripts in their own terminal, and that terminal experience is the product. Print
  the banner before any heavy import (announce slow stages like the eval stack),
  `flush=True`, and drive the harness progress bars (`v3/progress.py`) for anything
  long-running. A silent terminal — or a run buried where the user can't watch it —
  is a bug, full stop.
- **Critical-review the code you write:** after writing or changing code in `v3/`,
  before you report the work done, run `/critical-review` on the file(s) you just
  changed — pass them in. It spawns the read-only `critical-reviewer` and you resolve
  its findings with it until the code converges. Skip only for trivial non-logic
  edits (a rename, a comment, a one-line config tweak).

## Agent roster — orchestrator routing

The main-chat Claude is the orchestrator: it talks to the user and routes every job
to a specialist agent; it does no hands-on work itself. Plain questions get direct
conversational answers — no agents, no tool calls. Long runs still happen in the
user's terminal: agents prepare, the user runs. Definitions live in
`.claude/agents/`. Route by task:

- **v3-coder** — any code change in `v3/`.
- **critical-reviewer** — post-change review of `v3/` code (the hard rule above).
- **code-optimizer** — performance work; profiles first, benchmarks before/after.
- **maths-algorithmist** — mathematical algorithm design and verification.
- **order-of-operations** — sequencing/data-flow correctness of pipelines and algorithms.
- **logician** — invariants, boolean/set logic, proof-or-counterexample checks.
- **retrieval-scientist** — retrieval design and experiment proposals.
- **eval-statistician** — significance, sample size, judge reliability, judge-run cost math.
- **results-analyst** — reading `v3/output/`, reporting numbers (metric validity binding).
- **graph-refresher** — `python refresh_graph.py` + worklist processing.

## Artefact arm — built natively in `v3/artefact/`

The artefact is the system under test, rebuilt natively in `v3/artefact/`. Its
deterministic stages exist and are tested (`python -m pytest artefact/tests` from
`v3/`): `scan.py` (file catalog → sha256/file_id), `probe.py` (shape recovery, RFC
6901 pointers), `derive_corpus.py` (oracle strip), `resolver_prototype.py` (reference
resolution, hash-verified). The HERB mapping key (`keys/Salesforce__HERB.yaml`) and
the design references (`DESIGN.md`, `MODEL_CONTRACTS.md`) live there too. The graph
proper — chunk → tag → facet retrieval — is the unbuilt part; `pipelines/artifact.py`
is the arm entry that drives it. The design carried forward:

- **The graph spine is closed canon:** `Source → File → Chunk → Tag` are the only
  nodes. Hard fields are chunk attributes. The graph is references into untouched
  raw source, never copies — never put values, inventories, or mirrors of metadata
  directories into it.
- **The model emits no numbers, ever** (tagger and interpreter). The chunk
  description is dead. Tags are per-chunk contextual phrases.
- **`herb-eval` (Neo4j) is the prior artefact build under the superseded design** — a
  contrast/forensic baseline only, not adopted. The v3 artefact rebuilds from raw
  natively in `v3/artefact/`; never query `herb` (oracle-contaminated).
