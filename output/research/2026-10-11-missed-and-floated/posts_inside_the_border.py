"""His 2026-10-12 goal "solve this" (the gold is touched and badly placed; about 4 of a question's 10
gold chunks fit in the 72,000). The 72,000 is spent on whole chunks of about 13 posts, and a
question's gold is about 25 single posts. Here the unit delivered is the POST, or the
conversation, inside the border the product's name sets, valued by the post's own vector (the
vector baseline's record vectors, records behind "passage: ") against the question read WITHOUT
the product's name (behind "query: "). On the hundred, cached query side, no model call.

Units and orders:
  chunks   the three routes added (the stand-in for the arm), whole chunks
  posts    every record of the product on its own, by its nearness to the question
  posts+   the same with the standing of the post's chunk in the three routes added
  talks    a conversation (the messages of one channel on one day; any other record alone) by
           its closest post, by its two closest, by its closest post with its chunks' standing
  walks    posts by nearness; each post taken brings the rest of its conversation with it
Each with the question as asked and with the product's name taken out. Delivery stops at the
first unit that does not fit in 72,000 characters, a record counted at the length of its own
JSON text.

Printed: context_recall_id (share of the cited records delivered inside 72,000 characters), the
records delivered and how many of them are cited, and whether the first unit delivered holds a
cited record.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/posts_inside_the_border.py [gold100]
"""
import json
import os
import re
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timezone
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
from arms.artefact_v2 import _load_verified_doc, _resolve_chunk  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
TOKEN = re.compile(r"[a-z0-9]+")


def stamp(value):
    if value is None:
        return None
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00").replace(" ", "T")).timestamp()
    except ValueError:
        return None


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("posts inside the border")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, length = {}, np.zeros(n, dtype=np.int64)
post = {}                                   # record id -> size, chunk, conversation key
chunk_posts = []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    length[i] = len(text)
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    mine = []
    for r in [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]:
        if r.get("id") is None:
            continue
        rid = str(r["id"])
        when = stamp(((r.get("Message") or {}).get("User") or {}).get("timestamp")) if "Message" in r else None
        channel = (r.get("Channel") or {}).get("channelID") if "Channel" in r else None
        talk = ((row["relpath"], channel, datetime.fromtimestamp(when, timezone.utc).date().isoformat())
                if when is not None and channel is not None else ("alone", rid))
        if rid not in post:
            post[rid] = {"size": len(json.dumps(r, ensure_ascii=False)) + 1, "chunk": i, "talk": talk,
                         "when": when if when is not None else 0.}
        mine.append(rid)
    chunk_posts.append(mine)
corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
matrix = np.asarray(corpus["matrix"], dtype=np.float32)
matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
dim = matrix.shape[1]
AXES = V._QueryAxes(np.zeros((1, dim)), np.eye(dim))
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


def standing(x):
    x = np.asarray(x, dtype=np.float64)
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def without_the_names(question, names):
    out = question
    for name in names:
        parts = TOKEN.findall(name.lower())
        if parts:
            pattern = re.compile(r"(?<![A-Za-z0-9])" + r"[^A-Za-z0-9]*".join(re.escape(part) for part in parts)
                                 + r"(?![A-Za-z0-9])", re.IGNORECASE)
            out = pattern.sub("the product", out)
    return " ".join(out.split())


def vector_of(text):
    return np.asarray(V._query_cosines(text, [], AXES)[0]["query_description_cosines"], dtype=np.float32)


def deliver(units, cites):
    """units: lists of record ids, best first. A record already sent is not sent twice."""
    have, used, first = set(), 0, None
    for unit in units:
        fresh = [r for r in unit if r not in have]
        if not fresh:
            continue
        cost = sum(post[r]["size"] for r in fresh)
        if used + cost > BUDGET:
            break
        used += cost
        if first is None:
            first = bool(set(fresh) & cites)
        have.update(fresh)
    return len(cites & have) / len(cites), len(have), len(cites & have), bool(first)


results = defaultdict(lambda: [[], [], [], []])
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer = V._tag_cosines(description, tags, p)[0]
    rows, d_description = list(answer["tags"]), np.asarray(answer["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    t_near, _ = WK.tags_nearness(layer, np.array(rows, dtype=np.float64))
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    border, scope = V.scope_by_name(q.question, p.tree, n)
    inside = np.flatnonzero(border)
    plain = np.zeros(n)
    plain[inside] = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    order = inside[np.lexsort((id_rank[inside], -plain[inside]))]
    units = [chunk_posts[c] for c in order.tolist()]
    got = deliver(units, cites)
    for k in range(4):
        results["chunks: the three routes added, whole chunks"][k].append(got[k])
    held_in = {}
    for c in inside.tolist():
        for r in chunk_posts[c]:
            if r in row_of:
                held_in.setdefault(r, c)              # the first chunk of the border that holds the record
    records = list(held_in)
    at = np.array([row_of[r] for r in records], dtype=np.int64)
    of_chunk = np.array([held_in[r] for r in records], dtype=np.int64)
    talks = defaultdict(list)
    for k, r in enumerate(records):
        talks[post[r]["talk"]].append(k)
    for key in talks:
        talks[key].sort(key=lambda k: (post[records[k]]["when"], records[k]))
    for label, text in (("as asked", q.question), ("without the name", without_the_names(q.question, scope["names_in_the_question"]))):
        near = (matrix[at] @ vector_of(text)).astype(np.float64)
        z_post, z_chunk = standing(near), standing(plain[inside])
        chunk_z = dict(zip(inside.tolist(), z_chunk.tolist()))
        with_chunk = z_post + np.array([chunk_z[int(c)] for c in of_chunk])
        tries = {"posts: every record by its nearness": [[records[k]] for k in np.argsort(-near, kind="stable")],
                 "posts+: nearness and the standing of its chunk": [[records[k]] for k in np.argsort(-with_chunk, kind="stable")]}
        keys = list(talks)
        best = np.array([near[talks[key]].max() for key in keys])
        two = np.array([np.sort(near[talks[key]])[-2:].mean() for key in keys])
        with_c = standing(best) + np.array([max(chunk_z[int(of_chunk[k])] for k in talks[key]) for key in keys])
        for name, value in (("talks: a conversation by its closest post", best), ("talks: by its two closest posts", two),
                            ("talks: by its closest post and its chunks' standing", with_c)):
            tries[name] = [[records[k] for k in talks[keys[j]]] for j in np.argsort(-value, kind="stable")]
        walk, seen = [], set()
        for k in np.argsort(-near, kind="stable"):
            key = post[records[k]]["talk"]
            if key not in seen:
                seen.add(key)
                walk.append([records[j] for j in talks[key]])
        tries["walks: posts by nearness, each bringing its conversation"] = walk
        for name, units in tries.items():
            got = deliver(units, cites)
            for k in range(4):
                results[f"{name}, the question {label}"][k].append(got[k])
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the border the product's name sets")
print("== context_recall_id | records delivered, the middle | cited among them, the middle | the first unit holds a cited record ==")
for name, (recall, sent, cited, first) in results.items():
    print(f"  {float(np.mean(recall)):.3f} | {np.median(sent):4.0f} | {np.median(cited):3.0f} | {int(sum(first))} of {len(first)}  {name}")
print("done", flush=True)
