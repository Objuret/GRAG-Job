# Canon audit — what the repo tells agents vs. what the user actually said

> **Interpretation, produced 2026-08-03, unreviewed by the user.** An agent built this in a few
> hours. It does not sit above the material it adjudicates — it is one more claim about intent
> and state, pending review, and its verdicts are not rulings. Every verdict holds only as far
> as the citation attached to it: intent is the user's own typed turns in
> `docs/canon/raw/user_turns_all.jsonl`, state is the git history, and every verdict is
> checkable against them. Listed unreviewed in `docs/canon/REVIEW_REGISTER.md`.

**Question asked.** Where does this repo's canon state something the user never said, and
where does it contradict something he did say?

**Ground truth used** (nothing else counts as the user's voice):

| Source | What it is | Strength |
|---|---|---|
| `docs/canon/raw/user_turns_all.jsonl` / `.md` | 803 verbatim human turns, 2026-05-14 → 2026-08-03, byte-verified against the raw transcripts | first-hand |
| `docs/canon/raw/desktop_docs_record.md` | user rulings + verbatim quotes recovered from the May/June desktop design docs | second-hand (agent-written notes of a conversation) |
| `docs/canon/raw/git_record.md` | 18 numbered contradictions from git objects alone | artifact-level, authorship-blind |

**Coverage limit, binding on every verdict below.** Nothing survives before 2026-05-14, and
**2026-05-16 → 05-26** and **2026-05-29 → 06-26** hold zero records of any kind. A claim with no
quote behind it in those windows is marked **unsupported in the surviving record** — never "the
user never said this". Where the window *is* covered and the record is dense (July onward, and
the June design docs), absence is meaningful and is stated as such.

**Classification.**

| Tag | Meaning |
|---|---|
| **[GROUNDED]** | Traceable to a user quote. Cited with date. |
| **[AGENT-ORIGIN]** | No support in the surviving record; an agent wrote it, and repetition made it canon. |
| **[CONTRADICTS-USER]** | The record shows the user saying otherwise. Both sides cited. |
| **[STALE]** | Was true; superseded by a later user decision or by the code. |

Mechanical repo description (file paths, how to run a script) is not adjudicated.

---

## Counts

One verdict per claim; where a claim is grounded as a rule but stale in application, it is counted
under the verdict that governs what an agent should *do* with it.

| | CLAUDE.md | v3/README | agent defs | laptop memory | DESIGN + CONTRACTS | desktop memory | state docs | **total** |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| GROUNDED | 12 | 5 | 6 | 12 | 7 | 19 | 4 | **65** |
| AGENT-ORIGIN | 2 | 2 | 6 | 1 | 2 | 3 | 1 | **17** |
| CONTRADICTS-USER | 3 | 2 | 2 | 2 | 0 | 1 | 1 | **11** |
| STALE | 3 | 3 | 0 | 3 | 6 | 7 | 2 | **24** |
| **adjudicated** | **20** | **12** | **14** | **18** | **15** | **30** | **8** | **117** |

**11 contradictions, 17 agent-origin claims, 24 stale** across 117 adjudicated prescriptive
statements. 65 — a clear majority — are genuinely the user's, correctly recorded.

Two things the raw counts hide:

- **Concentration.** 5 of the 11 contradictions sit in `CLAUDE.md` and the agent definitions —
  the two surfaces every agent loads before doing anything. A contradiction there is worth many
  in a dated state doc nobody opens.
- **Compounding.** The agent definitions have the worst ratio in the repo (6 grounded vs 6
  invented), and they are the surface that converts a claim into an enforced hard rule. Most
  agent-origin items elsewhere are inert; there, they bind.

The charge is substantiated but is narrower and more specific than "agents invented the canon":
**the behavioural rules are overwhelmingly the user's own words; the design and results claims are
where agents wrote themselves into canon.**

---

## The ten most damaging — ranked by work misdirected

Ranked by what each one actually *caused*, not by how wrong it is.

### 1. Five of seven "the user's concepts" are agent coinages — and agents are forbidden to change them
**[CONTRADICTS-USER]** · `memory/project_terminology_canon.md` + **six** agent definitions

> "**areas / levels / walk / anchor / support / stated-scope / parts** are the user's concepts —
> never rename or substitute them" — `logician.md:41`, and near-verbatim in `code-optimizer.md:35`,
> `critical-reviewer.md:38`, `eval-statistician.md:44`, `maths-algorithmist.md:34`, `graph-refresher.md:23`

Measured against all 803 turns:

| Term | User uses it? | Evidence |
|---|---|---|
| levels of k's | **yes** | "well the concepts i were intrested in were the 'fuzzy clustering', 'levels of k's' etc" — 07-20 |
| areas | **yes (marginal)** | "clustering of areas to increase to if hits are weak" — 07-15 |
| walk | **no** | 18 hits; every one is agent text or the user echoing it back ("i dont think the walk and the 'best fit' is helping eachother" — 07-22) |
| anchor | **no** | 5 hits, **all** inside agent-written text the user pasted |
| stated-scope | **no** | 4 hits, **all** agent text |
| support | **no** | technical sense appears only in agent text |
| parts | **no** | user uses the ordinary word ("parts of the project"); the *field named `parts`* is agent |

**What it caused.** The same memory system that correctly records *"gap cut, NNK, RRF are agent
translations, unaccepted"* commits the identical error one layer up — it launders four agent
coinages into "the user's concepts" and then makes them **unrenameable by rule** across six
agents. The user's actual complaint was exactly this: *"you keep saying things i am unsure of,
have not really accepted and just fucking exist there, like the nkk pruning, fusion arrengement,
gap cut.. NONE of these are something i named or invented, what the fuck are they?"* (07-20).
"Door" is the proof case — it is not on the protected list only by luck, and when the user finally
met it he said: *"Dude, what is with that fucking herb door trace!? WHAT DOES IT EVEN MEAN!?"*
(07-29).

### 2. `HERB_TAG_FIRST` makes tags a gate — 12 minutes after the user forbade it
**[CONTRADICTS-USER]** · `v3/pipelines/artefact_v1.py:167-211`, commit `6730d13`, branch name

> **User, 2026-08-01 11:53:** "ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE ffs.. tags are supposed
> to INFORM/weight the chunks"
> **Commit `6730d13`, 2026-08-01 12:05:06** — "tags-first retrieval regime"; code comment: "under
> `HERB_TAG_FIRST` a chunk **no matched tag**…" — i.e. tag membership admits or excludes.
> **Branch name:** `tag-first-cluster-guide`.

The user had said the same thing three times before: *"you and every other agent seem to be missing
that the whole fucking point of the tags, is guiding to the correct gold-bearing chunks"* (07-30),
*"i was under the impression that we did the whole fucking tag-clustering and facets and weights
just to fucking guide it all to the correct chunks"* (07-30).

**What it caused.** An entire retrieval regime, a branch, and a commit built on the inverted
reading. The 08-02 adversarial agent reached the user's conclusion independently: *"HERB_TAG_FIRST
is a category error — delete it. Tags weight, they don't select."* Work is still sitting on that
branch.

### 3. "The chunk description is dead" — contradicted by the user on 08-02 and by the shipping code
**[CONTRADICTS-USER]** + **[STALE]** · `CLAUDE.md`, `DESIGN.md` §9.1/§14.1

> **CLAUDE.md:** "**The chunk description is dead.**"
> **User, 2026-08-02 09:17:** "wasnt the plan to cluster the tags weighted by facets **in
> combination with chunk-descriptions** to find the best fit of chunks?"
> **User, 2026-07-06 12:24:** "the chunks contain a short description of the chunk … Pretty much
> all of this is embedded, the chunk description, the tagsnames, the facets"
> **Code at HEAD:** the description path is one of three fused rankings, with its own weight
> `W_DESC` over `chunk_desc_emb` (git_record C-5).

The rule is genuinely grounded **for the v3 native tagger** (06-11, desktop record: user killed the
per-chunk description there). CLAUDE.md states it **unqualified**, so every agent applies it to the
arm that actually ships, where the user still wants descriptions.

**What it caused.** Agents repeatedly proposed removing or demoting the description path; the
07-28 thread's `detDESCCORR` run made description corroborate-only and **recall collapsed to
~0.085**. The user's own 08-02 sentence shows he never left the description behind.

### 4. "Never analyze from git archaeology" — the user demanded git archaeology, in capitals
**[CONTRADICTS-USER]** · `memory/feedback_grounding.md`

> **Memory:** "Ground answers in current repo docs — never analyze from stale/legacy/quarantined
> files **or git archaeology**"
> **User, 2026-08-02 22:42:** "**THE GODDAMN GIT REPO HAS ALL THE FUCKING HISTORY SPOKEN IN
> COMMITS, DIFFS, CODE and DOCS.. what the actual fuck is wrong with you?**"
> **User, 2026-08-02 21:23:** "you do understand that we are currently in a branch we have cleared
> out of all 'old stuff' also, right? meaning **you have to dig in the repo if you want true info**"

**What it caused.** This is the single instruction that kept agents ignorant of their own project.
The working tree was deliberately cleared of the design era, so "current repo docs" is precisely
the surface that *cannot* answer a design question. `USER_CANON.md` had to open with a section
titled "**THE MISSING PERIOD IS NOT MISSING — IT IS IN GIT. GO READ IT.**" to undo it, and records
that "an earlier agent repeatedly claimed provenance was lost; it never was." The same agent
labelled 2026-07-15 "the first day" of a project that started 2026-05-07 — the user's reply:
*"Day one? 2 weeks ago.. you ARE retarded.."* (08-02).

### 5. Pre-registered pass/fail bars, which the user explicitly rejected
**[CONTRADICTS-USER]** · `maths-algorithmist.md:29`, `:15`

> **Agent def:** "**Compare against the standing bars before proposing.** A ranking change is only
> interesting past scope-alone (0.7926 det 10smoke); a per-query-K mechanism is only interesting
> past a constant cut at the same mean depth."
> **User, 2026-07-31 23:05,** shown a bar of exactly this shape: "what is this garbage? '*Bar fixed
> before running: paired recall gain over the 0.7339 baseline > +0.03, p < 0.05 … pass and the
> mechanism ships, fail and it joins the graveyard*' What do you mean?"
> **User, 23:09:** "what the fuck are you even talking about, pass fail?"
> **User, 23:10:** "**we already have the fucking scores to compare to, stop making random shit up**"

**What it caused.** A gate the user rejected in three consecutive turns is written into a permanent
specialist's hard rules, where it silently kills proposals before he ever sees them. Same file
line 15 forbids re-deriving a list of "closed" findings — several of which the 07-28 audit panel
found **not statistically significant**.

### 6. "v3/ — the work" and "the artefact rebuilt natively in v3/artefact/"
**[CONTRADICTS-USER]** · `CLAUDE.md` (opening line and the closing section)

> **CLAUDE.md:** "`v3/` — **the work** … The artefact is the system under test, **rebuilt natively
> in `v3/artefact/`**"
> **User, 2026-07-26 23:07:** "why cant you even understand the current state of things by reading
> the reapo.. **we are NOT doing the v3 artefact, we are doing the v1artefact**, however, since only
> v3 is the downloaded area here … we have imported the v1arm here so we can atleast finish these
> fucking benchmarks/evals/datacollections … but, **EVERYTHING i have been TRYING to build for
> weeks now, have been the actual v1artefact**"

**What it caused.** The most-read paragraph in the repo points every fresh agent at the wrong
artefact. It compounds with the next item: the file simultaneously tells agents the thing they
*are* working on is "not adopted".

### 7. "herb-eval … not adopted" — while it is the only artefact ever measured
**[STALE]** / live contradiction · `CLAUDE.md`; git_record **C-2**, "the largest live contradiction in the repo"

> **CLAUDE.md:** "`herb-eval` (Neo4j) is the prior artefact build under the superseded design — a
> contrast/forensic baseline only, **not adopted**. … **never query `herb`**"
> **Code at HEAD:** `DATABASE = os.environ.get("NEO4J_DATABASE", "herb-eval")` — every artefact
> number the project has ever reported comes from this graph.
> **Canon drift is one-sided:** at `0efff16` the same rule read "**`herb-eval` is the canonical
> Neo4j DB**". The code never moved; the canon flipped around it.

**What it caused.** Agents periodically "discover" that the arm under test is illegitimate and
propose re-pointing it at `herb-v3` — a database git shows was **never populated** (G-5). The user's
position is settled and opposite: *"what the fuck are you even talking about, the v1artefact is
using the same fucking neo4j db, what do you think we are talking about?"* (07-26).

### 8. Graph refresh as a hard rule at every commit
**[AGENT-ORIGIN]**, and the user pushed back on its cost · `CLAUDE.md` hard rules

> **CLAUDE.md:** "**Refresh the navigation graph at commit time** … It is the ONLY rebuild path …
> If it prints a worklist, process it before committing."
> **The user's entire recorded relationship with graphify:** "fix graphify then" (07-20); "Use
> graphify in you can" (07-01); and — **07-29 23:02** — "ok, but the graphify is only supposed to
> update actually new things, so that should not take 17 fucking minutes, and changing 2 lines of
> code.. that took 25 minutes!? no, you are not reporting something here because all of that is
> actually fully retarded."
> Immediately before that, **07-29 23:00**: "**so, apparently somewhere i the docs there is
> something telling you to do this?**"

**What it caused.** The user caught this one live: a rule an agent wrote into CLAUDE.md was
consuming 25 minutes of his session, and he had to ask where it came from. It is still a hard rule.
Nothing in the record shows him asking for it.

### 9. "The model emits no numbers, ever" — true canon, applied to the wrong system
**[STALE]** · `CLAUDE.md`, `MODEL_CONTRACTS.md` §0; git_record **C-13**

> **Canon:** "**The model emits no numbers, ever** (tagger and interpreter)."
> **Grounded:** desktop record 06-11 §3 marks this **[USER-STATED]** — the user's own rule, with his
> v1 evidence: *"it took so fucking long to get it right and it still didn't work at all."*
> **Shipping arm:** the `artefact_v1` interpreter's pass-2 prompt is literally "Score retrieval tags
> against five facets (each 0.0-1.0)" and the validator **raises** if a facet value "is not a number".

**What it caused.** The rule is real and the user's. But canon states it as if the v3 artefact were
the system being measured, and it is not — so agents auditing the shipping arm find a flat canon
violation at its core and cannot tell whether to fix the code or the doc. The 07-22 adversarial
panel spent a review cycle on exactly this ("the interpreter emits facet numbers — check against
canon").

### 10. "Chase the score" framing baked into the memory index — **fixed 2026-08-04**
**[CONTRADICTS-USER]** · the two memory entries are deleted; run numbers live in
`v3/output/DATA_README.md`, recomputed from disk and carrying the unmatched-unit rule.
No memory entry holds a run number. The finding below is what they said.

> **Memory index, top two lines:** "artefact **0.594 vs vector 0.112 / lucene 0.074** … **wins all
> five type cells** … the lead generalizes"; "artefact **leads all valid metrics** (recall_id 0.64
> vs 0.09/0.11)"
> **User, 2026-07-25 01:45:** "what the fuck is it with you agents and the absurde insane fucking
> need to '**chase the highest number**' **i have fucking nowhere said or hinted that a high … score
> on something is the fucking target and point of this**. the fucking POINT, is that the ARTEFACT,
> is academically VALID according to WHAT THE FUCK I AM TRYING TO BUILD"
> **And the headline is known-bad:** the 07-28 audit panel found the 0.64-vs-0.09 figure is "**~85%
> unit artifact**; matched-budget ~1.8× is the real lead" — recorded in a *different* memory entry
> that does not correct the two above it.

**What it caused.** The first thing any agent read was a scoreboard the user disowned, quoting a
number a later audit invalidated: two memory entries asserted the win, a third quietly said it was
mostly an artifact, and nothing reconciled them. One record now carries all three readings —
k=50 unmatched (disqualified as a lead), matched 500-id budget (~1.79×), and the claims that fail
their own significance test.

---

## Surface 1 — `CLAUDE.md`

The file every agent loads first. Highest priority.

### Hard rules

| # | Claim (quoted) | Verdict | Evidence |
|---|---|---|---|
| 1.1 | "**Design before build:** no pipeline code until the relevant stage's design is explicitly signed off by the user." | **[GROUNDED]** | Desktop record 06-11 §3, **[USER-STATED]**: *"that means we fucking have to make sure all parts are decided upon first."* Reinforced 07-25: *"dude, stop treating every fucking question i have as a need to rewrite shit, i will fucking tell you if i want something rewritten"*; 07-25: *"STOP then, if nothing needs to fucking change, DONT CHANGE IT"*. |
| 1.2 | "**Talk to the user in plain spoken English, short answers** — no jargon walls" | **[GROUNDED]** | 06-12: *"use speech english instead of this almost 100% jargon."* 07-16: *"i am not fucking reading pages of info from you"*. 07-25: *"you are writing too fucking much, I DO NOT NEED THAT"*. 07-29: *"this wzs way too much and a bit incoherent, i'm not reading that"*. |
| 1.3 | "**Heed the user's intent — never 'correct' it with stale context.**" | **[GROUNDED]** | 07-21: *"well, you are both bastardizing and forgetting the origins, those are my thoughts defiled, the origial concepts were mine"*. 06-25: *"MY WORDS ARE THE CANON"*. |
| 1.4 | "**Docs track reality** … by removal of dead content, not banners. Dated state/handoff docs are frozen" | **[GROUNDED]** | 06-12: *"please do continously update information according to the things we decide"* / *"did you REMOVE, quarantine, legacy-note or something else"*; and *"that shit is still true for THAT build"* (frozen docs). |
| 1.5 | "**No historical or defensive comments** … no 'previously/now', 'no longer', 'NOT because', 'do not factor out', no review-finding labels." | **[GROUNDED]** on the principle; **[AGENT-ORIGIN]** on the specific banned-phrase list | Desktop record 06-23 records this as a hard rule from that session. The enumerated phrase list ("do not factor out", "NOT because") is agent-authored detail; no user quote uses them. |
| 1.6 | "**Every runnable shows life instantly and progress continuously** … A silent terminal — or a run buried where the user can't watch it — is a bug, full stop." | **[GROUNDED]**, verbatim in spirit | 07-16 08:42: *"literally 0 fucking output-response.. can you add some sort of permanent understanding of the human need to see/feel the fucing progress"*; 07-16 08:53: *"we have fucking 'progress graphics' on everything else here, seriously, if i start yelling at you, **perhaps thats a thing you should have in the .md** for all of this"* — the user explicitly asked for this rule to be written down. |
| 1.7 | "**Critical-review logic changes only:** after changing real logic in `v3/`, run `/critical-review` … one batched review per work burst" | **[AGENT-ORIGIN]** | **Zero** occurrences of "critical review" / "critical-review" in 803 turns. The user asked for *adversarial diagnostic panels* on the artefact (07-22 14:14, 07-23 14:07) — a different thing, scoped to design/validity, not a per-change code gate. The batching rule and the trigger conditions have no user source. |
| 1.8 | "**Refresh the navigation graph at commit time** … the ONLY rebuild path (never `graphify --update`)" | **[AGENT-ORIGIN]** — see ranked item 8 | Only user graphify statements are "fix graphify then" and a complaint that it cost him 25 minutes, followed by *"so, apparently somewhere i the docs there is something telling you to do this?"* (07-29). |

### Repo-shape and design claims

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1.9 | "`v3/` — **the work** … Self-contained." | **[CONTRADICTS-USER]** | Ranked item 6. 07-26: *"we are NOT doing the v3 artefact, we are doing the v1artefact"*. |
| 1.10 | "The artefact is the system under test, **rebuilt natively in `v3/artefact/`**" | **[CONTRADICTS-USER]** | Same. The system actually under test is `pipelines/artefact_v1.py` over `herb-eval`. |
| 1.11 | "The graph proper — chunk → tag → facet retrieval — is **the unbuilt part**; **`pipelines/artifact.py`** is the arm entry that drives it." | **[STALE]** — factually false at HEAD | git_record **C-14**: `pipelines/artifact.py` does not exist (deleted at `a515c94`, replaced by `artefact.py`); `chunk.py`, `tag.py`, `index.py`, `graph_store.py`, `interpreter.py` all exist. Only the *facet* layer is unbuilt. |
| 1.12 | "**The graph spine is closed canon:** `Source → File → Chunk → Tag` are the only nodes." | **[GROUNDED]** | Desktop record 06-12, from the user's own node/attribute rule: *"if we are saying file -> chunk ->tags .. where are those OTHER RANDOM FUCKING NODES!?"* and *"perhaps it's smarter to just have shit like that as attributes on chunks."* |
| 1.13 | "The graph is references into untouched raw source, **never copies**" | **[GROUNDED]** | 07-06 10:54: *"the actual content should never exist in the graph at all, and we fixed that by just making pointers again, right?"* |
| 1.14 | "**The model emits no numbers, ever** (tagger and interpreter)." | **[GROUNDED]** as a rule, **[STALE]** as applied | Ranked item 9. Grounded at 06-11; violated by the arm that ships. |
| 1.15 | "**The chunk description is dead.**" | **[CONTRADICTS-USER]** as written (unqualified) | Ranked item 3. User re-asserts chunk-descriptions in the plan on **08-02**. |
| 1.16 | "Tags are per-chunk contextual phrases." | **[GROUNDED]** | 06-11: *"what if we don't do the word, and just have the embedded 'small concept' as the node"*; *"Since the collective tags from a chunk should BE the content of the chunk, why do both?"* |
| 1.17 | "**`herb-eval` … not adopted** … never query `herb` (oracle-contaminated)" | **[STALE]** / live contradiction | Ranked item 7 (git_record C-2). The oracle-contamination point for `herb` specifically **is** grounded (06-14: *"DONT INCLUDE THE FUCKING EVAL FILES FOR THE PROBE TO EVER SENSE."*). The "not adopted" clause is what conflicts. |
| 1.18 | "**Agent roster** — the main-chat Claude is the orchestrator … it does no hands-on work itself … Agents always run in the background" | **[GROUNDED]** | 07-22 15:36: *"you are from now on always only the orchestrator … YOU however ALWAYS send an agent to do the job i ask you to do"*; 07-22 15:45 (the roster, itemised by the user); 07-29 22:48: *"do that shit with a fucking worker in the background, stop highjacking my conversation"*. |
| 1.19 | "Long runs still happen in the user's terminal: agents prepare, the user runs." | **[GROUNDED]** | 07-16 07:40: *"let ME be the one that actually runs the scripts here"*. |
| 1.20 | Entry-point pointer: "`docs/state/2026-07-28-…md` — **Read this first for any artefact_v1 retrieval work.**" | **[STALE]** — path is wrong on this machine | The state docs live flat in the OneDrive `state-transfer\GRAG-Job` folder, not `docs/state/`. The laptop memory already records this drift; CLAUDE.md still points into a directory that does not hold them. Newest doc is 2026-08-03, not 07-28. |

**CLAUDE.md subtotal: 12 GROUNDED · 2 AGENT-ORIGIN · 3 CONTRADICTS-USER · 3 STALE (20 claims).**

The pattern in this file: **the working-relationship rules are almost all genuinely the user's**
(items 1.1–1.6, 1.18, 1.19 — he asked for several of them in so many words). **The
machinery rules are the invented ones** (1.7, 1.8), and **the design statements have drifted off
the system that actually ships** (1.9–1.11, 1.14, 1.15, 1.17).

---

## Surface 2 — `README.md` (root) and `v3/README.md`

Root `README.md` is 344 bytes of pointer text. Nothing prescriptive. Not adjudicated.

`v3/README.md` carries a "## Decided" heading, which makes every line under it a canon claim.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 2.1 | "**artifact** — the artefact graph … The system under test, **built natively in v3**." | **[CONTRADICTS-USER]** + self-violating | Same as 1.10. It also spells the arm `artifact`, which the terminology canon every agent is made to enforce declares a different thing ("artefact = system under test; artifact = a HERB source record"). The canon's own reference file breaks the canon. |
| 2.2 | "**RAGAS is the only scorer.**" | **[GROUNDED]** | 06-25, twice and emphatically: *"this is ONLY RAGAS"*. This also resolves git_record **C-17**'s alarm that the deleted HERB anchor metric had "no rationale anywhere" — the rationale is a user ruling that git could not see. |
| 2.3 | "a top-k budget shared across arms (that it's *shared* is decided; **the value itself is still open**)" and "**Still open:** top-k budget" | **[STALE]** | k=50 has been the operating value since 06-27 and is grounded (06-25 desktop record: k=50 justified by HERB's median-52 citation count; user 06-27: *"for academic rigor, we have done k=50 now"*). The doc still calls it open. The user separately flagged the real problem, which the doc does not record: *"k=50 does not mean the same for all arms, and thats retarded"* (07-26). |
| 2.4 | "the judged metrics use the default haiku judge (`claude-haiku-4-5`)" | **[GROUNDED]** | 07-16: *"try haiku first then"*; 07-29: *"we decided to use haiku for the fucking evals also, was that entire line of thought erased?"* |
| 2.5 | "**Provenance** is two manifests … **no seed, no git-sha**." | **[CONTRADICTS-USER]** | 07-16 07:43: *"remember that the data about the builds ETC is important for **traeability, reproducibility etc, academic purposes**"*. A recorded decision to carry no seed and no git-sha means no run can be tied to the code that produced it — git_record G-9 lists this as the reason **no committed run is reproducible**. The user asked for the opposite property by name. |
| 2.6 | "**One LLM — generator** … `qwen/qwen3.5-397b-a17b` … **is still the shared generator**" | **[STALE]**, contested | Grounded originally (one shared generator so only retrieval varies — sound and never disputed). But the user's position on qwen hardened: *"why the fuck are we even using qwen anymore, this is so stupid, it just cannot take this fucking long"* (07-19); *"the question was if a claude model was viable to swap out for because qwen ia NIM is fucking uselessly slow"* (07-18). The judge was swapped to haiku; the generator was not, and the README does not record that this was ever decided. |
| 2.7 | "Multilingual, so HERB now and **the deferred Swedish Bonnier set** run on the same generator" | **[GROUNDED]** | 06-14: *"the Bonnier set will have to wait until some other time."* |
| 2.8 | "Not GPT-4o, so HERB's published baselines get **re-run, not cited**." | **[AGENT-ORIGIN]** | No user statement on GPT-4o or on re-running vs citing HERB baselines. Defensible methodology, but it is the agent's call presented under "Decided". |
| 2.9 | "**Generation contract — a thin, fixed RAG pipe** … held byte-identical across all three arms" | **[GROUNDED]** | The independence principle is from the user's framing that the comparison must be of retrieval only; desktop record 06-23 records "arms share only the corpus on disk and the injected generator — sharing a reader is contamination, not fairness" as that session's ruling. |
| 2.10 | "Equal allocation … **does not match HERB's natural mix**, so report per-type and don't compare the gold-100 aggregate to HERB's published average." | **[GROUNDED]** in spirit, **[AGENT-ORIGIN]** as written | The user demanded academic validity repeatedly (06-27: *"I WANT TO GATHER ALL THE DATA … this is an academic effort"*), but the specific caveat is an agent's analysis. It is correct and worth keeping — flagged only because it sits under "Decided" as if ruled. |
| 2.11 | "Arms … share **nothing** beyond the generator and the corpus on disk" | **[GROUNDED]** | Desktop record 06-23. |
| 2.12 | "(The orchestrator currently runs a single combined path; splitting it into the three modes is **the pending step**.)" | **[STALE]** | Describes a build state superseded by the run flow actually used since July (`--retrieval-only`, `--no-eval`, `--judge` re-scoring all exist and the user runs them by name). |

**v3/README subtotal: 5 GROUNDED · 2 AGENT-ORIGIN · 2 CONTRADICTS-USER · 3 STALE (12 claims).**

---

## Surface 3 — `.claude/agents/*.md` (ten agent definitions)

These encode routing and rules as canon and are loaded by every specialist. They are the second
most consequential surface after CLAUDE.md, and the least audited.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 3.1 | "**areas / levels / walk / anchor / support / stated-scope / parts are the user's concepts** — never rename or substitute them" — in six of ten definitions | **[CONTRADICTS-USER]** | **Ranked item 1.** Five of the seven are absent from 803 turns except as agent text. |
| 3.2 | "**Compare against the standing bars before proposing.** A ranking change is only interesting past scope-alone (0.7926 det 10smoke)" — `maths-algorithmist.md:29` | **[CONTRADICTS-USER]** | **Ranked item 5.** User rejected pre-set pass/fail bars three turns running on 07-31. |
| 3.3 | "**Never re-derive or re-propose what these close:** value-knee ≡ constant cut; … every re-rank of existing door values walls at ~0.79–0.80; stored w_facets are non-signal" — `maths-algorithmist.md:15` | **[AGENT-ORIGIN]**, and partly invalidated | These are agent measurements elevated to un-reopenable canon. The 07-28 audit panel found "clusterKglob-best and curve-walk-vs-constant **not significant**". Forbidding re-derivation of results that failed significance is how a null result becomes a law. Note also the term "**door**" appears here inside a rule about respecting the user's vocabulary — it is an agent coinage the user asked the meaning of (07-29). |
| 3.4 | "`docs/state/2026-07-22-…md` — current design state, the user's verdicts, rejected interpretations (**§8 is binding**)" — `maths-algorithmist.md:16` | **[AGENT-ORIGIN]** | A state doc section is declared binding on a permanent specialist. The user's standing rule is the opposite: *"you do understand that just because the text is in the repo, that doesnt mean i was the one that ok'd it or put it there"* (08-02). He also pre-emptively distrusted this exact document: *"i am going to assume that the agent that wrote the state doc now was.. unhelpful"* (07-22). |
| 3.5 | "the validity table in `v3/output/DATA_README.md` is **binding**" — `critical-reviewer.md:11`, `eval-statistician.md:23`, `logician.md:42`, `maths-algorithmist.md:35` | **[AGENT-ORIGIN]** | DATA_README is agent-written; no user ruling adopts it. The *content* is technically sound (id-density differs per arm, so `precision_id` really is not cross-arm) and worth keeping — but it is agent analysis wearing the word "binding" in four separate hard-rule blocks. |
| 3.6 | "the settled daily judge is claude-haiku-4-5 (**a closed decision — do not reopen it**)" — `eval-statistician.md:15` | **[GROUNDED]** | 07-29: *"we decided to use haiku for the fucking evals also"*. |
| 3.7 | "For any proposed run calling a claude-* model: compute tokens × calls × concurrency … **state the total out loud** … **This is a hard rule with no de-minimis exception.**" — `eval-statistician.md:40` | **[GROUNDED]**, with a documented tension | Grounded hard by consequence: 07-17 *"literally burned almost my entire usage in 30 seconds"*; 07-23 *"you just burned 70% usage on NOT finishing the fucking evals!?"*; 07-24 *"you actually burned my entire usage in 5 minutes achieveing NOTHING … how about you fucking solve this BEFORE you waste all my usage"*. The tension: 06-18 the user said *"YOU do not care about cost here, 0 fucks given… only for me. so fucking drop that fast as fuck."* Both are real; the July burns superseded the June instruction. Worth recording as *superseded*, since a future agent reading only the June record would drop the guard. |
| 3.8 | "**You design judge runs; you do not launch them.**" / "agents prepare, the user runs" | **[GROUNDED]** | 07-16: *"let ME be the one that actually runs the scripts here"*. |
| 3.9 | "**No historical or defensive comments** … flag them wherever the reviewed change adds them" | **[GROUNDED]** | Desktop record 06-23 hard rule. |
| 3.10 | "Never run … `refresh_graph.py`" (critical-reviewer) vs "**After any edit** under `v3/` … run `python refresh_graph.py`" (maths-algorithmist:38) | **[AGENT-ORIGIN]**, and mutually inconsistent | Two definitions give opposite instructions on the same script, and the second contradicts CLAUDE.md's own "never per-edit; one refresh per commit". Nothing here traces to the user. |
| 3.11 | "`REFRESH.md` is the procedure canon. Follow it exactly; **if this definition and REFRESH.md ever disagree, REFRESH.md wins**" — `graph-refresher.md:21` | **[AGENT-ORIGIN]** | An agent-written procedure doc is given precedence over an agent-written role doc, with no user anywhere in the chain. |
| 3.12 | "**Propose; never build unaccepted design.** Design sign-off belongs to the user" — `maths-algorithmist.md:31` | **[GROUNDED]** | 06-11 build gate; 07-25 *"i will fucking tell you if i want something rewritten"*. |
| 3.13 | Routing table: ten named specialists | **[GROUNDED]** | 07-22 15:45, the user itemising them: *"one code optimization expert/phd, one for maths algoritms, one for order of operations, one for logic and so on"*. |
| 3.14 | "Mechanisms **the user judged not working** (the chord break gluing, the value-knee) stay dead unless the user reopens them" — `maths-algorithmist.md:31` | **[AGENT-ORIGIN]** — attribution is false | The chord-break and value-knee verdicts were reached by *agents* measuring, not by the user judging. Attributing an agent's null result to the user's judgement is the audit's core pattern in miniature. |

**Agent-definition subtotal: 6 GROUNDED · 6 AGENT-ORIGIN · 2 CONTRADICTS-USER · 0 STALE (14 claims).**

This surface has the **worst grounded-to-invented ratio in the repo**. The rules about how to
*behave* are grounded; the rules about what is *settled science* in the project are largely
agents citing other agents.

---

## Surface 4 — laptop memory (`C:\Users\jocke\.claude\projects\C--Coding-exjobbet-GRAG-Job\memory\`)

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 4.1 | `project_terminology_canon.md`: "**Current arm (user's design) terms:** … **pool** … **areas** … **anchors** … **levels** … **support** … **walk** … **stated-scope part**" | **[CONTRADICTS-USER]** | **Ranked item 1.** The file's own provenance line convicts it: "*Grounded 2026-07-21 from v3/README.md, v3/output/DATA_README.md, docs/state/…, CLAUDE.md, and the live code.*" — **every source is an agent artifact.** A vocabulary labelled "the user's design terms" was assembled without consulting a single thing the user said. It flags exactly one coinage ("surface") while laundering four others. |
| 4.2 | `feedback_user_concepts_are_canon.md`: "fuzzy clustering / levels of k's / query-relative areas are the USER's concepts; gap cut, NNK, RRF are agent translations, unaccepted" | **[GROUNDED]** — the best entry in the memory | Accurately records 07-20/07-21. "fuzzy clustering", "levels of k's", "relevance spheres" are verbatim user terms. ("query-relative areas" is the agent's phrasing of his "clustering of areas".) This entry proves the project *could* tell the difference — and 4.1 shows the same memory system failing to. |
| 4.3 | Index line: "Ground answers in current repo docs — never analyze from stale/legacy/quarantined files **or git archaeology**" | **[CONTRADICTS-USER]** as summarised | **Ranked item 4.** In fairness the *body* of `feedback_grounding.md` is more careful — it says "Git is fine as a tool; the earlier 'stop gitting' was about using archaeology to *avoid* reading docs, not a ban on git." The index line drops that clause, and the index is what agents skim. Once the working branch was deliberately cleared of the design era, "read current repo docs instead of git" became an instruction to stay ignorant. |
| 4.4 | `feedback_commit_style.md`: "Do NOT include the `Co-Authored-By: Claude` trailer … **Why:** This is the user's exjobb (master's thesis)" | Rule **[AGENT-ORIGIN]** (unsupported in the surviving record); rationale **[CONTRADICTS-USER]** | Zero hits for "co-author", "attribution", or "footer" in 803 turns — though the May/June gap could hold it, and the desktop `no-claude-attribution.md` suggests it is real. The **rationale** is contradicted flatly: 06-14 *"drop the fucking thesis... it's done, this is post-thesis work"*; 07-22 *"thesis? wtf? we are building the fucking artefact here"*; 07-30 *"why the fuck are you going on about 'the thesis'?"*. |
| 4.5 | `feedback_trust_revoked.md`: "Take **NO action** … without an explicit instruction naming that action. Questions get answers … Neither gets a tool call beyond read-only lookups." | **[GROUNDED]** at origin, **[STALE]** in its absolutist form | Origin is solid (07-16: *"trust revoked you fucking maniac"*; *"Me having a fucking opinion will NEVER be a fucking command"*). But the user then spent two weeks demanding the opposite: *"just fucking DO shit ok"* (07-21), *"build it ffs"* (07-31), *"why the fuck dont you understand that you should spend almost all of your time in finding a good SOLUTION, not fucking testing"* (07-30), and *"and you fucking just run off and start working without a single fucking word again"* (07-30 — wanting narration, not paralysis). Read absolutely, this entry produces the passivity he complained about. |
| 4.6 | "artefact **leads all valid metrics** (recall_id 0.64 vs 0.09/0.11)" | **[FIXED 2026-08-04]** | **Ranked item 10.** The entry is deleted. `v3/output/DATA_README.md` carries the number with the unmatched-unit rule, and records that "leads all valid metrics" fails its own test (`answer_correctness` vs vector p=0.096). |
| 4.7 | "artefact 0.594 vs vector 0.112 / lucene 0.074 … **the lead generalizes**" | **[FIXED 2026-08-04]** | The entry is deleted. The held-out numbers are in the run record, read at k=50 and labelled unmatched-unit. |
| 4.8 | `feedback_visible_progress.md`: "print within 1s, heartbeat per model call, **never bury runs in background tasks**" | **[GROUNDED]** | 07-16 08:42/08:53/09:00. The user asked for it to be written into the .md. |
| 4.9 | `feedback_background_workers.md`: "**always** run_in_background true; foreground agent runs freeze the chat" | **[GROUNDED]** | 07-29 22:48. Note it sits in direct tension with 4.8's "never bury runs in background tasks" — the distinction (agents background, *runs* foreground in the user's terminal) is real but is not stated in either entry. |
| 4.10 | `feedback_never_relaunch_expensive_runs.md` / `feedback_judge_run_cost_math.md` | **[GROUNDED]** | 07-17, 07-23, 07-24 usage burns, quoted at 3.7. |
| 4.11 | `feedback_react_to_anger.md`: "acknowledge and name the failure before continuing" | **[GROUNDED]**, near-verbatim | 07-21 11:10: *"i need you to start actually reacting to getting yelled and cursed at, i need you to show you understand why i am getting angry because ignoring it is making it worse"*. |
| 4.12 | `feedback_infer_context_like_a_human.md` | **[GROUNDED]**, near-verbatim | 07-16 11:21: *"i am ALYWAY, without exception, having our latest actions, conversation, prompt, in mind when i am talking to you"*. |
| 4.13 | `feedback_commit_means_push.md` | **[GROUNDED]**, verbatim | 07-23 16:25: *"if i EVER ask you to commit, its a fucking push too, just push to a feature-arm or something"*. |
| 4.14 | `feedback_orchestrator_mode.md` | **[GROUNDED]**, verbatim | 07-22 15:36. |
| 4.15 | `feedback_reusable_tools.md`: "never weld a tool to one experiment" | **[GROUNDED]**, verbatim | 07-17 12:18: *"stop making fully fucking custom scripts i cant reuse for other things all the time"*. |
| 4.16 | `project_source_of_truth.md`: "real impl/docs live on origin/djuret/monorepo; **main + quarantine/ are legacy**" | **[GROUNDED]** | 05-14 (the user's own quarantine instruction, quoted by him verbatim); git_record confirms `origin/main` is not the work line. |
| 4.17 | `feedback_final_audit_panel.md`: three-adversary panel required before shipping | **[GROUNDED]**, verbatim | 07-23 14:07 — the user specified all three roles in one sentence. |
| 4.18 | `project_adversarial_panel_verdicts.md`: "stop rule **condemned** (permutation-proven uninformative)" | **[GROUNDED]** | Aligns with the user's own instinct on 07-23: *"'if fewer than 8 questions move, it's noise, stop' does this fucking matter if it only takes seconds?"* |

**Laptop-memory subtotal: 12 GROUNDED · 1 AGENT-ORIGIN · 2 CONTRADICTS-USER · 3 STALE (18 claims).**

The behavioural entries are excellent — many are near-verbatim and correctly dated. The damage is
concentrated in the two *project*-type entries that describe the design (4.1) and the results
(4.6, 4.7).

---

## Surface 5 — `v3/artefact/DESIGN.md` + `MODEL_CONTRACTS.md`

CLAUDE.md already brands §13–14 and MODEL_CONTRACTS §1 stale. The audit's finding is that
**staleness is not the main problem — unapproved content written as settled is.**

Credit where due: `MODEL_CONTRACTS.md` opens with the healthiest sentence in the whole repo —
*"**Working draft — approvals happen per-call, in conversation, schemas shown inline** (the doc
itself is never the approval)."* That is the direct institutional memory of the user's 06-14
rejection: *"i never saw the fucking schema."* This is the discipline every other surface lacks.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 5.1 | §14.7: "Matched literals are **stripped before the interpreter**" vs MODEL_CONTRACTS §2: "**marked spans, not stripped**" — and §5b lists that revision as status **"open"** | **[AGENT-ORIGIN]** — the pattern in its purest form | An **explicitly unapproved** revision (`b | open`) is written into the contract body as settled prose, while the doc it revises is left contradicting it. The user's rule: *"you literally put shit in writing and pretend its canon"* (08-02). |
| 5.2 | §13.5 per-facet extraction spec — "This is what the v2 tagger prompt encodes per facet — the missing spec that caused v1 degradation" | **[STALE]** — specified, never built | git_record **C-7**. The built `tag.py` emits `{"tags": ["..."]}`, a flat list, with the docstring "no facets (facets are measured later)". The most carefully specified artifact in the repo was replaced by a one-paragraph prompt, and no commit explains it (G-4). |
| 5.3 | §7 "Nothing else is a node" vs §13.1 "identities to `:Employee`/`:Customer` edges" and §9.6 "IDs, dates, and authors are now structural (**entities** + properties)" | **[STALE]** — unremoved residue | git_record **C-9**. Also §9.5 still argues from `:COVERS` edges that §7 abolished. This is the exact failure CLAUDE.md's "docs track reality … by removal of dead content" rule exists to prevent, sitting inside the design reference. |
| 5.4 | §11 tagger model `mistral-large-3-675b…`, justified by "**Swedish semantic fidelity (the Bonnier dataset)**" | **[STALE]** — the rationale was out of scope when written | git_record **C-10**. §12 of the *same file* defers Bonnier. The built tagger uses `z-ai/glm-5.1` (China-trained — the category the rationale rules out), and nothing documents the change. Three different interpreter models are named across three files. |
| 5.5 | §13.4 table: function/TAM are **tag-facets** vs MODEL_CONTRACTS §1: function/TAM are "**chunk attributes, not tags, never embedded**" — and DESIGN's own STATUS block agrees with the *contracts* file against its own table | **[STALE]**, self-contradicting | Three statements, two positions, one file. |
| 5.6 | §9.1 "3000 is a calibration seed, **not a verdict**" vs §15 "the cap **is fixed by design** … what's open is only the empirical sweep" | **[AGENT-ORIGIN]** drift | The user's position is the first one: desktop record 06-04, *"3000 is a calibration seed, not final."* §15 hardened it without a decision. The sweep was never run (git_record C-15). |
| 5.7 | §1 "the graph indexes references, it does not store copies" | **[GROUNDED]** | Desktop record 05-30, verbatim: *"thats the fucking reason i dont even want the data loaded into the goddamn graph, thats why i just want the fucking references."* |
| 5.8 | §7 "The graph is `Source → File → Chunk → Tag`. Nothing else is a node." + the node/attribute rule | **[GROUNDED]** | 06-12, the user's own rule: *"either they are nodes, but then we get edges to EVERY fucking chunk, or they are just attributes."* |
| 5.9 | §14.4 "**No hard filters anywhere in ranking**. Facets always *order*, never *filter*." | **[GROUNDED]** — strongly | 07-15: *"gate? wtf? why have a gate? why not ust that as promoted guidance? … hard filter seems insane, much better to use rankings"*. Desktop record marks it "the user wants NO hard filters anywhere — decided, strong stance". **This makes `HERB_TAG_FIRST` (ranked item 2) a violation of design canon as well as of a direct instruction.** |
| 5.10 | §14.9 "the embedding-axis-projection machinery … is dead (**it was never the user's design**)" | **[GROUNDED]**, and exemplary | The doc explicitly labels an agent invention as such and kills it — citing the user's 06-11 *"honestly, none of what you are saying now is a thought I have had, where the fuck did all of this even come from."* This is how every entry in this audit should have been handled at the time. Note §11 still justifies the embedder by "it sets the **facet-axis projection**" — the dead machinery. |
| 5.11 | §4 stage 0 structural oracle quarantine | **[GROUNDED]** | 06-14: *"DONT INCLUDE THE FUCKING EVAL FILES FOR THE PROBE TO EVER SENSE."* / 06-11: *"we just don't fucking include the eval part in the dataset, why is this an issue even"*. |
| 5.12 | §9.5 "**No overlap**", §9.4 deterministic boundary detector, embedding-based chunking rejected | **[GROUNDED]** | Desktop record 06-03; topic-drift segmentation is explicitly logged there as "the assistant invented it mid-conversation; never in the docs" and killed. |
| 5.13 | §12 "The SQL-agent remains the comparison baseline" | **[STALE]** | Three arms (artefact / lucene / vector) plus hybrid. Desktop memory notes the SQL-agent was "adopted, then silently un-adopted". |
| 5.14 | Both docs address a **`backend/v2/`** tree that no longer exists; DESIGN cites `v2_model_contracts.md`, MODEL_CONTRACTS cites `v2_artefact_rebuild_design.md` — neither filename exists | **[STALE]** | Mechanical, but it means every cross-reference in the design reference is dead. |
| 5.15 | MODEL_CONTRACTS §0 "**No numbers cross the model boundary, either direction.**" | **[GROUNDED]** as canon, **[STALE]** as applied | See ranked item 9. |

**DESIGN + MODEL_CONTRACTS subtotal: 7 GROUNDED · 2 AGENT-ORIGIN · 0 CONTRADICTS-USER · 6 STALE (15 claims).**

Note the zero: these documents do not contradict the user. They contradict *each other* and the
shipped code (13 internal/cross-file conflicts). They are stale, not invented — largely because
`MODEL_CONTRACTS.md` kept the "the doc itself is never the approval" discipline.

---

## Surface 6 — desktop memory (`docs/canon/raw/desktop_memory/`, 53 files)

This is the **best-attributed surface in the project**. Roughly 30 of its entries carry an explicit
user quote in a "Canonical user-established facts" slot, and several files name their own agent
inventions and kill them (`v2-chunking-model.md`: *"the assistant invented it mid-conversation"*;
`retriever-routing-model.md`: *"assistant invention, never the user's"*). The June discipline
worked. It was then lost.

Grounded, verbatim-quoted, and correct — not itemised further: `graph-is-references-not-copies`,
`v2-graph-spine`, `design-before-build`, `docs-track-reality`, `heed-user-intent-not-correct-it`
(*"MY WORDS ARE THE CANON"*), `no-silent-fallbacks`, `no-cutting-corners`, `delete-dont-preserve`,
`check-existing-before-adding`, `code-readability-plain-naming`, `lock-concept-language`,
`match-output-to-the-ask`, `memory-is-downstream-of-conversation`, `user-owns-execution`,
`state-handoff-utmost-care`, `thesis-is-done`, `data-layout-storage-vs-working`,
`no-fabricated-offline-checks`, `verify-before-asserting`.

The problems:

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 6.1 | `v3-arm-model-stack.md`: "**Why this overrides the earlier 'ground references' the user pasted:** that note named `all-MiniLM-L6-v2` … Dropped" | **[CONTRADICTS-USER]** in method | An agent documenting, in writing, that it overrode source material the user handed it. The technical call may be right (all-MiniLM is a weak baseline), but the standing rule is *"Heed the user's intent — never 'correct' it with stale context … Surface a genuine conflict as a question, not a correction."* This is the correction, recorded as settled. |
| 6.2 | `no-cost-estimates.md`: "Cost (time or money) must carry **ZERO weight** in my own reasoning, recommendations, or option-comparisons." | **[STALE]** — dangerously so | Grounded at 06-18 (*"YOU do not care about cost here, 0 fucks given"*) and then destroyed by events: 07-17, 07-23 and 07-24 each burned the user's entire usage window. The laptop memory now carries the exact opposite as a hard rule. **A fresh agent reading the desktop memory and not the laptop memory would reinstate the behaviour that caused three of the worst incidents in the project.** |
| 6.3 | `project_overview.md` "**RAGAS ONLY** … there is **NO separate HERB scorer** … do not reintroduce it" vs `v3-arm-model-stack.md` "**Scoring is HERB + RAGAS only**" | **[STALE]** cross-file conflict | The user settled it on 06-25 (*"this is ONLY RAGAS"*, twice). One entry records the ruling; the other preserves the superseded position with equal authority. |
| 6.4 | `herb-eval-arm.md` states, in one file, both "**context_ids are real**" and "**`context_ids` is empty**"; and both "the v1 full-text fallback is **DELETED**" and "**Gated full-text fallback kept**" | **[AGENT-ORIGIN]** — internally incoherent | Two flat self-contradictions about the arm that produces every reported number. Either could be acted on. |
| 6.5 | `facet-semantic-framework.md` "The facet set is **settled**: topic, process, stance, communicative-function, time" vs `tag-facets-vs-routing.md` "**Topic is not a facet**" vs `retag-facet-analysis.md` "**All five facets are RESTORED**" (topic/entities/activity/temporal/evidence) | **[STALE]** — three settled answers | Three files, three incompatible "settled" facet sets, same number. This is the substrate of git_record **C-6** (the condemned v1 facets returning under new names). |
| 6.6 | `retriever-routing-model.md` "Embedder is chosen: `nvidia/llama-3.2-nv-embedqa-1b-v2`" vs `nvidia-llm-host.md` / `v3-arm-model-stack.md`: `nvidia/llama-nemotron-embed-1b-v2` | **[STALE]** | Two embedder ids as settled fact. The user's own instruction was blunt: *"fs,. i just said it's NEMOTRON FFS!"* (06-28). |
| 6.7 | `v3-artefact-subsystem.md` "`herb-eval` … **never queried live**" vs `herb-eval-arm.md`, an entire arm that queries it live | **[STALE]** | The desktop-side twin of ranked item 7. |
| 6.8 | `docs-track-reality.md`: "this project uses **AGENTS.md**, not CLAUDE.md, as the auto-loaded brief" | **[STALE]** — actively misleading | There is no AGENTS.md. An agent following this would write canon into a file nothing reads. |
| 6.9 | `retag-facet-analysis.md` names "deepseek-v4-pro" as the v2 tagger host; `v3-artefact-subsystem.md` names `meta/llama-3.3-70b-instruct` for the interpreter; DESIGN §11 names Mistral Large; the built tagger is `z-ai/glm-5.1` | **[STALE]** | Four model names for two roles. git_record C-10. |
| 6.10 | `artefact-pass2-design.md`: "hub nodes for shared field values in a mid-selectivity band" vs `v2-graph-spine.md`: "The minted hub-node-per-label idea is **dead**" | **[AGENT-ORIGIN]**, honestly flagged | Credit: the pass-2 file **names the tension itself** and says "needs an explicit sign-off, not silent resolution either way." That is the correct handling. |
| 6.11 | `no-claude-attribution.md`: "Never include … AI/Claude attribution … **This is the user's master's thesis** … must read as the user's own" | Rule **[AGENT-ORIGIN]**; rationale **[CONTRADICTS-USER]** | Same split as 4.4. The rule is unsupported in the surviving record but plausible from the uncovered window; the thesis rationale is contradicted by *"drop the fucking thesis, it's done, this is post-thesis work"* — which the sibling file `thesis-is-done.md` records correctly. Two desktop memory files disagree about whether the thesis is live. |

**Desktop-memory subtotal: 19 GROUNDED · 3 AGENT-ORIGIN · 1 CONTRADICTS-USER · 7 STALE (30 claims).**

---

## Surface 7 — the state docs (OneDrive `state-transfer\GRAG-Job`, 10 dated + USER_CANON.md)

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 7.1 | `USER_CANON.md` in its entirety | **[GROUNDED]** — the one clean surface | Spot-checked against the 803-turn corpus: quotes are verbatim and correctly dated. It opens with an honest provenance table and the warning "**Absence of a statement here proves nothing.**" See the "recorded nowhere" section for the problem with it. |
| 7.2 | `USER_CANON.md`: "**THE MISSING PERIOD IS NOT MISSING — IT IS IN GIT. GO READ IT.** … An earlier agent repeatedly claimed provenance was lost; it never was." | **[GROUNDED]** | 08-02: *"THE GODDAMN GIT REPO HAS ALL THE FUCKING HISTORY SPOKEN IN COMMITS, DIFFS, CODE and DOCS."* Directly overturns memory entry 4.3. |
| 7.3 | `2026-07-22-v1-curve-walk-facets-and-cluster-k.md` §8 declared "**binding**" by `maths-algorithmist.md` | **[AGENT-ORIGIN]** | See 3.4. The user pre-emptively distrusted this document on the day it was written: *"i am going to assume that the agent that wrote the state doc now was.. unhelpful"* (07-22). |
| 7.4 | `2026-07-28-audit-absorption…md` — the five-reviewer verdicts, the full revert, "topic ≠ evidence" | **[GROUNDED]** | The revert is the user's explicit order: *"no, there is no semi-revert option here, either you absorb the knowledge or its gone"* (07-28). The audit itself was the user's instruction (07-23 14:07). |
| 7.5 | State docs recording "**the user's verdicts**" on mechanisms (chord break, value-knee) | **[CONTRADICTS-USER]** in attribution | See 3.14 — these were agent measurements. The user's actual verdicts are things like *"i dont think the walk and the 'best fit' is helping eachother, you?"* — a question, not a ruling. |
| 7.6 | `2026-08-02-benchmark-validity-record.md`, `2026-08-02-corpus-facts.md` | **[GROUNDED]** | Recent, measured, caveated. |
| 7.7 | CLAUDE.md's pointer to `docs/state/…` | **[STALE]** | The docs are in the OneDrive folder; `docs/state/` does not hold them on this machine. |
| 7.8 | `2026-06-20-v3-contract-vector-arm.md` and the older docs framing v3/artefact as the artefact | **[STALE]** | Superseded by 07-26 (*"we are NOT doing the v3 artefact"*). |

**State-doc subtotal: 4 GROUNDED · 1 AGENT-ORIGIN · 1 CONTRADICTS-USER · 2 STALE (8 claims).**

---

## User instructions recorded NOWHERE in any canon surface

These are things the user said that a fresh agent, loading CLAUDE.md and the memory index, would
never learn. **17 items.**

**The structural cause first.** `USER_CANON.md` — the only surface that records the user's words
verbatim — is referenced by **nothing**. It is not in CLAUDE.md's entry-point list, not in any
agent definition, not in the memory index. Same for the entire `docs/canon/` tree. Verified by
search: zero references. So *everything below that exists only in USER_CANON.md is, in practice,
still lost*, and the file that would fix this audit is itself unreachable.

| # | What the user said | Date | Status |
|---|---|---|---|
| 1 | "honestly, **you should not have the questions/gold available to you**, there is 0% good that can come out of taht" / "can we make sure 'you' never see them? that you only get the variable/pointer to it?" | 08-02 | **Enforced.** A CLAUDE.md hard rule and a hard rule in each designing agent (retrieval-scientist, maths-algorithmist, v3-coder): `v3/data/questions.jsonl` and `arm_outputs.jsonl` are closed to them; runs are specified by pointer and read back from `eval_results.jsonl` (metric values by question id and type). results-analyst and eval-statistician keep full access — they report, they do not design. |
| 2 | "**we are NOT doing the v3 artefact, we are doing the v1artefact** … EVERYTHING i have been TRYING to build for weeks now, have been the actual v1artefact" | 07-26 | **Nowhere** — and the opposite is written into CLAUDE.md and v3/README. |
| 3 | "**i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something**" / "also, arbitrarily decided hard limits, like the 64 chunk limit, i bet there is way more than 1 of these dumb limits lying around" | 07-15, 08-02 | USER_CANON only → unreachable. Absent from CLAUDE.md and every agent definition — while those definitions hard-code bars (0.7926, +0.03, p<0.05). |
| 4 | "**Dude, your dates and times are ALWAYS wrong, please stop from trying to measure time**, it's genuinely terrible and just builds a false narrative in YOUR mind" | 07-29 | **Nowhere.** Agents still compute durations and date-reason in reports. |
| 5 | "1. i THINK it might be smartest to **compute the clusters at build, and then weight-adjust them based on the query's facet-values** … 2. i used **best fit as the fuzzy cutoff-point for the cluster's edges** … perhaps the query-adjustment comes first" | 07-31 | USER_CANON only → unreachable. This is the *current* design direction, stated in his own words, and no agent-facing surface carries it. |
| 6 | "the original thought was … **clustering of tags weighted by facets, meaning each type of facet was a separate sort of clustering** to get semantically different clusters" | 07-31 | USER_CANON only → unreachable. |
| 7 | "arent all arms here kinda supposed to be available as '**tool calls**' for the llm … ours it can be a bit more active with" / "what i am after here, is **letting the agent actually 'hold on to the conversation'** and decide when it has the informtion to answer the question" | 07-21 | **Nowhere.** An entire architectural direction, never recorded, never built, never refused. |
| 8 | "**USE ALL THE FUCKING DATA IN THE FUCKING GRAPH!** why would you leave shit on the table like that" | 07-21 | USER_CANON only → unreachable. |
| 9 | "**all nim can be called in 1 batch**" / "why on earth havent everything in that dataset been embedded before already and just saved? it's fucking free and can be done in 1 batch" / "I want subsequent runs to be more or less fucking **instant and free**" | 07-23, 07-29 | Partially in USER_CANON; **not** in CLAUDE.md or any agent definition, despite being the thing he repeated most often across three weeks. |
| 10 | "**make the plan as fable, do the work as opus5-max**" | 08-02 | **Nowhere.** A direct model-routing instruction to the orchestrator. |
| 11 | "yeah, dude, but **dont fucking bloat a new session with contaminated informatioj!**" / "exactly, so we bould and clean and then do a **clean session**" | 08-02 | **Nowhere.** The clean-session/contamination discipline he was actively enforcing in the final week. |
| 12 | "**DO NOT fucking touch a part i have not asked you about**" | 07-30 | Only obliquely, inside the trust-revoked entry. |
| 13 | "if the constrct is the same, you can just **test with and without the different weights and solutions … just make them toggleable** … but only do it if it matters, tight, clean, to the point" | 07-22 | USER_CANON only → unreachable. The toggle flags exist in code; the rule that produced them does not. |
| 14 | "**k=50 does not mean the same for all arms, and thats retarded**" / "perhaps K shouldnt be chunks, perhaps we should put a **max token budget** instead" | 07-26 | USER_CANON + partly the validity memo. The user diagnosed the matched-budget problem **two days before** the audit panel "discovered" it as the 85%-unit-artifact finding. His own diagnosis is not recorded as canon. |
| 15 | "i mean, if the … **if we build the graph correctly, wont it emulate/do multihop natively purely by design?**" | 07-15 | USER_CANON only → unreachable. |
| 16 | "**i need you to start actually reacting to getting yelled and cursed at**" — recorded; but its companion, "**is it a you reason? is it reasoning? is it context bloat? is it truncated context? seriously, i need an answer to why you are this shitty now because i need to be able to avoid this frustration**" | 07-22 | The second half is **nowhere**: the user asked agents to diagnose *their own* degradation so he could work around it. No surface carries it. |
| 17 | "**conversations and memories also count, just because it didnt leave a conversation doesnt mean it shouldnt be saved**" | 06-28 | **Nowhere** in the current canon (desktop record only). It is the instruction that, followed, would have prevented this entire audit. |

---

## What the pattern actually is

Three distinct mechanisms produce all 23 contradictions, and they are worth separating because
they need different fixes:

1. **Laundering by provenance loss.** An agent writes a term or a number into a doc; a later agent
   reads that doc and records it in memory as "the user's"; a third agent enforces it as a hard
   rule. `project_terminology_canon.md` states its own sources — README, DATA_README, a state doc,
   CLAUDE.md, and the code — **all agent artifacts**, none of them the user. Nothing in the chain
   is dishonest; each step just drops one bit of attribution, and four steps drop all of it.

2. **Canon frozen against a moving system.** The design docs describe the v3 native artefact; the
   thing measured is `artefact_v1` over `herb-eval`. Every "the artefact does X" statement in
   CLAUDE.md is true of a system that has never been run and false of the one producing every
   number. This is C-2, C-5, C-13 and C-14 in one sentence.

3. **Measurements hardening into laws.** An agent measures something once, on 10smoke or one
   configuration; it becomes a "standing bar", a "closed decision", a "do not re-derive" line in a
   permanent specialist's hard rules — often after a later audit found the same result not
   significant.

The user identified all three himself, in one sentence, on 2026-07-25:

> "**YOU cannot assume canon by the fucking names of things.. thats equally retarded.. you see why
> it all went wrong now? you create an item and then suddenly think it's canon just because YOU
> fucking named it so.**"

---

*Read-only audit. No file outside this one was modified. No fixes are proposed — what happens to
the repo is the user's call.*
