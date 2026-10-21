"""Checks behind the answers to the analyst: counts only, no question, answer, gold or text printed.

1. which records each arm can reach (its pool) and whether every cited evidence record is in it
2. how much of the artefact's handed-over characters the JSON form takes, against the baselines' form
3. the artefact's texts that are a slice of one document, and the ids they are credited with
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Coding\exjobbet\GRAG-Job")
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]
from harness.record_text import ARTIFACT_TYPES, record_text  # noqa: E402

RUNS = {"lucene": "lucene__gold100__cb72000__20261008T234209Z",
        "vector": "vector__gold100__cb72000__20261017T061242Z",
        "artefact": "artefact_v4__gold100__cb72000__20261020T041923Z"}
HERB = ROOT / "data/raw/Salesforce__HERB"


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


gold_ids = {r["id"] for r in rows(ROOT / "data/gold100.jsonl")}
cites = {q["id"]: [str(c) for c in q["citations"]] for q in rows(ROOT / "data/questions.jsonl")
         if q["id"] in gold_ids}
assert len(cites) == 100

# every record of the six kinds in the product files
kind_of, rec_of, dup = {}, {}, 0
files = sorted((HERB / "products").glob("*.json"))
for f in files:
    data = json.loads(f.read_text(encoding="utf-8"))
    for kind in ARTIFACT_TYPES:
        for rec in data.get(kind) or []:
            rid = rec.get("id")
            if rid is None:
                continue
            rid = str(rid)
            if rid in kind_of:
                dup += 1
            kind_of[rid], rec_of[rid] = kind, rec
print(f"product files {len(files)}; records of the six kinds with an id: {len(kind_of)} (ids seen twice: {dup})")

# the artefact's pool, from the graph it ran on
from neo4j import GraphDatabase  # noqa: E402
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
man = json.loads((ROOT / "output/k=chars" / RUNS["artefact"] / "run_manifest.json").read_text(encoding="utf-8"))
db = man["index"]["graph"]
POOL = ('c.desc_emb IS NOT NULL AND (c)-[:product]->() '
        'AND EXISTS { MATCH (c)-[r:HAS_TAG]->() WHERE r.run_id = $run }')
drv = GraphDatabase.driver(os.environ.get("NEO4J_URI", "neo4j://localhost:7687"),
                           auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
                           notifications_min_severity="OFF")
with drv.session(database=db) as s:
    pool_rows = [dict(r) for r in s.run(
        f"MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE {POOL} "
        "RETURN c.chunk_id AS chunk, c.locator_json AS locator, f.rel_path AS relpath",
        run="pilot_full_herb")]
drv.close()
docs = {}
art_pool, slice_chunks = set(), 0
for r in pool_rows:
    loc = json.loads(r["locator"])
    rel = r["relpath"].replace("\\", "/")
    if rel not in docs:
        p = HERB / rel if (HERB / rel).exists() else HERB / "products" / Path(rel).name
        docs[rel] = json.loads(p.read_text(encoding="utf-8"))
    sec = docs[rel][loc["section"]]
    idx = loc["indices"] if "indices" in loc else [loc["index"]]
    slice_chunks += "char_range" in loc
    for i in idx:
        rid = sec[i].get("id")
        if rid is not None:
            art_pool.add(str(rid))
print(f"artefact pool: {len(pool_rows)} chunks ({slice_chunks} a slice of one document), "
      f"{len(art_pool)} distinct records; of them outside the six kinds: {len(art_pool - set(kind_of))}")
print(f"records of the six kinds the artefact pool does not reach: {len(set(kind_of) - art_pool)} "
      f"by kind {dict(Counter(kind_of[i] for i in set(kind_of) - art_pool))}")

# 1. cited evidence against each pool
all_cited = [(q, c) for q, cs in cites.items() for c in cs]
print(f"cited evidence: {len(all_cited)} (question, record) pairs, {len({c for _, c in all_cited})} records; "
      f"by kind {dict(Counter(kind_of.get(c, 'not one of the six kinds') for _, c in all_cited))}")
base_out = [(q, c) for q, c in all_cited if c not in kind_of]
art_out = [(q, c) for q, c in all_cited if c not in art_pool]
print(f"  outside the baselines' records: {len(base_out)} pairs in {len({q for q, _ in base_out})} questions")
print(f"  outside the artefact's pool: {len(art_out)} pairs in {len({q for q, _ in art_out})} questions; "
      f"by kind {dict(Counter(kind_of.get(c, 'not one of the six kinds') for _, c in art_out))}")

# 2. and 3. the artefact's handed-over texts
d = ROOT / "output/k=chars" / RUNS["artefact"]
json_chars = form_chars = whole_records = 0
by_kind = Counter()
by_kind_form = Counter()
slice_texts, slice_credit, slice_cited = 0, Counter(), 0
slice_cover = []
for r in rows(d / "arm_outputs.jsonl"):
    texts, id_lists = r["contexts"], r["meta"]["chunk_ids"]
    cut = r["meta"]["char_budget"].get("boundary")
    seen = set()
    passed_slices = {}
    for n, (text, ids) in enumerate(zip(texts, id_lists)):
        whole_text = not (cut and n == len(texts) - 1)
        if not text.startswith("{"):          # a slice of one document's text
            if whole_text:
                slice_texts += 1
                for i in ids:
                    passed_slices[str(i)] = passed_slices.get(str(i), 0) + len(text)
            continue
        lines = text.split("\n")
        complete = lines if whole_text else lines[:-1]
        for line in complete:
            rec = json.loads(line)
            rid = str(rec.get("id"))
            if rid in seen:
                continue
            seen.add(rid)
            k = kind_of[rid]
            whole_records += 1
            json_chars += len(line)
            f = len(record_text(k, rec))
            form_chars += f
            by_kind[k] += len(line)
            by_kind_form[k] += f
    for rid, chars in passed_slices.items():
        rec = rec_of[rid]
        full = len(rec.get("content") or rec.get("transcript") or rec.get("text") or "")
        slice_cover.append(chars / full if full else 1.0)
        credited_elsewhere = rid in seen
        if not credited_elsewhere:
            slice_credit[kind_of[rid]] += 1
            slice_cited += rid in cites[r["id"]]
print(f"artefact records passed whole (once per question): {whole_records}; JSON chars {json_chars:,}; "
      f"the same records in the baselines' form {form_chars:,} ({1 - form_chars / json_chars:.0%} fewer)")
for k in by_kind:
    print(f"  {k}: JSON {by_kind[k]:,} -> form {by_kind_form[k]:,} ({1 - by_kind_form[k] / by_kind[k]:.0%} fewer); "
          f"share of the JSON chars {by_kind[k] / json_chars:.0%}")
cover = sorted(slice_cover)
print(f"slice texts passed whole: {slice_texts}; documents credited only through slices: {sum(slice_credit.values())} "
      f"{dict(slice_credit)}; of them cited evidence of their question: {slice_cited}")
if cover:
    print(f"  share of the document's text the passed slices hold: min {cover[0]:.2f}, median "
          f"{cover[len(cover) // 2]:.2f}, max {cover[-1]:.2f}; whole document (>= 0.99): "
          f"{sum(c >= 0.99 for c in cover)} of {len(cover)}")
