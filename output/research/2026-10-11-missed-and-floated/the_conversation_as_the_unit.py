"""The agent's own reading, 2026-10-11 night, after `is_the_gold_one_cloud` (the gold of a question is
about five conversations that do not resemble each other in what the graph holds): a conversation
names what it is about in its opening, the later messages say "this PR", "the integration", and
the chunks were cut by size, so a later part often sits in another chunk than its opening. Two
counts, on the hundred, inside the question's product, cached query side, no model call.

  1  the gold Slack chunks by whether they hold the opening of a gold conversation they carry or
     only a later part: how many of each the plain order floats (the three routes' standings
     added, cut at 72,000 characters), and where they stand in it.
  2  what the conversation as the unit could reach. No description or tag exists per conversation
     and writing them is a model run, so this is sized with the record vectors the vector
     baseline has (records behind "passage: ", the question behind "query: "): the units are the
     conversations (and every record that is not a Slack message alone), a unit's value is the
     closeness to the question of its opening (its first message written by a person), of its
     closest message, or of its messages on average; units are delivered whole, the highest
     first, until 72,000 characters. Beside it: the chunks in the plain order, and the units that
     hold cited records first (what the unit could reach at most).

A conversation is the messages of one channel that follow each other closely in time, in two
readings: the same calendar day; no gap in the larger of the two clusters the product's channel
gaps fall into on the logarithm of the gap (least squares, `v4_walk.levels`).

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_conversation_as_the_unit.py [gold100]
"""
import json
import math
import os
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
KEPT = REPO / "output/embed_local/20261007_rev113abe4acafa_float32"
READINGS = ("the same day", "no large gap")
BOT = "slack_admin_bot"


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
p = V.prepare_over_corpus("the conversation as the unit")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
et, ec = layer["edge_tag"], layer["edge_chunk"]
docs, chunk_ids, length, chunk_section, chunk_file = {}, [], np.zeros(n, dtype=np.int64), [], []
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    length[i] = len(text)
    chunk_ids.append([str(x) for x in ids])
    chunk_section.append(json.loads(row["locator"])["section"])
    chunk_file.append((row["relpath"], row["sha256"]))
record_sets = [frozenset(ids) for ids in chunk_ids]
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
corpus = np.load(KEPT / "corpus_passage.npz", allow_pickle=True)
row_of = {str(r): k for k, r in enumerate(corpus["ids"])}
matrix = np.asarray(corpus["matrix"], dtype=np.float32)
asked_vectors = np.load(KEPT / "question_query_vecs.npz", allow_pickle=True)
question_at = {str(q): k for k, q in enumerate(asked_vectors["ids"])}

files = {}
for (relpath, sha), section in set(zip(chunk_file, chunk_section)):
    files.setdefault((relpath, sha), set()).add(section)
posts, talks = {}, {}
for (relpath, sha), sections in files.items():
    doc = _load_verified_doc(relpath, sha, docs)
    here = {}
    for section in sorted(sections):
        for record in doc[section]:
            if not isinstance(record, dict) or record.get("id") is None:
                continue
            user = (record.get("Message") or {}).get("User") or {}
            here[str(record["id"])] = {
                "size": len(json.dumps(record, ensure_ascii=False)) + 1,
                "channel": (record.get("Channel") or {}).get("channelID") if "Channel" in record else None,
                "when": stamp(user.get("timestamp")) if "Message" in record else None,
                "person": "Message" in record and str(user.get("userId")) != BOT}
    posts[relpath] = here
    by_channel = defaultdict(list)
    for rid, post in here.items():
        if post["channel"] is not None and post["when"] is not None:
            by_channel[post["channel"]].append(rid)
    gaps = []
    for members in by_channel.values():
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
                of[rid] = (channel, run)
                held.setdefault((channel, run), []).append(rid)
        talks[relpath, reading] = (of, held)
print("prepared the conversations", flush=True)


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


parts = {reading: defaultdict(lambda: [0, 0, []]) for reading in READINGS}
recall, units_sent, unit_sizes, gold_units = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    answer = V._tag_cosines(description, tags, p)[0]
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
    order = inside[np.lexsort((id_rank[inside], -base))]
    fits = np.cumsum(length[order]) <= BUDGET
    kept = int(fits.sum()) if fits.all() else int(np.argmin(fits))
    floated = set(order[:kept].tolist())
    place = {int(c): k + 1 for k, c in enumerate(order.tolist())}
    got = set().union(*(record_sets[i] for i in floated)) if floated else set()
    recall["the chunks in the plain order"].append(len(cites & got) / len(cites))
    relpath = chunk_file[int(inside[0])][0]
    here = posts[relpath]

    # 1: a gold Slack chunk holds the opening of a gold conversation it carries, or only a later part
    for reading in READINGS:
        of, held = talks[relpath, reading]
        for c in inside[gold[inside]].tolist():
            mine = [r for r in chunk_ids[c] if r in cites and r in of]
            if not mine:
                continue
            opening = any(next((m for m in held[of[r]] if here[m]["person"]), held[of[r]][0]) in record_sets[c]
                          for r in mine)
            row = parts[reading]["holds the opening" if opening else "only a later part"]
            row[0] += 1
            row[1] += int(c in floated)
            row[2].append(place[c])

    # 2: the conversation as the unit, valued through the record vectors
    near = matrix @ np.asarray(asked_vectors["matrix"][question_at[qid]], dtype=np.float32)
    inside_records = set().union(*(record_sets[c] for c in inside.tolist()))
    chunk_value = {r: float(base[k]) for k, c in enumerate(inside.tolist()) for r in chunk_ids[c]}
    for reading in READINGS:
        of, held = talks[relpath, reading]
        units, seen = [], set()
        for r in sorted(inside_records):
            if r in seen or r not in here:
                continue
            members = [m for m in held[of[r]] if m in inside_records] if r in of else [r]
            seen.update(members)
            units.append(members)
        closeness = [np.array([float(near[row_of[m]]) for m in members if m in row_of] or [float(near.min())])
                     for members in units]
        first = []
        for members in units:
            opener = next((m for m in members if here[m]["person"]), members[0])
            first.append(float(near[row_of[opener]]) if opener in row_of else float(near.min()))
        values = {
            "its opening": np.array(first),
            "its closest message": np.array([c.max() for c in closeness]),
            "its messages on average": np.array([c.mean() for c in closeness]),
            "its opening and the plain order's value of its best chunk (standings added)":
                standing(first) + standing([max(chunk_value[m] for m in members) for members in units]),
            "the units that hold cited records first (the most the unit could reach)":
                np.array([float(len(cites & set(members))) / len(members) for members in units]),
        }
        sizes = [sum(here[m]["size"] for m in members) for members in units]
        gold_units[reading].append(sum(1 for members in units if cites & set(members)))
        unit_sizes[reading] += sizes
        for name, value in values.items():
            have, used, sent = set(), 0, 0
            for k in sorted(range(len(units)), key=lambda k: (-float(value[k]), units[k][0])):
                if used + sizes[k] > BUDGET:
                    break
                used += sizes[k]
                sent += 1
                have.update(units[k])
            recall[f"units ({reading}) by {name}" if not name.startswith("the units") else f"({reading}) {name}"].append(
                len(cites & have) / len(cites))
            units_sent[f"units ({reading}) by {name}" if not name.startswith("the units") else f"({reading}) {name}"].append(sent)
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

print(f"\n{SET}: {len(wanted)} questions, inside the question's product; budget {BUDGET} characters")
print("\n== 1: the gold Slack chunks | how many | floated by the plain order | their place in it, the middle ==")
for reading in READINGS:
    for name, (count, got, places) in parts[reading].items():
        print(f"  ({reading}) {name}: {count} | {got} ({got / max(count, 1):.0%}) | {np.median(places):.0f} "
              f"({np.percentile(places, 25):.0f}-{np.percentile(places, 75):.0f})")
print("\n== 2: context_recall_id (share of the cited records delivered inside 72,000 characters) | units delivered, "
      "the middle ==")
for name, values in recall.items():
    sent = f"{np.median(units_sent[name]):.0f}" if name in units_sent else "-"
    print(f"  {float(np.mean(values)):.3f} | {sent}  {name}")
for reading in READINGS:
    print(f"  ({reading}) units that hold a cited record, a question: {np.median(gold_units[reading]):.0f} "
          f"({np.percentile(gold_units[reading], 25):.0f}-{np.percentile(gold_units[reading], 75):.0f}); "
          f"characters of a unit: {np.median(unit_sizes[reading]):,.0f} "
          f"({np.percentile(unit_sizes[reading], 25):,.0f}-{np.percentile(unit_sizes[reading], 75):,.0f})")
print("done", flush=True)
