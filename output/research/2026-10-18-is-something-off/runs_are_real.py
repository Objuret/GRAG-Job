"""Are the runs real (his 2026-10-18 "the fact that you keep spouting the same fucking numbers out no matter
what i tell you to build says me something is fucking off")? For each run of the hundred: the code it ran (the
sha256 of the arm and its arithmetic, as the run recorded them), its context_recall_id as the evaluation wrote
it against the same score recomputed from what the run delivered and the citation ids, and on how many questions
it delivered something else than the run before it. No question text, no model call.

    .venv/Scripts/python.exe output/research/2026-10-18-is-something-off/runs_are_real.py
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
from harness import questions as HQ  # noqa: E402

RUNS = ["artefact_v4__gold100__cb72000__20261015T232012Z_facets_off",
        "artefact_v4__gold100__cb72000__20261016T013552Z_influence_question",
        "artefact_v4__gold100__cb72000__20261017T023109Z_person_edges",
        "artefact_v4__gold100__cb72000__20261017T035222Z_clean",
        "artefact_v4__gold100__cb72000__20261017T211157Z_4combo",
        "artefact_v4__gold100__cb72000__20261018T013811Z_knee_clouds"]
cites = {q.id: {str(c) for c in q.citations} for q in HQ.load_questions()}
now = {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest()[:12]
       for name in ("test/arms/artefact_v4.py", "test/artefact/v4_walk.py")}
print(f"the code on disk now: arm {now['test/arms/artefact_v4.py']}, arithmetic {now['test/artefact/v4_walk.py']}")
before = None
for run in RUNS:
    folder = REPO / "output/k=chars" / run
    rows = [json.loads(l) for l in (folder / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    shas = rows[0]["meta"]["provenance"]["source_sha256"]
    arm = shas.get("test/arms/artefact_v4.py", "-")[:12]
    walk = shas.get("test/artefact/v4_walk.py", "-")[:12]
    written = [json.loads(l)["value"] for l in (folder / "eval_results.jsonl").read_text(encoding="utf-8").splitlines()
               if l.strip() and json.loads(l)["metric"] == "context_recall_id"]
    delivered = {r["id"]: set(map(str, r["context_ids"])) for r in rows}
    redone = [len(delivered[q] & cites[q]) / len(cites[q]) for q in delivered]
    changed = "-" if before is None else sum(delivered[q] != before[q] for q in delivered)
    print(f"{run.split('__')[-1]}: arm {arm}, arithmetic {walk}; context_recall_id written "
          f"{sum(written) / len(written):.4f}, recomputed {sum(redone) / len(redone):.4f}; questions delivered "
          f"differently from the run above: {changed}")
    before = delivered
