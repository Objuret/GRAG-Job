"""build_questions.py — one-shot: build the HERB question set from raw.

HERB ships no question ids, so this mints them and writes the complete set to
data/questions.jsonl (id, question, type, ground_truth, citations). Run once;
the runtime (questions.load_questions) just reads that file.
"""
import json
from pathlib import Path

_HERE = Path(__file__).parent
RAW = _HERE / "data" / "raw" / "Salesforce__HERB" / "products"
OUT = _HERE / "data" / "questions.jsonl"


def mint_id(product, answerable, index):
    # a|u marker required: both arrays are 0-indexed, else the ids collide.
    return f"{product}::{'a' if answerable else 'u'}::{index}"


def build():
    rows = []
    for pf in sorted(RAW.glob("*.json")):
        data = json.loads(pf.read_text(encoding="utf-8"))
        for i, rec in enumerate(data["answerable_questions"]):
            gt = rec.get("ground_truth", [])
            rows.append({
                "id": mint_id(pf.stem, True, i),
                "question": rec.get("question", ""),
                "type": rec.get("type", ""),
                "ground_truth": gt if isinstance(gt, list) else [gt],  # sometimes a bare string in raw
                "citations": rec.get("citations") or [],
            })
        for i, q in enumerate(data["unanswerable_questions"]):
            rows.append({
                "id": mint_id(pf.stem, False, i),
                "question": q, "type": "", "ground_truth": [], "citations": [],
            })
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                   encoding="utf-8")
    print(f"wrote {len(rows)} questions -> {OUT.relative_to(_HERE)}")


if __name__ == "__main__":
    build()
