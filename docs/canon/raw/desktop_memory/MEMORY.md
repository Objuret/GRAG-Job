# Memory Index

The repo is now just **v3** — a self-contained HERB evaluation harness. (v1/ and v2/
were deleted 2026-06-23; their source survives in git history. The artefact arm's
design is retained below, to be rebuilt natively in v3.)

## How I work (always-on)

- [Heed user intent, don't correct it](heed-user-intent-not-correct-it.md) — when the user names what they want, it's the spec; build to it, never argue it away with stale context; surface a real conflict as a question
- [Lock concept language](lock-concept-language.md) — once a concept is settled, ONE canonical phrasing forever; renaming the same mechanism mid-conversation reads as changing the implementation
- [Match output to the ask](match-output-to-the-ask.md) — TRIGGER before sending: cut anything longer/more-structured/more-built than asked; short Q = one line, plain English not spec-walls/jargon, no unrequested machinery, stop building on 2nd pushback; never drop scope silently — say it
- [Prompts are context, reconcile first](prompts-are-context-reconcile-first.md) — a bare share is CONTEXT to reconcile against repo+conversation (check BOTH), surface deltas/faults; generate nothing unless asked
- [Verify before asserting](verify-before-asserting.md) — never assert from training/narrative; verify FIRST against a current source (the running system AND online); re-check (don't double down) when given contradicting evidence
- [Check what exists before adding](check-existing-before-adding.md) — query the graphify graph (and the tree) for existing code BEFORE creating files
- [No cutting corners](no-cutting-corners.md) — do tasks fully and properly; no shortcuts, stubs, or partial work passed off as done
- [No silent fallbacks](no-silent-fallbacks.md) — user treats fallback/degradation paths as bloat; fail loud with actionable errors instead
- [Delete, don't preserve](delete-dont-preserve.md) — never keep legacy/superseded content, backups, fallbacks, or tests on my own initiative; delete and replace, preservation needs explicit approval
- [No fabricated offline checks](no-fabricated-offline-checks.md) — don't add offline `_selfcheck`/`__main__` test scaffolding to v3 eval code; the real smoke run is the validation
- [User owns execution](user-owns-execution.md) — the user runs scripts in their own terminal and owns progress/output; never background-run for them, hand off the command; make runs followable with live progress
- [No historical/defensive comments](no-historical-or-defensive-comments.md) — comments/docs/commits describe ONLY present state, as if written right the first time; no "previously/now/NOT because" narration; remove the mistake, don't annotate it
- [Code readability / plain naming](code-readability-plain-naming.md) — unreadable code is a real defect: descriptive greppable names (not alike-named symbols), one plain-English comment not five jargon lines, collapse dead/redundant mechanisms
- [Docs track reality](docs-track-reality.md) — update all affected docs in the same change that alters reality; stale docs are a defect, not a follow-up
- [No cost estimates](no-cost-estimates.md) — drop $X / Yh / "cheap path" framings; user judges cost themselves
- [No Claude attribution](no-claude-attribution.md) — never add Co-Authored-By/generated-with/AI attribution; this is the user's thesis repo
- [Memory is downstream of conversation](memory-is-downstream-of-conversation.md) — live conversation is source of truth; memory is a snapshot; if they conflict, conversation wins and memory gets updated
- [State/handoff = utmost care](state-handoff-utmost-care.md) — HARD: state/handoff docs are the most important artifact in ANY chat; audit every framing for hidden presupposition
- [Design before build](design-before-build.md) — gate: all parts explicitly decided before pipeline code; present decided-vs-open checklist per stage, get sign-off

## Project facts

- [Project overview](project_overview.md) — repo = v3/ HERB eval harness (artefact vs lucene+vector, scored HERB+RAGAS); v1/ and v2/ deleted
- [Thesis is done](thesis-is-done.md) — thesis submitted (2026 VT); this is POST-thesis work; never frame anything around thesis needs or "thesis numbers"
- [Data layout: storage vs working](data-layout-storage-vs-working.md) — HARD: A:\exjobbet\data\raw = cold storage, never touch; v3/data = working copy (corpus + raw)
- [NVIDIA NIM host](nvidia-llm-host.md) — NIM = v3's one transport (free, 40 RPM); generator+judge=qwen/qwen3.5-397b-a17b (one model, both roles), embedder=llama-nemotron-embed-1b-v2; user wants nim.py async capped to the rate
- [Benchmark data is safe to push](feedback_dont_stop_for_benchmark_data.md) — HERB and Bonnier are benchmark datasets, not real client data; don't pause push workflows to flag them
- [AI cost boundary](ai-cost-boundary.md) — per-item cost exists only where a model touches the item (interpret/embed); deterministic extraction is free

## v3 — eval harness

- [Dual-dataset eval plan](dual-dataset-eval-plan.md) — SCOPED: HERB-only for now, Bonnier DEFERRED; eventual plan = HERB scored/quant (gold-100), Bonnier naturalistic/external-validity
- [v3 arm model stack](v3-arm-model-stack.md) — shared generator + RAGAS judge = qwen/qwen3.5-397b-a17b on NIM (one model, both roles); vector embedder = llama-nemotron-embed-1b-v2; lucene = bm25s lucene-variant; all-MiniLM rejected
- [Arms share only corpus + generator](arms-share-only-corpus-and-generator.md) — HARD: the 3 arms share ONLY the corpus on disk + the injected generator; each reads/indexes/ranks with its OWN code; duplicated extraction is deliberate
- [Generator is a thin RAG pipe](generator-is-neutral-pipe.md) — one fixed generic grounding system prompt (answer only from docs, be concise), identical across arms; NO abstention/steering; structured {answer}; arms own advanced handling
- [v3 question id scheme](v3-question-id-scheme.md) — HERB has NO native id; mint `<product>::a|u::<index>`, 815+699=1514 unique, paired-test join key; loaded from raw, exact id filter, fail-loud
- [gold-100 ported to v3](gold100-ported-to-v3.md) — scored set at `v3/data/gold100.jsonl`, mechanically re-keyed from v1's list, each id text-verified
- [gold-100 stratified selection](gold-100-stratified-selection.md) — seeded round-robin by HERB type (equal allocation ~20/type); report per-type, don't compare aggregate to HERB's natural-mix average
- [gold-100 was effectively n=99](gold100-effective-n99.md) — one v1 question aborted on a hard gate; no-hard-filters + raw directories kill that failure class
- [Use established eval libraries](use-established-eval-libraries.md) — compute RAGAS metrics with the RAGAS library (validated/citable); custom NIM judge + transparent ID-based context metrics
- [RAGAS canonical sources](ragas-canonical-sources.md) — consult the EACL 2024 paper + docs.ragas.io for ANY RAGAS question, never blogs/memory; refs are in eval/ragas.py
- [Drop LLM context-precision](eval-drop-llm-context-precision.md) — context_precision_llm_ref dropped from SELECTED (now a single explicit metric list, 14 = 11 free + 3 judged); precision carried by exact judge-free context_precision_id/nonllm
- [NIM judge needs min_tokens=1](nim-judge-min-tokens.md) — Qwen judge greedily emits end-of-turn first for some prompts (0 tokens, null content, finish_reason=stop); min_tokens=1 forces a real token; temperature does NOT fix it; not thinking-related

## Artefact arm — design canon + v3/artefact build

- [Artefact pass-2 design](artefact-pass2-design.md) — **CURRENT facet canon (07-01)**: facets are relevance DIALS ("how much") not category labels ("which"); exponential scoring curve (exact=max); fuzzy=embedded not edit-distance; per-facet channels kept up to chunk; graph-relationships reopening (edges+hub nodes); DIFFUSE-FACET gated candidate. State doc: `docs/state/2026-07-01-artefact-pass2-dials-curve-relationships.md`
- [Tag-facets vs routing](tag-facets-vs-routing.md) — SUPERSEDED 06-25 baseline (guide-link + content-profile); kept for history, see [[artefact-pass2-design]] for current
- [v3/artefact subsystem](v3-artefact-subsystem.md) — the artefact rebuilt natively in `v3/artefact/`: deterministic spine built+tested (36 tests); **the graph + retrieval (pass 1: lean graph, live facets) is BUILT and RUNS** (not unbuilt) but precision is bad — not a good reference; pass 2 is designed, not built
- [Graph spine](v2-graph-spine.md) — Source→File→Chunk→Tag only; hard fields = chunk attrs; references not copies; embed only phrase tags; vocab-free interpreter; ambiguity = all candidates
- [Chunking model](v2-chunking-model.md) — chunk = coherence episode (not fixed-size); recurse into prefixed subchunks; materialized-path index; deterministic seam-finder, NO embeddings
- [Mapping key](v2-mapping-key.md) — repetition-ratio discriminator; kind bridges interpreter→directories; file-scope attrs on File node; universal enum w/ dataset-derived active subset
- [Retriever routing model](retriever-routing-model.md) — NO hard filters in ranking (mandatory=weight concentration+cap); gate-vs-boost by PATH; hard-field pre-pass vs live values; anchored retrieval
- [Facet semantic framework](facet-semantic-framework.md) — the 5-facet research synthesis (topic/process/stance/communicative-function/time; facts→structure; completeness+symmetry). STALE on "facet = relevance coordinate" and on the set being locked — see [[tag-facets-vs-routing]]
- [Retag facet analysis](retag-facet-analysis.md) — v1 tag pollution (~18% eid/year junk) was the designed output of temporal+entity facets; promote those to structure, forbid ID/date tags
- [Hard fields before tagging](design-hard-fields-before-tagging.md) — materialize structured hard fields as queryable Chunk props BEFORE tagging
- [Graph is references not copies](graph-is-references-not-copies.md) — CORE: graph indexes references into untouched raw source; never stores mutated content copies
- [Tagger build validation](tagger-build-validation.md) — test the tagger cheaply; tags=code assertions, weights=invariants+gold-100; error-analysis-by-reading first; ~30 catches a bug vs 250-500 measures a rate
- [herb-eval is the artefact DB](herb-eval-is-the-artefact.md) — `herb` has oracle baked in (ingestion error); `herb-eval` is THE canonical Neo4j DB; never query `herb`
- [artefact_v1 arm](herb-eval-arm.md) — `run.py --arm artefact_v1` (`pipelines/artefact_v1.py`): the herb-eval graph's facet-grounded retrieval ported native, ALL on v3 models; herb-eval is POINTERS (no content/descriptions — v1 schema doc stale), arm resolves text from v3/data/raw hash-verified, context_ids REAL from locator ids; six-per-tag facet vectors rebuilt with nemotron by `reembed_herb_eval.py` (context descriptions read from herb-eval-backup)
- [Neo4j data location](neo4j-data-location.md) — Neo4j data at A:\Coding\neo4j\; herb-eval-backup sibling DB + herb-eval.dump recovery artifact on A:\
