"""Stage query: interpret — one stateless structured call per prompt emits
facet phrases + literals + date_range + answer_shape (MODEL_CONTRACTS §2,
DESIGN §14.7).

The interpreter is a one-shot flagger with no tools: prompt + current date +
pre-pass marked spans in → structured JSON out. Deterministic code runs the
literal pre-pass before it (prepass.py) and the scoped distance-lookup after
it (a later build step). Marked spans ride in so polarity attaches to exact
matches ("apart from PitchForce" → excluded); the model must not re-emit a
matched span as a facet phrase.

Structured output via NIM `response_format: json_schema`, mirroring the
tagger. One temp-0 call per prompt, instance discarded — reproducible.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import nim
from artefact.prepass import MarkedSpan, prepass

INTERPRETER_MODEL = "meta/llama-3.3-70b-instruct"

SYSTEM = (
    "You read one query prompt and decompose it into the axes the retrieval "
    "pipeline matches on. Output is structured JSON with four fields.\n\n"
    "facet_phrases: 0–8 short contextual phrases naming what the prompt is "
    "about — the activities, arguments, or case-study situations a relevant "
    "chunk would discuss (e.g. \"debugging a memory leak\", \"postmortem "
    "analysis\", \"concerns about latency\", \"QA feedback on a spec document\"). "
    "Names-in-context welcome; bare labels discouraged. Each phrase becomes a "
    "cluster center scored against tag embeddings, so it must be a "
    "self-contained description of a retrievable topic. Do not re-emit any "
    "span that appears in the marked_spans block — those are literal "
    "entities, not facets.\n\n"
    "literals: entities the prompt names. For each marked span in the input, "
    "emit one entry with marked=true, token = the span text, kind and "
    "polarity copied from the span. Also flag entities the language names but "
    "the pre-pass did not match (marked=false), inferring kind from language "
    "alone (a person's name, an org/product name). kind ∈ {person, org, "
    "product}; polarity ∈ {wanted, excluded} — excluded when the prompt says "
    "\"apart from\"/\"excluding\"/\"except\"/\"not\" before the entity. "
    "Excluded means no boost downstream, never removal.\n\n"
    "date_range: a literal calendar window for the structural timestamp "
    "filter. Resolve relative phrases (\"last quarter\", \"previous "
    "release\", \"previous version\") against the current_date supplied in "
    "the input into a CLOSED past window — both endpoints strictly before "
    "current_date, never current_date itself as an endpoint (that would "
    "mean \"up to now\", which relative-past phrases never imply). Use ISO "
    "YYYY-MM-DD; set a field to null when the prompt expresses no time "
    "constraint at all on that side.\n\n"
    "answer_shape: \"content\" when the prompt wants retrieval-ranked passages "
    "(\"what did people say about X\", \"find links to Y\", \"summarize the "
    "discussion on Z\"), \"aggregate\" when it wants a count/max/group-by over "
    "structured records (\"max number of issues\", \"how many PRs\", \"list "
    "the engineers who…\", \"find the company that reported the most…\").\n\n"
    "MUST NOT appear in facet_phrases or in any literal token: ids (eid_*, "
    "CUST-*), dates, years, URLs, PR numbers, channel ids. Emit no numbers, "
    "no weights, no coefficients. Emit no fields beyond the four above."
)

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "facet_phrases": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "literals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "token": {"type": "string"},
                    "kind": {"type": "string", "enum": ["person", "org", "product"]},
                    "polarity": {"type": "string", "enum": ["wanted", "excluded"]},
                    "marked": {"type": "boolean"},
                },
                "required": ["token", "kind", "polarity", "marked"],
            },
        },
        "date_range": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "from": {"type": ["string", "null"]},
                "to": {"type": ["string", "null"]},
            },
            "required": ["from", "to"],
        },
        "answer_shape": {"type": "string", "enum": ["content", "aggregate"]},
    },
    "required": ["facet_phrases", "literals", "date_range", "answer_shape"],
}

_KINDS = ("person", "org", "product")
_POLARITIES = ("wanted", "excluded")
_DATE_RE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$")
# The contract's MUST-NOT set (MODEL_CONTRACTS §2): ids, dates, years, URLs,
# PR numbers, channel ids never appear in a facet phrase or a literal token.
_MUST_NOT_RE = __import__("re").compile(
    r"\b(?:eid_[0-9a-f]+|CUST-\d+|PR[-#]?\d+|#\d{2,})\b"
    r"|https?://\S+"
    r"|\b(?:19|20)\d{2}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b")


def _format_user(prompt: str, current_date: str, spans: list[MarkedSpan]) -> str:
    spans_json = json.dumps(
        [{"span": s.span, "kind": s.kind, "polarity": s.polarity,
          "start": s.start, "end": s.end} for s in spans],
        ensure_ascii=False, indent=2)
    return (
        f"current_date: {current_date}\n\n"
        f"prompt:\n{prompt}\n\n"
        f"marked_spans:\n{spans_json}"
    )


def _validate(parsed: dict, raw: str) -> None:
    """Fail loud on a schema-breaking response — never a silent partial."""
    for k in ("facet_phrases", "literals", "date_range", "answer_shape"):
        if k not in parsed:
            raise RuntimeError(f"interpreter output missing key {k!r}: {raw!r}")
    fp = parsed["facet_phrases"]
    if not isinstance(fp, list) or not all(isinstance(p, str) for p in fp):
        raise RuntimeError(f"facet_phrases not list[str]: {raw!r}")
    if len(fp) > 8:
        raise RuntimeError(f"facet_phrases over maxItems 8: {raw!r}")
    for p in fp:
        if _MUST_NOT_RE.search(p):
            raise RuntimeError(f"facet_phrase violates MUST-NOT: {p!r}: {raw!r}")
    for lit in parsed["literals"]:
        if not isinstance(lit, dict):
            raise RuntimeError(f"literal not object: {raw!r}")
        for k in ("token", "kind", "polarity", "marked"):
            if k not in lit:
                raise RuntimeError(f"literal missing {k!r}: {raw!r}")
        if not isinstance(lit["token"], str) or not lit["token"]:
            raise RuntimeError(f"literal token not non-empty str: {raw!r}")
        if lit["kind"] not in _KINDS:
            raise RuntimeError(f"literal kind out of enum: {raw!r}")
        if lit["polarity"] not in _POLARITIES:
            raise RuntimeError(f"literal polarity out of enum: {raw!r}")
        if not isinstance(lit["marked"], bool):
            raise RuntimeError(f"literal marked not bool: {raw!r}")
        if _MUST_NOT_RE.search(lit["token"]):
            raise RuntimeError(f"literal token violates MUST-NOT: {lit['token']!r}: {raw!r}")
    dr = parsed["date_range"]
    if not isinstance(dr, dict):
        raise RuntimeError(f"date_range not object: {raw!r}")
    f, t = dr.get("from"), dr.get("to")
    for k, v in (("from", f), ("to", t)):
        if v is not None and not (isinstance(v, str) and _DATE_RE.match(v)):
            raise RuntimeError(f"date_range.{k} not YYYY-MM-DD or null: {raw!r}")
    if f is not None and t is not None and f > t:
        raise RuntimeError(f"date_range reversed (from > to): {raw!r}")
    if parsed["answer_shape"] not in ("content", "aggregate"):
        raise RuntimeError(f"answer_shape out of enum: {raw!r}")


def interpret(prompt: str, *, current_date: str | None = None,
              model: str = INTERPRETER_MODEL,
              _spans: list[MarkedSpan] | None = None) -> tuple[dict, dict]:
    """One stateless temp-0 structured call → (parsed_json, usage). Fail loud
    on a null or schema-breaking response — never a silent partial.

    `_spans` is a pass-through for callers that already ran the pre-pass
    (e.g. the smoke loop prints them); left None it runs the pre-pass here."""
    cd = current_date or date.today().isoformat()
    spans = _spans if _spans is not None else prepass(prompt)
    user = _format_user(prompt, cd, spans)
    t0 = time.perf_counter()
    resp = nim.post("/chat/completions", {
        "model": model,
        "temperature": 0,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "interpretation", "schema": _SCHEMA},
        },
    })
    elapsed = time.perf_counter() - t0
    usage = resp.get("usage") or {}
    choices = resp.get("choices") or []
    if not choices:
        raise RuntimeError("interpreter returned no choices")
    finish = choices[0].get("finish_reason")
    content = (choices[0].get("message") or {}).get("content")
    if content is None:
        raise RuntimeError(f"interpreter returned null content (finish_reason={finish})")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"interpreter broke the schema (finish_reason={finish}): {content!r}") from e
    _validate(parsed, content)
    return parsed, {
        "tokens_in": int(usage.get("prompt_tokens", 0) or 0),
        "tokens_out": int(usage.get("completion_tokens", 0) or 0),
        "tokens": int(usage.get("total_tokens", 0) or 0),
        "time": elapsed,
        "finish_reason": finish,
        "n_facet_phrases": len(parsed["facet_phrases"]),
        "n_literals": len(parsed["literals"]),
        "n_marked_spans": len(spans),
    }


def _load_gold100() -> list[dict]:
    p = Path(__file__).resolve().parent.parent / "output" / "question_ids.gold100.jsonl"
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _stratified(qs: list[dict], per_type: int = 2) -> list[dict]:
    """`per_type` per HERB answer type (person/content/company/pr/url)."""
    by_type: dict[str, list[dict]] = {}
    for q in qs:
        by_type.setdefault(q["type"], []).append(q)
    out: list[dict] = []
    for t in sorted(by_type):
        out.extend(by_type[t][:per_type])
    return out


def smoke(n_per_type: int = 2, current_date: str | None = None) -> None:
    """Run the interpreter on a stratified slice of the gold-100 set; print
    each question, its pre-pass marked spans, and the interpreter JSON."""
    nim.require_key()
    qs = _stratified(_load_gold100(), per_type=n_per_type)
    cd = current_date or date.today().isoformat()
    print(f"== interpreter smoke: {len(qs)} gold-100 questions on {INTERPRETER_MODEL} ==")
    print(f"   current_date = {cd}\n")
    for q in qs:
        prompt = q["question"]
        spans = prepass(prompt)
        print(f"--- {q['id']}  (type={q['type']}) ---")
        print(f"Q: {prompt}")
        if spans:
            for s in spans:
                print(f"  span [{s.kind} {s.polarity}] {s.span!r}  @ {s.start}-{s.end}")
        else:
            print("  span (none)")
        try:
            parsed, usage = interpret(prompt, current_date=cd, _spans=spans)
        except RuntimeError as e:
            print(f"  FAILED: {str(e)[:200]}\n")
            continue
        print(f"  usage: in={usage['tokens_in']} out={usage['tokens_out']} "
              f"finish={usage['finish_reason']} {usage['time']:.1f}s")
        print(f"  JSON: {json.dumps(parsed, ensure_ascii=False)}")
        print()


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if args and args[0] == "smoke":
        n = int(args[1]) if len(args) > 1 else 2
        smoke(n_per_type=n)
    else:
        text = " ".join(args) or (
            "Find the name of company that reported the maximum number of issues "
            "that didn't need fixes in KnowledgeForce?"
        )
        parsed, usage = interpret(text)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
        print(f"\nusage: {usage}")
