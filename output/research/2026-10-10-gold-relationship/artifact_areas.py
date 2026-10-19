"""His 2026-10-11 "can our structure or scope help fix this somehow?": is a question's gold
gathered around a few artifacts? An artifact is a record that owns a link (a document, a PR, a URL
record). Its area: the chunks that hold it, the chunks whose records share its link, and (wider)
the chunks next to those in their parent. No query side; the hundred without a model call.

Per question, inside the gold's branch, artifacts are taken one at a time, each time the one
whose area adds the most gold chunks (the most that knowing the right artifacts could give).

The gold ids are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/artifact_areas.py [gold100]
"""
import json
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc, _resolve_chunk  # noqa: E402
from arms.artefact_v3 import file_adjacency  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")
STEPS = (1, 2, 3, 5, 8)

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("artifact areas")
n = len(p.chunk_ids)


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


docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
owns, mentions = [set() for _ in range(n)], [set() for _ in range(n)]
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    for r in [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]:
        for key in OWN:
            if isinstance(r.get(key), str) and r[key].startswith("http"):
                owns[i].add(clean(r[key]))
        body = (r[loc["field"]][loc["char_range"][0]:loc["char_range"][1]] if "char_range" in loc
                else " ".join(strings({k: v for k, v in r.items() if k not in OWN})))
        mentions[i].update(clean(u) for u in URL.findall(body))
    mentions[i] -= owns[i]
adjacency = file_adjacency([dict(r) for r in p.chunk_rows])
ptr, members = np.asarray(adjacency["ptr"]), np.asarray(adjacency["members"])
next_to = [set(members[ptr[i]:ptr[i + 1]].tolist()) for i in range(n)]
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
kind_names, kind_of = p.layer["kind_names"], p.layer["kind"]

S = {name: [] for name in ("artifacts", "with_gold", "gold_in_any", "gold_in_any_wide")}
steps = {wide: {k: {"gold": [], "records": [], "chunks": [], "chars": []} for k in STEPS} for wide in (False, True)}
for qid in wanted:
    cites = {str(c) for c in by_id[qid].citations}
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    g_all = np.flatnonzero(gold)
    if not g_all.size:
        continue
    main = Counter(branch_of[g_all].tolist()).most_common(1)[0][0]
    inside = set(np.flatnonzero(branch_of == main).tolist())
    g = set(i for i in g_all.tolist() if i in inside)
    area = {}
    for i in inside:
        for link in owns[i] | mentions[i]:
            area.setdefault(link, set()).add(i)
    owned = {link for i in inside for link in owns[i]}
    area = {link: chunks for link, chunks in area.items() if link in owned}
    wide = {link: chunks | {j for i in chunks for j in next_to[i] if j in inside} for link, chunks in area.items()}
    S["artifacts"].append(len(area))
    S["with_gold"].append(sum(1 for chunks in area.values() if chunks & g))
    S["gold_in_any"].append(len(g & set().union(*area.values())) / len(g) if area else 0.)
    S["gold_in_any_wide"].append(len(g & set().union(*wide.values())) / len(g) if wide else 0.)
    for is_wide, areas in ((False, area), (True, wide)):
        taken, covered, left = set(), set(), dict(areas)
        for k in range(1, max(STEPS) + 1):
            best = max(left, key=lambda a: (len((left[a] & g) - covered), -len(left[a] - taken)), default=None)
            if best is not None and (left[best] & g) - covered:
                taken |= left.pop(best)
                covered = taken & g
            if k in STEPS:
                got = set().union(*(records[i] for i in taken)) if taken else set()
                steps[is_wide][k]["gold"].append(len(covered) / len(g))
                steps[is_wide][k]["records"].append(len(cites & got) / len(cites))
                steps[is_wide][k]["chunks"].append(len(taken))
                steps[is_wide][k]["chars"].append(int(length[list(taken)].sum()) if taken else 0)

mean = lambda values: float(np.mean(values))
print(f"{SET}: {len(S['artifacts'])} questions, inside the gold's branch")
print(f"  artifacts (records that own a link) per branch: middle {np.median(S['artifacts']):.0f}; artifacts whose area holds "
      f"a gold chunk: middle {np.median(S['with_gold']):.0f}")
print(f"  share of the gold chunks inside some artifact's area: {mean(S['gold_in_any']):.2f}; with the chunks next to them: "
      f"{mean(S['gold_in_any_wide']):.2f}")
for is_wide, label in ((False, "an artifact's area: its own chunks and the chunks sharing its link"),
                       (True, "the same, with the chunks next to those")):
    print(f"\n== {label}; the best artifacts taken one at a time ==")
    for k in STEPS:
        s = steps[is_wide][k]
        print(f"  the best {k}: {mean(s['gold']):.2f} of the gold chunks, {mean(s['records']):.2f} of the cited records, in "
              f"{mean(s['chunks']):.1f} chunks, {mean(s['chars']):,.0f} characters")
print("done", flush=True)
