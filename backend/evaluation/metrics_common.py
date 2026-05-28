"""Shared helpers for HERB eval reports (token parsing, report merge)."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

_TOKEN_SPLIT = re.compile(r"[;\n,|]+")
_EID_RE = re.compile(r"\beid_[a-f0-9]{8}\b", re.IGNORECASE)


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for r in rows:
        rid = str(r.get("id") or "")
        if not rid:
            continue
        prev = by_id.get(rid)
        if prev is None or not (prev.get("meta") or {}).get("error"):
            by_id[rid] = r
    return list(by_id.values())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def reference_tokens(reference: str) -> list[str]:
    tokens: list[str] = []
    for part in _TOKEN_SPLIT.split(reference):
        t = part.strip()
        if len(t) >= 4:
            tokens.append(t.lower())
    return tokens


def extract_eids(text: str) -> set[str]:
    return {m.lower() for m in _EID_RE.findall(text or "")}


def answer_token_scores(reference: str, response: str) -> dict[str, Any]:
    """Deterministic answer vs gold for HERB token references (eid_* lists)."""
    ref_set = set(reference_tokens(reference))
    ref_eids = extract_eids(reference)
    if ref_eids:
        ref_set |= ref_eids

    if not ref_set:
        return {
            "answer_token_recall": None,
            "answer_token_precision": None,
            "answer_token_f1": None,
            "n_reference_tokens": 0,
            "n_found_in_response": 0,
        }

    resp_lower = (response or "").lower()
    found = {t for t in ref_set if t in resp_lower}

    recall = len(found) / len(ref_set)
    # Precision: eids mentioned in response that are in gold, over eids mentioned in response
    resp_eids = extract_eids(response)
    resp_tokens = {t for t in reference_tokens(response)} | resp_eids
    if not resp_tokens:
        precision = 0.0 if ref_set else None
    else:
        precision = len(found & resp_tokens) / len(resp_tokens)

    if precision is None:
        f1 = None
    elif recall + precision == 0:
        f1 = 0.0
    else:
        f1 = 2 * recall * precision / (recall + precision)

    return {
        "answer_token_recall": recall,
        "answer_token_precision": precision,
        "answer_token_f1": f1,
        "n_reference_tokens": len(ref_set),
        "n_found_in_response": len(found),
    }


def merge_report_payload(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Merge per-sample metric columns; recompute overall means."""
    by_id: dict[str, dict[str, Any]] = {r["id"]: dict(r) for r in base.get("per_sample", [])}
    for row in patch.get("per_sample", []):
        rid = row["id"]
        merged = by_id.setdefault(rid, {"id": rid})
        for k, v in row.items():
            if k != "id" and v is not None:
                merged[k] = v

    per_sample = list(by_id.values())
    metric_keys: set[str] = set()
    for row in per_sample:
        for k, v in row.items():
            if k == "id" or k.startswith("n_"):
                continue
            if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)):
                metric_keys.add(k)

    overall: dict[str, float] = {}
    overall_n: dict[str, int] = {}
    for k in sorted(metric_keys):
        vals = [
            row[k] for row in per_sample
            if isinstance(row.get(k), (int, float)) and not math.isnan(float(row[k]))
        ]
        if vals:
            overall[k] = sum(vals) / len(vals)
            overall_n[k] = len(vals)

    out = dict(base)
    out["per_sample"] = per_sample
    merged_overall = {**base.get("overall", {}), **overall}
    merged_overall_n = {**base.get("overall_n", {}), **overall_n}
    out["overall"] = {k: v for k, v in merged_overall.items() if not k.startswith("n_")}
    out["overall_n"] = {k: v for k, v in merged_overall_n.items() if not k.startswith("n_")}
    out["n_samples"] = len(per_sample)
    for k in ("judge_max_contexts", "judge_max_context_chars"):
        if k in patch:
            out[k] = patch[k]
    return out


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
