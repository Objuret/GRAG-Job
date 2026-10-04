# Area-first admission: a substantial construction effect

**Completed full-arm smoke:** 10 answers, 139 successful RAGAS cells and one faithfulness error. ID recall 33.05% -> 39.32%, precision 13.20% -> 16.52%; interpretations, chunk scores, areas and 72k budget identical on all ten. See [full results](2026-09-22-facet-area-smoke-results.md). This supersedes earlier pending/no-new-quality statements below; weights remain provisional. No further benchmark run is queued.

The fixed intervention in `2026-09-22-area-admission-protocol.md` completed on all
85 saved successful remaining-90 records. All five original interpreter failures
remain failures. No new interpretation, embedding, answer or LLM judging occurred.

## Actual installed RAGAS ID metrics

| Scheduling and score | Mean source-ID recall | Mean source-ID precision |
|---|---:|---:|
| Equal-depth, topic only | 27.2053% | 8.2363% |
| Equal-depth, joint facets | 29.1484% | 8.7489% |
| Area-first, topic only | 38.9100% | 11.6599% |
| Area-first, joint facets | **40.3130%** | **12.2520%** |

The scope change with joint scores adds **11.1647 percentage points of recall**
and **3.5031 points of precision**. Recall improves on 46 questions, worsens on
none and ties on 39. Precision improves on 52, worsens on 21 and ties on 12.
Source-question gold hits rise from 895 to 1,303; these are 408 extra links, not
408 independently judged relevant documents.

Counting the five failed queries as zero recall, joint recall over the planned
90 cases changes from 27.5290% to 38.0734%.

Under area-first admission the auxiliaries add **1.4031 recall points** over topic
alone, with 20 questions better, 11 worse and 54 tied. They add 0.5922 precision
points on average, with 38 better, 31 worse and 16 tied. The large change is the
scope scheduling decision; it is not evidence that new facet coefficients were
found. The coefficients and all numerical query/edge measurements stayed fixed.

## Mechanism and limits

Every successful saved query has a resolved area. The equal-depth joint policy
uses 2,446,489 characters on full units outside those areas. The area-first joint
policy uses no full outside units at this budget. These counts exclude partial
boundary text. They measure budget allocation, not irrelevant-text volume.

This test uses the old saved literal areas, overwhelmingly determined by the
single-product question setting. Earlier source-pointer diagnosis found every
gold link represented within the question's product. The result therefore
supports fixing this dataset's admission allocation, not a universal rule that
outside-area evidence is unhelpful. Strict priority can fail when area resolution
is wrong, when a question needs multiple areas, or when useful evidence is outside.
It retains outside candidates in the full order, but can exhaust the budget
before reaching them. That practical exclusion is explicit.

Record recovery can advance an outside sibling of an in-area sponsor; it remains
the same operator in both conditions. No raw-question text, benchmark product ID,
gold IDs or expected answers are inputs to scheduling. Gold enters only after
each condition's delivery is fixed.

The earlier sponsor-first repair is common to both policies. Compared with the
archived joint order it changes no recall on these 85 cases and improves precision
on one by a very small amount. Its fidelity justification remains sound; this
comparison confirms that it was not the main measured recall problem.

These are reused citation-ID cases, not a fresh holdout, exhaustive relevance
judgments or answer-quality evidence. No RAGAS faithfulness, answer correctness
or LLM context recall has been measured for this intervention.

## Integrity and usable implementation

The audit executes RAGAS 0.4.3's ID metric classes: 850 deterministic metric calls,
including the archived integrity condition. All 85 archived budgets and credited
ID sets reproduce exactly. The plan freezes inputs/code before the run; final
hash checks pass. Source movement IDs are preserved downstream of selection.

Independent verifier `tools/facet_area_admission_integrity.py` confirms all 85
saved resolver fingerprints against the pointer index and current resolver,
all 4,808 eligible units' exact serialized lengths and ordered artifact-ID lists,
30 raw-file hashes, unchanged trace/input hashes and the complete 90-case partition.

Artifacts are in
`output/k=chars/artefact_facet_joint__gold90__cb72000__20260922T090621382244Z/area_admission_diagnosis/`:
`plan.json`, `results.json`, `source_movements.jsonl`, `integrity.json`.

The normal harness now registers **`artefact_facet_area`**. It shares the joint
arm's interpreter, local embedder, facet scores, pinned graph, source resolver and
72k budget. It selects `area_first` explicitly during preparation and records
that selection plus the wrapper's source hash. `artefact_facet_joint` retains
`equal_depth`. No environment flag silently changes either policy.

The runnable area arm uses the current broader structural resolver. The replay
held the older saved areas fixed, so its reported numbers must not be presented
as a fresh run of this complete arm. A future run can use:

```powershell
.venv\Scripts\python.exe -B -X utf8 prod/run.py --arm artefact_facet_area --set 10smoke --char-budget 72000 --generator claude-sonnet-5 --no-eval
```

This command has **not** been executed. Integration/regression validation: 49
tests pass, and the normal CLI lists the new arm with character-budget support.
No final semantic validation or optimal facet-weight claim follows.
