# Does stable-ID tie ordering determine the 72k delivery boundary?

The engine orders nominations by depth, then whether recovery changed that depth,
then stable chunk ID. `tools/facet_nomination_audit.py` reran three fixed programs
on all 95 original cases and checked the exact tier containing the last full
chunk and next candidate. No gold was used to identify ties. The resolver applied
serialized character sizes after retrieval; sizes were not retrieval inputs.

| Fixed construction | Cases with a tie split at the full-chunk boundary | Largest split tier |
| --- | ---: | ---: |
| Original reference `program_000` | 39/95 | 3 chunks |
| Operation leader `program_692` | 0/95 | 0 |
| Entity-route hit leader `route_179` | 0/95 | 0 |

Evidence: `output/research/2026-09-23-nomination-audit/results.json`, including
case-level numerical diagnostics. This is a boundary diagnostic, not a gold-hit
comparison or proof that other ranking policies are optimal. It does not test
replacing nomination depth, reordering whole tiers, or internal delivered order.
It shows that stable-ID tie breaking at the cut is not currently limiting the
two completed-population hit leaders. In the reference, evidence-sensitive tie
breaking could change which small tied set fits. Audit newly selected independent
recruitment leaders after the active runs finish before retaining this conclusion
for those constructions.
