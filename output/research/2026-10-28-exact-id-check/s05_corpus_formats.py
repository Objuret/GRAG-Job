"""Learn the formats of the corpus's machine identifiers. Prints only generalised signatures
(regex-like) with counts, never a value: a token is printed literally only when it is the same
in at least 95 % of the values of that kind at that position (a fixed part of the format)."""
import glob
import json
import re
from collections import Counter, defaultdict

ROOT = "C:/Coding/exjobbet/GRAG-Job/data/corpus/Salesforce__HERB"

TOK = re.compile(r"[A-Za-z0-9]+|[^A-Za-z0-9]+")


def cls(tok):
    if tok.isdigit():
        return r"\d"
    if re.fullmatch(r"[0-9a-f]+", tok):
        return "[0-9a-f]"
    if re.fullmatch(r"[a-z]+", tok):
        return "[a-z]"
    if re.fullmatch(r"[A-Z]+", tok):
        return "[A-Z]"
    if re.fullmatch(r"[A-Za-z]+", tok):
        return "[A-Za-z]"
    if re.fullmatch(r"[a-z0-9]+", tok):
        return "[a-z0-9]"
    if re.fullmatch(r"[A-Z0-9]+", tok):
        return "[A-Z0-9]"
    return "[A-Za-z0-9]"


def signatures(values):
    """Group values by their token-class sequence, then within a group print a token literally
    when it is fixed (>= 95 %), otherwise as its class with the length range."""
    groups = defaultdict(list)
    for v in values:
        toks = TOK.findall(v)
        key = tuple("SEP:" + t if not t[0].isalnum() else cls(t) for t in toks)
        groups[key].append(toks)
    out = []
    for key, members in groups.items():
        n = len(members)
        parts = []
        for i, k in enumerate(key):
            col = [m[i] for m in members]
            top, cnt = Counter(col).most_common(1)[0]
            if k.startswith("SEP:"):
                if cnt == n:
                    parts.append(re.escape(top))
                else:
                    parts.append("[^A-Za-z0-9]+")
            elif cnt >= 0.95 * n and n >= 5:
                parts.append(re.escape(top))
            else:
                lo, hi = min(map(len, col)), max(map(len, col))
                parts.append(f"{k}{{{lo}}}" if lo == hi else f"{k}{{{lo},{hi}}}")
        out.append((n, "".join(parts)))
    return sorted(out, reverse=True)


kinds = defaultdict(list)

emp = json.load(open(f"{ROOT}/metadata/employee.json", encoding="utf-8"))
for key, e in emp.items():
    kinds["employee.json key"].append(key)
    kinds["employee.json employee_id"].append(e["employee_id"])
for c in json.load(open(f"{ROOT}/metadata/customers_data.json", encoding="utf-8")):
    kinds["customer id"].append(c["id"])


def team_ids(v):
    if isinstance(v, dict):
        if "employee_id" in v:
            yield v["employee_id"]
        for x in v.values():
            yield from team_ids(x)
    elif isinstance(v, list):
        for x in v:
            yield from team_ids(x)


kinds["salesforce_team employee_id"] = list(team_ids(json.load(open(f"{ROOT}/metadata/salesforce_team.json", encoding="utf-8"))))

for fp in sorted(glob.glob(f"{ROOT}/products/*.json")):
    d = json.load(open(fp, encoding="utf-8"))
    for r in d.get("documents", []):
        kinds["document id"].append(r["id"])
        kinds["document author"].append(r["author"])
        kinds["document document_link"].append(r["document_link"])
        kinds["document date"].append(r["date"])
    for r in d.get("meeting_chats", []):
        kinds["meeting_chat id"].append(r["id"])
    for r in d.get("meeting_transcripts", []):
        kinds["meeting_transcript id"].append(r["id"])
        kinds["meeting_transcript participant"].extend(r["participants"])
    for r in d.get("prs", []):
        kinds["pr id"].append(r["id"])
        kinds["pr link"].append(r["link"])
        kinds["pr number"].append(r["number"])
        kinds["pr user.login"].append(r["user"]["login"])
        for rv in r.get("reviews", []):
            kinds["pr review user.login"].append(rv["user"]["login"])
    for r in d.get("slack", []):
        kinds["slack id"].append(r["id"])
        kinds["slack channelID"].append(r["Channel"]["channelID"])
        kinds["slack userId"].append(r["Message"]["User"]["userId"])
        kinds["slack utterranceID"].append(r["Message"]["User"]["utterranceID"])
        kinds["slack timestamp"].append(r["Message"]["User"]["timestamp"])
        for t in r.get("ThreadReplies", []):
            kinds["slack thread reply (type)"].append(type(t).__name__)
    for r in d.get("urls", []):
        kinds["url id"].append(r["id"])
        kinds["url link"].append(r["link"])

for k in sorted(kinds):
    vals = [str(v) for v in kinds[k]]
    print(f"== {k}: {len(vals)} values, {len(set(vals))} distinct")
    for n, sig in signatures(vals)[:8]:
        print(f"   {n:6d}  {sig}")
