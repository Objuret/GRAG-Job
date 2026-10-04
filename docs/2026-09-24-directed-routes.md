# Directed employee routes in the retrieval construction

The fresh read-only Volmax capture contains 512 `Employee-[:manages]->Employee`
edges across a 530-employee inventory. The eligible 4,808 chunks and the employee
bindings match the pinned structural snapshot exactly: 30,309 employee/channel
chunk memberships and 184,286 employee/product chunk memberships. The capture
contains only opaque IDs and graph memberships; no source bodies, questions,
answers, names, or gold were passed into the route operator.

The tested path is `chunk -> Employee -> manages -> Employee -> chunk`.
Its usefulness is a relationship hypothesis, not a claim that management
direction determines semantic relevance. Channel bindings use Employee/slack/
Channel/chunk; product bindings use Employee/meeting_transcripts-or-documents/
Product/chunk. Both endpoint bindings use the same relation family in each run.

`forward` carries evidence from the manager's bound chunks to the report's
bound chunks; `reverse` reverses that relation; `symmetric` is their union.
Multiple employee paths or duplicate edges for the same source/target chunk pair
are one chunk sponsor. Same-chunk offers are excluded. Isolated destinations get
zero directed evidence. Finite repeated walks may revisit cycles, with the same
0.5 decay and destination gate as the selected parent; this is not an unbounded
or converged diffusion claim.

The projection has 426,663 directed channel chunk pairs (554,908 symmetric)
and 3,218,388 directed product chunk pairs (3,545,574 symmetric). Forward channel
routes have 2,345 source and 2,620 target chunks; reversing swaps those counts.
Product routes reach all 4,808 chunks on both sides. Every projection has zero
self pairs. These are graph inventories, not gold coverage measurements.

The 51-program matched comparison retains the reference and both fixed selected
parents. For each parent it crosses two bindings, three directions and three
placements: replace each graph-walk step, insert before the first graph walk,
or combine directed and original evidence with maximum before the first walk.
Additional channel/replace controls compare mean and sum with maximum chunk
sponsors in all three directions. Facet/query axes and the parent's destination
gate stay explicit. The new `directed_propagate` stage is part of the operation
graph before nomination; it is not a final-ranking adjustment.

Numeric tests cover asymmetric directions, reversal, cycles, duplicate paths,
isolated chunks, self exclusion, sponsor aggregation, destination gating and
placement before nomination. The one-case 51-program smoke independently
verifies delivery accounting and reproduces both unchanged parents' complete
order hashes and deliveries exactly.

Run/replay commands from the repository root:

```powershell
.venv/Scripts/python.exe -B tools/facet_directed_lab.py plan --out output/research/2026-09-24-directed-programs
.venv/Scripts/python.exe -B tools/facet_directed_lab.py batch --out output/research/2026-09-24-directed-programs
.venv/Scripts/python.exe -B tools/verify_facet_program_results.py --out output/research/2026-09-24-directed-programs
.venv/Scripts/python.exe -B -m pytest test/tests/test_facet_directed_values.py -q
```

The plan command refuses to overwrite the existing sealed plan; use the batch
command to resume it. All metrics are source-ID retrieval credit under the 72,000
character serving budget, not RAGAS or held-out validation.

The population completed: 95 cases, 51 programs, 4,845 independently verified
deliveries. All 190 unchanged-parent case comparisons reproduced the original
complete order hashes, deliveries, budgets and metrics exactly. See
`output/research/2026-09-24-directed-programs/directed-audit.json`.

The strongest fixed rule in this population is `directed_0034`: **1,951 gold
source hits**, macro recall **0.5290313523608015**. It adds a symmetric channel-bound
management-route propagation before the existing two-step joint parent. This
improves that parent's 1,939 hits by 12 (11 case wins, 11 losses, 73 ties) and
the previous 1,945-hit leader by six. Its macro recall remains below the unchanged
macro leader, 0.5323292735421256. Selection remains a development comparison;
fresh final-rule replay and boundary auditing are still required by the parent
workflow.

For the same two-step parent, channel binding and before-walk placement:

| Direction | Hits | Macro source-ID recall |
| --- | ---: | ---: |
| Manager to report | 1,950 | 0.5278784701552878 |
| Report to manager | 1,814 | 0.48795788672796014 |
| Symmetric union | 1,951 | 0.5290313523608015 |

Direction therefore changes outcomes materially in this matched context, but
the strongest rule is the symmetric control. It would be incorrect to attribute
the improvement simply to making the graph directed. Placement also matters:
using that same symmetric route to replace the two graph steps produces 1,731
hits; joining it with the seed before the walk produces 1,939, unchanged from the
parent. Inserting it before the original walk produces the 1,951 result.

One Windows status-file replacement failure occurred after 85 completed case
files. The original failure/status record is preserved in
`resume-after-status-error.json`. The same sealed plan and runner resumed without
changing retrieval or discarding completed cases. The final independent verifier
checked every delivery and all sealed input hashes.
