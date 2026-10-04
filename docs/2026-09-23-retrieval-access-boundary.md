# Retrieval access correction

User correction, 2026-09-23:

> the "corpus" is obviously not to be shown to the artefact/retriever like that, remember the fucking concepts and limits of this whole thing..

## Observed issue

The frozen joint arm's `Prepared.chunks` contains `source_text` copied into the
research snapshot. Its loader requires that field despite describing itself as
loading graph data only. The new program experiment initially passed that rich
object to the retrieval core. The arithmetic inspected did not read those
bodies, but the input interface exposed them. That is an actual boundary defect,
not evidence of source-text scoring or evidence that historical metrics changed.

The live Volmax Chunk properties inspected this session contain locators and
description embeddings, not source bodies. Graph-held description embeddings
are distinct from embeddings of raw chunk contents. `_resolve_chunk` is the
separate source recovery step used for delivery.

## Contained correction

`test/artefact/facet_graph_input.py` now supplies an immutable value-only graph
input: opaque chunk IDs, edge endpoints and facet readings, relation groups,
adjacency and product memberships. It retains no rich chunk records, source
locators, resolver, corpus root, gold, costs, or reference object callbacks.
`run_program` rejects anything other than this exact input type before reading
its fields. Query similarities remain numerical readings supplied separately.

The evaluation-side adapter constructs this projection. The evaluation process
still loads the legacy snapshot and gold separately; this is an explicit
function-input boundary, **not process isolation**. The old arm, sealed prior
experiments and snapshots have not been rewritten or promoted by this change.

## Verification and unfinished work

- Ten synthetic tests pass, including rejection of a rich object before any
  field access, immutable inputs, reference parity, and nonempty product paths.
- One frozen case (`case_001`) passes reference score and full-order parity:
  maximum expected-score difference 1.3877787807814457e-17; 4,808 graph IDs,
  4,807 ranked IDs. No new gold evaluation or judge call was used for this check.
- The broader program catalog has not been run on the evaluation population.
  The proposed global description stream, seed-derived scope and relation
  compositions are draft hypotheses. Their presence in executable code is not
  evidence that they respect the intended retrieval construction.
- Continue checking graph entry, grounding and scope formation against the
  concept, then systematically exercise the allowed structural alternatives.
  This correction neither finishes nor narrows that original objective.

Source bodies are recovered after selection for delivery; gold pointers join
outside retrieval for inspection. Neither becomes a recruitment or ranking
input. Existing evidence is preserved with these limitations stated explicitly.
