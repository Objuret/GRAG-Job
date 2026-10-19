"""Round 16, his 2026-10-12 "how is the gold density of the top chunk from the tags and chunks?": the
first chunk of the tags' route and of the chunk descriptions' route, inside the question's
product, the hundred: how often it is gold, and how much of it is gold (cited records among its
records)."""
import numpy as np

from explore import load, standing

Q = load()["questions"]
routes = {
    "the tags (the chunk's closest tag to a query tag)": lambda d: d["tags"],
    "the chunk descriptions (against the query description)": lambda d: d["description"],
    "the chunk descriptions (against the question)": lambda d: d["question"],
    "the three added": lambda d: standing(d["tags"]) + standing(d["description"]) + standing(d["question"]),
}
print("== the first chunk of a route, over the hundred: it is gold on | records in it, cited among them, share | the "
      "same inside the first chunks that are gold ==")
for name, make in routes.items():
    gold = records = cited = gold_records = gold_cited = 0
    for d in Q.values():
        top = int(np.lexsort((d["id_rank"], -np.asarray(make(d), dtype=np.float64)))[0])
        n = len(d["records"][top])
        c = int(d["cited"][top])
        records += n
        cited += c
        if d["gold"][top]:
            gold += 1
            gold_records += n
            gold_cited += c
    print(f"  {name}: {gold} of 100 | {records} records, {cited} cited, {cited / records:.0%} | "
          f"{gold_records} records, {gold_cited} cited, {gold_cited / max(gold_records, 1):.0%}")
all_records = sum(len(r) for d in Q.values() for r in d["records"])
all_cited = sum(int(d["cited"].sum()) for d in Q.values())
gold_chunk_records = sum(len(r) for d in Q.values() for r, g in zip(d["records"], d["gold"]) if g)
print(f"  for scale, every chunk of the product: {all_cited} of {all_records} records cited ({all_cited / all_records:.1%}); "
      f"inside the gold chunks: {all_cited} of {gold_chunk_records} ({all_cited / gold_chunk_records:.0%})")
