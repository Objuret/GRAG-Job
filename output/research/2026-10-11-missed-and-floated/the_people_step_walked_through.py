"""The step that is in the arm (`HERB_V4_SCOPE_STEP=persons`), walked through on one product with
the arm's own functions, for his 2026-10-13 "explain it in detail first then so i can see if its
correct". No question and no gold: the step never reads the question. Prints what the graph
says about the product's people, what that makes of its channels and pull requests, how one
channel's messages fall into conversations, and what is handed over chunk by chunk.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_people_step_walked_through.py [product] [channel name]
"""
import json
import os
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ.pop("HERB_V4_SCOPE_STEP", None)          # the step as it stands

from arms import artefact_v4 as V  # noqa: E402
from graph.db import _driver  # noqa: E402

PRODUCT = sys.argv[1] if len(sys.argv) > 1 else "CoachForce"
CHANNEL = sys.argv[2] if len(sys.argv) > 2 else "bug-iangarcia-CoachForce"
assert V._scope_step()[0] == "persons"
p = V.prepare_over_corpus("the people step walked through")
rows = p.chunk_rows
inside = [i for i, row in enumerate(rows) if row["product"] == PRODUCT]
who = p.persons[PRODUCT]
print(f"\n==== {PRODUCT}: {len(inside)} chunks in the pool ====")

# 1. what the graph says, as the arm read it
driver = _driver()
with driver.session(database=V.DATABASE, default_access_mode="READ") as session:
    channel_rows = [dict(r) for r in session.run(V.CHANNEL_PEOPLE_CYPHER) if r["product"] == PRODUCT]
    meeting_rows = [dict(r) for r in session.run(V.MEETING_PEOPLE_CYPHER) if r["product"] == PRODUCT]
driver.close()
doc_cache = {}
name_of, messages_in = {}, Counter()
for i in inside:
    if rows[i]["kind"] == "slack_thread_batch":
        for record in V._pointed_records(rows[i], doc_cache):
            name_of[str(record["Channel"]["channelID"])] = record["Channel"]["name"]
            messages_in[str(record["Channel"]["channelID"])] += 1
met = {e for row in meeting_rows for e in row["people"] if e is not None}
print(f"\n== 1: the graph's people. Employees in the product's meetings: {len(met)}. Per channel: employees who post in it | of them "
      "also in another channel of the product or in its meetings | messages ==")
held = {str(r["channel"]): {str(e) for e in r["people"] if e is not None} for r in channel_rows}
for channel in sorted(held, key=lambda c: name_of.get(c, c)):
    people = held[channel]
    elsewhere = met.union(*[w for other, w in held.items() if other != channel])
    mark = "   <- APART" if channel in who["apart"] else ""
    print(f"   {len(people):3d} | {len(people & elsewhere):3d} | {messages_in[channel]:4d}  {name_of.get(channel, channel)}{mark}")
print(f"   the product's people (employees of its channels that are not apart, and of its meetings): {len(who['people'])}")

# 2. the pull requests by their author
book = V.own_work(inside, p, doc_cache)
repos = defaultdict(lambda: [0, 0])
for i in inside:
    if rows[i]["kind"] == "pr_batch":
        for record in V._pointed_records(rows[i], doc_cache):
            repos["/".join(record["link"].split("/")[3:5])][0 if book["own"][str(record["id"])] else 1] += 1
print(f"\n== 2: the pull request records by their author: own {sum(book['own'].values())}, another project's "
      f"{sum(1 for v in book['own'].values() if not v)}. By repository: own | another project's ==")
for repo, (own, other) in sorted(repos.items(), key=lambda kv: -sum(kv[1]))[:8]:
    print(f"   {own:3d} | {other:3d}  {repo}")
print(f"   ... {len(repos)} repositories in all")

# 3. the conversations
per_channel = defaultdict(list)
for key, records in book["messages"].items():
    per_channel[key[1]].append((key, records))
print(f"\n== 3: conversations (a channel's messages between its long gaps). Messages in a channel apart: {len(book['apart'])}. "
      "Per channel: conversations | of them about another project's pull request | messages in those ==")
for channel in sorted(per_channel, key=lambda c: name_of.get(c, c)):
    talks = per_channel[channel]
    other = [t for t in talks if t[0] in book["other"]]
    print(f"   {len(talks):3d} | {len(other):3d} | {sum(len(t[1]) for t in other):4d}  {name_of.get(channel, channel)}")
target = next(c for c, n in name_of.items() if n == CHANNEL)
line = sorted((r for t in per_channel[target] for r in t[1]), key=lambda r: V._seconds(r["Message"]["User"]["timestamp"]))
gaps = np.diff([V._seconds(r["Message"]["User"]["timestamp"]) for r in line])
numbers = [book["talk"][str(r["id"])][2] for r in line]
new = np.array(numbers[1:]) != np.array(numbers[:-1])
print(f"\n   {CHANNEL}: {len(line)} messages, {len(per_channel[target])} conversations. The gaps inside a conversation: "
      f"the longest {gaps[~new].max() / 60:.0f} minutes; the gaps where a new one starts: the shortest {gaps[new].min() / 3600:.1f} hours")
for key, records in sorted(per_channel[target], key=lambda t: t[0][2])[:9]:
    first = records[0]["Message"]["User"]
    kind = "about another project's: LEFT OUT" if key in book["other"] else "kept"
    print(f"   conversation {key[2]:2d} | {first['timestamp'][:16]} | {len(records):2d} messages | {kind:33s} | "
          f"{first['text'][:88]!r}")

# 4. what is handed over, chunk by chunk, down that channel's chunks in their own order
order = sorted((i for i in inside if rows[i]["kind"] == "slack_thread_batch" and target in rows[i]["channels"]),
               key=lambda i: json.loads(rows[i]["locator"]).get("index_start", 0))
# the arm hands over down the order of the whole border, and reads the product's pull requests and
# documents from it; so the channel's chunks go first here and the rest of the product follows
rest = [i for i in inside if i not in set(order)]
contexts, id_lists, context_ids, budget, delivered, handed = V._hand_over(order + rest, p, None, len(inside), doc_cache)
at = {i: k for k, i in enumerate(delivered)}
print(f"\n== 4: {CHANNEL}, its {len(order)} chunks taken first, in their own order (no budget): for each chunk its messages by "
      "conversation, then what is handed over when its turn comes ==")
for i in order[:6]:
    mine = [str(r["id"]) for r in V._pointed_records(rows[i], doc_cache)]
    parts = Counter(book["talk"][m][2] for m in mine)
    said = ", ".join(f"conversation {n}: {c} messages" + (" (left out)" if (PRODUCT, target, n) in book["other"] else "")
                     for n, c in sorted(parts.items()))
    if i in at:
        k = at[i]
        ids = id_lists[k]
        gone = Counter(book["talk"][m][2] for m in ids)
        out = (f"handed over: {len(ids)} messages (" + ", ".join(f"conversation {n} whole: {c}" for n, c in sorted(gone.items()))
               + f"); {handed['per_chunk']['delivered_records_of_other_chunks'][k]} of them from other chunks; "
               f"{handed['per_chunk']['delivered_records_not_handed_over'][k]} of this chunk's messages not handed over with it; "
               f"{len(contexts[k]):,} characters against {len(V._resolve_chunk(rows[i], doc_cache)[0]):,} as it is")
    else:
        out = "handed over: nothing (its conversations are left out or went with an earlier chunk)"
    print(f"   chunk {rows[i]['chunkId'][:8]} | {len(mine)} messages: {said}\n        -> {out}")
print(f"\n   the whole product gone through this way: chunks with nothing handed over "
      f"{json.dumps(handed['record']['chunks_with_nothing_handed_over'])}; records left out "
      f"{json.dumps(handed['record']['records_left_out'])}; conversations handed over {handed['record']['conversations_handed_over']}; "
      f"texts {len(contexts)} of {len(inside)} chunks; characters {sum(len(c) for c in contexts):,} against "
      f"{sum(len(V._resolve_chunk(rows[i], doc_cache)[0]) for i in inside):,} as the chunks are")

# 5. two things the code takes for granted, checked over the whole pool
stamps, ids = Counter(), Counter()
for i, row in enumerate(rows):
    if "char_range" in json.loads(row["locator"]):
        continue
    for record in V._pointed_records(row, doc_cache):
        ids[(row["product"], str(record.get("id")))] += 1
        if row["kind"] == "slack_thread_batch":
            stamp = str(record["Message"]["User"]["timestamp"])
            stamps["with a zone" if stamp.endswith("Z") or "+" in stamp[10:] or stamp[10:].count("-") else "no zone"] += 1
by_id = Counter(rid for (_, rid), _ in ids.items())
print(f"\n== 5: checked over the pool: message times {dict(stamps)}; record ids that stand in more than one product: "
      f"{sum(1 for n in by_id.values() if n > 1)} of {len(by_id)}; record ids that stand twice inside one product: "
      f"{sum(1 for n in ids.values() if n > 1)} ==")
