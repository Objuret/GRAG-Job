from __future__ import annotations

if __name__ == "__main__":
    print("build_entity_graph: copy / cleanup / entities / relations / verify "
          "— loading neo4j …", flush=True)

import argparse
import collections
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from graph.db import DATASET_ID, _driver
from harness.progress import progress


SOURCE_DATABASE = "herb-eval"
TARGET_DATABASE = "herb-eval-v2"

GRAPH_VERSION = "copy+cleanup+directory-entities+relations"

PROTECTED_DATABASES = ("herb", "herb-eval", "neo4j", "system")

DESIGN_DOC = "docs/state/2026-08-12-entity-nodes-and-tag-cleanup-design.md"
ENTITY_DESIGN_DOC = "docs/state/2026-08-14-directory-entity-layer.md"

CORPUS = Path(__file__).resolve().parent.parent.parent / "data" / "corpus"

EMPLOYEE_FILE = "employee.json"
CUSTOMERS_FILE = "customers_data.json"
ORG_TREE_FILE = "salesforce_team.json"

EMPLOYEE_FIELDS = ("employee_id", "role", "org", "location")
CUSTOMER_FIELDS = ("id", "role", "company")

BUILD_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "graph_build"

EXECUTION_DEFAULTS = {
    "OPEN-1": "Employee + Customer + Org + Company + Product + Channel nodes; "
              "role and location are Employee attributes, role a Customer "
              "attribute; years and section stay chunk attributes",
    "OPEN-2": "an entity node exists where a corpus directory declares the "
              "entry; a person id no directory carries gets no node — the "
              "directory-less EMP_ logins are censused, never minted",
    "OPEN-3": "deterministic regex id-in-text mention edges in, as their own "
              "relationship type; name-resolver edges out",
    "OPEN-4": "the 61 existing metadata-mirror chunks kept unchanged",
    "OPEN-5": "vocabulary-level predicate; bare http_ protocol tags excluded "
              "from removal; decision/date tags not touched",
    "OPEN-6": "versioned copy, one combined new version",
    "OPEN-7": "new database herb-eval-v2; this manifest carries source, "
              "predicate + hash, counts, verification",
}

ENTITY_INCLUSION = {
    "Employee": "metadata/employee.json — one node per entry, keyed by the "
                "directory's own eid_ string, carrying that entry's `role` and "
                "`location`; the entry's `name` is read by nothing",
    "Customer": "metadata/customers_data.json — one node per entry, keyed by "
                "the directory's own CUST- string, carrying that entry's "
                "`role`; the entry's `name` is read by nothing",
    "Org": "metadata/employee.json — one node per distinct `org` value the "
           "directory carries, keyed by the source's own string",
    "Company": "metadata/customers_data.json — one node per distinct `company` "
               "value the directory carries, keyed by the source's own string",
    "Product": "one node per distinct `product` attribute on the chunks, "
               "cross-checked against the corpus's own product files",
    "Channel": "one node per distinct `channel` attribute on the chunks",
    "INVOLVES": "every (chunk, person id, role) a structured content field "
                "declares — slack userId, PR author and reviewer logins, "
                "document author, meeting participants — for every id one of "
                "the two directories carries; an id no directory carries gets "
                "no edge and is censused as unlinked",
    "MENTIONS": "every (chunk, person id) an exact id regex finds in the "
                "chunk's own declared content leaves, for every id one of the "
                "two directories carries",
    "IN_PRODUCT": "every chunk's own `product` attribute",
    "IN_CHANNEL": "every chunk's own `channel` attribute",
}

RELATION_INCLUSION = {
    "MANAGES": "metadata/salesforce_team.json — every nesting of a person entry "
               "inside another entry's report list, for every entry in the tree; "
               "`role` is the source's own list-field name",
    "COLLEAGUE": "metadata/salesforce_team.json — every unordered pair of person "
                 "entries reporting to one entry, for every entry in the tree; "
                 "one edge per pair, endpoints in sorted id order, `manager` the "
                 "shared owner's id",
    "IN_ORG": "metadata/employee.json — every entry's own `org` field; the "
              "directory carries the field on every entry, so every entry gets "
              "the relation",
    "IN_COMPANY": "metadata/customers_data.json — every entry's own `company` "
                  "field; the directory carries the field on every entry, so "
                  "every entry gets the relation",
    "APPEARS_IN_PRODUCT": "every (Person, Product) pair one chunk holds through "
                          "an INVOLVES or MENTIONS edge and an IN_PRODUCT edge",
    "APPEARS_IN_CHANNEL": "every (Person, Channel) pair one chunk holds through "
                          "an INVOLVES or MENTIONS edge and an IN_CHANNEL edge",
    "HAS_CHANNEL": "every (Product, Channel) pair one chunk's own product and "
                   "channel attributes declare together",
}

R_URL_PREFIXES = ("https_", "www_", "github_com_")
_GITHUB_PR = re.compile(r"github_pr_\d+")
_X_PR = re.compile(r".+_pr_\d+")
_PULL_REQUEST = re.compile(r"pull_request_\d+")
_X_PULL = re.compile(r"_pull_\d+")

_EID = re.compile(r"eid_[0-9a-f]{8}")
_EMP = re.compile(r"EMP_\d{6,12}")
_CUST = re.compile(r"CUST-\d+")

ID_SPACES = ("eid", "emp", "cust", "malformed")
MENTION_SPACES = ("eid", "emp", "cust")

EXPECTED_REMOVAL = {"tags": 4111, "edges": 5470,
                    "chunks_touched": 2240, "chunks_emptied": 0}

EXPECTED_REMOVED_SHA256 = "6a279b3465f4ec55f440607d0239a4c56d1580ebd9582c43a4d31265b4426116"

EXPECTED_ENTITIES = {
    "employee_nodes": 530,
    "customer_nodes": 120,
    "org_nodes": 6,
    "company_nodes": 10,
    "product_nodes": 30,
    "channel_nodes": 294,
    "involves": {"speaker": 13006, "participant": 9964, "reviewer": 2053,
                 "pr_author": 1197, "doc_author": 786},
    "mentions": {"employee": 8589, "customer": 1043},
    "mention_persons": {"employee": 512, "customer": 120},
    "product_edges": 4808,
    "channel_edges": 2669,
    "unlinked_involves": {"eid": 0, "emp": 4590, "cust": 0, "malformed": 685},
    "unlinked_involve_ids": {"eid": 0, "emp": 4590, "cust": 0, "malformed": 9},
    "unlinked_mentions": {"eid": 2, "emp": 0, "cust": 0},
    "unlinked_mention_ids": {"eid": 2, "emp": 0, "cust": 0},
}

EXPECTED_RELATIONS = {
    "manages": 512,
    "colleague": 1891,
    "in_org": 530,
    "in_company": 120,
    "appears_in_product": 2320,
    "appears_in_channel": 4655,
    "has_channel": 294,
}

PERSON_LABEL = "Person"
EMPLOYEE_LABEL = "Employee"
CUSTOMER_LABEL = "Customer"
ORG_LABEL = "Org"
COMPANY_LABEL = "Company"
PRODUCT_LABEL = "Product"
CHANNEL_LABEL = "Channel"
INVOLVES_TYPE = "INVOLVES"
MENTIONS_TYPE = "MENTIONS"
PRODUCT_TYPE = "IN_PRODUCT"
CHANNEL_TYPE = "IN_CHANNEL"
MANAGES_TYPE = "MANAGES"
COLLEAGUE_TYPE = "COLLEAGUE"
ORG_TYPE = "IN_ORG"
COMPANY_TYPE = "IN_COMPANY"
PERSON_PRODUCT_TYPE = "APPEARS_IN_PRODUCT"
PERSON_CHANNEL_TYPE = "APPEARS_IN_CHANNEL"
PRODUCT_CHANNEL_TYPE = "HAS_CHANNEL"

ENTITY_LABELS = (PERSON_LABEL, EMPLOYEE_LABEL, CUSTOMER_LABEL, ORG_LABEL,
                 COMPANY_LABEL, PRODUCT_LABEL, CHANNEL_LABEL)
ENTITY_TYPES = (INVOLVES_TYPE, MENTIONS_TYPE, PRODUCT_TYPE, CHANNEL_TYPE,
                MANAGES_TYPE, COLLEAGUE_TYPE, ORG_TYPE, COMPANY_TYPE,
                PERSON_PRODUCT_TYPE, PERSON_CHANNEL_TYPE, PRODUCT_CHANNEL_TYPE)
SPINE_LABELS = ("Source", "File", "Chunk", "Tag")
SPINE_TYPES = ("CONTAINS", "HAS_CHUNK", "HAS_TAG")

COPY_KEY = "__copy_src"

NODE_BATCH = 500
REL_BATCH = 2000
WRITE_BATCH = 1000
DELETE_BATCH = 500
INDEX_WAIT_S = 600.0
CHECKSUM_REL_TOL = 1e-6


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def collect_slug_sources(products: dict) -> dict:
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
    return {
        "tags": len(remove),
        "edges": sum(tag_degree[n] for n in remove),
        "chunks_touched": sum(1 for tags in chunk_tags.values() if tags & remove),
        "chunks_emptied": sum(1 for tags in chunk_tags.values()
                              if tags and tags <= remove),
    }


def gate_removed_sha(removed: list) -> str:
    sha = hashlib.sha256("\n".join(removed).encode("utf-8")).hexdigest()
    print(f"  removed-list sha256 {sha}", flush=True)
    if sha != EXPECTED_REMOVED_SHA256:
        raise SystemExit(f"removed-list sha256 mismatch: derived {sha}, "
                         f"expected {EXPECTED_REMOVED_SHA256} — stopping with "
                         f"nothing deleted.")
    return sha


def gate(name: str, actual: dict, expected: dict) -> None:
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


def classify_id(pid: str) -> str:
    if _EID.fullmatch(pid):
        return "eid"
    if _EMP.fullmatch(pid):
        return "emp"
    if _CUST.fullmatch(pid):
        return "cust"
    return "malformed"


def read_metadata(name: str) -> list:
    return json.loads((CORPUS / DATASET_ID / "metadata" / name)
                      .read_text(encoding="utf-8"))


def read_directories() -> dict:
    employees, customers = {}, {}
    for eid, rec in read_metadata(EMPLOYEE_FILE).items():
        missing = [f for f in EMPLOYEE_FIELDS if not rec.get(f)]
        if missing:
            raise SystemExit(f"employee entry {eid!r} carries no {missing}")
        if rec["employee_id"] != eid:
            raise SystemExit(f"employee entry keyed {eid!r} carries "
                             f"employee_id {rec['employee_id']!r}")
        employees[eid] = {"role": rec["role"], "location": rec["location"],
                          "org": rec["org"]}
    for rec in read_metadata(CUSTOMERS_FILE):
        missing = [f for f in CUSTOMER_FIELDS if not rec.get(f)]
        if missing:
            raise SystemExit(f"customer entry {rec.get('id')!r} carries no {missing}")
        if rec["id"] in customers:
            raise SystemExit(f"customer id {rec['id']!r} appears twice")
        customers[rec["id"]] = {"role": rec["role"], "company": rec["company"]}
    collision = sorted(set(employees) & set(customers))
    if collision:
        raise SystemExit(f"id in both directories: {collision}")
    return {
        "employees": employees, "customers": customers,
        "orgs": sorted({v["org"] for v in employees.values()}),
        "companies": sorted({v["company"] for v in customers.values()}),
    }


def resolve_records(locator: dict, section: str, products: dict) -> list:
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


def derive_entities(chunk_rows: list, products: dict, directories: dict) -> dict:
    employees, customers = directories["employees"], directories["customers"]
    involves = set()
    mentions = set()
    unlinked_involves = {k: 0 for k in ID_SPACES}
    unlinked_involve_ids = {k: set() for k in ID_SPACES}
    unlinked_mentions = {k: 0 for k in MENTION_SPACES}
    unlinked_mention_ids = {k: set() for k in MENTION_SPACES}
    product_edges = set()
    channel_edges = set()
    bar = progress(total=len(chunk_rows), desc="resolve chunks", unit="chunk")
    for row in chunk_rows:
        locator = json.loads(row["locator"])
        records = resolve_records(locator, row["section"], products)
        roles, found = chunk_entities(row["section"], records)
        for role, pid in roles:
            if pid in employees or pid in customers:
                involves.add((row["chunkId"], pid, role))
            else:
                kind = classify_id(pid)
                unlinked_involves[kind] += 1
                unlinked_involve_ids[kind].add(pid)
        for kind, ids in found.items():
            for pid in ids:
                if pid in employees or pid in customers:
                    mentions.add((row["chunkId"], pid))
                else:
                    unlinked_mentions[kind] += 1
                    unlinked_mention_ids[kind].add(pid)
        if row["product"]:
            product_edges.add((row["chunkId"], row["product"]))
        if row["channel"]:
            channel_edges.add((row["chunkId"], row["channel"]))
        bar.update(1)
    bar.close()

    def by_side(pairs: set) -> dict:
        return {"employee": sum(1 for _, pid in pairs if pid in employees),
                "customer": sum(1 for _, pid in pairs if pid in customers)}

    persons = {pid for _, pid in mentions}
    return {
        "involves": involves,
        "mentions": sorted(mentions),
        "unlinked_ids": {
            "involves": {k: len(v) for k, v in unlinked_involve_ids.items()},
            "mentions": {k: sorted(v) for k, v in unlinked_mention_ids.items()},
            "malformed": sorted(unlinked_involve_ids["malformed"]),
        },
        "census": {
            "employee_nodes": len(employees),
            "customer_nodes": len(customers),
            "org_nodes": len(directories["orgs"]),
            "company_nodes": len(directories["companies"]),
            "product_nodes": len({p for _, p in product_edges}),
            "channel_nodes": len({c for _, c in channel_edges}),
            "involves": dict(collections.Counter(role for _, _, role in involves)),
            "mentions": by_side(mentions),
            "mention_persons": {
                "employee": len(persons & set(employees)),
                "customer": len(persons & set(customers))},
            "product_edges": len(product_edges),
            "channel_edges": len(channel_edges),
            "unlinked_involves": unlinked_involves,
            "unlinked_involve_ids": {k: len(v) for k, v in unlinked_involve_ids.items()},
            "unlinked_mentions": unlinked_mentions,
            "unlinked_mention_ids": {k: len(v) for k, v in unlinked_mention_ids.items()},
        },
        "product_edges": product_edges,
        "channel_edges": channel_edges,
    }


def report_lists(entry: dict) -> list:
    return sorted(k for k, v in entry.items()
                  if isinstance(v, list) and v
                  and all(isinstance(x, dict) and "employee_id" in x for x in v))


def org_tree_relations(team: list) -> dict:
    manages, colleague, persons = set(), set(), set()

    def walk(entry: dict, manager: str | None, field: str | None) -> None:
        eid = entry["employee_id"]
        persons.add(eid)
        if manager is not None:
            manages.add((manager, eid, field))
        reports = set()
        for key in report_lists(entry):
            for child in entry[key]:
                reports.add(child["employee_id"])
                walk(child, eid, key)
        group = sorted(reports)
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                colleague.add((group[i], group[j], eid))

    for top in team:
        walk(top, None, None)
    return {"manages": manages, "colleague": colleague, "persons": persons}


def membership_edges(directory: dict, field: str) -> list:
    return sorted((key, rec[field]) for key, rec in directory.items())


_DB_NAME = re.compile(r"^[a-z][a-z0-9.-]{2,62}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bt(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _guard_target(source: str, target: str) -> None:
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


def archive_manifest(manifest_path: Path) -> dict | None:
    if not manifest_path.is_file():
        return None
    prior = json.loads(manifest_path.read_text(encoding="utf-8"))
    stamp = prior.get("timestamp")
    if not stamp:
        raise SystemExit(f"{manifest_path} carries no timestamp to archive it "
                         f"under — move it aside before rebuilding.")
    archive = manifest_path.with_name(
        f"{manifest_path.stem}_{stamp.replace('-', '').replace(':', '')}.json")
    if archive.exists():
        raise SystemExit(f"{archive} already holds a manifest of that build "
                         f"timestamp — move it aside before rebuilding.")
    manifest_path.replace(archive)
    print(f"  prior manifest archived: {archive.name} "
          f"(graph_version {prior.get('graph_version')!r})", flush=True)
    return {"file": archive.name, "timestamp": stamp,
            "graph_version": prior.get("graph_version"),
            "graph_census_sha256": prior.get("graph_census_sha256")}


def _clear_build_records(target: str) -> None:
    directory = BUILD_DIR / target
    if directory.is_dir():
        for name in ("step_copy.json", "step_cleanup.json", "step_entities.json",
                     "step_relations.json", "build_manifest.json"):
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
    if not labels:
        raise SystemExit(f"node {eid} carries zero labels — unsupported "
                         f"source shape.")
    return "\x00".join(sorted(labels)), labels[0]


def snapshot(s) -> dict:
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


def spine_census(s) -> dict:
    census = {label: _one(s, f"MATCH (n:{_bt(label)}) RETURN count(n)")
              for label in SPINE_LABELS}
    census.update({t: _one(s, f"MATCH ()-[r:{_bt(t)}]->() RETURN count(r)")
                   for t in SPINE_TYPES})
    return census


def drop_entity_layer(drv, target: str) -> dict:
    any_entity = " OR ".join(f"n:{_bt(label)}" for label in ENTITY_LABELS)
    with drv.session(database=target, default_access_mode="READ") as s:
        before = spine_census(s)
        present = {label: _one(s, f"MATCH (n:{_bt(label)}) RETURN count(n)")
                   for label in ENTITY_LABELS}
        edges = {t: _one(s, f"MATCH ()-[r:{_bt(t)}]->() RETURN count(r)")
                 for t in ENTITY_TYPES}
        total = _one(s, f"MATCH (n) WHERE {any_entity} RETURN count(n)")
    print(f"  spine before the drop: {before}", flush=True)
    print(f"  entity nodes to drop: {total} "
          f"({ {k: v for k, v in present.items() if v} })", flush=True)
    print(f"  entity edges they carry: "
          f"{ {k: v for k, v in edges.items() if v} }", flush=True)

    deleted_nodes = deleted_rels = 0
    with drv.session(database=target) as s:
        bar = progress(total=total, desc="drop entity layer", unit="node")
        for label in ENTITY_LABELS:
            while True:
                counters = s.run(
                    f"MATCH (n:{_bt(label)}) WITH n LIMIT $lim DETACH DELETE n",
                    lim=DELETE_BATCH).consume().counters
                deleted_nodes += counters.nodes_deleted
                deleted_rels += counters.relationships_deleted
                bar.update(counters.nodes_deleted)
                if counters.nodes_deleted == 0:
                    break
        bar.close()

    with drv.session(database=target, default_access_mode="READ") as s:
        after = spine_census(s)
        left = {label: _one(s, f"MATCH (n:{_bt(label)}) RETURN count(n)")
                for label in ENTITY_LABELS}
    gate("spine-across-drop", after, before)
    gate("entity-nodes-after-drop", left, {label: 0 for label in ENTITY_LABELS})
    print(f"  dropped {deleted_nodes} entity nodes and {deleted_rels} edges; "
          f"spine unchanged", flush=True)
    return {"spine_before": before, "spine_after": after,
            "nodes_present": present, "edges_present": edges,
            "nodes_deleted": deleted_nodes, "rels_deleted": deleted_rels}


def compare_snapshots(what: str, a: dict, b: dict) -> list:
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


def step_entities(drv, source: str, target: str, rebuild: bool) -> None:
    _guard_target(source, target)
    copy_rec = _require_step(target, "copy")
    _require_step(target, "cleanup", after=copy_rec)
    t0 = time.perf_counter()

    dropped = None
    if rebuild:
        print(f"dropping the entity and relation layer of {target!r} …", flush=True)
        dropped = drop_entity_layer(drv, target)

    with drv.session(database=target, default_access_mode="READ") as s:
        for label in ENTITY_LABELS:
            present = _one(s, f"MATCH (n:{_bt(label)}) RETURN count(n)")
            if present:
                raise SystemExit(f"{target!r} already carries {present} "
                                 f"{label} node(s) — the entity layer is not "
                                 f"re-runnable over itself; pass --rebuild to "
                                 f"drop the layer and build it again.")
        chunk_rows = _read(s, "MATCH (c:Chunk) RETURN c.chunk_id AS chunkId, "
                              "c.section AS section, c.product AS product, "
                              "c.channel AS channel, c.locator_json AS locator "
                              "ORDER BY chunkId")
        spine_before = spine_census(s)
    print(f"  {len(chunk_rows)} chunks read from {target!r}", flush=True)

    print("reading the corpus directories …", flush=True)
    directories = read_directories()
    employees, customers = directories["employees"], directories["customers"]
    print(f"  {len(employees)} employees over {len(directories['orgs'])} orgs, "
          f"{len(customers)} customers over {len(directories['companies'])} "
          f"companies", flush=True)

    root = CORPUS / DATASET_ID
    products = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                for p in sorted((root / "products").glob("*.json"))}
    derived = derive_entities(chunk_rows, products, directories)
    gate("entities", derived["census"], EXPECTED_ENTITIES)
    corpus_products = set(products)
    graph_products = {p for _, p in derived["product_edges"]}
    if graph_products != corpus_products:
        raise SystemExit(f"chunk products disagree with the corpus product "
                         f"files: {sorted(graph_products ^ corpus_products)}")

    unlinked = derived["census"]["unlinked_involves"]
    print(f"  ids no directory carries, linked to nothing: "
          f"{sum(unlinked.values())} field reads over "
          f"{sum(derived['census']['unlinked_involve_ids'].values())} distinct "
          f"ids {derived['census']['unlinked_involve_ids']}", flush=True)
    print(f"  malformed ids among them: {derived['unlinked_ids']['malformed']}",
          flush=True)
    print(f"  eid-shaped ids in content text that no directory carries: "
          f"{derived['unlinked_ids']['mentions']['eid']}", flush=True)

    with drv.session(database=target) as s:
        s.run(f"CREATE CONSTRAINT `person_id` IF NOT EXISTS "
              f"FOR (n:{_bt(PERSON_LABEL)}) REQUIRE n.id IS UNIQUE").consume()
        s.run(f"CREATE CONSTRAINT `org_name` IF NOT EXISTS "
              f"FOR (n:{_bt(ORG_LABEL)}) REQUIRE n.name IS UNIQUE").consume()
        s.run(f"CREATE CONSTRAINT `company_name` IF NOT EXISTS "
              f"FOR (n:{_bt(COMPANY_LABEL)}) REQUIRE n.name IS UNIQUE").consume()
        s.run(f"CREATE CONSTRAINT `product_name` IF NOT EXISTS "
              f"FOR (n:{_bt(PRODUCT_LABEL)}) REQUIRE n.name IS UNIQUE").consume()
        s.run(f"CREATE CONSTRAINT `channel_name` IF NOT EXISTS "
              f"FOR (n:{_bt(CHANNEL_LABEL)}) REQUIRE n.name IS UNIQUE").consume()
        await_indexes(s)

        employee_rows = [{"id": eid, "role": rec["role"],
                          "location": rec["location"]}
                         for eid, rec in sorted(employees.items())]
        bar = progress(total=len(employee_rows), desc="employee nodes", unit="node")
        for i in range(0, len(employee_rows), WRITE_BATCH):
            batch = employee_rows[i:i + WRITE_BATCH]
            s.run(f"UNWIND $rows AS row CREATE (p:{_bt(EMPLOYEE_LABEL)}"
                  f":{_bt(PERSON_LABEL)} {{id: row.id, role: row.role, "
                  f"location: row.location}})", rows=batch).consume()
            bar.update(len(batch))
        bar.close()
        s.run(f"UNWIND $rows AS row CREATE (p:{_bt(CUSTOMER_LABEL)}"
              f":{_bt(PERSON_LABEL)} {{id: row.id, role: row.role}})",
              rows=[{"id": cid, "role": rec["role"]}
                    for cid, rec in sorted(customers.items())]).consume()
        s.run(f"UNWIND $names AS name CREATE (o:{_bt(ORG_LABEL)} {{name: name}})",
              names=directories["orgs"]).consume()
        s.run(f"UNWIND $names AS name CREATE (c:{_bt(COMPANY_LABEL)} {{name: name}})",
              names=directories["companies"]).consume()
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
                        for cid, pid in derived["mentions"]]
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
            "employee_nodes": _one(s, f"MATCH (p:{_bt(EMPLOYEE_LABEL)}) RETURN count(p)"),
            "customer_nodes": _one(s, f"MATCH (p:{_bt(CUSTOMER_LABEL)}) RETURN count(p)"),
            "org_nodes": _one(s, f"MATCH (o:{_bt(ORG_LABEL)}) RETURN count(o)"),
            "company_nodes": _one(s, f"MATCH (c:{_bt(COMPANY_LABEL)}) RETURN count(c)"),
            "product_nodes": _one(s, f"MATCH (p:{_bt(PRODUCT_LABEL)}) RETURN count(p)"),
            "channel_nodes": _one(s, f"MATCH (p:{_bt(CHANNEL_LABEL)}) RETURN count(p)"),
            "involves": {r["role"]: r["n"] for r in _read(
                s, f"MATCH ()-[r:{_bt(INVOLVES_TYPE)}]->() "
                   f"RETURN r.role AS role, count(*) AS n")},
            "mentions": {r["side"]: r["n"] for r in _read(
                s, f"MATCH ()-[r:{_bt(MENTIONS_TYPE)}]->(p:{_bt(PERSON_LABEL)}) "
                   f"RETURN CASE WHEN p:{_bt(EMPLOYEE_LABEL)} THEN 'employee' "
                   f"ELSE 'customer' END AS side, count(*) AS n")},
            "mention_persons": {r["side"]: r["n"] for r in _read(
                s, f"MATCH ()-[r:{_bt(MENTIONS_TYPE)}]->(p:{_bt(PERSON_LABEL)}) "
                   f"RETURN CASE WHEN p:{_bt(EMPLOYEE_LABEL)} THEN 'employee' "
                   f"ELSE 'customer' END AS side, count(DISTINCT p) AS n")},
            "product_edges": _one(s, f"MATCH ()-[r:{_bt(PRODUCT_TYPE)}]->() RETURN count(r)"),
            "channel_edges": _one(s, f"MATCH ()-[r:{_bt(CHANNEL_TYPE)}]->() RETURN count(r)"),
        }
        person_total = _one(s, f"MATCH (p:{_bt(PERSON_LABEL)}) RETURN count(p)")
        spine_after = spine_census(s)
    gate("entity-census", db_census,
         {k: v for k, v in EXPECTED_ENTITIES.items()
          if not k.startswith("unlinked")})
    gate("spine-across-entities", spine_after, spine_before)
    print(f"  entity layer written: {db_census['employee_nodes']} Employee + "
          f"{db_census['customer_nodes']} Customer ({person_total} Person), "
          f"{db_census['org_nodes']} Org, {db_census['company_nodes']} Company, "
          f"{db_census['product_nodes']} Product, "
          f"{db_census['channel_nodes']} Channel", flush=True)

    _write_step(target, "entities", {
        "timestamp": _utc_now(), "target_database": target,
        "inclusion_rules": ENTITY_INCLUSION,
        "derived_census": derived["census"],
        "unlinked_ids": derived["unlinked_ids"],
        "person_total": person_total,
        "dropped_before_rebuild": dropped,
        "spine_before": spine_before, "spine_after": spine_after,
        "written": written, "db_census": db_census,
        "node_labels": {"employee": [EMPLOYEE_LABEL, PERSON_LABEL],
                        "customer": [CUSTOMER_LABEL, PERSON_LABEL],
                        "org": ORG_LABEL, "company": COMPANY_LABEL,
                        "product": PRODUCT_LABEL, "channel": CHANNEL_LABEL},
        "relationship_types": {"involves": INVOLVES_TYPE,
                               "mentions": MENTIONS_TYPE,
                               "product": PRODUCT_TYPE,
                               "channel": CHANNEL_TYPE},
        "elapsed_s": round(time.perf_counter() - t0, 1),
    })


def step_relations(drv, source: str, target: str) -> None:
    _guard_target(source, target)
    copy_rec = _require_step(target, "copy")
    cleanup_rec = _require_step(target, "cleanup", after=copy_rec)
    _require_step(target, "entities", after=cleanup_rec)
    t0 = time.perf_counter()

    new_types = (MANAGES_TYPE, COLLEAGUE_TYPE, ORG_TYPE, COMPANY_TYPE,
                 PERSON_PRODUCT_TYPE, PERSON_CHANNEL_TYPE, PRODUCT_CHANNEL_TYPE)
    with drv.session(database=target, default_access_mode="READ") as s:
        for rel_type in new_types:
            n = _one(s, f"MATCH ()-[r:{_bt(rel_type)}]->() RETURN count(r)")
            if n:
                raise SystemExit(f"{target!r} already carries {n} {rel_type} "
                                 f"edge(s) — the relation layer is not "
                                 f"re-runnable over itself.")
        person_ids = {r["id"] for r in _read(
            s, f"MATCH (p:{_bt(PERSON_LABEL)}) RETURN p.id AS id")}
        org_names = {r["name"] for r in _read(
            s, f"MATCH (o:{_bt(ORG_LABEL)}) RETURN o.name AS name")}
        company_names = {r["name"] for r in _read(
            s, f"MATCH (c:{_bt(COMPANY_LABEL)}) RETURN c.name AS name")}
        print(f"  {len(person_ids)} Person, {len(org_names)} Org and "
              f"{len(company_names)} Company nodes read from {target!r}", flush=True)
        spine_before = spine_census(s)

        print("aggregating person appearances off the chunk edges …", flush=True)
        person_product = [(r["pid"], r["name"]) for r in _read(
            s, f"MATCH (p:{_bt(PERSON_LABEL)})<-[:{_bt(INVOLVES_TYPE)}"
               f"|{_bt(MENTIONS_TYPE)}]-(:Chunk)-[:{_bt(PRODUCT_TYPE)}]->"
               f"(x:{_bt(PRODUCT_LABEL)}) "
               f"RETURN DISTINCT p.id AS pid, x.name AS name ORDER BY pid, name")]
        person_channel = [(r["pid"], r["name"]) for r in _read(
            s, f"MATCH (p:{_bt(PERSON_LABEL)})<-[:{_bt(INVOLVES_TYPE)}"
               f"|{_bt(MENTIONS_TYPE)}]-(:Chunk)-[:{_bt(CHANNEL_TYPE)}]->"
               f"(x:{_bt(CHANNEL_LABEL)}) "
               f"RETURN DISTINCT p.id AS pid, x.name AS name ORDER BY pid, name")]
        product_channel = [(r["product"], r["channel"]) for r in _read(
            s, f"MATCH (c:Chunk)-[:{_bt(PRODUCT_TYPE)}]->(p:{_bt(PRODUCT_LABEL)}) "
               f"MATCH (c)-[:{_bt(CHANNEL_TYPE)}]->(x:{_bt(CHANNEL_LABEL)}) "
               f"RETURN DISTINCT p.name AS product, x.name AS channel "
               f"ORDER BY product, channel")]

    print("reading the corpus directories …", flush=True)
    directories = read_directories()
    org = org_tree_relations(read_metadata(ORG_TREE_FILE))
    manages = sorted(org["manages"])
    colleague = sorted(org["colleague"])
    in_org = membership_edges(directories["employees"], "org")
    in_company = membership_edges(directories["customers"], "company")

    endpoints = org["persons"] | {pid for pid, _ in in_org + in_company}
    orphans = sorted(pid for pid in endpoints if pid not in person_ids)
    if orphans:
        raise SystemExit(f"{len(orphans)} relation endpoint(s) carry no Person "
                         f"node: {orphans[:20]}")
    values = {value for _, value in in_org} | {value for _, value in in_company}
    unnamed = sorted(v for v in values if v not in org_names | company_names)
    if unnamed:
        raise SystemExit(f"membership value(s) carry no node: {unnamed}")
    print(f"  org tree {len(org['persons'])} persons over {len(colleague)} "
          f"same-manager pairs; every endpoint has a node", flush=True)

    census = {
        "manages": len(manages),
        "colleague": len(colleague),
        "in_org": len(in_org),
        "in_company": len(in_company),
        "appears_in_product": len(person_product),
        "appears_in_channel": len(person_channel),
        "has_channel": len(product_channel),
    }
    gate("relations", census, EXPECTED_RELATIONS)

    with drv.session(database=target) as s:

        def write_edges(rows: list, cypher: str, desc: str) -> int:
            created = 0
            bar = progress(total=len(rows), desc=desc, unit="edge")
            for i in range(0, len(rows), WRITE_BATCH):
                batch = rows[i:i + WRITE_BATCH]
                created += s.run(cypher, rows=batch).consume().counters.relationships_created
                bar.update(len(batch))
            bar.close()
            return created

        written = {
            "manages": write_edges(
                [{"a": a, "b": b, "role": role} for a, b, role in manages],
                f"UNWIND $rows AS row "
                f"MATCH (a:{_bt(PERSON_LABEL)} {{id: row.a}}) "
                f"MATCH (b:{_bt(PERSON_LABEL)} {{id: row.b}}) "
                f"CREATE (a)-[r:{_bt(MANAGES_TYPE)} {{role: row.role}}]->(b)",
                "manages"),
            "colleague": write_edges(
                [{"a": a, "b": b, "manager": m} for a, b, m in colleague],
                f"UNWIND $rows AS row "
                f"MATCH (a:{_bt(PERSON_LABEL)} {{id: row.a}}) "
                f"MATCH (b:{_bt(PERSON_LABEL)} {{id: row.b}}) "
                f"CREATE (a)-[r:{_bt(COLLEAGUE_TYPE)} {{manager: row.manager}}]->(b)",
                "colleague"),
            "in_org": write_edges(
                [{"a": pid, "b": org_name} for pid, org_name in in_org],
                f"UNWIND $rows AS row "
                f"MATCH (a:{_bt(PERSON_LABEL)} {{id: row.a}}) "
                f"MATCH (b:{_bt(ORG_LABEL)} {{name: row.b}}) "
                f"CREATE (a)-[r:{_bt(ORG_TYPE)}]->(b)",
                "in_org"),
            "in_company": write_edges(
                [{"a": pid, "b": company} for pid, company in in_company],
                f"UNWIND $rows AS row "
                f"MATCH (a:{_bt(PERSON_LABEL)} {{id: row.a}}) "
                f"MATCH (b:{_bt(COMPANY_LABEL)} {{name: row.b}}) "
                f"CREATE (a)-[r:{_bt(COMPANY_TYPE)}]->(b)",
                "in_company"),
            "appears_in_product": write_edges(
                [{"a": pid, "b": name} for pid, name in person_product],
                f"UNWIND $rows AS row "
                f"MATCH (a:{_bt(PERSON_LABEL)} {{id: row.a}}) "
                f"MATCH (b:{_bt(PRODUCT_LABEL)} {{name: row.b}}) "
                f"CREATE (a)-[r:{_bt(PERSON_PRODUCT_TYPE)}]->(b)",
                "appears_in_product"),
            "appears_in_channel": write_edges(
                [{"a": pid, "b": name} for pid, name in person_channel],
                f"UNWIND $rows AS row "
                f"MATCH (a:{_bt(PERSON_LABEL)} {{id: row.a}}) "
                f"MATCH (b:{_bt(CHANNEL_LABEL)} {{name: row.b}}) "
                f"CREATE (a)-[r:{_bt(PERSON_CHANNEL_TYPE)}]->(b)",
                "appears_in_channel"),
            "has_channel": write_edges(
                [{"a": product, "b": channel} for product, channel in product_channel],
                f"UNWIND $rows AS row "
                f"MATCH (a:{_bt(PRODUCT_LABEL)} {{name: row.a}}) "
                f"MATCH (b:{_bt(CHANNEL_LABEL)} {{name: row.b}}) "
                f"CREATE (a)-[r:{_bt(PRODUCT_CHANNEL_TYPE)}]->(b)",
                "has_channel"),
        }

    with drv.session(database=target, default_access_mode="READ") as s:
        db_census = {
            "manages": _one(s, f"MATCH ()-[r:{_bt(MANAGES_TYPE)}]->() RETURN count(r)"),
            "colleague": _one(s, f"MATCH ()-[r:{_bt(COLLEAGUE_TYPE)}]->() RETURN count(r)"),
            "in_org": _one(s, f"MATCH ()-[r:{_bt(ORG_TYPE)}]->() RETURN count(r)"),
            "in_company": _one(s, f"MATCH ()-[r:{_bt(COMPANY_TYPE)}]->() RETURN count(r)"),
            "appears_in_product": _one(
                s, f"MATCH ()-[r:{_bt(PERSON_PRODUCT_TYPE)}]->() RETURN count(r)"),
            "appears_in_channel": _one(
                s, f"MATCH ()-[r:{_bt(PERSON_CHANNEL_TYPE)}]->() RETURN count(r)"),
            "has_channel": _one(
                s, f"MATCH ()-[r:{_bt(PRODUCT_CHANNEL_TYPE)}]->() RETURN count(r)"),
        }
        person_total = _one(s, f"MATCH (p:{_bt(PERSON_LABEL)}) RETURN count(p)")
        spine_after = spine_census(s)
        def degree(pattern: str, alias: str) -> dict:
            return _read(s, f"MATCH {pattern} WITH {alias}, count(*) AS n "
                            f"RETURN min(n) AS min, max(n) AS max, "
                            f"count({alias}) AS nodes, sum(n) AS degree_sum")[0]

        degrees = {
            "manages_out": degree(
                f"(p:{_bt(PERSON_LABEL)})-[:{_bt(MANAGES_TYPE)}]->()", "p"),
            "manages_in": degree(
                f"(p:{_bt(PERSON_LABEL)})<-[:{_bt(MANAGES_TYPE)}]-()", "p"),
            "colleague_undirected": degree(
                f"(p:{_bt(PERSON_LABEL)})-[:{_bt(COLLEAGUE_TYPE)}]-()", "p"),
            "appears_in_product_out": degree(
                f"(p:{_bt(PERSON_LABEL)})-[:{_bt(PERSON_PRODUCT_TYPE)}]->()", "p"),
            "appears_in_channel_out": degree(
                f"(p:{_bt(PERSON_LABEL)})-[:{_bt(PERSON_CHANNEL_TYPE)}]->()", "p"),
            "in_org_in": degree(
                f"(o:{_bt(ORG_LABEL)})<-[:{_bt(ORG_TYPE)}]-()", "o"),
            "in_company_in": degree(
                f"(c:{_bt(COMPANY_LABEL)})<-[:{_bt(COMPANY_TYPE)}]-()", "c"),
            "has_channel_out": degree(
                f"(p:{_bt(PRODUCT_LABEL)})-[:{_bt(PRODUCT_CHANNEL_TYPE)}]->()", "p"),
        }
    gate("relation-writes", written, {k: census[k] for k in written})
    gate("relation-census", {k: db_census[k] for k in census}, census)
    gate("spine-across-relations", spine_after, spine_before)
    print(f"  relation layer written: {person_total} Person, "
          f"{sum(written.values())} entity-to-entity edges", flush=True)

    _write_step(target, "relations", {
        "timestamp": _utc_now(), "target_database": target,
        "inclusion_rules": RELATION_INCLUSION,
        "relationship_types": {"manages": MANAGES_TYPE,
                               "colleague": COLLEAGUE_TYPE,
                               "in_org": ORG_TYPE,
                               "in_company": COMPANY_TYPE,
                               "appears_in_product": PERSON_PRODUCT_TYPE,
                               "appears_in_channel": PERSON_CHANNEL_TYPE,
                               "has_channel": PRODUCT_CHANNEL_TYPE},
        "person_total": person_total,
        "spine_before": spine_before, "spine_after": spine_after,
        "census": census, "written": written, "db_census": db_census,
        "degrees": degrees,
        "elapsed_s": round(time.perf_counter() - t0, 1),
    })


def step_verify(drv, source: str, target: str) -> None:
    _guard_target(source, target)
    copy_rec = _require_step(target, "copy")
    cleanup_rec = _require_step(target, "cleanup", after=copy_rec)
    entities_rec = _require_step(target, "entities", after=cleanup_rec)
    relations_rec = _require_step(target, "relations", after=entities_rec)
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

    employee_key = ":".join(sorted((EMPLOYEE_LABEL, PERSON_LABEL)))
    customer_key = ":".join(sorted((CUSTOMER_LABEL, PERSON_LABEL)))
    before = copy_rec["source_before"]
    expected_labels = dict(before["labels"])
    expected_labels["Tag"] = cleanup_rec["post"]["tags"]
    expected_labels[employee_key] = EXPECTED_ENTITIES["employee_nodes"]
    expected_labels[customer_key] = EXPECTED_ENTITIES["customer_nodes"]
    expected_labels[ORG_LABEL] = EXPECTED_ENTITIES["org_nodes"]
    expected_labels[COMPANY_LABEL] = EXPECTED_ENTITIES["company_nodes"]
    expected_labels[PRODUCT_LABEL] = EXPECTED_ENTITIES["product_nodes"]
    expected_labels[CHANNEL_LABEL] = EXPECTED_ENTITIES["channel_nodes"]
    expected_rels = dict(before["rels"])
    expected_rels["HAS_TAG"] = cleanup_rec["post"]["has_tag_edges"]
    expected_rels[INVOLVES_TYPE] = sum(EXPECTED_ENTITIES["involves"].values())
    expected_rels[MENTIONS_TYPE] = sum(EXPECTED_ENTITIES["mentions"].values())
    expected_rels[PRODUCT_TYPE] = EXPECTED_ENTITIES["product_edges"]
    expected_rels[CHANNEL_TYPE] = EXPECTED_ENTITIES["channel_edges"]
    expected_rels[MANAGES_TYPE] = EXPECTED_RELATIONS["manages"]
    expected_rels[COLLEAGUE_TYPE] = EXPECTED_RELATIONS["colleague"]
    expected_rels[ORG_TYPE] = EXPECTED_RELATIONS["in_org"]
    expected_rels[COMPANY_TYPE] = EXPECTED_RELATIONS["in_company"]
    expected_rels[PERSON_PRODUCT_TYPE] = EXPECTED_RELATIONS["appears_in_product"]
    expected_rels[PERSON_CHANNEL_TYPE] = EXPECTED_RELATIONS["appears_in_channel"]
    expected_rels[PRODUCT_CHANNEL_TYPE] = EXPECTED_RELATIONS["has_channel"]
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

    census_sha = hashlib.sha256(json.dumps(
        {"labels": final["labels"], "rels": final["rels"],
         "removed_tags_sha256": cleanup_rec["removed_tags_sha256"]},
        sort_keys=True).encode("utf-8")).hexdigest()
    manifest_path = BUILD_DIR / target / "build_manifest.json"
    previous = archive_manifest(manifest_path)
    manifest_path.write_text(json.dumps({
        "target_database": target,
        "source_database": source,
        "timestamp": _utc_now(),
        "graph_version": GRAPH_VERSION,
        "graph_census_sha256": census_sha,
        "previous_manifest": previous,
        "authority": [DESIGN_DOC, ENTITY_DESIGN_DOC],
        "execution_defaults": EXECUTION_DEFAULTS,
        "entity_inclusion": ENTITY_INCLUSION,
        "relation_inclusion": RELATION_INCLUSION,
        "databases_on_dbms": sorted(r["name"] for r in databases),
        "steps": {
            "copy": {k: v for k, v in copy_rec.items() if k != "source_before"},
            "cleanup": {k: v for k, v in cleanup_rec.items()
                        if k != "removed_tags"},
            "entities": entities_rec,
            "relations": relations_rec,
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
    print(f"build manifest written last: {manifest_path} "
          f"({GRAPH_VERSION}, census {census_sha[:12]})", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description='Build a versioned copy of a herb graph database: faithful copy, tag cleanup,')
    parser.add_argument("step", choices=("copy", "cleanup", "entities",
                                         "relations", "verify"))
    parser.add_argument("--source-db", default=SOURCE_DATABASE,
                        help="database the copy reads (read-only throughout)")
    parser.add_argument("--target-db", default=TARGET_DATABASE,
                        help="database the build writes (never a protected name)")
    parser.add_argument("--recreate", action="store_true",
                        help="copy only: drop an existing target and rebuild it")
    parser.add_argument("--rebuild", action="store_true",
                        help="entities only: drop the existing entity and "
                             "relation layer first, spine proved unchanged")
    args = parser.parse_args()

    drv = _driver()
    try:
        if args.step == "copy":
            step_copy(drv, args.source_db, args.target_db, args.recreate)
        elif args.step == "cleanup":
            step_cleanup(drv, args.source_db, args.target_db)
        elif args.step == "entities":
            step_entities(drv, args.source_db, args.target_db, args.rebuild)
        elif args.step == "relations":
            step_relations(drv, args.source_db, args.target_db)
        else:
            step_verify(drv, args.source_db, args.target_db)
    finally:
        drv.close()


if __name__ == "__main__":
    main()
