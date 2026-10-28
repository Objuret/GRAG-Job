"""Learn the formats of the corpus's id and link fields. Prints only generalized shapes and counts:
a token that is shared by at least 20% of a field's values at the same place is kept literal
(a pattern element like a prefix, a host or a path word); every other token becomes its class."""
import json
import glob
import re
from collections import Counter, defaultdict

ROOT = "C:/Coding/exjobbet/GRAG-Job/data/corpus/Salesforce__HERB"

values = defaultdict(list)  # field -> list of string values

for f in glob.glob(f"{ROOT}/products/*.json"):
    p = json.load(open(f, encoding="utf-8"))
    for r in p.get("slack", []):
        values["slack.Channel.channelID"].append(r["Channel"]["channelID"])
        values["slack.Message.User.userId"].append(r["Message"]["User"]["userId"])
        values["slack.Message.User.utterranceID"].append(r["Message"]["User"]["utterranceID"])
        values["slack.id"].append(r["id"])
        for t in r.get("ThreadReplies") or []:
            values["slack.ThreadReplies.keys"].append(",".join(sorted(t.keys())) if isinstance(t, dict) else type(t).__name__)
    for r in p.get("documents", []):
        values["documents.id"].append(r["id"])
        values["documents.document_link"].append(r["document_link"])
        values["documents.author"].append(r["author"])
    for r in p.get("meeting_transcripts", []):
        values["meeting_transcripts.id"].append(r["id"])
        for x in r["participants"]:
            values["meeting_transcripts.participants[]"].append(x)
    for r in p.get("meeting_chats", []):
        values["meeting_chats.id"].append(r["id"])
    for r in p.get("urls", []):
        values["urls.id"].append(r["id"])
        values["urls.link"].append(r["link"])
    for r in p.get("prs", []):
        values["prs.id"].append(r["id"])
        values["prs.link"].append(r["link"])
        values["prs.number"].append(str(r["number"]))
        values["prs.user.login"].append(r["user"]["login"])
        for rv in r["reviews"]:
            values["prs.reviews[].user.login"].append(rv["user"]["login"])

emp = json.load(open(f"{ROOT}/metadata/employee.json", encoding="utf-8"))
for k, v in emp.items():
    values["employee.json key"].append(k)
    values["employee.json employee_id"].append(v["employee_id"])
cust = json.load(open(f"{ROOT}/metadata/customers_data.json", encoding="utf-8"))
for c in cust:
    values["customers_data.json id"].append(c["id"])


def walk_team(o):
    if isinstance(o, dict):
        if "employee_id" in o:
            values["salesforce_team.json employee_id"].append(o["employee_id"])
        for v in o.values():
            walk_team(v)
    elif isinstance(o, list):
        for v in o:
            walk_team(v)


walk_team(json.load(open(f"{ROOT}/metadata/salesforce_team.json", encoding="utf-8")))

SPLIT = re.compile(r"([^A-Za-z0-9]+)")


def tok_class(t):
    if re.fullmatch(r"\d+", t):
        return r"\d{%d}" % len(t)
    if re.fullmatch(r"[0-9a-f]+", t) and re.search(r"\d", t) and re.search(r"[a-f]", t):
        return "[0-9a-f]{%d}" % len(t)
    if re.fullmatch(r"[a-z]+", t):
        return "[a-z]+"
    if re.fullmatch(r"[A-Z]+", t):
        return "[A-Z]+"
    if re.fullmatch(r"[A-Za-z]+", t):
        return "[A-Za-z]+"
    if re.fullmatch(r"[A-Za-z0-9]+", t):
        return "[A-Za-z0-9]+"
    return "?"


for field, vals in values.items():
    n = len(vals)
    distinct = len(set(vals))
    if field.endswith(".keys"):
        print(f"\n## {field}: n={n}", Counter(vals).most_common(5))
        continue
    toks = [SPLIT.split(v) for v in vals]
    # literal tokens: shared by >= 20% of values at the same position (and position count)
    pos_counts = defaultdict(Counter)
    for ts in toks:
        for i, t in enumerate(ts):
            pos_counts[(len(ts), i)][t] += 1
    shapes = Counter()
    for ts in toks:
        L = len(ts)
        out = []
        for i, t in enumerate(ts):
            if i % 2 == 1:  # separator
                out.append(re.escape(t))
                continue
            if t == "":
                continue
            share = pos_counts[(L, i)][t] / max(1, sum(pos_counts[(L, i)].values()))
            total_same_len = sum(pos_counts[(L, i)].values())
            if share >= 0.2 and total_same_len >= 50 and re.fullmatch(r"[A-Za-z]+", t):
                out.append(re.escape(t))
            else:
                out.append(tok_class(t))
        shapes["".join(out)] += 1
    print(f"\n## {field}: n={n} distinct={distinct} shapes={len(shapes)}")
    for s, c in shapes.most_common(12):
        print(f"  {c:6d}  {s}")
