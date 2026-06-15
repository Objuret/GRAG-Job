# Graph Report - .  (2026-06-15)

## Corpus Check
- 41 files · ~34,688 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 329 nodes · 474 edges · 48 communities (17 shown, 31 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 44 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Settings|Settings]]
- [[_COMMUNITY___main__.py|__main__.py]]
- [[_COMMUNITY_CLAUDE.md — project instructions  sessi...|CLAUDE.md — project instructions / sessi...]]
- [[_COMMUNITY_sql_agent.py|sql_agent.py]]
- [[_COMMUNITY_Facets as parallel relevance channels (t...|Facets as parallel relevance channels (t...]]
- [[_COMMUNITY_OPEN how a single phrase's per-facet re...|OPEN: how a single phrase's per-facet re...]]
- [[_COMMUNITY_utils.py|utils.py]]
- [[_COMMUNITY_Handoff v2 chunking model design (2026-...|Handoff: v2 chunking model design (2026-...]]
- [[_COMMUNITY_scan_dataset()|scan_dataset()]]
- [[_COMMUNITY_derive_corpus()|derive_corpus()]]
- [[_COMMUNITY_resolver_prototype.py|resolver_prototype.py]]
- [[_COMMUNITY_nvidia_connectivity_test.py|nvidia_connectivity_test.py]]
- [[_COMMUNITY_load_module()|load_module()]]
- [[_COMMUNITY_Per-facet weights ride ONE chunk-tag edg...|Per-facet weights ride ONE chunk-tag edg...]]
- [[_COMMUNITY_measure_pointers.py|measure_pointers.py]]
- [[_COMMUNITY_Routing sums per-facet channels weighted...|Routing sums per-facet channels weighted...]]
- [[_COMMUNITY_Retriever routing = weighted activation...|Retriever routing = weighted activation...]]
- [[_COMMUNITY_v2 requirements.txt|v2 requirements.txt]]
- [[_COMMUNITY_error_class.py|error_class.py]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY_Defect chunker discards source timestam...|Defect: chunker discards source timestam...]]
- [[_COMMUNITY_Doc drift graph_schema.md claims NEXTR...|Doc drift: graph_schema.md claims NEXT/R...]]
- [[_COMMUNITY_Defect ~18% of tags are literal IDsdat...|Defect: ~18% of tags are literal IDs/dat...]]
- [[_COMMUNITY_Infra Neo4j data moved to A, herb-eval...|Infra: Neo4j data moved to A:, herb-eval...]]
- [[_COMMUNITY_Pattern-delete junk tags via anchored re...|Pattern-delete junk tags via anchored re...]]
- [[_COMMUNITY_Defect relevance_to_file calibrated too...|Defect: relevance_to_file calibrated too...]]
- [[_COMMUNITY_Defect 23 tags silently unembedded (des...|Defect: 23 tags silently unembedded (des...]]
- [[_COMMUNITY_Finding w_facet is categorical (~9-valu...|Finding: w_facet is categorical (~9-valu...]]
- [[_COMMUNITY_Defect c.years back-projected from temp...|Defect: c.years back-projected from temp...]]
- [[_COMMUNITY_Reference triple {file_id, scheme, addre...|Reference triple {file_id, scheme, addre...]]
- [[_COMMUNITY_Shape probe (dataset-agnostic, recovers...|Shape probe (dataset-agnostic, recovers...]]
- [[_COMMUNITY_v1 preserved (tag artefact-v1 @244beb7,...|v1 preserved (tag artefact-v1 @244beb7,...]]
- [[_COMMUNITY_Anchoring reduction 85% single-pass to 1...|Anchoring reduction 85% single-pass to 1...]]
- [[_COMMUNITY_Fewer, richer phrase-level tags with con...|Fewer, richer phrase-level tags with con...]]
- [[_COMMUNITY_v1 w_chunk derivation (strength x covera...|v1 w_chunk derivation (strength x covera...]]
- [[_COMMUNITY_Axisprojection weight apparatus (SemAxi...|Axis/projection weight apparatus (SemAxi...]]
- [[_COMMUNITY_Interpreter contract one toolless LLM c...|Interpreter contract: one toolless LLM c...]]
- [[_COMMUNITY_Linguistics belongs to the interpreter (...|Linguistics belongs to the interpreter (...]]
- [[_COMMUNITY_Cross-chunk linking by phrase-embedding...|Cross-chunk linking by phrase-embedding...]]
- [[_COMMUNITY_Sibling centrality tag's relational val...|Sibling centrality: tag's relational val...]]
- [[_COMMUNITY_Swedish FrameNet (SweFN) frame-semantics...|Swedish FrameNet (SweFN) frame-semantics...]]
- [[_COMMUNITY_Ambiguity rule all candidates boosted,...|Ambiguity rule: all candidates boosted,...]]
- [[_COMMUNITY_HERB product twins (ContentForceContext...|HERB product twins (ContentForce/Context...]]
- [[_COMMUNITY_Literal-matching pipeline exact+normali...|Literal-matching pipeline: exact+normali...]]
- [[_COMMUNITY_Multi-hit rule multiple hard-field hits...|Multi-hit rule: multiple hard-field hits...]]
- [[_COMMUNITY_No corpus vocabulary in the interpreter'...|No corpus vocabulary in the interpreter'...]]
- [[_COMMUNITY_exjobbet Artefact Monorepo|exjobbet Artefact Monorepo]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 20 edges
2. `profile()` - 15 edges
3. `retrieve_baseline_content()` - 12 edges
4. `retrieve_baseline_vector()` - 11 edges
5. `derive_corpus()` - 10 edges
6. `run_question()` - 9 edges
7. `scan_dataset()` - 9 edges
8. `CLAUDE.md — project instructions / session entry point` - 9 edges
9. `Handoff: v2 chunking model design (2026-06-03)` - 9 edges
10. `cmd_probe()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `v2 pipeline scan to probe to reference to structure to tag to retrieve` --conceptually_related_to--> `v2 pipeline CLI.    python -m v2 derive-corpus <raw-dataset-dir> -> <data>/corpu`  [INFERRED]
  handoff/exjobbet-monorepo/2026-05-31-v2-artefact-rebuild-and-facet-design.md → v2/backend/v2/__main__.py
- `v2 tagger host = NVIDIA NIM (forever-free 40 RPM, rate-limiter required)` --references--> `NVIDIA NIM connectivity + model benchmark.  Reads the API key from backend/.env`  [EXTRACTED]
  handoff/exjobbet-monorepo/2026-05-31-v2-artefact-rebuild-and-facet-design.md → v2/.work/nvidia_connectivity_test.py
- `Keystone implementation = reference resolver (resolve + hash-verify + fail-loud)` --references--> `v2 reference-resolver prototype — proves the 'graph is references' stance.  A re`  [EXTRACTED]
  handoff/exjobbet-monorepo/2026-05-31-v2-artefact-rebuild-and-facet-design.md → v2/.work/resolver_prototype.py
- `derive-corpus stage 0: structural eval quarantine, one corpus view only` --references--> `One-time prep: derive the corpus view a dataset's pipeline run scans.  The publi`  [EXTRACTED]
  state/exjobbet/2026-06-14-v2-facets-as-relevance-channels.md → v2/backend/v2/derive_corpus.py
- `First v2 pipeline slice built: scan + probe stages, 12 tests green` --references--> `Stage 2: probe — recover the structural schema from shape. Meaning-free.  Profil`  [EXTRACTED]
  state/exjobbet/2026-06-11-v2-facet-carriers-and-build-gate.md → v2/backend/v2/probe.py

## Import Cycles
- 1-file cycle: `v2/backend/shared/utils.py -> v2/backend/shared/utils.py`

## Communities (48 total, 31 thin omitted)

### Community 0 - "Settings"
Cohesion: 0.08
Nodes (35): AsyncSession, exclusion_clause(), neo4j_session(), normalize_limit(), Shared helpers for v2 Neo4j baseline retrievers., RetrievedChunk, row_to_chunk(), sanitize_lucene() (+27 more)

### Community 1 - "__main__.py"
Cohesion: 0.10
Nodes (37): v2 pipeline scan to probe to reference to structure to tag to retrieve, Namespace, resolve_data_root(), Golden tests for the shape probe — the deterministic prefix is cheap to lock dow, test_array_fuses_elements(), test_candidates_collections_and_docleaves(), test_cross_file_fusion_marks_optional_and_merges_lengths(), test_empty_array_fuses_with_populated() (+29 more)

### Community 2 - "CLAUDE.md — project instructions / sessi..."
Cohesion: 0.07
Nodes (32): Eval oracle (answerable/unanswerable_questions) must be holdout, not corpus, Per-dataset declarative settings-file key (cross-refs + identity only), State doc 2026-06-09: weight production measure-not-emit, Design-before-build gate: no pipeline code until the stage's design is signed off, State doc 2026-06-11: v2 facet carriers and build gate, State doc 2026-06-12: v2 graph spine and literal matching, Docs reconciliation by removal not banners: dead content deleted, tombstones only to block revival, Field handling follows value shape (dates to time-range, id-shaped to id-sets, few-distinct to labels, names raw-only, long text to content); finalize at mapping key (+24 more)

### Community 3 - "sql_agent.py"
Cohesion: 0.12
Nodes (28): AgentRun, build_sqlite(), _chat(), execute_sql(), _format_rows(), _load_product(), main(), _question_records() (+20 more)

### Community 4 - "Facets as parallel relevance channels (t..."
Cohesion: 0.08
Nodes (24): Cheap zero-LLM cleanup plan (chunker+materialize+pattern-delete+docs), Handoff: graph-RAG artefact audit + cleanup plan (2026-05-25), Live herb-eval graph audit (4 labels, 3 edge types, no NEXT/Run), Bake combinator decision (multiplication rejected), Handoff: graph-RAG retrieval pipeline redesign (2026-05-25), No weight synthesis at query time, Recall to filter to rank to cap retrieval shape, 7-factor multiplicative scoreCypher (rejected synthesis) (+16 more)

### Community 5 - "OPEN: how a single phrase's per-facet re..."
Cohesion: 0.11
Nodes (20): Three baked weight layers (relevance_to_file / w_chunk / w_facet), v1 facets underspecified -> degraded into token-extraction (~18% junk), Combinator: prompt-conditioned weighted dot product, accumulation not max, Anisotropic cosine on this corpus (collapses to ~0.8 band), An LLM cannot emit correct weights (v1 evidence: 85% round-number anchoring), Measure, don't emit: geometry produces weights, model never emits a number, Tag-vs-description embedding distance as a relevance signal (later killed), Chunk description killed: union of phrase tags IS the chunk content (+12 more)

### Community 6 - "utils.py"
Cohesion: 0.24
Nodes (15): datetime, compare_hash_maps(), deep_merge(), ensure_dir(), find_latest_run_id(), hash_tree(), iso_utc(), make_json_safe() (+7 more)

### Community 7 - "Handoff: v2 chunking model design (2026-..."
Cohesion: 0.13
Nodes (16): Chunk as coherent episode, not fixed-size window, COVERS edge joining record references to chunks, Deterministic boundary seam-finder (no embeddings, no LLM), Handoff: v2 chunking model design (2026-06-03), Materialized path index as integer components, No chunk overlap (protects references-not-copies), Subchunks share path prefix, no parent node, Records-vs-prose is per-position in the tree (+8 more)

### Community 8 - "scan_dataset()"
Cohesion: 0.24
Nodes (13): First v2 pipeline slice built: scan + probe stages, 12 tests green, test_scan_dataset_skips_cache_dirs_and_fails_on_broken_json(), test_scan_empty_dataset_fails_loud(), test_scan_file_identity_and_format(), Path, Stage 2: probe — recover the structural schema from shape. Meaning-free.  Profil, FileRecord, _hash_file() (+5 more)

### Community 9 - "derive_corpus()"
Cohesion: 0.32
Nodes (10): _full_product(), _make_raw(), test_corpus_view_strips_rag_unsafe_keys_and_copies_rest_verbatim(), test_dataset_without_strip_keys_fails_loud(), test_partial_strip_keys_fail_loud(), test_requires_raw_working_root(), Path, derive_corpus() (+2 more)

### Community 10 - "resolver_prototype.py"
Cohesion: 0.31
Nodes (10): Keystone implementation = reference resolver (resolve + hash-verify + fail-loud), Path, json_pointer(), main(), v2 reference-resolver prototype — proves the 'graph is references' stance.  A re, RFC 6901. Raises (loud) on any miss — never returns a silent default., ref = {file_path, sha256, scheme, address}. Fail loud on hash mismatch., resolve() (+2 more)

### Community 11 - "nvidia_connectivity_test.py"
Cohesion: 0.40
Nodes (5): v2 tagger host = NVIDIA NIM (forever-free 40 RPM, rate-limiter required), Path, main(), parse_env(), NVIDIA NIM connectivity + model benchmark.  Reads the API key from backend/.env

### Community 12 - "load_module()"
Cohesion: 0.47
Nodes (5): load_module(), Load Python modules archived under quarantine/legacy_mirror/backend/., Load ``quarantine/legacy_mirror/backend/<relative_parts>`` as a one-off module., _repo_root(), Path

### Community 13 - "Per-facet weights ride ONE chunk-tag edg..."
Cohesion: 0.40
Nodes (5): All facet weights on the same chunk-tag edge, not one edge per facet, Three v2 edge weights (chunk-file, chunk-tag, tag-facet), Node/edge split: intrinsic per-phrase value on node, sibling-relational value on edge, Chunk-file relevance weight DEAD (containment edge carries no number; coherence chunking solves filler demotion), Per-facet weights ride ONE chunk-tag edge (a facet vector)

### Community 14 - "measure_pointers.py"
Cohesion: 0.70
Nodes (4): analyze(), load_env(), main(), mb()

### Community 15 - "Routing sums per-facet channels weighted..."
Cohesion: 0.67
Nodes (3): Combinator = prompt-conditioned weighted dot product (accumulate not max), Asked-for vs given split: rank by requested dimension, narrow by presupposed scope (no numeric prompt emphasis), Routing sums per-facet channels weighted by prompt's per-facet emphasis

## Knowledge Gaps
- **40 isolated node(s):** `Path`, `Path`, `Cursor`, `Path`, `v2 requirements-lock.txt` (+35 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `One-time prep: derive the corpus view a dataset's pipeline run scans.  The publi` connect `CLAUDE.md — project instructions / sessi...` to `derive_corpus()`?**
  _High betweenness centrality (0.231) - this node is a cross-community bridge._
- **Why does `State doc 2026-06-14: facets as parallel relevance channels` connect `CLAUDE.md — project instructions / sessi...` to `Facets as parallel relevance channels (t...`, `OPEN: how a single phrase's per-facet re...`?**
  _High betweenness centrality (0.230) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `Settings` (e.g. with `AsyncSession` and `RetrievedChunk`) actually correct?**
  _`Settings` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Path`, `RFC 6901. Raises (loud) on any miss — never returns a silent default.`, `ref = {file_path, sha256, scheme, address}. Fail loud on hash mismatch.` to the rest of the system?**
  _123 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Settings` be split into smaller, more focused modules?**
  _Cohesion score 0.07686274509803921 - nodes in this community are weakly interconnected._
- **Should `__main__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10121951219512196 - nodes in this community are weakly interconnected._
- **Should `CLAUDE.md — project instructions / sessi...` be split into smaller, more focused modules?**
  _Cohesion score 0.07459677419354839 - nodes in this community are weakly interconnected._