"""What one run keeps, shown on the made-up question. Never a test question.

    python proof.py <arm> [--answer] [--evaluate]

Runs the arm on the made-up question of output/walkthrough/20261005T040000Z/walkthrough.json
into a folder beside this file, through the harness as any run goes, then starts the same folder
once more (a leg that answers nothing) and prints every key the row, the manifest and the other
files hold, with the type and size of each value. The gold answer and the citation ids given to
the made-up question are made up here; the two ids are real corpus ids so the id scores compute.
"""
import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(REPO / "prod"))
sys.path.insert(0, str(REPO / "test"))

from harness import orchestrator  # noqa: E402

QID = "madeup::walkthrough::0"


def shape(v, depth=0, limit=6):
    if isinstance(v, dict):
        if depth >= limit:
            return f"dict[{len(v)}]"
        return {k: shape(x, depth + 1, limit) for k, x in v.items()}
    if isinstance(v, list):
        if not v:
            return "list[0]"
        return [f"list[{len(v)}] of", shape(v[0], depth + 1, limit)]
    if isinstance(v, str):
        return f"str[{len(v)}]" if len(v) > 40 else v
    return v


def main():
    p = argparse.ArgumentParser()
    p.add_argument("arm")
    p.add_argument("--answer", action="store_true")
    p.add_argument("--evaluate", action="store_true")
    args = p.parse_args()

    walk = json.loads((REPO / "output/walkthrough/20261005T040000Z/walkthrough.json")
                      .read_text(encoding="utf-8"))
    from arms import lucene
    two_ids = lucene.ingest_corpus(orchestrator.DEFAULT_CORPUS)[:2]
    qfile, ids = HERE / "madeup_question.jsonl", HERE / "madeup_ids.jsonl"
    qfile.write_text(json.dumps({
        "id": QID, "question": walk["question"], "type": "content",
        "ground_truth": ["This gold answer is made up for the proof and says nothing true."],
        "citations": [d["id"] for d in two_ids]}) + "\n", encoding="utf-8")
    ids.write_text(json.dumps({"id": QID}) + "\n", encoding="utf-8")

    out = HERE / f"{args.arm}{'__answer' if args.answer else ''}{'__eval' if args.evaluate else ''}"
    pipeline = importlib.import_module(f"arms.{args.arm}")
    scorer = None
    if args.evaluate:
        import eval.ragas as scorer
    config = {"questions_path": qfile, "out_dir": str(out), "char_budget": 72000,
              "top_k": orchestrator.DEFAULT_TOP_K, "workers": 1,
              "retrieval_only": not args.answer}
    orchestrator.run(pipeline, scorer, ids, dict(config))
    orchestrator.run(pipeline, scorer, ids, dict(config))

    print(f"\n================ folder {out.relative_to(REPO)}")
    for f in sorted(out.iterdir()):
        print(f"  {f.name:<28}{f.stat().st_size:>12,} bytes")
    row = json.loads((out / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    print("\n================ the row (one question = one run)")
    print(json.dumps(shape(row), indent=1, ensure_ascii=False))
    man = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    print("\n================ run_manifest.json")
    print(json.dumps(shape(man), indent=1, ensure_ascii=False))
    if args.evaluate:
        em = json.loads((out / "eval_manifest.json").read_text(encoding="utf-8"))
        print("\n================ eval_manifest.json")
        print(json.dumps(shape(em), indent=1, ensure_ascii=False))
        rows = [json.loads(x) for x in (out / "eval_results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        print(f"\n================ eval_results.jsonl: {len(rows)} rows; one judged row:")
        judged = next((r for r in rows if (r["components"].get("usage") or {}).get("chat_calls")), rows[0])
        print(json.dumps(shape(judged), indent=1, ensure_ascii=False))
        calls = [json.loads(x) for x in (out / "eval_calls.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        print(f"\n================ eval_calls.jsonl: {len(calls)} lines; by kind and score:")
        from collections import Counter
        for k, n in sorted(Counter((c.get("kind"), c.get("phase"), c.get("score")) for c in calls).items(), key=str):
            print("  ", k, n)
        print("one judge call line:")
        print(json.dumps(shape(next(c for c in calls if c.get("kind") == "chat")), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
