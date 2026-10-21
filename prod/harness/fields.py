"""What every file of a run folder is and what every field in it means.

`render(folder)` is the text of FIELDS.md, which a run writes into its folder; `undescribed(folder)`
lists every file and every field of a folder that has no word here; `relations(folder)` checks
the things the words claim that a number can check. The words stand here and nowhere else
(2026-10-09: "you can't just have fucking smashed fields with no word or explanation to what they
mean"). An arm gives the words for what only it writes (`meta`, `index`, `retrieval_flags`) in
its own `FIELDS`.

A word here says what a field holds. It never says what a run's numbers were.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import re
from pathlib import Path


def sub(text: str, fields: dict) -> tuple:
    """A dict, or a list of dicts, whose own fields are described one by one."""
    return (text, fields)


def whole(text: str) -> tuple:
    """Something kept whole from elsewhere: this one line stands for everything below it."""
    return (text, None)


USAGE = {
    "calls": "How many model calls this counts. An answer is one call, however many tries it took.",
    "attempts": "How many times the model was asked in all, the tries that did not answer included.",
    "tokens_in": "Tokens the model was sent in the try that answered: the provider's count of the "
                 "whole input, the part it read from its prompt cache included.",
    "cached_input_tokens": "The part of tokens_in the provider read from its prompt cache instead "
                           "of reading it fresh. It depends on what was sent shortly before, not "
                           "on the arm.",
    "tokens_out": "Tokens the model wrote in the try that answered.",
    "reasoning_tokens": "Always 0: thinking is off, and this way of calling the model reports none.",
    "time_s": "Seconds from asking until the answer was in hand: request_s + wait_s + retry_s.",
    "request_s": "Seconds of the try that answered, from starting the Claude program to its "
                 "reply. The program's own start and end are inside it.",
    "wait_s": "Always 0. Kept from an earlier way of calling models that queued.",
    "retry_s": "Seconds spent on tries that did not answer, and on the pauses before trying again.",
}

ATTEMPT = {
    "n": "The try's number within the call, from 1.",
    "started_at": "When the try started (UTC).",
    "seconds": "How long the try took.",
    "outcome": "ok (it answered), exit (the program ended with an error), bad_envelope (its reply "
               "could not be read), or timeout (cut at timeout_s).",
    "returncode": "The program's exit code; empty for a timeout.",
    "error": "The error of a try that did not answer; empty for the try that answered.",
    "stdout": "What the program printed, kept for a try that did not answer; empty for the try "
              "that answered, whose reply is in text and envelope.",
    "stderr": "What the program printed as errors, kept for a try that did not answer; empty for "
              "the try that answered, and empty when the program printed nothing.",
    "backoff_s": "The pause after a try that did not answer, before the next one.",
    "machine_asleep": "Only where a correction marked the try: the machine slept under it. See "
                      "corrections.json.",
}

CALL = {
    "kind": "chat: a call to a language model. (embed: a request to the embedder, see below.)",
    "seq": "The call's place among the calls of this question or score cell, from 0.",
    "model": "The model that was asked, by its id.",
    "exe": "The Claude program that made the call.",
    "flags": "The arguments the program was started with, without the system text and the schema. "
             "The empty argument after --tools is the empty tool list: the call has no tool.",
    "system": "The system text sent with the call; empty when the caller gave none.",
    "schema": whole("The JSON schema the reply had to follow, when the caller gave one."),
    "prompt": "The text sent as the user's message, exactly as sent.",
    "effort": "The effort level the caller named; empty when it named none.",
    "join_parts": "Whether a reply written in several parts was joined. Not used by the answer "
                  "call or the judge.",
    "cwd": "The folder the program was started in.",
    "timeout_s": "The longest a try may take before it is cut.",
    "max_tries": "The most tries the call may make.",
    "env_set": whole("The environment variables the harness set for this call, by name: the "
                     "switches that shape what the program sends."),
    "env_unset": "The switches the harness took away for this call, so that a value left in the "
                 "shell did not reach it.",
    "applied": whole("What the caller asked for and the call carried, one entry per setting."),
    "not_applied": whole("What the caller asked for and the call could not carry, each with the "
                         "reason; empty when the call carried all of it."),
    "payload_dropped": "The names of the settings in not_applied.",
    "started_at": "When the call started (UTC).",
    "finished_at": "When the call ended (UTC).",
    "attempts": sub("Every try of the call, in order.", ATTEMPT),
    "ok": "Whether the call ended with an answer.",
    "text": "The reply's text. For an answer call it is the JSON that holds the answer. Empty for "
            "a call that gave up: no try answered.",
    "usage": sub("The tokens of the try that answered; empty for a call that gave up.", {
        "prompt_tokens": "Tokens sent: fresh input, plus what was written to the prompt cache, "
                         "plus what was read from it.",
        "completion_tokens": "Tokens the model wrote.",
        "cached_input_tokens": "The part of prompt_tokens read from the prompt cache.",
    }),
    "envelope": whole("The Claude program's whole reply as it printed it, each part as the "
                      "program gives it: its own times in milliseconds (duration_ms for the whole "
                      "program run, duration_api_ms for the time spent with the model, ttft_ms "
                      "until the first token, ttft_stream_ms and time_to_request_ms), its own "
                      "token counts, the models it used with their context window in tokens "
                      "(contextWindow), its own price in US dollars (total_cost_usd, costUSD; no "
                      "number of this harness uses it), its counts of web requests (0: the call "
                      "has no tool), its session id, how many turns it took, and its error "
                      "fields, which are empty when the call had no error (api_error_status, "
                      "permission_denials). Empty for a call that gave up: no reply was read."),
    "stream": "The raw stream of a reply joined from parts; empty otherwise.",
    "stderr": "What the program printed as errors in the try that answered; empty when it "
              "printed nothing, and for a call that gave up.",
    "error": "The last error of a call that gave up; empty otherwise.",
    "role": "answer: the call that wrote the answer. Not there on the arm's own calls.",
}

EMBED = {
    "kind": "embed: a request to the embedder.",
    "seq": "The request's place among the calls of this question or score cell, from 0.",
    "model": "The embedding model, by its name.",
    "revision": "The exact version of the embedding model.",
    "device": "Where the embedder ran (cpu, or a graphics card).",
    "dtype": "The number type the embedder computed in.",
    "input_type": "query or passage: which of the embedder's two modes the texts were given in.",
    "prefix": "The word put in front of each text for that mode.",
    "batch": "How many texts the embedder took at a time.",
    "n_texts": "How many texts the request held.",
    "texts": "The texts that were embedded.",
    "tokens": "The token count of each text, prefix included.",
    "tokens_in": "The sum of tokens.",
    "started_at": "When the request started (UTC).",
    "finished_at": "When the request ended (UTC).",
    "lock_wait_s": "Seconds the request waited for the embedder to be free.",
    "encode_s": "Seconds the embedder worked on the request.",
}

RECORD = {**EMBED, **CALL}

TIMING = {
    "started_at": "When the work started (UTC).",
    "finished_at": "When the work ended (UTC).",
    "wall_s": "Seconds from start to end. Where a correction is recorded it is smaller than the "
              "two stamps are apart; the stamps are clock times.",
    "thread": "The worker thread that did the work.",
}

CODE_VERSION = {
    "commit": "The git commit the code was at.",
    "branch": "The git branch; HEAD when the code ran from a checkout of one commit.",
    "dirty": "Whether git saw anything changed or new anywhere in the checkout, files that are "
             "not code included. What differed in the code is in code_state.",
}

CODE_STATE = {
    "status": "The code paths that differed from the commit, as git lists them. Empty when the "
              "code was exactly the commit.",
    "diff_sha256": "The sha256 of the difference between the code and the commit. When nothing "
                   "differs it is the sha256 of nothing.",
    "diff_file": "The file in this folder that holds that difference; there only when there is one.",
    "untracked_sha256": whole("The sha256 of each code file git did not know; empty when git "
                              "knew every code file."),
}

LANE = {
    "exe": "The Claude program used for every model call.",
    "cli_version": "Its version.",
    "cwd": "The folder it is started in.",
    "fixed_flags": "The arguments every call is started with. The empty argument after --tools is "
                   "the empty tool list: no call has a tool.",
    "system_prompt": "How the system text is passed.",
    "stdin": "How the prompt is handed over.",
    "env_set": whole("The environment variables set on every call, by name."),
    "login": "How the program logs in.",
    "config_settings": whole("The settings file the harness puts in the program's own config "
                             "folder; cleanupPeriodDays is how many days the program keeps its "
                             "own transcripts of the calls."),
    "env_per_call": "The switches a call sets only when it asks for them, and that are taken away "
                    "when it does not.",
    "per_call": "Where to find what each single call carried.",
    "cli_adds": sub("What the program puts into every call by itself. It is in no row.", {
        "seen_with": "The program version it was seen with.",
        "system_prompt_first": "The line it puts first in the system text.",
        "in_front_of_the_prompt": "What it puts in front of the prompt. The date in it is the "
                                  "day of the call.",
    }),
    "max_tries_default": "The most tries a call makes when the caller names no number.",
}

CORRECTION = whole("Only where a stored number was corrected after the run: the rule, the value "
                   "as recorded and the corrected value, the seconds taken out (taken_out_s), and "
                   "in the sleep correction each slept try with its number within the call (from "
                   "1), its start, its seconds and its timeout in seconds. The folder's "
                   "corrections.json tells the whole of it, and the files as recorded stand beside "
                   "the corrected ones.")

RETRIEVAL_ENTRY = {
    "kind": "chat: a language model. embed: the embedder.",
    "model": "The model, by its id or name.",
    "calls": "chat: how many answers; an answer is one call, however many tries it took. embed: "
             "how many batches the embedder was given.",
    "attempts": "chat: how many times the model was asked in all, the tries that did not answer "
                "included. embed: the same as calls; the embedder is asked once a batch.",
    "tokens_in": "chat: tokens sent in the tries that answered, the part read from the prompt "
                 "cache included. embed: the tokens of the texts, prefix included.",
    "cached_input_tokens": "chat: the part of tokens_in read from the prompt cache. embed: 0.",
    "tokens_out": "chat: tokens the model wrote in the tries that answered. embed: 0.",
    "reasoning_tokens": "Always 0.",
    "time_s": "request_s + wait_s + retry_s.",
    "request_s": "chat: seconds of the tries that answered. embed: seconds the embedder worked "
                 "(encode_s).",
    "wait_s": "chat: 0. embed: seconds the requests waited for the embedder to be free "
              "(lock_wait_s).",
    "retry_s": "chat: seconds of the tries that did not answer and of the pauses before trying "
               "again; a try a correction marked as slept under is left out. embed: 0.",
}

BUILD_MODEL = {
    "kind": "chat: a language model. embed: the embedder. encoder: a model that encoded the "
            "tag-to-chunk edges for the facet values, or the candidates tried for that.",
    "model": "The model, by its id or name.",
    "what": "What the model did in the build.",
    "calls": "How many calls or requests its records count, added over the model's parts where "
             "it worked in several (for a graph, index.build_cost holds each part); empty when "
             "they count none.",
    "tokens_in": "Tokens sent, as the records give them, added over the model's parts in the "
                 "same way; empty when they do not give them.",
    "tokens_out": "Tokens written, added over the model's parts in the same way; 0 for the "
                  "embedder and the encoders, which write none; empty when the records do not "
                  "give them.",
    "seconds_summed_per_call": "The seconds of each call added up, over the model's parts in the "
                               "same way. Calls that ran side by side make this more than the "
                               "time it took. Empty when the records do not give it.",
    "seconds_elapsed": "Start to end of the model's work, as its records give it, added over its "
                       "parts where they ran one after the other; empty when they do not give "
                       "it.",
    "device": "Where it ran.",
    "not_recorded": "What the records do not give for this model; empty when they leave nothing "
                    "out.",
}

GRAPH = {
    "database": "The Neo4j database the arm read.",
    "graph_version": "The version the graph's last build record names. The build record is "
                     "output/graph_build/<database>/build_manifest.json; these five are empty when "
                     "the folder that ran had none. Steps that changed the graph after that build "
                     "are in the arm's index (build_cost).",
    "graph_census_sha256": "The census hash the last build record gives, of the graph as that "
                           "build left it.",
    "removed_tags_sha256": "The hash of the tags the build record says were removed; empty when "
                           "the build record gives none.",
    "build_timestamp": "When the last build record was written (UTC).",
    "source_database": "The database the last build copied from.",
    "census": sub("The graph as counted in it when this manifest was written. It counts and "
                  "reads no value.", {
                      "labels": whole("Nodes per set of labels, the labels joined by ':'."),
                      "relationships": whole("Relationships per type and the label sets at "
                                             "their start and end."),
                      "node_properties": whole("Per set of labels, how many nodes carry each "
                                               "property."),
                      "relationship_properties": whole("Per relationship type, how many carry "
                                                       "each property."),
                  }),
    "census_sha256": "The sha256 of the census, its keys in order: two runs with the same value "
                     "read a graph of the same shape.",
    "census_error": "Why the graph could not be counted; there only then.",
    "mixed_builds": whole("Only when the starts of this folder read different graphs: the graph "
                          "block of each start, in order."),
}

ROW = {
    "id": "The question's id. It joins a row to its score rows (question_id) and to the question "
          "set.",
    "question": "The question as it was asked.",
    "answer": "The answer the model gave from the delivered texts.",
    "answered_at": "When the row was written (UTC).",
    "contexts": "The texts handed to the model, best first, as many as fit the character budget. "
                "The last one can be a text cut where the budget ended.",
    "context_ids": "The ids of the corpus records that were handed over whole, in the same order. "
                   "A text cut at the budget is in contexts but its record is not counted here.",
    "search_time_s": "Seconds the arm took to rank the corpus for this question, without any "
                     "model call or embedder request it made on the way.",
    "generator": sub("What the answer call cost.", USAGE),
    "retrieval": sub("What the arm's own model calls and embedder requests for this question "
                     "cost, one entry per model, in the order the models were first asked; two "
                     "models are never added together. The harness works it out from the "
                     "question's call records (calls), the answer call left out, the same way for "
                     "every arm. Empty for an arm that makes none.", RETRIEVAL_ENTRY),
    "leg": "Which start of this folder made the row: 1 for the first start, one more for each "
           "time the run was taken up again. The start is in run_manifest.json under legs.",
    "timing": sub("The clock of the whole question: ranking and answering.", TIMING),
    "calls": sub("Every model call and every embedder request the question made, whole.", RECORD),
    "correction": CORRECTION,
}

LEG = {
    "leg": "The start's number, from 1.",
    "started_at": "When the start began (UTC).",
    "finished_at": "When its answering ended (UTC). The judging comes after and is in "
                   "eval_manifest.json.",
    "wall_s": "Seconds of the start up to the end of its answering.",
    "process_cpu_s": "Processor seconds the run's own process used in that time. Model calls run "
                     "in other processes and are not in it.",
    "workers": "How many questions were worked on at once.",
    "argv": "The command line of the start.",
    "pid": "The process number of the start.",
    "python_executable": "The Python that ran it.",
    "ids_file": "The file that lists the questions of the set, as a path on the machine that ran "
                "it. The path can be gone; inputs.ids_sha256 is what identifies the set.",
    "n_chosen": "How many questions the set holds.",
    "n_todo": "How many of them had no row yet when the start began.",
    "n_answered": "How many the start answered.",
    "n_unanswered_after": "How many still had no row when it ended.",
    "aborted": "Why the start stopped early; empty when it did not.",
    "prepare_s": "Seconds the arm took to get ready before the first question (building or "
                 "loading its index).",
    "embedder_load_s": "Seconds the embedder took to load in this process; empty when it was not "
                       "loaded by then.",
    "retrieval_only": "Whether the start ranked only, with no answer and no judging.",
    "evaluator": "What scored the answers after the start: ragas, or gen when nothing did.",
    "peak_memory_bytes": "The most memory the run's process held up to the end of the answering.",
    "code_version": sub("The code the start ran on, read before it answered anything.",
                        CODE_VERSION),
    "code_state": sub("How that code differed from the commit.", CODE_STATE),
    "flags": whole("The switches given on the command line for this start, each by its name with "
                   "the value it was given; empty when none. What a switch does is the arm's to "
                   "say (retrieval_flags)."),
    "lane": sub("How every model call of the start was made.", LANE),
    "correction": CORRECTION,
}

MANIFEST = {
    "arm": "The retrieval method the run tested.",
    "generator_model": "The model that wrote the answers; empty for a run without answers.",
    "interpreter_model": "The model an arm uses to read the question before ranking; empty for an "
                         "arm that uses none.",
    "top_k": "The number of units handed to the arm as a depth. A run with a character budget "
             "does not use it: the arm ranks everything and the budget decides how much is handed "
             "over.",
    "char_budget": "How many characters of delivered text each question gets; empty for a run cut "
                   "at a depth instead.",
    "questions_file": "The file the questions were read from, as a path on the machine that ran "
                      "it. The path can be gone; inputs.questions_sha256 identifies the file.",
    "n_questions": "How many questions the set holds.",
    "n_ran": "How many have an answer row.",
    "n_failed": "How many have none.",
    "n_exhausted": "For how many the ranking ran out before the budget was full.",
    "timestamp": "When this file was written (UTC).",
    "build_stats": sub("What building the arm's index cost.", {
        "build_time_s": "Seconds it took. For an index read from a stored file it is what the "
                        "making of that file took. For a graph built in steps it is the elapsed "
                        "seconds and the command spans of every step whose records give them, "
                        "added; work that was replaced later is not counted. Empty when no "
                        "record gives them.",
        "models": sub("One entry per model that worked on the build, in the order of the build; "
                      "two models are never added together. Empty for an index built without a "
                      "model.", BUILD_MODEL),
        "not_recorded": "What the build records do not give, step by step; empty when nothing is "
                        "noted.",
        "as_the_arm_gave_it": whole("Only for an older arm that gave one sum for none or several "
                                    "models: that sum and the names, as given."),
    }),
    "flags": whole("The switches given on the command line, each by its name with the value it "
                   "was given; empty when none. What a switch does is the arm's to say "
                   "(retrieval_flags)."),
    "graph": sub("For an arm that reads the graph database: which database, its last build "
                 "record, and the graph as counted when this manifest was written. Empty for an "
                 "arm that reads none.", GRAPH),
    "code_version": sub("The code the last answering start ran on.", CODE_VERSION),
    "environment": sub("The machine and the software.", {
        "host": "The machine's name.",
        "platform": "Its operating system.",
        "python": "The Python version.",
        "python_executable": "The Python that ran.",
        "cpu": "The processor.",
        "cpu_count": "How many processor threads it has.",
        "ram_bytes": "How much memory it has.",
        "packages": whole("The versions of the packages the run rests on most."),
        "packages_all": "Every installed package with its version.",
        "embedder": sub("The embedding model the run is set to use.", {
            "model": "Its name.", "revision": "Its exact version.",
            "device": "Where it runs.", "dtype": "The number type it computes in.",
        }),
    }),
    "inputs": sub("What the run read, as hashes: these identify the inputs, the paths do not.", {
        "questions_sha256": "The sha256 of the questions file.",
        "ids_sha256": "The sha256 of the file that lists the set's questions.",
        "corpus": sub("The corpus.", {
            "sha256": "One sha256 over all its files, each by its path and its own sha256.",
            "n_files": "How many files that is.",
        }),
    }),
    "legs": sub("One entry per start of this folder, in order.", LEG),
    "workers": "How many questions were worked on at once in the last start.",
    "lane": sub("How every model call was made.", LANE),
    "generator": sub("What every answer call is given.", {
        "model": "The model.",
        "system": "The system text.",
        "user_template": "How the prompt is put together from the delivered texts and the question.",
        "schema": whole("The JSON schema the answer has to follow."),
        "payload": whole("What the harness asks of the call. It is the asking, not what happened: "
                         "applied and not_applied say what the call carried."),
        "applied": whole("What of that the call carries, one entry per setting."),
        "not_applied": whole("What of that it cannot carry, each with the reason."),
        "env_set": whole("The environment variables set for the call, by name."),
        "env_unset": "The switches taken away for the call.",
        "timeout_s": "The longest a try may take.",
    }),
    "code_state": sub("How the code differed from the commit.", CODE_STATE),
    "env": whole("The environment variables of the run that can change what a run or a model "
                 "call does, by name. A secret shows as <set>."),
}

USAGE_CELL = {
    "eval_leg": "Which scoring start made the cell, by that start's own starting time.",
    "started_at": "When the cell started (UTC).",
    "finished_at": "When it ended (UTC).",
    "wall_s": "Seconds from start to end.",
    "thread": "The worker thread that did it.",
    "chat_calls": "How many judge calls the cell made.",
    "chat_attempts": "How many tries those took in all.",
    "tokens_in": "Tokens sent to the judge, summed over the cell's calls.",
    "cached_input_tokens": "The part of those the provider read from its prompt cache.",
    "tokens_out": "Tokens the judge wrote, summed.",
    "chat_s": "Seconds of all tries of the cell's judge calls, summed.",
    "embed_calls": "How many embedder requests the cell made.",
    "embed_texts": "How many texts those held.",
    "embed_tokens": "Their tokens.",
    "embed_s": "Seconds the embedder worked on them.",
}

SCORE_ROW = {
    "question_id": "The question's id: the id of its row in arm_outputs.jsonl.",
    "type": "The question's kind in the benchmark (person, content, pr, company, url).",
    "arm": "The retrieval method.",
    "metric": "Which score this row is. The scores are described above.",
    "value": "The score.",
    "status": "ok; nan when the scoring gave no number; error when it failed.",
    "components": sub("What belongs to the score beside its value.", {
        "usage": sub("What computing this one score for this one question cost.", USAGE_CELL),
        "error": "The error of a cell that failed.",
    }),
    "human_label": "Not used; always empty.",
}

SETTINGS = {
    "started_at": "When the scoring start began (UTC).",
    "finished_at": "When it ended (UTC).",
    "interrupted": "Why it was cut short; empty when it was not.",
    "workers": "How many score cells were worked on at once.",
    "retrieval_only": "Whether only the scores that need no model were made.",
    "scores": "The scores this start was set to make.",
    "judge_model": "The model set as judge.",
    "judge_backend": "The way the judge is called.",
    "judge_timeout_s": "The longest a judge call may take.",
    "judge_max_tries": "How many tries a judge call makes.",
    "judge_inflight": "The most judge calls that can be under way at once.",
    "judge_empty_reply_tries": "How many times a reply with no text in it is asked for again, in "
                               "all.",
    "judge_call": sub("What every judge call is given.", {
        "model": "The model.",
        "system": "The system text: none.",
        "payload": whole("What the harness asks of the call."),
        "applied": whole("What of that the call carries."),
        "not_applied": whole("What of that it cannot carry, each with the reason."),
        "env_set": whole("The environment variables set for the call, by name."),
        "env_unset": "The switches taken away for the call.",
    }),
    "max_judge_context_chars": "Above this many delivered characters a warning is printed. It "
                               "cuts nothing: the judge is sent the delivered texts whole.",
    "max_consecutive_failed_questions": "After this many questions in a row with mostly failed "
                                        "cells the scoring stops.",
    "ragas": "The version of RAGAS, the library that writes the judge's prompts and computes the "
             "scores.",
    "embed_model": "The embedding model the scores use.",
    "ragas_run_config": whole("RAGAS's own run settings as handed to it, in RAGAS's own units: "
                              "timeout and max_wait in seconds, max_retries and max_workers as "
                              "counts."),
    "ragas_do_not_track": "Whether RAGAS's usage reporting to its makers was switched off.",
    "lane": sub("How every judge call was made.", LANE),
    "calls_file": "The file that keeps every judge call and embedder request.",
    "argv": "The command line.",
    "pid": "The process number.",
    "python_executable": "The Python that ran.",
    "wall_s": "Seconds the scoring start took.",
    "embedding": sub("What the embedder did for this start, summed.", {
        "requests": "How many requests.", "texts": "How many texts.", "tokens_in": "Their tokens.",
        "lock_wait_s": "Seconds spent waiting for the embedder.",
        "encode_s": "Seconds the embedder worked.",
    }),
    "cells": whole("How many score cells ended in each status."),
}

EVAL_MANIFEST = {
    "scorer": "What scored the answers.",
    "judge_model": "The model that judged.",
    "source_run": "The folder that was scored, as a path on the machine that ran it.",
    "arm": "The retrieval method.",
    "timestamp": "When this file was written (UTC).",
    "judge_backend": "The way the judge was called.",
    "judge_effort": "The effort level set for a judge that takes one; empty otherwise.",
    "judge_usage": sub("What all judge calls cost, summed over every scoring start.", USAGE),
    "judge_elapsed_s": "Seconds of all scoring starts, summed.",
    "judge_legs": sub("One entry per scoring start, in order.", {
        "timestamp": "When the start's entry was written (UTC).",
        "judge_model": "The model that judged in this start; empty when it made no judge call.",
        "judge_backend": "The way the judge was called.",
        "usage": sub("What the start's judge calls cost.", USAGE),
        "elapsed_s": "Seconds the start took.",
        "settings": sub("What the start ran under.", SETTINGS),
    }),
    "judge_settings": sub("What the last scoring start ran under.", SETTINGS),
}

EVAL_CALL = {
    "eval_leg": "Which scoring start made the call, by that start's starting time.",
    "arm": "The retrieval method.",
    "question_id": "The question the call was made for; empty for the embeddings made once "
                   "before the cells.",
    "type": "The question's kind in the benchmark; not there for the embeddings made once before "
            "the cells.",
    "score": "The score the call was made for; empty for the embeddings made once before the "
             "cells (phase prime), which serve several scores.",
    "phase": "cell: made for one question and one score. prime: embeddings made once, before the "
             "cells.",
    **RECORD,
}

FAILURE = {
    "id": "The question's id.",
    "error": "What went wrong.",
    "failed_at": "When (UTC).",
    "leg": "Which start it happened in.",
    "traceback": "Where in the code it went wrong.",
    "timing": sub("The clock of the try that failed.", TIMING),
    "calls": sub("Every call the try had made by then.", RECORD),
}

EVAL_FAILURE = {
    "question_id": "The question's id.",
    "metric": "The score that failed.",
    "error": "What went wrong.",
    "eval_leg": "Which scoring start it happened in.",
    "failed_at": "When (UTC).",
    "usage": sub("What the failed cell had cost.", USAGE_CELL),
}

CORRECTION_ENTRY = {
    "made_at": "When the correction was made (UTC).",
    "ordered_by": "The words that ordered it.",
    "what_happened": "What was wrong in the stored numbers.",
    "rule": whole("The rule that decided which numbers were corrected, and how."),
    "not_changed_and_worth_knowing": "What the correction left as recorded and a reader should know.",
    "slept_tries": whole("Only in the sleep correction: the tries the rule found, each with its "
                         "question, its row (the line of arm_outputs.jsonl, counted from 0), its "
                         "try (its number within the call, from 1), its start (UTC), its recorded "
                         "seconds, its timeout in seconds, the seconds of low power the machine "
                         "logged inside it, whether a whole reply had come back, and that reply's "
                         "tokens."),
    "changes": whole("Every changed value: where it is, the value before and the corrected value, "
                     "and what was taken out (taken_out: seconds in the sleep correction; in the "
                     "clean-up correction the embedder's seconds and the seconds of refused first "
                     "calls). The value before is empty where the field was not there before the "
                     "correction. A copied value keeps its empty parts; its own field's words say "
                     "why they are empty."),
    "checks": whole("Only in the clean-up correction: what was checked against the call records "
                    "and the graph, whether it held, and how many places were looked at."),
    "judge_calls_with_logged_low_power_time_inside_them": whole("Only in the sleep correction: "
                                                               "judge calls the machine's own "
                                                               "sleep record touches, not changed; "
                                                               "each try as [its number from 1, "
                                                               "its outcome, its seconds]."),
    "low_power_intervals_the_machine_logged": whole("Only in the sleep correction: the machine's "
                                                    "own record of when it slept: start and end "
                                                    "(UTC), seconds, and what the machine said."),
    "files": whole("The sha256 of each corrected file, before and after the correction, and "
                   "where the file from before is kept. The sleep correction's are of the bytes "
                   "on the disk that ran it; the clean-up correction's are of the files with the "
                   "line ends git holds (LF), as line_ends says."),
    "evidence": "The file that holds the machine's own record.",
    "script": "The script that made the correction.",
    "code": whole("Only in the clean-up correction: the code the script ran on, which it imports "
                  "its harness and arms from: the commit, whether anything differed from it, and "
                  "what."),
}

CORRECTIONS = {
    "corrections": sub("One entry per correction, in the order they were made; each rests on "
                       "the files the one before it left.", CORRECTION_ENTRY),
}

# file name, or a pattern with *, -> (what the file is, how it joins, its fields or None)
FILES = {
    "FIELDS.md": ("This file.", "", None),
    "arm_outputs.jsonl": ("One line per question: what was delivered, the answer, and everything "
                          "the question cost.", "id", ROW),
    "eval_results.jsonl": ("One line per question and score: the score.",
                           "question_id = the id of arm_outputs.jsonl; metric", SCORE_ROW),
    "eval_calls.jsonl": ("One line per judge call and per embedder request of the scoring, whole. "
                         "The judge's prompts hold the gold answers.",
                         "question_id + score = one line of eval_results.jsonl", EVAL_CALL),
    "run_manifest.json": ("What the run was: the arm, its index, the code, the machine, the "
                          "inputs, and every start of this folder.",
                          "legs[].leg = the leg of a row", MANIFEST),
    "eval_manifest.json": ("What the scoring was: the judge, its settings, and what it cost.",
                           "judge_legs[].settings.started_at = the eval_leg of a score row",
                           EVAL_MANIFEST),
    "failures.jsonl": ("One line per try at a question that failed. Empty when none did. A "
                       "question that failed and was answered in a later start has a line here "
                       "and a row.", "id", FAILURE),
    "eval_failures.jsonl": ("One line per score cell that failed. Empty when none did.",
                            "question_id + metric", EVAL_FAILURE),
    "code.*.diff": ("The difference between the code that ran and its commit, when there was one.",
                    "its name is in code_state.diff_file", None),
    ".run.lock": ("There only while a run is writing into the folder.", "", None),
    "corrections.json": ("Only in a folder whose stored numbers were corrected after the run: "
                         "what was changed, by which rule, on whose word.", "", CORRECTIONS),
    "*.as_recorded.*": ("A file exactly as the run wrote it, kept when a correction changed the "
                        "file of the same name.", "", None),
    "machine_sleep_events.txt": ("The machine's own record of when it slept and woke, which a "
                                 "correction rests on.", "", None),
    "correct_slept_tries.py": ("The script that made the sleep correction; run on the files as "
                               "recorded it gives the files it corrected again.", "", None),
    "correct_usage_by_model.py": ("The script that made the clean-up correction (the cost per "
                                  "model, the search time without the model calls, the build "
                                  "cost per model, the graph as counted); run on the files from "
                                  "before it, it gives the corrected files again.", "", None),
    "correct_cut_chunk_records.py": ("The script that made the cut-chunk correction (the records "
                                     "of the cut chunk handed over whole counted in the two "
                                     "id-based scores); run on the files from before it, it gives "
                                     "the corrected files again.", "", None),
}

# score -> (RAGAS's own sentence, where it is from, what goes into it here, what it needs,
#           whether it may be compared between arms)
SCORES = {
    "context_recall_id": (
        "Calculates context recall by directly comparing retrieved context IDs with reference "
        "context IDs. The score represents what proportion of the reference IDs were successfully "
        "retrieved.", "class IDBasedContextRecall",
        "context_ids against the ids of the question's gold records.", "nothing", True),
    "context_precision_id": (
        "Calculates context precision by directly comparing retrieved context IDs with reference "
        "context IDs. The score represents what proportion of the retrieved context IDs are "
        "actually relevant (present in reference).", "class IDBasedContextPrecision",
        "context_ids against the ids of the question's gold records.", "nothing", True),
    "context_recall_nonllm": (
        "`NonLLMContextRecall` metric is computed using `retrieved_contexts` and "
        "`reference_contexts` [...] This metrics uses non-LLM string comparison metrics to "
        "identify if a retrieved context is relevant or not.", "docs, context_recall.md",
        "contexts against the text of each gold record; a gold record counts as found when a "
        "delivered text is more than 0.5 like it (Levenshtein).", "nothing", False),
    "context_precision_nonllm": (
        "To determine if a retrieved context is relevant, this method compares each retrieved "
        "context or chunk in `retrieved_contexts` with every context in `reference_contexts` "
        "using a non-LLM-based similarity measure.", "docs, context_precision.md",
        "each delivered text against the gold records' texts, more than 0.5 alike (Levenshtein), "
        "weighted by rank.", "nothing", False),
    "context_recall_llm": (
        "Estimates context recall by estimating TP and FN using annotated answer and retrieved "
        "context.", "class LLMContextRecall",
        "the gold answer, sentence by sentence, against contexts.", "the judge", True),
    "faithfulness": (
        "The **Faithfulness** metric measures how factually consistent a `response` is with the "
        "`retrieved context`. [...] A response is considered **faithful** if all its claims can "
        "be supported by the retrieved context.", "docs, faithfulness.md",
        "the answer's claims against contexts.", "the judge", True),
    "answer_correctness": (
        "Measures answer correctness compared to ground truth as a combination of factuality and "
        "semantic similarity.", "class AnswerCorrectness",
        "the answer against the gold answer: 0.75 times the F1 of the claims the judge finds in "
        "both, plus 0.25 times semantic_similarity (RAGAS's own weights).",
        "the judge and the embedder", True),
    "semantic_similarity": (
        "The **Semantic Similarity** metric evaluates the semantic resemblance between a "
        "generated response and a reference (ground truth) answer. [...] This metric uses "
        "embeddings and cosine similarity", "docs, semantic_similarity.md",
        "the answer against the gold answer, both embedded in passage mode.", "the embedder", True),
    "string_similarity": (
        "`NonLLMStringSimilarity` metric measures the similarity between the reference and the "
        "response using traditional string distance measures such as Levenshtein, Hamming, and "
        "Jaro.", "docs, traditional.md",
        "the answer against the gold answer, Levenshtein.", "nothing", True),
    "bleu": (
        "It measures the similarity between the response and the reference based on n-gram "
        "precision and brevity penalty.", "docs, traditional.md",
        "the answer against the gold answer.", "nothing", True),
    "rouge": (
        "It measures the overlap between the generated `response` and the `reference` text based "
        "on n-gram recall, precision, and F1 score.", "docs, traditional.md",
        "the answer against the gold answer: rougeL, F measure.", "nothing", True),
    "chrf": (
        "The `CHRFScore` metric evaluates the similarity between a `response` and a `reference` "
        "using **character n-gram F-score**.", "docs, traditional.md",
        "the answer against the gold answer.", "nothing", True),
    "exact_match": (
        "The `ExactMatch` metric checks if the response is exactly the same as the reference "
        "text.", "docs, traditional.md", "the answer against the gold answer.", "nothing", True),
    "string_presence": (
        "The `StringPresence` metric checks if the response contains the reference text.",
        "docs, traditional.md", "the answer against the gold answer.", "nothing", True),
}

_ARM_OWNED = ("meta", "index", "retrieval_flags")

# What was left out of the data the runs rest on, and on whose word: his words quoted with their
# time, or that no rule of his is recorded. An arm adds its own in its LEFT_OUT.
LEFT_OUT = [
    "The questions: every run answers the 100 questions of data/gold100.jsonl "
    "(inputs.ids_sha256). How these 100 were chosen from the benchmark's questions: no rule in "
    "his words is recorded. The set was first added on 2026-05-19 (commit 0b98b12, \"Scale gold "
    "set to n=100 (balanced) + statistically robust result\"); his messages from 2026-05-15 to "
    "2026-05-27 are not in the canon, because that work was done in Cursor.",
]


def arm_left_out(arm: str | None) -> list:
    """What an arm says was left out of the data it rests on; empty when it says nothing."""
    if not arm:
        return []
    try:
        return list(getattr(importlib.import_module(f"arms.{arm}"), "LEFT_OUT", None) or [])
    except ImportError:
        return []


def arm_fields(arm: str | None) -> dict:
    """The words an arm gives for what only it writes; empty when it gives none."""
    if not arm:
        return {}
    try:
        return dict(getattr(importlib.import_module(f"arms.{arm}"), "FIELDS", None) or {})
    except ImportError:
        return {}


def spec_for(arm: str | None) -> dict:
    """file -> the fields of that file, with the arm's own words put in their places."""
    own = arm_fields(arm)
    row, manifest, leg = dict(ROW), dict(MANIFEST), dict(LEG)
    if "meta" in own:
        row["meta"] = own["meta"]
    for key in ("index", "retrieval_flags"):
        if key in own:
            manifest[key] = own[key]
    if "index" in own:
        leg["index"] = own["index"]
    manifest["legs"] = sub(MANIFEST["legs"][0], leg)
    out = {name: fields for name, (_, _, fields) in FILES.items()}
    out["arm_outputs.jsonl"], out["run_manifest.json"] = row, manifest
    return out


def _match(name: str) -> str | None:
    for pattern in FILES:
        if pattern == name or ("*" in pattern and re.fullmatch(
                re.escape(pattern).replace(r"\*", ".+"), name)):
            return pattern
    return None


def _missing(value, fields: dict, path: str, out: set) -> None:
    if isinstance(value, list):
        for item in value:
            _missing(item, fields, path, out)
        return
    if not isinstance(value, dict):
        return
    for key, below in value.items():
        here = f"{path}.{key}" if path else key
        entry = fields.get(key)
        if entry is None:
            out.add(here)
        elif isinstance(entry, tuple) and entry[1] is not None:
            _missing(below, entry[1], here, out)
        elif isinstance(entry, str) and (
                (isinstance(below, dict) and below)
                or (isinstance(below, list) and any(isinstance(x, dict) for x in below))):
            out.add(here + ".*")


def undescribed(folder) -> list:
    """Every file of the folder with no word here, and every field of its files with none."""
    d = Path(folder)
    arm = _arm_of(d)
    spec = spec_for(arm)
    out = set()
    for p in sorted(d.iterdir()):
        if p.is_dir():
            continue
        pattern = _match(p.name)
        if pattern is None:
            out.add(f"{p.name} (the file)")
            continue
        fields = spec.get(pattern)
        if fields is None or ".as_recorded." in p.name:
            continue
        found = set()
        if p.suffix == ".jsonl":
            for record in _lines(p):
                _missing(record, fields, "", found)
        elif p.suffix == ".json":
            try:
                _missing(json.loads(p.read_text(encoding="utf-8")), fields, "", found)
            except ValueError:
                found.add("(the file is not readable as JSON)")
        out.update(f"{p.name}: {f}" for f in found)
    return sorted(out)


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _arm_of(d: Path) -> str | None:
    return _json(d / "run_manifest.json").get("arm")


def _lines(path: Path) -> list:
    """The records of a .jsonl file. A line that is not whole (a run cut off while writing its
    last line) is left out, as the harness itself leaves it out."""
    out = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def _same_entries(a: list, b: list) -> bool:
    """Two lists of per-model entries alike: the same models in the same order, the same counts,
    the same seconds to within a microsecond."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if set(x) != set(y):
            return False
        for k in x:
            if isinstance(x[k], float) or isinstance(y[k], float):
                if abs(float(x[k]) - float(y[k])) > 1e-6:
                    return False
            elif x[k] != y[k]:
                return False
    return True


def relations(folder) -> list:
    """(what the words claim, whether it holds in this folder, how many places were looked at)."""
    d = Path(folder)
    rows, res = _lines(d / "arm_outputs.jsonl"), _lines(d / "eval_results.jsonl")
    out = []

    def add(text, bad, n):
        out.append((text, bad == 0, f"{n} looked at, {bad} differ"))

    chats = [(r, c) for r in rows for c in r.get("calls") or []
             if c.get("kind") == "chat" and c.get("ok") and c.get("model") is not None]
    answer = [(r, c) for r, c in chats
              if c["usage"]["prompt_tokens"] == r["generator"]["tokens_in"]]
    add("generator.tokens_in is the envelope's input + cache creation + cache read tokens",
        sum(1 for r, c in answer if r["generator"]["tokens_in"] != sum(
            int((c["envelope"].get("usage") or {}).get(k) or 0) for k in
            ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))),
        len(answer))
    add("generator.time_s is request_s + wait_s + retry_s, to within half a second",
        sum(1 for r in rows if abs(r["generator"]["time_s"] - sum(
            r["generator"][k] for k in ("request_s", "wait_s", "retry_s"))) > 0.5), len(rows))
    from harness.capture import usage_by_model
    own = [r for r in rows if isinstance(r.get("retrieval"), list)]
    add("retrieval is the question's own call records summed per model, the answer call left out",
        sum(1 for r in own if not _same_entries(r["retrieval"], usage_by_model(
            [c for c in r.get("calls") or [] if c.get("role") != "answer"]))), len(own))
    answered = [r for r in rows if (r.get("generator") or {}).get("calls")]
    add("every answered row has one call marked answer, and it is the one generator counts",
        sum(1 for r in answered if [(c.get("usage") or {}).get("prompt_tokens")
                                    for c in r.get("calls") or []
                                    if c.get("role") == "answer" and c.get("ok")]
            != [r["generator"]["tokens_in"]]), len(answered))
    add("no second is counted twice: search_time_s, the retrieval's time_s and generator.time_s "
        "add up to no more than timing.wall_s, half a second allowed",
        sum(1 for r in own if r["search_time_s"] + sum(e["time_s"] for e in r["retrieval"])
            + r["generator"]["time_s"] > r["timing"]["wall_s"] + 0.5), len(own))
    cut = [r for r in rows if (r.get("meta") or {}).get("char_budget")]
    try:
        one_each = cut if getattr(importlib.import_module(f"arms.{_arm_of(d)}"),
                                  "UNIT_IS_ONE_RECORD", False) else []
    except ImportError:
        one_each = []
    add("a row's contexts are its context_ids plus the text cut at the budget, when one was cut",
        sum(1 for r in one_each if len(r["contexts"]) != len(r["context_ids"])
            + (1 if r["meta"]["char_budget"].get("boundary") else 0)), len(one_each))
    add("the delivered characters are the budget's, unless the ranking ran out",
        sum(1 for r in cut if sum(map(len, r["contexts"])) != r["meta"]["char_budget"]["chars"]
            or (r["meta"]["char_budget"]["chars"] != r["meta"]["char_budget"]["budget"]
                and not r["meta"]["char_budget"]["exhausted"])), len(cut))
    if res:
        ids = {r["id"] for r in rows}
        per = {}
        for r in res:
            per.setdefault(r["metric"], set()).add(r["question_id"])
        add("every score has one row for every question that has an answer row",
            sum(1 for qs in per.values() if qs != ids), len(per))
        try:
            ev = _json(d / "eval_manifest.json")
            cells = [(r.get("components") or {}).get("usage") or {} for r in res]
            add("the score rows' judge tokens add up to eval_manifest's judge_usage",
                int((sum(c.get("tokens_in", 0) for c in cells),
                     sum(c.get("tokens_out", 0) for c in cells),
                     sum(c.get("chat_calls", 0) for c in cells))
                    != (ev["judge_usage"]["tokens_in"], ev["judge_usage"]["tokens_out"],
                        ev["judge_usage"]["calls"])), 1)
        except (OSError, ValueError, KeyError, TypeError):
            add("the score rows' judge tokens add up to eval_manifest's judge_usage", 1, 1)
    return out


def source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# groups of fields that stand in several places: FIELDS.md says each once
_SHARED = [
    ("What a model's work cost", USAGE),
    ("A call record", RECORD),
    ("A clock", TIMING),
    ("The code", CODE_VERSION),
    ("How the code differed from its commit", CODE_STATE),
    ("How model calls were made", LANE),
    ("What a scoring start ran under", SETTINGS),
    ("What a score cell cost", USAGE_CELL),
]


def _table(fields: dict, shared: list, prefix: str = "", skip=()) -> list:
    lines = []
    for key, entry in fields.items():
        if key in skip:
            continue
        text, below = (entry, None) if isinstance(entry, str) else entry
        title = next((t for t, group in shared if group is below), None)
        if title:
            lines.append(f"| `{prefix}{key}` | {text} Its fields: see \"{title}\" below. |")
            continue
        lines.append(f"| `{prefix}{key}` | {text} |")
        if below:
            lines.extend(_table(below, shared, f"{prefix}{key}."))
    return lines


def _json_type(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "array" if isinstance(value, list) else "object"


def _typed(value, fields: dict, path: str, out: dict, record: int) -> None:
    """Every described field under value: the JSON types it holds, the records that hold it and
    the records that hold it empty (null, "", [] or {}). A field described as a whole is counted
    as one field; nothing below it is walked."""
    if isinstance(value, list):
        for item in value:
            _typed(item, fields, path, out, record)
        return
    if not isinstance(value, dict):
        return
    for key, below in value.items():
        here = f"{path}.{key}" if path else key
        entry = fields.get(key)
        if entry is None:
            continue
        seen = out.setdefault(here, {"types": set(), "records": set(), "empty": set()})
        seen["types"].add(_json_type(below))
        seen["records"].add(record)
        if below is None or below == "" or below == [] or below == {}:
            seen["empty"].add(record)
        if isinstance(entry, tuple) and entry[1] is not None and isinstance(below, (dict, list)):
            if isinstance(below, list):
                for item in below:
                    if isinstance(item, (dict, list)):
                        _typed(item, entry[1], here, out, record)
                    else:
                        seen["types"].add("array of " + _json_type(item))
            else:
                _typed(below, entry[1], here, out, record)


def _types_section(d: Path, spec: dict) -> list:
    """The fields as they stand in this folder, counted from its files: for every described field
    the JSON types it holds, in how many records, and in how many it is empty."""
    out = ["## The fields as they stand in this folder", "",
           "Counted from the files themselves when this was written. A record is a line of a "
           ".jsonl file, or the whole of a .json file. Empty is null, an empty text, an empty "
           "list or an empty object; the field's words say when and why it is empty.", ""]
    for p in sorted(d.iterdir()):
        pattern = _match(p.name) if p.is_file() else None
        fields = spec.get(pattern) if pattern else None
        if fields is None or ".as_recorded." in p.name or p.suffix not in (".jsonl", ".json"):
            continue
        records = (_lines(p) if p.suffix == ".jsonl" else [_json(p)])
        seen = {}
        for n, record in enumerate(records):
            _typed(record, fields, "", seen, n)
        if not records:
            out += [f"### `{p.name}` (0 records)", "", "The file holds no record.", ""]
            continue
        if not seen:
            continue
        out += [f"### `{p.name}` ({len(records)} records)", "",
                "| Field | Types | Records that hold it | Of those, empty |", "|---|---|---|---|"]
        for path in sorted(seen):
            s = seen[path]
            out.append(f"| `{path}` | {', '.join(sorted(s['types']))} | {len(s['records'])} | "
                       f"{len(s['empty'])} |")
        out.append("")
    return out


def render(folder=None, arm: str | None = None, stamp_files: bool = False) -> str:
    """The text of FIELDS.md, for a run folder when one is given."""
    d = Path(folder) if folder else None
    arm = arm or (_arm_of(d) if d else None)
    spec = spec_for(arm)
    own = arm_fields(arm)
    shared = list(_SHARED)
    if isinstance(own.get("index"), tuple):
        shared.append(("The arm's index", own["index"][1]))
    man = _json(d / "run_manifest.json") if d else {}
    ev = _json(d / "eval_manifest.json") if d else {}
    out = ["# What is in this folder, and what every field means", ""]
    if man:
        legs = man.get("legs") or []
        out += [
            f"One run of one retrieval method, **{man.get('arm')}**, over {man.get('n_questions')} "
            f"questions: for each question the texts the method delivered, one answer written "
            f"from them, and the scores of that answer and of what was delivered. Each answer "
            f"was written once and judged once.", "",
            f"- Answers by `{man.get('generator_model')}`"
            + (f", judged by `{ev.get('judge_model')}`." if ev else "."),
            f"- Code: commit `{(man.get('code_version') or {}).get('commit')}`; code paths that "
            f"differed from it: {len((man.get('code_state') or {}).get('status') or [])}.",
            f"- Starts of this folder: {len(legs)}"
            + (f", the first at {legs[0].get('started_at')}." if legs else "."), ""]
    out += ["**This folder holds the questions and, inside the judge's prompts, the gold answers.** "
            "It must not be given to a model or an agent that works on the retrieval method, and "
            "it is not for a public repository.", "",
            "## The files and how they join", "",
            "| File | What it is | Joins by |", "|---|---|---|"]
    present = {p.name for p in d.iterdir() if p.is_file()} if d else set()
    for pattern, (text, join, _) in FILES.items():
        names = sorted(n for n in present if _match(n) == pattern)
        if d and not names and pattern != "FIELDS.md":
            continue
        out.append(f"| `{'`, `'.join(names) if names else pattern}` | {text} | {join} |")
    out += ["", "Times are seconds (`_s`), milliseconds (`_ms`) or UTC stamps (`_at`; every other "
            "time text carries its own zone). Sizes are tokens, characters (`chars`) or bytes. A count (calls, attempts, requests, texts, records, edges, refits, and the "
            "like) is a plain number of the things it names. A price (`usd`, `USD`) is the "
            "Claude program's own, in US dollars; no number of this harness uses it. The "
            "evaluation's scores run from 0 to 1 and higher is more; a score an arm ranks by "
            "says its own scale.", "",
            "## The scores", "",
            "The scores are computed by RAGAS. The quoted sentence of each is RAGAS's own, from "
            "the place named; \"Here\" says what goes into it in this folder.", "",
            "| `metric` | What it measures | Needs | Between arms |", "|---|---|---|---|"]
    for name, (ragas, source, here, needs, across) in SCORES.items():
        out.append(f"| `{name}` | \"{ragas}\" (RAGAS, {source}) Here: {here} | {needs} | "
                   f"{'yes' if across else 'no, within one arm only'} |")
    out += ["", "\"No, within one arm only\": the score is counted per delivered text, and arms "
            "deliver texts of different size (one record, or a chunk of several records), so the "
            "same delivered records give different values. The id scores count record ids, the "
            "same for every arm.", "",
            "No stored score is called a hit rate. Whether a question got any gold record at all "
            "can be read from `context_recall_id` being above 0.", "",
            "## What was left out, and on whose word", ""]
    out += [f"- {line}" for line in LEFT_OUT + arm_left_out(arm)]
    out += ["",
            "## Easy to read wrongly", "",
            "- `top_k` in the manifest is not used by a run with a character budget.",
            "- `generator.payload` is what the harness asked for. `applied` and `not_applied` are "
            "what a call carried.",
            "- `calls` counts answers, `attempts` counts tries. `tokens_in` and `tokens_out` are "
            "those of the try that answered; a try that did not answer is in the call's own "
            "record under `attempts`.",
            "- `retrieval` is a list with one entry per model. A language model's tokens and the "
            "embedder's tokens are different things and are never added together; the same holds "
            "for the entries of `build_stats.models`.",
            "- `search_time_s` holds no model call and no embedder request; their seconds are in "
            "`retrieval`. `timing.wall_s` is the whole question, and the harness's own work is "
            "in it beside those.",
            "- In `build_stats.models`, `seconds_summed_per_call` and `seconds_elapsed` are two "
            "kinds of seconds: calls that ran side by side make the first more than the second.",
            "- `tokens_in` includes what was read from the prompt cache; `cached_input_tokens` is "
            "that part alone.",
            "- A text cut at the budget is in `contexts` and its record is not in `context_ids`, "
            "so the id scores do not count it.",
            "- `request_s` includes the Claude program's own start and end. The time with the "
            "model alone is in the call's `envelope`.",
            "- `wall_s` of a start ends when its answering ends. The judging's time is in "
            "`eval_manifest.json`.",
            "- Paths (`questions_file`, `ids_file`, `source_run`) are from the machine that ran "
            "it and can be gone. The `sha256` fields under `inputs` identify what was read.",
            "- The Claude program adds two things to every call that are in no row: a line first "
            "in the system text and a line with the day's date in front of the prompt "
            "(`lane.cli_adds`).", ""]
    for pattern, (text, _, _) in FILES.items():
        fields = spec.get(pattern)
        if fields is None or (d and not any(_match(n) == pattern for n in present)):
            continue
        out += [f"## `{pattern}`", "", text, "", "| Field | What it holds |", "|---|---|"]
        if pattern == "eval_calls.jsonl":
            out += _table(fields, shared, skip=set(RECORD))
            out += ["", "Beside these, each line has the fields of \"A call record\" below."]
        else:
            out += _table(fields, shared)
        if pattern == "arm_outputs.jsonl" and "meta" not in fields:
            out += ["", f"`meta` is written by the arm. The arm `{arm}` gives no words for it."]
        if pattern == "run_manifest.json" and not {"index", "retrieval_flags"} <= set(fields):
            out += ["", "`index` and `retrieval_flags` are written by the arm. The arm "
                    f"`{arm}` gives no words for them."]
        out.append("")
    out += ["## Groups of fields that stand in several places", ""]
    for title, group in shared:
        out += [f"### {title}", "", "| Field | What it holds |", "|---|---|"]
        out += _table(group, [g for g in shared if g[1] is not group])
        if group is RECORD:
            out += ["", "A record with `kind` chat is a call to a language model; one with `kind` "
                    "embed is a request to the embedder and has only the fields that say so."]
        out.append("")
    if d:
        gaps = undescribed(d)
        out += ["## Fields without a word", "",
                "None: every file and every field of this folder is described above." if not gaps
                else f"{len(gaps)} have none:", ""]
        out += [f"- `{g}`" for g in gaps]
        if gaps:
            out.append("")
        out += _types_section(d, spec)
    out += ["---", f"Written from `prod/harness/fields.py`, sha256 `{source_sha256()}`."]
    if d and stamp_files:
        # with the line ends git holds (LF): the harness writes CR LF on Windows, git keeps LF,
        # and a checkout on any machine then gives these sha256 back
        out += ["", "The files as they stood when this was written, their line ends as git holds "
                    "them (LF):", ""]
        for p in sorted(d.iterdir()):
            if p.is_file() and p.name != "FIELDS.md":
                digest = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                out.append(f"- `{p.name}` sha256 `{digest}`")
    return "\n".join(out) + "\n"


def write(folder, stamp_files: bool = False) -> Path:
    path = Path(folder) / "FIELDS.md"
    path.write_text(render(folder, stamp_files=stamp_files), encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    import sys

    stamp = "--stamp-files" in sys.argv
    for target in [a for a in sys.argv[1:] if not a.startswith("--")]:
        print(write(target, stamp_files=stamp))
        for line in undescribed(target):
            print("  no word for:", line)
        for text, ok, detail in relations(target):
            print(f"  [{'ok' if ok else 'NO'}] {text} | {detail}")
