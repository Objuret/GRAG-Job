
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from harness.questions import load_questions

_HERE = Path(__file__).parent
OUT = _HERE.parent / "output"
GOLD_N = 100
GOLD_SEED = 0


def stratified_gold(qs, n=GOLD_N, seed=GOLD_SEED):
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
    assert len({q.id for q in gold}) == len(gold) <= GOLD_N
    assert all("::a::" in q.id for q in gold)
    assert stratified_gold(qs) == gold

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
