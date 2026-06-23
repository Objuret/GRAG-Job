"""artifact.py — the ARTEFACT arm: the v2 graph (interpreter -> facet-channel
retrieval -> answer).

Why it's here: this is the system under test — the whole point of the comparison.
Why this one is relevant: it's the thesis contribution; the baselines exist only
to measure it against. Depends on the v2-built graph (NOT yet built).

Contract fit (mirrors lucene): prepare returns a Prepared carrying a
contract.BuildStats; answer_one_question returns a contract.ArmOutput. No logic.
"""


def connect_to_artefact_graph(corpus):
    # prepare(): attach to the built v2 graph over this corpus. runs once.
    # linked to: orchestrator.run_one_pipeline (called once before the loop)
    ...


def interpret_prompt_per_facet(question):
    # decompose the question into per-facet query content (topic/stance/...).
    # linked to: retrieve_chunks_by_facets (feeds it the decomposition)
    ...


def retrieve_chunks_by_facets(facets, prepared):
    # same-facet matching -> scored chunks (the artefact's core retrieval).
    # linked to: interpret_prompt_per_facet (input);
    #            resolve_chunk_artifact_ids + gather_chunk_text (consume output)
    ...


def resolve_chunk_artifact_ids(chunks):
    # dereference chunk references -> source artifact ids (msg/doc ids).
    # fills ArmOutput.context_ids (used by RAGAS citation-based ctx metrics)
    ...


def gather_chunk_text(chunks):
    # pull the evidence text via the chunks' references.
    # fills ArmOutput.contexts + feeds the generator
    ...


def answer_one_question(question, prepared, generate, k):
    # ENTRY: interpret -> retrieve -> resolve ids + gather text ->
    #   generate(answer from text) -> contract.ArmOutput.
    # linked to: orchestrator; shared `generate`; returns contract.ArmOutput
    ...
