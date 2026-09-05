from __future__ import annotations

print("resolve_ranking: ranked chunk ids -> artifact ids; loading the graph "
      "driver and the pointer resolution …", flush=True)

import argparse
import json
from pathlib import Path
from typing import Optional

from harness import jsonl
from arms.artefact_v2 import _driver, _resolve_chunk
from harness.progress import progress

FETCH_BATCH = 1000

OUTPUT_STEM = "ranked_artifact_ids"

_POINTER_CYPHER = """
UNWIND $chunkIds AS cid
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk {chunk_id: cid})
RETURN c.chunk_id AS chunkId, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256
"""


def ranked_chunk_ids(rec: dict) -> list:
    meta = rec.get("meta") or {}
    ranking = meta.get("ranking")
    if isinstance(ranking, dict) and "chunk_ids" in ranking:
        return list(ranking["chunk_ids"])
    trace = meta.get("door_trace")
    if isinstance(trace, list):
        return [row["chunkId"] for row in trace]
    raise RuntimeError(
        f"record {rec.get('id', '?')!r} carries neither meta.ranking.chunk_ids "
        f"nor meta.door_trace — the arm that wrote this run recorded no ranking "
        f"to resolve")


def delivery_boundaries(rec: dict) -> dict:
    meta = rec.get("meta") or {}
    ranking = meta.get("ranking") or {}
    budget = meta.get("char_budget") or {}
    returned = meta.get("returned")
    return {"ids_through": ranking.get("ids_through",
                                       budget.get("kept", returned)),
            "contexts_through": ranking.get("contexts_through", returned)}


def database_of(run: Path, override: Optional[str]) -> str:
    if override:
        return override
    manifest = run / "run_manifest.json"
    name = None
    if manifest.is_file():
        graph = json.loads(manifest.read_text(encoding="utf-8")).get("graph")
        name = (graph or {}).get("database")
    if not name:
        raise SystemExit(
            f"{manifest} records no graph.database — name the graph these chunk "
            f"ids were ranked over with --database")
    return name


def fetch_pointers(session, chunk_ids: list) -> dict:
    pointers: dict = {}
    batches = [chunk_ids[i:i + FETCH_BATCH]
               for i in range(0, len(chunk_ids), FETCH_BATCH)]
    for batch in progress(batches, desc="pointers", unit="batch"):
        for rec in session.run(_POINTER_CYPHER, chunkIds=batch):
            pointers[rec["chunkId"]] = {
                "chunkId": rec["chunkId"], "locator": rec["locator"],
                "relpath": rec["relpath"], "sha256": rec["sha256"]}
    missing = [cid for cid in chunk_ids if cid not in pointers]
    if missing:
        raise RuntimeError(
            f"{len(missing)} of {len(chunk_ids)} ranked chunk id(s) are not in "
            f"this graph, first {missing[0]!r} — the run was ranked over a "
            f"different graph than the one being resolved against")
    return pointers


def resolve_all(pointers: dict) -> dict:
    doc_cache: dict = {}
    resolved: dict = {}
    for cid in progress(sorted(pointers), desc="resolving", unit="chunk"):
        _, ids = _resolve_chunk(pointers[cid], doc_cache)
        resolved[cid] = ids
    return resolved


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", help="a run folder containing arm_outputs.jsonl")
    ap.add_argument("--depth", type=int, default=None,
                    help="resolve only the top N ranks per question (default: "
                         "the whole recorded ranking)")
    ap.add_argument("--database",
                    help="the graph to read pointers from (default: the "
                         "graph.database in run_manifest.json)")
    args = ap.parse_args()

    run = Path(args.run)
    records_path = run / "arm_outputs.jsonl"
    if not records_path.is_file():
        raise SystemExit(f"no arm_outputs.jsonl in {run}")
    if args.depth is not None and args.depth < 1:
        raise SystemExit(f"--depth must be >= 1, got {args.depth}")

    print(f"resolve_ranking: reading {records_path} "
          f"({records_path.stat().st_size / 1e6:.1f} MB) …", flush=True)
    records = jsonl.load(records_path)
    if not records:
        raise SystemExit(f"{records_path} holds no records")
    print(f"resolve_ranking: {len(records)} question(s)", flush=True)

    rankings = []
    for rec in progress(records, desc="rankings", unit="q"):
        ids = ranked_chunk_ids(rec)
        rankings.append((rec["id"],
                         ids if args.depth is None else ids[:args.depth],
                         delivery_boundaries(rec)))
    distinct = sorted({cid for _, ids, _ in rankings for cid in ids})
    positions = sum(len(ids) for _, ids, _ in rankings)
    database = database_of(run, args.database)
    print(f"resolve_ranking: {positions} ranked position(s) over "
          f"{len(distinct)} distinct chunk(s) in graph {database!r} — each "
          f"resolves once", flush=True)

    drv = _driver()
    try:
        with drv.session(database=database) as session:
            pointers = fetch_pointers(session, distinct)
    finally:
        drv.close()
    resolved = resolve_all(pointers)

    suffix = "" if args.depth is None else f".d{args.depth}"
    out_path = run / f"{OUTPUT_STEM}{suffix}.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for qid, ids, bounds in progress(rankings, desc="writing", unit="q"):
            fh.write(json.dumps(
                {"id": qid, "database": database, "ranked": len(ids), **bounds,
                 "chunk_ids": ids,
                 "artifact_ids": [resolved[cid] for cid in ids]},
                ensure_ascii=False) + "\n")
    carried = sum(1 for cid in distinct if resolved[cid])
    bounded = sum(1 for _, _, b in rankings if b["ids_through"] is not None)
    print(f"resolve_ranking: {out_path} — {len(rankings)} question(s), "
          f"{positions} ranked position(s), {carried} of {len(distinct)} "
          f"distinct chunk(s) carry an artifact id, {bounded} record(s) state "
          f"where the delivery cut fell "
          f"({out_path.stat().st_size / 1e6:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
