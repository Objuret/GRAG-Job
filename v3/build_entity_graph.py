"""Build a versioned copy of a herb graph database: faithful copy, tag cleanup,
entity layer. The authority for what gets built is the signed design
`docs/state/2026-08-12-entity-nodes-and-tag-cleanup-design.md`; the execution
defaults under the user's 08-12 build order are recorded in EXECUTION_DEFAULTS
and written into the build manifest.

Four subcommands, run in order against a target database that is never the
source:

  copy      create the target as a faithful copy of the source — every node,
            relationship, property (embeddings included), label, constraint and
            index — then verify it: per-label and per-reltype counts, property
            coverage, and numeric spot-checksums including the t.emb /
            c.desc_emb presence counts. The source is opened read-only and its
            before-snapshot is kept for the untouched proof.
  cleanup   derive the tag-removal predicate (design §3.1) from the target's
            own tag names against the oracle-stripped corpus — slugified
            prs[].title / prs[].link / urls[].link / documents[].document_link
            intersected with the tag names, plus the URL-prefix and PR-pointer
            forms; bare `http_` protocol tags are excluded from removal, and
            decision/date tags are not touched. The derived set must hit the
            EXPECTED_REMOVAL gate exactly (4,111 tags / 5,470 edges / 2,240
            chunks touched / 0 chunks losing all tags) and the removed-name
            list's sha256 (EXPECTED_REMOVED_SHA256 — its set identity, not
            just its size) or nothing is deleted. On a pass the Tag nodes are
            DETACH DELETEd and the full removed-name list lands in the step
            record for the manifest.
  entities  derive the entity layer from the target's chunk locators resolved
            against the corpus (design §2.1–2.2): Person nodes for every id
            observed in structured fields, uniformly across id-spaces, carrying
            the id string and an id-space kind only — no names anywhere;
            Product and Channel nodes from the chunk attributes; chunk→Person
            INVOLVES edges with a role from field structure; deterministic
            regex id-in-text MENTIONS edges as their own relationship type;
            chunk→Product / chunk→Channel edges. Every count is gated against
            EXPECTED_ENTITIES before anything is written. No model calls, no
            name resolver, no org-tree edges; the 61 metadata-mirror chunks
            stay as they are.
  verify    re-check everything read-only — the source untouched against its
            before-snapshot, the removed tags absent, every entity count — and
            assemble the build manifest, written last as the completeness
            marker.

The corpus read is `data/corpus/` (the oracle-stripped view), never `data/raw`;
no question file and no arm output is ever opened. Writes go only to the target
database: `herb` and `herb-eval` are refused as write targets.

Run with Neo4j up and NEO4J_PASSWORD in v3/.env:

    python build_entity_graph.py copy
    python build_entity_graph.py cleanup
    python build_entity_graph.py entities
    python build_entity_graph.py verify
"""
from __future__ import annotations

if __name__ == "__main__":
    print("build_entity_graph: copy / cleanup / entities / verify "
          "— loading neo4j …", flush=True)

import argparse
import collections
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from pipelines.artefact_v1 import DATASET_ID, _driver
from progress import progress

# --- configuration -------------------------------------------------------------

SOURCE_DATABASE = "herb-eval"
TARGET_DATABASE = "herb-eval-v2"

# Databases no write session may ever address: the oracle-contaminated pilot,
# the benchmarked graph every standing number was measured on, and the DBMS's
# own default and system databases. `herb` is refused as a source too.
PROTECTED_DATABASES = ("herb", "herb-eval", "neo4j", "system")

DESIGN_DOC = "docs/state/2026-08-12-entity-nodes-and-tag-cleanup-design.md"

# The oracle-stripped corpus view; the raw store never enters this build.
CORPUS = Path(__file__).resolve().parent / "data" / "corpus"

# One build directory per target database, holding the per-step records and the
# manifest that marks the build complete.
BUILD_DIR = Path(__file__).resolve().parent / "output" / "graph_build"

# The executor's calls under the user's 08-12 delegation ("construct another db
# using this, aka use the current as template and 'fix it' and add these
# things"), per the design's §7 execution-defaults block. Each stays open as a
# ruling; the manifest carries this record.
EXECUTION_DEFAULTS = {
    "OPEN-1": "Person + Product + Channel nodes; years and section stay chunk attributes",
    "OPEN-2": "all id-spaces in uniformly — EMP_ included, flagged low-value",
    "OPEN-3": "deterministic regex id-in-text mention edges in, as their own "
              "relationship type; name-resolver edges out",
    "OPEN-4": "the 61 existing metadata-mirror chunks kept unchanged",
    "OPEN-5": "vocabulary-level predicate; bare http_ protocol tags excluded "
              "from removal; decision/date tags not touched",
    "OPEN-6": "versioned copy, one combined new version",
    "OPEN-7": "new database herb-eval-v2; this manifest carries source, "
              "predicate + hash, counts, verification",
}

# The tag-removal predicate, design §3.1: URL-prefix classes (https_/www_ and
# bare github_com_; `http_` deliberately absent — its 14 tags are protocol
# concepts, not URLs) and the PR-pointer forms.
R_URL_PREFIXES = ("https_", "www_", "github_com_")
_GITHUB_PR = re.compile(r"github_pr_\d+")
_X_PR = re.compile(r".+_pr_\d+")
_PULL_REQUEST = re.compile(r"pull_request_\d+")
_X_PULL = re.compile(r"_pull_\d+")

# HERB's own id forms: employee ids (metadata/employee.json keys), PR logins,
# customer ids. The mention pass counts these by exact regex over the resolved
# records' declared content leaves.
_EID = re.compile(r"eid_[0-9a-f]{8}")
_EMP = re.compile(r"EMP_\d{6,12}")
_CUST = re.compile(r"CUST-\d+")

# The hard gate on the derived removal set: the design's censused figures.
# Any mismatch stops the build with nothing deleted.
EXPECTED_REMOVAL = {"tags": 4111, "edges": 5470,
                    "chunks_touched": 2240, "chunks_emptied": 0}

# The removed-name list's set identity: sha256 over the sorted, newline-joined
# names, gated beside the counts — matching counts over a different tag set
# stop the cleanup.
EXPECTED_REMOVED_SHA256 = "6a279b3465f4ec55f440607d0239a4c56d1580ebd9582c43a4d31265b4426116"

# The entity-layer gates: the design's censused figures (§2.1–2.2). Structured
# Person nodes by id-space kind; INVOLVES edges by role; MENTIONS edges and
# their distinct targets by id-space; Product/Channel nodes and their chunk
# edges from the existing chunk attributes.
EXPECTED_ENTITIES = {
    "person_kinds": {"eid": 512, "emp": 4590, "malformed": 9},
    "involves": {"speaker": 13690, "participant": 9964, "reviewer": 4349,
                 "pr_author": 3492, "doc_author": 786},
    "mentions": {"eid": 8591, "cust": 1043, "emp": 0},
    "mention_persons": {"eid": 514, "cust": 120},
    "product_nodes": 30,
    "channel_nodes": 294,
    "product_edges": 4808,
    "channel_edges": 2669,
}

# Node labels per the design's node set; relationship type names are the
# executor's calls under the delegation (the design proposes INVOLVES and marks
# the name open; the mention type is ordered as "their own relationship type"
# without a name).
PERSON_LABEL = "Person"
PRODUCT_LABEL = "Product"
CHANNEL_LABEL = "Channel"
INVOLVES_TYPE = "INVOLVES"
MENTIONS_TYPE = "MENTIONS"
PRODUCT_TYPE = "IN_PRODUCT"
CHANNEL_TYPE = "IN_CHANNEL"

# Copy scaffolding: the source element id carried on every copied node while
# relationships are wired, then stripped before verification.
COPY_KEY = "__copy_src"

NODE_BATCH = 500
REL_BATCH = 2000
WRITE_BATCH = 1000
DELETE_BATCH = 500
INDEX_WAIT_S = 600.0
CHECKSUM_REL_TOL = 1e-6


# --- the removal predicate (design §3.1) ---------------------------------------

def slug(value: str) -> str:
    """A field value in tag form: lowercase, every run of non-alphanumerics an
    underscore, no leading or trailing separator."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def collect_slug_sources(products: dict) -> dict:
    """The raw field values whose slugs the predicate intersects with the tag
    names: PR titles, PR links, urls links, document links."""
    out = {"pr_titles": [], "pr_links": [], "url_links": [], "doc_links": []}
    for doc in products.values():
        for rec in doc.get("prs") or []:
            if isinstance(rec.get("title"), str):
                out["pr_titles"].append(rec["title"])
            if isinstance(rec.get("link"), str):
                out["pr_links"].append(rec["link"])
        for rec in doc.get("urls") or []:
            if isinstance(rec.get("link"), str):
                out["url_links"].append(rec["link"])
        for rec in doc.get("documents") or []:
            if isinstance(rec.get("document_link"), str):
                out["doc_links"].append(rec["document_link"])
    return out


def derive_removal(tag_names: set, sources: dict) -> dict:
    """The removal classes over the live tag vocabulary -> {class: set of tag
    names}, REMOVE being their union. Vocabulary-level: a name in the set dies
    everywhere it is attached."""
    names = set(tag_names)
    s_titles = names & {slug(t) for t in sources["pr_titles"]}
    s_links = names & ({slug(u) for u in sources["pr_links"]}
                       | {slug(u) for u in sources["url_links"]}
                       | {slug(u) for u in sources["doc_links"]})
    r_url = {n for n in names if n.startswith(R_URL_PREFIXES)}
    r_pr = ({n for n in names if _GITHUB_PR.fullmatch(n)}
            | {n for n in names if _X_PR.fullmatch(n)}
            | {n for n in names if _PULL_REQUEST.fullmatch(n)}
            | {n for n in names if _X_PULL.search(n)})
    return {"S_titles": s_titles, "S_links": s_links, "R_url": r_url,
            "R_pr": r_pr, "REMOVE": s_titles | s_links | r_url | r_pr}


def removal_impact(remove: set, tag_degree: dict, chunk_tags: dict) -> dict:
    """What the removal set touches, in the gate's terms."""
    return {
        "tags": len(remove),
        "edges": sum(tag_degree[n] for n in remove),
        "chunks_touched": sum(1 for tags in chunk_tags.values() if tags & remove),
        "chunks_emptied": sum(1 for tags in chunk_tags.values()
                              if tags and tags <= remove),
    }


def gate_removed_sha(removed: list) -> str:
    """The removed-name list's identity: sha256 over the sorted, newline-joined
    names, held to EXPECTED_REMOVED_SHA256 — matching counts over a different
    tag set stop the cleanup with nothing deleted."""
    sha = hashlib.sha256("\n".join(removed).encode("utf-8")).hexdigest()
    print(f"  removed-list sha256 {sha}", flush=True)
    if sha != EXPECTED_REMOVED_SHA256:
        raise SystemExit(f"removed-list sha256 mismatch: derived {sha}, "
                         f"expected {EXPECTED_REMOVED_SHA256} — stopping with "
                         f"nothing deleted.")
    return sha


def gate(name: str, actual: dict, expected: dict) -> None:
    """Hold a measured census to its expected figures — every expected key at
    its exact value, no unexpected key present. Any mismatch fails loud with
    the full table; the caller deletes and writes nothing past it."""
    print(f"gate {name}:", flush=True)
    failed = False
    for key in expected:
        ok = actual.get(key) == expected[key]
        failed = failed or not ok
        print(f"  {key:<20} actual {actual.get(key)!r:>10}  "
              f"expected {expected[key]!r:>10}  {'ok' if ok else 'MISMATCH'}",
              flush=True)
    for key in actual:
        if key not in expected:
            failed = True
            print(f"  {key:<20} actual {actual[key]!r:>10}  UNEXPECTED KEY",
                  flush=True)
    if failed:
        raise SystemExit(f"gate {name} failed — stopping with nothing changed.")


# --- the entity derivation (design §2.1–2.2) ------------------------------------

def classify_id(pid: str) -> str:
    """The id-space kind of one observed person id. Anything outside the three
    exact forms is malformed and flagged as such, never repaired."""
    if _EID.fullmatch(pid):
        return "eid"
    if _EMP.fullmatch(pid):
        return "emp"
    if _CUST.fullmatch(pid):
        return "cust"
    return "malformed"


def resolve_records(locator: dict, section: str, products: dict) -> list:
    """One chunk's source records out of the product-level section arrays.
    A char-range chunk resolves to its whole carrier record — roles and
    mentions are record-level facts. Metadata chunks resolve to nothing here
    (the 61 mirror chunks stay as they are). Anything unresolvable fails loud."""
    if "metadata" in locator:
        return []
    pname = locator.get("product")
    if pname not in products:
        raise SystemExit(f"locator names unknown product {pname!r}")
    array = products[pname].get(section) or []
    indices = locator.get("indices")
    if indices is None:
        indices = [locator["index"]] if "index" in locator else None
    if not indices:
        raise SystemExit(f"locator carries neither indices nor index "
                         f"(keys: {sorted(locator)}) for section {section!r}")
    if max(indices) >= len(array):
        raise SystemExit(
            f"locator index out of bounds: {pname}/{section} {max(indices)} "
            f">= {len(array)}")
    records = [array[i] for i in indices]
    if section == "slack":
        want = locator.get("channel")
        got = {((r.get("Channel") or {}).get("name")) for r in records}
        if got != {want}:
            raise SystemExit(
                f"slack locator channel mismatch: locator {want!r}, records {got!r}")
    return records


def content_texts(section: str, rec: dict) -> list:
    """The declared content leaves of one record — the texts the mention
    regexes count over. urls records carry no content leaf."""
    if section == "slack":
        t = ((rec.get("Message") or {}).get("User") or {}).get("text")
        return [t] if isinstance(t, str) else []
    if section == "prs":
        out = [rec["summary"]] if isinstance(rec.get("summary"), str) else []
        out += [rv["comment"] for rv in rec.get("reviews") or []
                if isinstance(rv.get("comment"), str)]
        return out
    if section == "documents":
        return [rec[k] for k in ("content", "feedback") if isinstance(rec.get(k), str)]
    if section == "meeting_transcripts":
        t = rec.get("transcript")
        return [t] if isinstance(t, str) else []
    if section == "meeting_chats":
        t = rec.get("text")
        return [t] if isinstance(t, str) else []
    return []


def chunk_entities(section: str, records: list) -> tuple:
    """One chunk's person facts -> (role pairs, mention ids by id-space).
    Roles come from field structure — speaker / pr_author / reviewer /
    doc_author / participant — and mentions from exact id regexes over the
    records' content leaves, deduplicated within the chunk."""
    roles = set()
    texts = []
    for rec in records:
        texts.extend(content_texts(section, rec))
        if section == "slack":
            uid = ((rec.get("Message") or {}).get("User") or {}).get("userId")
            if uid:
                roles.add(("speaker", uid))
        elif section == "prs":
            login = (rec.get("user") or {}).get("login")
            if login:
                roles.add(("pr_author", login))
            for review in rec.get("reviews") or []:
                login = (review.get("user") or {}).get("login")
                if login:
                    roles.add(("reviewer", login))
        elif section == "documents":
            if rec.get("author"):
                roles.add(("doc_author", rec["author"]))
        elif section == "meeting_transcripts":
            for participant in rec.get("participants") or []:
                roles.add(("participant", participant))
    blob = "\n".join(texts)
    mentions = {"eid": set(_EID.findall(blob)) if blob else set(),
                "emp": set(_EMP.findall(blob)) if blob else set(),
                "cust": set(_CUST.findall(blob)) if blob else set()}
    return roles, mentions


def derive_entities(chunk_rows: list, products: dict) -> dict:
    """The whole entity layer from the chunks' locators against the corpus:
    INVOLVES triples, MENTIONS pairs by id-space, the structured person
    population by kind, and the Product/Channel memberships off the chunk
    attributes."""
    involves = set()                       # (chunk_id, person_id, role)
    mentions = {"eid": set(), "emp": set(), "cust": set()}   # (chunk_id, id)
    product_edges = set()                  # (chunk_id, product)
    channel_edges = set()                  # (chunk_id, channel)
    bar = progress(total=len(chunk_rows), desc="resolve chunks", unit="chunk")
    for row in chunk_rows:
        locator = json.loads(row["locator"])
        records = resolve_records(locator, row["section"], products)
        roles, found = chunk_entities(row["section"], records)
        for role, pid in roles:
            involves.add((row["chunkId"], pid, role))
        for kind, ids in found.items():
            for pid in ids:
                mentions[kind].add((row["chunkId"], pid))
        if row["product"]:
            product_edges.add((row["chunkId"], row["product"]))
        if row["channel"]:
            channel_edges.add((row["chunkId"], row["channel"]))
        bar.update(1)
    bar.close()

    structured_persons = {pid: classify_id(pid) for _, pid, _ in involves}
    kind_counts = collections.Counter(structured_persons.values())
    role_counts = collections.Counter(role for _, _, role in involves)
    return {
        "involves": involves,
        "mentions": mentions,
        "structured_persons": structured_persons,
        "census": {
            "person_kinds": dict(kind_counts),
            "involves": dict(role_counts),
            "mentions": {k: len(v) for k, v in mentions.items()},
            "mention_persons": {k: len({pid for _, pid in mentions[k]})
                                for k in ("eid", "cust")},
            "product_nodes": len({p for _, p in product_edges}),
            "channel_nodes": len({c for _, c in channel_edges}),
            "product_edges": len(product_edges),
            "channel_edges": len(channel_edges),
        },
        "product_edges": product_edges,
        "channel_edges": channel_edges,
    }


# --- graph plumbing -------------------------------------------------------------

_DB_NAME = re.compile(r"^[a-z][a-z0-9.-]{2,62}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bt(name: str) -> str:
    """A name as a backtick-quoted Cypher identifier, inner backticks doubled
    per Cypher's escaping rule, so no name can break out of the quoting."""
    return "`" + name.replace("`", "``") + "`"


def _guard_target(source: str, target: str) -> None:
    """No write session ever addresses a protected database or the source, and
    the oracle-contaminated pilot is never read either."""
    if not _DB_NAME.fullmatch(target) or not _DB_NAME.fullmatch(source):
        raise SystemExit(f"database name out of form: {source!r} / {target!r}")
    if target in PROTECTED_DATABASES:
        raise SystemExit(f"{target!r} is protected — it is never a write target.")
    if source == "herb":
        raise SystemExit("'herb' is the oracle-contaminated pilot database — "
                         "it is never read, not even as a copy source.")
    if target == source:
        raise SystemExit("target and source are the same database.")


def _read(s, cypher: str, **params) -> list:
    return [dict(r) for r in s.run(cypher, **params)]


def _one(s, cypher: str, **params):
    return s.run(cypher, **params).single()[0]


def _step_path(target: str, step: str) -> Path:
    return BUILD_DIR / target / f"step_{step}.json"


def _write_step(target: str, step: str, payload: dict) -> Path:
    path = _step_path(target, step)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True),
                    encoding="utf-8")
    print(f"  step record written: {path}", flush=True)
    return path


def _clear_build_records(target: str) -> None:
    """A fresh copy invalidates every record of this target's earlier builds:
    a step record or manifest describing a dropped database must not survive
    to satisfy a later step's precondition."""
    directory = BUILD_DIR / target
    if directory.is_dir():
        for name in ("step_copy.json", "step_cleanup.json",
                     "step_entities.json", "build_manifest.json"):
            (directory / name).unlink(missing_ok=True)


def _require_step(target: str, step: str, after: dict | None = None) -> dict:
    path = _step_path(target, step)
    if not path.is_file():
        raise SystemExit(f"step {step!r} has not run for {target!r} — "
                         f"no {path}. Run the steps in order: copy, cleanup, "
                         f"entities, verify.")
    record = json.loads(path.read_text(encoding="utf-8"))
    if after is not None and record["timestamp"] < after["timestamp"]:
        raise SystemExit(
            f"step {step!r} record ({record['timestamp']}) predates the step "
            f"it builds on ({after['timestamp']}) — stale after a re-copy; "
            f"re-run the steps in order.")
    return record


def node_label_key(eid: str, labels: list) -> tuple:
    """One source node's copy grouping -> (label-set key, first label). A node
    with zero labels has no MATCH shape for the relationship wiring and fails
    loud rather than copying into an unwireable target."""
    if not labels:
        raise SystemExit(f"node {eid} carries zero labels — unsupported "
                         f"source shape.")
    return "\x00".join(sorted(labels)), labels[0]


def snapshot(s) -> dict:
    """Counts and checksums that identify a graph's content: per-label-set and
    per-reltype counts, property-key coverage on both, embedding presence, and
    numeric property sums. Two faithful copies agree on all of it (float sums
    within CHECKSUM_REL_TOL — aggregation order is not fixed)."""
    labels = {":".join(sorted(r["ls"])): r["n"] for r in _read(
        s, "MATCH (n) RETURN labels(n) AS ls, count(*) AS n")}
    rels = {r["t"]: r["n"] for r in _read(
        s, "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n")}
    node_props = collections.defaultdict(dict)
    for r in _read(s, "MATCH (n) UNWIND labels(n) AS l UNWIND keys(n) AS k "
                      "RETURN l, k, count(*) AS n"):
        node_props[r["l"]][r["k"]] = r["n"]
    rel_props = collections.defaultdict(dict)
    for r in _read(s, "MATCH ()-[r]->() UNWIND keys(r) AS k "
                      "RETURN type(r) AS t, k, count(*) AS n"):
        rel_props[r["t"]][r["k"]] = r["n"]
    checksums = dict(_read(s, """
        OPTIONAL MATCH (t:Tag)
        WITH count(t.emb) AS tag_emb_present,
             sum(reduce(a = 0.0, x IN coalesce(t.emb, []) | a + x)) AS tag_emb_sum,
             sum(size(coalesce(t.name, ''))) AS tag_name_chars
        OPTIONAL MATCH (c:Chunk)
        WITH tag_emb_present, tag_emb_sum, tag_name_chars,
             count(c.desc_emb) AS desc_emb_present,
             sum(reduce(a = 0.0, x IN coalesce(c.desc_emb, []) | a + x)) AS desc_emb_sum,
             sum(coalesce(c.token_estimate, 0)) AS token_estimate_sum,
             sum(size(coalesce(c.chunk_id, ''))) AS chunk_id_chars
        OPTIONAL MATCH (f:File)
        WITH tag_emb_present, tag_emb_sum, tag_name_chars, desc_emb_present,
             desc_emb_sum, token_estimate_sum, chunk_id_chars,
             sum(coalesce(f.size_bytes, 0)) AS file_bytes_sum
        OPTIONAL MATCH ()-[r:HAS_TAG]->()
        RETURN tag_emb_present, tag_emb_sum, tag_name_chars, desc_emb_present,
               desc_emb_sum, token_estimate_sum, chunk_id_chars, file_bytes_sum,
               sum(coalesce(r.w_chunk, 0.0)) AS has_tag_w_chunk_sum,
               count(r.run_id) AS has_tag_run_id_present
    """)[0])
    return {"labels": labels, "rels": rels,
            "node_prop_coverage": {k: dict(v) for k, v in node_props.items()},
            "rel_prop_coverage": {k: dict(v) for k, v in rel_props.items()},
            "checksums": checksums}


def compare_snapshots(what: str, a: dict, b: dict) -> list:
    """Every disagreement between two snapshots, float checksums compared
    within CHECKSUM_REL_TOL. Empty means identical."""
    diffs = []
    for section in ("labels", "rels", "node_prop_coverage", "rel_prop_coverage"):
        if a[section] != b[section]:
            diffs.append(f"{what}: {section} differ: {a[section]} != {b[section]}")
    for key, va in a["checksums"].items():
        vb = b["checksums"].get(key)
        if isinstance(va, float) or isinstance(vb, float):
            scale = max(abs(float(va)), abs(float(vb)), 1.0)
            if abs(float(va) - float(vb)) > CHECKSUM_REL_TOL * scale:
                diffs.append(f"{what}: checksum {key}: {va} != {vb}")
        elif va != vb:
            diffs.append(f"{what}: checksum {key}: {va} != {vb}")
    return diffs


def schema_rows(s) -> tuple:
    """The source's declarative schema: constraints, and the indexes that no
    constraint owns (LOOKUP indexes excluded — a new database carries its
    own)."""
    constraints = _read(s, "SHOW CONSTRAINTS YIELD name, type, entityType, "
                           "labelsOrTypes, properties RETURN *")
    owned = {c["name"] for c in constraints}
    indexes = [r for r in _read(
        s, "SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, "
           "properties, options RETURN *")
        if r["type"] != "LOOKUP" and r["name"] not in owned]
    return constraints, indexes


def _constraint_cypher(c: dict) -> str:
    label = _bt(c["labelsOrTypes"][0])
    props = ", ".join(f"n.{_bt(p)}" for p in c["properties"])
    if c["type"] == "NODE_PROPERTY_UNIQUENESS":
        require = f"({props}) IS UNIQUE" if len(c["properties"]) > 1 else f"{props} IS UNIQUE"
    elif c["type"] == "NODE_KEY":
        require = f"({props}) IS NODE KEY"
    else:
        raise SystemExit(f"constraint type {c['type']!r} not covered — extend "
                         f"_constraint_cypher before copying this schema.")
    return (f"CREATE CONSTRAINT {_bt(c['name'])} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE {require}")


def _index_cypher(ix: dict) -> str:
    label = _bt(ix["labelsOrTypes"][0])
    config = (ix.get("options") or {}).get("indexConfig") or {}
    config_literal = ", ".join(f"{_bt(k)}: {json.dumps(v)}"
                               for k, v in sorted(config.items()))
    options = f" OPTIONS {{indexConfig: {{{config_literal}}}}}" if config_literal else ""
    name = _bt(ix["name"])
    if ix["type"] == "RANGE" and ix["entityType"] == "NODE":
        props = ", ".join(f"n.{_bt(p)}" for p in ix["properties"])
        return f"CREATE INDEX {name} IF NOT EXISTS FOR (n:{label}) ON ({props})"
    if ix["type"] == "RANGE" and ix["entityType"] == "RELATIONSHIP":
        props = ", ".join(f"r.{_bt(p)}" for p in ix["properties"])
        return (f"CREATE INDEX {name} IF NOT EXISTS "
                f"FOR ()-[r:{label}]-() ON ({props})")
    if ix["type"] == "FULLTEXT" and ix["entityType"] == "NODE":
        props = ", ".join(f"n.{_bt(p)}" for p in ix["properties"])
        return (f"CREATE FULLTEXT INDEX {name} IF NOT EXISTS "
                f"FOR (n:{label}) ON EACH [{props}]{options}")
    if ix["type"] == "VECTOR" and ix["entityType"] == "NODE":
        prop = _bt(ix["properties"][0])
        return (f"CREATE VECTOR INDEX {name} IF NOT EXISTS "
                f"FOR (n:{label}) ON (n.{prop}){options}")
    raise SystemExit(f"index type {ix['type']}/{ix['entityType']} not covered — "
                     f"extend _index_cypher before copying this schema.")


def await_indexes(s, timeout_s: float = INDEX_WAIT_S) -> None:
    """Block until every index on the session's database is ONLINE; a FAILED
    index or the timeout fails loud."""
    t0 = time.perf_counter()
    while True:
        states = _read(s, "SHOW INDEXES YIELD name, state RETURN name, state")
        failed = [r["name"] for r in states if r["state"] == "FAILED"]
        if failed:
            raise SystemExit(f"index(es) FAILED: {failed}")
        pending = [r["name"] for r in states if r["state"] != "ONLINE"]
        if not pending:
            return
        if time.perf_counter() - t0 > timeout_s:
            raise SystemExit(f"indexes not ONLINE after {timeout_s:.0f}s: {pending}")
        print(f"  waiting for {len(pending)} index(es): {pending[:4]} …", flush=True)
        time.sleep(2.0)


# --- step: copy -----------------------------------------------------------------

def step_copy(drv, source: str, target: str, recreate: bool) -> None:
    _guard_target(source, target)
    t0 = time.perf_counter()

    with drv.session(database="system") as sys_s:
        names = {r["name"] for r in _read(sys_s, "SHOW DATABASES YIELD name RETURN name")}
    if source not in names:
        raise SystemExit(f"source database {source!r} does not exist.")
    if target in names and not recreate:
        raise SystemExit(f"target database {target!r} already exists — "
                         f"pass --recreate to drop and rebuild it.")

    print(f"snapshotting source {source!r} …", flush=True)
    with drv.session(database=source, default_access_mode="READ") as s:
        source_before = snapshot(s)
        constraints, indexes = schema_rows(s)
        n_nodes = _one(s, "MATCH (n) RETURN count(n)")
        n_rels = _one(s, "MATCH ()-[r]->() RETURN count(r)")
    print(f"  {n_nodes} nodes, {n_rels} relationships, "
          f"{len(constraints)} constraints, {len(indexes)} indexes", flush=True)

    with drv.session(database="system") as sys_s:
        if target in names:
            print(f"dropping and recreating {target!r} …", flush=True)
            sys_s.run(f"DROP DATABASE {_bt(target)} IF EXISTS DESTROY DATA WAIT").consume()
        sys_s.run(f"CREATE DATABASE {_bt(target)} IF NOT EXISTS WAIT").consume()
    _clear_build_records(target)
    with drv.session(database=target) as s:
        if _one(s, "MATCH (n) RETURN count(n)") != 0:
            raise SystemExit(f"target {target!r} is not empty.")

    nodes_created = 0
    node_labels: dict = {}
    with drv.session(database=source, default_access_mode="READ") as rs, \
            drv.session(database=target) as ws:
        buffers: dict = collections.defaultdict(list)

        def flush(label_set: str) -> int:
            rows = buffers.pop(label_set)
            label_cypher = "".join(f":{_bt(l)}" for l in label_set.split("\x00"))
            counters = ws.run(
                f"UNWIND $rows AS row CREATE (n{label_cypher}) "
                f"SET n = row.props SET n.{_bt(COPY_KEY)} = row.eid",
                rows=rows).consume().counters
            return counters.nodes_created

        bar = progress(total=n_nodes, desc="copy nodes", unit="node")
        for rec in rs.run("MATCH (n) RETURN elementId(n) AS eid, labels(n) AS ls, "
                          "properties(n) AS props"):
            label_set, first_label = node_label_key(rec["eid"], rec["ls"])
            node_labels[rec["eid"]] = first_label
            buffers[label_set].append({"eid": rec["eid"], "props": rec["props"]})
            if len(buffers[label_set]) >= NODE_BATCH:
                nodes_created += flush(label_set)
            bar.update(1)
        for label_set in list(buffers):
            nodes_created += flush(label_set)
        bar.close()
    if nodes_created != n_nodes:
        raise SystemExit(f"copied {nodes_created} nodes, source has {n_nodes}.")

    with drv.session(database=target) as ws:
        for label in sorted(set(node_labels.values())):
            ws.run(f"CREATE INDEX {_bt('tmp_copy_' + label.lower())} IF NOT EXISTS "
                   f"FOR (n:{_bt(label)}) ON (n.{_bt(COPY_KEY)})").consume()
        await_indexes(ws)

    rels_created = 0
    with drv.session(database=source, default_access_mode="READ") as rs, \
            drv.session(database=target) as ws:
        buffers = collections.defaultdict(list)

        def flush_rels(key: tuple) -> int:
            rel_type, src_label, dst_label = key
            rows = buffers.pop(key)
            counters = ws.run(
                f"UNWIND $rows AS row "
                f"MATCH (a:{_bt(src_label)} {{{_bt(COPY_KEY)}: row.src}}) "
                f"MATCH (b:{_bt(dst_label)} {{{_bt(COPY_KEY)}: row.dst}}) "
                f"CREATE (a)-[r:{_bt(rel_type)}]->(b) SET r = row.props",
                rows=rows).consume().counters
            return counters.relationships_created

        bar = progress(total=n_rels, desc="copy rels", unit="rel")
        for rec in rs.run("MATCH (a)-[r]->(b) RETURN elementId(a) AS src, "
                          "elementId(b) AS dst, type(r) AS t, properties(r) AS props"):
            key = (rec["t"], node_labels[rec["src"]], node_labels[rec["dst"]])
            buffers[key].append({"src": rec["src"], "dst": rec["dst"],
                                 "props": rec["props"]})
            if len(buffers[key]) >= REL_BATCH:
                rels_created += flush_rels(key)
            bar.update(1)
        for key in list(buffers):
            rels_created += flush_rels(key)
        bar.close()
    if rels_created != n_rels:
        raise SystemExit(f"copied {rels_created} relationships, source has {n_rels}.")

    print("recreating constraints and indexes …", flush=True)
    with drv.session(database=target) as ws:
        for c in constraints:
            ws.run(_constraint_cypher(c)).consume()
        for ix in indexes:
            ws.run(_index_cypher(ix)).consume()
        for label in sorted(set(node_labels.values())):
            ws.run(f"DROP INDEX {_bt('tmp_copy_' + label.lower())} IF EXISTS").consume()
        bar = progress(total=n_nodes, desc="strip copy key", unit="node")
        for label in sorted(set(node_labels.values())):
            while True:
                stripped = _one(
                    ws, f"MATCH (n:{_bt(label)}) WHERE n.{_bt(COPY_KEY)} IS NOT NULL "
                        f"WITH n LIMIT $lim REMOVE n.{_bt(COPY_KEY)} RETURN count(n)",
                    lim=WRITE_BATCH)
                bar.update(stripped)
                if stripped == 0:
                    break
        bar.close()
        await_indexes(ws)

    print("verifying the copy …", flush=True)
    with drv.session(database=target, default_access_mode="READ") as s:
        target_snap = snapshot(s)
        target_constraints, target_indexes = schema_rows(s)
    diffs = compare_snapshots("copy", source_before, target_snap)

    def schema_key(rows):
        return sorted((r["name"], r["type"], tuple(r["labelsOrTypes"]),
                       tuple(r["properties"])) for r in rows)
    if schema_key(constraints) != schema_key(target_constraints):
        diffs.append("constraints differ between source and target")
    if schema_key(indexes) != schema_key(target_indexes):
        diffs.append("indexes differ between source and target")
    for d in diffs:
        print(f"  DIFF {d}", flush=True)
    if diffs:
        raise SystemExit("copy verification failed.")
    print(f"  copy verified: {nodes_created} nodes, {rels_created} rels, "
          f"tag_emb {target_snap['checksums']['tag_emb_present']}, "
          f"desc_emb {target_snap['checksums']['desc_emb_present']}", flush=True)

    _write_step(target, "copy", {
        "timestamp": _utc_now(), "source_database": source,
        "target_database": target, "nodes_copied": nodes_created,
        "rels_copied": rels_created,
        "constraints_recreated": len(constraints),
        "indexes_recreated": len(indexes),
        "source_before": source_before, "target_after_copy": target_snap,
        "elapsed_s": round(time.perf_counter() - t0, 1),
    })


# --- step: cleanup ---------------------------------------------------------------

def step_cleanup(drv, source: str, target: str) -> None:
    _guard_target(source, target)
    _require_step(target, "copy")
    t0 = time.perf_counter()

    print(f"reading tag vocabulary and edges from {target!r} …", flush=True)
    with drv.session(database=target, default_access_mode="READ") as s:
        tag_degree = {r["name"]: r["n"] for r in _read(
            s, "MATCH (t:Tag) OPTIONAL MATCH (t)<-[r:HAS_TAG]-() "
               "RETURN t.name AS name, count(r) AS n")}
        chunk_tags = collections.defaultdict(set)
        for r in _read(s, "MATCH (c:Chunk)-[:HAS_TAG]->(t:Tag) "
                          "RETURN c.chunk_id AS cid, t.name AS name"):
            chunk_tags[r["cid"]].add(r["name"])
        zero_before = _one(s, "MATCH (c:Chunk) WHERE NOT (c)-[:HAS_TAG]->() "
                              "RETURN count(c)")
    print(f"  {len(tag_degree)} tags, {sum(tag_degree.values())} HAS_TAG edges, "
          f"{zero_before} chunks without tags", flush=True)

    print("deriving the removal predicate from the corpus …", flush=True)
    root = CORPUS / DATASET_ID
    products = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                for p in sorted((root / "products").glob("*.json"))}
    classes = derive_removal(set(tag_degree), collect_slug_sources(products))
    remove = classes["REMOVE"]
    class_census = {k: {"tags": len(v), "edges": sum(tag_degree[n] for n in v)}
                    for k, v in classes.items()}
    for k, v in class_census.items():
        print(f"  {k:<10} {v['tags']:>6} tags {v['edges']:>6} edges", flush=True)

    impact = removal_impact(remove, tag_degree, chunk_tags)
    gate("removal", impact, EXPECTED_REMOVAL)

    removed = sorted(remove)
    removed_sha = gate_removed_sha(removed)
    print(f"deleting {len(removed)} Tag nodes from {target!r} …", flush=True)
    deleted_nodes = deleted_rels = 0
    with drv.session(database=target) as s:
        bar = progress(total=len(removed), desc="detach delete", unit="tag")
        for i in range(0, len(removed), DELETE_BATCH):
            batch = removed[i:i + DELETE_BATCH]
            counters = s.run("UNWIND $names AS name MATCH (t:Tag {name: name}) "
                             "DETACH DELETE t", names=batch).consume().counters
            deleted_nodes += counters.nodes_deleted
            deleted_rels += counters.relationships_deleted
            bar.update(len(batch))
        bar.close()
    if deleted_nodes != impact["tags"] or deleted_rels != impact["edges"]:
        raise SystemExit(f"delete counters disagree with the gate: "
                         f"{deleted_nodes} nodes / {deleted_rels} rels deleted, "
                         f"gate said {impact['tags']} / {impact['edges']}.")

    with drv.session(database=target, default_access_mode="READ") as s:
        post = {
            "tags": _one(s, "MATCH (t:Tag) RETURN count(t)"),
            "has_tag_edges": _one(s, "MATCH ()-[r:HAS_TAG]->() RETURN count(r)"),
            "chunks_without_tags": _one(
                s, "MATCH (c:Chunk) WHERE NOT (c)-[:HAS_TAG]->() RETURN count(c)"),
        }
    expected_post = {"tags": len(tag_degree) - impact["tags"],
                     "has_tag_edges": sum(tag_degree.values()) - impact["edges"],
                     "chunks_without_tags": zero_before}
    gate("post-cleanup", post, expected_post)
    print(f"  cleanup done: {post['tags']} tags, {post['has_tag_edges']} edges "
          f"remain.", flush=True)

    _write_step(target, "cleanup", {
        "timestamp": _utc_now(), "target_database": target,
        "predicate": {
            "spec": "REMOVE = (tag_names ∩ slug(prs[].title)) ∪ (tag_names ∩ "
                    "slug(prs[].link ∪ urls[].link ∪ documents[].document_link))"
                    " ∪ prefix(https_|www_|github_com_) ∪ (fullmatch "
                    "github_pr_\\d+ ∪ fullmatch .+_pr_\\d+ ∪ fullmatch "
                    "pull_request_\\d+ ∪ contains _pull_\\d+); bare http_ "
                    "excluded; vocabulary-level",
            "classes": class_census,
        },
        "impact": impact, "deleted_nodes": deleted_nodes,
        "deleted_rels": deleted_rels, "post": post,
        "removed_tags_sha256": removed_sha, "removed_tags": removed,
        "elapsed_s": round(time.perf_counter() - t0, 1),
    })


# --- step: entities ---------------------------------------------------------------

def step_entities(drv, source: str, target: str) -> None:
    _guard_target(source, target)
    copy_rec = _require_step(target, "copy")
    _require_step(target, "cleanup", after=copy_rec)
    t0 = time.perf_counter()

    with drv.session(database=target, default_access_mode="READ") as s:
        for label in (PERSON_LABEL, PRODUCT_LABEL, CHANNEL_LABEL):
            present = _one(s, f"MATCH (n:{_bt(label)}) RETURN count(n)")
            if present:
                raise SystemExit(f"{target!r} already carries {present} "
                                 f"{label} node(s) — the entity layer is not "
                                 f"re-runnable over itself.")
        chunk_rows = _read(s, "MATCH (c:Chunk) RETURN c.chunk_id AS chunkId, "
                              "c.section AS section, c.product AS product, "
                              "c.channel AS channel, c.locator_json AS locator "
                              "ORDER BY chunkId")
    print(f"  {len(chunk_rows)} chunks read from {target!r}", flush=True)

    root = CORPUS / DATASET_ID
    products = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                for p in sorted((root / "products").glob("*.json"))}
    derived = derive_entities(chunk_rows, products)
    gate("entities", derived["census"], EXPECTED_ENTITIES)
    corpus_products = set(products)
    graph_products = {p for _, p in derived["product_edges"]}
    if graph_products != corpus_products:
        raise SystemExit(f"chunk products disagree with the corpus product "
                         f"files: {sorted(graph_products ^ corpus_products)}")

    structured = derived["structured_persons"]
    mention_only = {}
    for kind in ("eid", "emp", "cust"):
        for _, pid in derived["mentions"][kind]:
            if pid not in structured and pid not in mention_only:
                mention_only[pid] = classify_id(pid)
    mention_only_kinds = collections.Counter(mention_only.values())
    print(f"  persons: {len(structured)} structured + {len(mention_only)} "
          f"mention-only ({dict(mention_only_kinds)})", flush=True)

    with drv.session(database=target) as s:
        s.run(f"CREATE CONSTRAINT `person_id` IF NOT EXISTS "
              f"FOR (n:{_bt(PERSON_LABEL)}) REQUIRE n.id IS UNIQUE").consume()
        s.run(f"CREATE CONSTRAINT `product_name` IF NOT EXISTS "
              f"FOR (n:{_bt(PRODUCT_LABEL)}) REQUIRE n.name IS UNIQUE").consume()
        s.run(f"CREATE CONSTRAINT `channel_name` IF NOT EXISTS "
              f"FOR (n:{_bt(CHANNEL_LABEL)}) REQUIRE n.name IS UNIQUE").consume()
        await_indexes(s)

        person_rows = ([{"id": pid, "kind": kind} for pid, kind in sorted(structured.items())]
                       + [{"id": pid, "kind": kind} for pid, kind in sorted(mention_only.items())])
        bar = progress(total=len(person_rows), desc="person nodes", unit="node")
        for i in range(0, len(person_rows), WRITE_BATCH):
            batch = person_rows[i:i + WRITE_BATCH]
            s.run(f"UNWIND $rows AS row CREATE (p:{_bt(PERSON_LABEL)} "
                  f"{{id: row.id, kind: row.kind}})", rows=batch).consume()
            bar.update(len(batch))
        bar.close()
        s.run(f"UNWIND $names AS name CREATE (p:{_bt(PRODUCT_LABEL)} {{name: name}})",
              names=sorted(graph_products)).consume()
        s.run(f"UNWIND $names AS name CREATE (p:{_bt(CHANNEL_LABEL)} {{name: name}})",
              names=sorted({c for _, c in derived["channel_edges"]})).consume()

        def write_edges(rows: list, cypher: str, desc: str) -> int:
            created = 0
            bar = progress(total=len(rows), desc=desc, unit="edge")
            for i in range(0, len(rows), WRITE_BATCH):
                batch = rows[i:i + WRITE_BATCH]
                created += s.run(cypher, rows=batch).consume().counters.relationships_created
                bar.update(len(batch))
            bar.close()
            return created

        involves_rows = [{"cid": cid, "pid": pid, "role": role}
                         for cid, pid, role in sorted(derived["involves"])]
        n_involves = write_edges(involves_rows, (
            f"UNWIND $rows AS row MATCH (c:Chunk {{chunk_id: row.cid}}) "
            f"MATCH (p:{_bt(PERSON_LABEL)} {{id: row.pid}}) "
            f"CREATE (c)-[r:{_bt(INVOLVES_TYPE)} {{role: row.role}}]->(p)"), "involves")

        mention_rows = [{"cid": cid, "pid": pid}
                        for kind in ("eid", "emp", "cust")
                        for cid, pid in sorted(derived["mentions"][kind])]
        n_mentions = write_edges(mention_rows, (
            f"UNWIND $rows AS row MATCH (c:Chunk {{chunk_id: row.cid}}) "
            f"MATCH (p:{_bt(PERSON_LABEL)} {{id: row.pid}}) "
            f"CREATE (c)-[r:{_bt(MENTIONS_TYPE)}]->(p)"), "mentions")

        product_rows = [{"cid": cid, "name": name}
                        for cid, name in sorted(derived["product_edges"])]
        n_products = write_edges(product_rows, (
            f"UNWIND $rows AS row MATCH (c:Chunk {{chunk_id: row.cid}}) "
            f"MATCH (p:{_bt(PRODUCT_LABEL)} {{name: row.name}}) "
            f"CREATE (c)-[r:{_bt(PRODUCT_TYPE)}]->(p)"), "in_product")

        channel_rows = [{"cid": cid, "name": name}
                        for cid, name in sorted(derived["channel_edges"])]
        n_channels = write_edges(channel_rows, (
            f"UNWIND $rows AS row MATCH (c:Chunk {{chunk_id: row.cid}}) "
            f"MATCH (p:{_bt(CHANNEL_LABEL)} {{name: row.name}}) "
            f"CREATE (c)-[r:{_bt(CHANNEL_TYPE)}]->(p)"), "in_channel")

    written = {"involves": n_involves, "mentions": n_mentions,
               "product_edges": n_products, "channel_edges": n_channels}
    expected_written = {"involves": len(involves_rows),
                        "mentions": len(mention_rows),
                        "product_edges": len(product_rows),
                        "channel_edges": len(channel_rows)}
    gate("entity-writes", written, expected_written)

    with drv.session(database=target, default_access_mode="READ") as s:
        db_census = {
            "person_kinds": {r["k"]: r["n"] for r in _read(
                s, f"MATCH (p:{_bt(PERSON_LABEL)}) RETURN p.kind AS k, count(*) AS n")},
            "involves": {r["role"]: r["n"] for r in _read(
                s, f"MATCH ()-[r:{_bt(INVOLVES_TYPE)}]->() "
                   f"RETURN r.role AS role, count(*) AS n")},
            "mentions": {r["k"]: r["n"] for r in _read(
                s, f"MATCH ()-[r:{_bt(MENTIONS_TYPE)}]->(p:{_bt(PERSON_LABEL)}) "
                   f"RETURN p.kind AS k, count(*) AS n")},
            "product_nodes": _one(s, f"MATCH (p:{_bt(PRODUCT_LABEL)}) RETURN count(p)"),
            "channel_nodes": _one(s, f"MATCH (p:{_bt(CHANNEL_LABEL)}) RETURN count(p)"),
            "product_edges": _one(s, f"MATCH ()-[r:{_bt(PRODUCT_TYPE)}]->() RETURN count(r)"),
            "channel_edges": _one(s, f"MATCH ()-[r:{_bt(CHANNEL_TYPE)}]->() RETURN count(r)"),
            "person_total": _one(s, f"MATCH (p:{_bt(PERSON_LABEL)}) RETURN count(p)"),
        }
    for role, n in EXPECTED_ENTITIES["involves"].items():
        if db_census["involves"].get(role) != n:
            raise SystemExit(f"post-write INVOLVES {role}: "
                             f"{db_census['involves'].get(role)} != {n}")
    for kind, n in EXPECTED_ENTITIES["mentions"].items():
        if db_census["mentions"].get(kind, 0) != n:
            raise SystemExit(f"post-write MENTIONS {kind}: "
                             f"{db_census['mentions'].get(kind, 0)} != {n}")
    print(f"  entity layer written: {db_census['person_total']} Person, "
          f"{db_census['product_nodes']} Product, "
          f"{db_census['channel_nodes']} Channel", flush=True)

    _write_step(target, "entities", {
        "timestamp": _utc_now(), "target_database": target,
        "derived_census": derived["census"],
        "structured_persons": len(structured),
        "mention_only_persons": dict(mention_only_kinds),
        "person_total": db_census["person_total"],
        "written": written, "db_census": db_census,
        "relationship_types": {"involves": INVOLVES_TYPE,
                               "mentions": MENTIONS_TYPE,
                               "product": PRODUCT_TYPE,
                               "channel": CHANNEL_TYPE},
        "elapsed_s": round(time.perf_counter() - t0, 1),
    })


# --- step: verify -----------------------------------------------------------------

def step_verify(drv, source: str, target: str) -> None:
    _guard_target(source, target)
    copy_rec = _require_step(target, "copy")
    cleanup_rec = _require_step(target, "cleanup", after=copy_rec)
    entities_rec = _require_step(target, "entities", after=cleanup_rec)
    t0 = time.perf_counter()

    print(f"re-snapshotting source {source!r} for the untouched proof …", flush=True)
    with drv.session(database=source, default_access_mode="READ") as s:
        source_after = snapshot(s)
    source_diffs = compare_snapshots("source", copy_rec["source_before"], source_after)
    for d in source_diffs:
        print(f"  DIFF {d}", flush=True)
    if source_diffs:
        raise SystemExit(f"source {source!r} changed during the build — "
                         f"the untouched proof failed.")
    print(f"  source {source!r} untouched: snapshots identical.", flush=True)

    removed = cleanup_rec["removed_tags"]
    with drv.session(database=target, default_access_mode="READ") as s:
        still_present = 0
        bar = progress(total=len(removed), desc="removed absent", unit="tag")
        for i in range(0, len(removed), WRITE_BATCH):
            batch = removed[i:i + WRITE_BATCH]
            still_present += _one(s, "UNWIND $names AS name "
                                     "MATCH (t:Tag {name: name}) RETURN count(t)",
                                  names=batch)
            bar.update(len(batch))
        bar.close()
        if still_present:
            raise SystemExit(f"{still_present} removed tag(s) still present.")
        print(f"snapshotting the final graph {target!r} …", flush=True)
        final = snapshot(s)
    with drv.session(database="system") as s:
        databases = _read(s, "SHOW DATABASES YIELD name RETURN name")

    before = copy_rec["source_before"]
    expected_labels = dict(before["labels"])
    expected_labels["Tag"] = cleanup_rec["post"]["tags"]
    expected_labels[PERSON_LABEL] = entities_rec["person_total"]
    expected_labels[PRODUCT_LABEL] = entities_rec["db_census"]["product_nodes"]
    expected_labels[CHANNEL_LABEL] = entities_rec["db_census"]["channel_nodes"]
    expected_rels = dict(before["rels"])
    expected_rels["HAS_TAG"] = cleanup_rec["post"]["has_tag_edges"]
    expected_rels[INVOLVES_TYPE] = sum(EXPECTED_ENTITIES["involves"].values())
    expected_rels[MENTIONS_TYPE] = sum(EXPECTED_ENTITIES["mentions"].values())
    expected_rels[PRODUCT_TYPE] = EXPECTED_ENTITIES["product_edges"]
    expected_rels[CHANNEL_TYPE] = EXPECTED_ENTITIES["channel_edges"]
    gate("final-labels", final["labels"], expected_labels)
    gate("final-rels", final["rels"], expected_rels)
    if (before["checksums"]["tag_emb_present"] != before["labels"].get("Tag", 0)
            or before["checksums"]["desc_emb_present"] != before["labels"].get("Chunk", 0)):
        raise SystemExit("source embedding coverage is not full — the final "
                         "embedding gate cannot be derived from it.")
    emb = {"tag_emb_present": final["checksums"]["tag_emb_present"],
           "desc_emb_present": final["checksums"]["desc_emb_present"]}
    gate("final-embeddings", emb,
         {"tag_emb_present": expected_labels["Tag"],
          "desc_emb_present": expected_labels["Chunk"]})

    manifest_path = BUILD_DIR / target / "build_manifest.json"
    manifest_path.write_text(json.dumps({
        "target_database": target,
        "source_database": source,
        "timestamp": _utc_now(),
        "authority": DESIGN_DOC,
        "execution_defaults": EXECUTION_DEFAULTS,
        "databases_on_dbms": sorted(r["name"] for r in databases),
        "steps": {
            "copy": {k: v for k, v in copy_rec.items() if k != "source_before"},
            "cleanup": {k: v for k, v in cleanup_rec.items()
                        if k != "removed_tags"},
            "entities": entities_rec,
        },
        "removal_predicate": cleanup_rec["predicate"],
        "removed_tags_sha256": cleanup_rec["removed_tags_sha256"],
        "removed_tags": removed,
        "verification": {
            "source_untouched": True,
            "source_before": copy_rec["source_before"],
            "source_after": source_after,
            "removed_tags_still_present": still_present,
            "final_target_snapshot": final,
        },
        "elapsed_s": round(time.perf_counter() - t0, 1),
    }, indent=1, sort_keys=True), encoding="utf-8")
    print(f"build manifest written last: {manifest_path}", flush=True)


# --- CLI ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("copy", "cleanup", "entities", "verify"))
    parser.add_argument("--source-db", default=SOURCE_DATABASE,
                        help="database the copy reads (read-only throughout)")
    parser.add_argument("--target-db", default=TARGET_DATABASE,
                        help="database the build writes (never a protected name)")
    parser.add_argument("--recreate", action="store_true",
                        help="copy only: drop an existing target and rebuild it")
    args = parser.parse_args()

    drv = _driver()
    try:
        if args.step == "copy":
            step_copy(drv, args.source_db, args.target_db, args.recreate)
        elif args.step == "cleanup":
            step_cleanup(drv, args.source_db, args.target_db)
        elif args.step == "entities":
            step_entities(drv, args.source_db, args.target_db)
        else:
            step_verify(drv, args.source_db, args.target_db)
    finally:
        drv.close()


if __name__ == "__main__":
    main()
