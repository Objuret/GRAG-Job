# Four recovered interpretations: numeric capture completed

The previously unfinished capture is now complete for `case_096`, `case_097`,
`case_098` and `case_100`. The successful saved interpretations were used as-is;
no new interpretation or judge calls were made. The pinned local CPU float32
embedding recipe was used. Questions, generated descriptions and tags remained
private and were not displayed during this work.

Output: `output/research/2026-09-22-retrieval-retry5/numeric_inputs/`.
All four NPZ hashes, metadata and capture dependencies are checked by the loader.
Query rows are respectively 5, 4, 8 and 4; graph tag/chunk dimensions are 16,669
and 4,808. Each query row has five facet readings. The original literal-Product
scope function was reused from its preserved source, maintaining comparability
with the saved 95-case inputs. Reference scores for the new cases are recomputed
reference-configuration scores, not historical successful retrieval outputs.

The original 95-case manifest and its inputs are unchanged. The additive
`combined99_manifest.json` records both source-manifest hashes and all 99 case
file hashes. It does not silently replace a 95-case benchmark with a 99-case one.

## Remaining failed interpretation

`case_099_failure_diagnostic.json` records a content-free diagnosis of the fifth
saved attempt: the model returned a response with `finish_reason=stop`, but the
extractor found no JSON object. The saved exception is a ValueError. The response
content was not inspected or exported, and the original failure is preserved.
No new retry or invented interpretation was substituted.

There are therefore **99 replayable cases out of the original 100**, with one
explicit interpretation failure. Do not call this a successful 100-case run.

## Separate recovered-case retrieval check

`tools/facet_recovered_lab.py benchmark` evaluated four configurations selected
before looking at these results: the reference, the two completed 95-case route
leaders, and the previous construction leader. All four cases passed reference
score/full-order parity. Independent verification checked all 16 deliveries,
input hashes, source-ID metrics and the 72k full/partial boundary accounting.

| Fixed configuration | Gold-source hits / 153 | Mean per-case recall |
|---|---:|---:|
| Reference | 34 | 24.1582% |
| Sequential Employee-intersection route (`route_179`) | 47 | 38.7415% |
| Parallel Employee-intersection route (`route_163`) | 59 | 51.8367% |
| Previous maximum-match / mean-query / group-intersection leader | 52 | 43.6735% |

Output: `output/research/2026-09-23-recovered4-retrieval/`. This is a four-case
additional check, not an independently sampled validation population, a new
95-case ranking, or a RAGAS evaluation. In particular, it does not justify
selecting a different configuration for each recovered case using gold.

The combined workbench on port 8773 now loads `RecoveredLab` and exposes these
four cases with a recovered label. The 95-case population run denominators stay
explicitly 95. Queries remain opaque case IDs on the page; gold pointers join
after retrieval and delivery.

```powershell
.venv/Scripts/python.exe -B tools/facet_retry5_capture.py
.venv/Scripts/python.exe -B tools/facet_recovered_lab.py index
.venv/Scripts/python.exe -B tools/facet_recovered_lab.py benchmark
.venv/Scripts/python.exe -B tools/verify_facet_program_results.py --out output/research/2026-09-23-recovered4-retrieval
```

The capture is resumable and refuses changed inputs. No need to reload the
embedding model for already completed numeric cases. The capture plan remains
separate from the construction-selection plans.
