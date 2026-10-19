"""What a chunk's tags and description cover, post by post (2026-10-16, his "if i am to act on this, i near
real actual hard data and you need to actually diagnose the exact issue"). Over the whole pool, no question
read. The last part uses the citation ids of the hundred and the arm's default run of it, ids only.

A post is one record of a chunk (a Slack message, a pull request, a URL, a meeting-chat line, a whole document
or transcript). Its text is the vector baseline's unit text for that record (corpus_passage.npz `texts`), its
vector the baseline's record vector (passage), the descriptions' and tags' vectors the 2026-10-07 passage ones.
Per post:
  findable    its own words (BM25, k1 1.2, b 0.75) against the chunk texts of its product put its own chunk
              first; a post that does not (a "thanks", a bare link) is content-poor and counted apart
  desc_place  its own vector against the descriptions of its product's chunks: the place of its own chunk
              (1 = its chunk's description is the nearest of them all)
  tags_place  the same through each chunk's tags (a chunk's nearest tag)
  own_tag     a tag of its chunk stands in its text (whole words, any case) and not in every post of the chunk
  idf_share   the share of its distinct words, each weighted by its rarity over all posts of the pool, that
              stand in its chunk's tags or description

    .venv/Scripts/python.exe output/research/2026-10-16-what-the-tagger-saw/coverage_by_post.py
"""
import json
import math
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import sparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc, _resolve_chunk  # noqa: E402
from harness import questions as HQ  # noqa: E402

KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
RUN = REPO / "output/k=chars/artefact_v4__gold100__cb72000__20261016T013552Z_influence_question"
TOKEN = re.compile(r"[a-z0-9]+(?:[_.\-][a-z0-9]+)*")
K1, B = 1.2, 0.75


def unit_rows(m):
    m = np.asarray(m, dtype=np.float32)
    return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-12)


def words(text):
    return TOKEN.findall(text.lower())


def mid(values):
    if not len(values):
        return "-"
    q1, m, q3 = np.percentile(np.asarray(values, dtype=np.float64), [25, 50, 75])
    return f"{m:.2f} ({q1:.2f}-{q3:.2f})" if max(abs(q1), abs(q3)) <= 1 else f"{m:.0f} ({q1:.0f}-{q3:.0f})"


def share(flags):
    flags = list(flags)
    return f"{sum(flags)}/{len(flags)} ({100 * sum(flags) / len(flags):.0f}%)" if flags else "-"


p = V.prepare_over_corpus("coverage by post")
layer, n = p.layer, len(p.chunk_ids)
kind_names, kind_of = layer["kind_names"], layer["kind"]
kind = [kind_names[kind_of[c]] for c in range(n)]
chunk_at = {str(cid): c for c, cid in enumerate(p.chunk_ids)}

# the posts of every chunk, in the chunk's order
docs, record_ids, ranged = {}, [], []
for row in p.chunk_rows:
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    record_ids.append(list(dict.fromkeys(str(r["id"]) for r in recs if r.get("id") is not None)))
    ranged.append("char_range" in loc)
chunk_text = [_resolve_chunk(dict(row), docs)[0] for row in p.chunk_rows]

corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
corpus_text = corpus["texts"]
M = unit_rows(corpus["matrix"])
dp = np.load(KEPT / "descriptions_passage.npz", allow_pickle=True)
at = {str(c): k for k, c in enumerate(dp["ids"])}
DP = unit_rows(dp["matrix"][[at[str(c)] for c in p.chunk_ids]])
tp = np.load(KEPT / "tags_passage.npz", allow_pickle=True)
tag_at = {str(t): k for k, t in enumerate(tp["ids"])}
TP = unit_rows(tp["matrix"])
tag_row = np.array([tag_at.get(str(t), -1) for t in p.graph_tags], dtype=np.int64)
desc_text = {}
for line in (KEPT / "descriptions.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        desc_text[str(r["id"])] = r["text"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
tags_of = defaultdict(list)
for e in range(len(et)):
    tags_of[int(ec[e])].append(int(et[e]))
readable = [V._readable(str(t)).lower() for t in p.graph_tags]

# a post: (chunk, place in the chunk, posts in the chunk, record id); a whole document or transcript is one post
posts = []
for c in range(n):
    rids = [r for r in record_ids[c] if r in row_of]
    if ranged[c] or not rids:
        continue
    for k, rid in enumerate(rids):
        posts.append((c, k, len(rids), rid))
post_words = [set(words(str(corpus_text[row_of[rid]]))) for _, _, _, rid in posts]
df = Counter(w for ws in post_words for w in ws)
idf = {w: math.log(len(posts) / d) for w, d in df.items()}
cover_words = {c: set(words(desc_text.get(str(p.chunk_ids[c]), ""))) | {w for t in tags_of[c] for w in words(readable[t])}
               for c in range(n)}

idf_share, own_tag = np.zeros(len(posts)), np.zeros(len(posts), dtype=bool)
patterns = {}
for i, (c, k, m, rid) in enumerate(posts):
    ws = post_words[i]
    total = sum(idf[w] for w in ws)
    idf_share[i] = sum(idf[w] for w in ws if w in cover_words[c]) / total if total else 0.0
by_chunk = defaultdict(list)
for i, (c, k, m, rid) in enumerate(posts):
    by_chunk[c].append(i)
for c, members in by_chunk.items():
    if len(members) < 2:
        continue
    texts = [str(corpus_text[row_of[posts[i][3]]]).lower() for i in members]
    for t in tags_of[c]:
        pat = patterns.get(t)
        if pat is None:
            pat = patterns[t] = re.compile(r"(?<![0-9a-z])" + re.escape(readable[t]) + r"(?![0-9a-z])")
        inside = [j for j, tx in enumerate(texts) if pat.search(tx)]
        if 0 < len(inside) < len(members):
            for j in inside:
                own_tag[members[j]] = True

# findable, desc_place, tags_place: inside each product
findable = np.zeros(len(posts), dtype=bool)
desc_place = np.zeros(len(posts), dtype=np.int64)
tags_place = np.zeros(len(posts), dtype=np.int64)
product_of = np.full(n, -1, dtype=np.int64)
products = list(V.tree_level(p.tree, "product"))
for b, (_, chunks) in enumerate(products):
    inside = np.asarray(chunks, dtype=np.int64)
    product_of[inside] = b
    local = {int(c): j for j, c in enumerate(inside)}
    mine = [i for i, (c, _, _, _) in enumerate(posts) if int(c) in local]
    if not mine:
        continue
    # BM25 of each post's words against the product's chunk texts
    docs_w = [Counter(words(chunk_text[int(c)])) for c in inside]
    vocab = {w: j for j, w in enumerate(sorted({w for d in docs_w for w in d}))}
    dl = np.array([sum(d.values()) for d in docs_w], dtype=np.float64)
    avg = dl.mean()
    dfp = Counter(w for d in docs_w for w in d)
    rows_, cols_, vals_ = [], [], []
    for j, d in enumerate(docs_w):
        for w, tf in d.items():
            weight = math.log(1 + (len(inside) - dfp[w] + 0.5) / (dfp[w] + 0.5))
            rows_.append(j)
            cols_.append(vocab[w])
            vals_.append(weight * tf * (K1 + 1) / (tf + K1 * (1 - B + B * dl[j] / avg)))
    W = sparse.csr_matrix((vals_, (rows_, cols_)), shape=(len(inside), len(vocab)))
    qr, qc = [], []
    for r, i in enumerate(mine):
        for w in post_words[i]:
            if w in vocab:
                qr.append(r)
                qc.append(vocab[w])
    Q = sparse.csr_matrix((np.ones(len(qr)), (qr, qc)), shape=(len(mine), len(vocab)))
    S_bm = (Q @ W.T).toarray()
    R = M[[row_of[posts[i][3]] for i in mine]]
    S_d = R @ DP[inside].T
    sel = np.flatnonzero(np.isin(ec, inside) & (tag_row[et] >= 0))
    tags_here, inv = np.unique(et[sel], return_inverse=True)
    TS = R @ TP[tag_row[tags_here]].T
    chunk_local = np.array([local[int(c)] for c in ec[sel]], dtype=np.int64)
    S_t = np.full((len(mine), inside.size), -np.inf, dtype=np.float32)
    for j in range(inside.size):
        cols = np.flatnonzero(chunk_local == j)
        if cols.size:
            S_t[:, j] = TS[:, inv[cols]].max(axis=1)
    for r, i in enumerate(mine):
        own = local[int(posts[i][0])]
        findable[i] = (S_bm[r] > S_bm[r, own]).sum() == 0 and S_bm[r, own] > 0
        desc_place[i] = 1 + int((S_d[r] > S_d[r, own]).sum())
        tags_place[i] = 1 + int((S_t[r] > S_t[r, own]).sum())

np.savez_compressed(HERE / "coverage_by_post.npz", chunk=np.array([q[0] for q in posts]),
                    position=np.array([q[1] for q in posts]), posts_in_chunk=np.array([q[2] for q in posts]),
                    record=np.array([q[3] for q in posts]), findable=findable, desc_place=desc_place,
                    tags_place=tags_place, own_tag=own_tag, idf_share=idf_share,
                    chunk_ids=np.array(p.chunk_ids), kinds=np.array(kind))


def where(i):
    c, k, m, _ = posts[i]
    if m == 1:
        return "the only post"
    return "first" if k == 0 else "last" if k == m - 1 else "in between"


print(f"\npool: {n} chunks, {len(posts)} posts with a baseline text "
      f"({sum(1 for c in range(n) if ranged[c])} document and transcript parts left out: they are pieces of one record)")
print("\n== every post, by kind of chunk and place in it; findable = its own words find its own chunk first "
      "(BM25 inside the product) ==")
print("   kind | place | posts | findable | of the findable: description nearest its own chunk | tags nearest "
      "its own chunk | an own tag stands in it | idf_share middle (quartiles)")
groups = defaultdict(list)
for i in range(len(posts)):
    groups[(kind[posts[i][0]], where(i))].append(i)
order = ["first", "in between", "last", "the only post"]
for kd in kind_names:
    for w in order:
        g = groups.get((kd, w))
        if not g:
            continue
        f = [i for i in g if findable[i]]
        print(f"   {kd} | {w} | {len(g)} | {share(findable[i] for i in g)} | "
              f"{share(desc_place[i] == 1 for i in f)} | {share(tags_place[i] == 1 for i in f)} | "
              f"{share(own_tag[i] for i in f)} | {mid([idf_share[i] for i in f])}")

print("\n== chunks with two or more findable posts: how many of a chunk's findable posts its description finds first "
      "(desc_place 1) ==")
for kd in kind_names:
    per = []
    for c, members in by_chunk.items():
        if kind[c] != kd:
            continue
        f = [i for i in members if findable[i]]
        if len(f) >= 2:
            per.append((sum(desc_place[i] == 1 for i in f), len(f)))
    if not per:
        continue
    none = sum(1 for a, m in per if a == 0)
    one = sum(1 for a, m in per if a == 1)
    allp = sum(1 for a, m in per if a == m)
    print(f"   {kd}: {len(per)} chunks, findable posts a chunk {mid([m for a, m in per])}; the description finds "
          f"none first {none}, exactly one {one}, all {allp}; share found first, middle {mid([a / m for a, m in per])}")

print("\n== the same through the tags (tags_place 1) ==")
for kd in kind_names:
    per = []
    for c, members in by_chunk.items():
        if kind[c] != kd:
            continue
        f = [i for i in members if findable[i]]
        if len(f) >= 2:
            per.append((sum(tags_place[i] == 1 for i in f), len(f)))
    if not per:
        continue
    print(f"   {kd}: {len(per)} chunks; the tags find none first {sum(1 for a, m in per if a == 0)}, exactly one "
          f"{sum(1 for a, m in per if a == 1)}, all {sum(1 for a, m in per if a == m)}; share found first, middle "
          f"{mid([a / m for a, m in per])}")

# the hundred: citation ids and the arm's default run, ids only
wanted = [json.loads(line)["id"] for line in (REPO / "data/gold100.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
cites = {q.id: {str(c) for c in q.citations} for q in HQ.load_questions()}
run = {}
for line in (RUN / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        rk = r["meta"]["ranking"]
        run[r["id"]] = (set(map(str, r["context_ids"])), [chunk_at[str(x)] for x in rk["ordered_chunk_ids"]],
                        {chunk_at[str(x)] for x in rk["delivered_chunk_ids"]})
recall = [len(cites[q] & run[q][0]) / len(cites[q]) for q in wanted if cites[q]]
print(f"\n== the hundred, run {RUN.name}: context_recall_id recomputed from its delivered ids "
      f"{np.mean(recall):.4f} ==")
post_at = defaultdict(dict)
for i, (c, k, m, rid) in enumerate(posts):
    post_at[c][rid] = i
cited_rows = []
not_in_order = 0
for q in wanted:
    delivered, ordered, chunks_delivered = run[q]
    place = {c: j + 1 for j, c in enumerate(ordered)}
    for rid in cites[q]:
        holders = [c for c in ordered if rid in post_at.get(c, {})]
        ranged_holders = [c for c in ordered if ranged[c] and rid in record_ids[c]]
        if holders:
            c = min(holders, key=lambda x: place[x])
            cited_rows.append((q, rid, c, post_at[c][rid], rid in delivered, c in chunks_delivered, place[c]))
        elif ranged_holders:
            c = min(ranged_holders, key=lambda x: place[x])
            cited_rows.append((q, rid, c, None, rid in delivered, c in chunks_delivered, place[c]))
        else:
            not_in_order += 1
print(f"   cited records {sum(len(cites[q]) for q in wanted)}: in a chunk of the product's order {len(cited_rows)}, "
      f"not {not_in_order}")
print("\n== cited records by kind of chunk and how their post is covered: delivered by the arm | its chunk's place "
      "in the arm's order, middle (quartiles) ==")
for kd in kind_names:
    rows = [r for r in cited_rows if kind[r[2]] == kd]
    if not rows:
        continue
    print(f"   {kd}: {len(rows)} cited records, delivered {share(r[4] for r in rows)}, place {mid([r[6] for r in rows])}")
    whole = [r for r in rows if r[3] is not None]
    if not whole:
        continue
    multi = [r for r in whole if posts[r[3]][2] > 1]
    if not multi:
        continue
    for name, test in (("description finds its chunk first", lambda i: desc_place[i] == 1),
                       ("tags find its chunk first", lambda i: tags_place[i] == 1),
                       ("an own tag stands in it", lambda i: own_tag[i]),
                       ("last post of the chunk", lambda i: posts[i][1] == posts[i][2] - 1)):
        yes = [r for r in multi if test(r[3])]
        no = [r for r in multi if not test(r[3])]
        print(f"      {name}: yes {len(yes)}, delivered {share(r[4] for r in yes)}, place {mid([r[6] for r in yes])}"
              f" | no {len(no)}, delivered {share(r[4] for r in no)}, place {mid([r[6] for r in no])}")
missed = [r for r in cited_rows if not r[4]]
print(f"\n== cited records the arm does not deliver: {len(missed)} of {len(cited_rows)} ==")
for kd in kind_names:
    rows = [r for r in missed if kind[r[2]] == kd]
    if not rows:
        continue
    multi = [r for r in rows if r[3] is not None and posts[r[3]][2] > 1]
    bare = [r for r in multi if desc_place[r[3]] != 1 and tags_place[r[3]] != 1 and not own_tag[r[3]]]
    print(f"   {kd}: {len(rows)} missed; in a chunk of two or more posts {len(multi)}, of those neither description "
          f"nor tags find it first and no own tag stands in it {len(bare)}")
print("done", flush=True)
