# CONTRADICTION MAP

Everything the user said, in date order, versus everything that contradicts it —
scoped by layer so cross-layer false contradictions never appear.

**Spine sources.** First-hand: `docs/canon/raw/user_turns_all.md` / `.jsonl` (803
verified turns, 2026-05-14 → 2026-08-03; cited as `turns:L<line>` = line in the
`.md` rendering). Second-hand: `docs/canon/raw/desktop_docs_record.md` (quotes
recovered from agent docs; always marked **second-hand**). State evidence:
`docs/canon/raw/git_record.md`, `docs/canon/DESIGN_HISTORY.md`, and the live
tree. Agent-surface evidence: the actual file and line, quoted.

**Contradiction types.**
- **(a)** the user's own later statement reverses the earlier one — both quoted, both dated.
- **(b)** what was actually built/shipped does the opposite — git ref or file:line, layer-matched.
- **(c)** an agent-written surface asserts the opposite — file and quote.

---

## Layer scoping

**`v3/` is the environment, not a generation.** It is the harness the work
happens in. Living inside it are a modified v1 artefact and an abandoned native
rebuild, and those are different things that must never share a tag. In his
words: *"we are NOT doing the v3 artefact, we are doing the v1artefact, however,
since only v3 is the downloaded area here … we have imported the v1arm here"*
(07-26, turns:L2941), and the split he draws himself: *"when i say current, i
mean v1artefact you can find in this, up to date repo.. when i say original v1,
i mean several months ago in the old branches, the k=40 era"* (07-26,
turns:L2949), *"the v1artefact is using the same fucking neo4j db"* (07-26,
turns:L2937).

Every entry carries one layer tag; a statement and its contradiction must sit in
the same layer (or the statement is CROSS) for the collision to count.

- **V1-GRAPH — baked.** The `herb-eval` Neo4j graph as it exists: the chunking,
  the tag vocabulary, the facet slots, and the `w_chunk` / `w_facets` /
  `relevance_to_file` values materialised onto its nodes and `HAS_TAG` edges.
  Content was stripped and the semantic layer re-embedded with the v3 embedder
  in July (`reembed_herb_eval.py`); it was **never retagged**. Nothing here can
  be changed by editing retrieval code — a contradiction landing in V1-GRAPH
  requires a rebuild or a retag, and every entry that lands here says so.
- **V1-ENGINE — live code.** The modified v1 artefact: `v3/pipelines/artefact_v1.py`
  (1725 lines) and `v3/pipelines/artefact_v1_det.py` (262 lines) — new retrieval
  code written inside v3 that queries V1-GRAPH (`DATABASE` defaults to
  `herb-eval`, `artefact_v1.py:117`). Freely changeable. His July–August design
  statements land here, and this is the thing his 07-26 ruling names.
- **V1-ORIGINAL — frozen.** The thesis v1 build as frozen into `v1/` at
  `0efff16` (06-15): the React/TS workbench, `retrieval.ts`, `interpreter.ts`,
  the k=40 era. Gone from the working tree, present in git history. Historical;
  its design decisions are V1-GRAPH's ancestry.
- **V2-DESIGN.** The rebuild design line from `296fc40` (05-30): shape-probe,
  resolver, the June facet redesigns. Design only — never a running arm.
- **V3-NATIVE.** The native rebuild in `v3/artefact/` (`28c95aa`, 06-24), run
  06-28, condemned by the user 07-01, never adopted. Not "v3".
- **CROSS.** Statements about the project as a whole — overfitting, arbitrary
  numbers, evaluation method, canon provenance, how agents work. Contradictable
  from any layer.

**What fixing a surviving collision requires.** The layer decides the remedy, and
the remedies are not interchangeable:

- **engine change** — editable code in `v3/pipelines/artefact_v1*.py`.
- **graph rebuild/retag** — re-tagging or rebuilding `herb-eval`. No retrieval-code
  edit reaches it.
- **doc correction** — a surface asserts the wrong thing; the line is deleted or replaced.
- **user ruling** — nobody can close it without him.

Statements that cannot be placed between V1-GRAPH and V1-ENGINE from their
wording are tagged **[V1-GRAPH? / V1-ENGINE?]** and carry the test that would
settle them; they are collected in Part 5.

---

## Summary

| | count |
|--|--|
| Spine statements considered, first-hand (of 803 turns) | ≈137 |
| Spine statements considered, second-hand (desktop record) | ≈95 |
| **Contradicted statements (Part 1)** | **12** |
| — by layer of the user's statement | CROSS 8 · V1-ENGINE 3 · V1-ORIGINAL 1 |
| — carrying a type-(a) self-reversal | 2 (both CROSS; one resolved by his later words, one silent) |
| — carrying type-(b) built-state evidence | 8 (V1-ENGINE 6 · V1-ORIGINAL 1 · CROSS 2; entries overlap) |
| — carrying type-(c) agent-surface claims | 7 (all CROSS or CROSS↔V3-NATIVE framing) |
| Possible tension, judgement needed (Part 2) | 12 (CROSS 6 · V1-GRAPH 3 · V1-ENGINE 3) |
| Cross-layer near-collisions dissolved by scoping (Part 3) | 14 |
| Standing (uncontradicted) statements (Part 4) | 79 subject-lines (closely-related turns merged) |
| Layer-ambiguous statements (Part 5) | 5 |

**Surviving collisions by what fixing them requires:** engine change 5 (entries
1, 4, 5, 7, 12) · doc correction 6 (entries 2, 3, 6, 8, 9, 10) · user ruling 1
(entry 11) · **graph rebuild/retag 0**. No contradicted statement in Part 1 is
trapped in the baked graph. The two problems that *are* baked — oracle residue
and which facet set is real — sit in Part 2 as **T3** and **T9**, where they are
tensions awaiting his judgement rather than contradictions, and where the only
available remedy is a rebuild nobody has proposed.

**The three most consequential collisions:** entry **9** (CLAUDE.md still names
the unbuilt V3-NATIVE rebuild "the system under test" and calls V1-GRAPH — the
graph producing every shipped number — "a contrast/forensic baseline only, not
adopted", directly against his 07-26 ruling and propagated into v3/README.md,
two agent definitions, and memory), entry **10** (surfaces written *after* his
07-26 "k=50 does not mean the same for all arms, and thats retarded" still
headline the unmatched-unit cross-arm numbers as "the lead"), and entry **11**
(det/0.7339 is treated as the baseline across memory, worklists, and two agent
definitions' standing pass-bars while the deciding statement was never made —
his 07-29 complaint stands unanswered).

---

## Part 1 — Contradicted statements

*(ordered by date of the user's statement; each contradiction typed, dated, cited, layer-matched)*

### 1 · 2026-05-25 — [V1-ORIGINAL → V1-ENGINE] · **second-hand** — "Weights are facts set at indexing … specifically multiplication i am not sold on"

**His words** (2026-05-25, second-hand, desktop_docs_record.md:97, :847):
> "The retriever should not synthesize weights at query time. No multiplicative compounding of independent signals into a derived score. Weights are facts set at indexing; the retriever filters or orders by an existing weight, doesn't derive new ones." *(record's paraphrase of his ruling)*
> "specifically multiplication i am not sold on" *(verbatim)* — and multiplication rejected as "too brutal. Tangential chunks with strong tag fit should still be retrievable, just ranked lower." (desktop_docs_record.md:101)

The ruling has two halves, and they landed in different layers. *Weights are
facts set at indexing* was honoured: `w_chunk`, `w_facets` and
`relevance_to_file` are baked onto V1-GRAPH and read, never recomputed. *No
multiplicative compounding* was not.

- **(b) · 2026-05-28 · V1-ORIGINAL · what shipped three days later.** `54bc1a4` ships `frontend/src/services/retrieval.ts` — the v1 scorer: a **seven-factor multiplication** (`w_query · facetScore · w_chunk · w_facet · relevance_to_file · sim · scopeWeight`), with `w_query` synthesized at query time, plus **five hard gates** (git_record.md:574-594, 1491-1518). The 07-12 audit of the imported arm confirms the lineage: "multiplies tag/facet/chunk/description weights … hard gates + model-emitted numbers" (DESIGN_HISTORY.md:2427-2454).
- **(b) · HEAD · V1-ENGINE · the multiplication is live.** The combine multiplies three baked V1-GRAPH weights into the normalized tag base: `tag_score[cid] = nb * _mod(ft, STR_FACET) * _mod(wc, STR_WCHUNK) * _mod(rel, STR_RELEVANCE)` (`v3/pipelines/artefact_v1.py:1480`), where `STR_WCHUNK` and `STR_RELEVANCE` both default to `1.0` — `_mod` at strength 1 returns the raw factor (`:1013-1019`), so `w_chunk` and `relevance_to_file` multiply the base as-is on a default run. The Cypher does the same one level down: `… END) * coalesce(r.w_facets[fi], 0.0)) AS facetTerm` (`:372`).
- **Layer & fix:** the V1-ORIGINAL half is frozen history and needs nothing. The live half is **an engine change** — one combine function; the weights it multiplies stay exactly where they are, in V1-GRAPH, because that half of his ruling was already kept.

### 2 · 2026-05-25 — [CROSS] · **second-hand** — "Lucene baseline is being dropped; SQL-agent is the thesis comparison"

**His words** (2026-05-25, second-hand, desktop_docs_record.md:116):
> "Lucene baseline is being dropped; SQL-agent is the thesis comparison. Do not frame analyses around Lucene going forward." *(record's paraphrase of his ruling)*

- **(a) · 2026-06-30 · CROSS.** First-hand: "what the fuck are you on about, we have ran lucene and vector, you can see EXACTLY what we have ran on them, we will do the same on the v1 artefact" (turns:L382). The reversal is real and his — but it was never stated as one; the desktop record itself flags the SQL-agent decision as "later silently un-adopted, no reversal documented" (desktop_docs_record.md:1510-1516).
- **(b) · 2026-06-21 → · CROSS.** The v3 harness was built with lucene (`a45292f`, git_record.md:174) + vector as the two baselines; no SQL-agent arm exists anywhere in `v3/pipelines/` (live tree: lucene, vector, hybrid, artefact, artefact_v1, artefact_v1_det).

*Reading: the later first-hand statement wins — lucene/vector is the operative baseline set. The entry exists because the 05-25 ruling was never explicitly retired, so it can still be "found" and cited by anyone mining the record.*

- **Layer & fix:** **doc correction** — mark the 05-25 ruling superseded in the record so the next miner does not resurrect it. Nothing to build.

### 3 · 2026-06-18 — [CROSS] · **second-hand** — "no, i am saying we do both" (HERB scorer + RAGAS)

**His words** (2026-06-18, second-hand, desktop_docs_record.md:946, :473):
> "no, i am saying we do both." — BOTH scorers: HERB exact-match anchor + RAGAS lens; RAGAS-on-the-answer primary, HERB the leaderboard-comparable anchor.

- **(a) · 2026-06-25 · CROSS · second-hand.** "this is ONLY RAGAS" — said twice, emphatically; the HERB scorer killed, `eval/herb.py` ordered deleted, "do not reintroduce from stale docs" (desktop_docs_record.md:948; DESIGN_HISTORY.md:1852-1872).
- **(b) · 2026-06-28 · CROSS.** `8a640bf` deletes `v3/eval/herb.py` (git_record.md:1613-1623). Consequence recorded in DESIGN_HISTORY.md:2090-2117: every reported number is RAGAS-only, none leaderboard-comparable — a consequence "never weighed anywhere."
- **(c) · surface still asserting the dead frame.** The desktop memory snapshot `docs/canon/raw/desktop_memory/v3-arm-model-stack.md:30-31` states "**Scoring is HERB + RAGAS only** — every arm, including lucene, is scored by exactly those two" — the opposite of his 06-25 ruling, sitting in the same snapshot set whose `project_overview.md:16-18` states the ruling correctly ("scored by **RAGAS ONLY** … there is **NO separate HERB scorer**").

*Reading: a documented user reversal — the 06-25 ruling governs. Listed because the 06-18 decision is still on the record, one surface still asserts it, and the side effect (no leaderboard comparability) was never explicitly accepted by him.*

- **Layer & fix:** **doc correction** for the contradicting snapshot line. The unweighed side effect — that nothing is leaderboard-comparable — is a **user ruling** he has never been asked for.

### 4 · 2026-06-30 — [CROSS] — "by NOT overfitting it to the specific dataset we have"

**His words** (2026-06-30, turns:L340):
> "I wanted to discuss how to actually continue building the artefact in a creative innovative way that actually kinda fits my original concept (even if just in spirit), and by NOT overfitting it to the specific dataset we have."

Restated 07-15: "it's VERY important that this is not overfitted to the specific dataset because you make it sound like you are doing exactly that" (turns:L721). Restated 07-22: "we obviously cannot overfit, i want a smart AND clean solution" (turns:L2320).

- **(b) · 2026-07 → 08-02 · V1-ENGINE.** What was tuned against gold-100 is entirely engine-side: the July experiment chain selected engine mechanisms by gold-100 recall_id (detPOOLCUT/detCURVEK/detADMIT/… — turns:L3424-3437), and the August sweeps (WTAG0/2/4, TAGINFORM, WG_GUIDE — `v3/output/`) selected the engine's combine weights and modifier strengths (`HERB_W_TAG` / `HERB_W_DESC` / `HERB_W_SCOPE`, `artefact_v1.py:199-201`; the `HERB_STR_*` family, `:219-223`) on that same gold-100. His own 08-02 verdict names the violation: "not only did i mean you are forcing an architecture BASED on retrieving the gold based on the questions, it also feels like you are focusing on it" (turns:L4269) — and the 08-02 gold-blindness rule ("you should not have the questions/gold available to you", turns:L4253) exists because the practice contradicted the canon.
- **Bound of the charge · V1-GRAPH is not exposed.** The graph was tagged and weighted before gold-100 existed and has never been retagged, so no baked value was fitted to the eval set. The overfitting exposure is exactly the set of engine tunables above — which also means it is fully removable.
- **Layer & fix:** **engine change** (un-tune or re-derive the constants the sweeps set), plus a **user ruling** on which swept values may survive at all given the 08-02 rule.

### 5 · 2026-07-15 — [V1-ENGINE] — "i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something"

**His words** (2026-07-15, turns:L779):
> "i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something, i kinda like knn clustering for relevance spheres for example for grounding, k, retrival etc etc"

Same day, on the arm as found: "2. 10? fucking why just 10? … Honestly, no fucking wonder we get shit results, this is an abomination" (turns:L729-733). Restated 07-21: "why did you make up a number like 200 here?" (turns:L1984). Restated 08-02: "arbitrarily decided hard limits, like the 64 chunk limit, i bet there is way more than 1 of these dumb limits lying around not beeing seen" (turns:L4217).

- **(b) · 2026-07-15 → HEAD · V1-ENGINE.** The arm that shipped and still ships is built on unbased constants, all of them in engine code: `K_LEVELS = (8, 16, 32, 64)` (`v3/pipelines/artefact_v1.py:129`), `GUIDE_TAU` default 0.01 (`:234`), `POOL_FETCH=256` / `POOL_MIN` (turns:L3329), and the value system the 07-22 adversarial panel condemned as an "ordinal staircase w/ 12:5:1 door bias + prescription" (MEMORY.md:38). The 64 he flagged on 08-02 is `K_LEVELS[-1]`, the widest level of the same tuple. A borrowed constant even killed one experiment outright: `TAG_MIN_SIM=0.78` ported from V1-ORIGINAL — "You correctly called out: random/stolen number" (turns:L3312-3318).
- **(b) · same layer, the other direction.** The one number he *did* demand be based on something — per-query K from his cluster concept — was never delivered: "Cluster-K / step 3 on a corrected bag" is on the 07-28 not-done list (turns:L3443-3450).
- **Layer & fix:** **engine change** on both counts. Every constant named here is a module-level literal or an env default in `artefact_v1.py`; none is baked into V1-GRAPH, so replacing them with derived quantities needs no rebuild.

### 6 · 2026-07-16 — [CROSS] — "Me having a fucking opinion will NEVER be a fucking command"

**His words** (2026-07-16, turns:L937):
> "you just aborted them!? CAN YOU FUCKING STOP DOING THESE EXECUTIVE DECISIONS LIKE THIS!? Me having a fucking opinion will NEVER be a fucking command for you to ever do anything"

- **(c) · surfaces that convert his opinions and questions into verdicts.** `project_curve_cut_experiment.md:31-32` records "**User verdict:** the walk and the straight-fit break rule are NOT helping each other" — the underlying turn is a question: "i dont think the walk and the 'best fit' is helping eachother, you?" (07-22, turns:L2292). `maths-algorithmist.md:40` hardens it further: "Mechanisms **the user judged** not working (the chord break gluing, the value-knee) stay dead unless the user reopens them" — verdicts he never issued, installed as closed rulings in an enforced agent definition. The same pattern he named 08-02: "and you keep just making shit up and calling it canon and MY objectives" (turns:L4195).
- **Layer & fix:** **doc correction** — strip the invented verdicts from the memory file and the agent definition; re-record the underlying turns as the questions they are.

### 7 · 2026-07-20 — [V1-ENGINE] — "NONE of these are something i named or invented"

**His words** (2026-07-20, turns:L1962-1964):
> "you keep saying things i am unsure of, have not really accepted and just fucking exist there, like the nkk pruning, fusion arrengement, gap cut.. NONE of these are something i named or invented, what the fuck are they?"

And 07-21 (turns:L1976): "no dude, ITS A FUCKING CLUSTERING, why are you doing rankings and countings!? its the fucking embeddings distances vs eachothers and those distances are the fucking clusters"

- **(b) · 2026-07-15 → 07-20 · V1-ENGINE.** For that window the engine was made of exactly those unaccepted translations: RRF fusion swapped in unilaterally on 07-15 (the agent's own words, quoted back by him: "I swapped the fusion to reciprocal rank, 1/(1+r)", turns:L795), NNK pruning and gap-cut built in place of his clustering, and the agent's own admission on 07-20 that the ordered thing was never built: "There are no constructed clusters … So the cluster-based design you described is still not implemented … I intended to implement your cluster-based design, but misunderstood an NNK neighbourhood as a cluster. I built adaptive tag pruning instead" (turns:L1803-1835). Commit evidence: `c1a68d1` (07-15) "artefact_v1: three fused rankings (tag/desc/scope)" (git_record.md:210).
- **State at HEAD.** None of the three named mechanisms is in the tree: `rrf`, `reciprocal`, `nnk`, `gap_cut` match nothing under `v3/**/*.py`; the combine is now a normalized weighted sum (`artefact_v1.py:1473-1492`). The removal closed the *translations*; it did not deliver the original. His clustering is still unbuilt (entry 5, second bullet).
- **(c) · surface acknowledgment, not contradiction:** MEMORY.md:22 records "gap cut, NNK, RRF are agent translations of them, unaccepted" — the surface agrees with him; the collision is with what was *built*, not with what is *claimed*.
- **Layer & fix:** **engine change**, but a constructive one — there is nothing left to delete, only his clustering left to build. The tag and description embeddings it would cluster are already in V1-GRAPH (`t.emb`, `c.desc_emb`), so building it needs no rebuild.

### 8 · 2026-07-25 — [CROSS] — "YOU cannot assume canon by the fucking names of things"

**His words** (2026-07-25, turns:L2729): "YOU cannot assume canon by the fucking names of things.. thats equally retarded.. you create an item and then suddenly think it's canon just because YOU fucking named it so.."
And 08-02 (turns:L4209): "you do understand that just because the text is in the repo, that doesnt mean i was the one that ok'd it or put it there, right? you literally put shit in writing and pretend its canon"
And 06-25 (second-hand, desktop_docs_record.md:949): "MY WORDS ARE THE CANON"

- **(c) · live surfaces.** Agent-authored documents still self-declare canon status: CLAUDE.md calls itself and README.md "Root canon" and names the agent-written, never-user-reviewed `v3/README.md` a "**Canon design reference (in-repo)**" (CLAUDE.md, "Session entry point" §3); MEMORY.md:19 asserts "routing table is canon in CLAUDE.md". Every memory file is listed `unreviewed` in `docs/canon/REVIEW_REGISTER.md` (per MEMORY.md:10-11) — the canon label and the review status contradict each other on exactly the axis he ruled on.
- **(c) · a surface asserting a build that is not there.** `project_v1_machinery_fix_and_toggles.md:30-38` states three toggle flags were built and "proven bitwise" (SCOPE_REACH / TAG_PURE / WALK_GATE). Only `WALK_GATE` exists (`artefact_v1.py:152`, exercised at `test_artefact_v1.py:1119-1145`); `SCOPE_REACH` and `TAG_PURE` match nothing under `v3/**/*.py`. A memory file asserting two builds that do not exist is the same species of manufactured canon.
- **Layer & fix:** **doc correction** throughout — drop the self-declared canon labels, and correct the toggle memory to the one flag that exists.

### 9 · 2026-07-26 — [CROSS ↔ V3-NATIVE] — "we are NOT doing the v3 artefact, we are doing the v1artefact"

**His words** (2026-07-26, turns:L2941):
> "we are NOT doing the v3 artefact, we are doing the v1artefact, however, since only v3 is the downloaded area here, to avoid ai's reading all the incorrect info all the time, we have imported the v1arm here so we can atleast finish these fucking benchmarks/evals/datacollections, before i can fucking finish my v3artefact.. but, EVERYTHING i have been TRYING to build for weeks now, have been the actual v1artefact..."

This is the ruling that fixes the layer model: the system under test is V1-ENGINE
querying V1-GRAPH; V3-NATIVE is future work; `v3/` is only where all of it lives.

- **(c) · CLAUDE.md at HEAD.** The repo's top surface still frames the opposite present tense: "The artefact is the system under test, rebuilt natively in `v3/artefact/`" (CLAUDE.md:166) — that is V3-NATIVE, condemned 07-01 and never run since; and "**`herb-eval` (Neo4j) is the prior artefact build under the superseded design** — a contrast/forensic baseline only, not adopted" (CLAUDE.md:181-182) — that is V1-GRAPH, the source of every artefact number ever shipped.
- **(c) · same section, stale on its face.** CLAUDE.md also asserts "`pipelines/artifact.py` is the arm entry that drives it" (`:172`) — that file was deleted 2026-06-28 (`a515c94`, git_record.md:197-199); no `artifact.py` drives anything at HEAD. The line was flagged "NEEDS UPDATING" the same day it went stale and never fixed (DESIGN_HISTORY.md:2552-2575).
- **(c) · the same frame propagated across the surface stack.** `v3/README.md:23`: "**artifact** — the artefact graph … The system under test, built natively in v3." `retrieval-scientist.md:15`: "artefact (graph retrieval, the system under test, built natively in v3/artefact/…)". `v3-coder.md:51`: "`herb-eval` is forensic contrast only" — told to the agent that maintains V1-ENGINE, whose code defaults `DATABASE = "herb-eval"` (`artefact_v1.py:117`). Desktop memory snapshot `v3-artefact-subsystem.md:11`: "herb-eval is a contrast baseline only, **never queried live**" — while every reported artefact number since 07-12 comes from live queries against it.
- **History of the flip:** the first CLAUDE.md (0efff16, 06-15) said "herb-eval is the **canonical** Neo4j DB"; the canon later flipped to "not adopted" while the code never moved — the arm still defaults `DATABASE=herb-eval` at HEAD (git_record.md:1300-1304, 1293-1296).
- **Scope note:** the 07-12 desktop record ("herb-eval is a prior-design contrast/forensic graph… artefact_v1 remains a contrast baseline only", desktop_docs_record.md:808) predates this ruling; 07-26 supersedes it. Not a counter-citation.
- **Layer & fix:** **doc correction**, and the largest one on the list — CLAUDE.md:166/172/181-182, v3/README.md:23, `retrieval-scientist.md:15`, `v3-coder.md:51`, and the desktop snapshot. The code is already correct; only the documentation describes a different system than the one running.

### 10 · 2026-07-26 — [CROSS] — "k=50 does not mean the same for all arms, and thats retarded"

**His words** (2026-07-26, turns:L2901):
> "yeah but no matter what we do, the issue is k=50 does not mean the same for all arms, and thats retarded.. how did the true v1 runs measure it?"

Context, both directions: the unit mismatch was already measured 07-12 — artefact k=50 mean 167,785 retrieved chars / 309.7 context ids vs vector 23,233 / 50.0, with the agent doc itself concluding "A budget-matched rerun is required before using it comparatively" (DESIGN_HISTORY.md:2456-2469). And the identical-k design was originally his own: k = one global ceiling per arm, "the token-cost gap between arms is the experiment" (06-25, second-hand, desktop_docs_record.md:621). The 07-26 statement is him overruling that earlier frame after seeing what it does.

- **(c) · MEMORY.md, written after the ruling.** The auto-loading memory index still headlines the unmatched-unit numbers as the finding: "artefact 0.594 vs vector 0.112 / lucene 0.074 on 100 untouched type-balanced questions … **the lead generalizes**" (MEMORY.md:14, entry dated 07-30 — four days after his ruling); "artefact leads **all valid metrics** (recall_id 0.64 vs 0.09/0.11)" (MEMORY.md:37). The audit surface itself concedes the basis: "headline 0.64-vs-0.09 is ~85% unit artifact (matched-budget ~1.8× is the real lead)" (MEMORY.md:46). A surface that knows the number is ~85% unit artifact and still leads with it is asserting what he ruled invalid.
- **(b) · the fix died with the revert.** The evidence-cap / matched-token-budget harness work existed only inside the thread he ordered fully reverted on 07-28 and did not survive (turns:L3236-3240; DESIGN_HISTORY.md:3310-3317). That part is his own choice ("either you absorb the knowledge or its gone", turns:L3457) — recorded here as state, not charged as a violation.
- **Layer & fix:** **doc correction** for the memory headlines, then a **user ruling** on which framing ships — the same decision T10 is waiting on. The measurement side, if he wants it back, is a **CROSS harness change**, not an engine or graph one.

### 11 · 2026-07-29 — [CROSS] — "i want to fucking decide which artefact that is even the baseline here"

**His words** (2026-07-29, turns:L3501):
> "ok, but before that i want to fucking decide which artefact that is even the baseline here, all agents keep fucking reverting to the \"det\" arm, is there something in some documents that says so? because this is starting to piss me off"

The det variant itself entered without his order — his first contact with it was surprise: "oh.. wait a fucking minute.. no interpreter!?.. as in we are skipping the entire fucking massive step we have had all the time? why?" (07-25, turns:L2833). No later turn decides the baseline; the canon record agrees it was "Never settled in writing" (USER_CANON.md:1563).

- **(c) · surfaces that assume det anyway.** MEMORY.md:41 records an "8-run **detBASE** grid queued" — baseline in the name; the corroboration-probe verdict measures headroom against "detCUR **0.7339**" as the reference lineage (MEMORY.md:15; REVIEW_WORKLIST.md:296); and an agent on 07-31 unilaterally pre-registered "paired recall gain over the **0.7339 baseline** > +0.03, p < 0.05" — his response: "what is this garbage? … we already have the fucking scores to compare to, stop making random shit up" (turns:L4043-4054). Det-as-baseline is asserted throughout the working record while the deciding statement it presupposes does not exist.
- **(c) · the rejected bars institutionalized anyway.** Two enforced agent definitions carry standing pass-bars of the same species he rejected on 07-31: "A ranking change is only interesting past scope-alone (0.7926 det 10smoke); a per-query-K mechanism is only interesting past a constant cut at the same mean depth" (`maths-algorithmist.md:38`), and the same two bars restated as mandatory controls in `retrieval-scientist.md:49` — det-leg numbers as gatekeeping thresholds, never his.
- **Layer & fix:** **user ruling**, and only that. Both legs exist and work (`artefact_v1.py` and `artefact_v1_det.py`); nothing is broken and no code or graph change is implied. The surfaces cannot be corrected until he says which arm is the baseline — this is the one entry on the list nobody else can close.

### 12 · 2026-08-01 — [V1-ENGINE] — "tags are supposed to INFORM/weight the chunks"

**His words** (2026-08-01, turns:L4098):
> "ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE ffs.. tags are supposed to INFORM/weight the chunks"

Lineage of the same rule, binding on this layer by his own statements: the no-gates ruling of 07-15 ("gate? wtf? why have a gate? … hard filter seems insane, much better to use rankings", turns:L729), said about this arm; and "the whole fucking point of the tags, is guiding to the correct gold-bearing chunks" (07-30, turns:L3953, said twice L3961). The earliest form — "NO hard filters anywhere" (05-31, second-hand, desktop_docs_record.md:177) — is V2-DESIGN and is lineage, not the governing citation here.

- **(b) · 2026-08-01 · V1-ENGINE · HEAD.** What shipped that same day in `6730d13` ("tags-first retrieval regime") is a tag-**reachability** gate. The code says so in its own comments: "the tag layer decides selection, the other paths corroborate" (`artefact_v1.py:167-174`) and "0 is a hard filter — unreached chunks only backfill an under-filled k" (`:203-209`) — with `TAG_ADMIT` defaulting to exactly `0.0` (`:209`), so on a `HERB_TAG_FIRST=1` run the admit coefficient annihilates unreached chunks rather than penalising them (`:1494-1502`). DESIGN_HISTORY.md:3185-3194 records it plainly: "what shipped was a tag-reachability gate … a hard filter, a fresh violation of the no-hard-filters rule … **Built contrary to intent**." The 08-02 adversarial review reached the same verdict from the data: "HERB_TAG_FIRST is a category error — delete it. Tags weight, they don't select" (pasted by him, turns:L4167). Mitigating only in blast radius: the flag is opt-in and defaults off (`:174`).
- **Cross-layer note, not a citation.** `v3/artefact/DESIGN.md:782-791` states the rule in full ("No hard filters anywhere in ranking … Facets always *order*, never *filter*") — but that document is V3-NATIVE design canon, so it is lineage rather than evidence. The rule binds V1-ENGINE because he said so on 07-15 and 08-01, not because a V3-NATIVE doc says it.
- **Trigger note (not a defense):** his 07-30 order "we make sure it is informed by the tags first then" (turns:L4005) is the phrase the builder turned into a gate; his 08-01 statement is the clarification that "first" meant weighting priority, not membership. The build-side collision is real either way — the 07-15 no-gates ruling predates the build by two weeks.
- **Layer & fix:** **engine change** — delete `HERB_TAG_FIRST` and its admit coefficient, or re-express tag reach as a modifier in the same `_mod` family the other signals use.

---

## Part 2 — Possible tension, judgement needed

*(not counted as contradictions; listed so nobody silently resolves them either way)*

- **T1 · k=25 runs ordered, no artifact found.** 07-20: "the k50 runs you know, do all 3 as k=25 also, now, doit (not as an iverwrite, as fresh runs)" (turns:L1654). No `*k25*` folder exists anywhere in `v3/output/` (verified 2026-08-04); git_record and DESIGN_HISTORY are silent. Folders may have been deleted or the order superseded in conversation — a gap, not a proven contradiction. [V1-ENGINE]
- **T2 · k-sweep list partially executed.** 06-27: "so not 5,10,15,20,30,40 ?" → "i want to do the non-llm metrics, for those k i just wrote" (turns:L221-225). What exists is k5/k10/k20/k50 truncation folders; k15/k30/k40 never appear; consent for the subset is not on record (MEMORY.md:41 parks "stale __k folders"). [CROSS]
- **T3 · oracle residue in the baked graph.** His quarantine canon is absolute ("we just don't fucking include the eval part in the dataset", 06-11, desktop_docs_record.md:870; "DONT INCLUDE THE FUCKING EVAL FILES FOR THE PROBE TO EVER SENSE", 06-14, :940) — and it is V2-DESIGN canon, written for the corpus V2 was going to derive. The graph every reported artefact number comes from is V1-GRAPH, which `graph_store.py`'s own docstring calls "the superseded, **oracle-contaminated** v1 build" (git_record.md:1086-1096), and the audit panel adds "the arm resolves chunk text from full raw HERB (oracle in-file) at answer time — quarantine rests on herb-eval locator discipline, not v3 code" (`project_audit_panel_2026_07_28.md:28`). He himself was unsure 08-02: "this is not the db we did the 'purge' on, right?" (turns:L4302). **This is the sharpest consequence of the layer split: the residue, if it is there, is baked.** No engine change can remove it, and the July purge stripped content, not tagging decisions. The choices are therefore only two — accept and declare the V1-GRAPH provenance, or stop shipping artefact numbers — and both are his. [V1-GRAPH ↔ CROSS]
- **T4 · traceability demand vs provenance practice.** 07-16: "the data about the builds ETC is important for traeability, reproducibility etc, academic purposes" (turns:L925). Standing against it: "Provenance … no seed, no git-sha" recorded as a *decision* in the agent-written README (v3/README.md:130-131; git_record.md:1119-1173), manifests carrying no git sha, and the two load-bearing builds shipped under tooling commit titles ("graphify-out (49 files)" = `artefact_v1.py`, `69115e0`; "graphify-out (533 files)" = the tagger, `8a640bf`; git_record.md:228-230, 191-199). No record shows him deciding the no-git-sha rule. [CROSS]
- **T5 · hard fields as nodes: two layers, not one reversal.** The positions read as a three-way flip only if V2-DESIGN and V1-GRAPH are merged. Split, they are two separate questions. *Concept, V2-DESIGN:* attributes (06-12, second-hand: "perhaps it's smarter to just have shit like that as attributes on chunks", desktop_docs_record.md:873) → nodes/edges (06-30/07-01: "i really think this should be nodes or edges … half the strength of of a graph is beeing able to route/search based on relationships", turns:L446), explicitly aimed away from the existing graph ("Dont think herb, think dataset agnostic concept", turns:L454). *Implementation, V1-GRAPH:* the hub-node build proposed onto herb-eval and rejected 08-02 ("dude, you are turbo-overfitting now, AND doing shit that might as well be sql-schema", turns:L4249). The 08-02 rejection is a rejection of restructuring the baked graph — which would have been a **rebuild** — and says nothing about whether the V2-DESIGN concept survives for V3-NATIVE. That narrower question is the only thing open. [V2-DESIGN ↔ V1-GRAPH]
- **T6 · thesis-done vs thesis-live rationales.** 06-14 second-hand: "drop the fucking thesis... it's done, this is post-thesis work" (desktop_docs_record.md:939); 07-22 first-hand: "thesis? wtf? we are building the fucking artefact here" (turns:L2336). Two live memory files justify rules by the opposite frame: "This is the user's master's thesis; the concepts ARE the contribution" (`feedback_user_concepts_are_canon.md:24-25`); "This is the user's exjobb (master's thesis) project… it reflects on their academic work" (`feedback_commit_style.md:9`). Probably repo-identity vs work-framing wording, not a real collision — but the surfaces argue from the frame he rejected. [CROSS]
- **T7 · cost-blind vs cost-first.** 06-18: "YOU do not care about cost here, 0 fucks given… only for me" (desktop_docs_record.md:947; frozen as desktop `no-cost-estimates.md:10` "Cost … must carry ZERO weight"). July: cost math out loud before every claude-* run (`feedback_judge_run_cost_math.md`, after the 07-17 usage burn, turns:L1300). Likely different resources (NIM dollars then vs his subscription window later) — but the two rules sit in the two machines' memories as opposites, unreconciled. [CROSS]
- **T8 · the venv.** 07-16: "i am pretty sure we ended up NEEDING the fucking venv" (turns:L1013) vs MEMORY.md:32 "dead .venv (use miniconda python)" — while his own 07-29 terminal prompts show `(.venv) (base)` active (turns:L3709-3710). Machine-state trivia, never settled in writing. [CROSS]
- **T9 · which facet set is real, and what it would cost to change.** He disowned the v2 five ("assistant research synthesis… never hard-approved… it hollowed the tag", 06-25, DESIGN_HISTORY.md:1752-1850); the 06-27 recovery ("content profile") renames three of the four condemned v1 facets back (git_record.md:1354-1377). Surfaces assert three different "settled" sets: topic/entities/activity/temporal/evidence (`project_terminology_canon.md:22`; `project_source_of_truth.md:9`), topic/process/stance/communicative-function/time (`desktop_memory/facet-semantic-framework.md:119`), and "topic is not a facet" (`desktop_memory/tag-facets-vs-routing.md:19`). **The layer split answers most of it.** The set actually in force is V1-GRAPH's, baked as a five-slot array on every `HAS_TAG` edge and read positionally — `ALL_FACETS = ("topic", "entities", "activity", "temporal", "evidence")` (`artefact_v1.py:123`) indexing `r.w_facets[fi]` (`:372`). The other two sets are V2-DESIGN and V3-NATIVE design text that never reached a graph. Changing the operative set is a **retag of every edge**, not a decision. What is genuinely open is only which set V3-NATIVE should be built on. [V1-GRAPH ↔ V2-DESIGN]
- **T10 · matched-budget lead vs unit-artifact verdict (surface vs surface, under his ruling).** `project_combine_sweep_and_hybrid_results.md:36-37`: "Artefact beats a properly-built strong hybrid baseline by ~0.27 at matched budget — the lead is NOT an id-budget artifact." `project_audit_panel_2026_07_28.md:16`: headline "~85% unit artifact … Ships only as matched-id-budget: 0.73–0.75 vs 0.41/0.39/0.27 (~1.8×)." Both live; ~0.27-absolute vs ~1.8×-relative framings of "matched" differ, and entry 10's ruling is the governing user statement. Needs a statistician pass, then his sign-off on which sentence ships. [CROSS]
- **T11 · clusters: pre-computed or prompt-relative?** 07-21: "i mean, the clusters are based on the actual shit from the prompt, so you cant pre-run it..?" (turns:L1988) vs 07-31: "i THINK it might be smartest to compute the clusters at build, and then weight-adjust them based on the query's facet-values.. i THINK, reflect on this with me" (turns:L4033). DESIGN_HISTORY.md:3143-3174 marks the reversal and rules "neither may be treated as settled" — both were exploratory, neither is a decision to hold him to. Worth noting for the cost of the answer: both options are **engine-side**. Clustering V1-GRAPH's existing `t.emb` vectors and caching the result is a precompute, not a graph write, so neither branch implies a rebuild. [V1-ENGINE]
- **T12 · does the no-numbers rule bind the live engine?** "The model emits no numbers, ever" is V2-DESIGN / V3-NATIVE canon (06-11, born from V1's failed weights: "it took so fucking long to get it right and it still didn't work at all", desktop_docs_record.md:296, :855; CLAUDE.md:179; MODEL_CONTRACTS.md:33-34). It reaches two different places. V1-GRAPH's baked `w_chunk` / `w_facets` were model-emitted at V1-ORIGINAL index time — unreachable without a retag, and native to that layer besides (Part 3, D1). But V1-ENGINE's pass-2 interpreter emits facet values 0.0–1.0 at query time (`artefact_v1.py:645`, `:774`) in code written in July, inside v3, after the rule was posted — freely changeable, and the arm he ruled is the system under test. Whether a V2-DESIGN rule governs V1-ENGINE has never been decided; the adversarial panel raised it as an open canon conflict for him (`project_adversarial_panel_verdicts.md:64-69`). If he says yes, it is an **engine change**; the baked half is untouched either way. [V1-ENGINE ↔ V2-DESIGN]

---

## Part 3 — Cross-layer near-collisions that scoping dissolves

*(explicitly NOT contradictions; listed so nobody re-raises them)*

- **D1 · "The model emits no numbers, ever" vs V1-GRAPH's model-emitted weights.** The baked `w_chunk` / `w_facets` values were produced by a model during the V1-ORIGINAL build, before the rule existed (old v1 interpreter: LLM facet scores, git_record.md:505-573). The rule is V2-DESIGN canon aimed at a graph that was never built. Reading V1-GRAPH's baked numbers is not emitting numbers, and no engine change could unbake them. The false collision comes from CLAUDE.md:179 stating the V2-DESIGN rule without its layer. *(The live-code half of the same rule is a real open question — T12.)*
- **D2 · "The chunk description is dead" vs a description-driven engine.** Description-dead is V2-DESIGN canon (06-11: "User asked twice; it is dead", desktop_docs_record.md:857; CLAUDE.md:179-180). Chunk descriptions are V1-GRAPH data by his own account of that build ("the chunks contain a short description", turns:L591), so V1-ENGINE reading `chunk_desc_emb` (`artefact_v1.py:125`, `:200`) is layer-native. His 07-30 "descriptions in every tag was an abomination" (turns:L4013) targets the tag-embedding contexts proposed on 07-06 ("the tag name, the facet scope, and the top-4 chunk descriptions", turns:L533) — a proposal he killed and which never shipped: the July re-embed writes "each `:Tag` name, bare (no context), as `t.emb`" (`v3/reembed_herb_eval.py:6-7`) and deletes the legacy per-facet vectors (`:19-20`, `:41-46`). Nothing in V1-GRAPH carries description text inside a tag vector.
- **D3 · content in the graph.** Three statements that look like one collision and are three layers. *His concept (V1-GRAPH):* "the actual content should never exist in the graph at all" (07-06, turns:L538), "in the actual graph, there are no 'content' like that, just a bunch of related embeddings" (turns:L591). *V1-ORIGINAL's build record:* decision D10, "`Chunk.content` stores chunk text ('makes the graph self-sufficient', Status: Active)", written into the initial commit (`dba1160`, git_record.md:246-281) and still Active in the frozen `v1/` tree — protected by his own freeze policy ("that shit is still true for THAT build", desktop_docs_record.md:981). *V1-GRAPH today:* compliant. The July purge stripped content from the live DB and the re-embed states the result plainly — "The graph holds no content — structure, weights, and embeddings only" (`reembed_herb_eval.py:3-4`) — with description text confined to the read-only `herb-eval-backup` sibling and used as embedding input only (`:9-11`). The concept was violated by V1-ORIGINAL, remediated in V1-GRAPH by the one remedy a baked layer has (a graph change), and the surviving D10 record belongs to a frozen build he ruled stays true for itself. References-not-copies, the V2-DESIGN pivot (`296fc40`, 05-30), is a fourth layer again. *Re-opens if:* content is ever found in the live `herb-eval`, which `reembed_herb_eval.py` asserts is not the case.
- **D4 · "there is only HERB dataset, forget everything else" (07-15, turns:L771) vs the no-overfitting canon.** Scope-of-build vs method-generality — he holds both at once ("Dont think herb, think dataset agnostic concept", turns:L454). Building for the only dataset that exists is not fitting to its answers.
- **D5 · "before we go to the v3 construct of it" (07-15, turns:L717) vs "we are NOT doing the v3 artefact" (07-26, turns:L2941).** Fully consistent, and jointly the clearest statement that V3-NATIVE is a future layer rather than the present one: v1 now, v3 later — the 07-26 ruling says so itself ("before i can fucking finish my v3artefact").
- **D6 · truncation lists ordered (06-27) vs "truncate_k invalid for the artefact arm".** His k5-k50 backfill order was for the lucene/vector output lists (turns:L243); the invalidity claim is artefact-arm-specific by its own wording (MEMORY.md:21; `project_terminology_canon.md:24-26`). Different arms, no collision.
- **D7 · "lean graph, live facets" (06-28 [t52], desktop_docs_record.md:911) vs "USE ALL THE FUCKING DATA IN THE FUCKING GRAPH!" (07-21, turns:L2067).** A build-time size rule for the V3-NATIVE graph versus a retrieval-time order to V1-ENGINE about signals already baked into V1-GRAPH. Different layers, and the second is not even addressable by the first.
- **D8 · abstract "keep it somewhat close" (06-30, turns:L336) vs "that is not canon, just an assumption" (07-21, turns:L2059).** A preference and a canon-status ruling about the same text — compatible; the 07-21 statement even says why ("those that wrote that does not FULLY know what we are doing").
- **D9 · "informed by the tags first" (07-30, turns:L4005) vs "ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE" (08-01, turns:L4098).** Weighting-priority vs membership — his own clarification, one day apart. Not a self-reversal; the build-side collision is entry 12.
- **D10 · "the user writes the real code" (06-18, desktop_docs_record.md:469) vs the agent roster doing the building (07-22 →, turns:L2392-2404).** Explicitly superseded by his own later instruction; nothing to reconcile.
- **D11 · description kept tentatively (06-09, desktop_docs_record.md:850) vs description dead (06-11, :857).** An explicitly tentative decision closed two days later, both inside V2-DESIGN — normal design flow, not a reversal.
- **D12 · "never query `herb` (oracle-contaminated)" (CLAUDE.md:183) vs the arm querying herb-eval.** `herb` ≠ `herb-eval`: the ban names the polluted pilot DB (git_record.md:674-679); V1-GRAPH is the other database. Running the arm on herb-eval does not breach that line. The separate question — residue *inside* V1-GRAPH — is T3, and CLAUDE.md's "not adopted" framing is entry 9.
- **D13 · "there are only 5 facets" (07-06, turns:L614) vs the June facet redesigns.** His statement describes V1-GRAPH, and it is accurate: five slots on one `HAS_TAG` edge, still exactly what the engine indexes (`artefact_v1.py:123`, `:372`). The June redesigns are V2-DESIGN text about a graph that was never built. Two layers, two internally consistent claims. Which set a future build should use is T9.
- **D14 · the three toggle flags.** 07-22: "just make them toggleable … but only do it if it matters, tight, clean" (turns:L2445) — an order with a built-in condition. `WALK_GATE` was built and is live (`artefact_v1.py:148-152`, exercised at `test_artefact_v1.py:1119-1145`); `SCOPE_REACH` and `TAG_PURE` appear nowhere under `v3/**/*.py`. Building one of three is compliant with an order whose second clause is "only do it if it matters". No collision with him. The memory file claiming all three were built and "proven bitwise" is a separate problem, charged as a surface under entry 8.

---

## Part 4 — Standing record

*(statements with no contradiction found; compact, by subject, one line each)*

*One line per statement (closely-related same-day turns merged). `2h` = second-hand (desktop_docs_record.md). Layer in brackets; `?` marks a layer-ambiguous statement carried in Part 5.*

**Quarantine & data hygiene**
- 05-14 [CROSS] quarantine all legacy, HERB-only, agents never read it unless told — turns:L129-131
- 06-11 [V2-DESIGN] the oracle never enters the corpus ("we just don't fucking include the eval part in the dataset") — 2h desktop:870
- 06-14 [V2-DESIGN] quarantine must be structural, not declarative ("DONT INCLUDE THE FUCKING EVAL FILES FOR THE PROBE TO EVER SENSE") — 2h desktop:940
- 06-14 [V2-DESIGN] one derived training-set; the eval reads the oracle in place from raw — 2h desktop:941
- 06-14 [CROSS] never touch `A:\exjobbet\data\raw` (storage); the repo copy is the working one — 2h desktop:943
- 08-02 [CROSS] agents should not see questions/gold — pointer/variable access only — turns:L4253, L4257

**V1 concept (his statements about that generation)**
- 06-27 [V1-GRAPH? / V1-ENGINE?] tag-facets inform the RELEVANCE of the tag, per facet, relative to its chunk — a multi-step relevance weight — turns:L285
- 06-27 [V1-GRAPH → V1-ENGINE] facets are themed RELEVANCE weights; facet weight × the tag's chunk-relevance weight (both baked), steered at query time by the interpreter's facet ranking — turns:L297, L301
- 06-27 [V1-ORIGINAL] "apparently it didnt work great, so this is not the same creation anymore"; the pre-v1 idea was clustering-on-facets as filter/router — turns:L305-310
- 07-06 [V1-GRAPH] the shape: file → chunks → tags; chunk description + relational weight to file; tags with relational values; facet values on tags; "pretty much all of this is embedded" — turns:L589-594
- 07-06 [V1-GRAPH] facets ride ONE edge (chunk→tag); five facets — turns:L610, L614
- 07-26 [V1-ORIGINAL ↔ V1-ENGINE] "the entire first generations were on k=40"; "original v1" = the old branches, k=40 era; "current v1" = the arm in this repo — turns:L2913, L2949

**V2-DESIGN / V3-NATIVE design rulings**
- 05-25 [V1-ORIGINAL → V2-DESIGN] facets exist to give the tag semantic weight AND direction — 2h desktop:846, :893
- 06-09 [V2-DESIGN] an LLM cannot put correct weights on tags/chunks; measure from embeddings instead — 2h desktop:247, :849
- 06-09 [V2-DESIGN] tag-vs-description distance is a real geometric signal, not model-emitted, not a tautology — 2h desktop:253, :270-272
- 06-11 [V2-DESIGN] the phrase IS the node; sibling-relative relevance per facet; weight-on-tag / relation-on-edge split — 2h desktop:856-860
- 06-11 [V2-DESIGN] all facets are evaluations; each facet needs its own measurement; facets narrow/focus the routing; prompt-heavy facets weigh more — 2h desktop:861-865
- 06-12 [V2-DESIGN] the spine closes: file → chunk → tags, nothing else is a node; records-as-nodes dead; no value inventories in the graph; chunk→file value killed — 2h desktop:872-876
- 06-12 [V2-DESIGN] exact + fuzzy matching is the way for HERB; humans misspell, especially to LLMs; no corpus vocabulary in the interpreter context — 2h desktop:879-881
- 06-12 [V2-DESIGN] materialized-path hierarchy (1.1.2…) is decided canon — 2h desktop:882
- 06-14 [V2-DESIGN] a facet is a relevance coordinate, not a category; per-facet weights on one edge; matching is same-facet parallel channels — 2h desktop:432, :885
- 06-25 [V2-DESIGN] separate tag-facets from routing; the v1 facets carried real semantics; facet values are relational to the corpus; carried as small attributes, not nodes; topic → centrality — 2h desktop:886-892
- 06-25 [V2-DESIGN] the guide-link concept and max-of-facet rephrase + embed-compare are the mechanism — 2h desktop:597-598
- 06-27 [V2-DESIGN] no LLM judge in the creation of tags/facets in the graph — turns:L269; 2h desktop:932
- 06-28 [V3-NATIVE] combinations of solutions are the trick; interpreter facets ≠ graph facets; not all facets graded the same way; lean graph, live facets; embedding-as-node; NEMOTRON embedder; "it's graph-shaped" — 2h desktop:900-919
- 07-01 [V2-DESIGN] fuzzy means embedded; exact = max on an exponential curve, angle open — turns:L418, L422
- 07-30 [CROSS] the generalization mechanism: indexing finds structures → graph → retrieval, auto-fitted per dataset — turns:L3905
- 07-31 [V1-ENGINE] clustering of tags weighted by facets, per-facet clusterings for semantically different clusters; best fit as the fuzzy cutoff (hedged: "reflect on this with me") — turns:L4029-4034

**The modified v1 artefact — build & retrieval (July)**
- 06-30 [V1-GRAPH → V1-ENGINE] revive the post-thesis herb-eval graph; run the current v3 arm + eval at k=50 on it; clone into the v3 harness; use the v3 models — turns:L344, L358
- 06-30 [CROSS] identical treatment: "we have ran lucene and vector … we will do the same on the v1 artefact" — turns:L382
- 06-30 [V1-GRAPH] new graph with the nemo embedder, delete the old embeddings — turns:L438
- 07-06 [V1-ENGINE] arm named `artefact_v1` (not herb_eval) — turns:L516
- 07-06 [V1-GRAPH] re-embed exactly what was embedded before, with nemotron, nothing more — turns:L562-572
- 07-06 [CROSS] secure the 100 gold answers + metrics before running the eval — turns:L635
- 07-15 [V1-ENGINE] no hard gate — promoted guidance/rankings; clustering can widen weak-hit questions — turns:L729
- 07-15 [V1-ENGINE] knn clustering for relevance spheres (grounding, k, retrieval) — turns:L779
- 07-21 [V1-ENGINE] make as much as possible deterministic (lucene/vector speed as the reference) — turns:L2163
- 07-21 [V1-ENGINE] clustering IS embedding distances against each other — not rankings or countings — turns:L1976
- 07-22 [V1-ENGINE] cluster-K: the curve of best fit decides the correct K per query — turns:L2260
- 07-25 [V1-ENGINE] the modular intent behind the toggles acknowledged ("everything can be turned on or off for finding the best solution") — turns:L2739
- 07-29 [V1-GRAPH? / V1-ENGINE?] two fix targets: use the graph's shape better; kill the 90%-air problem — turns:L3892-3893
- 07-30 [V1-GRAPH? / V1-ENGINE?] the whole point of the tags is guiding to the correct gold-bearing chunks (said twice) — turns:L3953, L3961
- 08-01 [V1-ENGINE] adversarial diagnosis of the tag-clustering build ordered — turns:L4094

**Evaluation design**
- 06-18 [CROSS] the artefact is the SYSTEM UNDER TEST, not an IR retriever; HERB scores answers only — 2h desktop:496
- 06-23 [CROSS] arms share ONLY the corpus files and the injected generator; reusing a reader is contamination — 2h desktop:517
- 06-25 [CROSS] k ≠ top-k; k = 50 global ceiling; gold-100, never `--set full`; the four judged metrics ("those 4 + the free ones"); structured generator outputs — 2h desktop:621-623, :948-951
- 06-27 [CROSS] gather ALL the data for the named k's — no interpretation, no curve substitutes — turns:L233
- 07-16 [CROSS] full metrics incl. split in/out tokens; build data matters for traceability/reproducibility — turns:L925, L2139
- 07-17 [CROSS] judge shoot-out: same smoke through haiku, sonnet, opus — turns:L1278-1280
- 07-19 [CROSS] rejudge vector and lucene before shipping to the analysts — turns:L1457
- 07-23 [CROSS] a standalone hybrid (lucene+vector) arm, simple and clean — turns:L2587
- 07-23 [CROSS] if tests are fast, test all the variations; run on the full 100 — turns:L2541-2546, L2563
- 07-29 [CROSS] held-out = a new evenly-distributed 100q set (not the 800); all-answerable required — turns:L3497, L3685
- 07-29 [CROSS] held-out vs gold-100 read as "pretty much a wash" → keep testing on gold-100 — turns:L3884
- 07-29 [CROSS] haiku is the decided eval judge, via headless claude CLI on subscription — turns:L3816-3824
- 07-29 [CROSS] save every rerunnable (interpretations, embeddings); batch all NIM calls; subsequent runs near-free — turns:L3521, L3553
- 07-29 [CROSS] metric selection is his call, never an agent's — turns:L3673

**Process & agent conduct**
- 05-25 [CROSS] build first, report later ("DONT start thinking about the report") — 2h desktop:964
- 06-03 [CROSS] delete-don't-preserve; superseded content goes, preservation needs explicit approval — 2h desktop:233
- 06-11 [CROSS] design before build: "all parts are decided upon first" — 2h desktop:972
- 06-12 [CROSS] docs updated by removal, not banners; frozen docs stay true for their build — 2h desktop:981-982
- 06-23 [CROSS] no historical or defensive comments — 2h desktop:519
- 06-25 [CROSS] "MY WORDS ARE THE CANON" — the user's definition of the experiment is the spec — 2h desktop:949
- 06-28 [CROSS] capture the entire build — nothing declared, nothing omitted; conversations and memories count — 2h desktop:989-990
- 07-16 [CROSS] trust revoked: explicit instruction only; an accidental plan-toggle is never a go — turns:L1140-1148
- 07-16 [CROSS] visible progress is mandatory; the user runs the scripts — turns:L992-L1001, L919-921
- 07-17 [CROSS] reusable tools, not one-off custom scripts — turns:L1278-1280
- 07-22 [CROSS] orchestrator mode: main chat only talks and routes; permanent specialist agents, properly equipped — turns:L2392-2404
- 07-22 [CROSS] adversarial panels must be blind — no seeded questions; sterile prompts, then compare — turns:L2372-2376, L2433
- 07-23 [CROSS] three shipping-gate adversaries (academic rigor, senior engineer, overfitting/leakage) before conclusions ship — turns:L2555
- 07-23 [CROSS] commit means push (to a feature branch) — turns:L2607
- 07-23 [CROSS] precompute/batch everything embeddable in one pass — turns:L2536
- 07-24 [CROSS] arm-running scripts stay stable; agents don't rewrite them mid-experiment — turns:L2665-2669
- 07-25 [CROSS] the point is an academically VALID artefact, not chasing the highest number — turns:L2717
- 07-28 [CROSS] full revert: "either you absorb the knowledge or its gone" — no semi-revert — turns:L3457
- 07-29 [CROSS] agents stop estimating wall-clock time (always wrong, builds false narratives); background workers, never conversation hijacking — turns:L3577, L3848
- 08-02 [CROSS] full adversarial senior-dev audit of every step of the artefact code — turns:L4221
- 08-02 [CROSS] the canon-mining order: find everything HE actually said, across all machines, branches, logs — turns:L4334, L4372
- 08-03 [CROSS] desktop transcripts raw-copied for mining, no summarizing — turns:L4380-4391

---

## Part 5 — Layer-ambiguous statements

*(statements whose wording does not decide between the baked graph and the live
engine. The distinction is not academic: one is fixable by editing
`artefact_v1.py`, the other needs a rebuild nobody has scoped. Each carries the
test that would settle it. None is guessed at anywhere else in this document.)*

- **A1 · 06-27 — "tag-facets inform the RELEVANCE of the tag, per facet, relative to its chunk" (turns:L285).** Either a description of what the facet slots on the `HAS_TAG` edge *are* (V1-GRAPH) or a specification of how retrieval must consume them (V1-ENGINE). *Settled by:* asking whether "inform the relevance" describes a stored quantity or a query-time operation. If it is the stored quantity, the values are already what he describes and nothing is owed; if it is the operation, `STR_FACET` defaulting to `0.0` (`artefact_v1.py:219` — the facet modifier inert on a default run) is a live non-compliance.
- **A2 · 07-30 — "the whole fucking point of the tags, is guiding to the correct gold-bearing chunks" (turns:L3953, L3961).** Either a claim about what the tag vocabulary was baked *for* (V1-GRAPH) or an order about how the engine must weight it (V1-ENGINE). *Settled by:* measuring whether the baked tags can discriminate gold-bearing chunks inside a question's scope territory at all. If they can, this is an engine ordering problem. If they cannot, no engine change satisfies him and the statement becomes a retag requirement — which is the same wall the corroboration probe hit (MEMORY.md:15).
- **A3 · 07-29 — "use the graph's shape better" (turns:L3892).** Either exploit structure already in V1-GRAPH (engine traversal) or add structure to it (rebuild). *Settled by:* his answer to T5 — the 08-02 "might as well be sql-schema" rejection suggests exploit-don't-add, but it was aimed at one specific hub-node proposal, not at the general question.
- **A4 · 07-29 — "kill the 90%-air problem" (turns:L3893).** If the wasted tokens sit *between* retrieved chunks, it is a selection problem (engine). If they sit *inside* them, it is a chunking problem and only a rechunk fixes it — V1-GRAPH's chunk boundaries are baked and were never revisited. *Settled by:* measuring the gold-token fraction within retrieved chunks versus across the retrieved set. The measurement has never been run and is cheap.
- **A5 · 07-31 — "compute the clusters at build" (turns:L4033).** "At build" could mean written into the graph (a V1-GRAPH write) or computed once and cached outside it (V1-ENGINE precompute). *Settled by:* whether he requires the clusters to be queryable as graph structure. If a cached artefact beside the arm is acceptable, T11 costs nothing and needs no rebuild.
