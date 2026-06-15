"""Emit gold-100 cohort in HERB dataset order (product file, then answerable_questions index)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_JSONL = _REPO / "frontend/scripts/ragas-questions.herb-gold100.jsonl"
_PRODUCTS = _REPO / "backend/data/raw/Salesforce__HERB/products"
_DEFAULT_OUT = _REPO / "docs/thesis/gold100_appendix_dataset_order.txt"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = p.parse_args()
    name_by_slug = {p.stem.lower(): p.stem for p in _PRODUCTS.glob("*.json")}
    items: list[dict] = []
    for line in _JSONL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        o = json.loads(line)
        m = re.match(r"gold_(.+)_(\d+)$", o["id"])
        if not m:
            continue
        slug, ix = m.group(1), int(m.group(2))
        pname = name_by_slug[slug]
        pfile = _PRODUCTS / f"{pname}.json"
        qtype = "?"
        data = json.loads(pfile.read_text(encoding="utf-8"))
        rec = data["answerable_questions"][ix]
        if isinstance(rec, dict):
            qtype = str(rec.get("type") or "?")
        items.append(
            {
                "product": pname,
                "file": f"products/{pname}.json",
                "qidx": ix,
                "qtype": qtype,
                "id": o["id"],
                "question": o["question"],
            }
        )
    items.sort(key=lambda x: (x["product"].lower(), x["qidx"]))

    lines: list[str] = []
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. HERB-källa: {it['file']} -> answerable_questions[{it['qidx']}]")
        lines.append(f"HERB-typ: {it['qtype']}")
        lines.append(f"Fråga: {it['question']}")
        lines.append("")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # UTF-8 BOM so Windows Notepad shows å/ä/ö correctly.
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    print(f"Wrote {len(items)} items -> {args.out}")


if __name__ == "__main__":
    main()
