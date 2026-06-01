# v2 Artefact Rebuild — Design

**Status:** design, validated against real HERB data. No v2 code written yet.
**Date:** 2026-05-30.
**Baseline it supersedes:** the v1 artefact (git tag `artefact-v1`, commit `244beb7`; Neo4j `herb-eval` + `herb-eval.dump` + sibling `herb-eval-backup`).

**Supersedes the design intent of these v1 docs** (they remain accurate for the v1
system as built, until v2 lands; where they conflict with this doc on *intent*, this
doc governs): [`graph_schema.md`](graph_schema.md), [`system_map.md`](system_map.md),
[`backend/architecture.md`](backend/architecture.md),
[`backend/herb_tagging_schema.md`](backend/herb_tagging_schema.md),
[`backend/herb_tagging_frames.md`](backend/herb_tagging_frames.md),
[`backend/codebase_map.md`](backend/codebase_map.md). Each carries a pointer back here.

This document records the design for rebuilding the access → index → chunk → tag
layer from scratch. The raw datasets, the semantic concepts (tags/weights/grounding
vectors), the eval harness, and the frontend are retained; the ingestion/indexing
path is rebuilt around a different stance.

---

## 1. Core principle — the graph indexes references, it does not store copies

The raw source files are authoritative and untouched. The graph stores **references**
into them plus the derived semantic layer. Content is **resolved on demand** from the
untouched source; the graph never becomes a second, mutated copy that replaces the
original.

The v1 chunker violated this: it consumed each record, rendered it to a prose string,
stored the string as `c.content`, and that lossy derivative became the only surviving
copy. Proof of the inversion: v1 HERB chunks were written with `start_offset=0,
end_offset=len(content)` where `content` is the fabricated prose — the "locator"
pointed inside the fabrication, not the source. The generic JSON path additionally
truncated silently (arrays capped at 50, strings clipped), a lossy fallback that only
spared HERB because HERB had a dedicated handler.

## 2. The reference triple

A reference is `{file_id, scheme, address}`. A resolver turns it into exact source
content on demand. The scheme is chosen by data shape:

| Shape | scheme | address |
|---|---|---|
| nested JSON | `json_pointer` (RFC 6901) | e.g. `/slack/42/Message/User/text` |
| long text leaf | `json_pointer` + `char_span` | field pointer + `[start,end]` within the value |
| flat text / markdown | `char_span` (or byte span) | offsets into the file |
| tabular (parquet/csv) | `row` | row index (+ column) |
| binary / image | reference only | no content resolution |

**Rendering moves, it doesn't disappear.** The tagger still needs text, but the rendered
prose is a transient view computed by resolving the reference, used as tagger input, and
discarded. It is never the stored record.

## 3. Resolution model — read in place, hash-verified

- Raw files stay on disk under a configurable `data_root`; the graph references them by
  relative path.
- **Identity is the content hash** — preflight already computes `sha256`, and
  `file_id = sha256[:24]`.
- **Verify the hash on resolve; fail loud on mismatch.** If the on-disk file no longer
  matches the hash the graph was built against, resolution stops — it does not serve
  drifted content.
- No content-addressed store. The raw is static benchmark data, single machine,
  re-downloadable; hash-on-resolve gives the integrity guarantee a CAS would, without
  duplicating large datasets.

## 4. Pipeline skeleton

1. **Scan** — catalog raw files (hash, format, file_class, split).
2. **Probe** — climb each file, record morphology; drives scheme choice.
3. **Reference** — emit reference triples for logical units. No content stored.
4. **Structure** — materialize source entities + relations as reference-carrying nodes.
5. **Tag** — resolve references to transient views; derive tags/weights/grounding vectors.
6. **Retrieve** — Match → Filter → Rank → Cap over references + semantics.

## 5. The shape probe — schema is recovered, not authored

The probe climbs any parsed file and describes its **shape**, with zero knowledge of
meaning. Its output **is the structural schema** — the tree the old chunker discarded.

- **Output:** one fused shape tree per file. Repetition is collapsed — a 1,200-element
  array becomes one node ("array of N, representative element shape"), not N entries.
  This is standard structural / JSON-schema type inference.
- **Records per position:** kind (object/array/scalar/long-text/binary/null); object
  key-sets; array length + element homogeneity; the JSON-pointer path.
- **Derives as candidates (not decisions):** *collections* (homogeneous arrays of objects
  = record types) and *document leaves* (long-text content to reference, not decompose).
- **Runs during the scan/index pass** (file already parsed — no second read) and
  **persists on `:File` as provenance**.
- **Fuse across all files, not one.** A single file under-determines the schema (see §10).

**The boundary that keeps it agnostic:** the probe describes shape + candidates only. It
does NOT decide "entity to preserve" vs "content leaf to reference." That is a *meaning*
judgment and belongs to the per-dataset mapping. This separation is what makes the probe
reusable for the next dataset unchanged.

## 6. Two senses of schema; semantic mapping is a thin overlay

- **Structural schema** — shape/topology, recovered automatically, agnostic. Carries the
  source's literal names verbatim (JSON keys in the shape tree + pointer paths; folder/
  file names on `:File`/`:Source`). Nothing renames the source.
- **Semantic schema** — meaning. A set of `(literal source name) → (meaning)` pairs, e.g.
  `slack → "Slack messages"`. Not recoverable from shape; it is a labeling.

Meaning is an overlay keyed on the source's own name — it never overwrites it. The raw
name stays permanently; the meaning attaches as a pair. At any point you can ask both
"what did the source call this?" and "what did we decide it means?".

## 7. Decomposition makes attributes queryable by construction

Faithful decomposition = every object → a node, every scalar attribute → a property. So
attributes are queryable from the start, automatically — there is no separate "promotion"
step (that was a re-import of the v1 blob assumption). The cut is simple:

- **Structured → decomposed → queryable.**
- **Only the irreducible free text is referenced-as-content** — the prose meant to be read
  and tagged. Resolved on demand for the tagger.

**Structure ≠ chunk.** Every row is its own structural node (queryable, referenced,
fine-grained) *while* the chunk packs many rows together for tagging. "Each line a node:
yes. Each line a chunk: no." They no longer fight because they are no longer the same thing.

## 8. The mapping key — a declarative settings file per dataset

Per-dataset meaning lives in a **declarative settings file** (a readable "key"/legend),
read by one generic interpreter — not per-dataset Python (which re-buries knowledge in
code, the original sin). The file holds the *rule* (e.g. `message.userId → Employee`);
the *result* (the `:AUTHORED_BY` edges) lives in the graph.

Because structure decomposes automatically, the key shrinks to the judgments shape can't
provide:

1. **Cross-references** — links the nesting doesn't express (`userId → Employee`).
2. **Identity / merge** — repeated mentions unify into one node (a stable id rule).

Labeling (source-name → human label) is optional sugar. Everything unmentioned mirrors
automatically. A small set of named transforms / a narrow escape hatch covers the ~5%
of cases pure declaration can't express (odd date parsing etc.).

## 9. Chunks, tags, and re-tagging

- **Chunks and tags are retained and strengthened.** The content unit *is* the chunk,
  reborn: tags + weights attach as before, but it references free text (resolved on
  demand) and is positioned inside the recovered structure (`:COVERS` the records, sits
  under the entities) instead of floating as a flat child of `:File`. A tag can now be
  traced down to which records it covers and up to which file/entity/attributes.
- **Tagging unit = chunk, per-span.** A coherent passage (e.g. a thread), not per-record;
  tags attach to the chunk, which `:COVERS` the fine-grained record nodes.
- **Chunk-span selection is shape-driven.** Thin/flat records pack many-into-one; document
  leaves get their own chunk (split only if over budget). No hardcoded per-section logic.
- **Re-tag, do not migrate v1 tags.** IDs/dates/authors become structural, so the tagger
  prompt changes to stop emitting them as concepts; chunks are re-derived. Regenerate the
  semantic layer against the clean structure.

## 10. Validation against real HERB data (2026-05-30)

A probe prototype (`.work/probe_prototype.py`) was run on real product files and the HERB
key was hand-drafted (`.work/herb_mapping_draft.yaml`). The design held. Findings:

- The probe recovered the full structural schema with source names verbatim, auto-detected
  every collection (including the nested `prs/*/reviews` records), and flagged the
  long-text document leaves. Scalars sit ready to decompose into queryable properties.
- **Fuse across files is required.** PitchForce alone had `meeting_chats` empty; fusing all
  30 products revealed its shape, showed `Reactions`/`ThreadReplies` are always-empty
  (vestigial), and flagged `answerable_questions/ground_truth` as raggedly typed.
- **Identity resolved empirically** against the metadata directories:
  - `eid_xxxxxxxx` (employee.json, 530 people; key == employee_id): slack `userId` (54/56),
    `team[]` (44/44), document `author` (15/15), transcript `participants` (33/33) →
    `:Employee`. salesforce_team.json is the org hierarchy → `:REPORTS_TO`.
  - `EMP_#########` (pr/review `user.login`): a **separate, directory-less population** —
    zero EMP_ ids exist in employee.json. → its own `:PrAuthor` node, not `:Employee`.
    (A first-pass key wrongly mapped login → Employee; the data corrected it.)
  - `:Customer` (customers_data.json, 120, id=CUST-####): product `customers[]` resolve 22/22.
  - Unresolved-ref policy: ~2/56 slack userIds resolve to no eid → flag loudly, never
    silently drop the edge or invent a node.
- **The eval oracle must be quarantined.** `answerable_questions` + `unanswerable_questions`
  carry `ground_truth` + `citations` — this is the contamination that polluted the old
  `herb` DB. In v2 they are held out of the corpus (`eval_holdout` in the key) and used
  only as the evaluation set; citations reference evidence records by `id`.

## 11. LLM host for the tagger

- **NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`), OpenAI-compatible, forever-free
  as of 2026-05, constrained by a **40 RPM** rate limit (upgradable to 200 RPM).
- The v1 tagger used the Anthropic SDK directly (forced `tool_use`); the **v2 tagger is
  built on the OpenAI-compatible client** pointed at NVIDIA.
- **Model: `deepseek-ai/deepseek-v4-pro`** — chosen by benchmark (reliable HTTP 200, valid
  JSON, consistent latency). `deepseek-v4-flash` is a working fallback; `moonshotai/kimi-k2.6`
  was ruled out (~118 s/call on the free tier, with and without JSON mode).
- **A shared async rate limiter is required** (sliding-window / token-bucket): one per
  process, every outbound call acquires before sending, retries included, target ~38/min
  for margin, with 429 back-off retained as a loud backstop.

## 12. Eval implications

Every run in `run data/` (gold-100, graph100, baseline100, mh_graph, …) was produced
against the v1 graph, whose retriever multiplies seven factors at query time and whose
vocabulary is polluted. Those numbers measure the v1 violation, not the intended product.
The HERB evaluation is re-run on the v2 graph for thesis numbers; v1 runs are kept as the
before/after contrast. The SQL-agent remains the comparison baseline.

## 13. Semantic dimensions — the research basis for the facets

### 13.1 Why the v1 facets degraded

The v1 tagger used five facets — `topic, entities, activity, temporal, evidence`
([`backend/tagging/pipeline.py`](../backend/tagging/pipeline.py) line 52). They were
intended as rich semantic dimensions but were never specified as such, so the model
defaulted to the shallowest reading of each and emitted literal tokens: `temporal` →
date strings (`2024_04_27`), `entities` → identifier strings (`eid_…`), `evidence` →
links (`https_github_com_…_pull_380`). This is the root of the ~18 % junk vocabulary
(`eid_*` alone ≈ 16 k `HAS_TAG` edges). The pollution is what an *underspecified
semantic dimension* collapses into when it is pointed at prose full of literal tokens.

The fix is two-part: (a) move the literal **facts** to structure (§7 — timestamps to
hard fields, identities to `:Employee`/`:Customer` edges, links to entities), removing
the temptation to tag them; and (b) **specify each dimension by its true semantic
intent** — e.g. `temporal` is the *time-relationship* (retrospective / now / forward,
span, urgency), never a date. The date is structure; the temporal *meaning* is the facet.

### 13.2 Convergence across research traditions

The dimensions needed to decompose chunk/sentence meaning are not invented here; seven
independent lineages converge on the same structure:

| Tradition | Dimensions it names |
|---|---|
| Ranganathan **PMEST** (faceted classification) | Personality, Matter, Energy, Space, Time |
| **neo-Davidsonian / AMR** (event semantics) | event + role-bound participants + time + location + manner |
| **5W1H** (journalism / semantic role labeling) | who, what, when, where, why, how |
| **SFL metafunctions** (Halliday) | ideational (content), interpersonal (stance), textual (discourse role) |
| **TAM** | tense, aspect, modality |
| **Appraisal + evidentiality** | attitude, graduation (intensity), engagement/sourcing vs epistemic certainty |
| **RST / speech-act / dialogue-act** | rhetorical / communicative function of a span |

De-duplicated, this yields a **three-tier model**:

- **Tier 1 — Propositional / ideational (the situation):** aboutness/topic (the frame
  or domain); process (what happens); participants + their *roles* (agent/patient/
  recipient — not identifiers); circumstance = time (full TAM) + space + manner +
  cause/purpose.
- **Tier 2 — Interpersonal (stance toward the situation):** evaluation/attitude
  (affect / judgement / appreciation); modality (certainty / obligation / possibility);
  evidentiality (how a claim is *sourced* — distinct from certainty).
- **Tier 3 — Pragmatic / textual (what the span does):** communicative / rhetorical
  function (question / assertion / decision / request / problem / resolution); genre /
  register.

Meaning = a **situation** (frame + process + roles + circumstance), wrapped in a
**stance** (evaluation + modality + sourcing), serving a **communicative function**,
classified by aboutness and genre. Temporal is TAM *inside* circumstance (then/now/
later, ongoing/done, planned) — not dates. A participant is a *role*, not a token.
Evidence is *sourcing*, not links.

### 13.3 Organizing principle — completeness across the totality + prompt/chunk symmetry

The dimensions are **not** all facets. The artefact has several mechanisms, and each
dimension is carried by whichever fits:

- **structure / hard fields** — literal facts (time = timestamp, space, participants as
  entities): exact, queryable;
- **facets on tags** — the genuinely semantic dimensions (stance, communicative
  function, process, aboutness) as weighted tag-edges;
- **chunk description + embedding** — holistic meaning that resists discretization;
- **grounding vectors** — the bridge between prompt-space and corpus-space;
- **prompt interpretation** — the query side.

Two invariants govern the design:

1. **Completeness.** Every dimension in the convergent model is represented *somewhere*
   in the totality (structure ∪ facets ∪ description ∪ grounding ∪ interpreter). None is
   dropped; the totality of the artefact covers the whole dimensional space.
2. **Symmetry.** Whatever the artefact uses to *retrieve* must be mirrored on the prompt
   side — chunk-representation and prompt-interpretation decompose along the *same* axes,
   or they cannot be matched. Communicative function is only useful if the interpreter
   also extracts "the user is asking for a decision"; TAM is only useful if the
   interpreter reads "what did we decide *last* quarter" as past/retrospective.

So facet design is an **allocation problem**, not a list: for each convergent dimension,
decide which mechanism(s) carry it — `{hard field | tag-facet | description/embedding |
grounding | interpreter}` — and confirm the prompt interpreter extracts the matching
axis. "Facets" are simply the subset of dimensions best carried as weighted tag-edges.
Building this dimension → mechanism allocation table (with the interpreter column) is the
next design step before the re-tag is implemented.

### 13.4 References

- Ranganathan, *Colon Classification* / PMEST — faceted classification:
  <https://en.wikipedia.org/wiki/Faceted_classification>
- Halliday, Systemic Functional Linguistics — metafunctions:
  <https://en.wikipedia.org/wiki/Metafunction>
- Thematic / semantic roles; Jurafsky & Martin, *SLP3* ch. 21 (Semantic Role Labeling):
  <https://web.stanford.edu/~jurafsky/slp3/21.pdf>; thematic relations:
  <https://en.wikipedia.org/wiki/Thematic_relation>
- Neo-Davidsonian event semantics (Landman, course notes):
  <https://www.tau.ac.il/~landman/Online%20Class%20Notes/2%20ADVANCED%20SEMANTICS/8%20Neo-davidsonian%20event%20semantics.pdf>
- Abstract Meaning Representation (AMR):
  <https://en.wikipedia.org/wiki/Abstract_Meaning_Representation>
- 5W1H semantic-role extraction:
  <https://arxiv.org/pdf/2505.14804>
- Tense–Aspect–Mood (TAM): <https://en.wikipedia.org/wiki/Tense%E2%80%93aspect%E2%80%93mood>
- Appraisal theory (Martin & White):
  <https://www.grammatics.com/appraisal/appraisaloutline/unframed/appraisaloutline.htm>
- Evidentiality vs epistemic modality (Kroeger, *Analyzing Meaning* ch. 17):
  <https://socialsci.libretexts.org/Bookshelves/Linguistics/Analyzing_Meaning_-_An_Introduction_to_Semantics_and_Pragmatics_(Kroeger)/17:_Evidentiality>
- Rhetorical Structure Theory: <https://en.wikipedia.org/wiki/Rhetorical_structure_theory>
