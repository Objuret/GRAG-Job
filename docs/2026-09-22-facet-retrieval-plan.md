# Facet retrieval: state, scope and finite execution plan

## Current continuation point

The user's later instruction to explore retrieval combinations broadly supersedes
the older stop/small-intervention directions below. The goal remains a usable,
valid measurement and composition of facets, with construction defects diagnosed
where they impede it. A high benchmark score or a runnable lab does not complete it.

The complete 10,240-configuration matrix across 95 saved queries raises observed
fixed-policy source-ID recall from 29.56% to 49.41%. The subsequent coefficient
grid reaches 50.96% with topic-largest weights, or 49.94% when coefficients are
selected on other product groups. Correct auxiliary query labels show no clear
advantage over their permutations at the original weights. All results are
retrospective; no new generated answers or judge calls were made for these replays.

The paired conditional edge/query experiment in
`tools/facet_edge_experiment.py` is complete. It jointly shuffled auxiliary edge vectors within
graph-tag × source-kind strata and cross with shuffled query-tag auxiliary
vectors. Preserve topic, graph, CDF, saved areas and budget; keep original and
previously group-selected coefficients fixed. Topic-only must be invariant.
The frozen protocol is `output/research/2026-09-22-retrieval-matrix/edge-controls/plan.json`.
It completed all 95 cases with unchanged hashes and invariants. The recall-leading
construction shows an edge-placement effect of −0.06 pp at original weights and
+0.28 pp at group-selected weights; both seed ranges cross zero despite actual
full-chunk-set changes on 55/95 and 70/95 cases. Existing semantic pair evidence
also shows only 60–67% decided agreement for the same tag across different chunks
of the same kind (70 pairs per facet; many ties). These pairs were excluded from
gradient training but used in backbone selection. The internal fit/validation
split also shares 24 chunks despite its comment claiming disjointness. See
`2026-09-22-facet-pair-kind-validity.md`. Next compare these heads with the actual
topic-cosine baseline on the identical restricted pair population, without new
labels or training. See
`2026-09-22-facet-edge-control-protocol.md` for full qualifications.

Use that result to identify whether useful edge placement, query-tag binding,
or their interaction is missing. Then inspect and repair the implicated
measurement/composition step and validate on concept evidence that is independent
of selecting benchmark winners. Final verification still requires the complete
query-to-delivery behavior and the meaning of the facet measurements; this has
not been established.

The usable lab and verified results are documented in
`2026-09-22-live-retrieval-matrix.md` and `2026-09-22-facet-weight-protocol.md`.

## Historical checkpoints, not current execution instructions

**Completed full-arm smoke:** 10 answers, 139 successful RAGAS cells and one faithfulness error. ID recall 33.05% -> 39.32%, precision 13.20% -> 16.52%; interpretations, chunk scores, areas and 72k budget identical on all ten. See [full results](2026-09-22-facet-area-smoke-results.md). This supersedes earlier pending/no-new-quality statements below; weights remain provisional. No further benchmark run is queued.

**New implemented and measured checkpoint:** optional strict area-first admission
raises saved-query RAGAS ID recall from 29.15% to 40.31% (+11.16 points) on the
85 successful cases, with identical scores, areas and 72k budget. Auxiliaries add
1.40 points within that policy. This is a controlled reused-data diagnosis, not
new answer quality or validated final weights. The normal harness now exposes
`artefact_facet_area`; the existing arm stays unchanged by default. 49 tests pass;
all 4,808 unit lengths/IDs and 30 raw-file hashes independently reverified. See
`docs/2026-09-22-area-admission-results.md`. The next validation must distinguish
this saved-area scheduling result from a fresh run with the broader resolver,
and must not relabel single-area dataset success as general scope correctness.

**Exposure check supersedes graph-transfer priority:** a streamed audit of the
85 saved successes found graph winners in only 2 of 1,383 fully delivered chunks.
Scope nomination and record recovery are separate and remain active. Do not
mistake the topology redundancy for an established primary cause. The next
construction target is direct tag/facet/description evidence into scope admission
and actual delivery. See `docs/2026-09-22-facet-composition-decisions.md`.

**Construction checkpoint:** all 2,375 chat-adjacency links are numerically
subsumed by the current joint product/channel max-transfer groups; 412 document
and transcript links are not. This is proved from endpoint containment and the
actual transfer formula, with a reproducible synthetic full-topology check.
The separate recovery-order defect is repaired: original nominations precede
advanced context within a frontier. 39 focused integration/regression tests pass.
See `docs/2026-09-22-graph-composition-diagnosis.md`. Next architecture decision:
distinguish graph area access from evidence transfer, then define how structural
support and facet evidence jointly select the delivered context. Do not disguise
that unresolved distinction with another coefficient sweep.

**Implemented checkpoint:** the raw-query arm now uses pinned structural
name-to-node routes and combined areas. Live Volmax eligibility and Product/Channel
memberships match the earlier snapshot; 22 focused tests and an independent
561-name round-trip check pass. This fixes the missing connection, not retrieval
quality or the equal-depth scheduler. No further benchmark/model run has occurred.
Next: settle the nomination decision that mixes global and structurally supported
candidates, while retaining outside access. See
`docs/2026-09-22-structural-landing-repair.md`.

**Latest steering:** the user rejects further small-delta benchmark repetition.
The remaining-90 run and paired analysis are complete (85 valid cases, five
preserved interpreter failures); no further benchmark/model runs are queued.
The missing structural landing/combination path is repaired. The nomination
decision and the graph/evidence composition remain open, not another facet
coefficient sweep. See `docs/2026-09-22-facet-critical-diagnosis.md`; its scope and
next steps supersede the older execution directions below. The research goal
remains active and semantic validity is not established.

Status: A/B/C, the 32-run D replay and independent E review complete, 2026-09-22.
The research goal remains active. No final weighting method is validated yet.

Metric clarification and completed measurement check: all three fixed conditions
now have locally executed RAGAS `context_precision_id` and `context_recall_id`.
Joint = 0.131969 / 0.330539; auxiliaries off = 0.126913 / 0.309877; mismatch =
0.124216 / 0.312321. No new answers or Claude judging. Against off, joint precision
is lower on five questions despite its higher mean; preserve that tradeoff.
See `docs/2026-09-22-gold-id-metrics.md` for the exact metric definitions and scope.

Latest user steering, 2026-09-22: replace further homemade-question work with a
diagnostic pointer map from HERB gold sources to chunks, graph/tag relations and
saved retrieval stages. The six-record transfer preparation stopped before
question construction or model calls. The previous “bounded next checkpoint”
below is superseded, not running. See `docs/facet-gold-source-trace.md` for the
implemented pointer index and the existing smoke's stage-by-stage trace.

The first fixed pointer comparison is now complete: switching auxiliaries off
with the same cached query inputs, scope, recovery and actual 72k delivery lowers
macro ID recall from 0.330539 to 0.309877. Joint is better on two questions and
ties eight by net count; 21 joint-only source links trade against 12 off-only links.
All ten baseline full recruitment objects and actual context strings reproduce
exactly. No model calls, weight fitting or new judge run. See
`docs/2026-09-22-gold-pointer-ablation-results.md`. This is bounded contribution
evidence, not validated semantics or a reason to rescue any particular gold source.

The complementary correspondence check is also complete: intended pairing
0.330539 versus one fixed auxiliary query/graph mismatch 0.312321. Two questions
favor intended, one favors mismatch, seven tie. All ten saved embedding hashes,
baseline deliveries and joint-relabeling symmetry deliveries match. No Claude or
judge calls; only local embedding reconstruction. See
`docs/2026-09-22-gold-pointer-correspondence-results.md`. Both controls favor the
current fixed candidate in aggregate; neither licenses coefficient fitting on
this smoke or claims of fully validated facet meanings.

User correction, 2026-09-22: 100% gold is unrealistic for this iteration; a
chosen question, tag or source may be unretrievable by this arm. Individual
misses, including PR10, are diagnostic observations, not acceptance gates.
Root had begun treating that one event as a repeated repair target. Stop that
drift: assess faithful implementation, sound measurement and useful behavior
across varied needs with documented tradeoffs. Neither a single miss nor less
than perfect gold recall invalidates a method; a single rescued event does not
validate it. No additional query-specific rescue is justified by these results.

Current decision after the independent scope/overfitting audit: close development
on these seven questions and preserve the runnable candidate. Reusing them across
original/fresh/phrase conditions creates substantial adaptive-overfitting risk;
42 conditions do not constitute 42 independent tasks. No inspected evidence of
gold-driven tuning was found, but absence of overfitting is not established.
This decision supersedes historical repair directions below. See
`docs/2026-09-22-facet-scope-overfitting-audit.md`.

Bounded next checkpoint: freeze the unchanged candidate and a new set of needs
from previously unused source groups before outcomes; compare auxiliaries on,
auxiliaries off and one predeclared correspondence control using actual 72k
delivery and method-hidden support assessments. Decide whether the contribution
is useful or remains unestablished, recording mixed results and ordinary misses.
Do not iterate until every source is recovered. No new experiment was launched
as part of the scope audit.

Newest execution checkpoint: the standard gold smoke is complete through the new
`artefact_facet_joint` raw-query arm. All ten answers and 140 metric cells completed;
one missing-JSON GENERATE response required an explicitly recorded single-case
retry, preserving the nine original answers. Recall_id 0.330539, precision_id
0.131969, answer_correctness 0.221402, faithfulness 0.876090. Same standard Claude
generator/judge and local pinned embedder. Full results/provenance:
`docs/2026-09-22-facet-joint-gold-smoke-results.md`. No gold-driven tuning follows.
The source-backed compound-route diagnosis has now led to one completed
phrase-preservation development trial: 7/7 GENERATE, 14/14 SCORE and 14/14
retrievals, with no retries. The later review event returns in both review readings
at 67,688 / 52,929 saved-source characters (fresh unchanged prompt: 92,029 /
74,741, outside budget). ActionGenie's known complete support arrives later,
at 30,653 / 27,138 instead of 12,767; durability causes that delay while model
update/frequency support arrives earlier. All six audited question/readings still
retain known requested components. Query fidelity remains imperfect: omitted Slack
and additional-load constraints, and reconsideration strengthened to reversal.
No general interpreter repair or facet validity is established; no production
prompt or weighting change is made. Full report:
`independent_sources/fresh_smoke/phrase_preservation/RESULTS.md`.
The completed delivery bridge checks the distinction between research
complete-frontier source accounting and the arm's serialized-context cut.
Neither trial review reading fully delivers that event at actual 72k: complete-unit
costs are 100,599 / 77,960. All 18 audited need/cohort/reading conditions retain
known requested component support. Treat this as a measurement qualification,
not a requirement to recover the event. See
`independent_sources/delivery_bridge/RESULTS.md`. Do not rerun gold to tune this prompt.

Newest diagnosis: a frozen Q-by-Z intervention and whole-compound-route probe
locate the fresh review-event loss in a missing query-route bundle. Old Q with
fresh Z still loses PR10; fresh Q with old Z retains it. Removing the old
`multilingual contextual analysis` route loses the event in both old readings;
adding that complete route over all 4,808 chunks to fresh inputs restores it at
30,090 source characters in both. The bundle includes old query facet readings;
this is not phrase-only causality or a validated repair. The prompt already says
to keep phrases whole, but raw GENERATE split the compound and structural parsing
accepted it. Record recovery adds 5,460 preceding characters, crossing the budget
in one fresh reading; scope is unchanged. See
`independent_sources/fresh_smoke/regression/RESULTS.md` and its independent review.
That diagnosis motivated the completed phrase trial; it is no longer an open
repair direction. No further source/tag rescue is justified on this development set.

Previous checkpoint: the fresh interpretation-to-context smoke completed 7/7
GENERATE, 14/14 SCORE and 14/14 retrievals without retries. The three previously
audited needs retain known component support in both readings. ActionGenie's
acquisition cost rises from 10,000 to 12,767 source characters; sentiment offering
and review component costs remain 22,854 and 3,290. However, the later PR10 review
drops outside the unchanged 72,000-character budget in both fresh review readings
(92,029 / 74,741), despite being selected with the old interpretations. The same
event also drops out of both intended-use readings, where it is extra context.
This qualifies the earlier retention finding: the candidate is runnable, but
event retention is not stable across fresh interpretations. No benchmark recall
or answer-quality score existed at that checkpoint; the later gold smoke is
reported above. See `independent_sources/fresh_smoke/RESULTS.md`.
That observed event loss motivated the completed diagnosis above. Do not repeat
a broad coefficient or budget sweep or ask the user to label sources.

Previous checkpoint: a completed crossed content audit of both sentiment questions
shows that all twelve original compositions acquire support for their own need.
Intended-use runs acquire design support before review findings; review runs
acquire review findings first. The same earliest component costs persist in cached
auxiliary-off conditions. Event-specific verification nevertheless finds that
auxiliaries admit the distinct later PR 10 review in all four max conditions;
auxiliary-off excludes it at the same budget while retaining earlier PR 6 evidence.
This is bounded information-retention evidence that Boolean component coverage
missed. Both independent readers also assessed the two additional control passages.
See `independent_sources/crossed_content/RESULTS.md` and the preserved reader joins.
No additional coefficient search is warranted by these two adequately served needs.

A usable prepared-query command now exists: `tools/facet_retrieval_demo.py`,
documented in `docs/facet-retrieval-demo.md`. It recomputes real graph/query inputs
through `retrieve_prepared_query` and exports full source contexts and route
witnesses. The example reproduces all 4,808 scores and 24 selected chunks exactly.
This is an experimental global-nomination baseline with explicit coefficients,
not a raw-question adapter, named-area policy or validated final weighting method.

The demo now also exposes `--verified-area`, reusing only saved verified membership
and provenance. Its resolved ActionGenie and unresolved sentiment executions match
all 4,808 archived scores and complete recruitment objects exactly. Global access
and unresolved fallback are preserved. The policy recommendation and comparable
retrieval-run numbers are in `docs/2026-09-22-facet-retrieval-recommendation.md`.

Earlier checkpoint: the geometric query-tag weighting hypothesis was not adopted.
The sensor-support interpretation now has a completed, internally consistent
manual repair test, with two new unchanged-prompt SCORE readings and a verified
description embedding. Max still puts approval before explanation; equal puts
explanation first. Both sources are selected under every repaired condition.
This is evidence about ordering and acquisition cost, not a demonstrated loss
of either source or a validation of facet exchange rates.

The measurement audit now distinguishes route arithmetic, pair ordering,
fixed-budget source inclusion, exact whole-frontier source acquisition cost,
and known support for all parts of a question. See
`output/research/2026-09-22-joint-streams/independent_sources/query_interpretation_intervention/MEASUREMENT_CONTRACT.md`
and the adjacent repair/results and selection/content audits. Source costs use
saved text lengths, not production token or serialization cost. Source readers
remain model judgments; no user annotation request is reinstated.

The designated-source omission for `sentiment_intended_use` is now investigated.
Adding actual Product propagation changed profiles but did not admit that source.
A separately frozen literal graph-Tag-to-chunk-to-Product lookup resolved imentAIX
without an invented alias, but also did not admit it. Both interventions preserve
the intended-use selected sets. Their full independent checks and topology trace
are under `independent_sources/product_connectivity/`.

Crucially, the completed 42-passage content audit shows that all three original
aggregations already select alternative imentAIX design passages explicitly
covering the enterprise/Slack multilingual offering and configurable thresholds
and reports. They enter at 16,070-22,854 source characters, within the existing
72,000 budget. Two method-hidden source readers agree on these passages; their
other disagreements and model-judgment limits remain recorded. The designated
document's absence is not an information omission. **Stop treating that source
ID as a repair target.** See `product_connectivity/CONTENT_RESULTS.md` and
`CONTENT_REVIEW.md`.

The next reasoning checkpoint must use source claims and complete information
needs as the functional units. Existing source-pair preferences remain local
diagnostics, not mandatory answer IDs. Reconcile the observed acquisition-cost
tradeoffs before proposing another operator or coefficient: equal is cheaper for
the explicit sentiment design claims, while max/reconstruction are cheaper for
known three-part ActionGenie support. Neither case identifies a unique facet
exchange rate, and the source audits do not independently validate facet meaning.

## The decision to finish

Recommend how tag paths, chunk-description matching, graph structure and facet
relevance work together to choose chunks. Tag selection or facet ordering alone
is not the requested retrieval method. The query's per-tag facet relevance
adjusts the tag–chunk connections within that combined process.
Provide an executable, isolated demonstration and explain which decisions the
facets actually make. Benchmark improvement is not the validity criterion.

The retained contract is:

1. Query description and semantic query tags express the sought content.
2. Query-tag/graph-tag matching chooses routes into the graph.
3. A graph facet is the tag's relevance to its chunk through that perspective.
   These values remain query-independent.
4. A query facet value is that query tag's relevance to the described content
   through the perspective. It is not the importance of the facet.
5. Query readings adjust the use of the graph readings. Weighted and multikey
   operators are both candidates; their exact mathematical interpretation is open.
6. Topic retains its stated main role. Tag matching, description matching, graph
   facets and route aggregation must not be silently collapsed into one quantity.
7. Graph shape and scope are active parts of the combined process, not merely a
   product-name exclusion or an optional gate inferred from a query. An isolated
   test of one link diagnoses that link; success or failure does not establish
   validity or invalidity of the combined concept.

Sources: the user's dated quotations in
`docs/2026-09-18-facet-work-complete-record.md:57–60,141–160,282–293`; the supplied
2026-09-20 state file; and the current clarification that report analysis and a
record of sharing the report both carry activity, with usefulness query-dependent.
These documents are evidence of decisions, not new instructions to expand scope.

## What changed in our understanding

The existing weighted and multirank forum modes have independently verifiable
mechanical properties: earlier keys can prevent facets from changing an order;
pool-relative scaling can change existing comparisons; first arrival discards
later routes to a chunk. Under the complete fixed staged tuple this is equivalent
to keeping the chunk's best tuple, not inherently arbitrary arrival dependence.
A later route loses because earlier keys dominate; replacing the walk with a
global sort on those same keys is not a correction. Package C tests this distinction.
The default arm mode is `concept`, not either forum mode.
The intended split querytagger is present, but the forum arm still calls the old
interpreter. Also, `querytag_cached()` uses the old five-facet schema; it is not
the adapter for the current split prompts.

The fixed-tag experiments expose failures of particular measurements and
combinations. They do not establish failure of the complete retrieval chain.
The fresh preference references are model-generated, so their feasibility
obstructions are conditional on those references and measurements.

The query-conditioned support classifier was a diagnostic detour. It changes the
quantity being measured, loses degrees of coverage, and can ignore supplied tags.
Its later repairs are incomplete and do not justify replacing the graph facets.
It is now quarantined: no further prompt revisions, training, or branches of that
experiment belong to this plan. Historical results and failures remain available.

The bounded query-route check is complete:

- Four generation calls used the existing GENERATE prompt and Haiku model, twice
  each for an analysis request and a report-sharing request. No benchmark was read.
- All 17 distinct generated phrases were matched against all 16,669 semantic
  graph tags in live Volmax, using the existing pinned embedder and query prefix.
  Product-name tags were excluded from this semantic vocabulary; no top-N cut was
  introduced. Full scores are retained, not only displayed neighbors.
- Both analysis generations provide stronger adjacent routes to the report than
  to the sharing record. Both sharing generations include a route to the record's
  `document sharing` tag. Thus the omitted semantic routes are real.
- The sharing generations differ. One has a stronger best route to the record;
  the other includes the shared `market research report` tag, making the maximum
  cosine over all tags identical for both chunks. A max summary hides the more
  discriminating sharing route in that case.

That last observation is an aggregation diagnostic, **not** a measured serving
result. Scope passes, fit levels, query facet scores, route order, deduplication
and delivery have not yet been replayed for these captures.

Evidence: `output/research/2026-09-21-facet-validity/query_route/route_matches.json`,
`tag_matching_scores.npz`, and `route_context/report_tags.json`. Broader findings
and limitations are in `output/research/2026-09-21-facet-validity/FRESH.md`.

## Execution: three parallel owners, then one integration

All new work stays in disposable tools, experimental tests and research output.
No production edits or database writes. No benchmark questions, gold, or
`arm_outputs.jsonl`. No new facet definitions or query prompts. No arbitrary
retrieval candidate caps. Only the designated capture owner makes model calls.

| Package | Owner | Concrete work | Finished when |
| --- | --- | --- | --- |
| A. Freeze intended query inputs | Scope/input agent | Validate all four current GENERATE captures with the split parser. Score each fixed description/tag list twice with the unchanged SCORE prompt. Preserve raw and cleaned tags, all exclusions, both readings, hashes and failures. Write `tools/facet_route_capture.py` and `route_capture/query_captures.json`. | Every captured run has an auditable description, complete tag list and five per-tag relevance values per successful SCORE reading; missing values remain explicit. No old interpreter or old facet schema is substituted. |
| B. Freeze graph routes | Pipeline agent | Reuse all captured tag vectors/scores. Read the established eligible Volmax graph, static facet overlay, chunk descriptions, scope membership and source content metadata. Compute required description/question embeddings once, in this owner only. Save a factorized graph snapshot and a manifest; do not materialize every repeated route unnecessarily. | Counts and identifiers reconcile to the graph/overlay; every generated tag's eligible tag–chunk routes can be reconstructed; scope and eligibility rules are recorded; no path is lost by first-arrival deduplication during capture. |
| C. Audit and expose operators | Evidence/operator agent | Specify and implement reusable local replay of the two existing forum operators, with deciding-key traces. Audit zeroed-facet ablations, higher-key barriers, pool additions, missing/tied values, query topic use, and route arrival/permutation. Provide a precise proposed correction only where the trace or a violated invariant justifies it. Own `test/artefact/facet_route_rank.py` and its focused tests. | Weighted equation and multikey tuple are explicit; all coefficients/scales have named origins; tests distinguish policy choices from defects. No invented coefficients are called validated. The operator interface can consume A/B without model or DB calls. |
| D. Integrate and decide | Parent | Reconcile A/B/C, run unchanged versus zeroed facets on identical captured inputs, preserve all route provenance, then compare any justified correction one change at a time. Audit route-to-chunk reduction and apply the context budget after full ordering. | Every changed position has a query tag, graph tag, edge and deciding rule. The trace identifies whether the analysis/sharing distinction survives, where it is lost, and whether facets contribute. |
| E. Independent final check | First available agent | Review the chosen method and claims against the frozen inputs, source passages, user contract and held-aside checks. | The final recommendation describes tag choice, query weight creation/use, weighted or multikey ordering, ties, missing values, route aggregation and budget behavior, with executable evidence and explicit limits. |

A and B run independently. C starts with an interface and fixtures while A/B
capture inputs. D starts only when the required inputs exist; E reviews D.
Agents own disjoint files. Parent alone edits this plan and the synthesis report.
The full vocabulary embedding work is reused. There is one graph snapshot and
one owner of further embedding work, avoiding repeated model loads and DB scans.

## Shared data contract

### Paper-informed check, within the same scope

The user's supplied paper, [Phrase Retrieval Learns Passage Retrieval, Too](https://arxiv.org/html/2109.08133),
uses contextual phrase vectors and maximum phrase-to-whole-query similarity to
score a source passage (section 3). Its within-passage negatives motivate checking
fine distinctions while holding topic/context close (section 4). It supplies no
five-facet weighting rule. Our shared graph-tag vector is not its contextual
phrase vector, and our maximum across separately generated query tags is not its
equation. Keep source context attached to routes and inspect generic versus
specific routes before chunk reduction. Use this as an aggregation diagnostic and
an inspiration for controlled checks, not a new indexing or training project.

The query capture keeps the original question ID, question, generated description,
raw tags, cleaned tags, parser exclusions, two separate SCORE readings and source
hashes. Canonical facet order is topic, temporal, why, activity, concreteness.
No averaging is hidden in capture; analysis must declare how it handles variation.

The graph snapshot is factorized into graph tags, chunks and HAS_TAG edges, plus
query-tag/tag similarities, description links and scope membership. Each edge
retains source IDs and its static five-facet measurements. The manifest specifies
how topic cosine and the four overlay values were obtained. Repeated query tags
or multiple routes must not silently create independent evidence.

Operator code consumes arrays/records and explicit configuration. It performs
no interpretation, model call, graph read, or cache selection. Its trace keeps
routes before chunk reduction and identifies the deciding key. Existing forum
code supplies the faithful baseline; its defaults and environment-dependent
options are captured rather than assumed.

## Decision gates and stopping rules

1. **Representation gate:** determine whether generated tags, actual matches and
   static edge readings contain the relevant distinction. If not, identify that
   precise missing link before changing the combination rule.
2. **Operator gate:** determine what the two sorts actually do with those inputs.
   Compare facets unchanged versus zeroed before fitting anything. A higher key
   deciding the result is not evidence for or against the facet values.
3. **Correction gate:** select at most one justified correction per diagnosed
   link. Do not launch a parameter sweep, another reader, or a new training round.
   A best-route diagnostic is not automatically the final aggregation policy:
   the current sharing example already warns that max can hide another route.
4. **Validity gate:** freeze the candidate and a small declared check pack before
   examining its outcomes. Include tag-route changes, within-tag facet tradeoffs,
   multiple-route behavior and mechanical invariants. Use explicit source-backed
   expectations; ambiguous preferences remain ambiguous. No benchmark tuning.
5. **Finish:** deliver the exact recommended rule, runnable replay, causal traces,
   checks and limitations. If neither operator supports a defensible method,
   finish this finite phase with the precise failed contract and the smallest
   necessary next change. Do not call the overarching goal complete, or start an
   unrelated substitute project to manufacture a positive result.

The next reasoning checkpoint is after D, before adding any new experiment.
This plan can be revised for a demonstrated dependency or failure; revisions must
name the reason and preserve completed evidence instead of restarting the task.

## Execution notes

- Controlled facet-path envelope comparison completed after the rejected joint
  candidate: same inputs, coefficients and relations, but max separately per
  facet before combining. 48 complete rankings; 17 component tests passed;
  230,784 output rows verified. The specific reversion path survives under all
  four auxiliary facets, but no tested pair direction improves. An exact bound
  shows that processing_design and sharing_1 cannot be repaired by any nonnegative
  final coefficients with topic at least as large as each auxiliary coefficient,
  conditional on these frozen path profiles. This is a conditional family bound,
  not a new definition of the user's topic-main requirement. Do not run a weight
  sweep in this family. Independent source checks beyond WorkFlowGenie are being
  frozen, including complementary evidence across two actually adjacent chunks.
  Results: `output/research/2026-09-22-joint-streams/source_first/facet_stream_envelope/RESULTS.md`.
  Independent review reproduced all witnesses and coefficient bounds. The new
  source-only pack is frozen and verified: seven questions, four source groups,
  nine source/context chunks, 25 quotations and 11 structural assertions in
  `output/research/2026-09-22-joint-streams/independent_sources/protocol.json`.
  No generated query fields or retrieval outcomes have been inspected for it.
  Next correction must address joint path/description/graph evidence before
  another final scalar weight fit; the failed fixed profiles cannot be repaired
  inside the tested coefficient family. Preserve these new cases as evaluation,
  and distinguish source groups from repeated SCORE measurements.

- New source-first pack and one frozen joint weighted candidate completed.
  Four answer-bearing questions were fixed before query generation/rank inspection.
  Existing concept and candidate each retain two of four expected source pair
  directions; candidate also loses the older sharing_1 distinction. Auxiliary
  facet removal preserves all pair directions; graph propagation wins only 0-2
  of 4,808 chunks per run. Candidate rejected, no constants tuned. In the reversion
  case, the specific tag path correctly favors the explanation but max-over-tags
  discards its distinction in favor of a broader subject match. The design case
  additionally loses caching detail in its stored description/tags. Evidence:
  `output/research/2026-09-22-joint-streams/source_first/joint_candidate/RESULTS.md`.
  Further scaling/increase checks were stopped after the user identified them as
  redundant. Next boundary is preservation of distinct query-tag/graph evidence,
  not another weight sweep or a claim that rank movement validates facets.

- The fuller concept assembly has now run on all eight captured readings, with
  actual frozen graph shape/adjacency and the current file overlay. These explicit
  file-source and split-input interventions are recorded; it is not an untouched
  production-default claim. All four report/sharing pair directions are correct,
  including sharing_1 which failed in both forum sorts. Exact source-link
  decomposition shows every focal direction is decided at the connection level
  before facets: this success does not validate weights. A separate 0.1 scaling of
  query facet magnitudes leaves all 4,808 positions unchanged. The common graph
  concentration modifier collapses all four non-topic positions on 56.78% of
  edges. See `output/research/2026-09-22-joint-streams/concept/RESULTS.md` and its
  frozen runs, control and independent review. The modifier ablation has also
  completed with graph growth/locality retained: 34,643 newly introduced
  four-column collapses, 147,180 changed coordinates, and 4,589-4,682 rank changes
  per generation, all within unchanged earlier-level groups. Four source-backed
  reversals within those groups were fixed for operator-blind reading. Both
  readers found all four insufficient to answer the questions, giving zero
  directional usefulness comparisons; this null result is retained. The next
  functional pack must establish answer-bearing contrasts before inspecting
  ranking changes, rather than count movement as improvement. Independent
  facet streams and final numerical combination remain unselected. The full goal
  is active and no validated complete method is claimed.

- User clarification after the replay: "the combination of the tag-path, the
  chunk_description-manouver, graph-shape(scope etc) TOGETHER would give the
  chunks, not just a single thing". This reiterates the existing contract. Root
  had narrowed the next step to tag aggregation again; that was scope drift.
  Standalone max/sum studies remain local diagnostics only. The next executable
  comparison must restore the joint description and structural mechanisms and
  audit how they interact with routes/facets, including what the forum branch
  omits. A missing interpreted gate is not the same as implementing graph scope.
- The user's next question raises separate recruitment by facet. Current forum
  and concept modes recruit through query tags; facets rank the shared candidate
  connections rather than independently recruiting streams. Per-(query-tag,
  facet) proposal streams are an OPEN architecture option, not a settled ruling.
  They must operate with tag fit, description links and graph structure; merging
  must retain provenance and avoid treating repeated routes as independent votes.
  No fixed batch sizes or stream weights have been selected. The revised combined
  contract is `output/research/2026-09-22-route-aggregation/CONTRACT.md`; current
  measurement limits are in the sibling `MEASUREMENT.md`.

- D completed 32 complete rankings. See
  `output/research/2026-09-21-facet-validity/route_replay/RESULTS.md` for the causal
  trace and decision at the planned checkpoint. Three generations retain the
  source-backed pair direction; sharing_1 fails under both operators and both
  SCORE readings, with or without the four non-topic graph facets. The broad
  route enters before the specific sharing route; its topic gap exceeds the
  weighted adjustment bound. New weight fitting is not the justified next step.

- A completed all eight SCORE attempts successfully, preserving 210 values. The
  repeated readings differ on 75/105 corresponding coordinates (mean absolute
  difference 0.1145; maximum 0.50). This is observed variation, not a calibrated
  uncertainty interval. See `route_capture/AUDIT.md` and `verification.json`.
- Both generated analysis descriptions omit the named flowAIX target and broaden
  possible analysis topics. The split output also supplies no structural gate.
  The primary replay therefore declares no inferred scope; it is an experimental
  input adapter, not a claim that the intended serving pipeline is complete.
- Exact delivery is conditional on safe source resolution. The existing resolver
  parses entire product files, including excluded benchmark sections. It has not
  been called here. Unless verified corpus-only resolved payloads already exist,
  D reports complete reachable-chunk ordering and explicitly omits delivery
  claims. The no-benchmark-read constraint takes precedence over reproducing the
  character-budget cut; exported plain text must not silently replace resolver
  payloads. This is a bounded reporting limitation, not a new loader project.
