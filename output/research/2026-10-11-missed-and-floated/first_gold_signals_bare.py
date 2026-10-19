"""For his 2026-10-11 goal "Explore this more to find the closest first gold". The question read
without the product's name puts a gold chunk first more often (the name set the border; inside
the border every chunk is of that product). Here the same is done to the rest of the query side:
the query description and the query tags of the cached first call with the product's name
replaced by "the product" (a tag that is only the name is dropped), embedded anew by the local
embedder. No model call.

Written beside the first table: the bare description against the descriptions (query mode both
sides; as a query against the passage vectors), and the bare query tags against the chunks' tags
(query mode both sides): per query tag the chunk's closest tag.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/first_gold_signals_bare.py gold100 <folder>
"""
import json
import os
import pickle
import re
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
OUT = Path(sys.argv[2])
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
TOKEN = re.compile(r"[a-z0-9]+")


def unit(m):
    m = np.asarray(m, dtype=np.float64)
    return m / np.maximum(np.linalg.norm(m, axis=-1, keepdims=True), 1e-12)


with open(OUT / f"first_gold_signals__{SET}.pkl", "rb") as handle:
    first = pickle.load(handle)["questions"]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("first gold signals, bare")
layer, n = p.layer, len(p.chunk_ids)
et, ec = layer["edge_tag"], layer["edge_chunk"]
CV, TV = unit(p.chunk_vectors), unit(p.tag_vectors)
desc_side = np.load(KEPT / "descriptions_passage.npz", allow_pickle=True)
desc_at = {str(c): k for k, c in enumerate(desc_side["ids"])}
CP = unit(desc_side["matrix"][[desc_at[str(c)] for c in p.chunk_ids]])
AXES = V._QueryAxes(TV, np.eye(CV.shape[1]))
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
print("prepared", flush=True)


def cached_sides():
    out = []
    for f in CACHE.glob("*.json"):
        if f.name.endswith(".started.json"):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        got = j.get("raw")
        if j.get("ok") and isinstance(got, dict) and got.get("description") and got.get("tags"):
            out.append((f.stat().st_mtime, (j.get("signature") or {}).get("user") or "", got))
    return sorted(out, key=lambda row: -row[0])


SIDES = cached_sides()


def side_of(q):
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, got in SIDES:
        if q.question in user:
            return str(got["description"]), names(got.get("tags")), names(got.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


def without_the_name(text, name):
    parts = TOKEN.findall(name.lower())
    if not parts:
        return text
    pattern = re.compile(r"(?<![A-Za-z0-9])" + r"[^A-Za-z0-9]*".join(re.escape(part) for part in parts)
                         + r"(?![A-Za-z0-9])", re.IGNORECASE)
    return " ".join(pattern.sub("the product", text).split())


def closest_tag(rows):
    out = np.full((rows.shape[0], n), -1.)
    np.maximum.at(out.T, ec, rows[:, et].T)
    return out


bare, done = {}, 0
held_name = dropped = changed_tags = changed_descriptions = total_tags = 0
for qid, d in first.items():
    q = by_id[qid]
    inside = d["chunks"]
    name = branches[int(branch_of[inside[0]])][0]
    description, tags, asked = side_of(q)
    every = tags + [t for t in asked if t not in tags]
    bare_description = without_the_name(description, name)
    changed_descriptions += int(bare_description != description)
    bare_tags = []
    for t in every:
        b = without_the_name(t, name)
        total_tags += 1
        changed_tags += int(b != t)
        if b.strip().lower() in ("the product", ""):
            dropped += 1
            continue
        bare_tags.append(b)
    bare_tags = list(dict.fromkeys(bare_tags)) or every
    got = V._query_cosines(bare_description, bare_tags, AXES, "query")[0]
    tag_vectors = np.asarray(got["query_chunk_cosines"], dtype=np.float64)
    description_vector = np.asarray(got["query_description_cosines"], dtype=np.float64)
    bare[qid] = {
        "bare_description": CV[inside] @ description_vector,
        "bare_description_to_passage": CP[inside] @ description_vector,
        "bare_fit": closest_tag(tag_vectors @ TV.T)[:, inside].astype(np.float32),
        "bare_tags_description": (tag_vectors @ CV[inside].T).astype(np.float32),
        "bare_tags_to_passage": (tag_vectors @ CP[inside].T).astype(np.float32),
    }
    done += 1
    if done % 10 == 0:
        print(f"  ... {done} questions", flush=True)
with open(OUT / f"first_gold_signals_bare__{SET}.pkl", "wb") as handle:
    pickle.dump(bare, handle)
print(f"{SET}: {len(bare)} questions; the product's name stood in the query description on {changed_descriptions}; in "
      f"{changed_tags} of {total_tags} query tags, {dropped} of them only the name and dropped")
print("done", flush=True)
