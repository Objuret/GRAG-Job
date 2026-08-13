# CONTRADICTION MAP

Everything the user said, in date order, versus everything that contradicts it —
scoped by layer so cross-layer false contradictions never appear.

**Spine sources.** First-hand: `docs/canon/raw/user_turns_all.md` / `.jsonl` (1,304
verified turns, 2026-05-14 → 2026-08-13; cited as `turns:L<line>` = line in the
`.md` rendering. The map's own readings were made against the 803 turns extant
on 08-03; turns after that are in the corpus and not yet swept).

**`turns:L<n>` is a drifting pointer, and the drift is measured.** The `.md` is a
rendering of the whole corpus in date order, so every union that adds an early
turn moves every line after it. Citations in this map were written against the
803-turn rendering; against the current one they sit **37 lines low** through the
08-02 material (the gold-blindness quote cited `turns:L4253` is at L4290) and
**114 low** by 08-05 (`turns:L5138`, "yes, i do want the k", is at L5252). The
2026-08-13 union added no turn before 2026-08-05, so it moved nothing that was
not already moved. **Resolve a citation by its quoted words, never by its line
number**, and re-derive the numbers before trusting any of them. Second-hand: `docs/canon/raw/desktop_docs_record.md` (quotes
recovered from agent docs; always marked **second-hand**). State evidence:
`docs/canon/raw/git_record.md`, `docs/canon/DESIGN_HISTORY.md`, and the live
tree. Agent-surface evidence: the actual file and line, quoted. Code is cited by
file and symbol, never by line number — the convention `v3/CONSTANTS.md` sets and
`check_constants.py` enforces.

**What the corpus cannot show — read this before treating an absence as evidence.**
`tools/canon_extract.py` discards a user record the moment it carries a
`tool_result` block, before any text is extracted (`classify`, the `tool_result`
rule at lines 118-121) — 2,530 records in the laptop pass
(`docs/canon/raw/EXTRACT_REPORT.md`). The harness delivers an answer to an
**AskUserQuestion** prompt as a tool result, so every ruling he gave that way is
absent from `user_turns_all.md` / `.jsonl` no matter how forcefully he made it.
**"No turn found" therefore does not mean "he never said it."** Where a ruling
reached the project that way, this map quotes the transcript record and names its
session file, record line and UTC timestamp under
`~/.claude/projects/C--Coding-exjobbet-GRAG-Job/`. There are four such records in
the whole project (2026-07-30T23:10:40.745Z, 2026-08-02T09:32:26.648Z,
2026-08-05T11:39:56.193Z, 2026-08-05T13:48:50.008Z).

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
  (1668 lines) and `v3/pipelines/artefact_v1_det.py` (264 lines) — new retrieval
  code written inside v3 that queries V1-GRAPH (`DATABASE` defaults to
  `herb-eval`: `artefact_v1.py` · `DATABASE`). Freely changeable. His July–August design
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
| Spine statements considered, first-hand (of the 803 turns extant at the 08-03 pass) | ≈137 |
| Spine statements considered, second-hand (desktop record) | ≈95 |
| **Contradicted statements (Part 1)** | **4** |
| — by layer of the user's statement | CROSS 2 · V1-ENGINE 2 |
| — carrying a type-(a) self-reversal | 0 |
| — carrying type-(b) built-state evidence | 4 (V1-ENGINE 3 · CROSS 1) |
| — carrying type-(c) agent-surface claims | 1 (CROSS — entry 3) |
| Possible tension, judgement needed (Part 2) | 15 entries covering 16 numbered tensions (T1+T2 share an entry; T8 retired). By the layer named first: V1-ENGINE 6 · CROSS 4 · V1-GRAPH 4 · V2-DESIGN 1 |
| Cross-layer near-collisions dissolved by scoping (Part 3) | 14 |
| Standing (uncontradicted) statements (Part 4) | 84 subject-lines (closely-related turns merged) |
| Layer-ambiguous statements (Part 5) | 5 |

**Surviving collisions by what fixing them requires:** engine change 3 (entries
1, 2, 4) · doc correction 1 (entry 3) · **user ruling 1** (entry 1, on which
gold-100-swept values may stand) · **graph rebuild/retag 0**. No contradicted statement in Part 1 is
trapped in the baked graph. The three problems that *are* baked — oracle residue,
which facet set is real, and the slug-polluted tag vocabulary — sit in Part 2 as
**T3**, **T9** and **T15**, where they are tensions awaiting his judgement rather
than contradictions, and where the only available remedy is a rebuild nobody has
proposed. **T15 is the one he found himself**, on 08-02, and it is what the
canon-mining order came out of 80 minutes later.

**The most consequential collision:** entry **3** — surfaces written *after* his
07-26 "k=50 does not mean the same for all arms, and thats retarded" headline the
unmatched-unit cross-arm numbers as the lead. The memory headlines are corrected, and
T10 closed 2026-08-05: the statistics are reported as measured, under the conditions
they were measured under, and no agent chooses what they mean.

---

## Part 1 — Contradicted statements

*(ordered by date of the user's statement; each contradiction typed, dated, cited, layer-matched)*

### 1 · 2026-06-30 — [CROSS] — "by NOT overfitting it to the specific dataset we have"

**His words** (2026-06-30, turns:L340):
> "I wanted to discuss how to actually continue building the artefact in a creative innovative way that actually kinda fits my original concept (even if just in spirit), and by NOT overfitting it to the specific dataset we have."

Restated 07-15: "it's VERY important that this is not overfitted to the specific dataset because you make it sound like you are doing exactly that" (turns:L721). Restated 07-22: "we obviously cannot overfit, i want a smart AND clean solution" (turns:L2320).

**What the charge is.** His own framing: the agent had the ground truth available and
started showing signs of fitting to it. The mechanism is access; the fitted constants are
what the access produced.

- **(b) · 2026-07 → 08-02 · V1-ENGINE.** What was tuned against gold-100 is entirely engine-side: the July experiment chain selected engine mechanisms by gold-100 recall_id (detPOOLCUT/detCURVEK/detADMIT/… — turns:L3424-3437), and the August sweeps (WTAG0/2/4, TAGINFORM, WG_GUIDE — `v3/output/`) selected the engine's combine weights and modifier strengths (`artefact_v1.py` · `W_TAG` / `W_DESC` / `W_SCOPE`, reading `HERB_W_TAG` / `HERB_W_DESC` / `HERB_W_SCOPE`; and the `STR_*` family reading `HERB_STR_*`) on that same gold-100. His own 08-02 verdict names the violation: "not only did i mean you are forcing an architecture BASED on retrieving the gold based on the questions, it also feels like you are focusing on it" (turns:L4269).
- **Bound of the charge · V1-GRAPH is not exposed.** The graph was tagged and weighted before gold-100 existed and has never been retagged, so no baked value was fitted to the eval set. The overfitting exposure is exactly the set of engine tunables above — which also means it is fully removable.
- **Bound of the charge · no swept value reached a default.** Across the 20 numeric tunables and flags of `artefact_v1.py` — `W_TAG` / `W_DESC` / `W_SCOPE`, the `STR_*` family, `K_LEVELS`, the `GUIDE_*` family, `AGG`, `NORM`, `NORM_SCOPE`, `KNN_OVERFETCH`, `CURVE_WALK` — `git log -p --follow` shows no assignment line ever removed or modified: every one stands at its first-commit value (`v3/CONSTANTS.md`, artefact preamble, which names the same 20 and states the same bound). The sweeps ran around the defaults and never fed back into them, so they are evidence *about* those values, not evidence *for* them. Model ids are outside this claim (`INTERPRET_MODEL` has carried three values). The exposure is therefore the mechanism selections, not the shipped numbers.
- **The access is cut.** He stated the constraint on 08-02 — "honestly, you should not have the questions/gold available to you, there is 0% good that can come out of taht" (turns:L4253), "can we make sure \"you\" never see them? that you only get the variable/pointer to it?" (turns:L4257) — and it became a rule in the tree at `bb95e4b` (2026-08-05), which is the only commit that touches the word in `CLAUDE.md`. It is a CLAUDE.md hard rule (`CLAUDE.md:103-112`) and a hard rule in each designing agent — retrieval-scientist, maths-algorithmist, v3-coder, logician: `v3/data/questions.jsonl` and any run's `arm_outputs.jsonl` are closed to them, runs are specified by pointer, and results come back as `eval_results.jsonl` metric values keyed by question id and type. results-analyst and eval-statistician keep full access; they report and design nothing.
- **Layer & fix:** what remains is the residue — the constants selected while the access was open. **Engine change** (re-derive them blind, or reset them), on a **user ruling** about which swept values may stand.

### 2 · 2026-07-15 — [V1-ENGINE] — "i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something"

**His words** (2026-07-15, turns:L779):
> "i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something, i kinda like knn clustering for relevance spheres for example for grounding, k, retrival etc etc"

Same day, on the arm as found: "2. 10? fucking why just 10? … Honestly, no fucking wonder we get shit results, this is an abomination" (turns:L729-733). Restated 07-21: "why did you make up a number like 200 here?" (turns:L1984). Restated 08-02: "arbitrarily decided hard limits, like the 64 chunk limit, i bet there is way more than 1 of these dumb limits lying around not beeing seen" (turns:L4217).

- **(b) · 2026-07-15 → HEAD · V1-ENGINE.** The arm that shipped and still ships is built on unbased constants, all of them in engine code: `K_LEVELS = (8, 16, 32, 64)` (`v3/pipelines/artefact_v1.py` · `K_LEVELS`), `GUIDE_TAU` default 0.01 (`artefact_v1.py` · `GUIDE_TAU`), and the value system the 07-22 adversarial panel condemned as an "ordinal staircase w/ 12:5:1 door bias + prescription" (MEMORY.md:38). `v3/CONSTANTS.md` puts the scale on it: 313 constants inventoried, 161 marked `unknown` — no evidence for the value anywhere. The 64 he flagged on 08-02 is `K_LEVELS[-1]`, the widest level of the same tuple. Two constants this entry used to cite are **not in the shipped tree**: `POOL_FETCH=256` (turns:L3329) and `TAG_MIN_SIM=0.78`, the borrowed number that killed the `detTAGBAR` experiment outright — "You correctly called out: random/stolen number" (turns:L3312-3318). Both are quoted from a pasted agent report on the July `det*` thread he ordered fully reverted on 07-28; neither name appears anywhere in `v3/**/*.py` or in `v3/CONSTANTS.md`. They are evidence about that thread, not about HEAD.
- **(b) · same layer, the other direction.** The one number he *did* demand be based on something — per-query K from his cluster concept — exists but is off in the shipped default: the clustering decides K only under `HERB_CURVE_WALK` (`artefact_v1.py` · `CURVE_WALK`), and the per-facet cluster guide only at `HERB_STR_GUIDE > 0` (`artefact_v1.py` · `STR_GUIDE`, default `0.0`). A default run takes the caller's flat k. In the flat regime the clustering is not merely off: the tag pool is clustered and the level chain built per part per question, then discarded unopened, because the widening loop's budget test is already satisfied when it is first reached.
- **His ruling (2026-08-05): K comes from the clustering.** *"yes, i do want the k, not the made up bullshit"* (08-05 13:54, turns:L5138), answering exactly this. Per-query K derived from his clustering belongs on the load-bearing path; `K_LEVELS` as the value model and budget does not. It does not settle **R3** (clusters computed at build or per query), and it does not adopt the existing curve-walk implementation — whose own stop rule is `_gap_break`, a two-sigma spacing test on merge-height gaps whose threshold, three-gap warmup and noise floor are all `unknown`, and which the 07-22 panel measured as carrying almost no order information (shuffled gaps produce 60.1±4.1 stops against 67 real). A K decided by a made-up stop rule is the thing he is ruling against, not an instance of what he asked for.
- **Layer & fix:** **engine change** on both counts, and on the ruling. Every constant named here is a module-level literal or an env default in `artefact_v1.py`; none is baked into V1-GRAPH, so replacing them with derived quantities needs no rebuild. What the ruling needs before code: the walk running at all (**OPEN_DECISIONS 21**) and a stop rule that is itself derived — where whether such a rule exists on these objects is unsettled in its own right (**OPEN_DECISIONS 16**).

### 3 · 2026-07-26 — [CROSS] — "k=50 does not mean the same for all arms, and thats retarded"

**His words** (2026-07-26, turns:L2901):
> "yeah but no matter what we do, the issue is k=50 does not mean the same for all arms, and thats retarded.. how did the true v1 runs measure it?"

Context, both directions: the unit mismatch was already measured 07-12 — artefact k=50 mean 167,785 retrieved chars / 309.7 context ids vs vector 23,233 / 50.0, with the agent doc itself concluding "A budget-matched rerun is required before using it comparatively" (DESIGN_HISTORY.md:2456-2469). And the identical-k design was originally his own: k = one global ceiling per arm, "the token-cost gap between arms is the experiment" (06-25, second-hand, desktop_docs_record.md:626). The 07-26 statement is him overruling that earlier frame after seeing what it does.

- **(c) · MEMORY.md, written after the ruling — since corrected.** *(Memory files are outside git, so the correction date is unverifiable; the corrected state is verified on disk — no run number of any kind survives in the index.)* The auto-loading memory index headlined the unmatched-unit numbers as the finding: "artefact 0.594 vs vector 0.112 / lucene 0.074 on 100 untouched type-balanced questions … **the lead generalizes**" (entry dated 07-30 — four days after his ruling); "artefact leads **all valid metrics** (recall_id 0.64 vs 0.09/0.11)"; and, in a third entry that corrected neither, "headline 0.64-vs-0.09 is ~85% unit artifact (matched-budget ~1.8× is the real lead)". A surface that knew the number was ~85% unit artifact and still led with it was asserting what he ruled invalid. The three entries are deleted and the index carries no run number; the wording is kept as the audit's finding at `CANON_AUDIT.md` 4.6–4.7, and every number now sits in `v3/output/DATA_README.md` under the unmatched-unit rule. What the correction does not settle is which framing ships — T10.
- **(b) · the fix died with the revert.** The evidence-cap / matched-token-budget harness work existed only inside the thread he ordered fully reverted on 07-28 and did not survive (turns:L3236-3240; DESIGN_HISTORY.md:3310-3317). That part is his own choice ("either you absorb the knowledge or its gone", turns:L3457) — recorded here as state, not charged as a violation.
- **Layer & fix:** **doc correction**, done — no surface headlines the unmatched-unit numbers, and `v3/output/DATA_README.md` carries every cross-arm figure under the rule. There is no framing decision behind it: T10 closed 2026-08-05 on his ruling that the statistics are reported as measured and agents do not interpret them. The measurement side, if he wants it back, is a **CROSS harness change**, not an engine or graph one.

### 4 · 2026-08-01 — [V1-ENGINE] — "tags are supposed to INFORM/weight the chunks"

**His words** (2026-08-01, turns:L4098):
> "ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE ffs.. tags are supposed to INFORM/weight the chunks"

Lineage of the same rule, binding on this layer by his own statements: the no-gates ruling of 07-15 ("gate? wtf? why have a gate? … hard filter seems insane, much better to use rankings", turns:L729), said about this arm; and "the whole fucking point of the tags, is guiding to the correct gold-bearing chunks" (07-30, turns:L3953, said twice L3961). The earliest form — "NO hard filters anywhere" (05-31, second-hand, desktop_docs_record.md:182) — is V2-DESIGN and is lineage, not the governing citation here.

- **(b) · 2026-08-01 · V1-ENGINE.** What shipped that same day in `6730d13` ("tags-first retrieval regime") is a tag-**reachability** gate. The code said so in its own comments — read them in the shipping object, `git show 6730d13:v3/pipelines/artefact_v1.py`: "`HERB_TAG_ADMIT` — the tag layer decides selection, the other paths corroborate" (the `TAG_FIRST` block) and "0 is a hard filter — unreached chunks only backfill an under-filled k, ordered by their ungated score" (the `TAG_ADMIT` block), with `TAG_ADMIT = _env_float("HERB_TAG_ADMIT", 0.0)` — so on a `HERB_TAG_FIRST=1` run the admit coefficient annihilated unreached chunks rather than penalising them, in the `if TAG_FIRST:` branch of `_retrieve` whose own comment names it "the combine gate". Mitigating only in blast radius: the flag was opt-in and defaulted off. The 08-02 adversarial review reached the same verdict from the data: "HERB_TAG_FIRST is a category error — delete it. Tags weight, they don't select. It also silently bundles a walk restructure with the gate, so its numbers are unattributable anyway" (pasted by him, turns:L4167).
- **Cross-layer note, not a citation.** `v3/artefact/DESIGN.md:782-791` states the rule in full ("No hard filters anywhere in ranking … Facets always *order*, never *filter*") — but that document is V3-NATIVE design canon, so it is lineage rather than evidence. The rule binds V1-ENGINE because he said so on 07-15 and 08-01, not because a V3-NATIVE doc says it.
- **Trigger note (not a defense):** his 07-30 order "we make sure it is informed by the tags first then" (turns:L4005) is the phrase the builder turned into a gate; his 08-01 statement is the clarification that "first" meant weighting priority, not membership. The build-side collision is real either way — the 07-15 no-gates ruling predates the build by two weeks.
- **What he actually said, and what is the previous agent's wording.** His own statement is a **question**, 08-05 07:27: *"well the design is to have the tags/weights to be PART of the routing to the final bag of chosen chunks, right?"* (turns:L4902). No turn and no AskUserQuestion record carries a ruling that the gate goes; the flat declarative — *"tags and their weights are PART of the routing to the final bag — they route and weight, they never exclude"* — first appears in an agent-written handoff prompt he pasted on 08-05 09:33 (turns:L5048), which listed the deletion as "needs his go before you touch code". His go is *"go on then"*, 08-05 11:32 (turns:L5134), and the deletion shipped in `bb95e4b` (2026-08-05 13:08). So the deletion is authorised and done; the sentence stating the design principle is the previous agent's phrasing of his question, not a quoted ruling. The reading behind it: the tags and their weights are *part* of the routing to the final bag of chosen chunks — which is what the default already does: the areas are clusters over the tag pool, so the tag layer finds most of the candidates, and the tag score is one of three summed contributions. `HERB_TAG_FIRST` does not extend that design, it replaces it, promoting one of three contributors into the gatekeeper. Tags route and weight; they never exclude.
- **Layer & fix:** **engine change, shipped in `bb95e4b`** — `HERB_TAG_FIRST`, `HERB_TAG_ADMIT` and the gated branch in `_retrieve` are gone. `TAG_FIRST`, `TAG_ADMIT`, `HERB_TAG_FIRST` and `HERB_TAG_ADMIT` are zero hits across `v3/**/*.py` and absent from `v3/CONSTANTS.md`. Nothing is queued.

---

## Part 2 — Possible tension, judgement needed

*(not counted as contradictions; listed so nobody silently resolves them either way)*

*T8 is absent on purpose. It recorded a `.venv` question — 07-16 "i am pretty sure we ended up NEEDING the fucking venv" (turns:L1013) against a memory line calling the venv dead — which `docs/ENVIRONMENT.md:22-29` now answers outright, and it was retired at `bb95e4b`. The surviving numbers are not renumbered, because other documents cite them.*

- **T1+T2 · the k sweeps were run as truncations, and only two arms got a valid one.** 06-27: "so not 5,10,15,20,30,40 ?" → "i want to do the non-llm metrics, for those k i just wrote" (turns:L221-225). 07-20: "the k50 runs you know, do all 3 as k=25 also, now, doit (**not as an iverwrite, as fresh runs**)" (turns:L1654). What was produced: lucene and vector at k = 5, 10, 15, 20, 25, 30, 40, 50 — every depth he named, k=25 included — recorded in `v3/output/DATA_README.md`. Two things depart from the order. They are **re-slices of the k=50 runs, not fresh runs at each depth**, which is what he explicitly asked against. And the **third arm has no valid curve at all**: the artefact k=50 run carries no `meta.chunk_ids`, so truncating it discards each chunk's own ids and measures a truncated id list — its `__k25` slice read 0.1309 against the parent's 0.6363 for that reason alone. The only sound artefact depth curve is on 10smoke (n=10). **Fix:** a gold-100 artefact depth curve needs fresh runs per depth, or a k=50 run that records `meta.chunk_ids` — an **engine/harness change**, cheap, retrieval-only. Whether re-slicing satisfies "as fresh runs" for the two baselines is his call. [V1-ENGINE ↔ CROSS]
- **T3 · oracle residue in the baked graph.** His quarantine canon is absolute ("we just don't fucking include the eval part in the dataset", 06-11, desktop_docs_record.md:875; "DONT INCLUDE THE FUCKING EVAL FILES FOR THE PROBE TO EVER SENSE", 06-14, :945) — and it is V2-DESIGN canon, written for the corpus V2 was going to derive. The graph every reported artefact number comes from is V1-GRAPH, which `graph_store.py`'s own docstring calls "the superseded, **oracle-contaminated** v1 build" (git_record.md:1086-1096), He himself was unsure 08-02: "this is not the db we did the 'purge' on, right?" (turns:L4302). The 07-28 audit measured the exposure and split it three ways: **no direct answer-text leakage** in any run directory; but **the arm resolves chunk text from full raw HERB at answer time** (oracle in-file), so quarantine rests on `herb-eval` locator discipline rather than on v3 code; and two soft vectors that remain unverified — the tag vocabulary was partly minted by a tagger that read the oracle, and `relevance_to_file` is carried over from the contaminated build. **This is the sharpest consequence of the layer split: the residue, if it is there, is baked.** No engine change can remove it, and the July purge stripped content, not tagging decisions. The choices are therefore only two — accept and declare the V1-GRAPH provenance, or stop shipping artefact numbers — and both are his. [V1-GRAPH ↔ CROSS]
- **T4 · traceability demand vs provenance practice.** 07-16: "the data about the builds ETC is important for traeability, reproducibility etc, academic purposes" (turns:L925). Standing against it: "Provenance … no seed, no git-sha" recorded as a *decision* in the agent-written README (v3/README.md:130-131; git_record.md:1119-1173), manifests carrying no git sha, and the two load-bearing builds shipped under tooling commit titles ("graphify-out (49 files)" = `artefact_v1.py`, `69115e0`; "graphify-out (533 files)" = the tagger, `8a640bf`; git_record.md:228-230, 191-199). No record shows him deciding the no-git-sha rule. [CROSS]
- **T5 · hard fields as nodes: two layers, not one reversal.** The positions read as a three-way flip only if V2-DESIGN and V1-GRAPH are merged. Split, they are two separate questions. *Concept, V2-DESIGN:* attributes (06-12, second-hand: "perhaps it's smarter to just have shit like that as attributes on chunks", desktop_docs_record.md:878) → nodes/edges (06-30/07-01: "i really think this should be nodes or edges … half the strength of of a graph is beeing able to route/search based on relationships", turns:L446), explicitly aimed away from the existing graph ("Dont think herb, think dataset agnostic concept", turns:L454). *Implementation, V1-GRAPH:* the hub-node build proposed onto herb-eval and rejected 08-02 ("dude, you are turbo-overfitting now, AND doing shit that might as well be sql-schema", turns:L4249). The 08-02 rejection is a rejection of restructuring the baked graph — which would have been a **rebuild** — and says nothing about whether the V2-DESIGN concept survives for V3-NATIVE. That narrower question is the only thing open.
  **Ordered built, 2026-08-12, and it is now a database.** *"wouldnt it be way more reasonable to make those fields into nodes to get actual use of this beeing in a graph?"* (08-12), with his security boundary asked in the same breath — *"yeah, what raw data would actually enter the graph tho? can we still claim to be \"secure\" if so?"* (08-12) — answered by ids-only: identifier strings, role labels and provenance pointers enter, names resolve outside the graph from the raw directories. Then the build order: *"well then, if you feel this is the way, construct another db using this, aka use the current as template and \"fix it\" and add these things, right?"* (08-12). All three are in the corpus at the 2026-08-13 union.
  **Both rulings stand, dated.** The 06-12 closed spine (`Source → File → Chunk → Tag`, hard fields as attributes) is his, and it governs `herb-eval` — which is untouched. The 08-12 order is also his, and it governs `herb-eval-v2`, a copy built from `herb-eval` as template (`v3/output/graph_build/herb-eval-v2/build_manifest.json`: `source_database` herb-eval, `target_database` herb-eval-v2) carrying Person 5,233 · Product 30 · Channel 294 nodes over INVOLVES 32,281 · MENTIONS 9,634 · IN_PRODUCT 4,808 · IN_CHANNEL 2,669 edges. **Neither retires the other**: they are two databases and two dates, and no agent may read the second as deleting the first. What is not ruled is whether the new shape is the shape — the 08-12 design doc says the sign-off makes it canon and records that it has not been given. [V2-DESIGN ↔ V1-GRAPH]
- **T6 · thesis-done vs thesis-live rationales.** 06-14 second-hand: "drop the fucking thesis... it's done, this is post-thesis work" (desktop_docs_record.md:944); 07-22 first-hand: "thesis? wtf? we are building the fucking artefact here" (turns:L2336). Two live memory files justify rules by the opposite frame: "This is the user's master's thesis; the concepts ARE the contribution" (`feedback_user_concepts_are_canon.md:24-25`); "This is the user's exjobb (master's thesis) project… it reflects on their academic work" (`feedback_commit_style.md:9`). Probably repo-identity vs work-framing wording, not a real collision — but the surfaces argue from the frame he rejected. [CROSS]
- **T7 · cost-blind vs cost-first.** 06-18: "YOU do not care about cost here, 0 fucks given… only for me" (desktop_docs_record.md:952; frozen as desktop `no-cost-estimates.md:10` "Cost … must carry ZERO weight"). July: cost math out loud before every claude-* run (`feedback_judge_run_cost_math.md`, after the 07-17 usage burn, turns:L1300). Likely different resources (NIM dollars then vs his subscription window later) — but the two rules sit in the two machines' memories as opposites, unreconciled. [CROSS]
- **T9 · which facet set is real, and what it would cost to change.** He disowned the v2 five ("assistant research synthesis… never hard-approved… it hollowed the tag", 06-25, DESIGN_HISTORY.md:1752-1850); the 06-27 recovery ("content profile") renames three of the four condemned v1 facets back (git_record.md:1354-1377). Surfaces assert three different "settled" sets: topic/entities/activity/temporal/evidence (`project_terminology_canon.md:22`), topic/process/stance/communicative-function/time (`desktop_memory/facet-semantic-framework.md:119`), and "topic is not a facet" (`desktop_memory/tag-facets-vs-routing.md:19`). **The layer split answers most of it.** The set actually in force is V1-GRAPH's, baked as a five-slot array on every `HAS_TAG` edge and read positionally — `ALL_FACETS = ("topic", "entities", "activity", "temporal", "evidence")` (`artefact_v1.py` · `ALL_FACETS`) indexing `r.w_facets[fi]` (`artefact_v1.py` · `_AREA_CHUNKS_CYPHER`). The other two sets are V2-DESIGN and V3-NATIVE design text that never reached a graph. Changing the operative set is a **retag of every edge**, not a decision. What is genuinely open is only which set V3-NATIVE should be built on. [V1-GRAPH ↔ V2-DESIGN]
- **T10 · CLOSED (2026-08-05) — there is no framing decision.** His ruling when asked which reading ships, in full: *"what the fuck are you talking about? framing? just the fucking stats, YOU DONTY INTERPRET THE RESULTS"*. It came through an **AskUserQuestion** answer and is therefore **not in the turn corpus** (see *What the corpus cannot show*); the record is `2d5a9560-73e8-476c-99fb-0bff3d735c76.jsonl` line 674, 2026-08-05T11:39:56.193Z, answering the question *"Which framing of the matched-budget result ships (map T10)?"*. The measured quantities are reported as measured, with the conditions they were measured under; no agent picks a headline, a lead sentence, or which of two descriptions of one measurement is the better story. **Anything that reads as choosing what a number means is out of scope for every agent and every surface in this repo.** What `v3/output/DATA_README.md` records, recomputed from disk: at a matched 500-id budget `artefact_v1_det` 0.7339 and `artefact_v1` 0.6363 against vector 0.4100, hybrid 0.3883, lucene 0.2742, with the paired delta, its 95% CI and W/L/T beside each; the id budget matched exactly and the character budget not; and at a common k=50 the same arms read 0.7339/0.6363 against 0.11/0.09, under the unmatched-unit rule his 07-26 ruling imposes. Both readings stand in the record as what they are. [CROSS]
- **T11 · clusters: pre-computed or prompt-relative?** 07-21: "i mean, the clusters are based on the actual shit from the prompt, so you cant pre-run it..?" (turns:L1988) vs 07-31: "i THINK it might be smartest to compute the clusters at build, and then weight-adjust them based on the query's facet-values.. i THINK, reflect on this with me" (turns:L4033). DESIGN_HISTORY.md:3143-3174 marks the reversal and rules "neither may be treated as settled" — both were exploratory, neither is a decision to hold him to. Worth noting for the cost of the answer: both options are **engine-side**. Clustering V1-GRAPH's existing `t.emb` vectors and caching the result is a precompute, not a graph write, so neither branch implies a rebuild. [V1-ENGINE]
- **T12 · does the no-numbers rule bind the live engine?** "The model emits no numbers, ever" is V2-DESIGN / V3-NATIVE canon (06-11, born from V1's failed weights: "it took so fucking long to get it right and it still didn't work at all", desktop_docs_record.md:301, :860; CLAUDE.md:216; MODEL_CONTRACTS.md:33-34). It reaches two different places. V1-GRAPH's baked `w_chunk` / `w_facets` were model-emitted at V1-ORIGINAL index time — unreachable without a retag, and native to that layer besides (Part 3, D1). But V1-ENGINE's pass-2 interpreter emits facet values 0.0–1.0 at query time (`artefact_v1.py` · `_PASS2_SYSTEM`, the pass-2 prompt that demands a 0.0–1.0 score per facet; parsed and clamped in `_validate_scores` and `_interpret`) in code written in July, inside v3, after the rule was posted — freely changeable, and the arm he ruled is the system under test. Whether a V2-DESIGN rule governs V1-ENGINE has never been decided; the adversarial panel raised it as an open canon conflict for him (`project_adversarial_panel_verdicts.md:64-69`). If he says yes, it is an **engine change**; the baked half is untouched either way. [V1-ENGINE ↔ V2-DESIGN]
- **T13 · which math combines the weights — product or sum. Held open by his ruling.** 05-25, second-hand: "specifically multiplication i am not sold on", multiplication called "too brutal. Tangential chunks with strong tag fit should still be retrievable, just ranked lower" (desktop_docs_record.md:97, :101). The outer combine already works that way — tag, desc and scope are a weighted sum over the union (`artefact_v1.py` · `_retrieve`, the `totals[cid] += W_TAG/W_DESC/W_SCOPE * s` accumulation), so no signal annihilates a chunk. Inside the tag term the three baked V1-GRAPH weights multiply the normalized base: `tag_score[cid] = nb * _mod(ft, STR_FACET) * _mod(wc, STR_WCHUNK) * _mod(rel, STR_RELEVANCE)` (`artefact_v1.py` · `_retrieve`), each factor strength-graded through `_mod` and clamped at 0 (`artefact_v1.py` · `_mod`), so at strength 1 a baked 0 zeroes that chunk's tag term while the sum still carries its desc and scope support. The Cypher multiplies one level down too (`artefact_v1.py` · `_AREA_CHUNKS_CYPHER`). **His ruling (2026-08-04, first-hand and in the corpus): canonically undecided — which sort of math combines the weights is what the experiments are testing.** *"this was about which sort of math would be used to combine the weights"* (16:25, turns:L4721), then *"mark that down as canonically undecided because we are testing what is the best solution there"* (16:33, turns:L4725). Neither form may be recorded as decided, in either direction. [V1-ENGINE]
- **T14 · which leg is the reported artefact configuration.** 07-29: "i want to fucking decide which artefact that is even the baseline here, all agents keep fucking reverting to the \"det\" arm, is there something in some documents that says so?" (turns:L3501) — nothing did. The det leg entered without his order; his first contact was surprise: "oh.. wait a fucking minute.. no interpreter!?.. as in we are skipping the entire fucking massive step we have had all the time? why?" (07-25, turns:L2833). **On the word "baseline", what he actually said is a question, 08-05 06:30:** *"until  decided upon, there is no \"baseline\" artefact, a comparable baseline are the vector and lucene arms, no?"* (turns:L4814) — conditioned on "until decided upon" and ending in "no?". The flat declarative in circulation — *baseline means lucene and vector; `artefact_v1.py` and `artefact_v1_det.py` are two configurations of the system under test, neither is a baseline, no measurement of either is a pass-bar* — is the **previous agent's wording**, first appearing in the handoff prompt he pasted on 08-05 09:33 (turns:L5048). That same handoff records the leg question as UNDECIDED. **Carried by a prompt-box answer, recovered 08-09:** *"Report both, decide nothing"* — 08-05 11:35, session 2d5a9560, now a turn in `raw/user_turns_all.md`. The extractor had dropped every prompt-box answer as a tool result until 08-09; fifteen were recovered, so this file's head-count of four such records is stale, and the remaining fourteen await absorption. Both legs exist and work; no code or graph change is implied either way. No surface may name one as *the* artefact number, and any figure quoted for one names its leg. The evidence behind them is not symmetric and that asymmetry is reported with them: on gold-100 the det leg leads by 0.0975, CI [−0.1382, −0.0569] paired, while every held-out and every judged number the project holds comes from the interpreting leg (`v3/output/DATA_README.md`). [V1-ENGINE]
- **T15 · the tag layer is polluted, and it is baked.** The `herb-eval` tag vocabulary carries the source's own field values as tags. Measured (`state:2026-08-02-corpus-facts.md`): **2,836 tags — 14.4% — are verbatim slugs of source field values**, 1,636 of them PR titles and 1,199 URLs, at degree 1.28 against 3.81 for the rest; **2,881 — 14.6% — contain a digit** (dates, CAGR, money, latency); and **the tightest embedding cluster in the whole tag space is n=488 at intra-cosine 0.94, a bin of `github_pr_NNNN`**, with consecutive PR ids embedding at 0.9925. It is not spottable by eye — `dynamic_table_structures` is a PR title. Re-derivable: slugify `prs[].title` and `urls[].link` and set-intersect against `MATCH (t:Tag) RETURN t.name`.
  **His.** He found it himself: *"Eh.. what..we have tags with that fucking syntax? For real?"* / *"but those you just showed me.. those are tags!?"* (08-02, turns:L4290, L4298), then *"so.. you can actually see the fucking canon for it, and itt's still constructed like this … but this is a retagged variant also? this is not the db we did the 'purge' on, right?"* (turns:L4302). The answer to that question is no: the July work stripped content and re-embedded the semantic layer, and **slug-tags were never in the purge's scope** (`state:2026-08-02-corpus-facts.md`). The graph has never been retagged.
  **It breaches his own standing rule.** "the actual content should never exist in the graph at all" (07-06, turns:L538) — Part 3, D3, records V1-GRAPH as compliant on chunk *content*, and it is; the tag layer is where the copies survive, and D3 does not cover it.
  **Why it is load-bearing now.** Any rule that reads structure out of tag-to-tag distance finds the slug bins before it finds evidence, because they are the strongest structure in the space. That is what closes the derived-K design at `OPEN_DECISIONS` 16, and the 07-22 panel had already measured the symptom — two different CoachForce questions producing an identical chain and an identical K=5. The only in-engine mitigation is excluding slug or digit tags from the pool, which is a hard filter on the tag layer and collides head-on with Part 1 entry 4 and the 07-15 no-gates ruling.
  **Measured 2026-08-11 — the first verbatim read of the vocabulary** (`state:2026-08-11-tag-vocabulary-inventory.md`, computed from the derived facet cache, cross-checked against live `herb-eval`). The 08-02 class is confirmed and bounded: 2,505 tags (12.7%) are PR pointers in four coexisting formats (`github_pr_302` / `elasticsearch_pr_1758` / `pull_request_4977` / `https_github_com_salesforce_castaix_pull_1`), 1,842 (9.3%) URL-shaped, 451 whole PR-title sentences, 169 decision-sentences, 95 date tags — nearly all at degree ~1.3. The extraction is otherwise clean: all 19,716 strings lowercase snake_case, zero duplicates after normalization, zero hashes or truncations; the head is `salesforce` (534 chunks — 11% of all chunks), `tensorflow` (428) and 17 synthetic product names; 25.7% of tags are exact substrings of other tags. The 08-02 digit figure (2,881) reproduces exactly.
  **His position, 08-11** (in the corpus at the 2026-08-13 union): shown the composition — *"not sure what your point is wit this at all, doesnt this seem to reflect the actual corpus?"*, then *"update the info based on this then"*. The vocabulary is a faithful extraction of a corpus that itself consists of PRs, URLs, decisions and dates. The field-value copies are still copies — the 07-06 breach above stands as written — and the slug-bin embedding geometry (n=488 at 0.94) is unchanged by the re-read; what the verbatim look removes is corruption of the tagger's output as the default explanation for the facet term's flatness. The measured suspects sit a level up: the facet estimators (four of five collapse to per-tag or per-chunk constants) and the query-side demand read (`state:2026-08-11-relevance-weight-demand-and-facet-measurements.md` §2–3).
  **Layer & fix:** **graph retag** — V1-GRAPH, so no retrieval-code edit reaches it, and it is the third baked problem beside T3 and T9.
  **Acted on 2026-08-12, in a copy, on his order** — *"including removing the pr-titles and url's"* (08-12, in the corpus at the 2026-08-13 union). `herb-eval-v2` is a copy of `herb-eval` with the pointer class deleted at vocabulary level: **4,111 tags and 5,470 HAS_TAG edges removed** (PR-title slugs 1,636, link slugs 1,200, `github_pr_NNNN`-shaped 2,370, URL-shaped 1,846 by class, overlapping), leaving Tag 19,716 → 15,605 and HAS_TAG 67,913 → 62,443, with **0 chunks emptied** and **0 chunks left without a tag** (`v3/output/graph_build/herb-eval-v2/build_manifest.json` · `steps.cleanup`; the predicate and the full removed list are in the manifest under a sha256). It is a removal, not a retag: the surviving 15,605 tags are the originals, minted by the same tagger. **`herb-eval` is untouched and every standing artefact number still comes from it** — a figure from one database is never a figure about the other. What is open is still his: whether the removal is the answer, whether a real retag follows, or whether the tag layer's provenance is declared and accepted. [V1-GRAPH]
- **T16 · most of the corpus never becomes a chunk, and nothing records that as a decision.** Measured (`state:2026-08-02-corpus-facts.md`): **7 of 38 leaf positions in the HERB mapping key are declared content — 42,774 of 304,253 leaf instances, 14.1%.** The other 85.9% is present in the raw files and reaches no chunk, so it is unreachable by any arm that queries the graph. Re-derivable: census `v3/data/corpus/Salesforce__HERB/**` against the `content:` entries in `v3/artefact/keys/Salesforce__HERB.yaml`. Two findings in the same record bound it: the key declares 6 sections and the code reads only `content` and `conversation` — `sources`, `directories` and `id_spaces` are read by zero lines — and all 3 metadata files produce 0 chunks.
  **Why it is a tension and not a defect.** Selecting which leaf positions carry retrievable content is a real design choice, and 14.1% may be the right one. What is missing is any record that it *was* a choice: no turn of his selects it, and no doc states it as decided. It is the shape of the thing he objects to — *"i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something"* (07-15, turns:L779) — applied to coverage rather than to a constant.
  **What it bounds.** Every recall number the project reports is against gold citations that live in the raw files; if a gold citation's text sits in one of the 31 undeclared leaf positions, no arm querying the graph can reach it and the ceiling is not what the id arithmetic says. Whether that happens, and how often, is unmeasured.
  **Layer & fix:** **graph rebuild** if the declared set changes — V1-GRAPH, chunking is baked. A **user ruling** on whether 14.1% coverage is the intended design; the measurement to bound its cost is cheap and has never been run. [V1-GRAPH]
- **T17 · the engine sums parallel paths; his stated concept is a chain. He named the gap himself on 2026-08-13.** Told the retriever scores four paths, he answered: *"you say 4 paths, what is that even, how does it work? **this does absolutely not sound like the architecture and thought i have had about this**, explaion"* (08-13, in the corpus at the 2026-08-13 union).
  **What the engine does.** Four bases are computed independently over their own pools, normalized, and added per chunk with a weight each — tag areas, description lookup, stated scope, and since 08-13 the person path: `totals[cid] += W_TAG/W_DESC/W_SCOPE * s` and `totals[cid] += W_PERSON * s` (`artefact_v1.py` · `_retrieve`). The paths do not feed one another. A chunk's score is a weighted sum of four parallel opinions about it, and the tag layer is one of the four addends.
  **What he has described, repeatedly, is a multi-step relevance chain.** 06-27: tag-facets *"inform the RELEVANCE of the tag, per facet, relative to its chunk"* — a relevance weight carried in steps (turns:L285, Part 4; layer-ambiguous as **A5** in Part 5). 07-06, the shape in his own words: file → chunks → tags, the chunk carrying a description and a relational weight to its file, the tags carrying relational values to their chunk (turns:L589-594). Under that reading the tag's relevance reaches the chunk, and the chunk's relevance reaches the file — tag → chunk → file — rather than tag, description and scope arriving side by side and being added.
  **This is not the same object as T13.** T13 is product-vs-sum *inside* the tag term, and he ruled it canonically undecided. T17 is whether the four paths are terms in a sum at all, or steps in one chain. No turn rules on it, and the sum was never presented to him as a design decision — it is the shape the engine was built in.
  **Adjacent, same day, unanswered.** On the new entity layer: *"mhm.. just watched the db now, so, these nodes are only connected to chunks.. and nothing else?"* and *"yeah, WHY are there no relations? like, whats the point it they have no edges? like, not even to eachother?"* (08-13). Person, Product and Channel nodes carry edges to chunks and to nothing else (`build_manifest.json` · `steps.entities.relationship_types`: INVOLVES, MENTIONS, IN_PRODUCT, IN_CHANNEL — every one chunk-to-entity), which is the star shape his question describes. His 06-30 statement is the same objection three months earlier: *"half the strength of of a graph is beeing able to route/search based on relationships instead of structures"* (turns:L446).
  **Layer & fix:** **user ruling** first — nobody can say what the architecture is supposed to be except him, and this entry proposes nothing. If the chain is the intent, the remedy is an **engine change** of unknown size in `artefact_v1.py`'s combine, and the entity layer's edge shape is a **graph rebuild** question on top of it. Recorded here as a divergence, unresolved. [V1-ENGINE]

---

## Part 3 — Cross-layer near-collisions that scoping dissolves

*(explicitly NOT contradictions; listed so nobody re-raises them)*

- **D1 · "The model emits no numbers, ever" vs V1-GRAPH's model-emitted weights.** The baked `w_chunk` / `w_facets` values were produced by a model during the V1-ORIGINAL build, before the rule existed (old v1 interpreter: LLM facet scores, git_record.md:505-573). The rule is V2-DESIGN canon aimed at a graph that was never built. Reading V1-GRAPH's baked numbers is not emitting numbers, and no engine change could unbake them. The false collision comes from CLAUDE.md:216 stating the V2-DESIGN rule without its layer. *(The live-code half of the same rule is a real open question — T12.)*
- **D2 · "The chunk description is dead" vs a description-driven engine.** Description-dead is V2-DESIGN canon (06-11: "Since the collective tags from a chunk should BE the content of the chunk, why do both?" with the doc's own note "(User asked twice; it is dead.)", desktop_docs_record.md:862 and :305; CLAUDE.md:216-217). Chunk descriptions are V1-GRAPH data by his own account of that build ("the chunks contain a short description", turns:L591), so V1-ENGINE reading `chunk_desc_emb` (`artefact_v1.py` · `DESC_INDEX`, weighted at `W_DESC`) is layer-native. His 07-30 "descriptions in every tag was an abomination" (turns:L4013) targets the tag-embedding contexts proposed on 07-06 ("the tag name, the facet scope, and the top-4 chunk descriptions", turns:L533) — a proposal he killed and which never shipped: the July re-embed writes "each `:Tag` name, bare (no context), as `t.emb`" (`v3/reembed_herb_eval.py:6-7`) and deletes the legacy per-facet vectors (`:19-20`, `:41-46`). Nothing in V1-GRAPH carries description text inside a tag vector.
- **D3 · content in the graph.** Three statements that look like one collision and are three layers. *His concept (V1-GRAPH):* "the actual content should never exist in the graph at all" (07-06, turns:L538), "in the actual graph, there are no 'content' like that, just a bunch of related embeddings" (turns:L591). *V1-ORIGINAL's build record:* decision D10, "`Chunk.content` stores chunk text ('makes the graph self-sufficient', Status: Active)", written into the initial commit (`dba1160`, git_record.md:246-281) and still Active in the frozen `v1/` tree — protected by his own freeze policy ("that shit is still true for THAT build", desktop_docs_record.md:986). *V1-GRAPH today:* compliant. The July purge stripped content from the live DB and the re-embed states the result plainly — "The graph holds no content — structure, weights, and embeddings only" (`reembed_herb_eval.py:3-4`) — with description text confined to the read-only `herb-eval-backup` sibling and used as embedding input only (`:9-11`). The concept was violated by V1-ORIGINAL, remediated in V1-GRAPH by the one remedy a baked layer has (a graph change), and the surviving D10 record belongs to a frozen build he ruled stays true for itself. References-not-copies, the V2-DESIGN pivot (`296fc40`, 05-30), is a fourth layer again. *Re-opens if:* content is ever found in the live `herb-eval`, which `reembed_herb_eval.py` asserts is not the case.
- **D4 · "there is only HERB dataset, forget everything else" (07-15, turns:L771) vs the no-overfitting canon.** Scope-of-build vs method-generality — he holds both at once ("Dont think herb, think dataset agnostic concept", turns:L454). Building for the only dataset that exists is not fitting to its answers.
- **D5 · "before we go to the v3 construct of it" (07-15, turns:L717) vs "we are NOT doing the v3 artefact" (07-26, turns:L2941).** Fully consistent, and jointly the clearest statement that V3-NATIVE is a future layer rather than the present one: v1 now, v3 later — the 07-26 ruling says so itself ("before i can fucking finish my v3artefact").
- **D6 · truncation lists ordered (06-27) vs "truncate_k invalid for the artefact arm".** His k5-k50 backfill order was for the lucene/vector output lists (turns:L243); the invalidity claim is artefact-arm-specific by its own wording (MEMORY.md:21; `project_terminology_canon.md:24-26`). Different arms, no collision.
- **D7 · "lean graph, live facets" (06-28 [t52], desktop_docs_record.md:916) vs "USE ALL THE FUCKING DATA IN THE FUCKING GRAPH!" (07-21, turns:L2067).** A build-time size rule for the V3-NATIVE graph versus a retrieval-time order to V1-ENGINE about signals already baked into V1-GRAPH. Different layers, and the second is not even addressable by the first.
- **D8 · abstract "keep it somewhat close" (06-30, turns:L336) vs "that is not canon, just an assumption" (07-21, turns:L2059).** A preference and a canon-status ruling about the same text — compatible; the 07-21 statement even says why ("those that wrote that does not FULLY know what we are doing").
- **D9 · "informed by the tags first" (07-30, turns:L4005) vs "ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE" (08-01, turns:L4098).** Weighting-priority vs membership — his own clarification, one day apart. Not a self-reversal; the build-side collision is entry 4.
- **D10 · "the user writes the real code" (06-18, desktop_docs_record.md:474) vs the agent roster doing the building (07-22 →, turns:L2392-2404).** Explicitly superseded by his own later instruction; nothing to reconcile.
- **D11 · description kept tentatively (06-09, desktop_docs_record.md:855) vs description dead (06-11, :862).** An explicitly tentative decision closed two days later, both inside V2-DESIGN — normal design flow, not a reversal.
- **D12 · "never query `herb` (oracle-contaminated)" (CLAUDE.md:200) vs the arm querying herb-eval.** `herb` ≠ `herb-eval`: the ban names the polluted pilot DB (git_record.md:674-679); V1-GRAPH is the other database. Running the arm on herb-eval does not breach that line. The separate question — residue *inside* V1-GRAPH — is T3.
- **D13 · "there are only 5 facets" (07-06, turns:L614) vs the June facet redesigns.** His statement describes V1-GRAPH, and it is accurate: five slots on one `HAS_TAG` edge, still exactly what the engine indexes (`artefact_v1.py` · `ALL_FACETS`, `_AREA_CHUNKS_CYPHER`). The June redesigns are V2-DESIGN text about a graph that was never built. Two layers, two internally consistent claims. Which set a future build should use is T9.
- **D14 · the three toggle flags.** 07-22: "just make them toggleable … but only do it if it matters, tight, clean" (turns:L2445) — an order with a built-in condition. `WALK_GATE` is the only one of the three ever built: `5006fed` (2026-07-23) added it and it stands in the committed tree at `8c8c787` (`artefact_v1.py` · `WALK_GATE`, exercised by `test_artefact_v1.py` · `WalkGateTests`). The working tree withdraws it — flag, tests and `v3/CONSTANTS.md` row removed together, uncommitted — so `grep -rn "WALK_GATE" v3 --include=*.py` returns nothing on disk while `git show HEAD:v3/pipelines/artefact_v1.py` still carries the assignment. `SCOPE_REACH` and `TAG_PURE` were never built in either: `git log --all -S "HERB_SCOPE_REACH"` and `-S "HERB_TAG_PURE"` over `*.py` return no commit that added either name. Building one of three is compliant with an order whose second clause is "only do it if it matters". No collision with him, and the memory file records the same: `WALK_GATE` is the one flag in the tree, scope-reach and tag-pure are grid configurations with no flag (`project_v1_machinery_fix_and_toggles.md:3`, `:31-33`).

---

## Part 4 — Standing record

*(statements with no contradiction found; compact, by subject, one line each)*

*One line per statement (closely-related same-day turns merged). `2h` = second-hand (desktop_docs_record.md). Layer in brackets; `?` marks a layer-ambiguous statement carried in Part 5.*

**Quarantine & data hygiene**
- 05-14 [CROSS] quarantine all legacy, HERB-only, agents never read it unless told — turns:L129-131
- 06-11 [V2-DESIGN] the oracle never enters the corpus ("we just don't fucking include the eval part in the dataset") — 2h desktop:875
- 06-14 [V2-DESIGN] quarantine must be structural, not declarative ("DONT INCLUDE THE FUCKING EVAL FILES FOR THE PROBE TO EVER SENSE") — 2h desktop:945
- 06-14 [V2-DESIGN] one derived training-set; the eval reads the oracle in place from raw — 2h desktop:946
- 06-14 [CROSS] never touch `A:\exjobbet\data\raw` (storage); the repo copy is the working one — 2h desktop:948
- 08-02 [CROSS] agents should not see questions/gold — pointer/variable access only — turns:L4253, L4257

**V1 concept (his statements about that generation)**
- 06-27 [V1-GRAPH? / V1-ENGINE?] tag-facets inform the RELEVANCE of the tag, per facet, relative to its chunk — a multi-step relevance weight — turns:L285
- 06-27 [V1-GRAPH → V1-ENGINE] facets are themed RELEVANCE weights; facet weight × the tag's chunk-relevance weight (both baked), steered at query time by the interpreter's facet ranking — turns:L297, L301
- 06-27 [V1-ORIGINAL] "apparently it didnt work great, so this is not the same creation anymore"; the pre-v1 idea was clustering-on-facets as filter/router — turns:L305-310
- 07-06 [V1-GRAPH] the shape: file → chunks → tags; chunk description + relational weight to file; tags with relational values; facet values on tags; "pretty much all of this is embedded" — turns:L589-594
- 07-06 [V1-GRAPH] facets ride ONE edge (chunk→tag); five facets — turns:L610, L614
- 07-26 [V1-ORIGINAL ↔ V1-ENGINE] "the entire first generations were on k=40"; "original v1" = the old branches, k=40 era; "current v1" = the arm in this repo — turns:L2913, L2949
- 07-26 [CROSS ↔ V3-NATIVE] the system under test is the v1 artefact querying `herb-eval`; the v3 native rebuild is future work; `v3/` is only where both live — turns:L2941

**V2-DESIGN / V3-NATIVE design rulings**
- 05-25 [V1-ORIGINAL → V2-DESIGN] facets exist to give the tag semantic weight AND direction — 2h desktop:851, :898
- 06-09 [V2-DESIGN] an LLM cannot put correct weights on tags/chunks; measure from embeddings instead — 2h desktop:252, :854
- 06-09 [V2-DESIGN] tag-vs-description distance is a real geometric signal, not model-emitted, not a tautology — 2h desktop:258, :275-277
- 06-11 [V2-DESIGN] the phrase IS the node; sibling-relative relevance per facet; weight-on-tag / relation-on-edge split — 2h desktop:861-865
- 06-11 [V2-DESIGN] all facets are evaluations; each facet needs its own measurement; facets narrow/focus the routing; prompt-heavy facets weigh more — 2h desktop:866-870
- 06-12 [V2-DESIGN] the spine closes: file → chunk → tags, nothing else is a node; records-as-nodes dead; no value inventories in the graph; chunk→file value killed — 2h desktop:877-881
- 06-12 [V2-DESIGN] exact + fuzzy matching is the way for HERB; humans misspell, especially to LLMs; no corpus vocabulary in the interpreter context — 2h desktop:884-886
- 06-12 [V2-DESIGN] materialized-path hierarchy (1.1.2…) is decided canon — 2h desktop:887
- 06-14 [V2-DESIGN] a facet is a relevance coordinate, not a category; per-facet weights on one edge; matching is same-facet parallel channels — 2h desktop:437, :890
- 06-25 [V2-DESIGN] separate tag-facets from routing; the v1 facets carried real semantics; facet values are relational to the corpus; carried as small attributes, not nodes; topic → centrality — 2h desktop:891-897
- 06-25 [V2-DESIGN] the guide-link concept and max-of-facet rephrase + embed-compare are the mechanism — 2h desktop:602-603
- 06-27 [V2-DESIGN] no LLM judge in the creation of tags/facets in the graph — turns:L269; 2h desktop:937
- 06-28 [V3-NATIVE] combinations of solutions are the trick; interpreter facets ≠ graph facets; not all facets graded the same way; lean graph, live facets; embedding-as-node; NEMOTRON embedder; "it's graph-shaped" — 2h desktop:905-924
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
- 07-20 [V1-ENGINE] agent translations he never named — gap cut, NNK, RRF fusion — do not exist in the engine — turns:L1962-1964
- 07-21 [V1-ENGINE] clustering IS embedding distances against each other — not rankings or countings — turns:L1976
- 07-22 [V1-ENGINE] cluster-K: the curve of best fit decides the correct K per query — turns:L2260
- 07-25 [V1-ENGINE] the modular intent behind the toggles acknowledged ("everything can be turned on or off for finding the best solution") — turns:L2739
- 07-29 [V1-GRAPH? / V1-ENGINE?] two fix targets: use the graph's shape better; kill the 90%-air problem — turns:L3892-3893
- 07-30 [V1-GRAPH? / V1-ENGINE?] the whole point of the tags is guiding to the correct gold-bearing chunks (said twice) — turns:L3953, L3961
- 08-01 [V1-ENGINE] adversarial diagnosis of the tag-clustering build ordered — turns:L4094

**Evaluation design**
- 06-18 [CROSS] the artefact is the SYSTEM UNDER TEST, not an IR retriever; HERB scores answers only — 2h desktop:501
- 06-23 [CROSS] arms share ONLY the corpus files and the injected generator; reusing a reader is contamination — 2h desktop:522
- 06-25 [CROSS] k ≠ top-k; k = 50 global ceiling; gold-100, never `--set full`; the four judged metrics ("those 4 + the free ones"); structured generator outputs — 2h desktop:626-628, :953-956
- 06-25 [CROSS] RAGAS only — no separate HERB scorer; nothing reported is leaderboard-comparable, and that is accepted ("we have never used the herb score and has no intention to", 08-04) — 2h desktop:953
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
- 05-25 [CROSS] build first, report later ("DONT start thinking about the report") — 2h desktop:969
- 06-03 [CROSS] delete-don't-preserve; superseded content goes, preservation needs explicit approval — 2h desktop:238
- 06-11 [CROSS] design before build: "all parts are decided upon first" — 2h desktop:977
- 06-12 [CROSS] docs updated by removal, not banners; frozen docs stay true for their build — 2h desktop:986-987
- 06-23 [CROSS] no historical or defensive comments — 2h desktop:524
- 06-25 [CROSS] "MY WORDS ARE THE CANON" — the user's definition of the experiment is the spec — 2h desktop:954
- 06-28 [CROSS] capture the entire build — nothing declared, nothing omitted; conversations and memories count — 2h desktop:994-995
- 07-16 [CROSS] trust revoked: explicit instruction only; an accidental plan-toggle is never a go — turns:L1140-1148
- 07-16 [CROSS] an opinion is never a command; a question he asks is not a verdict he gave, and is recorded as the question it is — turns:L937
- 07-16 [CROSS] visible progress is mandatory; the user runs the scripts — turns:L992-L1001, L919-921
- 07-17 [CROSS] reusable tools, not one-off custom scripts — turns:L1278-1280
- 07-22 [CROSS] orchestrator mode: main chat only talks and routes; permanent specialist agents, properly equipped — turns:L2392-2404
- 07-22 [CROSS] adversarial panels must be blind — no seeded questions; sterile prompts, then compare — turns:L2372-2376, L2433
- 07-23 [CROSS] three shipping-gate adversaries (academic rigor, senior engineer, overfitting/leakage) before conclusions ship — turns:L2555
- 07-23 [CROSS] commit means push (to a feature branch) — turns:L2607
- 07-23 [CROSS] precompute/batch everything embeddable in one pass — turns:L2536
- 07-24 [CROSS] arm-running scripts stay stable; agents don't rewrite them mid-experiment — turns:L2665-2669
- 07-25 [CROSS] the point is an academically VALID artefact, not chasing the highest number — turns:L2717
- 07-25 [CROSS] naming a thing does not make it canon; text in the repo is not his approval of it — turns:L2729, L4209
- 07-28 [CROSS] full revert: "either you absorb the knowledge or its gone" — no semi-revert — turns:L3457
- 07-29 [CROSS] agents stop estimating wall-clock time (always wrong, builds false narratives); background workers, never conversation hijacking — turns:L3577, L3848
- 08-02 [CROSS] full adversarial senior-dev audit of every step of the artefact code — turns:L4221
- 08-02 [CROSS] the canon-mining order: find everything HE actually said, across all machines, branches, logs — turns:L4334, L4372
- 08-03 [CROSS] desktop transcripts raw-copied for mining, no summarizing — turns:L4384-4395

---

## Part 5 — Layer-ambiguous statements

*(statements whose wording does not decide between the baked graph and the live
engine. The distinction is not academic: one is fixable by editing
`artefact_v1.py`, the other needs a rebuild nobody has scoped. Each carries the
test that would settle it. None is guessed at anywhere else in this document.)*

- **A1 · 06-27 — "tag-facets inform the RELEVANCE of the tag, per facet, relative to its chunk" (turns:L285).** Either a description of what the facet slots on the `HAS_TAG` edge *are* (V1-GRAPH) or a specification of how retrieval must consume them (V1-ENGINE). *Settled by:* asking whether "inform the relevance" describes a stored quantity or a query-time operation. If it is the stored quantity, the values are already what he describes and nothing is owed; if it is the operation, `STR_FACET` defaulting to `0.0` (`artefact_v1.py` · `STR_FACET` — the facet modifier inert on a default run) is a live non-compliance.
- **A2 · 07-30 — "the whole fucking point of the tags, is guiding to the correct gold-bearing chunks" (turns:L3953, L3961).** Either a claim about what the tag vocabulary was baked *for* (V1-GRAPH) or an order about how the engine must weight it (V1-ENGINE). *Settled by:* measuring whether the baked tags can discriminate gold-bearing chunks inside a question's scope territory at all. If they can, this is an engine ordering problem. If they cannot, no engine change satisfies him and the statement becomes a retag requirement — which is the same wall the corroboration probe hit (MEMORY.md:15).
- **A3 · 07-29 — "use the graph's shape better" (turns:L3892).** Either exploit structure already in V1-GRAPH (engine traversal) or add structure to it (rebuild). *Settled by:* his answer to T5 — the 08-02 "might as well be sql-schema" rejection suggests exploit-don't-add, but it was aimed at one specific hub-node proposal, not at the general question.
- **A4 · 07-29 — "kill the 90%-air problem" (turns:L3893).** If the wasted tokens sit *between* retrieved chunks, it is a selection problem (engine). If they sit *inside* them, it is a chunking problem and only a rechunk fixes it — V1-GRAPH's chunk boundaries are baked and were never revisited. *Settled by:* measuring the gold-token fraction within retrieved chunks versus across the retrieved set. The measurement has never been run and is cheap.
- **A5 · 07-31 — "compute the clusters at build" (turns:L4033).** "At build" could mean written into the graph (a V1-GRAPH write) or computed once and cached outside it (V1-ENGINE precompute). *Settled by:* whether he requires the clusters to be queryable as graph structure. If a cached artefact beside the arm is acceptable, T11 costs nothing and needs no rebuild.
