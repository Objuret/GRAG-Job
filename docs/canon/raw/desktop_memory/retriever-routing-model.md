---
name: retriever-routing-model
description: v2 retrieval = weighted activation propagation through the File-Chunk-Tag-Facet line; combinator = prompt-conditioned weighted dot product; NO hard filters
metadata: 
  node_type: memory
  type: project
  originSessionId: 9530d37d-60c5-471c-aef3-bfc28bf292b4
---

**The v2 retrieval ("routing") model, converged with the user 2026-05-31.** Builds on [[graph-is-references-not-copies]] and the facet design in [[facet-semantic-framework]].

## The graph it routes over — REVISED (2026-06-11/12)
The original 4-layer topology is dead in two places: shared Tag concept nodes + Facet nodes were replaced by **per-chunk phrase-tag nodes** (phrase IS the node, embedding proximity links chunks — 06-11 session), and the **chunk→file relevance weight is DEAD** (06-12, [[v2-graph-spine]]: containment carries no number; v1's filler-demotion job is solved by coherence chunking, and "typicality" buries the rare relevant aside). Spine: `Source → File → Chunk → Tag(phrase)`, hard fields as chunk attributes. Facet values are carried per-facet (carriers OPEN — Bucket 2).

## What routing IS
NOT filter-route, NOT pure embedding search, NOT clustering — it's **weighted propagation of query activation through the layers to chunks**:
1. interpreted prompt → entry points: embed + extract pTags; match corpus tags by embedding (the "cluster-search"); also activate facets by the prompt's facet character.
2. activation flows down weighted edges (facet→tags→chunks; no chunk→file modulation — that weight is dead), accumulating at chunks.
3. rank by accumulated weight; **cap** takes top-N.
Subsumes the candidates: embedding search = ENTRY, filters = (soft) prune, facet-clusters = SCOPE, weighted line = the RANKING signal.
**Two altitudes:** query can enter LOW (names a concept → its tags → chunks) or HIGH (facet-character only, no tag named → enters at facet → flows to all related tags → chunks). The facet layer is what enables abstract/thematic queries.

## The combinator (CONCEPT only — exact math OPEN, Bucket 3; the facet-weight-vector framing predates per-chunk phrase tags and may change with the carriers)
`score = promptFacetRelevance · facetWeights` — a **prompt-conditioned weighted dot product** of the prompt's per-facet relevance vector against the item's facet-weight vector. Applied TWICE: across facets to score a tag, then across tags to score a chunk (same rule, two altitudes).
- Cross-facet **accumulation, not max**: strong across several *relevant* facets beats max on one (user's example: tagB[func .8, temporal .9]=1.7 beats tagA[func 1.0, temporal .2]=1.2 when both facets relevant).
- Relevance is a **continuous coefficient**, not a gate: a weakly/irrelevant facet gets ~0.0–0.1 coefficient and self-attenuates. No separate "activated set" — the factor IS the gate, smoothly.
- **Normalization (open detail):** normalize the PROMPT vector (emphasis sums to 1) so "how much the prompt cares" is honest; keep TAG magnitude but BOUNDED so intensity survives without a few loud tags dominating. (cosine = direction only; dot = direction×intensity; chosen middle = normalized prompt · bounded-magnitude tag.)
- Rejected: multiplication (too brutal), raw unweighted add (dilutes — rewards vague-everywhere over exactly-right).

## NO HARD FILTERS (decided, strong stance)
The user wants NO hard filters anywhere. A hard filter crushes signal (same brutality as multiplication, taken to 0/1) and is especially dangerous because it gates on a JUDGMENT that can be wrong — a true decision mis-tagged `status` would be silently, totally excluded ([[no-silent-fallbacks]]). 
- **"Mandatory" is achieved by weight concentration, not a gate:** intense prompt focus → facet-relevance ~1.0 on that facet, ~0 elsewhere → non-matches sink in rank and fall out at the CAP. Nothing removed, only ranked low → a borderline-classified match with strong other signal can still climb back.
- The **CAP does the cutting**, on the ranked continuum — not a predicate mid-stream. So "Filter" in Match→Filter→Rank→Cap means at most pruning literally-zero candidates, never gating on uncertain judgments.
- Resolves facets-as-filter-vs-ordering: **always ordering, never filtering.**
- Only acceptable true-exclusion: an EXPLICIT, opt-in, user-set scope on a certain structural fact ("only 2026") — never an interpreter-INFERRED mandatory. Even that is soft by default.

## Hard fields fold in as a THIRD signal — soft boosts, not filters (decided 2026-05-31)
The materialized structural hard fields (kind, product, date/time, participant entities, provenance) participate in routing as **soft boosts/priors in the SAME weighted combination** — never as gates (consistent with NO HARD FILTERS). A hard-field match is binary by nature (chunk IS slack or isn't) but enters as a weighted boost: "in slack" lifts kind=slack chunks, doesn't delete the rest; a highly-relevant non-match can still surface.

Final chunk score = **weighted sum of (semantic propagation [facet·tag dot products]) + (structural hard-field match boosts)**. The interpreter produces BOTH from the prompt: a facet-relevance vector AND structural-constraint weights.

**Self-balancing by the same coefficient mechanism:**
- "Show me PR #381" → semantic ~0, structural dominates (lookup; the hard field IS the answer).
- "What were people worried about" → structural ~0, semantic dominates.
- "What did we decide in slack last quarter" → mixed: function+temporal facets blend with kind=slack + date-range boosts. Nothing excluded; cap cuts.
Same trick as intense-facet-focus: a purely-structural prompt makes structural terms dominate without a filter.

**Hard fields' second job (non-retrieval):** traceability + exact/aggregation queries ("how many PRs merged in Q2", "everything authored by X"). Structured-query use lives alongside the soft-boost retrieval use; both draw on the same materialized fields.

## Gate-vs-boost resolved by PATH, not UI (2026-06-01)
The "can it be both gate AND boost" question is resolved. UI scope-controls (dropdowns/toggles for "slack only"/"2026 only") were considered and **REJECTED as out-of-scope** (building a UI is a detour from the artefact). The "both" survives, split by **path** not UI:
- **Retrieval (ranking) path → all boosts**, never gates (consistent with NO HARD FILTERS).
- **Structured-query / aggregation path → exact** — a real gate, but only where a clean boolean genuinely exists ("count PRs in Q2"). This isn't retrieval ranking; it's a SQL-like query over the materialized fields ([[design-hard-fields-before-tagging]]'s second job).
Why a gate is fine ONLY there: a gate must be (a) explicitly asserted, not interpreter-inferred, AND (b) exact at the altitude it filters. `kind=slack` is clean per-chunk; a *date* on a chunk is a span (straddling thread) → exact date-exclusion belongs at the record/aggregation altitude, not chunk ranking.

## Prompt-side hard-field matching — deterministic pre-pass (REVISED 2026-06-12)
Before the LLM interpreter runs, match the raw prompt against the hard fields' **actual values, read at query time through the field connection into raw** (chunk attributes for kind/labels/ids; metadata directories like employee.json via references for names). **NO pre-embedded value vocabulary, no value inventory artifact** — that was rejected as copies-not-references + GDPR surface ([[v2-graph-spine]], [[ai-cost-boundary]]: never embed already-exact data).
- **exact literal match** (+ case/spacing normalization) → strong structural boost; matched literals stripped before the interpreter (no topic double-count).
- **fuzzy = DECIDED (2026-06-12):** no blanket string-fuzzy, no embedded values, no corpus vocab in the interpreter ([[ai-cost-boundary]]). Interpreter flags token type + wanted/excluded from language alone → scoped string-distance lookup against that ONE directory on a flagged miss (read from raw via references) → described-not-named ("the pitch tool") falls to the semantic layer (phrase tags carry names in context). HERB's twin products (ContentForce/ContextForce etc.) are why blanket fuzzy is dangerous; verified vs all 1,514 questions (perfectly spelled, people by role).
- **Ambiguity:** all candidates boosted; confidence sets boost (exact-unique > exact-ambiguous split > distance/interpreter-resolved). Jump only exact-unique.
- **Multiple hits in one prompt = boosts only (DECIDED 2026-06-12):** each hit boosts, the combination wins by addition (a chunk matching all hits collects all boosts); no multi-anchor jump, no subjective "which did they mean" selection. Interpreter marks each matched literal wanted-vs-EXCLUDED ("apart from PitchForce…"); excluded = no boost, never removal.

## Anchored retrieval — the third mode + agentic-but-lean control flow (2026-06-01; anchor wording revised 06-12)
An exact match that resolves to a **single anchor** (a file, a path subtree, an id — NOT an entity node; those don't exist) doesn't just boost — it triggers a navigational **jump**: scope to that anchor's path-prefix/attribute cohort → run the semantic chunksearch **inside it first** → if thin, **WIDEN** (loud, automatic) to full propagation. Three retrieval modes on a spectrum:
- **pure structured query** (exact only, no semantics) — "count PRs in Q2"
- **anchored retrieval** (exact anchor narrows, semantic ranks within) — "what did the PitchForce slack say about X"
- **pure fuzzy retrieval** (semantics; hard fields as boosts) — "what were people worried about"

"Check there first" is SAFE because it's a **first pass with a loud widen, NOT a permanent gate** — you can always widen, so nothing is silently deleted ([[no-silent-fallbacks]]). Control flow stays **LEAN, explicitly NOT a "factory"** (user, 2026-06-01): ONE deterministic branch (exact single-anchor → jump) + ONE loud widen rule, **reusing the existing engine** (anchor lookup = traversal over edges already built; search-within = the same combinator on a narrowed candidate set). NOT an LLM agent loop deciding *whether* to jump. Guards: (1) only exact single-anchor matches jump — fuzzy never jumps; (2) the widen is loud + automatic when the anchored pass comes back thin.

## Symmetry — machinery DEAD (2026-06-11)
The requirement stands conceptually (prompt-side and corpus-side must decompose along comparable axes or they can't be matched), but the **embedding-axis-projection machinery is DEAD** — assistant invention, never the user's ("where the fuck did all of this even come from"). The replacement mechanism is open with the facet carriers; the model emits NO numbers on either side.

## Still open
- combinator exact math (accumulation form, bounds) — Bucket 3.
- the chain-bake: index-time precompute vs query-time (weights are facts; query supplies the prompt side).
- fuzzy hard-field matching: string-similarity at query time vs none (see pre-pass section above).
- facet carriers + per-facet weight mechanisms (Bucket 2) — gates most of the above.
(chunk→file factor REMOVED — the weight is dead, [[v2-graph-spine]]. Embedder is chosen: nvidia/llama-3.2-nv-embedqa-1b-v2.)

## Related
- [[facet-semantic-framework]] — the dimensions/facets + embedding-axis magnitude
- [[graph-is-references-not-copies]] — retriever queries facts, never synthesizes weights
- [[v2-build-pipeline]] — the index this routes over
