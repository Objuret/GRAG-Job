---
name: facet-semantic-framework
description: "Linguistic/NLP grounding for the v2 facets — SFL metafunctions, thematic roles, TAM, appraisal — what dimensions are needed to decompose chunk meaning"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 394998a2-4808-4743-afe8-a2540eea4232
---

**Research grounding (2026-05-30) for defining the v2 facets as real semantic dimensions, not token extractors. The v1 facets (topic, entities, activity, temporal, evidence) capture only the IDEATIONAL strand and degraded into shallow extraction; established theory says meaning has more strands.**

## The four load-bearing frameworks

1. **SFL metafunctions (Halliday)** — every clause carries THREE strands of meaning simultaneously, equal status:
   - **ideational** = experience: the process (what's happening) + participants + circumstances (when/where/how).
   - **interpersonal** = stance/relationship: mood, modality, evaluation — the speaker's attitude.
   - **textual** = discourse role: theme/rheme, cohesion, how it functions in the larger text.
   → v1 facets are almost entirely ideational. Interpersonal (stance) and textual (discourse role) are MISSING.

2. **Frame semantics + thematic/semantic roles (Fillmore, Jackendoff)** — meaning = a frame (situation type) with participants in ROLES (agent/patient/recipient/instrument) and circumstances. The role is the meaning; the entity's name/id is not. → "entities" should capture participant ROLES, not raw identifiers.

3. **TAM — tense / aspect / modality** — temporal meaning decomposes into: tense (past/present/future = then/now/later), aspect (perfective/ongoing/habitual = completed/continuing/recurring, spans), modality (epistemic certainty, deontic obligation, volitional). → This IS the user's "temporal was never about dates." Dates = structure; tense+aspect+modality = the temporal facet.

4. **Appraisal theory (Martin & White)** — evaluation/stance = attitude (affect/judgement/appreciation) + engagement (sourcing/whose voice/evidentiality) + graduation (intensity). → grounds "evidence" as evidentiality/sourcing (not URLs), and supplies the missing stance dimension.

## CONVERGENCE across traditions (de-anchored — do NOT lead with SFL or the v1 5)

Six independent lineages converge on the same dimensional structure: Ranganathan **PMEST** (Personality/Matter/Energy/Space/Time), **neo-Davidsonian/AMR** event semantics (event + role-bound participants + time/location/manner), **5W1H** (who/what/when/where/why/how), **SFL** metafunctions, **TAM** (tense/aspect/modality), **Appraisal + evidentiality** (attitude/graduation/engagement vs epistemic certainty), **RST/speech-acts** (rhetorical function), register/genre theory.

De-duplicated convergent model — THREE tiers:
- **Tier 1 Propositional/ideational (the situation):** aboutness/topic (frame/domain); process (what happens); participants + their ROLES (agent/patient/recipient — not identifiers); circumstance = time(full TAM) + space + manner + cause/purpose.
- **Tier 2 Interpersonal (stance toward the situation):** evaluation/attitude (affect/judgement/appreciation); modality (certainty/obligation/possibility); evidentiality (sourcing/grounding, distinct from certainty).
- **Tier 3 Pragmatic/textual (what the span DOES):** communicative/rhetorical function (question/assertion/decision/request/problem/resolution — speech acts, RST, dialogue acts); genre/register.

Meaning = a SITUATION (frame+process+roles+circumstance), wrapped in a STANCE (evaluation+modality+sourcing), serving a COMMUNICATIVE FUNCTION, classified by aboutness + genre. Temporal = TAM inside circumstance (then/now/later, ongoing/done, planned) NOT dates. Participant = role NOT token. Evidence = sourcing NOT links.

Sources add: PMEST (en.wikipedia.org/wiki/Faceted_classification), AMR (en.wikipedia.org/wiki/Abstract_Meaning_Representation), neo-Davidsonian (Landman notes), 5W1H-SRL (arxiv 2505.14804), RST (en.wikipedia.org/wiki/Rhetorical_structure_theory), evidentiality vs epistemic modality (Kroeger ch.17).

## ORGANIZING PRINCIPLE (user, 2026-05-30): completeness across the TOTALITY + prompt/chunk symmetry

The dimensions are NOT all "facets." The real principle: the convergent dimensional space must be represented across the **totality of the artefact**, each dimension carried by whichever mechanism fits — none dropped. Mechanisms (carrier list updated 2026-06-12 — description + grounding vectors are DEAD, [[v2-graph-spine]]):
- **structure / hard fields** — literal facts (time=timestamp, space, participant ids as chunk attributes). exact, queryable.
- **facets on tags** — the genuinely semantic dims (stance, communicative function, process, aboutness), carried on the tags. **CONCEPT REFRAMED 2026-06-14 (user, hammered home):** a facet is NOT a bucket/category/container a tag belongs to — it is a **relevance coordinate / the character of a tag**, and the facets are **parallel comparison channels**. Retrieval = the interpreter decomposes the prompt per facet, then matches SAME-FACET, like-for-like: prompt.topic↔tag.topic, prompt.stance↔tag.stance, each channel a distance, summed weighted by prompt emphasis. The v1 tag CONCEPT (tags have per-facet relevance, one edge carrying the whole facet vector) was SOUND; only the model-emitted weights were the rot. NOTE: this SUPERSEDES the 2026-06-13 "per-facet phrase lists" carrier line — that is REOPENED; how a tag gets its per-facet content at build time is now an OPEN question. Every emitted tag is still its own per-chunk Tag node ([[v2-graph-spine]], unique, no shared vocabulary). See state doc 2026-06-14-v2-facets-as-relevance-channels.
- **phrase-tag embeddings** — bridge between prompt-space and corpus-space.
- **prompt interpretation** — the query side.

Two invariants:
1. **Completeness:** every dimension is represented somewhere in (structure ∪ tags/facets ∪ interpreter).
2. **Symmetry:** whatever is used to RETRIEVE must be mirrored on the prompt side — chunk-representation and prompt-interpretation decompose along the SAME axes, or they can't match. (e.g. communicative-function only useful if the interpreter also extracts "user wants a decision"; TAM only useful if interpreter reads "what did we decide LAST quarter" as past/retrospective.)

So the facet question becomes an ALLOCATION problem: for each convergent dimension → decide which mechanism(s) carry it {hard field | tag-facet | description/embedding | grounding | interpreter}, AND confirm the interpreter extracts the matching axis. "Facets" = the subset best carried as weighted tag-edges.

## DIMENSION → MECHANISM ALLOCATION (drafted 2026-05-30)

Each convergent dimension placed across mechanisms, with the prompt-side (interpreter) axis and match type (EXACT=structured query vs SEMANTIC=graded/grounded).

| Dimension | Primary carrier | Also | Interpreter extracts | Match |
|---|---|---|---|---|
| **Aboutness/topic** | tag-facet (topic) | phrase-tag embeddings | prompt topic | SEMANTIC |
| **Process** (what happens) | tag-facet (process/activity) | — | the action sought | SEMANTIC |
| **Participants + roles** | STRUCTURE (id attributes on chunks + raw directories via references; NO entity nodes — [[v2-graph-spine]]) | — | named/role refs ("PRs by X", "QA lead said") | EXACT |
| **Time (TAM)** | DUAL: STRUCTURE (literal date=hard field) + tag-facet (tense/aspect/modality stance) | — | both: "last quarter"→past+date-range; "upcoming"→planned | EXACT (date) + SEMANTIC (stance) |
| **Space/location** | STRUCTURE (hard field) | — | location constraints | EXACT |
| **Manner** | phrase tags (carrier OPEN; was description — dead) | — | (rare in prompts) | SEMANTIC |
| **Cause/purpose** | phrase tags (carrier OPEN; was description — dead) | possible relation edge | "why" intents | SEMANTIC |
| **Evaluation/attitude** (appraisal) | tag-facet (stance) | — | "complaints/concerns about X", polarity | SEMANTIC |
| **Modality** (certainty/obligation) | tag-facet (stance, w/ attitude) | — | "what must we" (deontic) / "might" (epistemic) | SEMANTIC |
| **Evidentiality/sourcing** | STRUCTURE (provenance = the reference triple) | minor facet (hedging strength) | "where documented / show evidence" | EXACT (provenance) |
| **Communicative/rhetorical function** | tag-facet (function) — HIGH value | — | ESSENTIAL: "find the decision/problem/question" | SEMANTIC |
| **Genre/register** | STRUCTURE (hard field: kind/section, from source) | — | "in slack" / "in the PRs" | EXACT |

### Resulting v2 facet set (the SMALL semantic-tag subset)
Facets = only the genuinely fuzzy-semantic dims worth graded tag-edges + grounding:
**topic, process, stance (attitude+modality), communicative-function** — (+ TAM-stance as the meaning-half of temporal). ~4–5 facets.

Everything else resolves cleanly:
- **STRUCTURE / hard fields (EXACT):** participants+roles (id attributes + raw directories), literal time, space, genre/kind, evidentiality/provenance. ← these are exactly the v1 "junk facets" (entities/temporal/evidence) correctly relocated to structure.
- **phrase-tag embeddings (SEMANTIC):** the prompt↔corpus bridge; manner and cause/purpose ride in the phrases (the description that used to hold them is dead).
- **interpreter:** must extract every axis used to retrieve (symmetry) — esp. communicative-function and TAM-stance.

This RESOLVES the facet-redesign question: v1's pollution was 3 fact-dimensions (entities/temporal/evidence) mis-assigned to tag-facets; the allocation puts facts in structure and keeps only the 4–5 truly-semantic facets.

## PER-FACET EXTRACTION SPECS (drafted 2026-05-31; STALE 2026-06-12 — examples show bare labels, but tags are now per-chunk contextual PHRASES, and the per-facet carriers/vocabularies are being redecided in Bucket 2/3; the model emits NO numbers; keep only as the dimensional intent)

The 4–5 v2 facets, each with: what it captures · tagger emits · MUST-NOT (now structure) · interpreter mirror (symmetry).

1. **topic** (aboutness / frame-domain)
   - captures: the subject/domain the chunk is *about*, at concept level.
   - emits: concise conceptual noun-phrase tags (e.g. `api_rate_limiting`, `billing_migration`, `mobile_performance`); external named tech-as-concept OK (`kubernetes`, `salesforce`).
   - MUST NOT: employee/customer ids, dates, URLs, PR numbers (→ structure).
   - interpreter: extract the topic(s) asked about → ground vs corpus topic tags.

2. **process** (what happens / transitivity)
   - captures: the action/event/process — the doing, distinct from its actors.
   - emits: action tags (`debugging`, `code_review`, `incident_response`, `planning`, `decision_making`).
   - MUST NOT: the actors (→ structure), the sentiment (→ stance).
   - interpreter: extract the action sought ("how was X fixed", "who reviewed Y"→review).

3. **stance** (attitude + modality — interpersonal)
   - captures: evaluative/modal posture — affect/judgement/appreciation + certainty/obligation/possibility.
   - emits: graded stance tags on (a) attitude (`critical`, `concerned`, `blocked`, `approving`), (b) modality (`proposed`, `required`, `uncertain`, `committed`).
   - MUST NOT: the factual content / topic.
   - interpreter: "concerns/complaints about X"→negative; "what must we"→deontic; "what's blocked"→negative+obligation.

4. **communicative-function** (rhetorical / speech-act — textual)
   - captures: what the span DOES in discourse.
   - emits: function-type from a controlled set: `question | problem | decision | resolution | request | proposal | announcement | status | explanation`.
   - MUST NOT: topic/content.
   - interpreter: ESSENTIAL — "find the decision"→decision; "what problems"→problem; "what was asked"→question. Highest retrieval leverage.

5. **temporal-stance (TAM)** — meaning-half of temporal (literal date = structure)
   - captures: tense (retrospective/current/prospective), aspect (one-off/ongoing/recurring/completed), temporal-modality (planned/deadline/overdue/urgent).
   - emits: TAM tags (`retrospective`, `ongoing`, `planned`, `deadline`, `recurring`). NEVER dates.
   - interpreter: "last quarter"→past + date-range filter on the STRUCTURAL timestamp; "upcoming/next"→prospective/planned; "still"→ongoing.

Controlled-vocab note: communicative-function and TAM are best as small CLOSED sets (enums); topic/process/stance are open but concept-only. This is the spec the v2 tagger prompt encodes per facet — the missing spec that caused v1 degradation.

## How to apply
- The facet set is settled: **topic, process, stance, communicative-function, time** (five — see the resulting-set section above). Carriers are OPEN again (the 06-13 "per-facet phrase lists" was superseded by the 06-14 relevance-channels reframe above): the live question is where/how a tag gets its per-facet content at build time so prompt.facetX can be matched to tag.facetX. The model emits no numbers; per-facet relevance is measured (distance), not emitted.
- Use these frameworks as the backbone when writing each facet's spec into the tagger contract — the explicit semantic intent v1 never had.

Sources: SFL/metafunctions (Halliday; en.wikipedia.org/wiki/Metafunction), thematic roles (en.wikipedia.org/wiki/Thematic_relation; Jurafsky SLP3 ch.21 SRL), TAM (en.wikipedia.org/wiki/Tense–aspect–mood), Appraisal (Martin & White 2005; grammatics.com/appraisal).

## Related
- [[retag-facet-analysis]] — why v1 facets degraded into junk; this is the fix
- [[v2-build-pipeline]] — re-tag on clean structure
- [[design-hard-fields-before-tagging]] — facts→structure so facets carry meaning
