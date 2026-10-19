"""For his 2026-10-12 work on the cloud combo and scope: the ties between the chunks of a question's
product, read from the records with no question and no gold needed, written beside the first
table (outside the repository): which chunks share a link (one holds a record that owns the
link, the other mentions it, or both mention it), and for every chunk the conversations it
holds (one channel, one day) and the days its records fall on.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/first_gold_signals_ties.py gold100 <folder>
"""
import json
import os
import pickle
import re
import sys
import warnings
from collections import defaultdict
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

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
OUT = Path(sys.argv[2])
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")


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


with open(OUT / f"first_gold_signals__{SET}.pkl", "rb") as handle:
    first = pickle.load(handle)["questions"]
p = V.prepare_over_corpus("first gold signals, the ties")
n = len(p.chunk_ids)
docs = {}
owns, mentions, talks, days = [set() for _ in range(n)], [set() for _ in range(n)], [set() for _ in range(n)], [set() for _ in range(n)]
talk_ids, day_ids = {}, {}
for i, row in enumerate(p.chunk_rows):
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    for r in [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]:
        for key in OWN:
            if isinstance(r.get(key), str) and r[key].startswith("http"):
                owns[i].add(clean(r[key]))
        body = (r[loc["field"]][loc["char_range"][0]:loc["char_range"][1]] if "char_range" in loc
                else " ".join(strings({k: v for k, v in r.items() if k not in OWN})))
        mentions[i].update(clean(u) for u in URL.findall(body))
        raw = ((r.get("Message") or {}).get("User") or {}).get("timestamp") if "Message" in r else (
            r.get("date") if "date" in r else r.get("created_at"))
        when = stamp(raw)
        if when is not None:
            day = (row["relpath"], datetime.fromtimestamp(when, timezone.utc).date().isoformat())
            days[i].add(day_ids.setdefault(day, len(day_ids)))
            channel = (r.get("Channel") or {}).get("channelID") if "Channel" in r else None
            if channel is not None:
                talks[i].add(talk_ids.setdefault((day, channel), len(talk_ids)))
    mentions[i] -= owns[i]
holders = defaultdict(set)
for i in range(n):
    for link in owns[i] | mentions[i]:
        holders[link].add(i)
owner = defaultdict(set)
for i in range(n):
    for link in owns[i]:
        owner[link].add(i)
print("prepared", flush=True)

ties = {}
for qid, d in first.items():
    inside = d["chunks"]
    local = {int(c): k for k, c in enumerate(inside.tolist())}
    own_pairs, any_pairs = set(), set()
    for c in inside.tolist():
        for link in mentions[c]:
            for o in owner.get(link, ()):
                if o != c and o in local:
                    own_pairs.add((min(local[c], local[o]), max(local[c], local[o])))
        for link in owns[c] | mentions[c]:
            for o in holders[link]:
                if o != c and o in local and len(holders[link]) <= 20:
                    any_pairs.add((min(local[c], local[o]), max(local[c], local[o])))
    ties[qid] = {
        "linked_to_owner": np.array(sorted(own_pairs), dtype=np.int32).reshape(-1, 2),
        "share_a_link": np.array(sorted(any_pairs), dtype=np.int32).reshape(-1, 2),
        "talks": [sorted(talks[c]) for c in inside.tolist()], "days": [sorted(days[c]) for c in inside.tolist()],
        "links_on_chunk": np.array([len(owns[c] | mentions[c]) for c in inside.tolist()]),
    }
with open(OUT / f"first_gold_signals_ties__{SET}.pkl", "wb") as handle:
    pickle.dump(ties, handle)
pairs = [len(t["share_a_link"]) for t in ties.values()]
print(f"{SET}: {len(ties)} questions; chunk pairs of a product that share a link, the middle: {np.median(pairs):.0f}")
print("done", flush=True)
