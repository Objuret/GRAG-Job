# Recommended experimental retrieval policy

## Current qualification

The earlier recommendations and stop directions below are historical. Subsequent
user-authorized broad retrieval experiments and their limits are recorded in
`2026-09-22-live-retrieval-matrix.md` and `2026-09-22-facet-weight-protocol.md`.
The live lab can replay the strongest observed constructions and custom weights.
These experiments have not established a final valid facet measurement method;
no construction is automatically promoted to the serving arms.

The completed 95-case matrix reaches 49.41% fixed-policy source-ID recall;
topic-largest coefficient exploration reaches 50.96% observed, or 49.94% with
coefficients chosen on other product groups. Label controls weaken the argument
that the auxiliary query dimensions are functioning as intended. The active
conditional edge/query experiment separates useful placement within tag/type
groups from query-tag assignment and their interaction. See the current section
of `2026-09-22-facet-retrieval-plan.md` for scope and outstanding validation.

## Historical candidate recommendations and evidence

**Completed full-arm smoke:** 10 answers, 139 successful RAGAS cells and one faithfulness error. ID recall 33.05% -> 39.32%, precision 13.20% -> 16.52%; interpretations, chunk scores, areas and 72k budget identical on all ten. See [full results](2026-09-22-facet-area-smoke-results.md). This supersedes earlier pending/no-new-quality statements below; weights remain provisional. No further benchmark run is queued.

**Latest candidate:** `artefact_facet_area` is now a selectable area-first version
of the existing joint scoring arm. A fixed saved-input scheduling intervention
raises RAGAS ID recall from 29.15% to 40.31%, with coefficients unchanged; auxiliaries
add 1.40 points inside the new policy. The 85 cases all have saved resolved areas,
and this is reused citation-ID evidence. The current runnable arm has the broader
resolver, so these are not fresh full-arm quality results. See
`2026-09-22-area-admission-results.md` for losses, limits, integrity and usage.
No final facet-weight or broad semantic-validity claim is made.

**Current status, following the user's critical review:** the recommendation below
is historical and is not the final answer. Stop coefficient comparisons. The
remaining-90 diagnosis exposes an incomplete structural landing path and an
unjustified global/area scheduling convention; these must be addressed before
claiming that this arm implements the intended combined retrieval design.
See [critical diagnosis](2026-09-22-facet-critical-diagnosis.md) for the measured
stage effects, limits of the evidence, and contained next repair.

The omitted structural landing path has now been connected and mechanically
verified; see the [repair record](2026-09-22-structural-landing-repair.md).
Scheduling and facet semantics remain unresolved. Earlier retrieval metrics
describe the pre-repair arm; no new quality result is claimed.

Use a separate best-supported path for each facet, combine those paths with
explicit topic-led coefficients, and recover connected source context before
applying the context budget. This is the current executable candidate, supported
by bounded source-based tests. It is a recommendation for the prototype, not a
claim of universally correct facet numbers or a production deployment.

Individual source misses are not vetoes on this iteration. The user's 2026-09-22
clarification explicitly rejects 100% gold as an expectation. Event-specific
probes below diagnose behavior and measurement; their recovery is not a required
success condition for recommending a useful, honestly measured experimental arm.

The independent scope/overfitting audit closes development on the current seven
questions. Repeated interpretations and retrieval conditions are not independent
validation; adaptive overfitting risk is substantial. Keep this candidate as a
usable experimental baseline with explicit operating coefficients, not validated
weights. Do not tune its prompt, scope or coefficients further on these cases.
See [`scope/overfitting audit`](2026-09-22-facet-scope-overfitting-audit.md).

A subsequent fixed comparison now measures the auxiliary contribution through
HERB gold-source pointers and actual delivery: joint ID recall 0.330539 versus
0.309877 with auxiliaries off, using identical saved inputs and scope. Two smoke
questions improve by net cited-source count and eight tie; 21 gained links trade
against 12 lost links. Exact baseline text-delivery parity holds for all ten.
This supports a bounded contribution claim for the experimental policy, not
optimal coefficients or new answer-quality results. See
[`gold-pointer comparison`](2026-09-22-gold-pointer-ablation-results.md).

A separate fixed correspondence control also favors the intended pairing in
aggregate: 0.330539 versus 0.312321 with rotated auxiliary query readings, with
two questions better, one worse and seven tied. Baseline and joint-relabeling
symmetry delivery checks pass for all ten. This strengthens the bounded functional
evidence, while leaving coefficient calibration and facet construct validity open.
See [`correspondence comparison`](2026-09-22-gold-pointer-correspondence-results.md).

The subsequent fresh interpretation-to-context smoke completed all 14 retrievals
but exposed a stability problem: the three audited needs retained known component
support in both readings, while the later imentAIX review fell outside the budget
in both fresh review readings. Treat this as a runnable experimental candidate,
not demonstrated reliable retrieval. See
[`fresh_smoke/RESULTS.md`](../output/research/2026-09-22-joint-streams/independent_sources/fresh_smoke/RESULTS.md).

The candidate now also has a raw-question harness arm, `artefact_facet_joint`.
Its standard fixed `10smoke` completed ten answers and all 140 RAGAS metric cells:
source-ID recall 0.330539, precision 0.131969, answer correctness 0.221402 and
faithfulness 0.876090. One interpreter response lacked JSON; a recorded retry of
only that missing case completed the run, preserving the other nine answers.
This establishes execution and reports quality, not validated facet semantics or
improvement over a matched baseline. It uses the shared serialized-context budget,
which differs from the research accounting below. See
[`2026-09-22-facet-joint-gold-smoke-results.md`](2026-09-22-facet-joint-gold-smoke-results.md).

One later development trial added a generic compound-preservation sentence to
GENERATION, leaving retrieval and facet coefficients fixed. Under research
source-character accounting it restores the known later review event in both
readings, but moves ActionGenie's complete known support
from 12,767 to 27,138-30,653 saved-source characters. Some query constraints are
still omitted or strengthened. This mixed result does not justify promoting the
prompt as a general fix; the registered raw-query arm remains unchanged. See
[`phrase_preservation/RESULTS.md`](../output/research/2026-09-22-joint-streams/independent_sources/fresh_smoke/phrase_preservation/RESULTS.md).

The completed delivery bridge qualifies that result: neither trial review reading
fully delivers that event under the actual 72,000 serialized-character budget;
complete-unit acquisition costs are 100,599 and 77,960. All 18 audited
need/cohort/reading conditions retain known requested component support. This is
a measurement distinction and a documented limitation, not another rescue target.
See [`delivery_bridge/RESULTS.md`](../output/research/2026-09-22-joint-streams/independent_sources/delivery_bridge/RESULTS.md).

## How the numbers are made and used

Keep the two measurements distinct:

- On each graph tag-to-chunk edge, keep its static facet readings. Topic comes
  from the existing tag/chunk-description cosine; the other four come from the
  saved learned head. They do not change with the question.
- For each query tag, keep the querytagger's five readings of that tag's relevance
  to the described answer content through each facet. These are not importance
  weights for the facet itself. Do not divide them by their sum or force one to 1.

For combination, express each graph column as a rank against one fixed reference:
all 57,204 eligible semantic tag-to-chunk edges in the frozen graph. A value's
score is the fraction below it plus half the tied fraction. This reference must
be versioned and must not change with the query's candidate pool.

This gives population-relative rank positions, not probabilities of usefulness.
It also transforms topic for scoring: the underlying topic measurement remains
cosine, but its rank replaces its raw cosine magnitude in this policy. Do not
claim that raw topic magnitude, sign and zero are preserved by this transform.

Let `u[i,f]` be a query reading and `F[f,e]` the fixed graph rank. For each facet:

```text
direct[i,f,c] = max over edges e=(tag t, chunk c):
                 positive_cos(query_tag_i, t)
                 * positive_cos(query_tag_i, chunk_description_c)
                 * u[i,f] * F[f,e]

neighbor[i,f,c] = 0.5 * positive_cos(query_tag_i, chunk_description_c)
                       * max direct[i,f,s] over actual neighbors s != c

Z[f,c] = max over query tags i: max(direct[i,f,c], neighbor[i,f,c])

score[c] = positive_cos(query_description, chunk_description_c)
           * (Z[topic,c] + 0.25 * sum Z[other_four_facets,c])
```

`positive_cos` is max(cosine, 0). Neighbors use actual shared Product+Channel
membership and locator adjacency. Each winning facet retains its own query tag,
graph edge, source seed and structural relation. A chunk can therefore receive
topic support through one path and temporal/activity/etc. support through another.
These are different perspectives on one chunk, not five independent evidence votes.

The coefficient rule is **topic 1; each auxiliary 1/4**. The denominator is the
number of auxiliary facets: they share one coefficient unit, with no unsupported
preference between them. That is an explicit symmetric operating convention,
chosen before the observed outcomes. It is not estimated from those outcomes or
derived from the facet names as utility. The extra-hop factor 0.5 is also a stated
engineering convention, not a measured likelihood.

Topic receives four times each auxiliary's coefficient. This does **not** force
topic to dominate every realized score, require all auxiliaries to use the topical
winner's route, or make topic lexicographically decisive. A stricter interpretation
would be a different policy. We should not silently claim that stronger contract.

## How tags and chunks are chosen

Consider every eligible semantic tag route in the captured graph; do not impose
a fixed tag pool or a fixed batch size per facet. Maxima prevent exact copies of
the same route or query tag from accumulating votes. The separate facet paths
remain available until the combined chunk score is formed, so an earlier sort
key cannot make the other facets irrelevant by construction.

Use the combined score for nomination. The research replay keeps complete tied
frontiers for source-character admission. The actual arm preserves the recovered
order, then uses the shared serialized-context helper, which can cut a boundary
unit; it does not provide the research replay's whole-frontier admission guarantee.
Preserve related parts of an exact source record:
overlapping or touching locator ranges share their earliest nomination depth.
Recovered parts retain their own scores and facet witnesses; they do not inherit
fabricated evidence from the triggering part.

Keep the structural-area option separate from the score. An externally verified
area can nominate from its own unchanged-score list alongside the global list,
using the existing equal-depth union. Outside chunks keep global access; unresolved
scope falls back to global nomination. No answer-derived alias, arbitrary boost
or product exclusion belongs in this policy. The demo's global mode is not itself
an area resolver; its optional frozen-area mode only consumes archived verified
membership and provenance.

The current 72,000-character limit is the inherited experiment's context budget,
not a newly optimized constant. The tool requires callers to state it explicitly.
Whole-frontier source-character accounting includes record recovery and overlap;
it is not the production token/serialization budget.

## What was actually run

The main comparison contains **42 frozen-input retrieval runs**: seven
source-derived questions, two query-score readings, and three query-tag aggregation
policies. These are retrieval replays, not 42 fresh end-to-end benchmark smokes.
The later standard gold smoke is reported above, separately from these replays.
Separately, the fresh smoke ran seven new GENERATE and fourteen new SCORE calls,
then fourteen retrievals with the same policy. Its results and regressions are
reported in the linked smoke report; these do not replace the historical replay
numbers below.
The comparison holds scope policy fixed across methods, reusing the archived
verified area when resolved. Both sentiment questions use the unresolved global
fallback. To reproduce a resolved-area row through the demo, use `--verified-area`.

The table shows saved source characters acquired before known supporting passages
cover the requested components. Smaller means earlier acquisition in that saved
ordering, not necessarily a better final answer. Ranges reflect two SCORE readings.

| Question | Max (recommended baseline) | Equal query-tag aggregation | Embedding reconstruction aggregation |
| --- | ---: | ---: | ---: |
| ActionGenie durability, model updates and refresh frequency | 10,000 | 13,630 | 10,000 |
| imentAIX intended enterprise offering and customization | 22,854 | 16,070-19,093 | 22,854 |
| imentAIX review components (earliest known support: PR6) | 3,290 | 3,290 | 3,290 |

All those known components fit within 72,000 characters. The content checks cover
43 ActionGenie passages and 71 sentiment/control passages, using two independent
agent readers per packet with exact source quotes and preserved disagreements.
These are fallible model judgments, not human gold. The seven questions are not
seven independently validated successful tasks; the table reports the narrower
source-audited comparisons.

The most useful auxiliary-facet result is event-specific. In four max conditions
(two sentiment questions, two readings), the later PR 10 review is retained
**4/4 with auxiliaries and 0/4 with auxiliaries off**, at the unchanged budget.
These are four related conditions, not four independent task replications.
Both conditions retain the earlier PR 6 review. Those events report different
accuracy/documentation findings. For the review question, the later event's
acquisition cost is 26,266/33,573 with auxiliaries versus 83,110/72,997 without.
For the intended-use question it is extra context, not improved offering coverage.
This is a bounded information-retention effect; it does not establish that every
auxiliary facet is semantically correct or necessary.

Source: `output/research/2026-09-22-joint-streams/independent_sources/crossed_content/RESULTS.md`,
its independent REVIEW and event_support.json; and
`query_interpretation_intervention/CONTENT_COST.md` beside that experiment.

## How to measure the function from here

Use supported claims with **subject, event and status**, retaining exact source
spans and alternative sources for the same claim. Measure whether the selected
delivered context contains them and the serialized cost of acquiring them. Keep
historical whole-frontier source costs explicitly separate. Preserve
qualifications and conflicting events instead of reducing both to a generic
"accuracy covered" flag. A missing designated document is not an information
loss when another selected document supplies the same claim.

Use component coverage as a coarse diagnostic, and inspect distinct claims/events
before calling two contexts equivalent. Keep correctness of the facet reading,
mechanical effect of its contribution and usefulness of the resulting context
as separate questions. A changed rank alone proves none of the latter two.

The current policy has reproducible mechanics, source-backed conditional behavior
and a demonstrated local auxiliary contribution. That is sufficient to recommend
it for the prototype. Unique exchange rates, perfect labels and winning every case
are not required for that recommendation. Stronger claims about unseen-query
robustness or validated facet semantics remain unsupported. The known query
interpretation errors, graph-head limitations and source-reader disagreements
remain counterevidence; this recommendation does not erase them.

## Runnable artifact and practical limits

See `docs/facet-retrieval-demo.md` and `tools/facet_retrieval_demo.py`. They expose
prepared queries, explicit coefficients and budget, full selected text, route
witnesses and recovery triggers. The original example recomputes all 4,808 scores
and exactly reproduces 24 contexts totaling 67,944 saved characters.
The opt-in archived-area example also reproduces all scores and the full saved
recruitment: ActionGenie returns 28 contexts / 66,549 characters, including nine
outside its area. The unresolved sentiment option returns the same 24 contexts /
67,944 characters as global nomination. Each new run includes verification.json.

This completes an executable experimental recommendation. The later snapshot-backed
raw-query arm adds harness integration, but does not establish a repaired interpreter,
optimal weights or deployment readiness.
Further work should address a concrete unsupported requirement or failure, not
keep retuning coefficients to this small set of already inspected sources.
