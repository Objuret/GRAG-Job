"""One worked example of his 2026-10-13 combo ("nearness by time and posts the same author is part
of", "from the SAME conversation", "the COMBO at the same time"), on the corpus alone: no
question, no gold. Every thing a person takes part in (a conversation, an own pull request, a
document, a meeting) is put in the order of time, per person. Standing on one conversation,
each of its writers points at the thing they were part of just before and just after.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_persons_line_of_time_example.py [product] [channel] [conversation number]
"""
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ties as TI  # noqa: E402

PRODUCT = sys.argv[1] if len(sys.argv) > 1 else "CoachForce"
CHANNEL = sys.argv[2] if len(sys.argv) > 2 else "bug-iangarcia-CoachForce"
NUMBER = int(sys.argv[3]) if len(sys.argv) > 3 else 4
P = TI.product(PRODUCT)


def seconds(stamp):
    return (datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()


things = []
talks = defaultdict(list)
for rid, t in P["talk_of"].items():
    if not TI.apart(rid, P):
        talks[t].append(rid)
for t, rids in talks.items():
    rids.sort(key=lambda r: P["raw"][r][1]["Message"]["User"]["timestamp"])
    first = P["raw"][rids[0]][1]["Message"]["User"]
    things.append({"what": f"conversation in {t[0]}", "key": t, "when": seconds(first["timestamp"]), "day": first["timestamp"][:10],
                   "who": {P["raw"][r][1]["Message"]["User"]["userId"] for r in rids} - P["everywhere"],
                   "says": first["text"][:95], "size": f"{len(rids)} messages"})
for rid, (kind, rec) in P["raw"].items():
    if kind == "prs" and P["pr_own"][rid]:
        things.append({"what": "own pull request", "key": rid, "when": seconds(rec["created_at"]), "day": rec["created_at"][:10],
                       "who": {rec["user"]["login"]} | {v["user"]["login"] for v in rec["reviews"]}, "says": rec["title"][:95],
                       "size": f"{len(rec['reviews'])} reviews"})
    elif kind == "documents":
        things.append({"what": "document", "key": rid, "when": seconds(rec["date"]), "day": str(rec["date"])[:10],
                       "who": {rec["author"]}, "says": rec["type"], "size": f"{len(rec['content']):,} characters"})
    elif kind == "meeting_transcripts":
        things.append({"what": "meeting", "key": rid, "when": seconds(rec["date"]), "day": str(rec["date"])[:10],
                       "who": set(rec["participants"]), "says": rec["document_type"], "size": f"{len(rec['participants'])} participants"})
lines = defaultdict(list)
for i, thing in enumerate(things):
    for person in thing["who"]:
        lines[person].append(i)
for line in lines.values():
    line.sort(key=lambda i: (things[i]["when"], i))
channel_talks = sorted((t for t in talks if t[0] == CHANNEL), key=lambda t: t[1])
start = next(i for i, thing in enumerate(things) if thing["key"] == channel_talks[NUMBER])
here = things[start]
print(f"{PRODUCT}: {len(things)} things on {len(lines)} persons' lines of time")
print(f"\nSTANDING ON: {here['what']}, {here['day']}, {here['size']}, {len(here['who'])} writers\n   {here['says']!r}")
pointed = defaultdict(list)
for person in sorted(here["who"]):
    line = lines[person]
    at = line.index(start)
    for label, other in (("just before", line[at - 1] if at else None), ("just after", line[at + 1] if at + 1 < len(line) else None)):
        if other is not None:
            pointed[other].append(f"{person} {label}")
print(f"\nIT POINTS AT {len(pointed)} things (each writer's thing just before and just after, on that writer's own line):")
for other, why in sorted(pointed.items(), key=lambda kv: things[kv[0]]["when"]):
    thing = things[other]
    days = (thing["when"] - here["when"]) / 86400.
    print(f"   {thing['day']} ({days:+.1f} days) | {thing['what']}, {thing['size']} | pointed at by {len(why)} writer(s)\n        {thing['says']!r}")
