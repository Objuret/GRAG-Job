"""Dataset payload discovery — one regex pattern per dataset."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


PAYLOAD_PATTERNS: dict[str, str] = {
    "Salesforce__HERB": r"^(products/.+\.json|metadata/.+\.json)$",
    "VLR-CVC__DocVQA-2026": r"^(val\.parquet|test\.parquet|assets/.+\.(png|jpg|jpeg))$",
    "fever__feverous": r"^data/.+\.jsonl$",
    "wenhu__hybrid_qa": r"^(released_data/.+\.json|hf_repo/.+\.zip)$",
}


def discover_payload(raw_catalog: pd.DataFrame, dataset_id: str) -> pd.DataFrame:
    pattern = PAYLOAD_PATTERNS.get(dataset_id)
    if pattern is None:
        return raw_catalog[
            (raw_catalog["dataset_id"] == dataset_id)
            & (raw_catalog["file_class"] == "payload_data")
        ].copy()
    subset = raw_catalog[raw_catalog["dataset_id"] == dataset_id].copy()
    rel = subset["dataset_rel_path"].astype(str).str.replace("\\", "/", regex=False)
    return subset[rel.str.match(pattern)].copy()


def summarize_payload(payload_df: pd.DataFrame) -> dict[str, Any]:
    return {
        "payload_files": int(len(payload_df)),
        "payload_bytes": int(payload_df["size_bytes"].sum()) if len(payload_df) else 0,
    }
