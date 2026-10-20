"""The finished data, for giving away: for each arm one workbook of its run and one of its
construction, values only, with the same sheets and columns for every arm.

    python tools/export_finished_data.py [--out finished_data]

Needs openpyxl. Reads the three final run folders, the graph's build cost and the facet layer's
records, and writes six .xlsx files. Nothing that belongs to this machine or this project goes in:
no path, host, user, session, repository file, commit, note or reason. The data sheet comes first;
the last sheet of each workbook is its key: every column with its meaning and unit.
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
                          "are among the retrieved records (records sheet, cut FALSE).", "0 to 1"),
    ("context_precision_id", "RAGAS IDBasedContextPrecision: the share of the retrieved records (records sheet, "
                             "cut FALSE, each record once) that are HERB evidence records for the question.", "0 to 1"),
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
    ("retrieved_characters", "Characters of retrieved text given to the answer model.", "characters"),
    ("search_seconds", "Time of the arm's own search. The arm's model calls and embedding requests are not "
                       "in it; they have their own columns.", "seconds"),
    ("first_call_seconds", "Time of the arm's call to a language model before its search, tries and waits "
                           "included. Empty for an arm without that call.", "seconds"),
    ("query_embedding_seconds", "Time of the arm's embedding requests, added up. Empty for an arm that embeds "
                                "nothing.", "seconds"),
    ("answer_seconds", "Time of the answer call, from the request to the answer.", "seconds"),
    ("total_seconds", "Time of all the work on the question: search, model calls and answer. A time when the "
                      "machine slept is not counted.", "seconds"),
    ("first_call_tokens_in", "Tokens sent to the first-call model. Empty for an arm without that call.", "tokens"),
    ("first_call_tokens_out", "Tokens that the first-call model wrote.", "tokens"),
    ("first_call_cached_tokens", "The part of first_call_tokens_in that the model provider read from its "
                                 "prompt cache.", "tokens"),
    ("first_call_tries", "Tries of the first call. More than 1 when a try failed.", "count"),
    ("query_embedding_requests", "The arm's embedding requests for the question. Empty for an arm that embeds "
                                 "nothing.", "count"),
    ("query_embedding_tokens", "Tokens of the texts that the arm embedded.", "tokens"),
    ("answer_tokens_in", "Tokens sent to the answer model.", "tokens"),
    ("answer_tokens_out", "Tokens that the answer model wrote.", "tokens"),
    ("answer_cached_tokens", "The part of answer_tokens_in that the model provider read from its prompt "
                             "cache.", "tokens"),
    ("answer_tries", "Tries of the answer call. More than 1 when a try failed.", "count"),
    ("judge_calls", "Calls to the judge model for this question's scores.", "count"),
    ("judge_tokens_in", "Tokens sent to the judge model for this question's scores.", "tokens"),
    ("judge_tokens_out", "Tokens that the judge model wrote for this question's scores.", "tokens"),
    ("judge_cached_tokens", "The part of judge_tokens_in that the model provider read from its prompt cache.",
     "tokens"),
    ("judge_seconds", "Time of the judge calls for this question's scores, added up.", "seconds"),
]
RECORDS = [
    ("question_id", "The question, as in the questions sheet.", ""),
    ("rank", "The position of the retrieved text in the arm's order, from 1. The records of one text share "
             "a rank, and one record can stand in more than one text.", "position"),
    ("record_id", "The id of a HERB corpus record in that text.", ""),
    ("cut", "TRUE for the records of the last text, which was cut at the character limit: only the start of "
            "that text was given to the answer model.", "TRUE or FALSE"),
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
    ("answer_model", "The language model that wrote every answer.", ""),
    ("judge_model", "The language model that judged for the scores that need a judge.", ""),
    ("first_call_model", "The language model that the arm calls before its search. Empty for an arm without "
                         "that call.", ""),
    ("embedding_model", "The embedding model: for the arm's own embeddings, and for the scores that compare "
                        "by embeddings.", ""),
    ("run_date", "The date (UTC) when the run started.", "date"),
    ("machine_cpu", "The processor of the machine that made the run.", ""),
    ("machine_threads", "Threads of that processor.", "count"),
    ("machine_ram_bytes", "Memory of that machine.", "bytes"),
    ("machine_os", "The operating system of that machine.", ""),
    ("run_seconds", "Time of the whole run over all questions, index_load_seconds included. A time when the "
                    "machine slept is not counted.", "seconds"),
    ("index_load_seconds", "Time to get the arm's index ready before the first question.", "seconds"),
    ("embedder_load_seconds", "Time to load the embedding model in the run. Empty where the run loaded none.",
     "seconds"),
    ("cpu_seconds", "Processor time of the run's own process. The language-model calls run in other processes "
                    "and are not in it.", "seconds"),
    ("peak_memory_bytes", "The largest memory use of the run's own process.", "bytes"),
    ("judging_seconds", "Time of the scoring of all questions, after the run.", "seconds"),
    ("score_embedding_requests", "Embedding requests that the scoring made once, for all questions, before it "
                                 "scored.", "count"),
    ("score_embedding_tokens", "Tokens of the texts in those requests.", "tokens"),
    ("score_embedding_seconds", "Time of those requests, added up.", "seconds"),
]
BUILD = [
    ("step", "The step of the build.", ""),
    ("part", "The part of the step.", ""),
    ("date", "The date (UTC) when the part was made.", "date"),
    ("model", "The model that the part used. Empty where it used no model, or where it fitted a small model "
              "of its own.", ""),
    ("device", "Where the part ran.", ""),
    ("count", "How many things the part made or handled. Empty where not counted.", "count"),
    ("count_of", "What count counts.", ""),
    ("calls", "Calls to a language model that gave an answer, or requests to an embedding model.", "count"),
    ("tries", "Every try of those calls, failed tries included. Empty where the tries were not counted.",
     "count"),
    ("tokens_in", "Tokens sent to the model.", "tokens"),
    ("tokens_out", "Tokens that the model wrote. 0 for an embedding model or an encoder.", "tokens"),
    ("seconds_start_to_end", "Time from the start to the end of the part. Empty where not measured.",
     "seconds"),
    ("seconds_of_calls_added_up", "The time of each call, added up. With several calls at the same time, it is "
                                  "more than seconds_start_to_end. Empty where not measured.", "seconds"),
    ("seconds_of_the_whole_command", "Time of the whole command that made the part, its backup and check "
                                     "included. Empty where not measured.", "seconds"),
]
INDEX = [
    ("name", "What is counted.", ""),
    ("value", "The count.", "count"),
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
            records += [{"question_id": r["id"], "rank": rank, "record_id": str(i), "cut": not w} for i in ids]
        mine = cells[r["id"]]
        if set(mine) != {s for s, _, _ in SCORES} or any(c["status"] != "ok" for c in mine.values()):
            sys.exit(f"{arm} {r['id']}: not every score is there and ok")
        use = [c["components"]["usage"] for c in mine.values()]
        if any(u.get("embed_calls") for u in use):
            sys.exit(f"{arm} {r['id']}: embedding requests inside a score; this export has no column for them")
        g, fc, qe = r["generator"], own.get("chat"), own.get("embed")
        questions.append({
            "question_id": r["id"],
            "question_type": one((c["type"] for c in mine.values()), f"{r['id']} type"),
            "question": r["question"],
            "answer": r["answer"],
            **{s: mine[s]["value"] for s, _, _ in SCORES},
            "retrieved_characters": r["meta"]["char_budget"]["chars"],
            "search_seconds": r["search_time_s"],
            "first_call_seconds": fc and fc["time_s"],
            "query_embedding_seconds": qe and qe["time_s"],
            "answer_seconds": g["time_s"],
            "total_seconds": r["timing"]["wall_s"],
            "first_call_tokens_in": fc and fc["tokens_in"],
            "first_call_tokens_out": fc and fc["tokens_out"],
            "first_call_cached_tokens": fc and fc["cached_input_tokens"],
            "first_call_tries": fc and fc["attempts"],
            "query_embedding_requests": qe and qe["calls"],
            "query_embedding_tokens": qe and qe["tokens_in"],
            "answer_tokens_in": g["tokens_in"],
            "answer_tokens_out": g["tokens_out"],
            "answer_cached_tokens": g["cached_input_tokens"],
            "answer_tries": g["attempts"],
            "judge_calls": sum(u["chat_calls"] for u in use),
            "judge_tokens_in": sum(u["tokens_in"] for u in use),
            "judge_tokens_out": sum(u["tokens_out"] for u in use),
            "judge_cached_tokens": sum(u["cached_input_tokens"] for u in use),
            "judge_seconds": sum(u["chat_s"] for u in use),
        })
    emb = js["embedding"]
    run = {
        "arm": arm, "dataset": DATASET, "dataset_licence": LICENCE,
        "questions": man["n_questions"], "answered": man["n_ran"], "failed": man["n_failed"],
        "character_limit": man["char_budget"],
        "answer_model": man["generator_model"], "judge_model": ev["judge_model"],
        "first_call_model": man["interpreter_model"], "embedding_model": env["embedder"]["model"],
        "run_date": leg["started_at"][:10],
        "machine_cpu": CPU[env["cpu"]], "machine_threads": env["cpu_count"], "machine_ram_bytes": env["ram_bytes"],
        "machine_os": env["platform"],
        "run_seconds": leg["wall_s"], "index_load_seconds": leg["prepare_s"],
        "embedder_load_seconds": leg["embedder_load_s"], "cpu_seconds": leg["process_cpu_s"],
        "peak_memory_bytes": leg["peak_memory_bytes"],
        "judging_seconds": js["wall_s"],
        "score_embedding_requests": emb["requests"], "score_embedding_tokens": emb["tokens_in"],
        "score_embedding_seconds": emb["encode_s"] + emb["lock_wait_s"],
    }
    return [("questions", QUESTIONS, questions), ("records", RECORDS, records), ("run", RUN, [run])]


def part(step, name, date, model, device, count=None, count_of=None, calls=None, tries=None, tokens_in=None,
         tokens_out=None, start_to_end=None, calls_added=None, command=None):
    def seconds(v):
        return None if v is None else float(v)
    return {"step": step, "part": name, "date": date, "model": model, "device": device, "count": count,
            "count_of": count_of, "calls": calls, "tries": tries, "tokens_in": tokens_in, "tokens_out": tokens_out,
            "seconds_start_to_end": seconds(start_to_end), "seconds_of_calls_added_up": seconds(calls_added),
            "seconds_of_the_whole_command": seconds(command)}


def artefact_parts(cost, counts):
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
    parts = [part("chunks", "the corpus cut into chunks", c["date"], None, "laptop", count=5843, count_of="chunks"),
             part("chunks", "question, unanswerable-question and product-profile chunks taken out", "2026-05-19",
                  None, "laptop", count=5843 - c["size"]["chunks_in_this_graph"], count_of="chunks")]
    passes, main = t["whole_run"]["by_pass"], t["whole_run"]["main"]
    pass_s = left_out("descriptions_and_tags", "per-pass elapsed")
    extract_calls = main["calls_with_usage"] - sum(passes[p]["calls"] for p in ("score_tags", "describe", "score"))
    # every second try of the main run is on an extract record; each of those records holds two tries
    retried = left_out("descriptions_and_tags", "time of the 48 retried calls")["records"]
    for name, label, n, tries, count, count_of in (
            ("extract", "per chunk, a description and its tags", extract_calls,
             passes["extract"]["records"] + retried, passes["extract"]["records"], "chunks"),
            ("score_tags", "per chunk, five facet scores for each of its tags", passes["score_tags"]["calls"],
             passes["score_tags"]["calls"], passes["score_tags"]["calls"], "chunks"),
            ("describe", "per file, a description", passes["describe"]["calls"], passes["describe"]["calls"],
             passes["describe"]["calls"], "files"),
            ("score", "per file, a relevance score for each of its chunks", passes["score"]["calls"],
             passes["score"]["calls"], passes["score"]["calls"], "files")):
        p = passes[name]
        parts.append(part("descriptions and tags", label, t["date"], haiku, tagger, count=count, count_of=count_of,
                          calls=n, tries=tries, tokens_in=p["tokens_in"], tokens_out=p["tokens_out"],
                          start_to_end=pass_s[name], calls_added=p["seconds_summed_per_call"]))
    rec_by = left_out("descriptions_and_tags", "the recovery by pass")
    rec_s = left_out("descriptions_and_tags", "the recovery's elapsed and its passes")
    for name, label in (("extract", "again: per chunk, a description and its tags"),
                        ("score_tags", "again: per chunk, five facet scores for each of its tags"),
                        ("score", "again: per file, a relevance score for each of its chunks"),
                        ("score_recovery", "again: relevance scores of single chunks")):
        n, tin, tout, secs = rec_by[name]
        parts.append(part("descriptions and tags", label, t["date"], haiku, tagger, calls=n, tokens_in=tin,
                          tokens_out=tout, start_to_end=rec_s[name], calls_added=secs))
    gs = g["seconds"]
    parts += [part("graph copies", "the graph copied", "2026-08-12", None, neo4j,
                   start_to_end=gs["herb_eval_v2_copy_elapsed"]),
              part("graph copies", "tags taken out, with their 5,470 edges", "2026-08-12", None, neo4j,
                   count=4111, count_of="tags", start_to_end=gs["herb_eval_v2_cleanup_elapsed"]),
              part("graph copies", "the cleaned graph copied", "2026-08-16", None, neo4j,
                   start_to_end=gs["volmax_copy_from_its_console_print"]),
              part("graph copies", "the entities planned", "2026-08-16", None, neo4j,
                   start_to_end=gs["volmax_entity_plan_elapsed"]),
              part("graph copies", "the entity nodes added", "2026-08-16", None, neo4j,
                   start_to_end=gs["volmax_entities_elapsed"])]
    ep, embed = e["parts"], "nvidia/llama-nemotron-embed-1b-v2"
    for key, label in (("tags", "every tag embedded"),
                       ("tags_with_underscores_in_readable_form", "tags with underscores embedded in readable form"),
                       ("descriptions", "every chunk description embedded")):
        p = ep[key]
        parts.append(part("embeddings", label, e["date"], embed, desktop if "1080" in p["device"] else "laptop CPU",
                          count=p["texts"], count_of="texts", calls=p["texts"], tries=p["texts"],
                          tokens_in=p["tokens_in"], tokens_out=0, start_to_end=p["seconds_elapsed"]))
    parts += [part("embeddings", "the tag vectors written to the graph", e["date"], None, neo4j,
                   count=ep["tags"]["texts"], count_of="vectors", start_to_end=ep["write_tag_vectors"]["seconds_elapsed"]),
              part("embeddings", "the description vectors written to the graph", e["date"], None, neo4j,
                   count=ep["descriptions"]["texts"], count_of="vectors",
                   start_to_end=ep["write_description_vectors"]["seconds_elapsed"])]
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
    for label, date, (n, tin, tout, secs, el) in judged:
        parts.append(part("facet layer", f"pairs of tag-to-chunk edges judged: {label}", date, "claude-opus-5",
                          "Claude Code, effort high, 8 calls at a time", count=n, count_of="pairs", calls=n,
                          tokens_in=tin, tokens_out=tout, start_to_end=el, calls_added=secs))
    bake = fp["encoder_bake_off"]
    metas = [read(pairs / "bakeoff/cache" / f"{m}.meta.json") for m in BAKE_OFF]
    if round(sum(m["seconds"] for m in metas), 1) != bake["seconds_elapsed"] or {m["edges"] for m in metas} != {bake["edges"]}:
        sys.exit("the bake-off's records do not add up to the step's numbers")
    for m in metas:
        parts.append(part("facet layer", "encoder candidate: the bake-off's edges encoded", m["written"][:10],
                          m["model"], "Colab, NVIDIA GPU (CUDA)", count=m["edges"], count_of="edges", tokens_out=0,
                          start_to_end=m["seconds"]))
    cache, head, refits, write = (fp[k] for k in ("encoder_cache", "head_selection_training_scoring",
                                                  "bootstrap_refits", "write"))
    cache_meta = read(pairs / "fullcache" / f"{BAKE_OFF[2]}.meta.json")
    if cache_meta["model"] != cache["model"].split(", ")[0]:
        sys.exit("the encoder cache's record names another model")
    parts += [part("facet layer", "the bake-off's report", read(pairs / "bakeoff/results/summary.json")["written"][:10],
                   None, "laptop", start_to_end=bake["report_seconds_on_the_laptop"]),
              part("facet layer", "every edge encoded", cache_meta["written"][:10], cache_meta["model"], desktop,
                   count=cache["edges"], count_of="edges", tokens_out=0, start_to_end=cache["seconds_elapsed"]),
              part("facet layer", "the facet head selected, trained and scored",
                   read(pairs / "rounds/round1/eval.json")["written"][:10], None, "laptop CPU",
                   count=head["combinations_fitted"], count_of="combinations fitted",
                   start_to_end=head["seconds_elapsed"]),
              # the refits' scores file (rounds/round1/bootstrap/scores_b24.npz) was written 2026-09-21T00:09Z
              part("facet layer", "bootstrap refits of the head", "2026-09-21", None, "laptop",
                   count=refits["refits"], count_of="refits", start_to_end=refits["seconds_elapsed"]),
              part("facet layer", "the graph backed up", "2026-10-08", None, neo4j, start_to_end=write["backup_seconds"]),
              part("facet layer", "the facet values written to the edges", "2026-10-08", None, neo4j,
                   count=cache["edges"], count_of="edges", start_to_end=write["seconds_elapsed"])]
    ls = later["seconds"]
    parts += [part("later edges", "person-to-chunk edges", "2026-10-17", None, "laptop", count=26950,
                   count_of="edges", command=ls["person_edges_tool_span"]),
              part("later edges", "the structure nodes' names and the customer-to-chunk edges", "2026-10-19", None,
                   "laptop", count=counts["customer_chunk_edges"], count_of="customer-to-chunk edges",
                   command=ls["structure_names_and_customer_edges_tool_span"]),
              part("later edges", "each chunk's record times", "2026-10-19", None, "laptop", count=38377,
                   count_of="times", command=ls["chunk_times_tool_span"])]
    return parts


def construction_tables(arm, folder):
    d = ROOT / "output/k=chars" / folder
    man = read(d / "run_manifest.json")
    idx, bs = man["index"], man["build_stats"]
    if arm == "lucene":
        parts = [part("index", "the BM25 index built in memory at the start of the run",
                      man["legs"][0]["started_at"][:10], None, "laptop CPU", count=idx["units"], count_of="records",
                      start_to_end=bs["build_time_s"])]
        counts = [("records in the index", idx["units"]), ("characters of all record texts", idx["text_chars"])]
    elif arm == "vector":
        note, m = idx["cache_cost_note"], bs["models"][0]
        parts = [part("index", "every record of the corpus embedded", note["made_utc"][:10], m["model"],
                      "desktop, " + m["device"], count=idx["units"], count_of="records", calls=m["calls"],
                      tries=m["calls"], tokens_in=m["tokens_in"], tokens_out=m["tokens_out"],
                      start_to_end=m["seconds_elapsed"])]
        counts = [("records in the index", idx["units"]), ("characters of all record texts", idx["text_chars"]),
                  ("vectors", idx["matrix_shape"][0]), ("dimensions of a vector", idx["matrix_shape"][1]),
                  ("records longer than the model's token limit", note["units_over_max_seq_length"])]
    else:
        c, census = idx["counts"], man["graph"]["census"]
        parts = artefact_parts(read(ROOT / "test/graph/build_cost.json"), c)
        chunk_step = next(s for s in idx["build_cost"]["steps"] if s["id"] == "chunks")

        def rel(key):
            kind, a, b = key.split(" ")
            return f"({a})-[{kind}]->({b}) relationships"
        counts = ([(f"{label} nodes", n) for label, n in census["labels"].items()]
                  + [(rel(k), n) for k, n in census["relationships"].items()]
                  + [(n, c[k]) for n, k in (
                      ("chunks the arm reads", "chunks"), ("tags on those chunks", "graph_tags"),
                      ("tag-to-chunk edges on those chunks", "edges"),
                      ("tags compared with the question's tags", "eligible_graph_tags"),
                      ("edges of those tags", "eligible_edges"), ("products", "products"),
                      ("people of the products", "people"), ("channels apart from their product", "channels_apart"),
                      ("chunks with their records' times", "chunks_with_a_time"))]
                  + [(f"{k} nodes with a name", v) for k, v in c["named_structure_nodes"].items()]
                  + [("tokens of all chunks, the chunker's estimate", chunk_step["size"]["token_estimate_of_those_chunks"])])
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
