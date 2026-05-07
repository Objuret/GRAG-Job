"""Raw file classification helpers."""

from __future__ import annotations

from pathlib import Path


def infer_split_from_path(path: str) -> str | None:
    parts = [segment.lower() for segment in Path(path).parts]
    file_name = Path(path).name.lower()
    candidates = ("train", "validation", "valid", "val", "test", "dev")
    for token in candidates:
        if token in parts or token in file_name:
            if token == "valid":
                return "validation"
            return token
    return None


def detect_format_family(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".json":
        return "json"
    if ext in {".jsonl", ".ndjson"}:
        return "jsonl"
    if ext == ".parquet":
        return "parquet"
    if ext in {".yaml", ".yml"}:
        return "yaml"
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return "image"
    if ext in {".zip", ".tar", ".gz"}:
        return "archive"
    return "unknown"


def classify_file(dataset_id: str, rel_path: str) -> tuple[str, str]:
    """Classify raw files into payload/repo-meta/cache-meta buckets."""
    _ = dataset_id
    posix_path = rel_path.replace("\\", "/")
    lowered = posix_path.lower()
    file_name = Path(lowered).name
    suffix = Path(lowered).suffix

    if lowered.startswith(".cache/huggingface/") or "/.cache/huggingface/" in lowered:
        return "cache_meta", "huggingface_cache_sidecar"
    if suffix == ".metadata":
        return "cache_meta", "huggingface_metadata_file"
    if file_name in {".gitignore", "cachedir.tag"}:
        return "cache_meta", "cache_control_file"

    if file_name in {"readme.md", ".gitattributes"}:
        return "repo_meta_code", "repository_metadata"
    if suffix in {".md", ".py", ".yaml", ".yml", ".tag"}:
        return "repo_meta_code", "dataset_repo_support_file"

    return "payload_data", "dataset_payload_candidate"


