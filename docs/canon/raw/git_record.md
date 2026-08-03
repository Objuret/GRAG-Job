# Git record — forensic reconstruction from git alone

**Scope.** Repo `c:\Coding\exjobbet\GRAG-Job` (remote `Objuret/GRAG-Job`). 30 refs, 77
commit objects (74 real commits + 3 `refs/stash` objects). Range 2026-05-07 → 2026-08-01.
Every claim below was verified against the actual git object; the reproduce command is
given inline. Nothing here is taken from memory, from `docs/state/`, or from `MEMORY.md`.

**Authors** (`git shortlog -sne --all`) — all four identities are the same person:

| Author | Email | Commits |
|---|---|---:|
| Objuret | jochen@wikman.com | 43 |
| Joakim Wikman | jochen@wikman.com | 25 |
| Joakim Sandström | h19josan@du.se | 8 |
| Joakim | h19josan@du.se | 1 |

**Labels used throughout.**

- **[USER]** — written by the human. Signals: first-person design voice, argument and
  counter-argument, decisions with dated sign-off markers, research reading with
  citations, profanity/frustration, commit messages in the terse human register
  ("ok", "ragas", "småfix", "doit").
- **[AGENT]** — written by an AI agent, committed by the human. Signals: an AI footer
  (`Co-Authored-By: Claude Opus 4.7`, `Co-authored-by: Cursor`), the mechanical
  `feat: update <dir> (N files)` + "changed files:" list format emitted by tooling,
  Claude-memory frontmatter blocks.
- **[UNKNOWN]** — genuinely undecidable from git. Most May/June docs are in this class
  at the sentence level: the *design* is plainly the user's (it is argued, dated, and
  signed off), the *prose* may well be agent-drafted under dictation. Where a document
  is jointly produced I say so rather than pick.

**A caution that applies to the whole record.** This repo's design is carried in prose
documents, and prose authorship cannot be settled from git metadata. What git *can*
settle is: what existed when, what changed, what was deleted, and whether a later state
contradicts an earlier one. Part 3 is the part that rests on hard evidence.

---

## Part 1 — Annotated commit timeline

Branch membership computed per commit with `git branch -a --contains <sha>`. Because
almost every branch descends from the same trunk, only the *distinguishing* membership
is noted; "trunk" means the commit is an ancestor of essentially all working branches.

### Topology in one paragraph

There is one long trunk from `dba1160` (05-07) to `6730d13` (08-01). Two things sit off
it. First, `origin/main` is **not** the work line: it carries only `48aa84f`, `4ab34b4`,
`a6ff064` (05-15, agent settings + Claude memory files) and stops there — the real work
continued on `origin/djuret/monorepo` and its successors. Second, `origin/jockedev` and
`origin/jockedev2` are Joakim Sandström's branches; `jockedev2`'s six-commit RAGAS series
was never merged — it was re-landed as one squashed commit (see `5706520` below).

### 2026-05-07 — the initial system (trunk)

| Date | SHA | Author | Subject |
|---|---|---|---|
| 05-07 | `dba1160` | Objuret | Initial commit |
| 05-07 | `4a95654` | Objuret | Freshen indexing pipeline smoke path |
| 05-07 | `5330ba0` | Objuret | Cap JSONL chunk content |
| 05-07 | `78ad0b9` | Objuret | Document post-cap smoke run |
| 05-07 | `01a904b` | Objuret | Clarify raw tag canonical mapping |
| 05-07 | `8c84b86` | Objuret | Expand smoke run report |

`dba1160` is not a skeleton: 52 files, 4,846 insertions, a complete Neo4j indexing
pipeline (`indexing/chunker.py` 388 lines, `indexing/orchestrator.py` 559,
`indexing/worklist.py` 310) plus eight design docs including `docs/architecture.md`
(a 12-entry decision log) and `docs/graph_schema.md` (280 lines). The system arrives
fully designed. All on trunk.

### 2026-05-08 — monorepo restructure (trunk)

| Date | SHA | Author | Subject |
|---|---|---|---|
| 05-08 | `070393f` | Objuret | chore: restructure project as monorepo |
| 05-08 | `c141021` | Objuret | chore: lock backend dependencies |
| 05-08 | `3acc7f6` | Objuret | chore: bundle graph export |

`070393f` moves everything under `backend/` and adds a `frontend/` React workbench.
`3acc7f6` commits a 46 MB `graph_export/grag_graph_latest.zip`.

### 2026-05-11 → 05-15 — the HERB tagging system (trunk, + jockedev)

| Date | SHA | Author | Subject | Branch note |
|---|---|---|---|---|
| 05-11 | `48fbc9d` | Objuret | chore: rename cluster dimensions | trunk; **leaves `origin/main`** |
| 05-11 | `96e8ebf` | Objuret | docs: align documentation with current codebase | trunk |
| 05-11 | `fa0c23c` | Joakim Sandström | ragas | **`origin/jockedev` only** |
| 05-13 | `c858f37` | Objuret | feat: add tagging pilot and file-backed worklist | trunk |
| 05-13 | `4981d37` | Joakim Sandström | småfix | **`origin/jockedev` only** |
| 05-13 | `399ee32` | Objuret | Rework HERB chunking and tagging frames | trunk |
| 05-14 | `415148d` | Objuret | Document HERB query interpretation layer | trunk |
| 05-14 | `bcc3156` | Objuret | Track current HERB snapshot artifact | trunk |
| 05-14 | `5debf4a` | Objuret | Consolidate project documentation | trunk |
| 05-15 | `b1edf29` | Objuret | Consolidate HERB thesis workflow | trunk |
| 05-15 | `fb311f6` | Objuret | frontend pipeline fixing | **tip of `origin/djuret/monorepo`** |

`48fbc9d` is the cluster-dimension rename (Part 2, item 4). `c858f37` adds
`backend/tagging/pipeline.py` (851 lines) and a 781-line pilot HANDOFF. `399ee32` reworks
the chunker (+869 lines) and adds the frames doc. `415148d` adds the tagging schema, the
query-interpretation layer, and the full-HERB pilot report. `b1edf29` introduces
`quarantine/` and the browser-direct frontend services.

`origin/jockedev` (2 commits) is a dead end — nothing downstream contains it.

### 2026-05-15 — the `origin/main` side-branch

| Date | SHA | Author | Subject | Branch note |
|---|---|---|---|---|
| 05-15 | `48aa84f` | Objuret | ok | `main`, `origin/dev-merge`, `claude/flamboyant-buck-4586c0` |
| 05-15 | `4ab34b4` | Objuret | ok | same |
| 05-15 | `a6ff064` | Objuret | Merge branch 'main' … into claude/dreamy-bohr-8d88a8 | same |

These three do **not** contain `48fbc9d` onward. `48aa84f` adds only
`.claude/settings.local.json`; `4ab34b4` adds `memory/MEMORY.md`,
`memory/project_active_branch.md`, `memory/project_architecture.md`. This is the only
place Claude memory files were ever committed, and they are forensically the single most
valuable artifact of the period (Part 2, item 12).

### 2026-05-17 → 05-20 — frontend, embeddings, and the RAGAS harness

| Date | SHA | Author | Subject | Branch note |
|---|---|---|---|---|
| 05-17 | `1b85721` | Joakim Wikman | Restore monorepo frontend; wire Prompt Mode (raw/context/hybrid) | **`origin/dev-merge` only** |
| 05-18 | `452fa5d` | Joakim Wikman | Embedding-based prompt-tag grounding + prompt mode | trunk; tip of `origin/claude/hardcore-engelbart-ea5bc5` |
| 05-19 | `c301840` | Objuret | Bundle e5-small-v2 fp32 locally; refresh embedded graph snapshot | trunk |
| 05-19 | `922d0cb` | Objuret | Make the Usage canvas the real executor; real metrics | trunk; tip of `origin/embeddings` |
| 05-19 | `c5c0a42` | Joakim Sandström | Add RAGAS evaluation: headless pipeline harness + Python runner | **`origin/jockedev2` only** |
| 05-19 | `497db9f` | Joakim Sandström | Fix --questions/--out path resolution under npm workspace cwd | `origin/jockedev2` only |
| 05-19 | `9114e31` | Joakim Sandström | Add ground-truth reference evaluation (HERB gold QA) | `origin/jockedev2` only |
| 05-19 | `7a0ab5e` | Joakim Sandström | Recall fix: fall back to gated full-text when tag scoring is empty | `origin/jockedev2` only |
| 05-19 | `0b98b12` | Joakim Sandström | Scale gold set to n=100 (balanced) + statistically robust result | `origin/jockedev2` only |
| 05-19 | `8b320ac` | Joakim Sandström | RQ2 comparative arm: baseline retrieval, temperature, multi-hop set | **tip of `origin/jockedev2`** |
| 05-19 | `5706520` | Objuret | Add HERB RAGAS evaluation harness | trunk; tip of `origin/ragas-eval-port` |
| 05-20 | `da25016` | Objuret | Add SQL-agent baseline and wire Run Builder exports into the RAGAS harness. | trunk |
| 05-20 | `98bb96a` | Objuret | Add thesis alignment docs and document gold-100 RAGAS results. | trunk; tip of `origin/eval-run-builder-sql` |

**The `jockedev2` squash.** `git log -1 --format='%h parents=%p' 5706520` returns
`5706520 parents=922d0cb` — a single parent, so `5706520` is **not** a merge. Yet
`git rev-parse 8b320ac:backend/evaluation/ragas_eval.py` and
`git rev-parse 5706520:backend/evaluation/ragas_eval.py` are the *same blob*
(`8db798b0…`), as are the two `build_gold_set.py` blobs (`99570033…`). The six
`jockedev2` commits were therefore re-landed as one commit with an **empty body**. Their
six detailed messages — which carry every measured result of that work and six
`Co-Authored-By: Claude Opus 4.7` footers — survive only on the unmerged branch. See
Part 3, contradiction C-11.

### 2026-05-28 → 06-01 — v1 forensics and the v2 pivot (trunk)

| Date | SHA | Author | Subject | Branch note |
|---|---|---|---|---|
| 05-28 | `54bc1a4` | Objuret | Add eval results, SQL baseline, thesis docs, and Bonnier dataset | tip of `origin/eval-results-complete-2026-05` |
| 05-29 | `244beb7` | Objuret | Snapshot v1 artefact forensics: verify scripts + RAGAS run dumps | trunk |
| 05-30 | `296fc40` | Objuret | Add v2 artefact-rebuild design, shape-probe prototype, NVIDIA host verification | trunk |
| 05-30 | `c2fabbb` | Objuret | Commit repo changes; remove thesis docs from tracking, gitignore thesis paths | trunk |
| 06-01 | `18d11df` | Objuret | Wire NVIDIA NIM into Settings; add reference-resolver prototype and v2 design docs | trunk |

`296fc40` is the pivot: `docs/v2_artefact_rebuild_design.md` (192 lines) declares the v1
artefact superseded. `18d11df` adds §13 (the semantic-dimensions research, +114 lines).
`c2fabbb` removes the entire thesis tree from version control.

### 2026-06-15 → 06-28 — the v1/v2 split and the v3 harness

| Date | SHA | Author | Subject | Branch note |
|---|---|---|---|---|
| 06-15 | `0efff16` | Objuret | Separate repo into v1/ (frozen) and v2/ (active) siblings | trunk |
| 06-15 | `b3381ee` | Objuret | Simplify regraph: drop headless-agent auto-extraction | tip of `origin/artefact-v2-rebuild-design` |
| 06-18 | `4da9c5b` | Objuret | feat: update graphify-out (213 files) | trunk |
| 06-19 | `14de2eb` | Objuret | feat: update graphify-out (2 files) | **`contract`, `v3` only**; tip of `origin/v3` |
| 06-19 | `4ac74c0` | Joakim Wikman | untracked files on main: … | **`refs/stash`** |
| 06-19 | `90452ac` | Joakim Wikman | index on main: … | **`refs/stash`** |
| 06-19 | `6be4692` | Joakim Wikman | On main: doit | **`refs/stash`** |
| 06-20 | `1d43959` | Joakim Wikman | update v3/contract.py v3/data/gold100.jsonl | tip of `origin/contract` |
| 06-21 | `a45292f` | Joakim | v3: implement lucene (BM25) arm + adopt shared contract | trunk |
| 06-23 | `0733a9d` | Objuret | feat: update graphify-out (76 files) | tip of `origin/vector` |
| 06-24 | `28c95aa` | Objuret | v3/artefact: artefact subsystem — probe, scan, derive-corpus, resolver, key, design | trunk |
| 06-28 | `8a640bf` | Objuret | feat: update graphify-out (533 files) | trunk |
| 06-28 | `2d688bc` | Objuret | feat: update graphify-out (15 files) | tip of `origin/arm_evals_k50_done` |
| 06-28 | `a515c94` | Objuret | feat: update v3 (48 files) | trunk |

`0efff16` is the largest single design landing in the repo: it grew the design doc by
**750 lines** (`git diff 18d11df:docs/v2_artefact_rebuild_design.md 0efff16:v2/docs/v2_artefact_rebuild_design.md --stat`
→ `750 insertions(+), 75 deletions(-)`), adding §7 (the closed graph spine), §8 (the
mapping key), §9 (chunking), §13.4–13.5 (the facet allocation table and per-facet specs),
§14 (retrieval routing), §15 and §16. It also adds the first `CLAUDE.md`.

The three `refs/stash` objects are unreachable from any branch. `4ac74c0` stashed the
entire untracked `data/Salesforce__HERB/` corpus (1,550,956 insertions) — the HERB raw
data was carried into the repo as an untracked stash, never as a commit on a branch.

**The misleading-message cluster.** `8a640bf`, `2d688bc` and `a515c94` are titled
`feat: update graphify-out (N files)` / `feat: update v3 (48 files)` with an
auto-generated "changed files:" list truncated to ten entries. Their real content is
substantial and largely invisible from the message: `8a640bf` ships
`v3/artefact/tag.py` (the tagger — the one item §16 called "the one design blocker"),
`v3/artefact/chunk.py`, a 38-line amendment to `DESIGN.md`, and a 659-line research
survey `docs/research/2026-06-27-facet-derivation-methods.md`. `a515c94` ships
`v3/artefact/interpreter.py` (278 lines), `v3/pipelines/artefact.py` (322 lines), and
**deletes** `v3/pipelines/artifact.py`.

### 2026-07-12 → 08-01 — the eval campaign

| Date | SHA | Author | Subject | Branch note |
|---|---|---|---|---|
| 07-12 | `69115e0` | Objuret | feat: update graphify-out (49 files) | trunk; adds `v3/pipelines/artefact_v1.py` (666 lines) |
| 07-15 | `ec0c1c6` | Joakim Wikman | update v3/artefact/tag.py … (12 files) | tip of `origin/v3_artefact_build` |
| 07-15 | `fe8cd3a` | Joakim Wikman | Merge v3_artefact_build (token in/out telemetry) into re-V1-k50 | trunk |
| 07-15 | `7fa7d28` | Joakim Wikman | refresh_graph: derive repo root from script location | trunk |
| 07-15 | `7295cec` | Joakim Wikman | vector: use generator_usage_from_nim for embed usage split | trunk |
| 07-15 | `c1a68d1` | Joakim Wikman | artefact_v1: three fused rankings (tag/desc/scope), sphere grounding, plan logging | trunk |
| 07-16 | `c73e887` | Objuret | artefact: add herb-eval Neo4j dump via git-lfs | trunk |
| 07-16 | `7deaec9` | Objuret | artefact: document herb-eval.dump restore steps | tip of `origin/v3lucene` |
| 07-16 | `90d1074` | Joakim Wikman | artefact_v1: glm-5.2 interpreter; byte-exact benchmark data; 480s NIM timeouts | trunk |
| 07-16 | `6dc8024` | Joakim Wikman | artefact_v1 run ops: glm interpreter, queue-proof timeouts, lazy eval imports | trunk |
| 07-16 | `0395bfa` | Joakim Wikman | data: byte-exact LF blobs for the full benchmark tree | trunk |
| 07-16 | `a6e43a2` | Joakim Wikman | nim: per-account key pool — NVIDIA_API_KEY_WORKER_* lanes | trunk |
| 07-16 | `78a3e38` | Joakim Wikman | model_test: run.py-style CLI; canon rule: runnables show life instantly | trunk |
| 07-16 | `87cb9cf` | Joakim Wikman | v3: pinned requirements (provisional laptop reconstruction) | trunk |
| 07-16 | `59a9f77` | Joakim Wikman | artefact_v1: silence per-query server notifications | trunk |
| 07-16 | `841a42e` | Joakim Wikman | requirements: ragas scoring-time deps | trunk |
| 07-16 | `9c4ec50` | Joakim Wikman | judge shoot-out: catalog probe tool, env-overridable judge, --judge re-scoring | trunk |
| 07-20 | `14dd887` | Joakim Wikman | model calls: one CLI lane for claude/gpt/gemini judges + a claude generator | trunk |
| 07-20 | `7879dfe` | Joakim Wikman | data: gold-100 three-arm shipment, single Haiku judge + judge shoot-out | trunk |
| 07-23 | `5006fed` | Joakim Wikman | v3: normalized combine + tunable modifiers, caches, hybrid lucene+vector arm | trunk |
| 07-31 | `c33594d` | Joakim Wikman | snapshot before tag-first retrieval build: heldout100 data, graph refresh, doc state | tip of `origin/re-V1-k50` |
| 08-01 | `6730d13` | Joakim Wikman | tags-first retrieval regime, per-facet tag cluster guidance, per-run --flag args | **HEAD**, tip of `origin/tag-first-cluster-guide` |

Note `69115e0`: titled "update graphify-out (49 files)", it actually introduces
`v3/pipelines/artefact_v1.py` — the arm that produces every artefact number the project
subsequently reports.

**Authorship of the timeline.** Commit *messages* split cleanly. The terse human register
("ok", "ragas", "småfix", "doit", "frontend pipeline fixing") is **[USER]**. The
`feat: update <dir> (N files)` + "changed files:" format is **[AGENT]** (tool-generated;
it appears only on `Objuret` commits from 06-18 onward and its file list is mechanically
truncated at ten). The long structured messages with `Co-Authored-By: Claude Opus 4.7`
(the six `jockedev2` commits) and `Co-authored-by: Cursor` (`da25016`, `98bb96a`) are
**[AGENT]**-drafted, human-committed. The long structured messages *without* a footer
(`296fc40`, `0efff16`, `28c95aa`, `c301840`, `922d0cb`, `5006fed`, `a45292f`) are
**[UNKNOWN]** — they read as the user's design voice but carry no proof either way.

---

## Part 2 — The design record, chronological

### 1. The three-layer pipeline and the twelve-decision log — 2026-05-07 — [UNKNOWN]

`git show dba1160:docs/architecture.md`

The system arrives with a formal decision log, D1–D12, each entry structured
**Decision • Rationale • Alternatives considered • Status**. The load-bearing ones:

> ### D1 — Path A deterministic chunker
> - **Decision.** Chunks are produced by deterministic, per-format rules in
>   `indexing/chunker.py`. The agent operates on pre-existing `(:Chunk)` rows; it does
>   **not** propose chunk boundaries.
> - **Rationale.** Reproducibility, idempotency, predictable cost. The agent's job is
>   interpretation, not segmentation.

> ### D2 — Tag uniqueness on `name` only; cluster on edges
> - **Decision.** `(:Tag) REQUIRE n.name IS UNIQUE`. Cluster is a property on
>   `(:Chunk)-[:HAS_TAG]->(:Tag)` and `(:File)-[:TAGGED]->(:Tag)`, not on the node.
> - **Rationale.** Tag names like `q2_2025` can be a `time_relevance` tag in one chunk
>   and a hint of an `event_process` in another. Tying the cluster to the edge keeps the
>   graph honest.

> ### D10 — Storing `Chunk.content` directly (vs offsets)
> - **Decision.** `(:Chunk).content` stores the chunk text. `start_offset`/`end_offset`
>   are kept for debugging … but the agent reads `content` from the graph.
> - **Rationale.** … storing offsets and re-reading the source file each time would add
>   I/O cost and a hard dependency on the source path being stable. Storing content
>   makes the graph self-sufficient.
> - **Status.** Active. Cost: graph size scales with corpus size. Acceptable for the
>   project scale.

D10 is reversed in full on 2026-05-30 (contradiction C-1). D2's `cluster`/`canonical_id`
machinery is abandoned by 2026-05-15 (C-3).

The decision log is a genuine design instrument — it records alternatives and rejects
them with reasons. Whether the *prose* is agent-drafted is undecidable; the *decisions*
are clearly owned.

### 2. The original graph spine — 2026-05-07 — [UNKNOWN]

`git show dba1160:docs/graph_schema.md`

Eight node labels: `:Source`, `:File`, `:Chunk`, `:Tag`, `:CanonicalTag`,
`:CanonicalTagProposal`, `:WorkItem`, `:Run`. Seven edge types: `CONTAINS`, `HAS_CHUNK`,
`NEXT`, `HAS_TAG`, `TAGGED`, `TARGETS`, `OBSERVED_IN`.

The `HAS_TAG` edge:

> | `cluster` | string | One of the five clusters. The cluster lives on the **edge**, not the Tag node. |
> | `canonical_id` | string \| null | The canonical label the agent mapped to, or `null` when proposing. **Indexed.** |
> | `weight_local` | float | Saliency in [0, 1] for this chunk. |

And the derived file-level rollup:

> | `weight_global` | float | `sum(coalesce(c.relevance_to_file, 0.5) * r.weight_local) / count(c)` per (file, tag, cluster, canonical_id) group. |

Six of the eight node labels and four of the seven edge types are gone by 2026-06-15
(C-4).

### 3. The controlled canonical vocabulary — 2026-05-07 — [UNKNOWN]

`git show dba1160:clustering/canonical_seed.yaml`

> ```yaml
> # Canonical tag vocabulary, organised by retrieval dimension.
> #
> # Source of truth for the clustering layer. Hybrid seed-and-grow:
> # proposals from the indexing run land in (:CanonicalTagProposal) and only
> # enter this file via `python -m clustering.review`.
>
> theme:
>   - advertising
>   - sports
>   …
> object_entity:
>   - person
>   - organization
>   …
> ```

Five dimensions × 5–7 seeded labels, with a documented promotion path (propose → triage →
promote). Deleted entirely on 2026-05-13 (C-3).

### 4. The cluster-dimension rename — 2026-05-11 — [USER]

`git show 48fbc9d -- backend/clustering/canonical_seed.yaml backend/agents/schemas.py`

Commit message: `chore: rename cluster dimensions`. Verified diff:

> ```
> -theme:            +topic:
> -object_entity:    +entities:
> -event_process:    +activity:
> -time_relevance:   +temporal:
> -information_need: +evidence:
> ```

and in `backend/agents/schemas.py`:

> ```python
>  Cluster = Literal[
> -    "theme",
> -    "object_entity",
> -    "event_process",
> -    "time_relevance",
> -    "information_need",
> +    "topic",
> +    "entities",
> +    "activity",
> +    "temporal",
> +    "evidence",
>  ]
> ```

Labelled **[USER]**: a pure rename with a one-line `chore:` message is a human editorial
act, and the new names are the ones the user still uses. This rename matters more than it
looks — the *old* names state what each dimension was *for* (`information_need`,
`time_relevance`), and the new names are bare nouns. §13.1 later diagnoses exactly this
loss of specification as the cause of facet degradation (C-6).

### 5. Interpretation frames — the model must not see pipeline machinery — 2026-05-13 — [UNKNOWN]

`git show 399ee32:backend/docs/herb_tagging_frames.md`

> HERB tagging should not ask the model to infer how to read a chunk from internal
> pipeline labels. The chunker and tagging harness know the source shape; they
> must choose the right interpretation frame before making the model call.

The routing rule:

> ```text
> Chunk.kind / locator / section
>         -> deterministic frame renderer
>         -> agent receives task-specific source evidence
>         -> agent returns description + facet tags + weights
> ```

The exclusion list:

> The agent should not receive raw internal labels such as:
> - `Chunk kind` · `Chunk reference` · `Parent reference` · `Chunk type` · `Source file` · `chunk_id`

Eleven evidence shapes are enumerated (thin directory batches, product profiles, org-tree
records, conversation batches, document parts, meeting transcripts, PR batches,
answerable QA records, QA citation overflow, URL lists, unanswerable question batches),
each with an explicit interpretation rule.

The doc closes with four open questions, one of which is later decided:

> - Whether float weights should survive, or be replaced by ordinal ranks after
>   the weight anchoring observed in `pilot_001` and `pilot_002`.

Note the design at this date has the agent returning **"description + facet tags +
weights"** — all three of which are later killed (C-5, C-7).

### 6. The tagging contract — the five-facet scoring schema — 2026-05-14 — [UNKNOWN]

`git show 415148d:backend/docs/herb_tagging_schema.md`

This is the normative model contract of the v1 system. Stages:

> ```text
> select -> extract -> describe -> score -> analyze
> ```

Envelope: Anthropic Messages API, `claude-haiku-4-5`, forced `tool_use`,
`max_tokens: 8192`, `temperature: 0.3`.

The non-contamination rule:

> The model receives only information that is semantically relevant to the task
> it is doing. Internal pipeline machinery is never sent as model evidence …
> A single irrelevant word in repeated prompt context can become
> a repeated semantic feature, so the default is to exclude it unless it is
> actual source evidence.

Pass 2 defines the five facets:

> | Facet    | Captures                                                                                    |
> |----------|---------------------------------------------------------------------------------------------|
> | topic    | Subject matter                                                                              |
> | entities | Named people, organisations, products, systems, places                                      |
> | activity | Actions, processes, events                                                                  |
> | temporal | Dates and time expressions present verbatim in the text                                     |
> | evidence | Kind of information: definition, example, metric, argument, procedure, case_study, raw_data |

**The derived-weight formula** — the single most consequential constant in the May design:

> ```text
> w_chunk = strength × coverage_bonus
>
> strength       = sqrt(sum(f²) / N)
> coverage_bonus = ((sum(f))² / (N × sum(f²))) ^ α
>
> with N = 5  (number of facets)
>      α = 0.25  (coverage sensitivity)
> ```

with its stated justification:

> - `coverage_bonus` measures how spread the force is. `(sum(f))² / sum(f²)` is
>   the effective number of active facets — 1 when the force is concentrated in
>   one facet, N when spread evenly across all N. Dividing by N normalises to
>   [0, 1]. `α = 0.25` softens the spread bonus so it complements strength
>   rather than dominates it.

**`α = 0.25` has a rationale but no derivation** — "softens the spread bonus" explains the
*direction* of the choice, not the *value*. No sweep, no sensitivity analysis, no
alternative value is recorded anywhere in git. Same for the multi-facet cutoff:

> For each tag, the pipeline writes a `HAS_TAG` edge for the **primary facet**
> (`argmax(facets)`) plus one edge per other facet with `facets[other] >=
> MULTI_FACET_THRESHOLD = 0.50`.

`0.50` appears with no derivation at all.

Tag cleaning, with a hardcoded stoplist:

> ```python
> s = raw.strip().lower()
> s = re.sub(r"[^a-z0-9]+", "_", s)
> return s.strip("_")
> ```
> Drop if cleaned name in `FILLER = {"data", "information", "content", "record", "text", "chunk", "item"}`.

### 7. The full-HERB pilot — the empirical basis — 2026-05-14 — [UNKNOWN]

`git show 415148d:backend/docs/pilot_full_herb_report.md`

> **Run date:** 2026-05-14
> **Dataset:** Salesforce__HERB (1 of 4 thesis datasets)
> **Database:** `herb`
> **Model:** `claude-haiku-4-5` (Anthropic Messages API, forced tool_use)

The rationale for deriving rather than emitting the weight:

> ### Why the model does not emit `w_chunk`
> Across smoke pilots, model-verbalised float weights anchored hard on round
> values (0.7, 0.8, 0.9 …). The two-pass design pulls `w_chunk` out of the
> model's emit surface entirely and derives it from the facet vector

Coverage, measured:

> | Chunks selected | 5843 |
> | `:HAS_TAG` edges written | 255,288 |
> | Unique tag names | 25,896 |
> | Multi-facet tags | 22,083 (85% of unique names) |

And the success criterion:

> - pilot_001 single-pass: **85%** on round anchors
> - pilot_format_smoke two-pass, model-emitted w_chunk: 47%
> - **pilot_full_herb two-pass, derived w_chunk: 12.3%**
>
> Reducing anchoring from 85% to 12% was the load-bearing goal of the design
> work; this is the evidence it succeeded.

This run is declared a success on 05-14 and condemned as ~18% junk vocabulary on 05-30
(C-6).

### 7b. The query interpretation layer — prompt/chunk symmetry — 2026-05-14 — [UNKNOWN]

`git show 415148d:backend/docs/query_interpretation_layer.md`

The founding principle, and the earliest statement of the symmetry idea that §13.3 later
elevates to an invariant:

> Query interpretation should use the same base shape as chunk interpretation:
>
> 1. Extract flat retrieval handles from the user prompt.
> 2. Score each handle against the same five facets.
> 3. Derive query-side centrality from the five-facet vector.
> 4. Add filters and answer instructions separately.
>
> This keeps retrieval as a comparison between two similar semantic objects:
>
> ```text
> query tag vector  <->  chunk tag vector
> ```

The division of labour between model and code:

> The goal is not to let the model write Cypher. The model interprets the prompt
> into a small structured query plan; deterministic code maps that plan to Neo4j
> queries.

The same anti-anchoring move as the chunk side, with the naming distinction spelled out:

> The model should not emit query centrality directly. Code derives it from the
> facet vector using the same formula as HERB `compute_w_chunk` …
> `w_query` means "how important this tag is to the user's information need";
> `w_chunk` means "how central this tag is to a chunk."

The scorer as designed — five factors (see C-12):

> ```text
> score += query_tag.w_query
>        * query_tag.facets[facet]
>        * chunk_edge.w_chunk
>        * chunk_edge.w_facet
>        * coalesce(chunk.relevance_to_file, 1.0)
> ```

with a matching constraint that is the ancestor of the whole later grounding problem:

> Only compare a prompt tag to a chunk edge when the cleaned tag names match, or
> when a later tag-expansion step has explicitly linked them.

Exact-name matching is what `452fa5d` (05-18, "Embedding-based prompt-tag grounding")
replaces with cosine similarity, adding the sixth factor `qt.sim`.

The query plan is designed to be inspectable, and the answer job is deliberately separated
from retrieval:

> `filters` and `answer_job` are not tags. They control what the retrieval code
> is allowed to search and what the answer model should do after retrieval.

> For thesis-safe behavior, the default should be:
> ```text
> evidence_policy = retrieved_only
> missing_evidence_policy = say_insufficient_evidence
> ```

The doc also records the abandonment of the canonical machinery as an instruction rather
than a decision — three weeks before any design doc says so:

> - Do not use old frontend assumptions such as `cluster`, `canonical_id`, or
>   `weightLocal` for HERB retrieval.

### 7c. The shipped v1 scorer — max-then-sum — 2026-05-28 — [UNKNOWN]

`git show 54bc1a4:frontend/src/services/retrieval.ts`

> ```
> // Weighted overlap: each prompt tag contributes its best matching HAS_TAG edge
> // on the chunk (max over that tag's grounded corpus links), then scores sum
> // across prompt tags. Stops generic corpus tags linked from many kNN hits from
> // piling onto the same chunk. Link-only mode drops grounding_sim from the product.
> ```
> ```cypher
> WITH c, promptIdx, (${edgeWeight}) AS contrib
> WITH c, promptIdx, max(contrib) AS bestPromptContrib
> WITH c, sum(bestPromptContrib) AS score
> ```

Max-within-a-prompt-tag, then sum-across-prompt-tags, with a stated reason (stopping
generic tags from piling up). This aggregation survives the entire rebuild: the 2026-07
arm still does it — `git show 6730d13:v3/pipelines/artefact_v1.py`, "An opened level's
tags pull their chunks, **each chunk keeping its highest-support tag**", summed across
parts. It is one of the few v1 mechanisms that was never repudiated.

### 8. Deletion of the canonical vocabulary — 2026-05-13 — [UNKNOWN]

`git show 399ee32 -- backend/clustering/canonical_seed.yaml`
→ `1 file changed, 49 deletions(-)`

`git show 399ee32 -- backend/scripts/bootstrap_schema.py` removes `seed_canonical_tags()`,
the `--skip-canonical-seed` flag, and the yaml load. The only prose trace is one line in
`git show 399ee32 -- backend/docs/architecture.md`:

> -| **clustering** | … | Canonical tag vocabulary (`canonical_seed.yaml`). Proposal triage (CLI) and named cluster query views are open work — not built. |
> +| **clustering** | … | Future HERB query views. The old canonical seed vocabulary has been removed. |

The commit message says only `Rework HERB chunking and tagging frames`. See C-3.

### 9. The v2 pivot — references, not copies — 2026-05-30 — [UNKNOWN]

`git show 296fc40:docs/v2_artefact_rebuild_design.md`

> **Status:** design, validated against real HERB data. No v2 code written yet.
> **Baseline it supersedes:** the v1 artefact (git tag `artefact-v1`, commit `244beb7`;
> Neo4j `herb-eval` + `herb-eval.dump` + sibling `herb-eval-backup`).

§1, the core principle, and the explicit charge against v1:

> The raw source files are authoritative and untouched. The graph stores **references**
> into them plus the derived semantic layer. Content is **resolved on demand** from the
> untouched source; the graph never becomes a second, mutated copy that replaces the
> original.
>
> The v1 chunker violated this: it consumed each record, rendered it to a prose string,
> stored the string as `c.content`, and that lossy derivative became the only surviving
> copy. Proof of the inversion: v1 HERB chunks were written with `start_offset=0,
> end_offset=len(content)` where `content` is the fabricated prose — the "locator"
> pointed inside the fabrication, not the source.

The reference triple (§2):

> A reference is `{file_id, scheme, address}`. A resolver turns it into exact source
> content on demand.
>
> | nested JSON | `json_pointer` (RFC 6901) | e.g. `/slack/42/Message/User/text` |
> | long text leaf | `json_pointer` + `char_span` | field pointer + `[start,end]` within the value |
> | tabular (parquet/csv) | `row` | row index (+ column) |

Resolution (§3):

> - **Identity is the content hash** — preflight already computes `sha256`, and
>   `file_id = sha256[:24]`.
> - **Verify the hash on resolve; fail loud on mismatch.**

§7 in this version mandates full entity decomposition — later reversed (C-8):

> Faithful decomposition = every object → a node, every scalar attribute → a property.

§12, the eval verdict that has never been acted on:

> Every run in `run data/` (gold-100, graph100, baseline100, mh_graph, …) was produced
> against the v1 graph, whose retriever multiplies seven factors at query time and whose
> vocabulary is polluted. Those numbers measure the v1 violation, not the intended product.
> The HERB evaluation is re-run on the v2 graph for thesis numbers; v1 runs are kept as the
> before/after contrast.

§11, tagger model, decision one of three:

> - **Model: `deepseek-ai/deepseek-v4-pro`** — chosen by benchmark (reliable HTTP 200, valid
>   JSON, consistent latency). `deepseek-v4-flash` is a working fallback; `moonshotai/kimi-k2.6`
>   was ruled out (~118 s/call on the free tier, with and without JSON mode).

§10 records identity resolution measured against real data — the strongest evidence in the
repo that this design was empirically driven:

> - `eid_xxxxxxxx` (employee.json, 530 people; key == employee_id): slack `userId` (54/56),
>   `team[]` (44/44), document `author` (15/15), transcript `participants` (33/33) →
>   `:Employee`.
> - `EMP_#########` (pr/review `user.login`): a **separate, directory-less population** —
>   zero EMP_ ids exist in employee.json. … (A first-pass key wrongly mapped login →
>   Employee; the data corrected it.)

and the oracle-quarantine requirement:

> - **The eval oracle must be quarantined.** `answerable_questions` +
>   `unanswerable_questions` carry `ground_truth` + `citations` — this is the
>   contamination that polluted the old `herb` DB.

### 10. The three-tier semantic model — 2026-06-01 — [UNKNOWN, but strongly user-shaped]

`git show 18d11df -- docs/v2_artefact_rebuild_design.md` (adds §13, +114 lines)

The diagnosis of why the v1 facets failed:

> The v1 tagger used five facets — `topic, entities, activity, temporal, evidence`
> … They were intended as rich semantic dimensions but were never specified as such, so
> the model defaulted to the shallowest reading of each and emitted literal tokens:
> `temporal` → date strings (`2024_04_27`), `entities` → identifier strings (`eid_…`),
> `evidence` → links (`https_github_com_…_pull_380`). This is the root of the ~18 % junk
> vocabulary (`eid_*` alone ≈ 16 k `HAS_TAG` edges). The pollution is what an
> *underspecified semantic dimension* collapses into when it is pointed at prose full of
> literal tokens.

The two-part fix:

> The fix is two-part: (a) move the literal **facts** to structure … and (b) **specify
> each dimension by its true semantic intent** — e.g. `temporal` is the
> *time-relationship* (retrospective / now / forward, span, urgency), never a date. The
> date is structure; the temporal *meaning* is the facet.

A seven-tradition convergence table (Ranganathan PMEST, neo-Davidsonian/AMR, 5W1H, SFL
metafunctions, TAM, Appraisal + evidentiality, RST/speech-act) reduced to a three-tier
model, then the two governing invariants:

> 1. **Completeness.** Every dimension in the convergent model is represented *somewhere*
>    in the totality (structure ∪ facets ∪ description ∪ grounding ∪ interpreter).
> 2. **Symmetry.** Whatever the artefact uses to *retrieve* must be mirrored on the prompt
>    side — chunk-representation and prompt-interpretation decompose along the *same* axes,
>    or they cannot be matched.

And the reframing of facet design:

> So facet design is an **allocation problem**, not a list: for each convergent dimension,
> decide which mechanism(s) carry it — `{hard field | tag-facet | description/embedding |
> grounding | interpreter}` … Building this dimension → mechanism allocation table (with
> the interpreter column) is the next design step before the re-tag is implemented.

Labelled [UNKNOWN] but with the strongest user-signal in the repo: it is an argued
position with fourteen academic citations, a named prior error, and a stated next step.

### 11. The v1 retrieval scoring formula — 2026-05-15 — [AGENT], quoting [USER]

`git show 4ab34b4:memory/project_architecture.md`

This is a Claude memory file (YAML frontmatter, `type: project`) — **[AGENT]**-written —
committed by the user on the `main` side-branch. It is the only surviving record of the
v1 query-time scoring formula:

> The two-pass prompt-interpretation method documented in (formerly)
> `backend/docs/query_interpretation_layer.md` is **good** and belongs to the frontend now:
> 1. LLM pass 1: prompt → `{description, flat tags[]}` (same prompt-cleaning rule as HERB extract)
> 2. LLM pass 2: each tag → 5-facet vector (`topic, entities, activity, temporal, evidence`)
> 3. Code derives `w_query` from facets using same `compute_w_chunk` formula as HERB
> 4. Retrieval scoring: `score += query_tag.w_query × query_tag.facets[facet] × chunk_edge.w_chunk × chunk_edge.w_facet × coalesce(chunk.relevance_to_file, 1.0)`
> 5. Plan shape: `{description, tags[], filters, ranking, answer_job, warnings}`
> 6. Answer-job modes: `direct_answer | list | compare | aggregate | summarize`, defaults
>    `evidence_policy=retrieved_only`, `missing_evidence_policy=say_insufficient_evidence`

That is a product of **five** factors. The v2 design's §12 charge says the v1 retriever
"multiplies **seven** factors at query time" — see C-12.

The same file records the abandonment of the D2/D4 canonical machinery as settled fact:

> 4. Field-name discipline: HERB graph uses `facet`, `w_chunk`, `w_facet`,
>    `relevance_to_file`. Legacy `cluster`, `canonical_id`, `weight_local`,
>    `weight_global` are old generic-tagger fields — do not use for HERB retrieval.

And it preserves verbatim user speech — the clearest **[USER]** fragment in the repo:

> User explicitly complained: *"i fucking cant understand why the agents always just
> 'kinda clean up' but leave the framework, documentation, scaffolding, some paint on the
> walls etc.. it's such a sloppy fucking mess"*. When cleaning up: actually delete the
> dead stuff. Don't leave empty placeholder dirs, contradictory docs, or orphan caches.

### 12. The architecture is browser-direct — 2026-05-15 — [AGENT]

Same file. Records that the whole app is the frontend talking straight to Neo4j and
Anthropic, and that a prior agent's FastAPI scaffolding was fiction:

> **No HTTP server in the middle. None planned.** …
> - The "agent put all those docs in the backend so something is seriously off" —
>   confirmed: a prior agent built scaffolding (orphan FastAPI, planned-HTTP docs) for an
>   architecture that was never going to ship. Treat any planned-HTTP language as that
>   agent's misunderstanding, not as design.

### 13. The closed graph spine — 2026-06-12, landed 2026-06-15 — [UNKNOWN]

`git show 28c95aa:v3/artefact/DESIGN.md` §7 (identical text lands at `0efff16` in
`v2/docs/v2_artefact_rebuild_design.md`)

> **The graph is `Source → File → Chunk → Tag`. Nothing else is a node.** This replaces
> the earlier draft in which every object became a node (Message/PullRequest/Employee
> entity nodes, COVERS edges) — that draft mirrored the dataset into the graph, which is
> the copies disease at the node level.

The decision rule:

> **The rule deciding node vs attribute:** a thing is a **node** only when others depend
> on its facts to resolve themselves, or retrieval walks *through* it. It is an
> **attribute** when it is a value you filter or boost by.

Consequences stated explicitly: records are not nodes, branch/collection positions are not
nodes, metadata directories are not nodes. And the per-chunk tag decision:

> - **Tag nodes are per-chunk emissions, not shared vocabulary (decided 2026-06-13).**
>   Each tag the tagger emits becomes its own `:Tag` node bound to exactly one chunk …
>   This is what made v1's residue possible: shared tags minted from oracle chunks
>   survived the herb-eval filter attached to clean chunks, and orphan-tag bookkeeping
>   existed at all.

This is an explicit, documented reversal of the 05-30 §7 — good practice, and it is
recorded as such. It is *not* in the silent-drop list for that reason; but see C-9 for the
residue it left behind inside the same document.

### 14. The chunking design — coherent episodes — 2026-06-15 — [UNKNOWN]

`git show 28c95aa:v3/artefact/DESIGN.md` §9.1–§9.7

> v1 filled records into a chunk up to a token budget — fill-to-budget batching. v2 kills
> that. **A chunk is a coherent episode**: a thread, a conversation that hangs together, a
> document.

The cap and its honest status:

> **The number: ~3000 tokens** (vs v1's 800 target / 1500 hard). Deliberately *larger* than
> the classic RAG 512–1024 band, for one reason: that band exists to fight single-vector
> compression, and v2 never embeds the raw chunk — meaning lives in the *tags* (the union of
> a chunk's phrase tags IS its semantic representation; there is no description, decided
> 2026-06-11) … 3000 is a calibration seed, not a verdict: sweep chunk size on HERB/Bonnier,
> watch where tag relevance starts to sag, and set the cap just under that knee (§15).

This is the cleanest constant in the repo: stated, justified by mechanism, and explicitly
flagged as unvalidated with a named validation procedure. The value is implemented
verbatim — `git show 6730d13:v3/artefact/chunk.py` line 44:

> ```python
> CAP_TOKENS = 3000        # tagger focus span (design §9.1); a seed for the §15 sweep, not a verdict
> ```

The sweep has never been run (no commit adds one).

The boundary detector (§9.4) is fully deterministic, per content-kind:

> - **Conversation:** explicit reply/quote link (works *against* cutting — an adjacency pair, a
>   question and its answer, stays together) > day-boundary / large **adaptive** time-gap (a
>   gap much larger than the *local* median, not a fixed minutes constant) > participant
>   turnover > lexical-topic shift.
> - **Prose:** section > paragraph > sentence / clause (EDU).
> - **Record collections:** record boundaries …

and embedding-based segmentation is rejected with reasons:

> **Embedding-similarity / topic-drift is rejected** as a boundary signal: it is circular
> (nothing is embedded at chunk-time — the chunk is the unit you are still forming), it needs
> an extra pre-pass embedding of every raw message, and terse chat ("+1", "see above") embeds
> to noise.

The statelessness commitment (§9.5):

> **One stateless call per chunk.** The tagger is a single structured-output invocation per
> chunk — same prompt, temp 0, one chunk in, phrase tags out (no description, no numbers),
> instance discarded — NOT a multi-step agent loop and NOT several chunks batched into one call.

### 15. The mapping key — 2026-06-12 — [UNKNOWN]

`git show 28c95aa:v3/artefact/DESIGN.md` §8; implemented at
`git show 28c95aa:v3/artefact/keys/Salesforce__HERB.yaml`

The automatic/declared split:

> **The automatic part — the shape→handling table.** What happens to a field follows the
> shape of its values, read off the probe tree with **no key entry** …
> The discriminator between "attribute" and "stays in raw" is the **repetition ratio**
> (distinct/total per field, measured by the probe across the fuse) … The gap between the
> two is a chasm, not a threshold to tune.
>
> **The declared part — the three judgments shape can't know:**
> 1. **Content choice** … 2. **Directories** … 3. **Id-space assignment**

The key implements exactly those three sections and nothing else, with resolution rates
carried as verified comments:

> ```yaml
> id_spaces:
>   employee:
>     - /slack/*/Message/User/userId          # 54/56 resolve
>     - /documents/*/author                   # 15/15
>     - /meeting_transcripts/*/participants/* # 33/33
>   pr_author:
>     - /prs/*/user/login
>     - /prs/*/reviews/*/user/login
> ```

with a loud-failure policy:

> ```yaml
> # Unresolved-ref policy: a value in an id-space field that resolves to no
> # directory entry (2/56 slack userIds) is flagged loudly at build time —
> # never silently dropped, never invented.
> ```

### 16. Structural oracle quarantine — 2026-06-12 — [UNKNOWN]

`git show 28c95aa:v3/artefact/DESIGN.md` §4 stage 0; implemented at
`git show 28c95aa:v3/artefact/derive_corpus.py`

> The quarantine is **structural, not declarative** (decided 2026-06-12, replacing
> the earlier `eval_holdout` key section): the probe can never sense the stripped
> surfaces, so contamination is impossible by construction instead of excluded by a
> yaml line.

Two categories are stripped, both with a cited external mandate:

> ```python
>   - the eval oracle: answerable_questions / unanswerable_questions
>     (815 + 699 = 1,514 questions; arXiv:2506.23139).
>   - the membership links: team / customers. Per the dataset card's RAG
>     Evaluation Note these exist "for oracle/long-context evaluation
>     settings only" — 390/815 answerable questions are people-/customer-
>     search, and membership must be inferred from the artifacts or from
>     metadata/* (which therefore STAYS in the corpus), never read off the
>     product-level lists.
> ```
> ```python
> ORACLE_KEYS = ("answerable_questions", "unanswerable_questions")
> RAG_UNSAFE_KEYS = ("team", "customers")
> STRIP_KEYS = ORACLE_KEYS + RAG_UNSAFE_KEYS
> ```

The `815 + 699 = 1,514` arithmetic checks out against the question file:
`git show 0733a9d:v3/data/questions.jsonl | wc -l` → `1514`.

This is the strongest piece of engineering in the record: a contamination class is made
impossible by construction rather than by policy, and the reason is cited to the
benchmark's own documentation.

### 17. The v2 facet set and per-facet specs — 2026-06-15 — [UNKNOWN]

`git show 28c95aa:v3/artefact/DESIGN.md` §13.4–§13.5

The allocation table promised on 06-01 was delivered. Its verdict:

> **Resulting v2 facet set** — only the genuinely fuzzy-semantic dimensions worth graded
> tag-edges + grounding: **topic, process, stance (attitude + modality),
> communicative-function**, plus **temporal-stance (TAM)** as the meaning-half of temporal.
> ~4–5 facets.
>
> - **Structure / hard fields (EXACT):** participants+roles, literal time, space, genre/kind,
>   evidentiality/provenance — exactly the v1 "junk facets" (entities/temporal/evidence)
>   relocated to where they belong.

§13.5 then gives each facet what §13.1 said v1 never had — a spec with a MUST-NOT list and
an interpreter mirror. E.g.:

> 4. **communicative-function** (rhetorical / speech-act — textual)
>    - emits: a function-type from a CLOSED set: `question | problem | decision | resolution
>      | request | proposal | announcement | status | explanation`.
>    - MUST NOT: topic/content.
>    - interpreter: ESSENTIAL, highest retrieval leverage …
>
> 5. **temporal-stance (TAM)** …
>    - emits: TAM tags from a CLOSED set (`retrospective`, `ongoing`, `planned`, `deadline`,
>      `recurring`). NEVER dates.

> **Controlled vocab:** communicative-function and TAM are small CLOSED sets (enums);
> topic/process/stance are open but concept-only. This is what the v2 tagger prompt encodes
> per facet — the missing spec that caused v1 degradation.

**None of this reached the built tagger.** See C-7.

### 18. The retrieval routing model — 2026-06-12 — [UNKNOWN]

`git show 28c95aa:v3/artefact/DESIGN.md` §14

> **weighted propagation of query activation through the layers down to chunks**:
> 1. The interpreted prompt produces entry points …
> 2. Activation flows down the weighted edges (facet→tags→chunks; no chunk→file
>    modulation — that weight is removed, §14.1), accumulating at chunks.
> 3. Rank by accumulated weight; the **cap** takes top-N.

The combinator (§14.3):

> `score = promptFacetRelevance · facetWeights` — a **prompt-conditioned weighted dot
> product** …
> - **Accumulation, not max** across facets …
> - Relevance is a **continuous coefficient, not a gate** …
> - **Normalization (open):** normalize the prompt vector (emphasis sums to 1) …
> - Rejected: multiplication (too brutal), raw unweighted addition (rewards
>   vague-everywhere over exactly-right).

Note "Rejected: multiplication (too brutal)" — the v1 retriever was pure multiplication
(item 11). No hard filters (§14.4):

> No hard filters anywhere in ranking. A hard filter crushes signal and — worse — gates on a
> *judgment that can be wrong*: a true decision mis-tagged would be silently, totally
> excluded (the loud-failure principle: surface it, never silently drop it).

And the removal of the file-relevance weight (§14.1):

> - **File→Chunk is containment only — it carries NO weight.** The v1 "chunk's relevance
>   to its file" number is removed: its job (demoting filler) is solved at the source by
>   coherence-episode chunking, and what it actually measured — typicality — buries the
>   rare relevant aside.

§14.7 records a measured reason to reject fuzzy product matching:

> Evidence: all 1,514 HERB questions are perfectly spelled with people referenced by
> role, while the product list holds deliberate near-twins (ContentForce/ContextForce,
> CollaborateForce/CollaborationForce, SearchFlow/SearchForce) — so blanket typo-fuzzy
> would conflate real products and is rejected; the exact layer is load-bearing.

### 19. Model contracts — a working draft with nine unsigned items — 2026-06-14 — [UNKNOWN]

`git show 28c95aa:v3/artefact/MODEL_CONTRACTS.md`

> **Working draft — approvals happen per-call, in conversation, schemas shown inline**
> (the doc itself is never the approval).

> **Status (2026-06-14): the tagger OUTPUT schema needs RE-VALIDATION.** It was verbally
> approved 2026-06-13 (calls a/d/f) but that predates the **2026-06-14 facet reframe**: a
> facet is the *relevance coordinate / character of a tag*, not a bucket; retrieval matches
> **same-facet** (prompt.topic↔tag.topic). Call (a) "per-facet contextual-phrase lists" is
> therefore **REOPENED**

The three touchpoints:

> | **Tagger** | build | chunk | `mistralai/mistral-large-3-675b-instruct-2512` (NIM) |
> | **Interpreter** | query | prompt | same LLM (draft call — §5c) |
> | **Embedder** | build + query | phrase tag / prompt phrase | `nvidia/llama-3.2-nv-embedqa-1b-v2` (NIM) |

The inherited invariant that becomes canon:

> - **No numbers cross the model boundary, either direction.** Tag weights are *measured*
>   downstream (mechanism open, §15 of the design doc); the prompt's facet-relevance
>   vector is *derived* from the interpreter's categorical output, never emitted by it.

The tagger output schema as drafted:

> ```json
> {
>   "topic":           ["contextual phrase", "..."],
>   "process":         ["contextual phrase", "..."],
>   "stance":          ["contextual phrase", "..."],
>   "function":        ["decision", "..."],
>   "temporal_stance": ["retrospective", "..."]
> }
> ```

§5 is a sign-off checklist of nine judgment calls; **six are still `open`** and one is
`REOPENED` at the last commit that touches this file. This document is the last state of
the facet design recorded in git.

### 20. Tagger model choice, revision two — 2026-06-15 — [UNKNOWN]

`git show 28c95aa:v3/artefact/DESIGN.md` §11

> - **Tagger model: `mistral-large-3-675b-instruct-2512`.** The deciding axis for facet
>   tagging is Swedish semantic fidelity (the Bonnier dataset) — stance / process /
>   communicative-function must be read correctly, not just tokenized — and the
>   European-trained Mistral family carries Swedish better than the China-trained
>   alternatives.

But §12 in the same file defers the dataset that rationale rests on:

> **Scope (2026-06-13): the build and eval are HERB-only for now.** Bonnier … is
> **deferred** to a later phase

See C-10.

### 21. The built tagger — facets abandoned — 2026-06-28 — [UNKNOWN]

`git show 8a640bf:v3/artefact/tag.py`

> ```python
> """Stage 5: tag — one stateless structured call per chunk emits contextual
> phrase tags (design §9.5).
>
> The model emits phrases only: no numbers, no description, no facets (facets are
> measured later over the finished tag corpus). …
> """
>
> TAGGER_MODEL = "z-ai/glm-5.1"
>
> _TAGS_SCHEMA = {
>     "type": "object",
>     "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
>     "required": ["tags"],
> }
>
> SYSTEM = (
>     "You read one chunk of source material and emit contextual phrase tags. "
>     "Each tag is a short phrase naming a salient, distinct thing the chunk is "
>     "about — a theme a reader would say it covers, not every sub-point or "
>     "passing mention. Prefer a handful of strong tags over an exhaustive list, "
>     "and collapse closely-related points into one. Never emit an id, a date, a "
>     "number, or a bare name as a tag."
> )
> ```

The design's §13.5 per-facet specs, closed enums, and interpreter mirrors are reduced to
one sentence; the facet dimension disappears from the model contract entirely. The
MUST-NOT list survives in compressed form. The model is a third choice, undocumented.
See C-7 and C-10.

The graph store, by contrast, implements §7 faithfully —
`git show 6730d13:v3/artefact/graph_store.py`:

> ```
> """Materialize the artefact graph into Neo4j: `Source -[:CONTAINS]-> File
> -[:CONTAINS]-> Chunk -[:HAS_TAG]-> Tag` (design §7, §14.1). A fresh, clean
> database — never herb-eval (the superseded, oracle-contaminated v1 build).
> ```
> ```python
> DB = "herb-v3"
> ```

### 22. The fourth facet set — the content profile — 2026-06-27 — [UNKNOWN]

`git show 8a640bf:docs/research/2026-06-27-facet-derivation-methods.md`

A 659-line literature survey, compiled under a new constraint:

> A literature catalog of every method found for **assigning per-facet semantic structure to an
> already-built corpus of short phrase-tags (each ≤ ~12 words) plus their sentence-embeddings**,
> under the constraint that **no generative LLM may create facet values at build time**.

and naming a facet set that appears nowhere before it:

> > **Target facets** (the v3 artefact "content profile"): `process/activity`,
> > `information-kind` (definition / example / metric / argument / procedure / case_study /
> > raw_data), `entity-type` (person / org / product / system / place), plus `centrality`
> > (topic-as-degree — how central a tag is to its chunk vs its sibling tags).

Three architectural paths are laid out (named axes / emergent structure / query-time
projection). This is where "facets are measured, not emitted" becomes a research programme.
See C-6 for what is remarkable about this particular list.

### 22b. The three-arm eval harness — 2026-06-23 — [UNKNOWN]

`git show 0733a9d:v3/README.md`

The comparison's central methodological commitment — arms share the corpus and nothing
else:

> Three arms:
> - **artifact** — the v2 graph (interpreter → facet retrieval → answer). The system under test.
> - **lucene** — BM25 baseline. Its own index over the corpus.
> - **vector** — dense / naive-RAG baseline. Its own index over the corpus.

> the arms share **nothing** — each reads, indexes and retrieves
> the corpus with its own code (how it does so is what the comparison measures); they
> share no retrieval code with each other, and nothing with the artefact.

Two scorers were planned; only one was built (C-17):

> ## Two scorers, on purpose
> - **HERB** (`eval/herb.py`) — … Exact, leaderboard-comparable. **The anchor.**
> - **RAGAS** (`eval/ragas.py`) — the multidimensional lens. … The
>   deterministic backbone is **ID-based** context precision/recall against the gold
>   citations (`IDBasedContextPrecision` / `IDBasedContextRecall`, no judge); the
>   judged picks are faithfulness + **response relevancy**.

Question-set construction, including the id-minting scheme and the counts:

> HERB ships no question id, so `build_questions.py` mints `<product>::a|u::<index>` and
> writes the full set (`{id, question, type, ground_truth, citations}`, a/u lives only in
> the id) to `data/questions.jsonl` … `build_question_sets.py` writes the
> `{id, type, question}` id-set views to `output/`: full / answerable / unanswerable
> (1514 / 815 / 699) plus `question_ids.gold100.jsonl` — the **gold-100**, a balanced
> answerable subset drawn by seeded round-robin over the HERB types (equal allocation,
> ~20/type).

**And a validity caveat stated at construction time**, which is the single most
responsible sentence in the eval design:

> Equal allocation keeps every type usable per-type; it does not match HERB's
> natural mix, so report per-type and don't compare the gold-100 aggregate to HERB's
> published average.

Other decisions recorded under "## Decided":

> - **Generation and scoring are separate phases** (`questions` / `evals` / `full`), so
>   iterating a scorer never re-runs the generator. The `questions` record is
>   **oracle-free**; `evals` re-joins `type` + `ground_truth` + `citations` by id …
> - **Per-question telemetry is split**: `ArmOutput.generator` (the shared answer-writer,
>   identical across arms) vs `ArmOutput.retrieval` (the arm's OWN retrieval-time model cost …)
> - **Provenance** is two manifests — `RunManifest` … + `EvalManifest` …; no seed, no git-sha.
> - Oracle read in place from raw; pipelines blind to it.

Note "no seed, no git-sha" is recorded as a *decision*, not an oversight — runs are not
reproducible to a commit by design.

At `git show 8a640bf -- v3/README.md` the judged metric set changes without comment in the
message:

> -  judged picks are faithfulness + **response relevancy**. …
> +  judged picks are **faithfulness, answer correctness, context precision, and
> +  context recall**. Faithfulness needs no reference, so it transfers to a no-gold
> +  set later; the other three lean on the gold answer / citations.

### 22c. The lucene baseline — 2026-06-21 — [UNKNOWN]

`git show a45292f` (commit message, one of the few long non-footer messages by "Joakim")

> - pipelines/lucene.py: bm25s Lucene-variant BM25 (k1=0.9, b=0.4, EN stopwords +
>   Snowball stem). Ingest flattens each HERB artifact to one {id,title,contents}
>   doc, native id preserved; artifacts-only index (all 17,087 gold citations
>   resolve to an artifact id). Returns ArmOutput; prepare attaches BuildStats.
>   Reads only id/question (truth quarantine by convention).

> Verified end-to-end on the real corpus (38,540 units). Not yet reviewed via
> /critical-review or refresh_graph (run on dev machine).

`k1=0.9, b=0.4` are the standard Lucene defaults, so unlike α and the 0.50 cutoff (C-15)
they carry an external warrant even though none is cited. Note the honest self-report that
the change is unreviewed. Note also "truth quarantine **by convention**" — the arm is
trusted not to read the oracle rather than prevented from doing so, which is weaker than
the structural quarantine `derive_corpus.py` gives the corpus (item 16).

### 23. The shipped artefact arm — 2026-07-12 onward — [UNKNOWN]

`git show 6730d13:v3/pipelines/artefact_v1.py` (docstring, lines 1–105)

> ```
> """artefact_v1.py — the ARTEFACT-V1 arm: query-relative fuzzy cluster retrieval
> over the Neo4j `herb-eval` graph (the v1 artefact build), scored head-to-head
> with the lucene and vector arms under the same shared generator and RAGAS eval.
>
> The graph under test is `Source -[:CONTAINS]-> File -[:HAS_CHUNK]-> Chunk
> -[:HAS_TAG]-> Tag`, holding no content — structure, weights, and embeddings
> only. Each `HAS_TAG` edge carries `w_chunk`, `w_facets`, `facets`, and
> `run_id`.
> ```

The retrieval design it implements — the user's "query-relative areas":

> ```
>   1. interpret — two Claude Haiku passes. Pass 1 emits a self-contained
>      statement of the information need plus the prompt parts … Pass 2 scores
>      each part across five facets (topic, entities, activity, temporal, evidence).
>   2. levels — each part is embedded and gathers its local tag pool from
>      `tag_emb` over a doubling sequence of kNN levels. Multi-k support: every
>      level contributes fuzzy k-NN weight (inverse squared distance, Keller et
>      al. 1985) … The pool's tags then cluster by their embedding
>      distances TO EACH OTHER (average-linkage): the part anchors at its
>      highest-support tag, and the anchor's containing-cluster chain through
>      the dendrogram — finest to coarsest — is the part's widening levels …
>   3. walk — every part's anchor level opens unconditionally … Widen only
>      while the distinct-chunk pool is still short of the caller's k …
>      Hard stop at k; no answer-sufficiency oracle.
> ```

The value model, with every coefficient exposed:

> ```
>      Value scores on one scale, identical in both regimes. Each of the three
>      paths — tag areas, description lookups, stated scope — gives a chunk a base
>      … and min-max normalizes that base over its own candidate pool. Priority
>      modifiers lift the normalized base by an exposed strength `s` as
>      base × (1 + s·(m − 1)): the tag path's facet agreement, `w_chunk` and
>      `relevance_to_file`, the description path's hint-match factor, the scope
>      path's match fraction — each a boost, never a filter. The three lifted
>      scores combine as a weighted sum (`W_TAG` / `W_DESC` / `W_SCOPE`) over the
>      union … Every coefficient — the three path
>      weights and the per-modifier strengths — is read from the environment
>      (RETRIEVAL_FLAGS) so a run documents and sweeps its own value model.
> ```

The order-of-operations principle, which is a genuine user concept:

> ```
>   Structure enters by order of operations: what the query STATES resolves
>   before what the interpreter reads into it. Stated scope (product / section
>   / channel / employee_id / years — extracted only when explicitly named) is
>   its own path whose pool is the matching chunk set — no clustering, nothing
>   fuzzy about a stated fact.
> ```

This arm is honest in its own docstring about what it runs on. Its conflict is with the
canon around it, not with itself — C-2, C-5, C-13.

---

## Part 3 — Contradictions and silent drops

**Sequenced by how much each matters, not by number.** IDs are fixed at discovery so they
stay stable as citations — C-16/C-17/C-18 were found last but rank above C-13/C-14/C-15,
so they appear there. "Silent" means the change is not mentioned in the commit message and
not recorded in a design doc at the time it happened.

Reading order as it appears below: C-1 · C-2 · C-3 · C-4 · C-5 · C-6 · C-7 · C-8 · C-9 ·
C-10 · C-11 · C-12 · C-16 · C-17 · C-18 · C-13 · C-14 · C-15.

### C-1 — D10 reversed: content-in-graph → references-only *(documented reversal)*

- **Then:** `git show dba1160:docs/architecture.md` — "D10 … `(:Chunk).content` stores the
  chunk text … Storing content makes the graph self-sufficient. **Status.** Active."
- **Now:** `git show 296fc40:docs/v2_artefact_rebuild_design.md` — "The v1 chunker
  violated this: it consumed each record, rendered it to a prose string, stored the string
  as `c.content`, and that lossy derivative became the only surviving copy."
- **Verdict:** a *reversal*, not a drop — argued and evidenced. Listed because the
  decision log entry D10 was never updated or retracted in place; it still reads
  "Status. Active" in every ref that carries it, including `28c95aa:v1/docs/backend/architecture.md`.

### C-2 — The v2 design declared all v1 eval numbers invalid; the shipped arm is the v1 graph

- **Declared:** `git show 296fc40:docs/v2_artefact_rebuild_design.md` §12 — "Every run in
  `run data/` … was produced against the v1 graph, whose retriever multiplies seven
  factors at query time and whose vocabulary is polluted. **Those numbers measure the v1
  violation, not the intended product.** The HERB evaluation is re-run on the v2 graph for
  thesis numbers."
- **Shipped:** `git show 6730d13:v3/pipelines/artefact_v1.py` line 2 — "over the Neo4j
  `herb-eval` graph (the v1 artefact build)"; line 117 —
  `DATABASE = os.environ.get("NEO4J_DATABASE", "herb-eval")`.
- **And canon agrees it shouldn't be:** `git show 6730d13:CLAUDE.md` — "**`herb-eval`
  (Neo4j) is the prior artefact build under the superseded design** — a contrast/forensic
  baseline only, **not adopted**."
- **Verdict:** the largest live contradiction in the repo. Every artefact number produced
  from 2026-07 onward comes from the graph three separate documents say must not be the
  product under test. Note the drift is in the *canon*, not the code: at
  `git show 0efff16:CLAUDE.md` the rule read "**`herb-eval` is the canonical Neo4j DB**".
  The code kept running herb-eval while the canon around it flipped from "canonical" to
  "not adopted" — and nothing reconciled them.

### C-3 — The controlled canonical vocabulary was deleted with no mention

- **Then:** `git show dba1160:clustering/canonical_seed.yaml` — five dimensions, 30 seeded
  labels, plus `:CanonicalTag` / `:CanonicalTagProposal` nodes, an `OBSERVED_IN` edge, a
  `canonical_id` edge property, a `--skip-canonical-seed` flag, `seed_canonical_tags()`,
  and a documented promotion path via `python -m clustering.review`.
- **Gone:** `git show 399ee32 -- backend/clustering/canonical_seed.yaml`
  → `1 file changed, 49 deletions(-)`. `git show 399ee32 -- backend/scripts/bootstrap_schema.py`
  removes the seeder and the flag.
- **Commit message:** `Rework HERB chunking and tagging frames` — no mention.
- **Only prose trace:** one substituted table cell in `architecture.md`: "Future HERB query
  views. The old canonical seed vocabulary has been removed."
- **What was not updated:** D2, D3 and D4 in the same file continue to specify
  `canonical_id`, the proposal flow, and cluster-on-edge as **Status: Active**. Confirmed
  still present at `git show 28c95aa:v1/docs/backend/architecture.md`.
- **Verdict:** genuine silent drop. An entire subsystem (controlled vocabulary + human
  triage loop) left the design with a one-cell edit, and its decision-log entries were
  left standing.

### C-4 — Six of eight node labels and four of seven edge types disappeared

- **Then:** `git show dba1160:docs/graph_schema.md` — `:Source`, `:File`, `:Chunk`,
  `:Tag`, `:CanonicalTag`, `:CanonicalTagProposal`, `:WorkItem`, `:Run`; edges
  `CONTAINS`, `HAS_CHUNK`, `NEXT`, `HAS_TAG`, `TAGGED`, `TARGETS`, `OBSERVED_IN`.
- **Now:** `git show 28c95aa:v3/artefact/DESIGN.md` §7 — "The graph is
  `Source → File → Chunk → Tag`. **Nothing else is a node.**"
- **Verdict:** the loss of `:CanonicalTag` / `:CanonicalTagProposal` is C-3. The loss of
  `(:File)-[:TAGGED]->(:Tag)` (the deterministic file rollup, with its
  `weight_global = sum(coalesce(c.relevance_to_file, 0.5) * r.weight_local) / count(c)`
  formula) and of `(:Chunk)-[:NEXT]->(:Chunk)` (the sequential-continuity link that D1's
  dispatch-mode design depended on) is **not discussed anywhere**. §7 argues at length
  about entity nodes and record nodes; it never mentions `TAGGED` or `NEXT`. Silent.

### C-5 — "The chunk description is dead" — except in the arm that ships

- **Killed:** `git show 28c95aa:v3/artefact/DESIGN.md` §9.1 — "there is no description,
  decided 2026-06-11"; §14.1 — "There is **no chunk description**; the union of a chunk's
  phrase tags is its semantic representation." Canon repeats it:
  `git show 6730d13:CLAUDE.md` — "The chunk description is dead."
- **Alive:** `git show 6730d13:v3/pipelines/artefact_v1.py` — the retrieval walk runs "a
  description lookup: the same fuzzy multi-k mechanism over `chunk_desc_emb`,
  chunk-level", and one of the three fused ranking paths is literally the description
  path with its own weight `W_DESC`.
- **Verdict:** the canon rule and the shipping code are in direct opposition. Both are
  current at HEAD.

### C-6 — The condemned v1 facets returned under new names

- **Condemned:** `git show 18d11df -- docs/v2_artefact_rebuild_design.md` §13.1 — the v1
  facets "`temporal` → date strings, `entities` → identifier strings, `evidence` → links
  … the root of the ~18 % junk vocabulary". §13.4 then relocates them:
  "**Structure / hard fields (EXACT):** … exactly the v1 'junk facets'
  (entities/temporal/evidence) relocated to where they belong."
- **Returned:** `git show 8a640bf:docs/research/2026-06-27-facet-derivation-methods.md` —
  the target facet set is "`process/activity`, `information-kind` (definition / example /
  metric / argument / procedure / case_study / raw_data), `entity-type` (person / org /
  product / system / place), plus `centrality`".
- **The match is exact.** `information-kind`'s value list is character-for-character the
  v1 `evidence` facet's definition from
  `git show 415148d:backend/docs/herb_tagging_schema.md`: "evidence | Kind of
  information: definition, example, metric, argument, procedure, case_study, raw_data".
  `entity-type` (person/org/product/system/place) is the v1 `entities` facet
  ("Named people, organisations, products, systems, places"). `centrality`
  ("how central a tag is to its chunk vs its sibling tags") is `w_chunk`, which
  `herb_tagging_schema.md` defines as "derived chunk centrality".
- **Verdict:** three of the four "content profile" facets are the two facets §13.1
  condemned plus the weight §14.1 removed, renamed. The 06-27 document does not
  acknowledge the return, cite §13.1, or explain why the same dimensions are now sound.
  Whether this is a considered reversal (measuring them geometrically instead of asking
  the model may genuinely fix the failure mode) or an unnoticed loop **cannot be told from
  git** — nothing argues it either way. Flagged because it is precisely the pattern being
  hunted.

### C-7 — The per-facet extraction spec was fully written and never built

- **Specified:** `git show 28c95aa:v3/artefact/DESIGN.md` §13.5 — five facets, each with
  emits / MUST-NOT / interpreter mirror; two closed enums; "This is what the v2 tagger
  prompt encodes per facet — the missing spec that caused v1 degradation."
  `git show 28c95aa:v3/artefact/MODEL_CONTRACTS.md` §1 gives the exact five-key JSON
  output schema. §16 calls this "**The one design blocker** before any run".
- **Built:** `git show 8a640bf:v3/artefact/tag.py` — output schema is
  `{"tags": ["..."]}`, a flat list. The docstring: "no facets (facets are measured later
  over the finished tag corpus)".
- **Verdict:** the most carefully specified artifact in the repo — an allocation table, a
  seven-tradition literature review, per-facet MUST-NOT rules, closed enums, an
  interpreter mirror, an explicit "this is the thing v1 lacked" — was superseded by a
  single-paragraph prompt. Git records the *reopening* (MODEL_CONTRACTS §5 call (a),
  "REOPENED 2026-06-14") but **not the resolution**: no commit explains the move from
  "the tagger emits per-facet phrase lists" to "facets are measured later over the
  finished tag corpus".

### C-8 — Entity decomposition specified, then reversed *(documented)*

- **Then:** `git show 296fc40:docs/v2_artefact_rebuild_design.md` §7 — "Faithful
  decomposition = every object → a node, every scalar attribute → a property"; §10
  specifies `:Employee`, `:Customer`, `:PrAuthor`, `:REPORTS_TO`, and §9 specifies
  `:COVERS` edges.
- **Now:** `git show 28c95aa:v3/artefact/DESIGN.md` §7 — "This replaces the earlier draft
  in which every object became a node (Message/PullRequest/Employee entity nodes, COVERS
  edges) — that draft mirrored the dataset into the graph, which is the copies disease at
  the node level."
- **Verdict:** properly documented reversal. Listed only because it is the *largest*
  design element ever discarded, and because it left residue — see C-9.

### C-9 — DESIGN.md contradicts itself in two places at the same commit

Both from `git show 28c95aa:v3/artefact/DESIGN.md`:

- §7: "Nothing else is a node … Records are NOT nodes … Metadata directories … are NOT
  nodes." §14.1 restates the spine.
- §9.5, in the same file: "**No overlap.** Overlap fights references-not-copies and
  dirties the `:COVERS` edges — the same record in two chunks would be double-tagged."
  `:COVERS` was abolished by §7.
- §9.6, same file: "IDs, dates, and authors are now structural (**entities + properties**)"
  — entity nodes were abolished by §7.
- **Verdict:** unremoved residue of the superseded draft, inside the current design
  reference. Both sentences still read as if the reversed design were live. This is the
  exact failure mode CLAUDE.md's "docs track reality … by removal of dead content" rule
  exists to prevent.

### C-10 — Three tagger-model decisions, each superseding the last; the final one undocumented

| Ref | Reproduce | Model | Stated basis |
|---|---|---|---|
| 05-30 | `git show 296fc40:docs/v2_artefact_rebuild_design.md` §11 | `deepseek-ai/deepseek-v4-pro` | "chosen by benchmark (reliable HTTP 200, valid JSON, consistent latency)" |
| 06-15 | `git show 28c95aa:v3/artefact/DESIGN.md` §11 | `mistral-large-3-675b-instruct-2512` | "the deciding axis … is Swedish semantic fidelity (the Bonnier dataset) … the European-trained Mistral family carries Swedish better than the China-trained alternatives" |
| 06-28 | `git show 8a640bf:v3/artefact/tag.py` | `z-ai/glm-5.1` | none in git |

Three compounding problems:

1. The 06-15 rationale rests on Bonnier, which **§12 of the same file defers**: "Scope
   (2026-06-13): the build and eval are HERB-only for now. Bonnier … is **deferred**."
   The deciding axis for the choice was, at the moment of the choice, out of scope.
2. The built model `z-ai/glm-5.1` is China-trained — the category the 06-15 rationale
   rules out — and no commit updates §11 or explains the change.
3. The interpreter multiplies the divergence: MODEL_CONTRACTS §0 says the interpreter is
   "same LLM" (Mistral Large); `git show 6730d13:v3/artefact/interpreter.py` line 25 says
   `INTERPRETER_MODEL = "meta/llama-3.3-70b-instruct"`; and the arm actually run,
   `git show 6730d13:v3/pipelines/artefact_v1.py` line 121, says
   `INTERPRET_MODEL = "claude-haiku-4-5"`.

### C-11 — Six commits of measured results were squashed away

- `git log -1 --format='%h parents=%p' 5706520` → `5706520 parents=922d0cb` (single parent
  — not a merge), yet `git rev-parse 8b320ac:backend/evaluation/ragas_eval.py` and
  `git rev-parse 5706520:backend/evaluation/ragas_eval.py` are the same blob.
- The six squashed-away messages (`git log origin/jockedev2`) carry the only record of
  several findings, including one that cuts against the project's thesis
  (`git show 8b320ac`):

  > Findings (n=100 lookup gold, n=15 multi-hop proxy; QA excluded, temp 0,
  > judge=sonnet, paired): on lookup questions baseline >= graph
  > (faithfulness 0.88/0.84, recall 0.47/0.34). On the multi-hop proxy the
  > direction flips (recall graph 0.28 vs base 0.13, precision 0.14 vs 0.07)
  > but the gain is concentrated in pr-relational questions (recall
  > 0.06->0.69); person/company aggregation fail in both arms. Effect is
  > question-type-dependent — **not a general graph win.**

  and (`git show 0b98b12`):

  > System is faithful but retrieval is the bottleneck. Recall is bimodal
  > (54/99 = 0, 35/99 >= 0.5), split by question type …

- **Verdict:** `5706520`'s body is empty. A reader of the trunk sees "Add HERB RAGAS
  evaluation harness" and none of the six measured results, none of the six
  `Co-Authored-By` footers, and no hint that the comparative finding was negative. The
  data survives only because `origin/jockedev2` was never deleted.

### C-12 — "Seven factors": the claim is **correct** *(checked, not a contradiction)*

Recorded because it looked like a discrepancy and is not — the check is worth keeping.

- **Claim:** `git show 296fc40:docs/v2_artefact_rebuild_design.md` §12 — "the v1 graph,
  whose retriever **multiplies seven factors** at query time". Repeated verbatim at
  `git show 28c95aa:v3/artefact/DESIGN.md` §12.
- **Design-time record (05-14/05-15), five factors:**
  `git show 415148d:backend/docs/query_interpretation_layer.md` —
  > ```text
  > score += query_tag.w_query
  >        * query_tag.facets[facet]
  >        * chunk_edge.w_chunk
  >        * chunk_edge.w_facet
  >        * coalesce(chunk.relevance_to_file, 1.0)
  > ```
  and identically in `git show 4ab34b4:memory/project_architecture.md`.
- **As actually shipped (05-28), seven factors:**
  `git show 54bc1a4:frontend/src/services/retrieval.ts` —
  > ```js
  >     : `qt.w_query * facetScore * r.w_chunk * r.w_facet
  >          * coalesce(c.relevance_to_file, 1.0)
  >          * qt.sim
  >          * coalesce(qt.scopeWeight, 1.0)`;
  > ```
  Count: `w_query` · `facetScore` · `w_chunk` · `w_facet` · `relevance_to_file` ·
  `sim` · `scopeWeight` = **seven**.
- **Verdict:** the design doc's charge is accurate. The two extra factors — the grounding
  cosine `qt.sim` (added by `452fa5d`, embedding-based grounding) and `qt.scopeWeight` —
  arrived between 05-15 and 05-28. The apparent conflict was an artifact of comparing
  documents from different dates. **No contradiction.**

### C-16 — "No hard filters anywhere in ranking" — written against a v1 that was full of them

- **v1 as shipped:** `git show 54bc1a4:frontend/src/services/retrieval.ts` — the scoring
  Cypher gates on five separate conditions before anything is ranked:
  > ```cypher
  >   AND r.run_id = $runId
  >   AND r.facet IN $activeFacets
  >   AND (qt.facet = 'all' OR r.facet = qt.facet)
  >   AND coalesce(r.w_chunk, 0.0) >= $minWChunk
  >   AND coalesce(c.relevance_to_file, 1.0) >= $minRelevanceToFile
  >   ${gate}
  >   ${exclude}
  > ```
- **v2 stance:** `git show 28c95aa:v3/artefact/DESIGN.md` §14.4 — "No hard filters
  anywhere in ranking. A hard filter crushes signal and — worse — gates on a *judgment
  that can be wrong*: a true decision mis-tagged would be silently, totally excluded."
- **Verdict:** a *justified reversal*, listed for completeness because it is the third
  major v1→v2 stance flip (with C-1 and C-8) and the only one whose v1 target is
  verifiable line-by-line. It also shows the v2 design was written against the real code,
  not a caricature of it — `minWChunk` and `minRelevanceToFile` are exactly the
  "gates on an uncertain judgment" §14.4 describes.

### C-17 — The leaderboard-comparable anchor metric was specced, stubbed, then deleted

- **Promised:** `git show 0733a9d:v3/README.md` — a section headed "## Two scorers, on
  purpose":
  > - **HERB** (`eval/herb.py`) — the dataset's own scoring: per-type set-F1
  >   (person/url/pr/company), a 0–100 judge for content, abstention for
  >   unanswerables. Exact, leaderboard-comparable. **The anchor.**

  and listed under the README's "## Decided" heading:
  > - Both scorers (HERB anchor + RAGAS lens).
- **Never implemented:** `git show 0733a9d:v3/eval/herb.py` is a 45-line stub — six
  function signatures with docstrings and a bare `...` body each:
  > ```python
  > def f1_over_sets(predicted, gold):
  >     # set precision/recall/F1 -> value + components (tp/fp/fn, the two sets).
  >     # linked to: extract_answer_items (input); build_eval_result (output)
  >     ...
  > ```
- **Deleted:** `git show 8a640bf --stat --format='' -- v3/eval/` → `v3/eval/herb.py | 45 ----`.
  `git ls-tree 6730d13 v3/eval/herb.py` → `fatal: path … does not exist`.
- **Docs did track it** — the same commit rewrote the README section to "## Scoring with
  RAGAS" and dropped `herb.py` from the file list. That part is clean.
- **Verdict:** the drop is real and consequential even though the doc edit was honest.
  The metric described as "**The anchor**" and "leaderboard-comparable" — the only planned
  measure that would let this work be compared against HERB's published results — was
  never written and then removed. Consequence: **every number the project reports is
  RAGAS-only**, and none is comparable to the benchmark's own leaderboard. No commit
  message, doc, or comment anywhere in git gives a reason for the removal, and the
  deletion is carried in a commit titled `feat: update graphify-out (533 files)`.

### C-18 — Design-bearing changes routinely hidden under tooling commit messages

Not a design contradiction — a record-keeping one, and it is why several items above were
nearly missed. Four commits authored `Objuret` carry auto-generated subjects and a
"changed files:" list mechanically truncated at ten entries, while shipping the most
consequential code in the project:

| Commit | Subject | What it actually contains |
|---|---|---|
| `4da9c5b` | `feat: update graphify-out (213 files)` | first `v3/eval/herb.py`; `CLAUDE.md` +82 |
| `0733a9d` | `feat: update graphify-out (76 files)` | `v3/README.md` +128 (the whole harness design), `contract.py`, `build_questions.py`, `build_question_sets.py`, `data/questions.jsonl` |
| `8a640bf` | `feat: update graphify-out (533 files)` | **`v3/artefact/tag.py`** (the tagger — §16's "one design blocker"), `chunk.py`, `DESIGN.md` +38/−22, the 659-line facet-derivation survey, **deletion of `v3/eval/herb.py`**, `CLAUDE.md` +152 |
| `a515c94` | `feat: update v3 (48 files)` | `v3/artefact/interpreter.py` (+278), `v3/pipelines/artefact.py` (+322), deletion of `v3/pipelines/artifact.py` |
| `69115e0` | `feat: update graphify-out (49 files)` | **`v3/pipelines/artefact_v1.py`** (+666) — the arm that produces every reported artefact number |

Reproduce any row with `git show <sha> --stat`. The subjects are tool output, not
authorship claims, but the effect is that the repository's own history does not surface
its most important changes.

### C-13 — "The model emits no numbers, ever" vs the arm that ships

- **Canon:** `git show 6730d13:CLAUDE.md` — "**The model emits no numbers, ever** (tagger
  and interpreter)." Present unchanged in every CLAUDE.md from `0efff16` onward
  (verified: `git show <ref>:CLAUDE.md | grep -c 'no numbers'` → 1 at `0efff16`,
  `4da9c5b`, `0733a9d`, `8a640bf`, `5006fed`, `c33594d`, `6730d13`).
  MODEL_CONTRACTS §0 states it as an inherited invariant: "No numbers cross the model
  boundary, either direction."
- **Shipped:** `git show 6730d13:v3/pipelines/artefact_v1.py` — the interpreter's pass 2
  prompt is "Score retrieval tags against five facets (each 0.0-1.0)" returning
  `{"scores":[{"t":"tag","facets":{"topic":0.0,"entities":0.0,"activity":0.0,"temporal":0.0,"evidence":0.0}}]}`,
  and the response validator raises `ValueError` if a facet value "is not a number".
- **Verdict:** the rule holds for the *v3 tagger* (`tag.py` emits phrases only) and is
  violated by the *arm under test*. Canon is written as if the v3 artefact were the
  system being measured; it is not.

### C-14 — Canon describes a build state that no longer exists

`git show 6730d13:CLAUDE.md`:

> The graph proper — chunk → tag → facet retrieval — is the unbuilt part;
> `pipelines/artifact.py` is the arm entry that drives it.

Two errors, both checkable:

1. `pipelines/artifact.py` **does not exist**. `git ls-tree -r 6730d13 --name-only | grep v3/pipelines/`
   returns `artefact.py`, `artefact_v1.py`, `artefact_v1_det.py`, `hybrid.py`,
   `lucene.py`, `vector.py`. The `artifact.py` spelling was deleted at `a515c94`
   (`v3/pipelines/artifact.py | 48 -`) and replaced by `artefact.py` (+322).
2. "chunk → tag … is the unbuilt part" is false: `git ls-tree -r 6730d13 --name-only`
   shows `v3/artefact/chunk.py`, `tag.py`, `index.py`, `graph_store.py`, `prepass.py`,
   `interpreter.py`, plus `tests/test_chunk.py`. Only the **facet** layer is genuinely
   unbuilt.

### C-15 — Two constants that no artifact in git ever derives

- `α = 0.25` and `MULTI_FACET_THRESHOLD = 0.50`, both from
  `git show 415148d:backend/docs/herb_tagging_schema.md`. α gets a directional rationale
  ("softens the spread bonus so it complements strength rather than dominates it");
  the 0.50 cutoff gets none. Neither is swept, and both are load-bearing on 255,288
  edges (`git show 415148d:backend/docs/pilot_full_herb_report.md`).
- `CAP_TOKENS = 3000` is the counter-example and the standard the others should be held
  to: `git show 28c95aa:v3/artefact/DESIGN.md` §9.1 states the value, the mechanism that
  sets it, its comparison to the literature band, and — explicitly — that it is "a
  calibration seed, not a verdict" with a named sweep in §15. **The sweep was never run**;
  no commit adds one. So the best-justified constant in the repo is still, by its own
  account, unvalidated.

---

## Part 4 — What git cannot tell you

### G-1 — Prose authorship is not decidable

The [USER]/[AGENT] split above is honest about this. Git records who *committed*, never
who *wrote*. All four author identities are one person. The only hard authorship evidence
is the presence or absence of an AI footer, and footers appear on just eight commits
(`c5c0a42`, `497db9f`, `9114e31`, `7a0ab5e`, `0b98b12`, `8b320ac` — Claude Opus 4.7;
`da25016`, `98bb96a` — Cursor). Every major design document — `architecture.md`,
`graph_schema.md`, `herb_tagging_frames.md`, `herb_tagging_schema.md`,
`v2_artefact_rebuild_design.md`, `DESIGN.md`, `MODEL_CONTRACTS.md` — carries **no**
footer and is therefore [UNKNOWN] as text, however clearly the *decisions* in them are
the user's.

### G-2 — The decision events are outside the repo

`DESIGN.md` and `MODEL_CONTRACTS.md` are dense with dated decisions — "decided
2026-06-11", "decided 2026-06-12", "decided 2026-06-13", "REOPENED 2026-06-14",
"finalized 2026-06-12", "rewritten 2026-06-12". **There is no commit on any of those
dates.** The commit sequence jumps `18d11df` (06-01) → `0efff16` (06-15). Every decision
in that fortnight — the closed spine, the death of the description, per-chunk tag nodes,
the structural oracle quarantine, the mapping-key finalization, the facet reframe —
happened in conversation and arrived pre-formed in one 750-line commit. Git shows the
outcome and the date claimed for it; it shows nothing of the argument, the alternatives,
or who proposed what.

### G-3 — The state-transfer documents were never committed

`git show 0efff16:CLAUDE.md` points at them by absolute path on a machine that is not
this one:

> 1. **Current entry state doc (read before doing anything else):**
>    `A:\Coding\skills\state\exjobbet\2026-06-14-v2-facets-as-relevance-channels.md`
>    It carries the facets-as-relevance-channels breakthrough and points back to the
>    2026-06-12 / 06-11 / 06-09 docs for spine, mapping-key, literal-matching, and
>    weights canon, and maps which design-doc sections are current vs stale.
> 2. **State doc folder (dated; newest = entry point):** `A:\Coding\skills\state\exjobbet\`
> 5. **Frozen historical handoffs (do not edit):** `A:\Coding\skills\handoff\exjobbet\`

Named-but-absent: the 06-09, 06-11, 06-12 and 06-14 state docs. The 06-14 one is the
direct antecedent of C-7 — it is where "facets as relevance channels" was decided, and it
is the last thing the reopened tagger schema was waiting on. Git holds the reopening and
never the resolution.

### G-4 — Why the built tagger dropped facets

The single most important unanswered question. Git shows: the spec (§13.5, 06-15), the
reopening (MODEL_CONTRACTS §5a, 06-14), and the flat-list implementation (`tag.py`,
06-28). It contains **no** document, comment, or commit message bridging them. The
`tag.py` docstring asserts the new position ("facets are measured later over the finished
tag corpus") without arguing it, and the 06-27 research survey presupposes it in its
opening constraint. The decision itself is not in the repo.

### G-5 — Whether anything was ever run on the v3 artefact

`graph_store.py` targets a database `herb-v3` that no commit demonstrates was populated.
Every eval output directory committed under `v3/output/` belongs to `artefact_v1`,
`lucene`, `vector` or `hybrid` (see `git show 7879dfe --stat`). Git cannot tell whether
the v3 chunker and tagger were ever run over the full corpus, only that the code to do it
exists and its unit tests pass (`28c95aa`: "Tests run from v3/ … — 16 pass").

### G-6 — The corpus arrived as a stash, not a commit

`git show 4ac74c0 --stat` shows `data/Salesforce__HERB/` (35 files, 1,550,956 insertions)
in a `refs/stash` object unreachable from any branch. How the benchmark data got onto the
machine, and whether the working copy matches the published release, is outside git.

### G-7 — *(closed)* The v1 frontend retrieval was read; C-12 resolved

Settled by `git show 415148d:backend/docs/query_interpretation_layer.md` and
`git show 54bc1a4:frontend/src/services/retrieval.ts`. See Part 2 items 7b/7c and C-12.
What remains genuinely unknowable: the intermediate revisions of `retrieval.ts` between
05-18 and 05-28 are recoverable, but *why* `scopeWeight` was introduced is not — no
commit message or doc mentions it.

### G-8 — Deleted history is unrecoverable

`c2fabbb` removed the entire `docs/thesis/` tree from tracking ("disk copies kept") and
gitignored it. `0efff16` deleted the pilot tagging-run dumps
(`backend/data/tagging_runs/pilot_001/`, 1,167 lines including the 781-line HANDOFF, and
`pilot_format_smoke/run.json`) and `.work/herb_mapping_draft.yaml`. Those blobs remain
reachable by SHA, but any later revision of them on disk is gone. Likewise the four
`.claude/worktrees` branches referenced in `4ab34b4` are not in this remote.

### G-9 — *(partly closed)* The eval design is in git; the results' meaning is not

The harness design, the metric set, the question-set construction rule and its
type-balance caveat are all recorded — see Part 2 items 22b/22c and C-17. What git still
cannot supply:

- **Why the HERB anchor metric was dropped** (C-17). No rationale exists anywhere.
- **Which cross-arm comparisons are legitimate.** `7879dfe` ships a `DATA_README` mapping
  metrics to cross-arm validity; this pass read the commit's file list but not that
  document's contents. Its judgements are the project's own and would need reading
  before any number here is quoted comparatively.
- **Reproducibility of any past run.** Recorded as a decision, not an accident:
  `git show 0733a9d:v3/README.md` — "**Provenance** is two manifests … **no seed, no
  git-sha**." No committed run can be tied to the code revision that produced it.

### G-10 — Why the arm under test was never switched

The deepest unanswered question, and the one C-2 turns on. Git shows `graph_store.py`
building a clean `herb-v3` database to the correct spine, and `artefact_v1.py` querying
`herb-eval` instead. It contains no commit, comment, or doc that weighs one against the
other, records a decision to defer the switch, or notes it as debt. The two coexist at
HEAD with no acknowledgement that they compete.

---

## Provenance of this document

Produced from git objects only, in the repo named above. No claim here was taken from
`docs/state/`, from `MEMORY.md`, or from any working-tree file. The prohibited data files
(`questions.jsonl`, `gold100.jsonl`, `heldout100.jsonl`, `10smoke.jsonl`) were not opened;
`questions.jsonl` was line-counted only, to check the `815 + 699 = 1,514` arithmetic in
`derive_corpus.py`.

Commits read for content: all 74 real commits by message and `--stat`; substantive diffs
or full blobs read for `dba1160`, `48fbc9d`, `399ee32`, `415148d`, `4ab34b4`, `b1edf29`,
`54bc1a4`, `5706520`, `8b320ac`, `0b98b12`, `a45292f`, `296fc40`, `18d11df`, `0efff16`,
`0733a9d`, `28c95aa`, `8a640bf`, `a515c94`, `69115e0`, `5006fed`, `c33594d`, `6730d13`.

**Known incompleteness.** Three things were in scope and not read: the `DATA_README`
shipped by `7879dfe` (metric validity — G-9); the 781-line `pilot_001/HANDOFF.md` at
`c858f37`; and the `.work/verify_*.py` forensic scripts at `244beb7`. None of them bears
on a Part 3 item. Every contradiction listed is verified against both refs it cites.

**Structural caveat on Part 3.** Items C-1, C-8 and C-16 are *documented reversals*, not
drops — they are listed because they are large, not because they are faults. The genuine
silent drops are **C-3** (canonical vocabulary), **C-4** (`TAGGED` / `NEXT` edges),
**C-7** (per-facet extraction spec) and **C-17** (the HERB anchor metric). The live
contradictions — where two current things disagree at HEAD — are **C-2**, **C-5**,
**C-9**, **C-13** and **C-14**. C-6 is the one item where git shows a loop but cannot say
whether it was deliberate; it is flagged rather than judged.
