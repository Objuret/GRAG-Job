from dataclasses import dataclass
from typing import Iterable, Optional

from harness.fields import sub

# what an arm writes into a row's meta about the cut (the words of FIELDS.md)
FIELDS = sub("How the character budget was filled.", {
    "budget": "The character budget.",
    "chars": "How many characters were handed over.",
    "kept": "How many units were handed over whole.",
    "boundary": sub("The unit that was cut where the budget ended. Empty when the budget ended "
                    "exactly at a unit's end, or when the ranking ran out first.", {
                        "id": "The id of its record.",
                        "chars_kept": "How many of its characters were handed over.",
                        "chars_full": "How many characters it has.",
                    }),
    "exhausted": "Whether the ranking ran out before the budget was full.",
})


@dataclass
class BudgetCut:
    contexts: list
    kept: int
    chars: int
    boundary: Optional[dict]
    exhausted: bool


def cut_at_budget(units: Iterable[tuple], budget: int) -> BudgetCut:
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
