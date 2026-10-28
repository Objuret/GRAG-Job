"""Shared loading for the exact-identifier check. Nothing here prints a value."""
import glob
import json
import re
from collections import defaultdict

REPO = "C:/Coding/exjobbet/GRAG-Job"
CORPUS = f"{REPO}/data/corpus/Salesforce__HERB"
RUNS_DIR = f"{REPO}/output/k=chars"
RUNS = {
    ("artefact", "gold100"): "artefact_v4__gold100__cb72000__20261023T021439Z",
    ("lucene", "gold100"): "lucene__gold100__cb72000__20261008T234209Z",
    ("vector", "gold100"): "vector__gold100__cb72000__20261017T061242Z",
    ("artefact", "answerable715"): "artefact_v4__answerable715__cb72000__20261025T211532Z",
    ("lucene", "answerable715"): "lucene__answerable715__cb72000__20261023T112745Z",
    ("vector", "answerable715"): "vector__answerable715__cb72000__20261024T004317Z",
}
ARMS = ("artefact", "lucene", "vector")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def question_set():
    """The 815 ids (gold100 then answerable715), each with its set name; checks they are disjoint."""
    ids = []
    for name in ("gold100", "answerable715"):
        for r in read_jsonl(f"{REPO}/data/{name}.jsonl"):
            ids.append((r["id"], name))
    assert len(ids) == len({i for i, _ in ids}), "the two sets overlap"
    return ids


def questions():
    return {r["id"]: r for r in read_jsonl(f"{REPO}/data/questions.jsonl")}


def reference(q):
    # what RAGAS was given: prod/eval/ragas.py _to_sample, reference=" ".join(gold)
    return " ".join(str(g) for g in (q["ground_truth"] or []))


def corpus_identifiers():
    """Every machine identifier the corpus holds, by kind: kind -> set of values."""
    kinds = defaultdict(set)
    emp = json.load(open(f"{CORPUS}/metadata/employee.json", encoding="utf-8"))
    for key, e in emp.items():
        kinds["employee id"].add(key)
        kinds["employee id"].add(e["employee_id"])
    for c in json.load(open(f"{CORPUS}/metadata/customers_data.json", encoding="utf-8")):
        kinds["customer id"].add(c["id"])

    def team_ids(v):
        if isinstance(v, dict):
            if "employee_id" in v:
                yield v["employee_id"]
            for x in v.values():
                yield from team_ids(x)
        elif isinstance(v, list):
            for x in v:
                yield from team_ids(x)

    for t in team_ids(json.load(open(f"{CORPUS}/metadata/salesforce_team.json", encoding="utf-8"))):
        kinds["employee id"].add(t)
    for fp in sorted(glob.glob(f"{CORPUS}/products/*.json")):
        d = json.load(open(fp, encoding="utf-8"))
        for r in d.get("documents", []):
            kinds["document id"].add(r["id"])
            kinds["document link"].add(r["document_link"])
            kinds["employee id"].add(r["author"])
        for r in d.get("meeting_chats", []):
            kinds["meeting chat id"].add(r["id"])
        for r in d.get("meeting_transcripts", []):
            kinds["meeting transcript id"].add(r["id"])
            kinds["employee id"].update(r["participants"])
        for r in d.get("prs", []):
            kinds["pr id"].add(r["id"])
            kinds["pr link"].add(r["link"])
            kinds["pr login"].add(r["user"]["login"])
            for rv in r.get("reviews", []):
                kinds["pr login"].add(rv["user"]["login"])
        for r in d.get("slack", []):
            kinds["slack message id"].add(r["id"])
            kinds["slack message id"].add(r["Message"]["User"]["utterranceID"])
            kinds["slack channel id"].add(r["Channel"]["channelID"])
            kinds["slack user id"].add(r["Message"]["User"]["userId"])
        for r in d.get("urls", []):
            kinds["url id"].add(r["id"])
            kinds["url link"].add(r["link"])
    return {k: {str(v) for v in vs} for k, vs in kinds.items()}
