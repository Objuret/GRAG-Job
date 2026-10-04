# Recruitment feeding traversal

Prior programs changed recruitment at final nomination, after computing graph
evidence. That does not test whether recruitment itself should determine which
facet evidence is allowed to enter traversal. This comparison exposes that
previously fixed dependency.

Both verified two-/four-step leaders are retained. Their query evidence is already
combined before the walk. Independent facet streams recruit complete score tiers
using the same pre-round visited set. Every supported chunk can eventually be
recruited: there is no arbitrary top-k frontier or candidate limit. The resulting
first-admission sponsors and priority then feed traversal in three ways:

- Original scores from the first-recruiting facets only.
- Inverse admission depth from those first-recruiting facets only.
- Inverse admission depth from every positively supporting facet, allowing facets
  that did not recruit the chunk first to contribute onward evidence.

These signals can replace only the graph-walk input or both direct and graph
inputs. Final nomination can use best rank or independent batches. Thus the
experiment also tests whether early recruitment followed by shared final ranking
differs from independent recruitment at both stages. It is a batch formulation
of recruitment-to-traversal feedback, not a networked asynchronous implementation
or a test of recruiting raw graph tags before chunk-edge aggregation.

The evaluator extension adds one explicit `nomination_evidence` operation in a
new file, preserving both old engines and all sealed runs. Its input boundary
still requires `GraphInput`; no corpus records, gold, delivery costs or source
resolver are passed to the operation. Gold pointers attach to stages afterward.

Three focused tests verify first sponsors versus other supporters, early-stage
placement, and exact unchanged intermediate arrays/rankings for all 693 earlier
programs on the test graph. The real-data one-case smoke independently verified
all 27 deliveries. Both unchanged leader programs also reproduce the original
engine's full-order hashes and delivery on that case.

The full run is active at `output/research/2026-09-24-recruitment-programs/`,
using `tools/facet_recruitment_lab.py`. The live page recognizes the new operation
and labels its recruitment-feedback choices explicitly. Its performance is not
established until the complete population verifies.
