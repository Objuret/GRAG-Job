"""His 2026-10-11 "dont you even understand what sphere of thinking this should be" and, long
before, "half the strength of a graph is being able to route/search based on relationships
instead of structures": what connects the gold posts of a question to each other, post to post.

A post is one record of the dataset (a Slack message, a document, a meeting transcript, a pull
request, a link record). Only the sections the graph's pool chunks point into are read; the
question and answer sections of a product file are never opened. Ties between two posts of one
product, read from the records' own fields:
  next in the channel   the message before or after it in the same Slack channel, by time
  shares its link       one post's text holds the link the other post owns (a document's or pull
                        request's own link), either way
  same link             both posts' texts hold the same owned link
  same person           the same user, author or pull request author
  next in time          the post before or after it in the product's whole timeline, any kind
  same day              the same calendar day
  same type             two documents of the same type, or two meetings of the same type

For each tie: from a gold post, how many posts one step reaches and how many of them are gold;
the same from a post that is not gold; how many gold posts have a gold post one step away. And
into how many separate pieces the gold posts of a question fall when only ties between gold posts
are followed.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/what_ties_the_gold_posts.py [gold100]
"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from graph.db import _driver  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")
TIES = ("next in the channel", "shares its link", "same link", "same person", "next in time", "same day", "same type")
CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)-[:product]->(p:Product) WHERE c.desc_emb IS NOT NULL
RETURN DISTINCT p.name AS product, f.rel_path AS relpath, f.sha256 AS sha256, c.section AS section
"""


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def clean(link):
    return link.rstrip(".,;:!?").rstrip("/").lower()


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


def person_of(record):
    user = ((record.get("Message") or {}).get("User") or {}).get("userId")
    if user:
        return str(user)
    if record.get("author"):
        return str(record["author"])
    login = (record.get("user") or {}).get("login") if isinstance(record.get("user"), dict) else None
    return str(login) if login else None


driver = _driver()
with driver.session(database=V.DATABASE) as session:
    rows = session.execute_read(lambda tx: [dict(r) for r in tx.run(CYPHER)])
driver.close()
files = defaultdict(lambda: {"sections": set()})
for row in rows:
    files[row["product"]].update(relpath=row["relpath"], sha256=row["sha256"])
    files[row["product"]]["sections"].add(row["section"])

docs, products = {}, {}
replies = Counter()
for product, spec in files.items():
    doc = _load_verified_doc(spec["relpath"], spec["sha256"], docs)
    posts = []
    for section in sorted(spec["sections"]):
        for record in doc[section]:
            if not isinstance(record, dict) or record.get("id") is None:
                continue
            message = record.get("Message") or {}
            when = (stamp((message.get("User") or {}).get("timestamp")) if "Message" in record
                    else stamp(record.get("date") if "date" in record else record.get("created_at")))
            owns = {clean(record[k]) for k in OWN if isinstance(record.get(k), str) and record[k].startswith("http")}
            text = " ".join(strings({k: v for k, v in record.items() if k not in OWN}))
            if "ThreadReplies" in record:
                replies["Slack posts"] += 1
                replies["with replies inside"] += int(bool(record.get("ThreadReplies")))
            posts.append({
                "id": str(record["id"]), "section": section, "when": when, "owns": owns,
                "mentions": {clean(u) for u in URL.findall(text)} - owns, "person": person_of(record),
                "channel": (record.get("Channel") or {}).get("channelID") if "Channel" in record else None,
                "type": record.get("type") or record.get("document_type"),
                "day": datetime.utcfromtimestamp(when).strftime("%Y-%m-%d") if when is not None else None,
            })
    index = {post["id"]: k for k, post in enumerate(posts)}
    ties = {name: [set() for _ in posts] for name in TIES}

    def pair(name, a, b):
        if a != b:
            ties[name][a].add(b)
            ties[name][b].add(a)

    by_channel = defaultdict(list)
    for k, post in enumerate(posts):
        if post["channel"] is not None:
            by_channel[post["channel"]].append(k)
    for members in by_channel.values():
        ordered = sorted(members, key=lambda k: (posts[k]["when"] is None, posts[k]["when"] or 0., k))
        for a, b in zip(ordered, ordered[1:]):
            pair("next in the channel", a, b)
    owner, holders = defaultdict(set), defaultdict(set)
    for k, post in enumerate(posts):
        for link in post["owns"]:
            owner[link].add(k)
    for k, post in enumerate(posts):
        for link in post["mentions"]:
            if link in owner:
                holders[link].add(k)
                for other in owner[link]:
                    pair("shares its link", k, other)
    for members in holders.values():
        members = sorted(members)
        for a in members:
            ties["same link"][a].update(m for m in members if m != a)
    for key, name in (("person", "same person"), ("day", "same day"), ("type", "same type")):
        groups = defaultdict(list)
        for k, post in enumerate(posts):
            if post[key] is not None and (key != "type" or post["section"] in ("documents", "meeting_transcripts")):
                groups[(post["section"], post[key]) if key == "type" else post[key]].append(k)
        for members in groups.values():
            for a in members:
                ties[name][a].update(m for m in members if m != a)
    timed = sorted((k for k, post in enumerate(posts) if post["when"] is not None), key=lambda k: (posts[k]["when"], k))
    for a, b in zip(timed, timed[1:]):
        pair("next in time", a, b)
    products[product] = (posts, index, ties)

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
step = {name: Counter() for name in TIES}
pieces = defaultdict(list)
gold_posts, unplaced, sections = [], 0, Counter()
for qid in wanted:
    q = by_id[qid]
    posts, index, ties = products[qid.split("::")[0]]
    gold = {index[c] for c in map(str, q.citations) if c in index}
    unplaced += sum(1 for c in map(str, q.citations) if c not in index)
    gold_posts.append(len(gold))
    sections.update(posts[k]["section"] for k in gold)
    for name in TIES:
        cell = step[name]
        for k in range(len(posts)):
            reached = ties[name][k]
            if not reached:
                continue
            hit = len(reached & gold)
            where = "gold" if k in gold else "other"
            cell[where, "posts with the tie"] += 1
            cell[where, "reached"] += len(reached)
            cell[where, "reached gold"] += hit
            cell[where, "with a gold post one step away"] += int(hit > 0)
        cell["gold", "all"] += len(gold)

    def fall_into(names):
        parent = {k: k for k in gold}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for k in gold:
            for name in names:
                for other in ties[name][k] & gold:
                    parent[find(k)] = find(other)
        return len({find(k) for k in gold})

    for label, names in (("next in the channel", ("next in the channel",)),
                         ("shares its link or same link", ("shares its link", "same link")),
                         ("channel and links", ("next in the channel", "shares its link", "same link")),
                         ("channel, links and next in time", ("next in the channel", "shares its link", "same link",
                                                             "next in time")),
                         ("channel, links and same type", ("next in the channel", "shares its link", "same link",
                                                          "same type")),
                         ("every tie but the person and the day", ("next in the channel", "shares its link", "same link",
                                                                  "next in time", "same type"))):
        pieces[label].append(fall_into(names))

m = len(wanted)
print(f"{SET}: {m} questions; gold posts per question, the middle {np.median(gold_posts):.0f} "
      f"({np.percentile(gold_posts, 25):.0f}-{np.percentile(gold_posts, 75):.0f}); cited ids not found among the posts "
      f"{unplaced}; gold posts by section: " + ", ".join(f"{k} {v}" for k, v in sections.most_common()))
print(f"Slack posts {replies['Slack posts']}, of them with replies inside the record {replies['with replies inside']}")
print("\n== one step along a tie: from a gold post, posts reached per post (mean) | of them gold | gold posts that "
      "have a gold post one step away || from a post that is not gold: reached per post | of them gold ==")
for name in TIES:
    cell = step[name]
    g_n, o_n = cell["gold", "posts with the tie"], cell["other", "posts with the tie"]
    g_r, o_r = cell["gold", "reached"], cell["other", "reached"]
    print(f"  {name}: {(g_r / g_n if g_n else 0):.1f} | {(cell['gold', 'reached gold'] / g_r if g_r else 0):.3f} | "
          f"{cell['gold', 'with a gold post one step away']} of {cell['gold', 'all']} || "
          f"{(o_r / o_n if o_n else 0):.1f} | {(cell['other', 'reached gold'] / o_r if o_r else 0):.4f}")
print("\n== the gold posts of a question, following only ties between gold posts: the pieces they fall into, the "
      "middle (a quarter - three quarters) ==")
for label, values in pieces.items():
    print(f"  {label}: {np.median(values):.0f} ({np.percentile(values, 25):.0f}-{np.percentile(values, 75):.0f}); "
          f"questions where they are one piece: {sum(1 for v in values if v == 1)}")
print("done", flush=True)
