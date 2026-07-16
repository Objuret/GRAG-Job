"""model_test.py — 3-question head-to-head: the full artefact_v1 pipeline
(interpret + generate) on one model, RAGAS-judged with the standard qwen judge.

Run each leg from v3/ (same harness UX as run.py — progress bar, q to abort,
resume on re-run):

    python model_test.py glm
    python model_test.py qwen

Question ids live in model_test_ids.jsonl; output lands in
output/artefact_v1__modeltest3_<leg>/.
"""
import importlib
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
os.chdir(_HERE)

label = sys.argv[1] if len(sys.argv) > 1 else ""
MODELS = {"glm": "z-ai/glm-5.2", "qwen": "qwen/qwen3.5-397b-a17b"}
if label not in MODELS:
    sys.exit(f"usage: python model_test.py {{{'|'.join(MODELS)}}} [workers]")
workers = int(sys.argv[2]) if len(sys.argv) > 2 else 1
model = MODELS[label]
os.environ["HERB_INTERPRET_MODEL"] = model  # read at pipeline import

import abort
import nim
nim._load_dotenv()
import orchestrator
import eval.ragas as scorer
from run_lock import RunLock

pipeline = importlib.import_module("pipelines.artefact_v1")
ids_file = _HERE / "model_test_ids.jsonl"
out_dir = _HERE / "output" / f"artefact_v1__modeltest3_{label}"
config = {"top_k": 50, "workers": 1, "out_dir": str(out_dir),
          "retrieval_only": False, "generator_model": model}

print(f"{label}: interpret+generate on {model} | judge {scorer.JUDGE_MODEL} | k=50"
      f"\n  ->  {out_dir}")
abort.watch()
print("running - press q to abort\n")
with RunLock(out_dir):
    summary = orchestrator.run(pipeline, scorer, ids_file, config)
print(json.dumps(summary, indent=1, default=str))
