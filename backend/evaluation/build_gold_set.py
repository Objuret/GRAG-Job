"""Build the HERB GOLD reference set from the live `herb` graph.

    python -m evaluation.build_gold_set [--count 15] [--out PATH]

Read-only. Pulls `qa_record` chunks (section=answerable_questions) — HERB's
own question/answer pairs — and emits a questions JSONL the harness consumes:
{"id","question","reference"} where `reference` is HERB's `ground_truth`.
One pair per product, so the set spans the corpus. This is authoritative
ground truth from the dataset itself, not LLM-guessed.

Neo4j creds resolve from env -> backend/.env -> frontend/.env.local
(VITE_NEO4J_*), same precedence as the harness.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_FRONTEND_ROOT = _BACKEND_ROOT.parent / "frontend"
_DEFAULT_OUT = _FRONTEND_ROOT / "scripts" / "ragas-questions.herb-gold.jsonl"


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if (v[:1], v[-1:]) in (('"', '"'), ("'", "'")):
            v = v[1:-1]
        if k:
            out[k] = v
    return out


def _cfg(name: str, default: str) -> str:
    import os

    be = _parse_env_file(_BACKEND_ROOT / ".env")
    fe = _parse_env_file(_FRONTEND_ROOT / ".env.local")
    return (
        os.environ.get(name)
        or be.get(name)
        or fe.get(name)
        or fe.get(f"VITE_{name}")
        or default
    )


def _extract_json(text: str) -> dict | None:
    """First balanced {...} block, ignoring braces inside JSON strings."""
    i = text.find("{")
    if i < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for j in range(i, len(text)):
        ch = text[j]
        if esc:
            esc = False
            continue
        if ch == chr(92) and in_str:  # backslash
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[i : j + 1])
                except Exception:
                    return None
    return None


def _stem(q: str) -> str:
    """Question-type signature: product names neutralised, first 7 words."""
    q = re.sub(r"[A-Z][a-zA-Z]*(Force|Genie|Flow)", "PROD", q or "")
    return " ".join(re.sub(r"[^a-z ]", " ", q.lower()).split()[:7])


def _norm_gt(gt: object) -> str:
    if gt is None:
        return ""
    if isinstance(gt, list):
        return "; ".join(str(x).strip() for x in gt if str(x).strip())
    return str(gt).strip()


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m evaluation.build_gold_set")
    p.add_argument("--count", type=int, default=15, help="Number of gold pairs (default 15)")
    p.add_argument("--out", type=Path, default=_DEFAULT_OUT, help=f"Output JSONL (default {_DEFAULT_OUT})")
    p.add_argument("--database", default=_cfg("NEO4J_DATABASE", "herb"))
    p.add_argument(
        "--types", default="",
        help="Comma-separated HERB answer-types to keep (content, person, url, "
             "pr, company). Empty = all. Multi-hop proxy: person,company,pr,url "
             "(relational/multi-step) vs content (single-document, ~single-hop).",
    )
    args = p.parse_args()

    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        _cfg("NEO4J_URI", "bolt://localhost:7687"),
        auth=(_cfg("NEO4J_USER", "neo4j"), _cfg("NEO4J_PASSWORD", "")),
    )
    try:
        cands = driver.execute_query(
            "MATCH (c:Chunk) WHERE c.kind='qa_record' "
            "AND c.section='answerable_questions' AND c.question IS NOT NULL "
            "RETURN c.chunk_id AS cid, c.question AS q, c.product AS product, "
            "c.item_index AS ix, c.content AS content "
            "ORDER BY c.product, c.item_index",
            database_=args.database,
        ).records
    finally:
        driver.close()

    # Parse + type-filter up front. HERB `type`: content/person/url/pr/company.
    types_filter = {t.strip() for t in args.types.split(",") if t.strip()}
    parsed: list[dict] = []
    for r in cands:
        obj = _extract_json(r["content"] or "")
        if not obj:
            continue
        qtype = str(obj.get("type") or "unknown")
        if types_filter and qtype not in types_filter:
            continue
        q = (r["q"] or obj.get("question") or "").strip()
        ref = _norm_gt(obj.get("ground_truth"))
        if not q or len(ref) < 3:
            continue
        parsed.append({"cid": r["cid"], "q": q, "product": r["product"],
                       "ix": r["ix"], "qtype": qtype, "ref": ref})

    # Product round-robin over the (filtered) records: round 1 takes one per
    # distinct question stem (every TYPE of question, products balanced),
    # round 2 fills to count with more product instances. Deterministic:
    # products sorted, each product's records ordered by item_index.
    from collections import deque

    by_prod: dict[str, deque] = {}
    for r in parsed:
        by_prod.setdefault(r["product"] or "x", deque()).append(r)
    products = sorted(by_prod)

    chosen: list[dict] = []
    chosen_cids: set[str] = set()
    seen_stems: set[str] = set()

    progressed = True
    while len(chosen) < args.count and progressed:
        progressed = False
        for p in products:
            if len(chosen) >= args.count:
                break
            dq = by_prod[p]
            skipped: list[dict] = []
            picked = None
            while dq:
                r = dq.popleft()
                if _stem(r["q"]) not in seen_stems:
                    picked = r
                    break
                skipped.append(r)  # seen-stem — keep for round 2
            dq.extendleft(reversed(skipped))
            if picked:
                seen_stems.add(_stem(picked["q"]))
                chosen.append(picked)
                chosen_cids.add(picked["cid"])
                progressed = True

    qi = 0
    queues = [by_prod[p] for p in products]
    while len(chosen) < args.count and any(queues):
        dq = queues[qi % len(queues)]
        qi += 1
        if dq:
            r = dq.popleft()
            if r["cid"] not in chosen_cids:
                chosen.append(r)
                chosen_cids.add(r["cid"])

    pairs: list[dict[str, str]] = []
    used_ids: set[str] = set()
    for r in chosen:
        prod = re.sub(r"[^a-z0-9]+", "", (r["product"] or "x").lower())
        base = f"gold_{r['qtype']}_{prod}_{r['ix']}"  # type in id → sliceable
        rid, n = base, 2
        while rid in used_ids:  # ids must be unique (resume + per-sample keying)
            rid, n = f"{base}_{n}", n + 1
        used_ids.add(rid)
        pairs.append({"id": rid, "question": r["q"], "reference": r["ref"]})

    header = [
        "# HERB GOLD reference set — authoritative ground truth from the dataset.",
        "# Generated by `python -m evaluation.build_gold_set` (read-only) from",
        "# qa_record chunks (section=answerable_questions): question = HERB's own",
        "# question, reference = HERB's ground_truth (lists joined with '; ').",
        "#",
        "# Run with the QA sections EXCLUDED so the pipeline answers from real",
        "# evidence, not the gold record (avoids circularity):",
        "#   npm --workspace frontend run ragas:export -- \\",
        "#     --questions ragas-questions.herb-gold.jsonl \\",
        "#     --exclude-sections answerable_questions,unanswerable_questions",
        "#   python -m evaluation.ragas_eval --judge-model claude-sonnet-4-6 \\",
        "#     --metrics faithfulness,context_recall,context_precision,answer_correctness",
        '# Format: one {"id","question","reference"} per line; # lines skipped.',
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n")
        for o in pairs:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

    print(f"Wrote {len(pairs)} gold pair(s) -> {args.out}")
    for o in pairs:
        print(f"  {o['id']:<28} q={o['question'][:62]!r}")


if __name__ == "__main__":
    main()
