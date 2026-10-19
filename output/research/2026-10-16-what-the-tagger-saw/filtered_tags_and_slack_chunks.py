"""Two counts on top of coverage_by_post.npz (run coverage_by_post.py first).
1. No gold: the graph's tags are fewer than the May tagger answered. The share of each post's words (weighted by
   rarity, as in coverage_by_post) carried by its chunk's description plus the graph's tags, against the description
   plus the May answer's own tags (unfiltered), and the same for an own tag standing in the post.
2. The hundred, ids only: Slack chunks that hold cited posts, split by whether any (and whether all) of their cited
   posts is covered (the description or the tags find the chunk first, or an own tag stands in the post): the
   chunk delivered, and its place in the arm's order.
Argument: the unzipped snapshot folder (git show bcc3156:backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip).

    .venv/Scripts/python.exe output/research/2026-10-16-what-the-tagger-saw/filtered_tags_and_slack_chunks.py <folder>
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
from graph.db import _driver, _readable  # noqa: E402
from harness import questions as HQ  # noqa: E402

folder = Path(sys.argv[1])
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
RUN = REPO / "output/k=chars/artefact_v4__gold100__cb72000__20261016T013552Z_influence_question"
TOKEN = re.compile(r"[a-z0-9]+(?:[_.\-][a-z0-9]+)*")


def words(text):
    return TOKEN.findall(text.lower())


def mid(values):
    if not len(values):
        return "-"
    q1, m, q3 = np.percentile(np.asarray(values, dtype=np.float64), [25, 50, 75])
    return f"{m:.2f} ({q1:.2f}-{q3:.2f})"


def share(flags):
    flags = list(flags)
    return f"{sum(flags)}/{len(flags)} ({100 * sum(flags) / len(flags):.0f}%)" if flags else "-"


z = np.load(HERE / "coverage_by_post.npz", allow_pickle=True)
chunk, position, m = z["chunk"], z["position"], z["posts_in_chunk"]
record = [str(r) for r in z["record"]]
kinds, chunk_ids = [str(k) for k in z["kinds"]], [str(c) for c in z["chunk_ids"]]
findable, desc_place, tags_place, own_tag = z["findable"], z["desc_place"], z["tags_place"], z["own_tag"]

corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
texts = corpus["texts"]
post_text = [str(texts[row_of[r]]).lower() for r in record]
post_words = [set(words(t)) for t in post_text]
df = Counter(w for ws in post_words for w in ws)
idf = {w: math.log(len(record) / d) for w, d in df.items()}
desc = {}
for line in (KEPT / "descriptions.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        desc[str(r["id"])] = r["text"]
dr = _driver()
with dr.session(database="herb-eval-volmax") as s:
    graph_tags = defaultdict(list)
    for r in s.run("MATCH (c:Chunk)-[:HAS_TAG]->(t:Tag) RETURN c.chunk_id AS c, t.name AS t"):
        graph_tags[r["c"]].append(_readable(r["t"]))
dr.close()
may_tags = {}
for line in (folder / "io.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    if r["stage"] == "extract" and r.get("response_tool_input"):
        may_tags[r["target_id"]] = [str(t) for t in r["response_tool_input"].get("tags") or []]


def carried(i, tags):
    ws = post_words[i]
    cover = set(words(desc.get(chunk_ids[int(chunk[i])], ""))) | {w for t in tags for w in words(t)}
    total = sum(idf[w] for w in ws)
    return sum(idf[w] for w in ws if w in cover) / total if total else 0.0


by_chunk = defaultdict(list)
for i in range(len(record)):
    by_chunk[int(chunk[i])].append(i)
patterns = {}


def own_tags(members, tags):
    out = set()
    for t in tags:
        pat = patterns.get(t.lower())
        if pat is None:
            pat = patterns[t.lower()] = re.compile(r"(?<![0-9a-z])" + re.escape(t.lower()) + r"(?![0-9a-z])")
        inside = [i for i in members if pat.search(post_text[i])]
        if 0 < len(inside) < len(members):
            out.update(inside)
    return out


rows = defaultdict(list)
for c, members in by_chunk.items():
    if len(members) < 2:
        continue
    cid = chunk_ids[c]
    g, may = graph_tags.get(cid, []), may_tags.get(cid, [])
    own_g, own_m = own_tags(members, g), own_tags(members, may)
    for i in members:
        if not findable[i]:
            continue
        k = position[i]
        place = "first" if k == 0 else "last" if k == m[i] - 1 else "in between"
        rows[(kinds[c], place)].append((carried(i, g), carried(i, may), i in own_g, i in own_m, len(g), len(may)))
print("== findable posts of chunks with two or more posts: words carried (rarity-weighted share) by the description "
      "plus the graph's tags | plus the May answer's tags | an own tag stands in it, graph | May | tags a chunk, "
      "graph | May (middles) ==")
for (kd, place) in sorted(rows):
    g = rows[(kd, place)]
    print(f"   {kd} | {place} | {len(g)} posts | {mid([x[0] for x in g])} | {mid([x[1] for x in g])} | "
          f"{share(x[2] for x in g)} | {share(x[3] for x in g)} | {np.median([x[4] for x in g]):.0f} | "
          f"{np.median([x[5] for x in g]):.0f}")
dropped = Counter()
for cid, may in may_tags.items():
    kept = {t.lower() for t in graph_tags.get(cid, [])}
    for t in may:
        if t.lower() not in kept:
            kind = ("a link" if re.search(r"https?://|github\.com|\.com/", t) else
                    "an id (EMP_, eid_)" if re.search(r"\b(emp_|eid_)", t.lower()) else
                    "a pull request number" if re.search(r"\b(pr|pull request)\s*#?\d+", t.lower()) else
                    "a date" if re.search(r"\b\d{4}-\d{2}(-\d{2})?\b", t) else
                    "a single word starting with a capital (a name?)" if re.fullmatch(r"[A-Z][a-z]+", t) else "other")
            dropped[kind] += 1
print("\n== May answer tags not on the graph's chunk, by what they look like (a rough sort by pattern) ==")
print("   " + ", ".join(f"{k} {v}" for k, v in dropped.most_common()))

wanted = [json.loads(line)["id"] for line in (REPO / "data/gold100.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
cites = {q.id: {str(c) for c in q.citations} for q in HQ.load_questions()}
chunk_at = {cid: c for c, cid in enumerate(chunk_ids)}
post_at = defaultdict(dict)
for i, rid in enumerate(record):
    post_at[int(chunk[i])][rid] = i
groups = defaultdict(list)
for line in (RUN / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    if r["id"] not in cites:
        continue
    rk = r["meta"]["ranking"]
    ordered = [chunk_at[str(x)] for x in rk["ordered_chunk_ids"]]
    delivered = {chunk_at[str(x)] for x in rk["delivered_chunk_ids"]}
    for place, c in enumerate(ordered, start=1):
        if kinds[c] != "slack_thread_batch" or len(by_chunk[c]) < 2:
            continue
        cited = [post_at[c][rid] for rid in cites[r["id"]] if rid in post_at[c]]
        if not cited:
            continue
        cov = [desc_place[i] == 1 or tags_place[i] == 1 or own_tag[i] for i in cited]
        groups["any cited post covered" if any(cov) else "no cited post covered"].append((c in delivered, place))
        groups["every cited post covered" if all(cov) else "not every cited post covered"].append((c in delivered, place))
print("\n== the hundred: Slack chunks that hold cited posts (a chunk counted once a question): chunks | delivered | "
      "place in the arm's order, middle (quartiles) ==")
for name in ("any cited post covered", "no cited post covered", "every cited post covered",
             "not every cited post covered"):
    g = groups[name]
    print(f"   {name}: {len(g)} | {share(x[0] for x in g)} | {mid([x[1] for x in g]).replace('.00', '')}")
print("done")
