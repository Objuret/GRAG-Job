"""For his 2026-10-12 goal "solve this" (the order): the question names the product by one name and,
inside the border, that name is read as "the product". The product's own records call it by its
other names too (the paper: a product has a name, an alias and an old name, and is renamed along
the way). Here the same is done on the other side: in the text of every own conversation and
own pull request (`own_units_for_embedding.py`) every own name of the product is replaced by
"the product", to be embedded again. No question, no gold, no model call of the lane.

A product's own names, read from the structure: the branch's name, the names of the
repositories of its own pull requests, the last part of the names of its channels that are not
apart, and what its own documents' ids hold beside the words of their type.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/own_units_without_names.py <in.jsonl> <out.jsonl>
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")

import ties as TI  # noqa: E402

WORD = re.compile(r"[a-z0-9]+")
VERSION = {"final", "latest", "new"}


def own_names(product, P):
    names = {product}
    for rid, own in P["pr_own"].items():
        if own:
            names.add(P["raw"][rid][1]["link"].split("/")[4])
    for channel in set(P["channel_of"].values()) - P["stops"]:
        names.add(channel.split("-")[-1])
    for rid, (kind, r) in P["raw"].items():
        if kind == "documents":
            kind_words = set(WORD.findall(r["type"].lower())) | VERSION
            rest = [w for w in WORD.findall(str(r["id"]).lower()) if w not in kind_words]
            if rest:
                names.add("_".join(rest))
    return {n for n in names if len(n) > 2}


def pattern_of(names):
    parts = []
    for name in sorted(names, key=len, reverse=True):
        words = WORD.findall(name.lower())
        parts.append(r"[^A-Za-z0-9]*".join(map(re.escape, words)))
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(parts) + r")(?![A-Za-z0-9])", re.IGNORECASE)


if __name__ == "__main__":
    source, out = Path(sys.argv[1]), Path(sys.argv[2])
    patterns, changed, names_n = {}, 0, Counter()
    rows = [json.loads(line) for line in open(source, encoding="utf-8")]
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            product = row["id"].split("|")[1]
            if product not in patterns:
                names = own_names(product, TI.product(product))
                patterns[product] = pattern_of(names)
                names_n[len(names)] += 1
            text = " ".join(patterns[product].sub("the product", row["text"]).split(" "))
            changed += text != row["text"]
            handle.write(json.dumps({"id": row["id"], "records": row["records"], "text": text}, ensure_ascii=False) + "\n")
    print(f"{len(rows)} rows; text changed in {changed} ({changed / len(rows):.0%}); own names a product: {dict(names_n)}")
