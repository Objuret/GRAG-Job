"""Stage query: pre-pass — deterministic literal matching against the corpus
name directories (DESIGN §14.7).

Loads product names (product filenames), employee names (employee.json), and
customer person + company names (customers_data.json) once, then matches a
prompt by case-folded, whitespace-normalized exact substring. Each match
carries kind, polarity (wanted/excluded via a nearby exclusion keyword), and
char offsets into the original prompt. Fail loud on missing files.

No embeddings, no fuzzy match — exact only. Ambiguity (multiple matches,
overlapping names) is returned in full; boost math is downstream.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path

_V3_ROOT = Path(__file__).resolve().parent.parent
_CORPUS = _V3_ROOT / "data" / "corpus" / "Salesforce__HERB"
_PRODUCTS_DIR = _CORPUS / "products"
_EMPLOYEE_JSON = _CORPUS / "metadata" / "employee.json"
_CUSTOMERS_JSON = _CORPUS / "metadata" / "customers_data.json"

# An exclusion keyword must be the LAST word(s) immediately before the match
# (only an optional determiner allowed in between). The regex is anchored at
# the end of the lookback slice (which ends at the match start), so a keyword
# followed by verbs/other entities ("discussed but not implemented in X",
# "sets the product apart from IBM Watson") does NOT bind to a later entity.
# This kills the false positives a bare "within 30 chars" rule produces on
# real HERB phrasing while still catching "apart from PitchForce" / "not X".
_EXCLUDE_RE = re.compile(
    r"(apart\s+from|excluding|except|but\s+not|not)\s*(?:the\s+|a\s+|an\s+)?$",
    re.IGNORECASE)
_LOOKBACK = 40  # generous slice; the `$` anchor does the binding


@dataclass(frozen=True)
class NameEntry:
    text: str   # original-cased name as it appears in the directory
    kind: str   # person | org | product


@dataclass(frozen=True)
class MarkedSpan:
    span: str       # original-cased substring from the prompt
    kind: str       # person | org | product
    polarity: str   # wanted | excluded
    start: int      # char offset into the original prompt
    end: int        # exclusive


_load_lock = threading.Lock()
_loaded: list[NameEntry] | None = None


def _load_names() -> list[NameEntry]:
    """Load + cache the three name directories. Fail loud on missing files."""
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
    """Case-fold + collapse whitespace runs to a single space. Returns the
    normalized string and a map from normalized-index → original-index."""
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
    """excluded if the text immediately before the match ends with an
    exclusion keyword (only an optional determiner in between), else wanted."""
    lookback = norm_prompt[max(0, match_start - _LOOKBACK):match_start]
    return "excluded" if _EXCLUDE_RE.search(lookback) else "wanted"


def prepass(prompt: str) -> list[MarkedSpan]:
    """Deterministic literal match of `prompt` against the corpus name
    directories. Returns every match — ambiguity is downstream's problem."""
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
            start = end  # advance past this match — non-overlapping per name
    spans.sort(key=lambda s: (s.start, s.end, s.kind, s.span))
    return _drop_contained(_dedupe_identical(spans))


def _dedupe_identical(spans: list[MarkedSpan]) -> list[MarkedSpan]:
    """Drop exact duplicates (same span/kind/polarity/start/end) — e.g. an
    employee and a customer sharing the same name produce two identical rows.
    Different-kind duplicates are real ambiguity and kept."""
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
    """Drop a match whose [start, end) is fully contained in another match's
    — e.g. "EdgeForce" inside "KnowledgeForce". A genuine prompt that names
    two distinct entities produces non-contained spans; containment is the
    substring-false-positive signature. Ties (identical span, different kind)
    are kept — that's real ambiguity, two directories resolving to one span."""
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
    """Diagnostic: how many names of each kind are loaded."""
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
