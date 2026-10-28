"""Completeness check, counts only: for each set of corpus id values, how many of the 815
references hold a member of it as a whole token, and how many of those members the patterns of
exact_check.py did not take."""
import json
import glob
import re
from collections import defaultdict

REPO = "C:/Coding/exjobbet/GRAG-Job"
ROOT = f"{REPO}/data/corpus/Salesforce__HERB"
sets = defaultdict(set)
for f in glob.glob(f"{ROOT}/products/*.json"):
    p = json.load(open(f, encoding="utf-8"))
    for r in p.get("slack", []):
        sets["slack record id / utterranceID"].add(r["id"])
        sets["slack record id / utterranceID"].add(r["Message"]["User"]["utterranceID"])
        sets["slack channelID"].add(r["Channel"]["channelID"])
        sets["person ids in records (userId, author, participants, logins)"].add(r["Message"]["User"]["userId"])
    for r in p.get("documents", []):
        sets["documents id"].add(r["id"])
        sets["links (document_link, urls.link, prs.link)"].add(r["document_link"])
        sets["person ids in records (userId, author, participants, logins)"].add(r["author"])
    for r in p.get("meeting_transcripts", []):
        sets["meeting ids (transcripts, chats)"].add(r["id"])
        for x in r["participants"]:
            sets["person ids in records (userId, author, participants, logins)"].add(x)
    for r in p.get("meeting_chats", []):
        sets["meeting ids (transcripts, chats)"].add(r["id"])
    for r in p.get("urls", []):
        sets["urls id"].add(r["id"])
        sets["links (document_link, urls.link, prs.link)"].add(r["link"])
    for r in p.get("prs", []):
        sets["prs id"].add(r["id"])
        sets["links (document_link, urls.link, prs.link)"].add(r["link"])
        sets["person ids in records (userId, author, participants, logins)"].add(r["user"]["login"])
        for rv in r["reviews"]:
            sets["person ids in records (userId, author, participants, logins)"].add(rv["user"]["login"])
for k in json.load(open(f"{ROOT}/metadata/employee.json", encoding="utf-8")):
    sets["employee.json ids"].add(k)
for c in json.load(open(f"{ROOT}/metadata/customers_data.json", encoding="utf-8")):
    sets["customers_data.json ids"].add(c["id"])

URL = re.compile(r"https?://[^\s<>\"'()\[\]{}]+")
EMPLOYEE_ID = re.compile(r"(?<![A-Za-z0-9_])eid_[0-9a-f]{8}(?![A-Za-z0-9])")
CUSTOMER_ID = re.compile(r"(?<![A-Za-z0-9])CUST-\d{4}(?![0-9])")
TOKEN = re.compile(r"[A-Za-z0-9_\-./:']+")

questions = {}
for line in open(f"{REPO}/data/questions.jsonl", encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        questions[r["id"]] = r
qids = [json.loads(l)["id"] for f in ("gold100", "answerable715")
        for l in open(f"{REPO}/data/{f}.jsonl", encoding="utf-8") if l.strip()]

for name, members in sets.items():
    refs_with, not_taken = 0, 0
    for q in qids:
        ref = " ".join(questions[q]["ground_truth"])
        taken = {m.group(0).rstrip(".,;:!?") for m in URL.finditer(ref)}
        taken |= set(EMPLOYEE_ID.findall(ref)) | set(CUSTOMER_ID.findall(ref))
        toks = {t.strip(".,;:!?'") for t in TOKEN.findall(ref)} | {m.group(0).rstrip(".,;:!?") for m in URL.finditer(ref)}
        hit = toks & members
        if hit:
            refs_with += 1
            not_taken += len(hit - taken)
    print(f"  {name:62s} size={len(members):6d} references holding a member={refs_with:4d} members not taken={not_taken}")
