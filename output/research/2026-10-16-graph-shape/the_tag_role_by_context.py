"""Does a tag keep its function where the graph's shape says the context is the same? His thesis 6.4:
the facet membership is stored on the relation between segment and tag "eftersom samma taggnamn
kan ha olika analytisk funktion beroende på kontext". The graph's shape gives the context: a
chunk's parent (its channel, its document, its batch of pull requests), its product, its kind.

A tag's role on an edge (as in the counts of 2026-10-15/16): the tag's chunks ranked against each
other in each of the four ranking facets; the role is the facet the chunk ranks best in (the first
in the fixed order on a tie). Ranks only, inside one tag, over every chunk of the pool.

For every pair of edges of the same tag, the pair's context: the same parent; the same product and
kind but another parent; the same kind in another product; another kind in the same product;
another kind in another product. Per context: the share of pairs whose two edges have the same
role, against the share expected if the tag's roles were dealt out at random among its own edges
(the tag's own role counts kept). Counted exactly from group sizes, every pair, no sample. Read
only; no model call; no gold.
"""
import os
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_FACETS"] = "off"

from arms import artefact_v4 as V  # noqa: E402

p = V.prepare_over_corpus("the tag role by context")
layer = p.layer
tag_e, chunk_e, place = layer["edge_tag"], layer["edge_chunk"], layer["pos"][:, 1:]
parent = [str(row["parent"]) for row in p.chunk_rows]
product = [name.split(".")[1] for name in parent]
kind = [str(row["kind"]) for row in p.chunk_rows]
edges_of_tag = defaultdict(list)
for k, t in enumerate(tag_e.tolist()):
    edges_of_tag[t].append(k)
print("prepared", flush=True)


def pairs_and_same(groups):
    """groups: per group the Counter of roles. Pairs inside the groups and pairs with one role."""
    pairs = same = 0
    for roles in groups:
        n = sum(roles.values())
        pairs += n * (n - 1) // 2
        same += sum(c * (c - 1) // 2 for c in roles.values())
    return pairs, same


CONTEXTS = ("the same parent", "same product and kind, another parent", "same kind, another product",
            "another kind, same product", "another kind, another product")
obs, exp, n_pairs = Counter(), Counter(), Counter()
tags_counted = 0
for t, e in edges_of_tag.items():
    if len(e) < 3:
        continue
    tags_counted += 1
    e = np.array(e)
    ranks = np.column_stack([rankdata(-place[e, f], method="average") for f in range(place.shape[1])])
    role = np.argmin(ranks, axis=1)
    chunks = chunk_e[e]
    total_pairs, total_same = pairs_and_same([Counter(role.tolist())])
    p_same = total_same / total_pairs
    by = {"parent": defaultdict(Counter), "product_kind": defaultdict(Counter), "kind": defaultdict(Counter),
          "product": defaultdict(Counter)}
    for r, c in zip(role.tolist(), chunks.tolist()):
        by["parent"][(parent[c], kind[c])][r] += 1          # a parent can hold a document and its parts
        by["product_kind"][(product[c], kind[c])][r] += 1
        by["kind"][kind[c]][r] += 1
        by["product"][product[c]][r] += 1
    P = {name: pairs_and_same(g.values()) for name, g in by.items()}
    # pairs in the same parent are inside the same product and kind (a parent sits under one product and kind)
    cells = {
        "the same parent": P["parent"],
        "same product and kind, another parent": (P["product_kind"][0] - P["parent"][0], P["product_kind"][1] - P["parent"][1]),
        "same kind, another product": (P["kind"][0] - P["product_kind"][0], P["kind"][1] - P["product_kind"][1]),
        "another kind, same product": (P["product"][0] - P["product_kind"][0], P["product"][1] - P["product_kind"][1]),
    }
    used = sum(v[0] for v in cells.values())
    used_same = sum(v[1] for v in cells.values())
    cells["another kind, another product"] = (total_pairs - used, total_same - used_same)
    for name, (m, s) in cells.items():
        obs[name] += s
        n_pairs[name] += m
        exp[name] += m * p_same

print(f"\n{tags_counted} tags with three chunks or more; pairs of edges of one tag, per context:")
for name in CONTEXTS:
    m = n_pairs[name]
    print(f"  {name:40s}: {m:9d} pairs | same role {obs[name] / max(m, 1):5.1%} | expected from the tag's own roles"
          f" {exp[name] / max(m, 1):5.1%} | ratio {obs[name] / max(exp[name], 1e-9):.2f}")
print("done", flush=True)
