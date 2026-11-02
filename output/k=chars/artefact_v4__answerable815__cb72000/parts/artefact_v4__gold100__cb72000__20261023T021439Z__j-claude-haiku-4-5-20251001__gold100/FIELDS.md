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
| `factual_correctness` | "It uses claim decomposition and natural language inference (NLI) to verify the claims made in the responses against reference texts." (RAGAS, class FactualCorrectness) Here: the answer against the gold answer: the F1 of precision TP / (TP + FP) and recall TP / (TP + FN), where TP and FP are the answer's claims that the judge finds and does not find in the gold answer, and FN the gold answer's claims that it does not find in the answer (RAGAS's defaults: mode f1, beta 1, atomicity and coverage low), rounded to two decimals. | the judge | yes |
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
- The graph: the 974 chunks of the benchmark's question, unanswerable-question and product-profile sections were dropped from the graph on 2026-05-19 (5,843 chunks made, 4,869 kept). No rule in his words is recorded; his messages of those days are not in the canon.
- The pool: the 61 chunks of the three metadata files (employee.json, salesforce_team.json, customers_data.json) are out of the pool (4,869 chunks in the graph, 4,808 in the pool). His words: "eh.. vector and lucene sure as fuck shoulw never use the artefact or the graph DB, and there is a fucking reason thoes 3 files or off for the artefact" (2026-09-13T01:00:57Z) · "just dont use those chunks, ffs, and yeah, i did ask for their fucking removal a million times but whatever" (2026-09-13T01:10:35Z).
- The tags: 4,111 tags and their 5,470 edges were removed from the graph copy herb-eval-v2 on 2026-08-12 (output/graph_build/herb-eval-v2/step_cleanup.json, with its predicate). His words: "ok, so, lets do this then, draft a new design based on these thoughts and herb-eval, including removing the pr-titles and url's" (2026-08-12T19:14:05Z) · "well then, if you feel this is the way, construct another db using this, aka use the current as template and "fix it" and add these things, right?" (2026-08-12T19:52:05Z). Which tags fall in the removed classes is the agent's rule, written in the predicate.

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
| `meta` | What the arm recorded about this question's retrieval. |
| `meta.provenance` | The graph the retrieval asked, checked and counted once when the run started. Every question asks the graph for its own chunks, tags and closeness; nothing here is what a question was ordered from. |
| `meta.provenance.database` | The graph database that was read. |
| `meta.provenance.run_id` | The run of tag-to-chunk edges read from it. |
| `meta.provenance.corpus_argument` | The corpus the harness named when it started the arm. The arm reads the graph, not that corpus. |
| `meta.provenance.interpreter_model` | The model of the first call. |
| `meta.provenance.facet_layer` | The graph's FacetLayer node as it stood: what the facet values on the tag-to-chunk edges were made from: its name and run, the four facets with their retrain flip gaps (equal_gap) and the pooled one (pooled_flip_gap), on the scale of the facet values on the edges and read from the bootstrap's BANDS.md (the columns named), how many refits the values are the mean of, how many edges carry them, when it was written, and the sha256 of its source files. |
| `meta.provenance.topic_on_the_edge_against_the_vectors_max_abs` | The largest difference, over the edges, between the topic value on the edge and the cosine of the tag's vector and the chunk description's vector. |
| `meta.provenance.counts` | What the graph held, counted in it. |
| `meta.provenance.counts.chunks` | Chunks in the pool. |
| `meta.provenance.counts.graph_tags` | Tags that sit on a chunk of the pool. |
| `meta.provenance.counts.edges` | Tag-to-chunk edges into the pool. |
| `meta.provenance.counts.products` | Products. |
| `meta.provenance.counts.eligible_graph_tags` | Tags that are not a product's name; only those are compared with the query tags. |
| `meta.provenance.counts.eligible_edges` | Edges that carry such a tag. |
| `meta.provenance.counts.product_named_tags` | Tags that are a product's name and are never compared. |
| `meta.provenance.counts.chunks_with_an_eligible_edge` | Chunks of the pool that carry an eligible tag. |
| `meta.provenance.counts.named_structure_nodes` | Per kind of structure node (Product, Channel, Employee, Customer, Company), how many carry name_keys the question is matched against. |
| `meta.provenance.counts.customer_chunk_edges` | Edges from a customer to a chunk whose records carry the customer's id. |
| `meta.provenance.counts.chunks_with_a_time` | Chunks of the pool that carry their records' own times in the graph (times). |
| `meta.provenance.counts.channels_apart` | Only in runs before 2026-10-23 (commit 751a72d): channels the graph's people set apart: a channel with employees none of whom is tied to another channel or to a meeting of its product. |
| `meta.provenance.counts.people` | Only in runs before 2026-10-23 (commit 751a72d): employees tied to a product's channel that is not apart or to its meetings, counted once a product. |
| `meta.provenance.source_sha256` | The sha256 of each code file the retrieval ran from, by path, its line ends as git holds them (LF), so that it is the sha256 of the commit's file whatever the checkout wrote. |
| `meta.interpreter` | The first call and what was embedded for the query side. |
| `meta.interpreter.model` | The model of the first call. |
| `meta.interpreter.stages` | One entry a model call of the query side. |
| `meta.interpreter.stages.stage` | Which call: querytag is the first call. |
| `meta.interpreter.stages.cache_hit` | Whether its answer was read from the cache instead of asked. |
| `meta.interpreter.stages.key` | The cache key: the sha256 of the call's instruction, message, schema and model. |
| `meta.interpreter.stages.asks` | How many times the start that wrote this row tried the call; a read from the cache counts as one. A try of an earlier start that failed or was cut off is kept in the store, in querytag/failed/ under the same key. |
| `meta.interpreter.stages.offline` | Whether the run refused to ask the model. |
| `meta.interpreter.stages.duplicate_tags_dropped` | How many tags of the answer were left out because the same phrase stood there twice. |
| `meta.interpreter.description_side_tags` | How many query tags the first call wrote from the content it described. |
| `meta.interpreter.question_side_tags` | How many it wrote from the question's own words. |
| `meta.interpreter.embeddings` | What was embedded, each in the query role. |
| `meta.interpreter.embeddings.description_side_tags` | The description and the tags written from it. |
| `meta.interpreter.embeddings.description_side_tags.tags` | How many tags. |
| `meta.interpreter.embeddings.description_side_tags.text_chars` | The description's length in characters. |
| `meta.interpreter.embeddings.description_side_tags.embedding` | The sha256 of the vectors. |
| `meta.interpreter.embeddings.question` | The question as asked. |
| `meta.interpreter.embeddings.question.text_chars` | Its length in characters. |
| `meta.interpreter.embeddings.question.embedding` | The sha256 of its vector. |
| `meta.interpreter.embeddings.question_side_tags` | The tags written from the question's own words. |
| `meta.interpreter.embeddings.question_side_tags.tags` | How many tags. |
| `meta.interpreter.embeddings.question_side_tags.embedding` | The sha256 of the vectors. |
| `meta.interpreter.embeddings.question_without_the_names` | The question with the names that made the border taken out, each replaced by "the" and the word for its kind (product, channel, person, customer, company). The chunk side is compared with this. |
| `meta.interpreter.embeddings.question_without_the_names.text_chars` | Its length in characters. |
| `meta.interpreter.embeddings.question_without_the_names.embedding` | The sha256 of its vector. |
| `meta.scope` | The border, and the scope inside it. |
| `meta.scope.names_in_the_question` | One entry a structure name that stands in the question word for word. |
| `meta.scope.names_in_the_question.name` | The name as the graph holds it (for a match on an id, the name of the node the id belongs to). |
| `meta.scope.names_in_the_question.key` | The plain form that was matched: lower case, everything but letters and digits one space. |
| `meta.scope.names_in_the_question.labels` | The kinds of node that carry it. |
| `meta.scope.names_in_the_question.nodes` | How many nodes carry it (one name several employees share is one name). |
| `meta.scope.names_in_the_question.chunks` | Pool chunks of the scope those nodes pick: a product's or a channel's chunks; for a person, a customer or a company, every chunk under the parents of the chunks it is tied to. |
| `meta.scope.names_in_the_question.set_aside` | Whether it was left out of the border because its kind would have left nothing. |
| `meta.scope.nothing_cut` | Whether no name made a border, so every chunk stayed in the pool. |
| `meta.scope.chunks_under_the_names` | Chunks inside the border. |
| `meta.scope.chunks_kept` | Chunks the order was made of. |
| `meta.scope.chunks_cut` | Chunks left out of the pool by the border. |
| `meta.scope.delivered_under_the_names` | How many of the delivered chunks lie inside the border. |
| `meta.scope.combo` | The two clouds and the scope gauged from them. A side's cloud is the chunks before the knee of its closeness sorted from the nearest, as many as the closeness shows. |
| `meta.scope.combo.chunks` | Chunks of the border. |
| `meta.scope.combo.clouds` | Chunks in each side's cloud. |
| `meta.scope.combo.clouds.tags` | Of the chunks' closeness through their tags, as many as its knee gives, taken by level moved by the facets. |
| `meta.scope.combo.clouds.description` | Of the chunk descriptions' closeness to the question without the names. |
| `meta.scope.combo.chunks_on_each_step` | How many chunks stand on each step: 2 in both clouds, 3 in one, 4 in neither. |
| `meta.scope.combo.scope_gauged_from_chunks` | How many chunks the scope was gauged from: those in a cloud. |
| `meta.scope.combo.scopes_taken` | The parents that hold the majority of those chunks. A parent is a channel, a product's whole documents, transcripts, pull requests, links or chats, or the parts of one document or one transcript. |
| `meta.scope.combo.chunks_in_scope` | Chunks of the border under those parents. |
| `meta.scope.combo.tags_cloud_by_the_facets` | What the facets' standing did to the tags' cloud. |
| `meta.scope.combo.tags_cloud_by_the_facets.nearer` | Chunks moved one level of closeness nearer. |
| `meta.scope.combo.tags_cloud_by_the_facets.farther` | Chunks moved one level farther. |
| `meta.scope.combo.tags_cloud_by_the_facets.changed` | Chunks in the tags' cloud that were not in it by closeness alone. |
| `meta.scope.facets` | The query's facets read relative to the tag: each chunk's edge to its closest tag against the same graph tag's other edges on chunks of its kind, in the facet the first call named for the query tag; the standing moves the chunk one level of closeness at the tags' cloud's edge. |
| `meta.scope.facets.per_query_tag` | One entry a query tag, in the order of the two tag lists (a phrase written in both lists stands twice). |
| `meta.scope.facets.per_query_tag.phrase` | The query tag as the first call wrote it. |
| `meta.scope.facets.per_query_tag.facet` | The one facet the first call named as mattering most for it. |
| `meta.scope.facets.per_query_tag.matters` | Whether the first call said that facet matters for it at all; only then does the facet give a standing. |
| `meta.scope.facets.query_tags_with_a_facet` | How many query tags have a facet that matters. |
| `meta.scope.facets.chunks_standing` | Chunks of the border by their closest edge's standing. |
| `meta.scope.facets.chunks_standing.above` | Standing above the same tag's other edges of their kind. |
| `meta.scope.facets.chunks_standing.below` | Standing below them. |
| `meta.scope.facets.own_phrase_edges_kept_from_below` | Chunks whose closest tag is the query tag's own phrase and that would have stood below. |
| `meta.scope.facets.tags_cloud_by_the_facets` | What the standing did to the tags' cloud. |
| `meta.scope.facets.tags_cloud_by_the_facets.nearer` | Chunks moved one level of closeness nearer. |
| `meta.scope.facets.tags_cloud_by_the_facets.farther` | Chunks moved one level farther. |
| `meta.scope.facets.tags_cloud_by_the_facets.changed` | Chunks in the tags' cloud that were not in it by closeness alone. |
| `meta.scope.storyline` | The 4-combo: the chosen chunks (those in both clouds; with none, those of the lowest step) and how the other chunks of the clouds are tied to them, asked of the graph for this question. A pair is a chosen chunk and another chunk of the clouds; it is tied by scope (the same parent), entities (a person tied to both), time (the smallest gap between a record of the one and a record of the other, before the knee of the upper half of the pairs' gaps) and nearness (their closeness to the query tags pointing the same way, before the knee of the upper half of the pairs' correlations). |
| `meta.scope.storyline.chosen_chunk_ids` | The chosen chunks, by chunk id. |
| `meta.scope.storyline.chunks_in_the_clouds` | Chunks in at least one side's cloud: the only chunks the 4-combo reorders. |
| `meta.scope.storyline.chosen_chunks` | How many chunks were chosen. |
| `meta.scope.storyline.pairs` | How many pairs were asked of the graph. |
| `meta.scope.storyline.pairs_tied` | Per way, how many pairs it ties. |
| `meta.scope.storyline.pairs_by_ways` | How many pairs are tied in 0, 1, 2, 3 and 4 ways. |
| `meta.scope.storyline.time_near_up_to_seconds` | The largest gap in time, in seconds, that counts as near; empty when no pair counts as near in time. |
| `meta.scope.storyline.nearness_from_correlation` | The lowest correlation that counts as near; empty when no pair counts as near. |
| `meta.scope.storyline.chunks_reached` | How many chunks are tied to a chosen chunk in at least one way. |
| `meta.ranking` | The order, and what lies behind each delivered chunk. The lists that start with delivered_ have one entry a delivered chunk, in the arm's order (the answer model read the texts in pointer order, reading_order). |
| `meta.ranking.ordered_chunk_ids` | Every chunk of the border in the arm's order, by chunk id. |
| `meta.ranking.delivered_chunk_ids` | The chunks whose text, what was handed over of them, went in whole before the budget ended, by chunk id. A text can also hold records of other chunks, the rest of a conversation (delivered_records_of_other_chunks); those records are named in chunk_ids by record id. A chosen part of a split record is its whole record; any other part is only that part. |
| `meta.ranking.delivered_step` | The chunk's step: its two levels added, 2 in both clouds, 3 in one, 4 in neither. |
| `meta.ranking.delivered_tags_level` | 1 when it is in the tags side's cloud, 2 when it is not. |
| `meta.ranking.delivered_description_level` | 1 when it is in the description side's cloud, 2 when it is not. |
| `meta.ranking.delivered_in_scope` | Whether it sits under a parent of the scope. |
| `meta.ranking.delivered_middle_rank` | The middle of its two ranks over the border, the tags side's and the description side's: the order inside a step. Every rank here counts from 1, the best; equal values share the mean of their places, so a rank can be a fraction. |
| `meta.ranking.delivered_tags_rank` | Its tags side's rank over the border, from its place (from 1). |
| `meta.ranking.delivered_description_rank` | Its description side's rank over the border, by closeness (from 1). |
| `meta.ranking.delivered_tags_place` | Its tags side's place: the best place a query tag gives it (from 1). |
| `meta.ranking.delivered_closeness_rank` | Under that query tag, its rank by closeness among the border's chunks (from 1; a chunk with no edge to the tag stands after every chunk that has one). |
| `meta.ranking.delivered_standing` | Its closest edge's standing in the named facet against the same graph tag's other edges on chunks of its kind: 1 above, 0 the same or no facet, -1 below; it moves the chunk one level of closeness at the tags' cloud's edge. |
| `meta.ranking.delivered_named_facet` | The facet the first call named for that query tag; empty where the first call said it does not matter. |
| `meta.ranking.delivered_tags_nearness` | The cosine of its closest tag to a query tag. |
| `meta.ranking.delivered_description_nearness` | The cosine of its description to the question without the names. |
| `meta.ranking.delivered_query_description_nearness` | The cosine of its description to the first call's description. It does not enter the order. |
| `meta.ranking.delivered_question_nearness` | The cosine of its description to the question as asked. It does not enter the order. |
| `meta.ranking.delivered_query_tags` | The query tag that gave its place, counted from 0 over the two tag lists; -1 for a chunk with no eligible tag. |
| `meta.ranking.delivered_graph_tags` | The graph tag of its closest edge to that query tag, by name; empty for such a chunk. |
| `meta.ranking.delivered_query_tag_phrases` | That query tag as the first call wrote it; empty for such a chunk. |
| `meta.ranking.delivered_chosen` | Whether it is one of the chosen chunks. |
| `meta.ranking.delivered_storyline_strength` | How strongly it is tied to the chosen chunks: the ways it is tied, added over the chosen chunks. The order is the chosen chunks first, then this, the higher the earlier. |
| `meta.ranking.delivered_storyline_ways` | Per way, how many chosen chunks it is tied to that way. |
| `meta.ranking.delivered_storyline_ways.scope` | Under the same parent. |
| `meta.ranking.delivered_storyline_ways.entities` | A person tied to both. |
| `meta.ranking.delivered_storyline_ways.time` | Near in time. |
| `meta.ranking.delivered_storyline_ways.nearness` | Near each other in what the query asks about. |
| `meta.ranking.delivered_records` | How many records were handed over with the chunk. |
| `meta.ranking.delivered_records_of_other_chunks` | How many of those lie in another chunk: the rest of a conversation this chunk holds a part of. |
| `meta.ranking.delivered_records_not_handed_over` | How many of the chunk's own records were not handed over with it: they went in before, with another chunk. |
| `meta.handed_over` | What of the ordered chunks was handed over. The counts are over the chunks gone through until the budget was full. |
| `meta.handed_over.chunks_gone_through` | How many chunks of the order were gone through. |
| `meta.handed_over.chunks_with_nothing_handed_over` | Of those, the chunks nothing was handed over of. |
| `meta.handed_over.chunks_with_nothing_handed_over.conversations_handed_over_before` | A batch of messages whose conversations all went in before, with another chunk. |
| `meta.handed_over.chunks_with_nothing_handed_over.record_handed_over_before` | A part of a split document or transcript whose whole record went in before. |
| `meta.handed_over.chunks_with_nothing_handed_over.in_a_channel_apart` | Only in runs before 2026-10-23 (commit 751a72d): all its messages lie in a channel apart. |
| `meta.handed_over.chunks_with_nothing_handed_over.no_own_pull_request` | Only in runs before 2026-10-23 (commit 751a72d): a batch of pull requests none of which is the product's own. |
| `meta.handed_over.chunks_with_nothing_handed_over.no_conversation_left` | Only in runs before 2026-10-23 (commit 751a72d): a batch of messages whose conversations are about another project's pull request or were handed over before with another chunk. |
| `meta.handed_over.products` | Only in runs before 2026-10-23 (commit 751a72d): per product of the border, what the graph's people say: the ids of its channels apart, and how many people the product has. |
| `meta.handed_over.records_left_out` | Only in runs before 2026-10-23 (commit 751a72d): records of those chunks left out: a channel apart and other projects' pull requests by the graph's people, talk about another project's pull request by the links in its messages. |
| `meta.handed_over.records_left_out.messages_of_a_channel_apart` | Messages of a channel apart. |
| `meta.handed_over.records_left_out.pull_requests_of_other_projects` | Pull requests whose author is not one of the product's people. |
| `meta.handed_over.records_left_out.messages_about_another_projects_pull_request` | Messages of a conversation that links to another project's pull request and to no own pull request or document. |
| `meta.handed_over.conversations_handed_over` | Conversations handed over whole, in the texts that went in whole (not the one cut at the budget). |
| `meta.handed_over.conversations_reaching_into_another_chunk` | Of those, the conversations with messages in another chunk than the one they first showed in. |
| `meta.diagnostics` | Counts that say how the order came about. |
| `meta.diagnostics.credited_delivered_rows` | How many texts went in whole before the budget ended. |
| `meta.diagnostics.boundary_chunk_id_not_credited` | The chunk id of the text that was cut where the budget ended; empty when none was. |
| `meta.diagnostics.query_tags` | Query tags in the two lists together. |
| `meta.diagnostics.phrases_standing_in_both_tag_lists` | Phrases the first call wrote in both lists. |
| `meta.diagnostics.query_tag_closest_graph_tag` | Per query tag, the cosine of its closest eligible graph tag on the border's chunks. |
| `meta.diagnostics.delivered_on_each_step` | How many of the delivered chunks stand on each step. |
| `meta.diagnostics.delivered_in_scope` | How many of the delivered chunks are in scope. |
| `meta.chunk_ids` | The record ids behind each text handed over, one list a text, in the order of contexts: the arm's order. |
| `meta.reading_order` | The order the answer model read the texts in, pointer order, as positions in contexts (0 the first). |
| `meta.returned` | How many texts were handed over, the one cut at the budget counted. |
| `meta.char_budget` | How the character budget was filled. |
| `meta.char_budget.budget` | The character budget. |
| `meta.char_budget.chars` | How many characters were handed over. |
| `meta.char_budget.kept` | How many units were handed over whole. |
| `meta.char_budget.boundary` | The unit that was cut where the budget ended. Empty when the budget ended exactly at a unit's end, or when the ranking ran out first. |
| `meta.char_budget.boundary.id` | The id of its record. |
| `meta.char_budget.boundary.chars_kept` | How many of its characters were handed over. |
| `meta.char_budget.boundary.chars_full` | How many characters it has. |
| `meta.char_budget.exhausted` | Whether the ranking ran out before the budget was full. |

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
| `envelope` | The Claude program's whole reply as it printed it, each part as the program gives it: its own times in milliseconds (duration_ms from the start of the request turn, after the program has started, to its end; duration_api_ms for the time spent in requests to the model; ttft_ms until the first block of the first request's reply is complete; ttft_stream_ms until the first event of that reply's stream; time_to_request_ms until the first request was sent; the last three from the start of the request turn), its own token counts, the models it used with their context window in tokens (contextWindow), its own price in US dollars (total_cost_usd, costUSD; no number of this harness uses it), its counts of web requests (0: the call has no tool), its session id, how many turns it took, and its error fields, which are empty when the call had no error (api_error_status, permission_denials). Empty for a call that gave up: no reply was read. |
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
| `graph` | The Neo4j database the arm reads. |
| `facet_layer_run` | The run id of the facet values on the tag-to-chunk edges. |
| `counts` | What the start of the run counted in the graph (as in provenance). |
| `build_cost` | Per build step of the graph: what it made, when, with which model or device, its calls, tokens in and out and seconds where the step's own record gives them, the records it is read from, and what those records do not give. Collected from the records into `test/graph/build_cost.json`; nothing in it is estimated except the chunks' token estimate, which the chunker itself wrote. Every number in it was recounted from its record on 2026-10-20 (`test/graph/build_cost_check.json`). |
| `build_cost_file_sha256` | The sha256 of that file, its line ends as git holds them (LF), which identifies the build cost given. |
| `first_call` | When and how the first call is made. |
| `question_embedding` | When and how the query tags, the description and the question are embedded. |
| `unit_text` | The form a record is written in for the answer model, and where that form is from; what a part of a split record brings; the order the texts reach the model in. |

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
| `calls.attempts.error` | null | 100 | 100 |
| `calls.attempts.n` | integer | 100 | 0 |
| `calls.attempts.outcome` | string | 100 | 0 |
| `calls.attempts.returncode` | integer | 100 | 0 |
| `calls.attempts.seconds` | number | 100 | 0 |
| `calls.attempts.started_at` | string | 100 | 0 |
| `calls.attempts.stderr` | null | 100 | 100 |
| `calls.attempts.stdout` | null | 100 | 100 |
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
| `meta.char_budget.boundary` | null, object | 100 | 11 |
| `meta.char_budget.boundary.chars_full` | integer | 89 | 0 |
| `meta.char_budget.boundary.chars_kept` | integer | 89 | 0 |
| `meta.char_budget.boundary.id` | string | 89 | 0 |
| `meta.char_budget.budget` | integer | 100 | 0 |
| `meta.char_budget.chars` | integer | 100 | 0 |
| `meta.char_budget.exhausted` | boolean | 100 | 0 |
| `meta.char_budget.kept` | integer | 100 | 0 |
| `meta.chunk_ids` | array | 100 | 0 |
| `meta.diagnostics` | object | 100 | 0 |
| `meta.diagnostics.boundary_chunk_id_not_credited` | null, string | 100 | 11 |
| `meta.diagnostics.credited_delivered_rows` | integer | 100 | 0 |
| `meta.diagnostics.delivered_in_scope` | integer | 100 | 0 |
| `meta.diagnostics.delivered_on_each_step` | object | 100 | 0 |
| `meta.diagnostics.phrases_standing_in_both_tag_lists` | integer | 100 | 0 |
| `meta.diagnostics.query_tag_closest_graph_tag` | array | 100 | 0 |
| `meta.diagnostics.query_tags` | integer | 100 | 0 |
| `meta.handed_over` | object | 100 | 0 |
| `meta.handed_over.chunks_gone_through` | integer | 100 | 0 |
| `meta.handed_over.chunks_with_nothing_handed_over` | object | 100 | 0 |
| `meta.handed_over.chunks_with_nothing_handed_over.conversations_handed_over_before` | integer | 100 | 0 |
| `meta.handed_over.chunks_with_nothing_handed_over.record_handed_over_before` | integer | 100 | 0 |
| `meta.handed_over.conversations_handed_over` | integer | 100 | 0 |
| `meta.handed_over.conversations_reaching_into_another_chunk` | integer | 100 | 0 |
| `meta.interpreter` | object | 100 | 0 |
| `meta.interpreter.description_side_tags` | integer | 100 | 0 |
| `meta.interpreter.embeddings` | object | 100 | 0 |
| `meta.interpreter.embeddings.description_side_tags` | object | 100 | 0 |
| `meta.interpreter.embeddings.description_side_tags.embedding` | string | 100 | 0 |
| `meta.interpreter.embeddings.description_side_tags.tags` | integer | 100 | 0 |
| `meta.interpreter.embeddings.description_side_tags.text_chars` | integer | 100 | 0 |
| `meta.interpreter.embeddings.question` | object | 100 | 0 |
| `meta.interpreter.embeddings.question.embedding` | string | 100 | 0 |
| `meta.interpreter.embeddings.question.text_chars` | integer | 100 | 0 |
| `meta.interpreter.embeddings.question_side_tags` | object | 100 | 0 |
| `meta.interpreter.embeddings.question_side_tags.embedding` | string | 100 | 0 |
| `meta.interpreter.embeddings.question_side_tags.tags` | integer | 100 | 0 |
| `meta.interpreter.embeddings.question_without_the_names` | object | 100 | 0 |
| `meta.interpreter.embeddings.question_without_the_names.embedding` | string | 100 | 0 |
| `meta.interpreter.embeddings.question_without_the_names.text_chars` | integer | 100 | 0 |
| `meta.interpreter.model` | string | 100 | 0 |
| `meta.interpreter.question_side_tags` | integer | 100 | 0 |
| `meta.interpreter.stages` | array | 100 | 0 |
| `meta.interpreter.stages.asks` | integer | 100 | 0 |
| `meta.interpreter.stages.cache_hit` | boolean | 100 | 0 |
| `meta.interpreter.stages.duplicate_tags_dropped` | integer | 100 | 0 |
| `meta.interpreter.stages.key` | string | 100 | 0 |
| `meta.interpreter.stages.offline` | boolean | 100 | 0 |
| `meta.interpreter.stages.stage` | string | 100 | 0 |
| `meta.provenance` | object | 100 | 0 |
| `meta.provenance.corpus_argument` | string | 100 | 0 |
| `meta.provenance.counts` | object | 100 | 0 |
| `meta.provenance.counts.chunks` | integer | 100 | 0 |
| `meta.provenance.counts.chunks_with_a_time` | integer | 100 | 0 |
| `meta.provenance.counts.chunks_with_an_eligible_edge` | integer | 100 | 0 |
| `meta.provenance.counts.customer_chunk_edges` | integer | 100 | 0 |
| `meta.provenance.counts.edges` | integer | 100 | 0 |
| `meta.provenance.counts.eligible_edges` | integer | 100 | 0 |
| `meta.provenance.counts.eligible_graph_tags` | integer | 100 | 0 |
| `meta.provenance.counts.graph_tags` | integer | 100 | 0 |
| `meta.provenance.counts.named_structure_nodes` | object | 100 | 0 |
| `meta.provenance.counts.product_named_tags` | integer | 100 | 0 |
| `meta.provenance.counts.products` | integer | 100 | 0 |
| `meta.provenance.database` | string | 100 | 0 |
| `meta.provenance.facet_layer` | object | 100 | 0 |
| `meta.provenance.interpreter_model` | string | 100 | 0 |
| `meta.provenance.run_id` | string | 100 | 0 |
| `meta.provenance.source_sha256` | object | 100 | 0 |
| `meta.provenance.topic_on_the_edge_against_the_vectors_max_abs` | number | 100 | 0 |
| `meta.ranking` | object | 100 | 0 |
| `meta.ranking.delivered_chosen` | array | 100 | 0 |
| `meta.ranking.delivered_chunk_ids` | array | 100 | 0 |
| `meta.ranking.delivered_closeness_rank` | array | 100 | 0 |
| `meta.ranking.delivered_description_level` | array | 100 | 0 |
| `meta.ranking.delivered_description_nearness` | array | 100 | 0 |
| `meta.ranking.delivered_description_rank` | array | 100 | 0 |
| `meta.ranking.delivered_graph_tags` | array | 100 | 0 |
| `meta.ranking.delivered_in_scope` | array | 100 | 0 |
| `meta.ranking.delivered_middle_rank` | array | 100 | 0 |
| `meta.ranking.delivered_named_facet` | array | 100 | 0 |
| `meta.ranking.delivered_query_description_nearness` | array | 100 | 0 |
| `meta.ranking.delivered_query_tag_phrases` | array | 100 | 0 |
| `meta.ranking.delivered_query_tags` | array | 100 | 0 |
| `meta.ranking.delivered_question_nearness` | array | 100 | 0 |
| `meta.ranking.delivered_records` | array | 100 | 0 |
| `meta.ranking.delivered_records_not_handed_over` | array | 100 | 0 |
| `meta.ranking.delivered_records_of_other_chunks` | array | 100 | 0 |
| `meta.ranking.delivered_standing` | array | 100 | 0 |
| `meta.ranking.delivered_step` | array | 100 | 0 |
| `meta.ranking.delivered_storyline_strength` | array | 100 | 0 |
| `meta.ranking.delivered_storyline_ways` | object | 100 | 0 |
| `meta.ranking.delivered_storyline_ways.entities` | array | 100 | 0 |
| `meta.ranking.delivered_storyline_ways.nearness` | array | 100 | 0 |
| `meta.ranking.delivered_storyline_ways.scope` | array | 100 | 0 |
| `meta.ranking.delivered_storyline_ways.time` | array | 100 | 0 |
| `meta.ranking.delivered_tags_level` | array | 100 | 0 |
| `meta.ranking.delivered_tags_nearness` | array | 100 | 0 |
| `meta.ranking.delivered_tags_place` | array | 100 | 0 |
| `meta.ranking.delivered_tags_rank` | array | 100 | 0 |
| `meta.ranking.ordered_chunk_ids` | array | 100 | 0 |
| `meta.reading_order` | array | 100 | 0 |
| `meta.returned` | integer | 100 | 0 |
| `meta.scope` | object | 100 | 0 |
| `meta.scope.chunks_cut` | integer | 100 | 0 |
| `meta.scope.chunks_kept` | integer | 100 | 0 |
| `meta.scope.chunks_under_the_names` | integer | 100 | 0 |
| `meta.scope.combo` | object | 100 | 0 |
| `meta.scope.combo.chunks` | integer | 100 | 0 |
| `meta.scope.combo.chunks_in_scope` | integer | 100 | 0 |
| `meta.scope.combo.chunks_on_each_step` | object | 100 | 0 |
| `meta.scope.combo.clouds` | object | 100 | 0 |
| `meta.scope.combo.clouds.description` | integer | 100 | 0 |
| `meta.scope.combo.clouds.tags` | integer | 100 | 0 |
| `meta.scope.combo.scope_gauged_from_chunks` | integer | 100 | 0 |
| `meta.scope.combo.scopes_taken` | array | 100 | 0 |
| `meta.scope.combo.tags_cloud_by_the_facets` | object | 100 | 0 |
| `meta.scope.combo.tags_cloud_by_the_facets.changed` | integer | 100 | 0 |
| `meta.scope.combo.tags_cloud_by_the_facets.farther` | integer | 100 | 0 |
| `meta.scope.combo.tags_cloud_by_the_facets.nearer` | integer | 100 | 0 |
| `meta.scope.delivered_under_the_names` | integer | 100 | 0 |
| `meta.scope.facets` | object | 100 | 0 |
| `meta.scope.facets.chunks_standing` | object | 100 | 0 |
| `meta.scope.facets.chunks_standing.above` | integer | 100 | 0 |
| `meta.scope.facets.chunks_standing.below` | integer | 100 | 0 |
| `meta.scope.facets.own_phrase_edges_kept_from_below` | integer | 100 | 0 |
| `meta.scope.facets.per_query_tag` | array | 100 | 0 |
| `meta.scope.facets.per_query_tag.facet` | string | 100 | 0 |
| `meta.scope.facets.per_query_tag.matters` | boolean | 100 | 0 |
| `meta.scope.facets.per_query_tag.phrase` | string | 100 | 0 |
| `meta.scope.facets.query_tags_with_a_facet` | integer | 100 | 0 |
| `meta.scope.facets.tags_cloud_by_the_facets` | object | 100 | 0 |
| `meta.scope.facets.tags_cloud_by_the_facets.changed` | integer | 100 | 0 |
| `meta.scope.facets.tags_cloud_by_the_facets.farther` | integer | 100 | 0 |
| `meta.scope.facets.tags_cloud_by_the_facets.nearer` | integer | 100 | 0 |
| `meta.scope.names_in_the_question` | array | 100 | 0 |
| `meta.scope.names_in_the_question.chunks` | integer | 100 | 0 |
| `meta.scope.names_in_the_question.key` | string | 100 | 0 |
| `meta.scope.names_in_the_question.labels` | array | 100 | 0 |
| `meta.scope.names_in_the_question.name` | string | 100 | 0 |
| `meta.scope.names_in_the_question.nodes` | integer | 100 | 0 |
| `meta.scope.names_in_the_question.set_aside` | boolean | 100 | 0 |
| `meta.scope.nothing_cut` | boolean | 100 | 0 |
| `meta.scope.storyline` | object | 100 | 0 |
| `meta.scope.storyline.chosen_chunk_ids` | array | 100 | 0 |
| `meta.scope.storyline.chosen_chunks` | integer | 100 | 0 |
| `meta.scope.storyline.chunks_in_the_clouds` | integer | 100 | 0 |
| `meta.scope.storyline.chunks_reached` | integer | 100 | 0 |
| `meta.scope.storyline.nearness_from_correlation` | null, number | 100 | 25 |
| `meta.scope.storyline.pairs` | integer | 100 | 0 |
| `meta.scope.storyline.pairs_by_ways` | object | 100 | 0 |
| `meta.scope.storyline.pairs_tied` | object | 100 | 0 |
| `meta.scope.storyline.time_near_up_to_seconds` | null, number | 100 | 17 |
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

### `eval_calls.jsonl` (602 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `applied` | object | 602 | 0 |
| `arm` | string | 602 | 0 |
| `attempts` | array | 602 | 0 |
| `attempts.error` | null, string | 602 | 601 |
| `attempts.n` | integer | 602 | 0 |
| `attempts.outcome` | string | 602 | 0 |
| `attempts.returncode` | integer, null | 602 | 1 |
| `attempts.seconds` | number | 602 | 0 |
| `attempts.started_at` | string | 602 | 0 |
| `attempts.stderr` | null, string | 602 | 602 |
| `attempts.stdout` | null, string | 602 | 602 |
| `cwd` | string | 602 | 0 |
| `effort` | null | 602 | 602 |
| `env_set` | object | 602 | 0 |
| `env_unset` | array | 602 | 0 |
| `envelope` | null, object | 602 | 1 |
| `error` | null, string | 602 | 601 |
| `eval_leg` | string | 602 | 0 |
| `exe` | string | 602 | 0 |
| `finished_at` | string | 602 | 0 |
| `flags` | array | 602 | 0 |
| `join_parts` | boolean | 602 | 0 |
| `kind` | string | 602 | 0 |
| `max_tries` | integer | 602 | 0 |
| `model` | string | 602 | 0 |
| `not_applied` | object | 602 | 602 |
| `ok` | boolean | 602 | 0 |
| `payload_dropped` | array | 602 | 602 |
| `phase` | string | 602 | 0 |
| `prompt` | string | 602 | 0 |
| `question_id` | string | 602 | 0 |
| `schema` | null | 602 | 602 |
| `score` | string | 602 | 0 |
| `seq` | integer | 602 | 0 |
| `started_at` | string | 602 | 0 |
| `stderr` | null, string | 602 | 602 |
| `stream` | null | 602 | 602 |
| `system` | string | 602 | 602 |
| `text` | null, string | 602 | 1 |
| `timeout_s` | number | 602 | 0 |
| `type` | string | 602 | 0 |
| `usage` | null, object | 602 | 1 |
| `usage.cached_input_tokens` | integer | 601 | 0 |
| `usage.completion_tokens` | integer | 601 | 0 |
| `usage.prompt_tokens` | integer | 601 | 0 |

### `eval_failures.jsonl` (1 records)

| Field | Types | Records that hold it | Of those, empty |
|---|---|---|---|
| `error` | string | 1 | 0 |
| `eval_leg` | string | 1 | 0 |
| `failed_at` | string | 1 | 0 |
| `metric` | string | 1 | 0 |
| `question_id` | string | 1 | 0 |
| `usage` | object | 1 | 0 |
| `usage.cached_input_tokens` | integer | 1 | 0 |
| `usage.chat_attempts` | integer | 1 | 0 |
| `usage.chat_calls` | integer | 1 | 0 |
| `usage.chat_s` | number | 1 | 0 |
| `usage.embed_calls` | integer | 1 | 0 |
| `usage.embed_s` | number | 1 | 0 |
| `usage.embed_texts` | integer | 1 | 0 |
| `usage.embed_tokens` | integer | 1 | 0 |
| `usage.eval_leg` | string | 1 | 0 |
| `usage.finished_at` | string | 1 | 0 |
| `usage.started_at` | string | 1 | 0 |
| `usage.thread` | string | 1 | 0 |
| `usage.tokens_in` | integer | 1 | 0 |
| `usage.tokens_out` | integer | 1 | 0 |
| `usage.wall_s` | number | 1 | 0 |

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
Written from `prod/harness/fields.py`, sha256 `1c4a0c739e74ffebf0a5a6c716aba0f32c6d222f566b01d1b471f2c222f6cfb6`.

The files as they stood when this was written, their line ends as git holds them (LF):

- `arm_outputs.jsonl` sha256 `fba8f4ccfb6df5a13d751693faf39880b170b56c39517eba1a814d363455be1f`
- `correct_missing_judge_legs.py` sha256 `e8adbbbe26fed551172e08ae67d12df25490d0ef05585d445acabee4d6e8c71e`
- `correct_nonllm_record_content.py` sha256 `22f302c2e645d3aecbf87ab8735b64b356695a43362ab1cad39ce406d6d59f75`
- `corrections.json` sha256 `193942483d717c16be8e27da2b8d94cae7a16a55b324e3de80a7c0cfef72ec42`
- `eval_calls.jsonl` sha256 `e76cf3b35933cab6bc42f5930b7e525b3779bc71e060f567e0f5b5d37cc2107e`
- `eval_failures.jsonl` sha256 `afa0dd2215302b8be8d9165de105a5afcb79371e22f7516b3c9487e752df0b88`
- `eval_manifest.as_recorded.json` sha256 `4377d0c6fafb4b8a8a0592353caf8a8011c8dbc9f76a1fa9504aae1f42d8acc0`
- `eval_manifest.json` sha256 `5128815ed182cd5a214866049d61b8cf345f6f6a1273dea447dd6d675d4e4978`
- `eval_results.as_recorded.jsonl` sha256 `becda2540fd2ceed71e49488e22c31c95a2a005583f026064652a9ab95b70432`
- `eval_results.jsonl` sha256 `052b81d573bf1f3a7fa330835519d5915efd7b76a624e65cd234fc0ca3236d54`
