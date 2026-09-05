from __future__ import annotations

if __name__ == "__main__":
    print("build_corpus_graph: plan / build — loading neo4j …", flush=True)

import argparse
import collections
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from graph.db import DATASET_ID, EXCLUDED_SECTIONS, _driver
from harness.progress import progress


TARGET_DATABASE = "herb-eval-volmax"

SOURCE_DATABASE = "herb-eval-v2"

PROTECTED_DATABASES = ("herb", "herb-eval", "herb-eval-v2", "neo4j", "system")

CARRIED_LABELS = ("Chunk", "Tag", "File")
CARRIED_TYPES = ("HAS_TAG", "HAS_CHUNK")

CARRIED_KEYS = {"Chunk": "chunk_id", "Tag": "name", "File": "file_id"}

COPY_BATCH = 200

TEMP_INDEX_PREFIX = "tmp_copy_"

GRAPH_VERSION = "corpus-architecture+registry+chunk-attachment"

AUTHORITY = "docs/canon/GRAPH_SHAPE_MAP.md"

CORPUS = Path(__file__).resolve().parent.parent.parent / "data" / "corpus"

BUILD_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "graph_build"

FORBIDDEN_KEYS = ("team", "customers", "answerable_questions",
                  "unanswerable_questions")

ARCHITECTURE = {
    "Salesforce__HERB": {
        "node": "Product",
        "directory": "products",
        "branches": {
            "slack": {
                "node": "slack",
                "ids": ("id",),
                "branches": {
                    "Channel": {"node": "Channel", "ids": ("channelID",)},
                    "Message": {
                        "node": "Message",
                        "branches": {
                            "User": {"node": "User",
                                     "ids": ("userId", "utterranceID")},
                        },
                    },
                },
            },
            "prs": {
                "node": "prs",
                "ids": ("id", "number"),
                "branches": {
                    "user": {"node": "user", "ids": ("login",)},
                    "reviews": {
                        "node": "reviews",
                        "branches": {
                            "user": {"node": "user", "ids": ("login",)},
                        },
                    },
                },
            },
            "documents": {"node": "documents", "ids": ("id", "author")},
            "meeting_transcripts": {"node": "meeting_transcripts",
                                    "ids": ("id", "participants")},
            "meeting_chats": {"node": "meeting_chats", "ids": ("id",)},
            "urls": {"node": "urls", "ids": ("id",)},
        },
    },
}

REGISTRIES = {
    "Salesforce__HERB": (
        {"file": "metadata/employee.json", "node": "Employee",
         "values": ("role", "org", "location"), "ids": ("employee_id",)},
        {"file": "metadata/customers_data.json", "node": "Customer",
         "values": ("role", "company"), "ids": ("id",)},
    ),
}

NESTINGS = {
    "Salesforce__HERB": (
        {"file": "metadata/salesforce_team.json", "key": "employee_id",
         "into": "Employee", "value": "role"},
    ),
}

ENTITY_LABEL = "Entity"

ENTITY_TYPE = "HAS_ENTITY"
CHUNK_TYPE = "HAS_CHUNK"

ENTITY_PROPERTIES = ("entity_id", "rel_path", "index")
ENTITY_ID_FORMAT = "ent_{:05d}"

POSITION_KEY = "path"
VALUE_KEY = "value"
ENTITY_KEY = "entity_id"

PROTECTED_LABELS = CARRIED_LABELS + (ENTITY_LABEL,)
PROTECTED_TYPES = CARRIED_TYPES + (ENTITY_TYPE,)

IN_PROGRESS_VERSION = "build in progress — database is mid-rebuild"

JSON_SCALARS = (str, int, float, bool, type(None))

CHUNK_PROPERTIES = ("chunk_id", "section", "metadata_section", "product",
                    "locator_json", "start_offset", "end_offset", "item_index",
                    "msg_index_start", "msg_index_end", "part_index",
                    "doc_field", "subsection")

EDGE_ATTRIBUTES = ("start_offset", "end_offset", "item_index", "msg_index_start",
                   "msg_index_end", "part_index", "doc_field", "subsection")

SHAPE_RULES = {
    "position": "one node per position of the source's own nesting, labelled as "
                "the source names it; a record is never a node",
    "branch": "one edge per branch, named with the field name the source wrote — "
              "never an invented verb",
    "value": "a directory's declared value set stands as nodes: one node per "
             "value across the corpus, reached by an edge named after the field, "
             "from the population declaring it and from every entry declaring "
             "it. A field a record of the corpus tree carries — a status, a "
             "type, a date — stays in the file",
    "registry": "a file whose records the source keys is a population: one node "
                "for the population, one node per entry",
    "entity_id": "an entry carries a synthetic id minted by this build and a "
                 "pointer into the corpus — the file and the i-th member of its "
                 "own container, a list element or one key/value pair of an "
                 "object in its own order — and nothing else; the source's own "
                 "key never enters the graph",
    "nesting": "a file that keys no population of its own relates entries a "
               "registry already declares: an edge between the two entries and "
               "an edge between the values they declare, both named with the "
               "branch the source wrote",
    "chunk": "a chunk attaches to the position it was read from, its edge "
             "carrying the ids of the records it covers and its own offsets and "
             "indices; a chunk naming an oracle section attaches to nothing",
    "carried": "the chunks, the tags, the files and the edges between them cross "
               "from the source database untouched and survive the purge",
    "excluded": "the forbidden keys are dropped from every record the walk reads",
}

WRITE_BATCH = 1000
DELETE_BATCH = 500
INDEX_WAIT_S = 600.0


def strip_forbidden(node, dropped: collections.Counter):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key in FORBIDDEN_KEYS:
                dropped[key] += 1
                continue
            out[key] = strip_forbidden(value, dropped)
        return out
    if isinstance(node, list):
        return [strip_forbidden(e, dropped) for e in node]
    return node


def read_corpus(root: Path) -> dict:
    files = sorted(p for p in root.rglob("*.json") if p.is_file())
    if not files:
        raise SystemExit(f"no json under {root} — nothing to read.")
    dropped = collections.Counter()
    out, stems = {}, {}
    bar = progress(total=len(files), desc="read corpus", unit="file")
    for path in files:
        raw = path.read_bytes()
        key = path.relative_to(root).as_posix()
        if path.stem in stems:
            raise SystemExit(f"two corpus files share the stem {path.stem!r} "
                             f"({stems[path.stem]} and {key}) — a locator naming "
                             f"it is ambiguous.")
        stems[path.stem] = key
        out[key] = {"key": key, "stem": path.stem,
                    "rel_path": path.relative_to(CORPUS).as_posix(),
                    "data": strip_forbidden(json.loads(raw.decode("utf-8")), dropped),
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest()}
        bar.update(1)
    bar.close()
    return {"files": out, "by_stem": stems, "forbidden_dropped": dict(dropped)}


def declared_for(dataset: str) -> tuple:
    architecture = ARCHITECTURE.get(dataset)
    if architecture is None:
        raise SystemExit(f"no architecture is declared for {dataset!r} — declare "
                         f"its positions in ARCHITECTURE before building it.")
    return architecture, REGISTRIES.get(dataset, ()), NESTINGS.get(dataset, ())


def declared_positions(spec: dict, path: str, parent, branch, out: list) -> None:
    out.append({"path": path, "label": spec["node"], "parent": parent,
                "branch": branch, "ids": tuple(spec.get("ids", ()))})
    for field, child in spec.get("branches", {}).items():
        declared_positions(child, f"{path}.{field}", path, field, out)


def walk_position(record, path: str, spec: dict, state: dict) -> None:
    if not isinstance(record, dict):
        raise SystemExit(f"{path}: a record is a {type(record).__name__}, "
                         f"not an object")
    state["records"][path] += 1
    branches = spec.get("branches", {})
    for field, value in record.items():
        if isinstance(value, dict):
            child = branches.get(field)
            if child is None:
                raise SystemExit(f"{path}.{field} nests an object no position is "
                                 f"declared for — declare it or the shape is not "
                                 f"the source's.")
            walk_position(value, f"{path}.{field}", child, state)
        elif isinstance(value, list):
            nested = [e for e in value if isinstance(e, dict)]
            if not nested:
                continue
            child = branches.get(field)
            if child is None:
                raise SystemExit(f"{path}.{field} nests {len(nested)} record(s) "
                                 f"no position is declared for — declare it or "
                                 f"the shape is not the source's.")
            for element in nested:
                walk_position(element, f"{path}.{field}", child, state)


def derive_architecture(architecture: dict, corpus: dict) -> dict:
    positions = []
    declared_positions(architecture, architecture["node"], None, None, positions)
    directory = architecture["directory"]
    members = sorted(key for key in corpus["files"]
                     if key.startswith(f"{directory}/"))
    if not members:
        raise SystemExit(f"the declaration names {directory!r} as the position "
                         f"{architecture['node']!r} and the corpus carries no "
                         f"file under it.")
    state = {"records": collections.Counter()}
    bar = progress(total=len(members), desc="walk corpus", unit="file")
    for key in members:
        walk_position(corpus["files"][key]["data"], architecture["node"],
                      architecture, state)
        bar.update(1)
    bar.close()

    empty = [p["path"] for p in positions if not state["records"][p["path"]]]
    if empty:
        raise SystemExit(f"the declaration names position(s) the corpus never "
                         f"fills: {empty}")
    for position in positions:
        position["records"] = state["records"][position["path"]]
    branch_edges = [{"type": p["branch"], "from_path": p["parent"],
                     "to_path": p["path"], "records": p["records"]}
                    for p in positions if p["parent"] is not None]
    return {"positions": positions, "files": members,
            "branch_edges": branch_edges}


def registry_entries(doc, file_key: str) -> list:
    if isinstance(doc, list):
        entries = [(i, None, entry) for i, entry in enumerate(doc)]
    elif isinstance(doc, dict):
        entries = [(i, key, entry)
                   for i, (key, entry) in enumerate(doc.items())]
    else:
        raise SystemExit(f"{file_key} holds a {type(doc).__name__} at its root, "
                         f"which no ordinal addresses.")
    for _, _, entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit(f"{file_key}: an entry is a {type(entry).__name__}, "
                             f"not an object")
    return entries


def entry_key(entry: dict, container_key, spec: dict, file_key: str) -> str:
    if container_key is not None:
        return container_key
    for field in spec["ids"]:
        value = entry.get(field)
        if isinstance(value, str) and value:
            return value
    raise SystemExit(f"{file_key}: an entry carries none of the identifier "
                     f"field(s) {spec['ids']} the declaration names.")


def derive_registry(registries: tuple, nestings: tuple, corpus: dict) -> dict:
    positions, entities, keys = [], [], {}
    value_edges, entity_value_edges = [], []
    declared = collections.defaultdict(collections.Counter)
    minted = 0
    for spec in registries:
        record = corpus["files"].get(spec["file"])
        if record is None:
            raise SystemExit(f"the declaration names the registry {spec['file']!r}, "
                             f"which the corpus does not carry.")
        entries = registry_entries(record["data"], spec["file"])
        positions.append({"path": spec["node"], "label": spec["node"],
                          "parent": None, "branch": None,
                          "ids": tuple(spec["ids"]), "records": len(entries)})
        bar = progress(total=len(entries), desc=f"read {record['stem']}",
                       unit="entry")
        for ordinal, container_key, entry in entries:
            minted += 1
            entity_id = ENTITY_ID_FORMAT.format(minted)
            source_key = entry_key(entry, container_key, spec, spec["file"])
            if source_key in keys:
                raise SystemExit(f"{spec['file']}: two entries are known by "
                                 f"one key.")
            keys[source_key] = entity_id
            entities.append({"entity_id": entity_id,
                             "rel_path": record["rel_path"], "index": ordinal,
                             "population": spec["node"]})
            for field in spec["values"]:
                value = entry.get(field)
                if not isinstance(value, str) or not value:
                    raise SystemExit(f"{spec['file']}: an entry declares "
                                     f"{field!r} as {value!r} — a value set the "
                                     f"source does not carry on every entry is "
                                     f"not one.")
                declared[(spec["node"], field)][value] += 1
                entity_value_edges.append({"type": field, "entity_id": entity_id,
                                           "field": field, "value": value})
            bar.update(1)
        bar.close()

    for (path, field), counted in sorted(declared.items()):
        for value, count in sorted(counted.items()):
            value_edges.append({"type": field, "from_path": path, "field": field,
                                "value": value, "records": count})

    relations, chain, chain_seen = [], [], set()
    for spec in nestings:
        record = corpus["files"].get(spec["file"])
        if record is None:
            raise SystemExit(f"the declaration names the nesting {spec['file']!r}, "
                             f"which the corpus does not carry.")
        entries = registry_entries(record["data"], spec["file"])
        bar = progress(total=len(entries), desc=f"read {record['stem']}",
                       unit="entry")
        for _, _, entry in entries:
            walk_nesting(entry, spec, keys, relations, chain, chain_seen)
            bar.update(1)
        bar.close()

    return {"positions": positions, "entities": entities,
            "value_edges": value_edges,
            "entity_value_edges": entity_value_edges,
            "relations": relations, "chain": chain,
            "populations": {spec["node"]: spec["file"] for spec in registries},
            "source_keys": len(keys)}


def walk_nesting(entry: dict, spec: dict, keys: dict, relations: list,
                 chain: list, seen: set) -> None:
    key = entry.get(spec["key"])
    if not isinstance(key, str) or key not in keys:
        raise SystemExit(f"{spec['file']}: a record names {spec['key']}={key!r}, "
                         f"which no entry of {spec['into']!r} carries.")
    for field, value in entry.items():
        if not isinstance(value, list):
            continue
        nested = [e for e in value if isinstance(e, dict)]
        if not nested:
            continue
        for element in nested:
            child = element.get(spec["key"])
            if not isinstance(child, str) or child not in keys:
                raise SystemExit(f"{spec['file']}: a record nested under {field!r} "
                                 f"names {spec['key']}={child!r}, which no entry "
                                 f"of {spec['into']!r} carries.")
            relations.append({"type": field, "from_id": keys[key],
                              "to_id": keys[child]})
            pair = (entry.get(spec["value"]), field, element.get(spec["value"]))
            if not all(isinstance(part, str) and part for part in pair):
                raise SystemExit(f"{spec['file']}: a nesting under {field!r} "
                                 f"relates {pair[0]!r} to {pair[2]!r} — the "
                                 f"declared value field {spec['value']!r} is not "
                                 f"carried on both sides.")
            if pair not in seen:
                seen.add(pair)
                chain.append({"type": field, "field": spec["value"],
                              "from_value": pair[0], "value": pair[2]})
            walk_nesting(element, spec, keys, relations, chain, seen)


def value_nodes(registry: dict) -> list:
    held = collections.defaultdict(collections.Counter)
    for edge in registry["value_edges"]:
        held[edge["field"]][edge["value"]] += edge["records"]
    for edge in registry["chain"]:
        held[edge["field"]].setdefault(edge["from_value"], 0)
        held[edge["field"]].setdefault(edge["value"], 0)
    return [{"field": field, "value": value, "records": count}
            for field in sorted(held) for value, count in sorted(held[field].items())]


def resolve_path(record, field_path: str, out: list) -> None:
    head, _, rest = field_path.partition(".")
    if isinstance(record, list):
        for element in record:
            resolve_path(element, field_path, out)
        return
    if not isinstance(record, dict) or head not in record:
        return
    value = record[head]
    if rest:
        resolve_path(value, rest, out)
    elif isinstance(value, list):
        out.extend(str(v) for v in value if isinstance(v, (str, int)))
    elif isinstance(value, (str, int)):
        out.append(str(value))


def ids_below(positions: list, path: str) -> list:
    out = []
    for position in positions:
        if position["path"] != path and not position["path"].startswith(f"{path}."):
            continue
        prefix = position["path"][len(path) + 1:]
        out.extend(f"{prefix}.{field}" if prefix else field
                   for field in position["ids"])
    return out


def nesting_ids(record, key: str, out: list) -> None:
    if isinstance(record, list):
        for element in record:
            nesting_ids(element, key, out)
        return
    if not isinstance(record, dict):
        return
    value = record.get(key)
    if isinstance(value, str):
        out.append(value)
    for nested in record.values():
        if isinstance(nested, (dict, list)):
            nesting_ids(nested, key, out)


def locator_indices(locator: dict, row: dict) -> list:
    if "indices" in locator:
        return locator["indices"]
    if "index" in locator:
        return [locator["index"]]
    raise SystemExit(f"chunk {row['chunk_id']} carries a locator naming no place "
                     f"in its container (keys: {sorted(locator)}).")


def chunk_records(row: dict, locator: dict, corpus: dict, shape: dict) -> tuple:
    section = locator.get("section")
    if section:
        if section in EXCLUDED_SECTIONS:
            return None, [], False
        path = f"{shape['root']}.{section}"
        if path not in shape["by_path"]:
            raise SystemExit(f"chunk {row['chunk_id']} names section {section!r}, "
                             f"which is no position of the declared shape.")
        product = locator.get("product")
        key = corpus["by_stem"].get(product)
        if key is None or key not in shape["members"]:
            raise SystemExit(f"chunk {row['chunk_id']} names product {product!r}, "
                             f"which no file of the architecture carries.")
        doc = corpus["files"][key]["data"]
        array = doc.get(section)
        if array is None:
            raise SystemExit(f"chunk {row['chunk_id']} names section {section!r}, "
                             f"absent from {key}.")
        indices = locator_indices(locator, row)
        if max(indices) >= len(array):
            raise SystemExit(f"chunk {row['chunk_id']} points at "
                             f"{key}/{section}[{max(indices)}], which holds "
                             f"{len(array)} record(s).")
        return path, [array[i] for i in indices], False

    named = locator.get("metadata") or row["metadata_section"]
    if not named:
        raise SystemExit(f"chunk {row['chunk_id']} names neither a section nor a "
                         f"metadata file (locator keys: {sorted(locator)}).")
    key = corpus["by_stem"].get(named)
    if key is None:
        raise SystemExit(f"chunk {row['chunk_id']} names metadata {named!r}, "
                         f"which the corpus does not carry.")
    path = shape["metadata_positions"].get(key)
    if path is None:
        raise SystemExit(f"chunk {row['chunk_id']} names metadata {named!r}, for "
                         f"which no population is declared.")
    doc = corpus["files"][key]["data"]
    records = [_nth(doc, i, key) for i in locator_indices(locator, row)]
    if locator.get("subsection"):
        records = [record[locator["subsection"]] for record in records]
    return path, records, key in shape["nesting_files"]


def _nth(doc, index: int, key: str):
    if isinstance(doc, list):
        if index >= len(doc):
            raise SystemExit(f"{key} holds {len(doc)} entries; a locator names "
                             f"{index}.")
        return doc[index]
    items = list(doc.items())
    if index >= len(items):
        raise SystemExit(f"{key} holds {len(items)} entries; a locator names "
                         f"{index}.")
    return items[index][1]


def chunk_edge_props(row: dict, path: str, records: list, nested: bool,
                     shape: dict) -> dict:
    props = {}
    for name in EDGE_ATTRIBUTES:
        if row[name] is not None:
            props[name] = row[name]
    found = collections.defaultdict(set)
    if nested:
        key = shape["nesting_key"][path]
        for record in records:
            values = []
            nesting_ids(record, key, values)
            found[key].update(values)
    else:
        for field_path in shape["ids"][path]:
            for record in records:
                values = []
                resolve_path(record, field_path, values)
                found[field_path].update(values)
    for name, values in found.items():
        if name in props:
            raise SystemExit(f"chunk {row['chunk_id']}: the identifier {name!r} "
                             f"and a chunk attribute both name one edge property.")
        if values:
            props[name] = sorted(values)
    return props


def map_chunks(rows: list, corpus: dict, shape: dict) -> dict:
    edges, unplaced = [], []
    per_position = collections.Counter()
    widest = 0
    bar = progress(total=len(rows), desc="map chunks", unit="chunk")
    for row in rows:
        locator = json.loads(row["locator_json"])
        path, records, nested = chunk_records(row, locator, corpus, shape)
        if path is None:
            unplaced.append(row["chunk_id"])
            bar.update(1)
            continue
        props = chunk_edge_props(row, path, records, nested, shape)
        widest = max([widest] + [len(v) for v in props.values()
                                 if isinstance(v, list)])
        edges.append({"path": path, "chunk_id": row["chunk_id"], "props": props})
        per_position[path] += 1
        bar.update(1)
    bar.close()
    return {"chunk_edges": edges, "unplaced": unplaced,
            "chunks_per_position": dict(sorted(per_position.items())),
            "widest_edge_list": widest}


def assemble(architecture: dict, registry: dict, declared: dict) -> dict:
    positions = architecture["positions"] + registry["positions"]
    by_path = {position["path"]: position for position in positions}
    if len(by_path) != len(positions):
        raise SystemExit("two positions of the declared shape share one path.")

    values = value_nodes(registry)
    labels = {position["label"] for position in positions}
    labels |= {value["field"] for value in values} | {ENTITY_LABEL}
    clash = sorted(labels & (set(PROTECTED_LABELS) - {ENTITY_LABEL}))
    if clash:
        raise SystemExit(f"the declaration mints {clash}, which the carried layer "
                         f"also uses as a label. A node minted under one would be "
                         f"protected from the purge and the database could not be "
                         f"rebuilt.")
    types = {edge["type"] for edge in architecture["branch_edges"]}
    types |= {edge["type"] for edge in registry["value_edges"]}
    types |= {edge["type"] for edge in registry["relations"]}
    types |= {edge["type"] for edge in registry["chain"]}
    clash = sorted(types & set(PROTECTED_TYPES))
    if clash:
        raise SystemExit(f"the declaration mints the relationship type(s) {clash}, "
                         f"which the carried layer already carries.")
    joined = sorted(name for name in labels | types if ":" in name)
    if joined:
        raise SystemExit(f"the declaration mints {joined} as a label or type; a "
                         f"name carrying ':' cannot be told apart from a joined "
                         f"label set in a census.")

    declared_values = {(value["field"], value["value"]) for value in values}
    edges = []
    for edge in architecture["branch_edges"]:
        edges.append(_edge(edge["type"], by_path[edge["from_path"]]["label"],
                           POSITION_KEY, edge["from_path"],
                           by_path[edge["to_path"]]["label"], POSITION_KEY,
                           edge["to_path"], {"records": edge["records"]}))
    for edge in registry["value_edges"]:
        _require_value(declared_values, edge["field"], edge["value"])
        edges.append(_edge(edge["type"], by_path[edge["from_path"]]["label"],
                           POSITION_KEY, edge["from_path"], edge["field"],
                           VALUE_KEY, edge["value"], {"records": edge["records"]}))
    for edge in registry["chain"]:
        _require_value(declared_values, edge["field"], edge["from_value"])
        _require_value(declared_values, edge["field"], edge["value"])
        edges.append(_edge(edge["type"], edge["field"], VALUE_KEY,
                           edge["from_value"], edge["field"], VALUE_KEY,
                           edge["value"], {}))
    for entity in registry["entities"]:
        edges.append(_edge(ENTITY_TYPE, entity["population"], POSITION_KEY,
                           entity["population"], ENTITY_LABEL, ENTITY_KEY,
                           entity["entity_id"], {}))
    for edge in registry["entity_value_edges"]:
        _require_value(declared_values, edge["field"], edge["value"])
        edges.append(_edge(edge["type"], ENTITY_LABEL, ENTITY_KEY,
                           edge["entity_id"], edge["field"], VALUE_KEY,
                           edge["value"], {}))
    for edge in registry["relations"]:
        edges.append(_edge(edge["type"], ENTITY_LABEL, ENTITY_KEY,
                           edge["from_id"], ENTITY_LABEL, ENTITY_KEY,
                           edge["to_id"], {}))

    root = architecture["positions"][0]["path"]
    metadata_positions, nesting_files, nesting_key = {}, set(), {}
    for node, file_key in registry["populations"].items():
        metadata_positions[file_key] = node
    for spec in declared["nestings"]:
        metadata_positions[spec["file"]] = spec["into"]
        nesting_files.add(spec["file"])
        nesting_key[spec["into"]] = spec["key"]
    return {"positions": positions, "values": values,
            "entities": registry["entities"], "edges": edges,
            "by_path": by_path, "root": root,
            "members": set(architecture["files"]),
            "metadata_positions": metadata_positions,
            "nesting_files": nesting_files, "nesting_key": nesting_key,
            "ids": {path: ids_below(positions, path) for path in by_path}}


def _edge(etype: str, from_label: str, from_key: str, from_id: str,
          to_label: str, to_key: str, to_id: str, props: dict) -> dict:
    return {"type": etype, "from_label": from_label, "from_key": from_key,
            "from_id": from_id, "to_label": to_label, "to_key": to_key,
            "to_id": to_id, "props": props}


def _require_value(declared: set, field: str, value: str) -> None:
    if (field, value) not in declared:
        raise SystemExit(f"an edge names {field}={value!r}, which the corpus's "
                         f"own value sets do not carry.")


def derive_shape(corpus: dict, dataset: str) -> dict:
    architecture_spec, registries, nestings = declared_for(dataset)
    architecture = derive_architecture(architecture_spec, corpus)
    registry = derive_registry(registries, nestings, corpus)
    shape = assemble(architecture, registry,
                     {"registries": registries, "nestings": nestings})
    shape["architecture"] = architecture
    shape["registry"] = registry
    return shape


_DB_NAME = re.compile(r"^[a-z][a-z0-9.-]{2,62}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bt(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _guard_target(source: str, target: str) -> None:
    for name in (source, target):
        if not _DB_NAME.fullmatch(name):
            raise SystemExit(f"database name out of form: {name!r}")
    if target in PROTECTED_DATABASES:
        raise SystemExit(f"{target!r} is protected — it is never a write target.")
    if source == "herb":
        raise SystemExit("'herb' is the oracle-contaminated pilot database — "
                         "it is never read, not even as a copy source.")
    if source == target:
        raise SystemExit("target and source are the same database.")


def _read(s, cypher: str, **params) -> list:
    return [dict(r) for r in s.run(cypher, **params)]


def _one(s, cypher: str, **params):
    return s.run(cypher, **params).single()[0]


def _sha(values: list) -> str:
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def _write_step(target: str, step: str, payload: dict) -> Path:
    path = BUILD_DIR / target / f"step_{step}.json"
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
            "graph_census_sha256": prior.get("graph_census_sha256"),
            "source_database": prior.get("source_database"),
            "removed_tags_sha256": prior.get("removed_tags_sha256")}


def mark_in_progress(manifest_path: Path, target: str, previous) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({
        "target_database": target,
        "timestamp": _utc_now(),
        "graph_version": IN_PROGRESS_VERSION,
        "graph_census_sha256": None,
        "source_database": previous["source_database"] if previous else None,
        "removed_tags_sha256": previous["removed_tags_sha256"] if previous else None,
        "previous_manifest": previous,
        "complete": False,
    }, indent=1, sort_keys=True), encoding="utf-8")
    print(f"  {manifest_path.name} now reads {IN_PROGRESS_VERSION!r} and stays "
          f"that way until this build finishes", flush=True)


def is_structure(labels: list) -> bool:
    return not any(label in CARRIED_LABELS for label in labels)


def structure_census(census_labels: dict) -> dict:
    return {key: n for key, n in sorted(census_labels.items())
            if is_structure(key.split(":"))}


def label_total(census_labels: dict, label: str) -> int:
    return sum(n for key, n in census_labels.items() if label in key.split(":"))


def carried_census(s) -> dict:
    chunk_ids = [r["id"] for r in _read(
        s, "MATCH (c:Chunk) RETURN c.chunk_id AS id ORDER BY id")]
    tag_names = [r["name"] for r in _read(
        s, "MATCH (t:Tag) RETURN t.name AS name ORDER BY name")]
    file_ids = [r["id"] for r in _read(
        s, "MATCH (f:File) RETURN f.file_id AS id ORDER BY id")]
    return {
        "chunks": len(chunk_ids),
        "tags": len(tag_names),
        "files": len(file_ids),
        "has_tag": _one(s, "MATCH (:Chunk)-[r:HAS_TAG]->(:Tag) RETURN count(r)"),
        "file_has_chunk": _one(s, "MATCH (:File)-[r:HAS_CHUNK]->(:Chunk) "
                                  "RETURN count(r)"),
        "desc_emb": _one(s, "MATCH (c:Chunk) WHERE c.desc_emb IS NOT NULL "
                            "RETURN count(c)"),
        "tag_emb": _one(s, "MATCH (t:Tag) WHERE t.emb IS NOT NULL "
                           "RETURN count(t)"),
        "chunk_ids_sha256": _sha(chunk_ids),
        "tag_names_sha256": _sha(tag_names),
        "file_ids_sha256": _sha(file_ids),
    }


def graph_census(s) -> dict:
    labels = {":".join(sorted(r["ls"])): r["n"] for r in _read(
        s, "MATCH (n) RETURN labels(n) AS ls, count(*) AS n")}
    rels = {r["t"]: r["n"] for r in _read(
        s, "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n")}
    return {"labels": dict(sorted(labels.items())),
            "rels": dict(sorted(rels.items()))}


def read_chunks(s) -> list:
    fields = ", ".join(f"c.{p} AS {p}" for p in CHUNK_PROPERTIES)
    return _read(s, f"MATCH (c:Chunk) RETURN {fields} ORDER BY chunk_id")


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


def schema_rows(s) -> tuple:
    wanted = set(CARRIED_LABELS) | set(CARRIED_TYPES)
    constraints = [c for c in _read(
        s, "SHOW CONSTRAINTS YIELD name, type, entityType, labelsOrTypes, "
           "properties RETURN *") if wanted & set(c["labelsOrTypes"] or ())]
    owned = {c["name"] for c in constraints}
    indexes = [r for r in _read(
        s, "SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, "
           "properties, options RETURN *")
        if r["type"] != "LOOKUP" and r["name"] not in owned
        and wanted & set(r["labelsOrTypes"] or ())]
    return constraints, indexes


def _constraint_cypher(c: dict) -> str:
    if c["entityType"] != "NODE":
        raise SystemExit(f"constraint {c['name']} is over a "
                         f"{c['entityType']}, which this copy does not cover.")
    label = _bt(c["labelsOrTypes"][0])
    props = ", ".join(f"n.{_bt(p)}" for p in c["properties"])
    if c["type"] == "NODE_PROPERTY_UNIQUENESS":
        require = (f"({props}) IS UNIQUE" if len(c["properties"]) > 1
                   else f"{props} IS UNIQUE")
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
    options = (f" OPTIONS {{indexConfig: {{{config_literal}}}}}"
               if config_literal else "")
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


def database_state(drv, source: str, target: str) -> dict:
    with drv.session(database="system") as s:
        names = sorted(r["name"] for r in
                       _read(s, "SHOW DATABASES YIELD name RETURN name"))
    if source not in names:
        raise SystemExit(f"source database {source!r} does not exist — "
                         f"the DBMS carries {names}.")
    exists = target in names
    chunks = 0
    if exists:
        with drv.session(database=target, default_access_mode="READ") as s:
            chunks = _one(s, "MATCH (c:Chunk) RETURN count(c)")
    return {"source": source, "target": target, "databases": names,
            "target_exists": exists, "target_chunks": chunks}


def source_lineage(source: str) -> dict | None:
    path = BUILD_DIR / source / "build_manifest.json"
    if not path.is_file():
        return None
    prior = json.loads(path.read_text(encoding="utf-8"))
    return {"database": source, "timestamp": prior.get("timestamp"),
            "graph_version": prior.get("graph_version"),
            "graph_census_sha256": prior.get("graph_census_sha256"),
            "removed_tags_sha256": prior.get("removed_tags_sha256"),
            "source_database": prior.get("source_database")}


def drop_temp_indexes(ws) -> list:
    names = [r["name"] for r in _read(ws, "SHOW INDEXES YIELD name RETURN name")
             if r["name"].startswith(TEMP_INDEX_PREFIX)]
    for name in names:
        ws.run(f"DROP INDEX {_bt(name)} IF EXISTS").consume()
    return names


def index_coverage(s, indexes: list) -> dict:
    out = {}
    for index in indexes:
        if index["entityType"] != "NODE":
            continue
        label = index["labelsOrTypes"][0]
        clause = " OR ".join(f"n.{_bt(p)} IS NOT NULL" for p in index["properties"])
        out[index["name"]] = _one(
            s, f"MATCH (n:{_bt(label)}) WHERE {clause} RETURN count(n)")
    return out


def source_layer(drv, source: str) -> dict:
    keep = list(CARRIED_LABELS)
    with drv.session(database=source, default_access_mode="READ") as s:
        constraints, indexes = schema_rows(s)
        counts = {label: _one(s, f"MATCH (n:{_bt(label)}) RETURN count(n)")
                  for label in CARRIED_LABELS}
        for label, key in sorted(CARRIED_KEYS.items()):
            distinct = _one(s, f"MATCH (n:{_bt(label)}) "
                               f"RETURN count(DISTINCT n.{_bt(key)})")
            if distinct != counts[label]:
                raise SystemExit(
                    f"{label}.{key} identifies {distinct} of {counts[label]} "
                    f"nodes in {source!r} — the copy wires edges back up by that "
                    f"property and cannot proceed without it being unique.")
        both = _one(s, "MATCH (n) WHERE size([l IN labels(n) WHERE l IN $keep]) > 1 "
                       "RETURN count(n)", keep=keep)
        if both:
            raise SystemExit(f"{both} node(s) in {source!r} carry more than one "
                             f"carried label — the copy addresses a node by the "
                             f"key of its label and cannot choose between two.")
        n_rels = _one(s, "MATCH (a)-[r]->(b) WHERE any(l IN labels(a) WHERE l IN $keep) "
                         "AND any(l IN labels(b) WHERE l IN $keep) "
                         "RETURN count(r)", keep=keep)
        coverage = index_coverage(s, indexes)
    return {"counts": counts, "edges": n_rels, "constraints": constraints,
            "indexes": indexes, "index_coverage": coverage}


def print_source_layer(survey: dict, source: str) -> None:
    print(f"  {source!r} holds {survey['counts']}, {survey['edges']} edge(s) "
          f"between them, {len(survey['constraints'])} constraint(s), "
          f"{len(survey['indexes'])} index(es)", flush=True)
    for constraint in survey["constraints"]:
        print(f"    constraint {constraint['name']}: {constraint['type']} on "
              f"{constraint['labelsOrTypes']}{constraint['properties']}", flush=True)
    for index in survey["indexes"]:
        covered = survey["index_coverage"].get(index["name"])
        held = "" if covered is None else f", covers {covered} node(s)"
        print(f"    index {index['name']}: {index['type']} on "
              f"{index['labelsOrTypes']}{index['properties']}{held}", flush=True)


def copy_carried_layer(drv, source: str, target: str, survey: dict) -> dict:
    counts, n_rels = survey["counts"], survey["edges"]
    print(f"copying the carried layer {source!r} -> {target!r} …", flush=True)
    written_rels = 0
    try:
        for label, key in sorted(CARRIED_KEYS.items()):
            with drv.session(database=target) as ws:
                ws.run(f"CREATE INDEX "
                       f"{_bt(TEMP_INDEX_PREFIX + label.lower())} IF NOT EXISTS "
                       f"FOR (n:{_bt(label)}) ON (n.{_bt(key)})").consume()
            with drv.session(database=source, default_access_mode="READ") as rs, \
                    drv.session(database=target) as ws:
                bar = progress(total=counts[label], desc=f"copy {label.lower()}s",
                               unit="node")
                batch = []
                for record in rs.run(f"MATCH (n:{_bt(label)}) "
                                     f"RETURN properties(n) AS props"):
                    batch.append(record["props"])
                    if len(batch) >= COPY_BATCH:
                        ws.run(f"UNWIND $rows AS row CREATE (n:{_bt(label)}) "
                               f"SET n = row", rows=batch).consume()
                        bar.update(len(batch))
                        batch = []
                if batch:
                    ws.run(f"UNWIND $rows AS row CREATE (n:{_bt(label)}) SET n = row",
                           rows=batch).consume()
                    bar.update(len(batch))
                bar.close()
        with drv.session(database=target) as ws:
            await_indexes(ws)

        with drv.session(database=source, default_access_mode="READ") as rs, \
                drv.session(database=target) as ws:
            bar = progress(total=n_rels, desc="copy carried edges", unit="edge")
            for src_label, dst_label in sorted(
                    (a, b) for a in CARRIED_KEYS for b in CARRIED_KEYS):
                src_key, dst_key = CARRIED_KEYS[src_label], CARRIED_KEYS[dst_label]
                buffers = collections.defaultdict(list)

                def flush(rel_type: str) -> int:
                    rows = buffers.pop(rel_type)
                    return ws.run(
                        f"UNWIND $rows AS row "
                        f"MATCH (a:{_bt(src_label)} {{{_bt(src_key)}: row.src}}), "
                        f"(b:{_bt(dst_label)} {{{_bt(dst_key)}: row.dst}}) "
                        f"CREATE (a)-[r:{_bt(rel_type)}]->(b) SET r = row.props",
                        rows=rows).consume().counters.relationships_created

                for record in rs.run(
                        f"MATCH (a:{_bt(src_label)})-[r]->(b:{_bt(dst_label)}) "
                        f"RETURN a.{_bt(src_key)} AS src, b.{_bt(dst_key)} AS dst, "
                        f"type(r) AS t, properties(r) AS props"):
                    buffers[record["t"]].append({"src": record["src"],
                                                 "dst": record["dst"],
                                                 "props": record["props"]})
                    bar.update(1)
                    if len(buffers[record["t"]]) >= WRITE_BATCH:
                        written_rels += flush(record["t"])
                for rel_type in list(buffers):
                    written_rels += flush(rel_type)
            bar.close()
    finally:
        with drv.session(database=target) as ws:
            names = drop_temp_indexes(ws)
        print(f"  {len(names)} temporary lookup index(es) dropped: {names}",
              flush=True)
    if written_rels != n_rels:
        raise SystemExit(f"copied {written_rels} carried edge(s), source has "
                         f"{n_rels}.")
    return {"nodes": counts, "edges": written_rels}


def apply_carried_schema(drv, target: str, survey: dict, missing: tuple) -> dict:
    constraint_names, index_names = missing
    with drv.session(database=target) as ws:
        names = drop_temp_indexes(ws)
        if names:
            print(f"  {len(names)} temporary lookup index(es) dropped before the "
                  f"schema: {names}", flush=True)
        wanted = [c for c in survey["constraints"] if c["name"] in constraint_names]
        for constraint in wanted:
            print(f"  constraint {constraint['name']} …", flush=True)
            ws.run(_constraint_cypher(constraint)).consume()
        held = [i for i in survey["indexes"] if i["name"] in index_names]
        for index in held:
            covered = survey["index_coverage"].get(index["name"])
            note = "" if covered is None else f" (covers {covered} node(s))"
            print(f"  index {index['name']} {index['type']}{note} …", flush=True)
            ws.run(_index_cypher(index)).consume()
        print("  waiting for every index to come ONLINE …", flush=True)
        await_indexes(ws)
    return {"constraints_created": [c["name"] for c in wanted],
            "indexes_created": [i["name"] for i in held],
            "temp_indexes_dropped": names}


def target_layer(drv, target: str) -> dict:
    keep = list(CARRIED_LABELS)
    with drv.session(database=target, default_access_mode="READ") as s:
        counts = {label: _one(s, f"MATCH (n:{_bt(label)}) RETURN count(n)")
                  for label in CARRIED_LABELS}
        edges = _one(s, "MATCH (a)-[r]->(b) WHERE any(l IN labels(a) WHERE l IN $keep) "
                        "AND any(l IN labels(b) WHERE l IN $keep) "
                        "RETURN count(r)", keep=keep)
        constraints, indexes = schema_rows(s)
    return {"counts": counts, "edges": edges,
            "constraints": {c["name"] for c in constraints},
            "indexes": {i["name"] for i in indexes
                        if not i["name"].startswith(TEMP_INDEX_PREFIX)}}


def carried_plan(drv, state: dict, survey: dict) -> dict:
    target = state["target"]
    wanted = ({c["name"] for c in survey["constraints"]},
              {i["name"] for i in survey["indexes"]})
    if not state["target_exists"]:
        return {"found": "absent — no such database yet", "partial": False,
                "empty": True, "missing": wanted, "stale": [],
                "would": f"create {target!r}, copy "
                         f"{sum(survey['counts'].values())} node(s) and "
                         f"{survey['edges']} edge(s), then apply "
                         f"{len(wanted[0])} constraint(s) and "
                         f"{len(wanted[1])} index(es)"}
    held = target_layer(drv, target)
    with drv.session(database=target, default_access_mode="READ") as s:
        stale = [r["name"] for r in _read(s, "SHOW INDEXES YIELD name RETURN name")
                 if r["name"].startswith(TEMP_INDEX_PREFIX)]
    missing = (wanted[0] - held["constraints"], wanted[1] - held["indexes"])
    empty = not any(held["counts"].values()) and not held["edges"]
    whole = held["counts"] == survey["counts"] and held["edges"] == survey["edges"]
    sweep = (f"drop {len(stale)} leftover lookup index(es) {stale}, then "
             if stale else "")

    if empty:
        return {"found": "empty — the database is there, the carried layer is not",
                "partial": False, "empty": True, "missing": missing, "stale": stale,
                "would": f"{sweep}copy {sum(survey['counts'].values())} node(s) "
                         f"and {survey['edges']} edge(s), then apply "
                         f"{len(missing[0])} constraint(s) and "
                         f"{len(missing[1])} index(es)"}
    if not whole:
        return {"found": f"a half copy — {held['counts']} and {held['edges']} "
                         f"edge(s) against {survey['counts']} and "
                         f"{survey['edges']} in the source",
                "partial": True, "empty": False, "missing": missing, "stale": stale,
                "would": "refuse to write: nothing here can tell which nodes are "
                         "missing, so drop the database and run again"}
    if not missing[0] and not missing[1]:
        return {"found": "complete — the source's nodes, edges and schema all "
                         "present", "partial": False, "empty": False,
                "missing": missing, "stale": stale,
                "would": f"{sweep}leave the carried layer alone" if sweep
                         else "leave the carried layer alone"}
    return {"found": f"nodes without schema — {sum(held['counts'].values())} "
                     f"node(s) and {held['edges']} edge(s) present, "
                     f"{len(missing[0])} constraint(s) and {len(missing[1])} "
                     f"index(es) missing: {sorted(missing[0] | missing[1])}",
            "partial": False, "empty": False, "missing": missing, "stale": stale,
            "would": f"{sweep}skip the copy and apply {len(missing[0])} "
                     f"constraint(s) and {len(missing[1])} index(es)"}


def ensure_carried_layer(drv, state: dict, survey: dict) -> dict:
    source, target = state["source"], state["target"]
    if not state["target_exists"]:
        print(f"creating database {target!r} …", flush=True)
        with drv.session(database="system") as s:
            s.run(f"CREATE DATABASE {_bt(target)} IF NOT EXISTS WAIT").consume()
        state = {**state, "target_exists": True}

    plan = carried_plan(drv, state, survey)
    print(f"target {target!r} is {plan['found']}", flush=True)
    print(f"  {plan['would']}", flush=True)
    if plan["partial"]:
        raise SystemExit(f"{target!r} carries a part-copied layer, and nothing "
                         f"here deletes a chunk or a tag to repair it. Drop the "
                         f"database and run this again:\n"
                         f"    cypher-shell -d system \"DROP DATABASE "
                         f"`{target}` IF EXISTS WAIT\"")

    with drv.session(database=target) as ws:
        stale = drop_temp_indexes(ws)
    if stale:
        print(f"  {len(stale)} temporary lookup index(es) left behind by an "
              f"earlier run dropped: {stale}", flush=True)

    copied, missing = None, plan["missing"]
    if plan["empty"]:
        copied = copy_carried_layer(drv, source, target, survey)
        held = target_layer(drv, target)
        if held["counts"] != survey["counts"] or held["edges"] != survey["edges"]:
            raise SystemExit(f"the copy left {held['counts']} and "
                             f"{held['edges']} edge(s), source has "
                             f"{survey['counts']} and {survey['edges']}.")
        missing = ({c["name"] for c in survey["constraints"]} - held["constraints"],
                   {i["name"] for i in survey["indexes"]} - held["indexes"])

    schema = None
    if missing[0] or missing[1]:
        print(f"applying the schema {source!r} declares — "
              f"{len(missing[0])} constraint(s), {len(missing[1])} index(es) …",
              flush=True)
        schema = apply_carried_schema(drv, target, survey, missing)

    final = target_layer(drv, target)
    short = ({c["name"] for c in survey["constraints"]} - final["constraints"],
             {i["name"] for i in survey["indexes"]} - final["indexes"])
    if short[0] or short[1]:
        raise SystemExit(f"{target!r} is still missing the constraint(s) "
                         f"{sorted(short[0])} and index(es) {sorted(short[1])} "
                         f"that {source!r} declares.")
    print(f"  carried layer settled: {final['counts']}, {final['edges']} edge(s), "
          f"{len(final['constraints'])} constraint(s), {len(final['indexes'])} "
          f"index(es)", flush=True)
    return {"target_database": target, "source_database": source,
            "timestamp": _utc_now(), "found": plan["found"], "would": plan["would"],
            "stale_indexes_dropped": stale, "copied": copied, "schema": schema,
            "source_layer": {"counts": survey["counts"], "edges": survey["edges"],
                             "constraints": sorted(c["name"] for c in survey["constraints"]),
                             "indexes": sorted(i["name"] for i in survey["indexes"]),
                             "index_coverage": survey["index_coverage"]},
            "target_layer": {"counts": final["counts"], "edges": final["edges"],
                             "constraints": sorted(final["constraints"]),
                             "indexes": sorted(final["indexes"])},
            "source_lineage": source_lineage(source)}


def _recordable(props: dict) -> dict:
    out = {}
    for key, value in props.items():
        if isinstance(value, JSON_SCALARS):
            out[key] = value
        elif isinstance(value, list):
            if all(isinstance(element, str) for element in value):
                out[key] = value
        else:
            out[key] = str(value)
    return out


def purge_structure(drv, target: str) -> dict:
    keep = list(CARRIED_LABELS)
    with drv.session(database=target, default_access_mode="READ") as s:
        n_nodes = _one(s, "MATCH (n) WHERE NOT any(l IN labels(n) WHERE l IN $keep) "
                          "RETURN count(n)", keep=keep)
        n_edges = _one(s, "MATCH (a)-[r]->(b) "
                          "WHERE NOT any(l IN labels(a) WHERE l IN $keep) "
                          "OR NOT any(l IN labels(b) WHERE l IN $keep) "
                          "RETURN count(r)", keep=keep)
        print(f"  reading the {n_nodes} node(s) and {n_edges} edge(s) the purge "
              f"will remove …", flush=True)
        bar = progress(total=n_nodes, desc="read purged nodes", unit="node")
        removed = []
        for record in s.run(
                "MATCH (n) WHERE NOT any(l IN labels(n) WHERE l IN $keep) "
                "RETURN elementId(n) AS eid, labels(n) AS labels, "
                "properties(n) AS props", keep=keep):
            removed.append({"element_id": record["eid"],
                            "labels": sorted(record["labels"]),
                            "props": _recordable(record["props"])})
            bar.update(1)
        bar.close()
        bar = progress(total=n_edges, desc="read purged edges", unit="edge")
        edges = []
        for record in s.run(
                "MATCH (a)-[r]->(b) "
                "WHERE NOT any(l IN labels(a) WHERE l IN $keep) "
                "OR NOT any(l IN labels(b) WHERE l IN $keep) "
                "RETURN type(r) AS type, properties(r) AS props, "
                "elementId(a) AS start, elementId(b) AS end", keep=keep):
            edges.append({"type": record["type"], "start": record["start"],
                          "end": record["end"],
                          "props": _recordable(record["props"])})
            bar.update(1)
        bar.close()
        print("  reading the chunk ids those edges name …", flush=True)
        chunk_ids = {r["eid"]: r["id"] for r in _read(
            s, "MATCH (c:Chunk) RETURN elementId(c) AS eid, c.chunk_id AS id")}

    by_label = collections.Counter(":".join(r["labels"]) for r in removed)
    by_type = collections.Counter(e["type"] for e in edges)
    touched = {e["start"] for e in edges} | {e["end"] for e in edges}
    survivors = {eid: chunk_id for eid, chunk_id in chunk_ids.items()
                 if eid in touched}
    print(f"  {len(removed)} node(s) to remove: {dict(sorted(by_label.items()))}",
          flush=True)
    print(f"  {len(edges)} edge(s) going with them: "
          f"{dict(sorted(by_type.items()))}", flush=True)
    print(f"  {len(survivors)} surviving chunk(s) named on one of those edges",
          flush=True)

    record = {
        "target_database": target, "timestamp": _utc_now(),
        "predicate": f"a node carrying none of {list(CARRIED_LABELS)} is "
                     f"structure and is removed",
        "nodes_by_label": dict(sorted(by_label.items())),
        "edges_by_type": dict(sorted(by_type.items())),
        "removed_nodes": removed, "removed_edges": edges,
        "surviving_chunk_ids": survivors,
    }
    _write_step(target, "purge", record)

    with drv.session(database=target) as s:
        bar = progress(total=len(removed), desc="purge structure", unit="node")
        deleted = 0
        while True:
            n = _one(s, "MATCH (n) WHERE NOT any(l IN labels(n) WHERE l IN $keep) "
                        "WITH n LIMIT $batch DETACH DELETE n RETURN count(*)",
                     keep=keep, batch=DELETE_BATCH)
            if not n:
                break
            deleted += n
            bar.update(n)
        bar.close()
        left = _one(s, "MATCH (n) WHERE NOT any(l IN labels(n) WHERE l IN $keep) "
                       "RETURN count(n)", keep=keep)
    if left:
        raise SystemExit(f"{left} structure node(s) survived the purge.")
    return {"nodes_removed": deleted, "nodes_expected": len(removed),
            "nodes_by_label": record["nodes_by_label"],
            "edges_by_type": record["edges_by_type"],
            "surviving_chunks_named": len(survivors)}


def prepare_indexes(drv, target: str) -> list:
    names = []
    with drv.session(database=target) as s:
        s.run(f"CREATE INDEX {_bt('entity_id_lookup')} IF NOT EXISTS FOR "
              f"(n:{_bt(ENTITY_LABEL)}) ON (n.{_bt(ENTITY_KEY)})").consume()
        names.append("entity_id_lookup")
        await_indexes(s)
    print(f"  structure lookups ONLINE: {names}", flush=True)
    return names


def write_shape(s, shape: dict) -> dict:
    by_label = collections.defaultdict(list)
    for position in shape["positions"]:
        by_label[position["label"]].append(
            {POSITION_KEY: position["path"], "records": position["records"]})
    bar = progress(total=len(shape["positions"]), desc="position nodes", unit="node")
    for label, rows in sorted(by_label.items()):
        s.run(f"UNWIND $rows AS row CREATE (n:{_bt(label)}) SET n = row",
              rows=rows).consume()
        bar.update(len(rows))
    bar.close()

    by_field = collections.defaultdict(list)
    for value in shape["values"]:
        by_field[value["field"]].append({VALUE_KEY: value["value"],
                                         "records": value["records"]})
    bar = progress(total=len(shape["values"]), desc="value nodes", unit="node")
    for field, rows in sorted(by_field.items()):
        s.run(f"UNWIND $rows AS row CREATE (n:{_bt(field)}) SET n = row",
              rows=rows).consume()
        bar.update(len(rows))
    bar.close()

    rows = [{name: entity[name] for name in ENTITY_PROPERTIES}
            for entity in shape["entities"]]
    bar = progress(total=len(rows), desc="entity nodes", unit="node")
    for i in range(0, len(rows), WRITE_BATCH):
        batch = rows[i:i + WRITE_BATCH]
        s.run(f"UNWIND $rows AS row CREATE (n:{_bt(ENTITY_LABEL)}) SET n = row",
              rows=batch).consume()
        bar.update(len(batch))
    bar.close()

    grouped = collections.defaultdict(list)
    for edge in shape["edges"]:
        grouped[(edge["type"], edge["from_label"], edge["from_key"],
                 edge["to_label"], edge["to_key"])].append(edge)
    bar = progress(total=len(shape["edges"]), desc="shape edges", unit="edge")
    for (etype, from_label, from_key, to_label, to_key), rows in sorted(grouped.items()):
        for i in range(0, len(rows), WRITE_BATCH):
            batch = rows[i:i + WRITE_BATCH]
            s.run(f"UNWIND $rows AS row "
                  f"MATCH (a:{_bt(from_label)} {{{_bt(from_key)}: row.from_id}}), "
                  f"(b:{_bt(to_label)} {{{_bt(to_key)}: row.to_id}}) "
                  f"CREATE (a)-[r:{_bt(etype)}]->(b) SET r = row.props",
                  rows=batch).consume()
            bar.update(len(batch))
    bar.close()
    return {"positions": len(shape["positions"]), "values": len(shape["values"]),
            "entities": len(shape["entities"]), "edges": len(shape["edges"])}


def attach_chunks(s, mapped: dict, shape: dict) -> dict:
    label_of = {path: position["label"]
                for path, position in shape["by_path"].items()}
    grouped = collections.defaultdict(list)
    for edge in mapped["chunk_edges"]:
        grouped[label_of[edge["path"]]].append(edge)
    bar = progress(total=len(mapped["chunk_edges"]), desc="chunk edges", unit="edge")
    for label, rows in sorted(grouped.items()):
        for i in range(0, len(rows), WRITE_BATCH):
            batch = rows[i:i + WRITE_BATCH]
            s.run(f"UNWIND $rows AS row "
                  f"MATCH (p:{_bt(label)} {{{_bt(POSITION_KEY)}: row.path}}), "
                  f"(c:Chunk {{chunk_id: row.chunk_id}}) "
                  f"CREATE (p)-[r:{_bt(CHUNK_TYPE)}]->(c) SET r = row.props",
                  rows=batch).consume()
            bar.update(len(batch))
    bar.close()
    return {"chunk_edges": len(mapped["chunk_edges"]),
            "chunks_unplaced": len(mapped["unplaced"])}


def print_shape(shape: dict) -> None:
    children = collections.defaultdict(list)
    values = collections.defaultdict(list)
    chains = collections.defaultdict(list)
    for edge in shape["edges"]:
        if edge["to_key"] == POSITION_KEY:
            children[edge["from_id"]].append(edge)
        elif edge["to_key"] == VALUE_KEY and edge["from_key"] == POSITION_KEY:
            values[(edge["from_id"], edge["type"])].append(edge["to_id"])
        elif edge["to_key"] == VALUE_KEY and edge["from_key"] == VALUE_KEY:
            chains[(edge["from_label"], edge["from_id"])].append(edge)

    def show(path: str, depth: int) -> None:
        for (owner, field), declared in sorted(values.items()):
            if owner != path:
                continue
            print(f"{'  ' * depth}-{field}-> {len(declared)}: "
                  f"{', '.join(sorted(declared)[:6])}"
                  f"{' …' if len(declared) > 6 else ''}", flush=True)
        for edge in sorted(children[path], key=lambda e: e["type"]):
            child = shape["by_path"][edge["to_id"]]
            print(f"{'  ' * depth}-{edge['type']}-> {child['label']}  "
                  f"({child['records']} records)", flush=True)
            show(edge["to_id"], depth + 1)

    for position in shape["positions"]:
        if position["parent"] is not None:
            continue
        print(f"{position['label']}  ({position['records']} records)", flush=True)
        show(position["path"], 1)
    for (label, value), edges in sorted(chains.items()):
        for edge in sorted(edges, key=lambda e: e["type"]):
            print(f"{label} {value} -{edge['type']}-> {edge['to_id']}", flush=True)


def build_census(shape: dict, corpus: dict, mapped: dict) -> dict:
    per_type = collections.Counter(edge["type"] for edge in shape["edges"])
    return {
        "dataset_id": DATASET_ID,
        "files": [{"path": record["rel_path"], "sha256": record["sha256"],
                   "size_bytes": record["size_bytes"]}
                  for record in sorted(corpus["files"].values(),
                                       key=lambda r: r["rel_path"])],
        "forbidden_dropped": corpus["forbidden_dropped"],
        "positions": {position["path"]: position["records"]
                      for position in shape["positions"]},
        "values": {field: sorted(v["value"] for v in shape["values"]
                                 if v["field"] == field)
                   for field in sorted({v["field"] for v in shape["values"]})},
        "entities": len(shape["entities"]),
        "entities_per_population": dict(sorted(collections.Counter(
            entity["population"] for entity in shape["entities"]).items())),
        "edges_by_type": dict(sorted(per_type.items())),
        "chunks_per_position": mapped["chunks_per_position"],
        "chunks_unplaced": mapped["unplaced"],
        "widest_edge_list": mapped["widest_edge_list"],
        "chunk_edges": len(mapped["chunk_edges"]),
    }


def derive(drv, state: dict) -> tuple:
    root = CORPUS / DATASET_ID
    print(f"reading the corpus at {root} …", flush=True)
    corpus = read_corpus(root)
    shape = derive_shape(corpus, DATASET_ID)
    print(f"  {len(shape['positions'])} positions, {len(shape['values'])} declared "
          f"values, {len(shape['entities'])} entities, {len(shape['edges'])} edges",
          flush=True)
    if corpus["forbidden_dropped"]:
        print(f"  forbidden keys dropped while reading: "
              f"{corpus['forbidden_dropped']}", flush=True)

    home = state["target"] if state["target_chunks"] else state["source"]
    print(f"reading the chunks of {home!r} …", flush=True)
    with drv.session(database=home, default_access_mode="READ") as s:
        chunk_rows = read_chunks(s)
        carried = carried_census(s)
    before = {"labels": {}, "rels": {}}
    if state["target_exists"]:
        with drv.session(database=state["target"], default_access_mode="READ") as s:
            before = graph_census(s)
    print(f"  {carried['chunks']} chunks, {carried['tags']} tags, "
          f"{carried['files']} files, {carried['has_tag']} HAS_TAG edges",
          flush=True)
    if not chunk_rows:
        raise SystemExit(f"{home!r} carries no Chunk nodes — this build attaches "
                         f"to a chunk layer, it does not create one.")

    mapped = map_chunks(chunk_rows, corpus, shape)
    print(f"  {len(mapped['chunk_edges'])} chunk edges over "
          f"{len(mapped['chunks_per_position'])} positions; "
          f"{len(mapped['unplaced'])} chunk(s) name an oracle section and attach "
          f"to nothing", flush=True)
    return corpus, shape, mapped, carried, before


def step_plan(drv, source: str, target: str) -> None:
    _guard_target(source, target)
    t0 = time.perf_counter()
    state = database_state(drv, source, target)
    print(f"surveying the carried layer of {source!r} …", flush=True)
    survey = source_layer(drv, source)
    print_source_layer(survey, source)
    plan = carried_plan(drv, state, survey)
    print(f"target {target!r} is {plan['found']}", flush=True)
    print(f"the build would {plan['would']}", flush=True)

    corpus, shape, mapped, carried, before = derive(drv, state)
    print("", flush=True)
    print_shape(shape)
    print("", flush=True)
    census = build_census(shape, corpus, mapped)
    print(f"chunks per position: {census['chunks_per_position']}", flush=True)
    print(f"edges by type: {census['edges_by_type']}", flush=True)
    doomed = structure_census(before["labels"])
    print(f"the purge would remove every node the carried layer does not hold — "
          f"{sum(doomed.values())} node(s): {doomed}", flush=True)
    _write_step(target, "plan", {
        "target_database": target, "source_database": source,
        "timestamp": _utc_now(), "graph_version": GRAPH_VERSION,
        "census": census, "shape_rules": SHAPE_RULES,
        "carried_layer": {"found": plan["found"], "would": plan["would"],
                          "stale_indexes": plan["stale"],
                          "missing_constraints": sorted(plan["missing"][0]),
                          "missing_indexes": sorted(plan["missing"][1]),
                          "source_constraints": sorted(c["name"] for c in survey["constraints"]),
                          "source_indexes": sorted(i["name"] for i in survey["indexes"]),
                          "source_index_coverage": survey["index_coverage"],
                          "census": carried},
        "database_before": before,
        "elapsed_s": round(time.perf_counter() - t0, 1)})
    print(f"plan complete in {time.perf_counter() - t0:.1f}s — nothing was "
          f"written to {target!r}.", flush=True)


def step_build(drv, source: str, target: str) -> None:
    _guard_target(source, target)
    t0 = time.perf_counter()
    state = database_state(drv, source, target)
    print(f"surveying the carried layer of {source!r} …", flush=True)
    survey = source_layer(drv, source)
    print_source_layer(survey, source)
    carried_step = ensure_carried_layer(drv, state, survey)

    state = database_state(drv, source, target)
    corpus, shape, mapped, carried, before = derive(drv, state)

    manifest_path = BUILD_DIR / target / "build_manifest.json"
    previous = archive_manifest(manifest_path)
    print("putting up the structure lookups …", flush=True)
    prepared = prepare_indexes(drv, target)
    mark_in_progress(manifest_path, target, previous)

    print(f"purging the structure of {target!r} — {CARRIED_LABELS} are kept …",
          flush=True)
    purged = purge_structure(drv, target)

    with drv.session(database=target) as s:
        after_purge = carried_census(s)
        if after_purge != carried:
            raise SystemExit(f"the carried layer changed across the purge: "
                             f"{carried} -> {after_purge}")
        print(f"  carried layer unchanged: {after_purge['chunks']} chunks, "
              f"{after_purge['tags']} tags, {after_purge['files']} files, "
              f"{after_purge['has_tag']} HAS_TAG", flush=True)
        written = write_shape(s, shape)
        attached = attach_chunks(s, mapped, shape)

    print("verifying …", flush=True)
    with drv.session(database=target, default_access_mode="READ") as s:
        final_carried = carried_census(s)
        final = graph_census(s)
        entities = _one(s, f"MATCH (n:{_bt(ENTITY_LABEL)}) RETURN count(n)")
        unfiled = _one(s, f"MATCH (c:Chunk) WHERE NOT (:File)"
                          f"-[:{_bt(CHUNK_TYPE)}]->(c) RETURN count(c)")
        held = collections.Counter(r["n"] for r in _read(
            s, f"MATCH (c:Chunk) RETURN count {{ ()-[:{_bt(CHUNK_TYPE)}]->(c) }} "
               f"AS n"))
    if final_carried != carried:
        raise SystemExit(f"the carried layer changed during the build: "
                         f"{carried} -> {final_carried}")
    if unfiled:
        raise SystemExit(f"{unfiled} chunk(s) hang off no file — the pointer into "
                         f"the raw source resolves through nothing.")
    unplaced = len(mapped["unplaced"])
    expected = {2: carried["chunks"] - unplaced}
    if unplaced:
        expected[1] = unplaced
    if dict(held) != expected:
        raise SystemExit(f"chunks carry {dict(held)} incoming {CHUNK_TYPE} edge(s) "
                         f"against {expected} — one file edge each, and one "
                         f"position edge for every chunk the corpus declares a "
                         f"position for.")
    for label, expected in sorted(collections.Counter(
            position["label"] for position in shape["positions"]).items()):
        held = label_total(final["labels"], label)
        if held != expected:
            raise SystemExit(f"{held} {label} node(s) in the graph, {expected} "
                             f"derived.")
    if entities != len(shape["entities"]):
        raise SystemExit(f"{entities} entity node(s) in the graph, "
                         f"{len(shape['entities'])} derived.")
    print(f"  every chunk on one position and one file; {entities} entities; "
          f"carried layer identical.", flush=True)

    census = build_census(shape, corpus, mapped)
    census_sha = hashlib.sha256(json.dumps(
        {"labels": final["labels"], "rels": final["rels"],
         "positions": census["positions"], "values": census["values"],
         "entities": census["entities_per_population"]},
        sort_keys=True).encode("utf-8")).hexdigest()
    manifest_path.write_text(json.dumps({
        "target_database": target,
        "source_database": source,
        "timestamp": _utc_now(),
        "graph_version": GRAPH_VERSION,
        "graph_census_sha256": census_sha,
        "removed_tags_sha256": previous["removed_tags_sha256"] if previous else None,
        "previous_manifest": previous,
        "complete": True,
        "authority": AUTHORITY,
        "corpus_root": str(CORPUS / DATASET_ID),
        "shape_rules": SHAPE_RULES,
        "census": census,
        "written": {**written, **attached},
        "structure_indexes": prepared,
        "purged": purged,
        "carried_layer_step": carried_step,
        "carried_layer": {"before": carried, "after": final_carried,
                          "unchanged": True},
        "database_before": before,
        "final_census": final,
        "elapsed_s": round(time.perf_counter() - t0, 1),
    }, indent=1, sort_keys=True), encoding="utf-8")
    print(f"build manifest written last: {manifest_path} "
          f"({GRAPH_VERSION}, census {census_sha[:12]})", flush=True)
    print(f"done in {time.perf_counter() - t0:.1f}s.", flush=True)


def _chunk_row(**overrides) -> dict:
    row = {name: None for name in CHUNK_PROPERTIES}
    row.update(overrides)
    return row


def _selfcheck() -> None:
    corpus = read_corpus(CORPUS / DATASET_ID)
    shape = derive_shape(corpus, DATASET_ID)
    paths = {position["path"] for position in shape["positions"]}

    assert "Product.slack.Channel" in paths, sorted(paths)
    assert "Product.prs.reviews.user" in paths, sorted(paths)
    assert {"Employee", "Customer"} <= paths, sorted(paths)
    assert shape["by_path"]["Product"]["records"] == 30, shape["by_path"]["Product"]
    assert shape["by_path"]["Product.slack"]["records"] == 33632
    assert shape["by_path"]["Product.prs.reviews"]["records"] == 4609

    declared = collections.defaultdict(set)
    for value in shape["values"]:
        declared[value["field"]].add(value["value"])
    assert len(declared["role"]) == 17, len(declared["role"])
    assert len(declared["org"]) == 6 and len(declared["location"]) == 8
    assert len(declared["company"]) == 10, len(declared["company"])
    assert set(declared) == {"role", "org", "location", "company"}, sorted(declared)
    assert len(shape["values"]) == 41, len(shape["values"])

    for field in ("state", "type", "document_type", "merged", "mergeable",
                  "date", "created_at", "submitted_at"):
        assert field not in {value["field"] for value in shape["values"]}, field
        assert field not in {edge["type"] for edge in shape["edges"]}, field

    chain = [e for e in shape["edges"]
             if e["type"] == "engineers" and e["to_key"] == VALUE_KEY]
    assert len(chain) == 1 and chain[0]["to_id"] == "Software Engineer", chain
    assert chain[0]["from_id"] == "Engineering Lead", chain
    assert chain[0]["from_label"] == "role" and chain[0]["to_label"] == "role", chain

    assert len(shape["entities"]) == 650, len(shape["entities"])
    populations = collections.Counter(e["population"] for e in shape["entities"])
    assert populations == {"Employee": 530, "Customer": 120}, dict(populations)
    assert all(set(entity) == set(ENTITY_PROPERTIES) | {"population"}
               for entity in shape["entities"]), shape["entities"][0]
    ids = {entity["entity_id"] for entity in shape["entities"]}
    assert len(ids) == 650, "two entries carry one synthetic id"
    held = {(entity["rel_path"], entity["index"]) for entity in shape["entities"]}
    assert len(held) == 650, "two entries resolve to one pointer"

    for entity in shape["entities"][:4] + shape["entities"][-4:]:
        record = corpus["files"][entity["rel_path"].split("/", 1)[1]]
        entry = _nth(record["data"], entity["index"], record["key"])
        assert isinstance(entry, dict) and "role" in entry, entry

    per_type = collections.Counter(edge["type"] for edge in shape["edges"])
    assert per_type[ENTITY_TYPE] == 650, per_type[ENTITY_TYPE]
    assert per_type["engineering_leads"] == 48, per_type["engineering_leads"]
    assert per_type["role"] == 650 + 20, per_type["role"]
    nesting = sum(per_type[t] for t in
                  ("chief_product_officers", "engineering_leads", "engineers",
                   "marketing_managers", "marketing_research_analysts",
                   "product_managers", "qa_specialists", "tech_architects",
                   "ux_researchers"))
    assert nesting == 512 + 9, nesting

    source_keys = set(json.loads(
        (CORPUS / DATASET_ID / "metadata" / "employee.json").read_text(
            encoding="utf-8")))
    minted = {entity["entity_id"] for entity in shape["entities"]}
    minted |= {edge["from_id"] for edge in shape["edges"]}
    minted |= {edge["to_id"] for edge in shape["edges"]}
    assert not (minted & source_keys), "a source key reached the graph"

    product = sorted(key for key in shape["members"])[0]
    stem = corpus["files"][product]["stem"]
    slack = _chunk_row(chunk_id="slack-1", section="slack", product=stem,
                       msg_index_start=0, msg_index_end=1,
                       locator_json=json.dumps({"product": stem, "section": "slack",
                                                "indices": [0, 1]}))
    path, records, nested = chunk_records(slack, json.loads(slack["locator_json"]),
                                          corpus, shape)
    assert path == "Product.slack" and not nested, path
    props = chunk_edge_props(slack, path, records, nested, shape)
    assert len(props["id"]) == 2, props["id"]
    assert "Channel.channelID" in props and "Message.User.userId" in props, sorted(props)
    assert "Channel.name" not in props, "a channel name reached an edge"

    pr = _chunk_row(chunk_id="pr-1", section="prs", product=stem, item_index=0,
                    locator_json=json.dumps({"product": stem, "section": "prs",
                                             "indices": [0, 1]}))
    path, records, nested = chunk_records(pr, json.loads(pr["locator_json"]),
                                          corpus, shape)
    props = chunk_edge_props(pr, path, records, nested, shape)
    assert path == "Product.prs", path
    assert "user.login" in props and "reviews.user.login" in props, sorted(props)
    assert "title" not in props and "state" not in props, sorted(props)

    doc = _chunk_row(chunk_id="doc-1", section="documents", product=stem,
                     start_offset=0, end_offset=50, doc_field="content",
                     locator_json=json.dumps({"product": stem, "section": "documents",
                                              "index": 0, "field": "content",
                                              "char_range": [0, 50]}))
    path, records, nested = chunk_records(doc, json.loads(doc["locator_json"]),
                                          corpus, shape)
    props = chunk_edge_props(doc, path, records, nested, shape)
    assert path == "Product.documents" and props["start_offset"] == 0, props
    assert len(props["id"]) == 1 and "author" in props, sorted(props)
    assert "content" not in props, "a document body reached an edge"

    meta = _chunk_row(chunk_id="meta-1", metadata_section="employee",
                      locator_json=json.dumps({"metadata": "employee",
                                               "indices": [0, 1]}))
    path, records, nested = chunk_records(meta, json.loads(meta["locator_json"]),
                                          corpus, shape)
    props = chunk_edge_props(meta, path, records, nested, shape)
    assert path == "Employee" and len(props["employee_id"]) == 2, (path, props)
    assert "name" not in props, "a person name reached an edge"

    tree = _chunk_row(chunk_id="tree-1", metadata_section="salesforce_team",
                      locator_json=json.dumps({"metadata": "salesforce_team",
                                               "index": 0,
                                               "subsection": "engineering_leads"}))
    path, records, nested = chunk_records(tree, json.loads(tree["locator_json"]),
                                          corpus, shape)
    props = chunk_edge_props(tree, path, records, nested, shape)
    assert path == "Employee" and nested, (path, nested)
    assert len(props["employee_id"]) > 1, props

    oracle = _chunk_row(chunk_id="oracle-1", section=EXCLUDED_SECTIONS[0],
                        product=stem,
                        locator_json=json.dumps({"product": stem,
                                                 "section": EXCLUDED_SECTIONS[0],
                                                 "index": 0}))
    path, records, nested = chunk_records(oracle, json.loads(oracle["locator_json"]),
                                          corpus, shape)
    assert path is None and records == [], (path, records)

    census = {"Product": 1, "Chunk": 4869, "Tag": 15605, "File": 33, "Entity": 650}
    assert structure_census(census) == {"Entity": 650, "Product": 1}, \
        structure_census(census)
    assert is_structure(["Product"]) and not is_structure(["File"])

    class _Spatial(tuple):
        def __str__(self):
            return "POINT(1 2)"

    kept = _recordable({"ids": ["b", "a"], "desc_emb": [0.1, 0.2], "n": 3,
                        "where": _Spatial((1, 2)), "flag": True, "none": None})
    assert kept == {"ids": ["b", "a"], "n": 3, "where": "POINT(1 2)",
                    "flag": True, "none": None}, kept
    json.dumps(kept)

    print(f"build_corpus_graph self-check OK — {len(shape['positions'])} positions, "
          f"{len(shape['values'])} declared values, {len(shape['entities'])} "
          f"entities, {len(shape['edges'])} shape edges", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="build_corpus_graph.py — the corpus's own architecture, written as the graph.")
    parser.add_argument("step", choices=("plan", "build", "selfcheck"))
    parser.add_argument("--target-db", default=TARGET_DATABASE,
                        help="database the build writes (never a protected name)")
    parser.add_argument("--source-db", default=SOURCE_DATABASE,
                        help="database the carried layer is copied out of")
    args = parser.parse_args()

    if args.step == "selfcheck":
        _selfcheck()
        return
    drv = _driver()
    try:
        if args.step == "plan":
            step_plan(drv, args.source_db, args.target_db)
        else:
            step_build(drv, args.source_db, args.target_db)
    finally:
        drv.close()


if __name__ == "__main__":
    main()
