"""The arm's own `v4_walk.both_sides` on the made-up question, from the arm's own prepare: the
record per k, to hold against both_sides_made_up.log (the lines "overlapping clouds for each
step", with the description). Read only: no write, no model call, no test question.

    .venv/Scripts/python.exe output/research/2026-10-10-two-clouds/both_sides_check.py
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from arms import artefact_v4 as V  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402

walk = json.loads((REPO / "output/walkthrough/20261005T040000Z/walkthrough.json").read_text(encoding="utf-8"))
query_tags = list(dict.fromkeys(t["text"] for t in walk["query_tags"]))
kept = np.load(HERE / "query_vectors.npz", allow_pickle=True)
if list(kept["texts"]) != [walk["question"], walk["description"]] + query_tags:
    raise SystemExit("the kept query vectors are not this question's; run two_clouds_made_up.py")
vectors = np.asarray(kept["vectors"], dtype=np.float64)

p = V.prepare_over_corpus("the made-up question")
rows = vectors[2:] @ p.tag_vectors.astype(np.float64).T
d_near = p.chunk_vectors.astype(np.float64) @ vectors[1]
# The made-up tags name no facet; the first stands in. It decides only the order inside a group.
named = np.zeros(len(query_tags), dtype=np.int64)
print(f"the question: {walk['question']}")
for k in (3, 4, 5, 6, 7):
    got = WK.both_sides(p.layer, rows, named, d_near, V.tree_leaves(p.tree),
                        dict(V.tree_level(p.tree, "product")), k)
    r = got["record"]
    clouds = r["nearness_clouds"]
    print(f"k={k}: nearness clouds tags {clouds['tags']['chunks']} / descriptions "
          f"{clouds['description']['chunks']}, in both {r['chunks_in_both_nearness_clouds']}; "
          f"scopes in both scope clouds {r['scopes_in_both_scope_clouds']}, main "
          f"{len(r['main_scopes'])}; border {r['branches'] if len(r['branches']) <= 5 else len(r['branches'])} "
          f"({int(got['border'].sum())} chunks); inside: tags' cloud {r['inside']['clouds']['tags']}, "
          f"descriptions' {r['inside']['clouds']['description']}, both {r['inside']['in_both']}, "
          f"one {r['inside']['in_one']}, neither {r['inside']['in_neither']}")
print("done", flush=True)
