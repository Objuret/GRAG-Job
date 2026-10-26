"""The new contents_handed_over against the committed one: identical on every row the old one
takes, and no raise on the rows it stopped on. Counts only."""
import json
import subprocess
import sys
import types
from pathlib import Path

repo = Path(sys.argv[1])
sys.path[:0] = [str(repo / "prod")]
import eval.ragas as new  # noqa: E402

old_src = subprocess.run(["git", "-C", str(repo), "show", "4518897:prod/eval/ragas.py"],
                         capture_output=True, text=True, encoding="utf-8").stdout
old = types.ModuleType("old_ragas")
old.__dict__["__name__"] = "old_ragas"
sys.modules["old_ragas"] = old
exec(compile(old_src, "old_ragas.py", "exec"), old.__dict__)

records_new = new.corpus_records(repo / "data" / "corpus" / "Salesforce__HERB")
records_old = old.corpus_records(repo / "data" / "corpus" / "Salesforce__HERB")
for run in sys.argv[2:]:
    same = differ = old_raise = new_raise = 0
    for line in (Path(run) / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        try:
            a = old.contents_handed_over(r["contexts"], r["context_ids"], r.get("meta"), records_old)
        except ValueError:
            a = None
            old_raise += 1
        try:
            b = new.contents_handed_over(r["contexts"], r["context_ids"], r.get("meta"), records_new)
        except ValueError:
            new_raise += 1
            continue
        if a is not None:
            same += a == b
            differ += a != b
    print(f"{Path(run).name}: same {same}, differ {differ}, old raised {old_raise}, new raises {new_raise}")
