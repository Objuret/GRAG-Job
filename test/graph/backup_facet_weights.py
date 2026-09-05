from __future__ import annotations

if __name__ == "__main__":
    print("backup_facet_weights: the facet layer of every HAS_TAG edge "
          "— loading neo4j …", flush=True)

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path

from graph.db import DATABASE, RUN_ID, _driver
from harness.progress import progress

BACKUP_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "facet_weight_backup"
WEIGHTS = "weights.jsonl"
MANIFEST = "manifest.json"

WRITE_BATCH = 1000

FIELDS = ("chunk_id", "tag", "facets", "w_facets", "w_chunk")

_COUNT_CYPHER = """
MATCH (:Chunk)-[r:HAS_TAG]->(:Tag)
WHERE r.run_id = $runId
RETURN count(r) AS n
"""

_READ_CYPHER = """
MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $runId
RETURN c.chunk_id AS chunk_id, t.name AS tag, r.facets AS facets,
       r.w_facets AS w_facets, r.w_chunk AS w_chunk
ORDER BY chunk_id, tag
"""

_RESTORE_CYPHER = """
UNWIND $rows AS row
MATCH (c:Chunk {chunk_id: row.chunk_id})-[r:HAS_TAG]->(t:Tag {name: row.tag})
WHERE r.run_id = $runId
SET r.facets = row.facets, r.w_facets = row.w_facets, r.w_chunk = row.w_chunk
"""


def entry_dir() -> Path:
    return BACKUP_DIR / f"{DATABASE}__{RUN_ID}"


def serialise(row: dict) -> str:
    return json.dumps({f: row[f] for f in FIELDS}, ensure_ascii=False,
                      separators=(",", ":"))


def parse(line: str) -> dict:
    row = json.loads(line)
    missing = [f for f in FIELDS if f not in row]
    if missing:
        raise ValueError(
            f"backup line carries no {', '.join(missing)}: {line[:120]!r}")
    return {f: row[f] for f in FIELDS}


def digest(path: Path) -> tuple:
    h = hashlib.sha256()
    lines = 0
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
            lines += block.count(b"\n")
    return h.hexdigest(), lines


def write_backup(rows: list, entry: Path) -> dict:
    entry.mkdir(parents=True, exist_ok=True)
    (entry / MANIFEST).unlink(missing_ok=True)
    path = entry / WEIGHTS
    bar = progress(total=len(rows), desc="write backup", unit="edge")
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(serialise(row) + "\n")
            bar.update(1)
    bar.close()
    sha, _ = digest(path)
    manifest = {"database": DATABASE, "run_id": RUN_ID, "file": WEIGHTS,
                "n_edges": len(rows), "sha256": sha,
                "written": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (entry / MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def require_backup(entry: Path = None) -> dict:
    entry = entry or entry_dir()
    marker = entry / MANIFEST
    again = "run `python backup_facet_weights.py backup` once."
    if not marker.is_file():
        raise RuntimeError(f"no facet-weight backup at {entry} — {again}")
    manifest = json.loads(marker.read_text(encoding="utf-8"))
    if (manifest.get("database"), manifest.get("run_id")) != (DATABASE, RUN_ID):
        raise RuntimeError(
            f"the backup at {entry} holds {manifest.get('database')!r} "
            f"run_id={manifest.get('run_id')!r}; this is {DATABASE!r} "
            f"run_id={RUN_ID!r} — {again}")
    path = entry / manifest.get("file", WEIGHTS)
    if not path.is_file():
        raise RuntimeError(
            f"the backup manifest at {entry} names {path.name}, which is not "
            f"there — {again}")
    sha, lines = digest(path)
    if sha != manifest.get("sha256"):
        raise RuntimeError(
            f"the backup {path} hashes {sha[:12]}…, its manifest records "
            f"{str(manifest.get('sha256'))[:12]}… — {again}")
    if lines != manifest.get("n_edges"):
        raise RuntimeError(
            f"the backup {path} holds {lines} edges, its manifest records "
            f"{manifest.get('n_edges')} — {again}")
    return manifest


def load_backup(entry: Path, manifest: dict) -> list:
    bar = progress(total=manifest["n_edges"], desc="read backup", unit="edge")
    rows = []
    with (entry / manifest["file"]).open("r", encoding="utf-8", newline="\n") as f:
        for line in f:
            rows.append(parse(line))
            bar.update(1)
    bar.close()
    return rows


def round_trip(rows: list) -> int:
    bad = 0
    bar = progress(total=len(rows), desc="round trip", unit="edge")
    for row in rows:
        if parse(serialise(row)) != row:
            bad += 1
        bar.update(1)
    bar.close()
    return bad


def read_edges(s) -> list:
    total = s.run(_COUNT_CYPHER, runId=RUN_ID).single()["n"]
    if not total:
        raise SystemExit(f"no HAS_TAG edge with run_id={RUN_ID!r} in {DATABASE!r}")
    rows = []
    bar = progress(total=total, desc="read edges", unit="edge")
    for rec in s.run(_READ_CYPHER, runId=RUN_ID):
        rows.append({f: rec[f] for f in FIELDS})
        bar.update(1)
    bar.close()
    return rows


def restore(s, rows: list) -> None:
    bar = progress(total=len(rows), desc="restore", unit="edge")
    for i in range(0, len(rows), WRITE_BATCH):
        batch = rows[i:i + WRITE_BATCH]
        s.run(_RESTORE_CYPHER, rows=batch, runId=RUN_ID).consume()
        bar.update(len(batch))
    bar.close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="back up, verify or restore the stored facet layer",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("mode", choices=("backup", "verify", "restore"),
                    help="backup: write the entry; verify: read-only round trip "
                         "and entry check; restore: write the entry back")
    args = ap.parse_args()

    entry = entry_dir()
    t0 = time.perf_counter()
    print(f"{args.mode}: {DATABASE!r} (run_id={RUN_ID!r}) at {entry} …", flush=True)
    drv = _driver()
    try:
        with drv.session(database=DATABASE) as s:
            if args.mode == "backup":
                manifest = write_backup(read_edges(s), entry)
                print(f"  {manifest['n_edges']} edges, "
                      f"sha256 {manifest['sha256'][:12]}…", flush=True)
            elif args.mode == "verify":
                rows = read_edges(s)
                bad = round_trip(rows)
                if bad:
                    raise RuntimeError(
                        f"{bad} of {len(rows)} edges do not survive "
                        f"serialise -> parse")
                print(f"  round trip: all {len(rows)} edges come back "
                      f"identical", flush=True)
                manifest = require_backup(entry)
                stored = load_backup(entry, manifest)
                differ = sum(1 for a, b in zip_longest(stored, rows) if a != b)
                if differ:
                    raise RuntimeError(
                        f"the backup at {entry} differs from the graph on "
                        f"{differ} of {len(rows)} edges")
                print(f"  entry: {manifest['n_edges']} edges, sha256 "
                      f"{manifest['sha256'][:12]}…, every value the graph's",
                      flush=True)
            else:
                manifest = require_backup(entry)
                rows = load_backup(entry, manifest)
                restore(s, rows)
                print(f"  {len(rows)} edges written back", flush=True)
    finally:
        drv.close()
    print(f"done ({time.perf_counter() - t0:.0f}s).", flush=True)


if __name__ == "__main__":
    main()
