"""The finished data, for giving away: one workbook, values only: the questions of the three
arms in one sheet, the runs and the construction with a column for each arm.

    python tools/export_finished_data.py [--out finished_data]

Needs openpyxl. Reads the three final run folders and the graph's build cost
(test/graph/build_cost.json), and writes finished_data.xlsx. A column of a run is a measure he named
(times, tokens, runtime, the RAGAS scores) or an id of the dataset, the evaluation or the run; the
construction holds what built the index that each final run read, one model at a time, and nothing
about how it was built. Nothing that belongs to this machine or this project
goes in: no path, host, user, session, repository file, commit, note or reason. The data sheets
come first; the last sheet is the key.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parent.parent
RUNS = {"lucene": "lucene__gold100__cb72000__20261008T234209Z",
        "vector": "vector__gold100__cb72000__20261017T061242Z",
        "artefact": "artefact_v4__gold100__cb72000__20261020T041923Z"}
DATASET, LICENCE = "HERB (Salesforce AI Research)", "CC BY-NC 4.0"
COMPARE_INSIDE = " It counts per retrieved text, so compare it inside one arm only."

# (column, meaning, unit) for every sheet of a run; the key sheet is written from these lists
SCORES = [
    ("faithfulness", "RAGAS Faithfulness: how factually consistent the answer is with the retrieved text. "
                     "The judge model reads the answer's claims against the retrieved text.", "0 to 1"),
    ("answer_correctness", "RAGAS AnswerCorrectness: the answer against HERB's reference answer: 0.75 times the "
                           "F1 of the claims that the judge model finds in both, plus 0.25 times "
                           "semantic_similarity.", "0 to 1"),
    ("context_recall_id", "RAGAS IDBasedContextRecall: the share of HERB's evidence records for the question that "
                          "are among the retrieved records.", "0 to 1"),
    ("context_precision_id", "RAGAS IDBasedContextPrecision: the share of the retrieved records that are HERB "
                             "evidence records for the question.", "0 to 1"),
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
    ("arm", "The retrieval method.", ""),
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
# the same for the three arms; the export stops if an arm differs
SETUP = [
    ("dataset", "The dataset that the questions and the corpus records come from.", ""),
    ("dataset_licence", "The dataset's licence: give its name as the source, and use the data for "
                        "non-commercial purposes only.", ""),
    ("character_limit", "The most characters of retrieved text given to the answer model for one question.",
     "characters"),
    ("answer_model", "The language model that wrote every answer.", ""),
    ("judge_model", "The language model that judged for the RAGAS scores that need a judge.", ""),
    ("embedding_model", "The embedding model: for the arm's own embeddings, and for the RAGAS scores that "
                        "compare by embeddings.", ""),
]
RUN = [
    ("run_seconds", "Time of the whole run over all questions. A time when the machine slept is not counted.",
     "seconds"),
    ("judge_tokens_in", "The evaluation's cost: tokens sent to the judge model for all questions.", "tokens"),
    ("judge_tokens_out", "The evaluation's cost: tokens that the judge model wrote for all questions.", "tokens"),
    ("judge_embedding_tokens", "The evaluation's cost: tokens that the evaluation embedded.", "tokens"),
    ("judging_seconds", "The evaluation's cost: time of the scoring of all questions, after the run.", "seconds"),
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


def runs_tables(arm, folder):
    d = ROOT / "output/k=chars" / folder
    man, ev = read(d / "run_manifest.json"), read(d / "eval_manifest.json")
    if len(man["legs"]) != 1 or len(ev["judge_legs"]) != 1:
        sys.exit(f"{arm}: more than one start; this export reads one")
    leg, js, env = man["legs"][0], ev["judge_settings"], man["environment"]
    if (man["n_questions"], man["n_ran"], man["n_failed"]) != (100, 100, 0):
        sys.exit(f"{arm}: not every one of the hundred questions was answered")
    cells = {}
    for r in rows(d / "eval_results.jsonl"):
        cells.setdefault(r["question_id"], {})[r["metric"]] = r
    questions = []
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
        mine = cells[r["id"]]
        if set(mine) != {s for s, _, _ in SCORES} or any(c["status"] != "ok" for c in mine.values()):
            sys.exit(f"{arm} {r['id']}: not every score is there and ok")
        g, interp, qe = r["generator"], own.get("chat"), own.get("embed")
        questions.append({
            "arm": arm,
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
    setup = {
        "dataset": DATASET, "dataset_licence": LICENCE,
        "character_limit": man["char_budget"], "answer_model": model_name(man["generator_model"]),
        "judge_model": model_name(ev["judge_model"]), "embedding_model": model_name(env["embedder"]["model"]),
    }
    # his 2026-10-21 "cba adding interpreter, it's just the answer model"
    if man["interpreter_model"] is not None and model_name(man["interpreter_model"]) != setup["answer_model"]:
        sys.exit(f"{arm}: the interpreter's model is not the answer model")
    run = {
        "run_seconds": leg["wall_s"],
        "judge_tokens_in": judge["tokens_in"], "judge_tokens_out": judge["tokens_out"],
        "judge_embedding_tokens": js["embedding"]["tokens_in"], "judging_seconds": js["wall_s"],
    }
    return questions, setup, run


def construction_table():
    """One row per property, one column per arm: what built the index that the final run read, one model
    at a time (his 2026-10-21 "The ONLY thing that matters, at all, is the iteration that ran the
    RAGAS"). For the artefact that is read from test/graph/build_cost.json: the descriptions and tags
    of the chunks in the graph, the vectors, the Opus judgements the facet network learned from, the
    encoding of every edge, and the steps with no model; work replaced later, trials and tests stay
    out."""
    mans = {a: read(ROOT / "output/k=chars" / f / "run_manifest.json") for a, f in RUNS.items()}
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
    if model_name(mans["artefact"]["environment"]["embedder"]["model"]) != embedder:
        sys.exit("the arms name different embedding models")
    encoder = model_name(facet["encoder_cache"]["model"].split(", ")[0])
    a = "artefact"
    things = [
        ("index", "What the arm searches.", {k: INDEX_KIND[k][0] for k in RUNS}),
        ("unit", "What one unit of the index is.", {k: INDEX_KIND[k][1] for k in RUNS}),
        ("units in the index", "How many units the arm searches.",
         {"lucene": mans["lucene"]["index"]["units"], "vector": mans["vector"]["index"]["units"],
          a: mans[a]["index"]["counts"]["chunks"]}),
        ("build time, seconds", "Time to build the index that the final run read. Lucene builds it in memory at "
                                "the start of each run. Vector's is the time to embed every record once. The "
                                "artefact's is the time of each step of its build, added; the time between the "
                                "steps is not counted.",
         {"lucene": mans["lucene"]["build_stats"]["build_time_s"], "vector": vector["seconds_elapsed"],
          a: haiku_seconds + embed_seconds + opus_seconds + encoder_seconds + no_model}),
        (f"{embedder}, texts embedded", f"Texts that {embedder} embedded for the index, one request each.",
         {"vector": vector["calls"], a: sum(p["texts"] for p in embedded)}),
        (f"{embedder}, tokens", "Tokens of those texts.",
         {"vector": vector["tokens_in"], a: sum(p["tokens_in"] for p in embedded)}),
        (f"{embedder}, seconds", f"Time that {embedder} worked for the index, from start to end.",
         {"vector": vector["seconds_elapsed"], a: embed_seconds}),
        ("claude-haiku-4-5, calls", "Calls to claude-haiku-4-5 for the index.", {a: graph_chunks["calls_with_usage"]}),
        ("claude-haiku-4-5, tokens in", "Tokens sent to claude-haiku-4-5 for the index.", {a: graph_chunks["tokens_in"]}),
        ("claude-haiku-4-5, tokens out", "Tokens that claude-haiku-4-5 wrote for the index.",
         {a: graph_chunks["tokens_out"]}),
        ("claude-haiku-4-5, seconds", "Time that claude-haiku-4-5 worked for the index: the time of the pass that "
                                      "wrote it, in the share of the calls' own time that the index's chunks took.",
         {a: haiku_seconds}),
        ("claude-opus-5, calls", "Calls to claude-opus-5 for the index.", {a: sum(r[0] for r in learned_from)}),
        ("claude-opus-5, tokens in", "Tokens sent to claude-opus-5 for the index.", {a: sum(r[1] for r in learned_from)}),
        ("claude-opus-5, tokens out", "Tokens that claude-opus-5 wrote for the index.",
         {a: sum(r[2] for r in learned_from)}),
        ("claude-opus-5, seconds", "Time that claude-opus-5 worked for the index, from start to end.", {a: opus_seconds}),
        (f"{encoder}, seconds", f"Time that {encoder} worked for the index, from start to end.", {a: encoder_seconds}),
    ]
    table = [{"property": t, **{k: values.get(k) for k in RUNS}} for t, _, values in things]
    return table, [{"sheet": "construction", "field": t, "meaning": m, "unit": ""} for t, m, _ in things]


WIDE = {"question": 60, "answer": 80, "meaning": 100, "property": 50}


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
    questions, setups, runs = [], {}, {}
    for arm, folder in RUNS.items():
        rows_of_arm, setups[arm], runs[arm] = runs_tables(arm, folder)
        questions += rows_of_arm
    setup = setups["lucene"]
    if any(s != setup for s in setups.values()):
        sys.exit("the arms differ in the setup; this export writes it once")
    # the run sheet: what is the same for the three arms once, then a table with a column per arm
    same = [{"property": c, "value": setup[c]} for c, _, _ in SETUP]
    run = [{"property": c, **{arm: runs[arm][c] for arm in RUNS}} for c, _, _ in RUN]
    construction, construction_key = construction_table()
    key = ([{"sheet": "questions", "field": c, "meaning": m, "unit": u} for c, m, u in QUESTIONS]
           + [{"sheet": "run", "field": c, "meaning": m, "unit": u} for c, m, u in SETUP + RUN] + construction_key)
    sheets = [("questions", [([c for c, _, _ in QUESTIONS], questions)]),
              ("run", [(["property", "value"], same), (["property", *RUNS], run)]),
              ("construction", [(["property", *RUNS], construction)]),
              ("key", [(["sheet", "field", "meaning", "unit"], key)])]
    path = out / "finished_data.xlsx"
    workbook(path, "finished data", sheets)
    print(f"{path.name}: {path.stat().st_size:,} bytes, sheets {[n for n, _ in sheets]}, "
          f"rows {[[len(t) for _, t in blocks] for _, blocks in sheets]}")


if __name__ == "__main__":
    main()
