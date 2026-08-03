# OPEN_DECISIONS — everything genuinely unresolved

Pulled from `USER_CANON.md`, `CANON_AUDIT.md`, `raw/git_record.md` and
`raw/desktop_docs_record.md`. Nothing here is invented and nothing is recommended: each entry
states the evidence, its date, its source, and what a ruling from him would settle.

All dates are 2026. `[CHAT]` = his own keystrokes; `[DOC]` = recovered from an agent-written doc
that quoted him. Trust ordering and coverage limits: `README.md`.

**Counts.** §1 unresolved reversals **7** · §2 specified and never built **23** · §3 questions
never answered **12** · §4 instructions recorded nowhere **17** · §5 audit findings awaiting a
ruling **28**. **87 open items.**

---

## 1. Unresolved reversals — he said opposite things and never ruled

Both sides stand. No agent picks a winner.
Source: `USER_CANON.md` §3, §4, §5, §11, §12; `CANON_AUDIT.md` ranked items 2 and 3, §3.7.

### R1 — Tags inform, or tags gate

> "ok, so we make sure it is **informed by the tags first** then, as IT WAS FUCKING INTENDED from
> the start.. didnt the original thesis artefact do it correctly?" — **[CHAT] 07-30**

> "you and every other agent seem to be missing that the whole fucking point of the tags, is
> **guiding to the correct gold-bearing chunks**" — **[CHAT] 07-30**

> "**ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE ffs.. tags are supposed to INFORM/weight the
> chunks**" — **[CHAT] 08-01**

**Ships now:** `HERB_TAG_FIRST` in `v3/pipelines/artefact_v1.py:167-211`, committed `6730d13` on
08-01 at 12:05 — twelve minutes after the 08-01 turn — on branch `tag-first-cluster-guide`. Under
it, a chunk with no matched tag is excluded: tag membership admits or excludes.
`USER_CANON.md` §3 reads the two as different mechanisms; `DESIGN.md` §14.4 ("no hard filters
anywhere in ranking") makes the gate a design-canon violation as well. An 08-02 adversarial agent
reached the same verdict independently: *"HERB_TAG_FIRST is a category error — delete it."*

**A ruling decides:** whether tags-first means weighted earliest and hardest in the ordering, or
membership; and therefore whether the branch's regime is deleted, kept, or rebuilt as pure weight.

### R2 — What a facet *is*: three definitions in thirteen days

| Date | Position | Quote |
|---|---|---|
| 06-14 | A facet is a relevance coordinate of a tag | "relevance weights, not interpretation." **[DOC]** |
| 06-25 | A facet is semantic meaning around the tag; routing is separate | "I think we should separate tag facets and routing." / "the v1 facets were actual semantic meaning around the tag." **[DOC]** |
| 06-27 | A facet is a graded "how much" dial | "you HAVE to remember that the facets are themed RELEVANCE weights.. meaninig you have to think about them differently, like info-kind and entity-type (**are they even facets..?**)" **[CHAT]** |

Each kills the one before; the third ends in his own open question. `USER_CANON.md` §4 (Reversal F1).

**Ships now:** the interpreter's pass 2 asks the model to score tags against five facets 0.0–1.0.
Five weeks of him asking what the facets are actually doing (07-20 "how the fuck are facets used
here then?", 07-21 "how did we get the facet-values now?", 07-25 "what is affecting the interpreter
from the facets") are recorded with no answer he accepted.

**A ruling decides:** what a facet measures, and therefore whether the facet layer is measured
geometry, a graded dial produced at query time, or removed.

### R3 — Clusters computed at build, or per query

> "i mean, the clusters are based on the actual shit from the prompt, so **you cant pre-run it..?**"
> — **[CHAT] 07-21**

> "1. i THINK it might be smartest to **compute the clusters at build**, and then weight-adjust them
> based on the query's facet-values.. i THINK, reflect on this with me..
> 2. something like that, i used **best fit as the fuzzy cutoff-point for the cluster's edges** tho
> … but perhaps the query-adjustment comes first before what the best fit is for this query" —
> **[CHAT] 07-31**

Ten days apart, opposite, **both hedged by him** (`"..?"`, `"i THINK"`, `"reflect on this with
me"`). Neither is a ruling. `USER_CANON.md` §5.

**Ships now:** neither. Cluster-K — defined 07-21 ("we get that curve of best fit and let that
decide the correct K for that solution") and respecified 07-31 — has never been on the
load-bearing path in any shipped configuration.

**A ruling decides:** where clustering runs, whether query facet-adjustment precedes or follows
best-fit, and therefore whether cluster-K is buildable at all.

### R4 — Entity-type and information-kind: out, in, out

- **Out** (05-30, agent allocation table he later disowned): entities/temporal/evidence relocated
  to hard fields as "the v1 junk facets".
- **Back in** (06-25): *"Would not the old facets work with the new tags? (not the weighting, the
  concept)."* — **[DOC]**
- **Out again** (06-27): *"like info-kind and entity-type (are they even facets..?)"* — **[CHAT]** —
  a thing that answers "which" is not a facet; a facet must be graded.

`USER_CANON.md` §4 (Reversal F2) records the reconciliation against the 06-28 categorical framing
as **an open problem that was never closed**. Compounding it, three desktop memory files each
declare a different five-facet set "settled" (`CANON_AUDIT.md` 6.5; `git_record.md` C-6).

**A ruling decides:** the facet set itself — which five, and whether categorical dimensions belong
in it at all.

### R5 — Hard fields: attributes, then nodes/edges, then rejected as SQL schema

> "either they are nodes, but then we get edges to EVERY fucking chunk, or they are just
> attributes… perhaps it's smarter to just have shit like that as attributes on chunks." —
> **[DOC] 06-12**

> "yeah i really think this should be nodes or edges so to speak etc, **half the strength of of a
> graph is beeing able to route/search based on relationships instead of structures**" —
> **[CHAT] 06-30**

> "having it as a rule to make nodes out of shared fields between files/areas etc.. Isn't that a
> generally useful concept? Dont think herb, think dataset agnostic concept." — **[CHAT] 07-01**

> "well.. you think this would be easier for you to build and think upon the artefact if we used
> the graph shape better? like the hard fields etc, should they be nodes or edges or something?" —
> **[CHAT] 08-02**

> "**dude, you are turbo-overfitting now, AND doing shit that might as well be sql-schema**" —
> **[CHAT] 08-02**, on the concrete answer to the question directly above

**All three positions are his and none has been retired** (`USER_CANON.md` §11). The desktop record
carries the same split unresolved: `artefact-pass2-design.md` specifies hub nodes for
mid-selectivity shared scalars while `v2-graph-spine.md` says "the minted hub-node-per-label idea is
**dead**" — and the pass-2 file names the tension itself and says it "needs an explicit sign-off,
not silent resolution either way" (`CANON_AUDIT.md` 6.10).

**Ships now:** hard fields are chunk attributes. The graph spine `Source → File → Chunk → Tag` is
closed canon.

**A ruling decides:** whether the relationships/hub-node layer (§2, item 2) gets built, and what
distinguishes a useful hub node from SQL schema.

### R6 — Dataset-agnostic, or HERB-only

> "Dont think herb, **think dataset agnostic concept**." — **[CHAT] 07-01**

> "…Was pretty good, but, **there is only HERB dataset, forget everything else**, and ther hard
> constrains still fucking confuse me" — **[CHAT] 07-15**

Both verbatim. `USER_CANON.md` §12 records the context — 07-01 is about what *rule* the indexing
should follow; 07-15 was a reply to an agent drawing a HERB-vs-other-datasets distinction inside
the hard-constraint logic — and states plainly that **which governs a given decision is not
resolved**. His 07-30 generalization mechanism ("the indexing stages finds structures in the
dataset which then translates to a helpful graph of it… that part gets auto-fitted to every new
dataset, not just herb") sits on the 07-01 side; the Bonnier set that would have tested it was
deferred 06-14 and never resumed.

**A ruling decides:** whether an indexing rule must be justifiable dataset-blind, or may be fitted
to HERB — the standing test every "is this overfitted?" argument turns on.

### R7 — Cost: zero weight, or a hard gate

> "**YOU do not care about cost here, 0 fucks given… only for me. so fucking drop that fast as
> fuck.**" — **[DOC] 06-18**

> "you unholy mother fucker.. you just burned 70% usage on NOT finishing the fucking evals!?" —
> **[CHAT] 07-23**

> "so, you absolute fucking trash cunt, you actually burned my entire usage in 5 minutes achieveing
> NOTHING… how about you fucking solve this BEFORE you waste all my usage.." — **[CHAT] 07-24**

`CANON_AUDIT.md` 3.7 and 6.2 record both as real, with the July burns superseding the June
instruction — but **no ruling in words exists**, and the two live surfaces still carry opposite
rules: laptop memory makes cost math a hard rule with no de-minimis exception; desktop
`no-cost-estimates.md` says cost must carry **zero weight** in reasoning. A fresh agent reading only
the desktop memory reinstates the behaviour that caused three of the worst incidents in the project.

**A ruling decides:** whether the June instruction is formally retired, so one rule stands.

---

## 2. Specified and never built

Designed, in some cases pseudocoded, with no implementation. Sources: `USER_CANON.md` Part IV;
`raw/desktop_docs_record.md` §5; `raw/git_record.md` Part 3.

### 2A — Designed in full, never built (8)

**1. The aggregation path.** Origin his: *"but, doesnt the graph give actual relational connections
to things like this, i mean, if the 'name' example you had, why wouldnt if just find all of those
names? i dont get it"* — **[DOC] 06-28 [t33]**. Designed complete across 06-28 §3.1 and 07-01 §11.7:
structural scope → semantic filter → full recall with no cap → group-by chunk attribute → count/max
→ directory join. Never written; the interpreter classifies 30+ of gold-100 as `aggregate`, logs it,
and returns top-k chunks anyway.
**Blocks:** every aggregate question. `exact_match` is **0.000 across all three arms**. The 06-28
doc calls it *"the biggest design gap in pass 1"* and *"where the artefact's relational-graph
advantage over flat-vector retrieval shows clearest"* — the one capability that would distinguish a
graph from a vector store.

**2. The relationships / hub-node layer.** *"half the strength of of a graph is beeing able to
route/search based on relationships instead of structures"* — **[CHAT] 06-30**. Traversable
containment + adjacency from the already-stored materialized path; hub nodes for mid-selectivity
shared scalars; two disciplines (reference-never-copy, weighted-and-steep); the HERB landmine named.
Listed as needing sign-off 07-01 §11.5; absent from the 07-12 built inventory.
**Blocks:** the "use the graph as a graph" requirement he then asked for again on 07-20, 07-28,
07-29 and 08-02 without either party recognising it had already been specified. Gated on **R5**.

**3. Pass 2 in its entirety — the exponential curve.** *"cant we just do the evaluation-curve for
the ranking of those "exponential", we dont have to decide the actual angle now, but kinda meaning
"exact = max" on that curve, ish..?"* — **[CHAT] 06-30**. Shape decided, angle deliberately left as
a sweep parameter. It was the *diagnosed fix* for the precision failure he condemned. 07-12 records
*"Pass-2 pipeline code has not been built."* Still true.
**Blocks:** the precision rot — "we find pretty much all gold, but also 90% air" (07-29).

**4. Per-facet channels.** Each dial's score kept separate from tag to chunk so a chunk carries a
facet-relevance profile — `DESIGN.md` §14.3's actual combinator (`promptFacetRelevance ·
facetWeights`). Pass 1 max-pools one unlabelled set; the designed combinator was never implemented
at all (`desktop_docs_record.md` §5.3).
**Blocks:** any facet mechanism that is more than a scalar.

**5. Centrality.** His own idea: *"perhaps we can do that, but based on each facet! giving a
relational value of the tag to its siblings based on each facet!?"* — **[DOC] 06-11**. Deferred
06-11 (unblessed), 06-25 (open), 06-28 (deferred), 07-01 (inherited), 07-12 (unbuilt). The chunk→tag
edge `DESIGN.md` §14.1 reserves for it carries nothing.
**Blocks:** the one facet measurement the research catalog calls **phrase-robust** — the one most
likely to actually work.

**6. Chunk attribute extraction.** Only `kind` and `product` are materialized (the latter read off
the file path). Person, org and date attributes were never extracted.
**Blocks:** three things at once — `date_range` is emitted by the interpreter on every query,
validated and thrown away; there is no structural join for "PRs by Anna"; and item 1's group-by keys
have nowhere to come from.

**7. The fuzzy-embedding pre-pass.** His idea at **[DOC] 06-28 [t24]**; its blocking question
(is fuzzy edit-distance or embedding closeness?) answered by him on 07-01 — *"i mean by fuzzy i
actually mean embedded"* — and then nothing was built.
**Blocks:** the exact+fuzzy lexical layer he called "the way to go for herb" (06-12).

**8. The gold-blindness mechanism.** *"can we make sure "you" never see them? that you only get the
variable/pointer to it?"* — **[CHAT] 08-02**, asked one day before the record ends.
**Blocks:** nothing technically — but the project's most important anti-leakage instruction is
currently enforced only by whoever remembers to put it in a prompt.

### 2B — The three falsifiers, each gating a layer, none run (3)

Designed three times (06-25 §7, 06-28 §3.7, 07-01 §7), never executed.

**9. The ~30-phrase orthogonality probe.** Does the embedding move more for the facet than for
incidental rewording, and do the facet-concepts separate at all?
**Blocks:** knowing whether the facet layer has any signal. `MULTI_FACET_THRESHOLD = 0.50` makes 85%
of tags multi-facet, which is itself the evidence for the orthogonality risk.

**10. The per-dial divergence check.** A handful of prompts, per-dial rewrites embedded — do the
retrieved tag sets diverge?

**11. The channel-blend reorder test**, whose stated consequence is why it matters:
> *"If nothing moves, **every facet design here collapses to topic retrieval** — and that finding
> matters in itself."* — 07-01 §7

The research catalog is candid that none of this is settled science: *"No benchmark evaluates any of
this on short context-free phrase-tags into a small facet set; the behavior on a real tag corpus is
an experiment, not a literature fact."*

### 2C — Constants no artifact ever derives (4)

Against his standing rule: *"i do NOT like arbitrary choices for k or any number or value, fucking
BASE it on something"* — **[CHAT] 07-15**. `USER_CANON.md` §7 and Part IV C.

**12. `α = 0.25` (coverage bonus).** Directional rationale only, never swept, load-bearing on 230k+
edges — and measured to work counterintuitively (mean `w_chunk` is *lower* on `w_facet=1.0` edges
than on 0.7–0.8 edges).

**13. `MULTI_FACET_THRESHOLD = 0.50`.** No rationale at all.

**14. `CAP_TOKENS = 3000`.** The best-justified constant in the repo — explicitly *"a calibration
seed, not a verdict"* (06-04, his own framing) with a named sweep. **The sweep was never run**, not
even after the tagger and chunks existed (`git_record.md` C-15). §15 of `DESIGN.md` meanwhile
hardened it to "fixed by design" with no decision behind it (§5, item A13).

**15. `POOL_FETCH`, the 64-chunk limit, `K_LEVELS`.** *"also, arbitrarily decided hard limits, like
the 64 chunk limit, i bet there is way more than 1 of these dumb limits lying around not beeing
seen"* — **[CHAT] 08-02**. Never enumerated since.

### 2D — Adopted, then silently un-adopted, with no reversal recorded (5)

`USER_CANON.md` Part IV D.

**16. The SQL-agent baseline.** 05-25: Lucene dropped, SQL-agent is the comparison, a memory file
written, both handoffs instructing the next agent accordingly. By 06-18 the harness is lucene +
vector + artefact and `baselines/sql_agent.py` is dead cruft. **No document records the reversal**;
`DESIGN.md` §12 still says the SQL-agent is the baseline.

**17. The HERB anchor metric.** *"no, i am saying we do both."* (**[DOC] 06-18**) → a 45-line stub of
six `...` bodies → deleted 06-28 inside a commit titled "update graphify-out (533 files)". The
*reason* is a real user ruling (*"this is ONLY RAGAS"*, 06-25, said twice), but its consequence is
weighed nowhere: **no number this project reports is comparable to HERB's published leaderboard.**

**18. The controlled canonical vocabulary.** `:CanonicalTag`, the seed file, the human review loop —
deleted 05-13 in a commit titled "Rework HERB chunking and tagging frames", with one substituted
table cell as its only prose trace. Decision-log entries D2/D3/D4 still read `Status: Active`.
**No user statement about it exists in any source** (`git_record.md` C-3).

**19. `(:File)-[:TAGGED]->(:Tag)` and `weight_global`.** The deterministic file rollup vanished. Not
discussed in any doc, comment or commit (`git_record.md` C-4).

**20. Bonnier / the second dataset.** Deferred by him 06-14 (*"the Bonnier set will have to wait
until some other time."*), never resumed. It was the only planned test of whether the design
generalizes beyond HERB — see **R6** — and the sole stated rationale for the Mistral tagger choice.

### 2E — Open at the moment the record ends, 2026-08-03 (3)

`USER_CANON.md` Part IV F.

**21. The 08-02 tag-layer diagnosis.** He pasted it — the tag path finds 3 chunks/question out of a
~418-chunk pool, zero widening levels ever open, `GUIDE_TAU = 0.0` makes every tag's guide value
exactly 1, and `HERB_TAG_FIRST` bundles a walk restructure with a gate — and answered *"so, lets fix
that and try it"* **[CHAT] 08-02**. Whether it was fixed is not in the record.

**22. The evidence-cap / matched-token-budget work.** Existed only inside the thread he ordered
fully reverted on 07-28 (*"no, there is no semi-revert option here, either you absorb the knowledge
or its gone"*) and did not survive the revert. It is the work that would answer his own 07-26
diagnosis: *"k=50 does not mean the same for all arms, and thats retarded"*.

**23. Cluster-K itself.** Defined 07-21, respecified 07-31, **never on the load-bearing path in any
shipped configuration**. Gated on **R3**.

---

## 3. Questions he asked that were never answered

Sources: `USER_CANON.md` §2, §4, Part IV E.

**1. Is the graph actually being used as a graph?** Asked **seven times across five weeks** — 06-30,
07-15, 07-20, 07-21, 07-28, 07-29, 08-02 — and never answered to his satisfaction:
> "the real question i have now tho, is wether the graph is actually built in a way that makes use
> of the actual qualities of a graph" — **[CHAT] 07-20**
> "also, are we underutilizing the fact that all of this is built in a graph format? i get a very
> distinct feeling that we are leaving quite alot out here, take your time in analyzing this" —
> **[CHAT] 07-28**

The 08-02 answer he did get, he rejected: *"dude, you are turbo-overfitting now, AND doing shit that
might as well be sql-schema"*. See **R5** and §2 item 2.

**2. What are the facets actually doing?** Asked continuously 07-20 → 07-25: *"how the fuck are
facets used here then?"*, *"is this useful? do the facets actually matter like this?"*, *"how do we
make the facets relevant then?"*, *"but HOW, how the fuck did facets get that value?"*, *"wait, what
is affecting the interpreter from the facets that actually changes the response/interpretation?"* —
all **[CHAT]**. No answer he accepted is in the record. See **R2**.

**3. Do we need multi-hop if the graph is built correctly?**
> "yeah but do we NEED multihop if we do the graph correctly?" / "what i said was: if we build the
> graph correctly, wont it emulate/do multihop natively purely by design?" — **[CHAT] 07-15**

Never answered; no mechanism was ever built that would test it.

**4. A dq-RL test.** *"honestly, cant we create a dq-RL-test for this where we finally find the
actually good solution?"* — **[CHAT] 07-20**. No implementation, no recorded ruling; he redirected
the same day to testing artefact variants instead.

**5. Hapax, and who decided what a tag layer is for.**
> "have you decided this? "which is what a tag layer is supposed to be" ? Because in min mind, just
> when thinking about it cursory, **hapax would let them matter more because of vectorisation?**" —
> **[CHAT] 08-02**

Open. No answer recorded.

**6. Is there an architectural difference between the det and haiku legs?** — **[CHAT] 07-29**,
asked while trying to settle which arm is the baseline: *"all agents keep fucking reverting to the
"det" arm, is there something in some documents that says so? because this is starting to piss me
off"*. Never settled in writing.

**7. Should rank-aware metrics replace set-based `recall_id`/`precision_id`?** — **[CHAT] 08-02**.
He pasted the agent report showing the eval `set()`s the retrieved ids and therefore discards the
ordering his changes were changing. **He did not rule.**

**8. The interpreter's "faceting" rename.** He asked for a different name so it stops colliding with
tag-facets (06-25 §11.5). Never done; `facet_phrases` still uses the word.

Four further questions the record raises that nobody has answered, listed for completeness
(`USER_CANON.md` Part IV E):

**9.** Why `qt.scopeWeight` was introduced into the v1 scorer (shipped 05-15 → 05-28). Named as a
factor to remove; **no source in any of the three records explains why it exists** (`git_record.md`
G-7).
**10.** Why the built tagger is `z-ai/glm-5.1` when the documented choice was Mistral Large. Three
tagger-model decisions, each superseding the last; the final one has no rationale anywhere
(`git_record.md` C-10, G-4).
**11.** Judge calibration against a human-labelled subset — recommended 06-18, never locked, never
run. The `MetricScore` record carries a `human_label` slot that is always empty. **Every judged
number this project reports is uncalibrated.**
**12.** H1–H4 from 06-23, notably lucene/vector `documents.feedback` parity. Never resolved; the doc
itself notes it *"muddies 'sparse vs dense' on that kind"*.

---

## 4. Instructions recorded in no surface any agent loads

Verbatim, so they can be placed. All 17 from `CANON_AUDIT.md` §"User instructions recorded NOWHERE".

**The structural cause:** `USER_CANON.md` — the only surface holding his words verbatim — was
referenced by nothing. Not CLAUDE.md's entry-point list, not any agent definition, not the memory
index. Verified by search: zero references. So everything below that exists only there is, in
practice, still lost.

| # | Verbatim | Date | Where it lives now |
|---|---|---|---|
| 1 | "honestly, **you should not have the questions/gold available to you**, there is 0% good that can come out of taht" / "can we make sure 'you' never see them? that you only get the variable/pointer to it?" | 08-02 | **Nowhere.** The single most important anti-leakage instruction in the project. |
| 2 | "**we are NOT doing the v3 artefact, we are doing the v1artefact** … EVERYTHING i have been TRYING to build for weeks now, have been the actual v1artefact" | 07-26 | **Nowhere** — and the opposite is written into CLAUDE.md and `v3/README`. |
| 3 | "**i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something**" / "also, arbitrarily decided hard limits, like the 64 chunk limit, i bet there is way more than 1 of these dumb limits lying around" | 07-15, 08-02 | USER_CANON only. Absent from CLAUDE.md and every agent definition — while those definitions hard-code bars (0.7926, +0.03, p<0.05). |
| 4 | "**Dude, your dates and times are ALWAYS wrong, please stop from trying to measure time**, it's genuinely terrible and just builds a false narrative in YOUR mind" | 07-29 | **Nowhere.** Agents still compute durations and date-reason in reports. |
| 5 | "1. i THINK it might be smartest to **compute the clusters at build, and then weight-adjust them based on the query's facet-values** … 2. i used **best fit as the fuzzy cutoff-point for the cluster's edges** … perhaps the query-adjustment comes first" | 07-31 | USER_CANON only. This is the *current* design direction in his own words; no agent-facing surface carries it. See **R3**. |
| 6 | "the original thought was … **clustering of tags weighted by facets, meaning each type of facet was a separate sort of clustering** to get semantically different clusters" | 07-31 | USER_CANON only. |
| 7 | "arent all arms here kinda supposed to be available as '**tool calls**' for the llm … ours it can be a bit more active with" / "what i am after here, is **letting the agent actually 'hold on to the conversation'** and decide when it has the informtion to answer the question" | 07-21 | **Nowhere.** An entire architectural direction — never recorded, never built, never refused. (He parked it himself the same day: *"dude, it's the same fucking thing, but we let the interpreter do it now.. so.. whatever.."*) |
| 8 | "**USE ALL THE FUCKING DATA IN THE FUCKING GRAPH!** why would you leave shit on the table like that" | 07-21 | USER_CANON only. |
| 9 | "**all nim can be called in 1 batch**" / "why on earth havent everything in that dataset been embedded before already and just saved? it's fucking free and can be done in 1 batch" / "I want subsequent runs to be more or less fucking **instant and free**" | 07-23, 07-29 | Partially in USER_CANON; **not** in CLAUDE.md or any agent definition — despite being the thing he repeated most across three weeks. |
| 10 | "**make the plan as fable, do the work as opus5-max**" | 08-02 | **Nowhere.** A direct model-routing instruction to the orchestrator. |
| 11 | "yeah, dude, but **dont fucking bloat a new session with contaminated informatioj!**" / "exactly, so we bould and clean and then do a **clean session**" | 08-02 | **Nowhere.** The clean-session discipline he was actively enforcing in the final week. |
| 12 | "**DO NOT fucking touch a part i have not asked you about**" | 07-30 | Only obliquely, inside the trust-revoked memory entry. |
| 13 | "if the constrct is the same, you can just **test with and without the different weights and solutions … just make them toggleable** … but only do it if it matters, tight, clean, to the point" | 07-22 | USER_CANON only. The toggle flags exist in code; the rule that produced them does not. |
| 14 | "**k=50 does not mean the same for all arms, and thats retarded**" / "perhaps K shouldnt be chunks, perhaps we should put a **max token budget** instead" | 07-26 | USER_CANON + partly the validity memo. He diagnosed the matched-budget problem **two days before** the audit panel "discovered" it as the 85%-unit-artifact finding; his own diagnosis is not recorded as canon. |
| 15 | "**if we build the graph correctly, wont it emulate/do multihop natively purely by design?**" | 07-15 | USER_CANON only. |
| 16 | "**is it a you reason? is it reasoning? is it context bloat? is it truncated context? seriously, i need an answer to why you are this shitty now because i need to be able to avoid this frustration**" | 07-22 | **Nowhere.** Its companion ("react to being yelled at") is recorded; this half — asking agents to diagnose their own degradation so he can work around it — is not. |
| 17 | "**conversations and memories also count, just because it didnt leave a conversation doesnt mean it shouldnt be saved**" | 06-28 | **Nowhere** in current canon (desktop record only). It is the instruction that, followed, would have prevented this entire audit. |

---

## 5. Audit findings awaiting his ruling

`CANON_AUDIT.md` adjudicated 117 prescriptive repo claims. These 28 are findings, **not fixes** —
nothing was changed. Each line says what a ruling would settle. Verdict tags are the audit's.

### 5A — The 11 CONTRADICTS-USER claims

| # | Claim, and where it lives | The record | A ruling decides |
|---|---|---|---|
| C1 | CLAUDE.md 1.9: "`v3/` — **the work** … Self-contained." | 07-26: "we are NOT doing the v3 artefact, we are doing the v1artefact" | Whether the most-read paragraph in the repo points fresh agents at `pipelines/artefact_v1.py` over `herb-eval`, or at `v3/artefact/`. |
| C2 | CLAUDE.md 1.10: "the artefact … **rebuilt natively in `v3/artefact/`**" | Same turn | Which tree is the system under test, in canon as well as in fact. |
| C3 | CLAUDE.md 1.15: "**The chunk description is dead.**" (unqualified) | 08-02: "wasnt the plan to cluster the tags weighted by facets **in combination with chunk-descriptions**"; 07-06: "the chunks contain a short description of the chunk … Pretty much all of this is embedded" | Whether the rule is qualified to the v3 native tagger (where it is grounded, 06-11) or applies to the shipping arm — where `W_DESC` over `chunk_desc_emb` is one of three fused rankings, and the 07-28 `detDESCCORR` run that demoted it collapsed recall to ~0.085. |
| C4 | `v3/README` 2.1: "**artifact** … The system under test, **built natively in v3**." | Same as C2 — and it spells the arm `artifact`, which the terminology canon every agent enforces defines as a different thing | Same as C2, plus whether the canon's own reference file must obey the artefact/artifact distinction. |
| C5 | `v3/README` 2.5: "**Provenance** is two manifests … **no seed, no git-sha**." | 07-16: "the data about the builds ETC is important for **traeability, reproducibility etc, academic purposes**" | Whether runs must carry seed + git-sha. As it stands, **no committed run is reproducible** (`git_record.md` G-9). |
| C6 | Agent definitions ×6: "**areas / levels / walk / anchor / support / stated-scope / parts are the user's concepts** — never rename or substitute them" | Measured over 803 turns: *levels of k's* yes; *areas* marginal; **walk, anchor, stated-scope, support, parts — no** (agent text, or him echoing it back). 07-20: "NONE of these are something i named or invented, what the fuck are they?" | Which words are actually his — and whether an unrenameable-by-rule vocabulary survives in six agent definitions. |
| C7 | `maths-algorithmist.md:29`: "**Compare against the standing bars before proposing** … past scope-alone (0.7926 det 10smoke)" | 07-31, three consecutive turns: "what is this garbage?" / "what the fuck are you even talking about, pass fail?" / "**we already have the fucking scores to compare to, stop making random shit up**" | Whether a permanent specialist may silently kill proposals against a bar he rejected before he ever sees them. |
| C8 | `memory/project_terminology_canon.md`: the list of "the user's design terms" | Its own provenance line names its sources — README, DATA_README, a state doc, CLAUDE.md, the code: **every one an agent artifact.** It flags one coinage ("surface") while laundering four others | Same vocabulary question as C6, plus whether that entry is rewritten or deleted. |
| C9 | `memory` index line: "never analyze from stale/legacy/quarantined files **or git archaeology**" | 08-02: "**THE GODDAMN GIT REPO HAS ALL THE FUCKING HISTORY SPOKEN IN COMMITS, DIFFS, CODE and DOCS**" / "you have to dig in the repo if you want true info" | Whether git is a first-class source. The file's *body* already says git is fine; the index line drops that clause, and the index is what agents skim. This is the instruction that kept agents ignorant of their own project. |
| C10 | desktop `v3-arm-model-stack.md`: "**Why this overrides the earlier 'ground references' the user pasted**" | An agent recording in writing that it overrode source material he handed it, against the standing rule "surface a genuine conflict as a question, not a correction" | Whether the embedder call stands, and whether the override is retracted as a method violation. |
| C11 | State docs recording "**the user's verdicts**" on mechanisms (chord break, value-knee) | These were **agent measurements**, not his judgements. His actual words are questions: "i dont think the walk and the 'best fit' is helping eachother, you?" (07-22) | Whether they are re-labelled agent measurements — which makes them reopenable — or stand as verdicts. |

### 5B — The 17 AGENT-ORIGIN claims

| # | Claim, and where it lives | Why it is agent-origin | A ruling decides |
|---|---|---|---|
| A1 | CLAUDE.md 1.7: "**Critical-review logic changes only** … one batched review per work burst" | **Zero** occurrences of "critical review" in 803 turns. He asked for *adversarial diagnostic panels* on the artefact (07-22, 07-23) — design/validity scoped, not a per-change code gate | Keep, rescope, or drop the per-change review gate. |
| A2 | CLAUDE.md 1.8: "**Refresh the navigation graph at commit time** … the ONLY rebuild path" | His entire recorded relationship with graphify is "fix graphify then", "Use graphify in you can", and 07-29: "changing 2 lines of code.. that took 25 minutes!? … all of that is actually fully retarded" — immediately after asking "**so, apparently somewhere i the docs there is something telling you to do this?**" | Whether a rule that cost him 25 minutes of a session, and that he had to ask the origin of, stays a hard rule. |
| A3 | `v3/README` 2.8: "Not GPT-4o, so HERB's published baselines get **re-run, not cited**." | No user statement on GPT-4o or on re-running vs citing. Defensible methodology presented under "Decided" | Whether it stays under "Decided" or moves to analysis. |
| A4 | `v3/README` 2.10: the equal-allocation / don't-compare-to-HERB's-average caveat | Correct and worth keeping, but it is an agent's analysis sitting under "Decided" as if ruled | Same. |
| A5 | `maths-algorithmist.md:15`: "**Never re-derive or re-propose what these close:** value-knee ≡ constant cut; every re-rank walls at ~0.79–0.80; stored w_facets are non-signal" | Agent measurements elevated to un-reopenable canon — and the 07-28 audit found clusterKglob-best and curve-walk-vs-constant **not significant** | Whether null results stay laws. Forbidding re-derivation of findings that failed significance is how a null result becomes a rule. |
| A6 | `maths-algorithmist.md:16`: state doc `2026-07-22…` "**§8 is binding**" | An agent-written state doc declared binding on a permanent specialist — against "just because the text is in the repo, that doesnt mean i was the one that ok'd it" (08-02) | Whether any state doc binds an agent. He distrusted this one the day it was written: *"i am going to assume that the agent that wrote the state doc now was.. unhelpful"*. |
| A7 | Four agent definitions: "the validity table in `v3/output/DATA_README.md` is **binding**" | DATA_README is agent-written; no user ruling adopts it. The content is technically sound | Adopt the table as canon, or drop the word "binding" from four hard-rule blocks. |
| A8 | `critical-reviewer.md`: "Never run `refresh_graph.py`" vs `maths-algorithmist.md:38`: "**After any edit** … run `python refresh_graph.py`" | Two definitions, opposite instructions on one script; the second also contradicts CLAUDE.md's "never per-edit" | One instruction. |
| A9 | `graph-refresher.md:21`: "**if this definition and REFRESH.md ever disagree, REFRESH.md wins**" | An agent-written procedure doc given precedence over an agent-written role doc, with no user anywhere in the chain | Whether precedence between two agent docs is a rule at all. |
| A10 | `maths-algorithmist.md:31`: "Mechanisms **the user judged not working** (chord break gluing, value-knee) stay dead unless the user reopens them" | **The attribution is false** — agents measured these; he never judged them. Same underlying items as C11 | Re-attribute, and decide whether they reopen. |
| A11 | `memory/feedback_commit_style.md`: no `Co-Authored-By` trailer, "**Why:** this is the user's master's thesis" | Zero hits for co-author/attribution/footer in 803 turns (though the May/June gap could hold it, and the desktop twin suggests it is real). The **rationale** is contradicted flatly: 06-14 "drop the fucking thesis... it's done, this is post-thesis work"; 07-22; 07-30 | Confirm the rule, and kill the thesis rationale. |
| A12 | `DESIGN.md` §14.7 "matched literals are **stripped before the interpreter**" vs MODEL_CONTRACTS §2 "**marked spans, not stripped**" — while §5b lists that revision as status "**open**" | An explicitly unapproved revision written into the contract body as settled prose, with the doc it revises left contradicting it | Strip, or mark spans. |
| A13 | `DESIGN.md` §15: "the cap **is fixed by design**" vs §9.1 "3000 is a calibration seed, **not a verdict**" | §9.1 is his position (06-04). §15 hardened it with no decision | Whether `CAP_TOKENS` is open and swept (see §2 item 14). |
| A14 | desktop `herb-eval-arm.md`: states both "**context_ids are real**" and "**`context_ids` is empty**"; both "the v1 full-text fallback is **DELETED**" and "**Gated full-text fallback kept**" | Two flat self-contradictions about the arm that produces every reported number. Either could be acted on | Which is true. |
| A15 | desktop `artefact-pass2-design.md` "hub nodes for shared field values" vs `v2-graph-spine.md` "the minted hub-node-per-label idea is **dead**" | Flagged honestly by the pass-2 file itself, which says it "needs an explicit sign-off, not silent resolution either way" | The hub-node question — same decision as **R5** and §2 item 2. |
| A16 | desktop `no-claude-attribution.md`: same rule and same thesis rationale as A11 | Two desktop memory files disagree about whether the thesis is live (`thesis-is-done.md` records it correctly) | Same as A11. |
| A17 | State doc `2026-07-22-v1-curve-walk-facets-and-cluster-k.md` §8 declared binding | Same underlying claim as A6, seen from the state-doc side | Same as A6. |

---

*Organisational only. No file outside `docs/canon/README.md` and this one was modified, no research
was run, and no conclusion was drawn that is not already in the sources cited.*
