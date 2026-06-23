"""Stage 1: scan — catalog raw files. Dumb and meaning-free.

Walks a dataset directory and records, per file: relative path, sha256,
file_id (= sha256[:24], the graph's identity for the file), size, and
format. No content is stored, no meaning is assigned — eval-holdout,
content-kinds, and cross-references are the mapping key's business, not
the scanner's.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

# Formats the pipeline knows how to parse downstream. Everything else is
# cataloged as opaque (referenced, never decomposed).
PARSEABLE_SUFFIXES = {".json": "json", ".md": "markdown", ".txt": "text", ".csv": "csv"}

SKIP_DIRS = {".cache", ".git", "__pycache__"}


@dataclass(frozen=True)
class FileRecord:
    relpath: str        # posix path relative to data_root — the graph's locator
    file_id: str        # sha256[:24] — identity is the content hash
    sha256: str
    n_bytes: int
    format: str         # json | markdown | text | csv | opaque
    parse_ok: bool      # for json: did it parse? (others: trivially True)


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def scan_file(path: Path, data_root: Path) -> FileRecord:
    sha = _hash_file(path)
    fmt = PARSEABLE_SUFFIXES.get(path.suffix.lower(), "opaque")
    parse_ok = True
    if fmt == "json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise RuntimeError(f"unparseable JSON in {path}: {e}") from e
    return FileRecord(
        relpath=path.relative_to(data_root).as_posix(),
        file_id=sha[:24],
        sha256=sha,
        n_bytes=path.stat().st_size,
        format=fmt,
        parse_ok=parse_ok,
    )


def scan_dataset(dataset_dir: Path, data_root: Path) -> list[FileRecord]:
    """Catalog every file under dataset_dir. Fails loud on the first broken file."""
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"dataset dir does not exist: {dataset_dir}")
    records: list[FileRecord] = []
    for path in sorted(dataset_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        records.append(scan_file(path, data_root))
    if not records:
        raise RuntimeError(f"scan found zero files under {dataset_dir}")
    return records


def write_manifest(records: list[FileRecord], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
