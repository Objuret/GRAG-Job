"""orchestrator.py — wires ONE pipeline + ONE evaluator over the chosen
questions and saves the result.

Why it's here: the run entry point. Also the home of the SHARED generator, so
every arm answers with the identical model (the fairness control). It routes
corpus -> pipeline and truth -> evaluator. No logic.
"""


def load_chosen_questions(ids_file, raw_root):
    # read the chosen ids, hydrate each into QuestionWithTruth from raw
    #   (text, type, ground_truth, citations). reads the oracle in place.
    # linked to: contract.QuestionWithTruth
    ...


def open_corpus(corpus_root):
    # handle onto the RAG-safe corpus — the only data a pipeline sees.
    # linked to: pipeline.prepare_over_corpus
    ...


def build_shared_generator(config):
    # build the ONE generator (model + params) injected into every arm.
    # linked to: every arm's answer_one_question (the `generate` argument)
    ...


def to_prompt(question):
    # project QuestionWithTruth -> PromptForPipeline (strip the truth).
    # the structural quarantine, in code. linked to: pipeline calls
    ...


def run_one_pipeline(pipeline, questions, corpus, generate):
    # prepare the arm once, then loop: to_prompt -> answer_one_question.
    # -> list[PipelineOutput].
    # linked to: pipeline.prepare_over_corpus + pipeline.answer_one_question
    ...


def run_one_evaluator(evaluator, outputs, questions):
    # -> Report. linked to: evaluator.score_outputs
    ...


def save_run(outputs, report, manifest, out_dir):
    # persist outputs + report + manifest under output/. nothing dropped.
    # linked to: output/ ; contract.RunManifest
    ...


def build_manifest(config):
    # capture provenance (models, top_k, seed, git sha). -> contract.RunManifest
    ...


def run(pipeline, evaluator, ids_file, config):
    # TOP ENTRY: load_chosen_questions -> open_corpus -> build_shared_generator
    #   -> run_one_pipeline -> run_one_evaluator -> save_run.
    # linked to: all of the above; smoke.run_smoke calls a trimmed version
    ...
