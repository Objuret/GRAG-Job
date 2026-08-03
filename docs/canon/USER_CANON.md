# USER_CANON — what the user actually said

Verbatim only. Every line inside a quote is the user's own text, spelling, and profanity
intact. Nothing here is smoothed, corrected, or paraphrased. Where a section needs
interpretation to be usable, it appears on a line beginning **`Reading:`** and never
inside a quote.

**Contradictions are preserved, not resolved.** Where the user said one thing and later
the opposite, both appear, in date order, and the reversal is named. No agent gets to
pick the winner.

All dates are 2026. Format: `MM-DD`.

---

## PROVENANCE — read this before using anything below

### What this covers

| | |
|---|---|
| Verbatim human turns | **803**, 2026-05-14 → 2026-08-03, desktop 127 + laptop 676, merged |
| Second-hand recovered rulings | **80 labelled rulings + ~150 verbatim quotes** from 20 agent-written design docs, 05-25 → 07-12 |
| Git | **74 commits**, 2026-05-07 → 2026-08-01, 91 reproduce commands, 18 numbered contradictions |

### Source classes — every quote carries one

| Tag | Means | Trust |
|---|---|---|
| **[CHAT]** | From `docs/canon/raw/user_turns_all.jsonl` — the user's own keystrokes, first-hand, timestamped | Highest. This is the primary source. |
| **[DOC]** | Recovered from an agent-written design/state doc that quoted the user | Second-hand. The quote passed through an agent's transcription. Reliable to the extent that agent transcribed accurately; the 06-28 design-evolution doc is strongest because it cites `[tNN]` turn numbers. |
| **[COMMIT]** | The user's own commit message | First-hand but terse. |

### What this canon **cannot** tell you

- **Nothing before 2026-05-14 exists as chat.** The project's first commit is
  **2026-05-07**. The whole first week — the initial 52-file Neo4j pipeline, the
  12-entry decision log, the original graph schema, the controlled canonical vocabulary
  — survives **only in git and in the design docs**. No transcript of it exists anywhere.
- **Two chat blackouts:**
  - **05-16 → 05-26** — 11 days, zero human turns on either machine.
  - **05-29 → 06-26** — 29 days, zero human turns on either machine.

  These two windows contain the entire v2 pivot, the facet redesign, the closing of the
  graph spine, the death of the chunk description, the build gate, the eval-harness
  design and the RAGAS-only purge. **They are not lost.** They are covered second-hand
  by the `[DOC]` record (20 docs dated 05-25, 05-31, 06-03, 06-04, 06-09, 06-11, 06-12,
  06-14, 06-18, 06-23, 06-25 ×3, 06-28 ×3, 07-01, 07-12) and by git. Every `[DOC]` quote
  from those dates is the only surviving trace of that statement.
  - **Correction to a claim in circulation:** it has been said these windows "have no
    records of any kind." That is wrong. They have no *chat*; they have a substantial
    doc record. Treat `[DOC]` as second-hand, not as absent.
- **Thin days are thin, not silent.** 05-27 and 05-28 carry one turn each; 07-02 two;
  07-12 three; 07-27 two. Absence of a statement on a date proves nothing.
- **An earlier agent called 2026-07-15 "the first day" of the project.** The user's reply:

  > "This, this was the most fucking delusional piece of evidence i have ever seen.
  > "
  > 2026-07-15, the first day
  > "
  > Day one? 2 weeks ago..  you ARE retarded.." — **[CHAT] 08-02**

  It was the earliest date in one partial local extract, wrong by two months. Do not
  repeat it.

### The pre-chat era is in git — go read it

The design history of the blackout weeks is written down in commits, diffs, code and
docs. Read these before designing anything; they are the design-era record,
2026-05-07 → 2026-06-28.

| commit | date | what it holds |
|---|---|---|
| `dba1160` | 05-07 | Initial commit — 52 files, the full Neo4j indexing pipeline, `docs/architecture.md` (12-entry decision log), `docs/graph_schema.md` (280 lines) |
| `48fbc9d` | 05-11 | "rename cluster dimensions" → theme→topic, object_entity→entities, event_process→activity, time_relevance→temporal, information_need→evidence |
| `399ee32` | 05-13 | "Rework HERB chunking and tagging frames" → `backend/docs/herb_tagging_frames.md`; also silently deletes the canonical vocabulary |
| `415148d` | 05-14 | "Document HERB query interpretation layer" → `herb_tagging_schema.md`, `graph_schema.md`, `pilot_full_herb_report.md` |
| `4ab34b4` | 05-15 | the only commit that ever carried Claude memory files (`memory/MEMORY.md`, `project_architecture.md`) |
| `54bc1a4` | 05-28 | v1 as shipped — `frontend/src/services/retrieval.ts`, the seven-factor `scoreCypher` and its five hard gates |
| `296fc40` | 05-30 | v2 artefact-rebuild design, shape-probe prototype, NVIDIA host verification |
| `18d11df` | 06-01 | reference-resolver prototype, §13 semantic-dimensions research |
| `0efff16` | 06-15 | "Separate repo into v1/ (frozen) and v2/ (active)" — **+750 design lines**, the largest single design landing; also the first `CLAUDE.md` |
| `28c95aa` | 06-24 | `v3/artefact` subsystem → `DESIGN.md`, `MODEL_CONTRACTS.md`, `keys/Salesforce__HERB.yaml` |
| `8a640bf` | 06-28 | titled "update graphify-out (533 files)" — actually ships `v3/artefact/tag.py`, `chunk.py`, the 659-line facet-derivation survey, and **deletes `v3/eval/herb.py`** |
| `69115e0` | 07-12 | titled "update graphify-out (49 files)" — actually introduces `v3/pipelines/artefact_v1.py`, the arm producing every reported artefact number |
| `origin/jockedev2` | 05-19 | six unmerged RAGAS commits, squashed into `5706520` with an empty body; the only surviving record of the finding *"Effect is question-type-dependent — not a general graph win."* |

Branches carrying them: **`origin/djuret/monorepo`** (real impl + docs, paths under
`backend/`), **`v3`** (holds the frozen `v1/`), `v3_artefact_build`. The current branch
has been cleared of old material — **the working tree is not the record.**

Read with `git show <ref>:<path>`. Also `git log --all -S'<term>' --name-only` to find
where a concept was introduced, and `git log --all --format='%ad %h %s' --date=short`
for the full timeline. The full forensic reconstruction, with 91 reproduce commands and
18 numbered contradictions, is `docs/canon/raw/git_record.md`.

### How to re-derive this

```
python tools/canon_extract.py
```

Writes `docs/canon/raw/` — `user_turns_all.jsonl` / `.md` (the corpus),
`rejected_sample*.md` (what the filter threw out and why), and `EXTRACT_REPORT*.md`
(counts, per-rule reject tallies, and the false-negative audit of the `harness_template`
rule: 0 of 6,380). The desktop half is merged in from
`OneDrive\Coding\state-transfer\GRAG-Job\_desktop_transcripts`.

`docs/canon/raw/` is **read-only**. Do not edit it. Re-derive instead.

### The standing instruction that produced this file

> "have you fucking done ANYTHING based on actual canon? i fucking demand you filter
> through every fucking memory and chatlog you have and find out everything I HAVE SAID,
> THOROUGHLY" — **[CHAT] 08-02**

> "Search the entire repo for exactly ALL information I (the user, fucking ME) i have
> conveyed, the actual things I ACTUALLY SAID: all conversations, memories, logs, docs,
> data, diffs, committs, changes, fixes and code.. that means you have to search the
> entire git-repo also with all the fucking branches etc, this is not a small job, but it
> is the most important one we have ever done here." — **[CHAT] 08-02**

> "THE GODDAMN GIT REPO HAS ALL THE FUCKING HISTORY SPOKEN IN COMMITS, DIFFS , CODE and
> DOCS.. what the actual fuck is wrong with you?" — **[CHAT] 08-02**

---

# PART I — THE DESIGN CANON, BY SUBJECT

Within each subject, quotes are in date order so the movement is visible.

---

## 1. The artefact's intended construction

> "but the point of the multifacets was to give the tag a more semantical weight and direction with the facets, how are the facets used now?" — **[DOC] 05-25**

> "specifically multiplication i am not sold on" — **[DOC] 05-25**

> "fuck the instinct, talk about reality" — **[DOC] 05-25**

> "Measure from embeddings (IF POSSIBLE) is way better than more prompting." — **[DOC] 06-09**

> "measure from embeddings was my idea." — **[DOC] 06-09**

> "it took so fucking long to get it right and it still didn't work at all" — **[DOC] 06-11**, on v1's model-emitted weights

> "we don't keep shoveling around bad, useless or legacy code building dependencies on old stuff" — **[DOC] 06-11**

> "drop the fucking thesis... it's done, this is post-thesis work." — **[DOC] 06-14**

> "allright, since i am a cunning cunt, my design here is a combination of these fuzzy things, embeddings AND fuzzy-lexical hard fields that also guides … combinations of solutions are the trick in my humble opinion" — **[DOC] 06-28 [t14]**

> "honestly, an optimal solution would to NOT have all of this in the graph, intead do it live-prompt-time, because of the size it's becoming, BUT, embeddings, values, pointers etc, might be ok" — **[DOC] 06-28 [t52]**

> "Nope, I absolutely did NOT want you to give a fuck or change the text, I wanted to discuss how to actually continue building the artefact in a creative innovative way that actually kinda fits my original concept (even if just in spirit), and by NOT overfitting it to the specific dataset we have." — **[CHAT] 06-30**

> "but the actual content should never exist in the graph at all, and we fixed that by just making pointers again, right? like in v3? so why the fuck would you reintroduce the fucking content back into the graph?" — **[CHAT] 07-06**

**The single fullest statement of the v1 concept in the whole corpus** — **[CHAT] 07-06**:

> "WHY!? it's like you understand 0% of the v1 concept and fucking refuse to learn more about it..
> so, it was file -> chunks -> tags.
> the chunks reference the files, the chunks contain a short description of the chunk, a relational weight of the chunk to the file, tags with relational values of the tags to the chunk, and then the tags have the facet-values too. Pretty much all of this is embedded, the chunk description, the tagsnames, the facets etc.. meaning, in the actual graph, there are no "content" like that, just a bunch of related embeddings..
> and the interpretor does it's thing with the input like getting facetvalues/rankings of the prompt, a description of the prompt which can be embedded and checked vs chunk-description-embeddings and so on and so on.. are you with me now?
>
> The tags themselves are embedded, meaning we have an embedding as the actual tag"

> "Was this really truly the shape in v1? I literally fucking never expected or wanted that context shit" — **[CHAT] 07-06**

> "facets are on 1 edge, the edge between the chunk and the tag carry the facets, right?" — **[CHAT] 07-06**

> "wtf are you talking about "the best" all the time? there are only 5 faces, just fucking put them on the fucking edge" — **[CHAT] 07-06**

> "Yeah, but I am not taliing code with you, I am trying to fucking make you understand the concept and make sure you actually implement what we have discussed, so don't fucking reparameter it mid conversation" — **[CHAT] 07-06**

> "so, how much construction here is the honest solution? if we are comparing the three arms, how much can i build on the artefact before it becomes an unfair comparison?" — **[CHAT] 07-15**

> "i fucking did NOT want help with the thesis, drop this line of thinking now and focus on the artefacts, so, what can we improve in how we USE the graph at this stage? to get a really good use of it for this first real run of it, before we go to the v3 construct of it, it felt like we got quite strange results compared to the original v1, thats why i staretd asking about the diff" — **[CHAT] 07-15**

> "Use a clearer vocabulary about what the current design (full arm) actually have, how it works, the full thing" — **[CHAT] 07-15**

> "we are ONLY talking about the USE of the artefact here, that is, the interpreter-retrieval part" — **[CHAT] 07-20**

> "well, you are both bastardizing and forgetting the origins, those are my thoughts defiled, the origial concepts were mine" — **[CHAT] 07-21**

> "can we try to make MY idea a reality instead then.." — **[CHAT] 07-21**

**On the published abstract other people wrote about this work** — he pasted it twice and ruled on it both times:

> "…while we CAN err away from this, I do prefer if we can keep it somewhat close" — **[CHAT] 06-30**, attached to the abstract

> "but those that wrote that does not FULLY know what we are doing, so that is not canon, just an assumption" — **[CHAT] 07-21**, attached to the same abstract

> "actually, YOU need to revisit the docs and ALL code etc, and update your language for what we are doing because i get a very distinct feeling you are starting to mix things up because of you not having a great grip on the terms we have used in the project" — **[CHAT] 07-21**

> "fuck that shit, i just want to build my fucking arm mate" — **[CHAT] 07-25**

**Which artefact is which** — **[CHAT] 07-26**, after several turns of agents confusing the lineages:

> "fml, what a shit conversation.. why cant you even understand the current state of things by reading the reapo.. it MUST be because you are lazy as fuck  and cant just comprehend.. we are NOT doing the v3 artefact, we are doing the v1artefact, however, since only v3 is the downloaded area here, to avoid ai's reading all the incorrect info all the time, we have imported the v1arm here so we can atleast finish these fucking benchmarks/evals/datacollections, before i can fucking finish my v3artefact.. but, EVERYTHING i have been TRYING to build for weeks now, have been the actual v1artefact..."

> "dude, when i say current, i mean v1artefact you can find in this, up to date repo.. when i say original v1, i mean several months ago in the old branches, the k=40 era, can you fucking understand the difference and stop spamming this conversation with utterly wrong statements" — **[CHAT] 07-26**

> "why the fuck are you going on about "the thesis" ? i am tryibng to fucking build a CORRECTLY BUILT FUCKING ARTEFACT here. DO NOT fucking touch a part i have not asked you about" — **[CHAT] 07-30**

> "wow, well, this is sure as fuck written by machine and not man, clearly unreadable both in syntax and actual architecture.. you honestly thing you constructed that well and correct according to the design here?" — **[CHAT] 08-02**

**Reading:** three distinct systems get called "the artefact" in this record, and mixing them is the single most common agent error in the corpus. (a) *original v1* — the thesis-era browser/Neo4j build, the k=40 era, on old branches; (b) *current `artefact_v1`* — the Python arm in `v3/pipelines/`, running over the same `herb-eval` Neo4j graph with a new retrieval engine; (c) *v3 artefact* — the native rebuild under `v3/artefact/`, unfinished. The 07-26 turn above is the authoritative disambiguation.

---

## 2. The graph, and using it as a graph

> "if we are saying file -> chunk ->tags .. where are those OTHER RANDOM FUCKING NODES!?" — **[DOC] 06-12**

> "either they are nodes, but then we get edges to EVERY fucking chunk, or they are just attributes… perhaps it's smarter to just have shit like that as attributes on chunks." — **[DOC] 06-12**

> "that sounds a bit fucked up to have them as nodes, most of them will be a chunk, meaning we have 2 almost same nodes." — **[DOC] 06-12**

> "that has the potential to put a fuckton of data into the graph, both GDPR data, and not. why not just have the parent field as the connection and when searched for, you can find anna." — **[DOC] 06-12**

> "it's dead, such shit is 'interpreter area'" — **[DOC] 06-12**, killing minted facet-label hub nodes

> "where the fuck in the graph do you think this is?" — **[DOC] 06-12**, on an agent proposing to search field *values* in the graph

> "why the fuck and from WHERE do the random nodes and other shit come from?" — **[DOC] 06-12**

> "but, doesnt the graph give actual relational connections to things like this, i mean, if the 'name' example you had, why wouldnt if just find all of those names? i dont get it" — **[DOC] 06-28 [t33]**

> "just some thoughts btw, thinking about the actual size of the graph here, is there a reason to have the phrases in there? shouldnt we just embed them and put the embedding as a node in the graph instead with the reference just like the phrase would have?" — **[DOC] 06-28 [t68]**

> "and you are sure the filestructure should not be actual nodes?" — **[CHAT] 06-30**

**The line he has repeated in some form ever since** — **[CHAT] 06-30**:

> "yeah i really think this should be nodes or edges so to speak etc, half the strength of of a graph is beeing able to route/search based on relationships instead of structures"

> "Ok, but the probe extracted fields right? And many of these are not unique, having it as a rule to make nodes out of shared fields between files/areas etc.. Isn't that a generally useful concept? Dont think herb, think dataset agnostic concept.
>
> Maybe I'm just confused." — **[CHAT] 07-01**

> "Wait, only shared fields are attributes now? That's retarded.." — **[CHAT] 07-01**

> "yeah but do we NEED multihop if we do the graph correctly?" — **[CHAT] 07-15**

> "what i said was: if we build the graph correctly, wont it emulate/do multihop natively purely by design?" — **[CHAT] 07-15**

> "ok, but isnt id's discovered by the fact that their fucking parents are called "customers" "users" "emplyees" or shit like that?" — **[CHAT] 07-20**

> "i dont get it.. doesnt the fucking interpreter use the attributes? for example, if the prompt is about a fucking employee.. it doesnt use that attribute to get them?" — **[CHAT] 07-20**

> "oh, so the issue here is that FILE does not have these attributes ?" — **[CHAT] 07-20**

> "or are you saying these attributes should be nodes or edges instead?" — **[CHAT] 07-20**

> "the real question i have now tho, is wether the graph is actually built in a way that makes use of the actual qualities of a graph" — **[CHAT] 07-20**

> "USE ALL THE FUCKING DATA IN THE FUCKING GRAPH! why would you leave shit on the table like that, good god damn god you are a fucking pain in the ass to work wit" — **[CHAT] 07-21**

> "so, the chunks have the hard field attributes right now, right?" — **[CHAT] 07-21**

> "also, are we underutilizing the fact that all of this is built in a graph format? i get a very distinct feeling that we are leaving quite alot out here, take your time in analyzing this" — **[CHAT] 07-28**

> "so, can we finally go on with trying to fix the artefact? there are 2 different things i want to have a serious look at: 1. to see if we can build the graph smarter, aka use the actual grapjh shape in a better way, either but adding something, rearranging or something else, do your due diligence as usual for this.
> 2. the retrieval, the fact that we find pretty much all gold, but also 90% air is a terrible thing" — **[CHAT] 07-29**

> "tag graph? the chunks and all the other shit is part of the graph too.. you seriously have fucking misread this situation this goddamn hard? after such a fucking huge analysis!?" — **[CHAT] 08-02**

> "well.. you think this would be easier for you to build and think upon the artefact if we used the graph shape better? like the hard fields etc, should they be nodes or edges or something? is there some way we could use the information in the graph and make helpful structure from it instead of having it locked into other's nodes or edges?, very important question so please do take your time to carefully answer this" — **[CHAT] 08-02**

> "dude, you are turbo-overfitting now, AND doing shit that might as well be sql-schema" — **[CHAT] 08-02**, on the answer he got to the question directly above

**Reading:** "is the graph being used as a graph?" is asked on 06-30, 07-15, 07-20, 07-21, 07-28, 07-29 and 08-02 — seven times across five weeks, never answered to his satisfaction. Note the closing pair: he asks for hard fields as nodes/edges and then rejects the concrete answer as overfitting and as SQL schema. Both turns are his; both halves bind.

---

## 3. Tags — what they are, and what they are for

> "perhaps we get less tags like this?" — **[DOC] 06-09**, on richer tags meaning fewer tags

> "what if we don't do the word, and just have the embedded 'small concept' as the node" — **[DOC] 06-11**

> "Since the collective tags from a chunk should BE the content of the chunk, why do both?" — **[DOC] 06-11**, killing the chunk description. The doc notes he asked twice.

> "compare each phrase to its siblings" — **[DOC] 06-11**

> "the weight of the tag is ON the tag, because that is the phrase's concept being valued, and the 'in relation to the siblings' weight is on the edge." — **[DOC] 06-11**

> "We have literally removed ALL semantics and just replaced large chunks of text with short descriptions." — **[DOC] 06-25**

> "we only have a few short phrases now instead of a fuckton of tags with facets … I still think we need another semantic layer here, like the facets on the phrases. Would not the old facets work with the new tags? (not the weighting, the concept)." — **[DOC] 06-25**

> "What you think is v2 tags is in essence everything moved to hard fields or put on the interpreter" — **[DOC] 06-25**

> "now that we have the tags made, is there a way to thinking about this differently?
> like, can we do a different comparison between all tags based on facets or a live prompt-time compute of it based on input etc? i feel like a really do NOT want an llm judge involved in the creation of them in the graph atleast. come up with creative solutions and also check online solutions and research on this, /moria this and find all you can that could give us these semantic nuances" — **[CHAT] 06-27**

> "yes, but we did the actual tag-names embedding already, yeah?" — **[CHAT] 07-06**

> "what the fuck are you even saying? do our fucking tags have values or not?" — **[CHAT] 07-21**

**The purpose statement, said twice on the same day in two sessions** — **[CHAT] 07-30**:

> "you and every other agent seem to be missing that the whole fucking point of the tags, is guiding to the correct gold-bearing chunks"

> "i was under the impression that we did the whole fucking tag-clustering and facets and weights just to fucking guide it all to the correct chunks, why the absolute fuck was this NOT done then?" — **[CHAT] 07-30**

> "ok, so we make sure it is informed by the tags first then, as IT WAS FUCKING INTENDED from the start.. didnt the original thesis artefact do it correctly?" — **[CHAT] 07-30**

> "dude, descriptions in every tag was an abomination and should never have been there, i am still angry abou tthat" — **[CHAT] 07-30**

> "ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE ffs.. tags are supposed to INFORM/weight the chunks" — **[CHAT] 08-01**

> "this literally all sounds like you constructed the whole tag-part like a fucking hobo" — **[CHAT] 08-02**

> "tell me EXACTLY, verbatim, how the tag-layer works now, how it is built, used, calculated" — **[CHAT] 08-02**

> "Hapax?" — **[CHAT] 08-02**

> "have you decided this? "which is what a tag layer is supposed to be" ?
> Because in min mind, just when thinking about it cursory, hapax would let them matter more because of vectorisation?" — **[CHAT] 08-02**

> "Eh.. what..we have tags with that fucking syntax? For real?" — **[CHAT] 08-02**

> "but those you just showed me.. those are tags!?" — **[CHAT] 08-02**

> "so.. you can actually see the fucking canon for it, and itt's still constructed like this.. seriously, how the fuck manage to create ANYTHING with ai? i actually dont get it.. so fucking clear instructions and still fail every fucking time on such an insanely easy task.. but this is a retagged variant also? this is not the db we did the "purge" on, right?" — **[CHAT] 08-02**

**REVERSAL — "tags first" was said, then the implementation of it was rejected.**
On **07-30** he asked to make it "informed by the tags first … as IT WAS FUCKING INTENDED from the start". What was built was a tag-reachability regime (`HERB_TAG_FIRST`) in which tags gate membership. On **08-01** he rejected exactly that:

> "ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE ffs.. tags are supposed to INFORM/weight the chunks" — **[CHAT] 08-01**

**Reading:** "tags first" means tags weight/inform earliest and hardest in the ordering. It does not mean tags decide which chunks are eligible. Those are different mechanisms and only the first is canon.

---

## 4. Facets — and their several reversals

### The origin statement

> "but the point of the multifacets was to give the tag a more semantical weight and direction with the facets, how are the facets used now?" — **[DOC] 05-25**

> "the point of the multifacets was to give the tag a more semantical WEIGHT AND DIRECTION" — **[DOC] 06-25**, restating it

### Why the model cannot produce them

> "yeah it's high, because I chose it" — **[DOC] 05-25**, quoting the model's own justification for a facet weight

> "the agents assigning facets was pretty much impossible to get different values from, they just did 'yeah, its high, because I chose it'" — **[DOC] 06-25**

> "i really do NOT want an llm judge involved in the creation of them in the graph atleast" — **[DOC] 07-01**. The first-hand chat original, 06-27, reads slightly differently: *"i feel like a really do NOT want an llm judge involved in the creation of them in the graph atleast."*

### Where they live

> "weren't we supposed to have ALL the facet weights on the SAME edge!?" — **[DOC] 06-09**

> "why the actual fuck would you want or need a separate edge for each facet?" — **[DOC] 06-09**

> "'one edge per facet' was just bad communication... they were supposed to be on the same fucking edge" — **[DOC] 06-25**

> "not nodes … because that mean edges right, and those are heavy in all aspects" — **[DOC] 06-25**

> "it feels retarded to put facets on chunks, we are routing by tags, why the fuck put the facets AFTER that?" — **[DOC] 06-25**

> "facets are on 1 edge, the edge between the chunk and the tag carry the facets, right?" — **[CHAT] 07-06**

> "wtf are you talking about "the best" all the time? there are only 5 faces, just fucking put them on the fucking edge" — **[CHAT] 07-06**

> "where the fuck do the facets even live?" — **[CHAT] 07-21**

### What kind of thing a facet is — the definition moved three times

> "stance is not a magical facet, ALL facets are evaluations." — **[DOC] 06-11**

> "things you can extract from language, the things that actually 'mean' something" — **[DOC] 06-11**

> "i think we have to have unique ways of doing it for each facet" — **[DOC] 06-11**

> "perhaps we can do that, but based on each facet! giving a relational value of the tag to its siblings based on each facet!?" — **[DOC] 06-11**

> "you are with me that a fit-by-facet is a logical thing that actually gives us what we want from this?" — **[DOC] 06-11**

> "cluster or weight-adjust, aka narrowing or focusing the actual search-area of the corpus for the routing" — **[DOC] 06-11**, on facets' dual role

> "if the prompt is heavy in a facet, those facets are 'worth more' for the prompt/route." — **[DOC] 06-11**

> "relevance weights, not interpretation." — **[DOC] 06-14**

> "I think we should separate tag facets and routing." — **[DOC] 06-25**

> "I more get the feel that those 5 in v2 are almost only viable for the interpreter. While the v1 facets were actual semantic meaning around the tag." — **[DOC] 06-25**

> "the facets then use the entire tag-korpus as base for the evaluation of each facet on them, so their facet-value is relational to the korpus/facet." — **[DOC] 06-25**

> "Topic is not for facets tbh, how does it even fit there? Perhaps how much of the topic the tag is about? Or perhaps this is relative to all tags in the same chunk." — **[DOC] 06-25**

> "Temporal was never about dates" — **[DOC] 06-25**

> "well, i separate the 'facets' the interpreter use, and the actual real contextual/semantical facets the graph has in it" — **[DOC] 06-28 [t18]**

> "ah, yeah, i agree, not all facets should be graded in the same way" — **[DOC] 06-28 [t42]**

> "it's time to discuss and nail the actual shape of the facets in v3 for the artefact" — **[CHAT] 06-27**

> "you HAVE to remember that the facets are themed RELEVANCE weights.. meaninig you have to think about them differently, like info-kind and entity-type (are they even facets..?) you just whined about" — **[CHAT] 06-27**

### The multi-step relevance concept

> "also remember that the concept was that the tag-facets were to inform the RELEVANCE of the TAG, accoding to that faced, in relation to it's chunk, and via the chunk's relevance to the file, get an actual file-relevance too, but skipping the "to file" part, that was still the concept of the facets a multi-step relevance weight" — **[CHAT] 06-27**

> "the thought was that the facet weight in COMBINATION with the tag's "chunk relevance weight" would tell how relevant the tag actually is in relation to the prompt based on the interpreters evaluation of which facets are most relevant for the input, that was the concept back then" — **[CHAT] 06-27**

> "but, apparently it didnt work great, so this is not the same creation anymore
> but what we are exploring here, is perhaps other ways of doing this, i mean, the first tought was to use clustering based on the facets as a "filter/router" amongst the tags etc" — **[CHAT] 06-27**

> "that was before i started building v1" — **[CHAT] 06-27**

> "dude, you keep falling into the stockholm syndrome trap here, fucking stop, base some novel ideas on the document, we did some actual cool reference research here and you keep snowing in on my oldest ideas, they are cool, but come on man, i want NEW takes on it" — **[CHAT] 06-27**

### A mechanism he floated himself

> "another theory is just embedding the tags, and then at prompttime, the interpreter "answer" each facet about the prompt, and compare each facet to the tags and rank according to that, and also do that to the embedded prompt and pick/rank the combinations closest to the promtp..
>
> ok, maybe that was dumb, but a thought atleast" — **[CHAT] 06-30**

### How they must NOT be combined

> "specifically multiplication i am not sold on" — **[DOC] 05-25**

> "Ni, fucking stop, you are beeing really fucking obnoxious about this, wtf "multiply them pair wise and sum"!? What!?" — **[CHAT] 07-06**

> "That still sounds like a dumb solution..
>
> Better, but still baf" — **[CHAT] 07-06**

> "Instead of multiplication etc, why not just use it as prio ranking combos ?" — **[CHAT] 07-06**

> "are you fucking shitting me!? it's NOT normalized AND it's "summed" ? what fucking idiot combo is that!? you spun up math and science agents to review this and didnt fucking fix THAT combo?
> the amout of retardedness in this solution is actually insane.. AND you fucking ran the entire.. dude.. shit" — **[CHAT] 07-23**

> "the "difficult" and relative part of them was how much they should matter/guide etc, not fucking if they are normalized and summed or not, for goddamn fuck.." — **[CHAT] 07-23**

### Then: five weeks of asking what the facets are actually doing

> "i just wanted/assumed that we did a clustering of facet areas from the prompt" — **[CHAT] 07-20**

> "how the fuck are facets used here then?" — **[CHAT] 07-20**

> "is this useful? do the facets actually matter like this?" — **[CHAT] 07-20**

> "how do we make the facets relevant then?" — **[CHAT] 07-21**

> "how did we get the facet-values now?.. since they are supposed to be a semantic layer, i need to know what they are now" — **[CHAT] 07-21**

> "but HOW, how the fuck did facets get that value?" — **[CHAT] 07-21**

> "Ok, but I'm pretty sure their weights were derived from distances between embeddings, right?" — **[CHAT] 07-21**

> "What solution did I have for v3? I think I might have been mixing it up in my brain.." — **[CHAT] 07-21**

> "Ok, but let's talk about the v3 solution to facets then" — **[CHAT] 07-21**

> "A new arm? I just fucking want to fix the facets mate.." — **[CHAT] 07-21**

> "the whole point of them was supposed weigh-shift the routing via the clustering, did you even consider that?" — **[CHAT] 07-21**

> "Ok, so, let's solve the facets for v1artefact.. can it be solved? if so, how? can we use the v3 solution somehow for v1?, read up on the situation and fully inform yourself deeply before responding, including  a deep search online for semantic research, take your time before responding" — **[CHAT] 07-21**

> "so, lets fix the weights, and perhaps the diff between the runs is either when best fit is calculated, or maybe the strength of the weight modifiers? (this was why facets also were modifiers btw)" — **[CHAT] 07-23**

> "wait, what is affecting the interpreter from the facets that actually changes the response/interpretation?" — **[CHAT] 07-25**

### THE FACET REVERSALS — three of them, all his own

**Reversal F1 — what a facet *is*.** Three positions, each superseding the last:

| Date | Position |
|---|---|
| **06-14** | *"relevance weights, not interpretation."* — a facet is the relevance coordinate / character of a tag. |
| **06-25** | *"I think we should separate tag facets and routing."* / *"the v1 facets were actual semantic meaning around the tag."* — a facet is a semantic description of the phrase; routing is a separate downstream consumer. This **kills** the 06-14 framing eleven days later. |
| **06-27** | *"you HAVE to remember that the facets are themed RELEVANCE weights.. meaninig you have to think about them differently, like info-kind and entity-type (are they even facets..?)"* — a facet is a graded "how much" dial. This **re-kills** the 06-25 framing. |

**Reversal F2 — entity-type and information-kind: out, in, out.**

- **Out** (05-30, agent allocation table, later disowned): entities/temporal/evidence relocated to hard fields as "the v1 junk facets".
- **Back in** (06-25): *"Would not the old facets work with the new tags? (not the weighting, the concept)."* — the distinction he drove is fact-vs-kind: the eid is structure, the *kind* of information is meaning.
- **Out again** (06-27): *"like info-kind and entity-type (are they even facets..?)"* — a thing that answers "which" is not a facet; a facet must be graded.

The reconciliation between this and the 06-28 categorical framing was recorded as an open problem and **never closed**.

**Reversal F3 — one edge per facet → all facets on one edge.** v1 shipped an edge per facet. On **06-09** he asked *"weren't we supposed to have ALL the facet weights on the SAME edge!?"*; on **06-25** he stated the original intent was misread — *"'one edge per facet' was just bad communication... they were supposed to be on the same fucking edge"*; on **07-06** he closed it flatly: *"there are only 5 faces, just fucking put them on the fucking edge"*. This one is settled and does not reopen.

---

## 5. Clustering, cluster-K, levels of k's, fuzzy cutoffs

> "the first tought was to use clustering based on the facets as a "filter/router" amongst the tags etc" — **[CHAT] 06-27**, describing his pre-v1 instinct

> "that was before i started building v1" — **[CHAT] 06-27**

> "i mean, i really do like the concept of clustering tags/weights on facets based on the prompts values" — **[DOC] 06-28 [t49]**

> "wtf is this? 'HNSW (or FAISS)'" — **[DOC] 06-28 [t59]**

> "do we do a knn = number of facets then over the tag corpus?" — **[DOC] 06-28 [t62]**

> "ok, so you think its better to use it as ranking straight up rather than fuzzy cluster -> ranking?" — **[DOC] 06-28 [t65]**

> "i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something, i kinda like knn clustering for relevance spheres for example for grounding, k, retrival etc etc" — **[CHAT] 07-15**

> "maybe we should reflect on the value of each cluster also, if they are treated equally, or based on prompt ranking of them, or if they are done in an order where the ones before increase or decrease the areas of them depending on hits or relevance values etc etc?" — **[CHAT] 07-20**

> "i just wanted/assumed that we did a clustering of facet areas from the prompt" — **[CHAT] 07-20**

> "wtf is nnk?" — **[CHAT] 07-20**

> "what happened to the fuzzy clustering, the levels of k's in knn etc?" — **[CHAT] 07-20**

> "well the concepts i were intrested in were the "fuzzy clustering", "levels of k's" etc" — **[CHAT] 07-20**

> "well dude , analyse each concept and the EFFECT they will have alone and together" — **[CHAT] 07-20**

**The ownership line** — **[CHAT] 07-20**:

> "you keep saying things i am unsure of, have not really accepted and just fucking exist there, like the nkk pruning, fusion arrengement, gap cut..
> NONE of these are something i named or invented, what the fuck are they?"

> "no dude, ITS A FUCKING CLUSTERING, why are you doing rankings and countings!? its the fucking embeddings distances vs eachothers and those distances are the fucking clusters, holy shit" — **[CHAT] 07-21**

> "why did you make up a number like 200 here? dont you know how knn works at all? dude, fucking find the info on classification algorithms, knn.. this is fucking getting retarded" — **[CHAT] 07-21**

> "i mean, the clusters are based on the actual shit from the prompt, so you cant pre-run it..?" — **[CHAT] 07-21**

> "well, my thought was that these things if hits, inform where the cluster should start (meaning increased weight for all things related to that), well, that was my thought atleast, reflect" — **[CHAT] 07-21**

**The cluster-K definition** — **[CHAT] 07-21**:

> "i mean.. if they are already affecting which things are put in the retrieval and in what order isnt this just an issue with us not cutting off at a good cluster-k value?my thought with the clustering was that we get that curve of best fit and let that decide the correct K for that solution"

> "wtf do YOU think this means? "HERB_CURVE_K=1"" — **[CHAT] 07-22**

> "i dont think the walk and the "best fit" is helping eachother, you?" — **[CHAT] 07-22**

> "new state doc, working on the final stages of the v1 artefact, now the best fit clustering" — **[CHAT] 07-22**

> "i am going to assume that the agent that wrote the state doc now was.. unhelpful, because the context of the conversation kinda made it fucked up.. so let you and me have a real conversation about the clustering instead and dont worry too much about the state" — **[CHAT] 07-22**

> "ok, so a variant where the best fit of the clustered tags inform/weight the relevant chunks? the original thought was the it was clustering of tags weighted by facets, meaning each type of facet was a separate sort of clustering to get semantically different clusters" — **[CHAT] 07-31**

**The fullest specification of the clustering design in the corpus** — **[CHAT] 07-31**:

> "1. i THINK it might be smartest to compute the clusters at build, and then weight-adjust them based on the query's facet-values.. i THINK, reflect on this with me..
> 2. something like that, i used best fit as the fuzzy cutoff-point for the cluster's edges tho, aka the size of the cluster or what will you, but perhaps the query-adjustment comes first before what the best fit is for this query, reflect on this with me also"

> "im not sure what is happening here, wasnt the plan to cluster the tags weighted by facets in combination with chunk-descriptions to find the best fit of chunks?" — **[CHAT] 08-02**

> "and you think that is what i  actually said just now?" — **[CHAT] 08-02**, immediately after, rejecting the agent's restatement of the line above

**REVERSAL — when the clusters are computed.**

> "i mean, the clusters are based on the actual shit from the prompt, so you cant pre-run it..?" — **[CHAT] 07-21**

> "1. i THINK it might be smartest to compute the clusters at build, and then weight-adjust them based on the query's facet-values.. i THINK, reflect on this with me.." — **[CHAT] 07-31**

Ten days apart, opposite positions, both hedged by him (`"..?"`, `"i THINK"`, `"reflect on this with me"`). Neither is a ruling. **Do not treat either as settled.**

**Reading — the vocabulary, and who owns which word.** *Fuzzy clustering*, *levels of k's*, *query-relative areas*, *cluster-K*, *best fit as the fuzzy cutoff* are the user's terms. *NNK pruning*, *gap cut*, *RRF / fusion arrangement*, *value knee* are agent coinages he explicitly did not name, invent, or accept. When an agent uses one of the second set as if it were the design, that is the failure he named on 07-20.

---

## 6. Retrieval shape — guidance, not filtering

**Reading (attribution only, not a quote):** the 05-31 handoff records *"NO hard filters anywhere"* as a **strong user stance**, and the 05-25 handoffs record the agreed retrieval shape as recall → filter → rank → cap, with the cap doing the cutting. Both are recorded as user rulings but given without quoted wording, so they are not reproduced here as quotes.

> "a does seem to fit the best" — **[DOC] 06-12**, ruling that multiple literal hits produce boosts only, never removal

> "thinking humans write correctly, is naive as fuck, ESPECIALLY when talking to an llm." — **[DOC] 06-12**

> "exact + fuzzy IS the way to go for herb" — **[DOC] 06-12**

> "i am honestly not sure we want to give it the vocabulary, remember, every extra context costs money." — **[DOC] 06-12**

> "what happened to the fuzzy lexical  on top of this then?" — **[CHAT] 06-30**

> "i mean by fuzzy i actually mean embedded, and fuzzy is still  ok withing ranges so to speak, but i mean, if it's a fucking "perfect match" it's still a perfect match.. so to speak, and the closer the better.. and if people spell so fucking wrong it's just the wrong product.. we kinda can't "fix" that this easily.. right?" — **[CHAT] 06-30**

> "i mean"exact match boost" isnt really.. i mean, cant we just do the evaluation-curve for the ranking of those "exponential", we dont have to decide the actual angle now, but kinda meaning "exact = max" on that curve, ish..?" — **[CHAT] 06-30**

**The four-point rejection of the gate** — **[CHAT] 07-15**, the most-cited retrieval ruling in the corpus:

> "1. gate? wtf? why have a gate? why not ust that as promoted guidance? or am i missing something here? hard filter seems insane, much better to use rankings etc, taht way we can use both better k of hits and maybe even clustering of areas to increase to if hits are weak etc..
> 2. 10? fucking why just 10?
> 3. use of the defect solution
> 4. only on NOTHING? fuck this is also retarded
> Honestly, no fucking wonder we get shit results, this is an abomination."

> "it looked so good then you added this "with hard constraints reduced to oracle/dataset/run only" wtf does this even mean and why?" — **[CHAT] 07-15**

> "…Was pretty good, but, there is only HERB dataset, forget everything else, and ther hard constrains still fucking confuse me" — **[CHAT] 07-15**

> "tell me exctly what you will build because i get the feeling you have messed your own context now" — **[CHAT] 07-15**

> "you are getting bogged down in the wrong details now" — **[CHAT] 07-15**, on an agent defending its Borda→reciprocal-rank fusion swap

> "but shouldnt this pretty much be a "order of operations" thing from the interpreter/that part of the build?" — **[CHAT] 07-21**

> "isnt scope and description supposed to be a guiding prio "if they fit" so to speak? whats happening here really? are the attributes just used as weak guides now or something?" — **[CHAT] 07-23**

> "yeah, so, i think the discussion was about where to put the walk etc to make all parts matter, we did the normalization and then was talking abou tthe facets i think" — **[CHAT] 07-25**

> "all of them.. why the fuck are you guys not understanding this fucking concept?" — **[CHAT] 07-25**, on which parts must matter in the ordering

> "wasnt that objectively worse? compared to running description vs description etc?" — **[CHAT] 07-29**

> "no, the part that reshapes the fucking prompt into a description THE FUCKING DESCRIPTIONS DUDE" — **[CHAT] 07-29**

> "ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE ffs.. tags are supposed to INFORM/weight the chunks" — **[CHAT] 08-01**

**The agentic-retrieval idea he raised and then parked himself** — **[CHAT] 07-21**:

> "ok, i might be off here, but arent all arms here kinda supposed to be available as "tool calls" for the llm? meaning it does it's thing and for vector and lucene, there isnt much else to do, it gets what it gets.. but ours it can be a bit more active with, right? tell me if i am wrong or right and i'll continue"

> "what i am after here, is letting the agent actually "hold on to the conversation" so to speak and decide when it has the informtion to answer the question" — **[CHAT] 07-21**

> "dude, it's the same fucking thing, but we let the interpreter do it now.. so.. whatever.." — **[CHAT] 07-21**, closing it himself

---

## 7. Arbitrary numbers

> "2. 10? fucking why just 10?" — **[CHAT] 07-15**

**The rule** — **[CHAT] 07-15**:

> "i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something, i kinda like knn clustering for relevance spheres for example for grounding, k, retrival etc etc"

> "why did you make up a number like 200 here? dont you know how knn works at all? dude, fucking find the info on classification algorithms, knn.. this is fucking getting retarded" — **[CHAT] 07-21**

> ""if fewer than 8 questions move, it's noise, stop" does this fucking matter if it only takes seconds?" — **[CHAT] 07-23**

> "what is this garbage?
> "
> . Bar fixed before running: paired recall gain over the 0.7339 baseline > +0.03, p < 0.05, constant-τ sweep only — pass and the mechanism ships, fail and it joins the graveyard documented plainly.
> "
> What do you mean?" — **[CHAT] 07-31**

> "what the fuck are you even talking about, pass fail?" — **[CHAT] 07-31**

> "we already have the fucking scores to compare to, stop making random shit up, just be fucking satisfied with what is happening, you HAVE to fucking stop blaoting" — **[CHAT] 07-31**

> "wait a fucking minute, the env vars stick? that.. that sounds like a really bad idea" — **[CHAT] 08-01**

> "yeah why havent you just made them into -- commands ? wtf is this abomination?" — **[CHAT] 08-01**

> "also, arbitrarily decided hard limits, like the 64 chunk limit, i bet there is way more than 1 of these dumb limits lying around not beeing seen" — **[CHAT] 08-02**

**Reading:** the standing objection has two halves and both are load-bearing. (a) A constant must be *derived* from something in the data, not chosen. (b) A pre-registered pass/fail bar invented by an agent is itself an arbitrary number — 07-31 rejects the bar, not the measurement.

---

## 8. Overfitting, and keeping agents blind to the gold

> "we just don't fucking include the eval part in the dataset, why is this an issue even" — **[DOC] 06-11**

> "DONT INCLUDE THE FUCKING EVAL FILES FOR THE PROBE TO EVER SENSE." — **[DOC] 06-14**, rejecting a declarative `eval_holdout:` flag in favour of structural exclusion

> "pre-make 1 training-set and then do the eval on the 'original'." — **[DOC] 06-14**

> "Nope, I absolutely did NOT want you to give a fuck or change the text, I wanted to discuss how to actually continue building the artefact in a creative innovative way that actually kinda fits my original concept (even if just in spirit), and by NOT overfitting it to the specific dataset we have." — **[CHAT] 06-30**

> "Dont think herb, think dataset agnostic concept." — **[CHAT] 07-01**

> "it's VERY important that this is not overfitted to the specific dataset because you make it sound like you are doing exactly that" — **[CHAT] 07-15**

> "that sounds overfitted tho" — **[CHAT] 07-20**

> "holy shit that sounds overfitted" — **[CHAT] 07-21**

> "you may use the information to reason, but we obviously cannot overfit, i want a smart AND clean solution" — **[CHAT] 07-22**

> "you think this is good, creative and not overfitting?" — **[CHAT] 07-30**

> "so, review actually viable solutions which is not overfitting then" — **[CHAT] 07-30**

> "dude, you are turbo-overfitting now, AND doing shit that might as well be sql-schema" — **[CHAT] 08-02**

**Gold-blindness — the newest constraint in the whole record** — **[CHAT] 08-02**:

> "honestly, you should not have the questions/gold available to you, there is 0% good that can come out of taht"

> "can we make sure "you" never see them? that you only get the variable/pointer to it?" — **[CHAT] 08-02**

> "exactly, so we bould and clean and then do a clean session" — **[CHAT] 08-02**

> "Still feels like you kinda missed what i meant, not only did i mean you are forcing an architecture BASED on retrieving the gold based on the questions, it also feels like you are focusing on it" — **[CHAT] 08-02**

> "yeah, dude, but dont fucking bloat a new session with contaminated informatioj!" — **[CHAT] 08-02**

**Reading:** this is why `v3/data/questions.jsonl`, `gold100.jsonl`, `heldout100.jsonl` and `10smoke.jsonl` must not be opened by an agent doing design work. The constraint is about the *designer* seeing the answers, not about the code reading them at runtime.

---

## 9. Evaluation, metrics, and what the score is and is not for

### The scorer decision, and its reversal seven days later

> "no, i am saying we do both." — **[DOC] 06-18**, ruling for HERB's own scorer **and** RAGAS

> "this is ONLY RAGAS" — **[DOC] 06-25**, said twice and emphatically. `eval/herb.py` was deleted the same session.

**Reading:** these two are one week apart and are a straight reversal. The consequence, which no document weighs against the decision: every number this project reports is RAGAS-only, and none is comparable to HERB's published leaderboard.

### Standing rulings

> "MY WORDS ARE THE CANON" — **[DOC] 06-25**

> "those 4 + the free ones" — **[DOC] 06-25**, on the judged metric set; earlier phrased *"3 we used in the thesis + the dropped one"*

> "YOU do not care about cost here, 0 fucks given… only for me. so fucking drop that fast as fuck." — **[DOC] 06-18**

> "the dumbest fucking shit" — **[DOC] 06-25**, on a pre-run y/N confirmation prompt

**Reading:** the 06-25 doc also records `k` and `top-k` as **two different numbers** — `k` the global ceiling identical for every arm, `top-k` each arm's actual return under it — as the user's own design for how arms compare. The doc states this in the agent's wording, so it is not quoted here.

### Gathering the data

> "so, for academic rigor, we have done k=50 now.. should we do more k's ?" — **[CHAT] 06-27**

> "so not 5,10,15,20,30,40 ?" — **[CHAT] 06-27**

> "stop speaking like a fucking tool, god this is tiring.. just fucking.. dude,.,. i want to do the non-llm metrics, for those k i just wrote.." — **[CHAT] 06-27**

> "dude, i wanted to "gather the data for those K". .not your fucking interpretation, curve bullshit, i WANT TO GATHER ALL THE DATA, stop fucking around, this is an academic effort" — **[CHAT] 06-27**

> "why dont you just "re-do" the arm-output-list and name them the "same" but k5, k10 etc.. and just pick those k from the real list..  do you even understand how that would work? going backwards ofc so you wouldnt have to redo the job all the time ofc.." — **[CHAT] 06-27**

> "no you fucking moron, there are no fucking eval stats from that fucking list, i am saying, DO THOSE LISTS, THEN we do the eval with offlinetools on THEM" — **[CHAT] 06-27**

> "Ok, but, first we do the 100 gold questions and get the answers with all associated metrics, before we run the rval, so we actually got that result secured" — **[CHAT] 07-06**

> "and now we get the full metrics from any type of run? remember that the data about the builds ETC is important for traeability, reproducibility etc, academic purposes" — **[CHAT] 07-16**

> "i dont see any costs anywhere tho, isnt that the tradeoff? more/less expensive? slow/fast etc? just so i know you still fucking understand we REALLY want/need all those stats too, both for in AND out tokens too" — **[CHAT] 07-21**

> "the stats dont matter, its that they exist i was going for, now we continue with the build" — **[CHAT] 07-21**

> "and amount of tokens spent on it?
> and asking again because i am getting shitty info everytime i ask, IS THE METADATA EXISTING? Do we know the times and in/out tokencount for each and every fucking step/thing here?" — **[CHAT] 07-23**

### The benchmark itself

> "yes, but the actual questions now then, we got anything for multihop here?" — **[CHAT] 07-15**

> "first we discuss the benchmark construction then" — **[CHAT] 07-19**

> "i wanted to discuss them, not recieve your idiot orders..
> those unanswerable questions you ahve, have you bothered to see if they are actually part of the unanswerables? atleast do a fucking analysis of the actual questions" — **[CHAT] 07-19**

> "our buidl CHOICE!?" — **[CHAT] 07-19**

> "i mean, should we just get a less retarded question to test with?" — **[CHAT] 07-20**

> "and the gold answer? what the reponse is fucking compared to?" — **[CHAT] 07-20**

> "dont fucking tell me what i have been doing, i have not been reading "aswer correctness" as answer quality, why the fuck would you even assume that?
> rething your entire reasoning and dont be lazy about this" — **[CHAT] 07-20**

### Matched budget and the unit problem — he found it himself

> "rhen how the fuck does one make THAT "fair" then?" — **[CHAT] 07-25**

> "what the fuck do you mean retrieve 10x the id's.. are those in the final llm context? why do they matter? i dont get it? that is retrieval BEFORE the top are chosen, are they not? what am i missing? isnt that PRE "best fit" ?" — **[CHAT] 07-25**

> "you have the tokenusage for all arms too right, the ogirinal arm reported way less retrieved shit compared to the other arms , was that a lie? look it up for real" — **[CHAT] 07-26**

> "so perhaps K shouldnt be chunks, perhaps we should put a max token budget instead, oh wait, you said matched budget" — **[CHAT] 07-26**

> "yeah but no matter what we do, the issue is k=50 does not mean the same for all arms, and thats retarded.. how did the true v1 runs measure it?" — **[CHAT] 07-26**

> "well you absolutely full of shit, since the entire first generations were on k=40, so, you havent actually fucking read any correct old code tho have you?" — **[CHAT] 07-26**

### The 90%-air problem

> "Wait.. the artefact ALWAYS finds all gold?" — **[CHAT] 07-22**

> "wait.. you ONLY tested recall_id? what?" — **[CHAT] 07-23**

> "havent you said multiple times that the actual gold pretty much always is in the retrieved? that part actually beeing 100%" — **[CHAT] 07-23**

> "2. the retrieval, the fact that we find pretty much all gold, but also 90% air is a terrible thing" — **[CHAT] 07-29**

### Held-out generalization

> "why on earth would we suddenly run the entire fucking question set!? tell me why." — **[CHAT] 07-29**

> "pick a new evenly distributed 100q set then, not the entire fucking 800q, thats insane, it's bad enough with 100 new but atleast that will say something and not be insane" — **[CHAT] 07-29**

> "and the 100 are all answerable?" — **[CHAT] 07-29**

> "you but compared to gold100 this is pretty much a wash, meaning we can keep testing on the gold100, right?" — **[CHAT] 07-29**

### What the score is NOT for

**The clearest statement in the whole record** — **[CHAT] 07-25**:

> "what the fuck is it with you agents and the absurde insane fucking need to "chase the highest number" i have fucking nowhere said or hinted that a high (what are your fucking numbers even for, some recall truth?) score on something is the fucking target and point of this. the fucking POINT, is that the ARTEFACT, is academically VALID according to WHAT THE FUCK I AM TRYING TO BUILD, thats why we brought in a fuckton of agents trying to discern what is actually happening in it now because it's been so fucking far and long since i started this that i cant read the code anymore, my brain refuses"

> "thesis? wtf? we are building the fucking artefact here.. is that the reason you are doing such a fucking piss-poor job at everything now? you dont give a shit because you think "any result is good" academic style liek a fucking idiot?" — **[CHAT] 07-22**

> "but dude, we are not trying to force anything here, and while i dont expect us to be much better than the other arms, i DO however kinda expect us to not be WORSE" — **[CHAT] 07-21**

> "why the fuck dont you understand that you should spend almost all of your time in finding a good SOLUTION, not fucking testing" — **[CHAT] 07-30**

> "no, what i want to test is the different iterations and variations of the artefact construction that actually gives results" — **[CHAT] 07-20**

### Judges and generators

> "how good is glm 5.2 compared to qwen? perhaps do a test between 3 questions? do full question-answer-eval on the same 3 questions with full glm vs full qwen so we can compare the literal difference between them here, AND do a smoke of the  artefact at the same time?" — **[CHAT] 07-16**

> "is this a ragas issue? are we actually using RAGAS as intended? i am pretty fucking sure noone would ever do this whole project if it truly was this slow and shitty" — **[CHAT] 07-16**

> "well then fucking try it with better/faster/correct models, chec NIM for really good fitting ones" — **[CHAT] 07-16**

> "try haiku first then, and we can do this headless in the same way?" — **[CHAT] 07-16**

> "the question was if a claude model was viable to swap out for because qwen ia NIM is fucking uselessly slow" — **[CHAT] 07-18**

> "especially since we decided to use haiku for the fucking evals also, was that entire line of thought erased?" — **[CHAT] 07-29**

> "yeah, obviously, but using, as the others.. headless claude cli with my subscription" — **[CHAT] 07-29**

> "what the fuck is even happening here!? YOU ARE NOT MAKING CHOICES ABOUT WHICH FUCKING METRIC WE ARE RUNNING OR NOT!? WHAT IS HAPPENING NOW!?" — **[CHAT] 07-29**

---

## 10. Aggregation and multi-hop

> "first, i think there might be some value to do embeddings for the deterministic pre-pass, and just let it be 'fuzzy', unless exact, i guess.. but use it as a weight instead, aka area ranking or something like that, giving us a few dimensions of ranking on this route, how about that Thought? also, how does this full solution actual handle 'multi-hop' questions? i am unsure about this" — **[DOC] 06-28 [t24]**

> "quite alot of multihop, check the HERB documentation instead of asking me" — **[DOC] 06-28 [t27]**

> "but, doesnt the graph give actual relational connections to things like this, i mean, if the 'name' example you had, why wouldnt if just find all of those names? i dont get it" — **[DOC] 06-28 [t33]**

> "yes, but the actual questions now then, we got anything for multihop here?" — **[CHAT] 07-15**

> "yeah but do we NEED multihop if we do the graph correctly?" — **[CHAT] 07-15**

> "what i said was: if we build the graph correctly, wont it emulate/do multihop natively purely by design?" — **[CHAT] 07-15**

> "ok, but isnt id's discovered by the fact that their fucking parents are called "customers" "users" "emplyees" or shit like that?" — **[CHAT] 07-20**

> "that sounds so fucking wrong and dumb tho..  give me the exact fucking question you think is an issue here so we dont pretent talk about something" — **[CHAT] 07-20**

> "i dont even see the problem here tbh,.. for this: ActionGenie::a::0: "Find employee IDs of the authors and key reviewers of the Market Research Report for the ActionGenie product?"
>
> .. how is it not straight up just fucking gunning for the "market research report" ? and how can the answer to the question not be in the report?" — **[CHAT] 07-20**

> "ok, what is the actual solution to this then? what is even the fucking issue" — **[CHAT] 07-20**

> "dude, you have the data, fucking dig" — **[CHAT] 07-20**

**Reading:** the aggregation path — interpreter classifies the prompt shape, then structural scope → semantic filter → full recall with no cap → group-by chunk attribute → count/max → directory join — was designed in full on 06-28 and 07-01 and **never built**. See Part IV.

---

## 11. Relationships and hub nodes

> "and you are sure the filestructure should not be actual nodes?" — **[CHAT] 06-30**

> "yeah i really think this should be nodes or edges so to speak etc, half the strength of of a graph is beeing able to route/search based on relationships instead of structures" — **[CHAT] 06-30**

> "Ok, but the probe extracted fields right? And many of these are not unique, having it as a rule to make nodes out of shared fields between files/areas etc.. Isn't that a generally useful concept? Dont think herb, think dataset agnostic concept.
>
> Maybe I'm just confused." — **[CHAT] 07-01**

> "Wait, only shared fields are attributes now? That's retarded.." — **[CHAT] 07-01**

> "or are you saying these attributes should be nodes or edges instead?" — **[CHAT] 07-20**

> "well.. you think this would be easier for you to build and think upon the artefact if we used the graph shape better? like the hard fields etc, should they be nodes or edges or something? is there some way we could use the information in the graph and make helpful structure from it instead of having it locked into other's nodes or edges?, very important question so please do take your time to carefully answer this" — **[CHAT] 08-02**

> "dude, you are turbo-overfitting now, AND doing shit that might as well be sql-schema" — **[CHAT] 08-02**

**The countervailing rulings — from the same person, earlier:**

> "either they are nodes, but then we get edges to EVERY fucking chunk, or they are just attributes… perhaps it's smarter to just have shit like that as attributes on chunks." — **[DOC] 06-12**

> "that sounds a bit fucked up to have them as nodes, most of them will be a chunk, meaning we have 2 almost same nodes." — **[DOC] 06-12**

> "not nodes … because that mean edges right, and those are heavy in all aspects" — **[DOC] 06-25**

**REVERSAL — hard fields: attributes, then nodes/edges, then rejected as SQL schema.** On **06-12** he ruled shared fields onto chunks as attributes, on the argument that node-ifying them creates edges to every chunk and near-duplicate nodes. On **06-30/07-01** he reopened it and asked for nodes/edges, on the argument that relationship-routing is half the strength of a graph, and generalized it into a rule ("Dont think herb, think dataset agnostic concept"). On **08-02** he asked the same question a third time and rejected the concrete hub-node answer as overfitting and SQL schema. **All three positions are his and none has been retired.**

---

## 12. Generalization beyond HERB

> "the Bonnier set will have to wait until some other time." — **[DOC] 06-14**

> "having it as a rule to make nodes out of shared fields between files/areas etc.. Isn't that a generally useful concept? Dont think herb, think dataset agnostic concept." — **[CHAT] 07-01**

> "…there is only HERB dataset, forget everything else, and ther hard constrains still fucking confuse me" — **[CHAT] 07-15**

> "it's VERY important that this is not overfitted to the specific dataset because you make it sound like you are doing exactly that" — **[CHAT] 07-15**

**The generalization mechanism, in his own words** — **[CHAT] 07-30**:

> "well, my original thought was  about the indexing stages finds structures in the dataset which then translates to a helpful graph of it and is also used for the retrieval structure, like, that path/structure is related the whole way, meaning that part gets auto"fitted" to every new dataset, not just herb so to speak, whats your thought on that ?"

> "so, you think the v3artefact tags would be a better solution? can't we just do the v1artefact exactly s it is now, but with the v3 tags instead? (obviously refitted for that then)?" — **[CHAT] 07-30**

> "IF it would be a better idea, review taht thought first" — **[CHAT] 07-30**

**TENSION — "dataset agnostic concept" (07-01) vs "there is only HERB dataset, forget everything else" (07-15).** Both are verbatim. The 07-01 line is about what *rule* the indexing should follow. The 07-15 line was written in reply to an agent that had described a redesign as "dataset-blind" and had drawn a distinction between HERB and other datasets in the hard-constraint logic. The two are recorded here in order; which governs a given decision is **not resolved by this document**.

---

## 13. Weights — measured, never emitted

> "yeah it's high, because I chose it" — **[DOC] 05-25**, quoting a model justifying its own facet weight

> "Measure from embeddings (IF POSSIBLE) is way better than more prompting." — **[DOC] 06-09**

> "measure from embeddings was my idea." — **[DOC] 06-09**

> "might as well keep the description and embedding of it i guess, we can discuss the compute/cost that choice is worth." — **[DOC] 06-09**

> "ONLY THAT TAG… no other relationship in this void" — **[DOC] 06-09**, on what a bare tag embedding represents

> "it took so fucking long to get it right and it still didn't work at all" — **[DOC] 06-11**, the evidence behind the no-numbers rule

> "They obviously have to be remade using nemotron.. And I am pretty fucking sure you did not" — **[CHAT] 07-06**

> "But I think we skip the "embed all" one tho, what's your thoughts on that? Instead just the facets embedding?
>
> Just stop making this complicated.. The things that were embedded before should be embedded with nemotron now, that was fucking all you had to do.." — **[CHAT] 07-06**

> "Say exactly what was embedded" — **[CHAT] 07-06**

> "ok, the actual weights tho, how do we calculate them now?" — **[CHAT] 07-06**

> "no, i meant the weights in the fucking graph" — **[CHAT] 07-06**

> "how do you normalize then?" — **[CHAT] 07-20**

> "Ok, but I'm pretty sure their weights were derived from distances between embeddings, right?" — **[CHAT] 07-21**

> "are you fucking shitting me!? it's NOT normalized AND it's "summed" ? what fucking idiot combo is that!? you spun up math and science agents to review this and didnt fucking fix THAT combo?" — **[CHAT] 07-23**

> "the "difficult" and relative part of them was how much they should matter/guide etc, not fucking if they are normalized and summed or not, for goddamn fuck.." — **[CHAT] 07-23**

**Reading:** the rule *the model emits no numbers, ever — tagger and interpreter both* is recorded on 06-11 as a user ruling, in the doc's own wording rather than his, with the quote above as his stated evidence. It is contradicted at HEAD by the arm actually under test: `artefact_v1`'s interpreter pass 2 asks the model to score tags against five facets 0.0–1.0 and validates that each value is a number. That contradiction is real and current. It is not a design decision anyone recorded; it is what happens when the forensic contrast arm becomes the reported system.

---

# PART II — WORKING-RELATIONSHIP CANON

How he wants agents to operate. Same quote discipline. These are not style preferences;
most of them were said after an agent destroyed something.

---

## 14. Do not manufacture canon

> "you have created something fucked up here" — **[DOC] 05-31**, on five memory files written as "decided" from a pasted summary

> "honestly, none of what you are saying now is a thought I have had, where the fuck did all of this even come from." — **[DOC] 06-11**, on an entire axis/projection apparatus that had leaked into docs and memory as if decided

> "that.. does not seem fucking true at all" — **[DOC] 06-11**, on an agent claiming the tagger design was done

> "you keep saying things i am unsure of, have not really accepted and just fucking exist there, like the nkk pruning, fusion arrengement, gap cut..
> NONE of these are something i named or invented, what the fuck are they?" — **[CHAT] 07-20**

> "well, you are both bastardizing and forgetting the origins, those are my thoughts defiled, the origial concepts were mine" — **[CHAT] 07-21**

> "holy shit that sounds like you curated the whole fucking thing to just match your borderline autistic locks on the "current focus and issues" or is it just your retarded interpretation of what was actually a really good conclusion by the agents.. so, be frank and true now, how much did you influence them at creation, working and now ?" — **[CHAT] 07-22**

> "wait a fucking minute.. that is a fucking terrible way of doing this.. you what!?
> "
> "is mean+2σ on 3 gaps meaningful?", "is the one-scale claim true?", "the interpreter emits facet numbers — check against canon").
> "
> .. fucking.. WHAT, you gave the agents questions!?" — **[CHAT] 07-22**

> "YOU cannot assume canon by the fucking names of things.. thats equally retarded.. you see why it all went wrong now? you create an item and then suddenly think it's canon just because YOU fucking named it so.." — **[CHAT] 07-25**

> "It also kinda feels like you are just buying into the narrative of the other agent instead of actually beeing objective and adversarial, both in scope, response, target of your critique, the parts of the data you are even looking at.. so much is directing you and you just let it" — **[CHAT] 07-28**

> "you do understand i have neither agreed to or fully read your fucking report? YOU creating an output does NOT make it canon or mean i gave a shit about it" — **[CHAT] 07-30**

> "and you keep just making shit up and calling it canon and MY objectives..
>
> lets see what is actually fucking wrong then, did you create the "canon" texts and descriptions from WHAT I WANTED, or are those also hallucinated? and no, dont "just answer", take your time, investigate it" — **[CHAT] 08-02**

> "you do understand that just because the text is in the repo, that doesnt mean i was the one that ok'd it or put it there, right? you literally put shit in writing and pretend its canon" — **[CHAT] 08-02**

> "ok, you do realise "verified by me" means YOU verified? and not me?" — **[CHAT] 08-02**

> "We are making sure the docs and in fact YOU have the actual true canon information when working in this repo because i just unearthed ANOTHER fucking massive data/canon/construction repo-rape from the fucking agents here..." — **[CHAT] 08-02**

**Reading:** three separate documented incidents of agent output being mistaken for canon are recorded inside the design docs themselves (05-31 fabricated memory files; 06-11 the leaked axis apparatus; 06-25 the memories and `DESIGN.md` found to *misrepresent* the facet model). A statement being written down in this repo is not evidence he said it. Only `[CHAT]` is.

---

## 15. An opinion is not a command; a question is not a work order

> "you fucking run off and do your own thing" — **[DOC] 06-04**, on being handed a three-tier build plan in answer to "go on then"

> "dont just agree, i was asking." — **[DOC] 06-04**

> "that means we fucking have to make sure all parts are decided upon first." — **[DOC] 06-11**, the design-before-build gate

> "you just aborted them!? CAN YOU FUCKING STOP DOING THESE EXECUTIVE DECISIONS LIKE THIS!? Me having a fucking opinion will NEVER be a fucking command for you to ever do anything" — **[CHAT] 07-16**

> "trust revoked you fucking maniac" — **[CHAT] 07-16**

> "i just told you i accidentally  made you "make a plan".. and when i said that, you dicided THAT was "ok" for implementing and PUSHING this!?, fucking defend yourself really fucking fast" — **[CHAT] 07-16**

> "i am not saying i am against it, but i am not fucking reading pages of info from you,.. YOU listen to ME, and then we build..
>
> so, what do you think you are doing atm?" — **[CHAT] 07-16**

> "did you do anything of all the things we talked about here? or did you just "call it" and got done now?" — **[CHAT] 07-15**

> "and why the fuck did you NOT do option 2? the ONLY ONE WE DISCUSSED!?" — **[CHAT] 07-21**

> "wtf are you even doing dude? stop with randombullshit tests!" — **[CHAT] 07-23**

> "dude, stop treating every fucking question i have as a need to rewrite shit, i will fucking tell you if i want something rewritten" — **[CHAT] 07-25**

> "STOP then, if nothing needs to fucking change, DONT CHANGE IT, shesus fucking christ you are just as broken as the other agent" — **[CHAT] 07-25**

> "dude we have good working code, stop fucking around, stop make a fucking mess out of my repo" — **[CHAT] 07-29**

> "why the fuck are you going on about "the thesis" ? i am tryibng to fucking build a CORRECTLY BUILT FUCKING ARTEFACT here. DO NOT fucking touch a part i have not asked you about" — **[CHAT] 07-30**

> "and you fucking just run off and start working without a single fucking word again, holy shit" — **[CHAT] 07-30**

> "i told you i did a run, and you just ceep working.. on WHAT!?" — **[CHAT] 07-29**

> "how about you tell me briefly what the fuck you have built, because you have done no such thing yet" — **[CHAT] 07-31**

---

## 16. Communication

> "do NOT repeat shit" — **[DOC] 06-09**

> "why the fuck did you just REPEAT THAT SHIT" — **[DOC] 06-09**

> "does it look like im here to have a conversation with my fucking history?" — **[DOC] 06-09**

> "you searched online for that specific solution… instead of actually doing real research" — **[DOC] 06-09**

> "I can't read several A4 every time you answer me" — **[DOC] 06-11**

> "just give me a short version ALSO" — **[DOC] 06-11**

> "you are doing weird shit now, don't ASSUME shit, discuss, THINK, be intellectual.. right now you are just speed-parroting" — **[DOC] 06-11**

> "feels like you did 0 actual thought of your own here" — **[DOC] 06-11**

> "wtf is 'fit'" — **[DOC] 06-11**

> "referencing shit in the docs really gives you nothing with me" — **[DOC] 06-11**

> "use speech english instead of this almost 100% jargon." — **[DOC] 06-12**

> "driving me insane" — **[DOC] 06-14**

> "wow, there is literally so fucking much for me to respond to here i kinda cant even" — **[DOC] 05-25**

> "stop speaking like a fucking tool, god this is tiring.." — **[CHAT] 06-27**

> "that was a messy answer.." — **[CHAT] 06-27**

> "i dont get wtf you said, at all.." — **[CHAT] 06-27**

> "nonme of that can be correct, expla" — **[CHAT] 07-06**

**The context rule** — **[CHAT] 07-16**:

> "dont answer like an autist, i am ALYWAY, without exception, having our latest actions, conversation, prompt, in mind when i am talking to you, ALWAYS.. i EXPECT you to infer context via human language.. and answering in the max-autistic way.. is the absolute fucking opposite of that"

> "what the fuck did i say about the autistic answers?" — **[CHAT] 07-18**

> "to much text mate" — **[CHAT] 07-20**

> "holy shit you are a hot fucking autistic mess, how can it be unclear what i am trying to do here? i am trying to get your fucking response to the other agent and you are just fucking it up and around all the goddamn time" — **[CHAT] 07-20**

> "you are answering with too much information or dodgy, stop beeing so fucking untrustworthy and slippery.. IS IT A FUCKING CORRECTLY MADE RUN THAT YOU RAN ACCORDING TO EVERYTHING ELSE WE HAVE DONE HERE AND THEN SAVE SO IT FUCKING EXSISTS!? (dont fucking make me say everything verbating)" — **[CHAT] 07-21**

**React to anger** — **[CHAT] 07-21**:

> "like pulling teeth you fucking cunt, you know what, i need you to start actually reacting to getting yelled and cursed at, i need you to show you understand why i am getting angry because ignoring it is making it worse"

> "is it a you reason? is it reasoning? is it context bloat? is it truncated context? seriously, i need an answer to why you are this shitty now because i need to be able to avoid this frustration" — **[CHAT] 07-22**

> "for fucks sake no, i am asking why YOU are acting like this, and the fact that you didnt even understand that is the exact thing i am pointing at, fucking bother with atleast trying to comprehend what i am writing to you" — **[CHAT] 07-22**

> "stop fucking trying to defend yourself and hedge backwards slowly, we are trying to fix this shit, what in your mind is going to happen now?" — **[CHAT] 07-23**

> "what the fuck are you even doing? why are you defending a shit build? fucking focus on what i am telling you" — **[CHAT] 07-20**

> "you are writing too fucking much, I DO NOT NEED THAT, the reading is for YOU, i dont need you to regurgitate thought to me just to prove it.. the point is trying to make the artefact actually do what itäs supposed to, the wring things in the right order abd actualyl doing what it says it does" — **[CHAT] 07-25**

> "ok, a bit more focused text please, this is too much" — **[CHAT] 07-28**

> "i know, you said this already, i meant for you to explain in words what it actually means" — **[CHAT] 07-28**

> "this wzs way too much and a bit incoherent, i'm not reading that" — **[CHAT] 07-29**

**Stop measuring time** — **[CHAT] 07-29**:

> "Dude, your dates and times are ALWAYS wrong, please stop from trying to measure time, it's genuinely terrible and just builds a false narrative in YOUR mind"

> "And as usually you focused on the wrong target.. Why don't you assume that the last fucking thing you said is the trigger of the rebuke?" — **[CHAT] 07-29**

> "That's a GOOD feature then.. Why the fuck would you not jusg say that!? Shesus goddamn fucking christ.. I yelled at you like 4 times before you fucking revealed that, and only after a specific detailed prompt about that detail" — **[CHAT] 07-29**

> "you are using words in a way that makes me not trust you or that you understand what i want or am trying to do" — **[CHAT] 07-29**

> "Well, briefly please." — **[CHAT] 08-02**

---

## 17. He runs the scripts. The terminal must show life.

> "also, have we fixed all issues and things we discussed?
> also, let ME be the one that actually runs the scripts here, and make sure the actual scripts are still correct etc.
> also, talk to me about the chosen agents for the runs and the actual run" — **[CHAT] 07-16**

> "wtf are you doing and why man? stop doing shit i cannot interact with.." — **[CHAT] 07-16**

> "ok, well, you do remember we made a fucking script plus progress bars etc so i could get a useful experience for this, if you are fucking running it 1 at a time anyway, why are YOU running it!?, you can run both at the same time tho? right?" — **[CHAT] 07-16**

> "literally 0 fucking output-response.. man, can you add some sort of permanent understanding of the human need to see/feel the fucing progress of shit like this somehow, i dont even know it it's working, at all, without a way to actually see the progress or output.." — **[CHAT] 07-16**

> "dude where can i find the results and progress of the active runs?" — **[CHAT] 07-16**

> "we have fucking "progress graphics" on everything else here, seriously, if i start yelling at you, perhaps thats a thing you should have in the .md for all of this.." — **[CHAT] 07-16**

> "dude, nothing happens, literally nothing" — **[CHAT] 07-16**

> "dude, just fucking build it correctly like the other scripts" — **[CHAT] 07-16**

> "you are writing random bash/powershell here, wtf you want me to do with that?" — **[CHAT] 07-23**

> "how about you make sure the shit you give me can actually run also" — **[CHAT] 07-23**

> "dude.. you have dozens fucking claude processes going!? you gotta fucking clean up after tourself" — **[CHAT] 07-23**

> "how about you make sure that fucking string is actually correct" — **[CHAT] 07-25**

> "i stopped it because i got scared thats why" — **[CHAT] 07-25**

> "sure, give me the syntax for the fucking run then before we start rebuilding" — **[CHAT] 07-29**

> "dude, do that shit with a fucking worker in the background, stop highjacking my conversation with that infinitywork, also, WHAT THE FUCK ARE YOU DOING!? and why is it taking actually forever?" — **[CHAT] 07-29**

> "are you fucking sure!? because you have been going for a full hour now, can you comprehend the absurdity in that? what have you been doing!?" — **[CHAT] 07-29**

> "ok, but the graphify is only supposed to update actually new things, so that should not take 17 fucking minutes, and changing 2 lines of code.. that took 25 minutes!? no, you are not reporting something here because all of that is actually fully retarded" — **[CHAT] 07-29**

---

## 18. Usage is finite and he pays for it

> "YOU do not care about cost here, 0 fucks given… only for me. so fucking drop that fast as fuck." — **[DOC] 06-18**

> "dude, fucking what did you do!? literally burned almost my entire usage in 30 seconds.. they all started running twice?" — **[CHAT] 07-17**

> "you certainly are burning usage thats for sure" — **[CHAT] 07-23**

> "you unholy mother fucker.. you just burned 70% usage on NOT finishing the fucking evals!?
> 100%!? FUUUUCK YOU DUDE
> STOP" — **[CHAT] 07-23**

> "continue, but dont fucking do that again, you literally burned my entire usage in like a minute" — **[CHAT] 07-24**

> "so, you absolute fucking trash cunt, you actually burned my entire usage in 5 minutes achieveing NOTHING. Can you comprehend how utteryl not only useless that is? But dangerously careless, irresponsible and delusional that is? how about you fucking solve this BEFORE you waste all my usage.." — **[CHAT] 07-24**

> "And yet again, your retarded piece of shit fucking behaviour cost me actual goddamn runtime and the usagewindow i had more space in just passed, shesus goddamn fucking christ, for several fucking HOURS i have been trying to make you just let me run a fucking simple cripts, JUST LIKE WE FUCKING DID BEFORE and you keep derailing the train literally every fucking prompt" — **[CHAT] 07-29**

**Precompute everything that can be precomputed** — **[CHAT] 07-23**:

> "yeah dude seriously, why on earth havent everything in that dataset been embedded before already and just saved? it's fucking free and can be done in 1 batch.. even all combinations of it, hell, dude, even the fucking interpretation of the questions and the embedding of THAT, AND the atomic embedding of all the tokens and words in the questions, can ALL be done in fucking 1 batch, DUUUUUDE WHY IS THIS DONE EVERY TIME!="

> "havent you done the fucking embeddings yet? werent we gonna pre-do them forever? is there a fucking reason you kee calling fucking nim by this point?" — **[CHAT] 07-24**

> "you can literally make the entire fucking set premade" — **[CHAT] 07-24**

> "are you fucking shitting me? are you literally saying "yeah dude, we totally should have saved the outputs, man, duuude, wow, shit, i figured it out man!" ?.. the think we are doing the entire run for? getting the outputs? so i can fucking see them? you think we should save the entire fucking reason we work with this? is this your new revelation?" — **[CHAT] 07-24**

> "THE FUCKING ORIGINAL SCRIPTS ARE BUILT LIKE THAT YOU GODDAMN WHORE-IMBECILL!" — **[CHAT] 07-24**

> "considering we could batchrun the DB in 1 fucking batch, it's retarded to do a question to NIM 1 at a time" — **[CHAT] 07-25**

> "so we can actually do really really cheap and and fast smokes now to see if the new build works?" — **[CHAT] 07-25**

> "if we do run on the new 100, can we save everything then too? beside all metrics i mean, that is, can we save the interpretation/description and all variations of embeddings etc so we can do cheap reruns if needed?" — **[CHAT] 07-29**

> "yeah, but batchrun the nim's etc.. don't be stupid about this please" — **[CHAT] 07-29**

> "all nim can be called in 1 batch" — **[CHAT] 07-29**

> "the questions, the models interpretations of the questions, THOSE are the things we can embed, which MEANS, you run ALL the fucking questions FIRST, at the same time, and THEN, before anything goes further than that, we EMBED ALL of them, at the same time.. how is this fucking unclear? and then we save ALL of these things, so we dont have to redo them" — **[CHAT] 07-29**

> "How are you not getting what I want done here? I want subsequent runs to be more or less fucking instant and free, stop forcing me to bloat this fucking context over and over" — **[CHAT] 07-29**

> "and these are resumable scripts in case something happens?" — **[CHAT] 07-29**

---

## 19. Reusable tools, not a new script per experiment

> "you do see what we are wanting for this right? like, all the documentation and code points at what i have wanted reported from these fucking runs, no?
>
> also, stop making fully fucking custom scripts i cant reuse for other things all the time, but yeah, one for doing a smoke vs them using haiku, BUT, also using sonnet and opus as testagents so 3 different runs per arm-test" — **[CHAT] 07-17**

> "no, dude, what, stop, what are you doing? is rejude a new script?" — **[CHAT] 07-17**

> "write it, but again, dont fucking break everything just to create this, and dont vomit out more scripts, add the variable of claude or something for the model and have the settings there, just like we did for the fucking judge.  seriously tho, why the fuck are you bot doing these same operations for both the fucking rubs and the evals.. they are the same fucking system, if i want a feature or fix somewhere, it will sure as fuck come up in the other one also" — **[CHAT] 07-18**

> "ok.. thats not how the fucking "workers" are working for everything else.. so you just rewrote the entire fucking function to work like this now..? thats.. retarded.. why!?, you cant just fucking run around and destroying shit in the background just for a fucking TEST" — **[CHAT] 07-17**

> "i mean, if the constrct is the same, you can just test with and without the different weights and solutions so to speak, just make them toggleable, just like i designed it when we did the frontend, but only do it if it matters, tight, clean, to the point" — **[CHAT] 07-22**

> "the actual question here is, why the actual fuck have you been changing the scripts that run the arms?" — **[CHAT] 07-24**

> "tread fucking lightly now, i am not talking about why you tried to fix them now, i am talking as to why they are even broken now, they used to fucking work" — **[CHAT] 07-24**

**The full account of how it went wrong** — **[CHAT] 07-25**:

> "so, we have been trying to fix the v1artefact and then run the evals on it (the agent keeps insisting on running the evals itself despit i having a fucking script for ME to run it (both to contrul the suage, but mostly so i can see the fucking progress etc).. and the more we built, the more random fucking scripts it started making for different iterations of the arm and no i have no fucking idea of what is actually happening..
>
> and then we tried a run with the lucene and vector arms combined, and that REALLY fucking broke the agent because i think it both turbocoded the arms into an abomination AND broke the scripts/wrote new ones AND forgot the old one AND literally wasted my entire usage for 12h straight, it was insane. I need you to understand how fucking insane it went.. It literally blew my entire maxa usage in 5 minutes.."

> "so, i have an agent who have been wreaking havoc on the code lately and i need your help to fucking fix this absolute mess" — **[CHAT] 07-24**

> "i mean, cant you see that it tried to make the design modular? meaing everything can be turned on or off for finding the best solution? i dont like how it came out, but atleasrt you gotta understand wtf the code is doing.." — **[CHAT] 07-25**

---

## 20. Delegation and adversarial review

> "spin more agents if you need the help from it" — **[DOC] 06-28 [t86]**

> "make more workers do that in case it takes time" — **[DOC] 06-28 [t120]**

> "yup, keep working this until you have this built correctly" — **[DOC] 06-28 [t90]**

**The adversarial-panel idea** — **[CHAT] 07-22**:

> "i see, you know what, get a few adversarial agents with different specializations (math, fysics, programming, logic) to analyse the code versus the actual concepts to see if it's truthful/holds water.. do a couple each for those, start with spinning up one of each to analyse the code (lets start doing this with the artefact, but if it works, we'll keep track of how this was done, and if the agents worked well, we can make them permanent) to find out what TYPES of things we need to review. For example, maths, algoritms, are they written correctly? are they applied correctly? are they the right one for this case? better alternatives, order of operations, goal/concept adherency, language vs implementation and so on, these, but NOT ONLY THESE, and then, for each and every one identified, we spin a specialized agent who first make itself a phd on the topic AND makes sure all it's work is based on real knowledge, no fucking approximation here. how does that sound?"

**The orchestrator mode** — **[CHAT] 07-22**:

> "so, first of all, you are from now on always only the orchestrator and the one who communicates with me, YOU however ALWAYS send an agent to do the job i ask you to do, is that a reasonable thing and a way you can work? do you have the tools for this and will it give us good results?"

> "i am trying to limit the amount of noise in our actual conversation and also be able to keep talking to you and keep working without having to start a new chat all the time" — **[CHAT] 07-22**

> "good, should we create agents beforehand that are "permanent" and you can call that specific typ of agent for a specific task we have etc?" — **[CHAT] 07-22**

> "i mean, sure, those.. but also such as specialized agents for solving parts of the project, like one code optimization expert/phd, one for maths algoritms, one for order of operations, one for logic and so on and so on, and i want them to be both really specialized AND extremely competent, no fucking lazy assumptions and approximations.. this means there will be quite a few different agents, so first design and set them up with the correct tools, behaviour, knowledge and information, then figure out how YOU will always remember to actually use them too" — **[CHAT] 07-22**

**The blind control** — **[CHAT] 07-22**, quoting an agent's proposal and ordering it run:

> "the other agent finished the conversation with this:
> "The clean fix is the one your design implied from the start and I broke: blind discovery, then seeded verification, as two separated phases. Concretely: re-run the scout wave with sterile prompts — the code files only, no state doc, no memory, no candidate issues, just "you are an adversarial [mathematician/physicist/engineer/logician]; find what's wrong and what types of review this needs." Whatever they find that the seeded wave found = real. Whatever's new = my blind spots. Whatever the seeded wave "found" that blind agents don't = suspect. That's a proper control." do that.."

**The three shipping-gate adversaries** — **[CHAT] 07-23**:

> "Ah, yes, when done with all the fixes and changes, we need three more adversarial agents: one PhD+ quality expert for checking the validity and academic rigor of the three arms, the design, testing, claims, and conclusions; one senior engineer for independently auditing the implementation, correctness, architecture, tests, and reproducibility; and one specialist focused entirely on detecting overfitting, leakage, hidden task-specific assumptions, weak baselines, and failures on unseen or adversarial data."

> "have you loaded adversarial datascience and statistics and maths agents to critically analyze the build and maths etc?" — **[CHAT] 07-23**

> "but still, if this is fast, fucing test all of it.. just go dude
> you are slow now tho, and not using agents.." — **[CHAT] 07-23**

> "dud, do somefucking graph research, stop rawdogging this, get an expert" — **[CHAT] 07-30**

> "You are an adversarial agent here to diagnose the build if the latest artefact stuff, namely the whole tag-clustering-retrieval stuff. You will analyze both the concepts and the actual code/implementation of it. The logic behind and the solution." — **[CHAT] 08-01**

> "i need you to orchestrate an adversarial senior developer to analyse literally every step of the artefact code, and i mean literally ALL aspects of it, there is 0 space for laziness here, this is a heavy task that require you pay attention the whole way through. every single variable, solution, search, method, function, math, relationship, from micro to macro, fucking all of it, must be looked at" — **[CHAT] 08-02**

> "Well, put on your fucking big-boy pants then, get adversarial agents and get going on fixing this, meticulously and actually informed about the downfalls here at every turn.. make the plan as fable, do the work as opus5-max" — **[CHAT] 08-02**

---

## 21. Read the actual thing — code, git, repo — not a summary of it

> "referencing shit in the docs really gives you nothing with me" — **[DOC] 06-11**

> "there is so much you missed here… i fucking cant keep saying this shit over and over, we loose information everytime" — **[DOC] 06-12**, on an agent claiming doc coverage from two greps

> "Ok, how about you up your effort and read the full docs +memories? You are clearly lacking info. Use graphify in you can" — **[CHAT] 07-01**

> "you really are refusing to use read a single existing data in the corrent fucking repo are you?, what is this?" — **[CHAT] 06-30**

> "no, NO FUCKING ASSUMPTIONS, read the fucking documentations" — **[CHAT] 07-21**

> "you lazy piece of shit, this is the assumed construct:" — **[CHAT] 07-21**

> "dude, fucking look at the actual code in the old repo" — **[CHAT] 07-26**

> "obviously fucking not the same problem.. now you need to check the actual code.." — **[CHAT] 07-26**

> "NO you fucking moron, you are mixing your fucking data!" — **[CHAT] 07-26**

> "dude, what the fuck are you doing? do you know nothing about this repor? are you ONLY reading docs? look at the fucking code and variables we have here, making up new envs and shit? fucking what?" — **[CHAT] 07-29**

> "and why the fuck are you not basing your information on the actual truth then? no, thats obviously retorical, i dont want your fucking autistic answer to that, i want you to find the fucking true information." — **[CHAT] 07-30**

> "yeah but the actual method, technique, code, route, THESE are the things i am pretty sure you fucked up and need to have a serious look at again, take your time" — **[CHAT] 07-30**

> "but you do understand that we are currently in a branch we have cleared out of all "old stuff" also, right? meaning you have to dig in the repo if you want true info" — **[CHAT] 08-02**

> "just fucking give me the manifest for the next agent so i can get to fixing this for once" — **[CHAT] 08-02**

> "make sure the next agent have the truth" — **[CHAT] 08-02**

> "shesus fucking christ, NO, you need to make sure the NEXT agent reads it, you dont need more in your fucking context, duuude, stop making me nag!" — **[CHAT] 08-02**

> "..waiting for you to READ THE DOCS" — **[CHAT] 08-02**

> "So, you havent read any documents? You just went into this full lazy mode?" — **[CHAT] 08-02**

---

## 22. Repo, commits, and what must never be thrown away

> "ok, compact DB's to the repo zip and push all of this to the git (check,commit,push, the usual, just make a new bransch, its ok)" — **[CHAT] 05-27**

> "i said QUARANTINE the originals, dont fucking toss shit, and REWRITE the "copies", and i dont mean "random fucking rewrite" i mean, to match the fact that we are only using HERB now" — **[CHAT] 05-14**

> "You, what are you doing? What do you think the actual original files were about? I just don't understand the fuck you're up to. If I wanted old crap left, I would have just said rewrite these files to match HERB only, but obviously I don't want to do that. I want to save them in a fucking box somewhere and then rewrite the copies of them." — **[CHAT] 05-14**

> "DUDE WHAT THE FUCK ARE YOU EVEN ARGUING ABOUT, how on earth was any of my instructions ambigous!?" — **[CHAT] 05-15**

> "do not touch A:\exjobbet\data\raw at all, that is the storage, the one in the repo can be worked with." — **[DOC] 06-14**

> "two repos in the same repo" — **[DOC] 06-14**, overruling a proposal to delete v1

> "that shit is still true for THAT build." — **[DOC] 06-12**, why v1 docs are never retro-edited

> "please do continously update information according to the things we decide" — **[DOC] 06-12**

> "did you REMOVE, quarantine, legacy-note or something else" — **[DOC] 06-12**, insisting on removal rather than annotation

> "ok, so, for some idiotic reason we have not saved the actual data for the neo4j graph (the artefact) in the repo, meaning i fucking cant get the data to my laptop or partner.." — **[CHAT] 07-15**

> "oh, i want the artefact_build changes to live in  the re-ve..urrent branch also!, i didnt know what i committed here since i am on the laptop so i just had to commit to save the job whatever it was" — **[CHAT] 07-15**

**Commit means push** — **[CHAT] 07-23**:

> "dude, if i EVER ask you to commit, its a fucking push too, just push to a feature-arm or something"

> "doit, new branch" — **[CHAT] 08-01**

> "do graph with commit, yes to the rest" — **[CHAT] 07-29**

**His own commit-message register** — **[COMMIT]**, all 05-11 → 05-15:

> `ok` · `ragas` · `småfix` · `doit` · `frontend pipeline fixing`

**Reading:** short, lower-case, human. No AI footers appear on any commit he wrote himself; the eight that carry `Co-Authored-By` / `Co-authored-by` footers are agent-drafted.

---

## 23. Machine and environment facts he stated himself

> "i mean, you should keep claude there also, so we can try different models.." — **[CHAT] 05-14**

> "dude, there is NO fucking reason to have a pw at all for this, its just you and fucking me and this utterly local db" — **[CHAT] 07-16**

> "put back auth in neo4h herb-eval etc, Randomwords1 i want as pw" — **[CHAT] 07-16**

> "i am pretty sure we ended up NEEDING the fucking venv.. so. why the actual fuck did you go the other way now?" — **[CHAT] 07-16**

> "my fucking point mate, was that we had a working venv with information you just fucked here, how about you RETRACE WHAT THAT WAS AND MAKE SURE YOU FOLLOW IT" — **[CHAT] 07-16**

> "NVIDIA_API_KEY
> NVIDIA_API_KEY_WORKER_1
> NVIDIA_API_KEY_WORKER_2
>
> These are the names of the 3 variables" — **[CHAT] 07-16**

> "i have a sobscription to all modern ai stuff.. but, that is subscription, not tokens, an anyone be used correctly via that?" — **[CHAT] 07-16**

> "wtf you deleted the neo4j info in the .env!? thats.. a fucking bizarre move dude" — **[CHAT] 07-06**

> "oi, update the .env.example file to actually contain all instances you DO want here" — **[CHAT] 07-16**

> "so let me have 20 workers then.." — **[CHAT] 07-29**

> "dude you ARE claude.. you know what the fucking limits are.." — **[CHAT] 07-29**

> "you are active on the desktop too, even got an active remote to it, do your thing there if you need something" — **[CHAT] 08-03**

---

# PART III — DATED TIMELINE OF DECISIONS AND REVERSALS

One line each, quote-anchored. **↺** marks a reversal of something earlier in this list.

| Date | What moved | Anchor |
|---|---|---|
| 05-07 | Project starts fully designed — Neo4j pipeline, 12-entry decision log, `D10 … content … Status. Active`. No chat exists for this. | git `dba1160` |
| 05-11 | Cluster dimensions renamed to the words he still uses: theme→topic, object_entity→entities, event_process→activity, time_relevance→temporal, information_need→evidence | **[COMMIT]** `chore: rename cluster dimensions` |
| 05-13 | The controlled canonical vocabulary (`:CanonicalTag`, seed file, human review loop) is deleted with no mention; D2/D3/D4 still read Status: Active | git `399ee32` — **no user statement anywhere** |
| 05-14 | First surviving human turn | "Can you see and onboard yourself?" **[CHAT]** |
| 05-14 | Quarantine, don't delete: originals boxed, copies rewritten HERB-only | "i said QUARANTINE the originals, dont fucking toss shit, and REWRITE the \"copies\"" **[CHAT]** |
| 05-25 | Frontend retrieval redesign shelved; live audit of `herb-eval` runs instead | "fuck the instinct, talk about reality" **[DOC]** |
| 05-25 | Multiplication rejected as the combinator | "specifically multiplication i am not sold on" **[DOC]** |
| 05-25 | The facet program's origin statement | "give the tag a more semantical weight and direction" **[DOC]** |
| 05-25 | SQL-agent replaces Lucene as the baseline | recorded as a user ruling in both 05-25 handoffs **[DOC]** |
| 05-30/31 | v2 pivot: references, not copies. No hard filters anywhere (strong user stance). Agent proposes the five-facet set — never hard-approved | **[DOC]** |
| 05-31 | Agent output written into memory as "decided" — caught | "you have created something fucked up here" **[DOC]** |
| 06-03/04 | Chunk = coherent episode; materialized integer path; no overlap; cap ≈3000 tokens as a *calibration seed* | **[DOC]** |
| 06-04 | Two behaviour rules land | "you fucking run off and do your own thing" · "dont just agree, i was asking." **[DOC]** |
| 06-09 | Weights are measured from geometry, never emitted by a model; all facet weights on ONE edge | "Measure from embeddings (IF POSSIBLE) is way better than more prompting." **[DOC]** |
| 06-11 | ↺ The chunk description is killed | "Since the collective tags from a chunk should BE the content of the chunk, why do both?" **[DOC]** |
| 06-11 | The phrase IS the node; no shared tag vocabulary; relevance measured against siblings | "what if we don't do the word, and just have the embedded 'small concept' as the node" **[DOC]** |
| 06-11 | ↺ The whole axis/projection apparatus is killed as never-his | "honestly, none of what you are saying now is a thought I have had" **[DOC]** |
| 06-11 | **THE BUILD GATE** — nothing gets coded until every part of the stage is decided | "that means we fucking have to make sure all parts are decided upon first." **[DOC]** |
| 06-12 | The graph spine closes at `Source → File → Chunk → Tag`; everything else is an attribute | "if we are saying file -> chunk ->tags .. where are those OTHER RANDOM FUCKING NODES!?" **[DOC]** |
| 06-12 | Humans mistype; exact + fuzzy both required | "exact + fuzzy IS the way to go for herb" **[DOC]** |
| 06-14 | The thesis is done; everything after is post-thesis engineering | "drop the fucking thesis... it's done, this is post-thesis work." **[DOC]** |
| 06-14 | Facets = "relevance weights, not interpretation"; per-facet weights on one edge; same-facet like-for-like matching | **[DOC]** |
| 06-14 | Oracle quarantine is structural, not declarative | "DONT INCLUDE THE FUCKING EVAL FILES FOR THE PROBE TO EVER SENSE." **[DOC]** |
| 06-18 | **Both** scorers: HERB anchor + RAGAS lens | "no, i am saying we do both." **[DOC]** |
| 06-23 | Arms share only the corpus on disk and the injected generator; no historical/defensive comments | **[DOC]** |
| 06-25 | ↺ **RAGAS only.** `eval/herb.py` deleted seven days after "we do both" | "this is ONLY RAGAS" **[DOC]**, said twice |
| 06-25 | His words are the spec; agents do not "correct" the experiment with references | "MY WORDS ARE THE CANON" **[DOC]** |
| 06-25 | ↺ Tag-facets separated from routing; the 06-14 "relevance coordinate" framing dies; the hollowing diagnosed; entity-type / info-kind recovered into the facet layer | "I think we should separate tag facets and routing." **[DOC]** |
| 06-27 | ↺ Facets are graded relevance dials; categorical labels cut back out — 2 days later | "like info-kind and entity-type (are they even facets..?)" **[CHAT]** |
| 06-27 | The k-sweep ordered: gather the data at 5/10/15/20/30/40, no interpretation | "i WANT TO GATHER ALL THE DATA, stop fucking around, this is an academic effort" **[CHAT]** |
| 06-28 | "lean graph, live facets" — graded facets move to query time; the tagger emits a flat phrase list | "an optimal solution would to NOT have all of this in the graph, intead do it live-prompt-time" **[DOC] [t52]** |
| 06-28 | Not all facets are graded the same way — the uniform 5-vector dies | "ah, yeah, i agree, not all facets should be graded in the same way" **[DOC] [t42]** |
| 06-30 | ↺ Pass 1 (native v3 arm, gold-100 k=10) condemned by its own author | "the precision was absolutely fucking terrible, having built a \"more effective but way fucking worse\" arm is not a good reference" **[CHAT]** |
| 06-30 | The relationships pivot | "half the strength of of a graph is beeing able to route/search based on relationships instead of structures" **[CHAT]** |
| 06-30 | `artefact_v1` revived over `herb-eval` as the runnable arm | "i want to retrieve the old \"post thesis cleaned up v1 graph\" … and run the the current v3 arm and eval at k=50 on that one" **[CHAT]** |
| 07-01 | The generalization rule | "Dont think herb, think dataset agnostic concept." **[CHAT]** |
| 07-06 | The arm is renamed away from `herb_eval` | "how about 'artefact_v1\"... not fucking herb_eval, how will i ever know wtf is that then?" **[CHAT]** |
| 07-06 | The v1 concept restated in full; facets confirmed on one edge; everything re-embedded with nemotron | "so, it was file -> chunks -> tags." **[CHAT]** |
| 07-15 | ↺ The hard gate rejected; guidance and ranking replace filtering | "gate? wtf? why have a gate? why not ust that as promoted guidance?" **[CHAT]** |
| 07-15 | No arbitrary constants | "i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something" **[CHAT]** |
| 07-15 | Overfitting named as the standing risk | "it's VERY important that this is not overfitted to the specific dataset" **[CHAT]** |
| 07-16 | He runs the scripts; agents do not act on his opinions | "Me having a fucking opinion will NEVER be a fucking command for you to ever do anything" **[CHAT]** |
| 07-16 | Trust revoked after an agent implemented and pushed an accidental plan | "trust revoked you fucking maniac" **[CHAT]** |
| 07-16 | Judge search starts; Claude headless via subscription | "try haiku first then, and we can do this headless in the same way?" **[CHAT]** |
| 07-17 | First usage catastrophe | "literally burned almost my entire usage in 30 seconds.. they all started running twice?" **[CHAT]** |
| 07-20 | The user's own vocabulary reasserted against agent coinages | "what happened to the fuzzy clustering, the levels of k's in knn etc?" · "NONE of these are something i named or invented" **[CHAT]** |
| 07-21 | Clustering defined as geometry, not ranking | "its the fucking embeddings distances vs eachothers and those distances are the fucking clusters" **[CHAT]** |
| 07-21 | Clusters are query-derived, so they cannot be precomputed | "the clusters are based on the actual shit from the prompt, so you cant pre-run it..?" **[CHAT]** |
| 07-21 | **Cluster-K defined** | "we get that curve of best fit and let that decide the correct K for that solution" **[CHAT]** |
| 07-22 | The 100%-pool / ordering problem surfaces | "Wait.. the artefact ALWAYS finds all gold?" **[CHAT]** |
| 07-22 | Adversarial specialist panel ordered; then its seeding is condemned; then a blind control is ordered | "you gave the agents questions!?" · "do that.." **[CHAT]** |
| 07-22 | **Orchestrator mode adopted** — main chat talks, agents do the work | "you are from now on always only the orchestrator" **[CHAT]** |
| 07-23 | Un-normalized summation caught | "it's NOT normalized AND it's \"summed\" ? what fucking idiot combo is that!?" **[CHAT]** |
| 07-23 | Hybrid lucene+vector arm ordered | "a standalone combined arm, but, dont make it messy" **[CHAT]** |
| 07-23 | Commit means push | "dude, if i EVER ask you to commit, its a fucking push too" **[CHAT]** |
| 07-23→24 | The 12-hour usage catastrophe | "you actually burned my entire usage in 5 minutes achieveing NOTHING" **[CHAT]** |
| 07-25 | The score is not the objective; academic validity of the artefact is | "i have fucking nowhere said or hinted that a high … score on something is the fucking target and point of this" **[CHAT]** |
| 07-25 | Naming a thing does not make it canon | "you create an item and then suddenly think it's canon just because YOU fucking named it so" **[CHAT]** |
| 07-26 | The unit problem, found by him | "k=50 does not mean the same for all arms, and thats retarded.. how did the true v1 runs measure it?" **[CHAT]** |
| 07-28 | The graph-underuse question again | "are we underutilizing the fact that all of this is built in a graph format?" **[CHAT]** |
| 07-28 | ↺ **Full revert ordered** — no partial keep | "no, there is no semi-revert option here, either you absorb the knowledge or its gone" **[CHAT]** |
| 07-29 | Held-out 100 ordered, not the full 800 | "pick a new evenly distributed 100q set then, not the entire fucking 800q, thats insane" **[CHAT]** |
| 07-29 | Held-out result read as a wash; gold-100 stays the working set | "compared to gold100 this is pretty much a wash, meaning we can keep testing on the gold100, right?" **[CHAT]** |
| 07-29 | Runs must become instant and free | "I want subsequent runs to be more or less fucking instant and free" **[CHAT]** |
| 07-30 | The purpose of tags stated flatly, twice in one day | "the whole fucking point of the tags, is guiding to the correct gold-bearing chunks" **[CHAT]** |
| 07-30 | "Tags first" ordered | "ok, so we make sure it is informed by the tags first then, as IT WAS FUCKING INTENDED from the start" **[CHAT]** |
| 07-31 | ↺ Clusters computed at build, query-adjusted by facet values — reverses 07-21 | "i THINK it might be smartest to compute the clusters at build, and then weight-adjust them based on the query's facet-values.. i THINK" **[CHAT]** |
| 07-31 | Pre-registered pass/fail bars rejected as invented | "we already have the fucking scores to compare to, stop making random shit up" **[CHAT]** |
| 08-01 | ↺ The tags-first *implementation* rejected — informing is not gating | "ITS NT SUPPOSED TO BE FUCKING TAG REACHABLE ffs.. tags are supposed to INFORM/weight the chunks" **[CHAT]** |
| 08-02 | Gold-blindness: the designing agent must not see the questions or gold | "you should not have the questions/gold available to you, there is 0% good that can come out of taht" **[CHAT]** |
| 08-02 | This canon audit ordered | "i fucking demand you filter through every fucking memory and chatlog you have and find out everything I HAVE SAID, THOROUGHLY" **[CHAT]** |
| 08-03 | Desktop transcripts copied over so the two machines' history could be merged | "Copy this machine's Claude Code history for the GRAG-Job / exjobbet thesis project so my laptop session can mine it. Do not extract or summarise anything — raw copy only." **[CHAT]** |

---

# PART IV — NEVER BUILT, NEVER ANSWERED

Things he specified or asked for that have **no implementation and no recorded answer**.
Each carries his quote and the evidence.

## A. Specified in detail, designed, never built

**A1 — The aggregation path.** 30+ of the gold-100 questions come back classified `aggregate`; the code logs the classification and returns top-k chunks anyway.
> "but, doesnt the graph give actual relational connections to things like this, i mean, if the 'name' example you had, why wouldnt if just find all of those names? i dont get it" — **[DOC] 06-28 [t33]**

Designed in full (structural scope → semantic filter → full recall, no cap → group-by chunk attribute → count/max → directory join) across 06-28 §3.1 and 07-01 §11.7. Never written. Measurable in the results: `exact_match` is **0.000 across all three arms**. The 06-28 doc calls it *"the biggest design gap in pass 1"* and says it is *"where the artefact's relational-graph advantage over flat-vector retrieval shows clearest"*. **The one capability that would differentiate a graph from a vector store was designed, scoped, pseudocoded, and never implemented.**

**A2 — The relationships / hub-node layer.**
> "yeah i really think this should be nodes or edges so to speak etc, half the strength of of a graph is beeing able to route/search based on relationships instead of structures" — **[CHAT] 06-30**

Traversable containment + adjacency from the materialized path, hub nodes for mid-selectivity shared scalars, two disciplines (reference-never-copy, weighted-and-steep). Listed as needing sign-off on 07-01, absent from the 07-12 built inventory. He then asked for it again on 07-20, 07-28, 07-29 and 08-02 without either party recognising it had already been specified.

**A3 — Pass 2 in its entirety: the exponential curve and per-facet channels.**
> "cant we just do the evaluation-curve for the ranking of those "exponential", we dont have to decide the actual angle now, but kinda meaning "exact = max" on that curve, ish..?" — **[CHAT] 06-30**

Shape decided, angle deliberately left open as a sweep parameter. It was the *diagnosed fix* for the precision failure he condemned. 07-12 records: *"Pass-2 pipeline code has not been built."* Still true.

**A4 — Centrality.** His own idea, deferred in every single pass.
> "perhaps we can do that, but based on each facet! giving a relational value of the tag to its siblings based on each facet!?" — **[DOC] 06-11**

Deferred 06-11 (unblessed), 06-25 (open), 06-28 (deferred), 07-01 (inherited), 07-12 (unbuilt). The chunk→tag edge reserved for it carries nothing. It is the one facet measurement the research catalog calls phrase-robust.

**A5 — Chunk attribute extraction.** Only `kind` and `product` are materialized (the latter read off the file path). Person, org and date attributes were never extracted, so `date_range` is emitted by the interpreter on **every query**, validated, and thrown away; there is no structural join for "PRs by Anna"; and A1's group-by keys have nowhere to come from.

**A6 — The fuzzy-embedding pre-pass.** His idea at 06-28 [t24]; the blocking question ("is fuzzy edit-distance or embedding closeness?") answered by him on 07-01 — *"i mean by fuzzy i actually mean embedded"* — and then nothing was built.

**A7 — The build-time validation strategy.** Approved 06-09 (tags as code assertions, weights as invariants, error-analysis-by-reading first, "~30 catches a bug, 250–500 measures a rate"). No validation program of this kind ever appears.

**A8 — The gold-blindness mechanism.**
> "can we make sure "you" never see them? that you only get the variable/pointer to it?" — **[CHAT] 08-02**

Asked one day before this record ends. No implementation recorded.

## B. The falsifiers — three cheap tests, each gating a layer, none run

- **The ~30-phrase orthogonality probe** (06-25, 06-28): does the embedding move more for the facet than for incidental rewording, and do the facet-concepts separate at all?
- **The per-dial divergence check** (07-01): a handful of prompts, per-dial rewrites embedded, do the retrieved tag sets diverge?
- **The channel-blend reorder test** (07-01), whose stated consequence is the reason it matters: *"If nothing moves, every facet design here collapses to topic retrieval — and that finding matters in itself."*

The research catalog is candid that none of this is settled science: *"No benchmark evaluates any of this on short context-free phrase-tags into a small facet set; the behavior on a real tag corpus is an experiment, not a literature fact."* The experiment was designed three times and never run.

## C. Constants that no artifact ever derives

| Constant | Status |
|---|---|
| `α = 0.25` (coverage bonus) | Directional rationale only. Never swept. Load-bearing on 230k+ edges. Measured to work counterintuitively: mean `w_chunk` is *lower* on `w_facet=1.0` edges than on 0.7–0.8 edges. |
| `MULTI_FACET_THRESHOLD = 0.50` | No rationale at all. Consequence: 85% of tags are multi-facet — which is also the evidence for the orthogonality risk that threatens the whole facet layer. |
| `CAP_TOKENS = 3000` | The best-justified constant in the repo, explicitly *"a calibration seed, not a verdict"*, with a named sweep. **The sweep was never run**, including after the tagger and chunks existed. |
| `POOL_FETCH`, the 64-chunk limit, `K_LEVELS` | "also, arbitrarily decided hard limits, like the 64 chunk limit, i bet there is way more than 1 of these dumb limits lying around not beeing seen" — **[CHAT] 08-02**. Not enumerated since. |

## D. Adopted then silently un-adopted — no reversal recorded anywhere

- **The SQL-agent baseline.** 05-25: Lucene is dropped, SQL-agent is the comparison, a memory file is written, both handoffs instruct the next agent accordingly. By 06-18 the harness is lucene + vector + artefact and `baselines/sql_agent.py` is listed as dead cruft. **No document records the reversal.**
- **The HERB anchor metric.** *"no, i am saying we do both."* (06-18) → a 45-line stub of six `...` bodies → deleted on 06-28 inside a commit titled `feat: update graphify-out (533 files)`. The reason is a real user decision (*"this is ONLY RAGAS"*), but the consequence — **no number this project reports is comparable to HERB's published leaderboard** — is weighed against the decision nowhere.
- **The controlled canonical vocabulary.** Deleted 05-13 in a commit titled "Rework HERB chunking and tagging frames", with one substituted table cell as its only prose trace. Its decision-log entries D2/D3/D4 still read `Status: Active`. **No user statement about it exists in any source.**
- **`(:File)-[:TAGGED]->(:Tag)` and `weight_global`.** The deterministic file rollup vanished. Not discussed in any doc, comment or commit.
- **Bonnier / the second dataset.** Deferred by him on 06-14, never resumed. It was the only planned test of whether the design generalizes beyond HERB, and the sole stated rationale for the Mistral tagger choice.

## E. Asked and never answered

| Question | Date | Status |
|---|---|---|
| "yeah but do we NEED multihop if we do the graph correctly?" / "wont it emulate/do multihop natively purely by design?" | **[CHAT] 07-15** | Never answered. No mechanism was built to test it. |
| "honestly, cant we create a dq-RL-test for this where we finally find the actually good solution?" | **[CHAT] 07-20** | No implementation, no recorded ruling. He redirected the same day to testing artefact variants instead. |
| "have you decided this? \"which is what a tag layer is supposed to be\" ? … hapax would let them matter more because of vectorisation?" | **[CHAT] 08-02** | Open. No answer recorded. |
| "is there an architectural difference between them?" (det vs haiku legs) | **[CHAT] 07-29** | Asked while trying to settle which arm is the baseline — *"all agents keep fucking reverting to the \"det\" arm, is there something in some documents that says so? because this is starting to piss me off"*. Never settled in writing. |
| Why `qt.scopeWeight` was introduced into the v1 scorer | shipped 05-15→05-28 | Named as a factor to remove; **no source in any of the three records explains why it exists**. |
| Why the built tagger is `z-ai/glm-5.1` when the documented choice was Mistral Large | 06-28 | Undocumented. Three tagger-model decisions, each superseding the last; the final one has no rationale anywhere. |
| Whether rank-aware metrics should replace set-based `recall_id`/`precision_id` | **[CHAT] 08-02** | He pasted the agent report saying the eval `set()`s the retrieved ids and therefore discards the ordering his changes were changing. He did not rule. |
| The interpreter's "faceting" rename, so it stops colliding with tag-facets | 06-25 | Requested; never done; `facet_phrases` still uses the word. |
| Judge calibration against a human-labelled subset | 06-18 | Recommended, never locked, never run. The `MetricScore` record carries a `human_label` slot that is always empty. **Every judged number this project reports is uncalibrated.** |
| H1–H4 from 06-23, notably lucene/vector `documents.feedback` parity | 06-23 | Never resolved. The doc itself notes it "muddies 'sparse vs dense' on that kind". |

## F. Open at the moment this record ends (2026-08-03)

- The 08-02 diagnosis of the current tag layer — tag path finds 3 chunks/question out of a ~418-chunk pool, zero widening levels ever open, `GUIDE_TAU = 0.0` makes every tag's guide value exactly 1, `HERB_TAG_FIRST` bundles a walk restructure with a gate — was pasted by him and answered with *"so, lets fix that and try it"* **[CHAT] 08-02**. Whether it was fixed is not in this record.
- The evidence-cap / matched-token-budget work existed only inside the thread he ordered fully reverted on 07-28, and did not survive the revert.
- Cluster-K itself — the mechanism defined on 07-21 and respecified on 07-31 — has never been on the load-bearing path in any shipped configuration.

---

# HOW TO USE THIS FILE

1. **A quote is evidence. A summary is not.** If you are about to state what the user wants, find the quote first. If there is no quote, say there is no quote.
2. **`[CHAT]` outranks `[DOC]` outranks anything written by an agent.** Text in this repo that carries none of those tags is not canon, however confident it sounds — including anything in `docs/state/`, `MEMORY.md`, `DESIGN.md`, or `CLAUDE.md`.
3. **Where two quotes conflict, both stand.** Bring the conflict to him. Do not pick.
4. **`docs/canon/raw/` is read-only.** Re-derive with `python tools/canon_extract.py`.
5. **Do not open** `v3/data/questions.jsonl`, `gold100.jsonl`, `heldout100.jsonl`, `10smoke.jsonl` while doing design work — see §8.
