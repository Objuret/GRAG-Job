"""Round 38, under his 2026-10-12 goal "solve this": what the look-alike chunks beside the gold are.

Read off the corpus with no question and no gold (and the benchmark's own paper, arXiv
2506.23139, names it): a product's file holds, beside the product's own work, material put there
as distraction: a second planning team that never continues (its people post nowhere else in the
product), pull requests of other projects (their authors post nowhere in the product) and the
talk about those in the product's own channels, public links. So a record is tied to the rest of
the product by its people and by what it links to, or it is not.

What is counted here, the hundred, inside the question's product, numbers only:
  1  the cited records by that tie
  2  every chunk by that tie: how many a question, share gold (a chunk of the product: 6%)
  3  the first 15 of the combo order as built: the chunks that are not gold, by that tie

The ties, all read from the records:
  own person      posts in a channel of the product that is not a planning channel, or is in a meeting
  planning channel of a team that does not continue: none of its posters is an own person
  own pull request: its author posts in the product's Slack; any other is another project's
  a talk          the messages of one channel on one day (as in the rounds before)
  a talk is about an own thing when a message of it links to an own pull request or to one of
  the product's documents; about another project's when it links to another project's pull
  request and to no own thing; else it has no such link
"""
import json
import pickle
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path[:0] = [r"C:\Coding\exjobbet\GRAG-Job\prod", r"C:\Coding\exjobbet\GRAG-Job\test"]
from artefact import v4_walk as WK  # noqa: E402

from explore import BUDGET, load, standing  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = Path(r"C:\Coding\exjobbet\GRAG-Job\data\raw\Salesforce__HERB\products")
T = load()
Q, KINDS, PARENTS = T["questions"], T["kind_names"], T["parent_names"]
URL = re.compile(r"https?://[^\s\"'<>\)\]|]+")


def clean(link):
    return link.rstrip(".,;:!?").rstrip("/").lower()


def product(name, kept={}):
    if name in kept:
        return kept[name]
    with open(RAW / f"{name}.json", encoding="utf-8") as handle:
        p = json.load(handle)
    posters_by_channel = defaultdict(set)
    for m in p["slack"]:
        who = m["Message"]["User"]["userId"]
        if who.startswith("eid_"):
            posters_by_channel[m["Channel"]["name"]].add(who)
    in_meeting = set()
    for t in p["meeting_transcripts"]:
        in_meeting.update(t["participants"])
    own_people = set(in_meeting)
    for channel, who in posters_by_channel.items():
        if not channel.startswith("planning-"):
            own_people |= who
    posters = set().union(*posters_by_channel.values())
    stops = {c for c, who in posters_by_channel.items() if c.startswith("planning-") and not (who & own_people)}
    pr_own = {r["id"]: r["user"]["login"] in posters for r in p["prs"]}
    pr_by_link = {clean(r["link"]): r["id"] for r in p["prs"]}
    doc_by_link = {clean(d["document_link"]): d["id"] for d in p["documents"]}
    talk_of, talk_links = {}, defaultdict(lambda: [0, 0, 0])   # own things, other projects' pull requests, other links
    channel_of = {}
    for m in p["slack"]:
        u = m["Message"]["User"]
        talk = (m["Channel"]["name"], u["timestamp"][:10])
        talk_of[m["id"]] = talk
        channel_of[m["id"]] = m["Channel"]["name"]
        for link in URL.findall(u["text"]):
            link = clean(link)
            if link in doc_by_link or (link in pr_by_link and pr_own[pr_by_link[link]]):
                talk_links[talk][0] += 1
            elif link in pr_by_link:
                talk_links[talk][1] += 1
            else:
                talk_links[talk][2] += 1
    kept[name] = {"stops": stops, "pr_own": pr_own, "talk_of": talk_of, "talk_links": talk_links,
                  "channel_of": channel_of, "channels": len(posters_by_channel)}
    return kept[name]


def tie_of_record(rid, kind, P):
    if kind == "pr_batch":
        return "an own pull request" if P["pr_own"][rid] else "another project's pull request"
    if kind == "slack_thread_batch":
        if P["channel_of"][rid] in P["stops"]:
            return "Slack: the planning team that does not continue"
        own, other, _ = P["talk_links"][P["talk_of"][rid]]
        return ("Slack: a talk about an own thing" if own else
                "Slack: a talk about another project's pull request" if other else "Slack: a talk with no such link")
    return {"document": "a document", "document_part": "a document", "meeting_transcript": "a meeting",
            "meeting_transcript_part": "a meeting", "meeting_chat_batch": "a meeting chat", "url_batch": "a url"}[kind]


def tie_of_chunk(records, kind, P):
    ties = Counter(tie_of_record(r, kind, P) for r in records)
    if kind == "pr_batch":
        own, other = ties["an own pull request"], ties["another project's pull request"]
        return ("pull requests: all own" if not other else "pull requests: all another project's" if not own
                else "pull requests: own and another project's")
    if kind == "slack_thread_batch":
        if ties["Slack: the planning team that does not continue"]:
            return "Slack: the planning team that does not continue"
        own, other = ties["Slack: a talk about an own thing"], ties["Slack: a talk about another project's pull request"]
        return ("Slack: talks about own things only" if own and not other else
                "Slack: talks about own things and about another project's" if own else
                "Slack: talks about another project's pull request, none about an own thing" if other else
                "Slack: no talk with such a link")
    return next(iter(ties))


def combo(d):
    D, Tg = np.asarray(d["question_bare"], dtype=np.float64), np.asarray(d["tags"], dtype=np.float64)
    step = (WK.levels(D, 5) + WK.levels(Tg, 5)).astype(np.float64)
    z = standing(D) + standing(Tg)
    hits = step <= 3 if (step <= 3).any() else step == step.min()
    ids = np.unique(d["parent"])
    held = np.array([int(hits[d["parent"] == a].sum()) for a in ids])
    total, last = 0, None
    for at in np.lexsort((ids, -held)):
        total += int(held[at])
        last = int(held[at])
        if total * 2 > int(held.sum()):
            break
    scope = np.isin(d["parent"], ids[held >= last])
    return np.lexsort((d["id_rank"], -z, ~scope, step))


with open(HERE / "first_gold_signals_tags__gold100.pkl", "rb") as handle:
    extra = pickle.load(handle)
cited_by, record_by = Counter(), Counter()
chunk_by, gold_by = Counter(), Counter()
top_by, top_gold_by = Counter(), Counter()
first_by = Counter()
stops_seen, products = [], set()
for qid, d in Q.items():
    d.update(extra[qid])
    name = qid.split("::")[0]
    P = product(name)
    if name not in products:
        products.add(name)
        stops_seen.append(len(P["stops"]))
    cited = set(d["cited_ids"])
    m = d["gold"].size
    tie = []
    for k in range(m):
        kind = KINDS[d["kind"][k]]
        for r in d["records"][k]:
            t = tie_of_record(r, kind, P)
            record_by[t] += 1
            cited_by[t] += r in cited
        tie.append(tie_of_chunk(d["records"][k], kind, P))
        chunk_by[tie[-1]] += 1
        gold_by[tie[-1]] += bool(d["gold"][k])
    order = combo(d)
    fits = np.cumsum(d["length"][order]) <= BUDGET
    kept = order[:int(fits.sum()) if fits.all() else int(np.argmin(fits))]
    for k in kept.tolist():
        top_by[tie[k]] += 1
        top_gold_by[tie[k]] += bool(d["gold"][k])
    first_by[(tie[int(order[0])], bool(d["gold"][order[0]]))] += 1
n = len(Q)
print(f"{n} questions over {len(products)} products; planning channels of a team that does not continue, a product: "
      f"{Counter(stops_seen).most_common()}")
print("\n== 1: the records of the product by their tie: records, a question | of them cited | share of the question's "
      "cited records ==")
total = sum(cited_by.values())
for t, count in sorted(record_by.items(), key=lambda kv: -cited_by[kv[0]]):
    print(f"  {count / n:7.1f} | {cited_by[t] / count:5.1%} | {cited_by[t] / total:5.1%}  {t}")
print("\n== 2: the chunks of the product by their tie: chunks, a question | share gold (a chunk of the product: "
      f"{sum(gold_by.values()) / sum(chunk_by.values()):.0%}) | share of the question's gold chunks ==")
total = sum(gold_by.values())
for t, count in sorted(chunk_by.items(), key=lambda kv: -gold_by[kv[0]]):
    print(f"  {count / n:6.1f} | {gold_by[t] / count:4.0%} | {gold_by[t] / total:4.0%}  {t}")
print(f"\n== 3: the chunks the combo order as built delivers ({sum(top_by.values()) / n:.1f} a question, "
      f"{sum(top_gold_by.values()) / sum(top_by.values()):.0%} gold): delivered, a question | share gold | "
      "delivered and not gold, a question ==")
for t, count in sorted(top_by.items(), key=lambda kv: -(kv[1] - top_gold_by[kv[0]])):
    print(f"  {count / n:5.2f} | {top_gold_by[t] / count:4.0%} | {(count - top_gold_by[t]) / n:5.2f}  {t}")
print("\n== the first chunk of the combo order by its tie: questions where it is gold | where it is not ==")
for t in sorted({t for t, _ in first_by}, key=lambda t: -(first_by[(t, True)] + first_by[(t, False)])):
    print(f"  {first_by[(t, True)]:3d} | {first_by[(t, False)]:3d}  {t}")
