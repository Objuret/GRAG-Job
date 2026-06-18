"""lucene.py — sparse baseline (BM25 / Lucene).

Why it's here: the sparse-retrieval control arm.
Why this one is relevant: classic keyword retrieval — the floor any dense or
structured method must beat. Builds its OWN index over the corpus and shares
NOTHING with the artefact. Implements contract.PipelineInterface. No logic.
"""


def build_sparse_index(corpus):
    # prepare(): build an own BM25 index over corpus artifacts. runs once.
    # independent of the artefact — own units, own index.
    # linked to: orchestrator.run_one_pipeline (called once)
    ...


def retrieve_top_k_units(prompt, prepared, k):
    # sparse top-k retrieval for the question text.
    # linked to: unit_to_artifact_id + gather_unit_text (consume the hits)
    ...


def unit_to_artifact_id(unit):
    # read the native artifact id off the raw record the unit came from.
    # fills PipelineOutput.retrieved_ids (same id space the artefact resolves to)
    ...


def gather_unit_text(units):
    # collect the units' text. fills PipelineOutput.retrieved_contexts + generator
    ...


def answer_one_question(prompt, prepared, generate):
    # ENTRY: retrieve_top_k -> ids + text -> generate -> PipelineOutput.
    # linked to: orchestrator; shared `generate`; returns contract.PipelineOutput
    ...
