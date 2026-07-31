"""prompt_tokens.py — exact token counts for the shared generator prompt.

Counts the same strings the harness sends: chat-templated messages via the Qwen
tokenizer (lazy-loaded once). No byte ratios."""
from __future__ import annotations

from contract import GENERATOR_SYSTEM, generator_messages, generator_output_text

_TOKENIZER = None
_TOKENIZER_ID = "Qwen/Qwen3-8B"


def _tokenizer():
    global _TOKENIZER
    if _TOKENIZER is None:
        from transformers import AutoTokenizer
        _TOKENIZER = AutoTokenizer.from_pretrained(_TOKENIZER_ID, trust_remote_code=True)
    return _TOKENIZER


def count_generator_tokens_in(question: str, contexts: list[str]) -> int:
    """Token count for the exact system + user messages the generator sends."""
    tok = _tokenizer()
    text = tok.apply_chat_template(
        generator_messages(question, contexts),
        tokenize=False,
        add_generation_prompt=True,
    )
    return len(tok.encode(text, add_special_tokens=False))


def count_generator_tokens_out(answer: str) -> int:
    """Token count for the structured JSON completion the generator returns."""
    tok = _tokenizer()
    return len(tok.encode(generator_output_text(answer), add_special_tokens=False))


def compute_generator_usage(question: str, contexts: list[str], answer: str) -> tuple[int, int]:
    """Exact tokens_in / tokens_out from the stored prompt and answer strings."""
    return count_generator_tokens_in(question, contexts), count_generator_tokens_out(answer)
