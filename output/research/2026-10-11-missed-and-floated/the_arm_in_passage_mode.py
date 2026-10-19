"""What the change of embedding mode on 2026-10-08 did, on the hundred. The arm is run as it stands
(the name border), retrieval only and offline, with the vectors it had before that day: the
graph's tags and chunk descriptions behind "passage: " (the 2026-10-07 side vectors), the query
tags and the query description behind "passage: " too, the raw question behind "query: " as
before, and the topic value on every edge made again from those vectors. Run with the arm's own
pick (each query tag's 5 nearest graph tags) and with the old pick (graph tags at the same-thing
level, the level taken from the passage vectors).

No model call (HERB_V4_OFFLINE=on); the local embedder writes the query side. The gold ids are
read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_arm_in_passage_mode.py [gold100]
"""
import inspect
import json
import os
import sys
import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ.pop("HERB_V4_SCOPE_STEP", None)        # the step as it stands: the name border

from arms import artefact_v4 as V  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from graph.db import _readable  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
PICK_LINE = "kth = np.array([np.sort(row[eligible])[::-1][min(k, int(eligible.sum())) - 1] for row in rows])"


def unit(m):
    m = np.asarray(m, dtype=np.float64)
    return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-12)


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the arm in passage mode")
layer = p.layer
tags_side = np.load(KEPT / "tags_passage.npz", allow_pickle=True)
tag_at = {str(t): k for k, t in enumerate(tags_side["ids"])}
missing = [t for t in p.graph_tags if str(t) not in tag_at]
if missing:
    raise SystemExit(f"{len(missing)} graph tags have no passage vector on the side")
tag_vectors = unit(tags_side["matrix"][[tag_at[str(t)] for t in p.graph_tags]])
desc_side = np.load(KEPT / "descriptions_passage.npz", allow_pickle=True)
desc_at = {str(c): k for k, c in enumerate(desc_side["ids"])}
chunk_vectors = unit(desc_side["matrix"][[desc_at[str(c)] for c in p.chunk_ids]])
et, ec = layer["edge_tag"], layer["edge_chunk"]
now = np.einsum("ij,ij->i", np.asarray(p.tag_vectors, dtype=np.float64)[et], np.asarray(p.chunk_vectors, dtype=np.float64)[ec])
print(f"the topic value on the graph's edges against the cosine of today's vectors: largest difference "
      f"{float(np.abs(layer['raw'][:, 0] - now).max()):.4f}", flush=True)
raw = np.array(layer["raw"], dtype=np.float64)
raw[:, 0] = np.einsum("ij,ij->i", tag_vectors[et], chunk_vectors[ec])
passage_layer = dict(layer)
passage_layer["raw"], passage_layer["pos"] = raw, WK.positions(raw)
held = replace(p, tag_vectors=tag_vectors, chunk_vectors=chunk_vectors, layer=passage_layer)
same = WK.same_thing_level([_readable(t) for t in p.graph_tags], tag_vectors, layer["eligible"])
print(f"the same-thing level from the passage vectors: {same['level']:.4f} (median {same['median']:.4f}, "
      f"{same['pairs']} pairs)", flush=True)


def tag_cosines_passage(description, tags, prepared):
    """`artefact_v4._tag_cosines` with the tags and the description embedded behind "passage: "."""
    dim = prepared.chunk_vectors.shape[1]
    matrices, used, recipe = V._query_cosines(
        description, tags, V._QueryAxes(prepared.tag_vectors, np.eye(dim)), "passage")
    query_tag_vectors = np.asarray(matrices["query_chunk_cosines"], dtype=np.float64)
    description_vector = np.asarray(matrices["query_description_cosines"], dtype=np.float64)
    return ({"tags": np.asarray(matrices["query_tag_cosines"], dtype=np.float64),
             "description": description_vector @ prepared.chunk_vectors.T,
             "tags_to_description": query_tag_vectors @ description_vector,
             "tags_to_chunks": query_tag_vectors @ prepared.chunk_vectors.T}, used, recipe)


V._tag_cosines = tag_cosines_passage
source = inspect.getsource(WK.chain)
if PICK_LINE not in source:
    raise SystemExit("the pick line of v4_walk.chain is not what this script expects")
space = dict(vars(WK))
space["SAME_LEVEL"] = float(same["level"])
exec(source.replace(PICK_LINE, "kth = np.full(rows.shape[0], SAME_LEVEL)").replace("def chain(", "def chain_same("), space)
own_chain, same_chain = WK.chain, space["chain_same"]
WAYS = {"passage vectors, the arm's own pick (5 nearest)": own_chain,
        "passage vectors, the old pick (the same-thing level)": same_chain}
recall = {name: [] for name in WAYS}
for n_done, qid in enumerate(wanted, 1):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    for name, chain in WAYS.items():
        WK.chain = chain
        out = V.answer_one_question((qid, q.question), held, None, 50, BUDGET)
        recall[name].append(len(cites & {str(x) for x in out.context_ids}) / len(cites))
    WK.chain = own_chain
    if n_done % 10 == 0:
        print(f"  ... {n_done} questions", flush=True)

before = np.load(HERE / f"the_arm_with_area_weight__{SET}.npy", allow_pickle=True).item()
pairs = (("passage vectors, the arm's own pick (5 nearest)", "the arm as it stands"),
         ("passage vectors, the old pick (the same-thing level)", "the old pick of tags"))
print(f"\n{SET}: {len(wanted)} questions, the arm with the name border, retrieval only, no model call")
print("== context_recall_id with the passage vectors | with today's query vectors | passage minus query: mean, its "
      "standard error, questions higher / lower ==")
for mine, theirs in pairs:
    a, b = np.asarray(recall[mine]), np.asarray(before[theirs])
    d = a - b
    print(f"  {a.mean():.3f} | {b.mean():.3f} | {d.mean():+.3f}, {d.std(ddof=1) / np.sqrt(d.size):.3f}, "
          f"{int((d > 0).sum())} / {int((d < 0).sum())}  {mine}")
np.save(HERE / f"the_arm_in_passage_mode__{SET}.npy", recall, allow_pickle=True)
print("done", flush=True)
