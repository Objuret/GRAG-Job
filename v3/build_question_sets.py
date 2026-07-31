# build_question_sets.py — one-shot: write the question-id set files to output/.

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from questions import load_questions

_HERE = Path(__file__).parent
OUT = _HERE / "output"
GOLD_N = 100
GOLD_SEED = 0


def stratified_gold(qs, n=GOLD_N, seed=GOLD_SEED):
    """The gold-N: a balanced ANSWERABLE subset, drawn by seeded round-robin
    over the HERB answer types (person/content/company/pr/url) — equal
    allocation, ~n/types per type.

    Equal allocation, not proportional, because the natural mix is lopsided
    (person 260 … url 20): a proportional draw leaves the rare types with too
    few items to say anything per-type, while round-robin gives each a usable
    count. The price is that the subset no longer matches HERB's real
    distribution, so report per-type and don't compare the gold-N aggregate to
    HERB's published average. Unanswerables carry no type, so this is
    answerable-only; the unanswerable abstention set is a separate draw.
    """
    by_type = defaultdict(list)
    for q in qs:
        if "::a::" in q.id:
            by_type[q.type].append(q)
    rng = random.Random(seed)
    for pool in by_type.values():
        rng.shuffle(pool)
    types = sorted(by_type)
    chosen, i = [], 0
    while len(chosen) < n and any(by_type.values()):
        pool = by_type[types[i % len(types)]]
        if pool:
            chosen.append(pool.pop())
        i += 1
    return chosen


def main():
    qs = load_questions()
    gold = stratified_gold(qs)
    assert len({q.id for q in gold}) == len(gold) <= GOLD_N  # unique, capped
    assert all("::a::" in q.id for q in gold)                # answerable only
    assert stratified_gold(qs) == gold                       # seed -> reproducible

    views = {
        "question_ids.jsonl": qs,
        "question_ids.answerable.jsonl": [q for q in qs if "::a::" in q.id],
        "question_ids.unanswerable.jsonl": [q for q in qs if "::u::" in q.id],
        "question_ids.gold100.jsonl": gold,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, items in views.items():
        with (OUT / name).open("w", encoding="utf-8") as fh:
            for q in items:
                fh.write(json.dumps(
                    {"id": q.id, "type": q.type, "question": q.question},
                    ensure_ascii=False) + "\n")
        print(f"{name}: {len(items)}")
    print("gold100 by type:", dict(Counter(q.type for q in gold)))


if __name__ == "__main__":
    main()
