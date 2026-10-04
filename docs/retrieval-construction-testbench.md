# Run and inspect the structural retrieval testbench

Run from `C:\Coding\exjobbet\GRAG-Job` using the existing `.venv`. All commands
below use frozen numeric query inputs and graph projections. No new model calls,
source-text search, gold-guided runtime selection or graph writes are needed.
The evaluation adapter resolves chunk pointers and joins gold after retrieval.

## Live page

```powershell
.venv/Scripts/python.exe -B tools/facet_combined_workbench.py --port 8773
```

Open `http://127.0.0.1:8773`. Reuse the existing server if that port is already
serving this page. Choose a case and construction, then compare. Pin a displayed
construction to compare any matched pair. The operation graph editor accepts
explicit node connections. Completed leaderboard entries load their full programs,
including custom ordering and scope policies, rather than recreating only their
basic factor settings. Population progress refreshes while the page is visible.
The experimental-construction picker also loads sealed programs from comparisons
that are still running. Case replay is available before population metrics are
complete. Compare/pin/clear retain the loaded operation graph; changing a factor
explicitly recompiles that graph.

The interaction section loads verified pairs where one structural change helps
or hurts under two settings of another component. Its deltas concern the 95-case
population; replay metrics concern only the currently selected case.

Original 95 cases and recovered four cases are labelled separately. The newer
structural scope captures cover the original 95 only. The unrecovered interpreter
failure is not fabricated into a valid question case.

## Current population runs

| Experiment | Runner | Output directory below `output/research/` |
| --- | --- | --- |
| Combined choices | `tools/facet_joint_search_fast.py` | `2026-09-23-joint-search-round1` |
| Reduction, gating, repeated traversal | `tools/facet_ordering_lab_v2.py` | `2026-09-23-ordering-programs-v2` |
| Graph-grounded scope through delivery | `tools/facet_scope_program_lab.py` | `2026-09-23-scope-programs` |
| Traversal-depth boundary | `tools/facet_depth_followup.py` | `2026-09-24-depth-programs` |
| Ordering, graph and scope integration | `tools/facet_integrated_followup.py` | `2026-09-24-integrated-programs` |
| Recruitment feeding traversal | `tools/facet_recruitment_lab.py` | `2026-09-24-recruitment-programs` |
| Matching crossed with ordering | `tools/facet_joint_search_fast.py` | `2026-09-24-matching-order-bridge` |
| Within-batch evidence ordering | `tools/facet_tie_programs.py` | `2026-09-24-tie-programs` |
| Graph-tag evidence before chunk aggregation | `tools/facet_tag_frontier_lab.py` | `2026-09-24-tag-frontier-programs` |
| Directional management relationships | `tools/facet_directed_lab.py` | `2026-09-24-directed-programs` |
| Tag batch arrival and sponsorship controls | `tools/facet_tag_frontier_followup.py` | `2026-09-24-tag-frontier-followup` |
| Per-query multikey facet priority | `tools/facet_query_priority_lab.py` | `2026-09-24-query-priority` |
| Tag-frontier and directional-route integration | `tools/facet_directed_frontier_lab.py` | `2026-09-24-directed-frontier-programs` |
| Query-priority and directional-route integration | `tools/facet_query_priority_directed.py` | `2026-09-24-query-priority-directed` |
| Exact-record recovery placement and assembly | `tools/facet_record_assembly_lab.py` | `2026-09-24-record-assembly-programs` |
| Record recovery in a graph context reaching fragments | `tools/facet_record_product_lab.py` | `2026-09-24-record-product-programs` |

Each runner uses `batch --out <output-directory>`. A sealed `plan.json` already
exists in each directory. Do not create a duplicate writer or restart a process
just because status has not changed. Confirm the actual running process/session
first. Checkpoints are written per complete case. Resume uses existing completed
cases and checks sealed hashes. A stale writer lock requires confirming its
recorded process has exited before removing that exact lock; never remove one
belonging to a live process. Do not edit sealed dependencies during a run.

## Verify and analyze completed results

Replace `<output-directory>` with one of the full paths above:

```powershell
.venv/Scripts/python.exe -B tools/verify_facet_program_results.py --out <output-directory>
.venv/Scripts/python.exe -B tools/facet_structural_findings.py --out <output-directory>
```

The verifier checks original inputs, delivered full chunks, source-ID credit,
metrics and character-boundary accounting. It explicitly does not recompute all
full orders. Engine/reference parity is separate evidence. Running this on an
incomplete directory produces checkpoint evidence, not population completion.

The structural analyzer includes custom ordering and scope dimensions in matched
effects. The older `facet_program_findings.py` is appropriate for its original
factor-only catalogs, but must not be used to attribute effects in custom-ordering
or custom-scope catalogs because it omits those dimensions.

Select a fixed rule only after the intended population completes and verifies.
Development gold may select the fixed configuration; it must not choose a different
configuration for each runtime question. Preserve gold-selected per-case maxima
as diagnostics, not deployable policies. Source-ID metrics are not RAGAS.

## Evidence map

- `docs/2026-09-24-selection-audit.md`: current fixed selection, exact replay,
  separate recovered-case results, tie sensitivity and remaining structural gaps.

- `docs/2026-09-23-construction-population-results.md`: completed operation comparison.
- `docs/2026-09-23-structural-route-comparison.md`: completed shared-entity route comparison.
- `docs/2026-09-23-structural-interactions.md`: matched four-corner findings.
- `docs/2026-09-23-reduction-traversal-ordering.md`: ordering experiment and preserved failed first packaging attempt.
- `docs/2026-09-23-structural-scope-delivery.md`: scope experiment.
- `docs/2026-09-23-retrieval-access-boundary.md`: graph-only retrieval boundary.
- `docs/state/2026-09-23-retrieval-construction.md`: full historical state and continuation links.

All listed populations and their final cross-comparison are complete. The final
selection is `output/research/2026-09-24-structural-selection-v3/`; fresh selected
replay is preserved in v2 and hash-linked from v3. The consolidated findings are
in `docs/2026-09-24-structural-outcome.md`. A settings count alone is not evidence
that the requested component relationships have been explored adequately.
