"""Per chunk, the model writes five facet numbers per tag; --out writes an overlay file
(HERB_FACET_OVERLAY), --write puts them on the edges of herb-eval-volmax (backup must match the
live layer). The numbers came back heaped on 0.05 and per-tag; see the ordering pass.

  python test/graph/reweight_facet_layer.py [--from-run DIR | --chunks FILE | --limit N]
         [--repeat] [--prompt his|tied] (--out FILE | --write)
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
for _sub in ("test", "prod"):
    _p = str(ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

BUILD_DATABASE = "herb-eval-volmax"
os.environ.setdefault("NEO4J_DATABASE", BUILD_DATABASE)

from arms.artefact_v2 import _chat_json                                         # noqa: E402
from graph import backup_facet_weights as bkp                                   # noqa: E402
from graph.build_facet_layer import _CHUNKS_CYPHER, _EDGES_CYPHER, read_chunks  # noqa: E402
from graph.db import ALL_FACETS, DATABASE, RUN_ID, _driver                      # noqa: E402
from harness.progress import progress                                           # noqa: E402

MODEL = "claude-haiku-4-5"          # the model the arm already reads the query with
CACHE_DIR = ROOT / "output" / "reweight_facet_cache"
GRAIN = 0.001                       # the lattice the numbers are stored on; what the model
                                    # actually uses is measured and printed after every pass
MAX_TAGS = 40                       # a chunk with more tags is asked in several calls
CHUNK_CHARS = 12000                 # the text handed to the model, from the head of the chunk
WRITE_BATCH = 500

_FACETS = ", ".join(ALL_FACETS)

_ANSWER = ('Answer with JSON only: {"tags": [{"t": "<tag exactly as given>", "w": ['
           + _FACETS + "]}, ...]}, one entry per tag, in the order given.")

PROMPTS = {
    # "his": the CLAUDE.md wording ("how relevant the tag is to the chunk, according to EACH
    # facet"); "tied": the first wording, kept for comparison
    "his": (
        "You are given one chunk of text and a list of tags that were attached to it.\n"
        "For every tag, say how relevant the tag is to this chunk, according to each of five "
        "facets:\n" + _FACETS + ".\n"
        "Each is a number from 0 to 1 with three decimals: 0 is not relevant according to that "
        "facet, 1 is fully relevant according to that facet.\n" + _ANSWER),
    "tied": (
        "You are given one chunk of text and a list of tags that were attached to it.\n"
        "For every tag, say how strongly that tag is tied to THIS chunk on each of five facets:\n"
        + _FACETS + ".\n"
        "Each is a number from 0 to 1 with three decimals: 0 is no tie on that facet, 1 is the "
        "strongest tie on that facet. Judge the tie between this tag and this chunk.\n"
        + _ANSWER),
}
_SYSTEM = PROMPTS["tied"]

_WRITE_CYPHER = """
UNWIND $rows AS row
MATCH (c:Chunk {chunk_id: row.chunkId})-[r:HAS_TAG]->(t:Tag {name: row.tag})
WHERE r.run_id = $runId
SET r.facets = $facets, r.w_facets = row.weights
"""


# ------------------------------------------------------------------ one chunk

def _key(chunk_id: str, text: str, tags: list, draw: int) -> str:
    h = hashlib.sha256()
    for field in (MODEL, _SYSTEM, chunk_id, text, json.dumps(tags), str(draw)):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _round(x) -> float:
    return round(min(1.0, max(0.0, float(x))) / GRAIN) * GRAIN


def _validate(tags: list):
    """the model's answer has to name every tag, in order, with five numbers each.
    Everything wrong is a ValueError so the caller's retry sees it."""
    def check(obj: dict) -> None:
        rows = obj.get("tags")
        if not isinstance(rows, list) or len(rows) != len(tags):
            raise ValueError(f"expected {len(tags)} tag rows, got "
                             f"{len(rows) if isinstance(rows, list) else type(rows).__name__}")
        for row, tag in zip(rows, tags):
            if not isinstance(row, dict):
                raise ValueError(f"tag row {row!r} is not an object")
            if str(row.get("t", "")).strip().casefold() != tag.casefold():
                raise ValueError(f"tag row {row.get('t')!r} is not {tag!r}")
            w = row.get("w")
            if not isinstance(w, list) or len(w) != len(ALL_FACETS):
                raise ValueError(f"{tag!r} carries {w!r}, not {len(ALL_FACETS)} numbers")
            try:
                [float(x) for x in w]
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{tag!r} carries a non-number: {w!r}") from exc
    return check


def weigh(chunk_id: str, text: str, tags: list, draw: int = 0) -> tuple:
    """the five numbers per tag for one chunk, one draw — (rows, calls, tokens_in, tokens_out)"""
    key = _key(chunk_id, text, tags, draw)
    path = CACHE_DIR / f"{key}.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8")), 0, 0, 0
        except (ValueError, OSError):
            pass
    user = "Chunk:\n" + text + "\n\nTags:\n" + json.dumps(tags, ensure_ascii=False)
    obj, tin, tout, _ = _chat_json(MODEL, _SYSTEM, user, 64 + 40 * len(tags),
                                   validate=_validate(tags))
    rows = [{"t": tag, "w": [_round(x) for x in row["w"]]}
            for tag, row in zip(tags, obj["tags"])]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows, 1, tin, tout


def batches(tags: list) -> list:
    return [tags[i:i + MAX_TAGS] for i in range(0, len(tags), MAX_TAGS)]


# ------------------------------------------------------------------ what came back

def lattice(values: np.ndarray) -> float:
    """the coarsest step that at least 99% of the values sit on"""
    v = np.asarray(values, dtype=np.float64)
    for step in (0.25, 0.2, 0.1, 0.05, 0.025, 0.02, 0.01, 0.005, 0.002, 0.001):
        on = np.abs(v / step - np.rint(v / step)) < 1e-6
        if on.mean() >= 0.99:
            return step
    return GRAIN


def describe(out: list, label: str) -> None:
    """per facet: distinct values, the lattice, and how much a tag varies across its chunks"""
    W = np.asarray([r["weights"] for r in out], dtype=np.float64)
    by_tag = collections.defaultdict(list)
    for i, r in enumerate(out):
        by_tag[r["tag"]].append(i)
    multi = [ix for ix in by_tag.values() if len(ix) >= 3]
    print(f"{label}: {len(out)} edges, {len(by_tag)} tags, {len(multi)} tags on 3+ chunks here")
    print(f"  {'facet':9s} {'distinct':>8s} {'lattice':>8s} {'mean':>6s} {'sd':>6s}   "
          f"per-tag sd across chunks: median   share < 0.001")
    for i, f in enumerate(ALL_FACETS):
        col = W[:, i]
        sds = np.array([col[ix].std() for ix in multi]) if multi else np.zeros(0)
        med = f"{np.median(sds):.3f}" if sds.size else "   -"
        flat = f"{(sds < 0.001).mean():.3f}" if sds.size else "   -"
        print(f"  {f:9s} {len(np.unique(col)):8d} {lattice(col):8.3f} {col.mean():6.3f} "
              f"{col.std():6.3f}   {med:>30s}   {flat:>6s}")


def spread(a: list, b: list) -> None:
    """two draws of the same edges: how far apart the numbers came back"""
    A = np.asarray([r["weights"] for r in a], dtype=np.float64)
    B = np.asarray([r["weights"] for r in b], dtype=np.float64)
    d = np.abs(A - B)
    print(f"repeat: {len(a)} edges weighed twice")
    print(f"  {'facet':9s} {'changed':>8s} {'median':>7s} {'p90':>7s} {'max':>7s}")
    for i, f in enumerate(ALL_FACETS):
        c = d[:, i]
        print(f"  {f:9s} {(c > 1e-9).mean():8.3f} {np.median(c):7.3f} "
              f"{np.percentile(c, 90):7.3f} {c.max():7.3f}")
    c = d.ravel()
    print(f"  {'all':9s} {(c > 1e-9).mean():8.3f} {np.median(c):7.3f} "
          f"{np.percentile(c, 90):7.3f} {c.max():7.3f}")


# ------------------------------------------------------------------ the pass

def chunk_ids_of_run(run_dir: Path) -> list:
    ids: list = []
    seen: set = set()
    with (run_dir / "arm_outputs.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            for cid in json.loads(line).get("meta", {}).get("ranking", {}).get("chunk_ids", []):
                if cid not in seen:
                    seen.add(cid)
                    ids.append(cid)
    return ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-run", metavar="DIR", help="the chunks this run opened")
    ap.add_argument("--chunks", metavar="FILE", help="chunk ids, one per line")
    ap.add_argument("--limit", type=int, default=0, help="only the first N chunks by id")
    ap.add_argument("--repeat", action="store_true", help="weigh every chunk twice")
    ap.add_argument("--out", metavar="FILE", help="write an overlay file, not the graph")
    ap.add_argument("--write", action="store_true", help="write the weights onto the edges")
    ap.add_argument("--workers", type=int, default=4, help="chunks in flight on the lane")
    ap.add_argument("--prompt", choices=sorted(PROMPTS), default="tied",
                    help="which wording asks the model")
    args = ap.parse_args()
    global _SYSTEM
    _SYSTEM = PROMPTS[args.prompt]
    if DATABASE != BUILD_DATABASE:
        raise SystemExit(f"NEO4J_DATABASE names {DATABASE!r}; this pass reads and writes "
                         f"{BUILD_DATABASE!r} only")
    if args.write and args.out:
        raise SystemExit("--write and --out are two different products; pick one")

    drv = _driver()
    with drv.session(database=DATABASE) as s:
        rows = [dict(r) for r in s.run(_CHUNKS_CYPHER)]
        edges = [dict(r) for r in s.run(_EDGES_CYPHER, runId=RUN_ID)]
    tags_of = collections.defaultdict(list)
    for e in edges:
        tags_of[e["chunkId"]].append(e["tag"])
    rows = [r for r in rows if tags_of.get(r["chunkId"])]

    chosen = None
    if args.from_run:
        chosen = chunk_ids_of_run(Path(args.from_run))
    elif args.chunks:
        chosen = [l.strip() for l in Path(args.chunks).read_text(encoding="utf-8").splitlines()
                  if l.strip()]
    if chosen is not None:
        want = set(chosen)
        rows = [r for r in rows if r["chunkId"] in want]
        missing = want - {r["chunkId"] for r in rows}
        if missing:
            raise SystemExit(f"{len(missing)} chosen chunk(s) are not in {DATABASE!r} "
                             f"with a {RUN_ID!r} tag: {sorted(missing)[:5]} …")
    if args.limit:
        rows = rows[:args.limit]
    if args.write and chosen is not None:
        raise SystemExit("--write is the whole corpus; a chosen set goes to --out")
    facts = read_chunks(rows)

    n_edges = sum(len(tags_of[r["chunkId"]]) for r in rows)
    calls = sum(len(batches(tags_of[r["chunkId"]])) for r in rows) * (2 if args.repeat else 1)
    tok_in = sum(min(len(f["text"]), CHUNK_CHARS) for f in facts) / 3.3 + calls * len(_SYSTEM) / 3.3
    print(f"reweight_facet_layer: {len(rows)} chunks, {n_edges} edges, {calls} calls to {MODEL} "
          f"on the claude lane, {args.workers} in flight, cache misses only; "
          f"about {tok_in / 1e3:.0f}k tokens in",
          flush=True)
    if not (args.write or args.out):
        print("  no product asked for — nothing is called. --out FILE for an overlay, "
              "--write for the graph.")
        return

    if args.write:
        entry = bkp.entry_dir()
        manifest = bkp.require_backup(entry)
        with drv.session(database=DATABASE) as s:
            live = bkp.read_edges(s)
        backed = {(r["chunkId"], r["tag"]): r for r in bkp.load_backup(entry, manifest)}
        differ = sum(1 for r in live if backed.get((r["chunkId"], r["tag"]), {}).get("w_facets")
                     != r.get("w_facets"))
        if differ or len(backed) != len(live):
            raise SystemExit(f"backup {entry.name} differs from the live layer on {differ} of "
                             f"{len(live)} edges — back up the live layer first")

    t0 = time.perf_counter()
    draws = (0, 1) if args.repeat else (0,)

    def weigh_chunk(k: int) -> tuple:
        cid = rows[k]["chunkId"]
        text = facts[k]["text"][:CHUNK_CHARS]
        got = {d: [] for d in draws}
        calls = tin = tout = 0
        for group in batches(tags_of[cid]):
            for d in draws:
                rows_d, c, i, o = weigh(cid, text, group, d)
                calls += c
                tin += i
                tout += o
                got[d].extend({"chunkId": cid, "tag": g["t"], "weights": g["w"]} for g in rows_d)
        return k, got, calls, tin, tout

    per_chunk: dict = {}
    n_calls = n_in = n_out = 0
    bar = progress(total=len(rows), desc="weigh chunks", unit="chunk")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for done, (k, got, c, i, o) in enumerate(pool.map(weigh_chunk, range(len(rows))), 1):
            per_chunk[k] = got
            n_calls += c
            n_in += i
            n_out += o
            bar.update(1)
            if done % 10 == 0 or done == len(rows):
                print(f"reweight_facet_layer: {done}/{len(rows)} chunks, {n_calls} calls, "
                      f"{time.perf_counter() - t0:.0f}s", flush=True)
    bar.close()
    out = [r for k in range(len(rows)) for r in per_chunk[k][0]]
    again = [r for k in range(len(rows)) for r in per_chunk[k][1]] if args.repeat else []
    print(f"reweight_facet_layer: {len(out)} edges weighed, {n_calls} calls, "
          f"{n_in} tokens in, {n_out} out, {time.perf_counter() - t0:.0f}s", flush=True)

    describe(out, "draw 1")
    if args.repeat:
        describe(again, "draw 2")
        spread(out, again)

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {"database": DATABASE, "run_id": RUN_ID, "model": MODEL, "facets": list(ALL_FACETS),
                "prompt": args.prompt, "system": _SYSTEM, "chunks": len(rows), "edges": out}
        if args.repeat:
            body["edges_draw2"] = again
        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"reweight_facet_layer: overlay {path} ({sha[:12]}) — "
              f"HERB_FACET_OVERLAY={path} reads it over the graph", flush=True)
        return
    if not args.write:
        return
    with drv.session(database=DATABASE) as s:
        bar = progress(total=len(out), desc="write layer", unit="edge")
        for i in range(0, len(out), WRITE_BATCH):
            batch = out[i:i + WRITE_BATCH]
            s.run(_WRITE_CYPHER, rows=batch, runId=RUN_ID, facets=list(ALL_FACETS)).consume()
            bar.update(len(batch))
        bar.close()
    print(f"reweight_facet_layer: written to {DATABASE}", flush=True)


if __name__ == "__main__":
    main()
