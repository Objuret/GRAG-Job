# What is in this folder, and what every field means

One run of one retrieval method, **vector**, over 100 questions: for each question the texts the method delivered, one answer written from them, and the scores of that answer and of what was delivered. Each answer was written once and judged once.

- Answers by `claude-sonnet-5`, judged by `claude-haiku-4-5-20251001`.
- Code: commit `fbc2f22c38238562599c683a0523b25e2f7e0221`; code paths that differed from it: 0.
- Starts of this folder: 1, the first at 2026-10-17T06:14:38.953732+00:00.

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

Times are seconds (`_s`) or UTC stamps (`_at`). Sizes are tokens, characters (`chars`) or bytes. Scores run from 0 to 1 and higher is more.

## The scores

The scores are computed by RAGAS. The quoted sentence of each is RAGAS's own, from the place named; "Here" says what goes into it in this folder.

| `metric` | What it measures | Needs | Between arms |
|---|---|---|---|
| `context_recall_id` | "Calculates context recall by directly comparing retrieved context IDs with reference context IDs. The score represents what proportion of the reference IDs were successfully retrieved." (RAGAS, class IDBasedContextRecall) Here: context_ids against the ids of the question's gold records. | nothing | yes |
| `context_precision_id` | "Calculates context precision by directly comparing retrieved context IDs with reference context IDs. The score represents what proportion of the retrieved context IDs are actually relevant (present in reference)." (RAGAS, class IDBasedContextPrecision) Here: context_ids against the ids of the question's gold records. | nothing | no, within one arm only |
| `context_recall_nonllm` | "`NonLLMContextRecall` metric is computed using `retrieved_contexts` and `reference_contexts` [...] This metrics uses non-LLM string comparison metrics to identify if a retrieved context is relevant or not." (RAGAS, docs, context_recall.md) Here: contexts against the text of each gold record; a gold record counts as found when a delivered text is more than 0.5 like it (Levenshtein). | nothing | no, within one arm only |
| `context_precision_nonllm` | "To determine if a retrieved context is relevant, this method compares each retrieved context or chunk in `retrieved_contexts` with every context in `reference_contexts` using a non-LLM-based similarity measure." (RAGAS, docs, context_precision.md) Here: each delivered text against the gold records' texts, more than 0.5 alike (Levenshtein), weighted by rank. | nothing | no, within one arm only |
| `context_recall_llm` | "Estimates context recall by estimating TP and FN using annotated answer and retrieved context." (RAGAS, class LLMContextRecall) Here: the gold answer, sentence by sentence, against contexts. | the judge | yes |
| `faithfulness` | "The **Faithfulness** metric measures how factually consistent a `response` is with the `retrieved context`. [...] A response is considered **faithful** if all its claims can be supported by the retrieved context." (RAGAS, docs, faithfulness.md) Here: the answer's claims against contexts. | the judge | yes |
| `answer_correctness` | "Measures answer correctness compared to ground truth as a combination of factuality and semantic similarity." (RAGAS, class AnswerCorrectness) Here: the answer against the gold answer: 0.75 times the F1 of the claims the judge finds in both, plus 0.25 times semantic_similarity (RAGAS's own weights). | the judge and the embedder | yes |
| `semantic_similarity` | "The **Semantic Similarity** metric evaluates the semantic resemblance between a generated response and a reference (ground truth) answer. [...] This metric uses embeddings and cosine similarity" (RAGAS, docs, semantic_similarity.md) Here: the answer against the gold answer, both embedded in passage mode. | the embedder | yes |
| `string_similarity` | "`NonLLMStringSimilarity` metric measures the similarity between the reference and the response using traditional string distance measures such as Levenshtein, Hamming, and Jaro." (RAGAS, docs, traditional.md) Here: the answer against the gold answer, Levenshtein. | nothing | yes |
| `bleu` | "It measures the similarity between the response and the reference based on n-gram precision and brevity penalty." (RAGAS, docs, traditional.md) Here: the answer against the gold answer. | nothing | yes |
| `rouge` | "It measures the overlap between the generated `response` and the `reference` text based on n-gram recall, precision, and F1 score." (RAGAS, docs, traditional.md) Here: the answer against the gold answer: rougeL, F measure. | nothing | yes |
| `chrf` | "The `CHRFScore` metric evaluates the similarity between a `response` and a `reference` using **character n-gram F-score**." (RAGAS, docs, traditional.md) Here: the answer against the gold answer. | nothing | yes |
| `exact_match` | "The `ExactMatch` metric checks if the response is exactly the same as the reference text." (RAGAS, docs, traditional.md) Here: the answer against the gold answer. | nothing | yes |
| `string_presence` | "The `StringPresence` metric checks if the response contains the reference text." (RAGAS, docs, traditional.md) Here: the answer against the gold answer. | nothing | yes |

"No, within one arm only": the score is counted per delivered unit, and arms deliver units of different size (one record, or a chunk of several records), so the same delivered records give different values.

No stored score is called a hit rate. Whether a question got any gold record at all can be read from `context_recall_id` being above 0.

## Easy to read wrongly

- `top_k` in the manifest is not used by a run with a character budget.
- `generator.payload` is what the harness asked for. `applied` and `not_applied` are what a call carried.
- `calls` counts answers, `attempts` counts tries. `tokens_in` and `tokens_out` are those of the try that answered; a try that did not answer is in the call's own record under `attempts`.
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
| `search_time_s` | Seconds the arm took to rank the corpus for this question, without any model call it made on the way. |
| `generator` | What the answer call cost. Its fields: see "What a model's work cost" below. |
| `retrieval` | What the arm's own model calls for this question cost, such as embedding the question. All zero for an arm that makes none. Its fields: see "What a model's work cost" below. |
| `leg` | Which start of this folder made the row: 1 for the first start, one more for each time the run was taken up again. The start is in run_manifest.json under legs. |
| `timing` | The clock of the whole question: ranking and answering. Its fields: see "A clock" below. |
| `calls` | Every model call and every embedder request the question made, whole. Its fields: see "A call record" below. |
| `correction` | Only where a stored number was corrected after the run: the rule, the value as recorded and the corrected value. The folder's corrections.json tells the whole of it, and the files as recorded stand beside the corrected ones. |
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
| `type` | The question's kind in the benchmark. |
| `score` | The score the call was made for. |
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
| `build_stats.build_time_s` | Seconds it took. For an index read from a stored file it is what the making of that file took. |
| `build_stats.model` | What the model that built it cost. Its fields: see "What a model's work cost" below. |
| `build_stats.models` | The models used to build it, by name. |
| `flags` | The switches given on the command line, each by its name with the value it was given; empty when none. What a switch does is the arm's to say (retrieval_flags). |
| `graph` | For an arm that reads the graph database: which database and which build of it. Empty for an arm that reads none. |
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
| `legs.correction` | Only where a stored number was corrected after the run: the rule, the value as recorded and the corrected value. The folder's corrections.json tells the whole of it, and the files as recorded stand beside the corrected ones. |
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
| `flags` | The arguments the program was started with, without the system text and the schema. |
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
| `not_applied` | What the caller asked for and the call could not carry, each with the reason. |
| `payload_dropped` | The names of the settings in not_applied. |
| `attempts` | Every try of the call, in order. |
| `attempts.n` | The try's number within the call, from 1. |
| `attempts.started_at` | When the try started (UTC). |
| `attempts.seconds` | How long the try took. |
| `attempts.outcome` | ok (it answered), exit (the program ended with an error), bad_envelope (its reply could not be read), or timeout (cut at timeout_s). |
| `attempts.returncode` | The program's exit code; empty for a timeout. |
| `attempts.error` | The error of a try that did not answer. |
| `attempts.stdout` | What the program printed, kept for a try that did not answer. |
| `attempts.stderr` | What the program printed as errors, kept for a try that did not answer. |
| `attempts.backoff_s` | The pause after a try that did not answer, before the next one. |
| `attempts.machine_asleep` | Only where a correction marked the try: the machine slept under it. See corrections.json. |
| `ok` | Whether the call ended with an answer. |
| `text` | The reply's text. For an answer call it is the JSON that holds the answer. |
| `usage` | The tokens of the try that answered. |
| `usage.prompt_tokens` | Tokens sent: fresh input, plus what was written to the prompt cache, plus what was read from it. |
| `usage.completion_tokens` | Tokens the model wrote. |
| `usage.cached_input_tokens` | The part of prompt_tokens read from the prompt cache. |
| `envelope` | The Claude program's whole reply as it printed it: its own times (duration_ms for the whole program run, duration_api_ms for the time spent with the model, ttft_ms until the first token), its own token counts, the models it used, its session id, how many turns it took. |
| `stream` | The raw stream of a reply joined from parts; empty otherwise. |
| `stderr` | What the program printed as errors in the try that answered. |
| `error` | The last error of a call that gave up; empty otherwise. |

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
| `untracked_sha256` | The sha256 of each code file git did not know. |

### How model calls were made

| Field | What it holds |
|---|---|
| `exe` | The Claude program used for every model call. |
| `cli_version` | Its version. |
| `cwd` | The folder it is started in. |
| `fixed_flags` | The arguments every call is started with. |
| `system_prompt` | How the system text is passed. |
| `stdin` | How the prompt is handed over. |
| `env_set` | The environment variables set on every call, by name. |
| `login` | How the program logs in. |
| `config_settings` | The settings file the harness puts in the program's own config folder. |
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
| `ragas_run_config` | RAGAS's own run settings as handed to it. |
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
| `cache_cost_note` | What making those vectors cost and on which machine, as noted beside the stored file when it was made. |
| `embedder_warm_s` | Seconds the embedder took for one empty request before the first question, so that no question pays for its loading. |
| `question_embedding` | When and how a question is embedded. |

## Fields without a word

None: every file and every field of this folder is described above.

---
Written from `prod/harness/fields.py`, sha256 `a9453fa46cb7ddf8a6289eee230dfaefeed38d395074143854e5c1b322b3ddae`.

The files as they stood when this was written:

- `arm_outputs.jsonl` sha256 `db8cfadf7b6a83b63bc95f52a8c00d48cb8163370f1a031a46d7a53ff5ff2afe`
- `eval_calls.jsonl` sha256 `f9636998f7961d8ef3a05c4c88a06cfddbc5bfb36b958125dca3c1f234f0c534`
- `eval_failures.jsonl` sha256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `eval_manifest.json` sha256 `3a66e386c6e27463105d717ed8740fc752a259e3e8e17abd964d95fb03b4d069`
- `eval_results.jsonl` sha256 `27f873274481f6e983c2659d622a6d5f6cb69fbf4d12a65252b20d4a3bbebdf7`
- `failures.jsonl` sha256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `run_manifest.json` sha256 `c4fe3e2e0850a221e6f0fe1bcf8d327bc966e95789021ccb44f5e9281246a520`
