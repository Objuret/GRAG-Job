"""The finished data, for giving away: for each arm one workbook of its run and one of its
construction, values only, with the same sheets and columns for every arm.

    python tools/export_finished_data.py [--out finished_data]

Needs openpyxl. Reads the three final run folders, the graph's build cost and the facet layer's
records, and writes six .xlsx files. A column is a measure he named (times, tokens, runtime, build
cost, the abstract's scores) or an id of the dataset, the evaluation or the run; nothing else goes
in, and nothing that belongs to this machine or this project: no path, host, user, session,
repository file, commit, note or reason. The data sheet comes first; the last sheet is the key.
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
BAKE_OFF = ("tasksource__deberta-small-long-nli", "tasksource__deberta-base-long-nli",
            "Alibaba-NLP__gte-reranker-modernbert-base", "BAAI__bge-reranker-v2-m3")
COMPARE_INSIDE = " It counts per retrieved text, so compare it inside one arm only."

# (column, meaning, unit) for every sheet; the key sheet is written from these lists
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
BUILD = [
    ("step", "The step of the build.", ""),
    ("part", "The part of the step.", ""),
    ("date", "The date (UTC) when the part was made.", "date"),
    ("model", "The model that the part used. Empty where it used no model, or where it fitted a small model "
              "of its own.", ""),
    ("device", "Where the part ran.", ""),
    ("calls", "Calls to a language model that gave an answer, or requests to an embedding model. Empty where "
              "the part made no calls, or where they were not counted.", "count"),
    ("tokens_in", "Tokens sent to the model. Empty where not counted.", "tokens"),
    ("tokens_out", "Tokens that the model wrote. 0 for an embedding model or an encoder.", "tokens"),
    ("seconds", "Time of the part, from its start to its end. Empty where not measured.", "seconds"),
]
INDEX = [
    ("name", "What the index holds.", ""),
    ("value", "How many.", "count"),
]
KEY = [("sheet", "", ""), ("column", "", ""), ("meaning", "", ""), ("unit", "", "")]


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
    return [("questions", QUESTIONS, questions), ("records", RECORDS, records), ("run", RUN, [run])]


def part(step, name, date, model, device, calls=None, tokens_in=None, tokens_out=None, seconds=None):
    return {"step": step, "part": name, "date": date, "model": model, "device": device, "calls": calls,
            "tokens_in": tokens_in, "tokens_out": tokens_out, "seconds": None if seconds is None else float(seconds)}


def artefact_parts(cost):
    steps = {s["id"]: s for s in cost["steps"]}

    def left_out(step, starts):
        hits = [x["values"] for x in cost["left_out"] if x["step"] == step and x["what"].startswith(starts)]
        if len(hits) != 1:
            sys.exit(f"build_cost.json left_out: not one entry {step!r} {starts!r}")
        return hits[0]

    c, t = steps["chunks"], steps["descriptions_and_tags"]
    g, e, f, later = (steps[k] for k in ("graph_copies", "embeddings", "facet_layer", "later_edges_and_fields"))
    haiku, tagger = "claude-haiku-4-5-20251001", "Anthropic API, 4 calls at a time"
    neo4j, desktop = "Neo4j on the laptop", "desktop, NVIDIA GeForce GTX 1080 Ti"
    parts = [part("chunks", "the corpus cut into chunks", c["date"], None, "laptop"),
             part("chunks", "question, unanswerable-question and product-profile chunks taken out", "2026-05-19",
                  None, "laptop")]
    passes, main = t["whole_run"]["by_pass"], t["whole_run"]["main"]
    pass_s = left_out("descriptions_and_tags", "per-pass elapsed")
    extract_calls = main["calls_with_usage"] - sum(passes[p]["calls"] for p in ("score_tags", "describe", "score"))
    for name, label, n in (("extract", "per chunk, a description and its tags", extract_calls),
                           ("score_tags", "per chunk, five facet scores for each of its tags", passes["score_tags"]["calls"]),
                           ("describe", "per file, a description", passes["describe"]["calls"]),
                           ("score", "per file, a relevance score for each of its chunks", passes["score"]["calls"])):
        p = passes[name]
        parts.append(part("descriptions and tags", label, t["date"], haiku, tagger, calls=n, tokens_in=p["tokens_in"],
                          tokens_out=p["tokens_out"], seconds=pass_s[name]))
    rec_by = left_out("descriptions_and_tags", "the recovery by pass")
    rec_s = left_out("descriptions_and_tags", "the recovery's elapsed and its passes")
    for name, label in (("extract", "again: per chunk, a description and its tags"),
                        ("score_tags", "again: per chunk, five facet scores for each of its tags"),
                        ("score", "again: per file, a relevance score for each of its chunks"),
                        ("score_recovery", "again: relevance scores of single chunks")):
        n, tin, tout, _ = rec_by[name]
        parts.append(part("descriptions and tags", label, t["date"], haiku, tagger, calls=n, tokens_in=tin,
                          tokens_out=tout, seconds=rec_s[name]))
    gs = g["seconds"]
    parts += [part("graph copies", "the graph copied", "2026-08-12", None, neo4j, seconds=gs["herb_eval_v2_copy_elapsed"]),
              part("graph copies", "4,111 tags taken out, with their 5,470 edges", "2026-08-12", None, neo4j,
                   seconds=gs["herb_eval_v2_cleanup_elapsed"]),
              part("graph copies", "the cleaned graph copied", "2026-08-16", None, neo4j,
                   seconds=gs["volmax_copy_from_its_console_print"]),
              part("graph copies", "the entities planned", "2026-08-16", None, neo4j, seconds=gs["volmax_entity_plan_elapsed"]),
              part("graph copies", "the entity nodes added", "2026-08-16", None, neo4j, seconds=gs["volmax_entities_elapsed"])]
    ep, embed = e["parts"], "nvidia/llama-nemotron-embed-1b-v2"
    for key, label in (("tags", "every tag embedded"),
                       ("tags_with_underscores_in_readable_form", "tags with underscores embedded in readable form"),
                       ("descriptions", "every chunk description embedded")):
        p = ep[key]
        parts.append(part("embeddings", label, e["date"], embed, desktop if "1080" in p["device"] else "laptop CPU",
                          calls=p["texts"], tokens_in=p["tokens_in"], tokens_out=0, seconds=p["seconds_elapsed"]))
    parts += [part("embeddings", "the tag vectors written to the graph", e["date"], None, neo4j,
                   seconds=ep["write_tag_vectors"]["seconds_elapsed"]),
              part("embeddings", "the description vectors written to the graph", e["date"], None, neo4j,
                   seconds=ep["write_description_vectors"]["seconds_elapsed"])]
    fp, pairs = f["parts"], ROOT / "output/facet_pairs"
    opus = fp["opus_judgements"]
    runs = left_out("facet_layer", "the Opus judge runs one by one")
    paused = left_out("facet_layer", "the paused held-out run")
    started = {k: read(pairs / f"answers/manifest.{k}.0of1.json")["start"][:10]
               for k in ("control", "train_round0", "heldout")}
    judged = [("control pairs", started["control"], runs["control"]),
              ("training pairs", started["train_round0"], runs["train"]),
              ("held-out pairs, the run that was paused", paused["first_answer"][:10],
               [paused["calls"], paused["tokens_in"], paused["tokens_out"], paused["seconds_summed_per_call"], None]),
              ("held-out pairs, the run resumed", started["heldout"], runs["heldout_resumed"])]
    if [sum(v[i] for _, _, v in judged) for i in range(3)] != [opus["calls"], opus["tokens_in"], opus["tokens_out"]]:
        sys.exit("the Opus judge runs do not add up to the step's numbers")
    for label, date, (n, tin, tout, _, el) in judged:
        parts.append(part("facet layer", f"pairs of tag-to-chunk edges judged: {label}", date, "claude-opus-5",
                          "Claude Code, effort high, 8 calls at a time", calls=n, tokens_in=tin, tokens_out=tout,
                          seconds=el))
    bake = fp["encoder_bake_off"]
    metas = [read(pairs / "bakeoff/cache" / f"{m}.meta.json") for m in BAKE_OFF]
    if round(sum(m["seconds"] for m in metas), 1) != bake["seconds_elapsed"] or {m["edges"] for m in metas} != {bake["edges"]}:
        sys.exit("the bake-off's records do not add up to the step's numbers")
    for m in metas:
        parts.append(part("facet layer", "encoder candidate: 5,469 edges encoded for the bake-off", m["written"][:10],
                          m["model"], "Colab, NVIDIA GPU (CUDA)", tokens_out=0, seconds=m["seconds"]))
    cache, head, refits, write = (fp[k] for k in ("encoder_cache", "head_selection_training_scoring",
                                                  "bootstrap_refits", "write"))
    cache_meta = read(pairs / "fullcache" / f"{BAKE_OFF[2]}.meta.json")
    if cache_meta["model"] != cache["model"].split(", ")[0]:
        sys.exit("the encoder cache's record names another model")
    parts += [part("facet layer", "the bake-off's report", read(pairs / "bakeoff/results/summary.json")["written"][:10],
                   None, "laptop", seconds=bake["report_seconds_on_the_laptop"]),
              part("facet layer", "every edge encoded", cache_meta["written"][:10], cache_meta["model"], desktop,
                   tokens_out=0, seconds=cache["seconds_elapsed"]),
              part("facet layer", "the facet head selected, trained and scored",
                   read(pairs / "rounds/round1/eval.json")["written"][:10], None, "laptop CPU",
                   seconds=head["seconds_elapsed"]),
              # the refits' scores file (rounds/round1/bootstrap/scores_b24.npz) was written 2026-09-21T00:09Z
              part("facet layer", "24 bootstrap refits of the head", "2026-09-21", None, "laptop",
                   seconds=refits["seconds_elapsed"]),
              part("facet layer", "the graph backed up", "2026-10-08", None, neo4j, seconds=write["backup_seconds"]),
              part("facet layer", "the facet values written to the edges", "2026-10-08", None, neo4j,
                   seconds=write["seconds_elapsed"])]
    ls = later["seconds"]
    parts += [part("later edges", "person-to-chunk edges", "2026-10-17", None, "laptop",
                   seconds=ls["person_edges_tool_span"]),
              part("later edges", "the structure nodes' names and the customer-to-chunk edges", "2026-10-19", None,
                   "laptop", seconds=ls["structure_names_and_customer_edges_tool_span"]),
              part("later edges", "each chunk's record times", "2026-10-19", None, "laptop",
                   seconds=ls["chunk_times_tool_span"])]
    return parts


def construction_tables(arm, folder):
    d = ROOT / "output/k=chars" / folder
    man = read(d / "run_manifest.json")
    idx, bs = man["index"], man["build_stats"]
    if arm == "lucene":
        parts = [part("index", "the BM25 index built in memory at the start of the run",
                      man["legs"][0]["started_at"][:10], None, "laptop CPU", seconds=bs["build_time_s"])]
        counts = [("records", idx["units"]), ("characters of all record texts", idx["text_chars"])]
    elif arm == "vector":
        note, m = idx["cache_cost_note"], bs["models"][0]
        parts = [part("index", "every record of the corpus embedded", note["made_utc"][:10], m["model"],
                      "desktop, " + m["device"], calls=m["calls"], tokens_in=m["tokens_in"], tokens_out=m["tokens_out"],
                      seconds=m["seconds_elapsed"])]
        counts = [("records", idx["units"]), ("characters of all record texts", idx["text_chars"]),
                  ("vectors", idx["matrix_shape"][0]), ("dimensions of a vector", idx["matrix_shape"][1])]
    else:
        c, census = idx["counts"], man["graph"]["census"]
        labels, edges = census["labels"], census["relationships"]
        parts = artefact_parts(read(ROOT / "test/graph/build_cost.json"))
        counts = [("files", labels["File"]), ("products", labels["Product"]), ("channels", labels["Channel"]),
                  ("employees", labels["Employee"]), ("customers", labels["Customer"]),
                  ("companies", labels["Company"]), ("record kinds", labels["Kind"]),
                  ("organisations", labels["Org"]), ("roles", labels["Role"]),
                  ("chunks in the graph", labels["Chunk"]), ("chunks the arm searches", c["chunks"]),
                  ("tags in the graph", labels["Tag"]), ("tags on the chunks the arm searches", c["graph_tags"]),
                  ("tag-to-chunk edges in the graph", edges["HAS_TAG Chunk Tag"]),
                  ("tag-to-chunk edges on the chunks the arm searches", c["edges"]),
                  ("person-to-chunk edges", edges["chunk Employee Chunk"]),
                  ("customer-to-chunk edges", edges["chunk Customer Chunk"]),
                  ("chunks with their records' times", c["chunks_with_a_time"])]
    return [("build", BUILD, parts), ("index", INDEX, [{"name": n, "value": v} for n, v in counts])]


WIDE = {"question": 60, "answer": 80, "meaning": 100, "part": 60}


def workbook(path, title, tables):
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.title, wb.properties.creator = title, ""
    key = []
    for name, columns, table in tables + [("key", KEY, None)]:
        ws = wb.create_sheet(name)
        if table is None:
            table = key
        heads = [c for c, _, _ in columns]
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
        key += [{"sheet": name, "column": c, "meaning": m, "unit": u} for c, m, u in columns if name != "key"]
    wb.save(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(ROOT / "finished_data"))
    out = Path(p.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    for arm, folder in RUNS.items():
        for kind, tables in (("runs", runs_tables(arm, folder)), ("construction", construction_tables(arm, folder))):
            path = out / f"{arm}_{kind}.xlsx"
            workbook(path, f"{arm} {kind}", tables)
            print(f"{path.name}: {path.stat().st_size:,} bytes, sheets {[n for n, _, _ in tables] + ['key']}, "
                  f"rows {[len(t) for _, _, t in tables]}")


if __name__ == "__main__":
    main()
