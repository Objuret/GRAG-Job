# What is in this folder, and what every field means

One run of one retrieval method, **vector**, over 715 questions: for each question the texts the method delivered, one answer written from them, and the scores of that answer and of what was delivered. Each answer was written once and judged once.

- Answers by `claude-sonnet-5`, judged by `claude-haiku-4-5-20251001`.
- Code: commit `02b207864dd542eb40ba4da6143ebb746203ad93`; code paths that differed from it: 0.
- Starts of this folder: 9, the first at 2026-10-24T00:43:34.547841+00:00.

**This folder holds the questions and, inside the judge's prompts, the gold answers.** It must not be given to a model or an agent that works on the retrieval method, and it is not for a public repository.

## The files and how they join

| File | What it is | Joins by |
|---|---|---|
| `FIELDS.md` | This file. |  |
| `arm_outputs.jsonl` | One line per question: what was delivered, the answer, and everything the question cost. | id |
| `eval_results.jsonl` | One line per question and score: the score. | question_id = the id of arm_outputs.jsonl; metric |
| `eval_calls.jsonl` | One line per judge call and per embedder request of the scoring, whole. The judge's prompts hold the gold answers. | question_id + score = one line of eval_results.jsonl |
| `run_manifest.json` | What the run was: the arm, its index, the code, the machine, the inputs, and every start of this folder. | legs[].leg = the leg of a row |
| `eval_manifest.json` | What the scoring was: the judge, its settings, and what it cost. | judge_legs[].settings.started_at = the eval_leg of a score row |
| `failures.jsonl` | One line per try at a question that failed. Empty when none did. A question that failed and was answered in a later start has a line here and a row. | id |
| `eval_failures.jsonl` | One line per score cell that failed. Empty when none did. | question_id + metric |
| `code.acb4fb450f447926.diff` | The difference between the code that ran and its commit, when there was one. | its name is in code_state.diff_file |
| `corrections.json` | Only in a folder whose stored numbers were corrected after the run: what was changed, by which rule, on whose word. |  |
| `eval_manifest.as_recorded.json` | eval_manifest.json exactly as the scoring wrote it, kept by the first correction that changed it (corrections.json names it). |  |
| `eval_results.as_recorded.jsonl` | eval_results.jsonl exactly as the scoring wrote it, kept by the first correction that changed it (corrections.json names it). |  |
| `arm_outputs.as_recorded.jsonl`, `eval_calls.as_recorded.jsonl`, `run_manifest.as_recorded.json` | A file exactly as the run wrote it, kept when a correction changed the file of the same name. |  |
| `correct_zero_usage.py` | The script that made the zero-usage correction (the tokens of the answer calls whose Claude program reply held 0 in its usage field); run on the files from before it, with its evidence file, it gives the corrected files again. |  |
| `cli_transcript_usage.json` | The evidence of the zero-usage correction: the Claude program's own transcript counts of each answer call it changed, by session id, read on the machine that made the calls. | session id = calls[].envelope.session_id of arm_outputs.jsonl |
| `correct_missing_judge_legs.py` | The script that made the missing-judge-legs correction (an entry in judge_legs for each scoring start that wrote none, built from its records in eval_calls.jsonl, and judge_usage as the sum of the entries); run on the files from before it, it gives the corrected files again. |  |
| `correct_nonllm_record_content.py` | The script that made the non-LLM record-content correction (context_recall_nonllm and context_precision_nonllm calculated again, record content against record content); run on the files from before it, with the code named in its entry, it gives the corrected files again. |  |
| `correct_embed_gpu_time.py` | The script that made the GPU-time correction (the query embeddings made on the CPU given the time the same embeddings take on the desktop's graphics card); run on the files from before it, with its evidence file, it gives the corrected files again. |  |
| `gpu_embed_times_all.json` | The evidence of the GPU-time correction with --all: per question, each embed call's seconds on the graphics card one call after the other, also of a call the run made on the card while other questions were under way, and its recorded seconds. | question id = id of arm_outputs.jsonl; seq = calls[].seq |
| `correct_judge_usage.py` | The script that made the judge-usage correction (a judge call whose record held fewer tokens than its own reply given the whole call's counts, with its scoring start's entry, judge_usage and its score cell); run on the files from before it, it gives the corrected files again. |  |
| `correct_search_time.py` | The script that made the search-time correction (each question's search time the time of the same retrieval made again with one question at a time on the laptop, and a question's wait for the embedder's lock out); run on the files from before it, with the re-made run its entry names, it gives the corrected files again. |  |
| `correct_judge_embed_gpu_time.py` | The script that made the judging's GPU-time correction (RAGAS's own embedding requests made on the CPU given the time the same requests take on the desktop's graphics card); run on the files from before it, with its evidence file, it gives the corrected files again. |  |
| `judge_embed_gpu_times.json` | The evidence of the judging's GPU-time correction: per RAGAS embedding request that the six final runs' judging made on the CPU, its seconds on the graphics card, its recorded seconds, texts and tokens. | run = the run folder; line = the record's line in eval_calls.jsonl, from 0; question_id, eval_leg, seq = the record's own |
| `correct_model_call_time.py` | The script that made the model-call-time correction (each answer call and first call given its answering try's server time, and a call started past the login's limit its arm's clean relation at its own output tokens); run on the files from before it, over the same run folders, it gives the corrected files again. |  |
| `model_call_times.json` | The evidence of the model-call-time correction: the login's backlog of claude-sonnet-5 input tokens (its rate, its limit, the files it was read from with their sha256), the clean relation of each arm and kind of call, and per corrected call its server time, backlog, relation time and time; with the check of the relations on calls sent again one at a time. | question_id = id of arm_outputs.jsonl; record = the call's place in calls; seq = calls[].seq |
| `correct_code_version_from_reflog.py` | The script that made the code-version correction (the commit each start ran on, by its clone's own reflog, where git gave no answer when the start began); run on the files from before it, with its evidence file, it gives the corrected files again. |  |
| `code_reflog.txt` | The evidence of the code-version correction: the reflog of the clone the run ran in, written on that machine: each move of HEAD, its commit, time and why. |  |
| `desktop_start_20261026T001551Z_FIELDS.md`, `desktop_start_20261026T001551Z_eval_manifest.json`, `desktop_start_20261026T001551Z_run_manifest.json`, `desktop_start_20261026T001551Z_sha256.txt` | The records of a start that ran in this run's own folder on the desktop after the folder kept here was copied from it: its run_manifest.json, eval_manifest.json and FIELDS.md as that start wrote them, and the sha256 of the folder's files as they then stood. The start answered no question and judged no cell (its judging entry holds 0 calls), so no value of this folder changes by it; the name holds when it began. |  |

Times are seconds (`_s`), milliseconds (`_ms`) or UTC stamps (`_at`; every other time text carries its own zone). Sizes are tokens, characters (`chars`) or bytes. A count (calls, attempts, requests, texts, records, edges, refits, and the like) is a plain number of the things it names. A price (`usd`, `USD`) is the Claude program's own, in US dollars; no number of this harness uses it. The evaluation's scores run from 0 to 1 and higher is more; a score an arm ranks by says its own scale.

## The scores

The scores are computed by RAGAS. The quoted sentence of each is RAGAS's own, from the place named; "Here" says what goes into it in this folder.

| `metric` | What it measures | Needs | Between arms |
|---|---|---|---|
| `context_recall_id` | "Calculates context recall by directly comparing retrieved context IDs with reference context IDs. The score represents what proportion of the reference IDs were successfully retrieved." (RAGAS, class IDBasedContextRecall) Here: context_ids against the ids of the question's gold records. | nothing | yes |
| `context_precision_id` | "Calculates context precision by directly comparing retrieved context IDs with reference context IDs. The score represents what proportion of the retrieved context IDs are actually relevant (present in reference)." (RAGAS, class IDBasedContextPrecision) Here: context_ids against the ids of the question's gold records. | nothing | yes |
| `context_recall_nonllm` | "`NonLLMContextRecall` metric is computed using `retrieved_contexts` and `reference_contexts` [...] This metrics uses non-LLM string comparison metrics to identify if a retrieved context is relevant or not." (RAGAS, docs, context_recall.md) Here: the content of each record handed over (record_content; every text cut into its records) against the content of each gold record; a gold record counts as found when a delivered record's content is more than 0.5 like it (Levenshtein). | nothing | no, within one arm only |
| `context_precision_nonllm` | "To determine if a retrieved context is relevant, this method compares each retrieved context or chunk in `retrieved_contexts` with every context in `reference_contexts` using a non-LLM-based similarity measure." (RAGAS, docs, context_precision.md) Here: the content of each record handed over (record_content; every text cut into its records) against the gold records' content, 0.5 or more alike (Levenshtein), weighted by rank. | nothing | no, within one arm only |
| `context_recall_llm` | "Estimates context recall by estimating TP and FN using annotated answer and retrieved context." (RAGAS, class LLMContextRecall) Here: the gold answer, sentence by sentence, against contexts. | the judge | yes |
| `faithfulness` | "The **Faithfulness** metric measures how factually consistent a `response` is with the `retrieved context`. [...] A response is considered **faithful** if all its claims can be supported by the retrieved context." (RAGAS, docs, faithfulness.md) Here: the answer's claims against contexts. | the judge | yes |
| `answer_correctness` | "Measures answer correctness compared to ground truth as a combination of factuality and semantic similarity." (RAGAS, class AnswerCorrectness) Here: the answer against the gold answer: 0.75 times the F1 of the claims the judge finds in both, plus 0.25 times semantic_similarity (RAGAS's own weights). | the judge and the embedder | yes |
| `factual_correctness` | "It uses claim decomposition and natural language inference (NLI) to verify the claims made in the responses against reference texts." (RAGAS, class FactualCorrectness) Here: the answer against the gold answer: the F1 of the answer's claims the judge finds in the gold answer and the gold answer's claims it finds in the answer (RAGAS's defaults: mode f1, beta 1, atomicity and coverage low), rounded to two decimals. | the judge | yes |
| `context_entity_recall` | "Calculates recall based on entities present in ground truth and context." (RAGAS, class ContextEntityRecall) Here: the entities the judge finds in the gold answer, found among the entities it finds in contexts joined into one text. | the judge | yes |
| `semantic_similarity` | "The **Semantic Similarity** metric evaluates the semantic resemblance between a generated response and a reference (ground truth) answer. [...] This metric uses embeddings and cosine similarity" (RAGAS, docs, semantic_similarity.md) Here: the answer against the gold answer, both embedded in passage mode. | the embedder | yes |
| `string_similarity` | "`NonLLMStringSimilarity` metric measures the similarity between the reference and the response using traditional string distance measures such as Levenshtein, Hamming, and Jaro." (RAGAS, docs, traditional.md) Here: the answer against the gold answer, Levenshtein. | nothing | yes |
| `bleu` | "It measures the similarity between the response and the reference based on n-gram precision and brevity penalty." (RAGAS, docs, traditional.md) Here: the answer against the gold answer. | nothing | yes |
| `rouge` | "It measures the overlap between the generated `response` and the `reference` text based on n-gram recall, precision, and F1 score." (RAGAS, docs, traditional.md) Here: the answer against the gold answer: rougeL, F measure. | nothing | yes |
| `chrf` | "The `CHRFScore` metric evaluates the similarity between a `response` and a `reference` using **character n-gram F-score**." (RAGAS, docs, traditional.md) Here: the answer against the gold answer. | nothing | yes |
| `exact_match` | "The `ExactMatch` metric checks if the response is exactly the same as the reference text." (RAGAS, docs, traditional.md) Here: the answer against the gold answer. | nothing | yes |
| `string_presence` | "The `StringPresence` metric checks if the response contains the reference text." (RAGAS, docs, traditional.md) Here: the answer against the gold answer. | nothing | yes |

"No, within one arm only": the score is counted per delivered text, and arms deliver texts of different size (one record, or a chunk of several records), so the same delivered records give different values. The id scores count record ids, the same for every arm.

No stored score is called a hit rate. Whether a question got any gold record at all can be read from `context_recall_id` being above 0.

## What was left out, and on whose word

- The questions: this run answers the 715 questions of data/answerable715.jsonl (inputs.ids_sha256): every question of HERB that has an answer ("::a::" in its id) and is not one of the 100 of data/gold100.jsonl, so that the runs on the two sets answer each of HERB's 815 such questions once (his 2026-10-25 "the fucking point is to have a full ragas-herb test done finally"). HERB's 699 questions with no answer ("::u::") are in neither set: no rule in his words is recorded.
- The directory files: the corpus's three directory files (people, teams, customers) are not embedded beside the product records (retrieval_flags.HERB_BASELINE_METADATA off). No rule in his words is recorded.

## Easy to read wrongly

- `top_k` in the manifest is not used by a run with a character budget.
- `generator.payload` is what the harness asked for. `applied` and `not_applied` are what a call carried.
- `calls` counts answers, `attempts` counts tries. `tokens_in` and `tokens_out` are those of the try that answered; a try that did not answer is in the call's own record under `attempts`.
- `retrieval` is a list with one entry per model. A language model's tokens and the embedder's tokens are different things and are never added together; the same holds for the entries of `build_stats.models`.
- `search_time_s` holds no model call and no embedder request; their seconds are in `retrieval`. `timing.wall_s` is the whole question, and the harness's own work is in it beside those.
- In `build_stats.models`, `seconds_summed_per_call` and `seconds_elapsed` are two kinds of seconds: calls that ran side by side make the first more than the second.
- `tokens_in` includes what was read from the prompt cache; `cached_input_tokens` is that part alone.
- A text cut at the budget is in `contexts` and its record is not in `context_ids`, so the id scores do not count it.
- `request_s` includes the Claude program's own start and end. The time with the model alone is in the call's `envelope`.
- `wall_s` of a start ends when its answering ends. The judging's time is in `eval_manifest.json`.
- Paths (`questions_file`, `ids_file`, `source_run`) are from the machine that ran it and can be gone. The `sha256` fields under `inputs` identify what was read.
- The Claude program adds two things to every call that are in no row: a line first in the system text and a line with the day's date in front of the prompt (`lane.cli_adds`).

## `arm_outputs.jsonl`

One line per question: what was delivered, the answer, and everything the question cost.

| Field | What it holds |
|---|---|
| `id` | The question's id. It joins a row to its score rows (question_id) and to the question set. |
| `question` | The question as it was asked. |
| `answer` | The answer the model gave from the delivered texts. |
| `answered_at` | When the row was written (UTC). |
| `contexts` | The texts handed to the model, best first, as many as fit the character budget. The last one can be a text cut where the budget ended. |
| `context_ids` | The ids of the corpus records that were handed over whole, in the same order. A text cut at the budget is in contexts but its record is not counted here. |
| `search_time_s` | Seconds the arm took to rank the corpus for this question, without any model call or embedder request it made on the way. |
| `generator` | What the answer call cost. Its fields: see "What a model's work cost" below. |
| `retrieval` | What the arm's own model calls and embedder requests for this question cost, one entry per model, in the order the models were first asked; two models are never added together. The harness works it out from the question's call records (calls), the answer call left out, the same way for every arm. Empty for an arm that makes none. |
| `retrieval.kind` | chat: a language model. embed: the embedder. |
| `retrieval.model` | The model, by its id or name. |
| `retrieval.calls` | chat: how many answers; an answer is one call, however many tries it took. embed: how many batches the embedder was given. |
| `retrieval.attempts` | chat: how many times the model was asked in all, the tries that did not answer included. embed: the same as calls; the embedder is asked once a batch. |
| `retrieval.tokens_in` | chat: tokens sent in the tries that answered, the part read from the prompt cache included. embed: the tokens of the texts, prefix included. |
| `retrieval.cached_input_tokens` | chat: the part of tokens_in read from the prompt cache. embed: 0. |
| `retrieval.tokens_out` | chat: tokens the model wrote in the tries that answered. embed: 0. |
| `retrieval.reasoning_tokens` | Always 0. |
| `retrieval.time_s` | request_s + wait_s + retry_s. |
| `retrieval.request_s` | chat: seconds of the tries that answered. embed: seconds the embedder worked (encode_s). |
| `retrieval.wait_s` | chat: 0. embed: seconds the requests waited for the embedder to be free (lock_wait_s). |
| `retrieval.retry_s` | chat: seconds of the tries that did not answer and of the pauses before trying again; a try a correction marked as slept under is left out. embed: 0. |
| `leg` | Which start of this folder made the row: 1 for the first start, one more for each time the run was taken up again. The start is in run_manifest.json under legs. |
| `timing` | The clock of the whole question: ranking and answering. Its fields: see "A clock" below. |
| `calls` | Every model call and every embedder request the question made, whole. Its fields: see "A call record" below. |
| `correction` | Only where a stored number was corrected after the run: the rule, the value as recorded and the corrected value, the seconds taken out (taken_out_s), and in the sleep correction each slept try with its number within the call (from 1), its start, its seconds and its timeout in seconds. The folder's corrections.json tells the whole of it, and the files as recorded stand beside the corrected ones. |
| `meta` | What the arm recorded about this question's ranking. |
| `meta.char_budget` | How the character budget was filled. |
| `meta.char_budget.budget` | The character budget. |
| `meta.char_budget.chars` | How many characters were handed over. |
| `meta.char_budget.kept` | How many units were handed over whole. |
| `meta.char_budget.boundary` | The unit that was cut where the budget ended. Empty when the budget ended exactly at a unit's end, or when the ranking ran out first. |
| `meta.char_budget.boundary.id` | The id of its record. |
| `meta.char_budget.boundary.chars_kept` | How many of its characters were handed over. |
| `meta.char_budget.boundary.chars_full` | How many characters it has. |
| `meta.char_budget.exhausted` | Whether the ranking ran out before the budget was full. |
| `meta.ranking` | The ranking the delivered texts were taken from. |
| `meta.ranking.n_units` | How many units the index holds. |
| `meta.ranking.n_ranked` | How many of them were ranked: all of them. |
| `meta.ranking.scores` | The cosine between the question's vector and each delivered text's vector, in delivered order. |
| `meta.ranking.next_score` | The cosine of the first unit that was not delivered; empty when none was left. |
| `meta.chunk_ids` | Only in a run cut at a depth with the directory files indexed: the record ids behind each delivered text. |

## `eval_results.jsonl`

One line per question and score: the score.

| Field | What it holds |
|---|---|
| `question_id` | The question's id: the id of its row in arm_outputs.jsonl. |
| `type` | The question's kind in the benchmark (person, content, pr, company, url). |
| `arm` | The retrieval method. |
| `metric` | Which score this row is. The scores are described above. |
| `value` | The score. |
| `status` | ok; nan when the scoring gave no number; error when it failed. |
| `components` | What belongs to the score beside its value. |
| `components.usage` | What computing this one score for this one question cost. Its fields: see "What a score cell cost" below. |
| `components.error` | The error of a cell that failed. |
| `human_label` | Not used; always empty. |

## `eval_calls.jsonl`

One line per judge call and per embedder request of the scoring, whole. The judge's prompts hold the gold answers.

| Field | What it holds |
|---|---|
| `eval_leg` | Which scoring start made the call, by that start's starting time. |
| `arm` | The retrieval method. |
| `question_id` | The question the call was made for; empty for the embeddings made once before the cells. |
| `type` | The question's kind in the benchmark; not there for the embeddings made once before the cells. |
| `score` | The score the call was made for; empty for the embeddings made once before the cells (phase prime), which serve several scores. |
| `phase` | cell: made for one question and one score. prime: embeddings made once, before the cells. |

Beside these, each line has the fields of "A call record" below.

## `run_manifest.json`

What the run was: the arm, its index, the code, the machine, the inputs, and every start of this folder.

| Field | What it holds |
|---|---|
| `arm` | The retrieval method the run tested. |
| `generator_model` | The model that wrote the answers; empty for a run without answers. |
| `interpreter_model` | The model an arm uses to read the question before ranking; empty for an arm that uses none. |
| `top_k` | The number of units handed to the arm as a depth. A run with a character budget does not use it: the arm ranks everything and the budget decides how much is handed over. |
| `char_budget` | How many characters of delivered text each question gets; empty for a run cut at a depth instead. |
| `questions_file` | The file the questions were read from, as a path on the machine that ran it. The path can be gone; inputs.questions_sha256 identifies the file. |
| `n_questions` | How many questions the set holds. |
| `n_ran` | How many have an answer row. |
| `n_failed` | How many have none. |
| `n_exhausted` | For how many the ranking ran out before the budget was full. |
| `timestamp` | When this file was written (UTC). |
| `build_stats` | What building the arm's index cost. |
| `build_stats.build_time_s` | Seconds it took. For an index read from a stored file it is what the making of that file took. For a graph built in steps it is the elapsed seconds and the command spans of every step whose records give them, added; work that was replaced later is not counted. Empty when no record gives them. |
| `build_stats.models` | One entry per model that worked on the build, in the order of the build; two models are never added together. Empty for an index built without a model. |
| `build_stats.models.kind` | chat: a language model. embed: the embedder. encoder: a model that encoded the tag-to-chunk edges for the facet values, or the candidates tried for that. |
| `build_stats.models.model` | The model, by its id or name. |
| `build_stats.models.what` | What the model did in the build. |
| `build_stats.models.calls` | How many calls or requests its records count, added over the model's parts where it worked in several (for a graph, index.build_cost holds each part); empty when they count none. |
| `build_stats.models.tokens_in` | Tokens sent, as the records give them, added over the model's parts in the same way; empty when they do not give them. |
| `build_stats.models.tokens_out` | Tokens written, added over the model's parts in the same way; 0 for the embedder and the encoders, which write none; empty when the records do not give them. |
| `build_stats.models.seconds_summed_per_call` | The seconds of each call added up, over the model's parts in the same way. Calls that ran side by side make this more than the time it took. Empty when the records do not give it. |
| `build_stats.models.seconds_elapsed` | Start to end of the model's work, as its records give it, added over its parts where they ran one after the other; empty when they do not give it. |
| `build_stats.models.device` | Where it ran. |
| `build_stats.models.not_recorded` | What the records do not give for this model; empty when they leave nothing out. |
| `build_stats.not_recorded` | What the build records do not give, step by step; empty when nothing is noted. |
| `build_stats.as_the_arm_gave_it` | Only for an older arm that gave one sum for none or several models: that sum and the names, as given. |
| `flags` | The switches given on the command line, each by its name with the value it was given; empty when none. What a switch does is the arm's to say (retrieval_flags). |
| `graph` | For an arm that reads the graph database: which database, its last build record, and the graph as counted when this manifest was written. Empty for an arm that reads none. |
| `graph.database` | The Neo4j database the arm read. |
| `graph.graph_version` | The version the graph's last build record names. The build record is output/graph_build/<database>/build_manifest.json; these five are empty when the folder that ran had none. Steps that changed the graph after that build are in the arm's index (build_cost). |
| `graph.graph_census_sha256` | The census hash the last build record gives, of the graph as that build left it. |
| `graph.removed_tags_sha256` | The hash of the tags the build record says were removed; empty when the build record gives none. |
| `graph.build_timestamp` | When the last build record was written (UTC). |
| `graph.source_database` | The database the last build copied from. |
| `graph.census` | The graph as counted in it when this manifest was written. It counts and reads no value. |
| `graph.census.labels` | Nodes per set of labels, the labels joined by ':'. |
| `graph.census.relationships` | Relationships per type and the label sets at their start and end. |
| `graph.census.node_properties` | Per set of labels, how many nodes carry each property. |
| `graph.census.relationship_properties` | Per relationship type, how many carry each property. |
| `graph.census_sha256` | The sha256 of the census, its keys in order: two runs with the same value read a graph of the same shape. |
| `graph.census_error` | Why the graph could not be counted; there only then. |
| `graph.mixed_builds` | Only when the starts of this folder read different graphs: the graph block of each start, in order. |
| `code_version` | The code the last answering start ran on. Its fields: see "The code" below. |
| `environment` | The machine and the software. |
| `environment.host` | The machine's name. |
| `environment.platform` | Its operating system. |
| `environment.python` | The Python version. |
| `environment.python_executable` | The Python that ran. |
| `environment.cpu` | The processor. |
| `environment.cpu_count` | How many processor threads it has. |
| `environment.ram_bytes` | How much memory it has. |
| `environment.packages` | The versions of the packages the run rests on most. |
| `environment.packages_all` | Every installed package with its version. |
| `environment.embedder` | The embedding model the run is set to use. |
| `environment.embedder.model` | Its name. |
| `environment.embedder.revision` | Its exact version. |
| `environment.embedder.device` | Where it runs. |
| `environment.embedder.dtype` | The number type it computes in. |
| `inputs` | What the run read, as hashes: these identify the inputs, the paths do not. |
| `inputs.questions_sha256` | The sha256 of the questions file. |
| `inputs.ids_sha256` | The sha256 of the file that lists the set's questions. |
| `inputs.corpus` | The corpus. |
| `inputs.corpus.sha256` | One sha256 over all its files, each by its path and its own sha256. |
| `inputs.corpus.n_files` | How many files that is. |
| `legs` | One entry per start of this folder, in order. |
| `legs.leg` | The start's number, from 1. |
| `legs.started_at` | When the start began (UTC). |
| `legs.finished_at` | When its answering ended (UTC). The judging comes after and is in eval_manifest.json. |
| `legs.wall_s` | Seconds of the start up to the end of its answering. |
| `legs.process_cpu_s` | Processor seconds the run's own process used in that time. Model calls run in other processes and are not in it. |
| `legs.workers` | How many questions were worked on at once. |
| `legs.argv` | The command line of the start. |
| `legs.pid` | The process number of the start. |
| `legs.python_executable` | The Python that ran it. |
| `legs.ids_file` | The file that lists the questions of the set, as a path on the machine that ran it. The path can be gone; inputs.ids_sha256 is what identifies the set. |
| `legs.n_chosen` | How many questions the set holds. |
| `legs.n_todo` | How many of them had no row yet when the start began. |
| `legs.n_answered` | How many the start answered. |
| `legs.n_unanswered_after` | How many still had no row when it ended. |
| `legs.aborted` | Why the start stopped early; empty when it did not. |
| `legs.prepare_s` | Seconds the arm took to get ready before the first question (building or loading its index). |
| `legs.embedder_load_s` | Seconds the embedder took to load in this process; empty when it was not loaded by then. |
| `legs.retrieval_only` | Whether the start ranked only, with no answer and no judging. |
| `legs.evaluator` | What scored the answers after the start: ragas, or gen when nothing did. |
| `legs.peak_memory_bytes` | The most memory the run's process held up to the end of the answering. |
| `legs.code_version` | The code the start ran on, read before it answered anything. Its fields: see "The code" below. |
| `legs.code_state` | How that code differed from the commit. Its fields: see "How the code differed from its commit" below. |
| `legs.flags` | The switches given on the command line for this start, each by its name with the value it was given; empty when none. What a switch does is the arm's to say (retrieval_flags). |
| `legs.lane` | How every model call of the start was made. Its fields: see "How model calls were made" below. |
| `legs.correction` | Only where a stored number was corrected after the run: the rule, the value as recorded and the corrected value, the seconds taken out (taken_out_s), and in the sleep correction each slept try with its number within the call (from 1), its start, its seconds and its timeout in seconds. The folder's corrections.json tells the whole of it, and the files as recorded stand beside the corrected ones. |
| `legs.source_run` | Only in a folder merged from two runs (merge.json): the run this start belongs to, by its folder's name; that folder is kept whole under halves/. |
| `legs.source_leg` | Only in a merged folder: the start's number in that run. |
| `legs.from_its_log` | Only in an entry rebuilt by correction unrecorded-starts/1 (corrections.json) for a start that wrote rows and no entry: what the start's own log says; the entry's other fields that the log cannot give are empty. |
| `legs.from_its_log.log` | The start's log, by its path in the folder the correction was made in. |
| `legs.from_its_log.embedder_device` | The device the log says the embedder loaded on; empty when it loaded none. |
| `legs.from_its_log.last_lines` | The log's last lines that name no question. |
| `legs.from_its_log.rule` | The correction's rule. |
| `legs.environment` | Only in a merged folder: the machine and the software of that run. |
| `legs.environment.host` | The machine's name. |
| `legs.environment.platform` | Its operating system. |
| `legs.environment.python` | The Python version. |
| `legs.environment.python_executable` | The Python that ran. |
| `legs.environment.cpu` | The processor. |
| `legs.environment.cpu_count` | How many processor threads it has. |
| `legs.environment.ram_bytes` | How much memory it has. |
| `legs.environment.packages` | The versions of the packages the run rests on most. |
| `legs.environment.packages_all` | Every installed package with its version. |
| `legs.environment.embedder` | The embedding model the run is set to use. |
| `legs.environment.embedder.model` | Its name. |
| `legs.environment.embedder.revision` | Its exact version. |
| `legs.environment.embedder.device` | Where it runs. |
| `legs.environment.embedder.dtype` | The number type it computes in. |
| `legs.env` | Only in a merged folder: that run's environment variables that can change what a run or a model call does, by name. A secret shows as <set>. |
| `legs.index` | What the arm's index is. Its fields: see "The arm's index" below. |
| `workers` | How many questions were worked on at once in the last start. |
| `lane` | How every model call was made. Its fields: see "How model calls were made" below. |
| `generator` | What every answer call is given. |
| `generator.model` | The model. |
| `generator.system` | The system text. |
| `generator.user_template` | How the prompt is put together from the delivered texts and the question. |
| `generator.schema` | The JSON schema the answer has to follow. |
| `generator.payload` | What the harness asks of the call. It is the asking, not what happened: applied and not_applied say what the call carried. |
| `generator.applied` | What of that the call carries, one entry per setting. |
| `generator.not_applied` | What of that it cannot carry, each with the reason. |
| `generator.env_set` | The environment variables set for the call, by name. |
| `generator.env_unset` | The switches taken away for the call. |
| `generator.timeout_s` | The longest a try may take. |
| `code_state` | How the code differed from the commit. Its fields: see "How the code differed from its commit" below. |
| `env` | The environment variables of the run that can change what a run or a model call does, by name. A secret shows as <set>. |
| `index` | What the arm's index is. Its fields: see "The arm's index" below. |
| `retrieval_flags` | The arm's own switches. |
| `retrieval_flags.HERB_BASELINE_METADATA` | Whether the corpus's three directory files (people, teams, customers) are taken in beside the records. Off: the records only. |

## `eval_manifest.json`

What the scoring was: the judge, its settings, and what it cost.

| Field | What it holds |
|---|---|
| `scorer` | What scored the answers. |
| `judge_model` | The model that judged. |
| `source_run` | The folder that was scored, as a path on the machine that ran it. |
| `arm` | The retrieval method. |
| `timestamp` | When this file was written (UTC). |
| `judge_backend` | The way the judge was called. |
| `judge_effort` | The effort level set for a judge that takes one; empty otherwise. |
| `judge_usage` | What all judge calls cost, summed over every scoring start. Its fields: see "What a model's work cost" below. |
| `judge_elapsed_s` | Seconds of all scoring starts, summed. |
| `judge_legs` | One entry per scoring start, in order. |
| `judge_legs.timestamp` | When the start's entry was written (UTC). |
| `judge_legs.judge_model` | The model that judged in this start; empty when it made no judge call. |
| `judge_legs.judge_backend` | The way the judge was called. |
| `judge_legs.usage` | What the start's judge calls cost. Its fields: see "What a model's work cost" below. |
| `judge_legs.elapsed_s` | Seconds the start took. |
| `judge_legs.settings` | What the start ran under. Its fields: see "What a scoring start ran under" below. |
| `judge_legs.source_run` | Only in a folder merged from two runs (merge.json): the run this scoring start belongs to, by its folder's name. |
| `judge_settings` | What the last scoring start ran under. Its fields: see "What a scoring start ran under" below. |

## `failures.jsonl`

One line per try at a question that failed. Empty when none did. A question that failed and was answered in a later start has a line here and a row.

| Field | What it holds |
|---|---|
| `id` | The question's id. |
| `error` | What went wrong. |
| `failed_at` | When (UTC). |
| `leg` | Which start it happened in. |
| `traceback` | Where in the code it went wrong. |
| `timing` | The clock of the try that failed. Its fields: see "A clock" below. |
| `calls` | Every call the try had made by then. Its fields: see "A call record" below. |

## `eval_failures.jsonl`

One line per score cell that failed. Empty when none did.

| Field | What it holds |
|---|---|
| `question_id` | The question's id. |
| `metric` | The score that failed. |
| `error` | What went wrong. |
| `eval_leg` | Which scoring start it happened in. |
| `failed_at` | When (UTC). |
| `usage` | What the failed cell had cost. Its fields: see "What a score cell cost" below. |

## `corrections.json`

Only in a folder whose stored numbers were corrected after the run: what was changed, by which rule, on whose word.

| Field | What it holds |
|---|---|
| `corrections` | One entry per correction, in the order they were made; each rests on the files the one before it left. |
| `corrections.made_at` | When the correction was made (UTC). |
| `corrections.ordered_by` | The words that ordered it. |
| `corrections.what_happened` | What was wrong in the stored numbers. |
| `corrections.rule` | The rule that decided which numbers were corrected, and how. |
| `corrections.not_changed_and_worth_knowing` | What the correction left as recorded and a reader should know. |
| `corrections.slept_tries` | Only in the sleep correction: the tries the rule found, each with its question, its row (the line of arm_outputs.jsonl, counted from 0), its try (its number within the call, from 1), its start (UTC), its recorded seconds, its timeout in seconds, the seconds of low power the machine logged inside it, whether a whole reply had come back, and that reply's tokens. |
| `corrections.changes` | Every changed value: where it is, the value before and the corrected value, and what was taken out (taken_out: seconds in the sleep correction; in the clean-up correction the embedder's seconds and the seconds of refused first calls). The value before is empty where the field was not there before the correction. A copied value keeps its empty parts; its own field's words say why they are empty. |
| `corrections.checks` | What the correction checked before it changed anything (in the clean-up correction against the call records and the graph), whether it held, and how many places were looked at. |
| `corrections.evidence` | Only in a correction that rests on a file it keeps in this folder: the file (or the files), its sha256 where given, and what it holds; in the sleep correction, the file that holds the machine's own record. |
| `corrections.before` | Only in the non-LLM record-content correction: the method that made the stored scores (method, and what_it_did), found by running each method the evaluation has used on the folder's own inputs; how many stored scores each method gives again, per score; and how many stored scores there were, per score. |
| `corrections.judge_calls_with_logged_low_power_time_inside_them` | Only in the sleep correction: judge calls the machine's own sleep record touches, not changed; each try as [its number from 1, its outcome, its seconds]. |
| `corrections.low_power_intervals_the_machine_logged` | Only in the sleep correction: the machine's own record of when it slept: start and end (UTC), seconds, and what the machine said. |
| `corrections.files` | The sha256 of each corrected file, before and after the correction, and where the file from before is kept. The sleep correction's are of the bytes on the disk that ran it; the clean-up correction's are of the files with the line ends git holds (LF), as line_ends says. |
| `corrections.script` | The script that made the correction. |
| `corrections.code` | The code the script ran on, which it imports its harness and arms from: the commit, whether anything differed from it, and what. |

## Groups of fields that stand in several places

### What a model's work cost

| Field | What it holds |
|---|---|
| `calls` | How many model calls this counts. An answer is one call, however many tries it took. |
| `attempts` | How many times the model was asked in all, the tries that did not answer included. |
| `tokens_in` | Tokens the model was sent in the try that answered: the provider's count of the whole input, the part it read from its prompt cache included. |
| `cached_input_tokens` | The part of tokens_in the provider read from its prompt cache instead of reading it fresh. It depends on what was sent shortly before, not on the arm. |
| `tokens_out` | Tokens the model wrote in the try that answered. |
| `reasoning_tokens` | Always 0: thinking is off, and this way of calling the model reports none. |
| `time_s` | Seconds from asking until the answer was in hand: request_s + wait_s + retry_s. |
| `request_s` | Seconds of the try that answered, from starting the Claude program to its reply. The program's own start and end are inside it. |
| `wait_s` | Always 0. Kept from an earlier way of calling models that queued. |
| `retry_s` | Seconds spent on tries that did not answer, and on the pauses before trying again. |

### A call record

| Field | What it holds |
|---|---|
| `kind` | chat: a call to a language model. (embed: a request to the embedder, see below.) |
| `seq` | The call's place among the calls of this question or score cell, from 0. |
| `model` | The model that was asked, by its id. |
| `revision` | The exact version of the embedding model. |
| `device` | Where the embedder ran (cpu, or a graphics card). |
| `dtype` | The number type the embedder computed in. |
| `input_type` | query or passage: which of the embedder's two modes the texts were given in. |
| `prefix` | The word put in front of each text for that mode. |
| `batch` | How many texts the embedder took at a time. |
| `n_texts` | How many texts the request held. |
| `texts` | The texts that were embedded. |
| `tokens` | The token count of each text, prefix included. |
| `tokens_in` | The sum of tokens. |
| `started_at` | When the call started (UTC). |
| `finished_at` | When the call ended (UTC). |
| `lock_wait_s` | Seconds the request waited for the embedder to be free. |
| `encode_s` | Seconds the embedder worked on the request. |
| `exe` | The Claude program that made the call. |
| `flags` | The arguments the program was started with, without the system text and the schema. The empty argument after --tools is the empty tool list: the call has no tool. |
| `system` | The system text sent with the call; empty when the caller gave none. |
| `schema` | The JSON schema the reply had to follow, when the caller gave one. |
| `prompt` | The text sent as the user's message, exactly as sent. |
| `effort` | The effort level the caller named; empty when it named none. |
| `join_parts` | Whether a reply written in several parts was joined. Not used by the answer call or the judge. |
| `cwd` | The folder the program was started in. |
| `timeout_s` | The longest a try may take before it is cut. |
| `max_tries` | The most tries the call may make. |
| `env_set` | The environment variables the harness set for this call, by name: the switches that shape what the program sends. |
| `env_unset` | The switches the harness took away for this call, so that a value left in the shell did not reach it. |
| `applied` | What the caller asked for and the call carried, one entry per setting. |
| `not_applied` | What the caller asked for and the call could not carry, each with the reason; empty when the call carried all of it. |
| `payload_dropped` | The names of the settings in not_applied. |
| `attempts` | Every try of the call, in order. |
| `attempts.n` | The try's number within the call, from 1. |
| `attempts.credential` | What the try logged in with: subscription (the lane's token) or api_key (the CLAUDE_API key, sent as ANTHROPIC_API_KEY). |
| `attempts.started_at` | When the try started (UTC). |
| `attempts.seconds` | How long the try took. |
| `attempts.outcome` | ok (it answered), exit (the program ended with an error), usage_limit (the subscription refused it at its usage limit, HTTP 429, and the same try went again with the CLAUDE_API key), bad_envelope (its reply could not be read), or timeout (cut at timeout_s). |
| `attempts.returncode` | The program's exit code; empty for a timeout. |
| `attempts.error` | The error of a try that did not answer; empty for the try that answered. |
| `attempts.stdout` | What the program printed, kept for a try that did not answer; empty for the try that answered, whose reply is in text and envelope. |
| `attempts.stderr` | What the program printed as errors, kept for a try that did not answer; empty for the try that answered, and empty when the program printed nothing. |
| `attempts.backoff_s` | The pause after a try that did not answer, before the next one. |
| `attempts.machine_asleep` | Only where a correction marked the try: the machine slept under it. See corrections.json. |
| `ok` | Whether the call ended with an answer. |
| `credential` | What the try that answered logged in with: subscription or api_key; empty when no try answered. |
| `text` | The reply's text. For an answer call it is the JSON that holds the answer. Empty for a call that gave up: no try answered. |
| `usage` | The tokens of the try that answered; empty for a call that gave up. |
| `usage.prompt_tokens` | Tokens sent: fresh input, plus what was written to the prompt cache, plus what was read from it. |
| `usage.completion_tokens` | Tokens the model wrote. |
| `usage.cached_input_tokens` | The part of prompt_tokens read from the prompt cache. |
| `envelope` | The Claude program's whole reply as it printed it, each part as the program gives it: its own times in milliseconds (duration_ms for the whole program run, duration_api_ms for the time spent with the model, ttft_ms until the first token, ttft_stream_ms and time_to_request_ms), its own token counts, the models it used with their context window in tokens (contextWindow), its own price in US dollars (total_cost_usd, costUSD; no number of this harness uses it), its counts of web requests (0: the call has no tool), its session id, how many turns it took, and its error fields, which are empty when the call had no error (api_error_status, permission_denials). Empty for a call that gave up: no reply was read. |
| `stream` | The raw stream of a reply joined from parts; empty otherwise. |
| `stderr` | What the program printed as errors in the try that answered; empty when it printed nothing, and for a call that gave up. |
| `error` | The last error of a call that gave up; empty otherwise. |
| `role` | answer: the call that wrote the answer. Not there on the arm's own calls. |

A record with `kind` chat is a call to a language model; one with `kind` embed is a request to the embedder and has only the fields that say so.

### A clock

| Field | What it holds |
|---|---|
| `started_at` | When the work started (UTC). |
| `finished_at` | When the work ended (UTC). |
| `wall_s` | Seconds from start to end. Where a correction is recorded it is smaller than the two stamps are apart; the stamps are clock times. |
| `thread` | The worker thread that did the work. |

### The code

| Field | What it holds |
|---|---|
| `commit` | The git commit the code was at. |
| `branch` | The git branch; HEAD when the code ran from a checkout of one commit. |
| `dirty` | Whether git saw anything changed or new anywhere in the checkout, files that are not code included. What differed in the code is in code_state. |

### How the code differed from its commit

| Field | What it holds |
|---|---|
| `status` | The code paths that differed from the commit, as git lists them. Empty when the code was exactly the commit. |
| `diff_sha256` | The sha256 of the difference between the code and the commit. When nothing differs it is the sha256 of nothing. |
| `diff_file` | The file in this folder that holds that difference; there only when there is one. |
| `untracked_sha256` | The sha256 of each code file git did not know; empty when git knew every code file. |

### How model calls were made

| Field | What it holds |
|---|---|
| `exe` | The Claude program used for every model call. |
| `cli_version` | Its version. |
| `cwd` | The folder it is started in. |
| `fixed_flags` | The arguments every call is started with. The empty argument after --tools is the empty tool list: no call has a tool. |
| `system_prompt` | How the system text is passed. |
| `stdin` | How the prompt is handed over. |
| `env_set` | The environment variables set on every call, by name. |
| `login` | How the program logs in. |
| `config_settings` | The settings file the harness puts in the program's own config folder; cleanupPeriodDays is how many days the program keeps its own transcripts of the calls. |
| `env_per_call` | The switches a call sets only when it asks for them, and that are taken away when it does not. |
| `per_call` | Where to find what each single call carried. |
| `cli_adds` | What the program puts into every call by itself. It is in no row. |
| `cli_adds.seen_with` | The program version it was seen with. |
| `cli_adds.system_prompt_first` | The line it puts first in the system text. |
| `cli_adds.in_front_of_the_prompt` | What it puts in front of the prompt. The date in it is the day of the call. |
| `max_tries_default` | The most tries a call makes when the caller names no number. |

### What a scoring start ran under

| Field | What it holds |
|---|---|
| `started_at` | When the scoring start began (UTC). |
| `finished_at` | When it ended (UTC). |
| `interrupted` | Why it was cut short; empty when it was not. |
| `workers` | How many score cells were worked on at once. |
| `retrieval_only` | Whether only the scores that need no model were made. |
| `scores` | The scores this start was set to make. |
| `judge_model` | The model set as judge. |
| `judge_backend` | The way the judge is called. |
| `judge_timeout_s` | The longest a judge call may take. |
| `judge_max_tries` | How many tries a judge call makes. |
| `judge_inflight` | The most judge calls that can be under way at once. |
| `judge_empty_reply_tries` | How many times a reply with no text in it is asked for again, in all. |
| `judge_call` | What every judge call is given. |
| `judge_call.model` | The model. |
| `judge_call.system` | The system text: none. |
| `judge_call.payload` | What the harness asks of the call. |
| `judge_call.applied` | What of that the call carries. |
| `judge_call.not_applied` | What of that it cannot carry, each with the reason. |
| `judge_call.env_set` | The environment variables set for the call, by name. |
| `judge_call.env_unset` | The switches taken away for the call. |
| `max_judge_context_chars` | Above this many delivered characters a warning is printed. It cuts nothing: the judge is sent the delivered texts whole. |
| `max_consecutive_failed_questions` | After this many questions in a row with mostly failed cells the scoring stops. |
| `ragas` | The version of RAGAS, the library that writes the judge's prompts and computes the scores. |
| `embed_model` | The embedding model the scores use. |
| `ragas_run_config` | RAGAS's own run settings as handed to it, in RAGAS's own units: timeout and max_wait in seconds, max_retries and max_workers as counts. |
| `ragas_do_not_track` | Whether RAGAS's usage reporting to its makers was switched off. |
| `lane` | How every judge call was made. Its fields: see "How model calls were made" below. |
| `calls_file` | The file that keeps every judge call and embedder request. |
| `argv` | The command line. |
| `pid` | The process number. |
| `python_executable` | The Python that ran. |
| `wall_s` | Seconds the scoring start took. |
| `embedding` | What the embedder did for this start, summed. |
| `embedding.requests` | How many requests. |
| `embedding.texts` | How many texts. |
| `embedding.tokens_in` | Their tokens. |
| `embedding.lock_wait_s` | Seconds spent waiting for the embedder. |
| `embedding.encode_s` | Seconds the embedder worked. |
| `cells` | How many score cells ended in each status. |

### What a score cell cost

| Field | What it holds |
|---|---|
| `eval_leg` | Which scoring start made the cell, by that start's own starting time. |
| `started_at` | When the cell started (UTC). |
| `finished_at` | When it ended (UTC). |
| `wall_s` | Seconds from start to end. |
| `thread` | The worker thread that did it. |
| `chat_calls` | How many judge calls the cell made. |
| `chat_attempts` | How many tries those took in all. |
| `tokens_in` | Tokens sent to the judge, summed over the cell's calls. |
| `cached_input_tokens` | The part of those the provider read from its prompt cache. |
| `tokens_out` | Tokens the judge wrote, summed. |
| `chat_s` | Seconds of all tries of the cell's judge calls, summed. |
| `embed_calls` | How many embedder requests the cell made. |
| `embed_texts` | How many texts those held. |
| `embed_tokens` | Their tokens. |
| `embed_s` | Seconds the embedder worked on them. |

### The arm's index

| Field | What it holds |
|---|---|
| `units` | How many units the index holds. A unit is one record of the corpus. |
| `text_chars` | The characters of all unit texts together. |
| `unit_text` | The form a record is written in to make its unit's text, and where that form is from. |
| `units_sha256` | One sha256 over all units in index order: per unit the id and then the text, each as UTF-8 behind its byte length written as 8 bytes, big end first. Two runs with the same value ran on the same units. |
| `matrix_shape` | The vectors: how many, and how many numbers each has. |
| `matrix_dtype` | The number type of the vectors. |
| `matrix_bytes` | Their size in memory. |
| `cache_file` | The stored file the vectors were read from, as a path on the machine that ran it. |
| `cache_file_bytes` | Its size. |
| `cache_file_sha256` | Its sha256, which identifies the vectors. |
| `cache_cost_note` | What making those vectors cost and on which machine, as noted beside the stored file when it was made: calls (requests to the embedder), batch (texts in a request), tokens, build_time_s and how it was read (build_time_note), max_seq_length (the most tokens a text may have) and how many units were longer, the device, the machine and the software. |
| `embedder_warm_s` | Seconds the embedder took for one empty request before the first question, so that no question pays for its loading. |
| `question_embedding` | When and how a question is embedded. |

## Fields without a word

None: every file and every field of this folder is described above.

## The fields as they stand in this folder

Counted from the files themselves when this was written. A record is a line of a .jsonl file, or the whole of a .json file. Empty is null, an empty text, an empty list or an empty object; the field's words say when and why it is empty.

### `arm_outputs.jsonl` (715 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `answer` | string | 715 | 0 |
| `answered_at` | string | 715 | 0 |
| `calls` | array | 715 | 0 |
| `calls.applied` | object | 715 | 0 |
| `calls.attempts` | array | 715 | 0 |
| `calls.attempts.backoff_s` | number | 43 | 0 |
| `calls.attempts.error` | null, string | 715 | 715 |
| `calls.attempts.n` | integer | 715 | 0 |
| `calls.attempts.outcome` | string | 715 | 0 |
| `calls.attempts.returncode` | integer | 715 | 0 |
| `calls.attempts.seconds` | number | 715 | 0 |
| `calls.attempts.started_at` | string | 715 | 0 |
| `calls.attempts.stderr` | null, string | 715 | 715 |
| `calls.attempts.stdout` | null, string | 715 | 715 |
| `calls.batch` | integer | 715 | 0 |
| `calls.cwd` | string | 715 | 0 |
| `calls.device` | string | 715 | 0 |
| `calls.dtype` | string | 715 | 0 |
| `calls.effort` | null | 715 | 715 |
| `calls.encode_s` | number | 715 | 0 |
| `calls.env_set` | object | 715 | 0 |
| `calls.env_unset` | array | 715 | 0 |
| `calls.envelope` | object | 715 | 0 |
| `calls.error` | null | 715 | 715 |
| `calls.exe` | string | 715 | 0 |
| `calls.finished_at` | string | 715 | 0 |
| `calls.flags` | array | 715 | 0 |
| `calls.input_type` | string | 715 | 0 |
| `calls.join_parts` | boolean | 715 | 0 |
| `calls.kind` | string | 715 | 0 |
| `calls.lock_wait_s` | number | 715 | 0 |
| `calls.max_tries` | integer | 715 | 0 |
| `calls.model` | string | 715 | 0 |
| `calls.n_texts` | integer | 715 | 0 |
| `calls.not_applied` | object | 715 | 0 |
| `calls.ok` | boolean | 715 | 0 |
| `calls.payload_dropped` | array | 715 | 0 |
| `calls.prefix` | string | 715 | 0 |
| `calls.prompt` | string | 715 | 0 |
| `calls.revision` | string | 715 | 0 |
| `calls.role` | string | 715 | 0 |
| `calls.schema` | object | 715 | 0 |
| `calls.seq` | integer | 715 | 0 |
| `calls.started_at` | string | 715 | 0 |
| `calls.stderr` | string | 715 | 715 |
| `calls.stream` | null | 715 | 715 |
| `calls.system` | string | 715 | 0 |
| `calls.text` | string | 715 | 0 |
| `calls.texts` | array | 715 | 0 |
| `calls.timeout_s` | number | 715 | 0 |
| `calls.tokens` | array | 715 | 0 |
| `calls.tokens_in` | integer | 715 | 0 |
| `calls.usage` | object | 715 | 0 |
| `calls.usage.cached_input_tokens` | integer | 715 | 0 |
| `calls.usage.completion_tokens` | integer | 715 | 0 |
| `calls.usage.prompt_tokens` | integer | 715 | 0 |
| `context_ids` | array | 715 | 0 |
| `contexts` | array | 715 | 0 |
| `generator` | object | 715 | 0 |
| `generator.attempts` | integer | 715 | 0 |
| `generator.cached_input_tokens` | integer | 715 | 0 |
| `generator.calls` | integer | 715 | 0 |
| `generator.reasoning_tokens` | integer | 715 | 0 |
| `generator.request_s` | number | 715 | 0 |
| `generator.retry_s` | number | 715 | 0 |
| `generator.time_s` | number | 715 | 0 |
| `generator.tokens_in` | integer | 715 | 0 |
| `generator.tokens_out` | integer | 715 | 0 |
| `generator.wait_s` | number | 715 | 0 |
| `id` | string | 715 | 0 |
| `leg` | integer | 715 | 0 |
| `meta` | object | 715 | 0 |
| `meta.char_budget` | object | 715 | 0 |
| `meta.char_budget.boundary` | object | 715 | 0 |
| `meta.char_budget.boundary.chars_full` | integer | 715 | 0 |
| `meta.char_budget.boundary.chars_kept` | integer | 715 | 0 |
| `meta.char_budget.boundary.id` | string | 715 | 0 |
| `meta.char_budget.budget` | integer | 715 | 0 |
| `meta.char_budget.chars` | integer | 715 | 0 |
| `meta.char_budget.exhausted` | boolean | 715 | 0 |
| `meta.char_budget.kept` | integer | 715 | 0 |
| `meta.ranking` | object | 715 | 0 |
| `meta.ranking.n_ranked` | integer | 715 | 0 |
| `meta.ranking.n_units` | integer | 715 | 0 |
| `meta.ranking.next_score` | number | 715 | 0 |
| `meta.ranking.scores` | array | 715 | 0 |
| `question` | string | 715 | 0 |
| `retrieval` | array | 715 | 0 |
| `retrieval.attempts` | integer | 715 | 0 |
| `retrieval.cached_input_tokens` | integer | 715 | 0 |
| `retrieval.calls` | integer | 715 | 0 |
| `retrieval.kind` | string | 715 | 0 |
| `retrieval.model` | string | 715 | 0 |
| `retrieval.reasoning_tokens` | integer | 715 | 0 |
| `retrieval.request_s` | number | 715 | 0 |
| `retrieval.retry_s` | number | 715 | 0 |
| `retrieval.time_s` | number | 715 | 0 |
| `retrieval.tokens_in` | integer | 715 | 0 |
| `retrieval.tokens_out` | integer | 715 | 0 |
| `retrieval.wait_s` | number | 715 | 0 |
| `search_time_s` | number | 715 | 0 |
| `timing` | object | 715 | 0 |
| `timing.finished_at` | string | 715 | 0 |
| `timing.started_at` | string | 715 | 0 |
| `timing.thread` | string | 715 | 0 |
| `timing.wall_s` | number | 715 | 0 |

### `corrections.json` (1 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `corrections` | array | 1 | 0 |
| `corrections.before` | object | 1 | 0 |
| `corrections.changes` | array | 1 | 0 |
| `corrections.checks` | array | 1 | 0 |
| `corrections.code` | object | 1 | 0 |
| `corrections.evidence` | object | 1 | 0 |
| `corrections.files` | object | 1 | 0 |
| `corrections.made_at` | string | 1 | 0 |
| `corrections.not_changed_and_worth_knowing` | array | 1 | 0 |
| `corrections.ordered_by` | string | 1 | 0 |
| `corrections.rule` | object | 1 | 0 |
| `corrections.script` | string | 1 | 0 |
| `corrections.what_happened` | string | 1 | 0 |

### `eval_calls.jsonl` (14653 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `applied` | object | 9139 | 0 |
| `arm` | string | 14653 | 0 |
| `attempts` | array | 9139 | 37 |
| `attempts.credential` | string | 6905 | 0 |
| `attempts.error` | null, string | 9102 | 8755 |
| `attempts.n` | integer | 9102 | 0 |
| `attempts.outcome` | string | 9102 | 0 |
| `attempts.returncode` | integer, null | 9102 | 35 |
| `attempts.seconds` | number | 9102 | 0 |
| `attempts.started_at` | string | 9102 | 0 |
| `attempts.stderr` | null, string | 9102 | 9100 |
| `attempts.stdout` | null, string | 9102 | 8794 |
| `batch` | integer | 5514 | 0 |
| `credential` | null, string | 6942 | 260 |
| `cwd` | string | 9139 | 0 |
| `device` | string | 5514 | 0 |
| `dtype` | string | 5514 | 0 |
| `effort` | null | 9139 | 9139 |
| `encode_s` | number | 5514 | 0 |
| `env_set` | object | 9139 | 0 |
| `env_unset` | array | 9139 | 9139 |
| `envelope` | null, object | 9139 | 384 |
| `error` | null, string | 9139 | 8755 |
| `eval_leg` | string | 14653 | 0 |
| `exe` | string | 9139 | 0 |
| `finished_at` | string | 14653 | 0 |
| `flags` | array | 9139 | 0 |
| `input_type` | string | 5514 | 0 |
| `join_parts` | boolean | 9139 | 0 |
| `kind` | string | 14653 | 0 |
| `lock_wait_s` | number | 5514 | 0 |
| `max_tries` | integer | 9139 | 0 |
| `model` | string | 14653 | 0 |
| `n_texts` | integer | 5514 | 0 |
| `not_applied` | object | 9139 | 9139 |
| `ok` | boolean | 9139 | 0 |
| `payload_dropped` | array | 9139 | 9139 |
| `phase` | string | 14653 | 0 |
| `prefix` | string | 5514 | 0 |
| `prompt` | string | 9139 | 0 |
| `question_id` | null, string | 14653 | 5514 |
| `revision` | string | 5514 | 0 |
| `schema` | null | 9139 | 9139 |
| `score` | null, string | 14653 | 5514 |
| `seq` | integer | 14653 | 0 |
| `started_at` | string | 14653 | 0 |
| `stderr` | null, string | 9139 | 9128 |
| `stream` | null | 9139 | 9139 |
| `system` | string | 9139 | 9139 |
| `text` | null, string | 9139 | 384 |
| `texts` | array | 5514 | 0 |
| `timeout_s` | number | 9139 | 0 |
| `tokens` | array | 5514 | 0 |
| `tokens_in` | integer | 5514 | 0 |
| `type` | string | 9139 | 0 |
| `usage` | null, object | 9139 | 384 |
| `usage.cached_input_tokens` | integer | 8755 | 0 |
| `usage.completion_tokens` | integer | 8755 | 0 |
| `usage.prompt_tokens` | integer | 8755 | 0 |

### `eval_failures.jsonl` (284 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `error` | string | 284 | 0 |
| `eval_leg` | string | 284 | 0 |
| `failed_at` | string | 284 | 0 |
| `metric` | string | 284 | 0 |
| `question_id` | string | 284 | 0 |
| `usage` | object | 284 | 0 |
| `usage.cached_input_tokens` | integer | 284 | 0 |
| `usage.chat_attempts` | integer | 284 | 0 |
| `usage.chat_calls` | integer | 284 | 0 |
| `usage.chat_s` | number | 284 | 0 |
| `usage.embed_calls` | integer | 284 | 0 |
| `usage.embed_s` | number | 284 | 0 |
| `usage.embed_texts` | integer | 284 | 0 |
| `usage.embed_tokens` | integer | 284 | 0 |
| `usage.eval_leg` | string | 284 | 0 |
| `usage.finished_at` | string | 284 | 0 |
| `usage.started_at` | string | 284 | 0 |
| `usage.thread` | string | 284 | 0 |
| `usage.tokens_in` | integer | 284 | 0 |
| `usage.tokens_out` | integer | 284 | 0 |
| `usage.wall_s` | number | 284 | 0 |

### `eval_manifest.json` (1 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `arm` | string | 1 | 0 |
| `judge_backend` | string | 1 | 0 |
| `judge_effort` | null | 1 | 1 |
| `judge_elapsed_s` | number | 1 | 0 |
| `judge_legs` | array | 1 | 0 |
| `judge_legs.elapsed_s` | null, number | 1 | 1 |
| `judge_legs.judge_backend` | string | 1 | 0 |
| `judge_legs.judge_model` | null, string | 1 | 1 |
| `judge_legs.settings` | object | 1 | 0 |
| `judge_legs.settings.argv` | array | 1 | 0 |
| `judge_legs.settings.calls_file` | string | 1 | 0 |
| `judge_legs.settings.cells` | object | 1 | 0 |
| `judge_legs.settings.embed_model` | string | 1 | 0 |
| `judge_legs.settings.embedding` | object | 1 | 0 |
| `judge_legs.settings.embedding.encode_s` | number | 1 | 0 |
| `judge_legs.settings.embedding.lock_wait_s` | number | 1 | 0 |
| `judge_legs.settings.embedding.requests` | integer | 1 | 0 |
| `judge_legs.settings.embedding.texts` | integer | 1 | 0 |
| `judge_legs.settings.embedding.tokens_in` | integer | 1 | 0 |
| `judge_legs.settings.finished_at` | null, string | 1 | 1 |
| `judge_legs.settings.interrupted` | null, string | 1 | 1 |
| `judge_legs.settings.judge_backend` | string | 1 | 0 |
| `judge_legs.settings.judge_call` | object | 1 | 0 |
| `judge_legs.settings.judge_call.applied` | object | 1 | 0 |
| `judge_legs.settings.judge_call.env_set` | object | 1 | 0 |
| `judge_legs.settings.judge_call.env_unset` | array | 1 | 1 |
| `judge_legs.settings.judge_call.model` | string | 1 | 0 |
| `judge_legs.settings.judge_call.not_applied` | object | 1 | 1 |
| `judge_legs.settings.judge_call.payload` | object | 1 | 0 |
| `judge_legs.settings.judge_call.system` | string | 1 | 1 |
| `judge_legs.settings.judge_empty_reply_tries` | integer | 1 | 0 |
| `judge_legs.settings.judge_inflight` | integer | 1 | 0 |
| `judge_legs.settings.judge_max_tries` | integer | 1 | 0 |
| `judge_legs.settings.judge_model` | string | 1 | 0 |
| `judge_legs.settings.judge_timeout_s` | number | 1 | 0 |
| `judge_legs.settings.lane` | object | 1 | 0 |
| `judge_legs.settings.lane.cli_adds` | object | 1 | 0 |
| `judge_legs.settings.lane.cli_adds.in_front_of_the_prompt` | string | 1 | 0 |
| `judge_legs.settings.lane.cli_adds.seen_with` | string | 1 | 0 |
| `judge_legs.settings.lane.cli_adds.system_prompt_first` | string | 1 | 0 |
| `judge_legs.settings.lane.cli_version` | string | 1 | 0 |
| `judge_legs.settings.lane.config_settings` | object | 1 | 0 |
| `judge_legs.settings.lane.cwd` | string | 1 | 0 |
| `judge_legs.settings.lane.env_per_call` | array | 1 | 0 |
| `judge_legs.settings.lane.env_set` | object | 1 | 0 |
| `judge_legs.settings.lane.exe` | string | 1 | 0 |
| `judge_legs.settings.lane.fixed_flags` | array | 1 | 0 |
| `judge_legs.settings.lane.login` | string | 1 | 0 |
| `judge_legs.settings.lane.max_tries_default` | integer | 1 | 0 |
| `judge_legs.settings.lane.per_call` | string | 1 | 0 |
| `judge_legs.settings.lane.stdin` | string | 1 | 0 |
| `judge_legs.settings.lane.system_prompt` | string | 1 | 0 |
| `judge_legs.settings.max_consecutive_failed_questions` | integer | 1 | 0 |
| `judge_legs.settings.max_judge_context_chars` | integer | 1 | 0 |
| `judge_legs.settings.pid` | integer | 1 | 0 |
| `judge_legs.settings.python_executable` | string | 1 | 0 |
| `judge_legs.settings.ragas` | string | 1 | 0 |
| `judge_legs.settings.ragas_do_not_track` | string | 1 | 0 |
| `judge_legs.settings.ragas_run_config` | object | 1 | 0 |
| `judge_legs.settings.retrieval_only` | boolean | 1 | 0 |
| `judge_legs.settings.scores` | array | 1 | 0 |
| `judge_legs.settings.started_at` | string | 1 | 0 |
| `judge_legs.settings.wall_s` | number | 1 | 0 |
| `judge_legs.settings.workers` | integer | 1 | 0 |
| `judge_legs.timestamp` | null, string | 1 | 1 |
| `judge_legs.usage` | object | 1 | 0 |
| `judge_legs.usage.attempts` | integer | 1 | 0 |
| `judge_legs.usage.cached_input_tokens` | integer | 1 | 0 |
| `judge_legs.usage.calls` | integer | 1 | 0 |
| `judge_legs.usage.reasoning_tokens` | integer | 1 | 0 |
| `judge_legs.usage.request_s` | number | 1 | 0 |
| `judge_legs.usage.retry_s` | number | 1 | 0 |
| `judge_legs.usage.time_s` | number | 1 | 0 |
| `judge_legs.usage.tokens_in` | integer | 1 | 0 |
| `judge_legs.usage.tokens_out` | integer | 1 | 0 |
| `judge_legs.usage.wait_s` | number | 1 | 0 |
| `judge_model` | string | 1 | 0 |
| `judge_settings` | object | 1 | 0 |
| `judge_settings.argv` | array | 1 | 0 |
| `judge_settings.calls_file` | string | 1 | 0 |
| `judge_settings.cells` | object | 1 | 0 |
| `judge_settings.embed_model` | string | 1 | 0 |
| `judge_settings.embedding` | object | 1 | 0 |
| `judge_settings.embedding.encode_s` | number | 1 | 0 |
| `judge_settings.embedding.lock_wait_s` | number | 1 | 0 |
| `judge_settings.embedding.requests` | integer | 1 | 0 |
| `judge_settings.embedding.texts` | integer | 1 | 0 |
| `judge_settings.embedding.tokens_in` | integer | 1 | 0 |
| `judge_settings.finished_at` | string | 1 | 0 |
| `judge_settings.interrupted` | null | 1 | 1 |
| `judge_settings.judge_backend` | string | 1 | 0 |
| `judge_settings.judge_call` | object | 1 | 0 |
| `judge_settings.judge_call.applied` | object | 1 | 0 |
| `judge_settings.judge_call.env_set` | object | 1 | 0 |
| `judge_settings.judge_call.env_unset` | array | 1 | 1 |
| `judge_settings.judge_call.model` | string | 1 | 0 |
| `judge_settings.judge_call.not_applied` | object | 1 | 1 |
| `judge_settings.judge_call.payload` | object | 1 | 0 |
| `judge_settings.judge_call.system` | string | 1 | 1 |
| `judge_settings.judge_empty_reply_tries` | integer | 1 | 0 |
| `judge_settings.judge_inflight` | integer | 1 | 0 |
| `judge_settings.judge_max_tries` | integer | 1 | 0 |
| `judge_settings.judge_model` | string | 1 | 0 |
| `judge_settings.judge_timeout_s` | number | 1 | 0 |
| `judge_settings.lane` | object | 1 | 0 |
| `judge_settings.lane.cli_adds` | object | 1 | 0 |
| `judge_settings.lane.cli_adds.in_front_of_the_prompt` | string | 1 | 0 |
| `judge_settings.lane.cli_adds.seen_with` | string | 1 | 0 |
| `judge_settings.lane.cli_adds.system_prompt_first` | string | 1 | 0 |
| `judge_settings.lane.cli_version` | string | 1 | 0 |
| `judge_settings.lane.config_settings` | object | 1 | 0 |
| `judge_settings.lane.cwd` | string | 1 | 0 |
| `judge_settings.lane.env_per_call` | array | 1 | 0 |
| `judge_settings.lane.env_set` | object | 1 | 0 |
| `judge_settings.lane.exe` | string | 1 | 0 |
| `judge_settings.lane.fixed_flags` | array | 1 | 0 |
| `judge_settings.lane.login` | string | 1 | 0 |
| `judge_settings.lane.max_tries_default` | integer | 1 | 0 |
| `judge_settings.lane.per_call` | string | 1 | 0 |
| `judge_settings.lane.stdin` | string | 1 | 0 |
| `judge_settings.lane.system_prompt` | string | 1 | 0 |
| `judge_settings.max_consecutive_failed_questions` | integer | 1 | 0 |
| `judge_settings.max_judge_context_chars` | integer | 1 | 0 |
| `judge_settings.pid` | integer | 1 | 0 |
| `judge_settings.python_executable` | string | 1 | 0 |
| `judge_settings.ragas` | string | 1 | 0 |
| `judge_settings.ragas_do_not_track` | string | 1 | 0 |
| `judge_settings.ragas_run_config` | object | 1 | 0 |
| `judge_settings.retrieval_only` | boolean | 1 | 0 |
| `judge_settings.scores` | array | 1 | 0 |
| `judge_settings.started_at` | string | 1 | 0 |
| `judge_settings.wall_s` | number | 1 | 0 |
| `judge_settings.workers` | integer | 1 | 0 |
| `judge_usage` | object | 1 | 0 |
| `judge_usage.attempts` | integer | 1 | 0 |
| `judge_usage.cached_input_tokens` | integer | 1 | 0 |
| `judge_usage.calls` | integer | 1 | 0 |
| `judge_usage.reasoning_tokens` | integer | 1 | 0 |
| `judge_usage.request_s` | number | 1 | 0 |
| `judge_usage.retry_s` | number | 1 | 0 |
| `judge_usage.time_s` | number | 1 | 0 |
| `judge_usage.tokens_in` | integer | 1 | 0 |
| `judge_usage.tokens_out` | integer | 1 | 0 |
| `judge_usage.wait_s` | number | 1 | 0 |
| `scorer` | string | 1 | 0 |
| `source_run` | string | 1 | 0 |
| `timestamp` | string | 1 | 0 |

### `eval_results.jsonl` (11440 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `arm` | string | 11440 | 0 |
| `components` | object | 11440 | 0 |
| `components.usage` | object | 11440 | 0 |
| `components.usage.cached_input_tokens` | integer | 11440 | 0 |
| `components.usage.chat_attempts` | integer | 11440 | 0 |
| `components.usage.chat_calls` | integer | 11440 | 0 |
| `components.usage.chat_s` | number | 11440 | 0 |
| `components.usage.embed_calls` | integer | 11440 | 0 |
| `components.usage.embed_s` | number | 11440 | 0 |
| `components.usage.embed_texts` | integer | 11440 | 0 |
| `components.usage.embed_tokens` | integer | 11440 | 0 |
| `components.usage.eval_leg` | string | 11440 | 0 |
| `components.usage.finished_at` | string | 11440 | 0 |
| `components.usage.started_at` | string | 11440 | 0 |
| `components.usage.thread` | string | 11440 | 0 |
| `components.usage.tokens_in` | integer | 11440 | 0 |
| `components.usage.tokens_out` | integer | 11440 | 0 |
| `components.usage.wall_s` | number | 11440 | 0 |
| `human_label` | null | 11440 | 11440 |
| `metric` | string | 11440 | 0 |
| `question_id` | string | 11440 | 0 |
| `status` | string | 11440 | 0 |
| `type` | string | 11440 | 0 |
| `value` | number | 11440 | 0 |

### `failures.jsonl` (0 records)

The file holds no record.

### `run_manifest.json` (1 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `arm` | string | 1 | 0 |
| `build_stats` | object | 1 | 0 |
| `build_stats.build_time_s` | number | 1 | 0 |
| `build_stats.models` | array | 1 | 0 |
| `build_stats.models.calls` | integer | 1 | 0 |
| `build_stats.models.device` | string | 1 | 0 |
| `build_stats.models.kind` | string | 1 | 0 |
| `build_stats.models.model` | string | 1 | 0 |
| `build_stats.models.not_recorded` | null | 1 | 1 |
| `build_stats.models.seconds_elapsed` | number | 1 | 0 |
| `build_stats.models.seconds_summed_per_call` | null | 1 | 1 |
| `build_stats.models.tokens_in` | integer | 1 | 0 |
| `build_stats.models.tokens_out` | integer | 1 | 0 |
| `build_stats.models.what` | string | 1 | 0 |
| `build_stats.not_recorded` | array | 1 | 1 |
| `char_budget` | integer | 1 | 0 |
| `code_state` | object | 1 | 0 |
| `code_state.diff_sha256` | null | 1 | 1 |
| `code_state.status` | null | 1 | 1 |
| `code_state.untracked_sha256` | object | 1 | 1 |
| `code_version` | object | 1 | 0 |
| `code_version.branch` | string | 1 | 0 |
| `code_version.commit` | string | 1 | 0 |
| `code_version.dirty` | null | 1 | 1 |
| `env` | object | 1 | 0 |
| `environment` | object | 1 | 0 |
| `environment.cpu` | string | 1 | 0 |
| `environment.cpu_count` | integer | 1 | 0 |
| `environment.embedder` | object | 1 | 0 |
| `environment.embedder.device` | string | 1 | 0 |
| `environment.embedder.dtype` | string | 1 | 0 |
| `environment.embedder.model` | string | 1 | 0 |
| `environment.embedder.revision` | string | 1 | 0 |
| `environment.host` | string | 1 | 0 |
| `environment.packages` | object | 1 | 0 |
| `environment.packages_all` | array | 1 | 0 |
| `environment.platform` | string | 1 | 0 |
| `environment.python` | string | 1 | 0 |
| `environment.python_executable` | string | 1 | 0 |
| `environment.ram_bytes` | integer | 1 | 0 |
| `flags` | null | 1 | 1 |
| `generator` | object | 1 | 0 |
| `generator.applied` | object | 1 | 0 |
| `generator.env_set` | object | 1 | 0 |
| `generator.env_unset` | array | 1 | 0 |
| `generator.model` | string | 1 | 0 |
| `generator.not_applied` | object | 1 | 0 |
| `generator.payload` | object | 1 | 0 |
| `generator.schema` | object | 1 | 0 |
| `generator.system` | string | 1 | 0 |
| `generator.timeout_s` | number | 1 | 0 |
| `generator.user_template` | string | 1 | 0 |
| `generator_model` | string | 1 | 0 |
| `graph` | null | 1 | 1 |
| `index` | object | 1 | 0 |
| `index.cache_cost_note` | object | 1 | 0 |
| `index.cache_file` | string | 1 | 0 |
| `index.cache_file_bytes` | integer | 1 | 0 |
| `index.cache_file_sha256` | string | 1 | 0 |
| `index.embedder_warm_s` | number | 1 | 0 |
| `index.matrix_bytes` | integer | 1 | 0 |
| `index.matrix_dtype` | string | 1 | 0 |
| `index.matrix_shape` | array | 1 | 0 |
| `index.question_embedding` | string | 1 | 0 |
| `index.text_chars` | integer | 1 | 0 |
| `index.unit_text` | string | 1 | 0 |
| `index.units` | integer | 1 | 0 |
| `index.units_sha256` | string | 1 | 0 |
| `inputs` | object | 1 | 0 |
| `inputs.corpus` | object | 1 | 0 |
| `inputs.corpus.n_files` | integer | 1 | 0 |
| `inputs.corpus.sha256` | string | 1 | 0 |
| `inputs.ids_sha256` | string | 1 | 0 |
| `inputs.questions_sha256` | string | 1 | 0 |
| `interpreter_model` | null | 1 | 1 |
| `lane` | object | 1 | 0 |
| `lane.cli_adds` | object | 1 | 0 |
| `lane.cli_adds.in_front_of_the_prompt` | string | 1 | 0 |
| `lane.cli_adds.seen_with` | string | 1 | 0 |
| `lane.cli_adds.system_prompt_first` | string | 1 | 0 |
| `lane.cli_version` | string | 1 | 0 |
| `lane.config_settings` | object | 1 | 0 |
| `lane.cwd` | string | 1 | 0 |
| `lane.env_per_call` | array | 1 | 0 |
| `lane.env_set` | object | 1 | 0 |
| `lane.exe` | string | 1 | 0 |
| `lane.fixed_flags` | array | 1 | 0 |
| `lane.login` | string | 1 | 0 |
| `lane.max_tries_default` | integer | 1 | 0 |
| `lane.per_call` | string | 1 | 0 |
| `lane.stdin` | string | 1 | 0 |
| `lane.system_prompt` | string | 1 | 0 |
| `legs` | array | 1 | 0 |
| `legs.aborted` | null | 1 | 1 |
| `legs.argv` | array | 1 | 0 |
| `legs.code_state` | object | 1 | 0 |
| `legs.code_state.diff_file` | string | 1 | 0 |
| `legs.code_state.diff_sha256` | null, string | 1 | 1 |
| `legs.code_state.status` | array, null | 1 | 1 |
| `legs.code_state.untracked_sha256` | object | 1 | 1 |
| `legs.code_version` | object | 1 | 0 |
| `legs.code_version.branch` | string | 1 | 0 |
| `legs.code_version.commit` | string | 1 | 0 |
| `legs.code_version.dirty` | boolean, null | 1 | 1 |
| `legs.embedder_load_s` | number | 1 | 0 |
| `legs.evaluator` | string | 1 | 0 |
| `legs.finished_at` | string | 1 | 0 |
| `legs.flags` | null | 1 | 1 |
| `legs.ids_file` | string | 1 | 0 |
| `legs.index` | object | 1 | 0 |
| `legs.index.cache_cost_note` | object | 1 | 0 |
| `legs.index.cache_file` | string | 1 | 0 |
| `legs.index.cache_file_bytes` | integer | 1 | 0 |
| `legs.index.cache_file_sha256` | string | 1 | 0 |
| `legs.index.embedder_warm_s` | number | 1 | 0 |
| `legs.index.matrix_bytes` | integer | 1 | 0 |
| `legs.index.matrix_dtype` | string | 1 | 0 |
| `legs.index.matrix_shape` | array | 1 | 0 |
| `legs.index.question_embedding` | string | 1 | 0 |
| `legs.index.text_chars` | integer | 1 | 0 |
| `legs.index.unit_text` | string | 1 | 0 |
| `legs.index.units` | integer | 1 | 0 |
| `legs.index.units_sha256` | string | 1 | 0 |
| `legs.lane` | object | 1 | 0 |
| `legs.lane.cli_adds` | object | 1 | 0 |
| `legs.lane.cli_adds.in_front_of_the_prompt` | string | 1 | 0 |
| `legs.lane.cli_adds.seen_with` | string | 1 | 0 |
| `legs.lane.cli_adds.system_prompt_first` | string | 1 | 0 |
| `legs.lane.cli_version` | string | 1 | 0 |
| `legs.lane.config_settings` | object | 1 | 0 |
| `legs.lane.cwd` | string | 1 | 0 |
| `legs.lane.env_per_call` | array | 1 | 0 |
| `legs.lane.env_set` | object | 1 | 0 |
| `legs.lane.exe` | string | 1 | 0 |
| `legs.lane.fixed_flags` | array | 1 | 0 |
| `legs.lane.login` | string | 1 | 0 |
| `legs.lane.max_tries_default` | integer | 1 | 0 |
| `legs.lane.per_call` | string | 1 | 0 |
| `legs.lane.stdin` | string | 1 | 0 |
| `legs.lane.system_prompt` | string | 1 | 0 |
| `legs.leg` | integer | 1 | 0 |
| `legs.n_answered` | integer | 1 | 0 |
| `legs.n_chosen` | integer | 1 | 0 |
| `legs.n_todo` | integer | 1 | 0 |
| `legs.n_unanswered_after` | integer | 1 | 0 |
| `legs.peak_memory_bytes` | integer | 1 | 0 |
| `legs.pid` | integer | 1 | 0 |
| `legs.prepare_s` | number | 1 | 0 |
| `legs.process_cpu_s` | number | 1 | 0 |
| `legs.python_executable` | string | 1 | 0 |
| `legs.retrieval_only` | boolean | 1 | 0 |
| `legs.started_at` | string | 1 | 0 |
| `legs.wall_s` | number | 1 | 0 |
| `legs.workers` | integer | 1 | 0 |
| `n_exhausted` | integer | 1 | 0 |
| `n_failed` | integer | 1 | 0 |
| `n_questions` | integer | 1 | 0 |
| `n_ran` | integer | 1 | 0 |
| `questions_file` | string | 1 | 0 |
| `retrieval_flags` | object | 1 | 0 |
| `retrieval_flags.HERB_BASELINE_METADATA` | boolean | 1 | 0 |
| `timestamp` | string | 1 | 0 |
| `top_k` | integer | 1 | 0 |
| `workers` | integer | 1 | 0 |

---
Written from `prod/harness/fields.py`, sha256 `ab7ca3537924b5c2d49c3a94c78e577d396b1ccac8dec1ae8194215985af050e`.

The files as they stood when this was written, their line ends as git holds them (LF):

- `arm_outputs.as_recorded.jsonl` sha256 `51b297b0a4fff313388a1f67bfd83043da0d66b7fd62b96bde9ba167c5e5fea9`
- `arm_outputs.jsonl` sha256 `4937afdf5b4d7e47803fc8f12451fdf40814c0c38364285c97aad97a8ad153be`
- `cli_transcript_usage.json` sha256 `6bd0d1f65ff278b3215ac2da72d1e09cffd09b6cdfa6690095a80d4ed2edb803`
- `code.acb4fb450f447926.diff` sha256 `acb4fb450f4479261d2bd5dd2c523c2ee90272df3795e2299c477c8b2c8a2ea9`
- `code_reflog.txt` sha256 `3afbde103bd3a20f21192f2128ed8a23ccd4dae9caa4683448649069ab195df5`
- `correct_code_version_from_reflog.py` sha256 `fa6dbcf7a2a2d8eb84900653a531b52b04d441fd8cfa1ce4dd37f3547f2b15e3`
- `correct_embed_gpu_time.py` sha256 `87b6b56b9f2194c78010b456ddc38135dbba349eff69e61c1a28e33500125123`
- `correct_judge_embed_gpu_time.py` sha256 `22823e15cb005f752c66af694f22e085e3081ca13bb30553de0945c2975fc64d`
- `correct_judge_usage.py` sha256 `233cb588a35ae1f957449e31bc163f3bf5138217b58ba7e90390f8c0c446a517`
- `correct_missing_judge_legs.py` sha256 `e8adbbbe26fed551172e08ae67d12df25490d0ef05585d445acabee4d6e8c71e`
- `correct_model_call_time.py` sha256 `f3e49a6b4fbfc779bba8d6793c98897415fbd7693202b2ff89f4e68771420a5c`
- `correct_nonllm_record_content.py` sha256 `22f302c2e645d3aecbf87ab8735b64b356695a43362ab1cad39ce406d6d59f75`
- `correct_search_time.py` sha256 `4002eb8c2826c46a2b52f634a169f207a2cfa37322d6db64c9517f745bee351d`
- `correct_zero_usage.py` sha256 `8f1cb37eec34d6b58c927e2098d3ce47bc603c6594227751e2ac01211f8b3c97`
- `corrections.json` sha256 `87fd04363a183a13a9d159f33de38d8aadc21071803a033791e0ba840671cfc5`
- `desktop_start_20261026T001551Z_eval_manifest.json` sha256 `6c75ecb95dd28dc01fe7e86c145df4263fe9892975f5788169722a9dae05e21c`
- `desktop_start_20261026T001551Z_FIELDS.md` sha256 `2b4ddb21e0db6fdb38e0a2cd10c6f5c44f1da86d1741e8784a3354a2676312ed`
- `desktop_start_20261026T001551Z_run_manifest.json` sha256 `5772125e2002848ff0870fafe89493592ce41a4d850040be2baa3cc9be477e23`
- `desktop_start_20261026T001551Z_sha256.txt` sha256 `5f8ed702f2262b4faca522f5985ad77f45938b9fc591b51115839a555eda33f1`
- `eval_calls.as_recorded.jsonl` sha256 `f2e5b9aae2aba418b5c7e04e09840323155afaee6ceecf58e8fcfa08c1530d18`
- `eval_calls.jsonl` sha256 `975b10c4e9cf8bd627f5e8ed3abde6a66e7195e05ec0f04404a4f8ed3ed43458`
- `eval_failures.jsonl` sha256 `695aa78b36c95732d50f62d3fc5579d69830d0c5542ee3a5200986865fa094ac`
- `eval_manifest.as_recorded.json` sha256 `cd3ede15ba4052ab14d2fbf8444a535af002ee817f4001629d372a7e6cfd797b`
- `eval_manifest.json` sha256 `55de5e521cbd1875460adf7f9bbcfe17b367013a45748733a013642610a9c938`
- `eval_results.as_recorded.jsonl` sha256 `c9200739e3245fdd0cd14104035f96d3cc99235fb2213da0999541f3e89f21b2`
- `eval_results.jsonl` sha256 `fdf04ecfb6874d6707c3160d81585a54f57084835c15b3f5301dac54cefb7b5b`
- `failures.jsonl` sha256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `gpu_embed_times_all.json` sha256 `db24c3d8fa2102717683be8dede03a2b04e863cfb82705a35817336693c5bac2`
- `judge_embed_gpu_times.json` sha256 `72aa41ffeb48a6228a901c06cbb90094fcdad07911147faef29efb1d1b1c9267`
- `model_call_times.json` sha256 `8c3d8f5782121961fa4015153091425ca09b88a6741257df8ce6d00e0ef6dfcb`
- `run_manifest.as_recorded.json` sha256 `0d12385a20b96bc564b83fee935563e07651f9295f108073f3491c75aa951b6d`
- `run_manifest.json` sha256 `b7782a78827d3eda1e5ca7d74f81ebffacdadf71fae96e7d82789afaef76cd1c`
