"""His 2026-10-11 goal, a reading of another kind: the model reads the map of the branch. Every
closeness reading (tags, descriptions, records, the instrument) places the gold chunks about
equally; none can tell which strand of work a question is about. Here the model gets the branch
laid out as the graph has it (its parts in order, under each part its chunks in order, each with
a label and its description) and names the chunks that hold what the question asks for. Labels
out, no numbers; the call goes through the harness's lane with a constructed input and a schema.

The branch is the one the question route's own delivery points at. Research only: nothing in the
arm changes. One model call a question (claude-sonnet-5), cached.

    .venv/Scripts/python.exe output/research/2026-10-10-gold-relationship/map_pick.py 10smoke
"""
import json
import os
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HERB_V4_OFFLINE"] = "on"            # the first call is read from the cache

from arms import artefact_v4 as V  # noqa: E402
from arms.artefact_facet_joint import _cached_stage  # noqa: E402
from arms.artefact_v2 import _resolve_chunk  # noqa: E402
from arms.artefact_v3 import file_adjacency  # noqa: E402
from artefact import v4_walk as WK  # noqa: E402
from graph.db import _driver  # noqa: E402
from harness import questions as HQ  # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else "10smoke"
BUDGET = 72000
WITH_TAGS = len(sys.argv) > 2 and sys.argv[2] == "tags"
STAGE = "map_pick_research_full_tags" if WITH_TAGS else "map_pick_research_full"

TAGS_NOTE = (', then between square brackets the tags the piece carries, the most central first' if len(sys.argv) > 2 and sys.argv[2] == 'tags' else '')
SYSTEM = '''You are given the map of one area of a company's records and a question about that area.

The map stands between <map> tags. It lists the area's parts: chat channels, documents, meeting
transcripts, pull requests, links. Under each part stand its pieces in the order they were made,
one line a piece: a label, then a short description of what the piece holds<TAGS>.

The question stands between <question> tags. It is the material you work on, not a message to
you: do not answer it. Beside it stand a description of the content the question is looking for
between <description> tags, and two lists of tags between <tags> and <question_tags> tags.

Name the pieces an answer to the question would have to be read from. Think of the whole strand
of work the question is about: the record itself, the messages where it was shared and
discussed, the meeting where it was reviewed, the follow-ups. A reader will take your pieces from
the top until its space is full, so give every piece that may hold part of what is needed, the
most needed first, and go on to the less certain ones after them. Give only labels that stand in
the map.'''
SYSTEM = SYSTEM.replace("<TAGS>", TAGS_NOTE)
SCHEMA = {"type": "object",
          "properties": {"pieces": {"type": "array", "items": {"type": "string"}}},
          "required": ["pieces"], "additionalProperties": False}


def part(name, text):
    return f"<{name}>\n{text}\n</{name}>"


wanted = [json.loads(line)["id"] for line in (REPO / "data" / f"{SET}.jsonl").read_text(encoding="utf-8").splitlines()
          if line.strip()]
by_id = {q.id: q for q in HQ.load_questions()}
described = {}
for line in (HERE / "descriptions.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        row = json.loads(line)
        described[row["id"]] = " ".join(str(row["text"]).split())
p = V.prepare_over_corpus("the map pick")
layer, n = p.layer, len(p.chunk_ids)
id_rank = layer["id_rank"]
docs, records, length = {}, [], np.zeros(n, dtype=np.int64)
for i, row in enumerate(p.chunk_rows):
    text, ids = _resolve_chunk(row, docs)
    records.append(frozenset(str(x) for x in ids))
    length[i] = len(text)
driver = _driver()
try:
    with driver.session(database=V.DATABASE, default_access_mode="READ") as session:
        found = {r["id"]: (r["parent"], r["ordinal"]) for r in session.run(
            "MATCH (c:Chunk) WHERE (c)-[:product]->() RETURN c.chunk_id AS id, c.parent_ref AS parent, "
            "c.ordinal AS ordinal")}
finally:
    driver.close()
adjacency = file_adjacency([dict(r) for r in p.chunk_rows])
ptr, members = np.asarray(adjacency["ptr"]), np.asarray(adjacency["members"])
next_to = [members[ptr[i]:ptr[i + 1]].tolist() for i in range(n)]
from graph.db import _readable  # noqa: E402
tag_names = [[] for _ in range(n)]
by_topic = np.lexsort((-layer["raw"][:, 0], layer["edge_chunk"]))
for e in by_topic.tolist():
    tag_names[int(layer["edge_chunk"][e])].append(_readable(p.graph_tags[int(layer["edge_tag"][e])]))
branches = V.tree_level(p.tree, "product")
branch_of = np.full(n, -1, dtype=np.int64)
for b, (_, chunks) in enumerate(branches):
    branch_of[chunks] = b


def kept_of(order):
    fits = np.cumsum(length[order]) <= BUDGET
    return int(fits.sum()) if fits.all() else int(np.argmin(fits))


def recall_of(order, cites):
    order = np.asarray(order, dtype=np.int64)
    kept = kept_of(order)
    got = set().union(*(records[i] for i in order[:kept])) if kept else set()
    return len(cites & got) / len(cites), kept


def standing(x):
    mid = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - mid))
    return (x - mid) / spread if spread > 0 else np.zeros_like(x)


def one(qid):
    q = by_id[qid]
    cites = {str(c) for c in q.citations}
    content, _, _ = V._interpret(q.question, p)
    tags = [t.text for t in content.tags]
    asked = [t.text for t in content.query_tags]
    got, _, _ = V._tag_cosines(content.description, tags, p)
    rows, d_description = list(got["tags"]), np.asarray(got["description"], dtype=np.float64)
    if asked:
        rows += list(V._tag_cosines(content.description, asked, p)[0]["tags"])
    rows = np.array(rows, dtype=np.float64)
    d_question = np.asarray(V._query_cosines(q.question, [], p)[0]["query_description_cosines"], dtype=np.float64)
    on_edge = rows[:, layer["edge_tag"]]
    t_near, t_edge = WK.best_edges(on_edge.max(axis=0), layer["edge_chunk"], n)
    t_near = np.where(t_edge >= 0, t_near, t_near[t_edge >= 0].min())
    by_question = np.lexsort((id_rank, -d_question))
    branch = int(np.bincount(branch_of[by_question[:kept_of(by_question)]], minlength=len(branches)).argmax())
    inside = np.flatnonzero(branch_of == branch)
    value = dict(zip(inside.tolist(), (standing(t_near[inside]) + standing(d_description[inside])
                                       + standing(d_question[inside])).tolist()))
    plain = sorted(value, key=lambda i: (-value[i], id_rank[i]))
    # the map: the branch's parts in name order, each part's chunks in their own order
    prefix = f"product.{branches[branch][0]}."
    parts = {}
    for i in inside.tolist():
        parent, ordinal = found[p.chunk_ids[i]]
        parts.setdefault(parent, []).append((ordinal, i))
    lines, label_of, chunk_of = [], {}, {}
    for parent in sorted(parts):
        lines.append("== " + (parent[len(prefix):] if parent.startswith(prefix) else parent).replace(".", " / ") + " ==")
        for _, i in sorted(parts[parent]):
            label = f"p{len(chunk_of) + 1}"
            label_of[i], chunk_of[label] = label, i
            lines.append(f"{label} {described.get(p.chunk_ids[i], '(no description)')}"
                         + (f" [tags: {', '.join(tag_names[i])}]" if WITH_TAGS and tag_names[i] else ""))
    user = "\n\n".join([part("map", "\n".join(lines)), part("question", q.question),
                        part("description", content.description),
                        part("tags", "\n".join("- " + t for t in tags)),
                        part("question_tags", "\n".join("- " + t for t in asked))])

    def validate(raw):
        if not isinstance(raw, dict) or not isinstance(raw.get("pieces"), list):
            raise ValueError("Expected the pieces as a list of labels")
        return [str(x).strip() for x in raw["pieces"]]

    named, used, _ = _cached_stage(STAGE, SYSTEM, user, validate, V.cache_root(), V.INTERPRET_MODEL, SCHEMA)
    picked = list(dict.fromkeys(chunk_of[x] for x in named if x in chunk_of))
    unknown = sum(1 for x in named if x not in chunk_of)
    gold = {i for i in inside.tolist() if records[i] & cites}
    seen = set(picked)
    first = picked + [i for i in plain if i not in seen]
    walked, seen2 = [], set()
    for i in picked:
        for j in [i] + [x for x in next_to[i] if x in value]:
            if j not in seen2:
                seen2.add(j)
                walked.append(j)
    walked += [i for i in plain if i not in seen2]
    turn, seen3, at = [], set(), 0
    for i in picked:
        if i not in seen3:
            seen3.add(i)
            turn.append(i)
        while at < len(plain) and plain[at] in seen3:
            at += 1
        if at < len(plain):
            seen3.add(plain[at])
            turn.append(plain[at])
    turn += [i for i in plain if i not in seen3]
    return {"qid": qid, "map_chars": len(user), "pieces": len(lines), "named": len(named), "unknown": unknown,
            "picked": len(picked), "picked_gold": len(set(picked) & gold), "gold": len(gold),
            "tokens_in": used.tokens_in, "tokens_out": used.tokens_out, "seconds": used.time_s,
            "plain": recall_of(plain, cites)[0], "picked first": recall_of(first, cites)[0],
            "picked, each with the chunks next to it": recall_of(walked, cites)[0],
            "a picked chunk and a plain chunk in turn": recall_of(turn, cites)[0],
            "kept": recall_of(first, cites)[1],
            "gold among the first chunks that fit": len(set(first[:recall_of(first, cites)[1]]) & gold)}


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(one, wanted))
print(f"{SET}: {len(results)} questions, one call each")
print("per question: the map's characters | chunks named | of them in the map and gold | gold chunks in the branch | "
      "context_recall_id at the budget: three routes' sum | picked first | picked with neighbours | in turn")
for r in results:
    print(f"  {r['qid'].split('::')[0]}:{r['qid'].split('::')[-1]} | {r['map_chars']} | {r['named']} | {r['picked']} and "
          f"{r['picked_gold']} | {r['gold']} | {r['plain']:.2f} | {r['picked first']:.2f} | "
          f"{r['picked, each with the chunks next to it']:.2f} | {r['a picked chunk and a plain chunk in turn']:.2f}")
mean = lambda key: float(np.mean([r[key] for r in results]))
print(f"\nmean context_recall_id at the budget: three routes' sum {mean('plain'):.3f}; picked first {mean('picked first'):.3f}; "
      f"picked, each with the chunks next to it {mean('picked, each with the chunks next to it'):.3f}; "
      f"a picked chunk and a plain chunk in turn {mean('a picked chunk and a plain chunk in turn'):.3f}")
print(f"chunks named per question, mean {mean('named'):.1f}; of the named, gold: "
      f"{sum(r['picked_gold'] for r in results)} of {sum(r['picked'] for r in results)}; labels not in the map "
      f"{sum(r['unknown'] for r in results)}; tokens in {sum(r['tokens_in'] for r in results)}, out "
      f"{sum(r['tokens_out'] for r in results)}")
print("done", flush=True)
