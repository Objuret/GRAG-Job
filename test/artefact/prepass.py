from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path

_V3_ROOT = Path(__file__).resolve().parent.parent.parent
_CORPUS = _V3_ROOT / "data" / "corpus" / "Salesforce__HERB"
_PRODUCTS_DIR = _CORPUS / "products"
_EMPLOYEE_JSON = _CORPUS / "metadata" / "employee.json"
_CUSTOMERS_JSON = _CORPUS / "metadata" / "customers_data.json"

_EXCLUDE_RE = re.compile(
    r"(apart\s+from|excluding|except|but\s+not|not)\s*(?:the\s+|a\s+|an\s+)?$",
    re.IGNORECASE)
_LOOKBACK = 40


@dataclass(frozen=True)
class NameEntry:
    text: str
    kind: str


@dataclass(frozen=True)
class MarkedSpan:
    span: str
    kind: str
    polarity: str
    start: int
    end: int


_load_lock = threading.Lock()
_loaded: list[NameEntry] | None = None


def _load_names() -> list[NameEntry]:
    global _loaded
    with _load_lock:
        if _loaded is not None:
            return _loaded
        if not _PRODUCTS_DIR.is_dir():
            raise RuntimeError(f"products dir missing: {_PRODUCTS_DIR}")
        if not _EMPLOYEE_JSON.is_file():
            raise RuntimeError(f"employee file missing: {_EMPLOYEE_JSON}")
        if not _CUSTOMERS_JSON.is_file():
            raise RuntimeError(f"customers file missing: {_CUSTOMERS_JSON}")
        entries: list[NameEntry] = []
        for pf in sorted(_PRODUCTS_DIR.glob("*.json")):
            entries.append(NameEntry(pf.stem, "product"))
        emp = json.loads(_EMPLOYEE_JSON.read_text(encoding="utf-8"))
        for rec in emp.values():
            name = (rec.get("name") or "").strip()
            if name:
                entries.append(NameEntry(name, "person"))
        cust = json.loads(_CUSTOMERS_JSON.read_text(encoding="utf-8"))
        for rec in cust:
            cname = (rec.get("name") or "").strip()
            if cname:
                entries.append(NameEntry(cname, "person"))
            comp = (rec.get("company") or "").strip()
            if comp:
                entries.append(NameEntry(comp, "org"))
        _loaded = entries
        return entries


def _normalize(s: str) -> tuple[str, list[int]]:
    norm_chars: list[str] = []
    orig_idx: list[int] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            norm_chars.append(" ")
            orig_idx.append(i)
            i += 1
            while i < n and s[i].isspace():
                i += 1
        else:
            norm_chars.append(c.casefold())
            orig_idx.append(i)
            i += 1
    return "".join(norm_chars), orig_idx


def _polarity(norm_prompt: str, match_start: int) -> str:
    lookback = norm_prompt[max(0, match_start - _LOOKBACK):match_start]
    return "excluded" if _EXCLUDE_RE.search(lookback) else "wanted"


def prepass(prompt: str) -> list[MarkedSpan]:
    if not prompt:
        return []
    names = _load_names()
    norm, idx_map = _normalize(prompt)
    spans: list[MarkedSpan] = []
    for entry in names:
        needle = " ".join(entry.text.split()).casefold()
        if not needle:
            continue
        start = 0
        while True:
            hit = norm.find(needle, start)
            if hit == -1:
                break
            end = hit + len(needle)
            orig_start = idx_map[hit]
            orig_end = idx_map[end - 1] + 1
            spans.append(MarkedSpan(
                span=prompt[orig_start:orig_end],
                kind=entry.kind,
                polarity=_polarity(norm, hit),
                start=orig_start,
                end=orig_end,
            ))
            start = end
    spans.sort(key=lambda s: (s.start, s.end, s.kind, s.span))
    return _drop_contained(_dedupe_identical(spans))


def _dedupe_identical(spans: list[MarkedSpan]) -> list[MarkedSpan]:
    seen: set[tuple] = set()
    out: list[MarkedSpan] = []
    for s in spans:
        key = (s.span, s.kind, s.polarity, s.start, s.end)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _drop_contained(spans: list[MarkedSpan]) -> list[MarkedSpan]:
    out: list[MarkedSpan] = []
    for s in spans:
        contained = False
        for o in spans:
            if s is o:
                continue
            if s.start >= o.start and s.end <= o.end and (o.start, o.end) != (s.start, s.end):
                contained = True
                break
        if not contained:
            out.append(s)
    return out


def name_counts() -> dict[str, int]:
    counts = {"product": 0, "person": 0, "org": 0}
    for e in _load_names():
        counts[e.kind] += 1
    return counts


if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or (
        "Apart from PitchForce, what did Anna say about ContextForce last quarter?"
    )
    print(f"names loaded: {name_counts()}")
    print(f"prompt: {text!r}\n")
    for s in prepass(text):
        print(f"  [{s.kind:7} {s.polarity:8}] {s.span!r}  @ {s.start}-{s.end}")
