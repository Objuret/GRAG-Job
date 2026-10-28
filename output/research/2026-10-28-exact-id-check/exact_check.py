"""Exact, entity-level check over the 815 questions (gold100 + answerable715 as one set), three
arms, no model call. Prints only patterns, counts and shares; never a question, answer, reference,
context, identifier, link or question id. Writes one aggregate JSON (counts only) beside itself.

An identifier is taken from the reference answer (data/questions.jsonl ground_truth, its parts
joined by one space, as prod/eval/ragas.py builds `reference`). Each identifier counts once per
question. It is looked for in the arm's delivered texts (the row's contexts, joined by a blank
line, as the answer model got them) and in the arm's answer (the row's answer):
  exact  - the identifier as a substring, letter for letter
  ci     - the same, both sides lower-cased
  whole  - exact, and the identifier is not the front part of a longer token (see BOUND)
"""
import json
import re
import statistics
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("C:/Coding/exjobbet/GRAG-Job")
OUT = Path(__file__).parent / "exact_check_counts.json"
RUNS = {
    "artefact": ["artefact_v4__gold100__cb72000__20261023T021439Z",
                 "artefact_v4__answerable715__cb72000__20261025T211532Z"],
    "lucene": ["lucene__gold100__cb72000__20261008T234209Z",
               "lucene__answerable715__cb72000__20261023T112745Z"],
    "vector": ["vector__gold100__cb72000__20261017T061242Z",
               "vector__answerable715__cb72000__20261024T004317Z"],
}

# ---- the patterns ------------------------------------------------------------------------
URL = re.compile(r"https?://[^\s<>\"'()\[\]{}]+")
URL_TRAIL = ".,;:!?"
PR_LINK = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+")
EMPLOYEE_ID = re.compile(r"(?<![A-Za-z0-9_])eid_[0-9a-f]{8}(?![A-Za-z0-9])")
CUSTOMER_ID = re.compile(r"(?<![A-Za-z0-9])CUST-\d{4}(?![0-9])")
# checks for kinds the corpus holds; none is expected in the references
EMP_LOGIN = re.compile(r"(?<![A-Za-z0-9_])EMP_\d{6,12}(?![0-9])")
SLACK_MSG_ID = re.compile(r"(?<![0-9])\d{8}-\d{1,3}-[0-9a-z]{5,6}(?![A-Za-z0-9])")
EID_LOOSE = re.compile(r"eid_[0-9a-fA-F]{6,9}", re.I)

KINDS = ("employee_id", "pr_link", "customer_id", "other_url")
BOUND_AFTER = {"employee_id": r"(?![A-Za-z0-9])", "customer_id": r"(?![0-9])",
               "pr_link": r"(?![0-9])", "other_url": r"(?![A-Za-z0-9_\-])"}
BOUND_BEFORE = {"employee_id": r"(?<![A-Za-z0-9_])", "customer_id": r"(?<![A-Za-z0-9])",
                "pr_link": "", "other_url": ""}


def extract(ref):
    """Distinct identifiers of a reference, as (kind, identifier), in first-seen order."""
    found = []
    masked = ref
    for m in URL.finditer(ref):
        u = m.group(0).rstrip(URL_TRAIL)
        kind = "pr_link" if PR_LINK.fullmatch(u) else "other_url"
        found.append((kind, u))
        masked = masked[:m.start()] + " " * (m.end() - m.start()) + masked[m.end():]
    for m in EMPLOYEE_ID.finditer(masked):
        found.append(("employee_id", m.group(0)))
    for m in CUSTOMER_ID.finditer(masked):
        found.append(("customer_id", m.group(0)))
    seen, out = set(), []
    for k, i in found:
        if i not in seen:
            seen.add(i)
            out.append((k, i))
    return out


def present(kind, ident, text, text_lower):
    exact = ident in text
    ci = ident.lower() in text_lower
    whole = bool(exact and re.search(BOUND_BEFORE[kind] + re.escape(ident) + BOUND_AFTER[kind], text))
    return {"exact": exact, "ci": ci, "whole": whole}


# ---- the questions and references --------------------------------------------------------
questions = {}
for line in open(REPO / "data/questions.jsonl", encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        questions[r["id"]] = r
qids = [json.loads(l)["id"] for f in ("gold100", "answerable715")
        for l in open(REPO / f"data/{f}.jsonl", encoding="utf-8") if l.strip()]
assert len(qids) == 815 and len(set(qids)) == 815

pattern_refs = Counter()   # references holding at least one match, per pattern
pattern_tokens = Counter()  # matches, with repeats, per pattern
check_refs = Counter()
idents = {}
odd_shape = re.compile(r"(?<![A-Za-z0-9_\-])[A-Z]+-\d{3}(?![A-Za-z0-9])")
odd_refs = 0
for qid in qids:
    ref = " ".join(questions[qid]["ground_truth"])
    ids = extract(ref)
    if ids:
        idents[qid] = ids
    kinds_here = Counter(k for k, _ in ids)
    for k in kinds_here:
        pattern_refs[k] += 1
    # matches with repeats
    urls = [m.group(0).rstrip(URL_TRAIL) for m in URL.finditer(ref)]
    pattern_tokens["pr_link"] += sum(1 for u in urls if PR_LINK.fullmatch(u))
    pattern_tokens["other_url"] += sum(1 for u in urls if not PR_LINK.fullmatch(u))
    pattern_tokens["employee_id"] += len(EMPLOYEE_ID.findall(ref))
    pattern_tokens["customer_id"] += len(CUSTOMER_ID.findall(ref))
    for name, rx in (("emp_login", EMP_LOGIN), ("slack_message_id", SLACK_MSG_ID),
                     ("eid_any_case_6_to_9", EID_LOOSE)):
        if rx.search(ref):
            check_refs[name] += 1
    if odd_shape.search(ref) and not CUSTOMER_ID.search(ref):
        odd_refs += 1

print("=== step 1: patterns in the 815 references ===")
for k in KINDS:
    print(f"  {k:12s} references with >=1: {pattern_refs[k]:4d}   matches with repeats: {pattern_tokens[k]:5d}")
print("  references with >=1 identifier of any kind:", len(idents))
print("  distinct identifiers per question, summed:", sum(len(v) for v in idents.values()))
print("  checks (references with >=1):", dict(check_refs),
      "| [A-Z]+-\\d{3} non-CUST token:", odd_refs)
print("  distinct identifiers per question, by kind:",
      dict(Counter(k for v in idents.values() for k, _ in v)))
print("  questions by number of identifiers:",
      sorted(Counter(len(v) for v in idents.values()).items()))
print("  questions holding more than one kind:",
      sum(1 for v in idents.values() if len({k for k, _ in v}) > 1))

# identifiers that also stand in the question text (the same for every arm)
in_question = {}
for qid, ids in idents.items():
    qt = questions[qid]["question"]
    for k, i in ids:
        in_question[(qid, i)] = i in qt
print("  identifiers that stand letter for letter in the question itself:",
      sum(in_question.values()), "of", len(in_question),
      dict(Counter(k for qid, ids in idents.items() for k, i in ids if in_question[(qid, i)])))


# ---- the arms ----------------------------------------------------------------------------
def load_rows(arm):
    rows = {}
    integrity = Counter()
    for run in RUNS[arm]:
        folder = REPO / "output/k=chars" / run
        rec = {}
        with open(folder / "arm_outputs.as_recorded.jsonl", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    rec[r["id"]] = hashlib.sha256(
                        json.dumps([r["answer"], r["contexts"]], ensure_ascii=False).encode()).hexdigest()
        with open(folder / "arm_outputs.jsonl", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if r["id"] in rows:
                    integrity["duplicate id"] += 1
                rows[r["id"]] = {"answer": r["answer"], "contexts": r["contexts"]}
                if r["question"] != questions[r["id"]]["question"]:
                    integrity["question text differs from questions.jsonl"] += 1
                h = hashlib.sha256(json.dumps([r["answer"], r["contexts"]], ensure_ascii=False).encode()).hexdigest()
                if rec.get(r["id"]) != h:
                    integrity["answer or contexts differ from as_recorded"] += 1
                if not r["answer"].strip():
                    integrity["empty answer"] += 1
                if not r["contexts"]:
                    integrity["no contexts"] += 1
    missing = set(qids) - set(rows)
    extra = set(rows) - set(qids)
    integrity["missing of the 815"] = len(missing)
    integrity["rows outside the 815"] = len(extra)
    return rows, integrity


MODES = ("exact", "ci", "whole")
results = {}   # arm -> qid -> list of (kind, ident, ctx{mode}, ans{mode})
integrity_all = {}
for arm in RUNS:
    rows, integ = load_rows(arm)
    integrity_all[arm] = dict(integ)
    res = {}
    for qid, ids in idents.items():
        row = rows[qid]
        ctx = "\n\n".join(row["contexts"])
        ctx_l = ctx.lower()
        ans = row["answer"]
        ans_l = ans.lower()
        res[qid] = [(k, i, present(k, i, ctx, ctx_l), present(k, i, ans, ans_l)) for k, i in ids]
    results[arm] = res

print("\n=== row checks per arm (counts over the 815 rows) ===")
for arm, integ in integrity_all.items():
    print(f"  {arm:9s}", integ)


def arm_counts(arm, mode, kind=None):
    res = results[arm]
    c = Counter()
    for qid, items in res.items():
        items = [x for x in items if kind is None or x[0] == kind]
        if not items:
            continue
        c["questions"] += 1
        n = len(items)
        nc = sum(1 for x in items if x[2][mode])
        na = sum(1 for x in items if x[3][mode])
        c["identifiers"] += n
        c["in_context"] += nc
        c["in_answer"] += na
        c["context_not_answer"] += sum(1 for x in items if x[2][mode] and not x[3][mode])
        c["answer_not_context"] += sum(1 for x in items if x[3][mode] and not x[2][mode])
        c["answer_not_context_in_question"] += sum(
            1 for x in items if x[3][mode] and not x[2][mode] and in_question[(qid, x[1])])
        c["neither"] += sum(1 for x in items if not x[2][mode] and not x[3][mode])
        c["q_ctx_" + ("all" if nc == n else "some" if nc else "none")] += 1
        c["q_ans_" + ("all" if na == n else "some" if na else "none")] += 1
    return c


def fmt(c):
    return (f"q={c['questions']:3d} ids={c['identifiers']:4d} in_ctx={c['in_context']:4d} "
            f"in_ans={c['in_answer']:4d} ctx_not_ans={c['context_not_answer']:4d} "
            f"ans_not_ctx={c['answer_not_context']:3d} (of these in the question: "
            f"{c['answer_not_context_in_question']}) neither={c['neither']:4d} | "
            f"ctx all/some/none={c['q_ctx_all']}/{c['q_ctx_some']}/{c['q_ctx_none']} | "
            f"ans all/some/none={c['q_ans_all']}/{c['q_ans_some']}/{c['q_ans_none']}")


summary = {"patterns": {"URL": URL.pattern, "URL trailing characters stripped": URL_TRAIL,
                        "pr_link (full match of a URL)": PR_LINK.pattern,
                        "employee_id": EMPLOYEE_ID.pattern, "customer_id": CUSTOMER_ID.pattern,
                        "whole: before": BOUND_BEFORE, "whole: after": BOUND_AFTER},
           "references_with_match": dict(pattern_refs), "matches_with_repeats": dict(pattern_tokens),
           "checks": dict(check_refs), "row_checks": integrity_all, "arms": {}, "pairs": {}}

print("\n=== step 3: per arm ===")
for mode in MODES:
    print(f"-- mode {mode}")
    for kind in (None,) + KINDS:
        for arm in RUNS:
            c = arm_counts(arm, mode, kind)
            summary["arms"].setdefault(mode, {}).setdefault(kind or "all", {})[arm] = dict(c)
            print(f"  {(kind or 'all kinds'):11s} {arm:9s} {fmt(c)}")


def shares(arm, mode, kind=None):
    out = {}
    for qid, items in results[arm].items():
        items = [x for x in items if kind is None or x[0] == kind]
        if not items:
            continue
        n = len(items)
        out[qid] = (sum(1 for x in items if x[2][mode]) / n, sum(1 for x in items if x[3][mode]) / n)
    return out


def compare(a, b, mode, kind=None):
    sa, sb = shares(a, mode, kind), shares(b, mode, kind)
    assert sa.keys() == sb.keys()
    res = {}
    for j, label in ((0, "context"), (1, "answer")):
        diffs = [sa[q][j] - sb[q][j] for q in sa]
        hi = [d for d in diffs if d > 1e-12]
        lo = [-d for d in diffs if d < -1e-12]
        eq = len(diffs) - len(hi) - len(lo)
        res[label] = {"questions": len(diffs), "higher": len(hi), "lower": len(lo), "equal": eq,
                      "median_higher": round(statistics.median(hi), 3) if hi else None,
                      "median_lower": round(statistics.median(lo), 3) if lo else None,
                      "median_all_differing_abs": round(statistics.median(hi + lo), 3) if hi + lo else None}
    return res


print("\n=== step 4: arm against arm, question by question (share of the question's identifiers) ===")
for mode in MODES:
    print(f"-- mode {mode}")
    for kind in (None,) + KINDS:
        for a, b in (("artefact", "lucene"), ("artefact", "vector"), ("lucene", "vector")):
            r = compare(a, b, mode, kind)
            summary["pairs"].setdefault(mode, {}).setdefault(kind or "all", {})[f"{a}_vs_{b}"] = r
            line = f"  {(kind or 'all kinds'):11s} {a} vs {b}: "
            for label in ("context", "answer"):
                x = r[label]
                line += (f"{label}: higher {x['higher']} (median {x['median_higher']}), lower {x['lower']} "
                         f"(median {x['median_lower']}), equal {x['equal']}; ")
            print(line)

OUT.write_text(json.dumps(summary, indent=1), encoding="utf-8")
print("\nwritten:", OUT)
