"""The pilot's text set: every distinct text the facet views are written for.

A text is a chunk's original text, or one of that chunk's facet counterfactuals as
`facet_counterfactuals` wrote them — one directory per generation, the same chunks asked twice.
A counterfactual is a text only when the teacher changed it and its edit list reconstructed
cleanly; the rest are counted here and never written. Texts are deduplicated by sha256 of the
exact string, and a text two counterfactuals happen to produce carries both origins.

The output is what `facet_views` asks the model about and, through it, what
`facet_embed_gpu.py` embeds: a line's `sha` is the sha256 of its exact `text`, the same sha the
embedder re-computes and refuses on mismatch.

    python test/graph/facet_views_texts.py \
        --cf-dir output/facet_neural/counterfactuals/herb-eval-volmax \
        --cf-dir output/facet_neural/counterfactuals_repeat/herb-eval-volmax \
        --ids-file output/facet_neural/selection_stage2.ids.txt \
        --out output/facet_views/pilot/texts.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "prod", ROOT / "test"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# The four facets and their order are `facet_edits`'s, the same list the counterfactual files
# were written under; that module holds no lane and no driver, so importing it costs nothing.
from graph.facet_edits import FACETS

# The generation a directory belongs to is read from its own path: the repeat pass writes under
# `counterfactuals_repeat`, the first pass under `counterfactuals`. `--cf-dir label=path` says
# it outright when a directory is somewhere else.
REPEAT_MARK = "counterfactuals_repeat"

MAIN = "main"

REPEAT = "repeat"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_cf_dir(value: str) -> tuple:
    """`label=path` or `path`. A head that carries a separator or a drive colon is a path, not
    a label, so a Windows path still reads as one argument."""
    if "=" in value:
        head, rest = value.split("=", 1)
        if head and not any(c in head for c in ("/", "\\", ":")):
            return head, Path(rest)
    path = Path(value)
    label = REPEAT if REPEAT_MARK in path.as_posix() else MAIN
    return label, path


def read_ids(path: str) -> list:
    ids, seen = [], set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line in seen:
            continue
        seen.add(line)
        ids.append(line)
    return ids


def chunk_file(directory: Path, chunk_id: str) -> Path:
    """The counterfactual file of one chunk, named the way `facet_answers.file_stem` names it —
    imported here, not restated, so the two readings cannot drift."""
    from graph.facet_answers import file_stem
    return Path(directory) / f"{file_stem(chunk_id)}.json"


def read_chunk(directory: Path, chunk_id: str, label: str) -> dict:
    path = chunk_file(directory, chunk_id)
    if not path.is_file():
        raise SystemExit(f"facet_views_texts: generation {label!r} has no file for {chunk_id} "
                         f"({path})")
    rec = json.loads(path.read_text(encoding="utf-8"))
    if rec.get("chunk_id") != chunk_id:
        raise SystemExit(f"facet_views_texts: {path} names chunk {rec.get('chunk_id')!r}, "
                         f"asked for {chunk_id!r}")
    if not isinstance(rec.get("text"), str) or not rec["text"]:
        raise SystemExit(f"facet_views_texts: {path} carries no text")
    if not isinstance(rec.get("edges"), list):
        raise SystemExit(f"facet_views_texts: {path} carries no edge list")
    return rec


def build(ids: list, generations: list) -> tuple:
    """(rows, counts, per_chunk). `generations` is [(label, directory)], the first labelled
    `main` supplying the original text every other generation is checked against."""
    labels = [label for label, _d in generations]
    if len(set(labels)) != len(labels):
        raise SystemExit(f"facet_views_texts: two generations share a label: {labels}")
    if MAIN not in labels:
        raise SystemExit(f"facet_views_texts: no generation is labelled {MAIN!r} — the original "
                         f"text comes from it; got {labels}")

    by_sha: dict = {}
    order: list = []
    counts = {"counterfactuals": 0, "unchanged": 0, "recon_fail": 0}
    per_chunk = []

    def add(text: str, chunk: dict, origin: dict) -> None:
        sha = sha256_of(text)
        row = by_sha.get(sha)
        if row is None:
            row = {"sha": sha, "text": text, "chunk_id": chunk["chunk_id"],
                   "kind": chunk.get("kind"), "product": chunk.get("product"),
                   "tags": list(chunk.get("tags") or []), "origins": []}
            by_sha[sha] = row
            order.append(sha)
            row["origins"].append(origin)
            return
        if row["chunk_id"] != chunk["chunk_id"]:
            raise SystemExit(f"facet_views_texts: text {sha[:12]} is both {row['chunk_id']} and "
                             f"{chunk['chunk_id']} — two chunks cannot share one text")
        row["origins"].append(origin)

    for chunk_id in ids:
        records = [(label, read_chunk(directory, chunk_id, label))
                   for label, directory in generations]
        main = dict(records)[MAIN]
        original = main["text"]
        for label, rec in records:
            if rec["text"] != original:
                raise SystemExit(
                    f"facet_views_texts: {chunk_id} generation {label!r} carries a different "
                    f"original text ({sha256_of(rec['text'])[:12]} vs "
                    f"{sha256_of(original)[:12]}) — the generations are not of one chunk")

        stat = {"chunk_id": chunk_id, "kind": main.get("kind"), "product": main.get("product"),
                "tags": len(main.get("tags") or []),
                "texts": {label: 0 for label in labels},
                "unchanged": {label: 0 for label in labels},
                "recon_fail": {label: 0 for label in labels},
                "distinct": 0}

        add(original, main, {"generation": "original"})

        for label, rec in records:
            for edge in rec["edges"]:
                tag = edge.get("t")
                for facet in FACETS:
                    cf = edge.get(facet)
                    if not isinstance(cf, dict) or not isinstance(cf.get("text"), str):
                        raise SystemExit(f"facet_views_texts: {chunk_id} {label} phrase {tag!r} "
                                         f"has no {facet} counterfactual")
                    counts["counterfactuals"] += 1
                    if not cf.get("changed"):
                        counts["unchanged"] += 1
                        stat["unchanged"][label] += 1
                        continue
                    if not cf.get("reconstruction_ok"):
                        counts["recon_fail"] += 1
                        stat["recon_fail"][label] += 1
                        continue
                    if cf["text"] == original:
                        raise SystemExit(
                            f"facet_views_texts: {chunk_id} {label} {tag!r} {facet} is marked "
                            f"changed but equals the original")
                    stat["texts"][label] += 1
                    add(cf["text"], main, {"generation": label, "tag": tag, "facet": facet})

        stat["distinct"] = sum(1 for sha in order if by_sha[sha]["chunk_id"] == chunk_id)
        per_chunk.append(stat)

    rows = [by_sha[sha] for sha in order]
    by_kind: dict = {}
    for row in rows:
        key = str(row.get("kind"))
        by_kind[key] = by_kind.get(key, 0) + 1
    counts["by_kind"] = dict(sorted(by_kind.items()))
    return rows, counts, per_chunk


def write_jsonl(path: Path, header: dict, rows: list) -> None:
    """Temp file then rename, so an interrupt never leaves a half file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"header": header}, ensure_ascii=False) + "\n")
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_texts(path: Path) -> tuple:
    """(header, rows) of a texts file, with every line's sha checked against its own text."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise SystemExit(f"facet_views_texts: {path} is empty")
    header = json.loads(lines[0]).get("header")
    if not isinstance(header, dict):
        raise SystemExit(f"facet_views_texts: {path} has no header line")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        row = json.loads(line)
        got = sha256_of(row["text"])
        if got != row["sha"]:
            raise SystemExit(f"facet_views_texts: {path} line sha {row['sha'][:12]} is really "
                             f"{got[:12]}")
        rows.append(row)
    return header, rows


def summary_path(out: Path) -> Path:
    return Path(out).with_name(Path(out).stem + "_summary.json")


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the distinct texts the facet views are written for")
    ap.add_argument("--cf-dir", action="append", default=[],
                    help="a counterfactual directory, repeatable; `label=path` names its "
                         "generation, a bare path takes it from the path itself")
    ap.add_argument("--ids-file", required=True, help="one chunk id per line")
    ap.add_argument("--out", required=True, help="the texts jsonl")
    args = ap.parse_args(argv)

    print("facet_views_texts starting", flush=True)
    if not args.cf_dir:
        raise SystemExit("facet_views_texts: --cf-dir is required")
    generations = [split_cf_dir(v) for v in args.cf_dir]
    for label, directory in generations:
        if not Path(directory).is_dir():
            raise SystemExit(f"facet_views_texts: {directory} is not a directory")
        print(f"  generation {label}: {directory}", flush=True)

    ids = read_ids(args.ids_file)
    print(f"  ids {len(ids)} from {args.ids_file}", flush=True)

    rows, counts, per_chunk = build(ids, generations)

    header = {
        "written": now_iso(),
        "cf_dirs": [{"generation": label, "path": str(directory)}
                    for label, directory in generations],
        "ids": len(ids),
        "texts": len(rows),
        "counterfactuals": counts["counterfactuals"],
        "unchanged": counts["unchanged"],
        "recon_fail": counts["recon_fail"],
        "by_kind": counts["by_kind"],
    }
    out = Path(args.out)
    write_jsonl(out, header, rows)

    summary = {"written": header["written"], "ids": len(ids), "texts": len(rows),
               "chunks": per_chunk}
    summary_path(out).parent.mkdir(parents=True, exist_ok=True)
    summary_path(out).write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                 encoding="utf-8")

    kept = counts["counterfactuals"] - counts["unchanged"] - counts["recon_fail"]
    print(f"facet_views_texts | ids {len(ids)} | counterfactuals {counts['counterfactuals']} "
          f"(kept {kept}, unchanged {counts['unchanged']}, recon_fail {counts['recon_fail']}) "
          f"| originals {len(ids)} | distinct texts {len(rows)}", flush=True)
    print(f"  by kind {counts['by_kind']}", flush=True)
    print(f"  tags on the texts {sum(len(r['tags']) for r in rows)} "
          f"(distinct phrases {len({t for r in rows for t in r['tags']})})", flush=True)
    print(f"  out {out}", flush=True)
    print(f"  summary {summary_path(out)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
