"""The querytagger: the query side of the tagger, reading the question and nothing else.

His names, 2026-09-14: the *tagger* is the 05-14 pilot that wrote the chunk descriptions and
tags; the query side is the **querytagger**. Confirmed by him the same day, *"Seems fine."*:
it reads the question and nothing else and produces (1) a description of the content of the
chunk that would answer this, its type and subject, in the tagger's register, not the question
restated, not a need statement, no invented facts; (2) tags — semantic phrases, what the
answering content is about, in the tagger's language, no names of people, products or channels
(those are structure); (3) no scope — *"i think this is impossible without overfitting and
perhaps we use logic instead using the actual graphshape after we have gotten a chunk pool? I
dislike naming scope from the query"* · *"Yup. Sounds good."* (2026-09-14); (4) per tag five
weights — **his ruling ("Yes.", 2026-09-14): how relevant this tag is to the described
content, seen through that facet**, not the tag's fit to the facet and not how much the facet
matters; weighed against the description, not the raw question — *"maybe their relevance to
the query-description"* · *"Yes, I think that's the play"* (2026-09-14).

Where each line of the prompt comes from — the tagger's own texts at commit c301840,
`backend/tagging/pipeline.py`:

  EXTRACT_PROMPT "## Description / Describe the chunk's content in 1-3 sentences."
      -> DESCRIPTION block, turned toward the query: the content of the chunk that would
         answer this question, its type and its subject.
  EXTRACT_PROMPT "List the retrieval handles present in the chunk: people, organisations,
      products, places, dated events, decisions, document subjects, evidence types."
      -> TAGS block, mirrored to the answering content, with the name classes struck:
         people, organisations, products, places and channels are structure and are matched
         elsewhere, so they are excluded here.
  EXTRACT_PROMPT "Keep proper names whole. Include central concepts and peripheral lookup
      handles." / "A retrieval handle is NOT a common verb, preposition, transitional word,
      sentence fragment, or generic category like "report" or "discussion"." / "Do not invent
      concepts the text does not contain."
      -> carried over word for word, the last turned to the question as its source.
  SCORE_TAGS_PROMPT "For each tag, weight its fit to every facet." and its facet table
      (topic / entities / activity / temporal / evidence)
      -> FACETS block: the table verbatim; the question asked of it is his, not the tagger's.
  SCORE_TAGS_PROMPT "`facets.<name>` — fit of this tag to that facet (1.00 = unambiguous,
      0.00 = does not belong)."
      -> the weight line, with the subject replaced by his ruling above.

The hallucination caution is his: describe the kind of content, not its facts. The prompt says
so twice — no fact the question does not carry, and no name unless the question names it.

One call, one JSON, cached under this module's own signature at `output/querytagger_cache/`
(key = sha256 over model, prompt signature and question), the cache pattern artefact_v2 uses
for `output/interp_cache`. Nothing here reads the graph, the corpus, or a question set.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

from harness import chat
from harness.contract import generator_usage_from_chat

from arms.artefact_v2 import ALL_FACETS, FILLER

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1536
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "querytagger_cache"

FACET_TABLE = """| Facet    | Captures                                                                                    |
|----------|---------------------------------------------------------------------------------------------|
| topic    | Subject matter                                                                              |
| entities | Named people, organisations, products, systems, places                                      |
| activity | Actions, processes, events                                                                  |
| temporal | Dates and time expressions present verbatim in the text                                     |
| evidence | Kind of information: definition, example, metric, argument, procedure, case_study, raw_data |"""

SYSTEM_V1 = f"""You read a question and describe the content that would answer it. You never see \
that content. Write it the way the corpus tagger wrote its chunk descriptions and tags.

## Description

Describe the content of the chunk that would answer this question in 1-3 sentences: what kind \
of content it is and what it is about.

It is not the question restated, and not a statement of what the user wants.

State no fact the question does not carry. Name no person, organisation, product, place, \
channel, system or date unless the question itself names it. Describe the kind of content, \
not its facts.

## Tags

List the retrieval handles the answering content carries: its subjects, its concepts, the \
activities, processes and decisions it turns on, the kinds of evidence it supplies.

Keep phrases whole. Include central concepts and peripheral lookup handles.

A retrieval handle is NOT a common verb, preposition, transitional word, sentence fragment, \
or generic category like "report" or "discussion".

Do not invent concepts the question does not support.

Names of people, organisations, products, places and channels are EXCLUDED from the tags. \
They are structure and are matched elsewhere. A tag is a semantic phrase — what the \
answering content is about.

## Facets

{FACET_TABLE}

## Weights

For each tag, weight how relevant that tag is to the content you described above, seen \
through each facet.

- `facets.<name>` — relevance of this tag to the described content through that facet \
(1.00 = unambiguous, 0.00 = does not belong).

This is not the tag's fit to the facet, and not how much the facet matters for the question.

Return ONLY valid JSON: \
{{"description":"...","tags":[{{"t":"tag","facets":{{"topic":0.0,"entities":0.0,\
"activity":0.0,"temporal":0.0,"evidence":0.0}}}}]}}"""

USER_TEMPLATE = "Question: {question}"

# The 2026-09-21 texts, shown to him and used verbatim: the querytagger split in two calls —
# one that writes the description and the tags, one that weighs the fixed tags against the
# fixed description through the five facets of the 09-09 ruling
# (topic / temporal / why / activity / concreteness).

GENERATE_SYSTEM = """You read a question and describe the content that would answer it. You \
never see that content. Write it the way the corpus tagger wrote its chunk descriptions and \
tags.

## Description

Describe the content of the chunk that would answer this question in 1-3 sentences: what kind \
of content it is and what it is about.

It is not the question restated, and not a statement of what the user wants.

It may say what kind of information that content holds — an explanation, a comparison, a \
sequence of changes, a figure — without supplying the information itself.

State no fact the question does not carry. Name no person, organisation, product, place, \
channel, system or date unless the question itself names it. Describe the kind of content, \
not its facts.

## Tags

List the retrieval handles the answering content carries: its subjects, its concepts, the \
activities, processes and decisions it turns on, the kinds of evidence it supplies.

Keep phrases whole. Include central concepts and peripheral lookup handles.

A retrieval handle is NOT a common verb, preposition, transitional word, sentence fragment, \
or generic category like "report" or "discussion".

Do not invent concepts the question does not support.

Names of people, organisations, products, places and channels are EXCLUDED from the tags. \
They are structure and are matched elsewhere. A tag is a semantic phrase — what the \
answering content is about.

Return ONLY valid JSON: {"description":"...","tags":["tag","tag"]}"""

GENERATE_USER_TEMPLATE = "Question: {question}"

SCORE_SYSTEM = """You are given a description of some content and a list of tags. You never \
see the content itself. For each tag, weigh how relevant that tag is to the described \
content, seen through each of five facets.

Evaluate the content characterised by the description; do not invent additional \
characteristics of an unseen answer.

## Facets

topic — looking at what that content is about: how relevant is the tag to that content?
temporal — looking at that content's time relations (before and after, now and then, done, \
pending, due; never a date): how relevant is the tag to that content, seen that way?
why — looking at that content's reasons, its causes and purposes: how relevant is the tag to \
that content, seen that way?
activity — looking at what is actually going on in that content, as against what is only \
described, referenced or discussed: how relevant is the tag to that content, seen that way?
concreteness — looking at that content's specifics, as against its general talk: how relevant \
is the tag to that content, seen that way?

## Weights

For each tag and each facet give a weight: 1.00 = could not be more relevant to that content \
through this facet, 0.00 = not relevant to it through this facet at all. Several facets may \
be high for one tag, or all of them low; give the weight you mean, never force a top value.

This is not the tag's fit to the facet, and not how much the facet matters.

Return ONLY valid JSON: {"tags":[{"t":"tag","facets":{"topic":0.0,"temporal":0.0,"why":0.0,\
"activity":0.0,"concreteness":0.0}}]}"""

SCORE_USER_TEMPLATE = "Description: {description}\n\nTags:\n{tags}"

SPLIT_FACETS = ("topic", "temporal", "why", "activity", "concreteness")


class QuerytaggerError(RuntimeError):

    def __init__(self, message: str, calls: int = 0, tokens_in: int = 0,
                 tokens_out: int = 0, time_s: float = 0.0):
        super().__init__(message)
        self.calls = calls
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.time_s = time_s


def extract_json(text: str) -> dict:
    """The first balanced JSON object in the model's text, fence or no fence."""
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    body = fence.group(1).strip() if fence else text
    start = body.find("{")
    if start == -1:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(body)):
        ch = body[i]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(body[start:i + 1])
    raise ValueError(f"unbalanced JSON object in model output: {text[:200]!r}")


def clean_tag(raw: str) -> str:
    """A tag as the vocabulary writes it — collapsed whitespace, nothing else.
    Case and punctuation carry meaning in the tag names the corpus holds."""
    return re.sub(r"\s+", " ", str(raw)).strip()


def parse_payload(raw: dict) -> dict:
    """The model's object -> {description, tags:[{t, facets}]}, or ValueError.

    Description non-empty. Tags cleaned, dropped when one character, filler, or a repeat of a
    tag already taken (case-insensitive, first spelling kept). Every surviving tag carries all
    five facets as numbers in [0, 1]; anything missing, non-numeric or out of range is the
    payload being wrong, not a value to mend.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"payload is {type(raw).__name__}, not an object")
    description = raw.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("description is empty")
    rows = raw.get("tags")
    if not isinstance(rows, list) or not rows:
        raise ValueError("tags is not a non-empty list")

    tags, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"tag row is {type(row).__name__}, not an object")
        t = clean_tag(row.get("t", ""))
        key = t.casefold()
        if len(t) < 2 or key in FILLER or key in seen:
            continue
        seen.add(key)
        facets_raw = row.get("facets")
        if not isinstance(facets_raw, dict):
            raise ValueError(f"tag {t!r} carries no facets object")
        facets = {}
        for f in ALL_FACETS:
            v = facets_raw.get(f)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"facet {f!r} of tag {t!r} is not a number: {v!r}")
            v = float(v)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"facet {f!r} of tag {t!r} is outside [0,1]: {v}")
            facets[f] = v
        tags.append({"t": t, "facets": facets})

    if not tags:
        raise ValueError("no tag survived cleaning")
    return {"description": description.strip(), "tags": tags}


def signature() -> str:
    """What the cache key answers for: the prompts, the vocabulary they exclude, the facet
    names, and the code that parses and validates the answer."""
    parts = [
        SYSTEM_V1, USER_TEMPLATE, MODEL, repr(sorted(FILLER)), repr(list(ALL_FACETS)),
        inspect.getsource(parse_payload), inspect.getsource(clean_tag),
        inspect.getsource(extract_json), inspect.getsource(querytag),
    ]
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


def prompt_for(question: str) -> tuple[str, str]:
    return SYSTEM_V1, USER_TEMPLATE.format(question=question)


def querytag(question: str, model: str = MODEL) -> dict:
    """One call, one JSON: {description, tags:[{t, facets}], usage}. A payload that does not
    parse is asked once more; the second failure raises."""
    system, user = prompt_for(question)
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    calls = tok_in = tok_out = 0
    elapsed = 0.0
    for attempt in (1, 2):
        t0 = time.perf_counter()
        resp = chat.post("/chat/completions", payload, timeout=480.0)
        elapsed += time.perf_counter() - t0
        calls += 1
        ti, to = generator_usage_from_chat(resp.get("usage"))
        tok_in += ti
        tok_out += to
        choices = resp.get("choices") or []
        finish = choices[0].get("finish_reason") if choices else "no choices"
        content = (choices[0].get("message") or {}).get("content") if choices else None
        if not content:
            raise QuerytaggerError(
                f"querytagger returned empty content (finish_reason={finish})",
                calls, tok_in, tok_out, elapsed)
        if finish == "length":
            raise QuerytaggerError(
                f"querytagger truncated at max_tokens={MAX_TOKENS} — raise the budget",
                calls, tok_in, tok_out, elapsed)
        try:
            plan = parse_payload(extract_json(content))
        except ValueError as e:
            if attempt == 2:
                raise QuerytaggerError(
                    f"querytagger emitted a malformed payload twice: {e}",
                    calls, tok_in, tok_out, elapsed) from e
        else:
            plan["usage"] = {"calls": calls, "tokens_in": tok_in,
                             "tokens_out": tok_out, "time_s": elapsed}
            return plan


def cache_key(question: str, model: str = MODEL) -> str:
    h = hashlib.sha256()
    for field in (model, signature(), question):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _store(key: str, plan: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False)
        os.replace(tmp, CACHE_DIR / f"{key}.json")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def querytag_cached(question: str, model: str = MODEL, fresh: bool = False) -> dict:
    """The cached call. A hit costs no call and reports zero usage."""
    key = cache_key(question, model)
    path = CACHE_DIR / f"{key}.json"
    if not fresh and path.is_file():
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            plan = None
        if isinstance(plan, dict) and isinstance(plan.get("tags"), list):
            plan["usage"] = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "time_s": 0.0}
            return plan
    plan = querytag(question, model)
    _store(key, {k: v for k, v in plan.items() if k != "usage"})
    return plan


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the querytagger")
    ap.add_argument("--dry", action="store_true",
                    help="print the prompt and the cache key, call nothing")
    ap.add_argument("--question", default="", help="the question to prompt with")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args(argv)
    if not args.dry:
        raise SystemExit("querytagger: only --dry runs from here; the arms make the calls")
    system, user = prompt_for(args.question)
    print(f"querytagger --dry | model {args.model} | signature {signature()[:12]}",
          flush=True)
    print("=== system ===")
    print(system)
    print("=== user ===")
    print(user)
    print("=== cache key ===")
    print(cache_key(args.question, args.model))
    return 0


if __name__ == "__main__":
    sys.exit(main())
