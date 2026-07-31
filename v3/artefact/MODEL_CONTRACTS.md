# v2 model contracts — structured I/O at every model touchpoint

**Working draft — approvals happen per-call, in conversation, schemas shown inline**
(the doc itself is never the approval). §5 tracks the status of every judgment call
beyond decided design. Everything not listed there is a restatement of decided design
(`v2_artefact_rebuild_design.md`, cited per section).

**Status (2026-06-14): the tagger OUTPUT schema needs RE-VALIDATION.** It was verbally
approved 2026-06-13 (calls a/d/f) but that predates the **2026-06-14 facet reframe**: a
facet is the *relevance coordinate / character of a tag*, not a bucket; retrieval matches
**same-facet** (prompt.topic↔tag.topic). Call (a) "per-facet contextual-phrase lists" is
therefore **REOPENED** — how a tag gets its per-facet content at build time is an open
question (see state doc 2026-06-14-v2-facets-as-relevance-channels and design §13 STATUS).
Likely-still-good: (d) bounded enum arrays, (f) source-language phrases (English under the
**HERB-only** scope, Bonnier deferred), per-chunk-unique Tag nodes (design §7). Confirm
before encoding.

## 0. The touchpoints and the inherited invariants

Per the cost boundary, a model touches an item in **exactly three places** — everything
else in the pipeline is deterministic and free:

| Touchpoint | When | Per | Model |
|---|---|---|---|
| **Tagger** | build | chunk | `mistralai/mistral-large-3-675b-instruct-2512` (NIM) |
| **Interpreter** | query | prompt | same LLM (draft call — §5c) |
| **Embedder** | build + query | phrase tag / prompt phrase | `nvidia/llama-3.2-nv-embedqa-1b-v2` (NIM) |

The dead arms stay dead: no description carrier, no LLM-judge, no model-emitted numbers.

Invariants every contract inherits (all decided):

- **No numbers cross the model boundary, either direction.** Tag weights are *measured*
  downstream (mechanism open, §15 of the design doc); the prompt's facet-relevance
  vector is *derived* from the interpreter's categorical output, never emitted by it.
- **Stateless, temp 0, one call per unit** (§9.5). Same fixed system prompt every call —
  the only variable across runs is the prompt version. This is the precondition for all
  of §16's validation (golden tests, response cache keyed chunk-hash + prompt-version,
  small-sample reads).
- **Structured output is schema-enforced, fail loud.** Guided decoding
  (`response_format` json-schema / NIM `nvext` guided_json — pin the mechanism at the
  build-start connectivity run). A response that violates the schema **halts the run**;
  no parse-and-hope, no silent retry-degradation (transient 429/5xx retries via the
  shared limiter are fine).
- **One shared async rate limiter** (~38/min target) in front of every NIM call — LLM
  and embedder both (§11).
- **Vocab-free model contexts.** No corpus values, vocabularies, or inventories in any
  system prompt. Only the universal enums live there (§8, §14.7).

## 1. The tagger contract (build time)

One chat-completions call per chunk, temp 0. System prompt = the fixed contract (facet
specs + MUST-NOT rules + enums, identical every call). User message = the chunk
envelope, a pure function of chunk + graph (§9.5):

```
<provenance>  source name; file; materialized path; probe kind of this position
              (conversation / document / record-run)                            </provenance>
<context>     ancestor scalar fields read from raw via references — channel name,
              document type/title, PR title + state, transcript date-line. Nothing
              model-generated, nothing from sibling chunks. (§5e)               </context>
<content>     the resolved raw text, verbatim, source language, untranslated    </content>
```

Output schema (the §13.4/§13.5 facet set, carriers made concrete — §5a):

```json
{
  "topic":           ["contextual phrase", "..."],
  "process":         ["contextual phrase", "..."],
  "stance":          ["contextual phrase", "..."],
  "function":        ["decision", "..."],
  "temporal_stance": ["retrospective", "..."]
}
```

- **topic / process / stance** — open, concept-only, **contextual phrases** (the only
  thing the pipeline ever embeds): short (~≤12 words), names-in-context welcome
  ("rate limiting criticized during the PitchForce migration"), bare labels discouraged.
  `topic` ≥ 1; `process`/`stance` may be empty. Each phrase becomes a Tag carrying its
  facet, embedded as a passage (§3).
- **function / temporal_stance** — CLOSED enums, and therefore **chunk attributes, not
  tags, never embedded** (closed facet labels = attributes, decided 2026-06-12).
  `function` ∈ {question, problem, decision, resolution, request, proposal,
  announcement, status, explanation}, 1–3 values (an episode can hold a question *and*
  its resolution — §5d). `temporal_stance` ∈ {retrospective, ongoing, planned, deadline,
  recurring}, 0–2 values. NEVER dates.
- **MUST NOT appear anywhere** (these are facts → structure; the v1 pollution): ids
  (`eid_*`, `EMP_*`, `CUST-*`), dates/years, URLs, PR numbers, channel ids. The §16
  assertion list is exactly this: schema validity, enum membership, MUST-NOT regexes,
  topic non-empty, phrase-length bounds, no duplicate phrases — wired as promptfoo
  regressions, no model in the loop.
- **No weights, no description, no numbers** in the output — decided.
- Phrases are emitted **in the source language** (Swedish stays Swedish — the embedder
  is multilingual and SEB-verified; translation would be a mutation — §5f).

## 2. The interpreter contract (query time)

One call per prompt, temp 0, **no tools** (decided 2026-06-12): prompt in, flags out;
deterministic code runs the exact pre-pass before it and the scoped distance-lookup
after it. Symmetry (§13.3) is what this contract exists for: it must extract every axis
retrieval uses, and nothing else.

Input: the user prompt, the current date (so "last quarter" can resolve — §5i), and the
pre-pass results as **marked spans, not stripped** (§5b — revises §14.7's "stripped"
wording): each span the exact pre-pass matched, with its kind. Marked spans must not be
re-emitted as facet phrases (no topic double-count) but MUST receive a polarity —
otherwise "apart from PitchForce" with an exact-matched "PitchForce" would silently
boost the excluded thing.

Output schema:

```json
{
  "literals": [
    {"token": "PitchForce", "kind": "product", "polarity": "excluded", "marked": true},
    {"token": "Anna",       "kind": "person",  "polarity": "wanted",   "marked": false}
  ],
  "facets": {
    "topic":           ["phrase", "..."],
    "process":         ["phrase", "..."],
    "stance":          ["phrase", "..."],
    "function":        ["decision"],
    "temporal_stance": ["retrospective"]
  },
  "date_range": {"from": "2026-01-01", "to": "2026-03-31"},
  "answer_shape": "content"
}
```

- **literals** — kind ∈ the universal enum {person, org, product}; polarity ∈ {wanted,
  excluded} (excluded = no boost, never removal). Unmarked flagged tokens trigger the
  scoped distance-lookup via the kind→directory join in the mapping key (§8); a kind
  the dataset's key doesn't declare has no landing spot → semantic layer, logged loudly.
- **facets** — the prompt-side mirror of §1, same enums, same phrase rules. The
  combinator's facet-relevance vector is derived deterministically from this block
  (presence/emphasis), together with the open combinator math — the model emits no
  coefficients.
- **date_range** — nullable; literal time extracted for the *structural* timestamp
  filter at the record/aggregation altitude (§14.6); TAM meaning rides in
  `temporal_stance`.
- **answer_shape** ∈ {content, aggregate} (§5h) — the second universal enum in the
  fixed contract: `aggregate` routes to the structured-query path ("count PRs in Q2"),
  `content` to retrieval ranking. The jump decision stays deterministic (exact-unique
  anchor — §14.8); the interpreter has no say in it.

## 3. The embedder contract

`nvidia/llama-3.2-nv-embedqa-1b-v2` on the NIM `/v1/embeddings` endpoint — an
**asymmetric** retrieval embedder; `input_type` is part of the contract:

| What | When | `input_type` |
|---|---|---|
| phrase tags (topic/process/stance) | build, after tagging | `passage` |
| interpreter facet phrases | query | `query` |

That table is exhaustive — **the pipeline embeds exactly one thing: phrase tags** (and
their prompt-side mirror). No field values, no raw chunks, no closed-enum labels, no
directory entries. The scoped typo lookup is string distance, not embedding.

- **Dimensions:** native 2048 (Matryoshka truncation available); take native — pin and
  verify against the live endpoint at the connectivity run (§5g), same place the
  guided-JSON mechanism is pinned.
- Vectors L2-normalized on store; cosine similarity. Batch tag-phrases per request up
  to the endpoint's input limit (verify same run), under the shared limiter.
- The paired reranker (`llama-3.2-nv-rerankqa-1b-v2`) exists on the same host but has
  **no place in the design** — nothing reranks raw chunks; listed only so its absence
  is a decision, not an oversight.

## 4. What is deliberately absent

- **No answerer/generation contract.** Thesis eval needs an answer-generation step
  (RAGAS arm), but it sits outside the artefact's index/retrieve design and is specced
  with the eval harness, not here.
- **No LLM-judge contract** — died with the description carrier (2026-06-11). Tag
  validation is code assertions; weight validation is invariants + gold-100 end-to-end.
- **No per-dataset prompt variants.** One tagger prompt, one interpreter prompt, for
  HERB and Bonnier alike; dataset meaning enters only through the mapping key and the
  chunk envelope's source-language content.

## 5. Sign-off checklist — the judgment calls beyond decided design

Decided design is restated above without asking; each call below is asked in
conversation with the schema shown inline, never approved via this doc:

| # | Status | Call | Position |
|---|---|---|---|
| a | **REOPENED 2026-06-14** | **Per-facet carriers** | the 06-13 "separate per-facet contextual-phrase lists" is superseded by the facet reframe (facets = relevance channels, same-facet matching). OPEN: how a tag gets its per-facet content at build time. Still standing: function/TAM = closed-enum chunk attributes; every tag = its own per-chunk node (§7) |
| b | open | **Marked spans, not stripped** | revises §14.7 wording: pre-pass matches passed to the interpreter as marked spans so polarity can attach to exact matches ("apart from PitchForce" hole) |
| c | open | **Interpreter model = tagger model** | same Mistral Large via NIM; (Swedish-fidelity rationale deferred with Bonnier — re-argue on HERB terms when asked) |
| d | **DECIDED 2026-06-13** | **function/TAM as bounded arrays** | function 1–3, TAM 0–2 — an episode can be question + resolution |
| e | open | **Context envelope = ancestor scalar fields only** | from raw via references; no sibling chunks, no generated summaries |
| f | **DECIDED 2026-06-13** | **Source-language phrases** | tagger never translates; English in practice while the build is HERB-only |
| g | open | **Embedder at native 2048 dims** | Matryoshka truncation unused; verify dims at connectivity run |
| h | open | **answer_shape = {content, aggregate}** | the minimal "answer shapes" enum the decided text reserves space for |
| i | open | **Current date in the interpreter input** | required for relative-time → date_range resolution |
