# Structural retrieval program experiment

This extends the existing frozen-input testbench. The task is to find how the
artefact components should cooperate to deliver more reference-source coverage
within 72,000 serialized characters. This experiment is underway, not a claim
that the entire requested construction investigation is finished.

## Executable construction

The engine runs a directed acyclic program of named operations, rather than a
fixed pipeline with only coefficients changed. The page compiles component
controls into this program and also permits editing its connections directly.
The explicit reach operator has a visited set and terminates at graph exhaustion.

Entry point: `tools/facet_program_lab.py`. Page: `tools/facet_program_lab.html`.
Numerical engine: `test/artefact/facet_construction_program.py`.
The reference is checked against the old operator matrix's scores and full order
for every batch case before alternative programs are evaluated.

The engine receives only `GraphInput` plus numeric query readings, scope masks
and graph-derived recovery/tie-break indices. It cannot receive the rich legacy
snapshot object. Graph chunk-description vectors are not raw chunk-body vectors.
Corpus bodies, gold labels and serialized sizes are not used to recruit or rank.
After retrieval, the evaluator applies the frozen delivery-size contract, then
joins gold pointers. See `2026-09-23-retrieval-access-boundary.md` for the actual
interface defect found and the limits of the correction (not process isolation).

## Declared mechanisms and their meanings

| Mechanism | Alternatives in the current catalog |
|---|---|
| Tag/description matching | Product, maximum, minimum, tag-only, description-only; all operate on graph-edge readings |
| Multiple tags reaching a chunk | Maximum, mean, sum across distinct graph-tag endpoints; duplicate edges cannot earn extra votes |
| Multiple query tags | Maximum, mean, minimum; exact duplicate numeric query readings count once |
| Facet combination | Retain facets through chunk/path accumulation, or combine on the same edge before accumulation |
| Graph routing | Direct only; adjacency; shared Product+Channel; both in parallel; adjacency then group; group then adjacency; shared Product |
| Parallel route combination | Maximum, sum, mean |
| Multiple graph sponsors | Maximum, mean, sum; self-sponsorship excluded |
| Propagation attenuation | Retain half or all of a sponsor's evidence per graph step |
| Direct/graph combination | Union by maximum; intersection by minimum; graph-only; exclusive positive support |
| Whole-query description | At final destination; on seed edges before propagation; independent recruitment stream; absent |
| Recruitment streams | Joint, per-facet, per-query-tag, direct/graph routes |
| Nomination | Best competition rank; independent rounds of next unseen complete score tiers; all-stream conjunction; automatic reference-compatible default |
| Scope formation | Saved original scope; union or intersection of graph regions reached from the strongest direct chunk(s) per query tag |
| Scope admission | Equal-depth area/global nominations; area then outside; area only |
| Scope/traversal ordering | Mask seeds before traversal or apply scope during nomination after traversal |
| Record recovery | On or off; explicit area-only programs constrain recovered siblings to the area |

These are hypotheses implemented by the agent, not algorithms endorsed by the
user. A graph-held description's independent recruitment stream tests a
different access route; it does not authorize a source-text search. Scope seeds
use query-to-graph edge evidence, not source text, source size or gold.

Mean over edge tags divides by distinct incident tags, including zero readings.
Mean over graph sponsors divides by all eligible distinct sponsors. These
denominators are explicit construction choices; means are not probabilities.
Union/intersection here describe support and score operators, not statistical
independence. Zero-evidence query streams abstain from scope-region combination;
all-stream nomination can instead veto access. Those are intentionally distinct.

## Coverage and continuing search

The frozen catalog contains **693 programs**: the reference, all valid single
and two-factor changes around it, six larger combined constructions, and the
exact structural context of the previous verified best. Invalid combinations
(e.g. facet recruitment after the facets have already been collapsed) fail
explicitly. Some parameter choices can produce equivalent programs; the count
is not a count of independent discoveries or distinct delivered orders.

The first population comparison is 95 cases, potentially 65,835 deliveries.
It is not a full factorial. Results must identify effective changes in access,
order and delivery, matched interactions, and case-level wins/losses.

After this population comparison, use the observed interactions to construct
and test larger combined programs, including alternatives that were poor when
changed in isolation. Preserve stage plans and distinguish new combinations
from reruns. Compare both total unique gold source hits across cases and macro
per-case recall; different objectives can select different fixed rules.

Remaining scope beyond this catalog includes broader structural-entity routes,
alternative query-to-region grounding, deeper/repeated evidence propagation
(the current closure discovers regions, not iterative score accumulation),
additional recruitment interleavings, and joint higher-order combinations.
The same frozen interpretation, facet readings, CDF and coefficients remain
controls; retrieval improvement does not validate those facet measurements.
Four recovered interpretations still require additive numeric capture, with
one interpretation still failed. None is silently included in the 95 cases.

## Inspect and reproduce

From the repository root:

```powershell
.venv/Scripts/python.exe -B -X utf8 tools/facet_program_lab.py batch
.venv/Scripts/python.exe -B -X utf8 tools/facet_program_lab.py serve --port 8772
.venv/Scripts/python.exe -B tools/verify_facet_program_results.py
```

Page: `http://127.0.0.1:8772`. Output directory:
`output/research/2026-09-23-construction-programs/`.
The page shows reference/new coverage, stage dependencies and gold-linked
access, chunk position changes, independent-stream sponsors, recovery depth,
source pointer credit and the partial budget boundary. Completed fixed-program
population results can be ranked by total gold hits or macro recall.
The historical query-reducer page and sealed results remain separate and intact.

Batch checkpoints commit only completed cases and resume without recomputing
them. Source and input hashes are sealed in `plan.json`; do not edit these
dependencies during a run. A live `writer.lock` is not by itself process proof:
verify its PID/session before treating the run as active or stopped. The verifier
can inspect committed checkpoints while a batch continues. It independently
recomputes source metrics and boundary accounting, but does not reconstruct the
entire ranking (explicit in its output).

## Evidence obtained before population completion

- Fourteen synthetic checks pass, including known witnesses for noncommuting
  traversal order, facet combination before/after edge accumulation, scope
  before traversal, independent nomination versus best-rank merge, exclusive
  support, duplicate controls, cycles, immutable graph inputs and reference parity.
- First case: all 693 programs finished. Reference source/order parity passed.
- The actual browser rendered the reference result and changing query reduction
  to mean reproduced 13/45 to 17/45 credited source IDs at 72,000 characters,
  with 12 fully delivered chunks and a 5,034/6,441-character partial boundary.
- Independent verification of the first two cases covered 1,386 deliveries,
  all sealed hashes and full-versus-partial source credit. This is checkpoint
  evidence only; use the current verifier output for later completion status.

Highest-scoring fixed configurations will still be evaluation-selected on
reused cases. Per-case gold-selected winners, if computed, are oracle diagnostics
and cannot be deployed as a selector. These are source-ID retrieval metrics;
no answer generator or RAGAS judge has been called for this experiment.
