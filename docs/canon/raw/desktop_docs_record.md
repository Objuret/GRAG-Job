# Desktop docs record — the handoff/state corpus, 2026-05-25 → 07-12

**Source.** `C:\Users\jocke\OneDrive - Högskolan Dalarna\Coding\state-transfer\GRAG-Job\_desktop_repo_docs`
— the desktop machine's gitignored `docs/handoff/` (6 files) and `docs/state/` (14 files),
6,719 lines total. Every file read in full. Read-only; nothing in the source was modified.

**Why this corpus matters.** It covers the exact window the two other records cannot reach.
`USER_CANON.md` starts 2026-07-06 (transcripts on the laptop only). `git_record.md` shows
outcomes but, per its own Part 4 (G-2), *"there is no commit on any of those dates … Every
decision in that fortnight … happened in conversation and arrived pre-formed in one 750-line
commit."* These twenty documents ARE that conversation, written down within hours of it. They
are agent-authored, but eleven of them carry an explicit **"Canonical user-established facts"**
section that separates what the user said from what the assistant proposed — a discipline the
project imposed on itself in June and mostly kept.

---

## Labelling

| Label | Means |
|---|---|
| **[USER-STATED]** | A verbatim user quote appears in the source doc, or the doc records an explicit user ruling in a "Canonical user-established facts" / "Decisions made (user)" slot with attribution. |
| **[USER-STATED — paraphrase]** | The doc records a user ruling but gives no quote. The ruling is attributed; the wording is the agent's. |
| **[AGENT-ASSERTED]** | An assistant proposal, synthesis, recommendation, or self-report. Includes anything in a "Working hypotheses"/"uncertain" section, and all agent-run measurements. |
| **[UNCLEAR]** | Attribution genuinely cannot be settled from the document. |

**The discipline these docs make possible, and its limit.** From 2026-06-09 onward each state
doc opens with a section that exists precisely to stop agent output being read back as canon —
`2026-06-09 §3`: *"Only things the user explicitly stated, confirmed, or corrected."* Those
sections are the highest-grade evidence in the corpus. But they are still **an agent's report of
a conversation**, written by the same agent whose proposals they are separating themselves from.
Three documents show that boundary failing and being caught: `2026-05-31` (*"you have created
something fucked up here"* — five memory files written as "decided" from a pasted summary),
`2026-06-11 §8` (the whole SemAxis axis/projection apparatus had *"leaked into docs/memory as if
decided"*), and `2026-06-25` (the memories and `DESIGN.md` found to **misrepresent** the facet
model). Where a doc's own later successor contradicts its canon section, I say so.

---

## 1. Inventory

### `docs/handoff/` (frozen session handoffs)

| # | File | Date | Lines | Covers |
|---|---|---|---:|---|
| 1 | `2026-05-25-graph-rag-retrieval-redesign.md` | 05-25 (earlier) | 144 | First retrieval redesign: bake-at-index vs synthesize-at-query; the 4-layer recall→filter→rank→cap shape; the 7-factor `scoreCypher` named as the violation; tagger temp 0.3→0; SQL-agent replaces Lucene as the baseline. Session was then **shelved** by doc #2. |
| 2 | `2026-05-25-middle-layer-weight-redesign.md` | 05-25 (same day) | 175 | Same conversation, deeper: three roles (indexing=math / interpreter=LLM / retriever=graph); five open product decisions (combinator, bake granularity, thresholds, rank default, facets-as-ordering); the facet "weight AND direction" origin statement. |
| 3 | `2026-05-25-artefact-audit-and-cleanup-plan.md` | 05-25 (latest) | 173 | The live audit of `herb-eval`. Verified node/edge/tag counts, the three weight layers with measured distributions, six real defects (23 unembedded tags, ~18% identifier pollution, dropped timestamps, `years` derived from tags, `relevance_to_file` mis-calibration, `w_facet` only categorical), the doc-drift list (`:NEXT` and `:Run` do not exist), and a $0 cleanup plan. |
| 4 | `2026-05-31-v2-artefact-rebuild-and-facet-design.md` | 05-31 | 108 | The v2 pivot session: references-not-copies; the scan→probe→reference→structure→tag→retrieve pipeline; identity resolution validated against real HERB; the oracle discovered; NVIDIA NIM verified (deepseek-v4-pro); the 7-tradition facet redesign; the retriever routing model (weighted activation propagation, dot-product combinator, no hard filters). |
| 5 | `2026-06-03-v2-chunking-model-design.md` | 06-03 | 49 | Chunking as coherent episodes; materialized integer path replaces flat ordinal; no overlap; deterministic boundary detector; embedding-based segmentation rejected; tagger model → Mistral Large (Swedish/Bonnier rationale); Swedish embedder chosen. Ends on an unanswered question about records-on-path vs COVERS. |
| 6 | `2026-06-04-v2-chunk-cap-and-budget.md` | 06-04 | 47 | The cap: ~3000 tokens = the tagger's focus span, *not* an embedder limit; the uniform split rule (best seam, not nearest); per-content-kind seams; embedding placement; cap calibration deferred to implementation time. NIM model default wired. |

### `docs/state/` (dated state-transfer documents)

| # | File | Date | Lines | Covers |
|---|---|---|---:|---|
| 7 | `2026-06-09-weight-production-measure-not-emit.md` | 06-09 | 170 | The weights thread: an LLM cannot emit correct weights; measure from embeddings; tag-vs-description distance as the signal; all facet weights on ONE edge; fewer/richer tags. Records the v1 `w_chunk` formula verbatim and the "42 is edges not concepts" trap. |
| 8 | `2026-06-11-v2-facet-carriers-and-build-gate.md` | 06-11 | 168 | The re-cut: per-chunk phrase-tag nodes (no shared vocabulary), the chunk description killed, all axis/projection machinery killed, per-facet unique mechanisms, sibling-relational measurement, intrinsic-on-node/relational-on-edge, facets' dual role, and **the design-before-build gate**. First v2 code (scan, probe). |
| 9 | `2026-06-12-v2-graph-spine-and-literal-matching.md` | 06-12 | 158 | The spine closed: `Source→File→Chunk→Tag`, nothing else is a node, via the user's node/attribute rule. Chunk→file weight killed. The full literal-matching pipeline (exact → vocab-free interpreter → scoped distance). All 1,514 HERB questions verified. A full docs/memory purge executed by removal. |
| 10 | `2026-06-14-v2-facets-as-relevance-channels.md` | 06-14 | 160 | The "facets as parallel relevance channels" breakthrough; same-facet matching; the tagger output schema verbally approved then immediately flagged for re-validation; derive-corpus stage 0 built (structural quarantine); mapping key finalized; repo split v1/v2; **the thesis recorded as done and submitted**. |
| 11 | `2026-06-18-v3-eval-harness-herb-ragas.md` | 06-18 | 338 | The eval methodology: **both** scorers (HERB anchor + RAGAS lens), deterministic citation-based context precision/recall, three arms with one shared generator, MetricScore tidy-long records, and the birth of `v3/` as the lean extraction destination. HERB/RAGAS/ARES read from primary sources. |
| 12 | `2026-06-23-v3-vector-arm-independence-comment-hygiene.md` | 06-23 | 306 | Arms share only the corpus on disk and the injected generator — sharing a reader is contamination, not fairness. `nim.py` transport. The "no historical or defensive comments" hard rule. Four undecided items (H1–H4). |
| 13 | `2026-06-25-artefact-tag-facets-vs-routing.md` | 06-25 (earlier) | 135 | The cut: tag-facets (semantic description of the phrase) ≠ routing (downstream consumer that owns weighting). Corpus-relative facet value. Topic → centrality. Recovered from a 06-15/16 transcript that had never been written up. |
| 14 | `2026-06-25-artefact-facets-guide-link-and-content-profile.md` | 06-25 (later) | 346 | **The pivotal document.** Recovers the real v1 facet definitions from git, diagnoses "the hollowing" (v2 misread `entities`/`evidence` as facts and deleted genuine semantic dimensions), and lands the guide-link design + the max-of-facet rephrase instrument. Declares `DESIGN.md`/`MODEL_CONTRACTS.md`/the memories **wrong**, not merely stale. |
| 15 | `2026-06-25-v3-vector-eval-k-vs-topk-ragas-ops.md` | 06-25 | 326 | **RAGAS ONLY — the HERB scorer purged and `eval/herb.py` deleted.** `k` (global ceiling) vs `top-k` (per-arm actual return). k=50 justified by HERB's median-52 citation count. The 4 judged metrics. Structured-output generator. NIM throttle ops. |
| 16 | `2026-06-28-artefact-build-deferred-and-next.md` | 06-28 | 646 | Pass-1 inventory: what was built, and eight deferred pieces each with why/unlocks/design/approach/open-question — aggregation path, categorical tag-attributes, centrality, fuzzy pre-pass, per-facet-axis split, chunk attribute extraction, geometry transforms, the Neo4j build. Five blockers. The k=10 baseline table. |
| 17 | `2026-06-28-artefact-build-design-evolution.md` | 06-28 | 1,272 | The 123-turn conversation reconstructed turn-by-turn with verbatim user quotes and `[tNN]` citations; 18 discarded ideas with reasons; 7 corrections; 9 cause-and-effect chains; a complete memory-file audit. **This is the single richest user-voice document in the corpus.** |
| 18 | `2026-06-28-artefact-lean-graph-live-facets-build.md` | 06-28 | 1,530 | The code record: every file, function, data structure, the full interpreter system prompt and JSON schema verbatim, the combinator math step by step, the graph shape, the end-to-end data flow, the gold-100 k=10 result table, 16 decisions with reasons. |
| 19 | `2026-07-01-artefact-pass2-dials-curve-relationships.md` | 07-01 | 463 | Pass 2, from a **parallel session** that did not know pass 1 existed. Facets are relevance **dials** ("how much"), not labels ("which"). The exponential curve. Embedded-fuzzy. DIFFUSE-FACET. **The relationships/hub-node pivot.** And the user's verdict killing pass 1. |
| 20 | `2026-07-12-v3-current-state-and-artefact-v1-review.md` | 07-12 | 205 | Repository review + the `artefact_v1` forensic audit: the 07-06 run's local recall 0.410 against Lucene 0.089 / vector 0.113 — with the **evidence-budget mismatch measured** (2.8× Lucene, 7.2× vector by characters) and declared not a fair win. Ten open problems. |

---

## 2. Chronological design record, 2026-05-25 → 07-12

### 2026-05-25 — the weight/retrieval redesign, then the audit that shelved it

Two handoffs from the same day describe the same conversation; a third, later one records a hard
pivot away from it.

**The origin statement for the whole facet program** — the user's last message before `/handoff`,
quoted in doc #2 §"Suggested next-session approach":

> *"but the point of the multifacets was to give the tag a more semantical weight and direction with the facets, how are the facets used now?"* — **[USER-STATED]**

Doc #2 §"Facets — design intent vs current state" records the intent behind it:

> "User's original intent: facets give a tag semantic **weight AND direction** — a directional/vector enrichment of the tag's meaning." — **[USER-STATED — paraphrase]**

and the degradation:

> "Current implementation degrades this to (a) edge filter, (b) embedding-space picker for grounding, (c) double multiplier in the 7-factor product." — **[AGENT-ASSERTED]** (verified against code)

**Weights are facts set at index, not synthesized at query.** Doc #1 §"Design conversation arc"
lists the user's articulated model:

> "2. **The retriever should not synthesize weights** at query time. No multiplicative compounding of independent signals into a derived score. 3. Weights are facts set at indexing; the retriever **filters or orders by an existing weight**, doesn't derive new ones. … 5. **Semantic weights are likely the most important part of the graph** — what differentiates it from a plain chunk store." — **[USER-STATED — paraphrase]**

**Multiplication rejected.** Doc #3's five open decisions §1: *"Multiplication is ruled out (user
said "specifically multiplication i am not sold on")"* — **[USER-STATED]**. Doc #1 adds the
reason: *"too brutal. Tangential chunks with strong tag fit should still be retrievable, just
ranked lower."* — **[USER-STATED — paraphrase]**

**The retrieval shape agreed:** recall (structural) → filter (weight thresholds, defaults at 0) →
rank (single ORDER BY) → cap (LIMIT). — **[USER-STATED — paraphrase]**, with five sub-decisions
left explicitly open and blocking implementation.

**Why the LLM cannot weight** — the user, quoted in doc #3 §"Facets":

> *"yeah it's high, because I chose it"* — **[USER-STATED]**, the user characterising the model's own weight behaviour. Doc #3: *"`w_facet` only has 21 distinct values across 255k edges because the LLM couldn't differentiate."*

**Only code change of the session:** tagger temperature `0.3 → 0` at `backend/tagging/pipeline.py:609`. — **[AGENT-ASSERTED]** (agent-executed, user-approved)

**The baseline switch that later un-switched itself.** Doc #1 §"Read these before doing anything else":

> "`memory/baseline-is-sql-agent.md` (added this session) | Lucene baseline is being dropped; **SQL-agent is the thesis comparison.** Do not frame analyses around Lucene going forward." — **[USER-STATED — paraphrase]**

**The pivot.** Doc #3 (the audit) §TL;DR:

> "**This conversation pivoted hard:** the user said *"fuck the instinct, talk about reality"* and declared the frontend not interesting for the session. … **The frontend retrieval redesign from the prior handoff is shelved for now. Do not pick it up unless the user re-opens it.**" — **[USER-STATED]**

#### The audit's measured findings — the empirical basis for everything after

All **[AGENT-ASSERTED]** but verified live against the `herb-eval` graph, and never contradicted
by any later document:

- **4 node labels, 3 edge types.** `:Source`×1, `:File`×33, `:Chunk`×4,869, `:Tag`×24,804;
  `:CONTAINS`×33, `:HAS_CHUNK`×4,869, `:HAS_TAG`×230,321. **"No `:NEXT`. No `:Run`. No
  `:CanonicalTag*`. (Schema doc claims these exist; they don't in `herb-eval`.)"**
- **`:NEXT` was argued unnecessary, not dropped:** *"Only `_part` kinds have order-dependent
  semantics (~12% of corpus). For those, `c.ordinal` carries the same info `:NEXT` would;
  `:NEXT` is not needed."* And *"All 33 files are `dispatch_mode=parallel`. The `sequential`
  tagging path with `_load_chunk_context` continuity hints is dead-but-documented code."*
- **The three weight layers, measured.** `relevance_to_file` mean 0.79, median 0.84, 90%+ above
  0.7 — *"Calibration is too high to discriminate at the top."* `w_chunk` 76 distinct values,
  constant across facet siblings. `w_facet` **19** distinct values over 230k edges, top 9 cover
  99%+ — *"Treated as continuous in code; functionally categorical with ~9-value resolution."*
- **The coverage_bonus works backwards from intuition:** *"cross-tab shows mean w_chunk is
  *lower* on `w_facet=1.0` edges than on `0.7-0.8` edges — because single-facet hits get
  penalized by coverage_bonus."*
- **The pollution quantified:** ~18% of 24,804 tags are literal identifiers — 2,352 `eid_*`/`emp_*`
  and 2,065 date-shaped; `eid_*` alone is 16,074 edges. *"only 1,072 of those are from
  `_supplement_lookup_tags` … **the other ~15,000 were emitted by the LLM during normal extract**
  because the tagging prompt doesn't tell the model "don't tag raw IDs as concepts.""*
- **The chunker discards source timestamps** — every `locator_json` has zero date keys, so
  `c.years` is back-projected from LLM temporal tags, *"a known violation of 'hard fields before
  tagging.'"*

The user's closing note: *"alright, good shit"* — **[USER-STATED]** (on the infrastructure work,
explicitly *not* signalling the next step).

---

### 2026-05-31 — the v2 pivot: references, not copies

**The core stance.** Doc #4 §2: the graph is *"a reference index over untouched raw source, not a
store of mutated copies. This is the root fix; v1's chunker fabricates prose and stores it as
`c.content`, with HERB chunk offsets pointing into the fabrication, not the source."* —
**[UNCLEAR]** as prose; the memory file `graph-is-references-not-copies.md` is named as its home
and the reference triple `{file_id, scheme, address}` + hash-verified resolve is recorded as
decided.

**The facet redesign from research.** Seven traditions (SFL, PMEST, AMR/neo-Davidsonian, 5W1H/SRL,
TAM, appraisal, RST) → convergent model → completeness + symmetry invariants → a
dimension→mechanism allocation table → **the five-facet set: topic, process, stance,
communicative-function, temporal-stance(TAM)**. — **[AGENT-ASSERTED]**.

> This is the set later documents repeatedly disown. `2026-06-25` §8: *"Treating the v2
> five-facet set as canon — it's an assistant research synthesis (SFL / appraisal / PMEST / AMR /
> RST), the user **never hard-approved the specific five**, and it hollowed the tag."* Doc #4
> itself says *"He drove the key insights (facets-as-dimensions, completeness-across-totality).
> Follow his lead; sharpen against research"* — so the *principles* are the user's and the
> *specific five* are the agent's. This distinction is load-bearing for C-6 and C-7.

**No hard filters — recorded as a strong user stance.** Doc #4 §"Retriever design":

> "**NO hard filters anywhere** (strong user stance) — "mandatory" = weight concentration; the **cap** does the cutting on rank. Resolves facets-as-filter-vs-ordering → always ordering." — **[USER-STATED — paraphrase]**

**The combinator.** *"prompt-conditioned weighted dot product — accumulate across relevant facets
(NOT max), relevance as a continuous coefficient (no gate), applied twice (facets→tag,
tags→chunk). Rejected: multiplication, raw add."* — **[AGENT-ASSERTED]**, consistent with the
user's 05-25 rejection of multiplication.

**Identity resolution validated against real data** (Employee=eid, Customer=CUST, PrAuthor=EMP as
a separate directory-less space) and **the eval oracle discovered**: `answerable_questions` +
`unanswerable_questions` carry `ground_truth` + `citations`, *"the contamination that polluted
`herb`"*. — **[AGENT-ASSERTED]**, empirically grounded.

**Tagger host:** NVIDIA NIM, `deepseek-v4-pro` chosen by benchmark; `kimi-k2.6` ruled out (~118 s/call). — **[AGENT-ASSERTED]**

**The behaviour correction of the session** — doc #4 §"User working style":

> "Early this session I wrote 5 memory files from a pasted prior-conversation summary as if "decided" — he called it out hard (*"you have created something fucked up here"*). Only record what was actually decided/established *in conversation*." — **[USER-STATED]**

---

### 2026-06-03 / 06-04 — chunking and the cap

**A chunk is a coherent episode**, not a fixed-size window; v1's fill-to-budget batching is
killed. Build by descending the source's own structure. — **[AGENT-ASSERTED]**, presented as the
session's joint design output and never disputed later.

**The materialized path** replaces the flat ordinal: integer components `[1,2,3]` carrying
position only. *"The same path does ancestry + context-expansion + dedup."* Over-budget episodes
split into prefixed subchunks that are *just chunks* — **no parent node**. — **[AGENT-ASSERTED]**;
confirmed by the user on 06-12 (*"didnt we have a discussion about the relational
chunks->subchunks file hierarchy such as 1.1.2…?"* — **[USER-STATED]**, and the 06-12 doc records
it as *"decided canon, untouched, now MORE load-bearing since the path attribute is how the tree
exists without branch nodes"*).

**No overlap** (fights references-not-copies, dirties COVERS). Boundary detection fully
**deterministic** — reply/quote links > adaptive relative time-gap > participant turnover;
**topic-drift/embedding-similarity considered and rejected**. — **[AGENT-ASSERTED]**

**The cap = the tagger's effective focus span, ~3000 tokens.** Doc #6:

> "The "budget" is **not** a token-count-for-its-own-sake and **not** an embedder limit (the embedder only ever sees short artifacts — tags and the chunk **description** — never raw chunk prose). It is the **tagger's effective focus span** … grounded in lost-in-the-middle / RULER / NoLiMa. **Cap ≈ 3000 tokens** (vs v1's 800/1500) — deliberately *larger* than the RAG 512–1024 band because v2 never embeds the raw chunk … 3000 is a **calibration seed**, not final." — **[AGENT-ASSERTED]**

**The cap sweep was deferred deliberately, not forgotten.** Doc #6 §"Open items":

> "**Cap calibration** — the only thing left on the chunking design, and it's *implementation-time*: an empirical sweep of chunk size vs tag relevance + description specificity, which can run only once the v2 tagger + chunks exist. **Not actionable yet.**" — **[AGENT-ASSERTED]**

**Tagger model revision 2:** `mistral-large-3-675b-instruct-2512`, *"chosen for Swedish fidelity
on the Bonnier data … tier beats recency, so Large over the newer mistral-small-4."* Swedish
embedder `nvidia/llama-3.2-nv-embedqa-1b-v2`. A second NVIDIA account to stack keys was
**rejected** (ToS + reproducibility liability). — **[AGENT-ASSERTED]**

**Two behaviour rules landed here**, both **[USER-STATED]**:

> *"you fucking run off and do your own thing"* (on being handed a 3-tier build plan in answer to "go on then")
> *"dont just agree, i was asking."*

and **delete-don't-preserve** — doc #5: *"Never keep legacy/superseded content, backups,
fallbacks, or tests on your own initiative. When you supersede something, delete it. Preservation
needs *explicit* approval."* — **[USER-STATED — paraphrase]**

---

### 2026-06-09 — weights: measure, don't emit

The first doc with the formal canon/hypothesis separation. Its §11 is blunt: *"the user is
actively co-designing the weight mechanism and has NOT decided it. Most "answers" in the
transcript are assistant proposals, several of which were wrong."*

**The spine of the whole weight design** — §3, all **[USER-STATED]**:

> "**An LLM cannot put correct weights on tags or chunks.** This is the user's central conviction and the spine of the whole discussion."

> *"Measure from embeddings (IF POSSIBLE) is way better than more prompting."* … *"measure from embeddings was my idea."*

> *"might as well keep the description and embedding of it i guess, we can discuss the compute/cost that choice is worth."* (description kept — **tentatively**, cost justification deferred)

> The tag-vs-description distance is a real signal: a tag embedding is *"ONLY THAT TAG… no other relationship in this void"*; the chunk description *"IS a semantic relational sentence or two"*; comparing them measures *"the relevance of the tag in distance from the chunk."*

> **All facet weights on the SAME edge:** *"weren't we supposed to have ALL the facet weights on the SAME edge!?"* and *"why the actual fuck would you want or need a separate edge for each facet?"*

> Richer tags mean fewer tags: *"perhaps we get less tags like this?"*

**The principle stated in one line** — §5:

> "**the model identifies (qualitative — which tags, what description), and geometry measures (quantitative — the weight). The model never emits a number.**" — **[AGENT-ASSERTED]** as phrasing, **[USER-STATED]** as substance

**Preserved v1 evidence** (§4, all measured, **[AGENT-ASSERTED]**): the `w_chunk` formula verbatim
(`strength × coverage_bonus`, α=0.25, N=5); anchoring 85% single-pass → 12.3% two-pass;
distinct-value counts 76 / 21 / 86; and the trap — **"42 tags per chunk" is 42 EDGES**, facet-
multiplied by the ≥0.50 rule, not 42 concepts.

**Two assistant claims the user rejected** (§8) — worth recording because both sound reasonable:

- *"Comparing a tag embedding to a description embedding hands the number back to the model."*
  **FALSE** — the cosine is geometric; the model produced two *texts*, not the number.
- *"tag-vs-description is a tautology / comparing the chunk to itself."* **FALSE** — a chunk's
  tags differ in distance to the description; that difference is exactly the ranking signal.

Both **[USER-STATED]** corrections.

**Behaviour rules, all [USER-STATED]:** *"do NOT repeat shit"* / *"why the fuck did you just
REPEAT THAT SHIT"*; *"does it look like im here to have a conversation with my fucking
history?"*; *"you searched online for that specific solution… instead of actually doing real
research"* (the confirmation-search failure).

**Also landed 06-09, user-approved** (§10): design-doc **§9.5 "one stateless call per chunk"** and
a new **§16 build-time validation strategy** (tags = code assertions; weights = invariants; error
analysis first; ~30 samples catches a bug, 250–500 measures a rate; *"the one design blocker = the
tagger prompt/output contract"*).

---

### 2026-06-11 — the re-cut: phrase nodes, no description, the build gate

Its own header: *"THE SHARED-TAG-NODE MODEL AND THE AXIS/PROJECTION WEIGHT APPARATUS FROM EARLIER
DOCS ARE DEAD."*

§3, **all [USER-STATED]**:

> **The model emits NO numbers, ever** — tagger and interpreter both. v1 evidence in the user's words: *"it took so fucking long to get it right and it still didn't work at all."*

> **Tag = a small concept (contextual phrase), and the phrase IS the node** — no bare-word shared tag nodes, no synonym canonicalization; cross-chunk linking is embedding **proximity**: *"what if we don't do the word, and just have the embedded 'small concept' as the node"*. The doc marks this **the user's idea**.

> **No chunk description.** *"Since the collective tags from a chunk should BE the content of the chunk, why do both?"* — the doc notes *"(User asked twice; it is dead.)"*

> **Tag relevance is measured against SIBLINGS** — *"compare each phrase to its siblings"*; and per-facet: *"perhaps we can do that, but based on each facet! giving a relational value of the tag to its siblings based on each facet!?"* (marked the user's idea, verbatim).

> **Node/edge split (the user's proposal):** *"the weight of the tag is ON the tag, because that is the phrase's concept being valued, and the 'in relation to the siblings' weight is on the edge."*

> **ALL facets are evaluations** — *"stance is not a magical facet, ALL facets are evaluations."*

> **Each facet gets its own UNIQUE mechanism** — *"i think we have to have unique ways of doing it for each facet"*. The doc flags the trap: concept uniform, instruments differ; hold both.

> **Facets are dual-purpose:** *"cluster or weight-adjust, aka narrowing or focusing the actual search-area of the corpus for the routing"*; *"if the prompt is heavy in a facet, those facets are 'worth more' for the prompt/route."*

> **Facets = extractable meaning dimensions of language** — *"things you can extract from language, the things that actually 'mean' something"*.

> **Linguistics belongs to the interpreter:** *"for the interpreter, it's helping it interpret the prompt, and picking it apart for tools, routes etc."*

> **The frontend is cut:** *"perhaps we even cut away the entire front-end... it just confuses agents"*. With it the API layer — v2 retrieval becomes a Python library + CLI.

> **The oracle never enters the corpus:** *"we just don't fucking include the eval part in the dataset, why is this an issue even"*.

> **v2 is a from-scratch rebuild beside v1:** *"we don't keep shoveling around bad, useless or legacy code building dependencies on old stuff"*.

**THE BUILD GATE** — §3, the rule that governs everything afterward:

> "**Design before build (the gate):** the assistant started coding on a misread; user: *"that means we fucking have to make sure all parts are decided upon first."* All parts decided before pipeline code." — **[USER-STATED]**

The scan+probe code already written was allowed to stand because its design was settled; the gate
became law from that point. The doc also records **[USER-STATED]** *"The tagger design is NOT
done — user called out the assistant's false claim"* (*"that.. does not seem fucking true at
all"*).

**The axis apparatus killed** — §8:

> "**The axis/projection apparatus is DEAD.** SemAxis-style facet axes, pole words, hand-written anchor-phrase poles, "stance-type axes" — all assistant inventions from earlier sessions that leaked into docs/memory as if decided. User: *"honestly, none of what you are saying now is a thought I have had, where the fuck did all of this even come from."*" — **[USER-STATED]**

**The explicit three-bucket ledger** (§7/§11) is the corpus's cleanest honesty device: nine
proposals labelled *"uncontested but never blessed"* — topic-as-sibling-centrality, stance
carrier, function carrier, process carrier, time carrier, interpreter property list, router
template library, multi-hop bridges, world-facts rule. All **[AGENT-ASSERTED]**; the doc forbids
presenting any of them as decided.

Two **[AGENT-ASSERTED]** risks flagged and never resolved: (a) per-chunk phrase nodes make
corpus-wide recall depend on k — no shared node means no one-hop "all chunks about X"; (b)
multi-topic chunks under-weight both topics under naive centroid centrality.

---

### 2026-06-12 — the spine closes

§3, **all [USER-STATED]**:

> **The graph spine is `file → chunk → tags`** (forcefully): *"if we are saying file -> chunk ->tags .. where are those OTHER RANDOM FUCKING NODES!?"*

> **The node/attribute fork is the user's:** *"either they are nodes, but then we get edges to EVERY fucking chunk, or they are just attributes… perhaps it's smarter to just have shit like that as attributes on chunks."*

> **Records-as-nodes is dead:** *"that sounds a bit fucked up to have them as nodes, most of them will be a chunk, meaning we have 2 almost same nodes."*

> **No value inventories in the graph:** *"that has the potential to put a fuckton of data into the graph, both GDPR data, and not. why not just have the parent field as the connection and when searched for, you can find anna."*

> **Minted facet-label hub nodes are dead:** *"it's dead, such shit is 'interpreter area'"*.

> **Chunk→file relevance value killed** — the user asked to *"revisit the value and point of 'chunk value to its file'"*; the kill landed. Plus a user correction: **the chunk never had embeddings — the description had**, *"but that was not the point of that field anyway."*

> **Humans don't type correctly:** *"thinking humans write correctly, is naive as fuck, ESPECIALLY when talking to an llm."* → *"exact + fuzzy IS the way to go for herb"*.

> **No corpus vocabulary in the interpreter's context:** *"i am honestly not sure we want to give it the vocabulary, remember, every extra context costs money."*

> **Field handling follows data shape:** *"this must be based on the structure of the final leaf/branch data-form… different ways of handling fields based on the type of data in them."* — blessed only *"ish"*: *"honestly not sure about that specific solution.. but yeah.. ish"*.

> **v1 docs stay untouched:** *"that shit is still true for THAT build."* — the rule that explains why v1's decision log was never retro-edited.

> **Removal, not banners:** *"please do continously update information according to the things we decide"*, and when asked whether stale content had been removed or merely annotated — *"did you REMOVE, quarantine, legacy-note or something else"*.

**The node/attribute rule, stated formally** (§4) — **[AGENT-ASSERTED]** phrasing of a
**[USER-STATED]** rule:

> "a thing is a **node** only when others depend on its facts to resolve themselves, or retrieval walks *through* it; it is an **attribute** when it is a value you filter/boost by."

**One embedding surface:** *"the pipeline embeds **phrase tags only**. No field values, no
descriptions (dead 06-11), no raw chunks."* — **[AGENT-ASSERTED]**, following from user rulings.

**The literal-matching pipeline decided in full** (§4): deterministic exact pre-pass with matched
literals stripped → vocab-free interpreter flags type + wanted/excluded → flagged miss triggers a
**scoped string-distance lookup against that one directory only** → described-not-named falls to
semantics. Ambiguity: all candidates boosted, confidence sets boost size, jump only on
exact-unique. Multi-hit: boosts only, additive (*"a does seem to fit the best"* — **[USER-STATED]**).

**HERB verified against all 1,514 questions** — **[AGENT-ASSERTED]**, run inline that session:

> "template-generated, perfectly spelled, products named exactly, customers named verbatim … people referenced by ROLE ("Engineering Lead") never by name; employee IDs are the *answers*, not prompt inputs. No typos, no paraphrases anywhere."

and the twins — ContentForce/ContextForce, CollaborateForce/CollaborationForce,
SearchFlow/SearchForce, TrendForce/ForecastForce — *"all real, separate products. Embeddings/string-distance
conflate them; only exact matching separates them."* This measurement is why blanket typo-fuzzy was
rejected and the exact layer is load-bearing.

**The corpus's most instructive agent failure** — §8:

> "**"Forcing shit into the graph" — the assistant did this THREE times** and must not again: (1) embed-the-vocabulary inventory, (2) "search the employee field's values in the graph" (values are NOT in the graph; they're in raw, reachable via references — *"where the fuck in the graph do you think this is?"*), (3) "metadata islands" (Employee/Customer nodes kept by inertia from the dead 05-30 draft — *"why the fuck and from WHERE do the random nodes and other shit come from?"*)." — **[USER-STATED]**

Also **[USER-STATED]**: *"there is so much you missed here… i fucking cant keep saying this shit
over and over, we loose information everytime"* (on claiming doc coverage from two greps), and
*"use speech english instead of this almost 100% jargon."*

---

### 2026-06-14 — facets as relevance channels; the thesis is done

**The single most consequential framing fact in the corpus** — §3:

> "**Thesis is DONE/submitted (2026 VT).** v2 is post-thesis. Do NOT justify/frame work around thesis needs or "thesis numbers." (User: *"drop the fucking thesis... it's done, this is post-thesis work."*)" — **[USER-STATED]**

Everything from 06-14 onward is post-thesis engineering. This is repeated in the 06-18 and 06-25
eval docs and is the direct antecedent of the user's July line *"thesis? wtf? we are building the
fucking artefact here"* in `USER_CANON.md`.

Other §3 facts, **all [USER-STATED]**:

> **Structural, not declarative, quarantine:** *"DONT INCLUDE THE FUCKING EVAL FILES FOR THE PROBE TO EVER SENSE."* A yaml `eval_holdout:` declaration was rejected as the weak version.

> **One derived artifact only:** *"pre-make 1 training-set and then do the eval on the 'original'."* — the harness reads the oracle in place from raw; no `eval/` copy.

> **Nothing deleted in the repo separation** — *"two repos in the same repo"*; the user overrode an assistant proposal to delete v1.

> **Cold storage is untouchable:** *"do not touch A:\exjobbet\data\raw at all, that is the storage, the one in the repo can be worked with."*

> **Tags unique per chunk** — same phrase may recur, each emission its own node. (User proposed.)

> **HERB-only; Bonnier deferred:** *"the Bonnier set will have to wait until some other time."*

**THE FACET BREAKTHROUGH** — §3, the user's framing *"hammered home repeatedly"*, **[USER-STATED]**:

> - Base the tag concept on v1. **The v1 tag CONCEPT was sound; the WEIGHTS were the problem** (specifically that they were *model-emitted numbers*).
> - Facets give **"relevance weights, not interpretation."** A facet is NOT a category, NOT a bucket, NOT a chunk attribute — it is a **relevance coordinate / the character of a tag**.
> - The per-facet weights live on **ONE edge** chunk→tag (v1's "one edge per facet" was bad implementation/communication; intended = one edge carrying the whole facet vector).
> - **Retrieval mechanism:** the interpreter decomposes the prompt **per facet**; matching is **same-facet, like-for-like** — prompt TOPIC vs tag TOPIC, prompt STANCE vs tag STANCE. Each facet is a **parallel comparison channel**. Routing sums the channels weighted by how much the prompt cares about each.

**A critical caveat the doc puts on its own decision** — §6.4:

> "**Tagger OUTPUT schema approved** in conversation (calls a/d/f): per-facet contextual-phrase lists for the open facets + closed-enum chunk attributes for function/TAM … **CAVEAT: this approval predates the §3 facet breakthrough and the §8 carrier reversal — re-validate it.**"

This is the exact reopening `git_record.md` finds in `MODEL_CONTRACTS.md` §5 and cannot resolve.

Also **[USER-STATED]**: the user rejected the contracts doc as an approval vehicle — *"i never saw
the fucking schema"*. And the session's mood: *"driving me insane"* (the assistant repeatedly
lunging at implementation instead of holding the concept).

**Model-choice honesty note** — §3, **[AGENT-ASSERTED]**:

> "**Mistral is the tagger model** … NOTE: the original Mistral rationale was Swedish fidelity — **now moot under HERB-only** — so the model choice rests on "largest tier" reasoning, not Swedish."

The Bonnier-rationale collapse that `git_record.md` flags as C-10 problem 1 was noticed and
recorded here, on the day, just never carried into `DESIGN.md` §11.

**Built and run this session** — **[AGENT-ASSERTED]**: `derive_corpus.py` stage 0 (strip set
`answerable_questions`, `unanswerable_questions`, `team`, `customers`; 18 tests pass; verified
against the HERB dataset card + arXiv paper), the mapping key finalized to three declarations,
and the `git mv` repo split into `v1/`/`v2/` (~194 renames, uncommitted).

---

### 2026-06-18 — the eval harness: two scorers, on purpose

§3, **all [USER-STATED]**:

> **Cost carries ZERO weight in the assistant's reasoning:** *"YOU do not care about cost here, 0 fucks given… only for me. so fucking drop that fast as fuck."*

> **`v2/` = build-site (mess allowed); `v3/` = the place to save the CLEAN, lean stuff.** New working model the user defined this session.

> **The user writes the real code.** Reason given: *"to ensure it does what's intended (v1's eval ran RAGAS metrics that measured the wrong thing)."* Assistant provides structure/spec/review only.

> **Do BOTH scorers** (HERB + RAGAS), not either/or: *"no, i am saying we do both."*

> **RAGAS-on-the-answer primary; HERB's exact scorer the anchor/secondary** — user confirmed "yes".

> **v3 must be LEAN** — no folder-per-concept, no fat trees. *"The user is repeatedly, intensely angry about assistant-created bloat and 'structural noise.'"*

> **Talk like a person, not a "shit machine."**

> **Check what already exists before creating anything** (the assistant had created a third parallel eval directory).

**The decided methodology** — **[AGENT-ASSERTED]** design, user-approved on the numbered points:

1. Both scorers; RAGAS primary, HERB anchor.
2. **Deterministic citation-based context precision/recall** (ID-based / non-LLM), not the judged
   variants — *"because in v1 the judged variants were degenerate (precision ~0) and biased
   (recall favored bigger context bags)."*
3. Three arms, one shared generator built once in the orchestrator; baselines build their own
   index over the corpus.
4. Evaluators emit raw per-question `MetricScore` records, tidy long, never pre-aggregated, plus a
   `RunManifest` — so paired Wilcoxon/McNemar, bootstrap CIs, per-type splits, effect sizes and
   judge κ all remain possible downstream.
5. `v3` created lean; layout user-shaped.

**The category error corrected** — §8, **[USER-STATED]**:

> "**DO NOT treat the artefact as "just another retriever" scored by IR recall@k.** Category error the user corrected hard. The artefact is the SYSTEM UNDER TEST, not an IR retriever; and HERB itself ships **no retrieval-recall metric** — it scores ANSWERS only."

**Verified external numbers** — **[AGENT-ASSERTED]**, read from primary sources: HERB 815
answerable (238 content / 260 people / 130 customer / 187 artifact) + 699 unanswerable = 1,514.
Leaderboard: zero-shot 4.55, vector 16.77, hybrid 20.61, ReAct GPT-4o 32.96; oracle Gemini 85.76 /
GPT-4o 61.73. Judge = GPT-4. **ARES considered and rejected** for HERB.

**The construct-validity caveat, raised and never closed** — §7, **[AGENT-ASSERTED]**:

> "answer-level scoring measures the whole pipeline, so a strong generator can mask retrieval quality. Keeping the deterministic context precision/recall … is what keeps an endpoint pointed at retrieval — the artefact's actual claim. Plausible and important; **not yet a locked decision.**"

and **judge calibration**: *"to defend the judged RAGAS metrics academically, calibrate against a
small human-labeled subset and report agreement. Recommended, not locked."* — **[AGENT-ASSERTED]**,
never actioned.

---

### 2026-06-23 — arm independence and comment hygiene

§3, **[USER-STATED — paraphrase]** (this doc records rulings without quoting them):

> "**The arms share ONLY two things: the corpus files on disk and the generator the orchestrator injects.** … Arms must NOT import or reuse another arm's corpus-reading or retrieval code. *Reusing a reader, or framing a shared unit set as a "fairness requirement," is contamination, not fairness* — because **how each approach turns the one shared corpus into retrieved evidence is the independent variable the experiment measures.**"

> "**No historical or defensive comments** … Rationale the user gave: narrating a fix invents fake project history AND — because comments/docs feed the graphify graph and the memory files — **dilutes the context of every future conversation.**"

The rule's own enforcement failure is recorded: the agent embedded a review-finding label ("F1")
*inside the CLAUDE.md rule forbidding such labels*, and the user caught it.

**Four items left undecided (H1–H4)** — **[AGENT-ASSERTED]**, and none is recorded as resolved
anywhere later in the corpus: lucene/vector `documents.feedback` parity; whether slack `userId`
tokens dilute the vector embeddings (*"slack is the dominant cited kind, so blast radius is
wide"*); empty-text artifact placeholders; README phrasing cleanup.

---

### 2026-06-25 (earlier) — the cut: tag-facets ≠ routing

Recovered from a 06-15/16 transcript that *"was never crystallized into a state doc"*. §3, quotes
verified against that transcript, **all [USER-STATED]**:

> *"I think we should separate tag facets and routing."*

> *"I more get the feel that those 5 in v2 are almost only viable for the interpreter. While the v1 facets were actual semantic meaning around the tag."*

> *"We have literally removed ALL semantics and just replaced large chunks of text with short descriptions."*

> *"we only have a few short phrases now instead of a fuckton of tags with facets … I still think we need another semantic layer here, like the facets on the phrases. Would not the old facets work with the new tags? (not the weighting, the concept)."*

> *"the facets then use the entire tag-korpus as base for the evaluation of each facet on them, so their facet-value is relational to the korpus/facet."* — carried as a small facet **attribute**, *"not nodes … because that mean edges right, and those are heavy in all aspects"*.

> *"Topic is not for facets tbh, how does it even fit there? Perhaps how much of the topic the tag is about? Or perhaps this is relative to all tags in the same chunk."* → topic becomes **centrality** (chunk-local degree).

**What this doc kills** — §7: *"A facet = the relevance coordinate / character of a tag" (the
06-14 framing) — **DEAD**; that was routing leaking into the facet definition."* And *"The
five-facet set as closed canon — reopened."* — **[AGENT-ASSERTED]** conclusions from
**[USER-STATED]** premises.

Note: this doc **supersedes on facets the very breakthrough recorded eleven days earlier**. The
facet definition changed three times in June alone (06-14 relevance-coordinate → 06-25 semantic
description → 07-01 relevance dial).

---

### 2026-06-25 (later) — the hollowing, and the content-profile revelation

The pivotal document. Its §1 states the problem plainly: the written canon *"and in one case
**wrong**"*.

§3 quotes, **all [USER-STATED]**:

> *"the point of the multifacets was to give the tag a more semantical WEIGHT AND DIRECTION"*

> *"the agents assigning facets was pretty much impossible to get different values from, they just did 'yeah, its high, because I chose it'"*

> *"giving a relational value of the tag to its siblings based on each facet"*

> *"'one edge per facet' was just bad communication... they were supposed to be on the same fucking edge"*

> *"it feels retarded to put facets on chunks, we are routing by tags, why the fuck put the facets AFTER that?"*

> *"What you think is v2 tags is in essence everything moved to hard fields or put on the interpreter"* — the sharpest statement of the hollowing.

> *"Temporal was never about dates"* — dates → structure; the time-RELATIONSHIP is the meaning.

> *"is it the 'design this from the retrieval side' that has been fucking you up so bad?"*

**THE HOLLOWING — the diagnosis that resolves C-6.** §5, **[AGENT-ASSERTED]** diagnosis,
**[USER-STATED]** confirmation:

> "The v2 redesign allocated every dimension across mechanisms … and that **emptied the tag**, because for every dimension there was a cheaper structure-or-interpreter home: entities → hard fields; temporal → hard fields + interpreter; communicative-function → structure + interpreter; stance → interpreter; topic → just the phrase's embedding. So the "v2 tag" is a bare topic phrase. **Tag-facets must be a THIRD thing: semantic content that lives ON the tag — neither a fact (structure) nor a query-decomposition (interpreter)** — i.e. *what KIND of content the tag is*. That is exactly what v1's content profile was."

§8, the misread named:

> "**"entities / temporal / evidence are fact dimensions, relocate to structure"** — **WRONG about evidence and entities.** `evidence` = information-KIND (metric/argument/procedure/…), a real semantic dimension; `entities` = named-thing TYPE, semantic. The *fact* (eid, URL) is structure; the *kind/type* is meaning. **This misread is what hollowed the tag.**"

and the provenance failure that caused it:

> "The memory `facet-semantic-framework.md` says "evidence = sourcing, not links"; the actual v1 doc says evidence = kind-of-information. **Read the v1 source, not the summary.**"

**The new design (the user's, current)** — §5, **[USER-STATED]**:

> 1. **The guide link:** a facet is a concept both sides are measured-close-to — the tag's closeness to it and the prompt's closeness to it; the shared closeness IS the match.
> 3. **"max-of-facet rephrase + embed-compare":** *Tag side (build)* — for each facet, recreate the phrase as "max of this facet", then embed-compare the max-F version to the original → the tag's value on that facet. *Prompt side (query)* — do the same to the prompt, rank facets by which was closest → that ranking is the prompt's facet-relevance, which modifies the tag's weights / filter / order.

**The disconfirming research on the user's own mechanism** — §7, **[AGENT-ASSERTED]**, delivered
straight rather than buried:

> "the rewrite-to-facet + embedding-distance scalar **conflates three things** — (1) incidental wording change (LLMs over-edit), (2) topic leak, (3) the actual facet change — and embedding distance tracks **surface/lexical** change more than the attribute, so it can run **backwards** … **Confirm/reject via a ~30-phrase probe.**"

Plus the **orthogonality risk**: *"If facet-concepts overlap in embedding space, the two
closeness-profiles correlate and facets collapse into one (v1: 85% of tags multi-facet at
threshold 0.50; topic/activity/evidence bled together)."*

---

### 2026-06-25 — RAGAS only, and the k / top-k distinction

§3, **all [USER-STATED]**:

> "**SCORING IS RAGAS ONLY. There is NO HERB scorer.** The user said this twice, emphatically (*"this is ONLY RAGAS"*). The old "HERB + RAGAS / two-way scoring / HERB anchor" framing is **dead** — purged this session. `eval/herb.py` was **deleted**. Do not reintroduce a HERB scorer from any stale doc."

> "**MY WORDS ARE THE CANON** (user's literal phrasing). When the user defines the experiment, that IS the spec. Do not "correct" it with references, production-RAG norms, or training pattern-matching."

> The four judged metrics: *"those 4 + the free ones"*, earlier phrased *"3 we used in the thesis + the dropped one"* → answer_correctness, context_recall, faithfulness, context_precision.

> **`k` and `top-k` are TWO DIFFERENT NUMBERS** — the session's most forceful point.

> **k = 50**, **gold-100 not the full 1514** (*"The user was furious when an earlier command used `--set full`"*), structured outputs for the generator, the user runs the scripts, and the pre-run y/N prompt removed as *"the dumbest fucking shit"*.

**The definitions, verbatim** (§4) — **[AGENT-ASSERTED]** wording of a **[USER-STATED]**
distinction:

> "**`k` = the global CEILING.** One fixed number, **identical for every arm**, chosen for **experiment feasibility** … the controlled variable.
> **`top-k` = each arm's ACTUAL RETURN under that ceiling.** Per-arm … the **measured** thing — read off via the arm's **token cost**: a dumb arm fills the whole ceiling; a selective arm returns fewer. **The token-cost gap between arms is the experiment.**"

This is the user's own design for how arms should be compared. It matters that both baselines are
single-stage: *"for them **top-k = k always** … The differentiation for baselines is therefore
token cost from *content size*, not count."*

**The measured justification for k=50** — **[AGENT-ASSERTED]**, computed that session over 815
answerable questions:

> "min 11, median 52, mean 71, p90 170, p99 298, max 683. Implication: at k=10 ZERO questions can reach full citation recall (min is 11). Recall@k is structurally capped at any sane k — **that is a property of HERB, reported honestly, not a bug.** The cap is equal across arms so the comparison stays fair."

---

### 2026-06-28 — pass 1: the lean graph + live facets (built and run)

The 123-turn conversation is reconstructed in doc #17 with turn citations. The decision chain that
produced the shipping tagger:

**[t14] [USER-STATED]** — the user reveals the design:

> *"allright, since i am a cunning cunt, my design here is a combination of these fuzzy things, embeddings AND fuzzy-lexical hard fields that also guides … combinations of solutions are the trick in my humble opinion"*

**[t18] [USER-STATED]** — the layer separation:

> *"well, i separate the 'facets' the interpreter use, and the actual real contextual/semantical facets the graph has in it"*

**[t24] [USER-STATED]** — fuzzy pre-pass and multi-hop, both raised by the user:

> *"first, i think there might be some value to do embeddings for the deterministic pre-pass, and just let it be 'fuzzy', unless exact, i guess.. but use it as a weight instead, aka area ranking or something like that, giving us a few dimensions of ranking on this route … also, how does this full solution actual handle 'multi-hop' questions? i am unsure about this"*

**[t27] [USER-STATED]** — and the correction that reversed the assistant's read of the benchmark:

> *"quite alot of multihop, check the HERB documentation instead of asking me"*

The assistant had claimed HERB was mostly single-hop; reading the dataset card reversed it — *"HERB
is fundamentally a multi-hop + aggregation benchmark … Every gold-100 question is multi-hop …
several need aggregation."* **[AGENT-ASSERTED]**, verified.

**[t33] [USER-STATED]** — the graph question that generated the aggregation design:

> *"but, doesnt the graph give actual relational connections to things like this, i mean, if the 'name' example you had, why wouldnt if just find all of those names? i dont get it"*

The answer (**[AGENT-ASSERTED]**): the graph *does* have them — chunk attributes + references +
directory joins. *"The gap is not graph structure, it's a **query-side path that composes those
pieces**."*

**[t42] [USER-STATED]** — the load-bearing cut:

> *"ah, yeah, i agree, not all facets should be graded in the same way"*

→ three measurement natures: categorical (entity-type, info-kind) / graded (activity, argument,
case_study) / scalar (centrality). The uniform 5-vector dies here.

**[t49] [USER-STATED]** — the direction the user likes:

> *"i mean, i really do like the concept of clustering tags/weights on facets based on the prompts values"*

**[t52] [USER-STATED]** — **the architectural pivot that produced the flat tagger**:

> *"honestly, an optimal solution would to NOT have all of this in the graph, intead do it live-prompt-time, because of the size it's becoming, BUT, embeddings, values, pointers etc, might be ok"*

→ *"lean graph, live facets."* Graded facets move to query time; nothing per-facet is baked or
emitted. The doc's cause-and-effect §4 spells out why this dissolved three open problems at once
(instrument, axis-definition, calibration) and flags the cost honestly: *"the §3 canon 'baked at
index, corpus-relative vector on the tag' is departed for the graded part. The user accepted this
at [t52]."*

**[t68] [USER-STATED]** — no phrase text in the node:

> *"just some thoughts btw, thinking about the actual size of the graph here, is there a reason to have the phrases in there? shouldnt we just embed them and put the embedding as a node in the graph instead with the reference just like the phrase would have?"*

**[t81]/[t82] [USER-STATED]** — the embedder and both stores:

> *"embedder is nemo, graph, do both, just do the db for my sake also, i like the visual representation of it and i want to see the size, else, yeah, can do it as a structure only, but, remember it's graph-shaped"* … *"fs,. i just said it's NEMOTRON FFS!"*

**[t59]/[t62]/[t65] [USER-STATED]** — the k / clustering exchange, directly relevant to
`USER_CANON`'s later "levels of k's" thread:

> *"wtf is this? 'HNSW (or FAISS)'"* → neither; exact kNN over a numpy matrix at HERB scale.
> *"do we do a knn = number of facets then over the tag corpus?"* → no: one full matmul, `tag_matrix @ facet_phrases.T`.
> *"ok, so you think its better to use it as ranking straight up rather than fuzzy cluster -> ranking?"* → the assistant's answer (**[AGENT-ASSERTED]**): *"they're the same thing … 'Ranking straight up' with the continuous cosine matrix IS the fuzzy-cluster-then-rank."*

**[t114]/[t119] [USER-STATED]** — the record demand that produced the trio:

> *"Allright, you need to collect exactly all the information of what you built, how it was built and why, ALL of it, NOTHING can be left out … EXACTLY THE ENTIRE FUCKING BUILD."*
> *"conversations and memories also count, just because it didnt leave a conversation doesnt mean it shouldnt be saved"*

#### What pass 1 actually is (doc #18, **[AGENT-ASSERTED]**, code-level)

Interpret (`meta/llama-3.3-70b-instruct`, one-shot, temp 0, json_schema, MUST-NOT regexes) →
embed `facet_phrases` as `input_type="query"` → mean-center against the corpus mean →
`S = matrix @ Q_c.T` → **max-pool across facet phrases** → **accumulate** phrase weights over each
chunk's tag rows → additive `+1.0` product-literal boost → stable argsort → cap.

Index: 13,776 unique phrases × 2,048 dims, 22,235 tag emissions over 5,377 chunks, load 3.3 s.
The interpreter's full system prompt, JSON schema, and MUST-NOT regex are reproduced verbatim in
doc #18 §7.5 — including `answer_shape ∈ {content, aggregate}`, which is emitted, logged, and then
ignored.

#### The pass-1 result (**[AGENT-ASSERTED]**, gold-100, k=10, retrieval-only)

| metric | artefact (n=99) | lucene | vector |
|---|---:|---:|---:|
| `context_recall_id` | **0.199** | 0.035 | 0.045 |
| `context_precision_id` | 0.068 | 0.102 | 0.148 |
| `context_precision_nonllm` | 0.116 | 0.285 | 0.448 |
| `context_recall_nonllm` | 0.023 | 0.041 | 0.050 |

The trio's own headline was *"~4–5× the gold-citation recall … the mechanism works."* Three days
later the user overturned that reading (below).

**Eight deferred pieces, each with a design and an open sign-off question** (doc #16 §3): the
aggregation path, categorical tag-attributes, centrality, the fuzzy-embedding pre-pass, the
per-facet-axis split, chunk attribute extraction, geometry-transform refinements, the Neo4j build.
**[AGENT-ASSERTED]**; none of the eight is recorded as built anywhere in this corpus.

---

### 2026-07-01 — pass 2: dials, the curve, and the relationships pivot

Written by a **parallel session** that produced the 06-27 research catalog and then designed pass 2
without knowing pass 1 had been built and run.

§3, **all [USER-STATED]**:

> **Facets are dials, not labels:** *"you HAVE to remember that the facets are themed RELEVANCE weights.. meaning you have to think about them differently, like info-kind and entity-type (are they even facets..?)"* — a thing that answers "which" is not a facet.

> **The original multi-step relevance concept:** *"the concept was that the tag-facets were to inform the RELEVANCE of the TAG, according to that facet, in relation to it's chunk, and via the chunk's relevance to the file, get an actual file-relevance too, but skipping the 'to file' part … still the concept of the facets a multi-step relevance weight."* And: *"the facet weight in COMBINATION with the tag's 'chunk relevance weight' would tell how relevant the tag actually is in relation to the prompt based on the interpreters evaluation of which facets are most relevant for the input."*

> **The pre-v1 instinct never tried:** *"the first thought was to use clustering based on the facets as a 'filter/router' amongst the tags"* … *"that was before i started building v1."*

> **PASS-1 CONDEMNED:** *"the precision was absolutely fucking terrible, having built a 'more effective but way fucking worse' arm is not a good reference."* The user intended to delete the gold-100 run outputs.

> **Novelty demanded:** *"stockholm syndrome trap … i want NEW takes on it"* — no relabels of the v1 combinator.

> **Fuzzy means embedded:** *"i mean by fuzzy i actually mean embedded … if it's a fucking 'perfect match' it's still a perfect match.. and the closer the better.. and if people spell so fucking wrong it's just the wrong product.. we kinda can't 'fix' that this easily.. right?"*

> **The exponential curve:** *"cant we just do the evaluation-curve for the ranking of those 'exponential', we dont have to decide the actual angle now, but kinda meaning 'exact = max' on that curve, ish..?"* — shape decided, angle deliberately open.

> **THE RELATIONSHIPS PIVOT:** *"yeah i really think this should be nodes or edges so to speak etc, half the strength of of a graph is beeing able to route/search based on relationships instead of structures."* And the generalization: *"having it as a rule to make nodes out of shared fields between files/areas etc.. Isn't that a generally useful concept? Dont think herb, think dataset agnostic concept."*

> **Attribute-rule correction:** *"Wait, only shared fields are attributes now? That's retarded.."* → the four-case rule (dates always attributes; id-spaces always attributes; generic short scalars by repetition ratio; long text stays referenced content).

> **The abstract is the north star:** *"I wanted to discuss how to actually continue building the artefact in a creative innovative way that actually kinda fits my original concept (even if just in spirit), and by NOT overfitting it to the specific dataset we have."*

> **Build-to-smoke-test:** *"we have the actual option here, to test ALL non-llm-judge ways here, meaning, we could probably finish the artefact/scaffold so we could smoketest it with all our implementations."*

> **No LLM judge at build time:** *"i really do NOT want an llm judge involved in the creation of them in the graph atleast"*. (The doc flags honestly: encoder-only discriminative models are a middle tier **the user has NOT ruled on**.)

**The pass-2 plan, in commitment order** (§5) — **[AGENT-ASSERTED]** synthesis of user decisions:
(1) flat `cosine → accumulate` becomes `cosine → exponential curve → accumulate`, with exact
literal matches entering the *same* curve at max (replacing the discrete +1.0 boost); (2) per-facet
channels kept separate up the line so a chunk carries a facet-relevance profile; (3) the dial set
(process/activity + centrality safe, a collapsed "concreteness" dial the candidate third);
(4) the relationships pivot; (5) DIFFUSE-FACET gated on (1)+(2) failing; (6) a generalization guard
— read facets from the tag *resolved in its segment*, never prune the design to what survives HERB.

**The named falsifiers, both cheap, neither run** — §7, **[AGENT-ASSERTED]**:

> "**Per-dial divergence** — the cheap falsifier is ~a handful of prompts, per-dial rewrites embedded, checking the retrieved tag sets diverge from each other and from the plain prompt."
> "**DIFFUSE-FACET** … go/no-go test: a Kendall-tau check that a process-heavy vs specificity-heavy channel blend actually reorders top-k. **If nothing moves, every facet design here collapses to topic retrieval — and that finding matters in itself.**"

**An unresolved conflict the doc declares openly** (§11.1): the user's 07-01 "are they even
facets?" cut versus the 06-28 trio's categorical-facet framing. Entity-type and information-kind
were recovered into the facet layer on 06-25 and cut back out of it on 07-01 — the formal
reconciliation is listed as open and never closes in this corpus.

---

### 2026-07-12 — the state of things, and the artefact_v1 audit

§3, **[USER-STATED — paraphrase]** (this doc quotes nothing):

> - Facets are graded relevance **dials**, not categorical labels. Entity type and information kind belong to structure or the interpreter.
> - **Pass 1's recall result is not a quality reference:** its precision is unacceptable. *"Do not market its 0.199 ID-recall number as a positive outcome."*
> - Pass 2 is curve first, then per-dial channels; the angle remains a sweep parameter.
> - Fuzzy means embedding closeness; edit-distance is rejected because of the near-twins.
> - No generative LLM creates graph facet values at build time.
> - **Design before build remains binding for pass-2 pipeline work.**
> - **`herb-eval` is a prior-design contrast/forensic graph; native v3 uses `herb-v3` when materialized.**

**What `artefact_v1` is** — §4, **[AGENT-ASSERTED]**:

> "a fourth, legacy contrast arm over a pre-existing `herb-eval` Neo4j graph. It gates candidates, asks Qwen for numeric five-facet scores, grounds tags through `tag_emb`, multiplies tag/facet/chunk/description weights, resolves pointers into raw HERB, and sends the resulting chunk text to the shared generator."

and why it stays forensic:

> "The old design applies model-derived hard gates … before ranking. It also asks the model for numeric facet scores. **Both are intentionally incompatible with current pass-2 canon; this is why v1 stays forensic.**"

**The budget mismatch, measured on 07-12** — **[AGENT-ASSERTED]**:

| run | mean retrieved chars | mean context IDs | mean generator tokens |
|---|---:|---:|---:|
| artefact_v1 k=50 | 167,785 | 309.7 | 59,152 |
| lucene k=50 | 59,130 | 50.0 | 11,249 |
| vector k=50 | 23,233 | 50.0 | 5,305 |

> "Therefore the v1 recall signal is real for the saved output but **is not evidence of a fair win.** It receives about 2.8 times Lucene's and 7.2 times vector's mean character budget … **A budget-matched rerun is required before using it comparatively.**"

This is the same finding the 2026-07-28 audit panel later reached (`MEMORY.md`: *"headline
0.64-vs-0.09 is ~85% unit artifact"*). It was on the record on 2026-07-12, sixteen days earlier.

**Pass-2 status:** *"Pass-2 pipeline code has not been built. Its open sign-off items are the dial
set, curve placement/normalization/steepness, per-dial divergence test, and relationship-layer
scope. Aggregation remains structurally unimplemented."* — **[AGENT-ASSERTED]**

---

## 3. Direct user quotes recovered — verbatim, by date

Every quote below appears verbatim inside a source document. This period predates the surviving
transcript record, so for most of these the desktop docs are the only trace.

### Design — the artefact, facets, weights, the graph

| Date | Quote | Source |
|---|---|---|
| 05-25 | *"but the point of the multifacets was to give the tag a more semantical weight and direction with the facets, how are the facets used now?"* | middle-layer-weight-redesign §Suggested next-session approach |
| 05-25 | *"specifically multiplication i am not sold on"* | middle-layer-weight-redesign §Open product decisions 1 |
| 05-25 | *"yeah it's high, because I chose it"* (the model's weighting behaviour) | middle-layer-weight-redesign §Facets |
| 06-09 | *"Measure from embeddings (IF POSSIBLE) is way better than more prompting."* / *"measure from embeddings was my idea."* | 06-09 §3 |
| 06-09 | *"might as well keep the description and embedding of it i guess, we can discuss the compute/cost that choice is worth."* | 06-09 §3 |
| 06-09 | *"ONLY THAT TAG… no other relationship in this void"* (a tag embedding) | 06-09 §3 |
| 06-09 | *"weren't we supposed to have ALL the facet weights on the SAME edge!?"* | 06-09 §3 |
| 06-09 | *"why the actual fuck would you want or need a separate edge for each facet?"* | 06-09 §3 |
| 06-09 | *"perhaps we get less tags like this?"* | 06-09 §3 |
| 06-11 | *"it took so fucking long to get it right and it still didn't work at all"* (v1 weights) | 06-11 §3 |
| 06-11 | *"what if we don't do the word, and just have the embedded 'small concept' as the node"* | 06-11 §3 |
| 06-11 | *"Since the collective tags from a chunk should BE the content of the chunk, why do both?"* | 06-11 §3 |
| 06-11 | *"compare each phrase to its siblings"* | 06-11 §3 |
| 06-11 | *"perhaps we can do that, but based on each facet! giving a relational value of the tag to its siblings based on each facet!?"* | 06-11 §3 |
| 06-11 | *"the weight of the tag is ON the tag, because that is the phrase's concept being valued, and the 'in relation to the siblings' weight is on the edge."* | 06-11 §3 |
| 06-11 | *"stance is not a magical facet, ALL facets are evaluations."* | 06-11 §3 |
| 06-11 | *"i think we have to have unique ways of doing it for each facet"* | 06-11 §3 |
| 06-11 | *"you are with me that a fit-by-facet is a logical thing that actually gives us what we want from this?"* | 06-11 §3 |
| 06-11 | *"cluster or weight-adjust, aka narrowing or focusing the actual search-area of the corpus for the routing"* | 06-11 §3 |
| 06-11 | *"if the prompt is heavy in a facet, those facets are 'worth more' for the prompt/route."* | 06-11 §3 |
| 06-11 | *"things you can extract from language, the things that actually 'mean' something"* (facets) | 06-11 §3 |
| 06-11 | *"for the interpreter, it's helping it interpret the prompt, and picking it apart for tools, routes etc."* | 06-11 §3 |
| 06-11 | *"we don't keep shoveling around bad, useless or legacy code building dependencies on old stuff"* | 06-11 §3 |
| 06-11 | *"perhaps we even cut away the entire front-end... it just confuses agents"* | 06-11 §3 |
| 06-11 | *"we just don't fucking include the eval part in the dataset, why is this an issue even"* | 06-11 §3 |
| 06-11 | *"can an AI agent help with this?"* (drafting the mapping key) | 06-11 §3 |
| 06-12 | *"if we are saying file -> chunk ->tags .. where are those OTHER RANDOM FUCKING NODES!?"* | 06-12 §3 |
| 06-12 | *"either they are nodes, but then we get edges to EVERY fucking chunk, or they are just attributes… perhaps it's smarter to just have shit like that as attributes on chunks."* | 06-12 §3 |
| 06-12 | *"that sounds a bit fucked up to have them as nodes, most of them will be a chunk, meaning we have 2 almost same nodes."* | 06-12 §3 |
| 06-12 | *"that has the potential to put a fuckton of data into the graph, both GDPR data, and not. why not just have the parent field as the connection and when searched for, you can find anna."* | 06-12 §3 |
| 06-12 | *"it's dead, such shit is 'interpreter area'"* (facet-label hub nodes) | 06-12 §3 |
| 06-12 | *"yes, but still, we dont have to do that now."* (the excluded-literal flag) | 06-12 §3 |
| 06-12 | *"this must be based on the structure of the final leaf/branch data-form… different ways of handling fields based on the type of data in them."* / *"honestly not sure about that specific solution.. but yeah.. ish"* | 06-12 §3 |
| 06-12 | *"thinking humans write correctly, is naive as fuck, ESPECIALLY when talking to an llm."* | 06-12 §3 |
| 06-12 | *"exact + fuzzy IS the way to go for herb"* | 06-12 §3 |
| 06-12 | *"i am honestly not sure we want to give it the vocabulary, remember, every extra context costs money."* | 06-12 §3 |
| 06-12 | *"didnt we have a discussion about the relational chunks->subchunks file hierarchy such as 1.1.2…?"* | 06-12 §3 |
| 06-12 | *"a does seem to fit the best"* (multi-hit = boosts only) | 06-12 §6 |
| 06-12 | *"do the herb questions take this into account? …or are they only 'perfect questions'?"* | 06-12 §8 |
| 06-14 | *"relevance weights, not interpretation."* (what facets give) | 06-14 §3 |
| 06-25 | *"I think we should separate tag facets and routing."* | 06-25 tag-facets-vs-routing §3 |
| 06-25 | *"I more get the feel that those 5 in v2 are almost only viable for the interpreter. While the v1 facets were actual semantic meaning around the tag."* | same |
| 06-25 | *"We have literally removed ALL semantics and just replaced large chunks of text with short descriptions."* | same |
| 06-25 | *"we only have a few short phrases now instead of a fuckton of tags with facets … I still think we need another semantic layer here, like the facets on the phrases. Would not the old facets work with the new tags? (not the weighting, the concept)."* | same |
| 06-25 | *"the facets then use the entire tag-korpus as base for the evaluation of each facet on them, so their facet-value is relational to the korpus/facet."* | same |
| 06-25 | *"not nodes … because that mean edges right, and those are heavy in all aspects"* | same |
| 06-25 | *"Topic is not for facets tbh, how does it even fit there? Perhaps how much of the topic the tag is about? Or perhaps this is relative to all tags in the same chunk."* | same |
| 06-25 | *"the point of the multifacets was to give the tag a more semantical WEIGHT AND DIRECTION"* | guide-link §3 |
| 06-25 | *"the agents assigning facets was pretty much impossible to get different values from, they just did 'yeah, its high, because I chose it'"* | guide-link §3 |
| 06-25 | *"'one edge per facet' was just bad communication... they were supposed to be on the same fucking edge"* | guide-link §3 |
| 06-25 | *"it feels retarded to put facets on chunks, we are routing by tags, why the fuck put the facets AFTER that?"* | guide-link §3 |
| 06-25 | *"What you think is v2 tags is in essence everything moved to hard fields or put on the interpreter"* | guide-link §3 |
| 06-25 | *"Temporal was never about dates"* | guide-link §3 |
| 06-25 | *"is it the 'design this from the retrieval side' that has been fucking you up so bad?"* | guide-link §3 |
| 06-28 | *"allright, since i am a cunning cunt, my design here is a combination of these fuzzy things, embeddings AND fuzzy-lexical hard fields that also guides … combinations of solutions are the trick in my humble opinion"* | design-evolution [t14] |
| 06-28 | *"well, i separate the 'facets' the interpreter use, and the actual real contextual/semantical facets the graph has in it"* | [t18] |
| 06-28 | *"ok, if we think on it from the side of the interpreter, a prompt comes in, before i say anything here, tell me what you think we do from then, to the retrieved content"* | [t21] |
| 06-28 | *"first, i think there might be some value to do embeddings for the deterministic pre-pass, and just let it be 'fuzzy', unless exact, i guess.. but use it as a weight instead, aka area ranking or something like that, giving us a few dimensions of ranking on this route, how about that Thought? also, how does this full solution actual handle 'multi-hop' questions? i am unsure about this"* | [t24] |
| 06-28 | *"quite alot of multihop, check the HERB documentation instead of asking me"* | [t27] |
| 06-28 | *"but, doesnt the graph give actual relational connections to things like this, i mean, if the 'name' example you had, why wouldnt if just find all of those names? i dont get it"* | [t33] |
| 06-28 | *"ok, so, lets go back to the 'tag facets' now that we have discussed the around things a bit.. or however it should be solved, that weighting or relational values or connections etc"* | [t36] |
| 06-28 | *"uniform vector? what?"* | [t39] |
| 06-28 | *"ah, yeah, i agree, not all facets should be graded in the same way"* | [t42] |
| 06-28 | *"fetch the orignal v2 facets"* | [t45] |
| 06-28 | *"i mean, i really do like the concept of clustering tags/weights on facets based on the prompts values"* | [t49] |
| 06-28 | *"honestly, an optimal solution would to NOT have all of this in the graph, intead do it live-prompt-time, because of the size it's becoming, BUT, embeddings, values, pointers etc, might be ok"* | [t52] |
| 06-28 | *"i mean, it wont cost us anything to try this so we might as well just build it, right?"* | [t55] |
| 06-28 | *"wtf is this? 'HNSW (or FAISS)'"* | [t59] |
| 06-28 | *"do we do a knn = number of facets then over the tag corpus?"* | [t62] |
| 06-28 | *"ok, so you think its better to use it as ranking straight up rather than fuzzy cluster -> ranking?"* | [t65] |
| 06-28 | *"just some thoughts btw, thinking about the actual size of the graph here, is there a reason to have the phrases in there? shouldnt we just embed them and put the embedding as a node in the graph instead with the reference just like the phrase would have?"* | [t68] |
| 06-28 | *"i agree, what is left to do and build now then? start embedding the phrases and build the graph?"* | [t71] |
| 06-28 | *"embedder is nemo, graph, do both, just do the db for my sake also, i like the visual representation of it and i want to see the size, else, yeah, can do it as a structure only, but, remember it's graph-shaped"* | [t81] |
| 06-28 | *"fs,. i just said it's NEMOTRON FFS!"* | [t82] |
| 06-28 | *"eh.. what happened with all the other phrases then?"* | [t96] |
| 06-28 | *"cool.. i think.."* | [t99] |
| 07-01 | *"you HAVE to remember that the facets are themed RELEVANCE weights.. meaning you have to think about them differently, like info-kind and entity-type (are they even facets..?)"* | 07-01 §3 |
| 07-01 | *"the concept was that the tag-facets were to inform the RELEVANCE of the TAG, according to that facet, in relation to it's chunk, and via the chunk's relevance to the file, get an actual file-relevance too, but skipping the 'to file' part … still the concept of the facets a multi-step relevance weight."* | 07-01 §3 |
| 07-01 | *"the facet weight in COMBINATION with the tag's 'chunk relevance weight' would tell how relevant the tag actually is in relation to the prompt based on the interpreters evaluation of which facets are most relevant for the input."* | 07-01 §3 |
| 07-01 | *"apparently it didnt work great, so this is not the same creation anymore … what we are exploring here, is perhaps other ways of doing this"* | 07-01 §3 |
| 07-01 | *"the first thought was to use clustering based on the facets as a 'filter/router' amongst the tags"* … *"that was before i started building v1."* | 07-01 §3 |
| 07-01 | *"i mean by fuzzy i actually mean embedded … if it's a fucking 'perfect match' it's still a perfect match.. and the closer the better.. and if people spell so fucking wrong it's just the wrong product.. we kinda can't 'fix' that this easily.. right?"* | 07-01 §3 |
| 07-01 | *"cant we just do the evaluation-curve for the ranking of those 'exponential', we dont have to decide the actual angle now, but kinda meaning 'exact = max' on that curve, ish..?"* | 07-01 §3 |
| 07-01 | *"yeah i really think this should be nodes or edges so to speak etc, half the strength of of a graph is beeing able to route/search based on relationships instead of structures."* | 07-01 §3 |
| 07-01 | *"having it as a rule to make nodes out of shared fields between files/areas etc.. Isn't that a generally useful concept? Dont think herb, think dataset agnostic concept."* | 07-01 §3 |
| 07-01 | *"Wait, only shared fields are attributes now? That's retarded.."* | 07-01 §3 |
| 07-01 | *"i really do NOT want an llm judge involved in the creation of them in the graph atleast"* | 07-01 §3 |
| 06-28 | *"combinations of solutions are the trick."* · *"lean graph, live facets."* · *"Nemotron."* · *"it's graph-shaped."* | lean-graph-build §3 |

### Evaluation, scope, and the thesis

| Date | Quote | Source |
|---|---|---|
| 06-14 | *"drop the fucking thesis... it's done, this is post-thesis work."* | 06-14 §3 |
| 06-14 | *"DONT INCLUDE THE FUCKING EVAL FILES FOR THE PROBE TO EVER SENSE."* | 06-14 §3 |
| 06-14 | *"pre-make 1 training-set and then do the eval on the 'original'."* | 06-14 §3 |
| 06-14 | *"the Bonnier set will have to wait until some other time."* | 06-14 §3 |
| 06-14 | *"do not touch A:\exjobbet\data\raw at all, that is the storage, the one in the repo can be worked with."* | 06-14 §3 |
| 06-14 | *"two repos in the same repo"* (the v1/v2 split, nothing deleted) | 06-14 §3 |
| 06-14 | *"i never saw the fucking schema"* (rejecting the contracts doc as an approval) | 06-14 §9 |
| 06-18 | *"no, i am saying we do both."* (HERB scorer **and** RAGAS) | 06-18 §3 |
| 06-18 | *"YOU do not care about cost here, 0 fucks given… only for me. so fucking drop that fast as fuck."* | 06-18 §3 |
| 06-25 | *"this is ONLY RAGAS"* (said twice, emphatically — the HERB scorer purge) | eval-ops §3 |
| 06-25 | *"MY WORDS ARE THE CANON"* | eval-ops §3 |
| 06-25 | *"those 4 + the free ones"* / *"3 we used in the thesis + the dropped one"* | eval-ops §3 |
| 06-25 | *"the dumbest fucking shit"* (the pre-run y/N prompt) | eval-ops §6 |
| 07-01 | *"I wanted to discuss how to actually continue building the artefact in a creative innovative way that actually kinda fits my original concept (even if just in spirit), and by NOT overfitting it to the specific dataset we have."* | 07-01 §3 |
| 07-01 | *"we have the actual option here, to test ALL non-llm-judge ways here, meaning, we could probably finish the artefact/scaffold so we could smoketest it with all our implementations."* | 07-01 §3 |
| 07-01 | *"the precision was absolutely fucking terrible, having built a 'more effective but way fucking worse' arm is not a good reference."* | 07-01 §3 |
| 07-01 | *"stockholm syndrome trap … i want NEW takes on it"* | 07-01 §3 |
| 07-01 | *"create a clean document … DO INCLUDE all references!"* | 07-01 §6 |

### Working method and communication

| Date | Quote | Source |
|---|---|---|
| 05-25 | *"fuck the instinct, talk about reality"* | audit §TL;DR |
| 05-25 | *"wow, there is literally so fucking much for me to respond to here i kinda cant even"* | audit §User communication style |
| 05-25 | *"DONT start thinking about the report, focus on the actual build."* | retrieval-redesign §User communication style |
| 05-25 | *"alright, good shit"* | audit §Last user message |
| 05-31 | *"you have created something fucked up here"* (memory files written as "decided") | 05-31 §User working style |
| 06-04 | *"you fucking run off and do your own thing"* | 06-04 §Read first |
| 06-04 | *"dont just agree, i was asking."* | 06-04 §Read first |
| 06-09 | *"do NOT repeat shit"* / *"why the fuck did you just REPEAT THAT SHIT"* | 06-09 §3 |
| 06-09 | *"does it look like im here to have a conversation with my fucking history?"* | 06-09 §3 |
| 06-09 | *"you searched online for that specific solution… instead of actually doing real research"* | 06-09 §3 |
| 06-11 | *"that means we fucking have to make sure all parts are decided upon first."* (the build gate) | 06-11 §3 |
| 06-11 | *"I can't read several A4 every time you answer me"* / *"just give me a short version ALSO"* | 06-11 §3 |
| 06-11 | *"honestly, none of what you are saying now is a thought I have had, where the fuck did all of this even come from."* | 06-11 §8 |
| 06-11 | *"wtf is 'fit'"* | 06-11 §8 |
| 06-11 | *"you are doing weird shit now, don't ASSUME shit, discuss, THINK, be intellectual.. right now you are just speed-parroting"* | 06-11 §8 |
| 06-11 | *"feels like you did 0 actual thought of your own here"* | 06-11 §8 |
| 06-11 | *"that.. does not seem fucking true at all"* (the tagger-design overclaim) | 06-11 §8 |
| 06-11 | *"referencing shit in the docs really gives you nothing with me"* | 06-11 §8 |
| 06-12 | *"use speech english instead of this almost 100% jargon."* | 06-12 §3 |
| 06-12 | *"that shit is still true for THAT build."* (v1 docs stay untouched) | 06-12 §3 |
| 06-12 | *"please do continously update information according to the things we decide"* / *"did you REMOVE, quarantine, legacy-note or something else"* | 06-12 §3 |
| 06-12 | *"where the fuck in the graph do you think this is?"* | 06-12 §8 |
| 06-12 | *"why the fuck and from WHERE do the random nodes and other shit come from?"* | 06-12 §8 |
| 06-12 | *"there is so much you missed here… i fucking cant keep saying this shit over and over, we loose information everytime"* | 06-12 §8 |
| 06-14 | *"driving me insane"* | 06-14 §1 |
| 06-28 | *"spin more agents if you need the help from it"* | [t86] |
| 06-28 | *"yup, keep working this until you have this built correctly"* | [t90] |
| 06-28 | *"Allright, you need to collect exactly all the information of what you built, how it was built and why, ALL of it, NOTHING can be left out, no relationship, no cause and effect, no reason and no function, nothing declared and nothing omitted can be left out, EXACTLY THE ENTIRE FUCKING BUILD."* | [t114] |
| 06-28 | *"conversations and memories also count, just because it didnt leave a conversation doesnt mean it shouldnt be saved"* | [t119] |
| 06-28 | *"make more workers do that in case it takes time"* | [t120] |

**Two continuity notes for the canon.** (1) The orchestrator/agent-delegation working mode that
`USER_CANON` dates to 07-22 has a direct precedent at 06-28 [t86]/[t120] — the user asking for more
parallel workers. (2) *"stop making fully fucking custom scripts i cant reuse"* (07-17) and the
07-15 *"i do NOT like arbitrary choices for k or any number"* both continue a line that begins
05-25 with the rejection of undefended multipliers and 06-04's *"3000 is a calibration seed, not
final."*

---

## 4. Cross-check against `git_record.md` — C-1 … C-18

Verdict vocabulary: **CONFIRMS** (independent second source agreeing), **REFUTES** (the material
contradicts the finding), **EXPLAINS** (supplies the missing decision, reason, or context that git
alone could not show), **NEITHER** (nothing bearing on it).

---

### C-1 — D10 reversed: content-in-graph → references-only — **EXPLAINS** (and confirms)

The reversal itself is confirmed: the 05-31 handoff records references-not-copies as the session's
core stance with the same charge against v1's fabricated `c.content`.

The part git could only note as odd — *"the decision log entry D10 was never updated or retracted
in place; it still reads 'Status. Active'"* — is **explained by a documented user ruling**:

> 2026-06-12 §3: **"v1 docs stay untouched:** *"that shit is still true for THAT build."* v1 documentation describes v1 as built; only v2-living docs get purged." — **[USER-STATED]**

Reinforced in §8: *"Don't touch v1 docs / historical snapshots when purging — they're true for that
build / frozen records."* D10 reading "Active" is not neglect; it is a deliberate policy that v1's
record describes v1.

---

### C-2 — v2 declared all v1 eval numbers invalid; the shipped arm is the v1 graph — **EXPLAINS**

The desktop corpus supplies the entire causal chain, and shows the contradiction did **not** exist
inside this window.

1. `artefact_v1` was introduced as a **contrast baseline**, explicitly. 07-12 §3: *"`herb-eval` is
   a prior-design contrast/forensic graph; native v3 uses `herb-v3` when materialized"*
   **[USER-STATED — paraphrase]**; §6: *"`artefact_v1` remains a contrast baseline only. Do not
   port its model-emitted numeric facets or hard gates into native v3."*
2. The **native v3 arm was built and run** (06-28, gold-100 k=10) — so the intended product did
   exist.
3. The user **condemned it** on 07-01: *"the precision was absolutely fucking terrible, having
   built a 'more effective but way fucking worse' arm is not a good reference."* **[USER-STATED]**
   The user intended to delete its outputs.
4. **Pass 2 was never built** — the design-before-build gate the user imposed on 06-11 required
   sign-off on the dial set, curve placement, per-dial divergence test, and relationship scope.
   07-12 §11 lists all four still open.
5. The native Neo4j `herb-v3` materialization **never ran** — blocked on Neo4j not running locally
   and `NEO4J_PASSWORD` unset (06-28 §5 blocker 3; 07-12: *"remains unverified in the current
   environment"*).

So: the intended arm was rejected by its own author, its replacement was gated behind sign-offs
that never came, and the forensic contrast arm was the only thing left running. **This also answers
`git_record.md` G-10** ("why the arm under test was never switched") and G-5 ("whether anything was
ever run on the v3 artefact" — yes: the in-memory index and a full gold-100 run; no: the Neo4j DB).
The contradiction is real at HEAD, but it is drift after 07-12, not a decision inside this window.

---

### C-3 — the controlled canonical vocabulary deleted with no mention — **CONFIRMS**

The corpus begins 05-25, twelve days after the 05-13 deletion, so it cannot witness the act. It
does independently confirm the end state and that the doc drift was **known**:

> 05-25 audit: *"**3 edge types only** … No `:Run`. **No `:CanonicalTag***. (Schema doc claims these exist; they don't in `herb-eval`.)"* — **[AGENT-ASSERTED]**, verified live.

The audit files this under "Doc drift … These are docs problems, not graph problems", to be fixed
*"when the cleanup work touches the affected docs"*. No user decision is recorded. The subsystem's
removal remains unexplained; only its consequence is corroborated. **Verdict: confirms; does not
explain.**

---

### C-4 — six of eight node labels and four of seven edge types disappeared — **PARTLY EXPLAINS**

Git's specific complaint was that the loss of `(:File)-[:TAGGED]->(:Tag)` and
`(:Chunk)-[:NEXT]->(:Chunk)` *"is not discussed anywhere"*.

**`:NEXT` is fully explained and the framing corrected.** The 05-25 audit shows `:NEXT` **was never
populated** and argues it unnecessary from measured data:

> *"**No `:NEXT`.** … Only `_part` kinds have order-dependent semantics (~12% of corpus). For those, `c.ordinal` carries the same info `:NEXT` would; `:NEXT` is not needed."* — **[AGENT-ASSERTED]**, verified live.

> *"All 33 files are `dispatch_mode=parallel`. The `sequential` tagging path with `_load_chunk_context` continuity hints is **dead-but-documented code** in `herb-eval`."*

Git's inference that `:NEXT` was "the sequential-continuity link that D1's dispatch-mode design
depended on" is therefore **partly refuted**: the sequential dispatch mode was never used on this
corpus, so nothing depended on it in practice. And the replacement is documented — 06-03/06-04
make the **materialized integer path** the successor to flat `ordinal` + `NEXT`, and 06-12 records
the path as *"MORE load-bearing since the path attribute is how the tree exists without branch
nodes."*

**`:TAGGED` / `weight_global` remain unexplained.** The file-level rollup is mentioned nowhere in
these twenty documents. That half of C-4 stands.

---

### C-5 — "the chunk description is dead" except in the arm that ships — **EXPLAINS** (and confirms the rule's provenance)

The rule is unambiguously the user's, with the exact words and a note that he asked twice:

> 06-11 §3: **"No chunk description.** *"Since the collective tags from a chunk should BE the content of the chunk, why do both?"* — the union of phrase tags is the chunk's semantic representation. (User asked twice; it is dead.)" — **[USER-STATED]**

The tension is explained by *which system each statement is about*. The description is dead in the
**v3 native artefact** — and `v3/artefact/tag.py` honours it. The description path that ships lives
in **`artefact_v1`**, which queries the v1 `herb-eval` graph where descriptions are a real
property of the data. 07-12 §4 describes v1 as multiplying *"tag/facet/chunk/**description**
weights"* and classifies the whole arm as *"intentionally incompatible with current pass-2 canon;
this is why v1 stays forensic."*

So the canon line and the code are not describing the same system. The genuine fault is that CLAUDE.md
states a v3-artefact rule as if it governed the arm producing the numbers — which is C-2's problem,
not a second independent one.

---

### C-6 — the condemned v1 facets returned under new names — **EXPLAINS, decisively**

This is the item git explicitly could not adjudicate: *"Whether this is a considered reversal … or
an unnoticed loop **cannot be told from git** — nothing argues it either way."*

**It is a considered, user-driven reversal, and the argument is on the record.** The 2026-06-25
guide-link doc devotes its §5 and §8 to exactly this:

> §8: *"**"entities / temporal / evidence are fact dimensions, relocate to structure"** — **WRONG about evidence and entities.** `evidence` = information-KIND (metric/argument/procedure/…), a real semantic dimension; `entities` = named-thing TYPE, semantic. The *fact* (eid, URL) is structure; the *kind/type* is meaning. **This misread is what hollowed the tag.**"*

The distinguishing principle is explicit — **fact vs kind/type**. The v1 *degradation* was
`evidence` collapsing into URLs; the v1 *definition* was "kind of information". The v2 allocation
table mistook the degradation for the definition and deleted the dimension. The user drove the
correction:

> *"What you think is v2 tags is in essence everything moved to hard fields or put on the interpreter"* — **[USER-STATED]**
> *"Would not the old facets work with the new tags? (not the weighting, the concept)."* — **[USER-STATED]**

The doc also traces the provenance failure: the memory file said *"evidence = sourcing, not links"*
while the actual v1 doc said kind-of-information, and *"the memories and `DESIGN.md`/`MODEL_CONTRACTS.md`
**MISREPRESENT** the facets — read the v1 source, not the summary."*

`centrality` is likewise argued, not renamed by accident: the user's *"Topic is not for facets
tbh… Perhaps how much of the topic the tag is about? Or perhaps this is relative to all tags in
the same chunk"* is what converts topic into chunk-local degree.

**One important addition git could not see: the loop closed again.** On 2026-07-01 the user cut
entity-type and information-kind **back out** of the facet layer — *"like info-kind and entity-type
(are they even facets..?)"* — on the ground that a facet must be a graded "how much" dial, not a
categorical "which" label. So the dimensions moved out (05-30), back in (06-25), and out again
(07-01). Each move is argued; the 07-01 doc lists the reconciliation with the 06-28 categorical
framing as **open problem §11.1**, and it never closes.

---

### C-7 — the per-facet extraction spec fully written and never built — **EXPLAINS, decisively**

Git's G-4 calls this *"the single most important unanswered question"* and records that no
document, comment, or commit bridges the spec to the flat `{"tags": [...]}` implementation. The
bridge is here, and it is four steps, all user-driven:

1. **06-14** — the tagger output schema (per-facet phrase lists) was verbally approved *and
   immediately flagged as invalid by the same document*: *"CAVEAT: this approval predates the §3
   facet breakthrough and the §8 carrier reversal — re-validate it."* This is the reopening git
   finds in `MODEL_CONTRACTS.md` §5.
2. **06-25** — the five-facet set is disowned: *"it's an assistant research synthesis … the user
   **never hard-approved the specific five**, and it hollowed the tag."* The spec's subject was
   never canon.
3. **06-28 [t42]** — *"ah, yeah, i agree, not all facets should be graded in the same way"*
   **[USER-STATED]**. A single uniform per-facet emission cannot carry three measurement natures.
4. **06-28 [t52]** — *"honestly, an optimal solution would to NOT have all of this in the graph,
   intead do it live-prompt-time, because of the size it's becoming"* **[USER-STATED]**, with
   [t49] *"i really do like the concept of clustering tags/weights on facets based on the prompts
   values"*.

The consequence is stated plainly in the design-evolution doc's cause-and-effect §4:

> "**Graded facets moved to query-time BECAUSE** doing so dissolves three open problems at once: (a) the graded instrument … (b) axis definition vs calibration … (c) the no-LLM-judge constraint — the weight is computed live (cosine), nothing emitted."

If nothing per-facet is stored, the tagger has nothing per-facet to emit — hence a flat phrase
list. The `tag.py` docstring's unargued assertion (*"facets are measured later over the finished
tag corpus"*) is the compressed residue of a fully argued decision. **G-4 is answered.**

---

### C-8 — entity decomposition specified, then reversed — **CONFIRMS, and upgrades the attribution**

Git labels this a properly documented reversal. The desktop record shows it was **the user's**
reversal, driven in conversation, with the deciding rule his own:

> *"if we are saying file -> chunk ->tags .. where are those OTHER RANDOM FUCKING NODES!?"*
> *"either they are nodes, but then we get edges to EVERY fucking chunk, or they are just attributes… perhaps it's smarter to just have shit like that as attributes on chunks."*
> *"that sounds a bit fucked up to have them as nodes, most of them will be a chunk, meaning we have 2 almost same nodes."* — all **[USER-STATED]**, 06-12 §3

It also records that the assistant kept trying to reinstate the dead draft — the three
"forcing shit into the graph" incidents — and that the 05-30 draft was named as the source of the
inertia: *"The 05-30 drafted graph model is the *source* of this inertia; it is dead; do not cite
it as design."*

---

### C-9 — DESIGN.md contradicts itself at the same commit — **PARTLY EXPLAINS**

The corpus explains the *mechanism* and shows part of the staleness was deliberate.

06-12 §9 records a full reconciliation pass, section by section, and names what was **knowingly**
left stale with the reason: *"STILL STALE knowingly: §13.5 emit-examples (bare labels; rewrite
when carriers close — its banner says so)."* The governing rule is stated in the 06-25 doc:
*"rewrite only when the tag-facet SET + axis-definition close (docs-track-reality — **no premature
rewrite of an open model**)."* Under a design-before-build gate, rewriting a section whose decision
is still open would be writing fiction. That is a defensible policy, and it explains why §13
carried stale content at every commit.

**It does not cover the two specific residues git found.** §9.5's `:COVERS` reference and §9.6's
"entities + properties" are not on any acknowledged-stale list; they are exactly the *"leave some
paint on the walls"* failure the user complained about. Those two are genuine unremoved residue.

---

### C-10 — three tagger-model decisions, the final one undocumented — **PARTLY EXPLAINS**

**Problem 1 (the Bonnier rationale was out of scope at the moment of the choice) is fully
explained** — and was noticed at the time:

> 06-14 §3: *"**Mistral is the tagger model** … NOTE: the original Mistral rationale was Swedish fidelity — **now moot under HERB-only** — so the model choice rests on "largest tier" reasoning, not Swedish."* — **[AGENT-ASSERTED]**, following the user's *"the Bonnier set will have to wait until some other time."* **[USER-STATED]**

So the collapse of the deciding axis was recorded on the day; it simply never propagated into
`DESIGN.md` §11.

**Problem 2 (why the built tagger is `z-ai/glm-5.1`) is not explained.** No document in this corpus
records the Mistral→glm-5.1 decision. The 06-28 docs treat glm-5.1 as an established fact
(*"`z-ai/glm-5.1` (same as the tagger — one model in the stack, proven on HERB)"*) and reference
`output/tags/Salesforce__HERB.stats.json` `by_model`, implying more than one model was used across
the tagging run. That gap stands.

**Problem 3 (the interpreter model divergence) is fully explained.** The glm-5.1 →
`meta/llama-3.3-70b-instruct` swap is documented as an operational response to NIM hard-throttling
glm-5.1 (every call 429'd after 6 retries). The user skipped the model-choice question at [t108];
the assistant chose. *"One line at `INTERPRETER_MODEL`; the contract is model-agnostic."* —
**[AGENT-ASSERTED]**.

---

### C-11 — six commits of measured results squashed away — **EXPLAINS the consequence**

The corpus says nothing about the squash. But it shows **the finding itself survived and shaped the
design** — which is the thing that mattered:

> 05-25 doc #1: *"`docs/backend/ragas_eval_report.md` | Current gold-100 eval results (graph slightly below Lucene baseline on context_recall; faithfulness ~tied)"*

> 06-18 §9: *"v1 RAGAS eval … Key result: faithfulness flat (0.81 vs 0.80), context_recall graph LOWER (0.86 vs 1.00, **bag-size biased**), context_precision ~0 both (**degenerate**); the real signal was deterministic eid token-F1."*

That reading is the stated reason the v3 harness adopted deterministic citation-based context
metrics over the judged variants (06-18 §6.2). The negative comparative result was not lost with
the squash; it was absorbed and acted on. The squash cost the commit-message record, not the
knowledge.

---

### C-12 — the "seven factors" claim is correct — **CONFIRMS**

Independently corroborated by a contemporaneous second source. The 05-25 handoffs, written against
the running code, name the same seven and list which to remove:

> doc #1: *"The 7-factor multiplicative synthesis in the current `frontend/src/services/retrieval.ts` `scoreCypher` is the explicit violation of this design."*
> doc #3: *"Drop the multiplicative 7-factor `edgeWeight`. Drop `qt.w_query`, `qt.sim` (as a score factor — keep as filter/grounding bridge), `qt.scopeWeight`."*

Git's resolution (five at design time, seven as shipped, the two extras being `qt.sim` and
`qt.scopeWeight`) is confirmed exactly. G-7's residual — *why* `scopeWeight` was introduced —
remains unanswered here too.

---

### C-13 — "the model emits no numbers, ever" vs the arm that ships — **EXPLAINS**

The rule's provenance is settled: it is the user's, stated in his own words with his own evidence:

> 06-11 §3: *"**The model emits NO numbers, ever** — tagger and interpreter both. v1 evidence: *"it took so fucking long to get it right and it still didn't work at all."*"* — **[USER-STATED]**

And the violation is explained as deliberate quarantine, not oversight:

> 07-12 §5: *"The old design applies model-derived hard gates … **It also asks the model for numeric facet scores.** Both are **intentionally incompatible with current pass-2 canon; this is why v1 stays forensic.**"* — **[AGENT-ASSERTED]**, aligned with the user's contrast-baseline ruling.

The numeric-facet-scoring code is v1 code, kept precisely *because* it violates the rule and
therefore serves as the before-picture. The contradiction at HEAD is the C-2 drift — the forensic
arm becoming the reported system — surfacing again on a second canon line.

---

### C-14 — canon describes a build state that no longer exists — **CONFIRMS, and dates it**

The desktop record **refutes the CLAUDE.md claim** and therefore confirms the contradiction, with
a precise date. As of 2026-06-28, `chunk.py`, `tag.py`, `embed_tags.py`, `index.py`, `prepass.py`,
`interpreter.py`, `graph_store.py`, and `pipelines/artefact.py` all existed, 36 tests passed, and a
full gold-100 retrieval run had been executed. The stale line was **identified as needing repair on
that very day**:

> design-evolution §5: *"`v3-artefact-subsystem.md` — **NEEDS UPDATING.** The graph is now built (was the unbuilt part); `pipelines/artefact.py` is now implemented (was a stub); 36 tests pass (was 16). The "graph (chunk→tag→retrieve) is the unbuilt part" line is stale."*

So the canon went stale on 2026-06-28, the staleness was logged the same day in the memory audit,
and the fix was never applied. Only the **facet** layer was genuinely unbuilt — exactly as git
concluded.

---

### C-15 — two constants no artifact derives — **CONFIRMS, and adds the missing measurements**

Confirms, and supplies empirical consequences git had no access to:

- **α = 0.25 / `coverage_bonus`.** The formula is preserved verbatim (06-09 §4). Its measured
  effect is in the 05-25 audit: *"**Rewards multi-facet coverage** (cross-tab shows mean w_chunk is
  *lower* on `w_facet=1.0` edges than on `0.7-0.8` edges — because single-facet hits get penalized
  by coverage_bonus)."* — **[AGENT-ASSERTED]**, measured. The constant was never swept, but its
  direction was checked against the live graph, and it does something counterintuitive.
- **`MULTI_FACET_THRESHOLD = 0.50`.** Its consequence is quantified: *"85% of the 25,896 unique tag
  names are multi-facet"*, and the "42 tags per chunk" figure is **42 edges**, facet-multiplied by
  this threshold — *"Distinct concepts per chunk ≈ low-20s."* (06-09 §4.) The 06-25 doc adds that
  this same 0.50/85% pattern is the evidence for the **orthogonality risk** that threatens the
  whole facet layer.
- **`CAP_TOKENS = 3000`.** The sweep's non-execution is a **documented deferral, not an
  oversight** — 06-04: *"the only thing left on the chunking design, and it's *implementation-time*
  … can run only once the v2 tagger + chunks exist. **Not actionable yet.**"* Once the tagger and
  chunks did exist (06-28), the sweep still did not appear on any of the eight deferred-piece
  lists.

---

### C-16 — "no hard filters" written against a v1 full of them — **CONFIRMS, and upgrades the attribution**

Git calls this a justified reversal. The corpus shows it is a **user stance**, recorded as such
before any v2 code existed:

> 05-31 §"Retriever design": *"**NO hard filters anywhere** (strong user stance) — "mandatory" = weight concentration; the **cap** does the cutting on rank."* — **[USER-STATED — paraphrase]**

Corroborated by the 05-25 handoffs, which independently identify the v1 gates (`minWChunk`,
`minRelevanceToFile`, `activeFacets`) as removal targets, and by 06-12's multi-hit ruling (*"a does
seem to fit the best"* — boosts only, never removal). The 06-28 build carries the principle down to
implementation detail: the product-literal boost is additive `+1.0` specifically because *"a
multiplicative boost on a zero semantic score would be a hard filter in disguise."*

---

### C-17 — the leaderboard-comparable anchor metric specced, stubbed, deleted — **EXPLAINS, decisively**

Git: *"No commit message, doc, or comment anywhere in git gives a reason for the removal."* The
reason is a direct, emphatic, twice-repeated user instruction, and the corpus captures both ends of
the decision:

**The anchor's origin, 06-18 §3:**
> *"**Do BOTH scorers** (HERB + RAGAS), not either/or. (User: *"no, i am saying we do both."*)"* — **[USER-STATED]**

**Its cancellation, 06-25 §3:**
> *"**SCORING IS RAGAS ONLY. There is NO HERB scorer.** The user said this twice, emphatically (*"this is ONLY RAGAS"*). The old "HERB + RAGAS / two-way scoring / HERB anchor" framing is **dead** — purged this session. `eval/herb.py` was **deleted**."* — **[USER-STATED]**

§6 records the mechanics: `eval/herb.py` deleted, and CLAUDE.md, README.md, `v3/README.md`,
`ragas_catalog.py`, and an orchestrator docstring all cleaned (with a note that the first grep pass
missed two `v3/README.md` lines). §8 makes reintroduction a named trap: *"**Reintroducing the HERB
scorer** from stale docs — RAGAS ONLY."*

**The deletion buried in `feat: update graphify-out (533 files)` was a user decision, not a silent
drop.** Git's downstream consequence still holds exactly as stated: every number the project
reports is RAGAS-only and none is comparable to HERB's published leaderboard. The desktop record
changes the attribution, not the consequence — and shows no document anywhere weighs that
consequence against the decision.

---

### C-18 — design-bearing changes hidden under tooling commit messages — **NEITHER (but explains the mechanism)**

No document discusses commit hygiene. The corpus does explain how the pattern arose: it repeatedly
records long uncommitted stretches — 06-11 *"NOTHING COMMITTED"*; 06-12 *"NOTHING COMMITTED this
session"*; 06-14 *"Repo split into `v1`/`v2` via `git mv` (nothing deleted, **not committed**)"* —
so bulk auto-generated commits were sweeping up weeks of accumulated work at once. The corpus also
supplies the missing *content* of the worst offenders: `8a640bf`'s `tag.py` and the 659-line
research catalog are documented in full by the 06-27/06-28 material, and `69115e0`'s
`artefact_v1.py` by the 07-12 review.

---

### Summary table

| # | Verdict | One line |
|---|---|---|
| C-1 | **EXPLAINS** | D10 still reads "Active" because the user ruled v1 docs frozen — *"that shit is still true for THAT build."* |
| C-2 | **EXPLAINS** | v1 was a declared forensic contrast; the native arm was built, condemned by the user on 07-01, pass 2 gated on sign-offs that never came, `herb-v3` never materialized. Answers G-5 and G-10. |
| C-3 | **CONFIRMS** | End state corroborated live on 05-25 and the doc drift flagged; no user decision found. Genuine silent drop. |
| C-4 | **PARTLY EXPLAINS** | `:NEXT` was never populated, argued unnecessary from data, and replaced by the materialized path. `:TAGGED`/`weight_global` still unexplained. |
| C-5 | **EXPLAINS** | The rule is the user's, verbatim; the surviving description path belongs to the v1 forensic graph, not the v3 artefact. |
| C-6 | **EXPLAINS** | A deliberate, user-driven reversal on an argued fact-vs-kind distinction — "the hollowing". And it reversed again on 07-01 (dials, not labels), still unreconciled. |
| C-7 | **EXPLAINS** | Four documented steps from spec to flat list, ending in the user's [t52] "lean graph, live facets". Answers G-4. |
| C-8 | **CONFIRMS** | Reversal upgraded from "documented" to **[USER-STATED]**, with the node/attribute rule shown to be the user's. |
| C-9 | **PARTLY EXPLAINS** | Most staleness was a deliberate no-premature-rewrite policy; §9.5 `:COVERS` and §9.6 entity residue are genuinely unremoved. |
| C-10 | **PARTLY EXPLAINS** | The Bonnier-rationale collapse was noticed on 06-14 and never propagated; the interpreter swap is fully documented; the glm-5.1 tagger choice is still undocumented. |
| C-11 | **EXPLAINS the consequence** | The negative finding survived into the eval design and is why v3 uses deterministic ID-based context metrics. |
| C-12 | **CONFIRMS** | Independent contemporaneous source names the same seven factors and the two extras. |
| C-13 | **EXPLAINS** | The no-numbers rule is the user's verbatim; the numeric-facet arm is v1, kept *because* it violates canon. |
| C-14 | **CONFIRMS** | Refutes the canon line outright and dates its staleness to 2026-06-28, when it was logged as needing repair. |
| C-15 | **CONFIRMS** | Adds measured consequences for α and 0.50, and shows the 3000-token sweep was an explicit deferral. |
| C-16 | **CONFIRMS** | "No hard filters" recorded as a strong user stance on 05-31, before any v2 code. |
| C-17 | **EXPLAINS** | *"this is ONLY RAGAS"* — said twice, emphatically. A user decision, not a silent drop. The consequence still stands. |
| C-18 | **NEITHER** | No commit-hygiene discussion; the long-uncommitted working pattern explains the mechanism. |

---

## 5. Specified in this period, never built — and not already in the git contradiction list

Ordered by consequence. Every item is traced to whoever specified it.

### 5.1 The aggregation path — 30+ of the 100 gold questions are structurally unanswerable

**[USER-STATED]** origin ([t33]: *"doesnt the graph give actual relational connections to things
like this … why wouldnt it just find all of those names? i dont get it"*), designed in full detail
across 06-28 §3.1 and 07-01 §11.7, never built.

The interpreter classifies each prompt `answer_shape ∈ {content, aggregate}`; **30+ of gold-100
come back `aggregate`**; the code then *logs it and returns top-k chunks anyway*
(`pipelines/artefact.py`). The designed path was: structural scope → semantic filter → **full
recall, no cap** → group-by chunk attribute → count/max → directory-join to resolve the answer.

Its absence is measurable in the corpus's own tables: `exact_match` is **0.000 across all three
arms**, and `bleu`/`rouge`/`string_presence` are near-zero. 06-28 §3.1 calls it *"the **biggest
design gap** in pass 1"* and — critically for the project's whole claim —

> *"This is where the artefact's relational-graph advantage over flat-vector retrieval shows clearest: **the graph HAS the connections** … that a vector arm structurally cannot compose; the query-engine path that composes them doesn't exist yet."*

The one capability that would differentiate a graph from a vector store was designed, scoped,
sketched to pseudocode, and never written.

### 5.2 The relationships / hub-node pivot — the user's "use the graph as a graph" requirement

**[USER-STATED]**, 07-01, and stated as a *general* rule rather than a HERB fix:

> *"yeah i really think this should be nodes or edges so to speak etc, half the strength of of a graph is beeing able to route/search based on relationships instead of structures."*
> *"having it as a rule to make nodes out of shared fields between files/areas etc.. Isn't that a generally useful concept? Dont think herb, think dataset agnostic concept."*

The design was worked out: traversable containment + adjacency edges derived from the materialized
path already stored; hub nodes for mid-selectivity shared scalars and id-space fields; two
disciplines (reference-never-copy; weighted-and-steep so a hit never floods a file); and the HERB
landmine named (never wire the stripped `team`/`customers` as edges). It is listed as needing
sign-off (07-01 §11.5) and is absent from the 07-12 review's built inventory.

**This is the direct antecedent of the user's most-repeated later complaint.** `USER_CANON` records
07-20 *"the real question i have now tho, is wether the graph is actually built in a way that makes
use of the actual qualities of a graph"*; 07-28 *"are we underutilizing the fact that all of this
is built in a graph format?"*; 07-29 *"to see if we can build the graph smarter, aka use the actual
grapjh shape in a better way"*. He was asking for something he had already specified on 07-01.

### 5.3 Pass 2 in its entirety — the exponential curve and per-facet channels

**[USER-STATED]** shape, 07-01: *"cant we just do the evaluation-curve for the ranking of those
'exponential' … kinda meaning 'exact = max' on that curve, ish..?"* — shape decided, angle
deliberately left as a sweep parameter.

The curve was the *diagnosed fix* for the precision failure the user condemned: 07-01 §5 —
*"The precision rot is structural to the flat transfer (every mediocre tag adds score; big
topically-broad chunks soak it up); the curve makes relevance concentrate."* It also unifies the
literal layer (an exact name lands at the ceiling of the same curve, retiring the discrete `+1.0`
boost).

Alongside it, **per-facet channels**: keeping each dial's score separate from tag to chunk so a
chunk carries a facet-relevance profile, which is `DESIGN.md` §14.3's actual combinator
(`promptFacetRelevance · facetWeights`). Pass 1 max-pools one unlabelled set — the designed
combinator was never implemented at all. 07-12 confirms: *"Pass-2 pipeline code has not been
built."*

### 5.4 The falsifiers that would have told them whether facets work — never run

Three cheap tests, each explicitly named as the go/no-go for the layer they gate, none executed:

- **The ~30-phrase orthogonality probe** (06-25 §7, 06-28 §3.7): *"does the embedding move more for
  the facet than for incidental rewording, AND do the facet-concepts separate?"*
- **The per-dial divergence check** (07-01 §7): *"a handful of prompts, per-dial rewrites embedded,
  checking the retrieved tag sets diverge."*
- **The channel-blend reorder test** (07-01 §7), with the consequence spelled out:
  > *"If nothing moves, **every facet design here collapses to topic retrieval** — and that finding matters in itself."*

The corpus is candid that none of this is settled science: 06-28 §3.7 quotes the research catalog —
*"No benchmark evaluates any of this on short context-free phrase-tags into a small facet set; the
behavior on a real tag corpus is an experiment, not a literature fact."* The experiment was
designed three times and never run.

### 5.5 Centrality — the user's own idea, deferred every single pass

**[USER-STATED]** verbatim on 06-11: *"perhaps we can do that, but based on each facet! giving a
relational value of the tag to its siblings based on each facet!?"*, and again on 06-25 as
topic-as-degree. It is the one measurement the research catalog calls **phrase-robust** — the
facet most likely to actually work. It is deferred in 06-11 (unblessed), 06-25 (open), 06-28 §3.3
(deferred), 07-01 §11.8 (inherited), 07-12 (unbuilt). The chunk→tag edge that `DESIGN.md` §14.1
reserves for it carries nothing.

### 5.6 Chunk attribute extraction — `DESIGN.md` §4 stage 4, only 2 of 5 fields materialized

Only `kind` and `product` (the latter read off `relpath`) are joinable. Person, org, and date
attributes were never extracted, so:

- **`date_range` is emitted by the interpreter on every query, validated, and then thrown away** —
  06-28 §2: *"`date_range` is logged but not applied (chunk date attributes aren't extracted yet)."*
- Person/org literals *"ride the semantic layer"* — there is no structural join for "PRs by Anna".
- The aggregation path's group-by keys (`customer_id`, `author_id`) have nowhere to come from,
  which is one reason 5.1 could not proceed.

### 5.7 The build-time validation strategy (`DESIGN.md` §16) — approved, never executed

User-approved on 06-09: two-materials framing, error-analysis-by-reading first, and the sampling
rule *"~30 catches a bug vs 250–500 measures a rate"*. No validation program of this kind appears
anywhere afterward. Its one concrete descendant — the per-model MUST-NOT violation rate — is logged
as an open measurement (1/100 observed for llama-3.3-70b, glm-5.1 unmeasurable because it 429'd)
and never characterized.

### 5.8 Judge calibration against human labels — recommended, never locked

**[AGENT-ASSERTED]**, 06-18 §7: *"to defend the judged RAGAS metrics (faithfulness,
answer-relevance) academically, calibrate against a small human-labeled subset and report
agreement. **Recommended, not locked** (subset size open)."* The `MetricScore` record even carries a
`human_label` calibration slot. Never filled. Every judged number the project reports is
uncalibrated. Flagged as an agent recommendation the user never ruled on — but it is the only
proposed defence of the judged metrics, and it is empty.

### 5.9 The SQL-agent baseline — adopted, then silently un-adopted

**[USER-STATED — paraphrase]**, 05-25: *"Lucene baseline is being dropped; **SQL-agent is the
thesis comparison.** Do not frame analyses around Lucene going forward."* A memory file was written
for it and both 05-25 handoffs instruct the next agent accordingly. By 06-18 the v3 harness is
lucene + vector + artefact, and `baselines/sql_agent.py` is listed as *"dead"* v2 cruft. No
document records the reversal. Not in the git contradiction list.

### 5.10 Smaller items

- **The interpreter's "faceting" rename.** The user wanted a different name so it would not be
  confused with tag-facets (06-25 §11.5). Never done; `facet_phrases` *"still squats on the
  reserved word"* (07-01 §11.10).
- **The fuzzy-embedding pre-pass** ([t24], the user's idea). Blocked on an unresolved question —
  whether to lift `DESIGN.md` §14.7's "no embedded value vocabulary" principle. 07-01 decided
  *fuzzy means embedded* **[USER-STATED]**, which answers it in principle; nothing was built.
- **Geometry-transform refinements** beyond mean-centering (soft-ZCA, cluster-local isotropy,
  IDF weighting), with IsoScore diagnostics. Designed 06-28 §3.7, never attempted.
- **H1–H4 from 06-23** — lucene/vector `documents.feedback` parity in particular. Divergent
  readers are allowed by design, but the doc itself notes it *"does muddy 'sparse vs dense' on that
  kind."* Never resolved.
- **Bonnier / the dual-dataset plan.** Deferred by the user on 06-14 and never resumed — which
  matters because it was the sole stated rationale for the Mistral tagger choice (C-10) and the
  only planned test of whether the design generalizes beyond HERB.

---

## 6. What this corpus settles from `git_record.md` Part 4

| Item | Status |
|---|---|
| **G-2** — the decision events are outside the repo | **Recovered.** The 06-09/06-11/06-12/06-14 docs *are* that fortnight, with the closed spine, the death of the description, per-chunk tag nodes, the structural quarantine, the mapping-key finalization, and the facet reframe each dated and attributed. |
| **G-3** — the state-transfer docs were never committed | **Recovered.** All four named-but-absent docs (06-09, 06-11, 06-12, 06-14) are present and read in full. |
| **G-4** — why the built tagger dropped facets | **Answered.** See C-7. |
| **G-5** — whether anything was ever run on the v3 artefact | **Answered.** The in-memory index was built (13,776 phrases × 2,048) and a full gold-100 k=10 retrieval run completed on 2026-06-28. The Neo4j `herb-v3` build **never ran** — blocked on Neo4j not running locally and `NEO4J_PASSWORD` unset. |
| **G-7** — why `scopeWeight` was introduced | **Still unknown.** Named as a factor to remove; never explained. |
| **G-9** — why the HERB anchor metric was dropped | **Answered.** See C-17. |
| **G-10** — why the arm under test was never switched | **Answered.** See C-2. |
| **G-1 / G-6 / G-8** | Untouched by this corpus. |

---

## 7. Caveats on this record

1. **These are agent-written documents about conversations.** Even the "Canonical user-established
   facts" sections are one party's report. Where a quote is given it is reliable to the extent the
   agent transcribed accurately; the 06-28 design-evolution doc is the strongest because it cites
   `[tNN]` line numbers in a named transcript. Where no quote is given I have labelled
   **[USER-STATED — paraphrase]** and the wording is not the user's.
2. **Three documented instances of agent output being mistaken for canon** are recorded inside the
   corpus itself (05-31 memory fabrication; 06-11 the leaked axis apparatus; 06-25 memories and
   `DESIGN.md` found to misrepresent the facet model). Treat any unquoted claim about "the design"
   accordingly.
3. **The facet definition changed three times in six weeks** — relevance-coordinate (06-14) →
   semantic description (06-25) → relevance dial (07-01) — each supersession written by the same
   pipeline of agents. Each is internally argued; none is final; the 07-01 reconciliation is open.
4. **Two parallel sessions ran unaware of each other** in late June (07-01 §1). Where the 06-28
   trio and the 07-01 doc disagree, the 07-01 user verdicts govern by the 07-01 doc's own
   instruction — but that instruction is itself an agent's arbitration.
5. **The 07-01 doc records the user intending to delete the pass-1 gold-100 outputs.** The 07-12
   review confirms the three 06-28 output folders were deleted in `69115e0`. Any pass-1 number
   quoted here comes from these documents, not from a surviving run directory.
6. **Nothing was read from the prohibited data files.** `questions.jsonl`, `gold100.jsonl`,
   `heldout100.jsonl` and `10smoke.jsonl` were not opened; all question-set figures quoted here
   (1,514 = 815 + 699; the citation distribution min 11 / median 52 / max 683; the twins) are as
   recorded inside the source documents.
