# Exact runtime optimization and preserved checkpoints

Profiling 24 existing programs on a real frozen case took 5.822 seconds;
3.568 seconds were inside NumPy's repeated row-uniqueness operation. Its very
wide structured-row handling dominated the query duplicate check, even though
there were only a few query rows. This is numerical bookkeeping, not retrieval
evidence or a construction choice.

`test/artefact/facet_construction_fast.py` is a frozen copy of the original
program engine with only that check replaced. It retains the original source
hash in its header. Finite numeric rows are compared by exact bytes after signed
zeros are normalized; first occurrences are retained in input order, matching
the original `np.unique(..., return_index=True)` followed by index sorting.
There is no rounding, tolerance, approximate grouping or evidence truncation.

The original engine and all original sealed dependencies remain unchanged.
The fast module imports the original Signal/Nomination types, preserving page
inspection and stage semantics. The fast evaluator also releases unused graph
embedding arrays and rich chunk records after making its graph-only projection;
query inputs were already captured numerically.

## Verification before switching runs

- Synthetic tests compared every intermediate signal, nomination, sponsor list,
  stage trace and full order for all 693 programs. Exact equality passed.
- Row tests covered float32/float64, signed zero, first occurrences and duplicate
  rows with 20,000 columns.
- All 693 programs on real `case_001` reproduced their saved full-order hashes,
  delivered chunks, budget boundary and metrics exactly: 31.28 seconds.
- All 224 structural-route programs on the same case reproduced those outputs
  exactly: 11.94 seconds.

The corresponding original first-case runs were about 84.61 and 47.56 seconds.
These are observed wall times under differing concurrent load, not controlled
hardware benchmark claims. Parity evidence is stored as
`fast-parity-case_001.json` in each original experiment directory.

## Current authoritative runs

The original processes were explicitly identified and stopped after parity
passed. Their terminal state and prior status were recorded in
`retired-status.json`; stale lock files are historical, not proof of live work.
Original case files, source code and plans remain intact.

- Operation run: `output/research/2026-09-23-construction-programs-fast/`.
  Imported all 21 completed original cases with SHA256 verification.
- Entity-route run: `output/research/2026-09-23-entity-route-programs-fast/`.
  Imported all 34 completed original cases with SHA256 verification.

Each new plan records the original plan hash and every imported case hash.
New cases retain reference score/order checks and the same 72k budget. An
independent checkpoint verification passed at 28 operation cases (19,404
deliveries) and 44 route cases (9,856 deliveries). These are partial populations;
use current status/verifier results for completion.

The combined workbench on port 8773 now selects the fast run directories when
present and uses the fast backend interactively. Browser verification showed
the correct resumed statuses and unchanged reference result (13/45 source IDs,
12 full chunks on `case_001`).

```powershell
.venv/Scripts/python.exe -B tools/facet_fast_resume.py batch --source output/research/2026-09-23-construction-programs --out output/research/2026-09-23-construction-programs-fast
.venv/Scripts/python.exe -B tools/facet_fast_resume.py batch --source output/research/2026-09-23-entity-route-programs --out output/research/2026-09-23-entity-route-programs-fast
```

Do not launch these again while their current processes are live. Inspect the
session/process first. For higher-order work, use the completed fast directories
as parents and `tools/facet_joint_search_fast.py` as the entry point. That wrapper
injects the verified backend into the unchanged search algorithm; it seals its
own source and the backend dependencies. It does not change the original search
script or its earlier integration-smoke evidence.

```powershell
.venv/Scripts/python.exe -B tools/facet_joint_search_fast.py plan --parent output/research/2026-09-23-construction-programs-fast --parent output/research/2026-09-23-entity-route-programs-fast --out output/research/2026-09-23-joint-search-round1
.venv/Scripts/python.exe -B tools/facet_joint_search_fast.py batch --out output/research/2026-09-23-joint-search-round1
```

This change accelerates the existing experiments. It is not a retrieval quality
improvement or additional structural coverage, and no winning rule is claimed.
