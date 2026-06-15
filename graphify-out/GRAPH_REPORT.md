# Graph Report - .  (2026-06-14)

## Corpus Check
- 41 files · ~34,268 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 332 nodes · 466 edges · 54 communities (20 shown, 34 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 50 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY___main__.py|__main__.py]]
- [[_COMMUNITY_CLAUDE.md — project instructions  sessi...|CLAUDE.md — project instructions / sessi...]]
- [[_COMMUNITY_vector.py|vector.py]]
- [[_COMMUNITY_sql_agent.py|sql_agent.py]]
- [[_COMMUNITY_Settings|Settings]]
- [[_COMMUNITY_Handoff graph-RAG retrieval pipeline re...|Handoff: graph-RAG retrieval pipeline re...]]
- [[_COMMUNITY_utils.py|utils.py]]
- [[_COMMUNITY_derive_corpus()|derive_corpus()]]
- [[_COMMUNITY_Handoff v2 chunking model design (2026-...|Handoff: v2 chunking model design (2026-...]]
- [[_COMMUNITY_scan_dataset()|scan_dataset()]]
- [[_COMMUNITY_HERB mapping key (Salesforce__HERB.yaml)|HERB mapping key (Salesforce__HERB.yaml)]]
- [[_COMMUNITY_resolver_prototype.py|resolver_prototype.py]]
- [[_COMMUNITY_nvidia_connectivity_test.py|nvidia_connectivity_test.py]]
- [[_COMMUNITY_load_module()|load_module()]]
- [[_COMMUNITY_measure_pointers.py|measure_pointers.py]]
- [[_COMMUNITY_Routing sums per-facet channels weighted...|Routing sums per-facet channels weighted...]]
- [[_COMMUNITY_Facets as parallel same-facet comparison...|Facets as parallel same-facet comparison...]]
- [[_COMMUNITY_Per-facet weights live on ONE chunk-tag...|Per-facet weights live on ONE chunk-tag...]]
- [[_COMMUNITY_REJECTED comparing a tag's embedding to...|REJECTED: comparing a tag's embedding to...]]
- [[_COMMUNITY_Three v2 edge weights (chunk-file, chunk...|Three v2 edge weights (chunk-file, chunk...]]
- [[_COMMUNITY_Interpreter contract one toolless LLM c...|Interpreter contract: one toolless LLM c...]]
- [[_COMMUNITY_Each facet gets its own unique weight-pr...|Each facet gets its own unique weight-pr...]]
- [[_COMMUNITY_v2 requirements.txt|v2 requirements.txt]]
- [[_COMMUNITY_error_class.py|error_class.py]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY_Defect chunker discards source timestam...|Defect: chunker discards source timestam...]]
- [[_COMMUNITY_Doc drift graph_schema.md claims NEXTR...|Doc drift: graph_schema.md claims NEXT/R...]]
- [[_COMMUNITY_Infra Neo4j data moved to A, herb-eval...|Infra: Neo4j data moved to A:, herb-eval...]]
- [[_COMMUNITY_Pattern-delete junk tags via anchored re...|Pattern-delete junk tags via anchored re...]]
- [[_COMMUNITY_Defect relevance_to_file calibrated too...|Defect: relevance_to_file calibrated too...]]
- [[_COMMUNITY_Defect 23 tags silently unembedded (des...|Defect: 23 tags silently unembedded (des...]]
- [[_COMMUNITY_Three baked weight layers (relevance_to_...|Three baked weight layers (relevance_to_...]]
- [[_COMMUNITY_Finding w_facet is categorical (~9-valu...|Finding: w_facet is categorical (~9-valu...]]
- [[_COMMUNITY_Defect c.years back-projected from temp...|Defect: c.years back-projected from temp...]]
- [[_COMMUNITY_Combinator = prompt-conditioned weighted...|Combinator = prompt-conditioned weighted...]]
- [[_COMMUNITY_Reference triple {file_id, scheme, addre...|Reference triple {file_id, scheme, addre...]]
- [[_COMMUNITY_Shape probe (dataset-agnostic, recovers...|Shape probe (dataset-agnostic, recovers...]]
- [[_COMMUNITY_v1 preserved (tag artefact-v1 @244beb7,...|v1 preserved (tag artefact-v1 @244beb7,...]]
- [[_COMMUNITY_Anchoring reduction 85% single-pass to 1...|Anchoring reduction 85% single-pass to 1...]]
- [[_COMMUNITY_Fewer, richer phrase-level tags with con...|Fewer, richer phrase-level tags with con...]]
- [[_COMMUNITY_Anisotropic cosine on this corpus (colla...|Anisotropic cosine on this corpus (colla...]]
- [[_COMMUNITY_v1 w_chunk derivation (strength x covera...|v1 w_chunk derivation (strength x covera...]]
- [[_COMMUNITY_Asked-for vs given split rank by reques...|Asked-for vs given split: rank by reques...]]
- [[_COMMUNITY_Linguistics belongs to the interpreter (...|Linguistics belongs to the interpreter (...]]
- [[_COMMUNITY_Cross-chunk linking by phrase-embedding...|Cross-chunk linking by phrase-embedding...]]
- [[_COMMUNITY_Sibling centrality tag's relational val...|Sibling centrality: tag's relational val...]]
- [[_COMMUNITY_Swedish FrameNet (SweFN) frame-semantics...|Swedish FrameNet (SweFN) frame-semantics...]]
- [[_COMMUNITY_Ambiguity rule all candidates boosted,...|Ambiguity rule: all candidates boosted,...]]
- [[_COMMUNITY_One embedding surface embed phrase tags...|One embedding surface: embed phrase tags...]]
- [[_COMMUNITY_HERB product twins (ContentForceContext...|HERB product twins (ContentForce/Context...]]
- [[_COMMUNITY_Literal-matching pipeline exact+normali...|Literal-matching pipeline: exact+normali...]]
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
- `derive-corpus stage 0: strips RAG-unsafe keys (answerable/unanswerable_questions, team, customers) into one corpus view; raw untouched` --references--> `One-time prep: derive the corpus view a dataset's pipeline run scans.  The publi`  [EXTRACTED]
  state/exjobbet/2026-06-14-v2-facets-as-relevance-channels.md → v2/backend/v2/derive_corpus.py
- `First v2 pipeline slice built: scan + probe stages, 12 tests green` --references--> `Stage 2: probe — recover the structural schema from shape. Meaning-free.  Profil`  [EXTRACTED]
  state/exjobbet/2026-06-11-v2-facet-carriers-and-build-gate.md → v2/backend/v2/probe.py

## Import Cycles
- 1-file cycle: `v2/backend/shared/utils.py -> v2/backend/shared/utils.py`

## Communities (54 total, 34 thin omitted)

### Community 0 - "__main__.py"
Cohesion: 0.11
Nodes (35): v2 pipeline scan to probe to reference to structure to tag to retrieve, Namespace, Golden tests for the shape probe — the deterministic prefix is cheap to lock dow, test_array_fuses_elements(), test_candidates_collections_and_docleaves(), test_cross_file_fusion_marks_optional_and_merges_lengths(), test_empty_array_fuses_with_populated(), test_pointer_escaping() (+27 more)

### Community 1 - "CLAUDE.md — project instructions / sessi..."
Cohesion: 0.07
Nodes (32): Defect: ~18% of tags are literal IDs/dates, not concepts, v1 facets underspecified -> degraded into token-extraction (~18% junk), An LLM cannot emit correct weights (v1 evidence: 85% round-number anchoring), Measure, don't emit: geometry produces weights, model never emits a number, Tag-vs-description embedding distance as a relevance signal (later killed), Chunk description killed: union of phrase tags IS the chunk content, Design-before-build gate: no pipeline code until the stage's design is signed off, Phrase tag IS the node: per-chunk contextual phrase + embedding, no bare-word shared nodes, no synonym merge (+24 more)

### Community 2 - "vector.py"
Cohesion: 0.15
Nodes (25): exclusion_clause(), neo4j_session(), normalize_limit(), Shared helpers for v2 Neo4j baseline retrievers., RetrievedChunk, row_to_chunk(), sanitize_lucene(), validate_dataset() (+17 more)

### Community 3 - "sql_agent.py"
Cohesion: 0.12
Nodes (28): AgentRun, build_sqlite(), _chat(), execute_sql(), _format_rows(), _load_product(), main(), _question_records() (+20 more)

### Community 4 - "Settings"
Cohesion: 0.10
Nodes (12): AsyncSession, BaseSettings, Settings, Path constants + runtime settings loaded from .env., # NOTE: the working endpoint is the `integrate.` subdomain; plain, Runtime settings. Loaded from backend/.env and overridable by env vars., resolve_data_root(), Settings (+4 more)

### Community 5 - "Handoff: graph-RAG retrieval pipeline re..."
Cohesion: 0.10
Nodes (21): Cheap zero-LLM cleanup plan (chunker+materialize+pattern-delete+docs), Handoff: graph-RAG artefact audit + cleanup plan (2026-05-25), Live herb-eval graph audit (4 labels, 3 edge types, no NEXT/Run), Bake combinator decision (multiplication rejected), Handoff: graph-RAG retrieval pipeline redesign (2026-05-25), No weight synthesis at query time, Recall to filter to rank to cap retrieval shape, 7-factor multiplicative scoreCypher (rejected synthesis) (+13 more)

### Community 6 - "utils.py"
Cohesion: 0.24
Nodes (15): datetime, compare_hash_maps(), deep_merge(), ensure_dir(), find_latest_run_id(), hash_tree(), iso_utc(), make_json_safe() (+7 more)

### Community 7 - "derive_corpus()"
Cohesion: 0.21
Nodes (14): Eval oracle (answerable/unanswerable_questions) must be holdout, not corpus, derive-corpus stage 0: strips RAG-unsafe keys (answerable/unanswerable_questions, team, customers) into one corpus view; raw untouched, Eval quarantine must be STRUCTURAL not declarative: corpus physically lacks the oracle; harness reads oracle in place from raw, _full_product(), _make_raw(), test_corpus_view_strips_rag_unsafe_keys_and_copies_rest_verbatim(), test_dataset_without_strip_keys_fails_loud(), test_partial_strip_keys_fail_loud() (+6 more)

### Community 8 - "Handoff: v2 chunking model design (2026-..."
Cohesion: 0.13
Nodes (16): Chunk as coherent episode, not fixed-size window, COVERS edge joining record references to chunks, Deterministic boundary seam-finder (no embeddings, no LLM), Handoff: v2 chunking model design (2026-06-03), Materialized path index as integer components, No chunk overlap (protects references-not-copies), Subchunks share path prefix, no parent node, Records-vs-prose is per-position in the tree (+8 more)

### Community 9 - "scan_dataset()"
Cohesion: 0.24
Nodes (13): First v2 pipeline slice built: scan + probe stages, 12 tests green, test_scan_dataset_skips_cache_dirs_and_fails_on_broken_json(), test_scan_empty_dataset_fails_loud(), test_scan_file_identity_and_format(), Path, Stage 2: probe — recover the structural schema from shape. Meaning-free.  Profil, FileRecord, _hash_file() (+5 more)

### Community 10 - "HERB mapping key (Salesforce__HERB.yaml)"
Cohesion: 0.22
Nodes (11): Per-dataset declarative settings-file key (cross-refs + identity only), State doc 2026-06-09: weight production measure-not-emit, State doc 2026-06-11: v2 facet carriers and build gate, State doc 2026-06-12: v2 graph spine and literal matching, Field handling follows value shape (dates to time-range, id-shaped to id-sets, few-distinct to labels, names raw-only, long text to content); finalize at mapping key, Multi-hop via id-joins through chunk attributes + raw directory reads (entity-node bridges impossible without entity nodes), State doc 2026-06-14: v2 facets as parallel relevance channels, HERB mapping key (Salesforce__HERB.yaml) (+3 more)

### Community 11 - "resolver_prototype.py"
Cohesion: 0.31
Nodes (10): Keystone implementation = reference resolver (resolve + hash-verify + fail-loud), Path, json_pointer(), main(), v2 reference-resolver prototype — proves the 'graph is references' stance.  A re, RFC 6901. Raises (loud) on any miss — never returns a silent default., ref = {file_path, sha256, scheme, address}. Fail loud on hash mismatch., resolve() (+2 more)

### Community 12 - "nvidia_connectivity_test.py"
Cohesion: 0.40
Nodes (5): v2 tagger host = NVIDIA NIM (forever-free 40 RPM, rate-limiter required), Path, main(), parse_env(), NVIDIA NIM connectivity + model benchmark.  Reads the API key from backend/.env

### Community 13 - "load_module()"
Cohesion: 0.47
Nodes (5): load_module(), Load Python modules archived under quarantine/legacy_mirror/backend/., Load ``quarantine/legacy_mirror/backend/<relative_parts>`` as a one-off module., _repo_root(), Path

### Community 14 - "measure_pointers.py"
Cohesion: 0.70
Nodes (4): analyze(), load_env(), main(), mb()

### Community 15 - "Routing sums per-facet channels weighted..."
Cohesion: 0.50
Nodes (4): Retriever routing = weighted activation propagation, no hard filters, Combinator: prompt-conditioned weighted dot product, accumulation not max, Multi-hit rule: multiple hard-field hits = additive boosts only, no multi-anchor jump, Routing sums per-facet channels weighted by prompt's per-facet emphasis (combinator math still open)

### Community 16 - "Facets as parallel same-facet comparison..."
Cohesion: 0.50
Nodes (4): All facets are evaluations: each facet weight = how much of that facet the tag carries, Facets dual-purpose: narrowing entry into corpus + prompt-priced weight modifier, Research backing: multidimensional relevance + multi-aspect dense retrieval do per-facet decomposition + same-facet matching + aggregation, Facets as parallel same-facet comparison channels (topic to topic, stance to stance)

### Community 17 - "Per-facet weights live on ONE chunk-tag..."
Cohesion: 0.67
Nodes (3): All facet weights on the same chunk-tag edge, not one edge per facet, Node/edge split: intrinsic per-phrase value on node, sibling-relational value on edge, Per-facet weights live on ONE chunk-tag edge carrying the whole facet vector

### Community 18 - "REJECTED: comparing a tag's embedding to..."
Cohesion: 0.67
Nodes (3): Axis/projection weight apparatus (SemAxis, pole words) is DEAD, Polarity does not survive embedding similarity; stance direction must be explicit text/label, REJECTED: comparing a tag's embedding to an abstract facet's embedding; matching is same-facet content-to-content

## Knowledge Gaps
- **43 isolated node(s):** `Path`, `Path`, `Cursor`, `Path`, `v2 requirements-lock.txt` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **34 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Settings` to `__main__.py`, `vector.py`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `datetime` connect `utils.py` to `sql_agent.py`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `derive_corpus()` connect `derive_corpus()` to `__main__.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `Settings` (e.g. with `AsyncSession` and `RetrievedChunk`) actually correct?**
  _`Settings` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Path`, `RFC 6901. Raises (loud) on any miss — never returns a silent default.`, `ref = {file_path, sha256, scheme, address}. Fail loud on hash mismatch.` to the rest of the system?**
  _126 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `__main__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10931174089068826 - nodes in this community are weakly interconnected._
- **Should `CLAUDE.md — project instructions / sessi...` be split into smaller, more focused modules?**
  _Cohesion score 0.07056451612903226 - nodes in this community are weakly interconnected._