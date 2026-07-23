# Graph Report - .  (2026-07-23)

## Corpus Check
- 59 files · ~25,359 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1044 nodes · 1812 edges · 60 communities (51 shown, 9 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 138 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY__Session|_Session]]
- [[_COMMUNITY_index.py|index.py]]
- [[_COMMUNITY_contract.py|contract.py]]
- [[_COMMUNITY_chunk.py|chunk.py]]
- [[_COMMUNITY_prepass.py|prepass.py]]
- [[_COMMUNITY_DESIGN|DESIGN.md]]
- [[_COMMUNITY_2026-07-20-v1-query-relative-areas|2026-07-20-v1-query-relative-areas.md]]
- [[_COMMUNITY_probe.py|probe.py]]
- [[_COMMUNITY_run.py|run.py]]
- [[_COMMUNITY_FuseTests|FuseTests]]
- [[_COMMUNITY_nim.py|nim.py]]
- [[_COMMUNITY_scan_dataset()|scan_dataset()]]
- [[_COMMUNITY__embed()|_embed()]]
- [[_COMMUNITY_artefact.py|artefact.py]]
- [[_COMMUNITY_vector.py|vector.py]]
- [[_COMMUNITY_lucene.py|lucene.py]]
- [[_COMMUNITY_ragas.py|ragas.py]]
- [[_COMMUNITY_ModelUsage|ModelUsage]]
- [[_COMMUNITY_artefact_v1.py|artefact_v1.py]]
- [[_COMMUNITY_artefact_v1_det.py|artefact_v1_det.py]]
- [[_COMMUNITY_hybrid.py|hybrid.py]]
- [[_COMMUNITY_2026-07-22-v1-curve-walk-facets-and-clus...|2026-07-22-v1-curve-walk-facets-and-clus...]]
- [[_COMMUNITY_DeterministicPlanTests|DeterministicPlanTests]]
- [[_COMMUNITY_derive_corpus()|derive_corpus()]]
- [[_COMMUNITY__retrieve()|_retrieve()]]
- [[_COMMUNITY__interpret()|_interpret()]]
- [[_COMMUNITY_progress()|progress()]]
- [[_COMMUNITY_GeminiCliRegressionTests|GeminiCliRegressionTests]]
- [[_COMMUNITY__JudgeLLM|_JudgeLLM]]
- [[_COMMUNITY_Artefact arm rebuilt natively in v3art...|Artefact arm: rebuilt natively in v3/art...]]
- [[_COMMUNITY_RuntimeError|RuntimeError]]
- [[_COMMUNITY__part_levels()|_part_levels()]]
- [[_COMMUNITY_main()|main()]]
- [[_COMMUNITY__NimEmbedder|_NimEmbedder]]
- [[_COMMUNITY_2026-07-22-retrieval-literature-sweep|2026-07-22-retrieval-literature-sweep.md]]
- [[_COMMUNITY_score_outputs()|score_outputs()]]
- [[_COMMUNITY__normalize()|_normalize()]]
- [[_COMMUNITY__embed_cached()|_embed_cached()]]
- [[_COMMUNITY_InterpCacheTests|InterpCacheTests]]
- [[_COMMUNITY__score_all()|_score_all()]]
- [[_COMMUNITY_LevelChainTests|LevelChainTests]]
- [[_COMMUNITY_CLAUDE.md — repo canon layout, session...|CLAUDE.md — repo canon: layout, session...]]
- [[_COMMUNITY_Repo layout v3 is the work — lean HERB...|Repo layout: v3/ is the work — lean HERB...]]
- [[_COMMUNITY_README|README.md]]
- [[_COMMUNITY_compare_arms.py|compare_arms.py]]
- [[_COMMUNITY_GapBreakTests|GapBreakTests]]
- [[_COMMUNITY_Pass2ValidationTests|Pass2ValidationTests]]
- [[_COMMUNITY_RetrievalFlagTests|RetrievalFlagTests]]
- [[_COMMUNITY_ragas_catalog.py|ragas_catalog.py]]
- [[_COMMUNITY__gemini_terminal_quota_error()|_gemini_terminal_quota_error()]]
- [[_COMMUNITY_export_raw.py|export_raw.py]]
- [[_COMMUNITY_ModifierLerpTests|ModifierLerpTests]]
- [[_COMMUNITY_MultiKSupportTests|MultiKSupportTests]]
- [[_COMMUNITY_SufficiencyTests|SufficiencyTests]]
- [[_COMMUNITY_truncate_k.py|truncate_k.py]]
- [[_COMMUNITY_corpus_gold_text()|corpus_gold_text()]]
- [[_COMMUNITY__tag_affinity()|_tag_affinity()]]
- [[_COMMUNITY_build_questions.py|build_questions.py]]
- [[_COMMUNITY_unpack_generation()|unpack_generation()]]
- [[_COMMUNITY_README|README.md]]

## God Nodes (most connected - your core abstractions)
1. `ModelUsage` - 38 edges
2. `_Session` - 35 edges
3. `_plan()` - 34 edges
4. `BuildStats` - 33 edges
5. `_row()` - 29 edges
6. `chunk_file()` - 20 edges
7. `ArmOutput` - 20 edges
8. `_ground_row()` - 20 edges
9. `profile()` - 17 edges
10. `CombineModeTests` - 15 edges

## Surprising Connections (you probably didn't know these)
- `RAGAS scoring-time deps pinned for offline metrics (rapidfuzz, sacrebleu, rouge_score, nltk) + scipy for NNK grounding` --references--> `ragas.py — multidimensional answer/evidence quality via the RAGAS library.  Scor`  [INFERRED]
  C:/Coding/exjobbet/GRAG-Job/v3/requirements.txt → v3/eval/ragas.py
- `Artefact arm: rebuilt natively in v3/artefact (scan/probe/derive/resolver tested); graph spine Source→File→Chunk→Tag closed canon; references not copies; model emits no numbers; herb-eval (Neo4j) is the prior v1 build — contrast baseline only` --references--> `Load the artefact index once. `corpus` is the corpus root the     orchestrator`  [INFERRED]
  C:/Coding/exjobbet/GRAG-Job/CLAUDE.md → v3/pipelines/artefact.py
- `Artefact arm: rebuilt natively in v3/artefact (scan/probe/derive/resolver tested); graph spine Source→File→Chunk→Tag closed canon; references not copies; model emits no numbers; herb-eval (Neo4j) is the prior v1 build — contrast baseline only` --references--> `artefact_v1.py — the ARTEFACT-V1 arm: query-relative fuzzy cluster retrieval ove`  [INFERRED]
  C:/Coding/exjobbet/GRAG-Job/CLAUDE.md → v3/pipelines/artefact_v1.py
- `Agent roster — orchestrator routing: main-chat Claude is the orchestrator — talks to the user, routes every job to a specialist agent, does no hands-on work; plain questions get direct conversational answers; long runs happen in the user's terminal (agents prepare, the user runs); definitions in .claude/agents/ — v3-coder (v3 code changes), critical-reviewer (post-change v3 review), code-optimizer (performance, profiles first), maths-algorithmist (mathematical algorithm design and verification), order-of-operations (pipeline sequencing/data-flow correctness), logician (invariants, proof-or-counterexample), retrieval-scientist (retrieval design and experiments), eval-statistician (significance, judge reliability, judge-run cost math), results-analyst (v3/output numbers, metric validity binding), graph-refresher (refresh_graph.py + worklist processing)` --references--> `Stable CLI progress bars for the v3 harness.`  [INFERRED]
  C:/Coding/exjobbet/GRAG-Job/CLAUDE.md → v3/progress.py
- `**Completeness.** Every dimension in the convergent model is represented *somewhere*` --related_to--> `ragas.py — multidimensional answer/evidence quality via the RAGAS library.  Scor`  [EXTRACTED]
  C:/Coding/exjobbet/GRAG-Job/v3/artefact/DESIGN.md → v3/eval/ragas.py

## Import Cycles
- None detected.

## Communities (60 total, 9 thin omitted)

### Community 0 - "_Session"
Cohesion: 0.06
Nodes (24): CombineModeTests, CombineTests, CurveWalkTests, _desc_row(), DoorTraceTests, EmbedCacheTests, _ground_row(), InterpreterBackendTests (+16 more)

### Community 1 - "index.py"
Cohesion: 0.06
Nodes (60): Chunk, chunk_dataset(), load_key(), Scan a corpus-view dataset dir and chunk every JSON file in it. The     prose-v, write_chunks(), build(), driver(), ensure_database() (+52 more)

### Community 2 - "contract.py"
Cohesion: 0.05
Nodes (53): backfill_file(), main(), Path, backfill_token_split.py — add tokens_in/tokens_out ONLY on rows with no token da, main(), The gold-N: a balanced ANSWERABLE subset, drawn by seeded round-robin     over, stratified_gold(), backfill_generator_usage() (+45 more)

### Community 3 - "chunk.py"
Cohesion: 0.08
Nodes (50): _chunk_conversation(), chunk_file(), _chunk_prose_records(), _chunk_short_records(), _ep_tokens(), est_tokens(), expand(), _get() (+42 more)

### Community 4 - "prepass.py"
Cohesion: 0.07
Nodes (40): _format_user(), interpret(), _load_gold100(), Stage query: interpret — one stateless structured call per prompt emits facet p, Fail loud on a schema-breaking response — never a silent partial., One stateless temp-0 structured call → (parsed_json, usage). Fail loud     on a, `per_type` per HERB answer type (person/content/company/pr/url)., Run the interpreter on a stratified slice of the gold-100 set; print     each q (+32 more)

### Community 5 - "DESIGN.md"
Cohesion: 0.05
Nodes (41): Materialize the artefact graph into Neo4j: `Source -[:CONTAINS]-> File -[:CONTA, A chunk reference in the resolver's self-resolving contract     (`resolver_prot, _resolver_ref(), `take` items evenly spread across a bucket — variety, deterministic., v2 Artefact Rebuild — Design, **Derive-corpus (one-time prep, per dataset that needs it)** — if the published, 9. Chunks, tags, and re-tagging, 9.6 Re-tag, do not migrate v1 tags (+33 more)

### Community 6 - "2026-07-20-v1-query-relative-areas.md"
Cohesion: 0.05
Nodes (39): Merge two shape signatures (array-element fusion and cross-file fusion)., Confirmed current-code problems, 6. Decisions made, Current fusion, `VizForce::a::16`, 4. Exact definitions and notation, 8. Rejected or dangerous interpretations, 1. Purpose of this state document (+31 more)

### Community 7 - "probe.py"
Cohesion: 0.11
Nodes (37): Any, Collection, content_files(), derive_candidates(), DocLeaf, escape_pointer_token(), fuse(), fuse_files() (+29 more)

### Community 8 - "run.py"
Cohesion: 0.09
Nodes (28): metrics_to_run(), The metrics this run scores — exactly SELECTED., main(), model_test.py — 3-question generator head-to-head through artefact_v1. Interpret, Judges with no queue to respect: open every cell at once., _wide_parallel_judge(), _fixed_ids_file(), _pid_alive() (+20 more)

### Community 9 - "FuseTests"
Cohesion: 0.07
Nodes (9): AnswerContractTests, _fake_lucene(), _fake_vector(), FuseTests, MinMaxTests, Regression checks for the hybrid arm — min-max late fusion of the lucene and vec, A vector stand-in: retrieve returns (ranked unit dicts, ModelUsage), the pair, A lucene stand-in: prepare hands back a Prepared-ish with a BuildStats;     retr (+1 more)

### Community 10 - "nim.py"
Cohesion: 0.09
Nodes (25): Progressive traversal without an answer-sufficiency oracle, Response, _back_off(), _claude_chat(), completed_calls(), _delay_after(), _fire(), _keys() (+17 more)

### Community 11 - "scan_dataset()"
Cohesion: 0.13
Nodes (24): json_pointer(), main(), v2 reference-resolver prototype — proves the 'graph is references' stance.  A, RFC 6901. Raises (loud) on any miss — never returns a silent default., ref = {file_path, sha256, scheme, address}. Fail loud on hash mismatch., resolve(), sha256_of(), unescape() (+16 more)

### Community 12 - "_embed()"
Cohesion: 0.10
Nodes (25): 9.5 Tagging unit, context, and no overlap, _embed(), _embed_request(), Embed one batch in a single NIM call -> (embeddings in input order, calls,     t, Embed texts via nv-embedqa -> (matrix [n, d] float32 L2-normalised, calls,     t, generator_usage_from_nim(), tokens_in/tokens_out from a NIM /chat/completions usage block., main() (+17 more)

### Community 13 - "artefact.py"
Cohesion: 0.13
Nodes (25): answer_one_question(), _apply_literal_boosts(), _chunk_scores(), _embed_facet_phrases(), _phrase_weights(), prepare_over_corpus(), Prepared, _qid_text() (+17 more)

### Community 14 - "vector.py"
Cohesion: 0.11
Nodes (25): answer_one_question(), _artifact_text(), build_dense_index(), _cache_path(), gather_unit_text(), load_query_vecs(), prepare_over_corpus(), _qid_text() (+17 more)

### Community 15 - "lucene.py"
Cohesion: 0.14
Nodes (23): answer_one_question(), build_sparse_index(), _flatten_one(), gather_unit_text(), ingest_corpus(), prepare_over_corpus(), Prepared, _qid_text() (+15 more)

### Community 16 - "ragas.py"
Cohesion: 0.14
Nodes (20): CompletedProcess, _check_judge_context_budget(), _claude_verdict(), _codex_usage(), _codex_verdict(), _encoding_for(), _estimate_tokens(), _gemini_usage() (+12 more)

### Community 17 - "ModelUsage"
Cohesion: 0.19
Nodes (19): ModelUsage, InterpreterError, Prepared, A failed interpreter turn. Carries the model usage spent across the     turn's a, Prepared, Handle returned by prepare(); fed back into answer_one_question. Holds the     L, Prepared, ArmOutput (+11 more)

### Community 18 - "artefact_v1.py"
Cohesion: 0.15
Nodes (18): answer_one_question(), _chat_json(), _env_float(), _extract_json(), _hint_match(), _load_verified_doc(), _nth_entry(), _open_area() (+10 more)

### Community 19 - "artefact_v1_det.py"
Cohesion: 0.18
Nodes (18): _anchors(), answer_one_question(), _det_plan(), _facet_direction(), _facet_router(), _facet_shaper(), _facet_triggers(), _phrase_at() (+10 more)

### Community 20 - "hybrid.py"
Cohesion: 0.15
Nodes (17): answer_one_question(), _env_float(), fuse(), _minmax(), prepare_over_corpus(), Prepared, _qid_text(), hybrid.py — late-fusion baseline: the lucene (BM25) and vector (dense) arms comb (+9 more)

### Community 21 - "2026-07-22-v1-curve-walk-facets-and-clus..."
Cohesion: 0.12
Nodes (15): Curve-walk gold-100 result: recall_id 0.7005 / precision_id 0.0545 vs flat baseline 0.6972 / 0.0518 — first variant beating baseline on both; kept hit the 50-ceiling on all 100 questions, _curve_k: break in a descending curve — unit square, head-to-tail straight fit, cut at the point furthest below it, 1e-9 noise guard, no dip means keep everything, Substitution failure (do not repeat): the value knee was built instead of the discussed height walk because it was less invasive; the user's concepts are the spec, Open decision: does stated scope count toward K, or corroborate and rank only, Measurement debts: haiku leg untested on the current build; k=5/10/20 need real runs; the detW2 gain bundles three membership changes, Geometric det facet channel (HERB_DET_FACETS support/routing/edges) moved recall ≤ +0.003 at k=50 — facet placement, not facet values, is the open question, HERB_CURVE_K naming flagged by the user (reads as forcing K=1; it is a boolean); rename to HERB_CURVE_WALK=1 or kill the flag — choice pending, Value-knee cut rejected by measurement: per-question K equivalent to a flat cut at the same mean depth (0.6368 vs flat-37 0.6397); its break tracks the tag/desc-floor seam, a pool-composition artifact (+7 more)

### Community 22 - "DeterministicPlanTests"
Cohesion: 0.16
Nodes (3): DeterministicPlanTests, _S, _Vocab

### Community 23 - "derive_corpus()"
Cohesion: 0.25
Nodes (12): derive_corpus(), DeriveReport, _dump(), One-time prep: derive the corpus view a dataset's pipeline run scans.  The pub, 4. Pipeline skeleton, _full_product(), _make_raw(), test_corpus_view_strips_rag_unsafe_keys_and_copies_rest_verbatim() (+4 more)

### Community 24 - "_retrieve()"
Cohesion: 0.18
Nodes (11): _agg(), _gap_break(), _mod(), _n_levels(), interpret-plan -> (pointer rows cut at k, query embed ModelUsage,     retrieval, The walk's stopping test, read from its own trajectory. The height     gaps betw, The number of doubling levels a stated-scope ranked set of size n spans —     th, Fold a path's per-part/source support dicts into one per-chunk base by     the H (+3 more)

### Community 25 - "_interpret()"
Cohesion: 0.18
Nodes (11): _clean_tag(), _interp_key(), _interpret(), _interpret_cached(), _parse_gate(), Normalise the model's loose gate into strict scope hints: string-or-null     fie, interpret a question -> (plan, calls, tokens_in, tokens_out, time_s).     plan =, Content address for one interpretation: (interpret model, interpreter     signat (+3 more)

### Community 26 - "progress()"
Cohesion: 0.24
Nodes (8): main(), _probe_model(), judge_probe.py — survey every chat-capable NIM model as a RAGAS-judge candidate., _verdict(), progress(), Stable CLI progress bars for the v3 harness., tqdm tuned for Windows terminals and captured logs., _selfcheck()

### Community 27 - "GeminiCliRegressionTests"
Cohesion: 0.22
Nodes (3): GeminiCliRegressionTests, Regression checks for Gemini CLI process and quota handling., _TimeoutProcess

### Community 28 - "_JudgeLLM"
Cohesion: 0.33
Nodes (3): BaseRagasLLM, _JudgeLLM, RAGAS LLM driven by nim.post or a headless subscription CLI.     The backend fol

### Community 29 - "Artefact arm: rebuilt natively in v3/art..."
Cohesion: 0.22
Nodes (9): Artefact arm: rebuilt natively in v3/artefact (scan/probe/derive/resolver tested); graph spine Source→File→Chunk→Tag closed canon; references not copies; model emits no numbers; herb-eval (Neo4j) is the prior v1 build — contrast baseline only, 13. Semantic dimensions — the research basis for the facets, GraphRAG family: Microsoft GraphRAG's communities are permanent and query-blind (the contrast case); HippoRAG 1/2 validate seed-weighted PPR over a tag-like graph; G-Retriever's prize-collecting Steiner tree is a one-shot budgeted subgraph alternative; ToG's stop rule is LLM sufficiency under a hard cap, 13.1 Why the v1 facets degraded, Facet verdict: stored HAS_TAG w_facets are non-signal — weights confined to 0.5–1.0, temporal on 555/20k edges; feeding query facet direction into them (detE) changed 5/100 retrieved sets, recall Δ 0.0000, NNK neighborhoods: redundancy pruning is by design (near-synonym tags get exactly zero weight); no published RAG/passage-retrieval use; if used at all it belongs at tag grounding, not chunk selection, Load the artefact index once. `corpus` is the corpus root the     orchestrator, artefact_v1.py — the ARTEFACT-V1 arm: query-relative fuzzy cluster retrieval ove (+1 more)

### Community 30 - "RuntimeError"
Cohesion: 0.25
Nodes (8): _driver(), prepare_over_corpus(), RuntimeError, Aborted, abort.py — press 'q' to stop a running gen/eval loop.  Ctrl+C can be swallowed, Raised from inside an in-flight call when q has been pressed, so a worker     p, Start a daemon thread that sets the abort flag when q/Q is pressed. No-op     w, watch()

### Community 31 - "_part_levels()"
Cohesion: 0.31
Nodes (9): _level_chain(), _multi_k_support(), _part_levels(), `a` scaled to unit length along its last axis; a zero vector has no     directio, Fuzzy k-NN support aggregated over the doubling level sequence: every     level, The anchor leaf's containing-cluster chain through the dendrogram,     finest to, One part -> its widening levels: [{height, tags: [(name, support)]}]     finest, _unit() (+1 more)

### Community 32 - "main()"
Cohesion: 0.47
Nodes (8): _cosine(), _embed_texts(), expand_folders(), _folder_question_ids(), main(), offline_eval.py — score run folders with the no-judge metrics.  Step 2 of the de, score_folder(), Path

### Community 33 - "_NimEmbedder"
Cohesion: 0.32
Nodes (3): BaseRagasEmbeddings, _NimEmbedder, RAGAS embeddings driven by nim.post — llama-nemotron-embed, asymmetric: question

### Community 34 - "2026-07-22-retrieval-literature-sweep.md"
Cohesion: 0.25
Nodes (7): Query-conditioned local graph clustering: Andersen-Chung-Lang PPR + sweep cut formalizes a soft query-relative region with a principled boundary; heat kernel (Kloster-Gleich) is the tighter-radius variant; Crestani's spreading-activation constraints catalogue the flooding failure modes, LLM-emitted scalars as ranking features: document-level LLM relevance labels can be load-bearing (Thomas et al., Bing/SIGIR 2024) but label-level agreement is fragile and scalar outputs compress; NO published validation of LLM-emitted per-edge numeric weights — HippoRAG-line systems derive weights structurally, LLM only discrete decisions, Five-finding synthesis: weighted score-space fusion over RRF; the more-tags-more-votes pathology starts at emission; PM-2 for the hard-k budget; query-relative areas = seed-weighted local diffusion; LLM per-edge scalars are unvalidated territory, Progressive budgeted retrieval: PM-2 proportional slot allocation (each of k slots to the most under-served aspect) beat xQuAD on TREC diversity — the published mechanism for multi-frontier selection under hard k; bandit budget allocation across subqueries gains +35% precision, Faceted / multi-aspect query representation: MADRAL fuses aspects into one vector pre-retrieval; its ECIR 2024 reproduction failed (learned aspects can be dead weight); ColBERT's MaxSim-then-sum is the proven score-space per-aspect aggregation, Rank fusion theory: RRF is rank-only and erases within-list multipliers (Cormack 2009); normalized-score convex combination beats RRF in- and out-of-domain (Bruch et al., TOIS 2023); weighted RRF puts importance in per-list weights; LLMs emit the prompted subquery count regardless of need (arXiv:2510.18633), Multi-faceted edge weights: PathSim shows the typed-edge channel must be chosen query-side; HGT shows learned per-relation weighting beats uniform; edge-weighted PPR (Xie KDD 2015) makes query-conditioned edge modulation tractable; CatRAG/MemORAI (2026, unreplicated) do it end-to-end

### Community 35 - "score_outputs()"
Cohesion: 0.25
Nodes (7): _build_metrics(), _print_status_summary(), Instantiate each selected metric with the wrappers it needs, then init() it —, ENTRY: per (output, question) score every metric in metrics_to_run() ->     list, One line per metric that produced any non-ok cell, so failures are visible at, score_outputs(), RunConfig

### Community 36 - "_normalize()"
Cohesion: 0.29
Nodes (8): _absolute(), _minmax(), _norm_pool(), _normalize(), Min-max a path's base scores against the given bounds: hi <= lo (a single     sc, Min-max normalize a path's per-chunk base scores onto [0, 1] over that     path', A pool-independent bounded score: the raw support saturated against a     per-pa, Put the three paths' bases on a comparable scale by the HERB_NORM mode:     rela

### Community 37 - "_embed_cached()"
Cohesion: 0.25
Nodes (8): _embed_cached(), _embed_key(), _load_cached_vec(), Content address for one embedding: (embed model, input_type, text), each     len, The cached embedding for `key`, or None on a miss. A corrupt or     half-written, Write one embedding under its content address, published atomically so a     con, Embed `texts` through the shared NIM embedder with a persistent per-text     cac, _store_cached_vec()

### Community 39 - "_score_all()"
Cohesion: 0.29
Nodes (7): _load_rows(), One contract pair -> a RAGAS SingleTurnSample. reference = the gold answer     (, Parsed rows already in results_path. A torn trailing line from a killed write, Score every (question, metric) cell -> list[EvalResult], in ordered passes: the, _score_all(), _to_sample(), SingleTurnSample

### Community 41 - "CLAUDE.md — repo canon: layout, session..."
Cohesion: 0.47
Nodes (6): Agent roster — orchestrator routing: main-chat Claude is the orchestrator — talks to the user, routes every job to a specialist agent, does no hands-on work; plain questions get direct conversational answers; long runs happen in the user's terminal (agents prepare, the user runs); definitions in .claude/agents/ — v3-coder (v3 code changes), critical-reviewer (post-change v3 review), code-optimizer (performance, profiles first), maths-algorithmist (mathematical algorithm design and verification), order-of-operations (pipeline sequencing/data-flow correctness), logician (invariants, proof-or-counterexample), retrieval-scientist (retrieval design and experiments), eval-statistician (significance, judge reliability, judge-run cost math), results-analyst (v3/output numbers, metric validity binding), graph-refresher (refresh_graph.py + worklist processing), CLAUDE.md — repo canon: layout, session entry, graph refresh, hard rules, agent roster, artefact arm, Hard rules: design sign-off before build; plain spoken English; heed user intent over stale context; docs track reality; no historical/defensive comments; visible progress in the user's terminal; critical-review all v3 code changes, Navigation graph: query graphify first; refresh_graph.py is the ONLY rebuild path (never graphify --update); worklists get model extraction bridged into .concept_index.txt, Session entry: gitignored state-transfer docs in docs/state (current: 2026-07-22 v1 curve walk, facets verdict, cluster-K; predecessor 2026-07-20 holds pre-walk definitions); newest dated doc is the entry point, Cluster-K concept (user canon): the clustering's curve of best fit decides the per-query evidence count K; the caller's k is only the ceiling

### Community 42 - "Repo layout: v3/ is the work — lean HERB..."
Cohesion: 0.33
Nodes (6): Repo layout: v3/ is the work — lean HERB eval harness, three arms (artefact / lucene / vector) scored with RAGAS, Scoring with RAGAS, Ops: run.py finishes but never exits under redirected stdin (press-q abort watcher) — poll the out dir; use --no-eval for retrieval A/Bs; id metrics computable from arm_outputs.jsonl + questions.jsonl, orchestrator.py — wires ONE pipeline + ONE evaluator over the chosen questions, v3/requirements.txt — harness environment pins (provisional laptop-reconstructed; desktop .venv is the canonical record), RAGAS scoring-time deps pinned for offline metrics (rapidfuzz, sacrebleu, rouge_score, nltk) + scipy for NNK grounding

### Community 43 - "README.md"
Cohesion: 0.33
Nodes (5): Still open, Run flow — two separate phases, Data split (the quarantine), v3 — HERB evaluation, One caveat worth remembering

### Community 44 - "compare_arms.py"
Cohesion: 0.47
Nodes (5): main(), _print(), compare_arms.py — side-by-side RAGAS comparison across the gold-100 runs.  Wal, (arm, k) -> {metric: [values...]} over the ok cells in eval_results.jsonl., _scan()

### Community 48 - "ragas_catalog.py"
Cohesion: 0.40
Nodes (4): _check(), Metric, ragas_catalog.py — the full RAGAS metric menu + the toggle for which ones a run, Fail loud before a run if SELECTED is malformed.

### Community 49 - "_gemini_terminal_quota_error()"
Cohesion: 0.40
Nodes (5): _gemini_quota_error_row(), _gemini_terminal_quota_error(), A terminal Gemini quota/entitlement rejection cannot improve with a retry., Whether a cell has Gemini CLI's terminal quota/entitlement rejection., Exception

### Community 50 - "export_raw.py"
Cohesion: 0.60
Nodes (4): _collect_rows(), main(), Path, export_raw.py — dump all eval_results to a single long-format CSV.      python

### Community 54 - "truncate_k.py"
Cohesion: 0.50
Nodes (4): main(), truncate_k.py — re-emit a run's arm_outputs at each eval depth k, no regeneratio, One arm_outputs record cut to its first k chunks, ids rebuilt from the     kept, truncate_record()

### Community 55 - "corpus_gold_text()"
Cohesion: 0.50
Nodes (4): corpus_gold_text(), Every string leaf of an artifact record, joined — a faithful text rendering of, artifact id -> its text. The non-LLM context metrics score retrieved text     ag, _string_leaves()

### Community 56 - "_tag_affinity()"
Cohesion: 0.50
Nodes (4): _hint_terms(), Cypher boolean terms for the interpreted scope hints, over chunk     fields. ([], Structural affinity per tag: the fraction of the tag's edges landing on     hint, _tag_affinity()

### Community 57 - "build_questions.py"
Cohesion: 0.67
Nodes (3): build(), mint_id(), build_questions.py — one-shot: build the HERB question set from raw.  HERB shi

### Community 58 - "unpack_generation()"
Cohesion: 0.50
Nodes (4): model_usage_from_telemetry(), Normalise a generator return into (answer, ModelUsage)., Build ModelUsage from a generator telemetry dict., unpack_generation()

## Knowledge Gaps
- **91 isolated node(s):** `Path`, `Metric`, `Response`, `v3 — HERB evaluation`, `Data split (the quarantine)` (+86 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BuildStats` connect `ModelUsage` to `main()`, `index.py`, `contract.py`, `FuseTests`, `artefact.py`, `vector.py`, `lucene.py`, `hybrid.py`, `RuntimeError`, `_part_levels()`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Why does `ModelUsage` connect `ModelUsage` to `main()`, `_NimEmbedder`, `index.py`, `score_outputs()`, `contract.py`, `_score_all()`, `FuseTests`, `artefact.py`, `lucene.py`, `ragas.py`, `_gemini_terminal_quota_error()`, `hybrid.py`, `unpack_generation()`, `_JudgeLLM`, `_part_levels()`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `chunk_dataset()` connect `index.py` to `scan_dataset()`, `chunk.py`, `probe.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `ModelUsage` (e.g. with `CompletedProcess` and `_JudgeLLM`) actually correct?**
  _`ModelUsage` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `BuildStats` (e.g. with `_write_build_stats()` and `ModelUsage`) actually correct?**
  _`BuildStats` has 32 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Ablation: attribute the gold-100 k=10 context_recall_id between the corpus-gene`, `Resume: per-question records already computed (id -> record). The     interpret`, `abort.py — press 'q' to stop a running gen/eval loop.  Ctrl+C can be swallowed` to the rest of the system?**
  _335 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `_Session` be split into smaller, more focused modules?**
  _Cohesion score 0.06435498089920658 - nodes in this community are weakly interconnected._