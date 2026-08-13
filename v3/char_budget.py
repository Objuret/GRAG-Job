"""char_budget.py — fill-to-budget consumption of a ranked context stream.

Shared harness plumbing, not retrieval code: an arm produces its own ranking and
hands it here as (unit_id, text) pairs, best first. Whole units keep their text
while the cumulative character count fits the budget; the unit that crosses it
is cut mid-text so the total context text is exactly the budget; everything
after is dropped. A ranking that runs out first returns its true total — no
padding, no error.
"""
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass
class BudgetCut:
    """One consumed ranking. `contexts` holds the whole units' texts plus, when
    a unit crossed the budget, its cut fragment as the final entry. `kept`
    counts the whole units only. `chars` is the total context text — the budget
    exactly, or less when the ranking ran out. `boundary` records the cut unit
    as {id, chars_kept, chars_full}, None when no unit was cut. `exhausted` is
    the ran-out case."""
    contexts: list
    kept: int
    chars: int
    boundary: Optional[dict]
    exhausted: bool


def cut_at_budget(units: Iterable[tuple], budget: int) -> BudgetCut:
    """Consume (unit_id, text) pairs in rank order up to `budget` characters.
    Iteration stops at the cut, so a lazy stream resolves only what is kept."""
    if budget < 1:
        raise ValueError(f"char budget must be >= 1, got {budget}")
    contexts: list = []
    kept = 0
    chars = 0
    for uid, text in units:
        if chars + len(text) <= budget:
            contexts.append(text)
            kept += 1
            chars += len(text)
            if chars == budget:
                return BudgetCut(contexts, kept, chars, None, False)
            continue
        take = budget - chars
        contexts.append(text[:take])
        return BudgetCut(
            contexts, kept, budget,
            {"id": uid, "chars_kept": take, "chars_full": len(text)}, False)
    return BudgetCut(contexts, kept, chars, None, True)


def _selfcheck():
    cut = cut_at_budget([("a", "xxxx"), ("b", "yyyy"), ("c", "zzzz")], 6)
    assert cut.contexts == ["xxxx", "yy"] and cut.kept == 1 and cut.chars == 6
    assert cut.boundary == {"id": "b", "chars_kept": 2, "chars_full": 4}
    assert not cut.exhausted

    cut = cut_at_budget([("a", "xxxx"), ("b", "yyyy")], 4)
    assert cut.contexts == ["xxxx"] and cut.boundary is None and not cut.exhausted

    cut = cut_at_budget([("a", "xx")], 9)
    assert cut.chars == 2 and cut.exhausted and cut.boundary is None
    print("char_budget self-check OK", flush=True)


if __name__ == "__main__":
    _selfcheck()
