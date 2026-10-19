"""The ties of a product's records to the rest of the product, read from the records alone (no
question, no gold): who made a thing and what a talk links to. Used by the rounds from 38 on.
No name of a channel, a person or a repository is read, and no number is given.

  a person          whoever posts in a channel, less those who post in every channel of the
                    product (someone who is everywhere ties nothing to anything; here that is
                    the account that opens the channels)
  a channel apart   none of its people post in another channel of the product or sit in a meeting
                    (in every product that is one planning channel: a team that does not continue)
  own pull request  its author posts in a channel of the product that is not apart; any other is
                    another project's
  a talk            the messages of one channel that follow each other closely. TALK (environment,
                    or the second argument of product) says how that is read:
                      gap    a new talk where the gap to the message before is one of the long
                             gaps of its channel (the logarithms of a channel's gaps cut in two
                             by least squares, `v4_walk.levels`)
                      count  from a message whose id counts 0 to the next that counts 0 (the
                             benchmark's own mark in a message's id)
                      day    one channel on one day
  a talk is about an own thing when a message of it links to an own pull request or to one of
  the product's documents; about another project's when it links to another project's pull
  request and to no own thing

apart(record id) is True for a record that is not the product's own work by those ties: another
project's pull request, a message of a talk about another project's, a message of a channel apart.
"""
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path("C:/Coding/exjobbet/GRAG-Job")
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
from artefact import v4_walk as WK  # noqa: E402

RAW = REPO / "data" / "raw" / "Salesforce__HERB" / "products"
URL = re.compile(r"https?://[^\s\"'<>\)\]|]+")
QUESTIONS = ("answerable_questions", "unanswerable_questions")     # never read
TALK = os.environ.get("TALK", "gap")


def clean(link):
    return link.rstrip(".,;:!?").rstrip("/").lower()


def product(name, talk=None, kept={}):
    talk = talk or TALK
    if (name, talk) in kept:
        return kept[(name, talk)]
    with open(RAW / f"{name}.json", encoding="utf-8") as handle:
        p = {k: v for k, v in json.load(handle).items() if k not in QUESTIONS}
    by_channel = defaultdict(list)
    for m in p["slack"]:
        by_channel[m["Channel"]["name"]].append(m)
    posters_by_channel = {c: {m["Message"]["User"]["userId"] for m in ms} for c, ms in by_channel.items()}
    everywhere = set.intersection(*posters_by_channel.values()) if len(posters_by_channel) > 1 else set()
    posters_by_channel = {c: who - everywhere for c, who in posters_by_channel.items()}
    in_meeting = set()
    for t in p["meeting_transcripts"]:
        in_meeting.update(t["participants"])
    stops = set()
    for channel, who in posters_by_channel.items():
        elsewhere = set(in_meeting).union(*[w for other, w in posters_by_channel.items() if other != channel])
        if who and not (who & elsewhere):
            stops.add(channel)
    posters = set().union(*[who for channel, who in posters_by_channel.items() if channel not in stops])
    pr_own = {r["id"]: r["user"]["login"] in posters for r in p["prs"]}
    pr_by_link = {clean(r["link"]): r["id"] for r in p["prs"]}
    doc_by_link = {clean(d["document_link"]): d["id"] for d in p["documents"]}
    talk_of, channel_of = {}, {}
    links = defaultdict(lambda: [0, 0, 0, set(), set()])   # own things, other projects', other links, own ids, other ids
    for channel, ms in by_channel.items():
        ms = sorted(ms, key=lambda m: m["Message"]["User"]["timestamp"])
        new = [False] * len(ms)
        if talk == "gap" and len(ms) > 1:
            t = np.array([datetime.fromisoformat(m["Message"]["User"]["timestamp"]).timestamp() for m in ms])
            gaps = np.log1p(np.maximum(np.diff(t), 0.))
            if np.unique(gaps).size > 1:
                new = [False] + (WK.levels(gaps, 2) == 1).tolist()
        run = 0
        for at, m in enumerate(ms):
            u = m["Message"]["User"]
            if talk == "day":
                key = (channel, u["timestamp"][:10])
            else:
                if at and (new[at] if talk == "gap" else m["id"].split("-")[1] == "0"):
                    run += 1
                key = (channel, run)
            talk_of[m["id"]] = key
            channel_of[m["id"]] = channel
            for link in map(clean, URL.findall(u["text"])):
                if link in doc_by_link:
                    links[key][0] += 1
                    links[key][3].add(doc_by_link[link])
                elif link in pr_by_link and pr_own[pr_by_link[link]]:
                    links[key][0] += 1
                    links[key][3].add(pr_by_link[link])
                elif link in pr_by_link:
                    links[key][1] += 1
                    links[key][4].add(pr_by_link[link])
                else:
                    links[key][2] += 1
    size, raw = {}, {}
    for kind in ("slack", "documents", "meeting_transcripts", "meeting_chats", "urls", "prs"):
        for r in p.get(kind) or []:
            size[str(r["id"])] = len(json.dumps(r, ensure_ascii=False))
            raw[str(r["id"])] = (kind, r)
    kept[(name, talk)] = {"stops": stops, "pr_own": pr_own, "talk_of": talk_of, "links": links,
                          "channel_of": channel_of, "size": size, "raw": raw, "everywhere": everywhere,
                          "channels": len(by_channel)}
    return kept[(name, talk)]


def tie(rid, P):
    """The record's tie in words."""
    if rid in P["pr_own"]:
        return "an own pull request" if P["pr_own"][rid] else "another project's pull request"
    if rid in P["talk_of"]:
        if P["channel_of"][rid] in P["stops"]:
            return "Slack: the planning team that does not continue"
        own, other = P["links"][P["talk_of"][rid]][:2]
        return ("Slack: a talk about an own thing" if own else
                "Slack: a talk about another project's pull request" if other else "Slack: a talk with no such link")
    return "another kind of record"


APART = {"another project's pull request", "Slack: a talk about another project's pull request",
         "Slack: the planning team that does not continue"}


def apart(rid, P):
    return tie(rid, P) in APART
