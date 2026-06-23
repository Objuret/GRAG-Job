# v2 Artefact Rebuild — Design

**Status:** design, validated against real HERB data. Covers the ingestion spine (§1–10),
the tagger host/model (§11), the facet allocation (§13.4–13.5), and the retrieval routing
model (§14). v2 code built so far: scan + probe stages (`backend/v2/`), plus
eval baselines copied to `backend/v2/baselines/` (lucene, vector, sql_agent).
**Date:** 2026-06-01. **Updated 2026-06-12:** graph spine decided — `Source → File →
Chunk → Tag` are the only nodes; hard fields ride as chunk attributes; no entity/record
nodes; the chunk→file relevance weight is removed; no pre-embedded hard-field vocabulary
(§7, §10, §14). The chunk *description* is dead (2026-06-11): a chunk's semantic
representation is the union of its phrase tags. §13–14 sections still describing shared
tag nodes, descriptions, or embedding-axis projection are stale pending the facet-carrier
decisions and are marked where they occur.
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

0. **Derive-corpus (one-time prep, per dataset that needs it)** — if the published
   dataset embeds RAG-unsafe surfaces inside the corpus files, derive the **corpus
   view** from the working raw (`backend/v2/derive_corpus.py`,
   `python -m v2 derive-corpus raw/<dataset>`): **`corpus/<dataset>/`** with those keys
   deleted — the root every later stage scans, and the canonical raw the graph
   references. For HERB the strip is two categories, both mandated by the benchmark
   itself (dataset card + arXiv:2506.23139):
   - the **eval oracle**: `answerable_questions` / `unanswerable_questions`;
   - the **membership links**: `team` / `customers` — the dataset card's RAG
     Evaluation Note marks them "for oracle/long-context evaluation settings only";
     390/815 answerable questions are people-/customer-search, and membership must be
     inferred from the artifacts or from `metadata/*` (which therefore **stays** in
     the corpus view).
   The quarantine is **structural, not declarative** (decided 2026-06-12, replacing
   the earlier `eval_holdout` key section): the probe can never sense the stripped
   surfaces, so contamination is impossible by construction instead of excluded by a
   yaml line. Nothing stripped is **copied anywhere** (references-not-copies applies
   to eval too): the eval harness reads the oracle in place from `raw/<dataset>/`.
   Files without stripped keys are copied byte-verbatim (hashes match the raw);
   stripped files are re-serialized deterministically. `raw/<dataset>/` stays
   byte-untouched; the derivation is rerunnable. Data layout rule:
   `A:\exjobbet\data\raw` is cold storage — never written, never worked with; the
   pipeline's `data_root` is the repo-local working copy (`backend/data`), where
   `raw/` and the derived `corpus/` live.
1. **Scan** — catalog the corpus view's files (hash, format, file_class, split).
2. **Probe** — climb each file, record morphology; drives scheme choice.
3. **Reference** — emit reference triples for logical units. No content stored.
4. **Structure** — extract the hard-field values (ids, timestamps, kinds, labels) from
   the structured parts; they become indexed attributes on the chunks formed next. No
   entity or record nodes are materialized (§7).
5. **Tag** — resolve references to transient views; derive tags/weights/grounding vectors.
6. **Retrieve** — Match → Filter → Rank → Cap over references + semantics (the routing model, §14).

## 5. The shape probe — schema is recovered, not authored

The probe climbs any parsed file and describes its **shape**, with zero knowledge of
meaning. Its output **is the structural schema** — the tree the old chunker discarded.

- **Output:** one fused shape tree per file. Repetition is collapsed — a 1,200-element
  array becomes one node ("array of N, representative element shape"), not N entries.
  This is standard structural / JSON-schema type inference.
- **Records per position:** kind (object/array/scalar/long-text/binary/null); object
  key-sets; array length + element homogeneity; the JSON-pointer path; per-field
  **repetition ratio** (distinct/total across the fuse) — the descriptive stat that
  drives the attribute-vs-raw split (§8).
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

## 7. The graph spine and the node/attribute rule (decided 2026-06-12)

**The graph is `Source → File → Chunk → Tag`. Nothing else is a node.** This replaces
the earlier draft in which every object became a node (Message/PullRequest/Employee
entity nodes, COVERS edges) — that draft mirrored the dataset into the graph, which is
the copies disease at the node level.

**The rule deciding node vs attribute:** a thing is a **node** only when others depend
on its facts to resolve themselves, or retrieval walks *through* it. It is an
**attribute** when it is a value you filter or boost by.

- **File = node.** It is the resolution catalog — path on disk, sha256, format, the
  probe's shape tree — and every reference depends on it; the hash must have one
  authoritative copy. Containment edges (Source→File→Chunk) stay.
- **Chunk = the finest node.** The hard-field values extracted from the structured
  parts ride as **indexed chunk attributes**: author ids, time range, kind,
  branch/channel labels, the materialized path. Caching exact values as attributes is
  fine — the authoritative copy is the raw, and a rebuild re-derives them
  deterministically. What is forbidden is the graph becoming the only home of content,
  or storing mutated content.
- **Attributes ride at the structural scope where the value sits (decided 2026-06-12).**
  Record-level values land on the covering chunk; file-level values land as
  **File-node attributes**. A file-level hit boosts through containment — broader and
  weaker than a chunk-level hit; the magnitude belongs to the combinator (§14.3).
  (HERB's only file-level values, `team[]`/`customers[]`, turned out to be RAG-unsafe
  and are stripped at §4 stage 0 — the rule stands, vacuous for HERB, live for
  Bonnier.)
- **Records are NOT nodes.** Most records are inside exactly one chunk — a record tier
  would duplicate the chunk tier. Records stay individually addressable through their
  references (json_pointer); their values ride on the covering chunk's attributes.
- **Branch/collection positions are NOT nodes.** The tree between file and chunk lives
  in the path attribute; "everything under slack" is a prefix filter, not a hop. Branch
  names and shapes live once on the File node (probe tree) and in the mapping key.
- **Metadata directories (employees, org hierarchy, customers) are NOT nodes.** They
  live in the raw, read through references at query time; ids in chunk attributes are
  the connection between content and directory. The graph never mirrors them.
- **Tag nodes are per-chunk emissions, not shared vocabulary (decided 2026-06-13).**
  Each tag the tagger emits becomes its own `:Tag` node bound to exactly one chunk; the
  same phrase text may recur on other chunks as *other* nodes. A tag is a reading *of*
  one chunk — sharing nodes conflates distinct emissions. Nothing walks *through* a
  tag (retrieval goes kNN-hit → its one chunk; diversity/expansion is path-prefix
  based), so shared identity carries no mechanism; "same phrase elsewhere" is text
  equality on an indexed property. This is what made v1's residue possible: shared
  tags minted from oracle chunks survived the herb-eval filter attached to clean
  chunks, and orphan-tag bookkeeping existed at all. Unique tags make per-chunk
  retag/delete local and lossless; a shared-vocabulary view stays derivable any time
  (group/merge by normalized text — the reverse direction is the lossy one).
  Embedding cost is unaffected: the embed cache keys on normalized text, identical
  text embeds once.

**Only the irreducible free text is referenced-as-content** — the prose meant to be read
and tagged, resolved on demand for the tagger. Which fields matter (become attributes)
is driven by the probe's classing plus the mapping key — no hand-written per-dataset code.

## 8. The mapping key — a declarative settings file per dataset (finalized 2026-06-12)

Per-dataset meaning lives in a **declarative settings file** (a readable "key"/legend),
read by one generic loader — not per-dataset Python (which re-buries knowledge in code,
the original sin). The key holds the *rule*; the materialized attributes in the graph
are the *result*, re-derived from raw on any rebuild. No node- or edge-minting
vocabulary exists in the file: the old draft's `refs:` (edges) and `id:` (node identity
/ merge) died with the spine (§7).

**The automatic part — the shape→handling table.** What happens to a field follows the
shape of its values, read off the probe tree with **no key entry**:

- **Date-shaped values** → the covering chunk's time-range attribute.
- **Fields assigned to an id-space** (declared below) → id-set attributes.
- **Repeated short scalars** → indexed label/value attributes. The discriminator
  between "attribute" and "stays in raw" is the **repetition ratio** (distinct/total
  per field, measured by the probe across the fuse): a value shared across many records
  (channel names, `state`, `type`) is a grouping coordinate → attribute; a
  per-record-unique free-form value (`title`, `link`) is content-like → stays in raw
  behind the reference, never copied. The gap between the two is a chasm, not a
  threshold to tune.
- **Long-text leaves** → the content itself: referenced, chunked, tagged (§9).
- **Attributes ride at the structural scope where the value sits** — record-level on
  the covering chunk, file-level on the File node (§7).

**The declared part — the three judgments shape can't know:**

1. **Content choice** — which fields are the prose to chunk and tag. The probe flags
   `str_long` candidates; only meaning draws the line (a 120-char url `description` is
   content; a 99-char PR `title` is not).
2. **Directories** — which files are id-directories rather than corpus
   (`employee.json`, `customers_data.json`), each with its key field, display-name
   field, and a **`kind`** drawn from the query interpreter's universal enum (starting
   set: `person` / `org` / `product`). The kind is the entire bridge from an
   interpreter flag ("person-ish") to the one directory the scoped distance-lookup
   searches (§14.7) — a literal equality join, no mapping layer. The **source-name
   space itself gets a kind too** (HERB sources are *products*; Bonnier sources are
   systems): what a source name *is* is dataset meaning, so it lives here.
3. **Id-space assignment** — which fields carry which id-space (`userId` → employee,
   `login` → the directory-less PR-author space). Shape sees `str maxlen=15`; it cannot
   know slack userIds and document authors are the same population while PR logins are
   not.

The eval oracle is **not** a key judgment: it is quarantined structurally at §4
stage 0 — the scanned root physically cannot contain it, so the key has nothing to say.

The enum is **universal** (language ontology, fixed in the interpreter's contract); the
**active subset is dataset-derived** — the union of kinds the key declares. An
interpreter flag with no declared kind has no landing spot: no lookup fires, the token
rides the semantic layer, and the miss is logged loudly (exactly the eval evidence that
would justify extending a key later). "What can be asked about in hard fields" emerges
at the join; it never enters the interpreter's context.

Labeling (source-name → human label, §6) is optional sugar. Everything unmentioned
mirrors automatically; silence means "mirror it". A small set of named transforms / a
narrow escape hatch covers the rare case pure declaration can't express (the ragged
`ground_truth` typing lives in the raw oracle and is the harness's problem; HERB's
corpus needs none).

## 9. Chunks, tags, and re-tagging

Chunks and tags are **retained and strengthened**, not removed. The content unit *is* the
chunk, reborn: tags and weights attach as before, but it references free text (resolved on
demand) and is positioned inside the recovered structure by its materialized path —
instead of floating as a flat child of `:File`. A tag can be traced down through the
chunk's references to the exact records it covers and up to the file. The sections below
govern how chunk spans are *formed*; records stay individually addressable through
references regardless of how chunks group them (§7 — no record nodes).

### 9.1 A chunk is a coherent episode, not a fixed-size window

v1 filled records into a chunk up to a token budget — fill-to-budget batching. v2 kills
that. **A chunk is a coherent episode**: a thread, a conversation that hangs together, a
document. Coherence is load-bearing now in a way it wasn't for v1's shallow keyword tags —
the v2 facets (§13) only mean something on a coherent unit, so a budget-smeared mixed bag
would corrupt them. The size cap survives only as a **guardrail** you hit on oversized
units, never the grouping rule.

**What the cap *is*.** Not a token limit for its own sake, and not an embedder limit — the
embedder only ever sees short artifacts (the phrase tags), never the raw chunk. It is the
**tagger's effective focus span**: the size past which the tagger can no longer hold the
whole unit in view well enough to emit one faithful set of tags. That degradation is
well-documented — a model's *effective* context on a non-literal task collapses far below
its raw window (lost-in-the-middle; RULER; NoLiMa, §9.7) — so the cap sits at the top of
the high-fidelity zone, not at the context window.

**The number: ~3000 tokens** (vs v1's 800 target / 1500 hard). Deliberately *larger* than
the classic RAG 512–1024 band, for one reason: that band exists to fight single-vector
compression, and v2 never embeds the raw chunk — meaning lives in the *tags* (the union of
a chunk's phrase tags IS its semantic representation; there is no description, decided
2026-06-11), so there is no fat vector to dilute. 3000 is a calibration seed, not a
verdict: sweep chunk size on HERB/Bonnier, watch where tag relevance starts to sag, and
set the cap just under that knee (§15).

Chunks are built by **descending the source's own structure** and grouping leaf-level
conversation/prose by coherence. This is the inverse of most chunking research, which is
about *splitting* long prose; the hard case here is the opposite — *grouping* tiny
discrete records — which maps onto conversation segmentation, not document splitting.
(Embedding-similarity "semantic chunking" was considered and rejected, on the grounds in
§9.4 and in the literature: it rarely beats structural splitting enough to justify the
cost.)

### 9.2 The index is a materialized path — canonical throughout, with one minted tier

The chunk index is a **materialized path stored as integer components** (`[1,2,3]`, not
the string `"1.2.3"` — so `1.10` doesn't missort and prefix-matching stays clean). It
replaces v1's flat per-chunk `ordinal`, of which it is a generalization, not a new
concept. The path carries **position only** — *where* a unit sits. *What* it is
(channel/thread/message) lives in the probe's recovered shape schema (§5), never crammed
into the numbers.

The path **is the canonical source structure, top to bottom — records included**. File →
channel → thread → message: every one of those positions is a real source unit, so every
position is canonical. A record's path component and its `json_pointer` reference are two
views of the same canonical spot, so there is no second, drift-prone address.

The **single exception is the subchunk split**. When a coherent episode exceeds the budget
ceiling, the fragments it is sliced into are the only positions on the whole path that
correspond to nothing in the source — *we* drew those lines. A split **inserts that one
non-canonical tier**: an over-budget thread at `[1,2]` gets fragments `[1,2,1]`, `[1,2,2]`,
`[1,2,3]`, and its messages ride one tier deeper as canonical leaves beneath them. There
is **no parent/episode node** — the episode exists only as "the fragments sharing the
`[1,2]` prefix," reassembled on demand at query time. The split rule is uniform (§9.4):
when a unit exceeds the cap, walk back to the **best natural seam** below it and recurse —
no minimum-size rule, because a unit that fits the cap is already a chunk, and the
worst-case seam is always a real boundary (a sentence), never an arbitrary cut.

The path does **triple duty**: structural ancestry, context expansion (gather by prefix),
and duplicate-collapse / diversity (group by prefix).

### 9.3 "Records vs prose" is per-position, not per-file

Whether something is a decomposed record or a referenced prose leaf is decided **per
position in the tree**, not as a per-file label — most real data is mixed. Walking the
recovered shape:
- **Regular structured parts** → addressable positions: references plus hard-field
  values extracted as chunk attributes (no nodes — §7).
- **Long-text leaves** → coherence-chunked. This includes a prose field *inside* an
  otherwise-structured record (a HERB document or transcript = metadata fields + one
  content field).
- **Binary/opaque** → reference only; no fake decomposition.

### 9.4 The boundary detector is fully deterministic — no embeddings, no LLM

One top-down seam-finder does both the first-pass episode segmentation and the recursive
over-budget splitting, at finer and finer scale. The unit comes from **structure first** —
an explicit thread, a document, a section, a record run; for a flat stream with no structure
the unit is the whole stream — and the seam-finder only does real work when that unit
exceeds the cap.

**Seams are per content-kind**, dispatched by the probe's recovered shape (NOT by file
format — that was the v1 sin). The vocabulary differs because the natural boundaries do:
- **Conversation:** explicit reply/quote link (works *against* cutting — an adjacency pair, a
  question and its answer, stays together) > day-boundary / large **adaptive** time-gap (a
  gap much larger than the *local* median, not a fixed minutes constant) > participant
  turnover > lexical-topic shift.
- **Prose:** section > paragraph > sentence / clause (EDU).
- **Record collections:** record boundaries (every boundary is clean; the run simply packs
  toward the cap).

**The split rule is uniform:** when a unit exceeds the cap, walk back from the cap to the
**best seam in that window** — the strongest available boundary, not merely the nearest —
cut there, and recurse on the remainder. There is **no minimum size**: a unit that fits the
cap is already a chunk, small coherent units included. The worst-case seam is always a real
boundary (a sentence / EDU), so a forced cut is never an arbitrary mid-thought butcher cut.

**Embedding-similarity / topic-drift is rejected** as a boundary signal: it is circular
(nothing is embedded at chunk-time — the chunk is the unit you are still forming), it needs
an extra pre-pass embedding of every raw message, and terse chat ("+1", "see above") embeds
to noise. The literature agrees structural beats embedding-semantic at a fraction of the cost
(§9.7). Boundaries are decided at structure-time, before the embedder or tagger touch
anything.

### 9.5 Tagging unit, context, and no overlap

- **Tagging unit = the chunk** (the coherent passage), not per-record. Tags attach to the
  chunk, whose references and attributes carry the records it spans. When an episode is split, tags attach to
  whatever fits the tagger — the fragment when split, the whole episode when not — and the
  episode is reassembled by prefix on demand.
- **Context comes from the graph around the chunk** (small-to-big / parent-record, in the
  spirit of contextual retrieval but free from the recovered structure), not from fat chunks.
- **No overlap.** Overlap fights references-not-copies and dirties the `:COVERS` edges — the
  same record in two chunks would be double-tagged, double-attributed, double-surfaced.
- **One stateless call per chunk.** The tagger is a single structured-output invocation per
  chunk — same prompt, temp 0, one chunk in, phrase tags out (no description, no numbers),
  instance discarded — NOT a multi-step agent loop and NOT several chunks batched into one call. The
  graph-assembled context above is handed in as an explicit *input* (a pure function of
  chunk + graph, hence reproducible), never carried in instance memory. Statelessness is
  load-bearing: it is the precondition for the build-time validation in §16 — golden tests,
  response-caching, small-sample error analysis, and prompt-regression assertions are valid
  only because the sole variable across runs is the prompt. It is the same commitment as the
  §9.1 cap (one coherent chunk, one focused fresh instance); batching chunks per call would
  violate both the focus-span premise and reproducibility.

### 9.6 Re-tag, do not migrate v1 tags

IDs, dates, and authors are now structural (entities + properties), so the tagger prompt
changes to stop emitting them as concepts; migrating old tags would drag the `eid_*` / year
junk forward. Chunks are also re-derived (reference-based, different spans), so old tags
attached to v1 prose blobs would not map cleanly. Regenerate the semantic layer against the
clean structure (the tagger is already at temp 0).

### 9.7 Research grounding

The model lines up with three literatures rather than being ad hoc:
- **Linguistic.** Topic segmentation cuts text into coherent multi-paragraph "episodes" via
  lexical cohesion (TextTiling), and discourse is a recursive tree of clause-level Elementary
  Discourse Units (RST) — so the "coherent episode," the hierarchy, and the sentence/EDU
  floor are the textbook units, not inventions. Conversation analysis adds adjacency pairs (a
  question and its answer belong together — the reply-link-protects-against-cutting rule).
- **Data / RAG.** Embedding-based "semantic chunking" does not justify its cost — fixed-size
  and structural splitting match or beat it, and what matters is per-sentence embedding
  quality, not boundary cleverness ("Is Semantic Chunking Worth the Computational Cost?",
  NAACL Findings 2025). Conversation disentanglement — the actual task for splitting
  interleaved chat — does it with reply-links + timing + lexical features, deterministically.
  Both back the structure-first, deterministic seam-finder.
- **LLM.** Effective context collapses below the raw window on non-literal tasks (RULER;
  NoLiMa), which is why the cap is the tagger's focus span, not its context window; and the
  usual small-chunk advice is downstream of single-vector compression, which v2 sidesteps by
  tagging rather than embedding the chunk (§9.1).

References: [TextTiling (Hearst 1997)](https://aclanthology.org/J97-1003.pdf) ·
[Rhetorical Structure Theory / EDUs](https://en.wikipedia.org/wiki/Rhetorical_structure_theory) ·
[Conversation disentanglement corpus (Kummerfeld et al.)](https://arxiv.org/abs/1810.11118) ·
[Is Semantic Chunking Worth the Computational Cost? (2025)](https://arxiv.org/abs/2410.13070) ·
[Rethinking Chunk Size for Long-Document Retrieval (2025)](https://arxiv.org/abs/2505.21700) ·
[NoLiMa (2025)](https://arxiv.org/abs/2502.05167) ·
[RULER (2024)](https://arxiv.org/abs/2404.06654)

## 10. Validation against real HERB data (2026-05-30)

A probe prototype (`.work/probe_prototype.py`) was run on real product files and the HERB
key was hand-drafted (`.work/herb_mapping_draft.yaml`). The design held. Findings:

- The probe recovered the full structural schema with source names verbatim, auto-detected
  every collection (including the nested `prs/*/reviews` records), and flagged the
  long-text document leaves. Scalars sit ready to decompose into queryable properties.
- **Fuse across files is required.** PitchForce alone had `meeting_chats` empty; fusing all
  30 products revealed its shape, showed `Reactions`/`ThreadReplies` are always-empty
  (vestigial), and flagged `answerable_questions/ground_truth` as raggedly typed.
- **Identity resolved empirically** against the metadata directories (2026-06-12 note:
  these are **id-spaces resolved through the raw directories via references**, not entity
  nodes — the graph mirrors none of them, §7):
  - `eid_xxxxxxxx` (employee.json, 530 people; key == employee_id): slack `userId` (54/56),
    `team[]` (44/44), document `author` (15/15), transcript `participants` (33/33) all
    resolve in the employee id-space. salesforce_team.json holds the org hierarchy — read
    from raw when needed.
  - `EMP_#########` (pr/review `user.login`): a **separate, directory-less population** —
    zero EMP_ ids exist in employee.json. Its own id-space; never conflate with employee
    ids. (A first-pass key wrongly mapped login → employee; the data corrected it.)
  - Customer id-space (customers_data.json, 120, id=CUST-####): product `customers[]`
    resolve 22/22.
  - Unresolved-ref policy: ~2/56 slack userIds resolve to no eid → flag loudly, never
    silently drop or invent an identity.
- **The RAG-unsafe surfaces are quarantined structurally (executed 2026-06-12).**
  `answerable_questions` + `unanswerable_questions` carry `ground_truth` + `citations` —
  the contamination that polluted the old `herb` DB — and `team`/`customers` are
  oracle-only membership links per the dataset card (the paper's own framing: product
  metadata links are "not typically available in real enterprise environments and
  should not be used to evaluate system performance"; 260 people-search + 130
  customer-search of the 815 answerable questions would otherwise be roster lookups).
  §4 stage 0 (`derive_corpus.py`) was run on the real data: 30 product files stripped,
  3 metadata files copied byte-verbatim; 815 + 699 = **1,514 questions**, **1,370 team
  entries**, and **720 customer entries** counted during derivation and left in place
  in the working raw (the harness reads the oracle there). Re-probing the corpus view
  shows 6 root collections and none of the stripped keys — the probe is blind to them
  by construction. Citations reference evidence records by `id`, resolved through
  references at eval time. Membership questions are answered the way the card
  prescribes: inferred from artifacts and `metadata/*`.

## 11. LLM host for the tagger

- **NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`), OpenAI-compatible, forever-free
  as of 2026-05, constrained by a **40 RPM** rate limit (upgradable to 200 RPM).
- The v1 tagger used the Anthropic SDK directly (forced `tool_use`); the **v2 tagger is
  built on the OpenAI-compatible client** pointed at NVIDIA.
- **Tagger model: `mistral-large-3-675b-instruct-2512`.** The deciding axis for facet
  tagging is Swedish semantic fidelity (the Bonnier dataset) — stance / process /
  communicative-function must be read correctly, not just tokenized — and the
  European-trained Mistral family carries Swedish better than the China-trained
  alternatives. NIM flattens cost (free, only rate-limited), so the largest tier is taken:
  most reasoning depth + best Swedish. Tagging is a depth problem, so Large is chosen over
  the newer/smaller `mistral-small-4-119b-2603`.
- **Embedder: `nvidia/llama-3.2-nv-embedqa-1b-v2`** (NeMo Retriever) — evaluated on 26
  languages including Swedish, 8 192-token context, Matryoshka dynamic sizing; paired
  reranker `nvidia/llama-3.2-nv-rerankqa-1b-v2`. Same OpenAI-compatible client. Swedish
  quality is confirmed on the Scandinavian Embedding Benchmark (SEB), not generic MTEB.
  This is the load-bearing choice for the retriever (§14): it sets the facet-axis
  projection and the fuzzy half of prompt-side hard-field matching.
- **A shared async rate limiter is required** (sliding-window / token-bucket): one per
  process, every outbound call acquires before sending, retries included, target ~38/min
  for margin, with 429 back-off retained as a loud backstop. Per-call latency on the free
  shared tier is load-driven, not intrinsic model speed, so throughput is governed by the
  limiter, not the model size.

## 12. Eval implications

Every run in `v1/run data/` (gold-100, graph100, baseline100, mh_graph, …) was produced
against the v1 graph, whose retriever multiplies seven factors at query time and whose
vocabulary is polluted. Those numbers measure the v1 violation, not the intended product.
The HERB evaluation is re-run on the v2 graph to validate the rebuild; v1 runs are kept
as the before/after contrast. The SQL-agent remains the comparison baseline.

**Scope (2026-06-13): the build and eval are HERB-only for now.** Bonnier — the
naturalistic arm (real multi-system Swedish data, self-authored questions, no baseline
numbers; external validity, not metrics) — is **deferred** to a later phase, together
with its mapping key and eval format (§15).

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

> **STATUS (2026-06-14).** §13.3–13.4 are updated to the current model (description
> purged, entities→attributes). **Facet concept reframed (2026-06-14, user):** a facet
> is NOT a bucket/category a tag belongs to — it is the **relevance coordinate / the
> character of a tag**, and the facets are **parallel comparison channels**. Retrieval
> decomposes the prompt per facet and matches **same-facet, like-for-like**
> (prompt.topic↔tag.topic, prompt.stance↔tag.stance); each channel yields a distance,
> summed weighted by prompt emphasis. The v1 tag concept (tags carry per-facet
> relevance, one edge carrying the whole facet vector) was SOUND; only the
> *model-emitted* weights were the defect. This **supersedes the 2026-06-13 "per-facet
> phrase lists" carrier note**, which is REOPENED: how a tag gets its per-facet content
> at build time is now an OPEN question (see state doc
> 2026-06-14-v2-facets-as-relevance-channels). Still standing: function/TAM are
> closed-enum chunk attributes (§7); every emitted tag is its own per-chunk node (§7);
> the model emits no numbers (per-facet relevance is measured, not emitted); the
> dimension→mechanism allocation logic (facts→structure, semantics→facets) and the
> five-facet set. §13.5's emit-examples (bare labels) are stale and rewritten when the
> carrier/build-time question closes.

### 13.3 Organizing principle — completeness across the totality + prompt/chunk symmetry

The dimensions are **not** all facets. The artefact has several mechanisms, and each
dimension is carried by whichever fits:

- **structure / hard fields** — literal facts (time = timestamp, space, participant ids
  as chunk attributes): exact, queryable;
- **facets on tags** — the genuinely semantic dimensions (stance, communicative
  function, process, aboutness), carried per-facet on the phrase tags;
- **phrase-tag embeddings** — the bridge between prompt-space and corpus-space;
- **prompt interpretation** — the query side.

Two invariants govern the design:

1. **Completeness.** Every dimension in the convergent model is represented *somewhere*
   in the totality (structure ∪ tags/facets ∪ interpreter). None is dropped; the
   totality of the artefact covers the whole dimensional space.
2. **Symmetry.** Whatever the artefact uses to *retrieve* must be mirrored on the prompt
   side — chunk-representation and prompt-interpretation decompose along the *same* axes,
   or they cannot be matched. Communicative function is only useful if the interpreter
   also extracts "the user is asking for a decision"; TAM is only useful if the
   interpreter reads "what did we decide *last* quarter" as past/retrospective.

So facet design is an **allocation problem**, not a list: for each convergent dimension,
decide which mechanism(s) carry it — `{hard field | tag-facet | description/embedding |
grounding | interpreter}` — and confirm the prompt interpreter extracts the matching
axis. "Facets" are simply the subset of dimensions best carried as weighted tag-edges.
The allocation table below (§13.4) fills this in; the per-facet extraction specs follow
in §13.5.

### 13.4 Dimension → mechanism allocation (the table)

Each convergent dimension is placed across mechanisms, with the prompt-side (interpreter)
axis and the match type (EXACT = structured query vs SEMANTIC = graded/grounded):

| Dimension | Primary carrier | Also | Interpreter extracts | Match |
|---|---|---|---|---|
| **Aboutness / topic** | tag-facet (topic) | phrase-tag embeddings | prompt topic | SEMANTIC |
| **Process** (what happens) | tag-facet (process) | — | the action sought | SEMANTIC |
| **Participants + roles** | STRUCTURE (id attributes on chunks + raw directories via references; no entity nodes — §7) | — | named/role refs ("PRs by X", "QA lead said") | EXACT |
| **Time (TAM)** | DUAL: STRUCTURE (literal date) + tag-facet (tense/aspect/modality) | — | "last quarter"→past+date-range; "upcoming"→planned | EXACT (date) + SEMANTIC (stance) |
| **Space / location** | STRUCTURE (hard field) | — | location constraints | EXACT |
| **Manner** | phrase tags (carrier OPEN; was description — dead) | — | (rare in prompts) | SEMANTIC |
| **Cause / purpose** | phrase tags (carrier OPEN; was description — dead) | possible relation edge | "why" intents | SEMANTIC |
| **Evaluation / attitude** | tag-facet (stance) | — | "concerns about X", polarity | SEMANTIC |
| **Modality** (certainty/obligation) | tag-facet (stance) | — | "what must we" (deontic) / "might" (epistemic) | SEMANTIC |
| **Evidentiality / sourcing** | STRUCTURE (provenance = the reference triple) | minor facet (hedging) | "where documented / show evidence" | EXACT (provenance) |
| **Communicative / rhetorical function** | tag-facet (function) — HIGH value | — | "find the decision / problem / question" | SEMANTIC |
| **Genre / register** | STRUCTURE (hard field: kind/section) | — | "in slack" / "in the PRs" | EXACT |

**Resulting v2 facet set** — only the genuinely fuzzy-semantic dimensions worth graded
tag-edges + grounding: **topic, process, stance (attitude + modality),
communicative-function**, plus **temporal-stance (TAM)** as the meaning-half of temporal.
~4–5 facets.

Everything else resolves cleanly:
- **Structure / hard fields (EXACT):** participants+roles, literal time, space, genre/kind,
  evidentiality/provenance — exactly the v1 "junk facets" (entities/temporal/evidence)
  relocated to where they belong.
- **Phrase-tag embeddings (SEMANTIC):** the bridge between prompt-space and corpus-space;
  manner and cause/purpose ride in the phrases (carrier detail open — the description
  that used to hold them is dead).
- **Interpreter:** must extract every axis used to retrieve (symmetry) — especially
  communicative-function and TAM-stance.

This resolves the facet-redesign question of §13.1: v1's pollution was three *fact*
dimensions mis-assigned to tag-facets; the allocation puts facts in structure and keeps
only the 4–5 truly-semantic facets.

### 13.5 Per-facet extraction specs

The spec that never existed in v1 — each facet with what it captures, what the tagger
emits, what it must NOT emit (now structure), and the interpreter mirror (symmetry).

1. **topic** (aboutness / frame-domain)
   - emits: concise conceptual noun-phrase tags (`api_rate_limiting`, `billing_migration`);
     external named tech-as-concept OK (`kubernetes`, `salesforce`).
   - MUST NOT: employee/customer ids, dates, URLs, PR numbers (→ structure).
   - interpreter: extract the topic(s) asked about → ground against corpus topic tags.

2. **process** (what happens / transitivity)
   - emits: action tags (`debugging`, `code_review`, `incident_response`, `planning`,
     `decision_making`).
   - MUST NOT: the actors (→ structure), the sentiment (→ stance).
   - interpreter: extract the action sought ("how was X fixed", "who reviewed Y"→review).

3. **stance** (attitude + modality — interpersonal)
   - emits: graded tags on attitude (`critical`, `concerned`, `blocked`, `approving`) and
     modality (`proposed`, `required`, `uncertain`, `committed`).
   - MUST NOT: the factual content / topic.
   - interpreter: "concerns/complaints about X"→negative; "what must we"→deontic; "what's
     blocked"→negative+obligation.

4. **communicative-function** (rhetorical / speech-act — textual)
   - emits: a function-type from a CLOSED set: `question | problem | decision | resolution
     | request | proposal | announcement | status | explanation`.
   - MUST NOT: topic/content.
   - interpreter: ESSENTIAL, highest retrieval leverage — "find the decision"→decision;
     "what problems"→problem; "what was asked"→question.

5. **temporal-stance (TAM)** — meaning-half of temporal (literal date = structure)
   - emits: TAM tags from a CLOSED set (`retrospective`, `ongoing`, `planned`, `deadline`,
     `recurring`). NEVER dates.
   - interpreter: "last quarter"→past + date-range filter on the *structural* timestamp;
     "upcoming/next"→prospective/planned; "still"→ongoing.

**Controlled vocab:** communicative-function and TAM are small CLOSED sets (enums);
topic/process/stance are open but concept-only. This is what the v2 tagger prompt encodes
per facet — the missing spec that caused v1 degradation.

### 13.6 References

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

---

## 14. Retrieval — the routing model

Expands the one-line §4.6. Converged with the design 2026-05-31, extended 2026-06-01.
Builds on the facets (§13) and the references-not-copies graph (§1).

### 14.1 The graph it routes over (rewritten 2026-06-12)

The spine of §7: `Source → File → Chunk → Tag`, plus hard-field attributes on chunks.
- **File→Chunk is containment only — it carries NO weight.** The v1 "chunk's relevance
  to its file" number is removed: its job (demoting filler) is solved at the source by
  coherence-episode chunking, and what it actually measured — typicality — buries the
  rare relevant aside. If one file floods the top of a ranked list, the fix is
  path-prefix grouping, not a stored number.
- **Tags are per-chunk phrase nodes** (2026-06-11): the contextual phrase IS the node,
  carrying the phrase text + its embedding. No shared concept nodes, no synonym merge —
  cross-chunk linking is embedding proximity. There is **no chunk description**; the
  union of a chunk's phrase tags is its semantic representation.
- **Per-facet values** ride at facet-specific carriers (node vs edge vs label —
  OPEN, the Bucket 2 carrier decisions). Intrinsic values sit on the tag node;
  sibling-relational values sit on the chunk→tag edge.
- Literal text is retained alongside every embedding; embeddings are an added index,
  never a replacement.

### 14.2 What routing IS

Not filter-routing, not pure embedding search, not clustering — **weighted propagation of
query activation through the layers down to chunks**:
1. The interpreted prompt produces entry points: embed it + extract prompt-tags; match
   corpus tags by embedding; activate facets by the prompt's facet character.
2. Activation flows down the weighted edges (facet→tags→chunks; no chunk→file
   modulation — that weight is removed, §14.1), accumulating at chunks.
3. Rank by accumulated weight; the **cap** takes top-N.

The earlier candidate mechanisms are subsumed: embedding search = the ENTRY, filters =
(soft) prune, facet-clusters = SCOPE, the weighted line = the RANKING signal. A query can
enter **LOW** (names a concept → its tags → chunks) or **HIGH** (facet-character only →
enters at the facet → flows to all related tags → chunks). The facet layer is what makes
abstract/thematic queries work.

### 14.3 The combinator

`score = promptFacetRelevance · facetWeights` — a **prompt-conditioned weighted dot
product** of the prompt's per-facet relevance vector against the item's facet-weight
vector. Applied twice with the same rule: across facets to score a tag, then across tags
to score a chunk.
- **Accumulation, not max** across facets: strong across several *relevant* facets beats a
  max on one.
- Relevance is a **continuous coefficient, not a gate** — a weak/irrelevant facet gets ~0
  coefficient and self-attenuates. The coefficient *is* the gate, smoothly.
- **Normalization (open):** normalize the prompt vector (emphasis sums to 1) so "how much
  the prompt cares" is honest; keep tag magnitude but **bounded** so intensity survives
  without a few loud tags dominating.
- Rejected: multiplication (too brutal), raw unweighted addition (rewards
  vague-everywhere over exactly-right).

### 14.4 No hard filters

No hard filters anywhere in ranking. A hard filter crushes signal and — worse — gates on a
*judgment that can be wrong*: a true decision mis-tagged would be silently, totally
excluded (the loud-failure principle: surface it, never silently drop it).
- **"Mandatory" is weight concentration, not a gate:** intense prompt focus drives
  facet-relevance ~1.0 on that facet, ~0 elsewhere; non-matches sink in rank and fall out
  at the cap. Nothing is removed — a borderline-classified match with strong other signal
  can climb back.
- The **cap does the cutting**, on the ranked continuum. So "Filter" in
  Match→Filter→Rank→Cap means pruning literally-zero candidates at most, never gating on
  uncertain judgments. Facets always *order*, never *filter*.

### 14.5 Hard fields as a third signal — soft boosts

The materialized structural hard fields (kind, product, date/time, participant ids,
provenance — chunk attributes, §7) enter routing as **soft boosts/priors in the same weighted combination**,
never as gates. A hard-field match is binary by nature (a chunk is slack or isn't) but
enters as a boost: "in slack" lifts slack chunks, doesn't delete the rest.

Final chunk score = **weighted sum of (semantic propagation: facet·tag dot products) +
(structural hard-field match boosts)**. The interpreter produces both from the prompt: a
facet-relevance vector AND structural-constraint weights. This self-balances by the same
coefficient mechanism:
- "Show me PR #381" → semantic ~0, structural dominates (the hard field *is* the answer).
- "What were people worried about" → structural ~0, semantic dominates.
- "What did we decide in slack last quarter" → mixed: function + temporal facets blend
  with kind=slack + date-range boosts.

Hard fields' second job is non-retrieval: traceability + exact/aggregation queries ("how
many PRs merged in Q2").

### 14.6 Gate-vs-boost split by path

Resolved by **path, not UI** (scope-control UI was considered and rejected as
out-of-scope):
- **Retrieval (ranking) path → all boosts**, never gates.
- **Structured-query / aggregation path → exact** — a real gate, but only where a clean
  boolean exists ("count PRs in Q2"). This is a SQL-like query over the materialized
  fields, not retrieval ranking.

A gate is acceptable there only because it is (a) explicitly asserted, not
interpreter-inferred, and (b) exact at the altitude it filters (`kind=slack` is clean
per-chunk; a chunk *date* is a span, so date-exclusion belongs at the record/aggregation
altitude).

### 14.7 Prompt-side hard-field matching — deterministic pre-pass (revised 2026-06-12)

Before the LLM interpreter runs, match the raw prompt against the hard fields' **actual
values, read at query time through the field connections** — chunk attributes for
kinds/labels/ids, the raw metadata directories (via references) for names. **There is no
pre-embedded value vocabulary and no value-inventory artifact**: that would be a second
copy of the data outside the structure (references-not-copies violation, and a needless
GDPR surface). Never embed already-exact data.
- **exact literal match** (value appears verbatim and is a real field value, after
  case/spacing normalization) → high confidence → **strong** structural boost. Matched
  literals are **stripped before the interpreter** so topic isn't double-counted.
- **Non-exact mentions (decided 2026-06-12):** the interpreter carries NO corpus
  vocabularies (context costs; only tiny universal enums like kinds and answer shapes
  sit in its fixed contract). From language alone it flags what a token looks like
  (product-ish, person-ish) and whether it is wanted vs **excluded** ("apart from
  PitchForce, …" — excluded = no boost, never a removal). On a flagged miss, a **scoped
  string-distance lookup against that one directory only** (values read from raw via
  references) catches typos. The **interpreter is a one-shot flagger with no tools**
  (decided 2026-06-12): prompt in, flags out, nothing returns to the model —
  deterministic code runs the lookup, so query cost stays one model call and the
  contract is testable as a pure function. The flag→directory join is literal equality
  on the `kind` each directory declares in the mapping key (§8); a flag with no
  declared kind has no landing spot and rides the semantic layer, logged loudly.
  Described-not-named things ("the pitch tool") get no
  structural boost and ride the semantic layer — phrase tags carry names in context.
  Evidence: all 1,514 HERB questions are perfectly spelled with people referenced by
  role, while the product list holds deliberate near-twins (ContentForce/ContextForce,
  CollaborateForce/CollaborationForce, SearchFlow/SearchForce) — so blanket typo-fuzzy
  would conflate real products and is rejected; the exact layer is load-bearing.
- **Ambiguous matches = all candidates boosted**, confidence sets the boost size
  (exact-unique strongest → exact-but-ambiguous split across candidates →
  distance/interpreter-resolved weaker). The jump (§14.8) fires only on exact-unique.
- **Multiple hits in one prompt = boosts only (decided 2026-06-12).** Each hit
  contributes its boost; a chunk matching all hits collects them all and wins by
  addition — separate AND combined, for free, with no subjective "which one was meant".
  No multi-anchor jump machinery.
- **The pipeline embeds exactly one thing: phrase tags.** No field values, no
  descriptions, no raw chunks — a name's semantic reach lives in the contextual phrases
  that mention it, which are better vectors than any bare value.

This is the explicit-vs-inferred line as a **confidence gradient with no UI**, mapped onto
boost magnitude: a literal like "PitchForce" is matched as structure, not fuzzed into a
topic facet. Grounded in what's actually in the corpus — no hallucinated field values.

### 14.8 Three retrieval modes + anchored retrieval

An exact match that resolves to a **single anchor** (a file, a path subtree, an id — not
an entity node; those don't exist) doesn't just boost — it triggers a navigational
**jump**: scope to that anchor's path-prefix / attribute cohort → run the semantic
chunk-search **inside it first** → if thin, **WIDEN** (loud, automatic) to full
propagation. Three modes on a spectrum:
- **pure structured query** (exact only) — "count PRs in Q2"
- **anchored retrieval** (exact anchor narrows, semantics rank within) — "what did the
  PitchForce slack say about X"
- **pure fuzzy retrieval** (semantics; hard fields as boosts) — "what were people worried
  about"

"Check there first" is safe because it's a first pass with a loud widen, not a permanent
gate. Control flow stays **lean — explicitly not a "factory":** one deterministic branch
(exact single-anchor → jump) + one loud widen rule, reusing the existing engine (anchor
lookup = traversal over edges already built; search-within = the same combinator on a
narrowed candidate set). Not an LLM agent loop deciding *whether* to jump. Guards: only
exact single-anchor matches jump (fuzzy never jumps); the widen is loud and automatic when
the anchored pass is thin.

### 14.9 Symmetry (requirement stands; machinery dead — 2026-06-11)

The requirement is conceptual and stands: prompt-side and corpus-side must decompose
along comparable dimensions or they cannot be matched. The **embedding-axis-projection
machinery this section used to describe is dead** (it was never the user's design); the
model emits no numbers on either side, and the replacement mechanism is decided together
with the facet carriers. The embedder is chosen (§11: `llama-3.2-nv-embedqa-1b-v2`).

---

## 15. Open design items

Decided above; these remain open and are the next design work:
- **Allocation table → tagger prompt.** The §13.4 table and §13.5 specs must be encoded
  into the actual v2 tagger prompt (the per-facet spec v1 never had). **Status: drafted**
  — `v2_model_contracts.md` defines all three model contracts (tagger, interpreter,
  embedder) with concrete I/O schemas; its §5 lists the nine judgment calls awaiting
  sign-off (per-facet carriers, marked-spans-not-stripped, etc.). Open until signed off.
- **Combinator normalization + magnitude bound** (§14.3) — exact prompt-vector
  normalization and the bounded tag magnitude.
- **chain-bake** — how much is precomputed at index time vs computed at query time (edge
  weights are facts/precomputed; the prompt supplies only the relevance vector at query
  time).
- **chunk-cap calibration** (§9.1) — the cap is fixed by design (the tagger's effective
  focus span, seeded at ~3000 tokens); what's open is only the empirical sweep (chunk size
  vs tag relevance) to firm the number, which can run only once the v2 tagger and chunks
  exist.
- **Bonnier arm — DEFERRED (2026-06-13: the build is HERB-only for now).** When picked
  up again: the Bonnier (Swedish) mapping key is undrafted (the declarative-reuse claim
  stays unproven on a second dataset), the eval format is undecided (format-first), and
  the Swedish path (source-language tags, SEB-verified embedder) is designed but
  unexercised.

## 16. Build-time validation — catching tagger errors before a full run

Pairs with §9 (the deterministic chunker) and §12 (thesis eval). §12 measures the finished
product; this section is how the expensive tagging stage is validated *during the build*, so
a small error surfaces on the first chunks instead of after the whole corpus is tagged. The
felt dichotomy — "bulletproof everything, or run blind" — is false.

**The pipeline is two materials.** The deterministic prefix (probe → reference → structure →
chunk) is pure functions over sacred raw source: run it on the whole corpus for free (no LLM),
dump stage artifacts, eyeball, and lock a few inputs with golden tests. Robustness here is
cheap *because running is free*. The expensive, stochastic part is only the tagger — and its
output quality is an empirical unknown (the same unknown the §9.1 cap-calibration sweep
measures), so it cannot be reasoned to correctness in advance; it must be run and looked at. A
sample run is therefore not a compromise short of "bulletproof" — it is the method.

**The one design blocker** before any run is the tagger prompt + output contract (the
phrase-tag contract encoded into the actual prompt, the JSON the model returns — phrases
only, no description, no numbers). Everything else in §15 is either implementation or
*downstream of the run* (combinator and chain-bake are stage-6 retrieval; cap calibration
needs the run to exist).

**The expensive call's outputs are separable**, each with a different cheapest test
(description removed 2026-06-11 — the LLM-judge arm goes with it):
- **Tags** → data-quality assertions in code, no LLM (instant, N=1). The MUST-NOT rules
  (no employee-ids / dates / PR-numbers as concepts) and closed-vocab membership where a
  closed set applies are already an assertion list. This is the SPADE pattern —
  synthesised assertions catch a large fraction of failures with no model in the loop.
  Wire them as promptfoo assertions so every prompt edit re-runs them: that is the
  prompt-regression net.
- **Weights** (measured, never model-emitted) → no isolated unit test exists for "is this weight correct." Cheaply you assert
  only *invariants* (weights must discriminate — uniform weights across a chunk is a bug; a
  chunk plainly about X must outweigh a tangential one). Real weight validation is
  end-to-end — does a high-weight chunk rank up for the matching query on gold-100 — so the
  weighting is the one piece that needs a thin retrieve path standing as a *test instrument*
  earlier than §14's ordering implies.

**Error analysis precedes the assertions** (the most important activity in evals): run the
real tagger on ~20–40 chunks spanning content-kinds, read every output against its source,
journal, cluster into a failure taxonomy, count. The assertions above are *discovered by this
looking*, not specified up front. Rule of thumb ~100 traces to saturation.

**Statelessness is the precondition** (§9.5): every chunk is a fresh temp-0 call, so the only
variable across runs is the prompt — which is what makes golden tests, response-caching, the
small-sample read generalising, and prompt-regression all valid. None of it holds against a
stateful agent whose output is order- and history-dependent.

**Sample size — catching ≠ measuring.** A frequent bug is caught in ~30 draws (binomial: a
20%-prevalence error almost cannot hide in 30); *measuring* a rate with a tight interval needs
250–500 (Clopper–Pearson for an exact small-n bound). gold-100 is the ready-made
in-distribution gold set for the measurement arm; the ~30-trace read is for catching errors
while iterating.

**Time levers.** NIM is free — the real budget is wall-clock under the 40 RPM limiter, so
the levers are about not re-spending time: cache tagger responses keyed on chunk-hash +
prompt-version so a re-run only re-spends on what changed; shake out structural / vocab /
wiring bugs with a small fast model first (those bugs are model-independent — don't spend
the large model's latency finding a schema error); the corpus pass is the only long run
and happens once per prompt version that survives the sample reads. Fail loud throughout
(as everywhere in this design): the first bad input should halt, not be averaged away.

**The progression** (walking skeleton / tracer bullet): full pipeline on ONE input → full
pipeline on a per-content-kind stratified sample (look here) → full corpus last. Corpus
breadth is the rollout dial, not the smoketest.

References: [Husain — error analysis in LLM evals](https://hamel.dev/blog/posts/evals-faq/why-is-error-analysis-so-important-in-llm-evals-and-how-is-it-performed.html) ·
[Shankar et al., *Who Validates the Validators?* (UIST 2024)](https://people.eecs.berkeley.edu/~bjoern/papers/shankar-validators-uist2024.pdf) ·
[SPADE — data-quality assertions for LLM pipelines (arXiv 2401.03038)](https://arxiv.org/abs/2401.03038) ·
[promptfoo — assertions / output validation](https://www.promptfoo.dev/docs/configuration/expected-outputs/) ·
[proxy-model smoke-testing (Google Cloud)](https://cloud.google.com/blog/products/data-analytics/more-than-100x-faster-and-cheaper-llm-powered-sql-queries-with-proxy-models) ·
[applying statistics to LLM evals — sample size / Clopper–Pearson (Wolfe)](https://cameronrwolfe.substack.com/p/stats-llm-evals)
