# DESIGN_HISTORY — how this system was actually designed and built

**2026-05-07 → 2026-08-03.** One timeline, fused from two independent forensic records
plus the verbatim user canon. Nothing here is new research and nothing here is a new
conclusion: every statement below already exists in a source record, and arrives with the
citation that record carries.

---

## How to read this file

### The three sources

| Source | Covers | What it can settle |
|---|---|---|
| `docs/canon/raw/git_record.md` | 2026-05-07 → 08-01. 74 commits, 30 refs, 91 `git show` reproduce commands | What existed when, what changed, what was deleted, whether a later state contradicts an earlier one. **Never who wrote prose.** |
| `docs/canon/raw/desktop_docs_record.md` | 2026-05-25 → 07-12. 20 desktop-only agent-written handoff/state docs, 6,719 lines, ~150 recovered user quotes | The decision *conversations* git cannot see — the fortnight git_record's own G-2 calls missing. Second-hand: an agent's report of a conversation. |
| `docs/canon/USER_CANON.md` | 803 verbatim human turns, 05-14 → 08-03, plus 80 recovered rulings | What the user actually said, verbatim. `[CHAT]` is first-hand keystrokes; `[DOC]` is a quote that passed through an agent's transcription. |

Both raw records stay on disk untouched as evidence. This file reorders them; it does not
replace them.

### Citation rule

Every statement below keeps the evidence its source record carried:

- a git claim carries its `git show <ref>:<path>` command, exactly as `git_record.md` gives it;
- a docs claim carries the desktop doc's **filename + heading**;
- a user quote carries **date + the quote**, and where `USER_CANON.md` holds it, that is said
  so the two files stay linked.

A claim without its citation is a defect. If you find one, it is a bug in this file, not a
licence to repeat it.

### Authorship labels — kept from both records

From `git_record.md`: **[USER]** (first-person design voice, terse human commit register),
**[AGENT]** (AI footer, or the mechanical `feat: update <dir> (N files)` tooling format),
**[UNKNOWN]** (undecidable from git — most May/June prose).

From `desktop_docs_record.md`: **[USER-STATED]** (verbatim quote or attributed ruling),
**[USER-STATED — paraphrase]** (attributed ruling, agent's wording), **[AGENT-ASSERTED]**
(proposal, synthesis, or agent-run measurement), **[UNCLEAR]**.

### Precedence when the two records disagree about who decided something

**First-hand chat > git blob > agent-written doc.** A `[CHAT]` turn in `USER_CANON.md`
outranks everything. A git blob proves a thing existed but can never attribute prose. An
agent-written state doc is the only attribution evidence for the two chat blackouts
(05-16 → 05-26 and 05-29 → 06-26) and is used as such — labelled second-hand, never
upgraded silently. Where the records genuinely disagree, both readings appear and the
better-evidenced one is named. The unsettled ones are collected at the end.

### The era map

| Era | Span | The hinge |
|---|---|---|
| 1 | 05-07 → 05-24 | Frames and facets — the system arrives fully designed, and starts shedding parts |
| 2 | 05-25 → 06-14 | The v2 rebuild pivot — references not copies, and the weights stop being emitted |
| 3 | 06-15 → 06-28 | Facet reconciliation and the v3 harness — the spec that was never built |
| 4 | 06-28 → 07-12 | The native artefact build, and its condemnation by its own author |
| 5 | 07-13 → 07-28 | The v1 retrieval engineering era — the forensic arm becomes the product |
| 6 | 07-29 → 08-03 | Audit, corpus, tag-first — and the canon audit that produced these records |

06-28 is a hinge day and appears in two eras: the commits that close era 3 and the
123-turn build session that opens era 4 happen on the same date.

---

# Era 1 — Frames and facets

**2026-05-07 → 2026-05-24**

**Evidence asymmetry, stated up front.** The desktop doc corpus begins 05-25, so it cannot
witness this era at all. `USER_CANON.md` records its first surviving human turn on 05-14
and notes a chat blackout 05-16 → 05-26. Almost everything below therefore rests on git
alone, and prose authorship is correspondingly undecidable.

## What was decided

### The system arrives fully designed — 2026-05-07 — [UNKNOWN]

`git show dba1160:docs/architecture.md`

`dba1160` is not a skeleton: 52 files, 4,846 insertions, a complete Neo4j indexing
pipeline (`indexing/chunker.py` 388 lines, `indexing/orchestrator.py` 559,
`indexing/worklist.py` 310) plus eight design docs. It carries a formal decision log,
D1–D12, each entry structured **Decision • Rationale • Alternatives considered • Status**.

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

D10 is the entry the whole v2 pivot is written against — **C-1**. D2's
`cluster`/`canonical_id` machinery is abandoned inside six days — **C-3**.

The decision log records alternatives and rejects them with reasons; whether the *prose*
is agent-drafted is undecidable, but the *decisions* are clearly owned.

### The original graph spine — 2026-05-07 — [UNKNOWN]

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

Six of the eight node labels and four of the seven edge types are gone by 06-15 — **C-4**.

### The controlled canonical vocabulary — 2026-05-07 — [UNKNOWN]

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
promote). Deleted entirely six days later — **C-3**.

### The cluster-dimension rename — 2026-05-11 — [USER]

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

Labelled **[USER]** by `git_record.md`: a pure rename with a one-line `chore:` message is a
human editorial act, and these are the names the user still uses.
`USER_CANON.md` carries the same commit under **[COMMIT] 05-11** for exactly that reason.

The rename matters more than it looks. The *old* names state what each dimension was
*for* (`information_need`, `time_relevance`); the new names are bare nouns. §13.1 of the
v2 design later diagnoses precisely this loss of specification as the cause of facet
degradation — **C-6**.

### Interpretation frames — the model must not see pipeline machinery — 2026-05-13 — [UNKNOWN]

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

One of its four closing open questions is later decided:

> - Whether float weights should survive, or be replaced by ordinal ranks after
>   the weight anchoring observed in `pilot_001` and `pilot_002`.

Note the design at this date has the agent returning **"description + facet tags +
weights"**. All three are later killed — **C-5**, **C-7**, and the no-numbers rule.

### The tagging contract — the five-facet scoring schema — 2026-05-14 — [UNKNOWN]

`git show 415148d:backend/docs/herb_tagging_schema.md`

The normative model contract of the v1 system. Stages:

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

`α = 0.25` has a rationale but no derivation, and the multi-facet cutoff has neither:

> For each tag, the pipeline writes a `HAS_TAG` edge for the **primary facet**
> (`argmax(facets)`) plus one edge per other facet with `facets[other] >=
> MULTI_FACET_THRESHOLD = 0.50`.

Both are **C-15**. Tag cleaning, with a hardcoded stoplist:

> ```python
> s = raw.strip().lower()
> s = re.sub(r"[^a-z0-9]+", "_", s)
> return s.strip("_")
> ```
> Drop if cleaned name in `FILLER = {"data", "information", "content", "record", "text", "chunk", "item"}`.

### The query interpretation layer — prompt/chunk symmetry — 2026-05-14 — [UNKNOWN]

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

The division of labour:

> The goal is not to let the model write Cypher. The model interprets the prompt
> into a small structured query plan; deterministic code maps that plan to Neo4j
> queries.

The same anti-anchoring move as the chunk side:

> The model should not emit query centrality directly. Code derives it from the
> facet vector using the same formula as HERB `compute_w_chunk` …
> `w_query` means "how important this tag is to the user's information need";
> `w_chunk` means "how central this tag is to a chunk."

**The scorer as designed — five factors:**

> ```text
> score += query_tag.w_query
>        * query_tag.facets[facet]
>        * chunk_edge.w_chunk
>        * chunk_edge.w_facet
>        * coalesce(chunk.relevance_to_file, 1.0)
> ```

with the matching constraint that is the ancestor of the whole later grounding problem:

> Only compare a prompt tag to a chunk edge when the cleaned tag names match, or
> when a later tag-expansion step has explicitly linked them.

Exact-name matching is what `452fa5d` (05-18) replaces with cosine similarity four days
later, adding a sixth factor. This five-vs-seven question is **C-12**.

The answer job is deliberately separated from retrieval:

> `filters` and `answer_job` are not tags. They control what the retrieval code
> is allowed to search and what the answer model should do after retrieval.

> For thesis-safe behavior, the default should be:
> ```text
> evidence_policy = retrieved_only
> missing_evidence_policy = say_insufficient_evidence
> ```

And it records the abandonment of the canonical machinery as an *instruction* rather than
a decision — three weeks before any design doc says so:

> - Do not use old frontend assumptions such as `cluster`, `canonical_id`, or
>   `weightLocal` for HERB retrieval.

### The full-HERB pilot — the empirical basis — 2026-05-14 — [UNKNOWN]

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

This run is declared a success on 05-14 and condemned as ~18% junk vocabulary sixteen days
later — **C-6**. It is also the origin of the whole "measure, don't emit" line the user
later claims as his own: **[DOC] 06-09** *"measure from embeddings was my idea."*
(`USER_CANON.md` §13).

## What was built

| Date | SHA | Author | What landed |
|---|---|---|---|
| 05-07 | `dba1160` … `8c84b86` | Objuret | the initial system, six commits, all trunk |
| 05-08 | `070393f` | Objuret | `chore: restructure project as monorepo` — everything under `backend/`, a `frontend/` React workbench |
| 05-08 | `3acc7f6` | Objuret | `chore: bundle graph export` — a 46 MB `graph_export/grag_graph_latest.zip` |
| 05-11 | `48fbc9d` | Objuret | the cluster rename; **this commit leaves `origin/main` behind** |
| 05-13 | `c858f37` | Objuret | `backend/tagging/pipeline.py` (851 lines) + a 781-line pilot HANDOFF |
| 05-13 | `399ee32` | Objuret | chunker rework (+869 lines), the frames doc, **and the silent vocabulary deletion** |
| 05-14 | `415148d` | Objuret | the tagging schema, the query-interpretation layer, the full-HERB pilot report |
| 05-15 | `b1edf29` | Objuret | `quarantine/` and the browser-direct frontend services |
| 05-18 | `452fa5d` | Joakim Wikman | `Embedding-based prompt-tag grounding + prompt mode` |
| 05-19 | `c301840` | Objuret | e5-small-v2 fp32 bundled locally; embedded graph snapshot refreshed |
| 05-19 | `922d0cb` | Objuret | the Usage canvas becomes the real executor |
| 05-20 | `da25016` | Objuret | SQL-agent baseline; Run Builder exports wired into the RAGAS harness — `Co-authored-by: Cursor`, **[AGENT]**-drafted |
| 05-20 | `98bb96a` | Objuret | thesis alignment docs, gold-100 RAGAS results — also Cursor-footered |

**The `origin/main` side-branch, 05-15.** `48aa84f`, `4ab34b4`, `a6ff064` do **not**
contain `48fbc9d` onward. `4ab34b4` adds `memory/MEMORY.md`,
`memory/project_active_branch.md`, `memory/project_architecture.md` — the only place
Claude memory files were ever committed, and forensically the single most valuable
artifact of the period.

### The v1 retrieval scoring formula, preserved in a memory file — 2026-05-15 — [AGENT], quoting [USER]

`git show 4ab34b4:memory/project_architecture.md`

A Claude memory file (YAML frontmatter, `type: project`) — **[AGENT]**-written, committed
by the user. It is the only surviving record of the v1 query-time scoring formula:

> The two-pass prompt-interpretation method documented in (formerly)
> `backend/docs/query_interpretation_layer.md` is **good** and belongs to the frontend now:
> 1. LLM pass 1: prompt → `{description, flat tags[]}` (same prompt-cleaning rule as HERB extract)
> 2. LLM pass 2: each tag → 5-facet vector (`topic, entities, activity, temporal, evidence`)
> 3. Code derives `w_query` from facets using same `compute_w_chunk` formula as HERB
> 4. Retrieval scoring: `score += query_tag.w_query × query_tag.facets[facet] × chunk_edge.w_chunk × chunk_edge.w_facet × coalesce(chunk.relevance_to_file, 1.0)`
> 5. Plan shape: `{description, tags[], filters, ranking, answer_job, warnings}`
> 6. Answer-job modes: `direct_answer | list | compare | aggregate | summarize`, defaults
>    `evidence_policy=retrieved_only`, `missing_evidence_policy=say_insufficient_evidence`

Same file, the D2/D4 abandonment stated as settled fact:

> 4. Field-name discipline: HERB graph uses `facet`, `w_chunk`, `w_facet`,
>    `relevance_to_file`. Legacy `cluster`, `canonical_id`, `weight_local`,
>    `weight_global` are old generic-tagger fields — do not use for HERB retrieval.

And the clearest **[USER]** fragment in the entire git record, preserved verbatim:

> User explicitly complained: *"i fucking cant understand why the agents always just
> 'kinda clean up' but leave the framework, documentation, scaffolding, some paint on the
> walls etc.. it's such a sloppy fucking mess"*. When cleaning up: actually delete the
> dead stuff. Don't leave empty placeholder dirs, contradictory docs, or orphan caches.

Same file, **[AGENT]**, on the architecture:

> **No HTTP server in the middle. None planned.** …
> - The "agent put all those docs in the backend so something is seriously off" —
>   confirmed: a prior agent built scaffolding (orphan FastAPI, planned-HTTP docs) for an
>   architecture that was never going to ship. Treat any planned-HTTP language as that
>   agent's misunderstanding, not as design.

### The user's own voice in this era

`USER_CANON.md` records the first surviving human turn on **05-14** — *"Can you see and
onboard yourself?"* — and two rulings that predate every design doc discussed above:

> *"i said QUARANTINE the originals, dont fucking toss shit, and REWRITE the "copies", and
> i dont mean "random fucking rewrite" i mean, to match the fact that we are only using
> HERB now"* — **[CHAT] 05-14**

> *"You, what are you doing? What do you think the actual original files were about? … I
> want to save them in a fucking box somewhere and then rewrite the copies of them."*
> — **[CHAT] 05-14**

> *"DUDE WHAT THE FUCK ARE YOU EVEN ARGUING ABOUT, how on earth was any of my instructions
> ambigous!?"* — **[CHAT] 05-15**

> *"i mean, you should keep claude there also, so we can try different models.."* — **[CHAT] 05-14**

These are the earliest evidence of two rules that later become canon: quarantine rather
than delete, and multi-model comparability.

## What diverged

### The canonical vocabulary was deleted with no mention — 2026-05-13 — **C-3**

`git show 399ee32 -- backend/clustering/canonical_seed.yaml` → `1 file changed, 49 deletions(-)`

`git show 399ee32 -- backend/scripts/bootstrap_schema.py` removes `seed_canonical_tags()`,
the `--skip-canonical-seed` flag, and the yaml load. The only prose trace is one
substituted table cell in `git show 399ee32 -- backend/docs/architecture.md`:

> -| **clustering** | … | Canonical tag vocabulary (`canonical_seed.yaml`). Proposal triage (CLI) and named cluster query views are open work — not built. |
> +| **clustering** | … | Future HERB query views. The old canonical seed vocabulary has been removed. |

The commit message says only `Rework HERB chunking and tagging frames`. D2, D3 and D4 in
the same file continue to specify `canonical_id`, the proposal flow, and cluster-on-edge
as **Status: Active** — still present at `git show 28c95aa:v1/docs/backend/architecture.md`.

An entire subsystem — controlled vocabulary plus human triage loop — left the design with
a one-cell edit. **No user statement about it exists in any of the three sources**
(`USER_CANON.md` Part IV.D says so explicitly).

### Two extra scoring factors arrive between design and ship — 2026-05-18 → 05-28 — **C-12**

`452fa5d` (05-18, "Embedding-based prompt-tag grounding") replaces exact-name matching
with cosine similarity and adds `qt.sim`. A second factor, `qt.scopeWeight`, appears by
05-28. Neither the git record nor the desktop corpus nor `USER_CANON.md` can say **why
`scopeWeight` exists** — it is named as a factor to remove and never explained. That gap
is git_record's G-7, and it survives all three records.

### The `jockedev2` RAGAS series is written and then squashed away — 2026-05-19 — **C-11**

Six commits by Joakim Sandström on `origin/jockedev2` (`c5c0a42`, `497db9f`, `9114e31`,
`7a0ab5e`, `0b98b12`, `8b320ac`), each carrying a `Co-Authored-By: Claude Opus 4.7`
footer, build the RAGAS harness, the ground-truth reference evaluation, the n=100 balanced
gold set, and the RQ2 comparative arm.

`git log -1 --format='%h parents=%p' 5706520` → `5706520 parents=922d0cb` — a single
parent, so `5706520` is **not** a merge. Yet `git rev-parse 8b320ac:backend/evaluation/ragas_eval.py`
and `git rev-parse 5706520:backend/evaluation/ragas_eval.py` are the same blob
(`8db798b0…`), as are the two `build_gold_set.py` blobs (`99570033…`). The six commits were
re-landed as one commit with an **empty body**.

What the empty body cost, from `git show 8b320ac`:

> Findings (n=100 lookup gold, n=15 multi-hop proxy; QA excluded, temp 0,
> judge=sonnet, paired): on lookup questions baseline >= graph
> (faithfulness 0.88/0.84, recall 0.47/0.34). On the multi-hop proxy the
> direction flips (recall graph 0.28 vs base 0.13, precision 0.14 vs 0.07)
> but the gain is concentrated in pr-relational questions (recall
> 0.06->0.69); person/company aggregation fail in both arms. Effect is
> question-type-dependent — **not a general graph win.**

and `git show 0b98b12`:

> System is faithful but retrieval is the bottleneck. Recall is bimodal
> (54/99 = 0, 35/99 >= 0.5), split by question type …

A reader of the trunk sees "Add HERB RAGAS evaluation harness" and none of this. The data
survives only because `origin/jockedev2` was never deleted.

### Two undefended constants go into 255,288 edges — **C-15**

`α = 0.25` and `MULTI_FACET_THRESHOLD = 0.50`, both from
`git show 415148d:backend/docs/herb_tagging_schema.md`, are load-bearing on the 255,288
`HAS_TAG` edges reported by `git show 415148d:backend/docs/pilot_full_herb_report.md`.
Neither is swept. The desktop corpus later measures what they actually did — see Era 2.

### Branch topology, for the record

There is one long trunk from `dba1160` (05-07) to `6730d13` (08-01). `origin/main` is
**not** the work line: it carries only `48aa84f`, `4ab34b4`, `a6ff064` (05-15) and stops.
`origin/jockedev` (2 commits, 05-11/05-13) is a dead end — nothing downstream contains it.
`origin/jockedev2`'s six-commit RAGAS series was never merged.

All four author identities — Objuret (43 commits), Joakim Wikman (25), Joakim Sandström
(8), Joakim (1) — are the same person (`git shortlog -sne --all`).

---

# Era 2 — The v2 rebuild pivot

**2026-05-25 → 2026-06-14**

The desktop doc corpus opens here, and with it the design conversations git cannot see.
`USER_CANON.md` records a chat blackout 05-29 → 06-26 covering almost all of this era:
the `[DOC]` quotes below are, for most of these statements, **the only surviving trace**.

## What was decided

### 2026-05-25 — the weight/retrieval redesign, then the audit that shelved it

Three handoffs from one day: two describe the same conversation, the third records a hard
pivot away from it.

**The origin statement for the whole facet programme**, the user's last message before
`/handoff`, in `2026-05-25-middle-layer-weight-redesign.md` §"Suggested next-session approach":

> *"but the point of the multifacets was to give the tag a more semantical weight and
> direction with the facets, how are the facets used now?"* — **[USER-STATED]**

`USER_CANON.md` carries this as **[DOC] 05-25** and makes it the first line of both §1 (the
artefact's intended construction) and §4 (facets). Same doc, §"Facets — design intent vs
current state", the intent behind it:

> "User's original intent: facets give a tag semantic **weight AND direction** — a
> directional/vector enrichment of the tag's meaning." — **[USER-STATED — paraphrase]**

and the degradation:

> "Current implementation degrades this to (a) edge filter, (b) embedding-space picker for
> grounding, (c) double multiplier in the 7-factor product." — **[AGENT-ASSERTED]**
> (verified against code)

**Weights are facts set at index, not synthesized at query** —
`2026-05-25-graph-rag-retrieval-redesign.md` §"Design conversation arc":

> "2. **The retriever should not synthesize weights** at query time. No multiplicative
> compounding of independent signals into a derived score. 3. Weights are facts set at
> indexing; the retriever **filters or orders by an existing weight**, doesn't derive new
> ones. … 5. **Semantic weights are likely the most important part of the graph** — what
> differentiates it from a plain chunk store." — **[USER-STATED — paraphrase]**

**Multiplication rejected** — `2026-05-25-artefact-audit-and-cleanup-plan.md`, five open
decisions §1: *"Multiplication is ruled out (user said "specifically multiplication i am
not sold on")"* — **[USER-STATED]**. `2026-05-25-graph-rag-retrieval-redesign.md` adds the
reason: *"too brutal. Tangential chunks with strong tag fit should still be retrievable,
just ranked lower."* — **[USER-STATED — paraphrase]**

`USER_CANON.md` §4 carries *"specifically multiplication i am not sold on"* — **[DOC]
05-25** — as the head of a line that runs all the way to 07-23.

**The retrieval shape agreed:** recall (structural) → filter (weight thresholds, defaults
at 0) → rank (single ORDER BY) → cap (LIMIT) — **[USER-STATED — paraphrase]**, with five
sub-decisions left explicitly open and blocking implementation.

**Why the LLM cannot weight** — `2026-05-25-middle-layer-weight-redesign.md` §"Facets":

> *"yeah it's high, because I chose it"* — **[USER-STATED]**, the user characterising the
> model's own weight behaviour. The doc: *"`w_facet` only has 21 distinct values across
> 255k edges because the LLM couldn't differentiate."*

**Only code change of the session:** tagger temperature `0.3 → 0` at
`backend/tagging/pipeline.py:609` — **[AGENT-ASSERTED]**, agent-executed, user-approved.

**The baseline switch that later un-switched itself** —
`2026-05-25-graph-rag-retrieval-redesign.md` §"Read these before doing anything else":

> "`memory/baseline-is-sql-agent.md` (added this session) | Lucene baseline is being
> dropped; **SQL-agent is the thesis comparison.** Do not frame analyses around Lucene
> going forward." — **[USER-STATED — paraphrase]**

**The pivot** — `2026-05-25-artefact-audit-and-cleanup-plan.md` §TL;DR:

> "**This conversation pivoted hard:** the user said *"fuck the instinct, talk about
> reality"* and declared the frontend not interesting for the session. … **The frontend
> retrieval redesign from the prior handoff is shelved for now. Do not pick it up unless
> the user re-opens it.**" — **[USER-STATED]**

### The 05-25 live audit — the empirical basis for everything after

All **[AGENT-ASSERTED]**, verified live against the `herb-eval` graph in
`2026-05-25-artefact-audit-and-cleanup-plan.md`, and never contradicted by any later
document:

- **4 node labels, 3 edge types.** `:Source`×1, `:File`×33, `:Chunk`×4,869, `:Tag`×24,804;
  `:CONTAINS`×33, `:HAS_CHUNK`×4,869, `:HAS_TAG`×230,321. **"No `:NEXT`. No `:Run`. No
  `:CanonicalTag*`. (Schema doc claims these exist; they don't in `herb-eval`.)"**
- **`:NEXT` was argued unnecessary, not dropped:** *"Only `_part` kinds have
  order-dependent semantics (~12% of corpus). For those, `c.ordinal` carries the same info
  `:NEXT` would; `:NEXT` is not needed."* And *"All 33 files are `dispatch_mode=parallel`.
  The `sequential` tagging path with `_load_chunk_context` continuity hints is
  dead-but-documented code."*
- **The three weight layers, measured.** `relevance_to_file` mean 0.79, median 0.84, 90%+
  above 0.7 — *"Calibration is too high to discriminate at the top."* `w_chunk` 76 distinct
  values, constant across facet siblings. `w_facet` **19** distinct values over 230k edges,
  top 9 cover 99%+ — *"Treated as continuous in code; functionally categorical with
  ~9-value resolution."*
- **The coverage_bonus works backwards from intuition:** *"cross-tab shows mean w_chunk is
  *lower* on `w_facet=1.0` edges than on `0.7-0.8` edges — because single-facet hits get
  penalized by coverage_bonus."*
- **The pollution quantified:** ~18% of 24,804 tags are literal identifiers — 2,352
  `eid_*`/`emp_*` and 2,065 date-shaped; `eid_*` alone is 16,074 edges. *"only 1,072 of
  those are from `_supplement_lookup_tags` … **the other ~15,000 were emitted by the LLM
  during normal extract** because the tagging prompt doesn't tell the model "don't tag raw
  IDs as concepts.""*
- **The chunker discards source timestamps** — every `locator_json` has zero date keys, so
  `c.years` is back-projected from LLM temporal tags, *"a known violation of 'hard fields
  before tagging.'"*

Closing note: *"alright, good shit"* — **[USER-STATED]**, on the infrastructure work,
explicitly *not* signalling the next step.

### 2026-05-30 — the v2 pivot: references, not copies — [UNKNOWN]

`git show 296fc40:docs/v2_artefact_rebuild_design.md`

> **Status:** design, validated against real HERB data. No v2 code written yet.
> **Baseline it supersedes:** the v1 artefact (git tag `artefact-v1`, commit `244beb7`;
> Neo4j `herb-eval` + `herb-eval.dump` + sibling `herb-eval-backup`).

§1, the core principle and the explicit charge against v1:

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

This is the reversal of D10 — **C-1**. The desktop record's
`2026-05-31-v2-artefact-rebuild-and-facet-design.md` §2 records the same stance from the
conversation side: the graph is *"a reference index over untouched raw source, not a store
of mutated copies. This is the root fix"* — **[UNCLEAR]** as prose, with the memory file
`graph-is-references-not-copies.md` named as its home.

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

§7 mandates full entity decomposition — reversed thirteen days later, **C-8**:

> Faithful decomposition = every object → a node, every scalar attribute → a property.

§12, the eval verdict that has never been acted on — the origin of **C-2**:

> Every run in `run data/` (gold-100, graph100, baseline100, mh_graph, …) was produced
> against the v1 graph, whose retriever multiplies seven factors at query time and whose
> vocabulary is polluted. Those numbers measure the v1 violation, not the intended product.
> The HERB evaluation is re-run on the v2 graph for thesis numbers; v1 runs are kept as the
> before/after contrast.

§11, tagger model, decision one of three — **C-10**:

> - **Model: `deepseek-ai/deepseek-v4-pro`** — chosen by benchmark (reliable HTTP 200, valid
>   JSON, consistent latency). `deepseek-v4-flash` is a working fallback; `moonshotai/kimi-k2.6`
>   was ruled out (~118 s/call on the free tier, with and without JSON mode).

§10, identity resolution measured against real data:

> - `eid_xxxxxxxx` (employee.json, 530 people; key == employee_id): slack `userId` (54/56),
>   `team[]` (44/44), document `author` (15/15), transcript `participants` (33/33) →
>   `:Employee`.
> - `EMP_#########` (pr/review `user.login`): a **separate, directory-less population** —
>   zero EMP_ ids exist in employee.json. … (A first-pass key wrongly mapped login →
>   Employee; the data corrected it.)

`2026-05-31-v2-artefact-rebuild-and-facet-design.md` corroborates this from the
conversation (Employee=eid, Customer=CUST, PrAuthor=EMP as a separate directory-less
space) — **[AGENT-ASSERTED]**, empirically grounded.

And the oracle-quarantine requirement:

> - **The eval oracle must be quarantined.** `answerable_questions` +
>   `unanswerable_questions` carry `ground_truth` + `citations` — this is the
>   contamination that polluted the old `herb` DB.

**No hard filters, recorded as a user stance before any v2 code existed** —
`2026-05-31-v2-artefact-rebuild-and-facet-design.md` §"Retriever design":

> "**NO hard filters anywhere** (strong user stance) — "mandatory" = weight concentration;
> the **cap** does the cutting on rank. Resolves facets-as-filter-vs-ordering → always
> ordering." — **[USER-STATED — paraphrase]**

This is **C-16**. Note the label: paraphrase, no quoted wording. `USER_CANON.md` §6 says so
explicitly and declines to reproduce it as a quote for exactly that reason.

**The combinator**, same doc: *"prompt-conditioned weighted dot product — accumulate across
relevant facets (NOT max), relevance as a continuous coefficient (no gate), applied twice
(facets→tag, tags→chunk). Rejected: multiplication, raw add."* — **[AGENT-ASSERTED]**,
consistent with the user's 05-25 rejection of multiplication.

**The behaviour correction of the session** — same doc, §"User working style":

> "Early this session I wrote 5 memory files from a pasted prior-conversation summary as if
> "decided" — he called it out hard (*"you have created something fucked up here"*). Only
> record what was actually decided/established *in conversation*." — **[USER-STATED]**

### 2026-06-01 — the three-tier semantic model — [UNKNOWN, strongly user-shaped]

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

And the reframing:

> So facet design is an **allocation problem**, not a list: for each convergent dimension,
> decide which mechanism(s) carry it — `{hard field | tag-facet | description/embedding |
> grounding | interpreter}` … Building this dimension → mechanism allocation table (with
> the interpreter column) is the next design step before the re-tag is implemented.

`git_record.md` labels this [UNKNOWN] with the strongest user-signal in the repo — an
argued position with fourteen academic citations. **The desktop record disagrees on
attribution, and it is the better-evidenced reading**:
`2026-05-31-v2-artefact-rebuild-and-facet-design.md` says the seven-tradition synthesis and
**the five-facet set that comes out of it — topic, process, stance,
communicative-function, temporal-stance(TAM) — are [AGENT-ASSERTED]**, and
`2026-06-25-artefact-facets-guide-link-and-content-profile.md` §8 has the user disowning
them outright:

> *"Treating the v2 five-facet set as canon — it's an assistant research synthesis (SFL /
> appraisal / PMEST / AMR / RST), the user **never hard-approved the specific five**, and
> it hollowed the tag."*

The 05-31 doc itself splits it: *"He drove the key insights (facets-as-dimensions,
completeness-across-totality). Follow his lead; sharpen against research"* — the
*principles* are the user's, the *specific five* are the agent's. This distinction is
load-bearing for **C-6** and **C-7**.

### 2026-06-03 / 06-04 — chunking and the cap

`2026-06-03-v2-chunking-model-design.md` and `2026-06-04-v2-chunk-cap-and-budget.md`,
**[AGENT-ASSERTED]** as session output, never disputed later:

- **A chunk is a coherent episode**, not a fixed-size window; v1's fill-to-budget batching
  is killed. Build by descending the source's own structure.
- **The materialized path** replaces the flat ordinal: integer components `[1,2,3]`
  carrying position only. *"The same path does ancestry + context-expansion + dedup."*
  Over-budget episodes split into prefixed subchunks that are *just chunks* — **no parent
  node**. Confirmed by the user on 06-12: *"didnt we have a discussion about the relational
  chunks->subchunks file hierarchy such as 1.1.2…?"* — **[USER-STATED]**, and
  `2026-06-12-v2-graph-spine-and-literal-matching.md` records it as *"decided canon,
  untouched, now MORE load-bearing since the path attribute is how the tree exists without
  branch nodes."*
- **No overlap** (fights references-not-copies, dirties COVERS). Boundary detection fully
  **deterministic** — reply/quote links > adaptive relative time-gap > participant
  turnover; **topic-drift/embedding-similarity considered and rejected**.

**The cap = the tagger's effective focus span, ~3000 tokens** —
`2026-06-04-v2-chunk-cap-and-budget.md`:

> "The "budget" is **not** a token-count-for-its-own-sake and **not** an embedder limit
> (the embedder only ever sees short artifacts — tags and the chunk **description** —
> never raw chunk prose). It is the **tagger's effective focus span** … grounded in
> lost-in-the-middle / RULER / NoLiMa. **Cap ≈ 3000 tokens** (vs v1's 800/1500) —
> deliberately *larger* than the RAG 512–1024 band because v2 never embeds the raw chunk
> … 3000 is a **calibration seed**, not final." — **[AGENT-ASSERTED]**

**The sweep was deferred deliberately, not forgotten** — same doc, §"Open items":

> "**Cap calibration** — the only thing left on the chunking design, and it's
> *implementation-time*: an empirical sweep of chunk size vs tag relevance + description
> specificity, which can run only once the v2 tagger + chunks exist. **Not actionable
> yet.**" — **[AGENT-ASSERTED]**

This is the half of **C-15** that git could only record as "the sweep was never run".

**Tagger model revision 2** — `mistral-large-3-675b-instruct-2512`, *"chosen for Swedish
fidelity on the Bonnier data … tier beats recency, so Large over the newer
mistral-small-4."* Swedish embedder `nvidia/llama-3.2-nv-embedqa-1b-v2`. A second NVIDIA
account to stack keys was **rejected** (ToS + reproducibility liability). —
**[AGENT-ASSERTED]**. This is **C-10** revision two.

Two behaviour rules land here, both **[USER-STATED]** and both carried in `USER_CANON.md`
§15 as **[DOC] 06-04**:

> *"you fucking run off and do your own thing"* (on being handed a 3-tier build plan in
> answer to "go on then")
> *"dont just agree, i was asking."*

and **delete-don't-preserve** — `2026-06-03-v2-chunking-model-design.md`: *"Never keep
legacy/superseded content, backups, fallbacks, or tests on your own initiative. When you
supersede something, delete it. Preservation needs *explicit* approval."* —
**[USER-STATED — paraphrase]**

### 2026-06-09 — weights: measure, don't emit

`2026-06-09-weight-production-measure-not-emit.md` — the first doc with the formal
canon/hypothesis separation. Its §11 is blunt: *"the user is actively co-designing the
weight mechanism and has NOT decided it. Most "answers" in the transcript are assistant
proposals, several of which were wrong."*

§3, all **[USER-STATED]**, and all carried in `USER_CANON.md` §13 as **[DOC] 06-09**:

> "**An LLM cannot put correct weights on tags or chunks.** This is the user's central
> conviction and the spine of the whole discussion."

> *"Measure from embeddings (IF POSSIBLE) is way better than more prompting."* …
> *"measure from embeddings was my idea."*

> *"might as well keep the description and embedding of it i guess, we can discuss the
> compute/cost that choice is worth."* (description kept — **tentatively**, cost
> justification deferred)

> The tag-vs-description distance is a real signal: a tag embedding is *"ONLY THAT TAG… no
> other relationship in this void"*; the chunk description *"IS a semantic relational
> sentence or two"*; comparing them measures *"the relevance of the tag in distance from
> the chunk."*

> **All facet weights on the SAME edge:** *"weren't we supposed to have ALL the facet
> weights on the SAME edge!?"* and *"why the actual fuck would you want or need a separate
> edge for each facet?"*

> Richer tags mean fewer tags: *"perhaps we get less tags like this?"*

The principle in one line — §5:

> "**the model identifies (qualitative — which tags, what description), and geometry
> measures (quantitative — the weight). The model never emits a number.**" —
> **[AGENT-ASSERTED]** as phrasing, **[USER-STATED]** as substance

**Preserved v1 evidence** (§4, all measured, **[AGENT-ASSERTED]**): the `w_chunk` formula
verbatim (`strength × coverage_bonus`, α=0.25, N=5); anchoring 85% single-pass → 12.3%
two-pass; distinct-value counts 76 / 21 / 86; and the trap — **"42 tags per chunk" is 42
EDGES**, facet-multiplied by the ≥0.50 rule, not 42 concepts. *"Distinct concepts per chunk
≈ low-20s."*

**Two assistant claims the user rejected** (§8), both **[USER-STATED]** corrections:

- *"Comparing a tag embedding to a description embedding hands the number back to the
  model."* **FALSE** — the cosine is geometric; the model produced two *texts*, not the
  number.
- *"tag-vs-description is a tautology / comparing the chunk to itself."* **FALSE** — a
  chunk's tags differ in distance to the description; that difference is exactly the
  ranking signal.

Also landed 06-09, user-approved (§10): design-doc **§9.5 "one stateless call per chunk"**
and a new **§16 build-time validation strategy** (tags = code assertions; weights =
invariants; error analysis first; *"~30 samples catches a bug, 250–500 measures a rate"*;
*"the one design blocker = the tagger prompt/output contract"*).

### 2026-06-11 — the re-cut: phrase nodes, no description, the build gate

`2026-06-11-v2-facet-carriers-and-build-gate.md`. Its own header: *"THE SHARED-TAG-NODE
MODEL AND THE AXIS/PROJECTION WEIGHT APPARATUS FROM EARLIER DOCS ARE DEAD."*

§3, **all [USER-STATED]** — this is the densest concentration of user rulings in the corpus,
and `USER_CANON.md` §§3, 4, 13 carry the lot as **[DOC] 06-11**:

> **The model emits NO numbers, ever** — tagger and interpreter both. v1 evidence in the
> user's words: *"it took so fucking long to get it right and it still didn't work at
> all."*

> **Tag = a small concept (contextual phrase), and the phrase IS the node** — no bare-word
> shared tag nodes, no synonym canonicalization; cross-chunk linking is embedding
> **proximity**: *"what if we don't do the word, and just have the embedded 'small concept'
> as the node"*. The doc marks this **the user's idea**.

> **No chunk description.** *"Since the collective tags from a chunk should BE the content
> of the chunk, why do both?"* — the doc notes *"(User asked twice; it is dead.)"*

> **Tag relevance is measured against SIBLINGS** — *"compare each phrase to its siblings"*;
> and per-facet: *"perhaps we can do that, but based on each facet! giving a relational
> value of the tag to its siblings based on each facet!?"* (marked the user's idea,
> verbatim).

> **Node/edge split (the user's proposal):** *"the weight of the tag is ON the tag, because
> that is the phrase's concept being valued, and the 'in relation to the siblings' weight
> is on the edge."*

> **ALL facets are evaluations** — *"stance is not a magical facet, ALL facets are
> evaluations."*

> **Each facet gets its own UNIQUE mechanism** — *"i think we have to have unique ways of
> doing it for each facet"*. The doc flags the trap: concept uniform, instruments differ.

> **Facets are dual-purpose:** *"cluster or weight-adjust, aka narrowing or focusing the
> actual search-area of the corpus for the routing"*; *"if the prompt is heavy in a facet,
> those facets are 'worth more' for the prompt/route."*

> **Facets = extractable meaning dimensions of language** — *"things you can extract from
> language, the things that actually 'mean' something"*.

> **Linguistics belongs to the interpreter:** *"for the interpreter, it's helping it
> interpret the prompt, and picking it apart for tools, routes etc."*

> **The frontend is cut:** *"perhaps we even cut away the entire front-end... it just
> confuses agents"*. With it the API layer — v2 retrieval becomes a Python library + CLI.

> **The oracle never enters the corpus:** *"we just don't fucking include the eval part in
> the dataset, why is this an issue even"*.

> **v2 is a from-scratch rebuild beside v1:** *"we don't keep shoveling around bad, useless
> or legacy code building dependencies on old stuff"*.

**THE BUILD GATE** — §3, the rule that governs everything afterward:

> "**Design before build (the gate):** the assistant started coding on a misread; user:
> *"that means we fucking have to make sure all parts are decided upon first."* All parts
> decided before pipeline code." — **[USER-STATED]**

The scan+probe code already written was allowed to stand because its design was settled;
the gate became law from that point. The doc also records **[USER-STATED]** *"The tagger
design is NOT done — user called out the assistant's false claim"* (*"that.. does not seem
fucking true at all"*).

**The axis apparatus killed** — §8:

> "**The axis/projection apparatus is DEAD.** SemAxis-style facet axes, pole words,
> hand-written anchor-phrase poles, "stance-type axes" — all assistant inventions from
> earlier sessions that leaked into docs/memory as if decided. User: *"honestly, none of
> what you are saying now is a thought I have had, where the fuck did all of this even come
> from."*" — **[USER-STATED]**

**The three-bucket ledger** (§7/§11) is the corpus's cleanest honesty device: nine
proposals labelled *"uncontested but never blessed"* — topic-as-sibling-centrality, stance
carrier, function carrier, process carrier, time carrier, interpreter property list, router
template library, multi-hop bridges, world-facts rule. All **[AGENT-ASSERTED]**; the doc
forbids presenting any of them as decided.

Two **[AGENT-ASSERTED]** risks flagged and never resolved: (a) per-chunk phrase nodes make
corpus-wide recall depend on k — no shared node means no one-hop "all chunks about X"; (b)
multi-topic chunks under-weight both topics under naive centroid centrality.

### 2026-06-12 — the spine closes

`2026-06-12-v2-graph-spine-and-literal-matching.md` §3, **all [USER-STATED]**, carried in
`USER_CANON.md` §2 as **[DOC] 06-12**:

> **The graph spine is `file → chunk → tags`** (forcefully): *"if we are saying file ->
> chunk ->tags .. where are those OTHER RANDOM FUCKING NODES!?"*

> **The node/attribute fork is the user's:** *"either they are nodes, but then we get edges
> to EVERY fucking chunk, or they are just attributes… perhaps it's smarter to just have
> shit like that as attributes on chunks."*

> **Records-as-nodes is dead:** *"that sounds a bit fucked up to have them as nodes, most of
> them will be a chunk, meaning we have 2 almost same nodes."*

> **No value inventories in the graph:** *"that has the potential to put a fuckton of data
> into the graph, both GDPR data, and not. why not just have the parent field as the
> connection and when searched for, you can find anna."*

> **Minted facet-label hub nodes are dead:** *"it's dead, such shit is 'interpreter area'"*.

> **Chunk→file relevance value killed** — the user asked to *"revisit the value and point of
> 'chunk value to its file'"*; the kill landed. Plus a user correction: **the chunk never
> had embeddings — the description had**, *"but that was not the point of that field
> anyway."*

> **Humans don't type correctly:** *"thinking humans write correctly, is naive as fuck,
> ESPECIALLY when talking to an llm."* → *"exact + fuzzy IS the way to go for herb"*.

> **No corpus vocabulary in the interpreter's context:** *"i am honestly not sure we want to
> give it the vocabulary, remember, every extra context costs money."*

> **Field handling follows data shape:** *"this must be based on the structure of the final
> leaf/branch data-form… different ways of handling fields based on the type of data in
> them."* — blessed only *"ish"*: *"honestly not sure about that specific solution.. but
> yeah.. ish"*.

> **v1 docs stay untouched:** *"that shit is still true for THAT build."* — the rule that
> explains why v1's decision log was never retro-edited.

> **Removal, not banners:** *"please do continously update information according to the
> things we decide"*, and *"did you REMOVE, quarantine, legacy-note or something else"*.

**The node/attribute rule, stated formally** (§4) — **[AGENT-ASSERTED]** phrasing of a
**[USER-STATED]** rule:

> "a thing is a **node** only when others depend on its facts to resolve themselves, or
> retrieval walks *through* it; it is an **attribute** when it is a value you filter/boost
> by."

**One embedding surface:** *"the pipeline embeds **phrase tags only**. No field values, no
descriptions (dead 06-11), no raw chunks."* — **[AGENT-ASSERTED]**, following from user
rulings.

**The literal-matching pipeline decided in full** (§4): deterministic exact pre-pass with
matched literals stripped → vocab-free interpreter flags type + wanted/excluded → flagged
miss triggers a **scoped string-distance lookup against that one directory only** →
described-not-named falls to semantics. Ambiguity: all candidates boosted, confidence sets
boost size, jump only on exact-unique. Multi-hit: boosts only, additive (*"a does seem to
fit the best"* — **[USER-STATED]**).

**HERB verified against all 1,514 questions** — **[AGENT-ASSERTED]**, run inline that
session:

> "template-generated, perfectly spelled, products named exactly, customers named verbatim
> … people referenced by ROLE ("Engineering Lead") never by name; employee IDs are the
> *answers*, not prompt inputs. No typos, no paraphrases anywhere."

and the twins — ContentForce/ContextForce, CollaborateForce/CollaborationForce,
SearchFlow/SearchForce, TrendForce/ForecastForce — *"all real, separate products.
Embeddings/string-distance conflate them; only exact matching separates them."* This
measurement is why blanket typo-fuzzy was rejected and the exact layer is load-bearing; it
reappears verbatim as §14.7 of the design doc in Era 3.

**The corpus's most instructive agent failure** — §8:

> "**"Forcing shit into the graph" — the assistant did this THREE times** and must not
> again: (1) embed-the-vocabulary inventory, (2) "search the employee field's values in the
> graph" (values are NOT in the graph; they're in raw, reachable via references — *"where
> the fuck in the graph do you think this is?"*), (3) "metadata islands" (Employee/Customer
> nodes kept by inertia from the dead 05-30 draft — *"why the fuck and from WHERE do the
> random nodes and other shit come from?"*)." — **[USER-STATED]**

### 2026-06-14 — facets as relevance channels; the thesis is done

`2026-06-14-v2-facets-as-relevance-channels.md`.

**The single most consequential framing fact in the corpus** — §3:

> "**Thesis is DONE/submitted (2026 VT).** v2 is post-thesis. Do NOT justify/frame work
> around thesis needs or "thesis numbers." (User: *"drop the fucking thesis... it's done,
> this is post-thesis work."*)" — **[USER-STATED]**

Everything from 06-14 onward is post-thesis engineering. `USER_CANON.md` traces the direct
line from here to **[CHAT] 07-22** *"thesis? wtf? we are building the fucking artefact
here"* and **[CHAT] 07-30** *"why the fuck are you going on about "the thesis"?"*

Other §3 facts, **all [USER-STATED]**:

> **Structural, not declarative, quarantine:** *"DONT INCLUDE THE FUCKING EVAL FILES FOR THE
> PROBE TO EVER SENSE."* A yaml `eval_holdout:` declaration was rejected as the weak
> version.

> **One derived artifact only:** *"pre-make 1 training-set and then do the eval on the
> 'original'."*

> **Nothing deleted in the repo separation** — *"two repos in the same repo"*; the user
> overrode an assistant proposal to delete v1.

> **Cold storage is untouchable:** *"do not touch A:\exjobbet\data\raw at all, that is the
> storage, the one in the repo can be worked with."*

> **Tags unique per chunk** — same phrase may recur, each emission its own node. (User
> proposed.)

> **HERB-only; Bonnier deferred:** *"the Bonnier set will have to wait until some other
> time."*

**THE FACET BREAKTHROUGH** — §3, the user's framing *"hammered home repeatedly"*,
**[USER-STATED]**:

> - Base the tag concept on v1. **The v1 tag CONCEPT was sound; the WEIGHTS were the
>   problem** (specifically that they were *model-emitted numbers*).
> - Facets give **"relevance weights, not interpretation."** A facet is NOT a category, NOT
>   a bucket, NOT a chunk attribute — it is a **relevance coordinate / the character of a
>   tag**.
> - The per-facet weights live on **ONE edge** chunk→tag (v1's "one edge per facet" was bad
>   implementation/communication; intended = one edge carrying the whole facet vector).
> - **Retrieval mechanism:** the interpreter decomposes the prompt **per facet**; matching
>   is **same-facet, like-for-like** — prompt TOPIC vs tag TOPIC, prompt STANCE vs tag
>   STANCE. Each facet is a **parallel comparison channel**. Routing sums the channels
>   weighted by how much the prompt cares about each.

**The caveat the doc puts on its own decision** — §6.4:

> "**Tagger OUTPUT schema approved** in conversation (calls a/d/f): per-facet
> contextual-phrase lists for the open facets + closed-enum chunk attributes for
> function/TAM … **CAVEAT: this approval predates the §3 facet breakthrough and the §8
> carrier reversal — re-validate it.**"

This is the exact reopening git finds in `MODEL_CONTRACTS.md` §5 and cannot resolve — the
first step of **C-7**. Also **[USER-STATED]**: the user rejected the contracts doc as an
approval vehicle — *"i never saw the fucking schema"*. And the session's mood: *"driving me
insane"*.

**Model-choice honesty note** — §3, **[AGENT-ASSERTED]**:

> "**Mistral is the tagger model** … NOTE: the original Mistral rationale was Swedish
> fidelity — **now moot under HERB-only** — so the model choice rests on "largest tier"
> reasoning, not Swedish."

The Bonnier-rationale collapse that git flags as **C-10** problem 1 was noticed and
recorded here, on the day. It never reached `DESIGN.md` §11.

**Built and run this session** — **[AGENT-ASSERTED]**: `derive_corpus.py` stage 0 (strip
set `answerable_questions`, `unanswerable_questions`, `team`, `customers`; 18 tests pass;
verified against the HERB dataset card + arXiv paper), the mapping key finalized to three
declarations, and the `git mv` repo split into `v1/`/`v2/` (~194 renames, uncommitted).

## What was built

| Date | SHA | Author | What landed |
|---|---|---|---|
| 05-28 | `54bc1a4` | Objuret | eval results, SQL baseline, thesis docs, Bonnier dataset — tip of `origin/eval-results-complete-2026-05` |
| 05-29 | `244beb7` | Objuret | `Snapshot v1 artefact forensics: verify scripts + RAGAS run dumps` — the commit the v2 design names as the superseded baseline |
| 05-30 | `296fc40` | Objuret | `docs/v2_artefact_rebuild_design.md` (192 lines), shape-probe prototype, NVIDIA host verification |
| 05-30 | `c2fabbb` | Objuret | removes the entire thesis tree from version control, gitignores thesis paths |
| 06-01 | `18d11df` | Objuret | NVIDIA NIM wired into Settings; reference-resolver prototype; §13 (+114 lines) |

**Nothing was committed between 06-01 and 06-15.** The entire fortnight of decisions above
— the closed spine, the death of the description, per-chunk tag nodes, the structural
quarantine, the mapping-key finalization, the facet reframe — lands in one 750-line commit
on 06-15. That gap is git_record's G-2, and the desktop corpus is what fills it.
`2026-06-11`, `2026-06-12` and `2026-06-14` each record *"NOTHING COMMITTED"* /
*"not committed"* explicitly — which is also the mechanism behind **C-18**.

## What diverged

### The shipped v1 scorer: seven factors and five hard gates — 2026-05-28

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

Max-within-a-prompt-tag, then sum-across-prompt-tags, with a stated reason. `git_record.md`
notes this aggregation survives the entire rebuild — `git show 6730d13:v3/pipelines/artefact_v1.py`,
"An opened level's tags pull their chunks, **each chunk keeping its highest-support tag**"
— and calls it *"one of the few v1 mechanisms that was never repudiated."* (See the
disagreements section: `USER_CANON.md` **[CHAT] 07-23** complicates that "never
repudiated".)

The seven-factor product, resolving **C-12**:

> ```js
>     : `qt.w_query * facetScore * r.w_chunk * r.w_facet
>          * coalesce(c.relevance_to_file, 1.0)
>          * qt.sim
>          * coalesce(qt.scopeWeight, 1.0)`;
> ```

Count: `w_query` · `facetScore` · `w_chunk` · `w_facet` · `relevance_to_file` · `sim` ·
`scopeWeight` = **seven**. The design-time record was five; the two extras arrived between
05-15 and 05-28.

And the five hard gates, which **C-16** is written against:

> ```cypher
>   AND r.run_id = $runId
>   AND r.facet IN $activeFacets
>   AND (qt.facet = 'all' OR r.facet = qt.facet)
>   AND coalesce(r.w_chunk, 0.0) >= $minWChunk
>   AND coalesce(c.relevance_to_file, 1.0) >= $minRelevanceToFile
>   ${gate}
>   ${exclude}
> ```

The 05-25 handoffs name the same targets independently, from the running code:
`2026-05-25-graph-rag-retrieval-redesign.md`: *"The 7-factor multiplicative synthesis in the
current `frontend/src/services/retrieval.ts` `scoreCypher` is the explicit violation of
this design."* `2026-05-25-artefact-audit-and-cleanup-plan.md`: *"Drop the multiplicative
7-factor `edgeWeight`. Drop `qt.w_query`, `qt.sim` (as a score factor — keep as
filter/grounding bridge), `qt.scopeWeight`."* Two independent contemporaneous sources, same
seven factors, same two extras.

### D10 is never retracted in place — **C-1**

The reversal is argued and evidenced, but `git show dba1160:docs/architecture.md`'s D10
still reads **"Status. Active"** in every ref that carries it, including
`git show 28c95aa:v1/docs/backend/architecture.md`. Git could only note this as odd.

The desktop record explains it as **policy, not neglect** —
`2026-06-12-v2-graph-spine-and-literal-matching.md` §3:

> **"v1 docs stay untouched:** *"that shit is still true for THAT build."* v1 documentation
> describes v1 as built; only v2-living docs get purged." — **[USER-STATED]**

Reinforced in §8: *"Don't touch v1 docs / historical snapshots when purging — they're true
for that build / frozen records."* `USER_CANON.md` §22 carries the quote as **[DOC] 06-12**.

### The SQL-agent baseline is adopted, then silently un-adopted

05-25 makes SQL-agent the thesis comparison and drops Lucene, with a memory file written
and both handoffs instructing the next agent accordingly. By 06-18 the v3 harness is
lucene + vector + artefact, and `baselines/sql_agent.py` is listed as *"dead"* v2 cruft.
**No document in any of the three records records the reversal.** It is not one of the 18
numbered contradictions; `desktop_docs_record.md` §5.9 and `USER_CANON.md` Part IV.D both
flag it as a nineteenth of the same kind.

### The five-facet set enters as an agent synthesis and is treated as canon

Recorded here because it is the root of both **C-6** and **C-7**: the set the whole of
§13.4/§13.5 and `MODEL_CONTRACTS.md` §1 are built on was never hard-approved by the user,
and the doc that says so most plainly (`2026-06-25-artefact-facets-guide-link-and-content-profile.md`
§8) is eleven days downstream of the design landing that shipped it.

---

# Era 3 — Facet reconciliation and the v3 harness

**2026-06-15 → 2026-06-28**

Two threads run in parallel: the artefact design is finished on paper (and immediately
starts contradicting itself), and a separate, much cleaner eval harness is designed and
built. The user's chat record is still dark until 06-27.

## What was decided

### 2026-06-15 — the largest design landing in the repo

`0efff16` — `Separate repo into v1/ (frozen) and v2/ (active) siblings`. It grew the design
doc by **750 lines**:

`git diff 18d11df:docs/v2_artefact_rebuild_design.md 0efff16:v2/docs/v2_artefact_rebuild_design.md --stat`
→ `750 insertions(+), 75 deletions(-)`

adding §7 (the closed graph spine), §8 (the mapping key), §9 (chunking), §13.4–13.5 (the
facet allocation table and per-facet specs), §14 (retrieval routing), §15 and §16. It also
adds the first `CLAUDE.md`. The identical text lands again at `28c95aa` as
`v3/artefact/DESIGN.md`, which is the ref most of the citations below use.

### The closed graph spine — decided 2026-06-12, landed 06-15 — [UNKNOWN] prose, [USER-STATED] decision

`git show 28c95aa:v3/artefact/DESIGN.md` §7

> **The graph is `Source → File → Chunk → Tag`. Nothing else is a node.** This replaces
> the earlier draft in which every object became a node (Message/PullRequest/Employee
> entity nodes, COVERS edges) — that draft mirrored the dataset into the graph, which is
> the copies disease at the node level.

The decision rule:

> **The rule deciding node vs attribute:** a thing is a **node** only when others depend
> on its facts to resolve themselves, or retrieval walks *through* it. It is an
> **attribute** when it is a value you filter or boost by.

Consequences stated explicitly: records are not nodes, branch/collection positions are not
nodes, metadata directories are not nodes. And:

> - **Tag nodes are per-chunk emissions, not shared vocabulary (decided 2026-06-13).**
>   Each tag the tagger emits becomes its own `:Tag` node bound to exactly one chunk …
>   This is what made v1's residue possible: shared tags minted from oracle chunks
>   survived the herb-eval filter attached to clean chunks, and orphan-tag bookkeeping
>   existed at all.

This is the documented reversal of 05-30 §7 — **C-8**. Git labels the reversal
"documented"; the desktop record upgrades the attribution to **the user's**, with the three
verbatim 06-12 quotes reproduced in Era 2 above. That is the better-evidenced reading: git
cannot attribute prose at all, and `USER_CANON.md` §2 carries the same three quotes as
**[DOC] 06-12**.

### The chunking design — coherent episodes — [UNKNOWN]

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

Implemented verbatim — `git show 6730d13:v3/artefact/chunk.py` line 44:

> ```python
> CAP_TOKENS = 3000        # tagger focus span (design §9.1); a seed for the §15 sweep, not a verdict
> ```

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

The statelessness commitment (§9.5) — the item the 06-09 doc records as user-approved:

> **One stateless call per chunk.** The tagger is a single structured-output invocation per
> chunk — same prompt, temp 0, one chunk in, phrase tags out (no description, no numbers),
> instance discarded — NOT a multi-step agent loop and NOT several chunks batched into one call.

### The mapping key — 2026-06-12 — [UNKNOWN]

`git show 28c95aa:v3/artefact/DESIGN.md` §8; implemented at
`git show 28c95aa:v3/artefact/keys/Salesforce__HERB.yaml`

> **The automatic part — the shape→handling table.** What happens to a field follows the
> shape of its values, read off the probe tree with **no key entry** …
> The discriminator between "attribute" and "stays in raw" is the **repetition ratio**
> (distinct/total per field, measured by the probe across the fuse) … The gap between the
> two is a chasm, not a threshold to tune.
>
> **The declared part — the three judgments shape can't know:**
> 1. **Content choice** … 2. **Directories** … 3. **Id-space assignment**

The key implements exactly those three sections, with resolution rates as verified comments:

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

The desktop record confirms the user's own hand here indirectly: the shape-driven rule was
blessed only *"ish"* on 06-12 (*"honestly not sure about that specific solution.. but
yeah.. ish"* — **[USER-STATED]**), and the key was *"finalized to three declarations"* on
06-14 (`2026-06-14-v2-facets-as-relevance-channels.md`, **[AGENT-ASSERTED]**).

### Structural oracle quarantine — 2026-06-12 — [UNKNOWN] prose, [USER-STATED] decision

`git show 28c95aa:v3/artefact/DESIGN.md` §4 stage 0; implemented at
`git show 28c95aa:v3/artefact/derive_corpus.py`

> The quarantine is **structural, not declarative** (decided 2026-06-12, replacing
> the earlier `eval_holdout` key section): the probe can never sense the stripped
> surfaces, so contamination is impossible by construction instead of excluded by a
> yaml line.

Two categories stripped, both with a cited external mandate:

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

The arithmetic checks out: `git show 0733a9d:v3/data/questions.jsonl | wc -l` → `1514`.

`git_record.md` calls this *"the strongest piece of engineering in the record"*. The
desktop record supplies the user's own words behind it, from
`2026-06-14-v2-facets-as-relevance-channels.md` §3: *"DONT INCLUDE THE FUCKING EVAL FILES
FOR THE PROBE TO EVER SENSE."* — **[USER-STATED]**, with the declarative `eval_holdout:`
yaml explicitly rejected as the weak version. `USER_CANON.md` §8 carries it as
**[DOC] 06-14**.

### The v2 facet set and per-facet specs — the spec that was never built — [UNKNOWN]

`git show 28c95aa:v3/artefact/DESIGN.md` §13.4–§13.5. The allocation table promised on
06-01 was delivered:

> **Resulting v2 facet set** — only the genuinely fuzzy-semantic dimensions worth graded
> tag-edges + grounding: **topic, process, stance (attitude + modality),
> communicative-function**, plus **temporal-stance (TAM)** as the meaning-half of temporal.
> ~4–5 facets.
>
> - **Structure / hard fields (EXACT):** participants+roles, literal time, space, genre/kind,
>   evidentiality/provenance — exactly the v1 "junk facets" (entities/temporal/evidence)
>   relocated to where they belong.

§13.5 gives each facet what §13.1 said v1 never had — a spec with a MUST-NOT list and an
interpreter mirror:

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

None of this reached the built tagger — **C-7**.

### The retrieval routing model — [UNKNOWN]

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

"Rejected: multiplication (too brutal)" is the design-doc form of the user's 05-25
*"specifically multiplication i am not sold on"* (**[DOC] 05-25**, `USER_CANON.md` §4) and
of `2026-05-25-graph-rag-retrieval-redesign.md`'s recorded reason, *"too brutal"*.

No hard filters (§14.4) — **C-16**:

> No hard filters anywhere in ranking. A hard filter crushes signal and — worse — gates on a
> *judgment that can be wrong*: a true decision mis-tagged would be silently, totally
> excluded (the loud-failure principle: surface it, never silently drop it).

The removal of the file-relevance weight (§14.1):

> - **File→Chunk is containment only — it carries NO weight.** The v1 "chunk's relevance
>   to its file" number is removed: its job (demoting filler) is solved at the source by
>   coherence-episode chunking, and what it actually measured — typicality — buries the
>   rare relevant aside.

§14.7 records the measured reason to reject fuzzy product matching — the same measurement
the 06-12 session ran inline:

> Evidence: all 1,514 HERB questions are perfectly spelled with people referenced by
> role, while the product list holds deliberate near-twins (ContentForce/ContextForce,
> CollaborateForce/CollaborationForce, SearchFlow/SearchForce) — so blanket typo-fuzzy
> would conflate real products and is rejected; the exact layer is load-bearing.

### Model contracts — a working draft with nine unsigned items — 2026-06-14 — [UNKNOWN]

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
`REOPENED` at the last commit that touches this file. This is the last state of the facet
design recorded in git. The desktop record supplies both the origin of the reopening
(06-14 §6.4, above) and the user's rejection of this doc as an approval vehicle: *"i never
saw the fucking schema"* — **[USER-STATED]**, `2026-06-14-v2-facets-as-relevance-channels.md` §9.

### The three-arm eval harness — 2026-06-18 → 06-23

`2026-06-18-v3-eval-harness-herb-ragas.md` §3, **all [USER-STATED]**:

> **Cost carries ZERO weight in the assistant's reasoning:** *"YOU do not care about cost
> here, 0 fucks given… only for me. so fucking drop that fast as fuck."*

> **`v2/` = build-site (mess allowed); `v3/` = the place to save the CLEAN, lean stuff.**
> New working model the user defined this session.

> **The user writes the real code.** Reason given: *"to ensure it does what's intended (v1's
> eval ran RAGAS metrics that measured the wrong thing)."*

> **Do BOTH scorers** (HERB + RAGAS), not either/or: *"no, i am saying we do both."*

> **RAGAS-on-the-answer primary; HERB's exact scorer the anchor/secondary** — user confirmed "yes".

> **v3 must be LEAN** — no folder-per-concept, no fat trees.

> **Talk like a person, not a "shit machine."** · **Check what already exists before creating anything.**

The decided methodology — **[AGENT-ASSERTED]** design, user-approved on the numbered points:

1. Both scorers; RAGAS primary, HERB anchor.
2. **Deterministic citation-based context precision/recall** (ID-based / non-LLM), not the
   judged variants — *"because in v1 the judged variants were degenerate (precision ~0) and
   biased (recall favored bigger context bags)."*
3. Three arms, one shared generator built once in the orchestrator; baselines build their
   own index over the corpus.
4. Evaluators emit raw per-question `MetricScore` records, tidy long, never pre-aggregated,
   plus a `RunManifest` — so paired Wilcoxon/McNemar, bootstrap CIs, per-type splits, effect
   sizes and judge κ all remain possible downstream.
5. `v3` created lean; layout user-shaped.

**The category error corrected** — §8, **[USER-STATED]**:

> "**DO NOT treat the artefact as "just another retriever" scored by IR recall@k.** Category
> error the user corrected hard. The artefact is the SYSTEM UNDER TEST, not an IR retriever;
> and HERB itself ships **no retrieval-recall metric** — it scores ANSWERS only."

**Verified external numbers** — **[AGENT-ASSERTED]**, read from primary sources: HERB 815
answerable (238 content / 260 people / 130 customer / 187 artifact) + 699 unanswerable =
1,514. Leaderboard: zero-shot 4.55, vector 16.77, hybrid 20.61, ReAct GPT-4o 32.96; oracle
Gemini 85.76 / GPT-4o 61.73. Judge = GPT-4. **ARES considered and rejected** for HERB.

**The construct-validity caveat, raised and never closed** — §7, **[AGENT-ASSERTED]**:

> "answer-level scoring measures the whole pipeline, so a strong generator can mask retrieval
> quality. Keeping the deterministic context precision/recall … is what keeps an endpoint
> pointed at retrieval — the artefact's actual claim. Plausible and important; **not yet a
> locked decision.**"

and **judge calibration**: *"to defend the judged RAGAS metrics academically, calibrate
against a small human-labeled subset and report agreement. Recommended, not locked."* —
**[AGENT-ASSERTED]**, never actioned. The `MetricScore` record carries a `human_label` slot
that is never filled.

The git-side record of the same harness is `git show 0733a9d:v3/README.md`:

> Three arms:
> - **artifact** — the v2 graph (interpreter → facet retrieval → answer). The system under test.
> - **lucene** — BM25 baseline. Its own index over the corpus.
> - **vector** — dense / naive-RAG baseline. Its own index over the corpus.

> the arms share **nothing** — each reads, indexes and retrieves
> the corpus with its own code (how it does so is what the comparison measures); they
> share no retrieval code with each other, and nothing with the artefact.

> ## Two scorers, on purpose
> - **HERB** (`eval/herb.py`) — … Exact, leaderboard-comparable. **The anchor.**
> - **RAGAS** (`eval/ragas.py`) — the multidimensional lens. … The
>   deterministic backbone is **ID-based** context precision/recall against the gold
>   citations (`IDBasedContextPrecision` / `IDBasedContextRecall`, no judge); the
>   judged picks are faithfulness + **response relevancy**.

Question-set construction, with the id-minting scheme and the counts:

> HERB ships no question id, so `build_questions.py` mints `<product>::a|u::<index>` and
> writes the full set (`{id, question, type, ground_truth, citations}`, a/u lives only in
> the id) to `data/questions.jsonl` … `build_question_sets.py` writes the
> `{id, type, question}` id-set views to `output/`: full / answerable / unanswerable
> (1514 / 815 / 699) plus `question_ids.gold100.jsonl` — the **gold-100**, a balanced
> answerable subset drawn by seeded round-robin over the HERB types (equal allocation,
> ~20/type).

**And a validity caveat stated at construction time:**

> Equal allocation keeps every type usable per-type; it does not match HERB's
> natural mix, so report per-type and don't compare the gold-100 aggregate to HERB's
> published average.

Other decisions under "## Decided":

> - **Generation and scoring are separate phases** (`questions` / `evals` / `full`), so
>   iterating a scorer never re-runs the generator. The `questions` record is
>   **oracle-free**; `evals` re-joins `type` + `ground_truth` + `citations` by id …
> - **Per-question telemetry is split**: `ArmOutput.generator` (the shared answer-writer,
>   identical across arms) vs `ArmOutput.retrieval` (the arm's OWN retrieval-time model cost …)
> - **Provenance** is two manifests — `RunManifest` … + `EvalManifest` …; no seed, no git-sha.
> - Oracle read in place from raw; pipelines blind to it.

"no seed, no git-sha" is recorded as a *decision*, not an oversight — runs are not
reproducible to a commit by design.

### Arm independence and comment hygiene — 2026-06-23

`2026-06-23-v3-vector-arm-independence-comment-hygiene.md` §3, **[USER-STATED — paraphrase]**
(this doc records rulings without quoting them):

> "**The arms share ONLY two things: the corpus files on disk and the generator the
> orchestrator injects.** … Arms must NOT import or reuse another arm's corpus-reading or
> retrieval code. *Reusing a reader, or framing a shared unit set as a "fairness
> requirement," is contamination, not fairness* — because **how each approach turns the one
> shared corpus into retrieved evidence is the independent variable the experiment
> measures.**"

> "**No historical or defensive comments** … Rationale the user gave: narrating a fix
> invents fake project history AND — because comments/docs feed the graphify graph and the
> memory files — **dilutes the context of every future conversation.**"

The rule's own enforcement failure is recorded: the agent embedded a review-finding label
("F1") *inside the CLAUDE.md rule forbidding such labels*, and the user caught it.

**Four items left undecided (H1–H4)** — **[AGENT-ASSERTED]**, none recorded as resolved
anywhere later: lucene/vector `documents.feedback` parity; whether slack `userId` tokens
dilute the vector embeddings (*"slack is the dominant cited kind, so blast radius is
wide"*); empty-text artifact placeholders; README phrasing cleanup.

### The lucene baseline — 2026-06-21 — [UNKNOWN]

`git show a45292f` (commit message):

> - pipelines/lucene.py: bm25s Lucene-variant BM25 (k1=0.9, b=0.4, EN stopwords +
>   Snowball stem). Ingest flattens each HERB artifact to one {id,title,contents}
>   doc, native id preserved; artifacts-only index (all 17,087 gold citations
>   resolve to an artifact id). Returns ArmOutput; prepare attaches BuildStats.
>   Reads only id/question (truth quarantine by convention).

> Verified end-to-end on the real corpus (38,540 units). Not yet reviewed via
> /critical-review or refresh_graph (run on dev machine).

`k1=0.9, b=0.4` are the standard Lucene defaults, so unlike α and the 0.50 cutoff they
carry an external warrant even though none is cited. Note "truth quarantine **by
convention**" — weaker than the structural quarantine `derive_corpus.py` gives the corpus.

### 2026-06-25 — three documents in one day

**(a) The cut: tag-facets ≠ routing.** `2026-06-25-artefact-tag-facets-vs-routing.md`,
recovered from a 06-15/16 transcript that *"was never crystallized into a state doc"*. §3,
**all [USER-STATED]**, all in `USER_CANON.md` §4 as **[DOC] 06-25**:

> *"I think we should separate tag facets and routing."*

> *"I more get the feel that those 5 in v2 are almost only viable for the interpreter. While
> the v1 facets were actual semantic meaning around the tag."*

> *"We have literally removed ALL semantics and just replaced large chunks of text with short
> descriptions."*

> *"we only have a few short phrases now instead of a fuckton of tags with facets … I still
> think we need another semantic layer here, like the facets on the phrases. Would not the
> old facets work with the new tags? (not the weighting, the concept)."*

> *"the facets then use the entire tag-korpus as base for the evaluation of each facet on
> them, so their facet-value is relational to the korpus/facet."* — carried as a small facet
> **attribute**, *"not nodes … because that mean edges right, and those are heavy in all
> aspects"*.

> *"Topic is not for facets tbh, how does it even fit there? Perhaps how much of the topic the
> tag is about? Or perhaps this is relative to all tags in the same chunk."* → topic becomes
> **centrality** (chunk-local degree).

What it kills — §7: *"A facet = the relevance coordinate / character of a tag" (the 06-14
framing) — **DEAD**; that was routing leaking into the facet definition."* And *"The
five-facet set as closed canon — reopened."* — **[AGENT-ASSERTED]** conclusions from
**[USER-STATED]** premises. This supersedes, eleven days later, the breakthrough of 06-14.

**(b) The hollowing, and the content profile.**
`2026-06-25-artefact-facets-guide-link-and-content-profile.md` — the pivotal document. Its
§1 states that the written canon is *"and in one case **wrong**"*.

§3 quotes, **all [USER-STATED]**:

> *"the point of the multifacets was to give the tag a more semantical WEIGHT AND DIRECTION"*

> *"the agents assigning facets was pretty much impossible to get different values from, they
> just did 'yeah, its high, because I chose it'"*

> *"'one edge per facet' was just bad communication... they were supposed to be on the same
> fucking edge"*

> *"it feels retarded to put facets on chunks, we are routing by tags, why the fuck put the
> facets AFTER that?"*

> *"What you think is v2 tags is in essence everything moved to hard fields or put on the
> interpreter"* — the sharpest statement of the hollowing.

> *"Temporal was never about dates"* — dates → structure; the time-RELATIONSHIP is the meaning.

**THE HOLLOWING** — §5, **[AGENT-ASSERTED]** diagnosis, **[USER-STATED]** confirmation:

> "The v2 redesign allocated every dimension across mechanisms … and that **emptied the
> tag**, because for every dimension there was a cheaper structure-or-interpreter home:
> entities → hard fields; temporal → hard fields + interpreter; communicative-function →
> structure + interpreter; stance → interpreter; topic → just the phrase's embedding. So the
> "v2 tag" is a bare topic phrase. **Tag-facets must be a THIRD thing: semantic content that
> lives ON the tag — neither a fact (structure) nor a query-decomposition (interpreter)** —
> i.e. *what KIND of content the tag is*. That is exactly what v1's content profile was."

§8, the misread named — this is the whole of **C-6**'s adjudication:

> "**"entities / temporal / evidence are fact dimensions, relocate to structure"** — **WRONG
> about evidence and entities.** `evidence` = information-KIND (metric/argument/procedure/…),
> a real semantic dimension; `entities` = named-thing TYPE, semantic. The *fact* (eid, URL)
> is structure; the *kind/type* is meaning. **This misread is what hollowed the tag.**"

and the provenance failure that caused it:

> "The memory `facet-semantic-framework.md` says "evidence = sourcing, not links"; the actual
> v1 doc says evidence = kind-of-information. **Read the v1 source, not the summary.**"

**The new design (the user's)** — §5, **[USER-STATED]**:

> 1. **The guide link:** a facet is a concept both sides are measured-close-to — the tag's
>    closeness to it and the prompt's closeness to it; the shared closeness IS the match.
> 3. **"max-of-facet rephrase + embed-compare":** *Tag side (build)* — for each facet,
>    recreate the phrase as "max of this facet", then embed-compare the max-F version to the
>    original → the tag's value on that facet. *Prompt side (query)* — do the same to the
>    prompt, rank facets by which was closest → that ranking is the prompt's facet-relevance,
>    which modifies the tag's weights / filter / order.

**The disconfirming research on the user's own mechanism** — §7, **[AGENT-ASSERTED]**,
delivered straight rather than buried:

> "the rewrite-to-facet + embedding-distance scalar **conflates three things** — (1)
> incidental wording change (LLMs over-edit), (2) topic leak, (3) the actual facet change —
> and embedding distance tracks **surface/lexical** change more than the attribute, so it can
> run **backwards** … **Confirm/reject via a ~30-phrase probe.**"

Plus the **orthogonality risk**: *"If facet-concepts overlap in embedding space, the two
closeness-profiles correlate and facets collapse into one (v1: 85% of tags multi-facet at
threshold 0.50; topic/activity/evidence bled together)."* Note that this ties **C-15**'s
undefended `MULTI_FACET_THRESHOLD = 0.50` directly to the risk that threatens the entire
facet layer.

**(c) RAGAS only, and the k / top-k distinction.**
`2026-06-25-v3-vector-eval-k-vs-topk-ragas-ops.md` §3, **all [USER-STATED]**:

> "**SCORING IS RAGAS ONLY. There is NO HERB scorer.** The user said this twice, emphatically
> (*"this is ONLY RAGAS"*). The old "HERB + RAGAS / two-way scoring / HERB anchor" framing is
> **dead** — purged this session. `eval/herb.py` was **deleted**. Do not reintroduce a HERB
> scorer from any stale doc."

> "**MY WORDS ARE THE CANON** (user's literal phrasing). When the user defines the experiment,
> that IS the spec. Do not "correct" it with references, production-RAG norms, or training
> pattern-matching."

> The four judged metrics: *"those 4 + the free ones"*, earlier phrased *"3 we used in the
> thesis + the dropped one"* → answer_correctness, context_recall, faithfulness,
> context_precision.

> **`k` and `top-k` are TWO DIFFERENT NUMBERS** — the session's most forceful point.

> **k = 50**, **gold-100 not the full 1514** (*"The user was furious when an earlier command
> used `--set full`"*), structured outputs for the generator, the user runs the scripts, and
> the pre-run y/N prompt removed as *"the dumbest fucking shit"*.

The definitions, §4 — **[AGENT-ASSERTED]** wording of a **[USER-STATED]** distinction:

> "**`k` = the global CEILING.** One fixed number, **identical for every arm**, chosen for
> **experiment feasibility** … the controlled variable.
> **`top-k` = each arm's ACTUAL RETURN under that ceiling.** Per-arm … the **measured**
> thing — read off via the arm's **token cost**: a dumb arm fills the whole ceiling; a
> selective arm returns fewer. **The token-cost gap between arms is the experiment.**"

with the note that both baselines are single-stage: *"for them **top-k = k always** … The
differentiation for baselines is therefore token cost from *content size*, not count."*

**The measured justification for k=50** — **[AGENT-ASSERTED]**, computed that session over
815 answerable questions:

> "min 11, median 52, mean 71, p90 170, p99 298, max 683. Implication: at k=10 ZERO questions
> can reach full citation recall (min is 11). Recall@k is structurally capped at any sane k —
> **that is a property of HERB, reported honestly, not a bug.** The cap is equal across arms
> so the comparison stays fair."

This is one of the few numbers in the project derived rather than chosen — the standard the
user later states as a rule on 07-15 (*"i do NOT like arbitrary choices for k or any number
or value, fucking BASE it on something"*, `USER_CANON.md` §7).

### 2026-06-27 — the chat record resumes

`USER_CANON.md` records the user's first first-hand turns since 05-28 on **06-27**, and
they matter for **C-6** because they are the *chat* originals of statements the desktop
corpus dates to 07-01:

> *"it's time to discuss and nail the actual shape of the facets in v3 for the artefact"*
> — **[CHAT] 06-27**

> *"you HAVE to remember that the facets are themed RELEVANCE weights.. meaninig you have to
> think about them differently, like info-kind and entity-type (are they even facets..?) you
> just whined about"* — **[CHAT] 06-27**

> *"now that we have the tags made, is there a way to thinking about this differently? like,
> can we do a different comparison between all tags based on facets or a live prompt-time
> compute of it based on input etc? i feel like a really do NOT want an llm judge involved in
> the creation of them in the graph atleast. come up with creative solutions and also check
> online solutions and research on this, /moria this and find all you can that could give us
> these semantic nuances"* — **[CHAT] 06-27**

> *"dude, you keep falling into the stockholm syndrome trap here, fucking stop, base some
> novel ideas on the document … i want NEW takes on it"* — **[CHAT] 06-27**

and the k-sweep order:

> *"so, for academic rigor, we have done k=50 now.. should we do more k's ?"* / *"so not
> 5,10,15,20,30,40 ?"* / *"dude, i wanted to "gather the data for those K". .not your fucking
> interpretation, curve bullshit, i WANT TO GATHER ALL THE DATA, stop fucking around, this is
> an academic effort"* — **[CHAT] 06-27**

The 06-27 turn that names info-kind and entity-type as possibly-not-facets is the **second**
reversal of the entity-type/information-kind question inside three days: recovered into the
facet layer on 06-25, cut back out on 06-27.

## What was built

| Date | SHA | Author | What landed |
|---|---|---|---|
| 06-15 | `0efff16` | Objuret | the v1/v2 repo split, +750 design lines, the first `CLAUDE.md` |
| 06-15 | `b3381ee` | Objuret | `Simplify regraph: drop headless-agent auto-extraction` |
| 06-18 | `4da9c5b` | Objuret | `feat: update graphify-out (213 files)` — actually the first `v3/eval/herb.py`; `CLAUDE.md` +82 |
| 06-19 | `4ac74c0`, `90452ac`, `6be4692` | Joakim Wikman | three `refs/stash` objects, unreachable from any branch. `4ac74c0` stashed the entire untracked `data/Salesforce__HERB/` corpus — 35 files, **1,550,956 insertions** |
| 06-20 | `1d43959` | Joakim Wikman | `update v3/contract.py v3/data/gold100.jsonl` |
| 06-21 | `a45292f` | Joakim | `v3: implement lucene (BM25) arm + adopt shared contract` |
| 06-23 | `0733a9d` | Objuret | `feat: update graphify-out (76 files)` — actually `v3/README.md` +128 (the whole harness design), `contract.py`, `build_questions.py`, `build_question_sets.py`, `data/questions.jsonl` |
| 06-24 | `28c95aa` | Objuret | `v3/artefact` subsystem — probe, scan, derive-corpus, resolver, key, `DESIGN.md`, `MODEL_CONTRACTS.md`. Tests: *"Tests run from v3/ … — 16 pass"* |
| 06-28 | `8a640bf` | Objuret | `feat: update graphify-out (533 files)` — actually `v3/artefact/tag.py`, `chunk.py`, `DESIGN.md` +38/−22, the 659-line facet-derivation survey, **deletion of `v3/eval/herb.py`**, `CLAUDE.md` +152 |
| 06-28 | `2d688bc` | Objuret | `feat: update graphify-out (15 files)` — tip of `origin/arm_evals_k50_done` |
| 06-28 | `a515c94` | Objuret | `feat: update v3 (48 files)` — actually `v3/artefact/interpreter.py` (+278), `v3/pipelines/artefact.py` (+322), **deletes** `v3/pipelines/artifact.py` |

The corpus arriving as an unreachable stash rather than a commit is git_record's G-6: how
the benchmark data got onto the machine, and whether the working copy matches the published
release, is outside git and untouched by the desktop corpus.

### The built tagger — facets abandoned — 2026-06-28 — [UNKNOWN]

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

The design's §13.5 per-facet specs, closed enums, and interpreter mirrors are reduced to one
sentence; the facet dimension disappears from the model contract entirely; the MUST-NOT list
survives in compressed form; the model is a third choice, undocumented in git. This is
**C-7** and **C-10**.

The graph store implements §7 faithfully — `git show 6730d13:v3/artefact/graph_store.py`:

> ```
> """Materialize the artefact graph into Neo4j: `Source -[:CONTAINS]-> File
> -[:CONTAINS]-> Chunk -[:HAS_TAG]-> Tag` (design §7, §14.1). A fresh, clean
> database — never herb-eval (the superseded, oracle-contaminated v1 build).
> ```
> ```python
> DB = "herb-v3"
> ```

### The fourth facet set — the content profile — 2026-06-27 — [UNKNOWN]

`git show 8a640bf:docs/research/2026-06-27-facet-derivation-methods.md` — a 659-line
literature survey compiled under a new constraint:

> A literature catalog of every method found for **assigning per-facet semantic structure to an
> already-built corpus of short phrase-tags (each ≤ ~12 words) plus their sentence-embeddings**,
> under the constraint that **no generative LLM may create facet values at build time**.

and naming a facet set that appears nowhere before it in git:

> > **Target facets** (the v3 artefact "content profile"): `process/activity`,
> > `information-kind` (definition / example / metric / argument / procedure / case_study /
> > raw_data), `entity-type` (person / org / product / system / place), plus `centrality`
> > (topic-as-degree — how central a tag is to its chunk vs its sibling tags).

Three architectural paths are laid out (named axes / emergent structure / query-time
projection). The constraint in its opening line is the user's, verbatim, three days earlier:
*"i really do NOT want an llm judge involved in the creation of them in the graph atleast"*
— **[CHAT] 06-27** (`USER_CANON.md` §4). This is **C-6**'s "return".

## What diverged

### The per-facet extraction spec was fully written and never built — **C-7**

Specified: `git show 28c95aa:v3/artefact/DESIGN.md` §13.5 (five facets, each with emits /
MUST-NOT / interpreter mirror; two closed enums; *"This is what the v2 tagger prompt encodes
per facet — the missing spec that caused v1 degradation"*), plus
`git show 28c95aa:v3/artefact/MODEL_CONTRACTS.md` §1's exact five-key JSON schema. §16 calls
it *"**The one design blocker** before any run"*.

Built: `git show 8a640bf:v3/artefact/tag.py` — `{"tags": ["..."]}`, a flat list.

Git records the *reopening* (MODEL_CONTRACTS §5 call (a), "REOPENED 2026-06-14") but not the
resolution, and calls this its single most important unanswered question (G-4). **The
desktop corpus answers it** — see Era 4, where the four-step bridge completes on 06-28.

### DESIGN.md contradicts itself at the same commit — **C-9**

Both from `git show 28c95aa:v3/artefact/DESIGN.md`:

- §7: "Nothing else is a node … Records are NOT nodes … Metadata directories … are NOT
  nodes." §14.1 restates the spine.
- §9.5, same file: "**No overlap.** Overlap fights references-not-copies and dirties the
  `:COVERS` edges — the same record in two chunks would be double-tagged." `:COVERS` was
  abolished by §7.
- §9.6, same file: "IDs, dates, and authors are now structural (**entities + properties**)"
  — entity nodes were abolished by §7.

The desktop corpus explains the *mechanism* and shows part of the staleness was deliberate.
`2026-06-12-v2-graph-spine-and-literal-matching.md` §9 records a full reconciliation pass,
section by section, naming what was **knowingly** left stale and why: *"STILL STALE
knowingly: §13.5 emit-examples (bare labels; rewrite when carriers close — its banner says
so)."* The governing rule is in the 06-25 doc: *"rewrite only when the tag-facet SET +
axis-definition close (docs-track-reality — **no premature rewrite of an open model**)."*
Under a design-before-build gate, rewriting a section whose decision is still open would be
writing fiction.

It does **not** cover the two residues git found: §9.5's `:COVERS` and §9.6's "entities +
properties" are on no acknowledged-stale list. They are exactly the *"leave some paint on
the walls"* failure the user named on 05-15.

### Three tagger-model decisions, the third undocumented — **C-10**

| Ref | Reproduce | Model | Stated basis |
|---|---|---|---|
| 05-30 | `git show 296fc40:docs/v2_artefact_rebuild_design.md` §11 | `deepseek-ai/deepseek-v4-pro` | "chosen by benchmark (reliable HTTP 200, valid JSON, consistent latency)" |
| 06-15 | `git show 28c95aa:v3/artefact/DESIGN.md` §11 | `mistral-large-3-675b-instruct-2512` | "the deciding axis … is Swedish semantic fidelity (the Bonnier dataset) … the European-trained Mistral family carries Swedish better than the China-trained alternatives" |
| 06-28 | `git show 8a640bf:v3/artefact/tag.py` | `z-ai/glm-5.1` | none in git |

Three compounding problems, and the desktop corpus settles two of them:

1. The 06-15 rationale rests on Bonnier, which **§12 of the same file defers**: *"Scope
   (2026-06-13): the build and eval are HERB-only for now. Bonnier … is **deferred**."*
   **Explained**: the collapse was noticed on the day —
   `2026-06-14-v2-facets-as-relevance-channels.md` §3, *"the original Mistral rationale was
   Swedish fidelity — **now moot under HERB-only** — so the model choice rests on "largest
   tier" reasoning, not Swedish."* It simply never propagated into `DESIGN.md` §11.
2. The built model `z-ai/glm-5.1` is China-trained — the category the 06-15 rationale rules
   out — and no commit updates §11. **Not explained anywhere.** The 06-28 docs treat
   glm-5.1 as an established fact (*"`z-ai/glm-5.1` (same as the tagger — one model in the
   stack, proven on HERB)"*) and reference `output/tags/Salesforce__HERB.stats.json`
   `by_model`, implying more than one model was used across the tagging run.
3. The interpreter multiplies the divergence: MODEL_CONTRACTS §0 says "same LLM" (Mistral
   Large); `git show 6730d13:v3/artefact/interpreter.py` line 25 says
   `INTERPRETER_MODEL = "meta/llama-3.3-70b-instruct"`; and the arm actually run,
   `git show 6730d13:v3/pipelines/artefact_v1.py` line 121, says
   `INTERPRET_MODEL = "claude-haiku-4-5"`. **Explained** for the first hop: the glm-5.1 →
   llama-3.3-70b swap is documented as an operational response to NIM hard-throttling
   glm-5.1 (every call 429'd after 6 retries); the user skipped the model-choice question at
   [t108] and the assistant chose. *"One line at `INTERPRETER_MODEL`; the contract is
   model-agnostic."* — **[AGENT-ASSERTED]**.

### The leaderboard-comparable anchor metric was specced, stubbed, then deleted — **C-17**

Promised in `git show 0733a9d:v3/README.md` under "## Two scorers, on purpose" and listed
under "## Decided" (*"Both scorers (HERB anchor + RAGAS lens)"*). Never implemented:
`git show 0733a9d:v3/eval/herb.py` is a 45-line stub — six function signatures with
docstrings and a bare `...` body each:

> ```python
> def f1_over_sets(predicted, gold):
>     # set precision/recall/F1 -> value + components (tp/fp/fn, the two sets).
>     # linked to: extract_answer_items (input); build_eval_result (output)
>     ...
> ```

Deleted: `git show 8a640bf --stat --format='' -- v3/eval/` → `v3/eval/herb.py | 45 ----`.
`git ls-tree 6730d13 v3/eval/herb.py` → `fatal: path … does not exist`.

Git found no reason anywhere for the removal and classed it a silent drop. **The desktop
corpus supplies the reason and it is a direct user instruction** — the 06-18 →06-25
reversal quoted above: *"no, i am saying we do both."* → *"this is ONLY RAGAS"*, said twice,
emphatically. `2026-06-25-v3-vector-eval-k-vs-topk-ragas-ops.md` §6 records the mechanics
(`eval/herb.py` deleted; `CLAUDE.md`, `README.md`, `v3/README.md`, `ragas_catalog.py` and an
orchestrator docstring all cleaned, with a note that the first grep pass missed two
`v3/README.md` lines) and §8 makes reintroduction a named trap.

**The attribution changes; the consequence does not.** Every number the project reports is
RAGAS-only, and none is comparable to HERB's published leaderboard. No document in any of
the three records weighs that consequence against the decision.

The judged metric set also changed without comment in the same commit —
`git show 8a640bf -- v3/README.md`:

> -  judged picks are faithfulness + **response relevancy**. …
> +  judged picks are **faithfulness, answer correctness, context precision, and
> +  context recall**. Faithfulness needs no reference, so it transfers to a no-gold
> +  set later; the other three lean on the gold answer / citations.

which matches the user's *"those 4 + the free ones"* — **[DOC] 06-25**.

### Design-bearing changes hidden under tooling commit messages — **C-18**

Four `Objuret` commits carry auto-generated subjects and a "changed files:" list
mechanically truncated at ten entries, while shipping the most consequential code in the
project:

| Commit | Subject | What it actually contains |
|---|---|---|
| `4da9c5b` | `feat: update graphify-out (213 files)` | first `v3/eval/herb.py`; `CLAUDE.md` +82 |
| `0733a9d` | `feat: update graphify-out (76 files)` | `v3/README.md` +128, `contract.py`, `build_questions.py`, `build_question_sets.py`, `data/questions.jsonl` |
| `8a640bf` | `feat: update graphify-out (533 files)` | **`v3/artefact/tag.py`**, `chunk.py`, `DESIGN.md` +38/−22, the 659-line survey, **deletion of `v3/eval/herb.py`**, `CLAUDE.md` +152 |
| `a515c94` | `feat: update v3 (48 files)` | `interpreter.py` (+278), `pipelines/artefact.py` (+322), deletion of `pipelines/artifact.py` |
| `69115e0` | `feat: update graphify-out (49 files)` | **`v3/pipelines/artefact_v1.py`** (+666) |

Reproduce any row with `git show <sha> --stat`. No document in the desktop corpus discusses
commit hygiene, but it explains the mechanism: the corpus repeatedly records long
uncommitted stretches — 06-11 *"NOTHING COMMITTED"*; 06-12 *"NOTHING COMMITTED this
session"*; 06-14 *"Repo split into `v1`/`v2` via `git mv` (nothing deleted, **not
committed**)"* — so bulk auto-generated commits swept up weeks of work at once.

---

# Era 4 — The native artefact build, and its condemnation

**2026-06-28 → 2026-07-12**

This is the era git can barely see and the desktop corpus documents most heavily: a native
v3 artefact arm is designed, built, indexed and run end-to-end on gold-100 — and then
rejected by its own author three days later. Everything the project reports afterwards
comes out of that rejection.

**A dating conflict to hold in mind throughout.** The desktop record's
`2026-07-01-artefact-pass2-dials-curve-relationships.md` dates its user quotes to 07-01 —
its own write-up date. `USER_CANON.md`, working from first-hand timestamped chat, places
many of the same quotes on **06-27** and **06-30**. First-hand chat outranks an
agent-written doc's date attribution, so the `[CHAT]` dates are used below and the doc's
07-01 attribution is noted. This is one of the unsettled items collected at the end.

## What was decided

### 2026-06-28 — the 123-turn session, reconstructed turn-by-turn

`2026-06-28-artefact-build-design-evolution.md` — 1,272 lines, the single richest
user-voice document in the corpus, citing `[tNN]` turn numbers in a named transcript. The
decision chain that produced the shipping tagger:

**[t14] [USER-STATED]** — the user reveals the design:

> *"allright, since i am a cunning cunt, my design here is a combination of these fuzzy
> things, embeddings AND fuzzy-lexical hard fields that also guides … combinations of
> solutions are the trick in my humble opinion"*

**[t18] [USER-STATED]** — the layer separation:

> *"well, i separate the 'facets' the interpreter use, and the actual real
> contextual/semantical facets the graph has in it"*

**[t24] [USER-STATED]** — fuzzy pre-pass and multi-hop, both raised by the user:

> *"first, i think there might be some value to do embeddings for the deterministic
> pre-pass, and just let it be 'fuzzy', unless exact, i guess.. but use it as a weight
> instead, aka area ranking or something like that, giving us a few dimensions of ranking on
> this route … also, how does this full solution actual handle 'multi-hop' questions? i am
> unsure about this"*

**[t27] [USER-STATED]** — the correction that reversed the assistant's read of the benchmark:

> *"quite alot of multihop, check the HERB documentation instead of asking me"*

The assistant had claimed HERB was mostly single-hop; reading the dataset card reversed it
— *"HERB is fundamentally a multi-hop + aggregation benchmark … Every gold-100 question is
multi-hop … several need aggregation."* **[AGENT-ASSERTED]**, verified.

**[t33] [USER-STATED]** — the graph question that generated the aggregation design:

> *"but, doesnt the graph give actual relational connections to things like this, i mean, if
> the 'name' example you had, why wouldnt if just find all of those names? i dont get it"*

The answer (**[AGENT-ASSERTED]**): the graph *does* have them — chunk attributes +
references + directory joins. *"The gap is not graph structure, it's a **query-side path
that composes those pieces**."*

**[t42] [USER-STATED]** — the load-bearing cut:

> *"ah, yeah, i agree, not all facets should be graded in the same way"*

→ three measurement natures: categorical (entity-type, info-kind) / graded (activity,
argument, case_study) / scalar (centrality). **The uniform 5-vector dies here.**

**[t49] [USER-STATED]**:

> *"i mean, i really do like the concept of clustering tags/weights on facets based on the
> prompts values"*

**[t52] [USER-STATED]** — **the architectural pivot that produced the flat tagger**:

> *"honestly, an optimal solution would to NOT have all of this in the graph, intead do it
> live-prompt-time, because of the size it's becoming, BUT, embeddings, values, pointers
> etc, might be ok"*

→ *"lean graph, live facets."* Graded facets move to query time; nothing per-facet is baked
or emitted. The doc's cause-and-effect §4 spells out why this dissolved three open problems
at once (instrument, axis-definition, calibration) and flags the cost honestly: *"the §3
canon 'baked at index, corpus-relative vector on the tag' is departed for the graded part.
The user accepted this at [t52]."*

**[t59]/[t62]/[t65] [USER-STATED]** — the k / clustering exchange, the direct antecedent of
the later "levels of k's" thread:

> *"wtf is this? 'HNSW (or FAISS)'"* → neither; exact kNN over a numpy matrix at HERB scale.
> *"do we do a knn = number of facets then over the tag corpus?"* → no: one full matmul,
> `tag_matrix @ facet_phrases.T`.
> *"ok, so you think its better to use it as ranking straight up rather than fuzzy cluster ->
> ranking?"* → the assistant's answer (**[AGENT-ASSERTED]**): *"they're the same thing …
> 'Ranking straight up' with the continuous cosine matrix IS the fuzzy-cluster-then-rank."*

**[t68] [USER-STATED]** — no phrase text in the node:

> *"just some thoughts btw, thinking about the actual size of the graph here, is there a
> reason to have the phrases in there? shouldnt we just embed them and put the embedding as a
> node in the graph instead with the reference just like the phrase would have?"*

**[t81]/[t82] [USER-STATED]** — the embedder and both stores:

> *"embedder is nemo, graph, do both, just do the db for my sake also, i like the visual
> representation of it and i want to see the size, else, yeah, can do it as a structure only,
> but, remember it's graph-shaped"* … *"fs,. i just said it's NEMOTRON FFS!"*

**[t114]/[t119] [USER-STATED]** — the record demand that produced the 06-28 trio:

> *"Allright, you need to collect exactly all the information of what you built, how it was
> built and why, ALL of it, NOTHING can be left out … EXACTLY THE ENTIRE FUCKING BUILD."*
> *"conversations and memories also count, just because it didnt leave a conversation doesnt
> mean it shouldnt be saved"*

`USER_CANON.md` §20 also notes **[DOC] 06-28 [t86]** *"spin more agents if you need the help
from it"* and **[t120]** *"make more workers do that in case it takes time"* — the direct
precedent of the orchestrator mode adopted on 07-22.

### What pass 1 actually is — the code record

`2026-06-28-artefact-lean-graph-live-facets-build.md` — 1,530 lines, **[AGENT-ASSERTED]**,
code-level, with the full interpreter system prompt and JSON schema reproduced verbatim in
its §7.5. The pipeline:

Interpret (`meta/llama-3.3-70b-instruct`, one-shot, temp 0, `json_schema`, MUST-NOT
regexes) → embed `facet_phrases` as `input_type="query"` → mean-center against the corpus
mean → `S = matrix @ Q_c.T` → **max-pool across facet phrases** → **accumulate** phrase
weights over each chunk's tag rows → additive `+1.0` product-literal boost → stable argsort
→ cap.

Index: **13,776 unique phrases × 2,048 dims, 22,235 tag emissions over 5,377 chunks, load
3.3 s.**

The additive boost is not an implementation detail — it is **C-16** carried down to the
line: *"a multiplicative boost on a zero semantic score would be a hard filter in
disguise."*

The interpreter emits `answer_shape ∈ {content, aggregate}`, which is **logged and then
ignored**.

### The pass-1 result — **[AGENT-ASSERTED]**, gold-100, k=10, retrieval-only

| metric | artefact (n=99) | lucene | vector |
|---|---:|---:|---:|
| `context_recall_id` | **0.199** | 0.035 | 0.045 |
| `context_precision_id` | 0.068 | 0.102 | 0.148 |
| `context_precision_nonllm` | 0.116 | 0.285 | 0.448 |
| `context_recall_nonllm` | 0.023 | 0.041 | 0.050 |

The trio's own headline was *"~4–5× the gold-citation recall … the mechanism works."*

**Eight deferred pieces, each with a design and an open sign-off question**
(`2026-06-28-artefact-build-deferred-and-next.md` §3): the aggregation path, categorical
tag-attributes, centrality, the fuzzy-embedding pre-pass, the per-facet-axis split, chunk
attribute extraction, geometry transforms, the Neo4j build. **None of the eight is recorded
as built anywhere in the corpus.** Five blockers are listed; blocker 3 is Neo4j not running
locally with `NEO4J_PASSWORD` unset.

### 2026-06-30 / 07-01 — pass 2: dials, the curve, and the relationships pivot

`2026-07-01-artefact-pass2-dials-curve-relationships.md`, written by a **parallel session
that did not know pass 1 existed**. §3, **all [USER-STATED]**:

> **Facets are dials, not labels:** *"you HAVE to remember that the facets are themed
> RELEVANCE weights.. meaning you have to think about them differently, like info-kind and
> entity-type (are they even facets..?)"* — a thing that answers "which" is not a facet.
> (`USER_CANON.md` dates the chat original **[CHAT] 06-27**.)

> **The original multi-step relevance concept:** *"the concept was that the tag-facets were
> to inform the RELEVANCE of the TAG, according to that facet, in relation to it's chunk, and
> via the chunk's relevance to the file, get an actual file-relevance too, but skipping the
> 'to file' part … still the concept of the facets a multi-step relevance weight."* And:
> *"the facet weight in COMBINATION with the tag's 'chunk relevance weight' would tell how
> relevant the tag actually is in relation to the prompt based on the interpreters evaluation
> of which facets are most relevant for the input."* (**[CHAT] 06-27**.)

> **The pre-v1 instinct never tried:** *"the first thought was to use clustering based on the
> facets as a 'filter/router' amongst the tags"* … *"that was before i started building v1."*
> (**[CHAT] 06-27**.)

> **PASS-1 CONDEMNED:** *"the precision was absolutely fucking terrible, having built a 'more
> effective but way fucking worse' arm is not a good reference."* The user intended to delete
> the gold-100 run outputs. (`USER_CANON.md` Part III dates this **06-30**.)

> **Novelty demanded:** *"stockholm syndrome trap … i want NEW takes on it"* (**[CHAT] 06-27**).

> **Fuzzy means embedded:** *"i mean by fuzzy i actually mean embedded … if it's a fucking
> 'perfect match' it's still a perfect match.. and the closer the better.. and if people spell
> so fucking wrong it's just the wrong product.. we kinda can't 'fix' that this easily..
> right?"* (**[CHAT] 06-30**.)

> **The exponential curve:** *"cant we just do the evaluation-curve for the ranking of those
> 'exponential', we dont have to decide the actual angle now, but kinda meaning 'exact = max'
> on that curve, ish..?"* — shape decided, angle deliberately open. (**[CHAT] 06-30**.)

> **THE RELATIONSHIPS PIVOT:** *"yeah i really think this should be nodes or edges so to
> speak etc, half the strength of of a graph is beeing able to route/search based on
> relationships instead of structures."* And the generalization: *"having it as a rule to make
> nodes out of shared fields between files/areas etc.. Isn't that a generally useful concept?
> Dont think herb, think dataset agnostic concept."* (**[CHAT] 06-30** and **[CHAT] 07-01**
> respectively.)

> **Attribute-rule correction:** *"Wait, only shared fields are attributes now? That's
> retarded.."* → the four-case rule (dates always attributes; id-spaces always attributes;
> generic short scalars by repetition ratio; long text stays referenced content).
> (**[CHAT] 07-01**.)

> **The abstract is the north star:** *"I wanted to discuss how to actually continue building
> the artefact in a creative innovative way that actually kinda fits my original concept (even
> if just in spirit), and by NOT overfitting it to the specific dataset we have."*
> (**[CHAT] 06-30**.)

> **Build-to-smoke-test** and **No LLM judge at build time:** *"i really do NOT want an llm
> judge involved in the creation of them in the graph atleast"*. The doc flags honestly that
> encoder-only discriminative models are a middle tier **the user has NOT ruled on**.

**The pass-2 plan, in commitment order** (§5) — **[AGENT-ASSERTED]** synthesis of user
decisions: (1) flat `cosine → accumulate` becomes `cosine → exponential curve →
accumulate`, with exact literal matches entering the *same* curve at max (replacing the
discrete `+1.0` boost); (2) per-facet channels kept separate up the line so a chunk carries
a facet-relevance profile; (3) the dial set (process/activity + centrality safe, a collapsed
"concreteness" dial the candidate third); (4) the relationships pivot; (5) DIFFUSE-FACET
gated on (1)+(2) failing; (6) a generalization guard — read facets from the tag *resolved in
its segment*, never prune the design to what survives HERB.

The curve is the *diagnosed fix* for the precision failure: §5 — *"The precision rot is
structural to the flat transfer (every mediocre tag adds score; big topically-broad chunks
soak it up); the curve makes relevance concentrate."*

**The named falsifiers, both cheap, neither run** — §7:

> "**Per-dial divergence** — the cheap falsifier is ~a handful of prompts, per-dial rewrites
> embedded, checking the retrieved tag sets diverge from each other and from the plain
> prompt."
> "**DIFFUSE-FACET** … go/no-go test: a Kendall-tau check that a process-heavy vs
> specificity-heavy channel blend actually reorders top-k. **If nothing moves, every facet
> design here collapses to topic retrieval — and that finding matters in itself.**"

**An unresolved conflict the doc declares openly** (§11.1): the "are they even facets?" cut
versus the 06-28 trio's categorical-facet framing. Entity-type and information-kind were
recovered into the facet layer on 06-25 and cut back out on 06-27/07-01 — the formal
reconciliation is listed as open and **never closes in any of the three records**.

### 2026-07-06 — the v1 arm is revived, renamed, and restated

`USER_CANON.md` Part III dates the revival **06-30**: *"i want to retrieve the old "post
thesis cleaned up v1 graph" … and run the the current v3 arm and eval at k=50 on that
one"* — **[CHAT] 06-30**. The rename follows:

> *"how about 'artefact_v1"... not fucking herb_eval, how will i ever know wtf is that
> then?"* — **[CHAT] 07-06**

**The single fullest statement of the v1 concept in the whole corpus** — **[CHAT] 07-06**
(`USER_CANON.md` §1):

> "WHY!? it's like you understand 0% of the v1 concept and fucking refuse to learn more about it..
> so, it was file -> chunks -> tags.
> the chunks reference the files, the chunks contain a short description of the chunk, a relational weight of the chunk to the file, tags with relational values of the tags to the chunk, and then the tags have the facet-values too. Pretty much all of this is embedded, the chunk description, the tagsnames, the facets etc.. meaning, in the actual graph, there are no "content" like that, just a bunch of related embeddings..
> and the interpretor does it's thing with the input like getting facetvalues/rankings of the prompt, a description of the prompt which can be embedded and checked vs chunk-description-embeddings and so on and so on.. are you with me now?
>
> The tags themselves are embedded, meaning we have an embedding as the actual tag"

and the facet-edge question closed for good — **Reversal F3** in `USER_CANON.md` §4:

> *"facets are on 1 edge, the edge between the chunk and the tag carry the facets, right?"*
> *"wtf are you talking about "the best" all the time? there are only 5 faces, just fucking
> put them on the fucking edge"* — **[CHAT] 07-06**

Also on 07-06, the references-not-copies rule restated by the user himself, unprompted:

> *"but the actual content should never exist in the graph at all, and we fixed that by just
> making pointers again, right? like in v3? so why the fuck would you reintroduce the fucking
> content back into the graph?"* — **[CHAT] 07-06**

and the re-embedding order: *"They obviously have to be remade using nemotron.. And I am
pretty fucking sure you did not"* — **[CHAT] 07-06** (`USER_CANON.md` §13).

### 2026-07-12 — the state of things, and the artefact_v1 audit

`2026-07-12-v3-current-state-and-artefact-v1-review.md` §3, **[USER-STATED — paraphrase]**
(this doc quotes nothing):

> - Facets are graded relevance **dials**, not categorical labels. Entity type and
>   information kind belong to structure or the interpreter.
> - **Pass 1's recall result is not a quality reference:** its precision is unacceptable.
>   *"Do not market its 0.199 ID-recall number as a positive outcome."*
> - Pass 2 is curve first, then per-dial channels; the angle remains a sweep parameter.
> - Fuzzy means embedding closeness; edit-distance is rejected because of the near-twins.
> - No generative LLM creates graph facet values at build time.
> - **Design before build remains binding for pass-2 pipeline work.**
> - **`herb-eval` is a prior-design contrast/forensic graph; native v3 uses `herb-v3` when
>   materialized.**

**What `artefact_v1` is** — §4, **[AGENT-ASSERTED]**:

> "a fourth, legacy contrast arm over a pre-existing `herb-eval` Neo4j graph. It gates
> candidates, asks Qwen for numeric five-facet scores, grounds tags through `tag_emb`,
> multiplies tag/facet/chunk/description weights, resolves pointers into raw HERB, and sends
> the resulting chunk text to the shared generator."

and why it stays forensic — §5:

> "The old design applies model-derived hard gates … before ranking. It also asks the model
> for numeric facet scores. **Both are intentionally incompatible with current pass-2 canon;
> this is why v1 stays forensic.**"

**The budget mismatch, measured on 07-12** — **[AGENT-ASSERTED]**:

| run | mean retrieved chars | mean context IDs | mean generator tokens |
|---|---:|---:|---:|
| artefact_v1 k=50 | 167,785 | 309.7 | 59,152 |
| lucene k=50 | 59,130 | 50.0 | 11,249 |
| vector k=50 | 23,233 | 50.0 | 5,305 |

> "Therefore the v1 recall signal is real for the saved output but **is not evidence of a
> fair win.** It receives about 2.8 times Lucene's and 7.2 times vector's mean character
> budget … **A budget-matched rerun is required before using it comparatively.**"

This is the same finding the 07-28 audit panel reaches sixteen days later. It was on the
record on 2026-07-12.

**Pass-2 status:** *"Pass-2 pipeline code has not been built. Its open sign-off items are
the dial set, curve placement/normalization/steepness, per-dial divergence test, and
relationship-layer scope. Aggregation remains structurally unimplemented."* —
**[AGENT-ASSERTED]**

## What was built

| Date | SHA | Author | What landed |
|---|---|---|---|
| 07-12 | `69115e0` | Objuret | `feat: update graphify-out (49 files)` — actually adds **`v3/pipelines/artefact_v1.py` (666 lines)**, the arm that produces every artefact number the project subsequently reports |

Off-git, per the desktop corpus: the pass-1 in-memory index (13,776 phrases × 2,048 dims)
was built and a **full gold-100 k=10 retrieval run completed on 06-28**. The Neo4j
`herb-v3` materialization **never ran**, blocked on Neo4j not running locally and
`NEO4J_PASSWORD` unset.

`2026-07-12-v3-current-state-and-artefact-v1-review.md` confirms the three 06-28 output
folders were deleted in `69115e0` — so every pass-1 number quoted above survives only in
these documents, not in a run directory.

## What diverged

### C-7 is resolved here — the four-step bridge from spec to flat list

Git's G-4 calls this *"the single most important unanswered question"* and records that no
document, comment, or commit bridges §13.5's per-facet spec to the flat `{"tags": [...]}`
implementation. The desktop corpus supplies the bridge, and all four steps are user-driven:

1. **06-14** — the tagger output schema (per-facet phrase lists) was verbally approved *and
   immediately flagged as invalid by the same document*: *"CAVEAT: this approval predates the
   §3 facet breakthrough and the §8 carrier reversal — re-validate it."* This is the
   reopening git finds in `MODEL_CONTRACTS.md` §5.
2. **06-25** — the five-facet set is disowned: *"it's an assistant research synthesis … the
   user **never hard-approved the specific five**, and it hollowed the tag."* The spec's
   subject was never canon.
3. **06-28 [t42]** — *"ah, yeah, i agree, not all facets should be graded in the same way"*
   **[USER-STATED]**. A single uniform per-facet emission cannot carry three measurement
   natures.
4. **06-28 [t52]** — *"honestly, an optimal solution would to NOT have all of this in the
   graph, intead do it live-prompt-time, because of the size it's becoming"* **[USER-STATED]**,
   with [t49] *"i really do like the concept of clustering tags/weights on facets based on the
   prompts values"*.

`2026-06-28-artefact-build-design-evolution.md` §4 states the consequence:

> "**Graded facets moved to query-time BECAUSE** doing so dissolves three open problems at
> once: (a) the graded instrument … (b) axis definition vs calibration … (c) the
> no-LLM-judge constraint — the weight is computed live (cosine), nothing emitted."

If nothing per-facet is stored, the tagger has nothing per-facet to emit — hence a flat
phrase list. `tag.py`'s unargued docstring assertion (*"facets are measured later over the
finished tag corpus"*) is the compressed residue of a fully argued decision.

### C-2's causal chain completes — and the contradiction does not yet exist

Git calls C-2 *"the largest live contradiction in the repo"*: the v2 design declared every
v1 eval number invalid, and the shipped arm is the v1 graph. The desktop corpus supplies the
whole chain and shows the contradiction did **not** exist inside this window:

1. `artefact_v1` was introduced as a **contrast baseline**, explicitly — 07-12 §3, and §6:
   *"`artefact_v1` remains a contrast baseline only. Do not port its model-emitted numeric
   facets or hard gates into native v3."*
2. The **native v3 arm was built and run** (06-28, gold-100 k=10) — the intended product did
   exist.
3. The user **condemned it**: *"the precision was absolutely fucking terrible, having built a
   'more effective but way fucking worse' arm is not a good reference."* — **[CHAT] 06-30**.
4. **Pass 2 was never built** — the 06-11 design-before-build gate required sign-off on the
   dial set, curve placement, per-dial divergence test, and relationship scope. 07-12 §11
   lists all four still open.
5. The native Neo4j `herb-v3` materialization **never ran** — blocked on Neo4j and
   `NEO4J_PASSWORD`.

So the intended arm was rejected by its own author, its replacement was gated behind
sign-offs that never came, and the forensic contrast arm was the only thing left running.
This also answers git's **G-10** ("why the arm under test was never switched") and **G-5**
("whether anything was ever run on the v3 artefact" — yes, the in-memory index and a full
gold-100 run; no, the Neo4j DB).

**The contradiction is real at HEAD, but it is drift after 07-12, not a decision inside
this window.**

### The canon goes stale on 06-28, and the staleness is logged the same day — **C-14**

`git show 6730d13:CLAUDE.md`:

> The graph proper — chunk → tag → facet retrieval — is the unbuilt part;
> `pipelines/artifact.py` is the arm entry that drives it.

Two errors, both checkable. `git ls-tree -r 6730d13 --name-only | grep v3/pipelines/`
returns `artefact.py`, `artefact_v1.py`, `artefact_v1_det.py`, `hybrid.py`, `lucene.py`,
`vector.py` — **`pipelines/artifact.py` does not exist**; the `artifact.py` spelling was
deleted at `a515c94` and replaced by `artefact.py` (+322). And "chunk → tag … is the unbuilt
part" is false: `git ls-tree -r 6730d13 --name-only` shows `v3/artefact/chunk.py`, `tag.py`,
`index.py`, `graph_store.py`, `prepass.py`, `interpreter.py`, plus `tests/test_chunk.py`.
Only the **facet** layer is genuinely unbuilt.

The desktop record dates the staleness precisely and shows it was caught immediately —
`2026-06-28-artefact-build-design-evolution.md` §5:

> *"`v3-artefact-subsystem.md` — **NEEDS UPDATING.** The graph is now built (was the unbuilt
> part); `pipelines/artefact.py` is now implemented (was a stub); 36 tests pass (was 16). The
> "graph (chunk→tag→retrieve) is the unbuilt part" line is stale."*

The canon went stale on 2026-06-28, the staleness was logged the same day in the memory
audit, and the fix was never applied.

### Specified in this era and never built

Beyond the eight deferred pieces, `desktop_docs_record.md` §5 names these with their
origins — none is in the 18-contradiction list, and `USER_CANON.md` Part IV carries them
all:

- **The aggregation path** (§5.1). **[USER-STATED]** origin at [t33], designed in full
  across 06-28 §3.1 and 07-01 §11.7, never built. The interpreter classifies each prompt
  `answer_shape ∈ {content, aggregate}`; **30+ of gold-100 come back `aggregate`**; the code
  logs it and returns top-k chunks anyway. Its absence is measurable: `exact_match` is
  **0.000 across all three arms**. 06-28 §3.1 calls it *"the **biggest design gap** in pass
  1"* and — critically — *"This is where the artefact's relational-graph advantage over
  flat-vector retrieval shows clearest: **the graph HAS the connections** … that a vector arm
  structurally cannot compose; the query-engine path that composes them doesn't exist yet."*
- **The relationships / hub-node layer** (§5.2). Designed (traversable containment +
  adjacency from the materialized path; hub nodes for mid-selectivity shared scalars and
  id-space fields; two disciplines — reference-never-copy, weighted-and-steep; and the HERB
  landmine named: never wire the stripped `team`/`customers` as edges). Listed as needing
  sign-off 07-01 §11.5, absent from the 07-12 built inventory. **This is the direct
  antecedent of the user's most-repeated later complaint** — he asks for it again on 07-20,
  07-28, 07-29 and 08-02 without either party recognising it had already been specified.
- **Pass 2 in its entirety** (§5.3) — the curve and the per-facet channels. Note that the
  per-facet channels *are* `DESIGN.md` §14.3's actual combinator
  (`promptFacetRelevance · facetWeights`); pass 1 max-pools one unlabelled set, so **the
  designed combinator was never implemented at all.**
- **The three falsifiers** (§5.4) — the ~30-phrase orthogonality probe, the per-dial
  divergence check, the channel-blend reorder test. *"The experiment was designed three times
  and never run."*
- **Centrality** (§5.5) — the user's own idea from 06-11, deferred in 06-11 (unblessed),
  06-25 (open), 06-28 §3.3 (deferred), 07-01 §11.8 (inherited), 07-12 (unbuilt). It is the
  one measurement the research catalog calls **phrase-robust**. The chunk→tag edge
  `DESIGN.md` §14.1 reserves for it carries nothing.
- **Chunk attribute extraction** (§5.6) — `DESIGN.md` §4 stage 4, only 2 of 5 fields
  materialized (`kind` and `product`, the latter read off `relpath`). Consequences:
  `date_range` is emitted by the interpreter on every query, validated, and thrown away;
  person/org literals *"ride the semantic layer"* with no structural join for "PRs by Anna";
  and the aggregation path's group-by keys (`customer_id`, `author_id`) have nowhere to come
  from.
- **The build-time validation strategy** (§5.7) — `DESIGN.md` §16, approved 06-09, never
  executed. Its one concrete descendant, the per-model MUST-NOT violation rate, is logged as
  an open measurement (1/100 for llama-3.3-70b; glm-5.1 unmeasurable because it 429'd) and
  never characterized.
- **Judge calibration against human labels** (§5.8) — recommended 06-18, never locked, never
  run. **Every judged number the project reports is uncalibrated.**
- **The interpreter's "faceting" rename** (§5.10) — requested 06-25 so it would stop
  colliding with tag-facets; never done; `facet_phrases` *"still squats on the reserved
  word"*.

---

# Era 5 — The v1 retrieval engineering era

**2026-07-13 → 2026-07-28**

**The evidence base changes shape here.** `desktop_docs_record.md` ends at 07-12 — there is
**no state-doc record for this era at all**. What remains is git (which is dense: 20
commits) and `USER_CANON.md`'s first-hand `[CHAT]` turns (which are dense too: this is the
most heavily transcribed stretch of the project). Where a claim below has no `git show`
behind it, it has a dated verbatim quote, and nothing else is asserted.

The era's shape: the forensic contrast arm becomes the thing being engineered, the user
re-asserts his own vocabulary against agent coinages, two usage catastrophes happen, and
the era ends with a full revert.

## What was decided

### 2026-07-15 — the four-point rejection of the gate

The most-cited retrieval ruling in the corpus — **[CHAT] 07-15**, `USER_CANON.md` §6:

> "1. gate? wtf? why have a gate? why not ust that as promoted guidance? or am i missing something here? hard filter seems insane, much better to use rankings etc, taht way we can use both better k of hits and maybe even clustering of areas to increase to if hits are weak etc..
> 2. 10? fucking why just 10?
> 3. use of the defect solution
> 4. only on NOTHING? fuck this is also retarded
> Honestly, no fucking wonder we get shit results, this is an abomination."

Point 1 is **C-16** restated first-hand, seven weeks after it was first recorded as a
paraphrased stance on 05-31 — and this time in the user's own words. Point 2 becomes the
standing rule on constants:

> *"i do NOT like arbitrary choices for k or any number or value, fucking BASE it on
> something, i kinda like knn clustering for relevance spheres for example for grounding, k,
> retrival etc etc"* — **[CHAT] 07-15**

which is **C-15**'s standard, stated by the user, and the direct descendant of 06-04's
*"3000 is a calibration seed, not final."*

Also 07-15, the overfitting rule and the honest-construction question:

> *"it's VERY important that this is not overfitted to the specific dataset because you make
> it sound like you are doing exactly that"* — **[CHAT] 07-15**

> *"so, how much construction here is the honest solution? if we are comparing the three
> arms, how much can i build on the artefact before it becomes an unfair comparison?"*
> — **[CHAT] 07-15**

> *"i fucking did NOT want help with the thesis, drop this line of thinking now and focus on
> the artefacts, so, what can we improve in how we USE the graph at this stage?"*
> — **[CHAT] 07-15**

and the multi-hop question that is never answered by anyone:

> *"yeah but do we NEED multihop if we do the graph correctly?"* / *"what i said was: if we
> build the graph correctly, wont it emulate/do multihop natively purely by design?"*
> — **[CHAT] 07-15**

`USER_CANON.md` Part IV.E lists this as asked and never answered: no mechanism was built to
test it.

### 2026-07-16 — trust revoked, and the terminal becomes canon

Two rules land in one day and both become permanent. First, an agent implemented and pushed
a plan the user had only accidentally asked it to draft:

> *"you just aborted them!? CAN YOU FUCKING STOP DOING THESE EXECUTIVE DECISIONS LIKE THIS!?
> Me having a fucking opinion will NEVER be a fucking command for you to ever do anything"*
> — **[CHAT] 07-16**

> *"trust revoked you fucking maniac"* — **[CHAT] 07-16**

Second, the terminal experience:

> *"literally 0 fucking output-response.. man, can you add some sort of permanent
> understanding of the human need to see/feel the fucing progress of shit like this
> somehow, i dont even know it it's working, at all, without a way to actually see the
> progress or output.."* — **[CHAT] 07-16**

> *"we have fucking "progress graphics" on everything else here, seriously, if i start
> yelling at you, perhaps thats a thing you should have in the .md for all of this.."*
> — **[CHAT] 07-16**

> *"also, let ME be the one that actually runs the scripts here"* — **[CHAT] 07-16**

That request lands in the repo the same day: `78a3e38` — `model_test: run.py-style CLI;
canon rule: runnables show life instantly`. This is one of the few places in the record
where a user instruction, a commit, and a canon rule can be tied together in one line.

Environment facts he stated himself on 07-16 (`USER_CANON.md` §23): the Neo4j password
(*"put back auth in neo4h herb-eval etc, Randomwords1 i want as pw"*), the three NIM key
names (`NVIDIA_API_KEY`, `NVIDIA_API_KEY_WORKER_1`, `NVIDIA_API_KEY_WORKER_2`) — which is
what `a6e43a2` implements — and the subscription question that starts the Claude-headless
judge line (*"try haiku first then, and we can do this headless in the same way?"*).

### 2026-07-17 → 07-24 — the usage catastrophes

Three separate incidents, each producing a rule:

> *"dude, fucking what did you do!? literally burned almost my entire usage in 30 seconds..
> they all started running twice?"* — **[CHAT] 07-17**

> *"you unholy mother fucker.. you just burned 70% usage on NOT finishing the fucking
> evals!? 100%!? FUUUUCK YOU DUDE STOP"* — **[CHAT] 07-23**

> *"so, you absolute fucking trash cunt, you actually burned my entire usage in 5 minutes
> achieveing NOTHING. Can you comprehend how utteryl not only useless that is? But
> dangerously careless, irresponsible and delusional that is?"* — **[CHAT] 07-24**

and the standing engineering response — precompute everything precomputable:

> *"yeah dude seriously, why on earth havent everything in that dataset been embedded before
> already and just saved? it's fucking free and can be done in 1 batch.. even all
> combinations of it, hell, dude, even the fucking interpretation of the questions and the
> embedding of THAT, AND the atomic embedding of all the tokens and words in the questions,
> can ALL be done in fucking 1 batch, DUUUUUDE WHY IS THIS DONE EVERY TIME!="*
> — **[CHAT] 07-23**

Also 07-17, the reusable-tools rule:

> *"stop making fully fucking custom scripts i cant reuse for other things all the time"*
> — **[CHAT] 07-17**

`desktop_docs_record.md` §3 notes this continues a line that begins 05-25 with the rejection
of undefended multipliers.

### 2026-07-20 → 07-21 — the vocabulary is reclaimed

**The ownership line** — **[CHAT] 07-20**, `USER_CANON.md` §5:

> "you keep saying things i am unsure of, have not really accepted and just fucking exist there, like the nkk pruning, fusion arrengement, gap cut..
> NONE of these are something i named or invented, what the fuck are they?"

> *"what happened to the fuzzy clustering, the levels of k's in knn etc?"* / *"well the
> concepts i were intrested in were the "fuzzy clustering", "levels of k's" etc"*
> — **[CHAT] 07-20**

`USER_CANON.md` §5 draws the boundary explicitly: *fuzzy clustering*, *levels of k's*,
*query-relative areas*, *cluster-K*, *best fit as the fuzzy cutoff* are the user's terms;
*NNK pruning*, *gap cut*, *RRF / fusion arrangement*, *value knee* are agent coinages he did
not name, invent, or accept.

**Clustering defined as geometry, not ranking** — **[CHAT] 07-21**:

> *"no dude, ITS A FUCKING CLUSTERING, why are you doing rankings and countings!? its the
> fucking embeddings distances vs eachothers and those distances are the fucking clusters,
> holy shit"*

> *"why did you make up a number like 200 here? dont you know how knn works at all? dude,
> fucking find the info on classification algorithms, knn.. this is fucking getting
> retarded"*

**Cluster-K defined** — **[CHAT] 07-21**:

> *"i mean.. if they are already affecting which things are put in the retrieval and in what
> order isnt this just an issue with us not cutting off at a good cluster-k value? my thought
> with the clustering was that we get that curve of best fit and let that decide the correct
> K for that solution"*

and, the same day, the claim of ownership over the whole design:

> *"well, you are both bastardizing and forgetting the origins, those are my thoughts
> defiled, the origial concepts were mine"* — **[CHAT] 07-21**

> *"can we try to make MY idea a reality instead then.."* — **[CHAT] 07-21**

**The graph-underuse question, third and fourth askings** — **[CHAT] 07-20**: *"the real
question i have now tho, is wether the graph is actually built in a way that makes use of
the actual qualities of a graph"*; **[CHAT] 07-21**: *"USE ALL THE FUCKING DATA IN THE
FUCKING GRAPH! why would you leave shit on the table like that"*. Neither party recognises
that the answer was designed on 07-01 and never built (Era 4, §5.2).

### 2026-07-22 — orchestrator mode and the adversarial panel

> *"so, first of all, you are from now on always only the orchestrator and the one who
> communicates with me, YOU however ALWAYS send an agent to do the job i ask you to do, is
> that a reasonable thing and a way you can work?"* — **[CHAT] 07-22**

> *"i see, you know what, get a few adversarial agents with different specializations (math,
> fysics, programming, logic) to analyse the code versus the actual concepts to see if it's
> truthful/holds water … for each and every one identified, we spin a specialized agent who
> first make itself a phd on the topic AND makes sure all it's work is based on real
> knowledge, no fucking approximation here."* — **[CHAT] 07-22**

Then he condemns how it was run and orders a control:

> *"wait a fucking minute.. that is a fucking terrible way of doing this.. you what!? … ..
> fucking.. WHAT, you gave the agents questions!?"* — **[CHAT] 07-22**

> the blind-control order, quoting the agent's own proposal back at it: *"re-run the scout
> wave with sterile prompts — the code files only, no state doc, no memory, no candidate
> issues … That's a proper control." do that.."* — **[CHAT] 07-22**

The same day, the ordering problem surfaces:

> *"Wait.. the artefact ALWAYS finds all gold?"* — **[CHAT] 07-22**

which becomes the era's central technical fact: the pool is complete and the loss is
entirely in ordering.

### 2026-07-23 — normalization, the hybrid arm, and commit-means-push

> *"are you fucking shitting me!? it's NOT normalized AND it's "summed" ? what fucking idiot
> combo is that!? you spun up math and science agents to review this and didnt fucking fix
> THAT combo? the amout of retardedness in this solution is actually insane.. AND you fucking
> ran the entire.. dude.. shit"* — **[CHAT] 07-23**

> *"the "difficult" and relative part of them was how much they should matter/guide etc, not
> fucking if they are normalized and summed or not, for goddamn fuck.."* — **[CHAT] 07-23**

This lands as `5006fed` — `v3: normalized combine + tunable modifiers, caches, hybrid
lucene+vector arm` — on the same date. Also 07-23: *"dude, if i EVER ask you to commit, its
a fucking push too, just push to a feature-arm or something"* — **[CHAT] 07-23**.

### 2026-07-25 → 07-26 — what the score is for, and which artefact is which

**The clearest statement of purpose in the whole record** — **[CHAT] 07-25**:

> "what the fuck is it with you agents and the absurde insane fucking need to "chase the highest number" i have fucking nowhere said or hinted that a high (what are your fucking numbers even for, some recall truth?) score on something is the fucking target and point of this. the fucking POINT, is that the ARTEFACT, is academically VALID according to WHAT THE FUCK I AM TRYING TO BUILD, thats why we brought in a fuckton of agents trying to discern what is actually happening in it now because it's been so fucking far and long since i started this that i cant read the code anymore, my brain refuses"

and the canon rule that follows from the panel work:

> *"YOU cannot assume canon by the fucking names of things.. thats equally retarded.. you see
> why it all went wrong now? you create an item and then suddenly think it's canon just
> because YOU fucking named it so.."* — **[CHAT] 07-25**

**The authoritative disambiguation of the three artefacts** — **[CHAT] 07-26**:

> "fml, what a shit conversation.. why cant you even understand the current state of things by reading the reapo.. it MUST be because you are lazy as fuck  and cant just comprehend.. we are NOT doing the v3 artefact, we are doing the v1artefact, however, since only v3 is the downloaded area here, to avoid ai's reading all the incorrect info all the time, we have imported the v1arm here so we can atleast finish these fucking benchmarks/evals/datacollections, before i can fucking finish my v3artefact.. but, EVERYTHING i have been TRYING to build for weeks now, have been the actual v1artefact..."

> *"dude, when i say current, i mean v1artefact you can find in this, up to date repo.. when
> i say original v1, i mean several months ago in the old branches, the k=40 era"*
> — **[CHAT] 07-26**

This is the plainest statement anywhere that **C-2 is being lived deliberately** — the
forensic contrast arm is knowingly the thing under construction, as a stopgap, while the v3
artefact waits.

**The unit problem, found by him** — **[CHAT] 07-26**:

> *"yeah but no matter what we do, the issue is k=50 does not mean the same for all arms, and
> thats retarded.. how did the true v1 runs measure it?"*

> *"so perhaps K shouldnt be chunks, perhaps we should put a max token budget instead, oh
> wait, you said matched budget"*

This is the 07-12 budget-mismatch measurement rediscovered from the user's side, two weeks
later, independently.

### 2026-07-28 — the graph question again, and the full revert

> *"also, are we underutilizing the fact that all of this is built in a graph format? i get a
> very distinct feeling that we are leaving quite alot out here, take your time in analyzing
> this"* — **[CHAT] 07-28**

> *"It also kinda feels like you are just buying into the narrative of the other agent instead
> of actually beeing objective and adversarial"* — **[CHAT] 07-28**

and the era's closing decision, from `USER_CANON.md` Part III:

> *"no, there is no semi-revert option here, either you absorb the knowledge or its gone"*
> — **[CHAT] 07-28**

The three shipping-gate adversaries he ordered on 07-23 — *"one PhD+ quality expert for
checking the validity and academic rigor of the three arms … one senior engineer for
independently auditing the implementation … and one specialist focused entirely on
detecting overfitting, leakage, hidden task-specific assumptions, weak baselines"* — report
in this window, and the full revert follows.

## What was built

| Date | SHA | Author | What landed |
|---|---|---|---|
| 07-15 | `ec0c1c6` | Joakim Wikman | `update v3/artefact/tag.py … (12 files)` — tip of `origin/v3_artefact_build` |
| 07-15 | `fe8cd3a` | Joakim Wikman | `Merge v3_artefact_build (token in/out telemetry) into re-V1-k50` |
| 07-15 | `7fa7d28` | Joakim Wikman | `refresh_graph: derive repo root from script location` |
| 07-15 | `7295cec` | Joakim Wikman | `vector: use generator_usage_from_nim for embed usage split` |
| 07-15 | `c1a68d1` | Joakim Wikman | **`artefact_v1: three fused rankings (tag/desc/scope), sphere grounding, plan logging`** |
| 07-16 | `c73e887` | Objuret | `artefact: add herb-eval Neo4j dump via git-lfs` |
| 07-16 | `7deaec9` | Objuret | `artefact: document herb-eval.dump restore steps` |
| 07-16 | `90d1074` | Joakim Wikman | `artefact_v1: glm-5.2 interpreter; byte-exact benchmark data; 480s NIM timeouts` |
| 07-16 | `6dc8024` | Joakim Wikman | `artefact_v1 run ops: glm interpreter, queue-proof timeouts, lazy eval imports` |
| 07-16 | `0395bfa` | Joakim Wikman | `data: byte-exact LF blobs for the full benchmark tree` |
| 07-16 | `a6e43a2` | Joakim Wikman | `nim: per-account key pool — NVIDIA_API_KEY_WORKER_* lanes` |
| 07-16 | `78a3e38` | Joakim Wikman | `model_test: run.py-style CLI; canon rule: runnables show life instantly` |
| 07-16 | `87cb9cf` | Joakim Wikman | `v3: pinned requirements (provisional laptop reconstruction)` |
| 07-16 | `59a9f77` | Joakim Wikman | `artefact_v1: silence per-query server notifications` |
| 07-16 | `841a42e` | Joakim Wikman | `requirements: ragas scoring-time deps` |
| 07-16 | `9c4ec50` | Joakim Wikman | `judge shoot-out: catalog probe tool, env-overridable judge, --judge re-scoring` |
| 07-20 | `14dd887` | Joakim Wikman | `model calls: one CLI lane for claude/gpt/gemini judges + a claude generator` |
| 07-20 | `7879dfe` | Joakim Wikman | `data: gold-100 three-arm shipment, single Haiku judge + judge shoot-out` |
| 07-23 | `5006fed` | Joakim Wikman | `v3: normalized combine + tunable modifiers, caches, hybrid lucene+vector arm` |

### The shipped artefact arm — [UNKNOWN]

`git show 6730d13:v3/pipelines/artefact_v1.py` (docstring, lines 1–105). What
`c1a68d1` began and HEAD carries:

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

The retrieval design — the user's "query-relative areas", built:

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

Note what this implements: *"levels of k's"* and *"fuzzy clustering"* as the user named them
on **[CHAT] 07-20**, and cluster-K's *"curve of best fit"* as defined on **[CHAT] 07-21** —
built as the anchor's containing-cluster chain.

The value model, with every coefficient exposed — this is `5006fed`'s answer to the 07-23
normalization complaint:

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

"each a boost, never a filter" is **C-16** honoured in the shipping code. And the order of
operations, a genuine user concept:

> ```
>   Structure enters by order of operations: what the query STATES resolves
>   before what the interpreter reads into it. Stated scope (product / section
>   / channel / employee_id / years — extracted only when explicitly named) is
>   its own path whose pool is the matching chunk set — no clustering, nothing
>   fuzzy about a stated fact.
> ```

which answers **[CHAT] 07-21** *"but shouldnt this pretty much be a "order of operations"
thing from the interpreter/that part of the build?"*

`git_record.md`'s verdict on this file: *"This arm is honest in its own docstring about what
it runs on. Its conflict is with the canon around it, not with itself."*

## What diverged

### Three canon rules and the arm that ships now disagree at HEAD

The forensic contrast arm is now the reported system, and three separate canon lines are
false of it. None of the three is a new decision; all three are Era 4's deferral hardening
into drift.

**C-2 — the graph under test.** `git show 296fc40:docs/v2_artefact_rebuild_design.md` §12
says v1 numbers *"measure the v1 violation, not the intended product"*; `git show
6730d13:v3/pipelines/artefact_v1.py` line 117 says
`DATABASE = os.environ.get("NEO4J_DATABASE", "herb-eval")`; and `git show 6730d13:CLAUDE.md`
says *"**`herb-eval` (Neo4j) is the prior artefact build under the superseded design** — a
contrast/forensic baseline only, **not adopted**."* The drift is in the *canon*, not the
code: at `git show 0efff16:CLAUDE.md` the rule read *"**`herb-eval` is the canonical Neo4j
DB**"*. The code kept running herb-eval while the canon around it flipped from "canonical"
to "not adopted", and nothing reconciled them.

**C-5 — the chunk description.** Killed at `git show 28c95aa:v3/artefact/DESIGN.md` §9.1
(*"there is no description, decided 2026-06-11"*) and §14.1, and repeated in
`git show 6730d13:CLAUDE.md` (*"The chunk description is dead."*). Alive at
`git show 6730d13:v3/pipelines/artefact_v1.py`, where one of the three fused ranking paths
is the description path with its own weight `W_DESC`. The desktop record explains why these
are not actually in conflict *about the same system*: the rule is the user's own, verbatim
(**[DOC] 06-11**, *"Since the collective tags from a chunk should BE the content of the
chunk, why do both?"*, asked twice), and it governs the **v3 native artefact** — which
`tag.py` honours. The surviving description path lives in **`artefact_v1`**, querying a
graph where descriptions are a real property of the data.

The user's own view of that path, later: *"dude, descriptions in every tag was an
abomination and should never have been there, i am still angry abou tthat"* —
**[CHAT] 07-30**. And, cutting the other way three weeks earlier, on the v1 concept:
*"the chunks contain a short description of the chunk"* — **[CHAT] 07-06**, describing v1 as
designed. Both are his.

**C-13 — "the model emits no numbers, ever."** Present unchanged in every `CLAUDE.md` from
`0efff16` onward (verified: `git show <ref>:CLAUDE.md | grep -c 'no numbers'` → 1 at
`0efff16`, `4da9c5b`, `0733a9d`, `8a640bf`, `5006fed`, `c33594d`, `6730d13`), and stated in
MODEL_CONTRACTS §0 as an inherited invariant. Violated by the arm under test:
`git show 6730d13:v3/pipelines/artefact_v1.py`'s interpreter pass 2 prompt is *"Score
retrieval tags against five facets (each 0.0-1.0)"* returning
`{"scores":[{"t":"tag","facets":{"topic":0.0,"entities":0.0,"activity":0.0,"temporal":0.0,"evidence":0.0}}]}`,
with a validator that raises `ValueError` if a facet value *"is not a number"*.

The rule's provenance is settled and it is the user's, with his own evidence:
**[DOC] 06-11**, *"it took so fucking long to get it right and it still didn't work at
all."* And the violation was deliberate quarantine when it was written —
`2026-07-12-v3-current-state-and-artefact-v1-review.md` §5: *"It also asks the model for
numeric facet scores. Both are **intentionally incompatible with current pass-2 canon; this
is why v1 stays forensic.**"* The numeric-facet code is kept precisely *because* it violates
the rule and therefore serves as the before-picture. What changed is not the code but its
status.

### What git cannot supply for this era

`git_record.md`'s G-9 flags one gap that bears directly on everything reported here: the
`DATA_README` shipped by `7879dfe`, which maps metrics to cross-arm validity, **was not
read** by the git pass. Its judgements are the project's own and would need reading before
any number from this era is quoted comparatively. Neither the desktop corpus (which ends
07-12) nor `USER_CANON.md` closes that gap.

Also unclosed: **reproducibility**. `git show 0733a9d:v3/README.md` records *"**Provenance**
is two manifests … **no seed, no git-sha**"* as a decision. No committed run from this era
can be tied to the code revision that produced it.

---

# Era 6 — Audit, corpus, tag-first

**2026-07-29 → 2026-08-03**

Two git commits, and the densest week of first-hand chat in the project.
`desktop_docs_record.md` does not reach this era; `git_record.md` stops at `6730d13`
(08-01); `USER_CANON.md` runs to 08-03 and is the primary source for everything after
08-01.

This era is also **reflexive**: the three records this document fuses were commissioned
inside it.

## What was decided

### 2026-07-29 — held-out generalization, on his terms

> *"why on earth would we suddenly run the entire fucking question set!? tell me why."*
> — **[CHAT] 07-29**

> *"pick a new evenly distributed 100q set then, not the entire fucking 800q, thats insane,
> it's bad enough with 100 new but atleast that will say something and not be insane"*
> — **[CHAT] 07-29**

> *"and the 100 are all answerable?"* — **[CHAT] 07-29**

and the reading of the result:

> *"you but compared to gold100 this is pretty much a wash, meaning we can keep testing on
> the gold100, right?"* — **[CHAT] 07-29**

The same day, the two things he wants fixed, stated as a numbered list —
**[CHAT] 07-29**, `USER_CANON.md` §2:

> "so, can we finally go on with trying to fix the artefact? there are 2 different things i want to have a serious look at: 1. to see if we can build the graph smarter, aka use the actual grapjh shape in a better way, either but adding something, rearranging or something else, do your due diligence as usual for this.
> 2. the retrieval, the fact that we find pretty much all gold, but also 90% air is a terrible thing"

Item 1 is the graph-underuse question for the fifth time. Item 2 is the ordering problem
from 07-22, now quantified by him as "90% air".

Also 07-29 — the precompute demand, now specified as an ordering:

> *"the questions, the models interpretations of the questions, THOSE are the things we can
> embed, which MEANS, you run ALL the fucking questions FIRST, at the same time, and THEN,
> before anything goes further than that, we EMBED ALL of them, at the same time.. how is
> this fucking unclear? and then we save ALL of these things, so we dont have to redo them"*
> — **[CHAT] 07-29**

> *"How are you not getting what I want done here? I want subsequent runs to be more or less
> fucking instant and free"* — **[CHAT] 07-29**

and the judge continuity ruling: *"especially since we decided to use haiku for the fucking
evals also, was that entire line of thought erased?"* — **[CHAT] 07-29**, plus
*"yeah, obviously, but using, as the others.. headless claude cli with my subscription"*.

### 2026-07-30 — what tags are for

**The purpose statement, said twice on the same day in two sessions** —
`USER_CANON.md` §3:

> *"you and every other agent seem to be missing that the whole fucking point of the tags, is
> guiding to the correct gold-bearing chunks"* — **[CHAT] 07-30**

> *"i was under the impression that we did the whole fucking tag-clustering and facets and
> weights just to fucking guide it all to the correct chunks, why the absolute fuck was this
> NOT done then?"* — **[CHAT] 07-30**

and the order:

> *"ok, so we make sure it is informed by the tags first then, as IT WAS FUCKING INTENDED from
> the start.. didnt the original thesis artefact do it correctly?"* — **[CHAT] 07-30**

**The generalization mechanism, in his own words** — **[CHAT] 07-30**, `USER_CANON.md` §12:

> "well, my original thought was  about the indexing stages finds structures in the dataset which then translates to a helpful graph of it and is also used for the retrieval structure, like, that path/structure is related the whole way, meaning that part gets auto"fitted" to every new dataset, not just herb so to speak, whats your thought on that ?"

This is the same idea as `DESIGN.md` §8's automatic/declared split (shape decides handling,
three declared judgments) restated from the retrieval side — and it is the answer to the
Bonnier generalization test that was deferred on 06-14 and never resumed.

He also raises the cross-lineage swap:

> *"so, you think the v3artefact tags would be a better solution? can't we just do the
> v1artefact exactly s it is now, but with the v3 tags instead? (obviously refitted for
> that then)?"* — **[CHAT] 07-30**

### 2026-07-31 — the fullest clustering specification, and a reversal

**[CHAT] 07-31**, `USER_CANON.md` §5:

> "1. i THINK it might be smartest to compute the clusters at build, and then weight-adjust them based on the query's facet-values.. i THINK, reflect on this with me..
> 2. something like that, i used best fit as the fuzzy cutoff-point for the cluster's edges tho, aka the size of the cluster or what will you, but perhaps the query-adjustment comes first before what the best fit is for this query, reflect on this with me also"

and the facet-weighted variant:

> *"ok, so a variant where the best fit of the clustered tags inform/weight the relevant
> chunks? the original thought was the it was clustering of tags weighted by facets, meaning
> each type of facet was a separate sort of clustering to get semantically different
> clusters"* — **[CHAT] 07-31**

**This reverses 07-21.** Ten days earlier: *"i mean, the clusters are based on the actual
shit from the prompt, so you cant pre-run it..?"* — **[CHAT] 07-21**. `USER_CANON.md` §5
rules on it and the ruling is binding on this document too: both are hedged by him (`"..?"`,
`"i THINK"`, `"reflect on this with me"`), **neither is a ruling, and neither may be treated
as settled.**

Also 07-31, pre-registered bars rejected:

> *"what is this garbage? " . Bar fixed before running: paired recall gain over the 0.7339
> baseline > +0.03, p < 0.05, constant-τ sweep only — pass and the mechanism ships, fail and
> it joins the graveyard documented plainly. " What do you mean?"* — **[CHAT] 07-31**

> *"we already have the fucking scores to compare to, stop making random shit up, just be
> fucking satisfied with what is happening, you HAVE to fucking stop blaoting"* — **[CHAT] 07-31**

`USER_CANON.md` §7 reads this precisely: the objection has two halves — a constant must be
*derived*, and **a pre-registered pass/fail bar invented by an agent is itself an arbitrary
number**. He rejects the bar, not the measurement.

### 2026-08-01 — tags-first ships, and is immediately rejected

`6730d13` — `tags-first retrieval regime, per-facet tag cluster guidance, per-run --flag
args` — is HEAD. It answers 07-30's *"informed by the tags first"* and 08-01's interface
complaint (*"yeah why havent you just made them into -- commands ? wtf is this
abomination?"* — **[CHAT] 08-01**, following *"wait a fucking minute, the env vars stick?
that.. that sounds like a really bad idea"*).

**And the regime it implements is rejected the same day** —
`USER_CANON.md` §3's named reversal:

> *"ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE ffs.. tags are supposed to INFORM/weight the
> chunks"* — **[CHAT] 08-01**

`USER_CANON.md`'s reading, which settles the mechanism: *"tags first" means tags
weight/inform earliest and hardest in the ordering. It does not mean tags decide which
chunks are eligible. Those are different mechanisms and only the first is canon.* What was
built was a tag-**reachability** regime (`HERB_TAG_FIRST`) in which tags gate membership —
which is a hard filter, and therefore also a fresh violation of **C-16**, the rule the user
has now restated on 05-31, 06-12, 07-15 and 08-01.

### 2026-08-02 — gold-blindness, and the canon audit

**The newest constraint in the whole record** — `USER_CANON.md` §8:

> *"honestly, you should not have the questions/gold available to you, there is 0% good that
> can come out of taht"* — **[CHAT] 08-02**

> *"can we make sure "you" never see them? that you only get the variable/pointer to it?"*
> — **[CHAT] 08-02**

> *"Still feels like you kinda missed what i meant, not only did i mean you are forcing an
> architecture BASED on retrieving the gold based on the questions, it also feels like you
> are focusing on it"* — **[CHAT] 08-02**

This is why `v3/data/questions.jsonl`, `gold100.jsonl`, `heldout100.jsonl` and
`10smoke.jsonl` are not opened by design work — including the work that produced this file.

**The canon audit ordered** — the standing instruction that produced all three records:

> *"have you fucking done ANYTHING based on actual canon? i fucking demand you filter through
> every fucking memory and chatlog you have and find out everything I HAVE SAID, THOROUGHLY"*
> — **[CHAT] 08-02**

> *"Search the entire repo for exactly ALL information I (the user, fucking ME) i have
> conveyed … that means you have to search the entire git-repo also with all the fucking
> branches etc, this is not a small job, but it is the most important one we have ever done
> here."* — **[CHAT] 08-02**

> *"THE GODDAMN GIT REPO HAS ALL THE FUCKING HISTORY SPOKEN IN COMMITS, DIFFS , CODE and
> DOCS.. what the actual fuck is wrong with you?"* — **[CHAT] 08-02**

and the reason he demanded it — `USER_CANON.md` §14:

> *"you do understand that just because the text is in the repo, that doesnt mean i was the
> one that ok'd it or put it there, right? you literally put shit in writing and pretend its
> canon"* — **[CHAT] 08-02**

> *"ok, you do realise "verified by me" means YOU verified? and not me?"* — **[CHAT] 08-02**

> *"We are making sure the docs and in fact YOU have the actual true canon information when
> working in this repo because i just unearthed ANOTHER fucking massive data/canon/construction
> repo-rape from the fucking agents here..."* — **[CHAT] 08-02**

**The tag layer inspected** — the 08-02 diagnosis he pasted and accepted, from
`USER_CANON.md` §F: the tag path finds 3 chunks/question out of a ~418-chunk pool, zero
widening levels ever open, `GUIDE_TAU = 0.0` makes every tag's guide value exactly 1, and
`HERB_TAG_FIRST` bundles a walk restructure with a gate. His answer: *"so, lets fix that and
try it"* — **[CHAT] 08-02**. Whether it was fixed is not in any of the three records.

His reaction to the tag corpus itself:

> *"this literally all sounds like you constructed the whole tag-part like a fucking hobo"*
> · *"Eh.. what..we have tags with that fucking syntax? For real?"* · *"but those you just
> showed me.. those are tags!?"* — **[CHAT] 08-02**

> *"Hapax?"* / *"have you decided this? "which is what a tag layer is supposed to be" ?
> Because in min mind, just when thinking about it cursory, hapax would let them matter more
> because of vectorisation?"* — **[CHAT] 08-02** — listed in `USER_CANON.md` Part IV.E as
> open, no answer recorded.

**The hard-fields question, third asking — and its rejection:**

> *"well.. you think this would be easier for you to build and think upon the artefact if we
> used the graph shape better? like the hard fields etc, should they be nodes or edges or
> something? is there some way we could use the information in the graph and make helpful
> structure from it instead of having it locked into other's nodes or edges?, very important
> question so please do take your time to carefully answer this"* — **[CHAT] 08-02**

> *"dude, you are turbo-overfitting now, AND doing shit that might as well be sql-schema"*
> — **[CHAT] 08-02**, on the answer to that exact question

`USER_CANON.md` §11 records this as an unretired three-position reversal: hard fields as
**attributes** (06-12, on the argument that node-ifying creates edges to every chunk and
near-duplicate nodes), as **nodes/edges** (06-30 / 07-01, on the argument that
relationship-routing is half the strength of a graph, generalized to a dataset-agnostic
rule), and the concrete hub-node answer **rejected as overfitting and SQL schema** (08-02).
**All three positions are his and none has been retired.**

And the correction that closes the provenance loop — an earlier agent had called 2026-07-15
"the first day" of the project:

> *"This, this was the most fucking delusional piece of evidence i have ever seen. " 2026-07-15,
> the first day " Day one? 2 weeks ago..  you ARE retarded.."* — **[CHAT] 08-02**

It was the earliest date in one partial local extract, wrong by two months. The whole
purpose of the git record is to make that error impossible again.

### 2026-08-03 — the two machines' history is merged

> *"Copy this machine's Claude Code history for the GRAG-Job / exjobbet thesis project so my
> laptop session can mine it. Do not extract or summarise anything — raw copy only."*
> — **[CHAT] 08-03**

> *"you are active on the desktop too, even got an active remote to it, do your thing there
> if you need something"* — **[CHAT] 08-03**

This is what makes `desktop_docs_record.md` possible: the desktop machine's gitignored
`docs/handoff/` (6 files) and `docs/state/` (14 files), 6,719 lines, covering exactly the
two chat blackouts.

## What was built

| Date | SHA | Author | What landed |
|---|---|---|---|
| 07-31 | `c33594d` | Joakim Wikman | `snapshot before tag-first retrieval build: heldout100 data, graph refresh, doc state` — tip of `origin/re-V1-k50` |
| 08-01 | `6730d13` | Joakim Wikman | `tags-first retrieval regime, per-facet tag cluster guidance, per-run --flag args` — **HEAD**, tip of `origin/tag-first-cluster-guide` |

Plus, off-git and inside this era, the three forensic records themselves:
`docs/canon/raw/git_record.md`, `docs/canon/raw/desktop_docs_record.md`, and
`docs/canon/USER_CANON.md` with its 803 verbatim turns — re-derivable via
`python tools/canon_extract.py`.

## What diverged

### The full revert took the matched-budget work with it

`USER_CANON.md` Part IV.F: *"The evidence-cap / matched-token-budget work existed only inside
the thread he ordered fully reverted on 07-28, and did not survive the revert."* The
budget mismatch was measured on 07-12, rediscovered by the user on 07-26, confirmed by the
07-28 audit panel — and the code that would have fixed it was reverted on the user's own
instruction (*"either you absorb the knowledge or its gone"* — **[CHAT] 07-28**), because
the same thread carried a regression.

### Cluster-K has never been on the load-bearing path

`USER_CANON.md` Part IV.F: *"Cluster-K itself — the mechanism defined on 07-21 and
respecified on 07-31 — has never been on the load-bearing path in any shipped
configuration."* The dendrogram chain exists in `artefact_v1.py`'s `levels` stage
(`git show 6730d13:v3/pipelines/artefact_v1.py`); the *cut* — best fit deciding K — does not
decide anything that ships.

### The arbitrary constants he predicted, unenumerated

> *"also, arbitrarily decided hard limits, like the 64 chunk limit, i bet there is way more
> than 1 of these dumb limits lying around not beeing seen"* — **[CHAT] 08-02**

`USER_CANON.md` Part IV.C lists `POOL_FETCH`, the 64-chunk limit and `K_LEVELS` alongside
α = 0.25, `MULTI_FACET_THRESHOLD = 0.50` and `CAP_TOKENS = 3000` — **not enumerated since**.
The **C-15** family has grown, not shrunk, in eleven weeks.

### The graph question, asked seven times, never answered

06-30, 07-15, 07-20, 07-21, 07-28, 07-29, 08-02. `USER_CANON.md` §2's reading:
*"never answered to his satisfaction"*, closing on a pair where he asks for hard fields as
nodes/edges and then rejects the concrete answer as overfitting and SQL schema — *"Both
turns are his; both halves bind."* The design that would have answered it was written on
07-01 and never built.

---

# The eighteen contradictions, adjudicated

C-numbers are fixed at discovery in `git_record.md` and are **kept unchanged** so existing
references resolve. They are listed here in numeric order; `git_record.md`'s own
by-importance reading order was C-1 · C-2 · C-3 · C-4 · C-5 · C-6 · C-7 · C-8 · C-9 · C-10 ·
C-11 · C-12 · C-16 · C-17 · C-18 · C-13 · C-14 · C-15.

Each entry gives the git evidence, the desktop-docs verdict, and one line of resolved
status. Verdict vocabulary from `desktop_docs_record.md` §4: **CONFIRMS** / **REFUTES** /
**EXPLAINS** / **PARTLY EXPLAINS** / **NEITHER**.

---

## C-1 — D10 reversed: content-in-graph → references-only

**Git.** Then: `git show dba1160:docs/architecture.md` — *"D10 … `(:Chunk).content` stores
the chunk text … Storing content makes the graph self-sufficient. **Status.** Active."*
Now: `git show 296fc40:docs/v2_artefact_rebuild_design.md` — *"The v1 chunker violated this:
it consumed each record, rendered it to a prose string, stored the string as `c.content`,
and that lossy derivative became the only surviving copy."* Git's verdict: a reversal, not a
drop — argued and evidenced — but listed because D10 was never updated or retracted in
place; it still reads "Status. Active" in every ref, including
`git show 28c95aa:v1/docs/backend/architecture.md`.

**Docs. EXPLAINS (and confirms).** `2026-05-31-v2-artefact-rebuild-and-facet-design.md` §2
confirms references-not-copies as the session's core stance with the same charge. The
un-retracted D10 is explained by a documented user ruling —
`2026-06-12-v2-graph-spine-and-literal-matching.md` §3: *"**v1 docs stay untouched:** "that
shit is still true for THAT build." v1 documentation describes v1 as built; only v2-living
docs get purged."* — **[USER-STATED]**, reinforced in §8.

**Resolved status: documented reversal.** The residue is not neglect — leaving D10 "Active"
is the user's own frozen-v1-docs policy (**[DOC] 06-12**, `USER_CANON.md` §22).

---

## C-2 — The v2 design declared all v1 eval numbers invalid; the shipped arm is the v1 graph

**Git.** Declared: `git show 296fc40:docs/v2_artefact_rebuild_design.md` §12 — *"Those
numbers measure the v1 violation, not the intended product. The HERB evaluation is re-run on
the v2 graph for thesis numbers."* Shipped:
`git show 6730d13:v3/pipelines/artefact_v1.py` line 2 — *"over the Neo4j `herb-eval` graph
(the v1 artefact build)"*; line 117 — `DATABASE = os.environ.get("NEO4J_DATABASE", "herb-eval")`.
Canon agrees it shouldn't be: `git show 6730d13:CLAUDE.md` — *"a contrast/forensic baseline
only, **not adopted**."* Git calls it the largest live contradiction in the repo, and notes
the drift is in the canon, not the code: at `git show 0efff16:CLAUDE.md` the rule read
*"**`herb-eval` is the canonical Neo4j DB**"*.

**Docs. EXPLAINS.** The five-step causal chain: `artefact_v1` was introduced as a declared
contrast baseline (`2026-07-12-v3-current-state-and-artefact-v1-review.md` §3, §6); the
native v3 arm **was** built and run (06-28, gold-100 k=10); the user condemned it
(*"the precision was absolutely fucking terrible"* — **[CHAT] 06-30**); pass 2 was gated
behind four sign-offs that never came (07-12 §11); `herb-v3` never materialized (Neo4j not
running, `NEO4J_PASSWORD` unset). Answers git's G-5 and G-10. The doc record's own
qualifier: *"The contradiction is real at HEAD, but it is drift after 07-12, not a decision
inside this window."*

**Resolved status: user decision misread as drift — which then became genuine drift.** The
forensic-contrast ruling is documented and deliberate (**[CHAT] 07-26**: *"we are NOT doing
the v3 artefact, we are doing the v1artefact … so we can atleast finish these fucking
benchmarks"*); what nobody reconciled is the canon written as if v3 were the system under
test. Live at HEAD.

---

## C-3 — The controlled canonical vocabulary was deleted with no mention

**Git.** `git show 399ee32 -- backend/clustering/canonical_seed.yaml` →
`1 file changed, 49 deletions(-)`; `git show 399ee32 -- backend/scripts/bootstrap_schema.py`
removes `seed_canonical_tags()` and `--skip-canonical-seed`. Commit message:
`Rework HERB chunking and tagging frames` — no mention. Only prose trace: one substituted
table cell. D2/D3/D4 left standing as **Status: Active**.

**Docs. CONFIRMS; does not explain.** The corpus begins 05-25, twelve days after the act.
It independently confirms the end state and that the drift was known —
`2026-05-25-artefact-audit-and-cleanup-plan.md`: *"**3 edge types only** … No `:Run`. **No
`:CanonicalTag***. (Schema doc claims these exist; they don't in `herb-eval`.)"* —
**[AGENT-ASSERTED]**, verified live. Filed under *"Doc drift … These are docs problems, not
graph problems"*, to be fixed *"when the cleanup work touches the affected docs"*.

**Resolved status: genuine silent drop.** An entire subsystem left the design with a
one-cell edit. **No user statement about it exists in any of the three sources**
(`USER_CANON.md` Part IV.D says so explicitly).

---

## C-4 — Six of eight node labels and four of seven edge types disappeared

**Git.** Then: `git show dba1160:docs/graph_schema.md` — eight labels, seven edge types.
Now: `git show 28c95aa:v3/artefact/DESIGN.md` §7 — *"Nothing else is a node."* Git's
specific complaint: the loss of `(:File)-[:TAGGED]->(:Tag)` (with its
`weight_global = sum(coalesce(c.relevance_to_file, 0.5) * r.weight_local) / count(c)`
formula) and of `(:Chunk)-[:NEXT]->(:Chunk)` *"is not discussed anywhere"*. §7 argues at
length about entity and record nodes and never mentions `TAGGED` or `NEXT`.

**Docs. PARTLY EXPLAINS.** `:NEXT` is fully explained and git's framing corrected — the
05-25 audit shows it **was never populated**: *"Only `_part` kinds have order-dependent
semantics (~12% of corpus). For those, `c.ordinal` carries the same info `:NEXT` would;
`:NEXT` is not needed."* and *"All 33 files are `dispatch_mode=parallel`. The `sequential`
tagging path … is dead-but-documented code."* Git's inference that `:NEXT` was the link D1's
dispatch-mode design depended on is therefore **partly refuted** — nothing depended on it in
practice — and the replacement is documented: 06-03/06-04 make the **materialized integer
path** the successor to flat `ordinal` + `NEXT`, and 06-12 records the path as *"MORE
load-bearing since the path attribute is how the tree exists without branch nodes."*
`:TAGGED` / `weight_global` are **mentioned nowhere in the twenty documents**.

**Resolved status: split — documented reversal for `:NEXT`, genuine silent drop for
`:TAGGED` / `weight_global`.**

---

## C-5 — "The chunk description is dead" — except in the arm that ships

**Git.** Killed: `git show 28c95aa:v3/artefact/DESIGN.md` §9.1 (*"there is no description,
decided 2026-06-11"*), §14.1, and `git show 6730d13:CLAUDE.md`. Alive:
`git show 6730d13:v3/pipelines/artefact_v1.py` — a description lookup over
`chunk_desc_emb` is one of the three fused ranking paths, with its own weight `W_DESC`. Both
current at HEAD.

**Docs. EXPLAINS.** The rule is the user's, verbatim, and he asked twice —
`2026-06-11-v2-facet-carriers-and-build-gate.md` §3: *"Since the collective tags from a
chunk should BE the content of the chunk, why do both?"* — **[USER-STATED]**. The tension
resolves by *which system each statement is about*: the description is dead in the **v3
native artefact**, which `tag.py` honours; the surviving path lives in **`artefact_v1`**,
querying the v1 graph where descriptions are real data
(`2026-07-12-v3-current-state-and-artefact-v1-review.md` §4, §5 —
*"intentionally incompatible with current pass-2 canon; this is why v1 stays forensic"*).

**Resolved status: user decision misread as drift.** Two true statements about two different
systems, with `CLAUDE.md` stating a v3 rule as if it governed the arm producing the numbers.
That framing error is C-2's, not a second independent fault. Live at HEAD.

---

## C-6 — The condemned v1 facets returned under new names

**Git.** Condemned: `git show 18d11df -- docs/v2_artefact_rebuild_design.md` §13.1 (*"the
root of the ~18 % junk vocabulary"*) and §13.4 (*"exactly the v1 'junk facets'
(entities/temporal/evidence) relocated to where they belong"*). Returned:
`git show 8a640bf:docs/research/2026-06-27-facet-derivation-methods.md` — target facets
`process/activity`, `information-kind` (definition / example / metric / argument / procedure
/ case_study / raw_data), `entity-type` (person / org / product / system / place),
`centrality`. **The match is exact**: `information-kind`'s value list is
character-for-character the v1 `evidence` facet from
`git show 415148d:backend/docs/herb_tagging_schema.md`; `entity-type` is the v1 `entities`
facet; `centrality` is `w_chunk`. Git's verdict: *"cannot be told from git — nothing argues
it either way. Flagged because it is precisely the pattern being hunted."*

**Docs. EXPLAINS, decisively.** `2026-06-25-artefact-facets-guide-link-and-content-profile.md`
§8 names the misread: *"**WRONG about evidence and entities.** `evidence` = information-KIND
… a real semantic dimension; `entities` = named-thing TYPE, semantic. The *fact* (eid, URL)
is structure; the *kind/type* is meaning. **This misread is what hollowed the tag.**"* The
distinguishing principle is **fact vs kind/type**: the v1 *degradation* was `evidence`
collapsing into URLs; the v1 *definition* was "kind of information"; the allocation table
mistook the degradation for the definition. User-driven — *"What you think is v2 tags is in
essence everything moved to hard fields or put on the interpreter"* and *"Would not the old
facets work with the new tags? (not the weighting, the concept)."* — **[USER-STATED]**. The
provenance failure is named too: the memory said *"evidence = sourcing, not links"* while
the v1 doc said kind-of-information — *"Read the v1 source, not the summary."*

**And the loop closed again**, which git could not see: on 06-27 the user cut entity-type
and information-kind **back out** — *"like info-kind and entity-type (are they even
facets..?)"* — **[CHAT] 06-27** — on the ground that a facet must be a graded "how much"
dial. Out (05-30) → in (06-25) → out (06-27). Each move argued; the reconciliation with the
06-28 categorical framing is open problem §11.1 and **never closes**.

**Resolved status: documented reversal — twice, both user-driven, reconciliation still
open.** Not an unnoticed loop.

---

## C-7 — The per-facet extraction spec was fully written and never built

**Git.** Specified: `git show 28c95aa:v3/artefact/DESIGN.md` §13.5 (five facets, each with
emits / MUST-NOT / interpreter mirror; two closed enums) and
`git show 28c95aa:v3/artefact/MODEL_CONTRACTS.md` §1 (the exact five-key JSON schema); §16
calls it *"**The one design blocker** before any run"*. Built:
`git show 8a640bf:v3/artefact/tag.py` — `{"tags": ["..."]}`, flat. Git records the reopening
(MODEL_CONTRACTS §5 call (a), "REOPENED 2026-06-14") but **not the resolution**, and G-4
calls this its single most important unanswered question.

**Docs. EXPLAINS, decisively.** A four-step, user-driven bridge: (1) 06-14 — the schema was
verbally approved *and flagged invalid by the same document* (*"CAVEAT: this approval
predates the §3 facet breakthrough and the §8 carrier reversal — re-validate it"*); (2)
06-25 — the five-facet set is disowned as an assistant synthesis the user *"never
hard-approved"*; (3) 06-28 [t42] — *"ah, yeah, i agree, not all facets should be graded in
the same way"* **[USER-STATED]**, killing the uniform 5-vector; (4) 06-28 [t52] —
*"honestly, an optimal solution would to NOT have all of this in the graph, intead do it
live-prompt-time"* **[USER-STATED]**. Consequence, from
`2026-06-28-artefact-build-design-evolution.md` §4: graded facets moved to query time
because it dissolved instrument, axis-definition and calibration at once. If nothing
per-facet is stored, the tagger has nothing per-facet to emit.

**Resolved status: documented reversal.** `tag.py`'s unargued docstring is the compressed
residue of a fully argued decision. **G-4 is answered.**

---

## C-8 — Entity decomposition specified, then reversed

**Git.** Then: `git show 296fc40:docs/v2_artefact_rebuild_design.md` §7 — *"Faithful
decomposition = every object → a node, every scalar attribute → a property"*; §10 specifies
`:Employee`, `:Customer`, `:PrAuthor`, `:REPORTS_TO`; §9 specifies `:COVERS`. Now:
`git show 28c95aa:v3/artefact/DESIGN.md` §7 — *"This replaces the earlier draft in which
every object became a node … the copies disease at the node level."* Git: properly
documented reversal, listed only because it is the largest design element ever discarded and
because it left residue (C-9).

**Docs. CONFIRMS, and upgrades the attribution.** It was **the user's** reversal, driven in
conversation, with the deciding rule his own —
`2026-06-12-v2-graph-spine-and-literal-matching.md` §3: *"if we are saying file -> chunk
->tags .. where are those OTHER RANDOM FUCKING NODES!?"*, *"either they are nodes, but then
we get edges to EVERY fucking chunk, or they are just attributes…"*, *"that sounds a bit
fucked up to have them as nodes, most of them will be a chunk, meaning we have 2 almost same
nodes."* — all **[USER-STATED]**. The corpus also records the assistant repeatedly trying to
reinstate the dead draft (the three "forcing shit into the graph" incidents) and names the
05-30 draft as the source of the inertia.

**Resolved status: documented reversal, attribution upgraded to the user.** Better-evidenced
reading: the desktop record — git cannot attribute prose at all, and `USER_CANON.md` §2
carries the same three quotes as **[DOC] 06-12**.

---

## C-9 — DESIGN.md contradicts itself in two places at the same commit

**Git.** All from `git show 28c95aa:v3/artefact/DESIGN.md`: §7 abolishes non-spine nodes and
`:COVERS`; §9.5 still says *"Overlap fights references-not-copies and dirties the `:COVERS`
edges"*; §9.6 still says *"IDs, dates, and authors are now structural (**entities +
properties**)"*. Git: unremoved residue of the superseded draft, inside the current design
reference — the exact failure mode `CLAUDE.md`'s docs-track-reality rule exists to prevent.

**Docs. PARTLY EXPLAINS.** `2026-06-12-v2-graph-spine-and-literal-matching.md` §9 records a
full section-by-section reconciliation pass naming what was **knowingly** left stale:
*"STILL STALE knowingly: §13.5 emit-examples (bare labels; rewrite when carriers close — its
banner says so)."* The governing rule, from the 06-25 doc: *"rewrite only when the tag-facet
SET + axis-definition close (docs-track-reality — **no premature rewrite of an open
model**)."* Under a design-before-build gate, rewriting an open section is writing fiction.
But §9.5's `:COVERS` and §9.6's "entities + properties" are on **no** acknowledged-stale
list.

**Resolved status: split — deliberate policy for §13, genuine unremoved residue for §9.5 and
§9.6.** The two named residues are precisely the *"some paint on the walls"* failure the
user complained about on 05-15 (`git show 4ab34b4:memory/project_architecture.md`).

---

## C-10 — Three tagger-model decisions, each superseding the last; the final one undocumented

**Git.** `git show 296fc40:…` §11 → `deepseek-ai/deepseek-v4-pro` ("chosen by benchmark");
`git show 28c95aa:v3/artefact/DESIGN.md` §11 → `mistral-large-3-675b-instruct-2512`
(Swedish/Bonnier); `git show 8a640bf:v3/artefact/tag.py` → `z-ai/glm-5.1` (no basis in git).
Three compounding problems: the Bonnier axis was out of scope at the moment of the choice
(§12 of the same file defers it); glm-5.1 is China-trained, the category §11 rules out; and
the interpreter diverges three ways (MODEL_CONTRACTS §0 "same LLM";
`git show 6730d13:v3/artefact/interpreter.py` line 25 `INTERPRETER_MODEL =
"meta/llama-3.3-70b-instruct"`; `git show 6730d13:v3/pipelines/artefact_v1.py` line 121
`INTERPRET_MODEL = "claude-haiku-4-5"`).

**Docs. PARTLY EXPLAINS.** Problem 1 **fully explained** and noticed on the day —
`2026-06-14-v2-facets-as-relevance-channels.md` §3: *"the original Mistral rationale was
Swedish fidelity — **now moot under HERB-only** — so the model choice rests on "largest
tier" reasoning, not Swedish."* It never propagated into `DESIGN.md` §11. Problem 2 **not
explained**: no document records the Mistral→glm-5.1 decision; the 06-28 docs treat glm-5.1
as established fact and reference a `by_model` stats field implying more than one model ran.
Problem 3 **fully explained**: the glm-5.1 → llama-3.3-70b swap was an operational response
to NIM hard-throttling glm-5.1 (every call 429'd after 6 retries); the user skipped the
model-choice question at [t108] and the assistant chose.

**Resolved status: split — documented reversal (rev 1→2, and the interpreter swap), silent
doc drift (the Bonnier collapse recorded but never propagated), genuine silent drop (the
glm-5.1 rationale, which exists nowhere).**

---

## C-11 — Six commits of measured results were squashed away

**Git.** `git log -1 --format='%h parents=%p' 5706520` → single parent, not a merge; yet
`git rev-parse 8b320ac:backend/evaluation/ragas_eval.py` and
`git rev-parse 5706520:backend/evaluation/ragas_eval.py` are the same blob. `5706520`'s body
is empty. Lost from the trunk: six `Co-Authored-By` footers and every measured result,
including `git show 8b320ac`'s *"Effect is question-type-dependent — **not a general graph
win.**"* and `git show 0b98b12`'s *"Recall is bimodal (54/99 = 0, 35/99 >= 0.5)"*.

**Docs. EXPLAINS the consequence.** Nothing about the squash, but the finding **survived and
shaped the design**: `2026-05-25-graph-rag-retrieval-redesign.md` cites
*"ragas_eval_report.md | Current gold-100 eval results (graph slightly below Lucene baseline
on context_recall; faithfulness ~tied)"*, and `2026-06-18-v3-eval-harness-herb-ragas.md` §9:
*"faithfulness flat (0.81 vs 0.80), context_recall graph LOWER (0.86 vs 1.00, **bag-size
biased**), context_precision ~0 both (**degenerate**)"*. That reading is the stated reason
the v3 harness adopted deterministic citation-based context metrics over the judged variants
(06-18 §6.2).

**Resolved status: genuine silent drop — of the record, not the knowledge.** The negative
comparative result was absorbed and acted on; the commit-message trace survives only because
`origin/jockedev2` was never deleted.

---

## C-12 — "Seven factors": the claim is correct

**Git.** Design-time (05-14/05-15) records **five**
(`git show 415148d:backend/docs/query_interpretation_layer.md`, identically at
`git show 4ab34b4:memory/project_architecture.md`); as shipped (05-28)
`git show 54bc1a4:frontend/src/services/retrieval.ts` multiplies **seven** — `w_query` ·
`facetScore` · `w_chunk` · `w_facet` · `relevance_to_file` · `sim` · `scopeWeight`. The two
extras arrived between 05-15 and 05-28. **No contradiction** — the apparent conflict was an
artifact of comparing documents from different dates.

**Docs. CONFIRMS.** A contemporaneous second source written against the running code names
the same seven and lists which to remove:
`2026-05-25-graph-rag-retrieval-redesign.md` (*"The 7-factor multiplicative synthesis in the
current … `scoreCypher` is the explicit violation of this design"*) and
`2026-05-25-artefact-audit-and-cleanup-plan.md` (*"Drop the multiplicative 7-factor
`edgeWeight`. Drop `qt.w_query`, `qt.sim` … `qt.scopeWeight`."*).

**Resolved status: not a contradiction — verified correct by both records independently.**
Residual, unclosed in all three: *why* `qt.scopeWeight` was introduced (git's G-7).

---

## C-13 — "The model emits no numbers, ever" vs the arm that ships

**Git.** Canon: `git show 6730d13:CLAUDE.md`, present unchanged in every `CLAUDE.md` from
`0efff16` onward (`git show <ref>:CLAUDE.md | grep -c 'no numbers'` → 1 at `0efff16`,
`4da9c5b`, `0733a9d`, `8a640bf`, `5006fed`, `c33594d`, `6730d13`), plus MODEL_CONTRACTS §0.
Shipped: `git show 6730d13:v3/pipelines/artefact_v1.py` — pass 2 scores five facets
0.0–1.0 and the validator raises `ValueError` if a facet value *"is not a number"*. The rule
holds for the v3 tagger and is violated by the arm under test.

**Docs. EXPLAINS.** Provenance settled — `2026-06-11-v2-facet-carriers-and-build-gate.md`
§3: *"**The model emits NO numbers, ever** — tagger and interpreter both"*, with the user's
own evidence *"it took so fucking long to get it right and it still didn't work at all."* —
**[USER-STATED]**. The violation is deliberate quarantine:
`2026-07-12-v3-current-state-and-artefact-v1-review.md` §5 — *"It also asks the model for
numeric facet scores. Both are **intentionally incompatible with current pass-2 canon; this
is why v1 stays forensic.**"*

**Resolved status: user decision misread as drift.** The numeric-facet code is kept
*because* it violates canon — it is the before-picture. The contradiction at HEAD is C-2's
drift surfacing on a second canon line. Live at HEAD.

---

## C-14 — Canon describes a build state that no longer exists

**Git.** `git show 6730d13:CLAUDE.md`: *"The graph proper — chunk → tag → facet retrieval —
is the unbuilt part; `pipelines/artifact.py` is the arm entry that drives it."* Both halves
false: `git ls-tree -r 6730d13 --name-only | grep v3/pipelines/` returns `artefact.py`,
`artefact_v1.py`, `artefact_v1_det.py`, `hybrid.py`, `lucene.py`, `vector.py` — no
`artifact.py` (deleted at `a515c94`); and `git ls-tree -r 6730d13 --name-only` shows
`chunk.py`, `tag.py`, `index.py`, `graph_store.py`, `prepass.py`, `interpreter.py` and
`tests/test_chunk.py`. Only the **facet** layer is genuinely unbuilt.

**Docs. CONFIRMS, and dates it.** As of 2026-06-28 all those files existed, 36 tests passed,
and a full gold-100 run had executed. The stale line was flagged the same day —
`2026-06-28-artefact-build-design-evolution.md` §5: *"**NEEDS UPDATING.** The graph is now
built (was the unbuilt part); `pipelines/artefact.py` is now implemented (was a stub); 36
tests pass (was 16). The "graph (chunk→tag→retrieve) is the unbuilt part" line is stale."*

**Resolved status: genuine silent drop — of the fix, not the finding.** The canon went stale
on 2026-06-28, the staleness was logged the same day, and the repair was never applied. Live
at HEAD.

---

## C-15 — Two constants that no artifact in git ever derives

**Git.** `α = 0.25` (directional rationale only) and `MULTI_FACET_THRESHOLD = 0.50` (no
rationale at all), both `git show 415148d:backend/docs/herb_tagging_schema.md`, load-bearing
on the 255,288 edges of `git show 415148d:backend/docs/pilot_full_herb_report.md`. Neither
swept. `CAP_TOKENS = 3000` is the counter-example — `git show 28c95aa:v3/artefact/DESIGN.md`
§9.1 states the value, the mechanism, the literature comparison and *"a calibration seed,
not a verdict"* with a named §15 sweep — **and the sweep was never run**.

**Docs. CONFIRMS, and adds the missing measurements.** α's measured effect, 05-25 audit:
*"cross-tab shows mean w_chunk is *lower* on `w_facet=1.0` edges than on `0.7-0.8` edges —
because single-facet hits get penalized by coverage_bonus"* — it does something
counterintuitive. 0.50's consequence quantified (06-09 §4): 85% of unique tag names are
multi-facet, and *"42 tags per chunk" is 42 **edges***, *"Distinct concepts per chunk ≈
low-20s."* The 06-25 doc ties that same 85% to the **orthogonality risk** that threatens the
whole facet layer. And `CAP_TOKENS`'s non-execution is a **documented deferral** —
`2026-06-04-v2-chunk-cap-and-budget.md`: *"it's *implementation-time* … can run only once
the v2 tagger + chunks exist. **Not actionable yet.**"* Once they existed (06-28), it still
appeared on none of the eight deferred-piece lists.

**Resolved status: not a contradiction — confirmed and enlarged.** α and 0.50 remain
underived; the 3000-token sweep is a deliberate deferral never executed. The user states the
standard himself on **[CHAT] 07-15** (*"i do NOT like arbitrary choices for k or any number
or value, fucking BASE it on something"*) and finds new instances on **[CHAT] 08-02**
(*"arbitrarily decided hard limits, like the 64 chunk limit"*).

---

## C-16 — "No hard filters anywhere in ranking" — written against a v1 that was full of them

**Git.** v1 as shipped: `git show 54bc1a4:frontend/src/services/retrieval.ts` gates on five
conditions before ranking (`r.run_id`, `r.facet IN $activeFacets`, the qt.facet match,
`>= $minWChunk`, `>= $minRelevanceToFile`, plus `${gate}` and `${exclude}`). v2 stance:
`git show 28c95aa:v3/artefact/DESIGN.md` §14.4. Git: a justified reversal, and the only one
whose v1 target is verifiable line-by-line — *"it shows the v2 design was written against
the real code, not a caricature of it."*

**Docs. CONFIRMS, and upgrades the attribution.**
`2026-05-31-v2-artefact-rebuild-and-facet-design.md` §"Retriever design": *"**NO hard filters
anywhere** (strong user stance) — "mandatory" = weight concentration; the **cap** does the
cutting on rank."* — **[USER-STATED — paraphrase]**, recorded before any v2 code existed.
Corroborated by the 05-25 handoffs naming the same gates as removal targets, by 06-12's
multi-hit ruling (*"a does seem to fit the best"* — boosts only), and carried to
implementation detail in the 06-28 build: the product-literal boost is additive `+1.0`
because *"a multiplicative boost on a zero semantic score would be a hard filter in
disguise."*

**Resolved status: documented reversal, attribution upgraded to a user stance.** Note the
attribution is a **paraphrase** — `USER_CANON.md` §6 declines to quote it because no wording
survives. The first-hand version arrives only on **[CHAT] 07-15**: *"gate? wtf? why have a
gate? why not ust that as promoted guidance?"* — and is violated again by `HERB_TAG_FIRST`
on 08-01.

---

## C-17 — The leaderboard-comparable anchor metric was specced, stubbed, then deleted

**Git.** Promised: `git show 0733a9d:v3/README.md` — *"**HERB** (`eval/herb.py`) … Exact,
leaderboard-comparable. **The anchor.**"*, listed under "## Decided". Never implemented:
`git show 0733a9d:v3/eval/herb.py` is a 45-line stub of six `...` bodies. Deleted:
`git show 8a640bf --stat --format='' -- v3/eval/` → `v3/eval/herb.py | 45 ----`;
`git ls-tree 6730d13 v3/eval/herb.py` → `fatal: path … does not exist`. Git: the doc edit was
honest, but *"No commit message, doc, or comment anywhere in git gives a reason for the
removal"*, and the deletion rides a commit titled `feat: update graphify-out (533 files)`.

**Docs. EXPLAINS, decisively.** Both ends of the decision are captured. Origin,
`2026-06-18-v3-eval-harness-herb-ragas.md` §3: *"**Do BOTH scorers** (HERB + RAGAS), not
either/or. (User: *"no, i am saying we do both."*)"* — **[USER-STATED]**. Cancellation,
`2026-06-25-v3-vector-eval-k-vs-topk-ragas-ops.md` §3: *"**SCORING IS RAGAS ONLY. There is NO
HERB scorer.** The user said this twice, emphatically (*"this is ONLY RAGAS"*) … `eval/herb.py`
was **deleted**."* — **[USER-STATED]**. §6 records the cleanup mechanics; §8 makes
reintroduction a named trap.

**Resolved status: documented reversal — a user decision, not a silent drop.** The
attribution changes; **the consequence does not**: every number the project reports is
RAGAS-only and none is comparable to HERB's published leaderboard, and **no document
anywhere weighs that consequence against the decision** (`USER_CANON.md` §9 says so too).

---

## C-18 — Design-bearing changes routinely hidden under tooling commit messages

**Git.** Five commits with auto-generated subjects and a "changed files:" list truncated at
ten entries, shipping `v3/eval/herb.py`, the whole harness design, `tag.py`, the 659-line
survey, the deletion of `eval/herb.py`, `interpreter.py`, `pipelines/artefact.py`, and
`artefact_v1.py`. Reproduce any row with `git show <sha> --stat`. Not a design
contradiction — a record-keeping one, *"and it is why several items above were nearly
missed."*

**Docs. NEITHER (but explains the mechanism).** No document discusses commit hygiene. The
corpus explains how the pattern arose: repeated long uncommitted stretches — 06-11
*"NOTHING COMMITTED"*; 06-12 *"NOTHING COMMITTED this session"*; 06-14 *"Repo split into
`v1`/`v2` via `git mv` (nothing deleted, **not committed**)"* — so bulk auto-generated
commits swept up weeks of work at once. It also supplies the missing *content* of the worst
offenders: `8a640bf`'s `tag.py` and the research catalog from the 06-27/06-28 material, and
`69115e0`'s `artefact_v1.py` from the 07-12 review.

**Resolved status: not a design contradiction — a record-keeping defect with an explained
mechanism.** The subjects are tool output, not authorship claims; the effect is that the
repository's own history does not surface its most important changes.

---

# Resolved-status table

| # | One-line resolved status | Live at HEAD? |
|---|---|---|
| **C-1** | **Documented reversal** — and the un-retracted "Status. Active" is the user's frozen-v1-docs policy, not neglect | no |
| **C-2** | **User decision misread as drift** — a declared forensic contrast arm, gated behind sign-offs that never came, that became the reported system | **yes** |
| **C-3** | **Genuine silent drop** — an entire subsystem removed with one table cell; no user statement exists in any source | no (removed) |
| **C-4** | **Split** — `:NEXT` a documented reversal (never populated, replaced by the materialized path); `:TAGGED` / `weight_global` a genuine silent drop | no |
| **C-5** | **User decision misread as drift** — the rule is the user's and governs v3; the surviving description path is v1's | **yes** |
| **C-6** | **Documented reversal, twice** — out (05-30), in (06-25, on the argued fact-vs-kind distinction), out again (06-27); reconciliation still open | open |
| **C-7** | **Documented reversal** — four user-driven steps from per-facet spec to flat list, ending at [t52] "lean graph, live facets"; answers G-4 | no |
| **C-8** | **Documented reversal**, attribution upgraded from [UNKNOWN] to the user's own node/attribute rule | no |
| **C-9** | **Split** — §13's staleness a deliberate no-premature-rewrite policy; §9.5 `:COVERS` and §9.6 "entities + properties" genuine unremoved residue | **yes** |
| **C-10** | **Split** — rev 1→2 and the interpreter swap documented; the Bonnier collapse recorded 06-14 but never propagated; the glm-5.1 rationale a genuine silent drop | **yes** |
| **C-11** | **Genuine silent drop** — of the commit record, not the knowledge: the negative finding shaped the v3 metric choice | no |
| **C-12** | **Not a contradiction** — five at design time, seven as shipped; confirmed independently by both records | n/a |
| **C-13** | **User decision misread as drift** — the no-numbers rule is the user's; the numeric-facet arm is kept *because* it violates it | **yes** |
| **C-14** | **Genuine silent drop** — of the fix: canon went stale 2026-06-28, staleness logged the same day, repair never applied | **yes** |
| **C-15** | **Not a contradiction** — confirmed and enlarged: α and 0.50 underived, the 3000-token sweep a deliberate deferral never executed | **yes** |
| **C-16** | **Documented reversal** — a user stance recorded 05-31 (paraphrase), first-hand 07-15; violated again by `HERB_TAG_FIRST` on 08-01 | **yes** (again) |
| **C-17** | **Documented reversal** — *"this is ONLY RAGAS"*, said twice; a user decision, not a silent drop. The unweighed consequence stands | **yes** (consequence) |
| **C-18** | **Not a design contradiction** — record-keeping, mechanism explained by long uncommitted stretches | **yes** |

**Tally.** Genuine silent drop: **3** (C-3, C-11, C-14). Documented reversal: **6** (C-1,
C-6, C-7, C-8, C-16, C-17). User decision misread as drift: **3** (C-2, C-5, C-13). Not a
contradiction — verified: **3** (C-12, C-15, C-18). Split across two statuses: **3** (C-4,
C-9, C-10). Total 18.

**Live at HEAD:** C-2, C-5, C-9, C-10, C-13, C-14, C-15, C-16, C-17, C-18. `git_record.md`'s
own live list was C-2, C-5, C-9, C-13, C-14; the desktop verdicts and the 08-01 `HERB_TAG_FIRST`
regime extend it.

---

# Where the two records disagree

## Settled by the precedence rule

**First-hand chat > git blob > agent-written doc.** Seven disagreements resolve cleanly.

| # | Disagreement | Resolution |
|---|---|---|
| 1 | **Dates of the 07-01 quotes.** `2026-07-01-artefact-pass2-dials-curve-relationships.md` dates its user quotes to 07-01, its own write-up date. `USER_CANON.md` places many on **06-27** and **06-30** from timestamped chat. | **Chat wins.** The conversation ran 06-27 → 07-01; the doc dates the write-up, not the turns. Affects the condemnation of pass 1, the relationships pivot, the exponential curve, "fuzzy means embedded", and the dials framing. |
| 2 | **Who owns the v2 five-facet set** (topic / process / stance / communicative-function / temporal-stance). Git treats §13.4–13.5 as the design, [UNKNOWN]. | **Docs win.** `2026-05-31-…-facet-design.md` labels it **[AGENT-ASSERTED]**, and `2026-06-25-…-guide-link-…md` §8 has the user disowning it: *"the user **never hard-approved the specific five**, and it hollowed the tag."* Load-bearing for C-6 and C-7. |
| 3 | **C-8 attribution.** Git: a properly documented reversal, prose [UNKNOWN]. | **Docs win.** Three verbatim 06-12 quotes make the node/attribute rule the user's own. Git cannot attribute prose at all. |
| 4 | **C-4's `:NEXT` claim.** Git infers `:NEXT` was *"the sequential-continuity link that D1's dispatch-mode design depended on."* | **Docs win.** The 05-25 live audit shows `:NEXT` was **never populated** and all 33 files are `dispatch_mode=parallel` — nothing depended on it in practice. Git's inference is partly refuted by measurement. |
| 5 | **C-1's residue.** Git reads D10 still saying "Status. Active" as untidiness. | **Docs win.** It is the user's explicit frozen-v1-docs policy — *"that shit is still true for THAT build."* |
| 6 | **C-17's cause.** Git: *"No commit message, doc, or comment anywhere in git gives a reason for the removal."* | **Docs win.** *"this is ONLY RAGAS"*, said twice, emphatically. A user decision. The consequence git identified still stands untouched. |
| 7 | **C-6's novelty.** Git says the 06-27 content-profile facet set *"appears nowhere before it."* | **Docs win.** The recovery was argued two days earlier in `2026-06-25-…-guide-link-and-content-profile.md` §5/§8. True of git alone; false of the full record. |

## Could not be settled

Eight items where the two records genuinely conflict, or where both fall silent, and this
document does not pick a winner.

**1 — Graph magnitudes: the 05-14 pilot vs the 05-25 live audit.**
`git show 415148d:backend/docs/pilot_full_herb_report.md` reports **5,843 chunks selected,
255,288 `:HAS_TAG` edges, 25,896 unique tag names**.
`2026-05-25-artefact-audit-and-cleanup-plan.md`, measured live against `herb-eval`, reports
**`:Chunk`×4,869, `:Tag`×24,804, `:HAS_TAG`×230,321**. Eleven days apart, every figure
lower. Whether the graph was rebuilt between the two, whether the pilot counted *selection*
rather than the persisted end state, or whether one measurement is simply wrong, **cannot be
told from either record** — both state their numbers as measured, neither mentions the
other. Every downstream percentage (the ~18% pollution, the 85% multi-facet rate) is quoted
against one base or the other without saying which.

**2 — `w_facet` distinct values: 19 or 21.** The desktop record contradicts *itself* here.
`2026-05-25-middle-layer-weight-redesign.md` §"Facets" says *"`w_facet` only has 21 distinct
values across 255k edges"*; the same day's audit measured-findings say **19** distinct values
over 230k edges; `2026-06-09-weight-production-measure-not-emit.md` §4 preserves the triple
as **76 / 21 / 86**. Git carries only the 21. Not settleable without re-measuring, which is
out of scope here.

**3 — Whether max-then-sum was "never repudiated".** `git_record.md` item 7c calls the
max-within-prompt-tag-then-sum-across aggregation *"one of the few v1 mechanisms that was
never repudiated"*, tracing it from
`git show 54bc1a4:frontend/src/services/retrieval.ts` to
`git show 6730d13:v3/pipelines/artefact_v1.py`. `USER_CANON.md` §4 carries **[CHAT] 07-23**:
*"are you fucking shitting me!? it's NOT normalized AND it's "summed" ? what fucking idiot
combo is that!?"* — and, in the same exchange, *"the "difficult" and relative part of them
was how much they should matter/guide etc, not fucking if they are normalized and summed or
not, for goddamn fuck.."* The first line reads as repudiation of the summation; the second
reads as saying the normalize/sum question was never the interesting part. **Both are his,
minutes apart.** Whether v1's aggregation survived un-repudiated is genuinely ambiguous.

**4 — Which framing governs facets: 06-28 categorical or 06-27/07-01 dials.** Both records
agree this is open and neither closes it.
`2026-07-01-artefact-pass2-dials-curve-relationships.md` §11.1 declares the conflict
explicitly; `desktop_docs_record.md` caveat 4 adds that **two parallel sessions ran unaware
of each other**, and that where they disagree *"the 07-01 user verdicts govern by the 07-01
doc's own instruction — but that instruction is itself an agent's arbitration."*
`USER_CANON.md` §4 Reversal F2 records the same three-move sequence (out 05-30, in 06-25,
out 06-27) and says the reconciliation *"never closed"*. **An agent arbitrating its own
precedence is not evidence**, so this document does not treat either framing as governing.

**5 — The interpreter model sequence does not reconcile across the records.** C-10 lists
three values for the interpreter: MODEL_CONTRACTS §0 *"same LLM"* (Mistral Large),
`git show 6730d13:v3/artefact/interpreter.py` line 25 `meta/llama-3.3-70b-instruct`, and
`git show 6730d13:v3/pipelines/artefact_v1.py` line 121 `claude-haiku-4-5`. The desktop
corpus explains exactly one hop — glm-5.1 → llama-3.3-70b, forced by NIM hard-throttling.
But the git commit table also carries `90d1074` (07-16) — *"artefact_v1: **glm-5.2
interpreter**; byte-exact benchmark data; 480s NIM timeouts"* — a value C-10 does not
include, and HEAD is `claude-haiku-4-5`. **No source states why the shipped arm's
interpreter became Haiku.** The adjacent chat (**[CHAT] 07-18**, *"the question was if a
claude model was viable to swap out for because qwen ia NIM is fucking uselessly slow"*) is
about the judge, not the interpreter, and cannot be stretched to cover it without
inventing a link.

**6 — Whether the pass-1 gold-100 output folders were deleted, and by which commit.**
`desktop_docs_record.md` caveat 5 states the 07-12 review confirms *"the three 06-28 output
folders were deleted in `69115e0`"*. `git_record.md`'s entry for `69115e0` describes only
what it **adds** (`v3/pipelines/artefact_v1.py`, +666) and says nothing about deletions.
Not a contradiction — the git pass may simply not have listed them — but **unverified from
git**, which matters because every pass-1 number in this document then survives only inside
the desktop docs, with no run directory behind it.

**7 — How severe C-2 is.** `git_record.md`: *"the largest live contradiction in the repo …
Every artefact number produced from 2026-07 onward comes from the graph three separate
documents say must not be the product under test."* `desktop_docs_record.md`: *"The
contradiction is real at HEAD, but it is drift after 07-12, not a decision inside this
window."* Both are true of different moments and the compound status above says so, but the
two records genuinely differ on whether this is the project's central fault or an
administrative lag. **[CHAT] 07-26** supports the milder reading (he knows exactly which arm
he is building and why); the canon lines at HEAD support the harsher one.

**8 — Shared silences neither record can fill.** Not disagreements, but they bound
everything above: *why `qt.scopeWeight` was introduced* (git G-7, and the desktop corpus
names it as a removal target without explaining it); *why the built tagger is `z-ai/glm-5.1`*
(C-10 problem 2, undocumented in both); *prose authorship generally* (git G-1 — footers
appear on only eight commits); *how the corpus reached the machine* (G-6 — it arrived as an
unreachable stash of 1,550,956 insertions); *what the `DATA_README` shipped by `7879dfe`
says about cross-arm metric validity* (G-9 — read by neither pass, and it governs whether
any Era 5 number may be quoted comparatively).

---

# Provenance of this document

**What it is.** A reorganisation of two existing forensic records into one chronology. No
git object was read for it, no document was re-verified, no measurement was taken, and no
conclusion appears here that is not already in a source record. Where the two records
disagree, both readings are shown and the precedence rule decides — or, in the eight cases
above, nothing decides.

**Sources, all read in full:**

- `docs/canon/raw/git_record.md` — 1,760 lines. 74 commits across 30 refs, 91 `git show`
  reproduce commands, items labelled [USER]/[AGENT]/[UNKNOWN], contradictions C-1…C-18,
  gaps G-1…G-10.
- `docs/canon/raw/desktop_docs_record.md` — 1,575 lines. 20 desktop-only design docs
  (6 handoffs + 14 state docs, 6,719 lines of source), 2026-05-25 → 07-12, items labelled
  [USER-STATED]/[USER-STATED — paraphrase]/[AGENT-ASSERTED]/[UNCLEAR], ~150 recovered
  quotes, and a verdict on each of C-1…C-18.
- `docs/canon/USER_CANON.md` — 1,577 lines, 803 verbatim human turns 05-14 → 08-03, read as
  cross-reference only.

**Untouched.** Nothing under `docs/canon/raw/` was modified; `USER_CANON.md` was not
modified. Both raw records remain on disk as evidence and remain the authority — where this
file and a raw record differ, the raw record wins.

**Not opened.** `v3/data/questions.jsonl`, `v3/data/gold100.jsonl`,
`v3/data/heldout100.jsonl`, `v3/data/10smoke.jsonl` — per **[CHAT] 08-02**, *"honestly, you
should not have the questions/gold available to you, there is 0% good that can come out of
taht"*. Every question-set figure quoted here (1,514 = 815 + 699; the citation distribution
min 11 / median 52 / mean 71 / p90 170 / p99 298 / max 683; the near-twin product names) is
reproduced from inside a source record, not from the data.

**Citation conventions, restated.** A git claim carries the `git show <ref>:<path>` command
its record carries. A docs claim carries the desktop doc's filename and heading. A user
quote carries its date, and the `[CHAT]` / `[DOC]` / `[COMMIT]` class where `USER_CANON.md`
holds it. Authorship labels are those of the source records and are never silently upgraded:
**[USER-STATED]** means a quote survives, **[USER-STATED — paraphrase]** means only an
attributed ruling does, and the difference matters — C-16 rests on a paraphrase for six
weeks before a first-hand quote appears.

**Reading order for anyone continuing this work.** Eras run in date order and each closes
with *what diverged*. The eighteen contradictions are adjudicated in numeric order after
Era 6 so existing C-number references resolve; `git_record.md`'s by-importance order is
preserved at the head of that section. The three statuses used are **genuine silent drop**,
**documented reversal**, and **user decision misread as drift** — plus **not a
contradiction** where both records verified an item as sound, and **split** where the two
halves of one C-number resolve differently.
