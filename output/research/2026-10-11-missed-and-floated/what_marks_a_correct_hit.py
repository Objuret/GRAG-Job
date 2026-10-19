"""His 2026-10-11 "how about you fucking FIGURE OUT a brilliant way then": what, without gold and
without a model call, tells a correct hit from one that is not. The signals are taken from his
concept first; the gold of the hundred is used only to read whether a signal separates.

On the hundred, inside the gold's branch, cached query side, no model call.

A  Names and handles the question itself carries: a graph tag whose name stands literally in the
   question. The first call excludes names from the query tags; the graph's tags were written
   with proper names kept whole.
B  How close the chunk's closest tag is, in his clusters: every query tag's closeness to every
   graph tag in one list, cut into 5 clusters (1 the closest); and against the graph's own
   same-thing level.
C  The facet a query tag names, read on the edge: among the edges one query tag picks, do the
   gold chunks sit on the edges where the named facet is higher. Topic and a facet that was not
   named are read the same way beside it.
D  How many chunks of the branch carry the matched tag (the agent's own reading, as a level).
E  How many of the three routes hit the chunk.

The gold ids and the question texts are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/what_marks_a_correct_hit.py [gold100]
"""
import json
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"
os.environ["HERB_V4_SCOPE_STEP"] = "both"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
CACHE = REPO / "output/private/artefact_v4_cache/querytag"
K = V._k_nearest()
FACETS = ("temporal", "why", "activity", "concreteness")
WORD = re.compile(r"[^a-z0-9]+")


def plain(text):
    return " " + WORD.sub(" ", str(text).lower()).strip() + " "


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("what marks a correct hit")
layer, n = p.layer, len(p.chunk_ids)
et, ec, eligible, raw = layer["edge_tag"], layer["edge_chunk"], layer["eligible"], layer["raw"]
tag_plain = [plain(V._readable(t)) if hasattr(V, "_readable") else plain(t) for t in p.graph_tags]
docs, records = {}, []
for row in p.chunk_rows:
    loc = json.loads(row["locator"])
    arr = _load_verified_doc(row["relpath"], row["sha256"], docs)[loc["section"]]
    recs = [arr[k] for k in (loc["indices"] if "indices" in loc else [loc["index"]])]
    records.append(frozenset(str(r["id"]) for r in recs if r.get("id") is not None))
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b
same = None
for holder in (getattr(p, "provenance", None), getattr(p.build_stats, "__dict__", None), V.RETRIEVAL_FLAGS):
    if isinstance(holder, dict) and isinstance(holder.get("same_thing_pairs"), dict):
        same = holder["same_thing_pairs"]
        break
SAME_MEDIAN = float(same["median"]) if same else 0.950
SAME_LEVEL = float(same["level"]) if same else 0.8541
print(f"the graph's same-thing pairs: median {SAME_MEDIAN:.4f}, 5% under {SAME_LEVEL:.4f} "
      f"({'read from the arm' if same else 'as the arm prints them at prepare'})", flush=True)


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
    def named(rows):
        out = {}
        for r in rows or []:
            if isinstance(r, dict) and str(r.get("t", "")).strip():
                out.setdefault(str(r["t"]).strip(), str(r.get("facet", "")))
        return list(out), list(out.values())
    for _, user, got in SIDES:
        if q.question in user:
            tags, tag_facets = named(got.get("tags"))
            asked, asked_facets = named(got.get("query_tags"))
            return str(got["description"]), tags, tag_facets, asked, asked_facets
    raise SystemExit(f"no cached first call for {q.id}")


def band(value, edges, names):
    for edge, name in zip(edges, names):
        if value <= edge:
            return name
    return names[-1]


tables = defaultdict(lambda: defaultdict(lambda: [0, 0]))     # (signal, where) -> level -> [gold, chunks]
literal = defaultdict(list)
halves = defaultdict(lambda: [0, 0, 0, 0])                    # (pick, reading) -> gold top, top, gold bottom, bottom
centile = defaultdict(list)
carried_in = {}
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, tag_facets, asked, asked_facets = side_of(q)
    answer, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(answer["tags"]), np.asarray(answer["description"], dtype=np.float64)
    named = list(tag_facets)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
        named += list(asked_facets)
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    inside = np.flatnonzero(branch_of == main)
    here = np.zeros(n, dtype=bool)
    here[inside] = True
    edges_here = np.flatnonzero(here[ec])
    if main not in carried_in:
        count = Counter(et[edges_here].tolist())
        carried_in[main] = count
    carried = carried_in[main]

    place_of_tag = np.full(rows.shape, np.inf)
    place_of_tag[:, eligible] = np.array([rankdata(-row[eligible], method="min") for row in rows])
    level_of_tag = np.full(rows.shape, K + 1, dtype=np.int64)
    level_of_tag[:, eligible] = WK.levels(rows[:, eligible].ravel(), K).reshape(rows.shape[0], -1)
    on_edge = rows[:, et]
    best_cos = np.full(n, -np.inf)
    np.maximum.at(best_cos, ec, on_edge.max(axis=0))
    best_edge = np.full(n, -1, dtype=np.int64)
    top = on_edge.max(axis=0)
    for e in edges_here.tolist():
        c = ec[e]
        if best_edge[c] < 0 or top[e] > top[best_edge[c]]:
            best_edge[c] = e
    best_place = np.full(n, np.inf)
    np.minimum.at(best_place, ec, place_of_tag[:, et].min(axis=0))
    best_level = np.full(n, K + 1, dtype=np.int64)
    np.minimum.at(best_level, ec, level_of_tag[:, et].min(axis=0))
    by_tags = best_place[inside] <= K
    by_description = WK.levels(d_description[inside], K) == 1
    by_question = WK.levels(d_question[inside], K) == 1
    routes = by_tags.astype(int) + by_description.astype(int) + by_question.astype(int)
    found = routes > 0

    # A: graph tags whose name stands literally in the question
    text = plain(q.question)
    written = {t for t in carried if eligible[t] and len(tag_plain[t]) > 3 and tag_plain[t] in text}
    literal["graph tags of the branch written in the question"].append(len(written))
    literal["of them among the picked tags"].append(
        sum(1 for t in written if (place_of_tag[:, t] <= K).any()))
    lit_count = np.zeros(n, dtype=np.int64)
    for e in edges_here.tolist():
        if et[e] in written:
            lit_count[ec[e]] += 1
    literal["chunks of the branch carrying one"].append(int((lit_count[inside] > 0).sum()))

    for k, c in enumerate(inside.tolist()):
        where = ("hit" if found[k] else "not hit")
        g = int(gold[c])
        readings = {
            "A  graph tags of the chunk written in the question": band(lit_count[c], (0, 1), ("none", "1", "2 or more")),
            "B  his clusters: the level of its closest tag (1 the closest)": str(int(best_level[c])) if best_level[c] <= K
            else "no tag",
            "B  its closest tag against the same-thing level": (
                "same thing (at or above the median)" if best_cos[c] >= SAME_MEDIAN else
                "above the 5% level" if best_cos[c] >= SAME_LEVEL else "below it"),
            "E  routes that hit it": str(int(routes[k])),
        }
        if best_edge[c] >= 0:
            readings["D  chunks of the branch carrying its closest tag"] = band(
                carried[int(et[best_edge[c]])], (1, 2, 5, 10), ("1", "2", "3-5", "6-10", "11 or more"))
        for signal, level in readings.items():
            for scope in (where, "all"):
                cell = tables[signal, scope][level]
                cell[0] += g
                cell[1] += 1

    # C: among the edges one query tag picks, the gold against the named facet's value on the edge
    for pick_name, picked in (("the 5 nearest graph tags", place_of_tag <= K), ("his first cluster", level_of_tag == 1)):
        for i in range(rows.shape[0]):
            if named[i] not in FACETS:
                continue
            f = 1 + FACETS.index(named[i])
            other = 1 + next(j for j, name in enumerate(FACETS) if name != named[i])
            mine = edges_here[picked[i, et[edges_here]]]
            if mine.size < 4:
                continue
            is_gold = gold[ec[mine]]
            if not is_gold.any() or is_gold.all():
                continue
            for reading, column in (("the named facet", f), ("topic", 0), ("a facet that was not named", other)):
                value = raw[mine, column]
                order = np.argsort(-value, kind="stable")
                half = mine.size // 2
                cell = halves[pick_name, reading]
                cell[0] += int(is_gold[order[:half]].sum())
                cell[1] += half
                cell[2] += int(is_gold[order[mine.size - half:]].sum())
                cell[3] += half
                ranks = rankdata(value, method="average") / mine.size
                centile[pick_name, reading].append(float(ranks[is_gold].mean()))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

m = len(wanted)
print(f"\n{SET}: {m} questions, inside the gold's branch; a query tag picks its {K} nearest graph tags")
print("\n== A: names and handles the question carries, per question, the middle (a quarter - three quarters) ==")
for name, values in literal.items():
    q1, mid, q3 = np.percentile(values, [25, 50, 75])
    print(f"  {name}: {mid:.0f} ({q1:.0f}-{q3:.0f}); questions with none: {sum(1 for v in values if v == 0)}")
for signal in sorted({key[0] for key in tables}):
    print(f"\n== {signal}: gold of chunks (share), among the hits | among the chunks not hit | all chunks of the branch ==")
    levels = sorted({level for key in tables if key[0] == signal for level in tables[key]})
    for level in levels:
        cells = []
        for scope in ("hit", "not hit", "all"):
            g, t = tables[signal, scope].get(level, (0, 0))
            cells.append(f"{g} of {t} ({(g / t if t else 0):.3f})")
        print(f"  {level}: " + " | ".join(cells))
print("\n== C: among the edges one query tag picks, the half with the higher value against the half with the lower: "
      "gold of chunks (share) | the same | the gold edges' middle standing by that value (0.5 = no difference) ==")
for key in sorted(halves):
    g1, t1, g2, t2 = halves[key]
    print(f"  {key[0]}, by {key[1]}: {g1} of {t1} ({(g1 / t1 if t1 else 0):.3f}) | {g2} of {t2} "
          f"({(g2 / t2 if t2 else 0):.3f}) | {float(np.mean(centile[key])):.3f} over {len(centile[key])} query tags")
print("done", flush=True)
