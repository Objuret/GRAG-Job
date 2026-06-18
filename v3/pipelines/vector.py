"""vector.py — dense baseline (embeddings + cosine), i.e. naive RAG.

Why it's here: the dense-retrieval control arm.
Why this one is relevant: standard vector RAG — the main thing the artefact's
structured retrieval is claimed to beat. Builds its OWN embedding index over the
corpus and shares NOTHING with the artefact.
Implements contract.PipelineInterface. No logic.
"""


def build_dense_index(corpus):
    # prepare(): embed corpus units + build a vector index. runs once.
    # independent of the artefact. linked to: orchestrator.run_one_pipeline (once)
    ...


def retrieve_top_k_units(prompt, prepared, k):
    # embed the question, cosine top-k.
    # linked to: unit_to_artifact_id + gather_unit_text (consume the hits)
    ...


def unit_to_artifact_id(unit):
    # native artifact id off the raw record. fills PipelineOutput.retrieved_ids
    ...


def gather_unit_text(units):
    # collect text. fills PipelineOutput.retrieved_contexts + generator
    ...


def answer_one_question(prompt, prepared, generate):
    # ENTRY: retrieve -> ids + text -> generate -> PipelineOutput.
    # linked to: orchestrator; shared `generate`; returns contract.PipelineOutput
    ...
