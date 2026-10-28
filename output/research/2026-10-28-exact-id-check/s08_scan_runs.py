"""For each arm and each question holding reference identifiers: is each identifier in the row's
contexts and in the row's answer. Four readings: exact substring, exact whole token,
case-insensitive substring, case-insensitive whole token. Also checks that the contexts are the
texts the answer model read (the recorded answer-call prompt). Writes flags to a scratch pickle;
prints only counts."""
import hashlib
import json
import pickle
import re
import sys
from collections import Counter

sys.path.insert(0, "C:/Coding/exjobbet/GRAG-Job/prod")
from harness.contract import generator_user_content  # noqa: E402

from common import ARMS, RUNS, RUNS_DIR, question_set, questions, read_jsonl  # noqa: E402

SCR = "C:/Users/jocke/AppData/Local/Temp/claude/c--Coding-exjobbet-GRAG-Job/9c164e78-008e-41e9-85f3-58c55027a64c/scratchpad/exact_check"
per_q = pickle.load(open(f"{SCR}/ref_identifiers.pkl", "rb"))
qs = questions()
set_of = dict(question_set())

BEFORE = r"(?<![A-Za-z0-9_])"
AFTER_ID = r"(?![A-Za-z0-9_])"
AFTER_URL = r"(?![A-Za-z0-9_\-])(?![/?#.%=&~+:@][A-Za-z0-9_\-])"
compiled = {}


def rx(v, kind, ci):
    key = (v, kind, ci)
    if key not in compiled:
        after = AFTER_URL if kind in ("PR link", "other URL") else AFTER_ID
        compiled[key] = re.compile(BEFORE + re.escape(v) + after, re.I if ci else 0)
    return compiled[key]


def flags(v, kind, text, low):
    return {
        "plain": v in text,
        "plain_ci": v.lower() in low,
        "tok": bool(rx(v, kind, False).search(text)),
        "tok_ci": bool(rx(v, kind, True).search(text)),
    }


def probe(v, kind, text):
    """Letter-for-letter misses of a near form, counted only."""
    out = {}
    if kind == "other URL" and v.endswith("/"):
        out["url_without_trailing_slash"] = bool(rx(v.rstrip("/"), kind, False).search(text))
    if kind in ("PR link", "other URL"):
        bare = re.sub(r"^https?://", "", v)
        out["url_without_scheme"] = bool(re.search(r"(?<![A-Za-z0-9_/.])" + re.escape(bare)
                                                   + AFTER_URL, text))
    return out


results = {}  # (arm, qid) -> {"ctx": [flags...], "ans": [...], "kinds": [...], "probe_ctx": [...], "probe_ans": [...]}
checks = {}
for (arm, set_name), run in RUNS.items():
    c = Counter()
    rec_hash = {}
    for r in read_jsonl(f"{RUNS_DIR}/{run}/arm_outputs.as_recorded.jsonl"):
        rec_hash[r["id"]] = hashlib.sha256(json.dumps([r["contexts"], r["answer"]]).encode()).hexdigest()
    seen = set()
    for r in read_jsonl(f"{RUNS_DIR}/{run}/arm_outputs.jsonl"):
        qid = r["id"]
        seen.add(qid)
        c["rows"] += 1
        c["row in its set"] += set_of.get(qid) == set_name
        c["question text as in questions.jsonl"] += r["question"] == qs[qid]["question"]
        c["contexts and answer as recorded"] += rec_hash.get(qid) == hashlib.sha256(
            json.dumps([r["contexts"], r["answer"]]).encode()).hexdigest()
        c["empty answer"] += not (r["answer"] or "").strip()
        ctxs = list(r["contexts"] or [])
        order = (r.get("meta") or {}).get("reading_order")
        if arm == "artefact":
            ok = isinstance(order, list) and sorted(order) == list(range(len(ctxs)))
            c["reading_order a permutation of the contexts"] += ok
            read = [ctxs[n] for n in order] if ok else ctxs
        else:
            read = ctxs
        expected = generator_user_content(r["question"], read)
        answer_calls = [x for x in (r.get("calls") or []) if x.get("role") == "answer"]
        c["rows with an answer call recorded"] += bool(answer_calls)
        c["answer-call prompt == Documents + contexts read + question"] += any(
            x.get("prompt") == expected for x in answer_calls)
        if not per_q[qid]:
            continue
        joined = "\n\n".join(ctxs)
        jlow = joined.lower()
        ans = r["answer"] or ""
        alow = ans.lower()
        entry = {"kinds": [], "ctx": [], "ans": [], "probe_ctx": [], "probe_ans": [],
                 "ctx_any_single": []}
        for v, kind in per_q[qid].items():
            entry["kinds"].append(kind)
            entry["ctx"].append(flags(v, kind, joined, jlow))
            entry["ans"].append(flags(v, kind, ans, alow))
            entry["probe_ctx"].append(probe(v, kind, joined))
            entry["probe_ans"].append(probe(v, kind, ans))
            entry["ctx_any_single"].append(any(v in t for t in ctxs))
        results[(arm, qid)] = entry
    c["ids missing from the run"] = sum(1 for q, s in set_of.items() if s == set_name and q not in seen)
    checks[(arm, set_name)] = dict(c)

for k, v in checks.items():
    print(k, v)

# the plain substring in the joined contexts and in any single context agree?
dis = sum(1 for e in results.values() for f, s in zip(e["ctx"], e["ctx_any_single"]) if f["plain"] != s)
print("identifier checks where joined contexts and single contexts disagree:", dis)
pickle.dump(results, open(f"{SCR}/run_flags.pkl", "wb"))
print("flags written (scratch): run_flags.pkl,", len(results), "arm-question entries")
