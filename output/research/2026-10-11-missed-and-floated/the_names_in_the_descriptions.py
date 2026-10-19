"""For his 2026-10-12 goal "solve this": the question names the product by one name, and inside the
border that name is read as "the product" (built). The chunk descriptions were written from
records that call the same product by its other names (the paper: a product has a name, an alias
and an old name, and is renamed along the way). How many descriptions hold one of the product's
own names, and which. No question, no gold, no model call; the graph is read for the chunks.

A product's own names, read from the structure: the branch's name, the names of the repositories
of its own pull requests (`first_gold_rounds/ties.py`), and the last part of the names of its
channels that are not apart.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_names_in_the_descriptions.py
"""
import json
import os
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"

import ties as TI  # noqa: E402
from arms import artefact_v4 as V  # noqa: E402


def own_names(product, P):
    names = {product}
    for rid, own in P["pr_own"].items():
        if own:
            names.add(P["raw"][rid][1]["link"].split("/")[4])
    for channel in set(P["channel_of"].values()) - P["stops"]:
        names.add(channel.split("-")[-1])
    return {n for n in names if len(n) > 2}


def pattern_of(names):
    parts = sorted((re.escape(n) for n in names), key=len, reverse=True)
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(parts) + r")(?![A-Za-z0-9])", re.IGNORECASE)


if __name__ == "__main__":
    p = V.prepare_over_corpus("the names in the descriptions")
    texts = {}
    with open(V.DESCRIPTIONS, encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            texts[row["id"]] = row["text"]
    products = [str(row["parent"]).split(".")[1] for row in p.chunk_rows]
    held, per_product, shown = Counter(), Counter(), Counter()
    names_of = {}
    for chunk_id, product in zip(p.chunk_ids, products):
        if product not in names_of:
            P = TI.product(product)
            names_of[product] = (own_names(product, P), {c.split("-")[-1] for c in P["stops"]})
        own, other_team = names_of[product]
        text = texts.get(chunk_id)
        if text is None:
            held["no description text"] += 1
            continue
        found = {m.group(0).lower() for m in pattern_of(own).finditer(text)}
        key = ("the branch's name" if found == {product.lower()} else "another own name" if found and product.lower() not in found
               else "both the branch's name and another" if found else "no own name")
        held[key] += 1
        held["the other planning team's name"] += bool(pattern_of(other_team).search(text)) if other_team else 0
    print(f"{len(p.chunk_ids)} chunks in the pool over {len(names_of)} products")
    print("own names, a product:", Counter(len(v[0]) for v in names_of.values()).most_common())
    print("e.g.", {k: sorted(v[0]) for k, v in list(names_of.items())[:5]})
    for key, count in held.most_common():
        print(f"  {count:5d} | {count / len(p.chunk_ids):4.0%}  descriptions holding: {key}")
