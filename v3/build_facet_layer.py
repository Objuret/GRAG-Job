"""Build the artefact arm's derived facet layer: five deterministic facet
weights and one magnitude per HAS_TAG edge of the arm's tagging run.

Every weight has the same form — φ_j(e) = ρ_j(e)·F_j(s_j(e)) + (1 − ρ_j(e))·b_j(e).
F is the mid-rank empirical CDF F = mean_rank/(n + 1) over the edges that facet
evidences, which is what makes all five marginally uniform and commensurable;
ρ is the Spearman-Brown reliability ρ(n) = n·ICC/(1 + (n − 1)·ICC) at that
edge's evidence count, with the ICC measured off this corpus rather than
chosen; b is the lower-variance estimator to fall back on, or FACET_PRIOR where
there is none. The five estimators:

  topic     z(t, c) = (cos(t.emb, c.desc_emb) − μ_t)/σ_t, μ and σ over the whole
            chunk population, and neighbour voting
            vote(t, c) = |NN_K(c) ∩ chunks(t)| − K·deg(t)/C over the chunk's
            description neighbours (Li/Snoek/Worring, TMM 2009). The vote leads
            at ρ(deg − 1), its ICC read off the spread of a tag's own edges
            against the whole spread; z is the fallback.
  entities  a one-vs-background axis in the tag embedding space (the TCAV
            construction, Kim et al. ICML 2018) seeded on the tags carrying a
            name the corpus declares about itself — the employee, customer and
            team directories, the product file names, the slack channels, the
            record handles — scored a_ent·t.emb. Fully evidenced, ρ ≡ 1.
  activity  the same construction seeded on deverbal `-ing` tags, then
            Gram-Schmidt orthogonalised against a_ent so the two axes score two
            facets instead of one twice. ρ ≡ 1.
  temporal  conc(t) = 1 − Var_within(t)/Var_total over chunk median day, and
            s = conc(t)·exp(−½z²) at z = |day(c) − centre(t)|/sd_corpus. The ICC
            is the correlation of the two halves' concentrations across a
            sha256-parity split of the chunk ids; a tag with fewer than two
            dated chunks carries ρ = 0 and the edge lands at FACET_PRIOR.
  evidence  15 countable register features per chunk — numeral, percentage,
            money, unit, URL, question, modal, causal, exemplifier,
            definitional, procedural, first- and second-person, code and bullet
            densities — z-scored over the corpus, cosine against the mean
            profile of every class the corpus declares. Chunk-level, so it is
            constant across a chunk's tags.

The magnitude is w = sqrt(A·Q), the geometric mean of the five values'
arithmetic and quadratic means, so A ≤ w ≤ Q on every edge. It is the same
functional the v1 build's `w_chunk` computes, over the derived vector.

The layer lands on the edge itself: `r.facets` (the five names in ALL_FACETS
order), `r.w_facets` (the five weights in that order) and `r.w_chunk` (the
magnitude), in one batched pass over the edges in (chunk_id, tag name) order —
float addition is not associative, so the build reads, accumulates and writes in
one fixed order and keeps it. The edge carries one facet layer, so the same pass
drops any parallel `dw_facets` / `dw_chunk`. `backup_facet_weights.py` holds
what the write replaces: the build refuses to start without a complete,
hash-checked backup of every edge it is about to touch.

Cache entry: output/derived_facet_cache/<db>__<run>__nn…__cls…__par…__prior…/
holding facets.npz (the layer, its evidence mask and its edge keys) and
manifest.json (the constants, the measured ICCs, the per-facet summary stats and
the corpus mean magnitude, written last as the completeness marker). The entry
is keyed by the constants: changed constants build a sibling entry.
Deterministic, no model calls.

Every text this reads comes from the oracle-stripped corpus copy under
data/corpus; the graph supplies structure and embeddings only.

Run with Neo4j up and NEO4J_PASSWORD in v3/.env:

    python backup_facet_weights.py backup
    python build_facet_layer.py
    python run.py --arm artefact_v1_det --set gold -k 50
"""
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

from backup_facet_weights import require_backup
from pipelines.artefact_v1 import (
    ALL_FACETS, DATABASE, DATASET_ID, EXCLUDED_SECTIONS, RUN_ID, _driver,
    _env_float, _unit,
)
from progress import progress

CORPUS = Path(__file__).resolve().parent / "data" / "corpus"

# The cache: one entry per build constant set, holding the layer and the
# manifest that marks it complete.
DERIVED_CACHE_DIR = Path(__file__).resolve().parent / "output" / "derived_facet_cache"

# The neighbour-vote width of the topic facet: how many nearest description
# neighbours of a chunk vote on whether its tag belongs there.
DERIVED_NN_K = 25

# How many chunks a corpus-declared class needs before its mean register
# profile is a prototype the evidence facet scores against.
DERIVED_MIN_CLASS = 20

# Which sha256-parity half of the tag names seeds the entity and activity axes.
DERIVED_SEED_PARITY = 0

# The shrinkage target where a facet has evidence for neither its own estimator
# nor a lower-variance one to fall back on — the temporal facet's, at fewer than
# two dated chunks. 0.5 is the calibrated scale's midpoint, no evidence and no
# opinion; 0.0 asserts absence from silence. It names the cache entry, so the
# two land in different builds and compare on one corpus.
FACET_PRIOR = _env_float("HERB_FACET_PRIOR", 0.5)

EMB_BATCH = 2000
COS_BLOCK = 2000
WRITE_BATCH = 1000

# Countable register features: what kind of record a chunk reads as, from marks
# a regex can count. Each is a per-PER_CHARS-character density, so length does
# not decide the profile; the column z-score then divides PER_CHARS back out.
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

# A tag names an entity when one run of its underscore tokens is a name the
# corpus declares; short names match too much to be evidence of anything.
MIN_NAME_CHARS = 6
MAX_NAME_TOKENS = 5
_ING = re.compile(r"ing$")

# A measured ICC is held away from asserting perfect or vanishing reliability.
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


# --- the calibration and the shrinkage ----------------------------------------

def midrank_cdf(x: np.ndarray, evidenced=None) -> np.ndarray:
    """The probability integral transform of `x` by mid-rank over the evidenced
    subset: F = mean_rank/(n + 1), ties sharing their mean rank, so every
    transformed value sits strictly inside (0, 1) and any two facets are
    comparable. An entry outside the subset carries no rank and returns 0 — the
    master form's reliability is zero there, so it never reaches a weight."""
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
    """Spearman-Brown reliability of a mean of `n` observations,
    ρ(n) = n·ICC/(1 + (n − 1)·ICC), rising from 0 at no evidence toward 1 as the
    evidence accumulates. The ICC is held inside (ICC_FLOOR, ICC_CEIL), so a
    measurement at either end still shrinks."""
    n = np.asarray(n, dtype=np.float64)
    icc = min(max(float(icc), ICC_FLOOR), ICC_CEIL)
    return np.where(n >= 1.0, n * icc / (1.0 + (n - 1.0) * icc), 0.0)


def shrink(score: np.ndarray, evidenced: np.ndarray, rho: np.ndarray,
           fallback) -> np.ndarray:
    """The master form: the calibrated score at the edge's own reliability,
    the rest of the weight on the fallback — another estimator's calibrated
    value, or the constant prior where there is none."""
    return rho * midrank_cdf(score, evidenced) + (1.0 - rho) * fallback


def magnitude(phi: np.ndarray) -> np.ndarray:
    """The edge magnitude w = sqrt(A·Q): the geometric mean of the row's
    arithmetic mean A and quadratic mean Q. A ≤ w ≤ Q by the power-mean
    inequality, so w is the concentration-aware size of the facet vector."""
    a = phi.mean(axis=1)
    q = np.sqrt((phi ** 2).mean(axis=1))
    return np.sqrt(a * q)


# --- the corpus side ----------------------------------------------------------

def _nth(root, i: int):
    """The i-th member of a locator's container: a list element, or one
    key/value pair of an object in its own order."""
    if isinstance(root, list):
        return root[i]
    key, value = list(root.items())[i]
    return {key: value}


def _day(stamp: str) -> int:
    """One HERB timestamp's calendar day as a proleptic Gregorian ordinal."""
    return date(int(stamp[0:4]), int(stamp[5:7]), int(stamp[8:10])).toordinal()


def _stamps(records: list, section) -> tuple:
    """The record days and the people one chunk's records name -> (days,
    handles). HERB carries both under a different key per section, so each
    section is read on its own terms."""
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
    """One chunk's source records -> (records, text). A char-range chunk's text
    is the sliced field alone, while its record keeps the carrier's identifying
    fields so the declared type and the timestamps survive the slice. A locator
    naming an excluded section fails loud: the oracle is stripped out of the
    corpus copy, so it can only mean the graph points somewhere it must not."""
    if "metadata" in locator:
        if "indices" in locator:
            records = [_nth(doc, i) for i in locator["indices"]]
        else:
            record = _nth(doc, locator["index"])
            if locator.get("subsection"):
                record = record[locator["subsection"]]
            records = [record]
        return records, "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
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
        return [{**sliced, **carried}], json.dumps(sliced, ensure_ascii=False)
    indices = locator["indices"] if "indices" in locator else [locator["index"]]
    records = [array[i] for i in indices]
    return records, "\n".join(json.dumps(r, ensure_ascii=False) for r in records)


def read_chunks(rows: list) -> list:
    """Resolve every chunk against the oracle-stripped corpus copy -> one fact
    row per chunk: the record text the register features count, the record days
    the temporal facet locates it by, the class the corpus declares it (HERB's
    own record type where it states one, else the chunk kind), its channel and
    the handles its records name."""
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
        records, text = _resolve(locator, doc)
        section = row["section"] or locator.get("section")
        days, people = _stamps(records, section)
        declared = None
        for rec in records:
            if isinstance(rec, dict):
                declared = rec.get("type") or rec.get("document_type") or declared
        facts.append({"text": text, "days": days, "channel": row["channel"],
                      "people": people, "declared": declared or row["kind"]})
        bar.update(1)
    bar.close()
    return facts


def _slug(value) -> str:
    """A name in tag form: lowercase, every run of non-alphanumerics an
    underscore, no leading or trailing separator."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def declared_names(facts: list) -> set:
    """Every name the corpus declares about itself, slugged: the employee,
    customer and team directories, the product file names, and the channels and
    handles the chunks' own records carry."""
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


def named_tags(tags: list, names: set) -> np.ndarray:
    """Which tags carry a declared name: true when some run of up to
    MAX_NAME_TOKENS of a tag's underscore tokens is a declared name of at least
    MIN_NAME_CHARS characters."""
    long_names = {n for n in names if len(n) >= MIN_NAME_CHARS}
    out = np.zeros(len(tags), dtype=bool)
    for i, tag in enumerate(tags):
        parts = tag.split("_")
        out[i] = any("_".join(parts[a:b]) in long_names
                     for a in range(len(parts))
                     for b in range(a + 1, min(a + MAX_NAME_TOKENS, len(parts)) + 1))
    return out


def sha256_parity(keys: list) -> np.ndarray:
    """The deterministic half each key falls in: the low nibble of its sha256,
    modulo two. It splits the corpus for every reliability measurement and
    selects the axis seeds, with no seed and no draw anywhere."""
    return np.array([int(hashlib.sha256(k.encode("utf-8")).hexdigest()[-1], 16) % 2
                     for k in keys])


# --- the five estimators ------------------------------------------------------

def background_z(U: np.ndarray, D: np.ndarray, rows: np.ndarray,
                 cols: np.ndarray) -> np.ndarray:
    """Each edge's topic cosine standardised against its tag's own background
    over the whole chunk population: z = (cos(t, c) − μ_t)/σ_t. Blocked over the
    tags, so the full tag × chunk product never materialises."""
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
    """Each edge's neighbour vote: how many of the chunk's DERIVED_NN_K nearest
    description neighbours also carry the tag, less what the tag's degree alone
    predicts — |NN_K(c) ∩ chunks(t)| − K·deg(t)/C. A tag that lands on a
    neighbourhood says more about this chunk than one that lands everywhere."""
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
    """The vote's intraclass correlation, read off the tags themselves: one
    minus the within-tag mean square over the total variance. A vote that
    varies as much inside a tag as across the corpus carries no tag signal and
    lands at 0."""
    total = np.zeros(n_tags)
    count = np.zeros(n_tags)
    np.add.at(total, rows, vote)
    np.add.at(count, rows, 1.0)
    mean = total / np.maximum(count, 1.0)
    within = np.zeros(n_tags)
    np.add.at(within, rows, (vote - mean[rows]) ** 2)
    return max(0.0, 1.0 - (within.sum() / max(len(vote) - n_tags, 1)) / vote.var())


def concept_axes(U: np.ndarray, entity_seed: np.ndarray,
                 activity_seed: np.ndarray) -> tuple:
    """The entity and activity directions over the unit tag vectors -> (entity
    axis, activity axis, cosine between them before orthogonalisation, after).
    Each axis is its seed set's mean direction less the pool's own — one concept
    against the background, not one concept against the other — and the activity
    axis is then Gram-Schmidt orthogonalised against the entity axis, which is
    load-bearing: the two seed sets sit on opposite sides of the same
    morphological contrast, so unorthogonalised they score one facet twice."""
    background = _unit(U.mean(axis=0))
    entity = _unit(_unit(U[entity_seed].mean(axis=0)) - background)
    activity = _unit(_unit(U[activity_seed].mean(axis=0)) - background)
    before = float(entity @ activity)
    activity = _unit(activity - before * entity)
    return entity, activity, before, float(entity @ activity)


def chunk_days(facts: list) -> np.ndarray:
    """Each chunk's median record day, NaN where the chunk carries no
    timestamp. The origin is the earliest such day: every quantity read off
    these is a variance or a difference, so the origin cancels."""
    day = np.full(len(facts), np.nan)
    for i, fact in enumerate(facts):
        if fact["days"]:
            day[i] = float(np.median(fact["days"]))
    dated = ~np.isnan(day)
    day[dated] -= day[dated].min()
    return day


def temporal_terms(day: np.ndarray, rows: np.ndarray, cols: np.ndarray,
                   half: np.ndarray, n_tags: int) -> tuple:
    """The temporal estimator -> (per-edge score, evidenced mask, per-edge
    reliability, ICC). A tag's concentration is 1 − Var_within/Var_total over
    its dated chunks' median days, and an edge scores that concentration decayed
    by how far this chunk sits from the tag's centre in corpus standard
    deviations. The ICC is the correlation between the concentrations the two
    halves of the corpus measure, so a facet that cannot reproduce itself
    shrinks away."""
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
    evidenced = dated[cols] & (count[rows] >= 2)
    z = np.zeros(len(rows))
    z[evidenced] = (np.abs(day[cols[evidenced]] - centre[rows[evidenced]]) /
                    np.sqrt(total_var))
    score = (np.where(np.isnan(concentration[rows]), 0.0, concentration[rows]) *
             np.exp(-0.5 * z ** 2))
    rho = reliability(np.where(np.isnan(within), 0.0, count), icc)[rows] * evidenced
    return score, evidenced, rho, icc


def register_profiles(texts: list) -> np.ndarray:
    """Every chunk's register profile: the REGISTER features as per-PER_CHARS
    densities, z-scored down the corpus so each feature speaks on its own
    spread."""
    raw = np.zeros((len(texts), len(REGISTER)))
    patterns = list(REGISTER.values())
    bar = progress(total=len(texts), desc="register features", unit="chunk")
    for i, text in enumerate(texts):
        length = max(len(text), 1)
        for j, pattern in enumerate(patterns):
            raw[i, j] = len(pattern.findall(text)) * PER_CHARS / length
        bar.update(1)
    bar.close()
    return (raw - raw.mean(axis=0)) / np.maximum(raw.std(axis=0), SD_FLOOR)


def class_match(profiles: np.ndarray, declared: np.ndarray) -> tuple:
    """How strongly each chunk reads as some class the corpus itself declares
    -> (best cosine per chunk, the classes). A class needs DERIVED_MIN_CLASS
    chunks before its mean profile is a prototype; the score is the chunk's best
    cosine against them, so a chunk with a distinctive register scores high
    whichever kind it is."""
    classes = [c for c in sorted(set(declared))
               if int((declared == c).sum()) >= DERIVED_MIN_CLASS]
    prototypes = np.asarray([profiles[declared == c].mean(axis=0) for c in classes])
    prototypes /= np.maximum(np.linalg.norm(prototypes, axis=1, keepdims=True), SD_FLOOR)
    rows = profiles / np.maximum(np.linalg.norm(profiles, axis=1, keepdims=True), SD_FLOOR)
    return (rows @ prototypes.T).max(axis=1), classes


# --- the graph side -----------------------------------------------------------

def fetch_matrix(s, cypher: str, keys: list, what: str) -> np.ndarray:
    """The embedding of every key, in key order, unit-normalised. A key the
    graph has no vector for fails loud — the semantic layer must be complete
    before any of this means anything."""
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
    """The cache entry name for one build: the database, the tagging run, and
    every constant the build depends on."""
    return (f"{DATABASE}__{RUN_ID}__nn{DERIVED_NN_K}__cls{DERIVED_MIN_CLASS}"
            f"__par{DERIVED_SEED_PARITY}__prior{FACET_PRIOR}")


def write_layer(s, edges: list, phi: np.ndarray, w: np.ndarray) -> None:
    """Write the layer onto the edges it was computed from, in the (chunk_id,
    tag name) order the build fixed: the five facet names, their five weights
    and the magnitude, and no parallel property beside them."""
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

        parity = sha256_parity(tags)
        named = named_tags(tags, names)
        deverbal = np.array([bool(_ING.search(t.split("_")[-1])) for t in tags])
        entity_seed = np.where(named & (parity == DERIVED_SEED_PARITY))[0]
        activity_seed = np.where(deverbal & (parity == DERIVED_SEED_PARITY))[0]
        a_ent, a_act, cos_before, cos_after = concept_axes(U, entity_seed, activity_seed)
        phi_entities = midrank_cdf((U @ a_ent)[rows])
        phi_activity = midrank_cdf((U @ a_act)[rows])
        print(f"  axes: {len(entity_seed)} entity seeds, {len(activity_seed)} "
              f"activity seeds, cos {cos_before:+.4f} -> {cos_after:+.4f}", flush=True)

        day = chunk_days(facts)
        score, dated_edge, rho_temp, icc_temp = temporal_terms(
            day, rows, cols, sha256_parity(chunk_ids), len(tags))
        phi_temporal = shrink(score, dated_edge, rho_temp, FACET_PRIOR)
        print(f"  temporal: split-half ICC of the concentration = {icc_temp:.4f}, "
              f"{int(dated_edge.sum())} evidenced edges", flush=True)

        declared = np.array([f["declared"] for f in facts])
        match, classes = class_match(register_profiles([f["text"] for f in facts]),
                                     declared)
        phi_evidence = midrank_cdf(match[cols])
        print(f"  evidence: {len(classes)} declared classes over "
              f"{len(REGISTER)} register features", flush=True)

        phi = np.column_stack([phi_topic, phi_entities, phi_activity,
                               phi_temporal, phi_evidence])
        w = magnitude(phi)
        evidenced = np.column_stack(
            [np.ones(len(edges), dtype=bool)] * 3 + [dated_edge] +
            [np.ones(len(edges), dtype=bool)])

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
        "nn_k": DERIVED_NN_K, "min_class": DERIVED_MIN_CLASS,
        "seed_parity": DERIVED_SEED_PARITY, "prior": FACET_PRIOR,
        "n_edges": len(edges), "n_tags": len(tags), "n_chunks": len(chunk_ids),
        "icc_topic_vote": icc_vote, "icc_temporal": icc_temp,
        "entity_seeds": int(len(entity_seed)), "activity_seeds": int(len(activity_seed)),
        "axis_cosine_before": cos_before, "axis_cosine_after": cos_after,
        "register_features": list(REGISTER), "declared_classes": classes,
        "facet_stats": stats, "w_mean": float(w.mean()),
        "w_min": float(w.min()), "w_max": float(w.max()),
        "build_time_s": time.perf_counter() - t0,
    }, indent=1), encoding="utf-8")
    print(f"done — {entry.name} written ({time.perf_counter() - t0:.0f}s).", flush=True)


if __name__ == "__main__":
    main()
