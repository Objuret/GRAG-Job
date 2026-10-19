"""Which hundred a gold run reads, against what the earlier baseline runs recorded. Ids file hash and counts only."""
import glob
import hashlib
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[3]
f = REPO / "data" / "gold100.jsonl"
ids = [json.loads(x)["id"] for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
print(f"data/gold100.jsonl: {len(ids)} ids, {len(set(ids))} distinct, sha256 {hashlib.sha256(f.read_bytes()).hexdigest()}")
print(f"data/questions.jsonl sha256 {hashlib.sha256((REPO / 'data' / 'questions.jsonl').read_bytes()).hexdigest()}")
for d in sorted(glob.glob(str(REPO / "output" / "k=chars" / "*__gold100__cb72000__*"))):
    name = Path(d).name
    if not name.startswith(("lucene__", "vector__")):
        continue
    try:
        m = json.loads((Path(d) / "run_manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        continue
    inp = m.get("inputs") or {}
    done = [json.loads(x)["id"] for x in (Path(d) / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    print(f"{name}: ids sha {inp.get('ids_sha256')} | questions sha {str(inp.get('questions_sha256'))[:16]} | "
          f"workers {m.get('workers')} | rows {len(done)} | same ids as data/gold100.jsonl, same order: {done == ids} | same set: {set(done) == set(ids)}")
