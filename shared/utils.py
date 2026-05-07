"""Shared helpers for run IDs, hashing, and JSON IO."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def stable_short_hash(text: str, length: int = 24) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def hash_tree(root: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not root.exists():
        return rows
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        rows[rel] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    return rows


def compare_hash_maps(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> dict[str, Any]:
    before_keys = set(before)
    after_keys = set(after)
    missing = sorted(before_keys - after_keys)
    added = sorted(after_keys - before_keys)
    changed = sorted(
        rel
        for rel in (before_keys & after_keys)
        if before[rel]["sha256"] != after[rel]["sha256"]
    )
    return {
        "unchanged": not (missing or added or changed),
        "missing_files": missing,
        "added_files": added,
        "changed_files": changed,
    }


def find_latest_run_id(root: Path) -> str:
    if not root.exists():
        raise RuntimeError(f"Run root does not exist: {root}")
    run_ids = sorted([path.name for path in root.iterdir() if path.is_dir()])
    if not run_ids:
        raise RuntimeError(f"No runs found under: {root}")
    return run_ids[-1]


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [make_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [make_json_safe(v) for v in value]
    if isinstance(value, set):
        return [make_json_safe(v) for v in sorted(value)]
    if isinstance(value, np.ndarray):
        return [make_json_safe(v) for v in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return iso_utc(value if value.tzinfo else value.replace(tzinfo=timezone.utc))
    return value


def write_json(payload: dict[str, Any], path: Path) -> None:
    ensure_dir(path.parent)
    safe_payload = make_json_safe(payload)
    path.write_text(json.dumps(safe_payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
