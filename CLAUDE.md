# CLAUDE.md

Only two kinds of text are facts here: his own sentences, quoted with their date, and what a
command prints. What an arm does is read from its file; what the graph holds is read by
querying it. Any other sentence, this file included, is a claim until checked.

## This file

*"wtf, day by day record in the claude.md? wtf?"* · *"yeah, clean that shit up"* ·
*"dude why carry alot for no reason?"* (2026-10-07) · *"do you ever remove old rules when putting
new in?"* · *"apparently you never remove some old outdated or contradicting information when i say
something new, you just cake it on top"* (2026-10-22)

It holds his rules and his concept in his own sentences, and where things are. Nothing else
goes in: no record of a conversation, no run number, no review finding, no build history, no
"what was done today", no note that a thing was built, replaced or taken out. A rule he states,
or a change he makes to the concept, goes in in the same turn as one line of his words with the
date, and in the same edit every line it replaces or contradicts goes out. What he said is in
the palace and the session transcripts; the numbers are in the run folders and under
`output/research/`. At commit: `python refresh_graph.py`, then `python tools/canon_extract.py`.

## Where

- `prod/` — the finished system: `harness/`, `eval/`, `arms/` (lucene, vector, hybrid), `run.py`,
  `tests/`. `test/` — the artefact: `arms/`, `artefact/`, `graph/` (db, builders, facet tools),
  `tests/`. `python prod/run.py --arm <arm> --set <set>` from the repo root loads arms from both.
  Runs and their manifests in `output/`; data in `data/`.
- The artefact: `test/arms/artefact_v4.py`. What it does, step by step with each step's function,
  is its docstring; what it writes into a run, its `FIELDS`. Beside it: `test/artefact/v4_walk.py`
  (the arithmetic), `test/artefact/query_content.py` (the first call, the arm's one model
  request). The graph builders it reads: `test/graph/build_person_edges.py` (person-to-chunk
  edges), `build_chunk_times.py` (each chunk's records' own times, `times`),
  `build_structure_names.py` (each structure node's `name` and `name_keys`, read through its
  pointer), `build_customer_edges.py` (customer-to-chunk edges where a record carries the
  customer's id). The graph's build cost: `test/graph/build_cost.json`, step by step from the
  build records (the arm writes it into each run's manifest, `index_info`, and one entry per model
  into `build_stats`); its recount `test/graph/build_cost_check.json`; every build record with its
  hashes `test/graph/build_records.json`; the haiku calls' time by their answering tries
  `test/graph/build_cost_haiku_answering_tries.json` (`tools/recount_haiku_answering_tries.py`, from the
  tagging run's records in git); the 63 readable tag names, embedded on the laptop's CPU, timed again on
  the desktop's graphics card `test/graph/build_cost_readable_names_gpu_times.json`, and their tokens
  `test/graph/build_cost_readable_names_tokens.json` (`tools/count_readable_tag_tokens.py`); the Opus
  calls' time from the CLI's own transcripts `test/graph/build_cost_opus_transcript_times.json`
  (`tools/recount_opus_build_times.py`).
- What in the arm is the agent's own choice and not his word: the knee looked for above the
  median, in the clouds and in the 4-combo; the clouds' steps (2 in both clouds, 3 in one, 4 in
  neither); the parents holding the majority of a cloud's chunks going first inside a step; the
  two sides' ranks counted equally; a chunk's tags-side place the best any query tag gives it;
  the border's names taken out of the question on the description side; the first call's
  description left out of the order; and a channel's conversations its gaps cut in two.
- `HERB_V4_OFFLINE=on` covers only the first call: its answer is read from the cache and the run
  stops where one is missing; the answer model and the judge still run. What a run used: its
  `run_manifest.json` and each row's `meta`. `output/code_before_*/` — copies of the code before
  each large change.
- `finished_data/full-grag-data.xlsx` — the data given away, one workbook and nothing else (his name,
  2026-10-29), four sheets: `results`, `run data`, `arm construction`, `key` (what each holds:
  "The data given away" below). Made by `tools/export_finished_data.py` (needs openpyxl) from the
  six final run folders (each arm's run on the hundred and its run on the 715), the re-judging
  folder beside each run on the hundred and `test/graph/build_cost.json`; the export stops on any
  value that does not line up.
- `docs/ENVIRONMENT.md` — the machines, the Neo4j start, the model lane and how many calls this
  laptop holds at once; the desktop's clone and graph for split runs, and the commands of a split
  run (`tools/merge_split_run.py split|merge`). `docs/canon/raw/user_turns.jsonl` — his typed messages
  (`tools/canon_extract.py`); archive, nothing reads it.
- `docs/record/CLAUDE_md_until_2026-10-07.md` — this file as it stood before the cut of
  2026-10-07: his turns, the answers and the run numbers, day by day. Read it only when a question
  needs it. Nothing is added to it.
- `output/research/<date>-…/` — the scripts and prints of each measurement.
- `graphify-out/` — the navigation graph over `prod/` and `test/`. Query it before grepping:
  `python -m graphify query "<question>"`, `python -m graphify explain "<node>"`,
  `python -m graphify path "A" "B"`. Rebuild with `python refresh_graph.py` (seconds, AST only),
  never `graphify --update`.
- `.claude/agents/` — the specialists.
- The palace (MemPalace): his conversations with every model, verbatim, one wing per project;
  `mempalace_search` in the main session, `mempalace search "…"` from a shell. A lookup by
  content, not a transcript. Nothing an agent writes goes into it (his 2026-09-04); nothing with
  gold or test questions ever does (his 2026-08-02). Its dates are the mining day until
  `tools/palace_dates.py --apply` has run after the last mine.

## Current state — print, never type

- The last conversation: `python tools/last_turns.py` (the SessionStart hook prints it into every
  new session). "Where are we / what's next" is answered from that print: quote his last words
  and the step they name; if no step is named, say so and ask. A specialist runs the script
  itself before any sentence about where the work stands. Not from the palace, not from memory.
- Arms: `ls prod/arms test/arms`. Database an arm used: its run manifest.
- Runs: `ls output/k=chars`. The final runs on the hundred, the ones the workbook reads:
  `artefact_v4__gold100__cb72000__20261023T021439Z` (his *"and the workbook is updated with
  this?"*, 2026-10-23; commit `751a72d`, one launch on the desktop with 27 workers; the answer
  call's tokens of 40 rows corrected from the CLI's own record, `tools/correct_zero_usage.py`),
  `lucene__gold100__cb72000__20261008T234209Z` and `vector__gold100__cb72000__20261017T061242Z`
  (commit `fbc2f22` from a clean checkout, one worker each). The artefact's
  interpreter answers were read from the store of `artefact_v4__gold100__cb72000__20261020T041923Z`
  (commit `0c082a3` from a clean checkout) and most query embeddings from the machines' embedding
  cache, so the workbook takes those values from that run. Each folder's `FIELDS.md` says what it
  holds and on whose word anything was left out; its `corrections.json`, what was corrected after
  the run. `factual_correctness` and `context_entity_recall` were judged after the three, on their
  answers with the same judge, by `prod/run.py --rejudge` into the folder beside each,
  `<run>__j-claude-haiku-4-5-20251001__gold100` (his *"just toggle them and run them on all 100 for
  all 3 arms"*, 2026-10-23); the workbook reads those two scores there.
  The final runs on the 715 other answerable questions (`data/answerable715.jsonl`), which the
  workbook reads beside the hundred (his *"the fucking point is to have a full ragas-herb test done
  finally"*, 2026-10-25): `artefact_v4__answerable715__cb72000__20261025T211532Z` (split over the
  laptop and the desktop and merged by `tools/merge_split_run.py`, both halves under its `halves/`),
  `lucene__answerable715__cb72000__20261023T112745Z` and
  `vector__answerable715__cb72000__20261024T004317Z`; each judged all sixteen scores itself. Their
  files over 100 MB are listed in `.gitignore` and copied between the machines. Starts of the
  artefact's run that the desktop's crashes ended had embedded some questions' query texts, and
  their records went with them, so the workbook takes that run's query embeddings from
  `artefact_v4__answerable715__cb72000__20261027_query_embeddings`: the same questions without
  answers, each first call read from the run's stores, the embedding cache empty, on the desktop's
  graphics card (the same retrieval on all 715; each text's vector checked against the run's own,
  `query_vectors_against_the_run.json` in it).
  `context_recall_id` and `context_precision_id` count record ids; the nonllm pair counts record
  content against record content, each delivered text cut into its records
  (`nonllm-record-content/1` in each run's `corrections.json`).
- A run: `python prod/run.py --arm artefact_v4 --set gold|10smoke --char-budget 72000 --workers 6
  --out <folder>`; the same command into the same folder resumes. `--retrieval-only` makes no
  answer and no judging; `--flag HERB_V4_OFFLINE=on` reads the first call's answers from the cache.
- Graph: `MATCH (n) UNWIND labels(n) AS l RETURN l, count(*)` ·
  `MATCH (a)-[r]->(b) RETURN labels(a)[0], type(r), labels(b)[0], count(*)` · `keys()` per label.
- Facet layer on `HAS_TAG`: hash against `output/facet_weight_backup/` with
  `test/graph/backup_facet_weights.py`, `NEO4J_DATABASE` naming the graph.
- A check that needs a question uses the made-up one in
  `output/walkthrough/20261005T040000Z/walkthrough.json`, never a test question.

## His rules, his words

Gold, results, numbers:

- *"you should not have the questions/gold available to you, there is 0% good that can come out of taht"* (2026-08-02)
- *"just the fucking stats, YOU DONTY INTERPRET THE RESULTS"* (2026-08-05)
- *"there is no "baseline" artefact, a comparable baseline are the vector and lucene arms, no?"* · *"Report both, decide nothing"* (2026-08-05)
- *"i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something"* (2026-07-15) · *"see, thats an arbitrary fucking number"* (2026-10-06, on a 5% point the agent had picked)
- *"they are legendarily bad at 'picking numbers' like that, actually the whole reason we wound up here at all is because of that"* (2026-09-08) — no model writes a per-edge number. *"the point is that the MODEL is not responsible for the VALUES, the NUMERIC values"* (2026-09-18)
- *"what the fuck does the benchmark have to do with it? this is about finding the correct chunks"* (2026-09-08)
- *"you are tryharding on "getting the best score" when the actual fucking best score, is given when this is CONSTRUCTED CORRECTLY"* (2026-09-11) — a design is never picked because it scored best on the gold.
- *"dont focus so fucking hard on the numbers, the reason behind the numbers is the important part, or more, the difference etc"* (2026-10-06)
- *"there is literally no fucking way that i can sit here and proofread chunks, actually 0"* (2026-09-20)
- *"the microgains you keep nagging about is litterally the fluctuations of ai generation and beside that.. Any change under 0.05 is utterly uninteresting"* (2026-10-11, on differences of 0.015 to 0.036 reported one after another) — a difference under 0.05 is not a gain or a loss and is not brought to him as one. *"drop the 0.05-line ffs"* (2026-10-19, on "under your 0.05 line" written beside two numbers) — the line is never quoted back to him; the numbers are given and nothing is said about the line.
- *"recall of WHAT? you have numbers there and utterly fucking unclear heading"* · *"2 questions... what kind of retarded metrics is this?"* (2026-10-10, on a table that split the ten's recall into groups of one to eight questions) — a score is reported as the evaluation gives it, with its name and what it measures in the heading; no made-up breakdown of it, no mean over a handful of questions.
- *"then stop showing me the fucking aggreagate every time!"* (2026-10-19, after a difference of 0.003 in the mean over the hundred hid recall going up on 16 questions and down on 16) — two runs are compared question by question: on how many questions the score went up, down or stayed, and by how much; the mean alone is never the comparison.
- *""Gold chunk in the cloud." It's the most retarded metric I have fucking ever heard."* · *"That's like saying if we pull all hits from the query, one of them will have a gold. No fucking shit, guy."* (2026-10-12, on "a gold chunk somewhere in the cloud: 86 to 94 of 100") — no count of a set that merely holds a gold chunk.
- *"is not only not interesting at all, its disturbing noise and making you focus on the wrong things, you can look that shit up if you want, maybe thats good, but i NEVER want to see such things unless i extremely specifically ask for just that"* (2026-10-22, on "The worst cases are TrendForce::a::9 (−19), ActionGenie::a::7 (−13) and VizForce::a::43 (−15)") — no single question is named or shown as a case in what he reads, unless he asks for exactly that.
- *"also, you need to fucking stop separating the 715 and the 100 in all places, they are theoretically "different runs" but they are also fucking not"* (2026-10-28) — the 815 questions are one set: a number is given over the 815, and the hundred and the 715 are named apart only where a file or a folder must be found.

What may be done:

- Nothing built, run, or written to the database without his words naming it; a "yeah" is not a go (2026-09-03). The one exception: *"Dude, if there are no model call.. Just fucking run it.."* (2026-10-11, on a retrieval-only hundred that was offered and not run) — a run or a count that makes no model call is run without asking.
- *"Unless i litterally tell you its ok or i want to do this, you do NEVER just "run ahead" if you have something unsettled"* (2026-10-07, after "Three things in the build are mine … Stop me if any is wrong" was followed by building) — an unsettled point stops the work and is put to him; "stop me if wrong" is not his ok.
- *"ok, obviously switch it on ALWAYS switch on the newest built thing unless stated otherwise"* (2026-09-07) · *"only make a switch when i specifically have asked for a "run both and see" or something like that.."* (2026-10-07) — the newest built thing is on and replaces the old behaviour; the old one is in git, not behind a switch.
- A comment says what the code does; his sentence goes in only where it is the reason, as one line (his "yes", 2026-10-07).
- *"the fucking dokumentation needs to reflect reality, at all times.."* (2026-10-17, after the 4-combo was written into this file as if built) — a sentence about what is built, what the arm does or where a thing is, is changed in the same turn as the change it describes.
- *".. do the fucking 100th also.. stop beeing satisfied with an incomplete run"* (2026-10-06)
- *"make sure you can run the new 100gold later cocurrently also, i want to do this on both the laptop and desktop every fucking time you do anything tbh, max speed if possible"* (2026-10-22) — a run on the hundred is split across the laptop and the desktop and run in parallel.
- *"no skips allowed"* (2026-10-08, on a test run that reported 1 skipped and five test files that did not load)
- *"if our history had a great solution for this, we would not still be working on it"* (2026-09-08) — restoring deleted code is not work.
- *"i am certain now that you have in fact NOT retrieved the facet concepts, you have found the v3 retrieval interpreter concepts"* · *"you have to look in the fucking git"* (2026-09-08) — the concept is in the initial commit and the thesis, not in later design docs.
- *"you can do whatever fucking temporary tests you want for your coding, but keep them off my fucking code when you have assertained that the code YOU wrote is actually working as intended"* (2026-10-21, on a test file grown with each change) — a check of the agent's own code is made in the scratchpad and stays there; no new test goes into the repo.

The harness and the data:

- *"but you are supposed to use a headless mode with constructed in and outputs, there is supposed to be fucking NOTHING more sent to the model than that"* (2026-10-05) — every model call goes through `prod/harness/chat.py` with `--safe-mode`, `--tools ""` and `--system-prompt`.
- *"Obviously both the fucking in AND output needs to be constructed! Why the fuck else do you think we are running headless!?"* (2026-10-07, on calls that sent the question raw and asked for JSON in words)
- *"wtf do the judges have to do with this? they are RAGAS, we cant do shit about those"* (2026-10-07) · *"obviously we need to make sure that shit is also done correctly then"* (2026-10-08, after RAGAS's own docs were read) — RAGAS's prompts and scoring stay RAGAS's; the judge model and how it is called are ours, and are sent correctly.
- *"yeah, thats fine, go ahead then"* (2026-10-09, on taking the account's e-mail address out of every call, which changes the login) — the lane's CLI runs under its own config folder (`~/.claude-herb-lane`) and logs in with the token of `.env`; a call without the token is refused.
- *"Stop using the api key then"* · *"It's done with that now"* (2026-10-26, after the final runs on the 715) —
  no run uses the API key: no start sets `HERB_CLAUDE_API_FALLBACK=on`, and `CLAUDE_API` in `.env` is a
  comment. The final runs on the 715 that had the fallback on record each try's `credential`.
- *"yes, they get those fields!"* (2026-10-09, on the fields of a record that lucene's and vector's text left out: a document's author, date and link, a transcript's participants and date, a PR's author, reviewers, state, dates and link, a Slack message's time) — a baseline unit's text is the record written the way the benchmark's own code writes it (`prod/harness/record_text.py`).
- *"yeah and it is contextnoise, ok, that part is removed (what the model gets that is), also in case we did t do it, we should "after the 72k cut, but before the model gets it" also order the chunks by the pointer order"* (2026-10-22, on the "[Part i of n]" mark on a part of a split record) · *"yeah, thats the fucking point, but that is part of the artefact"* (2026-10-22, on OP-RAG and on the arms' answer models then reading in different orders) · *"this feels academically ok, right?"* · *"... but why dude, did we not agree to create that?"* (2026-10-22, on RAGAS reading the texts in the arm's order, which its context precision reads as a rank, while the answer model reads them in pointer order) — no mark; after the cut the artefact's texts reach the answer model in pointer order, a step of the artefact's method, while `contexts`, which RAGAS reads, keeps the arm's order (`reading_order` in the row).
- *"yes, sonnet on those, sonnet used the vector and lucene too, right?"* (2026-10-06) — the first call and the answer model run on claude-sonnet-5, the judge on claude-haiku-4-5.
- *"2 out of almost 800 went over? That's quite the dumb reason to cap that.. No?"* · *"Doit"* (2026-10-23, on
  the Claude CLI's default output cap of 32,000 tokens cutting two judge replies) — a call that names no
  output cap of its own gets the model's own maximum (`CLAUDE_CODE_MAX_OUTPUT_TOKENS` 128000, which
  Claude Code lowers to each model's cap).
- *"72 is the cut for what gets fed to the agent to generate the output, the allowed context-size from the query"* (2026-09-13) · *"apparently we got it right with lucene and vector for tgose 72k caps, make sure the artefact also follows that rule"* (2026-09-13) — the arm ranks everything; the 72,000-character cut is the harness's, applied after.
- *"the db only exists for the artefact and is created with it"* (2026-08-27) · *"vector and lucene sure as fuck shoulw never use the artefact or the graph DB, and there is a fucking reason thoes 3 files or off for the artefact"* · *"just dont use those chunks"* (2026-09-13) — the three metadata files' 61 chunks are out of the artefact's pool.
- *"so, perhaps update the DB with the actual new information so the db is the only thing beeing used?"* · *"yeah make the db current before anything else"* (2026-10-06) — the facet layer is read from the graph.
- *"dude, it MUST be asked of the DB, what the fuck is the point of this is its not actually using the db.."* (2026-10-07) — the retrieval is asked of the database per question, not worked out on arrays read out of it at start.
- *"tracability is the pointers to the actual data etc"* (2026-10-05) · *"thats the fucking pointers to the real data..."* · *"and you know... SAVING THAT"* (2026-10-08, on the abstract's "traceability indicators")
- *"yeah we are never using nvidia NIM again"* (2026-10-07, on the vector baseline's stored vectors having been made by the hosted endpoint) — the embedder is the local `nvidia/llama-nemotron-embed-1b-v2` from Hugging Face.
- The vector arm embeds the question when it is asked, timed and counted in the row; the evaluation's `eval_calls.jsonl` keeps every judge prompt as sent, gold answers included, in the run folder (his "yes" to both, 2026-10-08).
- *"this time it's all in serious, this is not a test, we are building the "final run" here, so including litterally all fucking metrics possible from the runs also"* (2026-10-07, on how the lucene and vector baselines are to be handled academically)
- *"we do NOT care about monetary cost, cost only means compute or tokens or time here, thats all we can actually compare"* (2026-10-08, on dollar figures reported per call)
- *"what i am talking about are "times, tokens, runtime, build cost" etc etc etc, ALL FUCKING DATAMETRICS"* · *"ragas are not goddamn metrics you fucking hobo, thats the evaluation system"* (2026-10-08) — "metrics" is the measured data of a run; RAGAS is the evaluation.
- *"we literally have ALL THE FUCKING DATA possibly available! From tokens in/out, times, stamps, DATAPOINTERS and so on and on and on.. YOU just have to make fucking sure that is KEPT every run.. It is so goddamn important"* (2026-10-07) — every run keeps all of it in its own folder, per question and per model call.
- *"you can't just have fucking smashed fields with no word or explanation to what they mean.."* (2026-10-09, on a run folder that explained none of its fields) — every run folder holds `FIELDS.md`, written by the harness from `prod/harness/fields.py`; an arm gives the words for what only it writes (`FIELDS` in its own file).
- *"That sounds indeed like you have fufkcing smashes a bunch of data together that does not belong together.."* (2026-10-20, on the artefact's `retrieval` adding the first call's and the embedder's tokens into one sum) — a cost is held one model at a time: a row's `retrieval` and the manifest's `build_stats` hold one entry per model, worked out from the call and build records; two models are never one number.

The data given away:

- *"the size and shit of everything you have created will stay on this fucking computer/repo, not something given away"* · *"its great to have everything as you made it, all links to everything, all the history and reasoning, it IS important.. for me, but not for them, comments on this or that, reason a datapoint was remade etc is only noise to them"* (2026-10-20) — the workbook holds only the values, at the level of a CSV, in a proper format; the run folders, the records, the corrections, the links and the reasoning stay in the repo.
- *"YOU are not the one choosing what should be or not in the fucking files dude"* · *"have you no sense of proper protocol for data science and research, some fucking academic rigor? you are just "picking" random shit.."* · *"ok, yes but no,make sure 1-8 is done and correct for the folders/data we have right now"* (2026-10-20) — the data follows research practice: raw data stays as recorded and what is derived is made by a kept script; nothing is selected by the agent; one table per kind of observation; one schema across the arms, an empty value saying why; a data dictionary; provenance with checksums; corrections visible; data left out only by his rule, written in with his words, or "no rule recorded".
- *"answering started at, finished? WHY!? WHY IN THE GODDAMN FUCK!?"* · *"these fucking fields you have are not only fucking impossible to descipher without the motherfucking key, are they even what i asked for!?"* (2026-10-20, on the first export: a key block in each file, the run's clock times, client flags and settings, short field names in nested blocks) — a column's name says what it holds and its unit, read without a key.
- `results`: one row per arm and question of the final runs on the hundred and on the 715: the question with HERB's reference answer and evidence record ids (`reference_answer`, `reference_context_ids`: what RAGAS scored against, read from `data/questions.jsonl`, the file every final run read by its hash), the RAGAS scores (with `string_presence_per_id`: RAGAS's StringPresence run on each item of HERB's reference list, one employee ID, PR link or URL per item, the share of the items the answer holds; empty for content and company questions; his *"StringPresence needs to be in it because that is exactly what we do, meaning its a subcategory of StringPresence"* · *"yup, dont have to mention that it is not a ragas tho, it actully is, we just run it differently, anyway, lets do this"* · *"yeah thats what he asked for, well didnt ask for urls actually but those we keep"*, 2026-10-28; and `string_presence_per_id_precision` and `string_presence_per_id_f1`: the same StringPresence the other way round, each employee ID, PR link or URL the answer gives, of the forms of the reference's items, looked for in the reference, and the F1 of the two, 0 when the answer gives none; the forms are the agent's own rule, read from the corpus; his *"Ok, f1 and presc it's just to do then i guess, if so, and you know exactly how and what he means, do it"*, 2026-10-29), the characters of retrieved context given to the answer model (`retrieved_context_characters`, his *"how am i not telling you that this is what i want?"*, 2026-10-22, on the analyst's question), and the times and tokens one model at a time; a column is a measure he named or an id. *"why the fuck are the failed tries in there?"* · *"correct this"* (2026-10-21) — a model call's time is its answering try; the seconds of failed tries are out of the call, the question and the run. *"answer seconds looks really fucked up btw, there is litterally no chance those times are correct for real.. take a serious look at them"* · *"do a selected test/fix for a bunch and see if its the correct way"* · *"doit"* (2026-10-27) — that try's time is the server's own (the CLI's `duration_api_ms`, without the program's start on our machine); an answer call or first call that started past the login's limit of claude-sonnet-5 input tokens has its arm's clean relation at its own output tokens (`model-call-time/1`, `/2` where tokens were corrected after it, and `/3` with the first request below; the limit, the relations and their check in each folder's `model_call_times.json`, `model_call_times_v2.json` and `model_call_times_v3.json`, the measurements under `output/research/2026-10-27-model-call-times/`). The agent's own choice under his /goal (*"i want the same methods for them"*, 2026-10-27), not his word on it: a question's search time is the same retrieval made again one question at a time on the laptop, never as the first question of a process (`search-time/2`, the `*__20261027_search_1worker` and `*__20261028_first_question_warm` folders), and every embedding counts by its time on the desktop's graphics card, one request after the other (`judge-embed-gpu-time/1`, `embed-gpu-time/3`). A call's tokens are the CLI's own counts (`zero-usage/3`, `judge-usage/1` and `/2`). *"do we really want the rejected answers?"* · *"yeah, first request"* (2026-10-28, on the answers that the CLI rejected for their form and the model wrote again in the same call) — such a call counts by its first request, its time and its tokens (`model-call-time/3`: the first request's share of the call's server time by the CLI's transcript of the call, read on the machine that made it with `output/research/2026-10-28-first-request/extract.py`, the numbers in each folder's `cli_transcript_requests.json`). A sha256 in a `corrections.json` is of the file's bytes as the tool wrote them on the laptop; git keeps LF line ends, so a checkout can hold the same content with other line ends.
- `run data`: first what is the same for the three arms, once, property and value (the dataset, its licence, the character limit and the models; *"cba adding interpreter, it's just the answer model"*, 2026-10-21); under it one row per property and one column per arm, the run's runtime and the evaluation's cost; under it the mean of each measure of `results` over an arm's 815 questions, one column per arm (his "in run data, put the averages for each arm for each metric", 2026-10-21). *"THE RUN TIME IS THE ADDED TIME FOR ALL THE THINGS IN THE FUCKING RUN"* (2026-10-22) · *"wall time? this is not a thing"* (2026-10-23) — every arm's run time is the time of all the things in it added, its questions' times, and its judging's time its judge calls' server times and RAGAS's embedding times added; never a clock over the run, over a question's judging or over calls that ran at once.
- `arm construction`: *"Do you think they give ANY fuck about how ANYTHING was done in the artefact unless they specifically ask for it?"* · *"I do NOT think this needs to be 3 different files.. Col with things, and then 3 cols, one for each arm, with that arm's "data" for those fields"* (2026-10-20) · *"Especially shit I did before I found a different way. I don't give a shit about the cost for other things, and they even less so.. The ONLY thing that matters, at all, is the iteration that ran the RAGAS"* (2026-10-21) — one row per property, one column per arm: the index, its size, its build time and each model's calls, tokens and seconds, counting only what built the index that the final runs read, nothing on how a build was done. A model's seconds are its calls' times added, as a run's, each by its answering try (the Opus calls from prompt to reply in the CLI's own transcripts: their server time was not recorded); lucene's and vector's builds are those their runs on the 715 read (one timer each).
- `key`, the last sheet: *"just clinically and explicitly say what each thing is … based on what the documentation say, do fucking NOT make your own interpretations here"* (2026-10-21) — each field's meaning and unit, from the documentation (RAGAS's own definitions).

How to work with him:

- *"check what the fucking CODE says holy shit"* · *"ALWAYS check the code, how is this unclear? it's the only thing telling the truth."* (2026-10-23, after the order the judge reads was looked for by matching texts in the run's prompts before the code was read) — a question about what the system does is answered from the code first.
- *"you write a really long thing that needs reflection on, especially by you, then you end it with a semi-irrelevant question, if I answer that, you will pretty much toss out all the other stuff from your prompt.. Doesn't that seem like a really sharp weakness in the harness?"* · *"Good, decided"* (2026-10-02) — a message carrying reflection, analysis or a design ends with no question; a question comes as its own short message after he has reacted.
- *"you DO know the core concepts we worked with, right? how about instead of dragging up the entire fucking ship and luggage of past ghosts you take a look at the concepts, compare them to what you are doing now or NOT doing now, figure out fitting application of those based on the core concepts i have been hammering for fucking ever"* · *"stop forcing me to course correct every goddamn fucking time"* (2026-10-04)
- *"so, how can i make you actually guild the fucking thing i want you to build instead of you building your own shit every time?"* (2026-10-05) — what is the agent's own choice in a build is said to him as such.
- *"you stopped everything? wtf dude, i want you to just fucking communicate what you are doing, you have been working for HOURS"* (2026-10-05)
- *"shesus the fuck you are babbling alot and saying very little"* (2026-10-06) · *"you are not speaking my language at all now..."* · *"dont give me a fucking bullet list.."* (2026-09-21)
- *"just dont do the "infinity-review" after, ok"* (2026-10-07)
- *"if you DO NOT UNDERSTAND, fucking get the information you need, ask me after you define the exact detail you dont get"* · *"dude, always do an internet search for the same concept also"* (2026-10-08) — a concept of his is first looked up in his own words and on the internet; the question to him comes after, and names the exact detail.
- *"Do absolutely fucking NOT never goddamn fucking EVER make up your own language, terms and explanations for shit I have already defined."* (2026-10-07, after "the chain", "place" and "stands out" were said for what the tags and the chunk descriptions hit, for scope, and for "where the truth seems to be"; his *"WHAT FUCKING CHAIN?"*)
- *"k? 72k is the only fucking k"* · *"ah, you mean clustering. see.. you made that really fucking confusing"* (2026-10-10, on "k = 5" said for the number of clusters) — in talk the number of clusters is written out.
- *"i want it as a skill so i can finish a sentence, statement, whole thing, with /rar meaning 'reflect and reason upon this'"* · *"both scope and CONTEXTUAL INTELLECT/AWARENESS is highly relevant here"* (2026-10-10)
- *"But you are just trying MY shit over and over.."* (2026-10-11, on a day of counts of his ideas only)
- *"You are really beeing as fucking lazy as possible now"* · *"Yet again:weak ass lazy fucking effort"* · *"no, i wanted a better explanation"* (2026-10-12, on tables handed over as the answer to "How does scope before or after affect that?") — a how-does-this-affect-that question is answered by saying what happens and why, in words.
- *"you are extremely unkotivated and unhelpful now.."* (2026-10-12, on a fault of the retrieval described and left there)
- *"honestly, i cant read anything you write anymore, everything is too much, stop fucking spamming me with unimportant information"* (2026-10-15)
- *"dont fucking use MY old words as some sort of fucking arguments or weight for YOUR arguments.. its my fucking thoughts.."* (2026-10-17, after his "shouldnt that enforce the relevance if its reach in many ways?" was met with a line of his from 10-05) — his earlier words are never used to argue against what he says now or to give weight to the agent's own point.
- *"my complaint is you forcing every new idea and concept into what has already been done in some fashion"* (2026-10-18, after a day where the 4-combo was built as one more re-ranking on the clouds' order with the old hand-over after it, the person edges were used only to reproduce the old hand-over, and the knee clouds kept the old steps) — a new concept of his is built on its own terms, not as one more term in the existing order.
- *"stop forcing this somewhere ffs. you will fucking notice when i am done discussing it.."* (2026-10-17, after answers that each ended by asking for a go to build or write) — while he discusses, no answer steers to a decision, a go or a build.
- *"back to the goddamn fucking conversation we have had several times already"* · *"talk about missing my point herer, that A D you did a fucking "job" instead.."* (2026-10-16, after the first was answered by building and running a judged comparison) — a call back to the conversation is answered by talking; nothing is built or run on it.
- *"the format of the outputs you think you have given me, when its broken up by "work you do" it fucking atrocious.. … sure, write it out as it comes i guess, but you really need to write it all together when you have "finished", also explain the steps you took"* · *"did you jsut give me the entire fucking conversation? i mean after my fucking prompt to your "final answer""* (2026-10-16, the second on a recap of the whole day given in answer to the first) — short notes may come during the work; the message that finishes the work on a prompt of his, also when it comes after a background count, gathers everything done and found since that prompt and the steps taken, and nothing from before it.
- *"ALWAYS synopsis first, dude, always structure your outputs when marginally larger than just a snippet in the academic way (not academic for real, but the concept) of the abstract first, aka the synopsis, the the shit you have, followed by the conclusion, so that if i WANT, i read the synopsis and then maybe conclusion and if i give fucks, i unfold the "content" and read that"* (2026-10-22) — an output larger than a snippet is the synopsis first, then the content, then the conclusion: the output style `Synopsis` (`~/.claude/output-styles/synopsis.md`, on the laptop and on the desktop).
- *"NO YOU FUCKING MORON, calling you autistic means you did not understand the fucking context of my words and just took them literally"* · *"we also need a way to make sure that the autistic interpretation you have all the time is softened because its fucking driving me insane, its great when we are doing code ok for specs etc... but when conversing? you not understanding context is borderline unusable"* (2026-10-22) — in conversation a message is read against the last exchange for what he means and answered at its size; word-for-word reading is for code, specs and data. In the output style `Synopsis`, section "Reading the user".
- *"dude, if shit are going to take this long for a fucking answer, despite you having the entire fucking mempalace at your fingertips, you NEED to use more fucking agents to work faster"* (2026-10-07) · *"why have you not given it a singular tiny command, to do 1 operation and NOTHING else? and when done, you ask a DIFFERENT agent to do another single small task, or wait, hey, an idea, DO THEM AT THE SAME TIME"* (2026-10-22, on one agent given a long chain of checks before a run) — a known command goes to a background command, not an agent; an agent gets one small task; separate tasks, lookups and reads start at the same time; a palace lookup is answered from what the search returns.

The second model:

- *"you need to make a new rule or hook or something that gives you a "conversation-agent" what doubts and challenges everything you say, i do not want to see your conversations, but i think you need to do that to get more reliable outputs, it may NOT be the same model as you are, and not haiku"* (2026-09-20) — the partner below: never the main session's model, never haiku.
- *"when you reflect and reason on this input, i want you to have a conversational partner of another model than yourself, the next highest available quality (like opus or sonnet on high) to not only ball with, but that can critique, argue or whatever with you about this"* (2026-09-21) — the `partner` agent (`.claude/agents/partner.md`), opened before a draft exists and continued with SendMessage.
- *"the partner cannot be "hard coded" it's important that it's not the "same model as the current agent""* · *"if it's fable, the partner is opus(high), if it's opus, partner is sonnet(high), if it's sonnet, parner is opus (low)"* (2026-09-21) — `model` is passed explicitly on every dispatch; main sonnet uses `partner-low` on opus.
- *"sure as fuck not repo-only, but i do want to be able to toggle it off"* (2026-09-21) — the hook (`~/.claude/settings.json` → `~/.claude/partner/hook.sh`, text in `~/.claude/partner/reminder.txt`) prints the rule every turn; he types `partner off` / `partner on` as a whole message.
- *"the challenger after? i am pretty sure that the partner was supposed to be the challenger also at the same time, i mean, that the function of the partner wat to be challenging etc.. no?"* · *"dude, dont use the other agent as a fucking draftchecker.. use it to converse with DURING"* · *"i mean, the partner can still be somewhat challenging etc.."* (2026-10-07) — one agent, the partner, talked with while the thinking is open, and it still doubts and argues there; no agent checks a finished draft.

## The concept, his words

Tags, facets and their weights:

- *"the tags have facetweights on the edge to the chunk saying how relevant they are according to that facet, and the facetweights from the QUERY, determines how many fucks the retrieval take to each tag's facets"* (2026-08-31) · *"how relevant the tag is to the chunk, according to EACH facet, and the query part says how much each facet matters for this query, THAT is the concept"* · *"what we are truly after here, is a semantic relationship, something that separates "depending on""* (2026-09-06)
- *"the wohle point of the facets, weights and all weights of the tags-chunks-files-query, are about "how strong/relevant is the connection for this specific query""* (2026-09-02)
- *"the chunk descriptions and the tags are supposed to work TOGETHER to find gold.. it's a combo.."* (2026-08-11)
- *"my point is hitting all the correct chunks is the first step, the second step is floating the correct ones"* (2026-10-03) — the routes hitting different chunks is the design: *"doesnt that mean that its fucking WORKING as intended?"*
- *"ok, but fuck it.. how about we keep it slim and clean instead and just let this iteration be what it is, the important part now is getting actual data tp my people"* (2026-10-16, on the May tagger having described and tagged each chunk of several posts from part of them) — the graph's tags and descriptions stay as built in this iteration.

The query side:

- *"it's querydesc, query, querytags, querytag-facets, right?"* (2026-09-29)
- *"the interpreter should describe the query as 'what type of content it's trying to find'"* (2026-09-14) · *"i think the actual thought would be "describe the content the query is looking for" as in, not trying to guess the exact content, but describe it, instead to make sure nothing is made up for forced so to speak, but also to keep it in the fitting dimension?"* (2026-10-06)
- *"I think we should make query tags from the actual prompt also"* (2026-10-02) — both tag lists are query tags.
- *"i would rather it did exactly as i wanted with the desc and tags"* (2026-10-06) — the first call writes the description and the tags, with no tree.
- *"what if we only ranked the tags by 1 out of the 4 facets? The interpreter doesn't have to rank their tags, it doesn't have to give numbers, it just have to say (which of the facets is most important to this tag for this question)"* (2026-10-09) — the first call names that facet per tag.

Tags and closeness:

- *"first you pick a fizzy value for fit of tags via the tag vs querytags embeddings, right? thats how you PICK the tags, when the tags are picked, how do we decide which matters for this query?"* (2026-09-06) · *"you are sorting the fucking tags.."* (2026-09-06)
- *"but duuuude.. OBVIOUSLY we should use the similarity way, that was what i thought we were doing all the goddamn time!"* · *"i mean litterally everything that has been embedded for the artefact should use this, not only the tags"* (2026-10-05) — like against like is embedded in the same mode on both sides. *"yes to the question"* (2026-10-05) — the raw question is embedded in question mode.
- *"just run the fucking correct embedder on the correct things, save that on the side and then fucking use THAT instead!?"* (2026-10-05)
- *"thats not what i meant, what i meant is that their relation to the promt-tags is whats relevant, their relationship to eachother doesnt matter at all?"* (2026-10-04)
- *"ok, but perhaps the range of closeness must be different and fully relative to that facets tags numberrange etc?"* · *"what matters is the fucking semantic relevance of that number for the tag"* · *"does 0.7 mean "pretty much the same meaning of the word" or "it's kinda spelled the same""* (2026-10-05)
- *"well, you have to be aware of the different scales of values between each thing"* (2026-10-04)
- *"so, the actual issue might be the embeddings using "passage" instead of "query".."* · *"i guess we need query on both query and retrieval"* · *"since there maybe is an actual range to the numbers now, we can actually pick or cluster or do something actually smart and it might fucking work this time"* · *"obviously new picking rules, but if there is an obvious main cluster, that is the one"* · *"it's not a retarded idea "i think" to have like "nothing alike", "somewhat", "middle", "quite alike" "super alike""* · *"just do a fucking exploration and see how many clusters it discovers"* (2026-10-08, on the tags and the querytags embedded behind "query: " and not "passage: ").
- *"Ah, dogleg decides? That is fine I think, no?"* (2026-10-08) — the number of clusters is where the curve bends, not a number given.
- *"the descriptions are "long text"!?"* · *"run the queryembed on them also and see what the diff is"* · *"doit, if you see no quality downside of it, do query"* (2026-10-08) — the chunk descriptions and the query description are behind "query: " too; everything embedded for the artefact is.

Counts:

- *"a chunk beeing supported by more parts, does not mean it's a better fit, thats different scales or things to measure"* (2026-09-10)
- *"i dont think its a good idea to let "amount of tags" make a chunk more important"* (2026-10-05)
- *"i mean, isnt it fairly fucking obvious that the chance of getting correct shit if the chunk has better good tags matching the query? it makes it kinda "built-in" then and does not need fucking aid"* (2026-10-05)
- *"by that logic, we dont even have to do anything … that order is by amount of chunks a tag has"* (2026-09-08) — a within-tag rank compared across tags is the tag's chunk count.

Structure and scope:

- *"That's the point, letting the graph structure tell which area the information can be found"* · *"the point is finding the areas, and let the chunks fill in the content, so don't have to dig too deep before"* · *"a name and OR a product or whatever, should still be a 'limited area'. the combination i mean"* (2026-09-14)
- *"i DO want the actual structure of the graph to matter.."* (2026-09-29)
- *"and float those chunks, if they dont match what the tags float etc, that just gives us width, and if they reinforce, thats is good too"* (2026-10-06)
- *"beeing specific about product is very "fitted" and unagnostic concept"* (2026-10-07, on the arm using only the product of a returned place)
- *"the abstract said "structural filtering".. that means we are fucking OK with doing pretty much whatever we want with scope beside absurd overfitting"* · *"i have been trying to skirt the thing to not be too heavy handed with it and had forgotten we fucing already said it like this!"* (2026-10-07) — scope may filter.
- *"no i think i actually mean as it was said, as a filter"* · *"that way we can gauge where the truth seems to be, and can thus cut "the others""* · *"Well, we can just cluster by scope and see if that gathers the correct scopes?"* · *"And perhaps keep minorities if same parents or something..?"* · *"the clustering here is just a gauge of where the most relevance seems to lie"* · *"thats why i said clustering tbh, to get the "largest clouds" of relevancy"* (2026-10-07) — scope filters: a chunk outside it is out of the pool; clustering what the tags and the chunk descriptions hit by scope gauges where the relevance lies.
- *"I did sure as fuck not mean that a single scope is chosen. If majority of something, BRANCH is chosen"* · *"the definition maybe should be "parent" or something to make it less fitted for this specific dataset"* (2026-10-09)
- The border: *"what if we allow names of people, products and channels to be tags frmo the query, but we add scopes as if they were tags for the comparison?"* · *"a match on one of those does NOT pick/boost a chunk, it picks/boosts a scope, atleast for the conversation we are having about it now"* (2026-10-06) · *"Well, what happened to making tags out of the topology? If tags from the query match one of those, something else happens."* (2026-10-07) · *"i mran, sure, whatever, if we take our latest best run, and do that part for scope instead, where does that levave us? do gold smoke"* (2026-10-11, on the product's own name standing word for word in every question of the hundred) · *"my point is, if it's "easy" to find when creating the graph from the dataset, then its reasonable to use, like the "filestructure" etc"* · *"well build this, go on"* (2026-10-19, on the border by the product's name being fitted, and on it matching only product names) — structure that the graph's build reads off the dataset, such as the file structure and the names it holds, is reasonable to use; the border is where the names of products, channels, people, customers and companies standing in the question meet, each name picking a scope and never a chunk (`name_border`).
- *"Why not take the first or first 2 kNN clusters or something? Aka making 2 clouds, one based on embedding nearness, and the other, of the same, based on scope, and we take cloudintersection as main scope(s)?"* (2026-10-10)
- *""the tags cannot set scope".. oh, cant they? are they not connected to chunks?"* (2026-10-10, on the agent's claim, made from a count of every chunk the picked tags touch) — the tags reach the scope through their chunks.
- *"because we have tried doing this concept with the tags guiding, right? and we have tried it with the chunks guiding? now i want to do the both, side by side, together, either cleanly, or overlapping cloads for each step"* (2026-10-10) — both sides guide in the same retrieval.
- *"dont use "more ai" in the artefact"* (2026-10-11) — the artefact makes no model call beyond the first call.
- *"so, actually, what fucking IS missing, is a REAL use of the graph format, where finally ending up somewhere should make you search the correct scopes no matter what desc or tags say etc.. ffs"* · *"because we both have these and things related to "persons" etc (or users) and nothing at all is actually using the graph"* · *"well, what i am thinking is that a "nearest" chunk etc could be used for search-start or search-range for that specific person or whatever pointer etc"* · *"or just see it as a loss? i am thinking perhaps my nearness idea with graphsearch is a play, i mean, we should use the fucking graph somehow.."* (on the PR batches that are described and tagged from their last pull request) · *"well, i think we want an agnostic search that, if it's correct chunk, stops there, but if not, actually does a search and semi-deterministically actually find.."* (2026-10-11, on the gold chunks whose own description and tags do not bring them up, and on the gold that is found and not floated) — said as what is missing and as a thought; where the person or pointer comes from (the nearest chunk's own records or the question) is not said.
- *"Okay perhaps we can make the scope clouds better. Perhaps we take several clouds. For example if there's a relevance cloud at the top for a specific scope, the combination is scope, and high value is supposed to be a sort of cloud, right? Perhaps we just take several such scope clouds? Or bad?"* · *"doing the cluster clouds could be a combination thing. We could first use both the clouds and then after, still limited by the chosen scope. Or perhaps you do the scope first and then you scope the cloud, meaning the clouds give extra weight to specific areas of the scope while perhaps still in the same branch."* (2026-10-11) — a cloud is a scope together with its high values; several of them, and as weight on areas inside the chosen scope.
- *"ah yes, fuck, TIME, we dont have time in the graph!?"* · *"should we not check time-nearness both to eachother and to "now" unless time is mentioned in query, then nearness to that? and by that i mean using it as a ranking-weight"* (2026-10-11, after the gold of a question was shown to lie on a few days) — nearness in time between chunks is the 4-combo's time (below); nearness to "now" or to a time the question names is not built.
- *"Dude, it is INSANE if the top chunk is NOT a gold!"* (2026-10-12, on the first delivered chunk being gold on 37 of the hundred)
- *"But dude, the combo should fucking work.. So, if we use the chunk-cloud, see if you can find a way to combo or lift with the tags"* (2026-10-12)
- *"so, perhaps persons edges shouldnt go to scope directly, but to chunks instead?"* · *"my point just is, stop adding shit beside node -> chunk"* · *"well then, rebuild it"* (2026-10-17, on the graph's employees being tied only to channels and products while the dataset names them in the chunks' posts) — a person edge is the person's node to the chunk, nothing added to it (`test/graph/build_person_edges.py`).
- *"at first i think we should use it to find the rest of the conversation frmo the chosen chunk"* · *"time, scope, entities, chunknearness?"* · *"ok, so we agree, that IS the 4-combo. Make sure that is actually known and the actual implementation."* (2026-10-17) — the 4-combo: from the chosen chunk, the rest of its storyline is narrowed by time (nearness in time: the smallest gap between a record of one chunk and a record of the other), scope (the same area), entities (the people it shares) and chunk nearness, across kinds of record. *"shouldnt that enforce the relevance if its reach in many ways?"* · *"not near eachother.. i think, near eachother, based on the query?"* · *"yeah"* (2026-10-17) — a chunk reached in many ways is the more relevant; chunk nearness is near each other in what the query asks about (two chunks close to the same query tags), not near in general (`v4_walk.storyline`).
- *"well, perhaps "far below the cut" isnt really a good place to pull shit from tho..?"* · *"so, since we do the clouds and narrowing before, perhaps we actually do a fuzzy cut at that stage?"* · *"ok, build the thing"* (2026-10-18, after the clouds were shown to be a fixed five-way split borrowed from the nearest-tag k) — each side's cloud is the chunks before the knee of its own closeness, as many as the closeness shows; the chunks in both clouds are the chosen chunks; the 4-combo reorders only inside the clouds and lifts nothing from below them. *"it may not"* (2026-10-23, on whether a tie may lift a chunk from below the clouds).
- *"isnt it perhaps more reasonable to take the nearest chunk depending on time and entities? meaning the most related, if there is no match, then perhaps no chunk, by no match i mean in the same scope, as in we are trying to detect if this chunk is part of a split content etc? so we get "the rest of the same content" ?"* (2026-10-18, on taking the chunk above and under) — from a chosen chunk, what continues the same content; nothing when nothing matches. *"it is as it is then, we cant overfit for that now"* (2026-10-18, on a conversation having no structure in the data: a Slack message is a flat record whose thread replies are empty, and a conversation is only the arm's own cut at the channel's long gaps).
- *"when we retrieve for a question in the artefact, we can up the weight, or autoinclude chunks that are part of the same split object from the strongest chunks or something like that"* · *"yes, this happens after shit has been chosen as "good fit" for the query"* (2026-10-22, on the graph's `part_index` on the parts of a split document or transcript) · *"aaah, yes, this continued document chunks is the "other half" of the slack and whatevers!"* (2026-10-22, on the hand-over's rule that a Slack conversation goes in whole where it first shows) · *"yeah, that is a shit solution you have implemented, ofc we do want only good chunks to do this, how do we pick those then?"* · *"chosen it is."* (2026-10-22) — the rest of a split document and the rest of a conversation are one idea for two kinds of record: a chosen chunk (in both clouds) that is a part brings its whole record, once, at its place; any other part goes in as only that part and is not counted (`_hand_over`).
- *"that sounds the most overfitted jank i have ever heard of, it really does that?"* · *"holy shit thats retarded"* · *"yes, remove them"* (2026-10-23, on the hand-over leaving out a channel apart, other projects' pull requests and talk about another project's pull request) — every record of each ordered chunk is handed over; nothing is left out (`_hand_over`).
- *"nope, if this is the only way, the link stuff is fucking out"* (2026-10-23, on a link between two records reaching the graph only if every mention the data holds became a relation between two chunks, built into the graph; his link is one thing mentioned in, or connected to, another, all ways, never a web address) — no link is followed and no link ties two chunks.

## The facets

His thesis, §6.4 (2026-05): *"Taggar organiseras i klustren ämne, entiteter, aktivitet,
temporalitet och evidens, så att materialet kan beskrivas från flera analytiska perspektiv.
Klustertillhörigheten lagras på relationen mellan segment och tagg snarare än på taggnoden,
eftersom samma taggnamn kan ha olika analytisk funktion beroende på kontext."*

- *"the facets are themed RELEVANCE weights"* (2026-06-27) · *"it does not say what kind of tag it is, it says how relevant it is, in light of that facet"* (2026-08-31)
- *"how tag is facet to chunk … for all facets"* (2026-09-08) — every facet value is per edge. *"This is about the RELEVANCE OF THE TAG TO THE CHUNK! ,... NOT about "whats happening to the tag""* (2026-09-15)
- *"i really do NOT want an llm judge involved in the creation of them in the graph"* (2026-06-27)
- The five on the graph's edges since 2026-10-06: topic, temporal, why, activity, concreteness.
- topic — *"how central is the tag to the topic of the chunk"* · *"'what the topic is about' sounds just like the chunk descriptions"* (2026-09-08): the tag's vector against the chunk description's.
- temporal — *"its not just about time or dates, its about the relation of time, now, then, soon, before"* (2026-09-15)
- *"this is about a fucking tag-chunk relationship, how does 'entities' possibly fit there?"* (2026-09-08) — entities is not a facet.
- *"perhaps we should have the order slightly fuzzy, meaning for a specific order, things can be called "equal" if within a certain range of eachother"* · *"let the fact that there is 5 facets do the work"* · *"let clustering hand me the k, those fixed numbers are enraging me"* (2026-09-06)
- *"my thinking is that the "main weight" on a tag, is the topic one, and the others adjust that weight depending on the relevance of a facet to the query"* (2026-09-18) · *"topic is also a fucking facet value.."* (2026-09-29)
- *"ok, i am ready to use ranking instead of actual weights, one can convert ranks to weights"* (2026-09-20) · *"hm, for the facets.. perhaps we just use them as ranking (the 4, not topic) based on the most important in order from the query, per tag?"* · *"why not just use the actual "real" value they have, the ranking?"* · *"well, multiplying it might not really actually represent their relationship tho"* · *"rank the TAGS, no, i am not supersure how we we that"* (2026-10-05)
- *"What fucking values, we did a ranking on them, check if the RANKING is meaningful"* (2026-10-14) · *"its a RANKING system.. so, jsut fucking try using the actual rank relationships?"* (2026-10-15) — the facet layer is read as a ranking.
- *"the facets were never supposed to carry the whole weight themselves, they are supposed to influence the already existing relationship for chunks and tags so to speak"* (2026-10-15) · *"we somehow need to put the relative relation there too, not just "yeah, its the most important facet of all the tags here" but what if it's still quite fucking unimportant"* (2026-10-16) · *"YOU CANNOT FORCE THEM TO TRY AND CHANGE THE FUCKING ORDERS"* (2026-10-16) — the facets influence the closeness of tag and chunk; they do not make the order.
- *"go"* (2026-10-19, on: the facet per query tag, not one per question; the facet net is not read on the question side, where its numbers stand on nothing; the first call names, per tag, the facet that matters most for it and says whether that facet matters for the tag at all)
- *"i am thinking you have converted them to either a number, or just made arbitrary decisions for them"* · *"and you never stopped to think that perhaps how YOU converted the ranks was the fucking issue?"* (2026-10-19) — the facets' ranks are compared as ranks, never turned into a size and added to a cosine.
- *"how about they get a RELATIVE increase in importance, based on their relative rank compared to that chunk, based on the chosen facet? as in, the chunks are chosen first based on similarity, then that "most similar" IS a rank, and then that rank list is compared to the facets and is adjusted for relative rank"* · *"well thats the fucking point, that i goes both ways..?"* · *"type of record? who gives a shit.. we know that from scope.."* · *"ok, but can we make them adaptive easily deterministically?"* · *"well do that then"* (2026-10-19, the last three on the edges' facet values being mostly the record kind and the tag's own level) · *"thats why i fucking asked you to find the actual relationship to what gets added and what gets lost with the facets, to see what they actually affect, and thus be able to maybe do it adaptive"* · *"ok, do that and run a smoke?"* (2026-10-19, on: the chunks the facets push out hold gold most often when their tag is the query tag's own phrase) — each chunk's edge to its closest tag gets a standing in the named facet, read only against the same graph tag's other edges on chunks of the same kind (above, the same, below); an edge whose graph tag is the query tag's own phrase never stands below; the chunk moves one closeness level nearer or farther by its standing, and the tags' cloud, of the size its knee gives, takes the chunks by moved level (`v4_walk.closest_edge_standing`, `cloud_combo`'s `standing`).
- *"we will NOT use your random made up 'check words'"* (2026-09-08) · *"NEARNESS, we cant fucking use explicit shit"* (2026-09-09) · *"Well that was fucking not the concept"* (2026-09-14, on word counts as facet values)
