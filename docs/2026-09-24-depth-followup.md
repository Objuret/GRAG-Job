# Follow-up on the traversal-depth boundary

The completed ordering comparison's total-hit leader used four steps, the largest
tested depth. Treating that as an optimal stopping point would be unsupported.
This follow-up retains the completed population's Pareto frontier on total hits
and macro recall: `ordering_0016` and `ordering_0273`.

Both fixed constructions are tested at depths 1, 2, 3, 4, 5, 6, 7, 8, 12, 15,
16, 24, 31 and 32, with latest-step-only feedback and with seed reinsertion.
The duplicate reinsertion setting at one step is omitted. Including the canonical
reference gives 55 programs on the same 95 cases. Odd lengths are explicit so
the experiment does not silently retain an even-walk assumption on graphs that
permit revisits. This remains a finite-depth comparison, not a convergence claim.

`tools/facet_depth_followup.py` builds ordinary operation graphs for the unchanged
engine. The extension reproduces original 1-, 2- and 4-step graphs numerically in
focused tests, including reinsertion. Longer and odd walks remain finite and
inside the page's existing 100-operation editing limit. No candidate count or
tag-pool cutoff is introduced.

The one-case smoke independently verified all 55 deliveries and seals. The full
run is active in `output/research/2026-09-24-depth-programs/`, and the live page
tracks it. Plans seal the completed parent's plans, reports and all case outputs.
Parent selection uses evaluation gold; the resulting fixed programs run without
gold inputs. Whole-query and per-query description scores remain numeric graph
inputs, with no corpus-body access added.

After completion, verify and analyze before selecting a depth. Check whether
deeper settings plateau, lose quality, alternate, or still win at the tested
boundary; report the actual evidence rather than calling a boundary an optimum.
