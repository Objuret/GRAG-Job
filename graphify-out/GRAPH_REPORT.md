# Graph Report - .  (2026-06-23)

## Corpus Check
- 28 files · ~30,726 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 312 nodes · 383 edges · 52 communities (16 shown, 36 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 92 edges (avg confidence: 0.76)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_lucene.py|lucene.py]]
- [[_COMMUNITY_State doc 2026-06-18 v3 evaluation harn...|State doc 2026-06-18: v3 evaluation harn...]]
- [[_COMMUNITY_orchestrator.py|orchestrator.py]]
- [[_COMMUNITY_Facets as parallel relevance channels (t...|Facets as parallel relevance channels (t...]]
- [[_COMMUNITY_ragas.py|ragas.py]]
- [[_COMMUNITY_contract.py|contract.py]]
- [[_COMMUNITY_State doc 2026-06-14 facets as parallel...|State doc 2026-06-14: facets as parallel...]]
- [[_COMMUNITY_Handoff v2 chunking model design (2026-...|Handoff: v2 chunking model design (2026-...]]
- [[_COMMUNITY_artifact.py|artifact.py]]
- [[_COMMUNITY_nim.py|nim.py]]
- [[_COMMUNITY_Rejected tag-embedding vs abstract-face...|Rejected: tag-embedding vs abstract-face...]]
- [[_COMMUNITY_ragas_catalog.py|ragas_catalog.py]]
- [[_COMMUNITY_smoke.py|smoke.py]]
- [[_COMMUNITY_Per-facet weights ride ONE chunk-tag edg...|Per-facet weights ride ONE chunk-tag edg...]]
- [[_COMMUNITY_build_questions.py|build_questions.py]]
- [[_COMMUNITY_Routing sums per-facet channels weighted...|Routing sums per-facet channels weighted...]]
- [[_COMMUNITY_Defect chunker discards source timestam...|Defect: chunker discards source timestam...]]
- [[_COMMUNITY_Doc drift graph_schema.md claims NEXTR...|Doc drift: graph_schema.md claims NEXT/R...]]
- [[_COMMUNITY_Defect ~18% of tags are literal IDsdat...|Defect: ~18% of tags are literal IDs/dat...]]
- [[_COMMUNITY_Infra Neo4j data moved to A, herb-eval...|Infra: Neo4j data moved to A:, herb-eval...]]
- [[_COMMUNITY_Pattern-delete junk tags via anchored re...|Pattern-delete junk tags via anchored re...]]
- [[_COMMUNITY_Defect relevance_to_file calibrated too...|Defect: relevance_to_file calibrated too...]]
- [[_COMMUNITY_Defect 23 tags silently unembedded (des...|Defect: 23 tags silently unembedded (des...]]
- [[_COMMUNITY_Finding w_facet is categorical (~9-valu...|Finding: w_facet is categorical (~9-valu...]]
- [[_COMMUNITY_Defect c.years back-projected from temp...|Defect: c.years back-projected from temp...]]
- [[_COMMUNITY_Per-dataset declarative settings-file ke...|Per-dataset declarative settings-file ke...]]
- [[_COMMUNITY_v2 tagger host = NVIDIA NIM (forever-fre...|v2 tagger host = NVIDIA NIM (forever-fre...]]
- [[_COMMUNITY_Keystone implementation = reference reso...|Keystone implementation = reference reso...]]
- [[_COMMUNITY_Reference triple {file_id, scheme, addre...|Reference triple {file_id, scheme, addre...]]
- [[_COMMUNITY_Shape probe (dataset-agnostic, recovers...|Shape probe (dataset-agnostic, recovers...]]
- [[_COMMUNITY_v1 preserved (tag artefact-v1 @244beb7,...|v1 preserved (tag artefact-v1 @244beb7,...]]
- [[_COMMUNITY_v2 pipeline scan to probe to reference t...|v2 pipeline scan to probe to reference t...]]
- [[_COMMUNITY_Anchoring reduction 85% single-pass to 1...|Anchoring reduction 85% single-pass to 1...]]
- [[_COMMUNITY_Fewer, richer phrase-level tags with con...|Fewer, richer phrase-level tags with con...]]
- [[_COMMUNITY_v1 w_chunk derivation (strength x covera...|v1 w_chunk derivation (strength x covera...]]
- [[_COMMUNITY_Axisprojection weight apparatus (SemAxi...|Axis/projection weight apparatus (SemAxi...]]
- [[_COMMUNITY_Interpreter contract one toolless LLM c...|Interpreter contract: one toolless LLM c...]]
- [[_COMMUNITY_Linguistics belongs to the interpreter (...|Linguistics belongs to the interpreter (...]]
- [[_COMMUNITY_Cross-chunk linking by phrase-embedding...|Cross-chunk linking by phrase-embedding...]]
- [[_COMMUNITY_First v2 pipeline slice built scan + pr...|First v2 pipeline slice built: scan + pr...]]
- [[_COMMUNITY_Sibling centrality tag's relational val...|Sibling centrality: tag's relational val...]]
- [[_COMMUNITY_Swedish FrameNet (SweFN) frame-semantics...|Swedish FrameNet (SweFN) frame-semantics...]]
- [[_COMMUNITY_Ambiguity rule all candidates boosted,...|Ambiguity rule: all candidates boosted,...]]
- [[_COMMUNITY_Docs reconciliation by removal not banne...|Docs reconciliation by removal not banne...]]
- [[_COMMUNITY_Field handling follows value shape (date...|Field handling follows value shape (date...]]
- [[_COMMUNITY_Hard fields are indexed chunk attributes...|Hard fields are indexed chunk attributes...]]
- [[_COMMUNITY_HERB product twins (ContentForceContext...|HERB product twins (ContentForce/Context...]]
- [[_COMMUNITY_Literal-matching pipeline exact+normali...|Literal-matching pipeline: exact+normali...]]
- [[_COMMUNITY_Multi-hit rule multiple hard-field hits...|Multi-hit rule: multiple hard-field hits...]]
- [[_COMMUNITY_No corpus vocabulary in the interpreter'...|No corpus vocabulary in the interpreter'...]]
- [[_COMMUNITY_No value inventoriesmetadata mirrors in...|No value inventories/metadata mirrors in...]]
- [[_COMMUNITY_Nodeattribute rule node only if others...|Node/attribute rule: node only if others...]]

## God Nodes (most connected - your core abstractions)
1. `State doc 2026-06-18: v3 evaluation harness (HERB + RAGAS)` - 15 edges
2. `ModelUsage` - 14 edges
3. `_selfcheck()` - 13 edges
4. `run()` - 12 edges
5. `answer_one_question()` - 10 edges
6. `answer_one_question()` - 10 edges
7. `BuildStats` - 9 edges
8. `Prepared` - 9 edges
9. `Prepared` - 9 edges
10. `Handoff: v2 chunking model design (2026-06-03)` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Shared generator (fairness control)` --conceptually_related_to--> `post()`  [INFERRED]
  A:/exjobbet/repo/v3/README.md → v3/nim.py
- `Two scorers: HERB anchor + RAGAS lens` --references--> `faithfulness()`  [INFERRED]
  A:/exjobbet/repo/v3/README.md → v3/eval/ragas.py
- `Two scorers: HERB anchor + RAGAS lens` --references--> `answer_relevancy()`  [INFERRED]
  A:/exjobbet/repo/v3/README.md → v3/eval/ragas.py
- `Three arms (artefact/lucene/vector), one shared generator, shared top-k` --conceptually_related_to--> `orchestrator.py — wires ONE pipeline + ONE evaluator over the chosen questions a`  [INFERRED]
  state/2026-06-18-v3-eval-harness-herb-ragas.md → v3/orchestrator.py
- `Three arms (artefact/lucene/vector), one shared generator, shared top-k` --references--> `artifact.py — the ARTEFACT arm: the v2 graph (interpreter -> facet-channel retri`  [INFERRED]
  state/2026-06-18-v3-eval-harness-herb-ragas.md → v3/pipelines/artifact.py

## Import Cycles
- None detected.

## Communities (52 total, 36 thin omitted)

### Community 0 - "lucene.py"
Cohesion: 0.07
Nodes (54): Path, answer_one_question(), build_sparse_index(), _flatten_one(), gather_unit_text(), ingest_corpus(), prepare_over_corpus(), Prepared (+46 more)

### Community 1 - "State doc 2026-06-18: v3 evaluation harn..."
Cohesion: 0.07
Nodes (37): Eval oracle (answerable/unanswerable_questions) must be holdout, not corpus, Retriever routing = weighted activation propagation, no hard filters, Design-before-build gate: no pipeline code until the stage's design is signed off, v2 graph spine: Source to File to Chunk to Tag, nothing else is a node, derive-corpus stage 0: structural eval quarantine, one corpus view only, Rejected: designing the tagger from the retrieval side, Construct-validity: answer scoring measures the whole pipeline; deterministic ctx + oracle setting keep an endpoint on retrieval, Deterministic citation-based context precision/recall (ID-based / non-LLM), not the judged variants (+29 more)

### Community 2 - "orchestrator.py"
Cohesion: 0.11
Nodes (29): _arm_name(), build_eval_manifest(), build_run_manifest(), build_shared_generator(), load_chosen_questions(), open_corpus(), Strip the truth: hand the arm the question's id + text ONLY, as the (id,     tex, Prepare the arm once, then per question: to_arm_question -> answer.     -> (list (+21 more)

### Community 3 - "Facets as parallel relevance channels (t..."
Cohesion: 0.08
Nodes (26): Cheap zero-LLM cleanup plan (chunker+materialize+pattern-delete+docs), Handoff: graph-RAG artefact audit + cleanup plan (2026-05-25), Live herb-eval graph audit (4 labels, 3 edge types, no NEXT/Run), Bake combinator decision (multiplication rejected), Handoff: graph-RAG retrieval pipeline redesign (2026-05-25), No weight synthesis at query time, Recall to filter to rank to cap retrieval shape, 7-factor multiplicative scoreCypher (rejected synthesis) (+18 more)

### Community 4 - "ragas.py"
Cohesion: 0.11
Nodes (10): Do BOTH scorers: HERB exact anchor + RAGAS primary lens (not either/or), herb.py — HERB's own scorer: exact answer correctness, the anchor metric (leader, answer_relevancy(), context_precision(), context_recall(), faithfulness(), ragas.py — multidimensional answer/evidence quality (the primary lens, and what, ID-based context precision/recall (deterministic backbone) (+2 more)

### Community 5 - "contract.py"
Cohesion: 0.12
Nodes (16): main(), The gold-N: a balanced ANSWERABLE subset, drawn by seeded round-robin     over t, stratified_gold(), EvalManifest, EvalResult, QuestionWithTruth, contract.py — the shared shapes every arm and evaluator imports., Provenance for a `questions` run — answers generated by ONE arm. (+8 more)

### Community 6 - "State doc 2026-06-14: facets as parallel..."
Cohesion: 0.14
Nodes (16): Three baked weight layers (relevance_to_file / w_chunk / w_facet), v1 facets underspecified -> degraded into token-extraction (~18% junk), State doc 2026-06-09: weight production measure-not-emit, An LLM cannot emit correct weights (v1 evidence: 85% round-number anchoring), Measure, don't emit: geometry produces weights, model never emits a number, State doc 2026-06-11: v2 facet carriers and build gate, Each facet gets its own unique weight-production mechanism (concept uniform, instrument per-facet), State doc 2026-06-12: v2 graph spine and literal matching (+8 more)

### Community 7 - "Handoff: v2 chunking model design (2026-..."
Cohesion: 0.13
Nodes (16): Chunk as coherent episode, not fixed-size window, COVERS edge joining record references to chunks, Deterministic boundary seam-finder (no embeddings, no LLM), Handoff: v2 chunking model design (2026-06-03), Materialized path index as integer components, No chunk overlap (protects references-not-copies), Subchunks share path prefix, no parent node, Records-vs-prose is per-position in the tree (+8 more)

### Community 8 - "artifact.py"
Cohesion: 0.17
Nodes (5): Three arms (artefact/lucene/vector), one shared generator, shared top-k, artifact.py — the ARTEFACT arm: the v2 graph (interpreter -> facet-channel retri, lucene.py — sparse baseline (BM25, Lucene-variant ranking).  Why it's here: th, vector.py — dense baseline (embeddings + cosine), i.e. naive RAG.  Why it's here, orchestrator.py — wires ONE pipeline + ONE evaluator over the chosen questions a

### Community 9 - "nim.py"
Cohesion: 0.24
Nodes (8): _load_dotenv(), post(), nim.py — NVIDIA NIM REST transport (OpenAI-compatible endpoints).  Shared HARNES, Populate os.environ from a sibling .env (KEY=VALUE lines) without     overriding, The NIM API key, or a loud failure — no silent offline mode., POST payload to {BASE_URL}{path}, return the parsed JSON body.      Retries tran, require_key(), _run()

### Community 10 - "Rejected: tag-embedding vs abstract-face..."
Cohesion: 0.29
Nodes (7): Anisotropic cosine on this corpus (collapses to ~0.8 band), Tag-vs-description embedding distance as a relevance signal (later killed), Chunk description killed: union of phrase tags IS the chunk content, Phrase tag IS the node: per-chunk contextual phrase + embedding, no bare-word shared nodes, no synonym merge, Polarity does not survive embedding similarity; stance direction must be explicit text/label, Rejected: tag-embedding vs abstract-facet-embedding distance, A tag is ONE phrase carrying meaning; facet structure carries relevance separately

### Community 11 - "ragas_catalog.py"
Cohesion: 0.33
Nodes (6): _check(), Metric, metrics_to_run(), ragas_catalog.py — the full RAGAS metric menu + the toggle for which ones a run, The free deterministic backbone + the judged metrics you opted into., Fail loud before a run if SELECTED is malformed. SELECTED is judged-only;     de

### Community 12 - "smoke.py"
Cohesion: 0.40
Nodes (5): pick_few_question_ids(), smoke.py — tiny wiring check: run a few questions through one pipeline + evaluat, A small FIXED subset of answerable ids — one per type first (so the smoke     ex, Run orchestrator.run over n fixed questions into a per-run folder     output/smo, run_smoke()

### Community 13 - "Per-facet weights ride ONE chunk-tag edg..."
Cohesion: 0.40
Nodes (5): All facet weights on the same chunk-tag edge, not one edge per facet, Three v2 edge weights (chunk-file, chunk-tag, tag-facet), Node/edge split: intrinsic per-phrase value on node, sibling-relational value on edge, Chunk-file relevance weight DEAD (containment edge carries no number; coherence chunking solves filler demotion), Per-facet weights ride ONE chunk-tag edge (a facet vector)

### Community 14 - "build_questions.py"
Cohesion: 0.67
Nodes (3): build(), mint_id(), build_questions.py — one-shot: build the HERB question set from raw.  HERB ships

### Community 15 - "Routing sums per-facet channels weighted..."
Cohesion: 0.67
Nodes (3): Combinator = prompt-conditioned weighted dot product (accumulate not max), Asked-for vs given split: rank by requested dimension, narrow by presupposed scope (no numeric prompt emphasis), Routing sums per-facet channels weighted by prompt's per-facet emphasis

## Knowledge Gaps
- **40 isolated node(s):** `Metric`, `RAGAS metric catalog: deterministic always-on, judged via SELECTED`, `Two separate phases: questions / evals / full`, `Live herb-eval graph audit (4 labels, 3 edge types, no NEXT/Run)`, `Three baked weight layers (relevance_to_file / w_chunk / w_facet)` (+35 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **36 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `State doc 2026-06-18: v3 evaluation harness (HERB + RAGAS)` connect `State doc 2026-06-18: v3 evaluation harn...` to `artifact.py`, `ragas.py`?**
  _High betweenness centrality (0.254) - this node is a cross-community bridge._
- **Why does `Three arms (artefact/lucene/vector), one shared generator, shared top-k` connect `artifact.py` to `State doc 2026-06-18: v3 evaluation harn...`?**
  _High betweenness centrality (0.211) - this node is a cross-community bridge._
- **Why does `State doc 2026-06-14: facets as parallel relevance channels` connect `State doc 2026-06-14: facets as parallel...` to `State doc 2026-06-18: v3 evaluation harn...`, `Facets as parallel relevance channels (t...`?**
  _High betweenness centrality (0.172) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `State doc 2026-06-18: v3 evaluation harness (HERB + RAGAS)` (e.g. with `Open (undecided): lucene documents.feedback parity, slack userId/channel tokens in the embedded passage, empty-text artifact handling, README anti-sharing phrasing cleanup` and `Build isolation: the @v3/@v2/@v1 scope tag is authority; v3 self-contained; never open a v1/v2 file unless handed the exact one; overrides doc §9 pointers`) actually correct?**
  _`State doc 2026-06-18: v3 evaluation harness (HERB + RAGAS)` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `ModelUsage` (e.g. with `Path` and `answer_one_question()`) actually correct?**
  _`ModelUsage` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Path` (e.g. with `ArmOutput` and `BuildStats`) actually correct?**
  _`Path` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `_selfcheck()` (e.g. with `BuildStats` and `EvalResult`) actually correct?**
  _`_selfcheck()` has 4 INFERRED edges - model-reasoned connections that need verification._