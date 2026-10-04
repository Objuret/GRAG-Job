"""Five facet statistics per HAS_TAG edge, computed from the corpus text, never from a model.

    topic        cosine(Tag.emb, Chunk.desc_emb)                       (ruled 09-08)
    temporal     (DATE/TIME entities + past/perfect/future finite verbs) / tokens
    why          share of sentences holding an explicit PDTB Cause/Purpose connective (no "if")
    activity     share of sentences whose root verb is not in the textbook stative classes
    concreteness (numbers + named entities) / tokens                    (Louis & Nenkova NE+CD)
    No word list of the tool's own (struck 09-08: "we will NOT use your random made up
    'check words'"); the lists above are PDTB's connectives and Quirk et al.'s stative classes.

--anchor chunk (the build, 2026-09-09): the four text statistics are counted once per chunk on
all its sentences; on the edge they stand beside topic, and the part's facet order in the sort
combines them — his 09-08 13:02 combo (the chunk's weight of the facet AND the tag's relevance
to the chunk), with the statistic in place of the model. No string match, no new embedding.
--anchor string (the 09-09 first pass, kept for the record): counted on the sentences holding
the tag phrase verbatim, else at least half its content words; 5.1% of edges had none. Struck
09-09: *"NEARNESS, we cant fucking use explicit shit"*.

Writes output/facet_stats/<db>.jsonl (+ .overlay.json with --overlay) and prints the spread.
Reads the graph only.
    NEO4J_DATABASE=herb-eval-volmax .venv/Scripts/python.exe test/graph/facet_stats.py [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

# stative verbs, the textbook classes only (Quirk, Greenbaum, Leech & Svartvik 1985, §4.28–4.31):
# being and having; perception; cognition; emotion and attitude; relation. Nothing added.
STATIVE = set("""be have exist remain seem appear
see hear smell taste
know believe think understand suppose remember forget doubt recognise recognize mean
want need like love hate prefer wish fear hope mind
belong contain consist own possess include involve depend resemble lack matter deserve
equal comprise concern""".split())

# PDTB 2.0 explicit connectives annotated CONTINGENCY.Cause (reason / result) or
# CONTINGENCY.Purpose (PDTB-3 sense), lower-cased. Condition ("if", "unless", "in case") is NOT
# counted: on this corpus "if" is "let me know if", not cause. No phrase added beyond the list.
WHY_PHRASES = ["because", "because of", "so that", "in order to", "in order that", "due to",
               "as a result", "as a consequence", "consequently", "therefore", "thus", "hence",
               "for that reason", "for this reason", "to this end", "so as to", "owing to",
               "thanks to", "accordingly", "as a result of", "given that", "now that",
               "insofar as", "inasmuch as", "on account of", "for the purpose of", "lest"]
WHY_RE = re.compile(r"\b(" + "|".join(re.escape(p) for p in WHY_PHRASES) + r")\b")
# "since" / "as" / "so" are Cause connectives only as clause-introducing SCONJ (PDTB counts
# them as Contingency.Cause when so used); decided on the parse.
WHY_SCONJ = {"since", "as", "so"}

# temporal expressions are what the NER tags TIMEX-like (DATE, TIME); no word list of my own.
TEMPORAL_ENTS = {"DATE", "TIME"}
CONCRETE_ENTS = {"PERSON", "ORG", "PRODUCT", "GPE", "LOC", "FAC", "MONEY", "PERCENT", "QUANTITY",
                 "CARDINAL", "ORDINAL", "EVENT", "WORK_OF_ART", "LAW", "NORP"}


def load_env() -> None:
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def fetch(db: str, limit: int | None):
    from neo4j import GraphDatabase
    drv = GraphDatabase.driver(os.environ.get("NEO4J_URI", "neo4j://localhost:7687"),
                               auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))
    q = """MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
           WITH c, collect({name: t.name, emb: t.emb}) AS tags
           MATCH (f:File) WHERE f.file_id = c.file_id
           RETURN c.chunk_id AS chunk_id, c.kind AS kind, c.locator_json AS loc, c.desc_emb AS desc_emb,
                  f.rel_path AS rel_path, tags"""
    if limit:
        q += f" LIMIT {int(limit)}"
    with drv.session(database=db) as s:
        return s.run(q).data()


_cache: dict = {}


def _walk(doc, parts):
    cur = doc
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        elif isinstance(cur, dict) and len(cur) == 1 and isinstance(next(iter(cur.values())), (dict, list)):
            cur = next(iter(cur.values()))
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
    return cur


def _flat(x, out):
    if isinstance(x, dict):
        for v in x.values():
            _flat(v, out)
    elif isinstance(x, list):
        for v in x:
            _flat(v, out)
    elif isinstance(x, str):
        out.append(x)
    return out


def resolve_text(loc_json: str, rel_path: str) -> str | None:
    loc = json.loads(loc_json)
    if "metadata" in loc:
        return None
    if rel_path not in _cache:
        _cache[rel_path] = json.loads((ROOT / "data" / "corpus" / rel_path).read_text(encoding="utf-8"))
    sec = _walk(_cache[rel_path], loc["parent_ref"].split(".")[1:])
    if not isinstance(sec, list):
        return None
    idx = loc.get("indices") or [loc["index"]]
    try:
        items = [sec[i] for i in idx]
    except (IndexError, TypeError):
        return None
    if "field" in loc and "char_range" in loc and isinstance(items[0], dict):
        s = items[0].get(loc["field"], "")
        if isinstance(s, str):
            a, b = loc["char_range"]
            return s[a:b]
    return "\n".join(_flat(items, []))


def anchor_sentences(doc, tag: str):
    tl = tag.lower()
    hits = [s for s in doc.sents if tl in s.text.lower()]
    if hits:
        return hits, "verbatim"
    words = re.findall(r"[a-z0-9]{4,}", tl)
    if not words:
        return [], "none"
    out = []
    for s in doc.sents:
        st = s.text.lower()
        if sum(w in st for w in words) / len(words) >= 0.5:
            out.append(s)
    return out, ("partial" if out else "none")


def facet_stats(sents) -> dict:
    n_tok = sum(1 for s in sents for t in s if not t.is_space and not t.is_punct)
    if n_tok == 0:
        return {}
    timex = verbs_nonpresent = num = ne = why_sents = dyn_sents = 0
    seen_ents = set()
    for s in sents:
        for e in s.ents:
            if e.start in seen_ents:
                continue
            seen_ents.add(e.start)
            if e.label_ in TEMPORAL_ENTS:
                timex += 1
            if e.label_ in CONCRETE_ENTS:
                ne += 1
        for t in s:
            if t.is_punct or t.is_space:
                continue
            low = t.lower_
            if t.like_num and t.ent_type_ == "":
                num += 1
            if t.pos_ in ("VERB", "AUX") and t.morph.get("VerbForm") == ["Fin"]:
                tense = t.morph.get("Tense")
                aspect = t.morph.get("Aspect")
                if tense == ["Past"] or aspect == ["Perf"] or (t.pos_ == "AUX" and low in ("will", "shall", "wo")):
                    verbs_nonpresent += 1
        st = s.text.lower()
        is_why = bool(WHY_RE.search(st)) or any(t.lower_ in WHY_SCONJ and t.pos_ == "SCONJ" for t in s)
        why_sents += is_why
        root = s.root
        if root.pos_ == "VERB" and root.lemma_.lower() not in STATIVE:
            dyn_sents += 1
    n_s = len(sents)
    return {"temporal": (timex + verbs_nonpresent) / n_tok,
            "why": why_sents / n_s,
            "activity": dyn_sents / n_s,
            "concreteness": (num + ne) / n_tok,
            "n_sent": n_s, "n_tok": n_tok}


def cos(a, b):
    if a is None or b is None:
        return None
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / d) if d else None


def spread(rows, key, group):
    by = defaultdict(list)
    for r in rows:
        v = r.get(key)
        if v is not None:
            by[r[group]].append(v)
    multi = [np.std(v) for v in by.values() if len(v) > 1]
    return (float(np.mean(multi)) if multi else float("nan")), len(multi)


FACETS = ["topic", "temporal", "why", "activity", "concreteness"]


def report(rows, anchored):
    n = len(rows)
    print("anchor: " + "  ".join(f"{k} {v/n:.1%}" for k, v in sorted(anchored.items())) + f"   ({n} edges)")
    chunk_level = set(anchored) == {"chunk"}
    print(f"\n{'facet':13}{'n':>7}{'distinct':>9}{'zero':>7}{'p10':>7}{'p50':>7}{'p90':>7}"
          f"{'sd/tag':>8}" + ("" if chunk_level else f"{'sd/chunk':>9}")
          + ("   (sd/chunk is 0 by construction: chunk-level statistics)" if chunk_level else ""))
    for f in FACETS:
        v = np.array([r[f] for r in rows if r[f] is not None], dtype=float)
        if not len(v):
            print(f"{f:13} none")
            continue
        sdt, _ = spread(rows, f, "tag")
        sdc, _ = spread(rows, f, "chunk_id")
        print(f"{f:13}{len(v):7d}{len(np.unique(np.round(v, 4))):9d}{(v == 0).mean():7.1%}"
              f"{np.percentile(v, 10):7.3f}{np.percentile(v, 50):7.3f}{np.percentile(v, 90):7.3f}"
              f"{sdt:8.3f}" + ("" if chunk_level or f == "topic" else f"{sdc:9.3f}")
              + (f"{sdc:9.3f}" if f == "topic" and chunk_level else ""))
    full = [r for r in rows if all(r[f] is not None for f in FACETS)]
    M = np.array([[r[f] for f in FACETS] for r in full], dtype=float)
    from scipy.stats import spearmanr
    rho = spearmanr(M).correlation
    print(f"\nSpearman between facets, {len(full)} edges with all five:")
    print(" " * 13 + "".join(f"{f[:6]:>8}" for f in FACETS))
    for i, f in enumerate(FACETS):
        print(f"{f:13}" + "".join(f"{rho[i, j]:8.2f}" for j in range(5)))


def write_overlay(rows, db: str, out_path: Path) -> Path:
    """the arm's input: output/facet_stats/<db>.overlay.json, five values per edge in FACETS
    order, null where the tag could not be anchored; read by artefact_v3 (FACET_SOURCE=stats)"""
    run_id = os.environ.get("HERB_TAG_RUN_ID", "pilot_full_herb")
    import hashlib
    import spacy
    anchors = sorted({r["anchor"] for r in rows})
    body = {"database": db, "run_id": run_id, "facets": FACETS,
            "method": ("temporal, why, activity, concreteness: text statistics per "
                       + ("chunk on all its sentences" if anchors == ["chunk"] else f"anchor ({', '.join(anchors)})")
                       + "; topic = cosine(Tag.emb, Chunk.desc_emb)"),
            "tool": "test/graph/facet_stats.py",
            "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "spacy": spacy.__version__, "spacy_model": "en_core_web_sm",
            "spacy_model_version": spacy.load("en_core_web_sm").meta.get("version"),
            "source": str(out_path), "edges": [
                {"tag": r["tag"], "chunkId": r["chunk_id"], "anchor": r["anchor"],
                 "weights": [r[f] for f in FACETS]} for r in rows]}
    p = out_path.with_suffix(".overlay.json")
    p.write_text(json.dumps(body), encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--report-only", action="store_true", help="re-print the report from the written file")
    ap.add_argument("--overlay", action="store_true",
                    help="also write <db>.overlay.json for artefact_v3 (from the written file when "
                         "combined with --report-only)")
    ap.add_argument("--anchor", choices=("chunk", "string"), default="chunk",
                    help="chunk: the four statistics per chunk on all its sentences (the build); "
                         "string: on the sentences holding the tag phrase (struck 09-09)")
    args = ap.parse_args()
    load_env()
    db = os.environ.get("NEO4J_DATABASE", "herb-eval")
    out_path = ROOT / "output" / "facet_stats" / f"{db}.jsonl"
    if args.report_only:
        rows = [json.loads(l) for l in out_path.open(encoding="utf-8")]
        anchored = defaultdict(int)
        for r in rows:
            anchored[r["anchor"]] += 1
        report(rows, anchored)
        if args.overlay:
            print(f"[facet_stats] overlay -> {write_overlay(rows, db, out_path)}")
        return
    t0 = time.time()
    print(f"[facet_stats] graph {db}: fetching chunks and tags ...", flush=True)
    data = fetch(db, args.limit)
    print(f"[facet_stats] {len(data)} chunks, {sum(len(d['tags']) for d in data)} edges  "
          f"({time.time()-t0:.0f}s)", flush=True)
    import spacy
    from tqdm import tqdm
    nlp = spacy.load("en_core_web_sm")
    texts, meta, unresolved = [], [], 0
    for d in data:
        txt = resolve_text(d["loc"], d["rel_path"])
        if txt is None:
            unresolved += 1
            continue
        texts.append(txt)
        meta.append(d)
    print(f"[facet_stats] text resolved for {len(texts)} chunks, unresolved {unresolved}; parsing ...",
          flush=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    anchored = defaultdict(int)
    with out_path.open("w", encoding="utf-8") as fh:
        for d, doc in tqdm(zip(meta, nlp.pipe(texts, batch_size=32)), total=len(texts), unit="chunk",
                           mininterval=2.0):
            chunk_st = facet_stats(list(doc.sents)) if args.anchor == "chunk" else None
            for tg in d["tags"]:
                if args.anchor == "chunk":
                    st, how = chunk_st, "chunk"
                else:
                    sents, how = anchor_sentences(doc, tg["name"])
                    st = facet_stats(sents) if sents else {}
                anchored[how] += 1
                row = {"chunk_id": d["chunk_id"], "kind": d["kind"], "tag": tg["name"], "anchor": how,
                       "topic": cos(tg["emb"], d["desc_emb"]),
                       "temporal": st.get("temporal"), "why": st.get("why"),
                       "activity": st.get("activity"), "concreteness": st.get("concreteness"),
                       "n_sent": st.get("n_sent"), "n_tok": st.get("n_tok")}
                rows.append(row)
                fh.write(json.dumps(row) + "\n")
    print(f"\n[facet_stats] wrote {len(rows)} edges -> {out_path}  ({time.time()-t0:.0f}s)")
    report(rows, anchored)
    if args.overlay:
        print(f"[facet_stats] overlay -> {write_overlay(rows, db, out_path)}")


if __name__ == "__main__":
    main()
