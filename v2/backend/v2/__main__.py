"""v2 pipeline CLI.

  python -m v2 derive-corpus <raw-dataset-dir> -> <data>/corpus/<dataset>/
  python -m v2 scan  <dataset-dir>             -> out/<dataset>/manifest.jsonl
  python -m v2 probe <file-or-dir> [...]       -> out/<group>/probe.{txt,json}

Run from backend/. Artifacts land in backend/v2/out/ for eyeballing; they
are stage dumps, not graph state.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from shared.config import Settings, resolve_data_root

from .probe import derive_candidates, fuse_files, render_tree, shape_to_jsonable
from .scan import scan_dataset, write_manifest
from .derive_corpus import STRIP_KEYS, derive_corpus

OUT_ROOT = Path(__file__).resolve().parent / "out"


def _data_root() -> Path:
    return resolve_data_root(Settings().data_root)


def cmd_scan(args: argparse.Namespace) -> None:
    data_root = _data_root()
    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = data_root / dataset_dir
    records = scan_dataset(dataset_dir, data_root)
    out = OUT_ROOT / dataset_dir.name / "manifest.jsonl"
    write_manifest(records, out)
    fmts: dict[str, int] = {}
    for r in records:
        fmts[r.format] = fmts.get(r.format, 0) + 1
    print(f"scan: {len(records)} files, {sum(r.n_bytes for r in records):,} bytes")
    print(f"      formats: {fmts}")
    print(f"      -> {out}")


def cmd_probe(args: argparse.Namespace) -> None:
    paths: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if not p.is_absolute():
            p = _data_root() / p
        if p.is_dir():
            paths += sorted(p.glob("*.json"))
        elif p.is_file():
            paths.append(p)
        else:
            raise FileNotFoundError(f"no such file or dir: {p}")
    if not paths:
        raise RuntimeError("probe: no .json files matched")

    fused = fuse_files(paths)
    collections, docleaves = derive_candidates(fused)
    group = args.group or paths[0].parent.name
    out_dir = OUT_ROOT / group
    out_dir.mkdir(parents=True, exist_ok=True)

    tree_lines = render_tree(fused)
    (out_dir / "probe.txt").write_text(
        f"fused over {len(paths)} file(s)\n\n" + "\n".join(tree_lines) + "\n",
        encoding="utf-8",
    )
    (out_dir / "probe.json").write_text(
        json.dumps(
            {
                "files": [p.name for p in paths],
                "shape": shape_to_jsonable(fused),
                "collections": [asdict(c) for c in collections],
                "document_leaves": [asdict(d) for d in docleaves],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"probe: fused {len(paths)} file(s) -> {out_dir}\\probe.{{txt,json}}")
    print(f"\ncollections ({len(collections)}):")
    for c in collections:
        print(f"  {c.pointer}  [{c.length}]  keys: {list(c.keys)}")
    print(f"\ndocument leaves ({len(docleaves)}):")
    for d in docleaves:
        print(f"  {d.pointer}  (maxlen ~{d.maxlen})")


def cmd_derive_corpus(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = _data_root() / dataset_dir
    keys = tuple(args.keys) if args.keys else STRIP_KEYS
    report = derive_corpus(dataset_dir, keys)
    print(
        f"derive-corpus: {report.n_stripped} files stripped, {report.n_copied} copied "
        f"verbatim, {report.n_skipped} non-json skipped"
    )
    for k, n in report.stripped_counts.items():
        print(f"      {k}: {n} (left in place in raw, never corpus)")
    print(f"      corpus view: {dataset_dir.parent.parent / 'corpus' / dataset_dir.name}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m v2")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ep = sub.add_parser(
        "derive-corpus", help="derive the RAG-safe corpus view from a raw/ dataset"
    )
    ep.add_argument("dataset_dir", help="raw dataset dir (absolute, or relative to data_root)")
    ep.add_argument("--keys", nargs="+", help=f"root keys to strip (default: {list(STRIP_KEYS)})")
    ep.set_defaults(fn=cmd_derive_corpus)

    sp = sub.add_parser("scan", help="catalog a dataset directory")
    sp.add_argument("dataset_dir", help="dataset dir (absolute, or relative to data_root)")
    sp.set_defaults(fn=cmd_scan)

    pp = sub.add_parser("probe", help="fuse shape across files, emit candidates")
    pp.add_argument("paths", nargs="+", help="json files or dirs (relative to data_root ok)")
    pp.add_argument("--group", help="artifact group name (default: parent dir name)")
    pp.set_defaults(fn=cmd_probe)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
