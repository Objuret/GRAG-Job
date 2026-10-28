"""Counts only: by question type, how many references hold each identifier kind; and, for the
one token of shape [A-Z]+-\\d{3}, whether the corpus holds it as an id field value and in how
many records' text it stands. Also checks for slack-message-id-shaped tokens with all-digit
parts, which the candidate rule of scan_reference_shapes.py does not catch."""
import json
import glob
import re
from collections import Counter

REPO = "C:/Coding/exjobbet/GRAG-Job"
ROOT = f"{REPO}/data/corpus/Salesforce__HERB"
q = {}
for line in open(f"{REPO}/data/questions.jsonl", encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        q[r["id"]] = r
ids = [json.loads(l)["id"] for f in ("gold100", "answerable715")
       for l in open(f"{REPO}/data/{f}.jsonl", encoding="utf-8") if l.strip()]

KINDS = {
    "employee_id": re.compile(r"(?<![A-Za-z0-9_])eid_[0-9a-f]{8}(?![A-Za-z0-9])"),
    "pr_link": re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+"),
    "customer_id": re.compile(r"(?<![A-Za-z0-9])CUST-\d{4}(?![0-9])"),
    "any_url": re.compile(r"https?://\S+"),
    "odd": re.compile(r"(?<![A-Za-z0-9_\-])[A-Z]+-\d{3}(?![A-Za-z0-9])"),
    "slack_msg_id": re.compile(r"(?<![0-9])\d{8}-\d{1,3}-[0-9a-z]{5,6}(?![A-Za-z0-9])"),
    "emp_login": re.compile(r"EMP_\d{6,12}"),
}
tab = Counter()
odd_tokens = set()
for qid in ids:
    r = q[qid]
    ref = " ".join(r["ground_truth"])
    for k, rx in KINDS.items():
        found = rx.findall(ref)
        if found:
            tab[(k, r["type"])] += 1
            if k == "odd":
                odd_tokens.update(found)
for (k, t), c in sorted(tab.items()):
    print(f"  kind={k:13s} type={t:8s} references={c}")

print("odd tokens distinct:", len(odd_tokens))
# where does the odd token stand in the corpus?
id_values = set()
text_hits = Counter()
for f in glob.glob(f"{ROOT}/products/*.json"):
    p = json.load(open(f, encoding="utf-8"))
    for kind, recs in p.items():
        for rec in recs:
            if isinstance(rec, dict) and "id" in rec:
                id_values.add(rec["id"])
            s = json.dumps(rec, ensure_ascii=False)
            for t in odd_tokens:
                if t in s:
                    text_hits[kind] += 1
for f in glob.glob(f"{ROOT}/metadata/*.json"):
    s = open(f, encoding="utf-8").read()
    for t in odd_tokens:
        if t in s:
            text_hits["metadata"] += 1
print("odd token equal to a corpus record id:", any(t in id_values for t in odd_tokens))
print("records whose JSON holds the odd token, by kind:", dict(text_hits))
print("odd token: letters", [len(t.split('-')[0]) for t in odd_tokens])
