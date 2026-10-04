# Intended artefact and implemented retrieval: reconstruction

2026-09-24. This supersedes the **completion claim**, not the measurements, in the structural outcome and coverage reports. No retrieval experiment, model call, graph write or production repair was performed for this reconstruction.

## Finding

The request was to investigate how the complete artefact retrieves, starting with the query. The recent work instead investigated many downstream constructions conditional on one captured interpretation, one eligible graph population and one delivery contract. Those comparisons are real evidence about those conditions. They do not establish that the conditions implement the intended artefact.

The clearest traceable instance is the interpreter. A September 21 repeatability diagnostic separated generation from scoring. That diagnostic was subsequently installed as the interpreter used by the joint arm and inherited by the recent leader adapters. Its scoring stage cannot see the original question. The history supports **scoring the tag's relevance to the sought content through a facet**. It does not establish that withholding the original question is necessary to preserve that meaning, or that the diagnostic architecture won a retrieval comparison.

This document distinguishes intended semantics, measurement, retrieval policy, and evaluation. It is a reconstruction with explicit gaps, not a new agent-written canon. Reading a design document, implementing a proposal, or winning on reused gold does not convert a proposal into a user decision.

## Evidence and authority

Primary evidence is preserved in `output/research/2026-09-24-intent-reconstruction/primary-user-evidence.json`: 52 targeted user turns with archive path, line, timestamp, session ID, message UUID and archive hash. The archive retains both requests and questions; inclusion is not endorsement of every sentence. The two source archives overlap and have different coverage:

- `docs/canon/raw/user_turns_all.jsonl`: May 14–September 5, 2,371 turns.
- `docs/canon/raw/user_turns.jsonl`: August 13–September 20, 1,678 turns.
- Later original Claude and Codex sessions supply surrounding assistant proposals and the user's replies. Tool results, delegated-agent reports masquerading as user messages, and pasted advice are not treated as user-authored decisions.
- Historical Git sources supply implementation/design chronology, not independent proof of approval. In particular, old prohibitions cannot be silently revived after later decisions changed the design.

Original Claude session files below live under `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/`. Original Codex continuation: `C:/Users/jocke/.codex/sessions/2026/09/21/rollout-2026-09-21T10-39-25-01a0c31e-b78c-7243-a80b-9f376d13ed36.jsonl` (task title: **Design tag ranking for retrieval**).

### Decisions and changes over time

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| May implementation: `dba1160:docs/architecture.md`, `agents/schemas.py`; May interpretation plan `415148d:backend/docs/query_interpretation_layer.md` | Descriptions, tags and facet-aware query interpretation have long-standing roots; the old names and categorical framing differ from later semantics. | That the first implementation defines the current contract. |
| June design at `28c95aa:v3/artefact/DESIGN.md`, sections 1–4; `MODEL_CONTRACTS.md` | References into untouched authoritative sources, hash verification and a corpus-blind interpreter were explicit design concerns. | That June's removal of descriptions/entities or ban on model-emitted numbers remains current. The documents themselves mark reopened/stale sections; later work restores descriptions and richer structure. |
| June 27 / July 6, all-archive lines 36, 39–41, 100, 104 | Facets characterize a tag–chunk relevance relationship, not a tag class. Graph contains derived representations and references; description, tag edges and graph work together. | A uniquely specified combining formula, or permission to provide source bodies to the online interpreter/retriever. |
| July 20, all-archive 328, 347 | User expected query-relative facet areas/clustering; scope here was use of the artefact, interpreter through retrieval. | That an NNK neighborhood, fixed frontier or shared-membership projection is automatically such an area. |
| September 1, all-archive 2140 | Explicit request to examine each step, starting with the query: how it works, whether it works, method, order and downstream consequences. | A restriction to already captured query representations. |
| September 2–4, all-archive 2158, 2191, 2209, 2216, 2282, 2295 | Retrieval consequences matter; query facets, graph facets, tag matching, descriptions and graph shape must act together. Collapsing relationships into a generic tag value was rejected. | That every numeric sum is prohibited, or that one unexplained aggregation is sanctioned. The level and meaning of aggregation must be explicit. |
| September 5–7, later archive 791, 797, 866, 873, 876 | Fuzzy priorities, multikey ordering, density/grouping and description participation were proposed for investigation. | One fixed ordering/tie-width as the settled answer. |
| September 14, later archive 1161–1193; original exchanges below | Sought-content description, semantic tags, relational facet readings, separate structural name landing, graph-derived areas and outside access. | Correctness of every later prompt paraphrase or scale/combination rule. |
| September 15, later archive 1337, 1403 | Direct correction: relevance of the tag to the chunk through the facet, **not what is happening to the tag**. | That training a numerical reader automatically resolves this semantic distinction. |
| September 20, later archive 1652, 1656, 1660, 1668 | Description representativeness, ranking versus weights, population dependence and query/graph scale alignment remain substantive concerns. | That CDF normalization validates either meaning or arithmetic. |
| September 21, original `35c6be4d...` lines 1386, 1425–1440 | A controlled generation/scoring repeatability diagnostic was approved. | A comparative decision to make the split mandatory in serving. |
| Current conversation | User explicitly expected question plus description at interpretation to be among the tested alternatives; withdrew tolerance for another assumed construction. | Permission to inject new evidence or run further experiments during this reconstruction. |

### September 14: read the proposal with its acceptance

Original session `6c806933-883b-46c5-aec7-22468ef6b7f2.jsonl`:

- Assistant line 2781, UUID `0ccd1088-f9f6-470a-9346-21396eede0ea`, proposes semantic and named structural evidence strengthening each other, with graph paths and descriptions never cutting what tags found. User line 2784, UUID `b457d2b1-3a06-456a-83e3-9b59deb6e0f7`: **“Yes, exactly”**.
- Assistant line 2868, UUID `6a4fc82b-1f0e-4a74-9951-78a066b3af85`, distinguishes question phrasing from the description of sought content as the target of facet judgments. User line 2871, UUID `5fe3d59d-a40c-4ebb-afdb-24dbaf80444c`, agrees and requests a written record.
- Assistant line 2945, UUID `aba3df39-212d-47b8-b726-2f5d235e0db1`, states per-tag/per-facet relevance to described content, neither tag classification nor facet importance. User line 2948, UUID `d4172853-6b1e-4176-b893-42b7c84ff49d`: **“Yes.”**
- Assistant line 3178, UUID `3078c8bc-18bc-41e2-85b7-5cf848b9305e`, consolidates question-only external input, sought-content description, semantic tags, no model-invented scope, description-targeted facets; separate literal/nearest-unique name grounding, graph areas first with outside evidence retained. User line 3181, UUID `fb36566d-bc1c-4be5-83b5-ee2f0164df8b`: **“Seems fine.”**

These establish that **description-targeted meaning was not invented by the recent agent**. They also establish that a single interpretation call could see the question while producing description-targeted judgments. Access to the question and the target of the judgment are separate choices.

### September 21: how a diagnostic became a boundary

Original session `35c6be4d-c200-4b52-8a7f-f48fbb9b56e7.jsonl`:

1. User line 1170 asks for the entire line from query to output. Assistant line 1219 admits the active arm still uses an older interpreter, including an information-need description and model-named scope; the September 14 querytagger was not connected.
2. Line 1310 contains user-relayed advice distinguishing relational semantics from facet importance. Assistant line 1332 checks the September 14 original exchange and withdraws its proposal to discard the accepted meaning. This is already a recorded instance of the same semantic drift.
3. User-relayed advice at line 1386 asks to isolate generation stability from scoring stability, **“even if the eventual production implementation combines them.”** This is relayed advice, not independent user authorship, but it specifies the proposal being discussed.
4. Assistant line 1425 proposes asking generation twice, then fixing one description/tag output and scoring it twice. User line 1428, UUID `a6234ac5-710e-401b-9b02-646679754f80`: **“doit”**.
5. Assistant line 1440 explains that it split the prompt because the check was split; the scorer receives the fixed description and tags. The report is `output/querytagger_split/2026-09-21/REPORT.md`.
6. Current `test/arms/artefact_facet_joint.py::_interpret` calls precisely those separate generation and scoring helpers. Both newer leader adapters inherit it.

Supported conclusion: the split has legitimate diagnostic provenance. No question-only/description-only/both-input scorer comparison was found in the examined records. The diagnostic does not settle the serving dependency. This is a traceable untested assumption, not proof that the user never permitted the diagnostic or that using two calls is inherently wrong.

## Intended query-to-output process

The original question is the interpreter's external information source. Interpretation describes the kind and subject of answering content without inventing its answer, produces semantic retrieval phrases, and expresses each phrase's relevance to that described content through the facets. Named entities are grounded separately into existing graph structure. They are not invented scope labels or semantic tags by default.

Query phrases meet graph tags; facet-conditioned tag–chunk relationships and description matches contribute to chunk evidence. Graph structure establishes relationships and possible areas of evidence. How paths combine, which relationships can recruit independently, when scope forms, how descriptions influence discovery versus ordering, and how evidence is scheduled are exactly the construction questions the user wanted examined. Their arithmetic and ordering cannot be inferred merely from the words “relevance” or “graph.”

The resulting selected chunk pointers resolve authoritative source content for the shared answer generator. Source bodies belong at that delivery stage, not as extra evidence supplied to interpretation or numerical retrieval. Gold belongs to evaluation and diagnostics after selection. The user's later request to investigate exclusive joins authorizes studying alternatives; it does not silently supersede the accepted no-cut behavior as the definition of the artefact.

## Step-by-step comparison with current code

“Current” below distinguishes the common interpreter/delivery code, the numerical testbench, and selected leader programs. It does not imply every legacy arm executes the same path.

| Step | Observed implementation | Relationship to intent and remaining issue |
|---|---|---|
| Eligible artefact | Pinned 4,808 chunks / 57,204 eligible semantic edges; `artefact_facet_joint.py::prepare_over_corpus`. | A declared research population, not the whole live graph. Latest live inventory is 4,869 chunks / 62,028 HAS_TAG edges. Do not attribute conclusions about excluded metadata or tag populations to the whole artefact. |
| Description and phrase generation | `querytagger.py` GENERATE prompt asks for sought-content description and whole semantic phrases, excludes incidental names; parser checks shape/cleans strings. | Broadly matches September 14. Schema validity cannot establish that description preserves the query, that phrases stay semantically whole, or that all required relations survive. Generation was fixed in recent structural sweeps. |
| Facet interpretation | `_interpret` calls SCORE with description and generated tags; no original question. Values are independent 0–1 readings. | Accepted relational target; untested input restriction. Description errors become the scorer's entire context. Question+description, one versus two calls, and explicit handling of discrepancies remain construction alternatives, not a newly discovered feature request. |
| Facet meaning | Current prompt uses relevance seen through topic/time/reasons/activity/specificity. | Intended direction is supported. The precise activity contrast and other paraphrases must be checked against September 15 corrections; prompt wording and historical learned labels are not proven equivalent. No semantic repair is claimed here. |
| Query embeddings | Pinned model/revision, query-role prefix, CPU float32 then normalized float64; tag→graph-tag, tag→chunk-description and whole-description→chunk-description matrices. | Preserves several intended links. Original-question embedding is absent from this common path, although older arms and diagnostics used it. Matching a vector is not validation of a description's representativeness. |
| Graph facet measurement | Frozen edge layer; empirical fixed-population midranks in `facet_joint_candidate.py`. | Learned ordering and numerical convenience are separate from semantic truth. CDF values do not establish interval scales, probabilities, cross-facet exchange rates or comparability with generated 0–1 query readings. |
| Tag recruitment | `facet_tag_frontier.py`: positive similarities, unique-score tiers, query/facet gate; selected variants use reciprocal nomination depth. | Investigated alternatives exist. In query-only scalar streams, per-query positive facet scale can cancel out of tag order. “Uses query facets” is not evidence that they affect recruitment. All-positive ranking is not discovery of a natural query area. |
| Tag/query aggregation | Engines expose max/mean/sum and ordering variants; selected paths still make specific reductions before later operations. | Real downstream structural coverage. Max discards corroboration; sums count it; query means merge needs. Exact reduction location determines what later traversal can know. No single choice follows from the facet definitions. |
| Descriptions in retrieval | Tag→chunk-description and whole-description gates, seed/destination/off roles tested. Some program labels obscure which description link is used. | This tests placement conditional on captured descriptions. It does not test how descriptions are produced, whether the original query should remain available, or whether descriptions represent their source chunks. |
| Named-node grounding | `facet_structural_landing.py`: casefolded whole-name matching, contained-alias suppression; union nodes behind each name, intersection across distinct names; empty/unreachable result falls back globally. | Separate structural grounding matches the architecture. No OR/comparison interpretation. No fuzzy fallback, unlike the accepted September 14 proposal. This is an implementation difference requiring provenance/coverage, not grounds to silently restore guesses. |
| Scope formation | Named masks plus seed/reach variants; selected rules use area-first scheduling. | Area-first has actual historical support. Masks and shared memberships do not exhaust query-relative graph areas. Keeping outside access still delays it; finite context can make a priority act like effective exclusion. |
| Graph traversal | Product/Channel memberships and Employee projections, including management direction; finite-step numerical propagation. | Actual structure, but selected projections collapse intermediate paths and exclude other live relation types. Reachability is not automatically relevance. A half-discount, projected duplicate handling and finite walk depth are explicit hypotheses. |
| Joined/exclusive evidence | Testbench implements unions, intersections, graph-only and exclusive rules. Selected high-hit paths can require joint direct/graph support. | Legitimate experimental alternatives under the user's broad comparison request. An intersection can remove evidence tags found, unlike the accepted corroboration/no-cut design. A high score cannot erase that distinction. |
| Arbitration | Joint/independent streams, best/all rank, complete-tier/shared-visited variants; selected rules ultimately emit one order, with stable-ID ties. | Extensive conditional comparisons, not proof that their scheduling family captures every intended dependency. Stable IDs can decide which evidence survives a 72k boundary. |
| Source-record recovery | Numeric connected-record components may affect rank; source pointers are resolved afterward. | Recovery changes the retrieval construction and must remain visible. It is not automatically neutral packaging or semantic graph evidence. Existing recovery experiments distinguish contexts where it changes output from ones where it is inert. |
| Delivery | `_resolve_chunk` verifies source-file hash, follows locator; `_budget_contexts` applies shared serialized-character cut. Partial boundary text can be delivered while its source IDs get no credit. | Consistent reference integrity mechanism. A chunk, record, source ID and character are different units. Deduplicated source-ID credit is not deduplicated context text; neither is answer quality. |
| Answer generation | `prod/harness/contract.py`: original question plus resolved documents; instruction to answer only from those documents. | Generator sees source text only after retrieval. A fixed retrieval order is not a completed smoke; fresh answers and judge results must exist. |
| Evaluation | Source-ID retrieval measurements, fresh answer/judge smoke, and historical baselines are separate artifacts. | Development-selected fixed rules are runnable without gold but selected using it. Per-question gold-selected winners are diagnostic only. Neither is a held-out superiority claim. Failed judge cells stay failures. |

### Integrity boundary verified, with its limitation

`facet_construction_program.py` and `facet_directed_frontier_engine.py` require the value-only `GraphInput`; leader adapters pass numeric graph/query data to that stage. The outer prepared holder still contains pointer metadata and a `source_text` field in its captured chunk rows. Therefore the claim is a checked **function/API boundary**, not process-level isolation or absence of source material from the host process. Do not say the entire process never loaded corpus-bearing data.

The current read-only DB inventory is `output/research/2026-09-24-intent-reconstruction/live-graph-inventory.json`. It records labels, relationship endpoint counts and property-key counts, not source bodies. It confirms richer structure than the selected projections: Employee/org/role/slack/product/manages, File memberships, Product/Channel/Kind, and Customer/Company/Role. The inventory does not prove those routes are useful or historically identical to a pinned research snapshot.

## What was already tested, and what that evidence answers

| Existing evidence | Actual comparison | Boundary |
|---|---|---|
| `output/querytagger_stability/2026-09-14.md` | Repeated combined generation. | Changed descriptions/tags confound a pure scoring-repeatability claim. |
| `output/querytagger_split/2026-09-21/REPORT.md` | Repeat generation; repeat scoring with identical description/tags. | Fixed-input scoring still reverses some comparisons. No comparison of whether SCORE sees question, description or both; no retrieval superiority result. Report computation used zero new calls; underlying diagnostic used 41. |
| Original September 21 session, lines 1133 and 1219; facet-pairs run history | Raw question as retrieval part on/off; scope and sort changes in the older arm. | There was prior original-question use. “Original question was never tested” would be false. These are not tests of the current scorer's access to it. |
| `docs/2026-09-22-facet-composition-decisions.md` and linked conditional/fresh evidence | Query/edge interaction semantics; support/conflict/missing operators and fresh checks. | Prior failures and limits must be read before proposing the same operators as new. |
| `.../independent_sources/query_interpretation_intervention/PROTOCOL.md` | Frozen-output intervention on tags, raw-question versus generated-description endpoint, and aggregation. | Diagnostic, not an automatic query repair; SCORE inputs remained fixed. No need to reopen benchmark text to preserve this methodological result. |
| `.../independent_sources/query_reconstruction/RESULTS.md` | Strongest, equal, description-reconstruction-weighted tag contributions. | Geometric reconstruction does not correct a mistaken description; reused development source comparisons, not human gold or held-out performance. |
| `.../independent_sources/fresh_smoke/regression/RESULTS.md` | Earlier versus changed query phrase routing and restoration diagnostics. | Interpretation can change retrieval before downstream scoring. Restoring a route for a diagnosed case is not a general repair. |
| `.../independent_sources/crossed_content/PROTOCOL.md` | Separate model reading of saved retrieved passages against information needs. | Historical post-retrieval content diagnostic, not permission to feed additional content into the retriever. Model judgments are not benchmark gold. |
| `docs/2026-09-24-construction-coverage.md` and linked 18 populations | Aggregation, independent streams, ordering, graph depth/direction, scopes, description placement, joins, priorities, recovery. | Preserve actual comparisons and exact replay checks. They condition on frozen upstream inputs and a finite graph/program family. Their count cannot establish whole-pipeline coverage. |
| `output/research/2026-09-24-structural-selection-v3/` | Fixed total-hit and macro-recall selections, replayed original cases and separately recovered cases. | Selection used development gold. 2,015 source hits and mean source recall 0.533131 for one rule; 1,954 and 0.536217 for the other are retrieval metrics, not RAGAS. |
| Completed `artefact_facet_program_v2` 10smoke run and `output/research/2026-09-24-real-gold-smoke/lucene-vector-same-ten.json` | Ten fresh answers for the earlier 2,008-hit rule; same-ten historical Lucene/vector comparison. | 139 successful judge cells and one faithfulness error. Not smoke results for either later leader; not evidence of a new held-out winner. |
| `output/research/2026-09-24-leader-gold-smokes/preflight.json` | Twenty numeric order/delivery checks for later leader adapters. | No new answers, no RAGAS. Preparatory checks must not be reported as smoke results. |

In this table `...` means `output/research/2026-09-22-joint-streams`. No old diagnostic is retrospectively declared academically sufficient merely because its report exists.

## Discrepancy disposition

**Direct scope failure:** calling the structural investigation complete while interpretation and its dependencies were fixed contradicts the September 1 whole-process request and the current explicit correction. The completion banners are withdrawn.

**Supported meaning, unsupported restriction:** description-targeted facet relevance is accepted. Restricting the separate scorer to description/tags is diagnostic inheritance, not a demonstrated requirement. The question can be available without changing the target relationship; how to use both coherently remains to be specified and compared.

**Experimental alternative versus intended behavior:** independent streams, exclusive joins and intersections were requested as things to study. They must remain labeled alternatives where they contradict the previously accepted strengthening/no-cut behavior. Selecting one on gold cannot resolve that conceptual difference.

**Unresolved measurement:** neither a learned edge rank nor a generated decimal validates the relational meaning or their product. The graph layer, query layer, transforms and coefficients need separate provenance. Stability and retrieval benefit do not substitute for semantic validity.

**Incomplete graph/scope interpretation:** selected projections, exact literal landing and name-set intersection are concrete simplifications. Query-relative areas, ambiguity, misspellings and AND/OR relationships are not settled by testing many masks. Historical fuzzy grounding is a prior alternative, not a newly authorized repair.

**Preserved valid work:** graph/value boundary, hash-verified resolution, deterministic replay and structural effects remain useful verified mechanisms. They do not prove the entire concept correct. The numerical comparisons, failed runs, smoke errors and historical baselines remain unchanged.

## Follow-up verification against the task specification

The user required the reconstruction itself to be completed and explained, not replaced by an implementation specification. The checks below extend the earlier report; no new model or retrieval experiment was run. Original proposal/acceptance pairs are now preserved in `output/research/2026-09-24-intent-reconstruction/accepted-exchanges.json`, alongside the primary-turn ledger.

### What the frozen artefact actually supplies

The route snapshot manifest identifies **61,018 eligible edges before removing product-name edges**, of which 3,814 are removed, leaving 57,204 semantic routes. These are different populations from the live database's 62,028 HAS_TAG edges. The 4,808-chunk restriction is inherited research eligibility, not a query-time conclusion that the excluded 61 chunks are irrelevant.

The same manifest records that the legacy DB facet names are topic/entities/activity/temporal/evidence and that those stored values are **not** the layer used by this experiment. It explicitly rejects relabeling entities/evidence as why/concreteness. Topic is computed from graph Tag and Chunk-description vectors. The other four values come from `output/facet_pairs/rounds/round1/overlay.json`. Description text provenance points to the May 14 historical tagger snapshot at Git ref `bcc3156`; the DB description vectors were not regenerated for this work.

The round1 model configuration identifies a frozen `Alibaba-NLP/gte-reranker-modernbert-base` representation, revision `f7481e6055501a30fb19d090657df9ec1f79ab2c`, and a linear head using `mean_L-3`. It is not the DeBERTa model described by an older `facet_pairs/model.py` module. The cached representation was computed from tag–chunk inputs at build time. That is distinct from allowing the online retriever to inspect source bodies.

The Opus label manifest fingerprints `test/graph/prompts/facet_pairs_judge.txt` with SHA256 `b7e9ef897131ed89d9645f8edf9419177b3f3200323b0a3bf0bb76ee53e9a010`. Its actual wording asks, among other things, how much text gives the cause of the phrase's thing, what is happening to it, and specificity exemplified by “numbers, names, figures.” The contemporary `output/facet_pairs/PROGRESS.md` explicitly corrects attribution: the concreteness examples and some other clauses were agent additions. The current query scorer instead repeatedly asks how relevant the tag is to described content seen through each facet.

**Finding:** there are different operational wordings on the two sides, and the graph-label wording includes distinctions the user subsequently challenged. This is a concrete provenance and semantic-alignment problem. It does not prove every learned value is wrong or identify a valid replacement. Agreement with the same labels measures reproduction of those labels, not independent agreement with the user's concept.

The historical validity audit (`docs/2026-09-22-facet-pair-kind-validity.md`) already narrows the evidence: same-tag, different-chunk, same-kind comparisons have 22/33, 36/58, 24/40 and 32/53 correct decided comparisons for temporal/why/activity/concreteness, with ties excluded. The outer evaluation chunks were absent from gradient training but used in backbone selection. An internal checkpoint split had shared endpoints. These recorded qualifications prevent presenting the aggregate label-agreement figures as untouched validation. This reconstruction inspected the audit and its provenance code; it did not refit the layer or recompute its evaluation.

### The intended role of topic versus the executed combination

An additional direct user statement is later-archive line 1559, September 18, UUID `9432b247-e87b-480f-a150-af6e39a6f1b6`: “my thinking is that the ‘main weight’ on a tag, is the topic one, and the others adjust that weight depending on the relevance of a facet to the query”. Line 1487 asks why topic was not left alone as the working weight. Later proposals try to recover a topic-based scale, but do not establish that the translation succeeds.

In the current candidate and engines, **all five** graph columns, including topic, become fixed-population midranks. Each facet can then have a different strongest supporting edge. Their support is eventually added with coefficients 1/.25/.25/.25/.25. That is not literally an adjustment of one unchanged topic edge weight. It is an aggregation of separate facet-path contributions, on transformed scales. It may be studied as an alternative, but its resemblance to “topic plus adjustments” does not prove equivalence to the intended operation.

### Exact information flow in the highest-total-hit program

Verified against `best-total-hits.json`, `facet_tag_frontier.py`, `facet_directed_frontier_engine.py`, `facet_directed_values.py` and `artefact_facet_leader_hits.py`:

1. Produce the description/tags, then score tags against the description alone. Embed the description and tags. The original question goes to structural name matching, not the scorer or semantic embedding matrices in this adapter.
2. Clip semantic similarities at zero. Nominate graph tags independently per query tag in exact positive-score tiers. Carry every positive sponsor with reciprocal tier depth. This is ordering over an already available vocabulary, not incremental discovery of unknown nodes.
3. Multiply query-tag/graph-tag similarity, query-tag/chunk-description similarity, query facet reading, graph facet midrank and the tier factor. This creates one value per facet/query/edge.
4. Take the strongest graph edge for each facet/query/chunk. Different facets can now be supported by different graph tags. Nonwinning edge corroboration is discarded at this point.
5. Average over query tags **before traversal**. Distinct query requirements no longer have separate propagation state. Exact duplicate numerical query rows are deduplicated; this is not semantic deduplication of differently phrased needs.
6. Offer evidence over a forward management projection: chunk–Employee–manages–Employee–chunk, where the chunk memberships are channel-derived. Merge that offer with direct evidence by maximum. The projection keeps unique source/target chunk connectivity, not a count of all intermediate paths.
7. Run two shared Product–Channel propagation steps, strongest sponsor at each step, half attenuation and a destination gate from the mean query-tag/chunk-description match. A projected propagation step need not equal one original graph relationship.
8. Take the minimum of direct evidence and the resulting graph evidence. Either being zero removes the contribution. Thus earlier direct evidence can be lost despite its positive semantic support.
9. Sum the facet contributions with fixed coefficients, then multiply by whole-description/chunk-description similarity. The final single score carries neither a complete set of paths nor explicit coverage of separate requested needs.
10. Rank positive evidence within the named area before outside evidence. The exact-name resolver intersects distinct names' reachable sets, with global fallback for an empty intersection. This does not interpret whether the question meant conjunction, alternatives or a comparison.
11. Give connected source-record siblings their component's earliest nomination depth. Original sponsors precede advanced siblings at that depth; stable IDs resolve remaining ties. This can advance a chunk whose own evidence did not justify that position.
12. Resolve source pointers in that order and apply the common character prefix. The final context is therefore determined by the score, scope priority, recovery, tie ordering, source serialization and truncation together—not by the score alone.

There is no explicit selected-set check that each distinct requested relation has been covered. That is an observed absence, not a new requirement that every query phrase must become a mandatory subquestion. Descriptions and tags can represent multiple needs implicitly, but the code does not verify their coverage.

### Name-grounding provenance and its limits

The exact-only behavior is traceable to the September 22 structural repair (`docs/2026-09-22-structural-landing-repair.md`), which added captured Employee and Channel routes to a previously product-only arm. It deliberately did not reuse the old name cache and states that unknown capitalized words are not guessed. The earlier `landing.py` still contains the nearest-unique misspelling path. Thus the omission is not a missing implementation discovered only now: it is a difference between a later repair and an earlier accepted proposal.

The repair's tests establish literal-name binding, ambiguity handling, empty fallback and actual route linkage. They do not compare fuzzy grounding with literal grounding or establish user approval for removing misspelling recovery. The examined original continuation contains no matching explicit fuzzy/nearest-unique decision. The available evidence locates the change but does not justify claiming an exhaustive absence of approval in all conversations.

### Delivery and evaluation details that change interpretation

`prod/harness/char_budget.py` counts the lengths of the supplied serialized source units. It does not count the full generator prompt, the question, or the document separators added by `generator_user_content`. The 72,000-character setting is therefore a context-unit budget, not a total prompt-character or token limit.

The cut can split a source unit. `_budget_contexts` supplies that partial text to generation but only credits IDs from fully retained units. Source IDs are deduplicated for metrics; source text is not thereby deduplicated. Multiple chunk pointers can resolve several record IDs, and one record can have multiple chunk parts. Neither chunk count nor ID recall alone measures how much answer-bearing text was delivered.

For the completed earlier fixed-program smoke, the saved report records source-ID recall 0.562171 and answer correctness 0.181971; the earlier area arm has 0.393175 and 0.260430 respectively. The direction differs between those metrics on the same ten development questions. This establishes that the retrieval gain did not establish an answer-quality gain in that comparison. It is not a significance claim or a general ranking of architectures. The later 2,015-hit and 1,954-hit adapters still have numeric preflight evidence only, not their own completed fresh-answer smoke.

## Completion of this reconstruction and remaining uncertainty

This reconstruction covers the intended and implemented flow from external query through interpretation, graph evidence, selection, source resolution, generation and evaluation. It identifies the diagnostic-to-serving transfer with original conversational provenance and restores previously tested upstream alternatives to the account. It does not claim an exhaustive sentence-by-sentence reading of every month or that all historical contradictions have been adjudicated.

Unresolved items are explicit: semantic equivalence of the learned facet rubric and the user's relational definition; authorization and empirical justification for the later exact-only name policy; a justified joint question/description scoring contract; and the extent to which the projected graph can represent query-relative areas. The follow-up locates the measurement wording and the literal-only repair, but does not manufacture the missing justification. These uncertainties are findings of this reconstruction, not implementation decisions made here. None authorizes silently changing the artefact or adding data.

The next implementation/experiment brief must enumerate these input, meaning and dependency choices before choosing a program family. It must preserve the source/gold boundary and separate interpretation fidelity, mechanism effects, source-ID retrieval and answer quality. **No such run has been launched by this reconstruction.**
