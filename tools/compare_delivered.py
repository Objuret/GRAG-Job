"""Which questions a new run hands the answer model the same texts as a final run, and which not.

    python tools/compare_delivered.py <new run folder> <final run folder> [--write]

A question is the same when its delivered texts (`contexts`, in the arm's order), their record
ids (`context_ids`, and `meta.chunk_ids` where the arm writes them) and the order the answer
model reads them in (`meta.reading_order`, the artefact) are equal, character for character, in
both runs: the answer call is made of the question and those texts only, so its prompt is the
same. Every other question is changed. A changed question is marked when a text of the new run
holds an employee or a customer record (`harness.record_text.metadata_records`).

Prints counts only, never a question. --write puts `delivered_vs_final.json` into the new run
folder: both runs, the sha256 of both `arm_outputs.jsonl`, and the ids of the same and the
changed questions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prod"))

from harness.record_text import metadata_records  # noqa: E402

CORPUS = ROOT / "data" / "corpus" / "Salesforce__HERB"
OUT_NAME = "delivered_vs_final.json"


def _rows(folder: Path) -> dict:
    rows = {}
    with open(folder / "arm_outputs.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                rows[str(row["id"])] = row
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def delivered(row: dict) -> dict:
    meta = row.get("meta") or {}
    return {"contexts": row.get("contexts") or [],
            "context_ids": [str(i) for i in row.get("context_ids") or []],
            "chunk_ids": meta.get("chunk_ids"),
            "reading_order": meta.get("reading_order")}


def compare(new: dict, final: dict, profile_ids: set) -> dict:
    same, set_changed, order_only, ids_only, missing, with_profile = [], [], [], [], [], []
    for qid, old in final.items():
        if qid not in new:
            missing.append(qid)
            continue
        a, b = delivered(new[qid]), delivered(old)
        if a == b:
            same.append(qid)
            continue
        if sorted(a["contexts"]) != sorted(b["contexts"]):
            set_changed.append(qid)
        elif a["contexts"] != b["contexts"] or a["reading_order"] != b["reading_order"]:
            order_only.append(qid)
        else:
            ids_only.append(qid)
        ids = set(a["context_ids"]) | {str(i) for ids in (a["chunk_ids"] or []) for i in ids}
        if ids & profile_ids:
            with_profile.append(qid)
    return {"same": same, "texts_changed": set_changed, "order_changed_only": order_only,
            "ids_changed_only": ids_only, "missing_in_new_run": missing,
            "changed_with_a_profile_delivered": with_profile,
            "extra_in_new_run": sorted(set(new) - set(final))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("new_run", type=Path)
    ap.add_argument("final_run", type=Path)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    profile_ids = {str(i) for _, i, _ in metadata_records(CORPUS)}
    result = compare(_rows(args.new_run), _rows(args.final_run), profile_ids)
    changed = len(result["texts_changed"]) + len(result["order_changed_only"]) + len(result["ids_changed_only"])
    print(f"{args.new_run.name} against {args.final_run.name}")
    print(f"  same {len(result['same'])} | changed {changed} (texts {len(result['texts_changed'])}, "
          f"order only {len(result['order_changed_only'])}, ids only {len(result['ids_changed_only'])})"
          f" | of the changed, with a profile delivered {len(result['changed_with_a_profile_delivered'])}"
          f" | missing in the new run {len(result['missing_in_new_run'])}"
          f" | not in the final run {len(result['extra_in_new_run'])}")
    if args.write:
        out = {"new_run": args.new_run.name, "final_run": args.final_run.name,
               "new_arm_outputs_sha256": _sha256(args.new_run / "arm_outputs.jsonl"),
               "final_arm_outputs_sha256": _sha256(args.final_run / "arm_outputs.jsonl"),
               "same_means": "contexts, context_ids, meta.chunk_ids and meta.reading_order equal",
               **result}
        (args.new_run / OUT_NAME).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"  written {args.new_run / OUT_NAME}")


if __name__ == "__main__":
    main()
