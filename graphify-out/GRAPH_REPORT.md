# Graph Report - .  (2026-07-31)

## Corpus Check
- 61 files · ~30,144 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1109 nodes · 1934 edges · 76 communities (66 shown, 10 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 129 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY__Session|_Session]]
- [[_COMMUNITY_index.py|index.py]]
- [[_COMMUNITY_chunk.py|chunk.py]]
- [[_COMMUNITY_v3README|v3/README.md]]
- [[_COMMUNITY_prepass.py|prepass.py]]
- [[_COMMUNITY_probe.py|probe.py]]
- [[_COMMUNITY_2026-07-20-v1-query-relative-areas|2026-07-20-v1-query-relative-areas.md]]
- [[_COMMUNITY_FuseTests|FuseTests]]
- [[_COMMUNITY_run.py|run.py]]
- [[_COMMUNITY_nim.py|nim.py]]
- [[_COMMUNITY_DESIGN|DESIGN.md]]
- [[_COMMUNITY_scan_dataset()|scan_dataset()]]
- [[_COMMUNITY_vector.py|vector.py]]
- [[_COMMUNITY_lucene.py|lucene.py]]
- [[_COMMUNITY_ragas.py|ragas.py]]
- [[_COMMUNITY_ModelUsage|ModelUsage]]
- [[_COMMUNITY_artefact.py|artefact.py]]
- [[_COMMUNITY_artefact_v1_det.py|artefact_v1_det.py]]
- [[_COMMUNITY_2026-07-22-v1-curve-walk-facets-and-clus...|2026-07-22-v1-curve-walk-facets-and-clus...]]
- [[_COMMUNITY_orchestrator.py|orchestrator.py]]
- [[_COMMUNITY_DeterministicPlanTests|DeterministicPlanTests]]
- [[_COMMUNITY_hybrid.py|hybrid.py]]
- [[_COMMUNITY_derive_corpus()|derive_corpus()]]
- [[_COMMUNITY_2026-07-28-audit-absorption-full-revert-...|2026-07-28-audit-absorption-full-revert-...]]
- [[_COMMUNITY_artefact_v1.py|artefact_v1.py]]
- [[_COMMUNITY_Audit verdicts haiku  det supported on...|Audit verdicts: haiku < det supported on...]]
- [[_COMMUNITY_2026-07-25-combine-clusterk-hybrid-and-j...|2026-07-25-combine-clusterk-hybrid-and-j...]]
- [[_COMMUNITY_score_outputs()|score_outputs()]]
- [[_COMMUNITY_reembed_herb_eval.py|reembed_herb_eval.py]]
- [[_COMMUNITY__retrieve()|_retrieve()]]
- [[_COMMUNITY_2026-07-22-retrieval-literature-sweep|2026-07-22-retrieval-literature-sweep.md]]
- [[_COMMUNITY__chat_json()|_chat_json()]]
- [[_COMMUNITY_GeminiCliRegressionTests|GeminiCliRegressionTests]]
- [[_COMMUNITY_Audit verdict on scope-dominance haiku...|Audit verdict on scope-dominance: haiku...]]
- [[_COMMUNITY_RuntimeError|RuntimeError]]
- [[_COMMUNITY_load_questions()|load_questions()]]
- [[_COMMUNITY_contract.py|contract.py]]
- [[_COMMUNITY_main()|main()]]
- [[_COMMUNITY__NimEmbedder|_NimEmbedder]]
- [[_COMMUNITY__JudgeLLM|_JudgeLLM]]
- [[_COMMUNITY__embed_cached()|_embed_cached()]]
- [[_COMMUNITY__part_levels()|_part_levels()]]
- [[_COMMUNITY_main()|main()]]
- [[_COMMUNITY_embed_tags.py|embed_tags.py]]
- [[_COMMUNITY_InterpCacheTests|InterpCacheTests]]
- [[_COMMUNITY__score_all()|_score_all()]]
- [[_COMMUNITY__normalize()|_normalize()]]
- [[_COMMUNITY__embed()|_embed()]]
- [[_COMMUNITY_backfill_file()|backfill_file()]]
- [[_COMMUNITY__selfcheck()|_selfcheck()]]
- [[_COMMUNITY_LevelChainTests|LevelChainTests]]
- [[_COMMUNITY_Rebuilt combine (v3pipelinesartefact_v...|Rebuilt combine (v3/pipelines/artefact_v...]]
- [[_COMMUNITY_ragas.py — multidimensional answerevide...|ragas.py — multidimensional answer/evide...]]
- [[_COMMUNITY_ragas_catalog.py|ragas_catalog.py]]
- [[_COMMUNITY__interpret_cached()|_interpret_cached()]]
- [[_COMMUNITY_GapBreakTests|GapBreakTests]]
- [[_COMMUNITY_Pass2ValidationTests|Pass2ValidationTests]]
- [[_COMMUNITY_RetrievalFlagTests|RetrievalFlagTests]]
- [[_COMMUNITY_13. Semantic dimensions — the research b...|13. Semantic dimensions — the research b...]]
- [[_COMMUNITY_Cluster-K concept (user canon) the clus...|Cluster-K concept (user canon): the clus...]]
- [[_COMMUNITY__gemini_terminal_quota_error()|_gemini_terminal_quota_error()]]
- [[_COMMUNITY_export_raw.py|export_raw.py]]
- [[_COMMUNITY_ModifierLerpTests|ModifierLerpTests]]
- [[_COMMUNITY_MultiKSupportTests|MultiKSupportTests]]
- [[_COMMUNITY_SufficiencyTests|SufficiencyTests]]
- [[_COMMUNITY_herb-eval.dump|herb-eval.dump]]
- [[_COMMUNITY__tag_affinity()|_tag_affinity()]]
- [[_COMMUNITY_build_questions.py|build_questions.py]]
- [[_COMMUNITY_build_eval_manifest()|build_eval_manifest()]]
- [[_COMMUNITY__rehydrate()|_rehydrate()]]
- [[_COMMUNITY_unpack_generation()|unpack_generation()]]
- [[_COMMUNITY_build_run_manifest()|build_run_manifest()]]
- [[_COMMUNITY_truncate_k.py|truncate_k.py]]
- [[_COMMUNITY_A chunk reference in the resolver's self...|A chunk reference in the resolver's self...]]
- [[_COMMUNITY_`take` items evenly spread across a buck...|`take` items evenly spread across a buck...]]
- [[_COMMUNITY__score_one()|_score_one()]]

## God Nodes (most connected - your core abstractions)
1. `ModelUsage` - 38 edges
2. `_Session` - 35 edges
3. `_plan()` - 34 edges
4. `BuildStats` - 33 edges
5. `_row()` - 29 edges
6. `v3/README.md` - 24 edges
7. `chunk_file()` - 20 edges
8. `ArmOutput` - 20 edges
9. `_ground_row()` - 20 edges
10. `profile()` - 17 edges

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

## Communities (76 total, 10 thin omitted)

### Community 0 - "_Session"
Cohesion: 0.07
Nodes (22): CombineModeTests, CombineTests, CurveWalkTests, _desc_row(), DoorTraceTests, EmbedCacheTests, _ground_row(), InterpreterBackendTests (+14 more)

### Community 1 - "index.py"
Cohesion: 0.06
Nodes (61): Chunk, chunk_dataset(), load_key(), Scan a corpus-view dataset dir and chunk every JSON file in it. The     prose-v, write_chunks(), build(), driver(), ensure_database() (+53 more)

### Community 2 - "chunk.py"
Cohesion: 0.08
Nodes (50): _chunk_conversation(), chunk_file(), _chunk_prose_records(), _chunk_short_records(), _ep_tokens(), est_tokens(), expand(), _get() (+42 more)

### Community 3 - "v3/README.md"
Cohesion: 0.05
Nodes (47): Materialize the artefact graph into Neo4j: `Source -[:CONTAINS]-> File -[:CONTA, Agent roster — orchestrator routing: main-chat Claude is the orchestrator — talks to the user, routes every job to a specialist agent, does no hands-on work; plain questions get direct conversational answers; agents always run in the background — a foreground agent freezes the conversation; prompts are scoped to the change — a two-line change gets a two-line prompt, never a tree-wide audit unless the user asks; long runs happen in the user's terminal (agents prepare, the user runs); definitions in .claude/agents/ — v3-coder (v3 code changes), critical-reviewer (post-change v3 review), code-optimizer (performance, profiles first), maths-algorithmist (mathematical algorithm design and verification), order-of-operations (pipeline sequencing/data-flow correctness), logician (invariants, proof-or-counterexample), retrieval-scientist (retrieval design and experiments), eval-statistician (significance, judge reliability, judge-run cost math), results-analyst (v3/output numbers, metric validity binding), graph-refresher (refresh_graph.py + worklist processing), Artefact arm: the artefact is the system under test, rebuilt natively in v3/artefact — deterministic stages scan.py (file catalog → sha256/file_id), probe.py (shape recovery, RFC 6901 pointers), derive_corpus.py (oracle strip), resolver_prototype.py (reference resolution, hash-verified) exist and are tested; the HERB mapping key keys/Salesforce__HERB.yaml and design references DESIGN.md / MODEL_CONTRACTS.md live there; the graph proper (chunk → tag → facet retrieval) is the unbuilt part, pipelines/artifact.py the arm entry; graph spine Source → File → Chunk → Tag is closed canon, hard fields are chunk attributes, the graph is references into untouched raw source never copies; the model emits no numbers (tagger and interpreter), the chunk description is dead, tags are per-chunk contextual phrases; herb-eval (Neo4j) is the prior artefact build under the superseded design — contrast/forensic baseline only, never query herb (oracle-contaminated), CLAUDE.md — repo canon: layout, session entry, graph refresh, hard rules, agent roster, artefact arm, Hard rules: design sign-off before build; plain spoken English, short answers, verify claims against the real system; heed the user's intent — never correct it with stale context, surface a genuine conflict as a question; docs track reality — update design doc + memory in the same pass by removal of dead content, dated state/handoff docs are frozen; no historical or defensive comments — state only the present, comments feed the graph and memory; refresh the navigation graph at commit time, never per-edit — doc extraction is expensive so all changed docs ride the same pass; every runnable shows life instantly and progress continuously (banner before any heavy import, flush=True, v3/progress.py bars) — a silent terminal is a bug; critical-review logic changes only — background, one batched review per work burst, config flips / default changes / renames / comments / help text / doc lines get no review, Navigation graph: query graphify FIRST before grepping (graphify query / explain / path); rebuild with python refresh_graph.py at commit time — once per commit, right before committing, batching every edit since the last refresh; the ONLY rebuild path, never graphify --update (drops the external-doc bridges); a printed worklist means model extraction: process .refresh_worklist.json, bridge into .concept_index.txt, committed repo docs to graphify's semantic cache, gitignored state/handoff docs as sidecar fragments in .external_cache/ ({source_file,hash,nodes,edges}), then re-run, Repo layout: v3/ is the work — a lean HERB evaluation harness, three arms (artefact / lucene / vector) scored with RAGAS, self-contained, design reference v3/README.md; root canon (CLAUDE.md, README.md) plus the gitignored state/handoff docs under docs/ complete the picture, v2 Artefact Rebuild — Design (+39 more)

### Community 4 - "prepass.py"
Cohesion: 0.07
Nodes (40): _format_user(), interpret(), _load_gold100(), Stage query: interpret — one stateless structured call per prompt emits facet p, Fail loud on a schema-breaking response — never a silent partial., One stateless temp-0 structured call → (parsed_json, usage). Fail loud     on a, `per_type` per HERB answer type (person/content/company/pr/url)., Run the interpreter on a stratified slice of the gold-100 set; print     each q (+32 more)

### Community 5 - "probe.py"
Cohesion: 0.11
Nodes (37): Any, Collection, content_files(), derive_candidates(), DocLeaf, escape_pointer_token(), fuse(), fuse_files() (+29 more)

### Community 6 - "2026-07-20-v1-query-relative-areas.md"
Cohesion: 0.06
Nodes (36): Merge two shape signatures (array-element fusion and cross-file fusion)., Confirmed current-code problems, 6. Decisions made, Current fusion, `VizForce::a::16`, 4. Exact definitions and notation, 8. Rejected or dangerous interpretations, 1. Purpose of this state document (+28 more)

### Community 7 - "FuseTests"
Cohesion: 0.07
Nodes (9): AnswerContractTests, _fake_lucene(), _fake_vector(), FuseTests, MinMaxTests, Regression checks for the hybrid arm — min-max late fusion of the lucene and vec, A vector stand-in: retrieve returns (ranked unit dicts, ModelUsage), the pair, A lucene stand-in: prepare hands back a Prepared-ish with a BuildStats;     retr (+1 more)

### Community 8 - "run.py"
Cohesion: 0.09
Nodes (26): metrics_to_run(), main(), model_test.py — 3-question generator head-to-head through artefact_v1. Interpret, Judges with no queue to respect: open every cell at once., _wide_parallel_judge(), _fixed_ids_file(), _pid_alive(), Single-writer guard for run output folders. (+18 more)

### Community 9 - "nim.py"
Cohesion: 0.09
Nodes (26): Judged-eval failure modes are operational: NIM generator 404 (hosted-catalog outage) forces --generator claude-haiku-4-5; the claude CLI's 3-second stdin-wait trips under machine load, and answer_correctness makes the most sub-calls so it fails first; run serial/low workers on an unloaded machine and reap the claude process tree after, Progressive traversal without an answer-sufficiency oracle, Response, _back_off(), _claude_chat(), completed_calls(), _delay_after(), _fire() (+18 more)

### Community 10 - "DESIGN.md"
Cohesion: 0.07
Nodes (28): **Derive-corpus (one-time prep, per dataset that needs it)** — if the published, 9. Chunks, tags, and re-tagging, 9.6 Re-tag, do not migrate v1 tags, **topic** (aboutness / frame-domain), 9.1 A chunk is a coherent episode, not a fixed-size window, 13.3 Organizing principle — completeness across the totality + prompt/chunk symmetry, **Id-space assignment** — which fields carry which id-space (`userId` → employee,, 12. Eval implications (+20 more)

### Community 11 - "scan_dataset()"
Cohesion: 0.13
Nodes (24): json_pointer(), main(), v2 reference-resolver prototype — proves the 'graph is references' stance.  A, RFC 6901. Raises (loud) on any miss — never returns a silent default., ref = {file_path, sha256, scheme, address}. Fail loud on hash mismatch., resolve(), sha256_of(), unescape() (+16 more)

### Community 12 - "vector.py"
Cohesion: 0.11
Nodes (27): answer_one_question(), _artifact_text(), build_dense_index(), _cache_path(), gather_unit_text(), load_query_vecs(), prepare_over_corpus(), Prepared (+19 more)

### Community 13 - "lucene.py"
Cohesion: 0.12
Nodes (25): 9. Source-of-truth artifacts, answer_one_question(), build_sparse_index(), _flatten_one(), gather_unit_text(), ingest_corpus(), prepare_over_corpus(), Prepared (+17 more)

### Community 14 - "ragas.py"
Cohesion: 0.14
Nodes (20): CompletedProcess, _check_judge_context_budget(), _claude_verdict(), _codex_usage(), _codex_verdict(), _encoding_for(), _estimate_tokens(), _gemini_usage() (+12 more)

### Community 15 - "ModelUsage"
Cohesion: 0.21
Nodes (17): ModelUsage, InterpreterError, Prepared, A failed interpreter turn. Carries the model usage spent across the     turn's, Prepared, ArmOutput, BuildStats, ModelUsage (+9 more)

### Community 16 - "artefact.py"
Cohesion: 0.18
Nodes (18): answer_one_question(), _apply_literal_boosts(), _chunk_scores(), _embed_facet_phrases(), _phrase_weights(), prepare_over_corpus(), Prepared, _qid_text() (+10 more)

### Community 17 - "artefact_v1_det.py"
Cohesion: 0.19
Nodes (17): _anchors(), answer_one_question(), _det_plan(), _facet_direction(), _facet_router(), _facet_shaper(), _facet_triggers(), _phrase_at() (+9 more)

### Community 18 - "2026-07-22-v1-curve-walk-facets-and-clus..."
Cohesion: 0.12
Nodes (16): Curve-walk gold-100 result: recall_id 0.7005 / precision_id 0.0545 vs flat baseline 0.6972 / 0.0518 — first variant beating baseline on both; kept hit the 50-ceiling on all 100 questions, _curve_k: break in a descending curve — unit square, head-to-tail straight fit, cut at the point furthest below it, 1e-9 noise guard, no dip means keep everything, Best-fit cuts on ladder-shaped curves seam-lock: the rewrite's desc admission produced semantic in {65, 33} exactly (82/18 of 100) — the K_LEVELS staircase deciding, not evidence; same class as the condemned value-knee; any future cut rule must be checked against a structureless-pool control, Substitution failure (do not repeat): the value knee was built instead of the discussed height walk because it was less invasive; the user's concepts are the spec, Open decision: does stated scope count toward K, or corroborate and rank only, Measurement debts: haiku leg untested on the current build; k=5/10/20 need real runs; the detW2 gain bundles three membership changes, HERB_CURVE_K naming flagged by the user (reads as forcing K=1; it is a boolean); rename to HERB_CURVE_WALK=1 or kill the flag — choice pending, Middle design (unsigned): desc finds + stated scope mints + tags score-only — the measurement-consistent shape; scope was corroborate-only across the entire rewrite lineage including detREBUILD, so 'scope needn't mint' has no test; graph side shows scope territory contains 100% of the loss (+8 more)

### Community 19 - "orchestrator.py"
Cohesion: 0.19
Nodes (15): _arm_name(), build_shared_generator(), _done_ids(), load_chosen_questions(), open_corpus(), Handle onto the RAG-safe corpus — the only data a pipeline sees. Validates, Build the ONE generator (on NIM) injected into every arm.     Returns a callabl, Ids already answered — one per line in arm_outputs.jsonl. This is the resume (+7 more)

### Community 20 - "DeterministicPlanTests"
Cohesion: 0.16
Nodes (3): DeterministicPlanTests, _S, _Vocab

### Community 21 - "hybrid.py"
Cohesion: 0.19
Nodes (14): answer_one_question(), _env_float(), fuse(), _minmax(), prepare_over_corpus(), Prepared, _qid_text(), (id, question_text) from a QuestionWithTruth, dict, (id, text) tuple, or a     b (+6 more)

### Community 22 - "derive_corpus()"
Cohesion: 0.25
Nodes (12): derive_corpus(), DeriveReport, _dump(), One-time prep: derive the corpus view a dataset's pipeline run scans.  The pub, 4. Pipeline skeleton, _full_product(), _make_raw(), test_corpus_view_strips_rag_unsafe_keys_and_copies_rest_verbatim() (+4 more)

### Community 23 - "2026-07-28-audit-absorption-full-revert-..."
Cohesion: 0.15
Nodes (13): Audit panel 2026-07-28: five parallel read-only reviewers (logic, maths, order-of-operations, overfitting/leakage, statistics) over code + v3/output + state docs; stats protocol = paired sign-flip permutation (20k, seed 20260728), BCa bootstrap CI, Holm within declared families, Corroboration probe protocol: Stage 1 signal test — do missed-gold chunks rank above the non-gold territory remainder by corroboration score (per-question and pooled enrichment/AUC); no separation means stop, the graph cannot express event identity and the wall is the finding; Stage 2 ordering test (only if stage 1 separates) — replace the kept-50 tail with top corroborated territory chunks, paired recall_id vs baseline ordering, desc-distance fill (the decisive control), and random territory fill (floor); pre-declared bar: beats the desc-distance control with effect >~+0.03 (MDE), audit-grade stats; a positive result inherits the tag-provenance asterisk until the tag-provenance check runs, Tags do not need to mint membership: desc-only ~ desc+tight-tags (0.625 vs 0.634); tags-only collapses (0.085, broken-run caveat); under det, desc carried ~88% of admit's recovered gold and tag areas latched onto PR/URL-style tags, Topic is not evidence: ranking optimizes 'about the query', not 'holds the citations'; gold membership in HERB is co-citation in the oracle answer — event identity, not query similarity — which is why similarity re-ranks wall, Leakage audit: the arm resolves chunk text from full raw HERB at answer time — quarantine rests on herb-eval locator discipline, not v3 code; no direct answer-text leakage found in any of 129 run dirs; soft vectors (tag vocabulary from the oracle-reading tagger; relevance_to_file from the contaminated build) unverified; HERB_SCOPE_REACH/HERB_TAG_PURE exist in no source era — only in five 2026-07-23 manifests, Audit verdict on 'leads all valid metrics': false as worded — answer_correctness vs vector n.s. (p=0.096) and generator-confounded (sonnet vs qwen); the faithfulness and context_recall_llm leads hold within the haiku judge, Metric definitions: recall_id = |retrieved context_ids ∩ gold citations| / |gold|, union-based, cross-arm valid; nDCG@50 from meta.chunk_ids (ranked kept chunks, first-gold-gain, self-normalized IDCG), within-arm only; truncate_k slicing context_ids[:k] is invalid for the artefact arm (ids not 1:1 with chunks); stats protocol = paired sign-flip permutation + Wilcoxon + exact sign test + BCa CI + Holm, conjunctive decision rule, m≥8 detectability gate reported not filtered, Audit verdict on the ~0.80 ordering wall: tried-set enumeration on n=10 is optimistically biased; gold-100 max over everything tried is 0.7492; ship as 'no tried re-rank of existing values exceeded 0.75 on gold-100' (+5 more)

### Community 24 - "artefact_v1.py"
Cohesion: 0.19
Nodes (13): answer_one_question(), _env_float(), _hint_match(), _load_verified_doc(), _nth_entry(), _open_area(), _qid_text(), Open one area: its tags pull their chunks; each chunk keeps its     highest-sup (+5 more)

### Community 25 - "Audit verdicts: haiku < det supported on..."
Cohesion: 0.18
Nodes (12): Audit verdict on recall_id 0.64 vs 0.09/0.11: real arithmetic, ~85% unit artifact (artefact ~443 ids/q vs 50; one-id-per-chunk counterfactual -> 0.090, about lucene's level); ship only matched-id-budget 0.73-0.75 vs 0.41/0.39/0.27, ~1.8x, Holm p~3e-4, rank-biserial 0.85-1.0; missing control = granularity-matched baseline (packed chunks + bundle credit), which doubles as the graph-attribution ablation, Audit verdicts: haiku < det supported on gold-100 (-0.130, p=5e-5); hybrid loses at matched budget supported retrieval-only — judged comparison open, and the partial 2026-07-23 JUDGE_* dirs are unusable (arm-correlated missingness: artefact answer_correctness 0/100 cells), Judged eval, partial (artefact-global only, claude-haiku generator + judge): faithfulness 0.8707 (68/100), context_recall_llm 0.6171 (91/100), semantic_similarity 0.3455 (100/100), context_recall_id 0.6812, rouge 0.1114, bleu 0.0241, answer_correctness 0/100; faithfulness 0.87 = artefact answers strongly grounded in their evidence; hybrid and vector judging in progress at session end — their __j-claude-haiku-4-5 dirs hold what completed, Hybrid arm (v3/pipelines/hybrid.py): min-max late fusion of the lucene and vector arms; HERB_HYBRID_ALPHA (0=lucene, 1=vector, 0.5 default); union gated on positive arm-weight so the endpoints reduce exactly to the pure arms; regression tests in v3/test_hybrid.py, Matched id-budget comparison (~500 ids each, gold-100, retrieval-only): artefact haiku-global 0.6812 and det 0.7339 vs pure vector 0.4100, hybrid α=0.5 0.3883, pure lucene 0.2742 — the artefact's lead is not an id-budget artifact; fusion ≈ pure vector (weak lucene drags it); the artefact carries ~500 ids from its 50 chunks while the baselines are 1:1, so raw recall_id@50 is not comparable across them — match the id budget (baselines at k=500), hybrid.py — late-fusion baseline: the lucene (BM25) and vector (dense) arms comb, Late-fuse the two arms' ranked (id, score) lists into the top-k artifact ids,, main() (+4 more)

### Community 26 - "2026-07-25-combine-clusterk-hybrid-and-j..."
Cohesion: 0.21
Nodes (11): Session entry: gitignored state-transfer docs in docs/state, newest dated doc is the entry point; current entry 2026-07-28-audit-absorption-full-revert-corroboration-probe.md — five-reviewer audit verdicts on every shipping claim, the full revert to 5006fed, the absorbed rewrite-thread lessons (topic ≠ evidence, membership measurements, evidence-budget design), the graph topology/adjacency facts (one gold file per question; discrimination inside scope territory is the whole residual), the open-decisions list; the corroboration probe it specs has run: real signal, redundant with description distance, oracle headroom +0.21 in-territory, the Part-J discriminator remains unfound; predecessors 2026-07-25 (combine sweep, cluster-K runs, hybrid arm, judged-eval burn) and 2026-07-22 (cluster-K concept, curve-walk results) hold the definitions; older live threads: 2026-06-25 artefact tag-facet design (content-profile + guide-link, facets = weight+direction measured by geometry, one edge per tag carrying the full facet vector; DESIGN.md §13–14 / MODEL_CONTRACTS §1 are stale) and 2026-06-25 v3 vector eval (k-vs-top-k, judged metrics, k=50 / gold-100, NIM-throttle run ops), Corroboration probe (next measurement; offline, free; pending the user's go): can rare-tag sharing between candidates express 'same event' (not just 'same topic') inside scope territory — the discriminator Part-J step (3) needs; per gold-100 question: territory = gold file's chunks, seeds = top-ranked kept chunks from the committed-baseline detCUR run, corroboration score = rare tags shared with seeds (degree cap swept <=5/<=10/<=25/<=50; seed depth swept top-10/top-25), Judge-run rule: each claude-* judge/generation attempt is a full billable run on the user's subscription window; on failure stop and diagnose from disk; never delete saved __j result dirs, never re-run a full judge to fix a partial failure — eval_results.jsonl IS the saved judge scores and the harness resumes from it, keeping finished rows and filling only the gaps, Run-folder provenance: detREBUILD, detREBUILD_artComp, detPOOLCUT, detCURVEK, detTAGBAR, detADMIT, detDESCCORR, detDESCFIRST (all __gold100, 2026-07-25 to 07-28) come from uncommitted code and are comparable only to each other; committed-baseline gold-100 references: detBASE 0.7039, detCUR 0.7339, detNONE 0.7390, detGLOB 0.7394, clusterK 0.7341, clusterKglob 0.7492 (2026-07-23); the 0.7339-vs-0.6906 gap is a cross-lineage comparison — never present either lineage's numbers as the other's, Measurement apparatus stays untouched during an eval: nim.py transport, orchestrator.py, contract.py; an uncommitted nim.py stdin edit (_claude_chat ~line 193: prompt written to a tempfile redirected as stdin) sits unexecuted pending review-or-revert, and commit 5006fed carries swept-in contract/orchestrator/model_test changes pending review, Open decisions and not-done list: scope minting (middle design) needs user sign-off; canon conflict — 'the chunk description is dead' vs desc as the measured recall door — user ruling owed; granularity-matched baseline (= graph-attribution ablation) not run; judged eval completion for the matched-budget trio owed (claude-* run, cost math + explicit go required); cluster-K on a discriminated list after the discriminator; evidence-budget rebuild on the committed baseline as its own signed step; CLAUDE.md entry-point pointer update to this doc; held-out 715 answerable questions on det parked as the cheapest generalization test, Run outputs (v3/output, gold-100, 20260723, untracked): det norm probes detCUR/detMAX/detABS/detNONE/detGLOB; haiku sweep cells haikuCELL1/haikuMAX/haikuABS/haikuMAXABS/haikuGLOB/haikuNONE/haikuFACET; clusterK + clusterKglob; hybrid k=50 (hybA0_lucene, hybA1_vector) and matched-budget k=500 (hybk500, luck500, veck500); JUDGE_artefactGlobal__gold100__20260723T170605Z with its __j-claude-haiku-4-5 sibling, JUDGE_hybrid__...172437Z, JUDGE_vector__...173630Z — saved results, kept, Open problems: finish the judged eval through the harness's save/resume (--rejudge at the existing JUDGE_* answer dirs; cost math + explicit user go before any claude-* run); whether artefact answer_correctness completes on an unloaded machine; whether making the K-cut fire below the ceiling is worth pursuing; held-out validation on the 715 non-gold-100 citation-bearing questions (cost-gated); the three-adversary final audit panel before any conclusions ship (+3 more)

### Community 27 - "score_outputs()"
Cohesion: 0.17
Nodes (11): _build_metrics(), corpus_gold_text(), _print_status_summary(), One line per metric that produced any non-ok cell, so failures are visible at, Instantiate each selected metric with the wrappers it needs, then init() it —, Every string leaf of an artifact record, joined — a faithful text rendering of, artifact id -> its text. The non-LLM context metrics score retrieved text     ag, ENTRY: per (output, question) score every metric in metrics_to_run() ->     list (+3 more)

### Community 28 - "reembed_herb_eval.py"
Cohesion: 0.31
Nodes (10): 9.5 Tagging unit, context, and no overlap, drop_legacy(), embed_chunk_descriptions(), embed_tags(), main(), Drop + recreate one cosine vector index — a re-run after a dimension     change, Tag names, bare, one vector per tag reachable through the arm's tagging     run, Each chunk's description (text read from the backup, embedding input     only) - (+2 more)

### Community 29 - "_retrieve()"
Cohesion: 0.18
Nodes (11): _agg(), _gap_break(), _mod(), _n_levels(), interpret-plan -> (pointer rows cut at k, query embed ModelUsage,     retrieval, The walk's stopping test, read from its own trajectory. The height     gaps bet, The number of doubling levels a stated-scope ranked set of size n spans —     t, Fold a path's per-part/source support dicts into one per-chunk base by     the (+3 more)

### Community 30 - "2026-07-22-retrieval-literature-sweep.md"
Cohesion: 0.22
Nodes (9): GraphRAG family: Microsoft GraphRAG's communities are permanent and query-blind (the contrast case); HippoRAG 1/2 validate seed-weighted PPR over a tag-like graph; G-Retriever's prize-collecting Steiner tree is a one-shot budgeted subgraph alternative; ToG's stop rule is LLM sufficiency under a hard cap, Query-conditioned local graph clustering: Andersen-Chung-Lang PPR + sweep cut formalizes a soft query-relative region with a principled boundary; heat kernel (Kloster-Gleich) is the tighter-radius variant; Crestani's spreading-activation constraints catalogue the flooding failure modes, LLM-emitted scalars as ranking features: document-level LLM relevance labels can be load-bearing (Thomas et al., Bing/SIGIR 2024) but label-level agreement is fragile and scalar outputs compress; NO published validation of LLM-emitted per-edge numeric weights — HippoRAG-line systems derive weights structurally, LLM only discrete decisions, Literature sweep coverage gaps: the 2026-07-22 sweep covers diffusion-framed expansion (PPR, HippoRAG), communities (rejected: query-blind), path methods, degree/IDF seeds; never covered — plain co-tag one-hop, file/container-sibling expansion, graph-native clustering of the chunk graph as areas, bipartite similarity, hub-tag IDF over own vocabulary, Five-finding synthesis: weighted score-space fusion over RRF; the more-tags-more-votes pathology starts at emission; PM-2 for the hard-k budget; query-relative areas = seed-weighted local diffusion; LLM per-edge scalars are unvalidated territory, Progressive budgeted retrieval: PM-2 proportional slot allocation (each of k slots to the most under-served aspect) beat xQuAD on TREC diversity — the published mechanism for multi-frontier selection under hard k; bandit budget allocation across subqueries gains +35% precision, Faceted / multi-aspect query representation: MADRAL fuses aspects into one vector pre-retrieval; its ECIR 2024 reproduction failed (learned aspects can be dead weight); ColBERT's MaxSim-then-sum is the proven score-space per-aspect aggregation, Rank fusion theory: RRF is rank-only and erases within-list multipliers (Cormack 2009); normalized-score convex combination beats RRF in- and out-of-domain (Bruch et al., TOIS 2023); weighted RRF puts importance in per-list weights; LLMs emit the prompted subquery count regardless of need (arXiv:2510.18633) (+1 more)

### Community 31 - "_chat_json()"
Cohesion: 0.20
Nodes (10): _chat_json(), _clean_tag(), _extract_json(), _interpret(), _parse_gate(), The interpreter holds the conversation: evidence is shown cumulatively     at t, One JSON turn on the interpreter model -> (parsed_json, tokens_in,     tokens_o, Normalise the model's loose gate into strict scope hints: string-or-null     fi (+2 more)

### Community 32 - "GeminiCliRegressionTests"
Cohesion: 0.22
Nodes (3): GeminiCliRegressionTests, Regression checks for Gemini CLI process and quota handling., _TimeoutProcess

### Community 33 - "Audit verdict on scope-dominance: haiku..."
Cohesion: 0.22
Nodes (9): Audit verdict on scope-dominance: haiku leg only (global +0.077, p=6e-4; absolute -0.068); det leg insensitive after Holm; ship as benchmark-structure alignment (questions name their product = gold's partition key), not a retrieval law, Haiku combine sweep (cross-part live, 3-8 parts/q, gold-100): default 0.6039/nDCG 0.416; global-norm 0.6812/nDCG 0.462; none 0.6536/nDCG ~0.462; absolute 0.5359; max (corroboration off) nDCG −0.026 → corroboration/sum helps ordering; facets null; the per-path/absolute norm loses — letting stated scope dominate (global/none) wins, Audit verdict on facets: not a point null — bounded failure-to-detect (+/-0.035), tendency weakly positive on ordering, One gold file per question, 100/100: covered gold sits in exactly one file; missed gold is inside that file 95/95; the dominant retrieved file IS the gold file 90/95; retrieval holds mean 32 chunks of the gold file and the remainder (~130 chunks) contains all missed gold at ~4% density — membership was never the residual problem, discrimination inside scope territory is; ~18 of 50 kept slots go out-of-territory (provably never gold), so spending the whole budget in-territory is free recall, Audit verdict on 'pool ceiling 1.0 / all loss is ordering': an n=10 diagnostic, unverifiable from disk (traces carry locators, not ids); true of union-ranking machinery, false of any semantic-only keep, Three retrieval paths (user's terms): tag areas (the walk), description lookups, stated scope; pool = union of the three, dominated by stated scope (hard-field OR-match, no LIMIT — 1,078 chunks on one CoachForce question, 84% off-target); gold ~100% in the pool on 10smoke; the loss is ordering within the top-k cut, Geometric det facet channel (HERB_DET_FACETS support/routing/edges) moved recall ≤ +0.003 at k=50 — facet placement, not facet values, is the open question, Global normalization is a scale artifact — stated scope's extend=True level count hands it the win; report the result as 'scope-dominance wins', never as 'global normalization is correct' (+1 more)

### Community 34 - "RuntimeError"
Cohesion: 0.25
Nodes (8): _driver(), prepare_over_corpus(), RuntimeError, Aborted, abort.py — press 'q' to stop a running gen/eval loop.  Ctrl+C can be swallowed, Raised from inside an in-flight call when q has been pressed, so a worker     p, Start a daemon thread that sets the abort flag when q/Q is pressed. No-op     w, watch()

### Community 35 - "load_questions()"
Cohesion: 0.25
Nodes (7): main(), The gold-N: a balanced ANSWERABLE subset, drawn by seeded round-robin     over, stratified_gold(), QuestionWithTruth, load_questions(), questions.py — load the HERB question set from data/questions.jsonl.  Each rec, The HERB question set as QuestionWithTruth records.

### Community 36 - "contract.py"
Cohesion: 0.25
Nodes (8): generator_messages(), generator_output_text(), generator_usage_from_nim(), generator_user_content(), contract.py — the shared shapes every arm and evaluator imports., The exact system + user messages the shared generator sends to NIM., The structured JSON body the generator returns., tokens_in/tokens_out from a NIM /chat/completions usage block.

### Community 37 - "main()"
Cohesion: 0.47
Nodes (8): _cosine(), _embed_texts(), expand_folders(), _folder_question_ids(), main(), offline_eval.py — score run folders with the no-judge metrics.  Step 2 of the de, score_folder(), Path

### Community 38 - "_NimEmbedder"
Cohesion: 0.32
Nodes (3): BaseRagasEmbeddings, _NimEmbedder, RAGAS embeddings driven by nim.post — llama-nemotron-embed, asymmetric: question

### Community 39 - "_JudgeLLM"
Cohesion: 0.36
Nodes (3): BaseRagasLLM, _JudgeLLM, RAGAS LLM driven by nim.post or a headless subscription CLI.     The backend fol

### Community 40 - "_embed_cached()"
Cohesion: 0.25
Nodes (8): _embed_cached(), _embed_key(), _load_cached_vec(), Content address for one embedding: (embed model, input_type, text), each     le, The cached embedding for `key`, or None on a miss. A corrupt or     half-writte, Write one embedding under its content address, published atomically so a     co, Embed `texts` through the shared NIM embedder with a persistent per-text     ca, _store_cached_vec()

### Community 41 - "_part_levels()"
Cohesion: 0.36
Nodes (8): _level_chain(), _multi_k_support(), _part_levels(), `a` scaled to unit length along its last axis; a zero vector has no     directi, The anchor leaf's containing-cluster chain through the dendrogram,     finest t, One part -> its widening levels: [{height, tags: [(name, support)]}]     finest, _unit(), ndarray

### Community 42 - "main()"
Cohesion: 0.39
Nodes (7): _arm_output(), _context_ids(), _load_checkpoint(), main(), Ablation: attribute the gold-100 k=10 context_recall_id between the corpus-gene, Resume: per-question records already computed (id -> record). The     interpret, _topk_chunks()

### Community 43 - "embed_tags.py"
Cohesion: 0.36
Nodes (7): _cache_path(), _load_tags(), main(), Path, embed_tags.py — precompute the artefact arm's tag-embedding index.  The lean g, Read the tags jsonl -> records [{chunk_id, kind, tags: [...]}]., Content-addressed cache: any change to the model, the tags file, or the     ded

### Community 45 - "_score_all()"
Cohesion: 0.29
Nodes (7): _load_rows(), One contract pair -> a RAGAS SingleTurnSample. reference = the gold answer     (, Parsed rows already in results_path. A torn trailing line from a killed write, Score every (question, metric) cell -> list[EvalResult], in ordered passes: the, _score_all(), _to_sample(), SingleTurnSample

### Community 46 - "_normalize()"
Cohesion: 0.33
Nodes (7): _absolute(), _minmax(), _norm_pool(), _normalize(), Min-max a path's base scores against the given bounds: hi <= lo (a single     s, Min-max normalize a path's per-chunk base scores onto [0, 1] over that     path, A pool-independent bounded score: the raw support saturated against a     per-p

### Community 47 - "_embed()"
Cohesion: 0.29
Nodes (6): _embed(), _embed_request(), Embed one batch in a single NIM call -> (embeddings in input order, calls,     t, Embed texts via nv-embedqa -> (matrix [n, d] float32 L2-normalised, calls,     t, main(), embed_questions.py — precompute the dense (vector) arm's question vectors.  Ru

### Community 48 - "backfill_file()"
Cohesion: 0.38
Nodes (6): backfill_file(), main(), Path, backfill_token_split.py — add tokens_in/tokens_out ONLY on rows with no token da, backfill_generator_usage(), Add tokens_in/tokens_out only when generator has no token fields at all.

### Community 49 - "_selfcheck()"
Cohesion: 0.29
Nodes (7): EvalResult, Strip the truth: hand the arm the question's id + text ONLY, as the (id,     te, -> list[contract.EvalResult]. The arm label + corpus (so an evaluator can     d, Wiring check with fakes — no NIM, no bm25s, no disk questions. Verifies the, run_one_evaluator(), _selfcheck(), to_arm_question()

### Community 51 - "Rebuilt combine (v3/pipelines/artefact_v..."
Cohesion: 0.33
Nodes (6): Combine toggles (env, defaults byte-identical when off): HERB_AGG sum|max = corroboration aggregation, HERB_NORM relative|absolute|none, HERB_NORM_SCOPE per_path|global, per-modifier strengths (HERB_STR_FACET default 0.0); HERB_NO_REVIEW=1 skips the sufficiency review for clean retrieval sweeps; the user's sweep axes verbatim: combined, per path, relative, relative per path, Audit verdict on the +0.030 combine rebuild: supported (p=0.0005, CI +0.014..+0.054, 23 up / 5 down) — a defect fix, not a swept knob, Rebuilt combine (v3/pipelines/artefact_v1.py): per-path base = fuzzy multi-k support 1/max(d,1e-6)² summed over K_LEVELS=(8,16,32,64); normalize; strength-graded modifier _mod(m,s)=max(0,1+s·(m−1)); weighted sum over the union; top-k — measured +0.030 recall on gold-100 (det default 0.7039 → 0.7339), the biggest single move, Fuzzy k-NN support aggregated over the doubling level sequence: every     level, Put the three paths' bases on a comparable scale by the HERB_NORM mode:     rel, HERB_AGG / HERB_NORM / HERB_NORM_SCOPE select cells of the combine grid;     th

### Community 52 - "ragas.py — multidimensional answer/evide..."
Cohesion: 0.33
Nodes (6): **Completeness.** Every dimension in the convergent model is represented *somewhere*, Graph and evidence units, 13.4 Dimension → mechanism allocation (the table), ragas.py — multidimensional answer/evidence quality via the RAGAS library.  Scor, v3/requirements.txt — harness environment pins (provisional laptop-reconstructed; desktop .venv is the canonical record), RAGAS scoring-time deps pinned for offline metrics (rapidfuzz, sacrebleu, rouge_score, nltk) + scipy for NNK grounding

### Community 53 - "ragas_catalog.py"
Cohesion: 0.33
Nodes (5): _check(), Metric, ragas_catalog.py — the full RAGAS metric menu + the toggle for which ones a run, Fail loud before a run if SELECTED is malformed., RAGAS (eval/ragas.py) is the scorer; the full metric menu lives in eval/ragas_catalog.py; every judge-free deterministic metric always runs because it costs nothing, and SELECTED adds the judged ones

### Community 54 - "_interpret_cached()"
Cohesion: 0.33
Nodes (6): _interp_key(), _interpret_cached(), Content address for one interpretation: (interpret model, interpreter     signa, Write one interpreted plan under its content address, published     atomically, interpret with a persistent plan cache keyed by (model, prompt     signature, q, _store_interp()

### Community 58 - "13. Semantic dimensions — the research b..."
Cohesion: 0.40
Nodes (5): 13. Semantic dimensions — the research basis for the facets, 13.1 Why the v1 facets degraded, Facet verdict: stored HAS_TAG w_facets are non-signal — weights confined to 0.5–1.0, temporal on 555/20k edges; feeding query facet direction into them (detE) changed 5/100 retrieved sets, recall Δ 0.0000, NNK neighborhoods: redundancy pruning is by design (near-synonym tags get exactly zero weight); no published RAG/passage-retrieval use; if used at all it belongs at tag grounding, not chunk selection, Embed the herb-eval graph's semantic layer with the v3 embedder (nemotron).  The

### Community 59 - "Cluster-K concept (user canon): the clus..."
Cohesion: 0.50
Nodes (5): Cluster-K / best-fit on the rebuilt combine (HERB_CURVE_WALK=1, gold-100): clusterK 0.7341/nDCG 0.4748; clusterK+global-norm (clusterKglob) 0.7492/nDCG 0.4756 = best artefact config of the session, beating flat-global 0.6812 and det-default 0.7339; K=50 on all 100 questions — the K-decision is inert (never cuts below the ceiling); the gain is the curve-walk's progressive-frontier ordering, not cluster-K choosing K, Part-J control flow (designed, researched, not built): (1) constrain with stated hard fields when they are constraints; (2) desc = recall door inside that space; (3) a different signal discriminates evidence from topical siblings; (4) cluster/gap cut chooses K on the discriminated list; open forks — hard filter vs boost, and which discriminator; cluster-K (the user's concept) returns after a discriminator exists, Audit verdict on clusterKglob as best config: not supported — +0.0154 over detCUR, p=0.36, below best-of-36 selection noise, and its nDCG is worse than detCUR's (best ordering of all configs = detCUR 0.5021); it does beat its own leg's flat-global (+0.068, p=4e-4); the K-decision is structurally inert at k=50 — stops fired 100/100, semantic >=122 always, kept=50 always, Cluster-K concept (user canon): the clustering's curve of best fit decides the per-query evidence count K; the caller's k is only the ceiling, The curve walk (HERB_CURVE_WALK=1): one progressive frontier opens the     chea

### Community 60 - "_gemini_terminal_quota_error()"
Cohesion: 0.40
Nodes (5): _gemini_quota_error_row(), _gemini_terminal_quota_error(), A terminal Gemini quota/entitlement rejection cannot improve with a retry., Whether a cell has Gemini CLI's terminal quota/entitlement rejection., Exception

### Community 61 - "export_raw.py"
Cohesion: 0.60
Nodes (4): _collect_rows(), main(), Path, export_raw.py — dump all eval_results to a single long-format CSV.      python

### Community 65 - "herb-eval.dump"
Cohesion: 0.50
Nodes (3): herb-eval.dump, exjobbet — HERB evaluation harness, herb-eval graph topology (run_id pilot_full_herb, read-only probe): 4,869 chunks, 19,716 tags, 33 files, 67,913 HAS_TAG edges, one connected component; connectivity dense but generic — 34.4% of tags on >=2 chunks, hub tags are generic vocabulary (salesforce 534, tensorflow 428, gdpr 287), median chunk is one shared tag from ~482 chunks (~10% of graph); discriminative structure thin — tags deg<=10, and >=2-shared-tag pairs are 1.9% of all pairs

### Community 66 - "_tag_affinity()"
Cohesion: 0.50
Nodes (4): _hint_terms(), Cypher boolean terms for the interpreted scope hints, over chunk     fields. ([, Structural affinity per tag: the fraction of the tag's edges landing on     hin, _tag_affinity()

### Community 67 - "build_questions.py"
Cohesion: 0.67
Nodes (3): build(), mint_id(), build_questions.py — one-shot: build the HERB question set from raw.  HERB shi

### Community 68 - "build_eval_manifest()"
Cohesion: 0.50
Nodes (4): EvalManifest, Provenance for an `evals` run — ONE scorer over one run file., build_eval_manifest(), Provenance for the eval side -> contract.EvalManifest (timestamp now, UTC).

### Community 69 - "_rehydrate()"
Cohesion: 0.50
Nodes (4): model_usage_from_dict(), Rehydrate ModelUsage from a persisted dict (arm_outputs / run_manifest)., A persisted arm-output record (dict) -> contract.ArmOutput, so the scorer     r, _rehydrate()

### Community 70 - "unpack_generation()"
Cohesion: 0.50
Nodes (4): model_usage_from_telemetry(), Normalise a generator return into (answer, ModelUsage)., Build ModelUsage from a generator telemetry dict., unpack_generation()

### Community 71 - "build_run_manifest()"
Cohesion: 0.50
Nodes (4): Provenance for a `questions` run — answers generated by ONE arm., RunManifest, build_run_manifest(), Provenance for the generation side -> contract.RunManifest (timestamp now,

### Community 72 - "truncate_k.py"
Cohesion: 0.67
Nodes (3): main(), One arm_outputs record cut to its first k chunks, ids rebuilt from the     kept, truncate_record()

### Community 73 - "A chunk reference in the resolver's self..."
Cohesion: 0.67
Nodes (3): A chunk reference in the resolver's self-resolving contract     (`resolver_prot, 2. The reference triple, **Tag** — resolve references to transient views; derive tags/weights/grounding vectors.

## Knowledge Gaps
- **110 isolated node(s):** `Path`, `Metric`, `Response`, `All three arms answer with the same generator, built once in the orchestrator and injected, so any difference is retrieval not the LLM; beyond that generator and the corpus on disk the arms share nothing, each reading, indexing and ranking the corpus with its own code`, `lucene arm = BM25 baseline with its own index over the corpus` (+105 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CombineModeTests` connect `_Session` to `Rebuilt combine (v3/pipelines/artefact_v...`?**
  _High betweenness centrality (0.174) - this node is a cross-community bridge._
- **Why does `HERB_AGG / HERB_NORM / HERB_NORM_SCOPE select cells of the combine grid;     th` connect `Rebuilt combine (v3/pipelines/artefact_v...` to `_Session`?**
  _High betweenness centrality (0.172) - this node is a cross-community bridge._
- **Why does `Audit verdict on the +0.030 combine rebuild: supported (p=0.0005, CI +0.014..+0.054, 23 up / 5 down) — a defect fix, not a swept knob` connect `Rebuilt combine (v3/pipelines/artefact_v...` to `2026-07-28-audit-absorption-full-revert-...`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `ModelUsage` (e.g. with `CompletedProcess` and `_JudgeLLM`) actually correct?**
  _`ModelUsage` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `BuildStats` (e.g. with `_write_build_stats()` and `ModelUsage`) actually correct?**
  _`BuildStats` has 32 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Ablation: attribute the gold-100 k=10 context_recall_id between the corpus-gene`, `Resume: per-question records already computed (id -> record). The     interpret`, `abort.py — press 'q' to stop a running gen/eval loop.  Ctrl+C can be swallowed` to the rest of the system?**
  _342 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `_Session` be split into smaller, more focused modules?**
  _Cohesion score 0.0669753086419753 - nodes in this community are weakly interconnected._