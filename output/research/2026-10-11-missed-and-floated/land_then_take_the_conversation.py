"""His 2026-10-11 "a 'nearest' chunk etc could be used for search-start or search-range for that
specific person or whatever pointer" and "an agnostic search that, if it's correct chunk, stops
there, but if not, actually does a search and semi-deterministically actually find", after
`what_ties_the_gold_posts` (from a gold post the next message in the channel is gold 87%).

On the hundred, inside the gold's branch, cached query side, no model call. The search starts
where the first order lands (the three routes' standings added, chunk by chunk from the nearest).
What is delivered for a chunk:
  the chunk            the chunk as it is (what the arm does today)
  its conversations    for a Slack chunk every conversation one of its messages belongs to, whole,
                       and the records whose link a message of it shares; any other chunk as it is
  its main conversation  the same with only the conversation most of the chunk's messages are in
A conversation is the messages of one channel that follow each other closely in time. Two
readings of "closely": the same calendar day; and no gap in the larger of the two clusters the
channel gaps of the product fall into on the logarithm of the gap (least squares, `v4_walk.levels`).

Delivery stops at the first unit that does not fit in 72,000 characters, a record counted at the
length of its own text. Printed: the cited records delivered (context_recall_id), the records
delivered and how many of them are cited. The construction is the agent's reading of his words.

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/land_then_take_the_conversation.py [gold100]
"""
import json
import math
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
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
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")
READINGS = ("the same day", "no large gap")


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


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("land then take the conversation")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, chunk_records, chunk_ids, length, chunk_section, chunk_file = {}, [], [], np.zeros(n, dtype=np.int64), [], []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    length[i] = len(text)
    chunk_ids.append([str(x) for x in ids])
    loc = json.loads(row["locator"])
    chunk_section.append(loc["section"])
    chunk_file.append((row["relpath"], row["sha256"]))
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
record_sets = [frozenset(ids) for ids in chunk_ids]

# the posts of a product file, by id: size, channel, time, what it owns and what it holds
files = {}
for (relpath, sha), section in set(zip(chunk_file, chunk_section)):
    files.setdefault((relpath, sha), set()).add(section)
posts = {}                      # (relpath) -> id -> post
talks = {}                      # (relpath, reading) -> id -> conversation key ; and conversation -> ids in order
for (relpath, sha), sections in files.items():
    doc = _load_verified_doc(relpath, sha, docs)
    here, owner = {}, defaultdict(set)
    for section in sorted(sections):
        for record in doc[section]:
            if not isinstance(record, dict) or record.get("id") is None:
                continue
            rid = str(record["id"])
            message = record.get("Message") or {}
            owns = {clean(record[k]) for k in OWN if isinstance(record.get(k), str) and record[k].startswith("http")}
            text = " ".join(strings({k: v for k, v in record.items() if k not in OWN}))
            here[rid] = {"size": len(json.dumps(record, ensure_ascii=False)) + 1, "owns": owns,
                         "mentions": {clean(u) for u in URL.findall(text)} - owns,
                         "channel": (record.get("Channel") or {}).get("channelID") if "Channel" in record else None,
                         "when": stamp((message.get("User") or {}).get("timestamp")) if "Message" in record else None}
            for link in owns:
                owner[link].add(rid)
    for post in here.values():
        post["points at"] = sorted({o for link in post["mentions"] for o in owner.get(link, ())})
    posts[relpath] = here
    by_channel = defaultdict(list)
    for rid, post in here.items():
        if post["channel"] is not None and post["when"] is not None:
            by_channel[post["channel"]].append(rid)
    gaps = []
    for channel, members in by_channel.items():
        members.sort(key=lambda r: (here[r]["when"], r))
        gaps += [here[b]["when"] - here[a]["when"] for a, b in zip(members, members[1:])]
    logs = np.log1p(np.maximum(np.asarray(gaps, dtype=np.float64), 0.))
    level = WK.levels(logs, 2) if logs.size else np.zeros(0, dtype=np.int64)
    large = float(logs[level == 1].min()) if (level == 1).any() and (level == 2).any() else math.inf
    for reading in READINGS:
        of, held = {}, {}
        for channel, members in by_channel.items():
            run = 0
            for k, rid in enumerate(members):
                if k:
                    before = here[members[k - 1]]["when"]
                    if reading == "the same day":
                        new = (datetime.fromtimestamp(before, timezone.utc).date()
                               != datetime.fromtimestamp(here[rid]["when"], timezone.utc).date())
                    else:
                        new = math.log1p(max(here[rid]["when"] - before, 0.)) >= large
                    run += int(new)
                key = (channel, run)
                of[rid] = key
                held.setdefault(key, []).append(rid)
        talks[relpath, reading] = (of, held)


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
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


recall, sent, sent_gold, units_sent, sizes = (defaultdict(list) for _ in range(5))
talk_sizes = defaultdict(list)
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(answer["tags"]), np.asarray(answer["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    gold = np.array([bool(record_sets[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    t_near, t_edge = WK.best_edges(rows[:, et].max(axis=0), ec, n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    base = standing(t_near[inside]) + standing(d_description[inside]) + standing(d_question[inside])
    order = inside[np.lexsort((id_rank[inside], -base))].tolist()

    def deliver(name, units_of):
        """units_of(chunk) yields units, each a list of (record id, size); a unit already wholly sent is skipped."""
        have, used, units = set(), 0, 0
        stop = False
        for c in order:
            for unit in units_of(c):
                fresh = [(r, s) for r, s in unit if r not in have]
                if not fresh:
                    continue
                cost = sum(s for _, s in fresh)
                if used + cost > BUDGET:
                    stop = True
                    break
                used += cost
                units += 1
                have.update(r for r, _ in fresh)
            if stop:
                break
        recall[name].append(len(cites & have) / len(cites))
        sent[name].append(len(have))
        sent_gold[name].append(len(cites & have))
        units_sent[name].append(units)
        sizes[name].append(used)

    def as_it_is(c):
        share = length[c] / max(len(chunk_ids[c]), 1)
        yield [(r, share) for r in chunk_ids[c]]

    deliver("the chunk as it is", as_it_is)
    for reading in READINGS:
        def conversations(c, only_main, reading=reading):
            relpath = chunk_file[c][0]
            here = posts[relpath]
            of, held = talks[relpath, reading]
            mine = [r for r in chunk_ids[c] if r in of]
            if not mine:
                yield from as_it_is(c)
                return
            keys = Counter(of[r] for r in mine)
            chosen = [keys.most_common(1)[0][0]] if only_main else list(dict.fromkeys(of[r] for r in mine))
            for key in chosen:
                members = held[key]
                unit = [(r, here[r]["size"]) for r in members]
                seen = set(members)
                for r in members:
                    for o in here[r]["points at"]:
                        if o not in seen and o in here:
                            seen.add(o)
                            unit.append((o, here[o]["size"]))
                yield unit

        deliver(f"its conversations, whole, and what they link to ({reading})",
                lambda c: conversations(c, False))
        deliver(f"its main conversation, whole, and what it links to ({reading})",
                lambda c: conversations(c, True))
        of, held = talks[chunk_file[order[0]][0], reading]
        talk_sizes[reading] += [len(v) for v in held.values()]
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

first = "the chunk as it is"
print(f"\n{SET}: {len(wanted)} questions, inside the gold's branch; budget {BUDGET} characters")
for reading in READINGS:
    v = talk_sizes[reading]
    print(f"messages in a conversation ({reading}): the middle {np.median(v):.0f} ({np.percentile(v, 25):.0f}-"
          f"{np.percentile(v, 75):.0f})")
print("\n== what is delivered for each chunk the first order lands on: context_recall_id | against the chunk as it "
      "is: mean difference, its standard error, questions higher / lower | records delivered, the middle | of them "
      "cited, the middle | units | characters used ==")
for name in recall:
    diff = np.asarray(recall[name]) - np.asarray(recall[first])
    print(f"  {float(np.mean(recall[name])):.3f} | {float(diff.mean()):+.3f}, {float(diff.std(ddof=1) / np.sqrt(diff.size)):.3f}, "
          f"{int((diff > 0).sum())} / {int((diff < 0).sum())} | {np.median(sent[name]):.0f} | "
          f"{np.median(sent_gold[name]):.0f} | {np.median(units_sent[name]):.0f} | {np.median(sizes[name]):,.0f}  {name}")
print("done", flush=True)
