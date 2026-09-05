from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    judge: bool
    embed: bool
    needs: str
    direction: str
    applies: bool
    note: str = ""


CATALOG = {
    "context_precision_id":     Metric(False, False, "citation_ids",      "higher", True,  "retrieved ids ∩ gold citation ids / retrieved (IDBasedContextPrecision)"),
    "context_recall_id":        Metric(False, False, "citation_ids",      "higher", True,  "gold citation ids found among retrieved (IDBasedContextRecall)"),
    "context_precision_nonllm": Metric(False, False, "gold_context_text", "higher", True,  "string-sim of retrieved vs gold context text (NonLLMContextPrecisionWithReference)"),
    "context_recall_nonllm":    Metric(False, False, "gold_context_text", "higher", True,  "string-sim recall of gold context text (NonLLMContextRecall)"),
    "context_precision_llm":    Metric(True,  False, "none",              "higher", True,  "judge rates each chunk vs the answer (LLMContextPrecisionWithoutReference)"),
    "context_precision_llm_ref":Metric(True,  False, "gold_answer",       "higher", True,  "judge rates each chunk vs gold answer (LLMContextPrecisionWithReference)"),
    "context_recall_llm":       Metric(True,  False, "gold_answer",       "higher", True,  "gold-answer claims supported by contexts (LLMContextRecall)"),
    "context_entity_recall":    Metric(True,  False, "gold_answer",       "higher", True,  "gold entities present in retrieved contexts"),
    "context_relevance_nv":     Metric(True,  False, "none",              "higher", True,  "Nvidia: are contexts pertinent to the question"),
    "noise_sensitivity":        Metric(True,  False, "gold_answer",       "lower",  True,  "how often junk context drives wrong claims"),

    "faithfulness":             Metric(True,  False, "none",              "higher", True,  "answer claims grounded in the contexts"),
    "faithfulness_hhem":        Metric(True,  False, "none",              "higher", True,  "LLM decomposes the answer into statements; the Vectara HHEM-2.1 classifier verifies each against the contexts (needs the HHEM model installed)"),
    "answer_relevancy":         Metric(True,  True,  "none",              "higher", True,  "answer addresses the question (judge generates probe Qs, embeddings score them)"),
    "response_groundedness_nv": Metric(True,  False, "none",              "higher", True,  "Nvidia: answer supported by the contexts"),
    "answer_accuracy_nv":       Metric(True,  False, "gold_answer",       "higher", True,  "Nvidia: answer agrees with gold answer"),
    "factual_correctness":      Metric(True,  False, "gold_answer",       "higher", True,  "claim-overlap of answer vs gold via NLI"),
    "answer_correctness":       Metric(True,  True,  "gold_answer",       "higher", True,  "RAGAS AnswerCorrectness: factual (claim F1) + semantic similarity of answer vs gold"),
    "semantic_similarity":      Metric(False, True,  "gold_answer",       "higher", True,  "cosine(answer, gold) embeddings"),
    "string_similarity":        Metric(False, False, "gold_answer",       "higher", True,  "Levenshtein/Jaro vs gold (NonLLMStringSimilarity)"),
    "bleu":                     Metric(False, False, "gold_answer",       "higher", True,  "n-gram precision vs gold (weak for QA)"),
    "rouge":                    Metric(False, False, "gold_answer",       "higher", True,  "n-gram overlap vs gold (weak for QA)"),
    "chrf":                     Metric(False, False, "gold_answer",       "higher", True,  "character n-gram F-score vs gold"),
    "exact_match":              Metric(False, False, "gold_answer",       "higher", True,  "answer == gold, word-for-word"),
    "string_presence":          Metric(False, False, "gold_answer",       "higher", True,  "answer contains gold"),

    "aspect_critic":            Metric(True,  False, "criterion",         "higher", True,  "binary: does the answer meet an aspect you define"),
    "simple_criteria":          Metric(True,  False, "criterion",         "higher", True,  "your discrete scale against a criterion you define"),
    "rubrics_score":            Metric(True,  False, "gold_answer",       "higher", True,  "score per a rubric you write (also needs gold)"),
    "instance_rubrics":         Metric(True,  False, "gold_answer",       "higher", True,  "per-item rubric you write (also needs gold)"),

    "multimodal_faithfulness":  Metric(True,  False, "images",            "higher", False, "needs visual context — HERB is text"),
    "multimodal_relevance":     Metric(True,  False, "images",            "higher", False, "needs visual context — HERB is text"),
    "topic_adherence":          Metric(True,  False, "reference_topics",  "higher", False, "agent topic-staying — needs reference topics"),
    "tool_call_accuracy":       Metric(False, False, "reference_tool_calls", "higher", False, "agent tool-use — needs reference tool calls"),
    "tool_call_f1":             Metric(False, False, "reference_tool_calls", "higher", False, "agent tool-use — needs reference tool calls"),
    "agent_goal_accuracy":      Metric(True,  False, "agent_trajectory",  "higher", False, "multi-turn agent goal — not a QA task"),
    "datacompy_sql":            Metric(False, False, "sql+db",            "higher", False, "executes SQL and diffs tables — no DB here"),
    "sql_semantic_equivalence": Metric(True,  False, "sql+db",            "higher", False, "judges SQL equivalence — no SQL here"),
    "summarization_score":      Metric(True,  False, "reference_contexts","higher", False, "summary-quality task, not QA scoring"),
}


SELECTED = [
    "context_precision_id",
    "context_recall_id",
    "context_precision_nonllm",
    "context_recall_nonllm",
    "semantic_similarity",
    "string_similarity",
    "bleu",
    "rouge",
    "chrf",
    "exact_match",
    "string_presence",
    "faithfulness",
    "answer_correctness",
    "context_recall_llm",
]


def metrics_to_run():
    return list(SELECTED)


def _check():
    unknown = [m for m in SELECTED if m not in CATALOG]
    assert not unknown, f"SELECTED names not in CATALOG: {unknown}"
    wrong_task = [m for m in SELECTED if not CATALOG[m].applies]
    assert not wrong_task, f"SELECTED metrics HERB can't feed: {wrong_task}"
    dupes = sorted({m for m in SELECTED if SELECTED.count(m) > 1})
    assert not dupes, f"SELECTED has duplicates: {dupes}"
    judged = sum(1 for m in SELECTED if CATALOG[m].judge)
    print(f"ragas_catalog OK — {len(CATALOG)} in menu; {len(SELECTED)} selected "
          f"({judged} judged, {len(SELECTED) - judged} free)")


if __name__ == "__main__":
    _check()
