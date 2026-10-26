# What is in this folder, and what every field means

**This folder holds the questions and, inside the judge's prompts, the gold answers.** It must not be given to a model or an agent that works on the retrieval method, and it is not for a public repository.

## The files and how they join

| File | What it is | Joins by |
|---|---|---|
| `FIELDS.md` | This file. |  |
| `arm_outputs.jsonl` | One line per question: what was delivered, the answer, and everything the question cost. | id |
| `eval_results.jsonl` | One line per question and score: the score. | question_id = the id of arm_outputs.jsonl; metric |
| `eval_calls.jsonl` | One line per judge call and per embedder request of the scoring, whole. The judge's prompts hold the gold answers. | question_id + score = one line of eval_results.jsonl |
| `eval_manifest.json` | What the scoring was: the judge, its settings, and what it cost. | judge_legs[].settings.started_at = the eval_leg of a score row |
| `eval_failures.jsonl` | One line per score cell that failed. Empty when none did. | question_id + metric |
| `corrections.json` | Only in a folder whose stored numbers were corrected after the run: what was changed, by which rule, on whose word. |  |
| `eval_manifest.as_recorded.json` | eval_manifest.json exactly as the scoring wrote it, kept by the first correction that changed it (corrections.json names it). |  |
| `eval_results.as_recorded.jsonl` | eval_results.jsonl exactly as the scoring wrote it, kept by the first correction that changed it (corrections.json names it). |  |
| `correct_missing_judge_legs.py` | The script that made the missing-judge-legs correction (an entry in judge_legs for each scoring start that wrote none, built from its records in eval_calls.jsonl, and judge_usage as the sum of the entries); run on the files from before it, it gives the corrected files again. |  |
| `correct_nonllm_record_content.py` | The script that made the non-LLM record-content correction (context_recall_nonllm and context_precision_nonllm calculated again, record content against record content); run on the files from before it, with the code named in its entry, it gives the corrected files again. |  |

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

- The questions: every run answers the 100 questions of data/gold100.jsonl (inputs.ids_sha256). How these 100 were chosen from the benchmark's questions: no rule in his words is recorded. The set was first added on 2026-05-19 (commit 0b98b12, "Scale gold set to n=100 (balanced) + statistically robust result"); his messages from 2026-05-15 to 2026-05-27 are not in the canon, because that work was done in Cursor.
- The directory files: the corpus's three directory files (people, teams, customers) are not indexed beside the product records (retrieval_flags.HERB_BASELINE_METADATA off). No rule in his words is recorded.

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
| `meta.ranking.n_ranked` | How many of them scored above zero for this question. Only those are ranked; a unit that shares no word with the question is never delivered. |
| `meta.ranking.scores` | The BM25 score of each delivered text, in delivered order. A BM25 score has no upper bound; a higher score is a closer match to the question's words. |
| `meta.ranking.next_score` | The BM25 score of the first unit that was not delivered, on the same scale; empty when none was left. |
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
| `method` | The BM25 variant. |
| `k1` | BM25's k1. |
| `b` | BM25's b. |
| `bm25_parameters` | Where k1 and b are from. |
| `stopwords` | The stop word list. |
| `stemmer` | The stemmer. |
| `bm25s` | The version of the BM25 library. |
| `PyStemmer` | The version of the stemmer. |
| `kept` | Where the index lives. |

## Fields without a word

None: every file and every field of this folder is described above.

## The fields as they stand in this folder

Counted from the files themselves when this was written. A record is a line of a .jsonl file, or the whole of a .json file. Empty is null, an empty text, an empty list or an empty object; the field's words say when and why it is empty.

### `arm_outputs.jsonl` (100 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `answer` | string | 100 | 0 |
| `answered_at` | string | 100 | 0 |
| `calls` | array | 100 | 0 |
| `calls.applied` | object | 100 | 0 |
| `calls.attempts` | array | 100 | 0 |
| `calls.attempts.backoff_s` | number | 2 | 0 |
| `calls.attempts.error` | null, string | 100 | 100 |
| `calls.attempts.machine_asleep` | boolean | 2 | 0 |
| `calls.attempts.n` | integer | 100 | 0 |
| `calls.attempts.outcome` | string | 100 | 0 |
| `calls.attempts.returncode` | integer, null | 100 | 2 |
| `calls.attempts.seconds` | number | 100 | 0 |
| `calls.attempts.started_at` | string | 100 | 0 |
| `calls.attempts.stderr` | null, string | 100 | 100 |
| `calls.attempts.stdout` | null, string | 100 | 100 |
| `calls.cwd` | string | 100 | 0 |
| `calls.effort` | null | 100 | 100 |
| `calls.env_set` | object | 100 | 0 |
| `calls.env_unset` | array | 100 | 0 |
| `calls.envelope` | object | 100 | 0 |
| `calls.error` | null | 100 | 100 |
| `calls.exe` | string | 100 | 0 |
| `calls.finished_at` | string | 100 | 0 |
| `calls.flags` | array | 100 | 0 |
| `calls.join_parts` | boolean | 100 | 0 |
| `calls.kind` | string | 100 | 0 |
| `calls.max_tries` | integer | 100 | 0 |
| `calls.model` | string | 100 | 0 |
| `calls.not_applied` | object | 100 | 0 |
| `calls.ok` | boolean | 100 | 0 |
| `calls.payload_dropped` | array | 100 | 0 |
| `calls.prompt` | string | 100 | 0 |
| `calls.role` | string | 100 | 0 |
| `calls.schema` | object | 100 | 0 |
| `calls.seq` | integer | 100 | 0 |
| `calls.started_at` | string | 100 | 0 |
| `calls.stderr` | string | 100 | 100 |
| `calls.stream` | null | 100 | 100 |
| `calls.system` | string | 100 | 0 |
| `calls.text` | string | 100 | 0 |
| `calls.timeout_s` | number | 100 | 0 |
| `calls.usage` | object | 100 | 0 |
| `calls.usage.cached_input_tokens` | integer | 100 | 0 |
| `calls.usage.completion_tokens` | integer | 100 | 0 |
| `calls.usage.prompt_tokens` | integer | 100 | 0 |
| `context_ids` | array | 100 | 0 |
| `contexts` | array | 100 | 0 |
| `correction` | object | 2 | 0 |
| `generator` | object | 100 | 0 |
| `generator.attempts` | integer | 100 | 0 |
| `generator.cached_input_tokens` | integer | 100 | 0 |
| `generator.calls` | integer | 100 | 0 |
| `generator.reasoning_tokens` | integer | 100 | 0 |
| `generator.request_s` | number | 100 | 0 |
| `generator.retry_s` | number | 100 | 0 |
| `generator.time_s` | number | 100 | 0 |
| `generator.tokens_in` | integer | 100 | 0 |
| `generator.tokens_out` | integer | 100 | 0 |
| `generator.wait_s` | number | 100 | 0 |
| `id` | string | 100 | 0 |
| `leg` | integer | 100 | 0 |
| `meta` | object | 100 | 0 |
| `meta.char_budget` | object | 100 | 0 |
| `meta.char_budget.boundary` | object | 100 | 0 |
| `meta.char_budget.boundary.chars_full` | integer | 100 | 0 |
| `meta.char_budget.boundary.chars_kept` | integer | 100 | 0 |
| `meta.char_budget.boundary.id` | string | 100 | 0 |
| `meta.char_budget.budget` | integer | 100 | 0 |
| `meta.char_budget.chars` | integer | 100 | 0 |
| `meta.char_budget.exhausted` | boolean | 100 | 0 |
| `meta.char_budget.kept` | integer | 100 | 0 |
| `meta.ranking` | object | 100 | 0 |
| `meta.ranking.n_ranked` | integer | 100 | 0 |
| `meta.ranking.n_units` | integer | 100 | 0 |
| `meta.ranking.next_score` | number | 100 | 0 |
| `meta.ranking.scores` | array | 100 | 0 |
| `question` | string | 100 | 0 |
| `retrieval` | array | 100 | 100 |
| `search_time_s` | number | 100 | 0 |
| `timing` | object | 100 | 0 |
| `timing.finished_at` | string | 100 | 0 |
| `timing.started_at` | string | 100 | 0 |
| `timing.thread` | string | 100 | 0 |
| `timing.wall_s` | number | 100 | 0 |

### `corrections.json` (1 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `corrections` | array | 1 | 0 |
| `corrections.before` | object | 1 | 0 |
| `corrections.changes` | array | 1 | 0 |
| `corrections.checks` | array | 1 | 0 |
| `corrections.code` | object | 1 | 0 |
| `corrections.files` | object | 1 | 0 |
| `corrections.made_at` | string | 1 | 0 |
| `corrections.not_changed_and_worth_knowing` | array | 1 | 0 |
| `corrections.ordered_by` | string | 1 | 0 |
| `corrections.rule` | object | 1 | 0 |
| `corrections.script` | string | 1 | 0 |
| `corrections.what_happened` | string | 1 | 0 |

### `eval_calls.jsonl` (606 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `applied` | object | 606 | 0 |
| `arm` | string | 606 | 0 |
| `attempts` | array | 606 | 0 |
| `attempts.error` | null, string | 606 | 603 |
| `attempts.n` | integer | 606 | 0 |
| `attempts.outcome` | string | 606 | 0 |
| `attempts.returncode` | integer, null | 606 | 3 |
| `attempts.seconds` | number | 606 | 0 |
| `attempts.started_at` | string | 606 | 0 |
| `attempts.stderr` | null, string | 606 | 606 |
| `attempts.stdout` | null, string | 606 | 605 |
| `cwd` | string | 606 | 0 |
| `effort` | null | 606 | 606 |
| `env_set` | object | 606 | 0 |
| `env_unset` | array | 606 | 0 |
| `envelope` | null, object | 606 | 3 |
| `error` | null, string | 606 | 603 |
| `eval_leg` | string | 606 | 0 |
| `exe` | string | 606 | 0 |
| `finished_at` | string | 606 | 0 |
| `flags` | array | 606 | 0 |
| `join_parts` | boolean | 606 | 0 |
| `kind` | string | 606 | 0 |
| `max_tries` | integer | 606 | 0 |
| `model` | string | 606 | 0 |
| `not_applied` | object | 606 | 606 |
| `ok` | boolean | 606 | 0 |
| `payload_dropped` | array | 606 | 606 |
| `phase` | string | 606 | 0 |
| `prompt` | string | 606 | 0 |
| `question_id` | string | 606 | 0 |
| `schema` | null | 606 | 606 |
| `score` | string | 606 | 0 |
| `seq` | integer | 606 | 0 |
| `started_at` | string | 606 | 0 |
| `stderr` | null, string | 606 | 606 |
| `stream` | null | 606 | 606 |
| `system` | string | 606 | 606 |
| `text` | null, string | 606 | 3 |
| `timeout_s` | number | 606 | 0 |
| `type` | string | 606 | 0 |
| `usage` | null, object | 606 | 3 |
| `usage.cached_input_tokens` | integer | 603 | 0 |
| `usage.completion_tokens` | integer | 603 | 0 |
| `usage.prompt_tokens` | integer | 603 | 0 |

### `eval_failures.jsonl` (3 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `error` | string | 3 | 0 |
| `eval_leg` | string | 3 | 0 |
| `failed_at` | string | 3 | 0 |
| `metric` | string | 3 | 0 |
| `question_id` | string | 3 | 0 |
| `usage` | object | 3 | 0 |
| `usage.cached_input_tokens` | integer | 3 | 0 |
| `usage.chat_attempts` | integer | 3 | 0 |
| `usage.chat_calls` | integer | 3 | 0 |
| `usage.chat_s` | number | 3 | 0 |
| `usage.embed_calls` | integer | 3 | 0 |
| `usage.embed_s` | number | 3 | 0 |
| `usage.embed_texts` | integer | 3 | 0 |
| `usage.embed_tokens` | integer | 3 | 0 |
| `usage.eval_leg` | string | 3 | 0 |
| `usage.finished_at` | string | 3 | 0 |
| `usage.started_at` | string | 3 | 0 |
| `usage.thread` | string | 3 | 0 |
| `usage.tokens_in` | integer | 3 | 0 |
| `usage.tokens_out` | integer | 3 | 0 |
| `usage.wall_s` | number | 3 | 0 |

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
| `judge_legs.judge_model` | string | 1 | 0 |
| `judge_legs.settings` | object | 1 | 0 |
| `judge_legs.settings.embedding` | object | 1 | 0 |
| `judge_legs.settings.embedding.encode_s` | integer | 1 | 0 |
| `judge_legs.settings.embedding.lock_wait_s` | integer | 1 | 0 |
| `judge_legs.settings.embedding.requests` | integer | 1 | 0 |
| `judge_legs.settings.embedding.texts` | integer | 1 | 0 |
| `judge_legs.settings.embedding.tokens_in` | integer | 1 | 0 |
| `judge_legs.settings.finished_at` | null | 1 | 1 |
| `judge_legs.settings.interrupted` | string | 1 | 0 |
| `judge_legs.settings.started_at` | string | 1 | 0 |
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
| `judge_settings` | null | 1 | 1 |
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

### `eval_results.jsonl` (1600 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `arm` | string | 1600 | 0 |
| `components` | object | 1600 | 0 |
| `components.usage` | object | 1600 | 0 |
| `components.usage.cached_input_tokens` | integer | 1600 | 0 |
| `components.usage.chat_attempts` | integer | 1600 | 0 |
| `components.usage.chat_calls` | integer | 1600 | 0 |
| `components.usage.chat_s` | number | 1600 | 0 |
| `components.usage.embed_calls` | integer | 1600 | 0 |
| `components.usage.embed_s` | number | 1600 | 0 |
| `components.usage.embed_texts` | integer | 1600 | 0 |
| `components.usage.embed_tokens` | integer | 1600 | 0 |
| `components.usage.eval_leg` | string | 1600 | 0 |
| `components.usage.finished_at` | string | 1600 | 0 |
| `components.usage.started_at` | string | 1600 | 0 |
| `components.usage.thread` | string | 1600 | 0 |
| `components.usage.tokens_in` | integer | 1600 | 0 |
| `components.usage.tokens_out` | integer | 1600 | 0 |
| `components.usage.wall_s` | number | 1600 | 0 |
| `human_label` | null | 1600 | 1600 |
| `metric` | string | 1600 | 0 |
| `question_id` | string | 1600 | 0 |
| `status` | string | 1600 | 0 |
| `type` | string | 1600 | 0 |
| `value` | number | 1600 | 0 |

---
Written from `prod/harness/fields.py`, sha256 `bd121e0a2cb46d6c89216b24d24db0e97fe15fba3a887562d427a38bfaf3360d`.

The files as they stood when this was written, their line ends as git holds them (LF):

- `arm_outputs.jsonl` sha256 `ec7a7c427294692bdd9a0aa3f5ddca97d62100400a060d642c49cf451a77060d`
- `correct_missing_judge_legs.py` sha256 `e8adbbbe26fed551172e08ae67d12df25490d0ef05585d445acabee4d6e8c71e`
- `correct_nonllm_record_content.py` sha256 `f915dd944ce45f6b5927efc63e4fa0edd73af4be036e20f304c0180aea64877a`
- `corrections.json` sha256 `5cb52f78a34aedf453907d35442ebc3266911758a6d6e86678f87f7a2e9cf0e3`
- `eval_calls.jsonl` sha256 `9e53a1c2ca4821f01df76d6b14aad98daa47cc7da1370d655280ad5f705d45fa`
- `eval_failures.jsonl` sha256 `3d9a427a577a09f03302e2f5a912a5ecac2c3d710db92ecf022a1aed6c395efd`
- `eval_manifest.as_recorded.json` sha256 `0ff4d2e8666901d6b2c74b970bbf02049f59b82b37d29bd22169a6265ef74d26`
- `eval_manifest.json` sha256 `50f2ccd28d251fd12e9a03e383ea3622be793f2e25346e9c4cdc274924363e4d`
- `eval_results.as_recorded.jsonl` sha256 `30b7ed46e1adcf98a0449f9b10c5ec98ea182c53e11a90faef9e3f1e07639da6`
- `eval_results.jsonl` sha256 `56686501bb00732796584a52a30cc85191f09e7771f515d093ae3023ccc6a5b2`
