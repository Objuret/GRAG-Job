"""The finished data, for giving away: one workbook, values only. Sheets: results (the three
arms' questions in one table), run data (what is the same for the arms once, then a column per
arm), arm construction (a column per arm), key.

    python tools/export_finished_data.py [--out finished_data]

Needs openpyxl. Reads the three final run folders and the graph's build cost
(test/graph/build_cost.json), and writes grag-data.xlsx. A column of a run is a measure he named
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
# the sheets' names
PER_QUESTION, PER_RUN, CONSTRUCTION, KEY = "results", "run data", "arm construction", "key"

# (field, meaning, unit): the data dictionary is written from these lists. A score's meaning is
# RAGAS's own definition (docs.ragas.io, available metrics) with the setting RAGAS 0.4.3 used.
SCORES = [
    ("faithfulness", "RAGAS Faithfulness. Claims in the answer supported by the retrieved context / all claims "
                     "in the answer.", "0-1"),
    ("answer_correctness", "RAGAS AnswerCorrectness. Weighted average of factual similarity to the reference "
                           "answer (weight 0.75) and semantic_similarity (weight 0.25). Reference answer: HERB's answer.", "0-1"),
    ("context_recall_id", "RAGAS IDBasedContextRecall. Reference context ids found in the retrieved context ids / "
                          "all reference context ids. Reference context ids: HERB's evidence record ids.", "0-1"),
    ("context_precision_id", "RAGAS IDBasedContextPrecision. Retrieved context ids found in the reference context "
                             "ids / all retrieved context ids.", "0-1"),
    ("context_recall_llm", "RAGAS LLMContextRecall. Claims in the reference answer supported by the retrieved "
                           "context / all claims in the reference answer.", "0-1"),
    ("context_recall_nonllm", "RAGAS NonLLMContextRecall. Relevant contexts retrieved / all reference contexts. "
                              "Relevant: Levenshtein similarity to a reference context of 0.5 or more. Reference context: text of a "
                              "HERB evidence record.", "0-1"),
    ("context_precision_nonllm", "RAGAS NonLLMContextPrecisionWithReference. Context precision@K: mean of "
                                 "precision@k over the ranks k of the relevant retrieved contexts. Relevant: "
                                 "Levenshtein similarity to a reference context of 0.5 or more.", "0-1"),
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
    ("question_type", "HERB question type.", ""),
    ("question", "Question, from HERB.", ""),
    ("answer", "Answer of the answer model.", ""),
    *SCORES,
    ("search_seconds", "Retrieval time, without the interpreter and the query embedding.", "seconds"),
    ("interpreter_seconds", "Time of the interpreter call: the answer model, called before retrieval. Artefact "
                            "only.", "seconds"),
    ("query_embedding_seconds", "Time to embed the query. Vector and artefact only.", "seconds"),
    ("answer_seconds", "Time of the answer model call.", "seconds"),
    ("total_seconds", "Time of all steps for the question, to the answer.", "seconds"),
    ("interpreter_tokens_in", "Input tokens of the interpreter call. Artefact only.", "tokens"),
    ("interpreter_tokens_out", "Output tokens of the interpreter call. Artefact only.", "tokens"),
    ("query_embedding_tokens", "Tokens embedded for the query. Vector and artefact only.", "tokens"),
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
    ("run_seconds", "Time of the run over the 100 questions.", "seconds"),
    ("judge_tokens_in", "Input tokens of all RAGAS judge calls.", "tokens"),
    ("judge_tokens_out", "Output tokens of all RAGAS judge calls.", "tokens"),
    ("judge_embedding_tokens", "Tokens embedded by RAGAS.", "tokens"),
    ("judging_seconds", "Time of the RAGAS evaluation over the 100 questions.", "seconds"),
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
    # run data: what is the same for the three arms once, then a table with a column per arm
    same = [{"property": c, "value": setup[c]} for c, _, _ in SETUP]
    run = [{"property": c, **{arm: runs[arm][c] for arm in RUNS}} for c, _, _ in RUN]
    construction, construction_key = construction_table()
    key = ([{"sheet": PER_QUESTION, "field": c, "meaning": m, "unit": u} for c, m, u in QUESTIONS]
           + [{"sheet": PER_RUN, "field": c, "meaning": m, "unit": u} for c, m, u in SETUP + RUN if m]
           + construction_key)
    sheets = [(PER_QUESTION, [([c for c, _, _ in QUESTIONS], questions)]),
              (PER_RUN, [(["property", "value"], same), (["property", *RUNS], run)]),
              (CONSTRUCTION, [(["property", *RUNS], construction)]),
              (KEY, [(["sheet", "field", "meaning", "unit"], key)])]
    path = out / "grag-data.xlsx"
    workbook(path, "grag data", sheets)
    print(f"{path.name}: {path.stat().st_size:,} bytes, sheets {[n for n, _ in sheets]}, "
          f"rows {[[len(t) for _, t in blocks] for _, blocks in sheets]}")


if __name__ == "__main__":
    main()
