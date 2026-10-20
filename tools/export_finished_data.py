"""The finished data, for giving away: for each arm one file of its run and one of its construction,
values only, the same shape for every arm.

    python tools/export_finished_data.py [--out finished_data]

Reads the three final run folders, the graph's build cost and the bake-off's cache records; writes
six JSON files. Nothing that belongs to this machine or this project goes in: no path, host, user,
session, file of the repository, commit, note or reason. What every field holds is said in the
file's own `fields`.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = {"lucene": "lucene__gold100__cb72000__20261008T234209Z",
        "vector": "vector__gold100__cb72000__20261017T061242Z",
        "artefact": "artefact_v4__gold100__cb72000__20261020T041923Z"}
SCORES = ("context_recall_id", "context_precision_id", "context_recall_llm", "context_recall_nonllm",
          "context_precision_nonllm", "faithfulness", "answer_correctness", "semantic_similarity",
          "string_similarity", "bleu", "rouge", "chrf", "exact_match", "string_presence")
COST = ("model", "calls", "attempts", "tokens_in", "cached_tokens_in", "tokens_out",
        "seconds_summed_per_call", "seconds_elapsed")
BAKE_OFF = ("tasksource__deberta-small-long-nli", "tasksource__deberta-base-long-nli",
            "Alibaba-NLP__gte-reranker-modernbert-base", "BAAI__bge-reranker-v2-m3")

COST_FIELDS = {
    "model": "The model.",
    "calls": "Language model: calls that answered, however many tries each took. Embedder: requests.",
    "attempts": "Language model: every try, the tries that did not answer included. Embedder: requests. "
                "null where the tries were not counted.",
    "tokens_in": "Tokens sent in the tries that answered (language model), or tokens of the embedded texts (embedder).",
    "cached_tokens_in": "The part of tokens_in read from the provider's prompt cache; 0 for an embedder. null where "
                        "not counted.",
    "tokens_out": "Tokens written. 0 for an embedder or an encoder.",
    "seconds_summed_per_call": "Seconds of the tries, the pauses between tries and any wait for a free slot, "
                               "added up over the calls. null where not measured.",
    "seconds_elapsed": "Seconds from the start to the end, measured around the calls. null where not measured.",
}
RUN_FIELDS = {
    "run.arm": "The retrieval method.",
    "run.benchmark": "The benchmark that the questions and the corpus come from.",
    "run.questions": "How many questions the run was given.",
    "run.answered": "How many questions it answered.",
    "run.failed": "How many questions it did not answer.",
    "run.char_budget": "The largest number of characters of delivered text for one question.",
    "run.questions_at_once": "How many questions were worked on at the same time.",
    "run.first_call_model": "The language model that the arm calls before it ranks. null for an arm that makes no such call.",
    "run.first_call_settings": "The settings of that call: its system prompt, its output schema, and thinking, effort, "
                               "temperature and max_output_tokens (null where none was sent). Every value null for an "
                               "arm that makes no such call.",
    "run.generator_model": "The language model that wrote every answer.",
    "run.generator_settings": "The settings of the answer call: its system prompt, how its prompt is put together, "
                              "and thinking, effort, temperature and max_output_tokens (null where none was sent).",
    "run.judge_model": "The language model that judged for the scores that need a judge.",
    "run.judge_settings": "The settings of a judge call: thinking, effort, temperature (null where none was sent), "
                          "tries, timeout_s, and max_context_chars (the most characters of delivered text the judge got).",
    "run.model_client": "The client that every language-model call went through, with its version and its fixed flags "
                        "(the empty value after --tools is the empty list of tools).",
    "run.embedder": "The embedding model, its revision and how it ran: for the arm's own embeddings (arm_prefix, null "
                    "for an arm that embeds nothing) and for the scores that compare by embeddings (score_prefix).",
    "run.ragas": "RAGAS, which computed the scores: its version and its run settings.",
    "run.answering": "The answering: started_at and finished_at (UTC clock times); wall_s (seconds of the answering, "
                     "a time when the machine slept not counted); prepare_s (seconds to get the index ready before the "
                     "first question, inside wall_s); embedder_load_s (seconds to load the embedder, null where it was not "
                     "loaded); process_cpu_s (processor seconds of the run's own process; the language-model calls run "
                     "in other processes); peak_memory_bytes.",
    "run.judging": "The scoring after the answering: started_at and finished_at (UTC), and wall_s (seconds).",
    "run.judging.score_embedding": "The embedder's requests for the scores, made once for all questions before the "
                                   "scoring; the keys of a cost block.",
    "run.machine": "The machine of the run: cpu, cpu_count (threads), ram_bytes and platform.",
    "run.software": "The version of Python and of the main packages of the run.",
    "questions[].question_id": "The question: the benchmark's product file name, 'a' for answerable, and the question's "
                               "place, counted from 0, in that file's list of answerable questions.",
    "questions[].question_type": "The question's type in the benchmark.",
    "questions[].question": "The question as it was asked.",
    "questions[].answer": "The answer that the generator wrote from the delivered texts.",
    "questions[].delivered": "The texts handed to the generator, in the order of the arm's ranking: each with its text, the "
                             "ids of the corpus records it holds, and whole (false for the one text cut where the character "
                             "budget ended). One record can stand in more than one text. The id-based scores count "
                             "the record ids of the whole texts, each id once.",
    "questions[].delivered_chars": "Characters handed over.",
    "questions[].ranking_ran_out": "true where the arm had nothing more to hand over before the character budget was full.",
    "questions[].scores": "The 14 scores, one entry each: score (its name in RAGAS), value (0 to 1, higher is better), "
                          "seconds_elapsed (seconds to compute it), and the judge's cost for it in judge_calls, judge_attempts, "
                          "tokens_in, cached_tokens_in, tokens_out and seconds_summed_per_call, as in a cost block (0 for a "
                          "score that needs no judge). context_precision_nonllm and context_recall_nonllm count per delivered "
                          "text, so they compare inside one arm only; the other scores compare across arms.",
    "questions[].started_at": "When the work on the question started (UTC clock time).",
    "questions[].finished_at": "When it ended (UTC clock time).",
    "questions[].wall_s": "Seconds of the work on the question: ranking, model calls and answering; a time when the "
                          "machine slept not counted.",
    "questions[].search_s": "Seconds the arm took to rank for the question, its own model calls and embedder requests not counted.",
    "questions[].first_call": "The cost of the arm's call to a language model before it ranks: a cost block, every value "
                              "null for an arm that makes no such call.",
    "questions[].query_embedding": "The cost of the arm's own embedder requests: a cost block, every value null for an arm "
                                   "that embeds nothing.",
    "questions[].answer_call": "The cost of the call that wrote the answer: a cost block.",
    **{f"cost block.{k}": v for k, v in COST_FIELDS.items()},
}
CONSTRUCTION_FIELDS = {
    "index.arm": "The retrieval method.",
    "index.kind": "What the arm ranks with.",
    "index.unit": "What one unit of the index is.",
    "index.units": "How many units the index holds.",
    "index.built": "When the index is built.",
    "index.counts": "What the index holds, each as a name and a value.",
    "index.parameters": "How the index was built, each as a name and a value.",
    "parts[].step": "The step of the build.",
    "parts[].part": "The part of the step.",
    "parts[].date": "When the part was made (UTC).",
    "parts[].kind": "chat: a language model; embed: an embedding model; encoder: a model that encodes tag-to-chunk "
                    "pairs; training: a model fitted here; none: no model.",
    "parts[].model": "The model. null for no model, or for a model fitted here.",
    "parts[].device": "Where the part ran.",
    "parts[].items": "How many things the part made or handled; item says what they are. null where not counted.",
    "parts[].item": "What items counts.",
    **{f"parts[].{k}": v for k, v in COST_FIELDS.items() if k != "model"},
    "parts[].seconds_command_span": "Seconds from the start to the end of the command that ran the part, its backup and "
                                    "check included. null where not measured.",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def block(**values):
    return {k: values.get(k) for k in COST}


def entry_block(entry):
    if not entry:
        return block()
    return block(model=entry["model"], calls=entry["calls"], attempts=entry["attempts"],
                 tokens_in=entry["tokens_in"], cached_tokens_in=entry["cached_input_tokens"],
                 tokens_out=entry["tokens_out"], seconds_summed_per_call=entry["time_s"])


def call_settings(system, applied, payload):
    def sent(v):
        return None if v is None or str(v).startswith("none sent") else v
    return {"system_prompt": system, "thinking": applied.get("thinking"), "effort": sent(applied.get("effort")),
            "temperature": sent(applied.get("temperature")),
            "max_output_tokens": sent(applied.get("max_output_tokens", payload.get("max_tokens")))}


def one(values, what):
    values = list(values)
    if any(v != values[0] for v in values):
        sys.exit(f"{what} differs between questions; this export reads one")
    return values[0]


def run_file(arm, folder):
    d = ROOT / "output/k=chars" / folder
    man, ev = read(d / "run_manifest.json"), read(d / "eval_manifest.json")
    if len(man["legs"]) != 1 or len(ev["judge_legs"]) != 1:
        sys.exit(f"{arm}: more than one start; this export reads one")
    leg, js, env, gen = man["legs"][0], ev["judge_settings"], man["environment"], man["generator"]
    cells = {}
    for r in rows(d / "eval_results.jsonl"):
        cells.setdefault(r["question_id"], {})[r["metric"]] = r
    arm_rows = rows(d / "arm_outputs.jsonl")
    out = []
    for r in arm_rows:
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
            sys.exit(f"{arm} {r['id']}: the record ids do not line up with the delivered texts")
        mine = cells[r["id"]]
        if set(mine) != set(SCORES) or any(c["status"] != "ok" for c in mine.values()):
            sys.exit(f"{arm} {r['id']}: not every score is there and ok")
        scores = []
        for s in SCORES:
            u = mine[s]["components"]["usage"]
            if u.get("embed_calls"):
                sys.exit(f"{arm} {r['id']} {s}: embedder requests inside a score; this export has no field for them")
            scores.append({"score": s, "value": mine[s]["value"], "seconds_elapsed": u["wall_s"],
                           "judge_calls": u["chat_calls"], "judge_attempts": u["chat_attempts"],
                           "tokens_in": u["tokens_in"], "cached_tokens_in": u["cached_input_tokens"],
                           "tokens_out": u["tokens_out"], "seconds_summed_per_call": u["chat_s"]})
        g = r["generator"]
        out.append({
            "question_id": r["id"],
            "question_type": one((c["type"] for c in mine.values()), f"{r['id']} type"),
            "question": r["question"],
            "answer": r["answer"],
            "delivered": [{"text": t, "record_ids": [str(i) for i in ids], "whole": w}
                          for t, ids, w in zip(texts, id_lists, whole)],
            "delivered_chars": r["meta"]["char_budget"]["chars"],
            "ranking_ran_out": r["meta"]["char_budget"]["exhausted"],
            "scores": scores,
            "started_at": r["timing"]["started_at"],
            "finished_at": r["timing"]["finished_at"],
            "wall_s": r["timing"]["wall_s"],
            "search_s": r["search_time_s"],
            "first_call": entry_block(own.get("chat")),
            "query_embedding": entry_block(own.get("embed")),
            "answer_call": block(model=man["generator_model"], calls=g["calls"], attempts=g["attempts"],
                                 tokens_in=g["tokens_in"], cached_tokens_in=g["cached_input_tokens"],
                                 tokens_out=g["tokens_out"],
                                 seconds_summed_per_call=g["request_s"] + g["wait_s"] + g["retry_s"],
                                 seconds_elapsed=g["time_s"]),
        })
    first = {"system_prompt": None, "thinking": None, "effort": None, "temperature": None,
             "max_output_tokens": None, "schema": None}
    if man["interpreter_model"]:
        firsts = [next(c for c in r["calls"] if c["kind"] == "chat" and c.get("role") != "answer") for r in arm_rows]
        first = call_settings(one((c["system"] for c in firsts), "the first call's system prompt"),
                              one((c["applied"] for c in firsts), "the first call's settings"), {})
        first["schema"] = one((c["schema"] for c in firsts), "the first call's schema")
    prime = [c for c in rows(d / "eval_calls.jsonl") if c.get("phase") == "prime"]
    emb, embedder, judge = js["embedding"], env["embedder"], js["judge_call"]
    arm_embeds = [c for r in arm_rows for c in r["calls"] if c["kind"] == "embed"]
    return {
        "fields": RUN_FIELDS,
        "run": {
            "arm": arm,
            "benchmark": "HERB (Salesforce AI Research): 100 of its answerable questions, and its corpus",
            "questions": man["n_questions"], "answered": man["n_ran"], "failed": man["n_failed"],
            "char_budget": man["char_budget"],
            "questions_at_once": leg["workers"],
            "first_call_model": man["interpreter_model"],
            "first_call_settings": first,
            "generator_model": man["generator_model"],
            "generator_settings": {**call_settings(gen["system"], gen["applied"], gen["payload"]),
                                   "prompt": gen["user_template"].replace("\\n", "\n")},
            "judge_model": ev["judge_model"],
            "judge_settings": {**call_settings(judge["system"] or None, judge["applied"], judge["payload"]),
                               "tries": js["judge_max_tries"], "timeout_s": js["judge_timeout_s"],
                               "max_context_chars": js["max_judge_context_chars"]},
            "model_client": {"name": "Claude Code", "version": man["lane"]["cli_version"].split(" ")[0],
                             "fixed_flags": man["lane"]["fixed_flags"]},
            "embedder": {"model": embedder["model"], "revision": embedder["revision"], "device": embedder["device"],
                         "dtype": embedder["dtype"],
                         "arm_prefix": one((c["prefix"] for c in arm_embeds), "the arm's embedding prefix")
                         if arm_embeds else None,
                         "score_prefix": one((c["prefix"] for c in prime), "the scores' embedding prefix")},
            "ragas": {"version": js["ragas"], **{k: js["ragas_run_config"][k]
                                                 for k in ("seed", "timeout", "max_retries", "max_wait")}},
            "answering": {"started_at": leg["started_at"], "finished_at": leg["finished_at"],
                          "wall_s": leg["wall_s"], "prepare_s": leg["prepare_s"],
                          "embedder_load_s": leg["embedder_load_s"], "process_cpu_s": leg["process_cpu_s"],
                          "peak_memory_bytes": leg["peak_memory_bytes"]},
            "judging": {"started_at": js["started_at"], "finished_at": js["finished_at"], "wall_s": js["wall_s"],
                        "score_embedding": block(model=embedder["model"], calls=emb["requests"],
                                                 attempts=emb["requests"], tokens_in=emb["tokens_in"],
                                                 cached_tokens_in=0, tokens_out=0,
                                                 seconds_summed_per_call=emb["encode_s"] + emb["lock_wait_s"])},
            "machine": {"cpu": env["cpu"], "cpu_count": env["cpu_count"], "ram_bytes": env["ram_bytes"],
                        "platform": env["platform"]},
            "software": {"python": env["python"], **env["packages"]},
        },
        "questions": out,
    }


def part(step, name, date, kind, model, device, items=None, item=None, calls=None, attempts=None,
         tokens_in=None, cached_tokens_in=None, tokens_out=None, summed=None, elapsed=None, span=None):
    def seconds(v):
        return None if v is None else float(v)
    return {"step": step, "part": name, "date": date, "kind": kind, "model": model, "device": device,
            "items": items, "item": item, "calls": calls, "attempts": attempts, "tokens_in": tokens_in,
            "cached_tokens_in": cached_tokens_in, "tokens_out": tokens_out, "seconds_summed_per_call": seconds(summed),
            "seconds_elapsed": seconds(elapsed), "seconds_command_span": seconds(span)}


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
    parts = [part("chunks", "the corpus cut into chunks", c["date"], "none", None, "laptop",
                  items=5843, item="chunks"),
             part("chunks", "question, unanswerable-question and product-profile chunks taken out", "2026-05-19",
                  "none", None, "laptop", items=5843 - c["size"]["chunks_in_this_graph"], item="chunks")]
    passes, main = t["whole_run"]["by_pass"], t["whole_run"]["main"]
    pass_s = left_out("descriptions_and_tags", "per-pass elapsed")
    extract_calls = main["calls_with_usage"] - sum(passes[p]["calls"] for p in ("score_tags", "describe", "score"))
    # every second try of the main run is on an extract record; each of those records holds two tries
    retried = left_out("descriptions_and_tags", "time of the 48 retried calls")["records"]
    extract_tries = passes["extract"]["records"] + retried
    for name, label, n, tries, items, item in (
            ("extract", "per chunk, a description and its tags", extract_calls, extract_tries,
             passes["extract"]["records"], "chunks"),
            ("score_tags", "per chunk, five facet scores for each of its tags", passes["score_tags"]["calls"],
             passes["score_tags"]["calls"], passes["score_tags"]["calls"], "chunks"),
            ("describe", "per file, a description", passes["describe"]["calls"], passes["describe"]["calls"],
             passes["describe"]["calls"], "files"),
            ("score", "per file, a relevance score for each of its chunks", passes["score"]["calls"],
             passes["score"]["calls"], passes["score"]["calls"], "files")):
        p = passes[name]
        parts.append(part("descriptions and tags", label, t["date"], "chat", haiku, tagger, items=items, item=item,
                          calls=n, attempts=tries, tokens_in=p["tokens_in"], tokens_out=p["tokens_out"],
                          summed=p["seconds_summed_per_call"], elapsed=pass_s[name]))
    rec_by = left_out("descriptions_and_tags", "the recovery by pass")
    rec_s = left_out("descriptions_and_tags", "the recovery's elapsed and its passes")
    for name, label in (("extract", "again: per chunk, a description and its tags"),
                        ("score_tags", "again: per chunk, five facet scores for each of its tags"),
                        ("score", "again: per file, a relevance score for each of its chunks"),
                        ("score_recovery", "again: relevance scores of single chunks")):
        n, tin, tout, secs = rec_by[name]
        parts.append(part("descriptions and tags", label, t["date"], "chat", haiku, tagger, calls=n, tokens_in=tin,
                          tokens_out=tout, summed=secs, elapsed=rec_s[name]))
    gs = g["seconds"]
    parts += [part("graph copies", "the graph copied", "2026-08-12", "none", None, neo4j,
                   elapsed=gs["herb_eval_v2_copy_elapsed"]),
              part("graph copies", "tags taken out, with their 5,470 edges", "2026-08-12", "none", None, neo4j,
                   items=4111, item="tags", elapsed=gs["herb_eval_v2_cleanup_elapsed"]),
              part("graph copies", "the cleaned graph copied", "2026-08-16", "none", None, neo4j,
                   elapsed=gs["volmax_copy_from_its_console_print"]),
              part("graph copies", "the entities planned", "2026-08-16", "none", None, neo4j,
                   elapsed=gs["volmax_entity_plan_elapsed"]),
              part("graph copies", "the entity nodes added", "2026-08-16", "none", None, neo4j,
                   elapsed=gs["volmax_entities_elapsed"])]
    ep, embed = e["parts"], "nvidia/llama-nemotron-embed-1b-v2"
    for key, label in (("tags", "every tag embedded"),
                       ("tags_with_underscores_in_readable_form", "tags with underscores embedded in readable form"),
                       ("descriptions", "every chunk description embedded")):
        p = ep[key]
        parts.append(part("embeddings", label, e["date"], "embed", embed,
                          desktop if "1080" in p["device"] else "laptop CPU", items=p["texts"], item="texts",
                          calls=p["texts"], attempts=p["texts"], tokens_in=p["tokens_in"], cached_tokens_in=0,
                          tokens_out=0,
                          elapsed=p["seconds_elapsed"]))
    parts += [part("embeddings", "the tag vectors written to the graph", e["date"], "none", None, neo4j,
                   items=ep["tags"]["texts"], item="vectors", elapsed=ep["write_tag_vectors"]["seconds_elapsed"]),
              part("embeddings", "the description vectors written to the graph", e["date"], "none", None, neo4j,
                   items=ep["descriptions"]["texts"], item="vectors",
                   elapsed=ep["write_description_vectors"]["seconds_elapsed"])]
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
        parts.append(part("facet layer", f"pairs of tag-to-chunk edges judged: {label}", date, "chat",
                          "claude-opus-5", "Claude Code, effort high, 8 calls at a time", items=n, item="pairs",
                          calls=n, tokens_in=tin, tokens_out=tout, summed=secs, elapsed=el))
    bake = fp["encoder_bake_off"]
    metas = [read(pairs / "bakeoff/cache" / f"{m}.meta.json") for m in BAKE_OFF]
    if round(sum(m["seconds"] for m in metas), 1) != bake["seconds_elapsed"] or {m["edges"] for m in metas} != {bake["edges"]}:
        sys.exit("the bake-off's records do not add up to the step's numbers")
    for m in metas:
        parts.append(part("facet layer", "encoder candidate: the bake-off's edges encoded", m["written"][:10], "encoder",
                          m["model"], "Colab, NVIDIA GPU (CUDA)", items=m["edges"], item="edges", tokens_out=0,
                          elapsed=m["seconds"]))
    cache, head, refits, write = (fp[k] for k in ("encoder_cache", "head_selection_training_scoring",
                                                  "bootstrap_refits", "write"))
    cache_meta = read(pairs / "fullcache" / f"{BAKE_OFF[2]}.meta.json")
    if cache_meta["model"] != cache["model"].split(", ")[0]:
        sys.exit("the encoder cache's record names another model")
    parts += [part("facet layer", "the bake-off's report", read(pairs / "bakeoff/results/summary.json")["written"][:10],
                   "none", None, "laptop", elapsed=bake["report_seconds_on_the_laptop"]),
              part("facet layer", "every edge encoded", cache_meta["written"][:10], "encoder", cache_meta["model"],
                   desktop, items=cache["edges"], item="edges", tokens_out=0, elapsed=cache["seconds_elapsed"]),
              part("facet layer", "the facet head selected, trained and scored",
                   read(pairs / "rounds/round1/eval.json")["written"][:10], "training", None, "laptop CPU",
                   items=head["combinations_fitted"], item="combinations fitted", elapsed=head["seconds_elapsed"]),
              # the refits' scores file (rounds/round1/bootstrap/scores_b24.npz) was written 2026-09-21T00:09Z
              part("facet layer", "bootstrap refits of the head", "2026-09-21", "training", None, "laptop",
                   items=refits["refits"], item="refits", elapsed=refits["seconds_elapsed"]),
              part("facet layer", "the graph backed up", "2026-10-08", "none", None, neo4j,
                   elapsed=write["backup_seconds"]),
              part("facet layer", "the facet values written to the edges", "2026-10-08", "none", None, neo4j,
                   items=cache["edges"], item="edges", elapsed=write["seconds_elapsed"])]
    ls = later["seconds"]
    parts += [part("later edges", "person-to-chunk edges", "2026-10-17", "none", None, "laptop",
                   items=26950, item="edges", span=ls["person_edges_tool_span"]),
              part("later edges", "the structure nodes' names and the customer-to-chunk edges", "2026-10-19", "none",
                   None, "laptop", items=counts["customer_chunk_edges"], item="customer-to-chunk edges",
                   span=ls["structure_names_and_customer_edges_tool_span"]),
              part("later edges", "each chunk's record times", "2026-10-19", "none", None, "laptop",
                   items=38377, item="times", span=ls["chunk_times_tool_span"])]
    return parts


def construction_file(arm, folder):
    d = ROOT / "output/k=chars" / folder
    man = read(d / "run_manifest.json")
    idx, bs, env = man["index"], man["build_stats"], man["environment"]
    if arm == "lucene":
        index = {"arm": arm, "kind": "BM25 index (bm25s, the Lucene variant of BM25)",
                 "unit": "one record of the corpus", "units": idx["units"], "built": "in memory, at the start of the run",
                 "counts": [{"name": "characters of all unit texts", "value": idx["text_chars"]}],
                 "parameters": [{"name": n, "value": idx[k]} for n, k in (
                     ("method", "method"), ("k1", "k1"), ("b", "b"), ("stop words", "stopwords"),
                     ("stemmer", "stemmer"), ("bm25s version", "bm25s"), ("PyStemmer version", "PyStemmer"))]}
        parts = [part("index", "the BM25 index built", man["legs"][0]["started_at"][:10], "none", None, "laptop CPU",
                      items=idx["units"], item="units", elapsed=bs["build_time_s"])]
    elif arm == "vector":
        note, m = idx["cache_cost_note"], bs["models"][0]
        index = {"arm": arm, "kind": "dense vector index, cosine closeness",
                 "unit": "one record of the corpus", "units": idx["units"],
                 "built": "once, stored, and read at the start of the run",
                 "counts": [{"name": "characters of all unit texts", "value": idx["text_chars"]},
                            {"name": "vectors", "value": idx["matrix_shape"][0]},
                            {"name": "dimensions of a vector", "value": idx["matrix_shape"][1]},
                            {"name": "units longer than the model's most tokens", "value": note["units_over_max_seq_length"]}],
                 "parameters": [{"name": n, "value": note[k]} for n, k in (
                     ("model", "model"), ("revision", "revision"), ("number type", "dtype"), ("mode", "mode"),
                     ("prefix", "prefix"), ("texts in a request", "batch"), ("most tokens in a text", "max_seq_length"),
                     ("Python", "python"), ("torch", "torch"), ("sentence-transformers", "sentence_transformers"),
                     ("transformers", "transformers"))]}
        parts = [part("index", "every record of the corpus embedded", note["made_utc"][:10], "embed", m["model"],
                      "desktop, " + m["device"], items=idx["units"], item="records", calls=m["calls"],
                      attempts=m["calls"], tokens_in=m["tokens_in"], cached_tokens_in=0, tokens_out=m["tokens_out"],
                      elapsed=m["seconds_elapsed"])]
    else:
        counts, census = idx["counts"], man["graph"]["census"]
        layer = rows(d / "arm_outputs.jsonl")[0]["meta"]["provenance"]["facet_layer"]
        parts = artefact_parts(read(ROOT / "test/graph/build_cost.json"), counts)
        chunk_step = next(s for s in idx["build_cost"]["steps"] if s["id"] == "chunks")

        def rel(key):
            kind, a, b = key.split(" ")
            return f"({a})-[{kind}]->({b})"
        index = {"arm": arm, "kind": "graph (Neo4j): chunks of the corpus records, their tags, the tag-to-chunk edges "
                                     "with facet values, and the benchmark's structure",
                 "unit": "one chunk: one or more records of the corpus", "units": counts["chunks"],
                 "built": "once, in steps, and read at the start of the run",
                 "counts": [{"name": f"{label} nodes", "value": n} for label, n in census["labels"].items()]
                 + [{"name": rel(k), "value": n} for k, n in census["relationships"].items()]
                 + [{"name": n, "value": counts[k]} for n, k in (
                     ("chunks the arm reads", "chunks"), ("tags on those chunks", "graph_tags"),
                     ("tag-to-chunk edges on those chunks", "edges"),
                     ("tags compared with the question's tags", "eligible_graph_tags"),
                     ("edges of those tags", "eligible_edges"), ("products", "products"),
                     ("people of the products", "people"), ("channels apart from their product", "channels_apart"),
                     ("chunks with their records' times", "chunks_with_a_time"))]
                 + [{"name": f"{k} nodes with a name", "value": v} for k, v in counts["named_structure_nodes"].items()]
                 + [{"name": "tokens of all chunks, the chunker's estimate",
                     "value": chunk_step["size"]["token_estimate_of_those_chunks"]}],
                 "parameters": [{"name": "facets", "value": layer["facets"]},
                                {"name": "bootstrap refits that each facet value is the mean of", "value": layer["refits"]},
                                {"name": "retrain flip gap of each facet, in the order of the facets after topic",
                                 "value": layer["equal_gap"]},
                                {"name": "pooled retrain flip gap", "value": layer["pooled_flip_gap"]},
                                {"name": "embedding model, query mode, for tags and chunk descriptions", "value":
                                 "nvidia/llama-nemotron-embed-1b-v2"},
                                {"name": "language model of the descriptions and the tags", "value": "claude-haiku-4-5-20251001"},
                                {"name": "temperature of the description and tag calls", "value": 0.3},
                                {"name": "output of the description and tag calls", "value": "forced tool use"},
                                {"name": "language model of the judged pairs", "value": "claude-opus-5"},
                                {"name": "encoder of the facet values", "value": "Alibaba-NLP/gte-reranker-modernbert-base"}]}
        if layer["equal_gap_facets"] != layer["facets"][1:]:
            sys.exit("the facet layer's gaps are not in the order of the facets after topic")
    return {"fields": CONSTRUCTION_FIELDS, "index": index, "parts": parts}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(ROOT / "finished_data"))
    out = Path(p.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    for arm, folder in RUNS.items():
        for kind, data in (("runs", run_file(arm, folder)), ("construction", construction_file(arm, folder))):
            path = out / f"{arm}_{kind}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1, allow_nan=False) + "\n",
                            encoding="utf-8", newline="\n")
            print(f"{path.name}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
