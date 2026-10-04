# Independent review: fixed auxiliary-off pointer comparison

2026-09-22. Reviewed `tools/facet_gold_pointer_ablation.py`, the declared protocol, the facet-envelope/final-readout and recruitment code, and **only the summary** of the generated comparison. No benchmark questions, answers, contexts, source bodies or per-question gold details were inspected. No model, embedding or retrieval execution was performed by this reviewer.

**PASS for this bounded counterfactual.** It measures the auxiliary block's contribution to source-ID credit in the existing saved smoke, with the query representation, graph, scope and actual delivery mechanism held fixed. It is not a new gold smoke, generated-answer evaluation, independent validation set or demonstration of correct facet meanings.

## Mathematical sufficiency of the cached topic contribution

In `test/artefact/facet_stream_envelope.py:48-63`, each facet is computed with all other facet inputs zero. Its direct/neighbor maxima form an independent column `Z[:,f]`. In `test/artefact/facet_retrieval_pipeline.py:59-69`, the final score and saved contribution are:

```text
score(c) = Q(c) * sum_f beta(f) * Z(c,f)
contribution(c,f) = Q(c) * beta(f) * Z(c,f)
```

The saved topic coefficient is checked to be 1. Therefore replacing beta `(1,.25,.25,.25,.25)` with `(1,0,0,0,0)` leaves `Q` and `Z_topic` unchanged, and its entire score is the saved topic contribution. No re-embedding, query interpretation or route search is needed. A missing topic witness means no positive topic envelope and yields zero. The code also zeros the displayed auxiliary coefficients/contributions while retaining their route witnesses as inactive provenance (`tools/facet_gold_pointer_ablation.py:144-158`).

This argument depends on the present independent-facet architecture. It would not apply unchanged to an operator whose winning topic route depends on the combined auxiliary score. The review checked the actual implementation, not merely the formula described in the protocol.

## Preservation and accounting checks

The tool freezes source hashes and the two coefficient conditions before computing the comparison. It verifies graph/facet snapshots and the relevant resolver, budget, envelope and recruitment code against saved run provenance. It checks the sum of recorded contributions against every saved chunk score and preserves the original saved scores for baseline ordering, avoiding a changed summation order.

For each of the ten existing cases, the code reuses the saved verified-area membership and provenance, recomputes nomination/record recovery, and checks complete baseline recruitment equality and recovered-order equality. Actual shared `_resolve_chunk` and `_budget_contexts` logic then reproduces **the exact saved context strings, credited source IDs and budget object** before the counterfactual is interpreted (`:134-143`). Raw texts are used mechanically for that equality test, not printed or exported.

The off condition runs the same scope/recovery and actual 72,000-character delivery helper. It does not discard outside-area access, change the budget, substitute the research text-length accounting, or assume the old delivered set remains valid after reranking. Partial boundary text and full-unit artifact credit retain the shared harness semantics.

## Gold boundary and scope

Gold citation values do not enter score computation, area membership, recovery or delivery. They are joined to the resulting source credits afterward (`:159-178`). One wording qualification matters: the gold index and original trace file are loaded earlier (`:89,112`), so this is **downstream use of gold only**, not literally a program that first reads gold after ranking. The saved question IDs select the fixed ten cases; citation membership cannot alter either condition's scores or order.

The treatment is one prespecified auxiliary-off alternative. There is no coefficient search, new query generation, source-specific rescue, model judge or answer generation. The protocol explicitly ends with gains/losses/ties and prohibits tuning in response. The HTML inherits the pointer diagnostic's question/answer/source-body text omission and source-ID-versus-evidence warning.

## Observed aggregate result

The generated comparison summary reports:

| Check or outcome | Result |
| --- | ---: |
| Saved cases / exact full recruitment and text-delivery parity | 10 / 10 |
| Maximum contribution-sum discrepancy | 2.7755575615628914e-17 |
| Macro source-ID recall, joint | 0.33053887697655054 |
| Macro source-ID recall, auxiliaries off | 0.309877256567243 |
| Joint minus off | +0.02066162040930754 |
| Source–question links credited only with auxiliaries | 21 |
| Source–question links credited only without auxiliaries | 12 |
| Questions with better joint / better off / tied net ID recall | 2 / 0 / 8 |
| Model calls / embedding calls / new answers | 0 / 0 / 0 |

The valid interpretation is **a small positive aggregate source-ID effect for the auxiliary block on these fixed saved queries, with source-level tradeoffs**. The eight tied net-recall cases do not prove identical delivered sources or contexts. Zero questions with worse net recall does not mean no source losses: twelve source–question links occur only in the off condition.

These are dependent source/question links from the same ten already observed smoke questions. No significance, generalization or exhaustive answer-evidence claim follows. This result does not isolate which facet helps, prove named query/graph facet correspondence, validate coefficient magnitudes, or establish better generated answers. Neither low absolute recall nor individual missed sources invalidates this bounded comparison or requires a rescue.

Reviewed implementation SHA-256: `e14fa604c5874b40ebd6df55f6fd1f3eef01dc4de151461a63a8964c1befcc53`. Reviewed protocol SHA-256: `d87859309b08f14b06681f95642e426d3df37d934835e74a5c41b8cac7eaed84`.

No correction to the comparison mathematics or serving accounting is requested. Carry the outcome into the user's source-pointer inspection, with the limits above; do not expand this review into a new experiment or perfect-recall gate.
