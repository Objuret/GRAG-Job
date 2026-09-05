import json
from pathlib import Path

_HERE = Path(__file__).parent.parent
RAW = _HERE / "data" / "raw" / "Salesforce__HERB" / "products"
OUT = _HERE / "data" / "questions.jsonl"


def mint_id(product, answerable, index):
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
                "ground_truth": gt if isinstance(gt, list) else [gt],
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
