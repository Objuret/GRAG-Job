"""The query's names land on structure nodes, and the graph walks from there to its areas.

resolve_names reads every structure node that carries a name or a pointer to one,
resolves the name out of the corpus file the pointer names, and caches the list under
the corpus tree sha. land matches those names in the question text literally, and reads
a misspelling as a capitalised query word the literal pass left untouched that is nearest
to exactly one name over all kinds. areas walks the graph's own
relations from each landed node to the chunks it reaches. combine reads one landing
per name — every node the name landed on is that one landing — and takes the question's
area to be where the distinct landings' chunk sets meet.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from harness import provenance
from harness.progress import say

REPO = Path(__file__).resolve().parent.parent.parent
CORPUS = REPO / "data" / "corpus"
CACHE = REPO / "output" / "landing_names.json"

FULL = "full"
FIRST = "first"
CHANNEL = "channel"
PRODUCT = "product"
COMPANY = "company"

ID_PROPERTY = {"Employee": "eid", "Channel": "id", "Customer": "id",
               "Product": "name", "Company": "value"}

POINTER_NODES = (
    ("Employee", "eid", ("name",)),
    ("Channel", "id", ("name",)),
    ("Customer", "id", ("name",)),
)

ROUTES = {
    "employee_channel": ("Employee",
                         "MATCH (n:Employee) WHERE n.eid IN $ids "
                         "MATCH (n)-[:slack]->(:Channel)<-[:channel]-(c:Chunk) "
                         "RETURN n.eid AS node, c.chunk_id AS chunk"),
    "employee_product": ("Employee",
                         "MATCH (n:Employee) WHERE n.eid IN $ids "
                         "MATCH (n)-[:meeting_transcripts|documents]->(:Product)"
                         "<-[:product]-(c:Chunk) "
                         "RETURN n.eid AS node, c.chunk_id AS chunk"),
    "channel_chunk": ("Channel",
                      "MATCH (n:Channel) WHERE n.id IN $ids "
                      "MATCH (n)<-[:channel]-(c:Chunk) "
                      "RETURN n.id AS node, c.chunk_id AS chunk"),
    "product_chunk": ("Product",
                      "MATCH (n:Product) WHERE n.name IN $ids "
                      "MATCH (n)<-[:product]-(c:Chunk) "
                      "RETURN n.name AS node, c.chunk_id AS chunk"),
    "product_kind": ("Product",
                     "MATCH (n:Product) WHERE n.name IN $ids "
                     "MATCH (n)-[:has]->(:Kind)<-[:kind]-(c:Chunk) "
                     "RETURN n.name AS node, c.chunk_id AS chunk"),
}

DEFAULT_ROUTES = ("employee_channel", "employee_product", "channel_chunk",
                  "product_chunk")

_TOKEN = re.compile(r"[^\s]+")
_EDGE_PUNCT = '.,;:!?"\'()[]{}<>'


@dataclass(frozen=True)
class Landing:
    label: str
    node_id: str
    name: str
    kind: str


@dataclass(frozen=True)
class Hit:
    label: str
    node_id: str
    name: str
    kind: str
    form: str
    rule: str


@dataclass(frozen=True)
class Areas:
    by_node: dict
    by_chunk: dict
    by_route: dict


@dataclass(frozen=True)
class Area:
    chunks: frozenset
    landings: dict
    nodes: dict
    by_chunk: dict
    unmet: tuple
    dropped: tuple = ()


def _pointer(doc, pointer: str):
    if pointer in ("", "/"):
        return doc
    node = doc
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def _names_of(record: dict, label: str) -> list:
    name = record.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SystemExit(f"{label} record carries no name: {sorted(record)}")
    out = [(name, FULL if label in ("Employee", "Customer") else CHANNEL)]
    if label in ("Employee", "Customer"):
        out.append((name.split()[0], FIRST))
    return out


def _read_nodes(session) -> dict:
    files = {r["file_id"]: r["rel_path"] for r in session.run(
        "MATCH (f:File) RETURN f.file_id AS file_id, f.rel_path AS rel_path")}
    rows = {}
    for label, id_prop, _ in POINTER_NODES:
        rows[label] = [dict(r) for r in session.run(
            f"MATCH (n:{label}) RETURN n.{id_prop} AS node_id, "
            f"n.file_id AS file_id, n.pointer AS pointer ORDER BY node_id")]
    rows["Product"] = [dict(r) for r in session.run(
        "MATCH (n:Product) RETURN n.name AS node_id, n.name AS name ORDER BY node_id")]
    rows["Company"] = [dict(r) for r in session.run(
        "MATCH (n:Company) RETURN n.value AS node_id, n.value AS name ORDER BY node_id")]
    return {"files": files, "rows": rows}


def _resolve(session) -> list:
    read = _read_nodes(session)
    files, rows = read["files"], read["rows"]
    docs = {}
    landings = []
    for label, _, _ in POINTER_NODES:
        for row in rows[label]:
            rel = files.get(row["file_id"])
            if rel is None:
                raise SystemExit(f"{label} {row['node_id']!r} names file_id "
                                 f"{row['file_id']!r}, which no File node carries")
            if rel not in docs:
                docs[rel] = json.loads((CORPUS / rel).read_text(encoding="utf-8"))
            record = _pointer(docs[rel], row["pointer"])
            for name, kind in _names_of(record, label):
                landings.append(Landing(label, row["node_id"], name, kind))
    for row in rows["Product"]:
        landings.append(Landing("Product", row["node_id"], row["name"], PRODUCT))
    for row in rows["Company"]:
        landings.append(Landing("Company", row["node_id"], row["name"], COMPANY))
    return landings


def resolve_names(session, dataset_id: str | None = None,
                  cache: Path = CACHE) -> list:
    """Every named structure node, its name resolved through its pointer; cached per corpus tree."""
    dataset_id = dataset_id or os.environ.get("HERB_DATASET_ID", "Salesforce__HERB")
    database = os.environ.get("NEO4J_DATABASE", "herb-eval")
    digest = provenance.tree_digest(CORPUS / dataset_id)
    if digest is None:
        raise SystemExit(f"no corpus tree at {CORPUS / dataset_id}")
    key = {"corpus_sha256": digest["sha256"], "n_files": digest["n_files"],
           "database": database, "dataset_id": dataset_id}
    if cache.is_file():
        held = json.loads(cache.read_text(encoding="utf-8"))
        if all(held.get(k) == v for k, v in key.items()):
            say(f"landing names: {len(held['landings'])} from {cache.name}")
            return [Landing(**row) for row in held["landings"]]
    t0 = time.perf_counter()
    landings = _resolve(session)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({**key, "landings": [asdict(l) for l in landings]},
                                indent=1), encoding="utf-8")
    say(f"landing names: {len(landings)} resolved in "
        f"{time.perf_counter() - t0:.2f}s, written to {cache}")
    return landings


def _tokens(text: str) -> list:
    out = []
    for m in _TOKEN.finditer(text):
        word = m.group(0).strip(_EDGE_PUNCT)
        if word:
            out.append((word, m.start(), m.start() + len(word)))
    return out


def distance(a: str, b: str) -> int:
    """Levenshtein distance between two strings."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        row = [i]
        for j, cb in enumerate(b, 1):
            row.append(min(prev[j] + 1, row[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = row
    return prev[-1]


def _capitalised(word: str) -> bool:
    return word[:1].isupper()


def _candidates(tokens: list, covered: list, width: int) -> list:
    """Capitalised token windows that are no literal name match, widest first.

    The first token of the question is never a candidate: a sentence-initial capital
    says nothing about the word. Every token of a window must be capitalised, as every
    word of a resolved full name is, and a window that sits inside a literal name match
    is that name, not a misspelling of one.
    """
    out = []
    for w in range(width, 0, -1):
        for i in range(1, len(tokens) - w + 1):
            span = tokens[i:i + w]
            if not all(_capitalised(word) for word, _, _ in span):
                continue
            first, last = span[0], span[-1]
            if any(a <= first[1] and last[2] <= b for a, b in covered):
                continue
            out.append((" ".join(word for word, _, _ in span), first[1], last[2],
                        range(i, i + w)))
    return out


def land(question: str, landings, known=None) -> list:
    """The names the question text carries: literal whole-word, else the nearest name of a misspelt word.

    A misspelling is a query word that is nearly a name: a capitalised token, or a window
    of capitalised tokens no wider than the widest name, that is no literal name match
    and sits inside none. Each candidate is measured against every
    resolved name of every kind, and lands only when exactly one distinct name is nearest.
    The widest candidate is read first and the tokens it lands are not read again, so a
    landed name's own words cannot land a second name. A question whose capitalised words
    are all literal names, or which has none, lands nothing by this rule.

    known, when given, is the set of casefolded tokens the corpus carries (split as
    `_tokens` splits). A word the corpus carries is a word, not a misspelling: a candidate
    window whose every token is in `known` never reaches the nearest-name pass (the
    orchestrator's construction). Literal matches are read as before.
    """
    by_name = {}
    for l in landings:
        by_name.setdefault(l.name.lower(), []).append(l)
    hits = []
    landed = set()
    covered = []
    for lowered, group in by_name.items():
        pattern = re.compile(r"(?<!\w)" + re.escape(group[0].name) + r"(?!\w)",
                             re.IGNORECASE)
        found = list(pattern.finditer(question))
        if not found:
            continue
        landed.add(lowered)
        covered.extend((m.start(), m.end()) for m in found)
        for l in group:
            hits.append(Hit(l.label, l.node_id, l.name, l.kind, found[0].group(0),
                            "literal"))
    tokens = _tokens(question)
    width = max(len(l.name.split()) for l in landings) if landings else 0
    consumed = set()
    for word, start, end, positions in _candidates(tokens, covered, width):
        if consumed.intersection(positions) or word.lower() in by_name:
            continue
        if known is not None and all(tokens[i][0].casefold() in known for i in positions):
            continue
        best, nearest = None, set()
        for lowered in by_name:
            d = distance(word.lower(), lowered)
            if best is None or d < best:
                best, nearest = d, {lowered}
            elif d == best:
                nearest.add(lowered)
        if len(nearest) != 1:
            continue
        lowered = next(iter(nearest))
        consumed.update(positions)
        if lowered in landed:
            continue
        landed.add(lowered)
        for l in by_name[lowered]:
            hits.append(Hit(l.label, l.node_id, l.name, l.kind,
                            question[start:end], "nearest-unique"))
    return hits


def areas(session, hits, routes=DEFAULT_ROUTES) -> Areas:
    """The chunks each landed node reaches over the graph's own relations."""
    ids = {}
    for h in hits:
        ids.setdefault(h.label, set()).add(h.node_id)
    by_node, by_chunk, by_route = {}, {}, {}
    for route in routes:
        label, cypher = ROUTES[route]
        if label not in ids:
            continue
        reached = {}
        for r in session.run(cypher, ids=sorted(ids[label])):
            reached.setdefault(r["node"], set()).add(r["chunk"])
            by_node.setdefault((label, r["node"]), set()).add(r["chunk"])
            by_chunk.setdefault(r["chunk"], set()).add((label, r["node"]))
        for node, chunks in reached.items():
            by_route[(route, node)] = len(chunks)
    return Areas(by_node=by_node, by_chunk=by_chunk, by_route=by_route)


def combine(areas: Areas, hits, drop_empty=False) -> Area | None:
    """The question's area: one landing per name, the meet of the distinct landings' chunks.

    A landing is a name, not a node: every node that name landed on belongs to it, and its
    chunk set is the union over those nodes' route chunks. The question's area is the
    intersection over the distinct landings, so a person and a product meet on the person's
    chunks that sit under that product. One landing is its own area; no landing is no area.
    An empty meet stays empty and names in `unmet` the landings that reach none of it;
    `by_chunk` carries, for every chunk any landing reaches, the landings that reach it.

    drop_empty: a landing whose nodes reach no chunk defines no area; it is left out of the
    meet and named in `dropped` (the orchestrator's construction). When every landing is
    dropped the area has no landings and no chunks.
    """
    display, nodes, reach = {}, {}, {}
    for h in hits:
        key = (h.kind, h.name.lower())
        display.setdefault(key, h.name)
        nodes.setdefault(key, set()).add((h.label, h.node_id))
        reach.setdefault(key, set()).update(areas.by_node.get((h.label, h.node_id), ()))
    if not reach:
        return None
    named = {key: (key[0], display[key]) for key in reach}
    dropped = ()
    if drop_empty:
        dropped = tuple(sorted(named[k] for k, v in reach.items() if not v))
        reach = {k: v for k, v in reach.items() if v}
    landings = {named[k]: frozenset(v) for k, v in reach.items()}
    meet = frozenset.intersection(*landings.values()) if landings else frozenset()
    by_chunk = {}
    for name, chunks in landings.items():
        for chunk in chunks:
            by_chunk.setdefault(chunk, set()).add(name)
    return Area(chunks=meet,
                landings=landings,
                nodes={named[k]: tuple(sorted(v)) for k, v in nodes.items() if k in reach},
                by_chunk={c: tuple(sorted(n)) for c, n in by_chunk.items()},
                unmet=tuple(sorted(n for n, c in landings.items() if not c & meet)),
                dropped=dropped)


def _smoke() -> None:
    from graph.db import DATABASE, _driver

    say(f"landing smoke on {DATABASE!r} — read only, no model calls")
    drv = _driver()
    with drv.session(database=DATABASE, default_access_mode="READ") as s:
        landings = resolve_names(s)
        kinds = {}
        for l in landings:
            kinds[(l.label, l.kind)] = kinds.get((l.label, l.kind), 0) + 1
        for key in sorted(kinds):
            say(f"  {key[0]:<9} {key[1]:<8} {kinds[key]:>5}")
        pick = {kind: next(l for l in landings if l.kind == kind)
                for kind in (FULL, CHANNEL, PRODUCT)}
        probes = [
            f"who is {pick[FULL].name} and what did they decide",
            f"what was discussed in {pick[CHANNEL].name} last quarter",
            f"which incidents hit {pick[PRODUCT].name}",
            f"what did {pick[FULL].name} do on {pick[PRODUCT].name}",
        ]
        for probe in probes:
            t0 = time.perf_counter()
            hits = land(probe, landings)
            t1 = time.perf_counter()
            a = areas(s, hits)
            t2 = time.perf_counter()
            rules = {}
            for h in hits:
                rules[(h.label, h.kind, h.rule)] = rules.get((h.label, h.kind, h.rule), 0) + 1
            say(f"probe {probes.index(probe) + 1}: {len(hits)} hits, "
                f"{len(a.by_node)} landed nodes with chunks, "
                f"{len(a.by_chunk)} chunks, "
                f"land {t1 - t0:.3f}s, areas {t2 - t1:.3f}s")
            for key in sorted(rules):
                say(f"    {key[0]:<9} {key[1]:<8} {key[2]:<14} {rules[key]:>4}")
            routes = {}
            for (route, _), n in a.by_route.items():
                routes[route] = routes.get(route, 0) + n
            for route in sorted(routes):
                say(f"    route {route:<18} {routes[route]:>6} node-chunk pairs")
            t3 = time.perf_counter()
            area = combine(a, hits)
            t4 = time.perf_counter()
            if area is None:
                say(f"    no landing, no area, combine {t4 - t3:.3f}s")
                continue
            for name in sorted(area.landings):
                say(f"    landing {name[0]:<8} {name[1]:<24} "
                    f"{len(area.nodes[name]):>4} nodes {len(area.landings[name]):>6} chunks")
            say(f"    meet {len(area.chunks):>6} chunks over {len(area.landings)} landings, "
                f"{len(area.unmet)} did not meet, combine {t4 - t3:.3f}s")
            for name in area.unmet:
                say(f"      unmet {name[0]:<8} {name[1]}")
    drv.close()


if __name__ == "__main__":
    print("landing: resolve names, land a probe, walk the areas — loading neo4j …",
          flush=True)
    sys.exit(_smoke())
