"""The four facets and the edit-list reconstruction, with no graph or model lane behind them.

`facet_counterfactuals` writes the edit lists; `facet_rulers` reads them back and must
reconstruct exactly the same text. Both import from here so the reconstruction has one
definition and so the ruler pass runs on a machine with no neo4j driver and no claude lane.
"""
from __future__ import annotations

FACETS = ("temporal", "why", "activity", "concreteness")


def apply_edits(text: str, edits: list) -> tuple:
    """(reconstructed text, problems). An edit whose `find` is absent from the text, occurs
    more than once, or overlaps another edit of the same facet is not applied and is named.
    The anchor check is the whole guarantee that an edit list says the same thing a full
    rewrite would: every untouched character is the original's."""
    problems, spans = [], []
    for i, e in enumerate(edits):
        if not isinstance(e, dict):
            problems.append(f"edit {i} is {type(e).__name__}, not an object")
            continue
        find = e.get("find")
        repl = e.get("replace")
        if not isinstance(find, str) or not find:
            problems.append(f"edit {i} carries no `find` string")
            continue
        if not isinstance(repl, str):
            problems.append(f"edit {i} `replace` is not a string: {repl!r}")
            continue
        n = text.count(find)
        if n == 0:
            problems.append(f"edit {i} anchor not in the text: {find[:60]!r}")
            continue
        if n > 1:
            problems.append(f"edit {i} anchor occurs {n} times: {find[:60]!r}")
            continue
        start = text.index(find)
        spans.append((start, start + len(find), repl, i))
    spans.sort()
    out, cursor, applied = [], 0, 0
    for start, end, repl, i in spans:
        if start < cursor:
            problems.append(f"edit {i} overlaps an earlier edit")
            continue
        out.append(text[cursor:start])
        out.append(repl)
        cursor = end
        applied += 1
    out.append(text[cursor:])
    return "".join(out), problems
