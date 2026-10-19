"""His 2026-10-11 "can our structure or scope help fix this somehow?": two things the records
carry and the graph does not yet: when a record was made, and the links it shares or owns. How
the gold chunks of a question sit in time and along shared links, inside the gold's branch.
No query side, so it runs on the hundred without a model call.

  time    a chunk's time is the middle of its records' times (a Slack message's timestamp, a
          document's or transcript's date, a PR's created_at)
  links   a chunk owns the links of its records (a document's document_link, a PR's link, a URL
          record's link) and mentions every link written in its records' texts; two chunks are
          linked when one mentions a link the other owns

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/gold_time_links.py [gold100]
"""
import json
import re
import sys
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
DRAWS = 200
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("the gold time and links test")
n = len(p.chunk_ids)


def stamp(value):
    """A record's time as seconds; None where it carries none that reads."""
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


docs, records, when = {}, [], np.full(n, np.nan)
owns, mentions = [set() for _ in range(n)], [set() for _ in range(n)]
for i, row in enumerate(p.chunk_rows):
    loc = json.loads(row["locator"])
    doc = _load_verified_doc(row["relpath"], row["sha256"], docs)
    arr = doc[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    records.append(frozenset(str(r["id"]) for r in recs if r.get("id") is not None))
    times = []
    for r in recs:
        t = stamp(((r.get("Message") or {}).get("User") or {}).get("timestamp")) if "Message" in r else \
            stamp(r.get("date") if "date" in r else r.get("created_at"))
        if t is not None:
            times.append(t)
        for key in OWN:
            if isinstance(r.get(key), str) and r[key].startswith("http"):
                owns[i].add(clean(r[key]))
        text = (r[loc["field"]][loc["char_range"][0]:loc["char_range"][1]] if "char_range" in loc
                else " ".join(strings({k: v for k, v in r.items() if k not in OWN})))
        mentions[i].update(clean(u) for u in URL.findall(text))
    if times:
        when[i] = float(np.median(times))
    mentions[i] -= owns[i]
owner = {}
for i in range(n):
    for link in owns[i]:
        owner.setdefault(link, set()).add(i)
linked = [set() for _ in range(n)]
for i in range(n):
    for link in mentions[i]:
        for j in owner.get(link, ()):
            if j != i:
                linked[i].add(j)
                linked[j].add(i)
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
kind_names, kind_of = p.layer["kind_names"], p.layer["kind"]
print(f"{SET}: {len(wanted)} questions; pool {n} chunks; with a time {int(np.isfinite(when).sum())}; owning a link "
      f"{sum(bool(x) for x in owns)}; mentioning a link {sum(bool(x) for x in mentions)}; linked to another chunk "
      f"{sum(bool(x) for x in linked)}; linked pairs {sum(len(x) for x in linked) // 2}")
same_branch = sum(1 for i in range(n) for j in linked[i] if branch_of[i] == branch_of[j]) // 2
print(f"  linked pairs inside one branch: {same_branch}; chunks with a time by kind: "
      + ", ".join(f"{kind_names[k]} {int(np.isfinite(when[kind_of == k]).sum())}/{int((kind_of == k).sum())}"
                  for k in range(len(kind_names))))

rng = np.random.default_rng(20261011)
S = {name: [] for name in ("gold", "timed", "window", "held", "near_gold", "near_chance", "near_other", "near_other_chance",
                           "gold_linked", "linked_gold", "linked_chance", "reach", "reach_size")}
for qid in wanted:
    cites = {str(c) for c in by_id[qid].citations}
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    g_all = np.flatnonzero(gold)
    if not g_all.size:
        continue
    main = Counter(branch_of[g_all].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    g = g_all[branch_of[g_all] == main]
    S["gold"].append(g.size)
    timed = inside[np.isfinite(when[inside])]
    gt = g[np.isfinite(when[g])]
    S["timed"].append(gt.size / g.size)
    if gt.size >= 2 and timed.size >= 3:
        lo, hi = when[timed].min(), when[timed].max()
        a, b = when[gt].min(), when[gt].max()
        if hi > lo:
            S["window"].append((b - a) / (hi - lo))
            S["held"].append(float(((when[timed] >= a) & (when[timed] <= b)).mean()))
        # the chunk nearest in time to a gold chunk: is it gold? (any parent, and another kind of record)
        order = timed[np.argsort(when[timed])]
        place = {int(c): k for k, c in enumerate(order)}
        hit, hit_other = [], []
        for c in gt.tolist():
            k = place[c]
            around = [order[x] for x in (k - 1, k + 1) if 0 <= x < order.size]
            nearest = min(around, key=lambda x: abs(when[x] - when[c]))
            hit.append(bool(gold[nearest]))
            others = timed[kind_of[timed] != kind_of[c]]
            if others.size:
                hit_other.append(bool(gold[others[np.argmin(np.abs(when[others] - when[c]))]]))
        S["near_gold"].append(float(np.mean(hit)))
        S["near_chance"].append((gt.size - 1) / (timed.size - 1))
        if hit_other:
            S["near_other"].append(float(np.mean(hit_other)))
            S["near_other_chance"].append(g.size / inside.size)
    # links
    with_link = [c for c in g.tolist() if linked[c]]
    S["gold_linked"].append(len(with_link) / g.size)
    if with_link:
        S["linked_gold"].append(float(np.mean([np.mean([gold[j] for j in linked[c]]) for c in with_link])))
        S["linked_chance"].append(g.size / inside.size)
    # everything linked to a gold chunk: how much of the gold it reaches, and how many chunks it is
    reach = set()
    for c in g.tolist():
        reach |= {j for j in linked[c] if branch_of[j] == main}
    S["reach"].append(len(reach & set(g.tolist())) / g.size)
    S["reach_size"].append(len(reach))

mean = lambda name: float(np.mean(S[name])) if S[name] else float("nan")
print(f"\n== {len(S['gold'])} questions, inside the gold's branch ==")
print(f"  gold chunks with a time: {mean('timed'):.2f}")
print(f"  time: from the first to the last gold chunk is {mean('window'):.2f} of the branch's whole time, and "
      f"{mean('held'):.2f} of the branch's chunks lie inside it ({len(S['window'])} questions)")
print(f"  the chunk nearest in time to a gold chunk is gold: {mean('near_gold'):.3f}; by chance {mean('near_chance'):.3f}")
print(f"  the chunk of another kind of record nearest in time to a gold chunk is gold: {mean('near_other'):.3f}; "
      f"by chance {mean('near_other_chance'):.3f}")
print(f"  gold chunks linked to another chunk: {mean('gold_linked'):.2f}; of the chunks a gold chunk is linked to, gold: "
      f"{mean('linked_gold'):.3f}; by chance {mean('linked_chance'):.3f} ({len(S['linked_gold'])} questions)")
print(f"  the chunks linked to any gold chunk: {mean('reach_size'):.1f} per question, holding {mean('reach'):.2f} of the gold chunks")
print("done", flush=True)
