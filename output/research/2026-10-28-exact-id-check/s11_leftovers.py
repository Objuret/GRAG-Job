"""What else the references hold that is not counted: the leftover identifier-like tokens and
names (employee, customer, company, channel names). Counts and signatures only."""
import glob
import json
import re
from collections import Counter

from common import CORPUS, corpus_identifiers, question_set, questions, reference

qs = questions()
ids = question_set()
refs = {i: reference(qs[i]) for i, _ in ids}

# the join does not split or make an identifier: per part and joined give the same identifiers
RX = [r"(?<![A-Za-z0-9_])eid_[0-9a-f]{7,8}(?![A-Za-z0-9_])", r"(?<![A-Za-z0-9_])CUST-\d{4}(?![A-Za-z0-9_])",
      r"https?://[^\s<>\"'\[\]()]+"]
same = 0
for i, _ in ids:
    joined = sorted(m for rx in RX for m in re.findall(rx, refs[i]))
    parts = sorted(m for rx in RX for g in qs[i]["ground_truth"] for m in re.findall(rx, str(g)))
    same += joined == parts
print("questions where per-part and joined extraction agree:", same, "of", len(ids))

kinds = corpus_identifiers()
all_ids = set().union(*kinds.values())
channel_names, emp_names, cust_names, companies = set(), set(), set(), set()
emp = json.load(open(f"{CORPUS}/metadata/employee.json", encoding="utf-8"))
emp_names = {e["name"] for e in emp.values()}
for c in json.load(open(f"{CORPUS}/metadata/customers_data.json", encoding="utf-8")):
    cust_names.add(c["name"])
    companies.add(c["company"])
for fp in sorted(glob.glob(f"{CORPUS}/products/*.json")):
    d = json.load(open(fp, encoding="utf-8"))
    for r in d.get("slack", []):
        channel_names.add(r["Channel"]["name"])

covered = re.compile("|".join(f"(?:{rx})" for rx in RX))
LOOK = re.compile(r"\b(?=[A-Za-z0-9_\-./:]*[0-9_])(?=[A-Za-z0-9_\-./:]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9_\-./:]*[A-Za-z0-9]\b")
left = Counter()
for i, r in refs.items():
    for tok in LOOK.findall(covered.sub(" ", r)):
        left["tokens"] += 1
        left["a corpus identifier value"] += tok in all_ids
        left["a channel name"] += tok in channel_names
        left["part of a channel name"] += any(tok in c for c in channel_names)
        left["in the question too"] += tok in qs[i]["question"]
print("leftover identifier-like tokens:", dict(left))


def count_refs(names, label):
    names = {n for n in names if n and len(n) > 2}
    n_refs = 0
    n_hits = 0
    for i, r in refs.items():
        h = [n for n in names if re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", r)]
        n_refs += bool(h)
        n_hits += len(h)
    print(f"  {label:16s} distinct values={len(names):5d} references holding one={n_refs:4d} names found={n_hits:5d}")


print("names in the references (not counted as identifiers in this check):")
count_refs(emp_names, "employee names")
count_refs(cust_names, "customer names")
count_refs(companies, "company names")
count_refs(channel_names, "channel names")
print("channel name signature classes:", Counter(
    "has digit" if re.search(r"\d", c) else "letters and separators" for c in channel_names))
