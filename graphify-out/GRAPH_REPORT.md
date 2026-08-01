# Graph Report - .  (2026-08-01)

## Corpus Check
- 62 files · ~30,144 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1173 nodes · 2062 edges · 70 communities (57 shown, 13 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 130 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY__plan()|_plan()]]
- [[_COMMUNITY_chunk.py|chunk.py]]
- [[_COMMUNITY_vector.py|vector.py]]
- [[_COMMUNITY_index.py|index.py]]
- [[_COMMUNITY_DESIGN|DESIGN.md]]
- [[_COMMUNITY_prepass.py|prepass.py]]
- [[_COMMUNITY_probe.py|probe.py]]
- [[_COMMUNITY_graph_store.py|graph_store.py]]
- [[_COMMUNITY_2026-07-20-v1-query-relative-areas|2026-07-20-v1-query-relative-areas.md]]
- [[_COMMUNITY_v3README|v3/README.md]]
- [[_COMMUNITY_run.py|run.py]]
- [[_COMMUNITY_nim.py|nim.py]]
- [[_COMMUNITY_scan_dataset()|scan_dataset()]]
- [[_COMMUNITY_build_tag_clusters.py|build_tag_clusters.py]]
- [[_COMMUNITY_ragas.py|ragas.py]]
- [[_COMMUNITY_ModelUsage|ModelUsage]]
- [[_COMMUNITY_hybrid.py|hybrid.py]]
- [[_COMMUNITY_2026-07-25-combine-clusterk-hybrid-and-j...|2026-07-25-combine-clusterk-hybrid-and-j...]]
- [[_COMMUNITY_artefact_v1.py|artefact_v1.py]]
- [[_COMMUNITY_artefact_v1_det.py|artefact_v1_det.py]]
- [[_COMMUNITY_orchestrator.py|orchestrator.py]]
- [[_COMMUNITY_2026-07-22-v1-curve-walk-facets-and-clus...|2026-07-22-v1-curve-walk-facets-and-clus...]]
- [[_COMMUNITY_DeterministicPlanTests|DeterministicPlanTests]]
- [[_COMMUNITY_test_hybrid.py|test_hybrid.py]]
- [[_COMMUNITY_derive_corpus()|derive_corpus()]]
- [[_COMMUNITY_2026-07-28-audit-absorption-full-revert-...|2026-07-28-audit-absorption-full-revert-...]]
- [[_COMMUNITY_contract.py|contract.py]]
- [[_COMMUNITY_score_outputs()|score_outputs()]]
- [[_COMMUNITY_answer_one_question()|answer_one_question()]]
- [[_COMMUNITY_FuseTests|FuseTests]]
- [[_COMMUNITY__retrieve()|_retrieve()]]
- [[_COMMUNITY__part_levels()|_part_levels()]]
- [[_COMMUNITY_Audit verdicts haiku  det supported on...|Audit verdicts: haiku < det supported on...]]
- [[_COMMUNITY_2026-07-22-retrieval-literature-sweep|2026-07-22-retrieval-literature-sweep.md]]
- [[_COMMUNITY__chat_json()|_chat_json()]]
- [[_COMMUNITY_InterpreterError|InterpreterError]]
- [[_COMMUNITY_GeminiCliRegressionTests|GeminiCliRegressionTests]]
- [[_COMMUNITY_load_questions()|load_questions()]]
- [[_COMMUNITY__selfcheck()|_selfcheck()]]
- [[_COMMUNITY_main()|main()]]
- [[_COMMUNITY__NimEmbedder|_NimEmbedder]]
- [[_COMMUNITY__JudgeLLM|_JudgeLLM]]
- [[_COMMUNITY_Metric definitions recall_id = retriev...|Metric definitions: recall_id = |retriev...]]
- [[_COMMUNITY__normalize()|_normalize()]]
- [[_COMMUNITY__embed_cached()|_embed_cached()]]
- [[_COMMUNITY_InterpCacheTests|InterpCacheTests]]
- [[_COMMUNITY__score_all()|_score_all()]]
- [[_COMMUNITY_backfill_file()|backfill_file()]]
- [[_COMMUNITY_LevelChainTests|LevelChainTests]]
- [[_COMMUNITY_RetrievalFlagTests|RetrievalFlagTests]]
- [[_COMMUNITY_AnswerContractTests|AnswerContractTests]]
- [[_COMMUNITY_ragas_catalog.py|ragas_catalog.py]]
- [[_COMMUNITY__interpret_cached()|_interpret_cached()]]
- [[_COMMUNITY_abort.py|abort.py]]
- [[_COMMUNITY_GapBreakTests|GapBreakTests]]
- [[_COMMUNITY_GuideBuildTests|GuideBuildTests]]
- [[_COMMUNITY_Pass2ValidationTests|Pass2ValidationTests]]
- [[_COMMUNITY_RunFlagTests|RunFlagTests]]
- [[_COMMUNITY_Audit verdict on scope-dominance haiku...|Audit verdict on scope-dominance: haiku...]]
- [[_COMMUNITY__gemini_terminal_quota_error()|_gemini_terminal_quota_error()]]
- [[_COMMUNITY_export_raw.py|export_raw.py]]
- [[_COMMUNITY_ModifierLerpTests|ModifierLerpTests]]
- [[_COMMUNITY_MultiKSupportTests|MultiKSupportTests]]
- [[_COMMUNITY_SufficiencyTests|SufficiencyTests]]
- [[_COMMUNITY_herb-eval.dump|herb-eval.dump]]
- [[_COMMUNITY__tag_affinity()|_tag_affinity()]]
- [[_COMMUNITY_build_questions.py|build_questions.py]]
- [[_COMMUNITY_build_eval_manifest()|build_eval_manifest()]]
- [[_COMMUNITY_build_run_manifest()|build_run_manifest()]]
- [[_COMMUNITY__score_one()|_score_one()]]

## God Nodes (most connected - your core abstractions)
1. `_plan()` - 44 edges
2. `_Session` - 42 edges
3. `ModelUsage` - 38 edges
4. `_row()` - 35 edges
5. `BuildStats` - 33 edges
6. `v3/README.md` - 24 edges
7. `_ground_row()` - 22 edges
8. `chunk_file()` - 20 edges
9. `ArmOutput` - 20 edges
10. `_levels()` - 18 edges

## Surprising Connections (you probably didn't know these)
- `RAGAS scoring-time deps pinned for offline metrics (rapidfuzz, sacrebleu, rouge_score, nltk) + scipy for NNK grounding` --references--> `ragas.py — multidimensional answer/evidence quality via the RAGAS library.  Scor`  [INFERRED]
  C:/Coding/exjobbet/GRAG-Job/v3/requirements.txt → v3/eval/ragas.py
- `**Completeness.** Every dimension in the convergent model is represented *somewhere*` --related_to--> `ragas.py — multidimensional answer/evidence quality via the RAGAS library.  Scor`  [EXTRACTED]
  C:/Coding/exjobbet/GRAG-Job/v3/artefact/DESIGN.md → v3/eval/ragas.py
- `Graph and evidence units` --related_to--> `ragas.py — multidimensional answer/evidence quality via the RAGAS library.  Scor`  [EXTRACTED]
  state/2026-07-20-v1-query-relative-areas.md → v3/eval/ragas.py
- `13.4 Dimension → mechanism allocation (the table)` --related_to--> `ragas.py — multidimensional answer/evidence quality via the RAGAS library.  Scor`  [EXTRACTED]
  C:/Coding/exjobbet/GRAG-Job/v3/artefact/DESIGN.md → v3/eval/ragas.py
- `RAGAS (eval/ragas.py) is the scorer; the full metric menu lives in eval/ragas_catalog.py; every judge-free deterministic metric always runs because it costs nothing, and SELECTED adds the judged ones` --related_to--> `ragas.py — multidimensional answer/evidence quality via the RAGAS library.  Scor`  [EXTRACTED]
  C:/Coding/exjobbet/GRAG-Job/v3/README.md → v3/eval/ragas.py

## Import Cycles
- None detected.

## Communities (70 total, 13 thin omitted)

### Community 0 - "_plan()"
Cohesion: 0.05
Nodes (28): CombineModeTests, CombineTests, CurveWalkTests, _desc_row(), DoorTraceTests, EmbedCacheTests, _ground_row(), GuideTests (+20 more)

### Community 1 - "chunk.py"
Cohesion: 0.08
Nodes (52): Chunk, _chunk_conversation(), chunk_file(), _chunk_prose_records(), _chunk_short_records(), _ep_tokens(), est_tokens(), expand() (+44 more)

### Community 2 - "vector.py"
Cohesion: 0.06
Nodes (49): answer_one_question(), _artifact_text(), build_dense_index(), _cache_path(), _embed(), _embed_request(), gather_unit_text(), load_query_vecs() (+41 more)

### Community 3 - "index.py"
Cohesion: 0.07
Nodes (48): chunk_artifact_ids(), find_tags_npz(), load_artefact_index(), _load_tags_npz(), _load_verified_doc(), _mean_center(), _pointer_get(), PreparedIndex (+40 more)

### Community 4 - "DESIGN.md"
Cohesion: 0.05
Nodes (46): A chunk reference in the resolver's self-resolving contract     (`resolver_prot, `take` items evenly spread across a bucket — variety, deterministic., 13. Semantic dimensions — the research basis for the facets, **Derive-corpus (one-time prep, per dataset that needs it)** — if the published, 9. Chunks, tags, and re-tagging, 9.6 Re-tag, do not migrate v1 tags, **topic** (aboutness / frame-domain), 9.1 A chunk is a coherent episode, not a fixed-size window (+38 more)

### Community 5 - "prepass.py"
Cohesion: 0.07
Nodes (40): _format_user(), interpret(), _load_gold100(), Stage query: interpret — one stateless structured call per prompt emits facet p, Fail loud on a schema-breaking response — never a silent partial., One stateless temp-0 structured call → (parsed_json, usage). Fail loud     on a, `per_type` per HERB answer type (person/content/company/pr/url)., Run the interpreter on a stratified slice of the gold-100 set; print     each q (+32 more)

### Community 6 - "probe.py"
Cohesion: 0.11
Nodes (37): Any, Collection, content_files(), derive_candidates(), DocLeaf, escape_pointer_token(), fuse(), fuse_files() (+29 more)

### Community 7 - "graph_store.py"
Cohesion: 0.09
Nodes (37): chunk_dataset(), load_key(), Scan a corpus-view dataset dir and chunk every JSON file in it. The     prose-v, build(), driver(), ensure_database(), ingest(), load_tags_index() (+29 more)

### Community 8 - "2026-07-20-v1-query-relative-areas.md"
Cohesion: 0.06
Nodes (38): Merge two shape signatures (array-element fusion and cross-file fusion)., Confirmed current-code problems, 6. Decisions made, Current fusion, `VizForce::a::16`, 4. Exact definitions and notation, 8. Rejected or dangerous interpretations, 1. Purpose of this state document (+30 more)

### Community 9 - "v3/README.md"
Cohesion: 0.06
Nodes (38): Materialize the artefact graph into Neo4j: `Source -[:CONTAINS]-> File -[:CONTA, Agent roster — orchestrator routing: main-chat Claude is the orchestrator — talks to the user, routes every job to a specialist agent, does no hands-on work; plain questions get direct conversational answers; agents always run in the background — a foreground agent freezes the conversation; prompts are scoped to the change — a two-line change gets a two-line prompt, never a tree-wide audit unless the user asks; long runs happen in the user's terminal (agents prepare, the user runs); definitions in .claude/agents/ — v3-coder (v3 code changes), critical-reviewer (post-change v3 review), code-optimizer (performance, profiles first), maths-algorithmist (mathematical algorithm design and verification), order-of-operations (pipeline sequencing/data-flow correctness), logician (invariants, proof-or-counterexample), retrieval-scientist (retrieval design and experiments), eval-statistician (significance, judge reliability, judge-run cost math), results-analyst (v3/output numbers, metric validity binding), graph-refresher (refresh_graph.py + worklist processing), Artefact arm: the artefact is the system under test, rebuilt natively in v3/artefact — deterministic stages scan.py (file catalog → sha256/file_id), probe.py (shape recovery, RFC 6901 pointers), derive_corpus.py (oracle strip), resolver_prototype.py (reference resolution, hash-verified) exist and are tested; the HERB mapping key keys/Salesforce__HERB.yaml and design references DESIGN.md / MODEL_CONTRACTS.md live there; the graph proper (chunk → tag → facet retrieval) is the unbuilt part, pipelines/artifact.py the arm entry; graph spine Source → File → Chunk → Tag is closed canon, hard fields are chunk attributes, the graph is references into untouched raw source never copies; the model emits no numbers (tagger and interpreter), the chunk description is dead, tags are per-chunk contextual phrases; herb-eval (Neo4j) is the prior artefact build under the superseded design — contrast/forensic baseline only, never query herb (oracle-contaminated), CLAUDE.md — repo canon: layout, session entry, graph refresh, hard rules, agent roster, artefact arm, Navigation graph: query graphify FIRST before grepping (graphify query / explain / path); rebuild with python refresh_graph.py at commit time — once per commit, right before committing, batching every edit since the last refresh; the ONLY rebuild path, never graphify --update (drops the external-doc bridges); a printed worklist means model extraction: process .refresh_worklist.json, bridge into .concept_index.txt, committed repo docs to graphify's semantic cache, gitignored state/handoff docs as sidecar fragments in .external_cache/ ({source_file,hash,nodes,edges}), then re-run, Repo layout: v3/ is the work — a lean HERB evaluation harness, three arms (artefact / lucene / vector) scored with RAGAS, self-contained, design reference v3/README.md; root canon (CLAUDE.md, README.md) plus the gitignored state/handoff docs under docs/ complete the picture, v2 Artefact Rebuild — Design, Cross-cutting audit findings: the judge is validated only on lucene/vector prose, not artefact-style contexts; two gold-100 definitions exist — runs use data/gold100.jsonl (55 content / 22 person / 17 pr / 5 company / 1 url), not the balanced set v3/README.md describes; invalid flat-slice __k dirs sit in v3/output (e.g. artefact_v1__gold100__20260718T231758Z__k25) and need quarantine before any analyst pass; manifests carry no git sha (provenance is flags + timestamp); hybrid rankings are k-dependent (min-max over the 4k fetch window before the cut; k=50 not a prefix of k=500 on 100/100 questions) so hybrid depth sweeps are not nested; the vector query-embed cache is keyed by question id only (silent staleness on embedder change) (+30 more)

### Community 10 - "run.py"
Cohesion: 0.08
Nodes (31): metrics_to_run(), main(), model_test.py — 3-question generator head-to-head through artefact_v1. Interpret, Judges with no queue to respect: open every cell at once., _wide_parallel_judge(), _apply_flags(), _fixed_ids_file(), _flag() (+23 more)

### Community 11 - "nim.py"
Cohesion: 0.09
Nodes (26): Judged-eval failure modes are operational: NIM generator 404 (hosted-catalog outage) forces --generator claude-haiku-4-5; the claude CLI's 3-second stdin-wait trips under machine load, and answer_correctness makes the most sub-calls so it fails first; run serial/low workers on an unloaded machine and reap the claude process tree after, Progressive traversal without an answer-sufficiency oracle, Response, _back_off(), _claude_chat(), completed_calls(), _delay_after(), _fire() (+18 more)

### Community 12 - "scan_dataset()"
Cohesion: 0.13
Nodes (24): json_pointer(), main(), v2 reference-resolver prototype — proves the 'graph is references' stance.  A, RFC 6901. Raises (loud) on any miss — never returns a silent default., ref = {file_path, sha256, scheme, address}. Fail loud on hash mismatch., resolve(), sha256_of(), unescape() (+16 more)

### Community 13 - "build_tag_clusters.py"
Cohesion: 0.11
Nodes (24): Hard rules: design sign-off before build; plain spoken English, short answers, verify claims against the real system; heed the user's intent — never correct it with stale context, surface a genuine conflict as a question; docs track reality — update design doc + memory in the same pass by removal of dead content, dated state/handoff docs are frozen; no historical or defensive comments — state only the present, comments feed the graph and memory; refresh the navigation graph at commit time, never per-edit — doc extraction is expensive so all changed docs ride the same pass; every runnable shows life instantly and progress continuously (banner before any heavy import, flush=True, v3/progress.py bars) — a silent terminal is a bug; critical-review logic changes only — background, one batched review per work burst, config flips / default changes / renames / comments / help text / doc lines get no review, facet_participation(), fetch_tags(), floor_participation(), kmeanspp_init(), main(), memberships(), ndarray (+16 more)

### Community 14 - "ragas.py"
Cohesion: 0.14
Nodes (20): CompletedProcess, _check_judge_context_budget(), _claude_verdict(), _codex_usage(), _codex_verdict(), _encoding_for(), _estimate_tokens(), _gemini_usage() (+12 more)

### Community 15 - "ModelUsage"
Cohesion: 0.17
Nodes (20): build_sparse_index(), _flatten_one(), ingest_corpus(), prepare_over_corpus(), Prepared, lucene.py — sparse baseline (BM25, Lucene-variant ranking).  Why it's here: th, One artifact -> (id, title, contents). None if the record carries no id., Flatten HERB into one document per artifact: {id, title, contents, kind}. (+12 more)

### Community 16 - "hybrid.py"
Cohesion: 0.15
Nodes (18): Hybrid arm (v3/pipelines/hybrid.py): min-max late fusion of the lucene and vector arms; HERB_HYBRID_ALPHA (0=lucene, 1=vector, 0.5 default); union gated on positive arm-weight so the endpoints reduce exactly to the pure arms; regression tests in v3/test_hybrid.py, ModelUsage, answer_one_question(), _env_float(), fuse(), _minmax(), prepare_over_corpus(), Prepared (+10 more)

### Community 17 - "2026-07-25-combine-clusterk-hybrid-and-j..."
Cohesion: 0.14
Nodes (17): Session entry: gitignored state-transfer docs in docs/state, newest dated doc is the entry point; current entry 2026-07-28-audit-absorption-full-revert-corroboration-probe.md — five-reviewer audit verdicts on every shipping claim, the full revert to 5006fed, the absorbed rewrite-thread lessons (topic ≠ evidence, membership measurements, evidence-budget design), the graph topology/adjacency facts (one gold file per question; discrimination inside scope territory is the whole residual), the open-decisions list; the corroboration probe it specs has run: real signal, redundant with description distance, oracle headroom +0.21 in-territory, the Part-J discriminator remains unfound; predecessors 2026-07-25 (combine sweep, cluster-K runs, hybrid arm, judged-eval burn) and 2026-07-22 (cluster-K concept, curve-walk results) hold the definitions; older live threads: 2026-06-25 artefact tag-facet design (content-profile + guide-link, facets = weight+direction measured by geometry, one edge per tag carrying the full facet vector; DESIGN.md §13–14 / MODEL_CONTRACTS §1 are stale) and 2026-06-25 v3 vector eval (k-vs-top-k, judged metrics, k=50 / gold-100, NIM-throttle run ops), Cluster-K / best-fit on the rebuilt combine (HERB_CURVE_WALK=1, gold-100): clusterK 0.7341/nDCG 0.4748; clusterK+global-norm (clusterKglob) 0.7492/nDCG 0.4756 = best artefact config of the session, beating flat-global 0.6812 and det-default 0.7339; K=50 on all 100 questions — the K-decision is inert (never cuts below the ceiling); the gain is the curve-walk's progressive-frontier ordering, not cluster-K choosing K, Corroboration probe (next measurement; offline, free; pending the user's go): can rare-tag sharing between candidates express 'same event' (not just 'same topic') inside scope territory — the discriminator Part-J step (3) needs; per gold-100 question: territory = gold file's chunks, seeds = top-ranked kept chunks from the committed-baseline detCUR run, corroboration score = rare tags shared with seeds (degree cap swept <=5/<=10/<=25/<=50; seed depth swept top-10/top-25), Part-J control flow (designed, researched, not built): (1) constrain with stated hard fields when they are constraints; (2) desc = recall door inside that space; (3) a different signal discriminates evidence from topical siblings; (4) cluster/gap cut chooses K on the discriminated list; open forks — hard filter vs boost, and which discriminator; cluster-K (the user's concept) returns after a discriminator exists, Judge-run rule: each claude-* judge/generation attempt is a full billable run on the user's subscription window; on failure stop and diagnose from disk; never delete saved __j result dirs, never re-run a full judge to fix a partial failure — eval_results.jsonl IS the saved judge scores and the harness resumes from it, keeping finished rows and filling only the gaps, Run-folder provenance: detREBUILD, detREBUILD_artComp, detPOOLCUT, detCURVEK, detTAGBAR, detADMIT, detDESCCORR, detDESCFIRST (all __gold100, 2026-07-25 to 07-28) come from uncommitted code and are comparable only to each other; committed-baseline gold-100 references: detBASE 0.7039, detCUR 0.7339, detNONE 0.7390, detGLOB 0.7394, clusterK 0.7341, clusterKglob 0.7492 (2026-07-23); the 0.7339-vs-0.6906 gap is a cross-lineage comparison — never present either lineage's numbers as the other's, Combine toggles (env, defaults byte-identical when off): HERB_AGG sum|max = corroboration aggregation, HERB_NORM relative|absolute|none, HERB_NORM_SCOPE per_path|global, per-modifier strengths (HERB_STR_FACET default 0.0); HERB_NO_REVIEW=1 skips the sufficiency review for clean retrieval sweeps; the user's sweep axes verbatim: combined, per path, relative, relative per path, Audit verdict on the +0.030 combine rebuild: supported (p=0.0005, CI +0.014..+0.054, 23 up / 5 down) — a defect fix, not a swept knob (+9 more)

### Community 18 - "artefact_v1.py"
Cohesion: 0.14
Nodes (17): answer_one_question(), _env_float(), _env_int(), _hint_match(), _load_verified_doc(), _nth_entry(), _open_area(), Prepared (+9 more)

### Community 19 - "artefact_v1_det.py"
Cohesion: 0.19
Nodes (17): _anchors(), answer_one_question(), _det_plan(), _facet_direction(), _facet_router(), _facet_shaper(), _facet_triggers(), _phrase_at() (+9 more)

### Community 20 - "orchestrator.py"
Cohesion: 0.17
Nodes (17): _arm_name(), build_shared_generator(), _done_ids(), load_chosen_questions(), open_corpus(), Handle onto the RAG-safe corpus — the only data a pipeline sees. Validates, Build the ONE generator (on NIM) injected into every arm.     Returns a callabl, Strip the truth: hand the arm the question's id + text ONLY, as the (id,     te (+9 more)

### Community 21 - "2026-07-22-v1-curve-walk-facets-and-clus..."
Cohesion: 0.12
Nodes (16): Curve-walk gold-100 result: recall_id 0.7005 / precision_id 0.0545 vs flat baseline 0.6972 / 0.0518 — first variant beating baseline on both; kept hit the 50-ceiling on all 100 questions, _curve_k: break in a descending curve — unit square, head-to-tail straight fit, cut at the point furthest below it, 1e-9 noise guard, no dip means keep everything, Best-fit cuts on ladder-shaped curves seam-lock: the rewrite's desc admission produced semantic in {65, 33} exactly (82/18 of 100) — the K_LEVELS staircase deciding, not evidence; same class as the condemned value-knee; any future cut rule must be checked against a structureless-pool control, Substitution failure (do not repeat): the value knee was built instead of the discussed height walk because it was less invasive; the user's concepts are the spec, Open decision: does stated scope count toward K, or corroborate and rank only, Measurement debts: haiku leg untested on the current build; k=5/10/20 need real runs; the detW2 gain bundles three membership changes, HERB_CURVE_K naming flagged by the user (reads as forcing K=1; it is a boolean); rename to HERB_CURVE_WALK=1 or kill the flag — choice pending, Middle design (unsigned): desc finds + stated scope mints + tags score-only — the measurement-consistent shape; scope was corroborate-only across the entire rewrite lineage including detREBUILD, so 'scope needn't mint' has no test; graph side shows scope territory contains 100% of the loss (+8 more)

### Community 22 - "DeterministicPlanTests"
Cohesion: 0.16
Nodes (3): DeterministicPlanTests, _S, _Vocab

### Community 23 - "test_hybrid.py"
Cohesion: 0.14
Nodes (8): _fake_lucene(), _fake_vector(), MinMaxTests, PrepareStatsTests, Regression checks for the hybrid arm — min-max late fusion of the lucene and vec, A vector stand-in: retrieve returns (ranked unit dicts, ModelUsage), the pair, A lucene stand-in: prepare hands back a Prepared-ish with a BuildStats;     retr, RetrievalFlagTests

### Community 24 - "derive_corpus()"
Cohesion: 0.25
Nodes (12): derive_corpus(), DeriveReport, _dump(), One-time prep: derive the corpus view a dataset's pipeline run scans.  The pub, 4. Pipeline skeleton, _full_product(), _make_raw(), test_corpus_view_strips_rag_unsafe_keys_and_copies_rest_verbatim() (+4 more)

### Community 25 - "2026-07-28-audit-absorption-full-revert-..."
Cohesion: 0.15
Nodes (13): One gold file per question, 100/100: covered gold sits in exactly one file; missed gold is inside that file 95/95; the dominant retrieved file IS the gold file 90/95; retrieval holds mean 32 chunks of the gold file and the remainder (~130 chunks) contains all missed gold at ~4% density — membership was never the residual problem, discrimination inside scope territory is; ~18 of 50 kept slots go out-of-territory (provably never gold), so spending the whole budget in-territory is free recall, Corroboration probe protocol: Stage 1 signal test — do missed-gold chunks rank above the non-gold territory remainder by corroboration score (per-question and pooled enrichment/AUC); no separation means stop, the graph cannot express event identity and the wall is the finding; Stage 2 ordering test (only if stage 1 separates) — replace the kept-50 tail with top corroborated territory chunks, paired recall_id vs baseline ordering, desc-distance fill (the decisive control), and random territory fill (floor); pre-declared bar: beats the desc-distance control with effect >~+0.03 (MDE), audit-grade stats; a positive result inherits the tag-provenance asterisk until the tag-provenance check runs, Tags do not need to mint membership: desc-only ~ desc+tight-tags (0.625 vs 0.634); tags-only collapses (0.085, broken-run caveat); under det, desc carried ~88% of admit's recovered gold and tag areas latched onto PR/URL-style tags, Topic is not evidence: ranking optimizes 'about the query', not 'holds the citations'; gold membership in HERB is co-citation in the oracle answer — event identity, not query similarity — which is why similarity re-ranks wall, Leakage audit: the arm resolves chunk text from full raw HERB at answer time — quarantine rests on herb-eval locator discipline, not v3 code; no direct answer-text leakage found in any of 129 run dirs; soft vectors (tag vocabulary from the oracle-reading tagger; relevance_to_file from the contaminated build) unverified; HERB_SCOPE_REACH/HERB_TAG_PURE exist in no source era — only in five 2026-07-23 manifests, Audit verdict on 'leads all valid metrics': false as worded — answer_correctness vs vector n.s. (p=0.096) and generator-confounded (sonnet vs qwen); the faithfulness and context_recall_llm leads hold within the haiku judge, Audit verdict on 'pool ceiling 1.0 / all loss is ordering': an n=10 diagnostic, unverifiable from disk (traces carry locators, not ids); true of union-ranking machinery, false of any semantic-only keep, Three retrieval paths (user's terms): tag areas (the walk), description lookups, stated scope; pool = union of the three, dominated by stated scope (hard-field OR-match, no LIMIT — 1,078 chunks on one CoachForce question, 84% off-target); gold ~100% in the pool on 10smoke; the loss is ordering within the top-k cut (+5 more)

### Community 26 - "contract.py"
Cohesion: 0.18
Nodes (12): generator_messages(), generator_output_text(), generator_usage_from_nim(), generator_user_content(), model_usage_from_telemetry(), contract.py — the shared shapes every arm and evaluator imports., Normalise a generator return into (answer, ModelUsage)., The exact system + user messages the shared generator sends to NIM. (+4 more)

### Community 27 - "score_outputs()"
Cohesion: 0.17
Nodes (11): _build_metrics(), corpus_gold_text(), _print_status_summary(), One line per metric that produced any non-ok cell, so failures are visible at, Instantiate each selected metric with the wrappers it needs, then init() it —, Every string leaf of an artifact record, joined — a faithful text rendering of, artifact id -> its text. The non-LLM context metrics score retrieved text     ag, ENTRY: per (output, question) score every metric in metrics_to_run() ->     list (+3 more)

### Community 28 - "answer_one_question()"
Cohesion: 0.18
Nodes (12): answer_one_question(), gather_unit_text(), _qid_text(), (id, question_text) from a QuestionWithTruth, dict, (id, text) tuple, or     a, Sparse top-k retrieval for the question text -> list of unit dicts     {id, tex, Read the native artifact id off the unit. Fills ArmOutput.context_ids     (same, Collect the units' text. Fills ArmOutput.contexts + feeds the generator., Normalise a generator's return into (answer, ModelUsage). (+4 more)

### Community 30 - "_retrieve()"
Cohesion: 0.18
Nodes (11): _agg(), _gap_break(), _mod(), _n_levels(), A priority modifier over the normalized base: strength 0 returns 1 (the     mod, interpret-plan -> (pointer rows cut at k, query embed ModelUsage,     retrieval, The walk's stopping test, read from its own trajectory. The height     gaps bet, The number of doubling levels a stated-scope ranked set of size n spans —     t (+3 more)

### Community 31 - "_part_levels()"
Cohesion: 0.25
Nodes (11): _guidance(), _level_chain(), _multi_k_support(), _part_levels(), The anchor leaf's containing-cluster chain through the dendrogram,     finest t, Cluster guidance g per pool tag, in [0, 1]. The part's facet values     normali, One part -> its widening levels: [{height, tags: [(name, support)]}]     finest, `a` scaled to unit length along its last axis; a zero vector has no     directi (+3 more)

### Community 32 - "Audit verdicts: haiku < det supported on..."
Cohesion: 0.24
Nodes (9): Audit verdict on recall_id 0.64 vs 0.09/0.11: real arithmetic, ~85% unit artifact (artefact ~443 ids/q vs 50; one-id-per-chunk counterfactual -> 0.090, about lucene's level); ship only matched-id-budget 0.73-0.75 vs 0.41/0.39/0.27, ~1.8x, Holm p~3e-4, rank-biserial 0.85-1.0; missing control = granularity-matched baseline (packed chunks + bundle credit), which doubles as the graph-attribution ablation, Audit verdicts: haiku < det supported on gold-100 (-0.130, p=5e-5); hybrid loses at matched budget supported retrieval-only — judged comparison open, and the partial 2026-07-23 JUDGE_* dirs are unusable (arm-correlated missingness: artefact answer_correctness 0/100 cells), Judged eval, partial (artefact-global only, claude-haiku generator + judge): faithfulness 0.8707 (68/100), context_recall_llm 0.6171 (91/100), semantic_similarity 0.3455 (100/100), context_recall_id 0.6812, rouge 0.1114, bleu 0.0241, answer_correctness 0/100; faithfulness 0.87 = artefact answers strongly grounded in their evidence; hybrid and vector judging in progress at session end — their __j-claude-haiku-4-5 dirs hold what completed, Matched id-budget comparison (~500 ids each, gold-100, retrieval-only): artefact haiku-global 0.6812 and det 0.7339 vs pure vector 0.4100, hybrid α=0.5 0.3883, pure lucene 0.2742 — the artefact's lead is not an id-budget artifact; fusion ≈ pure vector (weak lucene drags it); the artefact carries ~500 ids from its 50 chunks while the baselines are 1:1, so raw recall_id@50 is not comparable across them — match the id budget (baselines at k=500), main(), _print(), compare_arms.py — side-by-side RAGAS comparison across the gold-100 runs.  Wal, (arm, k) -> {metric: [values...]} over the ok cells in eval_results.jsonl. (+1 more)

### Community 33 - "2026-07-22-retrieval-literature-sweep.md"
Cohesion: 0.22
Nodes (9): GraphRAG family: Microsoft GraphRAG's communities are permanent and query-blind (the contrast case); HippoRAG 1/2 validate seed-weighted PPR over a tag-like graph; G-Retriever's prize-collecting Steiner tree is a one-shot budgeted subgraph alternative; ToG's stop rule is LLM sufficiency under a hard cap, Query-conditioned local graph clustering: Andersen-Chung-Lang PPR + sweep cut formalizes a soft query-relative region with a principled boundary; heat kernel (Kloster-Gleich) is the tighter-radius variant; Crestani's spreading-activation constraints catalogue the flooding failure modes, LLM-emitted scalars as ranking features: document-level LLM relevance labels can be load-bearing (Thomas et al., Bing/SIGIR 2024) but label-level agreement is fragile and scalar outputs compress; NO published validation of LLM-emitted per-edge numeric weights — HippoRAG-line systems derive weights structurally, LLM only discrete decisions, Literature sweep coverage gaps: the 2026-07-22 sweep covers diffusion-framed expansion (PPR, HippoRAG), communities (rejected: query-blind), path methods, degree/IDF seeds; never covered — plain co-tag one-hop, file/container-sibling expansion, graph-native clustering of the chunk graph as areas, bipartite similarity, hub-tag IDF over own vocabulary, Five-finding synthesis: weighted score-space fusion over RRF; the more-tags-more-votes pathology starts at emission; PM-2 for the hard-k budget; query-relative areas = seed-weighted local diffusion; LLM per-edge scalars are unvalidated territory, Progressive budgeted retrieval: PM-2 proportional slot allocation (each of k slots to the most under-served aspect) beat xQuAD on TREC diversity — the published mechanism for multi-frontier selection under hard k; bandit budget allocation across subqueries gains +35% precision, Faceted / multi-aspect query representation: MADRAL fuses aspects into one vector pre-retrieval; its ECIR 2024 reproduction failed (learned aspects can be dead weight); ColBERT's MaxSim-then-sum is the proven score-space per-aspect aggregation, Rank fusion theory: RRF is rank-only and erases within-list multipliers (Cormack 2009); normalized-score convex combination beats RRF in- and out-of-domain (Bruch et al., TOIS 2023); weighted RRF puts importance in per-list weights; LLMs emit the prompted subquery count regardless of need (arXiv:2510.18633) (+1 more)

### Community 34 - "_chat_json()"
Cohesion: 0.20
Nodes (10): _chat_json(), _clean_tag(), _extract_json(), _interpret(), _parse_gate(), The interpreter holds the conversation: evidence is shown cumulatively     at t, One JSON turn on the interpreter model -> (parsed_json, tokens_in,     tokens_o, Normalise the model's loose gate into strict scope hints: string-or-null     fi (+2 more)

### Community 35 - "InterpreterError"
Cohesion: 0.22
Nodes (9): _driver(), _guide_key(), _guide_tables(), InterpreterError, prepare_over_corpus(), The cache entry name for one build of the membership matrices: the     database, The cached membership matrices, loaded once per process: `U` stacked     (n_fac, A failed interpreter turn. Carries the model usage spent across the     turn's (+1 more)

### Community 36 - "GeminiCliRegressionTests"
Cohesion: 0.22
Nodes (3): GeminiCliRegressionTests, Regression checks for Gemini CLI process and quota handling., _TimeoutProcess

### Community 37 - "load_questions()"
Cohesion: 0.25
Nodes (7): main(), The gold-N: a balanced ANSWERABLE subset, drawn by seeded round-robin     over, stratified_gold(), QuestionWithTruth, load_questions(), questions.py — load the HERB question set from data/questions.jsonl.  Each rec, The HERB question set as QuestionWithTruth records.

### Community 38 - "_selfcheck()"
Cohesion: 0.22
Nodes (9): EvalResult, model_usage_from_dict(), Rehydrate ModelUsage from a persisted dict (arm_outputs / run_manifest)., A persisted arm-output record (dict) -> contract.ArmOutput, so the scorer     r, -> list[contract.EvalResult]. The arm label + corpus (so an evaluator can     d, Wiring check with fakes — no NIM, no bm25s, no disk questions. Verifies the, _rehydrate(), run_one_evaluator() (+1 more)

### Community 39 - "main()"
Cohesion: 0.47
Nodes (8): _cosine(), _embed_texts(), expand_folders(), _folder_question_ids(), main(), offline_eval.py — score run folders with the no-judge metrics.  Step 2 of the de, score_folder(), Path

### Community 40 - "_NimEmbedder"
Cohesion: 0.32
Nodes (3): BaseRagasEmbeddings, _NimEmbedder, RAGAS embeddings driven by nim.post — llama-nemotron-embed, asymmetric: question

### Community 41 - "_JudgeLLM"
Cohesion: 0.36
Nodes (3): BaseRagasLLM, _JudgeLLM, RAGAS LLM driven by nim.post or a headless subscription CLI.     The backend fol

### Community 42 - "Metric definitions: recall_id = |retriev..."
Cohesion: 0.29
Nodes (7): Audit panel 2026-07-28: five parallel read-only reviewers (logic, maths, order-of-operations, overfitting/leakage, statistics) over code + v3/output + state docs; stats protocol = paired sign-flip permutation (20k, seed 20260728), BCa bootstrap CI, Holm within declared families, Metric definitions: recall_id = |retrieved context_ids ∩ gold citations| / |gold|, union-based, cross-arm valid; nDCG@50 from meta.chunk_ids (ranked kept chunks, first-gold-gain, self-normalized IDCG), within-arm only; truncate_k slicing context_ids[:k] is invalid for the artefact arm (ids not 1:1 with chunks); stats protocol = paired sign-flip permutation + Wilcoxon + exact sign test + BCa CI + Holm, conjunctive decision rule, m≥8 detectability gate reported not filtered, Evidence-budget design (user-specified, for a fresh signed rebuild on the committed baseline): total-bag budget over whole chunks kept in rank order until a char ceiling — per-chunk truncation explicitly rejected by the user; CLI shape --evidence-cap matched (= 72,000 chars = thesis 40x1800) and --max-context-chars N; measured offline: artefact at 72k keeps ~14 chunks, recall ~0.69 -> ~0.43, vector barely changes — the artefact's lead depends on the budget currency (ids 0.73 vs 0.41; chars ~0.43), so the thesis comparison table needs this third currency beside matched-k and matched-ids; hybrid needs the same apply_evidence_budget call every other arm has, main(), truncate_k.py — re-emit a run's arm_outputs at each eval depth k, no regeneratio, One arm_outputs record cut to its first k chunks, ids rebuilt from the     kept, truncate_record()

### Community 43 - "_normalize()"
Cohesion: 0.29
Nodes (8): _absolute(), _minmax(), _norm_pool(), _normalize(), Min-max a path's base scores against the given bounds: hi <= lo (a single     s, Min-max normalize a path's per-chunk base scores onto [0, 1] over that     path, A pool-independent bounded score: the raw support saturated against a     per-p, Put the three paths' bases on a comparable scale by the HERB_NORM mode:     rel

### Community 44 - "_embed_cached()"
Cohesion: 0.25
Nodes (8): _embed_cached(), _embed_key(), _load_cached_vec(), Content address for one embedding: (embed model, input_type, text), each     le, The cached embedding for `key`, or None on a miss. A corrupt or     half-writte, Write one embedding under its content address, published atomically so a     co, Embed `texts` through the shared NIM embedder with a persistent per-text     ca, _store_cached_vec()

### Community 46 - "_score_all()"
Cohesion: 0.29
Nodes (7): _load_rows(), One contract pair -> a RAGAS SingleTurnSample. reference = the gold answer     (, Parsed rows already in results_path. A torn trailing line from a killed write, Score every (question, metric) cell -> list[EvalResult], in ordered passes: the, _score_all(), _to_sample(), SingleTurnSample

### Community 47 - "backfill_file()"
Cohesion: 0.38
Nodes (6): backfill_file(), main(), Path, backfill_token_split.py — add tokens_in/tokens_out ONLY on rows with no token da, backfill_generator_usage(), Add tokens_in/tokens_out only when generator has no token fields at all.

### Community 51 - "ragas_catalog.py"
Cohesion: 0.33
Nodes (5): _check(), Metric, ragas_catalog.py — the full RAGAS metric menu + the toggle for which ones a run, Fail loud before a run if SELECTED is malformed., RAGAS (eval/ragas.py) is the scorer; the full metric menu lives in eval/ragas_catalog.py; every judge-free deterministic metric always runs because it costs nothing, and SELECTED adds the judged ones

### Community 52 - "_interpret_cached()"
Cohesion: 0.33
Nodes (6): _interp_key(), _interpret_cached(), Content address for one interpretation: (interpret model, interpreter     signa, Write one interpreted plan under its content address, published     atomically, interpret with a persistent plan cache keyed by (model, prompt     signature, q, _store_interp()

### Community 53 - "abort.py"
Cohesion: 0.33
Nodes (5): Aborted, abort.py — press 'q' to stop a running gen/eval loop.  Ctrl+C can be swallowed, Raised from inside an in-flight call when q has been pressed, so a worker     p, Start a daemon thread that sets the abort flag when q/Q is pressed. No-op     w, watch()

### Community 58 - "Audit verdict on scope-dominance: haiku..."
Cohesion: 0.40
Nodes (5): Audit verdict on scope-dominance: haiku leg only (global +0.077, p=6e-4; absolute -0.068); det leg insensitive after Holm; ship as benchmark-structure alignment (questions name their product = gold's partition key), not a retrieval law, Haiku combine sweep (cross-part live, 3-8 parts/q, gold-100): default 0.6039/nDCG 0.416; global-norm 0.6812/nDCG 0.462; none 0.6536/nDCG ~0.462; absolute 0.5359; max (corroboration off) nDCG −0.026 → corroboration/sum helps ordering; facets null; the per-path/absolute norm loses — letting stated scope dominate (global/none) wins, Audit verdict on facets: not a point null — bounded failure-to-detect (+/-0.035), tendency weakly positive on ordering, Geometric det facet channel (HERB_DET_FACETS support/routing/edges) moved recall ≤ +0.003 at k=50 — facet placement, not facet values, is the open question, Global normalization is a scale artifact — stated scope's extend=True level count hands it the win; report the result as 'scope-dominance wins', never as 'global normalization is correct'

### Community 59 - "_gemini_terminal_quota_error()"
Cohesion: 0.40
Nodes (5): _gemini_quota_error_row(), _gemini_terminal_quota_error(), A terminal Gemini quota/entitlement rejection cannot improve with a retry., Whether a cell has Gemini CLI's terminal quota/entitlement rejection., Exception

### Community 60 - "export_raw.py"
Cohesion: 0.60
Nodes (4): _collect_rows(), main(), Path, export_raw.py — dump all eval_results to a single long-format CSV.      python

### Community 64 - "herb-eval.dump"
Cohesion: 0.50
Nodes (3): herb-eval.dump, exjobbet — HERB evaluation harness, herb-eval graph topology (run_id pilot_full_herb, read-only probe): 4,869 chunks, 19,716 tags, 33 files, 67,913 HAS_TAG edges, one connected component; connectivity dense but generic — 34.4% of tags on >=2 chunks, hub tags are generic vocabulary (salesforce 534, tensorflow 428, gdpr 287), median chunk is one shared tag from ~482 chunks (~10% of graph); discriminative structure thin — tags deg<=10, and >=2-shared-tag pairs are 1.9% of all pairs

### Community 65 - "_tag_affinity()"
Cohesion: 0.50
Nodes (4): _hint_terms(), Cypher boolean terms for the interpreted scope hints, over chunk     fields. ([, Structural affinity per tag: the fraction of the tag's edges landing on     hin, _tag_affinity()

### Community 66 - "build_questions.py"
Cohesion: 0.67
Nodes (3): build(), mint_id(), build_questions.py — one-shot: build the HERB question set from raw.  HERB shi

### Community 67 - "build_eval_manifest()"
Cohesion: 0.50
Nodes (4): EvalManifest, Provenance for an `evals` run — ONE scorer over one run file., build_eval_manifest(), Provenance for the eval side -> contract.EvalManifest (timestamp now, UTC).

### Community 68 - "build_run_manifest()"
Cohesion: 0.50
Nodes (4): Provenance for a `questions` run — answers generated by ONE arm., RunManifest, build_run_manifest(), Provenance for the generation side -> contract.RunManifest (timestamp now,

## Knowledge Gaps
- **112 isolated node(s):** `Path`, `Metric`, `Response`, `All three arms answer with the same generator, built once in the orchestrator and injected, so any difference is retrieval not the LLM; beyond that generator and the corpus on disk the arms share nothing, each reading, indexing and ranking the corpus with its own code`, `lucene arm = BM25 baseline with its own index over the corpus` (+107 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BuildStats` connect `ModelUsage` to `vector.py`, `InterpreterError`, `index.py`, `_selfcheck()`, `graph_store.py`, `main()`, `hybrid.py`, `artefact_v1.py`, `AnswerContractTests`, `test_hybrid.py`, `contract.py`, `FuseTests`, `_part_levels()`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Why does `ModelUsage` connect `ModelUsage` to `vector.py`, `index.py`, `graph_store.py`, `ragas.py`, `hybrid.py`, `artefact_v1.py`, `test_hybrid.py`, `contract.py`, `score_outputs()`, `FuseTests`, `_part_levels()`, `InterpreterError`, `_selfcheck()`, `main()`, `_NimEmbedder`, `_JudgeLLM`, `_score_all()`, `AnswerContractTests`, `_gemini_terminal_quota_error()`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Why does `_selfcheck()` connect `_selfcheck()` to `build_eval_manifest()`, `build_run_manifest()`, `load_questions()`, `ModelUsage`, `orchestrator.py`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `ModelUsage` (e.g. with `CompletedProcess` and `_JudgeLLM`) actually correct?**
  _`ModelUsage` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `BuildStats` (e.g. with `_write_build_stats()` and `ModelUsage`) actually correct?**
  _`BuildStats` has 32 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Ablation: attribute the gold-100 k=10 context_recall_id between the corpus-gene`, `Resume: per-question records already computed (id -> record). The     interpret`, `abort.py — press 'q' to stop a running gen/eval loop.  Ctrl+C can be swallowed` to the rest of the system?**
  _364 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `_plan()` be split into smaller, more focused modules?**
  _Cohesion score 0.05211141060197664 - nodes in this community are weakly interconnected._