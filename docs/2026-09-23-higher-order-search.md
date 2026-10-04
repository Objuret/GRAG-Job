# Higher-order construction search and effective coverage

> Latest continuation: both original 95-case comparisons have now completed and
> passed independent delivery verification. The combined 561-construction run is
> executing. Four recovered cases have also been captured and checked separately.
> See [completed results and continuation](2026-09-23-construction-population-results.md)
> and [recovered-case evidence](2026-09-23-recovered-case-capture.md). Earlier
> preparation-time status statements below are preserved as historical context.

The two population comparisons are still running. This document records the
next executable search stage; it is not a result or a completion claim.

## Measure effective changes

`tools/facet_program_findings.py` reads completed case checkpoints and reports:

- Distinct full-order signatures, delivered prefixes and delivered sets.
- Settings observationally equivalent across the observed cases.
- Every available matched one-factor contrast, including nonreference contexts.
- Best fixed rules by total gold-source hits and by macro per-case recall.
- A separately labelled per-case gold-selected oracle over the finite catalog.

Example checkpoint: 14 operation-comparison cases had 524 distinct full-order
signatures among 693 settings; eight entity-route cases had 131 among 224.
These equivalences are observations on those subsets, not proof that the
constructions are universally equivalent. Refresh findings after population
completion. Do not use settings counts as the number of useful experiments.

```powershell
.venv/Scripts/python.exe -B tools/facet_program_findings.py --out output/research/2026-09-23-construction-programs
.venv/Scripts/python.exe -B tools/facet_program_findings.py --out output/research/2026-09-23-entity-route-programs
```

## Search rule declared before completed parent results

`tools/facet_joint_search.py` requires completed, independently verified parents
with identical case populations. It refuses partial checkpoints as seed inputs.

Within each recruitment/scope family, retain configurations not dominated on
both total gold-source hits and macro per-case recall. Keeping separate families
prevents one globally strong joint rule from eliminating independent recruitment
or alternative scope formation before their combinations are investigated.

For equal metrics and identical full-order signatures within a family, retain a
deterministic representative, preferring fewer operations. This prunes the search;
it does **not** establish semantic equivalence under future changes. From each
retained configuration, test every valid single-component change and each
alternative shared-entity projection. Reference and seed configurations remain
in the new population for matched comparisons. This permits multi-component
constructions beyond the original pairs around the reference.

This is a local search. It neither guarantees a global optimum nor covers every
possible dataflow program. If another round is justified by the results, include
the completed round as an additional parent and keep the exact plans/results.
Do not silently reset the experiment around a new hand-chosen construction.

Seed selection uses evaluation gold, as requested for finding high-performing
settings. Each resulting fixed retrieval rule runs without gold inputs. The
search does not establish performance on unseen questions. Per-case oracle
choices remain diagnostic and must never be substituted for a runtime selector.

## Run after both parents complete

```powershell
.venv/Scripts/python.exe -B tools/facet_joint_search.py plan --parent output/research/2026-09-23-construction-programs --parent output/research/2026-09-23-entity-route-programs --out output/research/2026-09-23-joint-search-round1
.venv/Scripts/python.exe -B tools/facet_joint_search.py batch --out output/research/2026-09-23-joint-search-round1
.venv/Scripts/python.exe -B tools/verify_facet_program_results.py --out output/research/2026-09-23-joint-search-round1
.venv/Scripts/python.exe -B tools/facet_program_findings.py --out output/research/2026-09-23-joint-search-round1
```

The planner seals parent case files, plans and executable dependencies. The runner
checks reference scores/order, checkpoints completed cases, and keeps gold outside
retrieval. The same 72k serialized-character serving cut applies.

## Verification performed so far

Twenty-one focused tests pass across construction, structural-route projection,
scope operators, finding analysis and seed selection. Synthetic analysis verifies
that two complementary fixed rules can each have two gold hits while their
per-case oracle has four; the oracle is explicitly nondeployable. Seed selection
preserves different recruitment families and both Pareto objectives, while
removing dominated candidates and declared observational duplicates.

An integration smoke in `output/research/2026-09-23-joint-runner-smoke/` executed
two declared programs on `case_001`: the reference, and a combination of mean
query evidence, independent facets, area-first admission and Employee-union
graph relations. Independent verification checked both deliveries and seals.
This one-case smoke verifies runner plumbing only; it is not the higher-order
95-case search, and no winning policy is inferred from it.

Remaining completion work is unchanged: finish and verify the population runs,
run the higher-order comparisons, explain the observed construction effects,
surface resulting fixed rules on the page, and audit still-uncovered structural
alternatives. Source-ID results remain distinct from RAGAS and facet validity.

## Retry capture and runtime note

`tools/facet_retry5_capture.py` now implements the outstanding additive four-case
numeric capture from saved successful interpretations. It reuses the original
literal-Product scope function, passes only graph vectors to local embedding
comparison and only numeric graph fields to scoring, and keeps the four cases
separate from the sealed 95. It makes no new interpretation or judge calls.
Only syntax has been checked so far; the pinned local embedding model has not
been loaded and no numeric-capture completion is claimed.

At preparation, available physical memory was about 1.5 GB. Run this capture
after the active population jobs release sufficient memory for the pinned CPU
float32 model. The older page servers on ports 8771 and 8772 were stopped after
verifying their process identities; the combined workbench on 8773 remains the
current live page. Historical output directories and source files are intact.
