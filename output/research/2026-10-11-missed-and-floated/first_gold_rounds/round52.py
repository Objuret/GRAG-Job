"""Round 52, under his 2026-10-12 goal "solve this": is a question's gold "the conversations of one
kind"? A conversation's kind is read from how it opens: the first words of its first message
(the benchmark writes its conversations from a few openings: "please check my PR for", "I looked
into the reported issue about", "several customers are reporting issues with"). The hundred and
the 300 unused questions; no graph, no model call; numbers only, no opening is printed.

  the kind of a conversation: the first five words of its first message, lower case, a word that
  holds a digit or an at-sign left out
  1  kinds a product has; conversations a kind (the middle)
  2  a question's cited conversations: how many kinds; share in the kind that holds most of them
  3  of ALL the product's own conversations of that kind: share that the question cites
     (1.0 = the question cites every conversation of the kind)
  4  the same with the kind held to one stretch of the work (the conversations of that kind in
     the channels where a cited one is)
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path("C:/Coding/exjobbet/GRAG-Job")
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
import ties as TI  # noqa: E402
from harness import questions as HQ  # noqa: E402

WORD = re.compile(r"[A-Za-z']+|\S+")
ids_of = {name: {json.loads(line)["id"] for line in (REPO / "data" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()} for name in ("gold100", "heldout100")}
every = HQ.load_questions()
fresh = sorted((q for q in every if q.id not in ids_of["gold100"] | ids_of["heldout100"] and q.citations), key=lambda q: q.id)
sets = {"the gold hundred": [q for q in every if q.id in ids_of["gold100"]],
        "300 unused questions": random.Random(20261011).sample(fresh, 300)}


def kind_of(text):
    words = [w.lower().strip(".,!?:;") for w in text.split() if not any(c.isdigit() for c in w) and "@" not in w and "<" not in w]
    return " ".join(words[:5])


holder, made = {}, {}
kinds_n, per_kind = [], []
for path in sorted(TI.RAW.glob("*.json")):
    P = TI.product(path.stem)
    for rid in P["raw"]:
        holder.setdefault(rid, path.stem)
    talks = defaultdict(list)
    for rid, t in P["talk_of"].items():
        if not TI.apart(rid, P):
            talks[t].append(rid)
    kind = {}
    for t, rs in talks.items():
        first = min(rs, key=lambda r: P["raw"][r][1]["Message"]["User"]["timestamp"])
        kind[t] = kind_of(P["raw"][first][1]["Message"]["User"]["text"])
    made[path.stem] = (talks, kind)
    count = Counter(kind.values())
    kinds_n.append(len(count))
    per_kind.extend(count.values())
print(f"1: kinds a product has: middle {np.median(kinds_n):.0f}; conversations a kind: middle {np.median(per_kind):.0f}, "
      f"a tenth of the kinds hold {np.percentile(per_kind, 90):.0f} or more")
for label, questions in sets.items():
    n_kinds, in_main, whole, held = [], [], [], []
    by_type = defaultdict(list)
    for q in questions:
        cites = {str(c) for c in q.citations}
        owners = Counter(holder[c] for c in cites if c in holder)
        if not owners:
            continue
        talks, kind = made[owners.most_common(1)[0][0]]
        cited = [t for t, rs in talks.items() if cites & set(rs)]
        if not cited:
            continue
        count = Counter(kind[t] for t in cited)
        main, n_main = count.most_common(1)[0]
        n_kinds.append(len(count))
        in_main.append(n_main / len(cited))
        of_kind = [t for t in talks if kind[t] == main]
        whole.append(n_main / len(of_kind))
        channels = {t[0] for t in cited if kind[t] == main}
        near = [t for t in of_kind if t[0] in channels]
        held.append(n_main / len(near))
        by_type[str(q.type)].append((n_main / len(cited), n_main / len(of_kind), len(cited)))
    w, h = np.array(whole), np.array(held)
    print(f"\n==== {label}: {len(n_kinds)} questions ====")
    print(f"2: kinds among a question's cited conversations: middle {np.median(n_kinds):.0f}; share of them in the kind that holds most: "
          f"mean {np.mean(in_main):.0%}")
    print(f"3: of all the product's conversations of that kind, the share the question cites: mean {w.mean():.0%}; every one of them on "
          f"{int((w > 0.999).sum())} questions; half or more on {int((w >= 0.5).sum())}")
    print(f"4: the same, the kind held to the channels where a cited one is: mean {h.mean():.0%}; every one on {int((h > 0.999).sum())}; "
          f"half or more on {int((h >= 0.5).sum())}")
    print("   by type of question: questions | cited conversations (middle) | share in the main kind | share of the kind cited")
    for name, rows in sorted(by_type.items()):
        a = np.array(rows)
        if len(rows) >= 15:
            print(f"     {name:8s} {len(rows):3d} | {np.median(a[:, 2]):.0f} | {a[:, 0].mean():.0%} | {a[:, 1].mean():.0%}")
