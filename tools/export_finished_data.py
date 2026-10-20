"""The finished data, for giving away: one workbook of the run for each arm, and one workbook of
the construction with a column for each arm, values only.

    python tools/export_finished_data.py [--out finished_data]

Needs openpyxl. Reads the three final run folders and writes four .xlsx files. A column of a run
is a measure he named (times, tokens, runtime, the RAGAS scores) or an id of the dataset, the
evaluation or the run; the construction holds what building each arm's index cost, one model at
a time, and nothing about how it was built. Nothing that belongs to this machine or this project
goes in: no path, host, user, session, repository file, commit, note or reason. The data sheet
comes first; the last sheet is the key.
"""
import argparse
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parent.parent
RUNS = {"lucene": "lucene__gold100__cb72000__20261008T234209Z",
        "vector": "vector__gold100__cb72000__20261017T061242Z",
        "artefact": "artefact_v4__gold100__cb72000__20261020T041923Z"}
DATASET, LICENCE = "HERB (Salesforce AI Research)", "CC BY-NC 4.0"
# the run records give the laptop's processor only as its CPUID string; this is its product name
CPU = {"Intel64 Family 6 Model 186 Stepping 2, GenuineIntel": "13th Gen Intel Core i7-1360P"}
COMPARE_INSIDE = " It counts per retrieved text, so compare it inside one arm only."

# (column, meaning, unit) for every sheet of a run; the key sheet is written from these lists
SCORES = [
    ("faithfulness", "RAGAS Faithfulness: how factually consistent the answer is with the retrieved text. "
                     "The judge model reads the answer's claims against the retrieved text.", "0 to 1"),
    ("answer_correctness", "RAGAS AnswerCorrectness: the answer against HERB's reference answer: 0.75 times the "
                           "F1 of the claims that the judge model finds in both, plus 0.25 times "
                           "semantic_similarity.", "0 to 1"),
    ("context_recall_id", "RAGAS IDBasedContextRecall: the share of HERB's evidence records for the question that "
                          "are among the records given in full (records sheet).", "0 to 1"),
    ("context_precision_id", "RAGAS IDBasedContextPrecision: the share of the records given in full (records "
                             "sheet, each record once) that are HERB evidence records for the question.", "0 to 1"),
    ("context_recall_llm", "RAGAS LLMContextRecall: the share of the reference answer's sentences that the judge "
                           "model finds supported by the retrieved text.", "0 to 1"),
    ("context_recall_nonllm", "RAGAS NonLLMContextRecall: the share of HERB's evidence records whose text a "
                              "retrieved text matches more than 0.5 (Levenshtein)." + COMPARE_INSIDE, "0 to 1"),
    ("context_precision_nonllm", "RAGAS NonLLMContextPrecisionWithReference: the retrieved texts that match the text "
                                 "of an evidence record more than 0.5 (Levenshtein), weighted by rank."
                                 + COMPARE_INSIDE, "0 to 1"),
    ("semantic_similarity", "RAGAS SemanticSimilarity: the cosine of the answer and the reference answer, both "
                            "embedded by the embedding model.", "0 to 1"),
    ("string_similarity", "RAGAS NonLLMStringSimilarity: the answer against the reference answer, Levenshtein.",
     "0 to 1"),
    ("bleu", "RAGAS BleuScore: the answer against the reference answer, n-gram precision with a brevity penalty.",
     "0 to 1"),
    ("rouge", "RAGAS RougeScore: the answer against the reference answer, ROUGE-L F-measure.", "0 to 1"),
    ("chrf", "RAGAS ChrfScore: the answer against the reference answer, character n-gram F-score.", "0 to 1"),
    ("exact_match", "RAGAS ExactMatch: 1 when the answer is exactly the reference answer, else 0.", "0 or 1"),
    ("string_presence", "RAGAS StringPresence: 1 when the answer contains the reference answer, else 0.", "0 or 1"),
]
QUESTIONS = [
    ("question_id", "The question: the name of HERB's product file, 'a' for answerable, and the question's "
                    "position, counted from 0, in that file's list of answerable questions.", ""),
    ("question_type", "The question's type, as HERB gives it.", ""),
    ("question", "The question, from HERB.", ""),
    ("answer", "The answer that the answer model wrote from the retrieved text.", ""),
    *SCORES,
    ("search_seconds", "Time of the arm's own search, without its model calls.", "seconds"),
    ("interpreter_seconds", "Time of the interpreter: the arm's call to a language model before its search. "
                            "Empty for an arm without an interpreter.", "seconds"),
    ("query_embedding_seconds", "Time of the arm's embedding of the question. Empty for an arm that embeds "
                                "nothing.", "seconds"),
    ("answer_seconds", "Time of the answer model's call.", "seconds"),
    ("total_seconds", "Time of all the work on the question, from the question to the answer.", "seconds"),
    ("interpreter_tokens_in", "Tokens sent to the interpreter. Empty for an arm without an interpreter.", "tokens"),
    ("interpreter_tokens_out", "Tokens that the interpreter wrote.", "tokens"),
    ("query_embedding_tokens", "Tokens that the arm embedded for the question. Empty for an arm that embeds "
                               "nothing.", "tokens"),
    ("answer_tokens_in", "Tokens sent to the answer model.", "tokens"),
    ("answer_tokens_out", "Tokens that the answer model wrote.", "tokens"),
]
RECORDS = [
    ("question_id", "The question, as in the questions sheet.", ""),
    ("rank", "The position of the retrieved text in the arm's order, from 1. The records of one text share "
             "a rank, and one record can stand in more than one text.", "position"),
    ("record_id", "The id of a HERB corpus record in that text.", ""),
    ("given_in_full", "FALSE for the records of the last text, which was cut at the character limit: only the "
                      "start of that text was given to the answer model.", "TRUE or FALSE"),
]
RUN = [
    ("arm", "The retrieval method.", ""),
    ("dataset", "The dataset that the questions and the corpus records come from.", ""),
    ("dataset_licence", "The dataset's licence: give its name as the source, and use the data for "
                        "non-commercial purposes only.", ""),
    ("questions", "Questions given to the run.", "count"),
    ("answered", "Questions answered.", "count"),
    ("failed", "Questions not answered.", "count"),
    ("character_limit", "The most characters of retrieved text given to the answer model for one question.",
     "characters"),
    ("interpreter_model", "The language model of the interpreter. Empty for an arm without an interpreter.", ""),
    ("answer_model", "The language model that wrote every answer.", ""),
    ("judge_model", "The language model that judged for the RAGAS scores that need a judge.", ""),
    ("embedding_model", "The embedding model: for the arm's own embeddings, and for the RAGAS scores that "
                        "compare by embeddings.", ""),
    ("run_date", "The date (UTC) when the run started.", "date"),
    ("machine_cpu", "The processor of the machine that made the run.", ""),
    ("machine_threads", "Threads of that processor.", "count"),
    ("machine_ram_bytes", "Memory of that machine.", "bytes"),
    ("machine_os", "The operating system of that machine.", ""),
    ("run_seconds", "Time of the whole run over all questions. A time when the machine slept is not counted.",
     "seconds"),
    ("cpu_seconds", "Processor time of the run's own process. The language-model calls run in other processes "
                    "and are not in it.", "seconds"),
    ("peak_memory_bytes", "The largest memory use of the run's own process.", "bytes"),
    ("judge_tokens_in", "The evaluation's cost: tokens sent to the judge model for all questions.", "tokens"),
    ("judge_tokens_out", "The evaluation's cost: tokens that the judge model wrote for all questions.", "tokens"),
    ("judge_embedding_tokens", "The evaluation's cost: tokens that the evaluation embedded.", "tokens"),
    ("judging_seconds", "The evaluation's cost: time of the scoring of all questions, after the run.", "seconds"),
]
INDEX_KIND = {"lucene": ("BM25 full-text index", "corpus record"),
              "vector": ("dense vector index", "corpus record"),
              "artefact": ("graph database (Neo4j)", "chunk: one or more corpus records")}
# a model's rows in the construction, by kind: (row, meaning, its value in the model's build entry)
MODEL_ROWS = {
    "chat": [("calls", "Calls to {m} that the build's records count.", "calls"),
             ("tokens in", "Tokens sent to {m} in the build.", "tokens_in"),
             ("tokens out", "Tokens that {m} wrote in the build.", "tokens_out"),
             ("seconds", "Time that {m} worked in the build, from start to end.", "seconds_elapsed")],
    "embed": [("texts embedded", "Texts that {m} embedded in the build, one request each.", "calls"),
              ("tokens", "Tokens of those texts.", "tokens_in"),
              ("seconds", "Time that {m} worked in the build, from start to end.", "seconds_elapsed")],
    "encoder": [("seconds", "Time that {m} worked in the build, from start to end.", "seconds_elapsed")],
}
HARDWARE = {"lucene": "laptop CPU", "vector": "desktop, NVIDIA GeForce GTX 1080 Ti",
            "artefact": "laptop; desktop, NVIDIA GeForce GTX 1080 Ti; Colab GPU; the model providers' services"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def one(values, what):
    values = list(values)
    if any(v != values[0] for v in values):
        sys.exit(f"{what} differs between questions; this export reads one")
    return values[0]


def runs_tables(arm, folder):
    d = ROOT / "output/k=chars" / folder
    man, ev = read(d / "run_manifest.json"), read(d / "eval_manifest.json")
    if len(man["legs"]) != 1 or len(ev["judge_legs"]) != 1:
        sys.exit(f"{arm}: more than one start; this export reads one")
    leg, js, env = man["legs"][0], ev["judge_settings"], man["environment"]
    if env["cpu"] not in CPU:
        sys.exit(f"{arm}: a processor this export does not name: {env['cpu']}")
    cells = {}
    for r in rows(d / "eval_results.jsonl"):
        cells.setdefault(r["question_id"], {})[r["metric"]] = r
    questions, records = [], []
    for r in rows(d / "arm_outputs.jsonl"):
        own = {}
        for e in r["retrieval"]:
            if e["kind"] in own:
                sys.exit(f"{arm} {r['id']}: two {e['kind']} models in the arm's own calls")
            own[e["kind"]] = e
        texts, cut = r["contexts"], r["meta"]["char_budget"].get("boundary")
        if arm == "artefact":
            id_lists = r["meta"]["chunk_ids"]
        else:
            id_lists = [[i] for i in r["context_ids"]] + ([[cut["id"]]] if cut else [])
        whole = [not (cut and n == len(texts) - 1) for n in range(len(texts))]
        counted = list(dict.fromkeys(str(i) for ids, w in zip(id_lists, whole) if w for i in ids))
        if len(id_lists) != len(texts) or counted != [str(i) for i in r["context_ids"]]:
            sys.exit(f"{arm} {r['id']}: the record ids do not line up with the retrieved texts")
        for rank, (ids, w) in enumerate(zip(id_lists, whole), 1):
            records += [{"question_id": r["id"], "rank": rank, "record_id": str(i), "given_in_full": w} for i in ids]
        mine = cells[r["id"]]
        if set(mine) != {s for s, _, _ in SCORES} or any(c["status"] != "ok" for c in mine.values()):
            sys.exit(f"{arm} {r['id']}: not every score is there and ok")
        g, interp, qe = r["generator"], own.get("chat"), own.get("embed")
        questions.append({
            "question_id": r["id"],
            "question_type": one((c["type"] for c in mine.values()), f"{r['id']} type"),
            "question": r["question"],
            "answer": r["answer"],
            **{s: mine[s]["value"] for s, _, _ in SCORES},
            "search_seconds": r["search_time_s"],
            "interpreter_seconds": interp and interp["time_s"],
            "query_embedding_seconds": qe and qe["time_s"],
            "answer_seconds": g["time_s"],
            "total_seconds": r["timing"]["wall_s"],
            "interpreter_tokens_in": interp and interp["tokens_in"],
            "interpreter_tokens_out": interp and interp["tokens_out"],
            "query_embedding_tokens": qe and qe["tokens_in"],
            "answer_tokens_in": g["tokens_in"],
            "answer_tokens_out": g["tokens_out"],
        })
    use = [c["components"]["usage"] for q in cells.values() for c in q.values()]
    judge = ev["judge_usage"]
    if (sum(u["chat_calls"] for u in use), sum(u["tokens_in"] for u in use), sum(u["tokens_out"] for u in use)) \
            != (judge["calls"], judge["tokens_in"], judge["tokens_out"]) or any(u.get("embed_calls") for u in use):
        sys.exit(f"{arm}: the scores' judge cost does not add up to the evaluation's")
    run = {
        "arm": arm, "dataset": DATASET, "dataset_licence": LICENCE,
        "questions": man["n_questions"], "answered": man["n_ran"], "failed": man["n_failed"],
        "character_limit": man["char_budget"],
        "interpreter_model": man["interpreter_model"], "answer_model": man["generator_model"],
        "judge_model": ev["judge_model"], "embedding_model": env["embedder"]["model"],
        "run_date": leg["started_at"][:10],
        "machine_cpu": CPU[env["cpu"]], "machine_threads": env["cpu_count"], "machine_ram_bytes": env["ram_bytes"],
        "machine_os": env["platform"],
        "run_seconds": leg["wall_s"], "cpu_seconds": leg["process_cpu_s"], "peak_memory_bytes": leg["peak_memory_bytes"],
        "judge_tokens_in": judge["tokens_in"], "judge_tokens_out": judge["tokens_out"],
        "judge_embedding_tokens": js["embedding"]["tokens_in"], "judging_seconds": js["wall_s"],
    }
    tables = [("questions", QUESTIONS, questions), ("records", RECORDS, records), ("run", RUN, [run])]
    key = [{"sheet": name, "column": c, "meaning": m, "unit": u} for name, columns, _ in tables for c, m, u in columns]
    return [(name, [c for c, _, _ in columns], table) for name, columns, table in tables], \
        (["sheet", "column", "meaning", "unit"], key)


def construction_table():
    """One row per thing, one column per arm: what building each arm's index cost, one model at a time."""
    built = {}
    for arm, folder in RUNS.items():
        man = read(ROOT / "output/k=chars" / folder / "run_manifest.json")
        units = man["index"]["counts"]["chunks"] if arm == "artefact" else man["index"]["units"]
        built[arm] = (man["build_stats"], units)
    things = [("index", "What the arm searches.", {a: INDEX_KIND[a][0] for a in RUNS}),
              ("unit", "What one unit of the index is.", {a: INDEX_KIND[a][1] for a in RUNS}),
              ("units in the index", "How many units the arm searches.", {a: built[a][1] for a in RUNS}),
              ("build time, seconds", "Time to build the index. Lucene builds it in memory at the start of each "
                                      "run. Vector's is the time to embed every record once. The artefact's is the "
                                      "time of each step of its build, added; the time between the steps is not "
                                      "counted.", {a: built[a][0]["build_time_s"] for a in RUNS})]
    models = {}
    for arm in RUNS:
        for e in built[arm][0]["models"]:
            models.setdefault((e["kind"], e["model"]), {})[arm] = e
    for (kind, model), by_arm in models.items():
        for row, meaning, field in MODEL_ROWS[kind]:
            things.append((f"{model}, {row}", meaning.format(m=model), {a: e[field] for a, e in by_arm.items()}))
    things.append(("hardware", "Where the index was built.", HARDWARE))
    table = [{"thing": t, **{a: values.get(a) for a in RUNS}} for t, _, values in things]
    key = [{"thing": t, "meaning": m} for t, m, _ in things]
    return [("construction", ["thing", *RUNS], table)], (["thing", "meaning"], key)


WIDE = {"question": 60, "answer": 80, "meaning": 100, "thing": 50}


def workbook(path, title, tables, key):
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.title, wb.properties.creator = title, ""
    for name, heads, table in tables + [("key", *key)]:
        ws = wb.create_sheet(name)
        ws.append(heads)
        for row in table:
            if set(row) != set(heads):
                sys.exit(f"{path.name} {name}: a row's columns differ from the sheet's")
            ws.append([row[h] for h in heads])
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, h in enumerate(heads, 1):
            longest = max([len(h)] + [len(str(r[h])) for r in table[:200] if r[h] is not None])
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(WIDE.get(h, 40), max(10, longest + 2))
    wb.save(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(ROOT / "finished_data"))
    out = Path(p.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    books = [(f"{arm}_runs", runs_tables(arm, folder)) for arm, folder in RUNS.items()]
    books.append(("construction", construction_table()))
    for name, (tables, key) in books:
        path = out / f"{name}.xlsx"
        workbook(path, name.replace("_", " "), tables, key)
        print(f"{path.name}: {path.stat().st_size:,} bytes, sheets {[n for n, _, _ in tables] + ['key']}, "
              f"rows {[len(t) for _, _, t in tables]}")


if __name__ == "__main__":
    main()
