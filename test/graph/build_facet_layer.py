from __future__ import annotations

if __name__ == "__main__":
    print("build_facet_layer: five derived facet weights per HAS_TAG edge "
          "— loading numpy + neo4j …", flush=True)

import collections
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path

import numpy as np

from graph.backup_facet_weights import require_backup
from graph.db import ALL_FACETS, DATABASE, DATASET_ID, EXCLUDED_SECTIONS, RUN_ID, _driver, _env_float, _unit
from harness.progress import progress

CORPUS = Path(__file__).resolve().parent.parent.parent / "data" / "corpus"

BUILD_DATABASE = "herb-eval-volmax"

DERIVED_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "derived_facet_cache"

PAIR_ANCHOR = "pair-record"

DERIVED_NN_K = 25

DERIVED_MIN_CLASS = 20

FACET_PRIOR = _env_float("HERB_FACET_PRIOR", 0.5)

EMB_BATCH = 2000
COS_BLOCK = 2000
WRITE_BATCH = 1000

REGISTER = {
    "numeral": re.compile(r"\b\d[\d,\.]*\b"),
    "percent": re.compile(r"\d+\s?%"),
    "money": re.compile(r"[$€£]\s?\d"),
    "unit": re.compile(r"\b\d+\s?(ms|s|kb|mb|gb|tb|k|m|bn|x)\b", re.I),
    "url": re.compile(r"https?://"),
    "question": re.compile(r"\?"),
    "modal": re.compile(r"\b(should|must|will|may|could|would|shall)\b", re.I),
    "causal": re.compile(r"\b(because|therefore|thus|hence|so that|due to)\b", re.I),
    "example": re.compile(r"\b(e\.g\.|for example|such as|for instance)\b", re.I),
    "definition": re.compile(r"\b(is defined as|refers to|means that|is a\b)\b", re.I),
    "procedure": re.compile(r"\b(step \d|first,|then,|finally,|procedure|workflow)\b", re.I),
    "first_person": re.compile(r"\b(i|we|our|us)\b", re.I),
    "second_person": re.compile(r"\b(you|your)\b", re.I),
    "code": re.compile(r"[a-z_]+\([^)]*\)|[A-Za-z]+\.[a-z]{2,}\(|```"),
    "bullet": re.compile(r"(^|\\n)\s*[-*•]\s"),
}
PER_CHARS = 1000.0

DOING = ("modal", "causal", "procedure")

MIN_NAME_CHARS = 6
MAX_NAME_TOKENS = 5

MIN_TOKEN_CHARS = 3

ICC_FLOOR = 1e-6
ICC_CEIL = 0.999

SD_FLOOR = 1e-9
TAG_SD_FLOOR = 1e-6

_CHUNKS_CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
RETURN c.chunk_id AS chunkId, c.locator_json AS locator, f.rel_path AS relpath,
       c.section AS section, c.kind AS kind, c.channel AS channel
ORDER BY chunkId
"""

_EDGES_CYPHER = """
MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $runId
RETURN c.chunk_id AS chunkId, t.name AS tag
ORDER BY chunkId, tag
"""

_TAG_EMB_CYPHER = """
UNWIND $keys AS key
MATCH (t:Tag {name: key})
RETURN t.name AS key, t.emb AS emb
"""

_CHUNK_EMB_CYPHER = """
UNWIND $keys AS key
MATCH (c:Chunk {chunk_id: key})
RETURN c.chunk_id AS key, c.desc_emb AS emb
"""

_WRITE_CYPHER = """
UNWIND $rows AS row
MATCH (c:Chunk {chunk_id: row.chunkId})-[r:HAS_TAG]->(t:Tag {name: row.tag})
WHERE r.run_id = $runId
SET r.facets = $facets, r.w_facets = row.weights, r.w_chunk = row.magnitude
REMOVE r.dw_facets, r.dw_chunk
"""


def midrank_cdf(x: np.ndarray, evidenced=None) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    mask = np.ones(len(x), dtype=bool) if evidenced is None else evidenced
    out = np.zeros(len(x), dtype=np.float64)
    values = x[mask]
    if not len(values):
        return out
    order = np.argsort(values, kind="mergesort")
    rank = np.empty(len(values), dtype=np.float64)
    rank[order] = np.arange(1, len(values) + 1)
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    totals = np.zeros(len(counts))
    np.add.at(totals, inverse, rank)
    out[mask] = (totals / counts)[inverse] / (len(values) + 1.0)
    return out


def reliability(n, icc: float) -> np.ndarray:
    n = np.asarray(n, dtype=np.float64)
    icc = min(max(float(icc), ICC_FLOOR), ICC_CEIL)
    return np.where(n >= 1.0, n * icc / (1.0 + (n - 1.0) * icc), 0.0)


def shrink(score: np.ndarray, evidenced: np.ndarray, rho: np.ndarray,
           fallback) -> np.ndarray:
    return rho * midrank_cdf(score, evidenced) + (1.0 - rho) * fallback


def magnitude(phi: np.ndarray) -> np.ndarray:
    a = phi.mean(axis=1)
    q = np.sqrt((phi ** 2).mean(axis=1))
    return np.sqrt(a * q)


def _nth(root, i: int):
    if isinstance(root, list):
        return root[i]
    key, value = list(root.items())[i]
    return {key: value}


def _day(stamp: str) -> int:
    return date(int(stamp[0:4]), int(stamp[5:7]), int(stamp[8:10])).toordinal()


def _stamps(records: list, section) -> tuple:
    days, people = [], []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if section == "slack":
            user = ((rec.get("Message") or {}).get("User") or {})
            if user.get("timestamp"):
                days.append(_day(user["timestamp"]))
            if user.get("userId"):
                people.append(user["userId"])
            for reply in (rec.get("ThreadReplies") or []):
                inner = (reply.get("User") or reply) if isinstance(reply, dict) else None
                if isinstance(inner, dict) and inner.get("timestamp"):
                    days.append(_day(inner["timestamp"]))
        elif section == "prs":
            if rec.get("created_at"):
                days.append(_day(rec["created_at"]))
            if (rec.get("user") or {}).get("login"):
                people.append(rec["user"]["login"])
            for review in (rec.get("reviews") or []):
                if not isinstance(review, dict):
                    continue
                if review.get("submitted_at"):
                    days.append(_day(review["submitted_at"]))
                if (review.get("user") or {}).get("login"):
                    people.append(review["user"]["login"])
        elif section in ("documents", "meeting_transcripts"):
            if rec.get("date"):
                days.append(_day(rec["date"]))
            if rec.get("author"):
                people.append(rec["author"])
            people.extend(rec.get("participants") or [])
    return days, people


_CARRIER_FIELDS = ("id", "date", "author", "type", "document_type", "participants")


def _resolve(locator: dict, doc) -> tuple:
    if "metadata" in locator:
        if "indices" in locator:
            records = [_nth(doc, i) for i in locator["indices"]]
        else:
            record = _nth(doc, locator["index"])
            if locator.get("subsection"):
                record = record[locator["subsection"]]
            records = [record]
        return records, [json.dumps(r, ensure_ascii=False) for r in records]
    section = locator["section"]
    if section in EXCLUDED_SECTIONS:
        raise RuntimeError(f"chunk locator names the excluded section {section!r}")
    array = doc[section]
    if "char_range" in locator:
        record = array[locator["index"]]
        start, end = locator["char_range"]
        field = locator["field"]
        sliced = {field: record[field][start:end]}
        carried = {k: v for k, v in record.items() if k in _CARRIER_FIELDS}
        return [{**sliced, **carried}], [json.dumps(sliced, ensure_ascii=False)]
    indices = locator["indices"] if "indices" in locator else [locator["index"]]
    records = [array[i] for i in indices]
    return records, [json.dumps(r, ensure_ascii=False) for r in records]


def read_chunks(rows: list) -> list:
    docs: dict = {}
    facts = []
    bar = progress(total=len(rows), desc="resolve chunks", unit="chunk")
    for row in rows:
        relpath = row["relpath"]
        doc = docs.get(relpath)
        if doc is None:
            doc = json.loads((CORPUS / relpath).read_text(encoding="utf-8"))
            docs[relpath] = doc
        locator = json.loads(row["locator"])
        records, texts = _resolve(locator, doc)
        section = row["section"] or locator.get("section")
        days, people = _stamps(records, section)
        record_days = [_stamps([rec], section)[0] for rec in records]
        declared = None
        for rec in records:
            if isinstance(rec, dict):
                declared = rec.get("type") or rec.get("document_type") or declared
        facts.append({"text": "\n".join(texts), "texts": texts, "days": days,
                      "record_days": record_days, "channel": row["channel"],
                      "people": people, "declared": declared or row["kind"]})
        bar.update(1)
    bar.close()
    return facts


def _slug(value) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def declared_names(facts: list) -> set:
    root = CORPUS / DATASET_ID
    names = set()

    employees = json.loads((root / "metadata" / "employee.json").read_text(encoding="utf-8"))
    for record in employees.values():
        if isinstance(record, dict):
            names.update(_slug(record[f]) for f in ("name", "org", "role", "location")
                         if record.get(f))

    customers = json.loads((root / "metadata" / "customers_data.json").read_text(encoding="utf-8"))
    for record in customers:
        names.update(_slug(record[f]) for f in ("name", "company", "role") if record.get(f))

    team = json.loads((root / "metadata" / "salesforce_team.json").read_text(encoding="utf-8"))
    for record in team:
        for key, value in record.items():
            if key in ("name", "org") and value:
                names.add(_slug(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        names.add(_slug(item))
                    elif isinstance(item, dict) and item.get("name"):
                        names.add(_slug(item["name"]))

    for product in (root / "products").iterdir():
        names.add(_slug(product.stem))

    for fact in facts:
        if fact["channel"]:
            names.add(_slug(fact["channel"]))
        names.update(_slug(p) for p in fact["people"])

    names.discard("")
    return names


def name_count(tokens: list, long_names: set) -> int:
    count = a = 0
    while a < len(tokens):
        for b in range(min(a + MAX_NAME_TOKENS, len(tokens)), a, -1):
            if "_".join(tokens[a:b]) in long_names:
                count += 1
                a = b
                break
        else:
            a += 1
    return count


def sha256_parity(keys: list) -> np.ndarray:
    return np.array([int(hashlib.sha256(k.encode("utf-8")).hexdigest()[-1], 16) % 2
                     for k in keys])


def register_count(text: str) -> np.ndarray:
    return np.array([len(p.findall(text)) for p in REGISTER.values()], dtype=np.float64)


def standardise(raw: np.ndarray, reference: np.ndarray) -> np.ndarray:
    return ((raw - reference.mean(axis=0)) /
            np.maximum(reference.std(axis=0), SD_FLOOR))


def register_profiles(texts: list) -> np.ndarray:
    raw = np.zeros((len(texts), len(REGISTER)))
    bar = progress(total=len(texts), desc="register features", unit="chunk")
    for i, text in enumerate(texts):
        raw[i] = register_count(text) * PER_CHARS / max(len(text), 1)
        bar.update(1)
    bar.close()
    return standardise(raw, raw)


def record_table(facts: list, names: set) -> dict:
    long_names = {n for n in names if len(n) >= MIN_NAME_CHARS}
    start = np.zeros(len(facts) + 1, dtype=np.int64)
    start[1:] = np.cumsum([len(f["texts"]) for f in facts])
    n = int(start[-1])
    slug, days = [], []
    length = np.zeros(n)
    register = np.zeros((n, len(REGISTER)))
    occurrences = np.zeros(n)
    bar = progress(total=n, desc="record features", unit="record")
    i = 0
    for fact in facts:
        for text, record_days in zip(fact["texts"], fact["record_days"]):
            slugged = _slug(text)
            slug.append(slugged)
            days.append(record_days)
            length[i] = len(text)
            register[i] = register_count(text)
            occurrences[i] = name_count(slugged.split("_"), long_names)
            i += 1
            bar.update(1)
    bar.close()
    return {"start": start, "slug": slug, "length": length, "register": register,
            "names": occurrences, "days": days}


def tag_records(tag: str, slugs: list) -> tuple:
    phrase = _slug(tag)
    hit = [i for i, s in enumerate(slugs) if phrase in s]
    if hit:
        return hit, "verbatim"
    tokens = [p for p in phrase.split("_") if len(p) >= MIN_TOKEN_CHARS]
    if tokens:
        hit = [i for i, s in enumerate(slugs) if all(tok in s for tok in tokens)]
        if hit:
            return hit, "all_tokens"
    return [], "none"


def background_z(U: np.ndarray, D: np.ndarray, rows: np.ndarray,
                 cols: np.ndarray) -> np.ndarray:
    mu = np.zeros(len(U), dtype=np.float32)
    sd = np.zeros(len(U), dtype=np.float32)
    cos = np.zeros(len(rows), dtype=np.float32)
    order = np.argsort(rows, kind="mergesort")
    at = 0
    bar = progress(total=len(U), desc="topic cosine", unit="tag")
    for i in range(0, len(U), COS_BLOCK):
        block = U[i:i + COS_BLOCK] @ D.T
        mu[i:i + len(block)] = block.mean(axis=1)
        sd[i:i + len(block)] = block.std(axis=1)
        while at < len(order) and rows[order[at]] < i + len(block):
            e = order[at]
            cos[e] = block[rows[e] - i, cols[e]]
            at += 1
        bar.update(len(block))
    bar.close()
    return ((cos.astype(np.float64) - mu[rows]) /
            np.maximum(sd[rows].astype(np.float64), TAG_SD_FLOOR))


def neighbour_vote(D: np.ndarray, rows: np.ndarray, cols: np.ndarray,
                   degree: np.ndarray) -> np.ndarray:
    similarity = D @ D.T
    nearest = np.argsort(-similarity, axis=1, kind="stable")[:, 1:DERIVED_NN_K + 1]
    del similarity
    members: list = [set() for _ in degree]
    for t, c in zip(rows, cols):
        members[t].add(int(c))
    prior = degree * (DERIVED_NN_K / len(D))
    vote = np.zeros(len(rows), dtype=np.float64)
    bar = progress(total=len(rows), desc="neighbour vote", unit="edge")
    for e, (t, c) in enumerate(zip(rows, cols)):
        carried = members[t]
        vote[e] = sum(1 for n in nearest[c] if int(n) in carried) - prior[t]
        bar.update(1)
    bar.close()
    return vote


def vote_reliability(vote: np.ndarray, rows: np.ndarray, n_tags: int) -> float:
    total = np.zeros(n_tags)
    count = np.zeros(n_tags)
    np.add.at(total, rows, vote)
    np.add.at(count, rows, 1.0)
    mean = total / np.maximum(count, 1.0)
    within = np.zeros(n_tags)
    np.add.at(within, rows, (vote - mean[rows]) ** 2)
    return max(0.0, 1.0 - (within.sum() / max(len(vote) - n_tags, 1)) / vote.var())


def pair_terms(tags: list, rows: np.ndarray, cols: np.ndarray, table: dict,
               origin: float) -> dict:
    n = len(rows)
    doing = [list(REGISTER).index(f) for f in DOING]
    evidenced = np.zeros(n, dtype=bool)
    register = np.zeros((n, len(REGISTER)))
    entities = np.zeros(n)
    activity = np.zeros(n)
    day = np.full(n, np.nan)
    found: dict = collections.Counter()
    start = table["start"]
    bar = progress(total=n, desc="tag records", unit="edge")
    for e, (t, c) in enumerate(zip(rows, cols)):
        lo, hi = int(start[c]), int(start[c + 1])
        members, how = tag_records(tags[t], table["slug"][lo:hi])
        found[how] += 1
        if members:
            at = np.asarray(members) + lo
            length = table["length"][at].sum()
            register[e] = table["register"][at].sum(axis=0) * PER_CHARS / length
            entities[e] = table["names"][at].sum() * PER_CHARS / length
            activity[e] = register[e, doing].sum()
            days = [d for i in at for d in table["days"][i]]
            if days:
                day[e] = float(np.median(days)) - origin
            evidenced[e] = True
        bar.update(1)
    bar.close()
    return {"evidenced": evidenced, "register": register, "entities": entities,
            "activity": activity, "day": day, "found": dict(found)}


def chunk_days(facts: list) -> tuple:
    day = np.full(len(facts), np.nan)
    for i, fact in enumerate(facts):
        if fact["days"]:
            day[i] = float(np.median(fact["days"]))
    dated = ~np.isnan(day)
    origin = float(day[dated].min())
    day[dated] -= origin
    return day, origin


def temporal_terms(day: np.ndarray, edge_day: np.ndarray, rows: np.ndarray,
                   cols: np.ndarray, half: np.ndarray, n_tags: int) -> tuple:
    dated = ~np.isnan(day)
    total_var = float(np.var(day[dated]))

    def per_tag(mask: np.ndarray) -> tuple:
        count = np.zeros(n_tags)
        centre = np.full(n_tags, np.nan)
        within = np.full(n_tags, np.nan)
        seen: dict = collections.defaultdict(list)
        for t, c in zip(rows, cols):
            if dated[c] and mask[c]:
                seen[t].append(day[c])
        for t, values in seen.items():
            values = np.asarray(values)
            count[t] = len(values)
            centre[t] = values.mean()
            if len(values) >= 2:
                within[t] = values.var(ddof=1)
        return count, centre, within

    count, centre, within = per_tag(np.ones(len(day), dtype=bool))
    count_a, _, within_a = per_tag(half == 0)
    count_b, _, within_b = per_tag(half == 1)
    both = (count_a >= 2) & (count_b >= 2)
    icc = max(0.0, float(np.corrcoef(1.0 - within_a[both] / total_var,
                                     1.0 - within_b[both] / total_var)[0, 1]))
    concentration = 1.0 - within / total_var
    evidenced = ~np.isnan(edge_day) & (count[rows] >= 2)
    z = np.zeros(len(rows))
    z[evidenced] = (np.abs(edge_day[evidenced] - centre[rows[evidenced]]) /
                    np.sqrt(total_var))
    score = (np.where(np.isnan(concentration[rows]), 0.0, concentration[rows]) *
             np.exp(-0.5 * z ** 2))
    rho = reliability(np.where(np.isnan(within), 0.0, count), icc)[rows] * evidenced
    return score, evidenced, rho, icc


def class_match(profiles: np.ndarray, declared: np.ndarray, rows=None) -> tuple:
    classes = [c for c in sorted(set(declared))
               if int((declared == c).sum()) >= DERIVED_MIN_CLASS]
    prototypes = np.asarray([profiles[declared == c].mean(axis=0) for c in classes])
    prototypes /= np.maximum(np.linalg.norm(prototypes, axis=1, keepdims=True), SD_FLOOR)
    rows = profiles if rows is None else rows
    rows = rows / np.maximum(np.linalg.norm(rows, axis=1, keepdims=True), SD_FLOOR)
    return (rows @ prototypes.T).max(axis=1), classes


def fetch_matrix(s, cypher: str, keys: list, what: str) -> np.ndarray:
    found: dict = {}
    bar = progress(total=len(keys), desc=f"pull {what}", unit=what)
    for i in range(0, len(keys), EMB_BATCH):
        batch = keys[i:i + EMB_BATCH]
        for rec in s.run(cypher, keys=batch):
            if rec["emb"] is not None:
                found[rec["key"]] = rec["emb"]
        bar.update(len(batch))
    bar.close()
    missing = [k for k in keys if k not in found]
    if missing:
        raise SystemExit(
            f"{len(missing)} {what}(s) without an embedding (e.g. {missing[:5]}) — "
            f"run `python reembed_herb_eval.py` once.")
    return _unit(np.asarray([found[k] for k in keys], dtype=np.float32))


def _derived_key() -> str:
    return (f"{DATABASE}__{RUN_ID}__nn{DERIVED_NN_K}__cls{DERIVED_MIN_CLASS}"
            f"__prior{FACET_PRIOR}__{PAIR_ANCHOR}")


def write_layer(s, edges: list, phi: np.ndarray, w: np.ndarray) -> None:
    bar = progress(total=len(edges), desc="write layer", unit="edge")
    for i in range(0, len(edges), WRITE_BATCH):
        rows = [{"chunkId": edge["chunkId"], "tag": edge["tag"],
                 "weights": [float(x) for x in phi[i + j]],
                 "magnitude": float(w[i + j])}
                for j, edge in enumerate(edges[i:i + WRITE_BATCH])]
        s.run(_WRITE_CYPHER, rows=rows, runId=RUN_ID,
              facets=list(ALL_FACETS)).consume()
        bar.update(len(rows))
    bar.close()


def main() -> None:
    if DATABASE != BUILD_DATABASE:
        raise SystemExit(
            f"this build writes {BUILD_DATABASE!r}, the current graph, and "
            f"NEO4J_DATABASE names {DATABASE!r} — run it as "
            f"NEO4J_DATABASE={BUILD_DATABASE} python build_facet_layer.py")
    t0 = time.perf_counter()
    backup = require_backup()
    print(f"backup: {backup['n_edges']} edges at sha256 "
          f"{backup['sha256'][:12]}…", flush=True)
    entry = DERIVED_CACHE_DIR / _derived_key()
    if (entry / "manifest.json").is_file():
        print(f"cache entry {entry.name} already complete — skipping "
              f"(delete the entry to rebuild).", flush=True)
        return
    print(f"reading {DATABASE!r} (run_id={RUN_ID!r}) …", flush=True)
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            chunk_rows = [dict(r) for r in s.run(_CHUNKS_CYPHER)]
            edges = [dict(r) for r in s.run(_EDGES_CYPHER, runId=RUN_ID)]
            if not edges:
                raise SystemExit(
                    f"no HAS_TAG edge with run_id={RUN_ID!r} in {DATABASE!r}")
            if len(edges) != backup["n_edges"]:
                raise SystemExit(
                    f"the backup holds {backup['n_edges']} edges and this build "
                    f"writes {len(edges)} — run "
                    f"`python backup_facet_weights.py backup` again.")
            chunk_ids = [r["chunkId"] for r in chunk_rows]
            tags = sorted({e["tag"] for e in edges})
            print(f"  {len(edges)} edges, {len(tags)} tags, "
                  f"{len(chunk_ids)} chunks", flush=True)
            U = fetch_matrix(s, _TAG_EMB_CYPHER, tags, "tag")
            D = fetch_matrix(s, _CHUNK_EMB_CYPHER, chunk_ids, "chunk")

        tag_at = {t: i for i, t in enumerate(tags)}
        chunk_at = {c: i for i, c in enumerate(chunk_ids)}
        rows = np.array([tag_at[e["tag"]] for e in edges])
        cols = np.array([chunk_at[e["chunkId"]] for e in edges])
        degree = np.bincount(rows, minlength=len(tags)).astype(np.float64)

        facts = read_chunks(chunk_rows)
        names = declared_names(facts)
        print(f"  {len(names)} declared names, "
              f"{sum(len(f['days']) > 0 for f in facts)} dated chunks", flush=True)

        z = background_z(U, D, rows, cols)
        vote = neighbour_vote(D, rows, cols, degree)
        icc_vote = vote_reliability(vote, rows, len(tags))
        rho_vote = reliability(np.maximum(degree[rows] - 1.0, 0.0), icc_vote)
        phi_topic = shrink(vote, None, rho_vote, midrank_cdf(z))
        print(f"  topic: ICC(vote over a tag's own edges) = {icc_vote:.4f}", flush=True)

        day, origin = chunk_days(facts)
        table = record_table(facts, names)
        pair = pair_terms(tags, rows, cols, table, origin)
        paired = pair["evidenced"]
        rho_pair = paired.astype(np.float64)
        found = pair["found"]
        print(f"  pair: {len(table['slug'])} records; "
              f"{found.get('verbatim', 0)} edges verbatim, "
              f"{found.get('all_tokens', 0)} by every token, "
              f"{found.get('none', 0)} without a record", flush=True)

        phi_entities = shrink(pair["entities"], paired, rho_pair, FACET_PRIOR)
        phi_activity = shrink(pair["activity"], paired, rho_pair, FACET_PRIOR)
        print(f"  entities: declared-name density over the pair, "
              f"{int(paired.sum())} evidenced edges", flush=True)
        print(f"  activity: {'+'.join(DOING)} density over the pair, "
              f"{int(paired.sum())} evidenced edges", flush=True)

        score, dated_edge, rho_temp, icc_temp = temporal_terms(
            day, pair["day"], rows, cols, sha256_parity(chunk_ids), len(tags))
        phi_temporal = shrink(score, dated_edge, rho_temp, FACET_PRIOR)
        print(f"  temporal: split-half ICC of the concentration = {icc_temp:.4f}, "
              f"{int(dated_edge.sum())} evidenced edges", flush=True)

        start = table["start"]
        chunk_raw = np.array([
            table["register"][start[i]:start[i + 1]].sum(axis=0) * PER_CHARS /
            table["length"][start[i]:start[i + 1]].sum()
            for i in range(len(facts))])
        declared = np.array([f["declared"] for f in facts])
        match, classes = class_match(standardise(chunk_raw, chunk_raw), declared,
                                     standardise(pair["register"], chunk_raw))
        phi_evidence = shrink(match, paired, rho_pair, FACET_PRIOR)
        print(f"  evidence: {len(classes)} declared classes over "
              f"{len(REGISTER)} register features, "
              f"{int(paired.sum())} evidenced edges", flush=True)

        phi = np.column_stack([phi_topic, phi_entities, phi_activity,
                               phi_temporal, phi_evidence])
        w = magnitude(phi)
        evidenced = np.column_stack(
            [np.ones(len(edges), dtype=bool), paired, paired, dated_edge, paired])

        print(f"{'facet':10s} {'mean':>8s} {'sd':>8s} {'min':>8s} {'max':>8s} "
              f"{'evidenced':>10s}", flush=True)
        stats = {}
        for j, facet in enumerate(ALL_FACETS):
            column = phi[:, j]
            stats[facet] = {"mean": float(column.mean()), "sd": float(column.std()),
                            "min": float(column.min()), "max": float(column.max()),
                            "evidenced": float(evidenced[:, j].mean())}
            print(f"  {facet:8s} {column.mean():8.4f} {column.std():8.4f} "
                  f"{column.min():8.4f} {column.max():8.4f} "
                  f"{evidenced[:, j].mean() * 100:9.2f}%", flush=True)
        print(f"  magnitude mean {w.mean():.4f} sd {w.std():.4f} "
              f"min {w.min():.4f} max {w.max():.4f}", flush=True)

        entry.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(entry / "facets.npz", phi=phi, magnitude=w,
                            evidenced=evidenced,
                            chunk_id=np.array([e["chunkId"] for e in edges]),
                            tag=np.array([e["tag"] for e in edges]))
        with drv.session(database=DATABASE) as s:
            write_layer(s, edges, phi, w)
    finally:
        drv.close()

    (entry / "manifest.json").write_text(json.dumps({
        "database": DATABASE, "run_id": RUN_ID, "facets": list(ALL_FACETS),
        "pair_anchor": PAIR_ANCHOR, "nn_k": DERIVED_NN_K,
        "min_class": DERIVED_MIN_CLASS, "prior": FACET_PRIOR,
        "min_name_chars": MIN_NAME_CHARS, "max_name_tokens": MAX_NAME_TOKENS,
        "min_token_chars": MIN_TOKEN_CHARS, "doing_features": list(DOING),
        "n_edges": len(edges), "n_tags": len(tags), "n_chunks": len(chunk_ids),
        "n_records": len(table["slug"]), "declared_names": len(names),
        "pairs_found": {how: int(found.get(how, 0))
                        for how in ("verbatim", "all_tokens", "none")},
        "evidenced_share": {f: stats[f]["evidenced"] for f in ALL_FACETS},
        "icc_topic_vote": icc_vote, "icc_temporal": icc_temp,
        "register_features": list(REGISTER), "declared_classes": classes,
        "facet_stats": stats, "w_mean": float(w.mean()),
        "w_min": float(w.min()), "w_max": float(w.max()),
        "build_time_s": time.perf_counter() - t0,
    }, indent=1), encoding="utf-8")
    print(f"done — {entry.name} written ({time.perf_counter() - t0:.0f}s).", flush=True)


if __name__ == "__main__":
    main()
