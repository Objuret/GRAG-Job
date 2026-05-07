"""Public API for raw dataset layer."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from huggingface_hub import snapshot_download

from shared.config import DEFAULT_DATA_ROOT

from .adapters import discover_payload, summarize_payload, PAYLOAD_PATTERNS
from .classification import classify_file, detect_format_family, infer_split_from_path
from .registry import EXTERNAL_FILES, HF_DATASETS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(data: dict[str, Any], path: Path) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    if df.empty:
        table = pa.table({})
    else:
        table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, path)


def file_size(path: Path) -> int:
    if path.is_file():
        return int(path.stat().st_size)
    total = 0
    for node in path.rglob("*"):
        if node.is_file():
            total += int(node.stat().st_size)
    return total


def download_url(url: str, destination: Path, timeout: int = 120) -> None:
    ensure_dir(destination.parent)
    head = requests.head(url, allow_redirects=True, timeout=timeout)
    head.raise_for_status()
    remote_size = int(head.headers.get("Content-Length", "0"))
    if destination.exists() and remote_size and destination.stat().st_size == remote_size:
        return
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def sync_sources(
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config or {}
    output_root = Path(cfg.get("output_root") or DEFAULT_DATA_ROOT)
    hf_token = cfg.get("hf_token")
    timeout = int(cfg.get("timeout", 120))
    max_workers = int(cfg.get("max_workers", 8))
    ensure_dir(output_root)

    manifest: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_root": str(output_root),
        "datasets": [],
        "external_files": [],
    }

    for dataset in HF_DATASETS:
        target_dir = output_root / dataset.target
        ensure_dir(target_dir)
        snapshot_download(
            repo_id=dataset.repo_id,
            repo_type="dataset",
            local_dir=str(target_dir),
            token=hf_token,
            max_workers=max_workers,
        )
        manifest["datasets"].append(
            {
                "name": dataset.name,
                "path": str(target_dir),
                "bytes": file_size(target_dir),
            }
        )

    for source in EXTERNAL_FILES:
        destination = output_root / source.target
        download_url(source.url, destination, timeout=timeout)
        manifest["external_files"].append(
            {
                "dataset": source.dataset,
                "url": source.url,
                "path": str(destination),
                "bytes": int(destination.stat().st_size),
            }
        )

    dataset_total = int(sum(entry["bytes"] for entry in manifest["datasets"]))
    external_total = int(sum(entry["bytes"] for entry in manifest["external_files"]))
    manifest["dataset_bytes"] = dataset_total
    manifest["external_bytes"] = external_total
    manifest["total_bytes"] = dataset_total + external_total
    manifest_path = output_root / "manifest.json"
    write_json(manifest, manifest_path)
    return {
        "ok": True,
        "manifest_path": str(manifest_path),
        "manifest": manifest,
    }


def scan_raw_tree(data_root: str | Path) -> pd.DataFrame:
    root = Path(data_root)
    raw_root = root / "raw"
    if not raw_root.exists():
        raise FileNotFoundError(f"Raw root not found: {raw_root}")

    columns = [
        "dataset_id",
        "dataset_rel_path",
        "split",
        "rel_path",
        "file_path",
        "file_name",
        "file_ext",
        "format_family",
        "size_bytes",
        "modified_at",
        "sha256",
        "file_class",
        "class_reason",
    ]
    rows: list[dict[str, Any]] = []
    for file_path in sorted(raw_root.rglob("*")):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(raw_root).as_posix()
        dataset_id = rel_path.split("/", 1)[0] if "/" in rel_path else rel_path
        dataset_rel_path = rel_path.split("/", 1)[1] if "/" in rel_path else ""
        class_name, class_reason = classify_file(dataset_id=dataset_id, rel_path=dataset_rel_path)
        stat = file_path.stat()
        rows.append(
            {
                "dataset_id": dataset_id,
                "dataset_rel_path": dataset_rel_path,
                "split": infer_split_from_path(dataset_rel_path),
                "rel_path": rel_path,
                "file_path": str(file_path.resolve()),
                "file_name": file_path.name,
                "file_ext": file_path.suffix.lower(),
                "format_family": detect_format_family(dataset_rel_path),
                "size_bytes": int(stat.st_size),
                "modified_at": iso_utc(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
                "sha256": sha256_file(file_path),
                "file_class": class_name,
                "class_reason": class_reason,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def snapshot_raw_hash_map(data_root: str | Path) -> dict[str, dict[str, Any]]:
    catalog = scan_raw_tree(data_root)
    out: dict[str, dict[str, Any]] = {}
    for row in catalog.to_dict(orient="records"):
        out[str(row["rel_path"])] = {
            "sha256": str(row["sha256"]),
            "size_bytes": int(row["size_bytes"]),
        }
    return out


def _resolve_latest_run(raw_dataset_root: Path, run_id: str | None) -> tuple[str, Path]:
    if run_id:
        return run_id, raw_dataset_root / run_id
    candidates = sorted([path for path in raw_dataset_root.iterdir() if path.is_dir()])
    if not candidates:
        raise RuntimeError(f"No raw_dataset_runs under {raw_dataset_root}")
    chosen = candidates[-1]
    return chosen.name, chosen


def _next_run_id(root: Path) -> str:
    run_id = utc_now().strftime("%Y%m%dT%H%M%SZ")
    candidate = root / run_id
    if candidate.exists():
        raise RuntimeError(f"Run directory already exists: {candidate}")
    return run_id


def build_dataset_run(
    data_root: str | Path,
    source_manifest: str | Path | None = None,
    run_id: str | None = None,
    max_records_per_file: int = 1,
) -> dict[str, Any]:
    root = Path(data_root)
    raw_dataset_root = root / "raw_dataset_runs"
    ensure_dir(raw_dataset_root)
    resolved_run_id = run_id or _next_run_id(raw_dataset_root)
    run_dir = raw_dataset_root / resolved_run_id
    if run_dir.exists():
        raise RuntimeError(f"raw_dataset_run already exists: {run_dir}")
    ensure_dir(run_dir)

    started = utc_now()
    raw_catalog = scan_raw_tree(root)

    payload_frames: list[pd.DataFrame] = []
    profile_rows: list[dict[str, Any]] = []

    dataset_ids = sorted(set(raw_catalog["dataset_id"].dropna().astype(str).tolist()) | set(PAYLOAD_PATTERNS))
    for dataset_id in dataset_ids:
        group = raw_catalog[raw_catalog["dataset_id"] == dataset_id].copy()
        discovered = discover_payload(raw_catalog, dataset_id)
        summary = summarize_payload(discovered)

        if not discovered.empty:
            payload_frames.append(discovered)

        dataset_profile = {
            "dataset_id": str(dataset_id),
            "total_files": int(len(group)),
            "total_bytes": int(group["size_bytes"].sum()),
            "payload_files": int(summary.get("payload_files", 0)),
            "payload_bytes": int(summary.get("payload_bytes", 0)),
        }
        profile_rows.append(dataset_profile)

    payload_catalog = (
        pd.concat(payload_frames, ignore_index=True)
        if payload_frames
        else pd.DataFrame(columns=list(raw_catalog.columns))
    )
    dataset_profile = pd.DataFrame(profile_rows)

    raw_catalog_path = run_dir / "raw_file_catalog.parquet"
    payload_catalog_path = run_dir / "dataset_payload_catalog.parquet"
    profile_path = run_dir / "dataset_profile.parquet"

    write_parquet(raw_catalog, raw_catalog_path)
    write_parquet(payload_catalog, payload_catalog_path)
    write_parquet(dataset_profile, profile_path)

    finished = utc_now()
    source_manifest_path = Path(source_manifest) if source_manifest else (root / "manifest.json")
    source_manifest_checksum = (
        sha256_file(source_manifest_path) if source_manifest_path.exists() and source_manifest_path.is_file() else None
    )
    manifest: dict[str, Any] = {
        "raw_dataset_run_id": resolved_run_id,
        "run_started_utc": iso_utc(started),
        "run_finished_utc": iso_utc(finished),
        "data_root": str(root),
        "paths": {
            "raw_file_catalog_parquet": str(raw_catalog_path),
            "dataset_payload_catalog_parquet": str(payload_catalog_path),
            "dataset_profile_parquet": str(profile_path),
        },
        "counts": {
            "raw_file_rows": int(len(raw_catalog)),
            "payload_rows": int(len(payload_catalog)),
            "datasets_seen": sorted(raw_catalog["dataset_id"].dropna().astype(str).unique().tolist()),
        },
    }
    manifest_path = run_dir / "dataset_run_manifest.json"
    write_json(manifest, manifest_path)
    return {
        "ok": True,
        "run_id": resolved_run_id,
        "run_dir": str(run_dir),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
    }

