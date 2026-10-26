"""The finished data, for giving away: one workbook, values only. Sheets: results (the three
arms' questions in one table), run data (what is the same for the arms once, then a column per
arm), arm construction (a column per arm), key.

    python tools/export_finished_data.py [--out finished_data]

Needs openpyxl. Reads the final run folders, one per arm and question set (RUNS), the questions
file they all read (data/questions.jsonl, checked against each run's hash of it), the files of the
question sets (SETS, which together are HERB's answerable questions, each once) and the graph's
build cost (test/graph/build_cost.json), and writes grag-data.xlsx. It prints which question sets
each arm's runs cover and names a set an arm has no run on. A run split over the laptop and the
desktop is read with its halves for its environment. Every run's time, and its judging's time, is
its questions' times added; an arm's is its runs' added. A run that read its interpreter's answers
and its query embeddings from an earlier run takes those values from that run (MADE_IN). Two scores
judged after a run, on its answers with its judge, are read from the folder beside the run
(REJUDGED), and their judging is added to the run's. A column of a run is a measure he named
(times, tokens, characters, runtime, the RAGAS scores) or an id of the dataset, the evaluation or
the run; the construction holds what built the index that each final run read, one model at a
time, and nothing about how it was built. Nothing that belongs to this machine or this project
goes in: no path, host, user, session, repository file, commit, note or reason. The data sheets
come first; the last sheet is the key.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

import correct_missing_judge_legs as judge_records

ROOT = Path(__file__).resolve().parent.parent
# an arm's final runs, one per question set; their rows go into the same sheets (his 2026-10-25
# "the fucking point is to have a full ragas-herb test done finally")
RUNS = {"lucene": ["lucene__gold100__cb72000__20261008T234209Z",
                   "lucene__answerable715__cb72000__20261023T112745Z"],
        "vector": ["vector__gold100__cb72000__20261017T061242Z",
                   "vector__answerable715__cb72000__20261024T004317Z"],
        "artefact": ["artefact_v4__gold100__cb72000__20261023T021439Z",
                     "artefact_v4__answerable715__cb72000__20261025T211532Z"]}
# HERB's answerable questions, each in one of these files of ids; a run's set is the file whose
# sha256 its manifest names as its ids file
SETS = {"gold100": "data/gold100.jsonl", "answerable715": "data/answerable715.jsonl"}
# the artefact's run on the hundred read its interpreter's answers and its query embeddings, the same
# on every question, from this run (his 2026-10-22 "it's the same as the fucking "old run's interpreter"")
MADE_IN = {"artefact_v4__gold100__cb72000__20261023T021439Z": "artefact_v4__gold100__cb72000__20261020T041923Z"}
# scores judged after a run, on its answers with its judge, by prod/run.py --rejudge into the folder
# beside the run, named by the run, this and the set (his 2026-10-23 "just toggle them and run them
# on all 100 for all 3 arms"); a run that judged every score itself has no such folder
REJUDGED = "__j-claude-haiku-4-5-20251001__"
REJUDGED_SCORES = ("factual_correctness", "context_entity_recall")
DATASET, LICENCE = "HERB (Salesforce AI Research)", "CC BY-NC 4.0"
# the sheets' names
PER_QUESTION, PER_RUN, CONSTRUCTION, KEY = "results", "run data", "arm construction", "key"

# (field, meaning, unit): the data dictionary is written from these lists. A score's meaning is
# RAGAS's own definition (docs.ragas.io, available metrics) with the setting RAGAS 0.4.3 used.
SCORES = [
    ("faithfulness", "RAGAS Faithfulness. Claims in the answer supported by the retrieved context / all claims "
                     "in the answer.", "0-1"),
    ("answer_correctness", "RAGAS AnswerCorrectness. Weighted average of factual similarity to the reference "
                           "answer (weight 0.75) and semantic_similarity (weight 0.25). Reference answer: HERB's answer.", "0-1"),
    ("factual_correctness", "RAGAS FactualCorrectness. F1 of precision, TP / (TP + FP), and recall, TP / (TP + FN). "
                            "TP: claims in the answer present in the reference answer. FP: claims in the answer not "
                            "present in the reference answer. FN: claims in the reference answer not present in the "
                            "answer. Claims and their presence: the judge's, atomicity and coverage low. Rounded to "
                            "two decimals.", "0-1"),
    ("context_recall_id", "RAGAS IDBasedContextRecall. Reference context ids found in the retrieved context ids / "
                          "all reference context ids. Reference context ids: HERB's evidence record ids.", "0-1"),
    ("context_precision_id", "RAGAS IDBasedContextPrecision. Retrieved context ids found in the reference context "
                             "ids / all retrieved context ids.", "0-1"),
    ("context_recall_llm", "RAGAS LLMContextRecall. Claims in the reference answer supported by the retrieved "
                           "context / all claims in the reference answer.", "0-1"),
    ("context_entity_recall", "RAGAS ContextEntityRecall. Entities common to the reference answer and the retrieved "
                              "context / all entities in the reference answer. Entities: the judge's.", "0-1"),
    ("context_recall_nonllm", "RAGAS NonLLMContextRecall. Relevant contexts retrieved / all reference contexts. "
                              "Relevant: Levenshtein similarity to a reference context of more than 0.5. Reference context: the "
                              "content of a HERB evidence record, without ids, labels, dates and names. Retrieved "
                              "contexts: the content of each record passed to the answer model.", "0-1"),
    ("context_precision_nonllm", "RAGAS NonLLMContextPrecisionWithReference. Context precision@K: mean of "
                                 "precision@k over the ranks k of the relevant retrieved contexts. Relevant: "
                                 "Levenshtein similarity to a reference context of 0.5 or more. Reference context: the content "
                                 "of a HERB evidence record, without ids, labels, dates and names. Retrieved contexts: "
                                 "the content of each record passed to the answer model.", "0-1"),
    ("semantic_similarity", "RAGAS SemanticSimilarity. Cosine similarity of the embeddings of the answer and the "
                            "reference answer.", "0-1"),
    ("string_similarity", "RAGAS NonLLMStringSimilarity. Levenshtein similarity of the answer and the reference "
                          "answer.", "0-1"),
    ("bleu", "RAGAS BleuScore. BLEU of the answer against the reference answer.", "0-1"),
    ("rouge", "RAGAS RougeScore. ROUGE-L F-measure of the answer against the reference answer.", "0-1"),
    ("chrf", "RAGAS ChrfScore. chrF of the answer against the reference answer.", "0-1"),
    ("exact_match", "RAGAS ExactMatch. 1 if the answer is the same as the reference answer, else 0.", "0 or 1"),
    ("string_presence", "RAGAS StringPresence. 1 if the answer contains the reference answer, else 0.", "0 or 1"),
]
QUESTIONS = [
    ("arm", "Retrieval method.", ""),
    ("question_id", "Question id: product, a (answerable), index of the question in the product's answerable "
                    "questions in HERB, from 0.", ""),
    ("question_set", "Question set of the question: gold100, 100 of HERB's 815 answerable questions; "
                     "answerable715, the other 715.", ""),
    ("question_type", "HERB question type.", ""),
    ("question", "Question, from HERB.", ""),
    ("reference_answer", "Reference answer: HERB's answer to the question, as RAGAS was given it (its parts "
                         "joined by spaces).", ""),
    ("reference_context_ids", "Reference context ids: the ids of HERB's evidence records for the question.", ""),
    ("answer", "Answer of the answer model.", ""),
    *SCORES,
    ("search_seconds", "Retrieval time, without the interpreter and the query embedding.", "seconds"),
    ("interpreter_seconds", "Time of the interpreter call's answering try: the answer model, called before "
                            "retrieval. Artefact only.", "seconds"),
    ("query_embedding_seconds", "Time to embed the query. Vector and artefact only. The artefact embeds its "
                                "query texts and reads a text embedded before from its cache, counted as no "
                                "call: its time is that of the texts embedded for the question, empty when all "
                                "of them were embedded before.", "seconds"),
    ("answer_seconds", "Time of the answer model call's answering try.", "seconds"),
    ("total_seconds", "Time of all steps for the question, to the answer, without failed tries of model "
                      "calls.", "seconds"),
    ("interpreter_tokens_in", "Input tokens of the interpreter call. Artefact only.", "tokens"),
    ("interpreter_tokens_out", "Output tokens of the interpreter call. Artefact only.", "tokens"),
    ("query_embedding_tokens", "Tokens embedded for the query. Vector and artefact only; for the artefact, "
                               "those of the texts embedded for the question, empty when all of them were "
                               "embedded before.", "tokens"),
    ("retrieved_context_characters", "Characters of the retrieved context given to the answer model. At most "
                                     "character_limit.", "characters"),
    ("answer_tokens_in", "Input tokens of the answer model call.", "tokens"),
    ("answer_tokens_out", "Output tokens of the answer model call.", "tokens"),
]
# the same for the three arms; the export stops if an arm differs. The dataset and its licence
# are their own words and have no entry in the data dictionary.
SETUP = [
    ("dataset", None, ""),
    ("dataset_licence", None, ""),
    ("character_limit", "Maximum characters of retrieved text given to the answer model per question.",
     "characters"),
    ("answer_model", "Language model of the answers and of the artefact's interpreter.", ""),
    ("judge_model", "Language model that RAGAS uses as judge.", ""),
    ("embedding_model", "Embedding model of the query embeddings and of the RAGAS scores that use embeddings.", ""),
]
RUN = [
    ("run_seconds", f"Time of the arm's runs over its questions in {PER_QUESTION}, without failed tries of "
                    "model calls.", "seconds"),
    ("judge_tokens_in", "Input tokens of all RAGAS judge calls.", "tokens"),
    ("judge_tokens_out", "Output tokens of all RAGAS judge calls.", "tokens"),
    ("judge_embedding_tokens", "Tokens embedded by RAGAS.", "tokens"),
    ("judging_seconds", f"Time of the RAGAS evaluation over the arm's questions in {PER_QUESTION}.", "seconds"),
]
INDEX_KIND = {"lucene": ("BM25 full-text index", "corpus record"),
              "vector": ("dense vector index", "corpus record"),
              "artefact": ("graph database (Neo4j)", "chunk: one or more corpus records")}


def model_name(name):
    """A model's name without its publisher and without a snapshot date (his 2026-10-21 "fucking
    off with the nvidia tag", "20251001 for haiku? Stop beeing retarded")."""
    return None if name is None else re.sub(r"-\d{8}$", "", str(name).split("/")[-1])


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def one(values, what):
    values = list(values)
    if any(v != values[0] for v in values):
        sys.exit(f"{what} differs between questions; this export reads one")
    return values[0]


def covered(intervals):
    """The seconds a set of (start, end) intervals covers, overlaps counted once."""
    total, end = 0.0, None
    for a, b in sorted(intervals):
        if end is None or a > end:
            total, end = total + (b - a).total_seconds(), b
        elif b > end:
            total, end = total + (b - end).total_seconds(), b
    return total


def judging_seconds(calls, ids, what):
    """The judging's time as each question's judging added, one span per question and scoring start:
    from the question's first call record in that start to its last. The time between two starts is
    in no span (his 2026-10-22 "THE RUN TIME IS THE ADDED TIME FOR ALL THE THINGS IN THE FUCKING
    RUN", 2026-10-23 "wall time? this is not a thing"). A judge call's time is its answering try: out
    of each span goes the time in which only tries that did not answer, or the pauses after tries, of
    the question's calls were under way, and no answering try or embedder request of the question
    (his 2026-10-21 "a model call's time is its answering try; the seconds of failed tries are out of
    the call, the question and the run"). Also the seconds so taken out."""
    spans, failed, answering = {}, {}, {}
    for c in calls:
        if c.get("question_id") not in ids or not (c.get("started_at") and c.get("finished_at")):
            continue
        key = (c["question_id"], c["eval_leg"])
        a, b = datetime.fromisoformat(c["started_at"]), datetime.fromisoformat(c["finished_at"])
        s = spans.setdefault(key, [a, b])
        s[0], s[1] = min(s[0], a), max(s[1], b)
        if c.get("kind") != "chat":
            answering.setdefault(key, []).append((a, b))
            continue
        tries = c.get("attempts") or []
        for n, t in enumerate(tries):
            if not t.get("started_at") or t.get("seconds") is None:
                sys.exit(f"{what}: a judge call's try has no start or no seconds; its time cannot be cut")
            t0 = datetime.fromisoformat(t["started_at"])
            t1 = t0 + timedelta(seconds=float(t["seconds"]))
            if c.get("ok") and n == len(tries) - 1:
                answering.setdefault(key, []).append((t0, t1))
            else:
                failed.setdefault(key, []).append((t0, t1 + timedelta(seconds=float(t.get("backoff_s") or 0.0))))
    if {q for q, _ in spans} != set(ids):
        sys.exit(f"{what}: not every question has its judge calls")
    out = {k: covered(failed[k] + answering.get(k, [])) - covered(answering.get(k, [])) for k in failed}
    return sum((b - a).total_seconds() - out.get(k, 0.0) for k, (a, b) in spans.items()), sum(out.values())


def judge_cost(folder, ev, calls, cells):
    """judge_usage, checked against the scoring starts and the call records: every start in the call
    records has its entry in judge_legs, each entry's counts are those of its start's judge calls that
    answered (counted as tools/correct_missing_judge_legs.py counts them), judge_usage is the entries'
    sum, and the score cells' usage is their own calls'. And the tokens the evaluation embedded: the
    entries' embedding, checked against the embedder records."""
    counts = judge_records.COUNTS
    legs = ev["judge_legs"]
    starts = [(leg.get("settings") or {}).get("started_at") for leg in legs]
    by_leg = {}
    for c in calls:
        by_leg.setdefault(c["eval_leg"], []).append(c)
    if not all(starts) or set(by_leg) - set(starts):
        sys.exit(f"{folder}: the scoring starts {sorted(set(by_leg) - set(starts))} are in eval_calls.jsonl "
                 f"and have no entry in judge_legs, or an entry names no start")
    for start, leg in zip(starts, legs):
        records = judge_records.usage_of(by_leg.get(start, []))
        diff = judge_records.differs(leg["usage"], records, counts)
        # a written entry stays as recorded. A start that was cut short can have counted calls whose cell
        # wrote no record before it stopped, so its entry may hold more than its records; it may never hold
        # less, and no other entry may differ (the main session's decision of 2026-10-25, by his rule that
        # the data stays as recorded)
        if diff and (leg["settings"].get("interrupted")
                     and all(leg["usage"][k] >= records[k] for k in counts)):
            print(f"{folder}: the entry of scoring start {start}, which was cut short, holds more than its "
                  f"records (entry, records): {diff}; the entry stands")
        elif diff:
            sys.exit(f"{folder}: the entry of scoring start {start} and its judge call records differ "
                     f"(entry, records): {diff}")
    if judge_records.differs(judge_records.summed(legs), ev["judge_usage"], counts):
        sys.exit(f"{folder}: judge_usage is not the sum of judge_legs")
    own = {(qid, m, c["components"]["usage"]["eval_leg"]) for qid, q in cells.items() for m, c in q.items()}
    use = [c["components"]["usage"] for q in cells.values() for c in q.values()]
    mine = [c for c in calls if c.get("kind") == "chat" and (c.get("question_id"), c.get("score"), c["eval_leg"]) in own]
    if ((sum(u["chat_calls"] for u in use), sum(u["tokens_in"] for u in use), sum(u["tokens_out"] for u in use))
            != (len(mine), sum(int((c.get("usage") or {}).get("prompt_tokens") or 0) for c in mine),
                sum(int((c.get("usage") or {}).get("completion_tokens") or 0) for c in mine))
            or not all(c.get("ok") for c in mine)):
        sys.exit(f"{folder}: the scores' judge cost is not that of their own judge calls")
    embedded = sum(leg["settings"]["embedding"]["tokens_in"] for leg in legs)
    if embedded != judge_records.embedding_of(calls)["tokens_in"]:
        sys.exit(f"{folder}: the scoring starts' embedding tokens are not those of the embedder records")
    # the cost is every judge call that answered, the cells that failed or that a later start dropped
    # included: judge_usage (the main session's decision of 2026-10-25, by the key's "all RAGAS judge calls")
    return ev["judge_usage"], embedded


def failed_tries_seconds(records):
    """The seconds of the model calls' tries that did not answer, and of the pauses after tries, as
    the call records hold them; an embedder request makes no try. A try marked machine_asleep was
    taken out of retry_s whole by the sleep correction (slept-try/1, the folder's corrections.json),
    so it counts here with no seconds; its pause stays."""
    return sum(sum(float(t.get("seconds") or 0.0) for t in c.get("attempts") or []
                   if t.get("outcome") != "ok" and not t.get("machine_asleep"))
               + sum(float(t.get("backoff_s") or 0.0) for t in c.get("attempts") or [])
               for c in records if c.get("kind") == "chat")


def interpreter_and_embeddings(r):
    """What the interpreter answered and what was embedded for the query, without how each was got
    (asked anew, or read from a store or a cache)."""
    i = r["meta"]["interpreter"]
    return ([{k: v for k, v in s.items() if k not in ("cache_hit", "offline", "asks")} for s in i["stages"]],
            i["embeddings"])


def halves(d, name):
    """A file of each half of a run split over two machines, as that half wrote it."""
    return [read(p) for p in sorted((d / "halves").glob(f"*/{name}"))]


def environment(d, man):
    """The run's environment; a split run keeps it in its halves, which must name one embedding model."""
    if man["environment"] is not None:
        return man["environment"]
    envs = [h["environment"] for h in halves(d, "run_manifest.json")]
    if len(envs) != len(man["legs"]) or len({e["embedder"]["model"] for e in envs}) != 1:
        sys.exit(f"{d.name}: the halves do not name one embedding model")
    return envs[0]


def rejudged(arm, d, cells, judge_model, set_name):
    """REJUDGED_SCORES from the folder beside the run, which judged the run's own answers and holds the
    run's other scores as the run has them. Their cost is that of every judge call of the folder that
    answered, as the run's own judging is counted (judge_usage; the key's "all RAGAS judge calls"); their
    time each question's span of calls added, one span per start of the judging, as the run's. A run
    with no such folder must have judged every score itself."""
    j = d.parent / (d.name + REJUDGED + set_name)
    if not j.exists():
        return {}, 0.0, 0, 0, 0.0
    if any(s in q for q in cells.values() for s in REJUDGED_SCORES):
        sys.exit(f"{arm}: {d.name} judged {REJUDGED_SCORES} itself and {j.name} judged them again")
    judged = lambda f: {r["id"]: (r["question"], r["answer"], r["contexts"], r["context_ids"])  # noqa: E731
                        for r in rows(f / "arm_outputs.jsonl")}
    if judged(j) != judged(d):
        sys.exit(f"{arm}: {j.name} judged other answers than the run's")
    added, kept = {}, set()
    for r in rows(j / "eval_results.jsonl"):
        if r["metric"] in REJUDGED_SCORES:
            added.setdefault(r["question_id"], {})[r["metric"]] = r
            kept.add((r["question_id"], r["metric"], r["components"]["usage"]["eval_leg"]))
        elif r != cells[r["question_id"]][r["metric"]]:
            sys.exit(f"{arm} {r['question_id']}: {r['metric']} in {j.name} is not the run's")
    every = rows(j / "eval_calls.jsonl")
    if any(c.get("score") not in REJUDGED_SCORES or c.get("question_id") not in cells for c in every):
        sys.exit(f"{arm}: {j.name} holds a call for another score or question than the re-judged ones")
    calls = [c for c in every if (c.get("question_id"), c.get("score"), c.get("eval_leg")) in kept]
    use = [c["components"]["usage"] for q in added.values() for c in q.values()]
    tokens = [c.get("usage") or {} for c in calls]
    if ((sum(u["chat_calls"] for u in use), sum(u["tokens_in"] for u in use), sum(u["tokens_out"] for u in use))
            != (len(calls), sum(int(t.get("prompt_tokens") or 0) for t in tokens),
                sum(int(t.get("completion_tokens") or 0) for t in tokens))
            or any(c["kind"] != "chat" or c["model"] != judge_model for c in every)):
        sys.exit(f"{arm}: the re-judged scores' cost is not their calls', or a call is not the run's judge's")
    # one basis for every judging: every judge call that answered (the main session's decision of
    # 2026-10-25, by the key's "all RAGAS judge calls")
    cost = judge_records.usage_of(every)
    seconds, failed = judging_seconds(every, set(cells), f"{arm}: {j.name}")
    return added, seconds, cost["tokens_in"], cost["tokens_out"], failed


def references():
    """Each question's row of the questions file, which holds HERB's reference answer and evidence record
    ids; every final run must have read this file as it is."""
    path = ROOT / "data/questions.jsonl"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for folder in (f for folders in RUNS.values() for f in folders):
        if read(ROOT / "output/k=chars" / folder / "run_manifest.json")["inputs"]["questions_sha256"] != digest:
            sys.exit(f"{folder}: the run read another questions file than {path}")
    return {q["id"]: q for q in rows(path)}


def question_sets(refs):
    """Each set's question ids and, by the sha256 of its file, its name. Together the sets are HERB's
    answerable questions (the ids with ::a::), each once."""
    sets, by_sha = {}, {}
    for name, file in SETS.items():
        path = ROOT / file
        by_sha[hashlib.sha256(path.read_bytes()).hexdigest()] = name
        sets[name] = [json.loads(x)["id"] for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    every = [i for ids in sets.values() for i in ids]
    if len(every) != len(set(every)) or set(every) != {i for i in refs if "::a::" in i}:
        sys.exit(f"the question sets {list(SETS)} are not HERB's answerable questions, each once")
    return sets, by_sha


def runs_tables(arm, folder, refs, sets, by_sha):
    d = ROOT / "output/k=chars" / folder
    man, ev = read(d / "run_manifest.json"), read(d / "eval_manifest.json")
    env = environment(d, man)
    set_name = by_sha.get(man["inputs"]["ids_sha256"])
    if set_name is None:
        sys.exit(f"{folder}: the run's question set is none of {list(SETS)}")
    ids = sets[set_name]
    if (man["n_questions"], man["n_ran"], man["n_failed"]) != (len(ids), len(ids), 0):
        sys.exit(f"{folder}: not every one of the {len(ids)} questions of {set_name} was answered")
    outputs = rows(d / "arm_outputs.jsonl")
    if sorted(r["id"] for r in outputs) != sorted(ids):
        sys.exit(f"{folder}: the rows are not the questions of {set_name}, each once")
    cells = {}
    for r in rows(d / "eval_results.jsonl"):
        cells.setdefault(r["question_id"], {})[r["metric"]] = r
    calls = rows(d / "eval_calls.jsonl")
    judge, embedded = judge_cost(folder, ev, calls, cells)
    seconds, failed_judging = judging_seconds(calls, set(cells), folder)
    added, added_seconds, added_in, added_out, added_failed = rejudged(arm, d, cells, ev["judge_model"], set_name)
    for qid, scores in added.items():
        cells[qid].update(scores)
    source = {o["id"]: o for o in rows(ROOT / "output/k=chars" / MADE_IN[folder] / "arm_outputs.jsonl")} \
        if folder in MADE_IN else {}
    questions = []
    for r in outputs:
        own = {}
        for e in r["retrieval"]:
            if e["kind"] in own:
                sys.exit(f"{arm} {r['id']}: two {e['kind']} models in the arm's own calls")
            own[e["kind"]] = e
        arm_calls = [c for c in r["calls"] if c.get("role") != "answer"]
        records = [(r["generator"], [c for c in r["calls"] if c.get("role") == "answer"])] + [
            (e, [c for c in arm_calls if c.get("kind") == k]) for k, e in own.items()]
        replaced = None
        if source:
            o = source[r["id"]]
            records += [(e, [c for c in o["calls"] if c.get("role") != "answer" and c.get("kind") == e["kind"]])
                        for e in o["retrieval"]]
            if "chat" in own or interpreter_and_embeddings(r) != interpreter_and_embeddings(o):
                sys.exit(f"{arm} {r['id']}: the interpreter's answers or the query embeddings are not those of "
                         f"{MADE_IN[folder]}")
            made = {e["kind"]: e for e in o["retrieval"]}
            # this run's own embedding calls, for texts its machine had not embedded before, give way to
            # the calls that embedded all of them
            replaced = own.get("embed")
            own["chat"], own["embed"] = made["chat"], made["embed"]
        mine = cells[r["id"]]
        if set(mine) != {s for s, _, _ in SCORES} or any(c["status"] != "ok" for c in mine.values()):
            sys.exit(f"{arm} {r['id']}: not every score is there and ok")
        g, interp, qe = r["generator"], own.get("chat"), own.get("embed")
        # a model call's time is its answering try; the seconds of failed tries are taken out of
        # the call, the question and the run (his 2026-10-21 "correct this"). What is taken out,
        # retry_s, must be the seconds of the tries that did not answer and of the pauses after tries,
        # as the call records hold them (two clock readings of the same tries: within 1e-4 s), and
        # the call's time must hold its tries and its wait; the rest of it is the harness's own time
        # in the call and stays in it, as in the final runs (the main session's decision of 2026-10-25)
        for call, recs in records:
            if (abs(call["retry_s"] - failed_tries_seconds(recs)) > 1e-4
                    or call["time_s"] - call["request_s"] - call["wait_s"] - call["retry_s"] < -1e-6):
                sys.exit(f"{arm} {r['id']}: a call's retry_s is not its records' failed tries and pauses, or "
                         f"its time does not hold its tries and its wait")
        # the question's time holds all its steps: an interpreter call and embedding calls made in
        # MADE_IN's run count by their answering try, in place of this run's own embedding calls;
        # an interpreter call that a start of this run made before the start that wrote the row
        # (read from the run's store, its record given back by correction store-hit-calls/1) counts
        # by its answering try, outside the row's own span
        stored = (not source and interp is not None
                  and all(s.get("cache_hit") for s in r["meta"]["interpreter"]["stages"]))
        failed = sum(call["retry_s"] for call in
                     ((g, replaced) if source else (g, qe) if stored else (g, interp, qe)) if call)
        made_elsewhere = ((sum(c["time_s"] - c["retry_s"] for c in (interp, qe))
                           - (replaced["time_s"] - replaced["retry_s"] if replaced else 0.0)) if source
                          else interp["time_s"] - interp["retry_s"] if stored else 0.0)
        # the characters the cut handed over, checked against the texts themselves
        chars = r["meta"]["char_budget"]["chars"]
        if chars != sum(len(t) for t in r["contexts"]) or chars > man["char_budget"]:
            sys.exit(f"{arm} {r['id']}: the characters handed over are not those of the retrieved context")
        ref = refs[r["id"]]
        if ref["question"] != r["question"]:
            sys.exit(f"{arm} {r['id']}: the question is not the questions file's")
        questions.append({
            "arm": arm,
            "question_id": r["id"],
            # where the row comes from, like an id (the main session's decision of 2026-10-25)
            "question_set": set_name,
            "question_type": one((c["type"] for c in mine.values()), f"{r['id']} type"),
            "question": r["question"],
            "reference_answer": " ".join(str(g) for g in ref["ground_truth"]),
            "reference_context_ids": ", ".join(str(c) for c in ref["citations"]),
            "answer": r["answer"],
            **{s: mine[s]["value"] for s, _, _ in SCORES},
            "search_seconds": r["search_time_s"],
            "interpreter_seconds": interp and interp["time_s"] - interp["retry_s"],
            "query_embedding_seconds": qe and qe["time_s"] - qe["retry_s"],
            "answer_seconds": g["time_s"] - g["retry_s"],
            "total_seconds": r["timing"]["wall_s"] - failed + made_elsewhere,
            "interpreter_tokens_in": interp and interp["tokens_in"],
            "interpreter_tokens_out": interp and interp["tokens_out"],
            "query_embedding_tokens": qe and qe["tokens_in"],
            "retrieved_context_characters": chars,
            "answer_tokens_in": g["tokens_in"],
            "answer_tokens_out": g["tokens_out"],
        })
    setup = {
        "dataset": DATASET, "dataset_licence": LICENCE,
        "character_limit": man["char_budget"], "answer_model": model_name(man["generator_model"]),
        "judge_model": model_name(ev["judge_model"]), "embedding_model": model_name(env["embedder"]["model"]),
    }
    # his 2026-10-21 "cba adding interpreter, it's just the answer model"
    if man["interpreter_model"] is not None and model_name(man["interpreter_model"]) != setup["answer_model"]:
        sys.exit(f"{arm}: the interpreter's model is not the answer model")
    # a run's time, and its judging's, is the time of all the things in it added: its questions' times,
    # never the clock of the run as a whole (his 2026-10-22 "THE RUN TIME IS THE ADDED TIME FOR ALL THE
    # THINGS IN THE FUCKING RUN", 2026-10-23 "wall time? this is not a thing")
    run = {
        "run_seconds": sum(q["total_seconds"] for q in questions),
        "judge_tokens_in": judge["tokens_in"] + added_in, "judge_tokens_out": judge["tokens_out"] + added_out,
        "judge_embedding_tokens": embedded,
        "judging_seconds": seconds + added_seconds,
    }
    failed_answer = sum(1 for r in outputs for c in r["calls"] if c.get("role") == "answer"
                        for t in c.get("attempts") or [] if t.get("outcome") != "ok")
    print(f"{folder}: {set_name}, {len(questions)} rows; answer calls' tries that did not answer {failed_answer}, "
          f"their seconds and pauses out: {sum(r['generator']['retry_s'] for r in outputs):.1f} s; seconds of judge "
          f"calls' tries that did not answer, and their pauses, taken out of the judging's spans: "
          f"{failed_judging + added_failed:.1f} s")
    return questions, setup, run, set_name


def construction_table():
    """One row per property, one column per arm: what built the index that the final run read, one model
    at a time (his 2026-10-21 "The ONLY thing that matters, at all, is the iteration that ran the
    RAGAS"). For the artefact that is read from test/graph/build_cost.json: the descriptions and tags
    of the chunks in the graph, the vectors, the Opus judgements the facet network learned from, the
    encoding of every edge, and the steps with no model; work replaced later, trials and tests stay
    out. Every run of an arm must have read the same index, by what the index holds; the column holds
    the build of the index that the arm's run on the hundred read."""
    of_runs = {a: [read(ROOT / "output/k=chars" / f / "run_manifest.json") for f in fs] for a, fs in RUNS.items()}

    # an index is the same when it holds the same: the same units, their text and its digest, from the
    # same corpus, made by the same method or embedding model; not the same cache file or build seconds
    # (the main session's decision of 2026-10-25: the vector runs' two cache files hold the same units
    # and texts, their vectors equal within float rounding)
    def holds(arm, folder, m):
        i, emb = m["index"], environment(ROOT / "output/k=chars" / folder, m)["embedder"]
        out = {"corpus.sha256": m["inputs"]["corpus"]["sha256"]}
        embedder = {f"embedder.{k}": emb.get(k) for k in ("model", "revision", "dtype")}
        if arm == "lucene":
            out.update({f"index.{k}": i.get(k) for k in ("units", "text_chars", "unit_text", "units_sha256",
                                                          "method", "k1", "b", "stopwords", "stemmer", "bm25s",
                                                          "PyStemmer")})
        elif arm == "vector":
            out.update({f"index.{k}": i.get(k) for k in ("units", "text_chars", "unit_text", "units_sha256",
                                                          "matrix_shape", "matrix_dtype", "matrix_bytes")},
                       **embedder)
        else:
            out.update({"index.graph": i.get("graph"), "index.facet_layer_run": i.get("facet_layer_run"),
                        "index.counts": json.dumps(i.get("counts"), sort_keys=True),
                        "index.build_cost_file_sha256": i.get("build_cost_file_sha256"),
                        "graph": json.dumps(m.get("graph"), sort_keys=True)}, **embedder)
        return out

    unequal = []
    for a, ms in of_runs.items():
        held = [holds(a, f, m) for f, m in zip(RUNS[a], ms)]
        unequal += [f"{a} {k}: " + ", ".join(f"{f} {h[k]}" for f, h in zip(RUNS[a], held))
                    for k in held[0] if any(h[k] != held[0][k] for h in held)]
    if unequal:
        sys.exit("the runs of an arm read different indexes, by what the indexes hold:\n  " + "\n  ".join(unequal))
    gold = next(hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for s, f in SETS.items() if s == "gold100")
    mans = {}
    for a, ms in of_runs.items():
        on_gold = [m for m in ms if m["inputs"]["ids_sha256"] == gold]
        if len(on_gold) != 1:
            sys.exit(f"{a}: not one run on gold100, whose index build the construction holds")
        mans[a] = on_gold[0]
        # for the record: each run's own build, of which only the hundred's goes into the column
        print(f"{a}: build seconds of each run's index: " + ", ".join(
            f"{f} {m['build_stats'].get('build_time_s')}" for f, m in zip(RUNS[a], ms)))
    cost = read(ROOT / "test/graph/build_cost.json")
    steps = {s["id"]: s for s in cost["steps"]}

    def left_out(step, starts):
        hits = [x["values"] for x in cost["left_out"] if x["step"] == step and x["what"].startswith(starts)]
        if len(hits) != 1:
            sys.exit(f"build_cost.json left_out: not one entry {step!r} {starts!r}")
        return hits[0]

    tagging = steps["descriptions_and_tags"]
    graph_chunks = tagging["the_4869_chunks_of_this_graph"]["extract"]
    recovery = left_out("descriptions_and_tags", "the recovery by pass")["extract"]   # calls, in, out, summed
    # the pass wrote these chunks and the ones taken out later; its time is split by the calls' own time
    pass_seconds = (left_out("descriptions_and_tags", "per-pass elapsed")["extract"]
                    + left_out("descriptions_and_tags", "the recovery's elapsed and its passes")["extract"])
    haiku_seconds = pass_seconds * graph_chunks["seconds_summed_per_call"] / (
        tagging["whole_run"]["by_pass"]["extract"]["seconds_summed_per_call"] + recovery[3])
    vectors = steps["embeddings"]["parts"]
    embedded = [vectors[k] for k in ("tags", "tags_with_underscores_in_readable_form", "descriptions")]
    runs = left_out("facet_layer", "the Opus judge runs one by one")
    learned_from = [runs["control"], runs["train"]]    # calls, in, out, summed, elapsed; the held-out only tested
    facet = steps["facet_layer"]["parts"]
    no_model = (sum(steps["graph_copies"]["seconds"].values())
                + vectors["write_tag_vectors"]["seconds_elapsed"] + vectors["write_description_vectors"]["seconds_elapsed"]
                + facet["head_selection_training_scoring"]["seconds_elapsed"]
                + facet["bootstrap_refits"]["seconds_elapsed"]
                + facet["write"]["seconds_elapsed"] + facet["write"]["backup_seconds"]
                + sum(steps["later_edges_and_fields"]["seconds"].values()))
    embed_seconds = sum(p["seconds_elapsed"] for p in embedded)
    opus_seconds = sum(r[4] for r in learned_from)
    encoder_seconds = facet["encoder_cache"]["seconds_elapsed"]
    vector = mans["vector"]["build_stats"]["models"][0]
    embedder = model_name(vector["model"])
    if any(model_name(environment(ROOT / "output/k=chars" / f, m)["embedder"]["model"]) != embedder
           for f, m in zip(RUNS["artefact"], of_runs["artefact"])):
        sys.exit("the arms name different embedding models")
    encoder = model_name(facet["encoder_cache"]["model"].split(", ")[0])
    a = "artefact"
    things = [
        ("index", "Index type.", "", {k: INDEX_KIND[k][0] for k in RUNS}),
        ("unit", "Unit stored in the index.", "", {k: INDEX_KIND[k][1] for k in RUNS}),
        ("units in the index", "Units in the index.", "count",
         {"lucene": mans["lucene"]["index"]["units"], "vector": mans["vector"]["index"]["units"],
          a: mans[a]["index"]["counts"]["chunks"]}),
        ("build time, seconds", "Time to build the index. Artefact: sum of the times of the build steps.", "seconds",
         {"lucene": mans["lucene"]["build_stats"]["build_time_s"], "vector": vector["seconds_elapsed"],
          a: haiku_seconds + embed_seconds + opus_seconds + encoder_seconds + no_model}),
        (f"{embedder}, texts embedded", "Texts embedded for the index.", "count",
         {"vector": vector["calls"], a: sum(p["texts"] for p in embedded)}),
        (f"{embedder}, tokens", "Tokens embedded for the index.", "tokens",
         {"vector": vector["tokens_in"], a: sum(p["tokens_in"] for p in embedded)}),
        (f"{embedder}, seconds", "Embedding time for the index.", "seconds",
         {"vector": vector["seconds_elapsed"], a: embed_seconds}),
        ("claude-haiku-4-5, calls", "Calls to claude-haiku-4-5 for the index.", "count",
         {a: graph_chunks["calls_with_usage"]}),
        ("claude-haiku-4-5, tokens in", "Input tokens of those calls.", "tokens", {a: graph_chunks["tokens_in"]}),
        ("claude-haiku-4-5, tokens out", "Output tokens of those calls.", "tokens", {a: graph_chunks["tokens_out"]}),
        ("claude-haiku-4-5, seconds", "Time of those calls: the time of the pass that made them, multiplied by "
                                      "their share of the pass's call time.", "seconds", {a: haiku_seconds}),
        ("claude-opus-5, calls", "Calls to claude-opus-5 for the index.", "count",
         {a: sum(r[0] for r in learned_from)}),
        ("claude-opus-5, tokens in", "Input tokens of those calls.", "tokens", {a: sum(r[1] for r in learned_from)}),
        ("claude-opus-5, tokens out", "Output tokens of those calls.", "tokens", {a: sum(r[2] for r in learned_from)}),
        ("claude-opus-5, seconds", "Time of those calls.", "seconds", {a: opus_seconds}),
        (f"{encoder}, seconds", f"Encoding time of {encoder} for the index.", "seconds", {a: encoder_seconds}),
    ]
    table = [{"property": t, **{k: values.get(k) for k in RUNS}} for t, _, _, values in things]
    return table, [{"sheet": CONSTRUCTION, "field": t, "meaning": m, "unit": u} for t, m, u, _ in things]


WIDE = {"question": 60, "reference_answer": 60, "answer": 80, "meaning": 100, "property": 50}


def workbook(path, title, sheets):
    """sheets: (name, [(heads, rows), ...]); the tables of one sheet stand under each other, a blank
    row between them."""
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.title, wb.properties.creator = title, ""
    for name, blocks in sheets:
        ws = wb.create_sheet(name)
        widths = {}
        for n, (heads, table) in enumerate(blocks):
            if n:
                ws.append([])
            ws.append(heads)
            for cell in ws[ws.max_row]:
                cell.font = Font(bold=True)
            for row in table:
                if set(row) != set(heads):
                    sys.exit(f"{path.name} {name}: a row's columns differ from its table's")
                ws.append([row[h] for h in heads])
            for i, h in enumerate(heads, 1):
                longest = max([len(h)] + [len(str(r[h])) for r in table[:200] if r[h] is not None])
                widths[i] = max(widths.get(i, 10), min(WIDE.get(h, 40), longest + 2))
        if len(blocks) == 1:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
        for i, w in widths.items():
            ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    wb.save(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(ROOT / "finished_data"))
    out = Path(p.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    questions, setups, runs, covered = [], {}, {arm: [] for arm in RUNS}, {arm: {} for arm in RUNS}
    refs = references()
    sets, by_sha = question_sets(refs)
    for arm, folders in RUNS.items():
        for folder in folders:
            rows_of_run, setups[folder], run_of, set_name = runs_tables(arm, folder, refs, sets, by_sha)
            if set_name in covered[arm]:
                sys.exit(f"{arm}: two runs on {set_name}")
            covered[arm][set_name] = len(rows_of_run)
            questions += rows_of_run
            runs[arm].append(run_of)
    # which question sets each arm's runs cover; an arm without a run on a set is named, and nothing
    # is decided about it here
    for arm in RUNS:
        lacks = [s for s in SETS if s not in covered[arm]]
        print(f"{arm}: " + ", ".join(f"{s} {n} questions" for s, n in covered[arm].items())
              + (f"; no run on {', '.join(lacks)}" if lacks else ""))
    if len({tuple(sorted(c)) for c in covered.values()}) > 1:
        print("the arms' rows, their run data and their means cover different questions")
    setup = next(iter(setups.values()))
    if any(s != setup for s in setups.values()):
        sys.exit("the runs differ in the setup; this export writes it once")
    # run data: what is the same for the three arms once, then a table with a column per arm, each
    # value the arm's runs' added
    same = [{"property": c, "value": setup[c]} for c, _, _ in SETUP]
    run = [{"property": c, **{arm: sum(r[c] for r in runs[arm]) for arm in RUNS}} for c, _, _ in RUN]
    # the mean of each measure of the results over an arm's questions in results; empty where the arm has none
    measures = [c for c, _, u in QUESTIONS if u]
    means = [{"mean of": c, **{arm: (lambda v: sum(v) / len(v) if v else None)(
        [q[c] for q in questions if q["arm"] == arm and q[c] is not None]) for arm in RUNS}} for c in measures]
    construction, construction_key = construction_table()
    key = ([{"sheet": PER_QUESTION, "field": c, "meaning": m, "unit": u} for c, m, u in QUESTIONS]
           + [{"sheet": PER_RUN, "field": c, "meaning": m, "unit": u} for c, m, u in SETUP + RUN if m]
           + [{"sheet": PER_RUN, "field": "mean of", "meaning": f"Mean over the arm's questions in {PER_QUESTION} "
                                                               f"of the field of {PER_QUESTION} named in the row.",
               "unit": ""}]
           + construction_key)
    sheets = [(PER_QUESTION, [([c for c, _, _ in QUESTIONS], questions)]),
              (PER_RUN, [(["property", "value"], same), (["property", *RUNS], run),
                         (["mean of", *RUNS], means)]),
              (CONSTRUCTION, [(["property", *RUNS], construction)]),
              (KEY, [(["sheet", "field", "meaning", "unit"], key)])]
    path = out / "grag-data.xlsx"
    workbook(path, "grag data", sheets)
    print(f"{path.name}: {path.stat().st_size:,} bytes, sheets {[n for n, _ in sheets]}, "
          f"rows {[[len(t) for _, t in blocks] for _, blocks in sheets]}")


if __name__ == "__main__":
    main()
