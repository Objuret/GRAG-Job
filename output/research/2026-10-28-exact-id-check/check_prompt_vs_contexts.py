"""Cross-check, counts only: for every reference identifier, is its presence (exact substring) in
the row's contexts the same as in the prompt the answer call recorded (the row's calls entry with
role 'answer')? Also: does any answer call's system prompt hold one of the identifiers?"""
import json
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0])
import importlib.util

spec = importlib.util.spec_from_file_location(
    "ec", __file__.replace("check_prompt_vs_contexts.py", "exact_check_lib.py"))

REPO = "C:/Coding/exjobbet/GRAG-Job"
RUNS = {
    "artefact": ["artefact_v4__gold100__cb72000__20261023T021439Z",
                 "artefact_v4__answerable715__cb72000__20261025T211532Z"],
    "lucene": ["lucene__gold100__cb72000__20261008T234209Z",
               "lucene__answerable715__cb72000__20261023T112745Z"],
    "vector": ["vector__gold100__cb72000__20261017T061242Z",
               "vector__answerable715__cb72000__20261024T004317Z"],
}
import re
URL = re.compile(r"https?://[^\s<>\"'()\[\]{}]+")
PR_LINK = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+")
EMPLOYEE_ID = re.compile(r"(?<![A-Za-z0-9_])eid_[0-9a-f]{8}(?![A-Za-z0-9])")
CUSTOMER_ID = re.compile(r"(?<![A-Za-z0-9])CUST-\d{4}(?![0-9])")


def extract(ref):
    found, masked = [], ref
    for m in URL.finditer(ref):
        found.append(m.group(0).rstrip(".,;:!?"))
        masked = masked[:m.start()] + " " * (m.end() - m.start()) + masked[m.end():]
    found += EMPLOYEE_ID.findall(masked) + CUSTOMER_ID.findall(masked)
    return list(dict.fromkeys(found))


questions = {}
for line in open(f"{REPO}/data/questions.jsonl", encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        questions[r["id"]] = r
qids = [json.loads(l)["id"] for f in ("gold100", "answerable715")
        for l in open(f"{REPO}/data/{f}.jsonl", encoding="utf-8") if l.strip()]
idents = {q: extract(" ".join(questions[q]["ground_truth"])) for q in qids}
idents = {q: v for q, v in idents.items() if v}

for arm, runs in RUNS.items():
    c = Counter()
    for run in runs:
        with open(f"{REPO}/output/k=chars/{run}/arm_outputs.jsonl", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row["id"] not in idents:
                    continue
                calls = [x for x in row["calls"] if x.get("role") == "answer"]
                c["answer calls per row = %d" % len(calls)] += 1
                prompt = calls[0]["prompt"]
                system = calls[0].get("system") or ""
                ctx = "\n\n".join(row["contexts"])
                c["contexts joined stand in the prompt (any order)"] += all(t in prompt for t in row["contexts"])
                for i in idents[row["id"]]:
                    c["identifiers"] += 1
                    a, b = i in ctx, i in prompt
                    c["ctx yes, prompt yes" if a and b else "ctx no, prompt no" if not a and not b
                      else "ctx yes, prompt no" if a else "ctx no, prompt yes"] += 1
                    c["in the system prompt"] += i in system
    print(arm, dict(c))
