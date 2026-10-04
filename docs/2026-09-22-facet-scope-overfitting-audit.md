# Independent scope and overfitting audit

2026-09-22. Requested by the user; conducted by a fresh review agent. Read-only review except for this report. No model or embedding calls, benchmark questions/gold/answers/contexts, or raw corpus were inspected. The reviewed evidence comprises the supplied 2026-09-20 state, current plan/recommendation, actual arm and scoring code, experiment protocols/results, delivery parity report, and aggregate gold-smoke report. This is a bounded code/document audit, not a rerun or a proof that every historical action was uncontaminated.

## Verdict

**The implemented candidate remains within the joint-retrieval scope, but the investigation drifted toward repeatedly repairing one known event. The development evidence has substantial adaptive-overfitting risk. I found no evidence in the inspected arm/protocols of gold-driven tuning or a hardcoded rescue. I cannot establish absence of statistical overfitting without independent checks.**

The relevant goal is a viable, faithful, measurably useful way to use the facets with tag paths, descriptions and graph structure. It is not perfect gold recall, retrieval of every chosen source, or a unique mathematically optimal coefficient vector. The user's latest clarification is consistent with that goal. A missed event may be an ordinary limitation of this iteration; one returned event cannot validate the design either.

## Findings

### 1. Real scope alignment in the runnable arm; semantic validity remains open

The actual arm uses unchanged split query interpretation, fixed graph readings, tag/chunk and description matching, actual graph relations, facet-specific path maxima, area/global nomination, and source-record recovery. It then calls the shared delivery helper. It is not merely a flat tag sort: see `test/arms/artefact_facet_joint.py:24-31,66-75,317-330,348-357` and `test/artefact/facet_retrieval_pipeline.py:50-69`. Literal Product area resolution is explicitly limited (`artefact_facet_joint.py:307-314`); it should not be described as a complete semantic scope resolver.

The formula's coefficients `(1,.25,.25,.25,.25)` and extra-hop factor `.5` are operating conventions. A fixed graph percentile reference supplies comparable positions, not validated cardinal facet utilities or topic units. The recommendation says this correctly (`docs/2026-09-22-facet-retrieval-recommendation.md:50-58,83-93`). The experiment does not yet establish that the named facet correspondence is useful: the correspondence control changes selections in 9/12 related conditions, but shows no uniform advantage in the measured support/event outcomes (`fresh_smoke/correspondence/RESULTS.md:19-36,86-97`). That is a limitation of the evidence, not a demand to make every case win and not proof that facets are useless.

The supplied state itself distinguishes user meaning, measurements and agent constructions (lines 6-17). Its warning that existing pairwise judgments inherit agent-added facet glosses is material (section 5, “Known contamination”). Downstream retrieval success would not by itself repair that construct-validity issue. The newer user clarification about activity also takes precedence over an older restrictive operational gloss.

### 2. Adaptive development reuse is real; independent generalization is not established

The fresh smoke uses seven existing development questions, with two SCORE readings each (`fresh_smoke/RESULTS.md:8-12`). The phrase trial explicitly says the known review regression motivates it and these same seven questions are development material (`phrase_preservation/PROTOCOL.md:3-5,30-39`). The resulting 42 original/fresh/trial retrieval records are repeated conditions on those questions, not 42 independent tasks. Only three needs have the comparable component audit; four questions have execution evidence without that quality audit (`phrase_preservation/RESULTS.md:23-34`).

A frozen protocol protects a particular experiment against changing its rules after that experiment's results. It does **not** erase the prior outcomes used to choose the next experiment. Repeated attention to PR10, the compound-route intervention, graph-scope alternatives, and the later phrase prompt therefore form an adaptive development sequence. A generic prompt change can overfit a small inspected development set without containing a product name or source ID. More hashes, controls, repeated SCORE calls or another fresh generation of the same questions do not create independent validation.

The documentation mostly acknowledges these limits. Its repeated headline emphasis on the rescued/missed event can nevertheless make that event an implicit acceptance gate. The plan now explicitly admits and stops this drift (`docs/2026-09-22-facet-retrieval-plan.md:6-14`). That correction should govern actual next actions, not only wording.

### 3. Diagnosis was legitimate; continuing until PR10 returns would not be

The Q-by-Z and whole-route interventions establish a specific dependency of the existing mechanism, while distinguishing the bundled old facet readings from phrase-only causality (`fresh_smoke/regression/RESULTS.md:3-8,24-33,55-58`). This is useful causal diagnosis within the user's authorization to investigate failures. The subsequent generic phrase trial was a bounded development experiment, not an intrinsically illegitimate task.

The drift begins when recovering that event becomes the reason for further changes despite adequate alternative support and no requirement to retrieve every event. The trial itself reports that the review question does not establish both PR6 and PR10 as mandatory (`phrase_preservation/RESULTS.md:51`). Preserve the miss and the successful alternative support as part of the observed tradeoff. Do not add another phrase, coefficient, scope, or budget repair to get this source across the cutoff.

### 4. The delivery bridge materially qualifies the last “recovered” result

The phrase trial's research accounting reports PR10 back in both review readings (`phrase_preservation/RESULTS.md:43-45`). Actual serialized delivery at the same nominal **72,000 characters** does not fully deliver that witness in either reading: complete-unit costs are **100,599 and 77,960** (`delivery_bridge/RESULTS.md:60-67`). This does not invalidate the archived research measurement; it means its source-character cutoff and actual delivered-context cutoff are different instruments.

The bridge is directly within scope because it tests the function actually served, without altering rankings or adding labels (`delivery_bridge/PROTOCOL.md:3-6,15-20`). Actual scope and recovered-order parity were checked for all 42 conditions (`delivery_bridge/AREA_ORDER_REVIEW.md:3-5,19-33`). All 18 audited need/cohort/reading conditions still retain known complete component support under delivery (`delivery_bridge/RESULTS.md:21-38`). Therefore the valid conclusion is a measurement qualification and mixed development behavior, not another mandatory rescue.

The recommendation's current “restores ... in both readings” headline needs this explicit delivery qualification (`docs/2026-09-22-facet-retrieval-recommendation.md:31-37`). Also distinguish its research whole-tie admission rule (`:103-105`) from the actual arm's serialized partial-boundary helper (`test/arms/artefact_facet_joint.py:356-357,379`). Neither should be silently presented as the other's serving contract.

For the separate gold smoke, 72,000 was indeed the delivery budget. The evaluator's 60,000 setting is a warning threshold, not a truncation cap: `prod/eval/ragas.py:537,589-612`; the corrected smoke report now states this accurately.

### 5. No inspected evidence of direct benchmark leakage; the smoke is not a matched comparison

The arm receives raw questions through the ordinary harness and contains no question-ID lookup or PR10 rule. The generic phrase rule includes no example phrase, product exception or expected source (`phrase_preservation/PROTOCOL.md:15-18,34-36`), and was not promoted into the arm. The blind runner freezes code/settings, checks them before evaluation, and aggregates metric cells (`tools/facet_joint_gold_smoke.py:101-143,198-224,238-248,288-298`). These are substantive protections.

The smoke report records ten completed answers, one format retry preserving nine successes, aggregate-only inspection and no tuning from those results (`docs/2026-09-22-facet-joint-gold-smoke-results.md`, “Reliability and interpretation”). I did not inspect private logs or independently reconstruct the entire interaction history, so “no evidence found” must not become a claim of proven absence of leakage.

Recall 0.331 and correctness 0.221 neither disqualify the candidate for missing perfection nor prove it improved on an older arm. There is no matched baseline in that smoke. Faithfulness is a different property from evidence coverage. Keep those observations separate from claims about whether a specific facet measurement or combination is valid.

## Carry forward and stop

Carry forward the working experimental arm, fixed and explicit policy, route provenance, actual 72k delivery instrument, bounded causal diagnoses, documented null/mixed results, and the gold smoke as an execution/quality observation. It is reasonable to call this a usable experimental baseline.

Stop treating the existing seven questions or a fresh generation of them as new validation; stop PR10 rescue as a success gate; do not promote the phrase prompt from its development result; do not fit coefficients or choose new scope behavior from these cases or the observed smoke means. The inspected evidence is insufficient for “validated facet weights,” “generally better interpreter,” or “improved retrieval over baseline.”

## At most three next steps

1. **Freeze this candidate and close the current development loop.** Update the top-level claims with the delivery qualification and keep this seven-question set explicitly as development/regression material. No further rescue of its named sources is needed.
2. **Make the next functional check independent and facet-focused.** Before outcomes, freeze a small new set of information needs from distinct, previously unused source groups and method-hidden support assessments; compare the unchanged joint candidate with the same pipeline's auxiliaries disabled and one predeclared correspondence control at actual 72k delivery. Preserve misses, alternatives and unknown judgments; aggregate at the independent need/source-group level. This is one bounded check, not a threshold requiring all cases to improve and not a request for the user to label the corpus.
3. **Decide at that checkpoint.** If the evidence supports useful auxiliary contributions with acceptable tradeoffs, retain the explicit operating policy and report its limits. If the result is null or inconsistent, leave this arm as a runnable baseline and identify the unresolved facet measurement/readout claim. Do not turn another individual miss into an open-ended repair program or demand unique optimal weights.

No new experiment was launched by this audit. Its central finding is scope drift and adaptive evidence reuse, not a demonstrated numerical overfit estimate or benchmark-contamination verdict.
