"""His 2026-10-11 goal: can the structure fix the order? An artifact (a record that owns a link:
a document, a PR, a URL record) and the chunks whose records share its link are tied together in
the records themselves. Here the artifacts' areas are valued from the three routes with no gold,
the best areas are delivered whole, and the result is held against the routes alone.

  a chunk's value   the three routes' standings added (tags, description, question), inside the branch
  an area           narrow: the chunks holding the artifact and the chunks sharing its link;
                    wide: those and the chunks next to them in their parent
  an area's value   several readings, printed side by side

The branch is the gold's (to isolate the order) and, second, the one the question route's own
delivery points at (what the system would have). Cached query side, no model call. The gold ids
are read inside this script; it prints numbers only.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/areas_orders.py [gold100]
"""
import json
import os
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
os.environ["HERB_V4_OFFLINE"] = "on"

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_v2 import _load_verified_doc, _resolve_chunk  # noqa: E402
from arms.artefact_v3 import file_adjacency  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "gold100"
BUDGET = 72000
ROUTES = ("tags", "description", "question")
URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
OWN = ("document_link", "link")
CACHE = REPO / "output/private/artefact_v4_cache/querytag"

wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
p = V.prepare_over_corpus("areas and orders")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]


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


def cached_sides():
    out = []
    for f in CACHE.glob("*.json"):
        if f.name.endswith(".started.json"):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        raw = j.get("raw")
        if j.get("ok") and isinstance(raw, dict) and raw.get("description") and raw.get("tags"):
            out.append((f.stat().st_mtime, (j.get("signature") or {}).get("user") or "", raw))
    return sorted(out, key=lambda row: -row[0])


SIDES = cached_sides()


def side_of(q):
    def names(rows):
        return list(dict.fromkeys(str(r["t"]).strip() for r in rows or []
                                  if isinstance(r, dict) and str(r.get("t", "")).strip()))
    for _, user, raw in SIDES:
        if q.question in user:
            return str(raw["description"]), names(raw.get("tags")), names(raw.get("query_tags"))
    raise SystemExit(f"no cached first call for {q.id}")


def kept_of(order):
    fits = np.cumsum(length[order]) <= BUDGET
    return int(fits.sum()) if fits.all() else int(np.argmin(fits))


def recall_of(order, cites):
    order = np.asarray(order, dtype=np.int64)
    kept = kept_of(order)
    got = set().union(*(records[i] for i in order[:kept])) if kept else set()
    return len(cites & got) / len(cites)


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def orders_for(inside, signal, named, gold=None):
    """Every order tried, for one branch: name -> the chunks in order."""
    value = dict(zip(inside.tolist(), sum(standing(signal[r][inside]) for r in ROUTES).tolist()))
    plain = sorted(value, key=lambda i: (-value[i], id_rank[i]))
    within = set(value)
    holders, sharers = {}, {}
    for i in within:
        for link in owns[i]:
            holders.setdefault(link, set()).add(i)
    for i in within:
        for link in mentions[i]:
            if link in holders:
                sharers.setdefault(link, set()).add(i)
    narrow = {a: holders[a] | sharers.get(a, set()) for a in holders}
    wide = {a: narrow[a] | {j for i in sharers.get(a, set()) for j in next_to[i] if j in within} for a in holders}
    top = lambda chunks: max(value[i] for i in chunks)
    readings = {
        "the mean of its chunks' values (narrow)": {a: float(np.mean([value[i] for i in narrow[a]])) for a in narrow},
        "its best chunk's value (narrow)": {a: top(narrow[a]) for a in narrow},
        "the lower of its best holder and its best sharer (only artifacts that are shared)":
            {a: min(top(holders[a]), top(sharers[a])) for a in narrow if a in sharers},
        "its best sharer's value (only artifacts that are shared)": {a: top(sharers[a]) for a in narrow if a in sharers},
        "the mean of its chunks' values (wide)": {a: float(np.mean([value[i] for i in wide[a]])) for a in wide},
    }
    # the artifact's own name (a document's type, a PR's title, a URL record's description) against
    # the query side: the question, the description, the closest query tag
    known = [a for a in narrow if a in name_at]
    if known:
        at = np.array([name_at[a] for a in known])
        by_name = {"the question": named["question"][at], "the description": named["description"][at],
                   "the closest query tag": named["tags"][:, at].max(axis=0)}
        by_name["question, description and closest tag (standings added)"] = sum(standing(v) for v in by_name.values())
        for label, v in by_name.items():
            readings[f"its name's closeness to {label}"] = dict(zip(known, v.tolist()))
        if gold is not None:
            best = max(known, key=lambda a: len(wide[a] & gold))
            if wide[best] & gold:
                for label, v in by_name.items():
                    name_rank.setdefault(label, []).append(1 + int((v > v[known.index(best)]).sum()))
                name_rank.setdefault("artifacts in the branch", []).append(len(known))
    out = {"the three routes' standings added, no areas": plain}

    def areas_first(reading, areas):
        seen, order = set(), []
        for a in sorted(reading, key=lambda a: (-reading[a], a)):
            for i in sorted(areas[a], key=lambda i: (-value[i], id_rank[i])):
                if i not in seen:
                    seen.add(i)
                    order.append(i)
        return order + [i for i in plain if i not in seen]

    def in_turn(reading, areas):
        """One area, then the best chunk of the plain order not taken yet, in turn."""
        seen, order, at = set(), [], 0
        for a in sorted(reading, key=lambda a: (-reading[a], a)):
            for i in sorted(areas[a], key=lambda i: (-value[i], id_rank[i])):
                if i not in seen:
                    seen.add(i)
                    order.append(i)
            while at < len(plain) and plain[at] in seen:
                at += 1
            if at < len(plain):
                seen.add(plain[at])
                order.append(plain[at])
        return order + [i for i in plain if i not in seen]

    for name, reading in readings.items():
        out[f"areas first, an area valued by {name}, delivered narrow"] = areas_first(reading, narrow)
        out[f"areas first, an area valued by {name}, delivered wide"] = areas_first(reading, wide)
        out[f"an area and a plain chunk in turn, an area valued by {name}, delivered wide"] = in_turn(reading, wide)
    return out


got_names = np.load(HERE / "artifact_titles_query.npz", allow_pickle=True)
NAMES = np.asarray(got_names["matrix"], dtype=np.float32)
name_at = {str(link): k for k, link in enumerate(got_names["ids"])}
name_rank = {}
scores = {"gold": {}, "gauged": {}}
right = 0
done = 0
for qid in wanted:
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    description, tags, asked = side_of(q)
    got, _, _ = V._tag_cosines(description, tags, p)
    rows, d_description = list(got["tags"]), np.asarray(got["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    on_edge = rows[:, layer["edge_tag"]]
    t_near, t_edge = WK.best_edges(on_edge.max(axis=0), layer["edge_chunk"], n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    signal = {"tags": t_near, "description": d_description, "question": d_question}
    gold = np.array([bool(records[i] & cites) for i in range(n)])
    main = Counter(branch_of[np.flatnonzero(gold)].tolist()).most_common(1)[0][0]
    by_question = np.lexsort((id_rank, -d_question))
    counts = np.bincount(branch_of[by_question[:kept_of(by_question)]], minlength=len(branches))
    gauged = int(counts.argmax())
    right += int(gauged == main)
    axes = V._QueryAxes(p.tag_vectors, NAMES)
    tag_names = [np.asarray(V._query_cosines(description, part, axes, "query")[0]["query_chunk_cosines"], dtype=np.float64)
                 for part in (tags, asked) if part]
    named = {"tags": np.vstack(tag_names),
             "description": np.asarray(V._query_cosines(description, tags, axes, "query")[0]["query_description_cosines"],
                                       dtype=np.float64),
             "question": np.asarray(V._query_cosines(q.question, [], axes, "query")[0]["query_description_cosines"],
                                    dtype=np.float64)}
    for where, branch in (("gold", main), ("gauged", gauged)):
        inside = np.flatnonzero(branch_of == branch)
        found = orders_for(inside, signal, named, set(np.flatnonzero(gold).tolist()) if where == "gold" else None)
        for name, order in found.items():
            scores[where].setdefault(name, []).append(recall_of(order, cites))
    done += 1
    if done % 20 == 0:
        print(f"  ... {done} questions", flush=True)

m = len(wanted)
print(f"\n{SET}: {m} questions; the branch the question route points at is the gold's on {right}")
print("== context_recall_id at the budget, mean over the questions: inside the gold's branch | inside the branch the "
      "question route points at ==")
for name in sorted(scores["gold"], key=lambda k: -float(np.mean(scores["gold"][k]))):
    print(f"  {float(np.mean(scores['gold'][name])):.3f} | {float(np.mean(scores['gauged'][name])):.3f}  {name}")
print()
print("== the artifact whose wide area holds the most gold: its place among the branch's artifacts by its name's closeness ==")
for label, values in name_rank.items():
    if label != "artifacts in the branch":
        print(f"  to {label}: middle place {np.median(values):.0f}, first on {sum(1 for v in values if v == 1)} of {len(values)}, "
              f"within the first five on {sum(1 for v in values if v <= 5)}")
print(f"  artifacts in the branch: middle {np.median(name_rank.get('artifacts in the branch', [0])):.0f}")
np.save(HERE / f"areas_orders__{SET}.npy", scores, allow_pickle=True)
print("done", flush=True)
