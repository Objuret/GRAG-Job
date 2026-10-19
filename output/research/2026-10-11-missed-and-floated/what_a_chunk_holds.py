"""For his 2026-10-11 goal "Explore this more to find the closest first gold": what each chunk of the
pool HOLDS, counted from its records, with no question and no gold: links, @mentions, people who
write in it, pull-request numbers, messages, messages by the channel's bot, conversations (one
channel, one day), characters. Written beside the per-chunk table of the hundred.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/what_a_chunk_holds.py <folder>
"""
import json
import os
import pickle
import re
import sys
import warnings
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
from arms.artefact_v2 import _load_verified_doc  # noqa: E402

OUT = Path(sys.argv[1])
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
MENTION = re.compile(r"@eid_[0-9a-f]+|@[A-Z][a-z]+ [A-Z][a-z]+")
PULL = re.compile(r"pull/\d+|PR ?#?\d+", re.IGNORECASE)
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?%?")
QUESTION = re.compile(r"\?")
BOT = "slack_admin_bot"


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


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


p = V.prepare_over_corpus("what a chunk holds")
n = len(p.chunk_ids)
names = ("links", "distinct links", "mentions", "people writing", "pull-request numbers", "numbers", "question marks",
         "messages", "messages by the bot", "conversations", "characters", "links per 1,000 characters",
         "mentions per 1,000 characters")
table = np.zeros((n, len(names)))
docs = {}
for i, row in enumerate(p.chunk_rows):
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    text, people, bots, talks = [], set(), 0, set()
    for r in recs:
        body = (r[loc["field"]][loc["char_range"][0]:loc["char_range"][1]] if "char_range" in loc
                else " ".join(strings(r)))
        text.append(body)
        user = (r.get("Message") or {}).get("User") or {}
        if "Message" in r:
            who = str(user.get("userId"))
            bots += int(who == BOT)
            if who != BOT:
                people.add(who)
            when = stamp(user.get("timestamp"))
            if when is not None:
                talks.add(((r.get("Channel") or {}).get("channelID"),
                           datetime.fromtimestamp(when, timezone.utc).date().isoformat()))
        for key in ("author", "user"):
            who = r.get(key)
            if isinstance(who, dict):
                who = who.get("login")
            if isinstance(who, str):
                people.add(who)
        for review in r.get("reviews") or []:
            who = (review.get("user") or {}).get("login") if isinstance(review, dict) else None
            if who:
                people.add(str(who))
        for who in r.get("participants") or []:
            people.add(str(who))
    whole = " ".join(text)
    links = URL.findall(whole)
    size = max(len(whole), 1)
    table[i] = (len(links), len(set(links)), len(MENTION.findall(whole)), len(people), len(PULL.findall(whole)),
                len(NUMBER.findall(whole)), len(QUESTION.findall(whole)), len(recs), bots, len(talks), len(whole),
                1000. * len(links) / size, 1000. * len(MENTION.findall(whole)) / size)
OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "what_a_chunk_holds.pkl", "wb") as handle:
    pickle.dump({"names": names, "table": table, "chunk_ids": list(p.chunk_ids)}, handle)
print(f"{n} chunks; the middle of each count: " + ", ".join(f"{name} {np.median(table[:, k]):.1f}" for k, name in enumerate(names)))
print("done", flush=True)
