# CLAUDE.md

Only two kinds of text are facts here: his own sentences, quoted with their date, and what a
command prints. What an arm does is read from its file; what the graph holds is read by
querying it. Any other sentence, this file included, is a claim until checked.

## This file

*"wtf, day by day record in the claude.md? wtf?"* · *"yeah, clean that shit up"* ·
*"dude why carry alot for no reason?"* (2026-10-07)

It holds his rules and his concept in his own sentences, and where things are. Nothing else
goes in: no record of a conversation, no run number, no review finding, no build history, no
"what was done today". A line is added only when he states a new rule or changes the concept:
his words, the date, one line. What he said is in the palace and the session transcripts; the
numbers are in the run folders and under `output/research/`.

## Where

- `prod/` — the finished system: `harness/`, `eval/`, `arms/` (lucene, vector, hybrid), `run.py`,
  `tests/`. `test/` — the artefact in progress: `arms/` (every artefact arm), `artefact/` (the
  rebuild), `graph/` (db, builders, facet tools), `tests/`. `python prod/run.py --arm <arm> --set <set>`
  from the repo root loads arms from both. Runs and their manifests in `output/`; data in `data/`.
- The artefact (one path since the clean-up of 2026-10-17, his *"yes wwe are creating the final
  clean artefact now"*): `test/arms/artefact_v4.py` (the arm: `name_border` sets the border from
  the names of products, channels, people, customers and companies (a person's or customer's id
  too) that stand in the question, asked of the graph per question, each name picking a scope
  and never a chunk (a person, customer or company the parents of the chunks it is tied to), names
  of one kind adding up,
  kinds narrowing each other and a kind that would leave nothing set aside (`border_of`), no name
  no cut; `cloud_combo` makes the two clouds inside it, each
  side's cloud the chunks before the knee of the upper half of its own closeness (the median is the
  agent's choice), and the chunks
  in both clouds are the chosen chunks; `closest_edge_standing` gives each chunk's edge to its
  closest tag a standing in the facet the first call names for that query tag, read against the
  same graph tag's other edges on chunks of the same kind (above, the same, below; the query tag's
  own phrase never below), and the tags' cloud, of the size its knee gives, takes the chunks by
  their level of closeness moved one by the standing; `closeness_places` gives the tags side's
  places by closeness, and inside a step the tags side's rank and the description side's rank
  count equally, `storyline` is the 4-combo that orders the rest of the clouds by how
  strongly it is tied to the chosen chunks (the graph asked per question, `STORYLINE_CYPHER`) and
  lifts nothing from below the clouds, `_hand_over` leaves out channels apart and other projects'
  pull requests by the graph's people (`product_persons`, read through the person-to-chunk edges)
  and talk about another project's pull request by the links in its messages; everything the
  order is made of is asked of the graph per question, `_ask_graph`, and the start of a run only
  checks and counts the graph),
  `test/artefact/v4_walk.py` (the arithmetic behind it), `test/artefact/query_content.py` (the one
  model request, the first call), `test/graph/build_cost.json` (what building the graph cost, step
  by step from the build records; the arm writes it into each run's manifest, `index_info`, and
  one entry per model into its `build_stats`, `build_stats_from_cost`; its recount against every
  record it names is `test/graph/build_cost_check.json`, and every build record with its hashes
  `test/graph/build_records.json`), `test/graph/build_person_edges.py` (the person-to-chunk edges),
  `test/graph/build_chunk_times.py` (each chunk's records' own times, `times`; the 4-combo's gap
  in time is the smallest gap between a record of one chunk and a record of the other),
  `test/graph/build_structure_names.py` (each structure node's `name` and `name_keys`, read through
  its pointer), `test/graph/build_customer_edges.py` (customer-to-chunk edges where a record carries
  the customer's id). No count of clusters is given in the arm's order: every near group is read
  off where the upper half of its list bends (the half is the agent's choice); a channel's
  conversations are its gaps cut in two.
  `HERB_V4_OFFLINE` refuses model calls. The code as it stood before the clean-up, older steps
  included: `output/code_before_final_cleanup/20261017T032817Z/`; before the 4-combo:
  `output/code_before_4combo/20261017T210436Z/`; before the knee clouds:
  `output/code_before_knee_clouds/20261018T013204Z/`; before the border by every structure name:
  `output/code_before_structure_names/20261019T011742Z/`. What a run used: its `run_manifest.json` and each
  row's `meta`.
- `finished_data/` — the data given away, one workbook and nothing else: `finished_data.xlsx`
  (sheets `questions`: one row per arm and question of the final runs on the hundred, with the
  RAGAS scores and the times and tokens one model at a time, a column a measure he named or an id;
  `run`: two tables, first what is the same for the three arms, once, property and value (the
  dataset, its licence, the character limit and the models, the interpreter not named apart: his
  *"cba adding interpreter, it's just the answer model"*, 2026-10-21), under it one row per
  property and one column per arm, the run's runtime and the evaluation's cost;
  `construction`: one row per property, one column per arm, the index, its size, its build time
  and each model's calls, tokens and seconds, counting only what built the index that the final
  runs read, nothing on how a build was done; `key`). Values only, the key sheet last. Made by
  `tools/export_finished_data.py` (needs openpyxl) from the three final run folders and
  `test/graph/build_cost.json`; the export stops on any value that does not line up.
- `docs/ENVIRONMENT.md` — the machines, the Neo4j start, the model lane and how many calls this
  laptop holds at once. `docs/canon/raw/user_turns.jsonl` — his typed messages
  (`tools/canon_extract.py`); archive, nothing reads it.
- `docs/record/CLAUDE_md_until_2026-10-07.md` — this file as it stood before the cut: his turns,
  the answers and the run numbers, day by day. Read it only when a question needs it. Nothing is
  added to it.
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
- Runs: `ls output/k=chars`. The artefact's final run on the hundred (his "build", 2026-10-20):
  `artefact_v4__gold100__cb72000__20261020T041923Z` (commit `0c082a3` from a clean checkout,
  `GRAG-Job-0c082a3`, one question at a time, the first call and the embeddings made in the run,
  the graph's build cost in its manifest). The two baselines on the hundred:
  `lucene__gold100__cb72000__20261008T234209Z` and `vector__gold100__cb72000__20261017T061242Z`
  (commit `fbc2f22` from a clean checkout, one question at a time). Each folder's `FIELDS.md` says
  what it holds (every field's words, its type and counts in the folder, and what was left out and
  on whose word) and its `corrections.json` what was corrected after the run: in all three on
  2026-10-20 the cost held one model at a time, the artefact's search time without its model
  calls, the build cost per model, the artefact's graph counted and its file hashes as git holds
  them (`tools/correct_usage_by_model.py`); in lucene before that the laptop's sleep. Across arms
  `context_recall_id` and `context_precision_id` compare (both count record ids); the nonllm
  pair is within-arm (counted per delivered text).
- A run: `python prod/run.py --arm artefact_v4 --set gold|10smoke --char-budget 72000 --workers 6
  --out <folder>`; the same command into the same folder resumes. `--retrieval-only` makes no
  answer and no judging; `--flag HERB_V4_OFFLINE=on` refuses any model call.
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

What may be done:

- Nothing built, run, or written to the database without his words naming it; a "yeah" is not a go (2026-09-03).
- *"Unless i litterally tell you its ok or i want to do this, you do NEVER just "run ahead" if you have something unsettled"* (2026-10-07, after "Three things in the build are mine … Stop me if any is wrong" was followed by building) — an unsettled point stops the work and is put to him; "stop me if wrong" is not his ok.
- *"ok, obviously switch it on ALWAYS switch on the newest built thing unless stated otherwise"* (2026-09-07)
- *"only make a switch when i specifically have asked for a "run both and see" or something like that.."* (2026-10-07) — a change replaces the old behaviour; the old one is in git.
- *"Dude, if there are no model call.. Just fucking run it.."* (2026-10-11, on a retrieval-only hundred that was offered and not run) — a run that makes no model call is run without asking.
- A comment says what the code does; his sentence goes in only where it is the reason, as one line (his "yes", 2026-10-07).
- *"the fucking dokumentation needs to reflect reality, at all times.."* (2026-10-17, after the 4-combo was written into this file as if built) — a sentence about what is built, what the arm does or where a thing is, is changed in the same turn as the change it describes.
- *".. do the fucking 100th also.. stop beeing satisfied with an incomplete run"* (2026-10-06)
- *"no skips allowed"* (2026-10-08, on a test run that reported 1 skipped and five test files that did not load)
- *"if our history had a great solution for this, we would not still be working on it"* (2026-09-08) — restoring deleted code is not work.
- *"i am certain now that you have in fact NOT retrieved the facet concepts, you have found the v3 retrieval interpreter concepts"* · *"you have to look in the fucking git"* (2026-09-08) — the concept is in the initial commit and the thesis, not in later design docs.
- No agent writes a sentence about the system for a later reader (2026-09-04).

The harness and the data:

- *"but you are supposed to use a headless mode with constructed in and outputs, there is supposed to be fucking NOTHING more sent to the model than that"* (2026-10-05) — every model call goes through `prod/harness/chat.py` with `--safe-mode`, `--tools ""` and `--system-prompt`.
- *"Obviously both the fucking in AND output needs to be constructed! Why the fuck else do you think we are running headless!?"* (2026-10-07, on calls that sent the question raw and asked for JSON in words)
- *"wtf do the judges have to do with this? they are RAGAS, we cant do shit about those"* (2026-10-07) — the constructed-call rule is for the harness's own calls; the judge's prompts are RAGAS's. *"we have no control over the judges, stop fucking trying to affect the judges"* (2026-10-08, on the CLI's own system prompt going along with every judge call) · changed the same day, after RAGAS's own docs were read (RAGAS writes the prompts and the scoring; the judge model and how it is called are the user's): *"obviously we need to make sure that shit is also done correctly then"* (2026-10-08) — the judge calls are ours to send correctly too; RAGAS's prompts and scoring stay RAGAS's.
- *"yeah, thats fine, go ahead then"* (2026-10-09, on taking the account's e-mail address out of every call, which changes the login) — the lane's CLI runs under its own config folder (`~/.claude-herb-lane`) and logs in with the token of `.env`; a call without the token is refused.
- *"yes, they get those fields!"* (2026-10-09, on the fields of a record that lucene's and vector's text left out: a document's author, date and link, a transcript's participants and date, a PR's author, reviewers, state, dates and link, a Slack message's time) — a baseline unit's text is the record written the way the benchmark's own code writes it (`prod/harness/record_text.py`).
- *"yes, sonnet on those, sonnet used the vector and lucene too, right?"* (2026-10-06) — the querytagger and the generator run on claude-sonnet-5, the judge on claude-haiku-4-5.
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
- *"the size and shit of everything you have created will stay on this fucking computer/repo, not something given away"* · *"its great to have everything as you made it, all links to everything, all the history and reasoning, it IS important.. for me, but not for them, comments on this or that, reason a datapoint was remade etc is only noise to them"* (2026-10-20) — the data given away (two files per arm: the runs and the construction) holds only the values, at the level of a CSV, in a proper format; the run folders, the records, the corrections, the links and the reasoning stay in the repo. *"answering started at, finished? WHY!? WHY IN THE GODDAMN FUCK!?"* · *"these fucking fields you have are not only fucking impossible to descipher without the motherfucking key, are they even what i asked for!?"* (2026-10-20, on the first six files: a key block in each, the run's clock times, client flags and settings, short field names in nested blocks) — a column's name says what it holds and its unit, read without a key. *"Do you think they give ANY fuck about how ANYTHING was done in the artefact unless they specifically ask for it?"* · *"I do NOT think this needs to be 3 different files.. Col with things, and then 3 cols, one for each arm, with that arm's "data" for those fields"* (2026-10-20, on the construction workbooks that listed every part of the artefact's build) — the construction is one table, a row per thing and a column per arm, and holds nothing on how a build was done. *"Especially shit I did before I found a different way. I don't give a shit about the cost for other things, and they even less so.. The ONLY thing that matters, at all, is the iteration that ran the RAGAS"* (2026-10-21, on build costs that added in work replaced later, trials and tests) — the construction counts only what built the index that the final runs read.
- *"YOU are not the one choosing what should be or not in the fucking files dude"* · *"have you no sense of proper protocol for data science and research, some fucking academic rigor? you are just "picking" random shit.."* · *"ok, yes but no,make sure 1-8 is done and correct for the folders/data we have right now"* (2026-10-20) — the data follows research practice: raw data stays as recorded and what is derived is made by a kept script; nothing is selected by the agent; one table per kind of observation; one schema across the arms, an empty value saying why; a data dictionary; provenance with checksums; corrections visible; data left out only by his rule, written in with his words, or "no rule recorded".

How to work with him:

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

The second model:

- *"you need to make a new rule or hook or something that gives you a "conversation-agent" what doubts and challenges everything you say, i do not want to see your conversations, but i think you need to do that to get more reliable outputs, it may NOT be the same model as you are, and not haiku"* (2026-09-20) — first built as the `challenger` agent run on finished drafts; since his 2026-10-07 words below the doubting is the partner's, during the thinking.
- *"when you reflect and reason on this input, i want you to have a conversational partner of another model than yourself, the next highest available quality (like opus or sonnet on high) to not only ball with, but that can critique, argue or whatever with you about this"* (2026-09-21) — the `partner` agent (`.claude/agents/partner.md`), opened before a draft exists and continued with SendMessage.
- *"the partner cannot be "hard coded" it's important that it's not the "same model as the current agent""* · *"if it's fable, the partner is opus(high), if it's opus, partner is sonnet(high), if it's sonnet, parner is opus (low)"* (2026-09-21) — `model` is passed explicitly on every dispatch; main sonnet uses `partner-low` on opus.
- *"sure as fuck not repo-only, but i do want to be able to toggle it off"* (2026-09-21) — the hook (`~/.claude/settings.json` → `~/.claude/partner/hook.sh`, text in `~/.claude/partner/reminder.txt`) prints the rule every turn; he types `partner off` / `partner on` as a whole message.
- *"the challenger after? i am pretty sure that the partner was supposed to be the challenger also at the same time, i mean, that the function of the partner wat to be challenging etc.. no?"* · *"dude, dont use the other agent as a fucking draftchecker.. use it to converse with DURING"* · *"i mean, the partner can still be somewhat challenging etc.."* (2026-10-07) — one agent, the partner, talked with while the thinking is open, and it still doubts and argues there; no agent checks a finished draft. The hook text and the agent files say the same since that day.
- *"dude, if shit are going to take this long for a fucking answer, despite you having the entire fucking mempalace at your fingertips, you NEED to use more fucking agents to work faster"* (2026-10-07) — lookups and reads go out in parallel; a palace lookup is answered from what the search returns.

## The concept, his words

Tags, facets and their weights:

- *"the tags have facetweights on the edge to the chunk saying how relevant they are according to that facet, and the facetweights from the QUERY, determines how many fucks the retrieval take to each tag's facets"* (2026-08-31)
- *"the wohle point of the facets, weights and all weights of the tags-chunks-files-query, are about "how strong/relevant is the connection for this specific query""* (2026-09-02)
- *"the chunk descriptions and the tags are supposed to work TOGETHER to find gold.. it's a combo.."* (2026-08-11)
- *"how relevant the tag is to the chunk, according to EACH facet, and the query part says how much each facet matters for this query, THAT is the concept"* · *"what we are truly after here, is a semantic relationship, something that separates "depending on""* (2026-09-06)
- *"my point is hitting all the correct chunks is the first step, the second step is floating the correct ones"* (2026-10-03) — the routes hitting different chunks is the design: *"doesnt that mean that its fucking WORKING as intended?"*
- *"ok, but fuck it.. how about we keep it slim and clean instead and just let this iteration be what it is, the important part now is getting actual data tp my people"* (2026-10-16, on the May tagger having described and tagged each chunk of several posts from part of them) — the graph's tags and descriptions stay as built in this iteration.

The query side:

- *"it's querydesc, query, querytags, querytag-facets, right?"* (2026-09-29)
- *"the interpreter should describe the query as 'what type of content it's trying to find'"* (2026-09-14) · *"i think the actual thought would be "describe the content the query is looking for" as in, not trying to guess the exact content, but describe it, instead to make sure nothing is made up for forced so to speak, but also to keep it in the fitting dimension?"* (2026-10-06)
- *"I think we should make query tags from the actual prompt also"* (2026-10-02) — both tag lists are query tags.
- The readings on a query tag: *"maybe their relevance to the query-description"* · *"Yes, I think that's the play"* (2026-09-14) — per tag, per facet, how relevant the tag is to the described content seen through that facet.
- *"i would rather it did exactly as i wanted with the desc and tags, and then perhaps another call used that info + tree/scope"* (2026-10-06) · *"yup, like this"* (2026-10-07) — the first call writes the description and the tags with no tree; a second call gets the question, that description, those tags and the tree, and returns the scope. Built as the arm's `call` step; taken out in the clean-up of 2026-10-17.

Tags and closeness:

- *"first you pick a fizzy value for fit of tags via the tag vs querytags embeddings, right? thats how you PICK the tags, when the tags are picked, how do we decide which matters for this query?"* (2026-09-06) · *"you are sorting the fucking tags.."* (2026-09-06)
- *"tags are the "main" path, not chunk_desc"* (2026-09-29)
- *"but duuuude.. OBVIOUSLY we should use the similarity way, that was what i thought we were doing all the goddamn time!"* · *"i mean litterally everything that has been embedded for the artefact should use this, not only the tags"* (2026-10-05) — like against like is embedded in the same mode on both sides. *"yes to the question"* (2026-10-05) — the raw question is embedded in question mode.
- *"just run the fucking correct embedder on the correct things, save that on the side and then fucking use THAT instead!?"* (2026-10-05)
- *"thats not what i meant, what i meant is that their relation to the promt-tags is whats relevant, their relationship to eachother doesnt matter at all?"* (2026-10-04)
- *"ok, but perhaps the range of closeness must be different and fully relative to that facets tags numberrange etc?"* · *"what matters is the fucking semantic relevance of that number for the tag"* · *"does 0.7 mean "pretty much the same meaning of the word" or "it's kinda spelled the same""* (2026-10-05) — what counts as "equally close" is not ruled.
- *"well, you have to be aware of the different scales of values between each thing"* (2026-10-04)
- *"so, the actual issue might be the embeddings using "passage" instead of "query".."* · *"i guess we need query on both query and retrieval"* · *"since there maybe is an actual range to the numbers now, we can actually pick or cluster or do something actually smart and it might fucking work this time"* · *"obviously new picking rules, but if there is an obvious main cluster, that is the one"* · *"it's not a retarded idea "i think" to have like "nothing alike", "somewhat", "middle", "quite alike" "super alike""* · *"just do a fucking exploration and see how many clusters it discovers"* (2026-10-08, on the tags and the querytags embedded behind "query: " and not "passage: ").
- *"what if we do all facets and only take the top cluster for each?"* · *"perhaps all query tags should be clustered at the same time? One facet at a time.."* · his "Yes" to: per question, every querytag's closeness is clustered in one list and the top cluster is the picked tags; the picked tags' edges are clustered one facet at a time and each facet's top cluster is the "equal" range in the multi-key order (2026-10-08) — the 5% same-thing level is gone; the clustering on the line (least squares) is the agent's choice. *"Ah, dogleg decides? That is fine I think, no?"* (2026-10-08) — the number of clusters is where the curve of the fit bends, not a number given.
- *"the descriptions are "long text"!?"* · *"run the queryembed on them also and see what the diff is"* · *"doit, if you see no quality downside of it, do query"* (2026-10-08) — the chunk descriptions and the query description are behind "query: " too; everything embedded for the artefact is.

Counts:

- *"a chunk beeing supported by more parts, does not mean it's a better fit, thats different scales or things to measure"* (2026-09-10)
- *"i dont think its a good idea to let "amount of tags" make a chunk more important, just as i dont think "amount of closely related chunks" makes a chunk more important"* (2026-10-05)
- *"i mean, isnt it fairly fucking obvious that the chance of getting correct shit if the chunk has better good tags matching the query? it makes it kinda "built-in" then and does not need fucking aid"* (2026-10-05)
- *"by that logic, we dont even have to do anything … that order is by amount of chunks a tag has"* (2026-09-08) — a within-tag rank compared across tags is the tag's chunk count.

The facets in the order:

- *"the queryfacets is the order of sorting-prio based on facets for tags, so, if facet 1 is most important for a tag from query, that is sorting order 1, and descending meaning that they are "sorted".. like.. multi-key sort or multi-level sorting."* (2026-09-05)
- *"perhaps we should have the order slightly fuzzy, meaning for a specific order, things can be called "equal" if within a certain range of eachother"* · *"let the fact that there is 5 facets do the work"* · *"let clustering hand me the k, those fixed numbers are enraging me"* (2026-09-06)
- *"Of course they don't change with the question, that's why we have the interpretor put a value on its tags in relation to the query... So we can weight-adjust the facets based on that.."* (2026-09-13)
- *"my thinking is that the "main weight" on a tag, is the topic one, and the others adjust that weight depending on the relevance of a facet to the query"* (2026-09-18) · *"topic is also a fucking facet value.."* (2026-09-29)
- *"ok, i am ready to use ranking instead of actual weights, one can convert ranks to weights"* (2026-09-20)
- *"hm, for the facets.. perhaps we just use them as ranking (the 4, not topic) based on the most important in order from the query, per tag?"* · *"why not just use the actual "real" value they have, the ranking?"* · *"well, multiplying it might not really actually represent their relationship tho"* · *"rank the TAGS, no, i am not supersure how we we that"* (2026-10-05)

Structure and scope:

- *"Products chunks? That's you determining something before it even is a thing, you fucking do NOT know that information beforehand."* · *"I dislike naming scope from the query"* (2026-09-14)
- *"That's the point, letting the graph structure tell which area the information can be found"* · *"the point is finding the areas, and let the chunks fill in the content, so don't have to dig too deep before"* · *"a name and OR a product or whatever, should still be a 'limited area'. the combination i mean"* (2026-09-14)
- *"no, i think this is better used later in the line, if at all, i mean, i DO want the actual structure of the graph to matter.."* (2026-09-29)
- *"instead of "finding or naming" scope like how you are trying to do it, i think it's better to show the model the topology of the graph? i mean, the filetree-ish"* · *"i mean product isnt the only fucking scope?"* · *"but yeah, the point is inferring scope from query based on tree?"* (2026-10-06)
- *"and float those chunks, if they dont match what the tags float etc, that just gives us width, and if they reinforce, thats is good too"* (2026-10-06)
- *"beeing specific about product is very "fitted" and unagnostic concept"* (2026-10-07, on the arm using only the product of a returned place)
- *"the abstract said "structural filtering".. that means we are fucking OK with doing pretty much whatever we want with scope beside absurd overfitting"* · *"i have been trying to skirt the thing to not be too heavy handed with it and had forgotten we fucing already said it like this!"* (2026-10-07) — scope may filter.
- *"i THINK its a viable idea to use the structure last, as a "vertical cut" making the pool more narrow?"* · *"no i think i actually mean as it was said, as a filter"* (2026-10-07) — structure comes last and filters: a chunk outside the scope is out of the pool. *"that way we can gauge where the truth seems to be, and can thus cut "the others""* · *"yeah, but i dont think we use the second call if we do this, right?"* · *"Well, we can just cluster by scope and see if that gathers the correct scopes?"* · *"And perhaps keep minorities if same parents or something..?"* · *"the clustering here is just a gauge of where the most relevance seems to lie"* · *"thats why i said clustering tbh, to get the "largest clouds" of relevancy"* (2026-10-07) — the scope is gauged from what the tags and the chunk descriptions hit, by clustering those by scope; asked as questions. Built since as older steps (clouds, cluster, levels, hits) beside the second call (`call`); all of them taken out in the clean-up of 2026-10-17.
- A side thought, no go: *"what if we allow names of people, products and channels to be tags frmo the query, but we add scopes as if they were tags for the comparison?"* · *"a match on one of those does NOT pick/boost a chunk, it picks/boosts a scope, atleast for the conversation we are having about it now"* (2026-10-06)
- *"what if we force the n of k in the kNN instead?"* · *"remove your dogleg and clustering package then for kNN first of all"* · *"the dogleg and the main cluster code are commented out. No?"* · *"build it and explore what k=3 to 7 mean"* (2026-10-09) — the pick is each query tag's k nearest graph tags; the dogleg stayed in the file switched off until the clean-up of 2026-10-17 took it out.
- *"we DID build that neural net for judging the facets, why the fuck is the model doing that work then?"* · *"what we need to carefully make, is the "chunk text" equivalent from the query"* (2026-10-09) — the query tags' facet readings come from the facet instrument on (query tag, question + description), not from the model.
- *"I am pretty fucking sure we don't need that second call at all based on the concept I suggested"* · *"1. We do the tag embedding check, etc. 2. We check on those and show them what the majority has on their scope stats. 3. We pick that scope. 4. We cut everything that isn't fit into that scope. 5. We actually check the tags, clusters, facets, and all that shit."* · *"I did sure as fuck not mean that a single scope is chosen. If majority of something, BRANCH is chosen"* · *"the definition maybe should be "parent" or something to make it less fitted for this specific dataset"* (2026-10-09)
- *"what if we only ranked the tags by 1 out of the 4 facets? The interpreter doesn't have to rank their tags, it doesn't have to give numbers, it just have to say (which of the facets is most important to this tag for this question)"* (2026-10-09) — the first call names that facet per tag; the arm reads it since 2026-10-19 (see The facets).
- *"What if chunk desc and their scope sets the first border? Then tags do their thing?"* · *"Stop, no, I did not mean it like that"* (on the build that followed: the 50 nearest chunk descriptions, their majority branch kept) · *"50 was random.. Why not take the first or first 2 kNN clusters or something? Aka making 2 clouds, one based on embedding nearness, and the other, of the same, based on scope, and we take cloudintersection as main scope(s)?"* (2026-10-10) — asked, not built.
- *""the tags cannot set scope".. oh, cant they? are they not connected to chunks?"* (2026-10-10, on the agent's claim, made from a count of every chunk the picked tags touch) — the tags reach the scope through their chunks.
- *"because we have tried doing this concept with the tags guiding, right? and we have tried it with the chunks guiding? now i want to do the both, side by side, together, either cleanly, or overlapping cloads for each step"* (2026-10-10) — both sides guide in the same retrieval. Overlapping clouds for each step was built that day (`v4_walk.both_sides`, step `both`) on his *"biuld and goldsmoke"* to the agent's ask that named the order after the overlap; "cleanly" is not built. His verdict on it: *"did you just make up some shit because you didnt understand a specific step?"* (the scope cloud there was the agent's average per scope, not his "majority"). Taken out in the clean-up of 2026-10-17.
- *"lets pretend that the current baseline is just 50% tags and 50% desc"* · *"can our structure or scope help fix this somehow? /goal reason and research until you find an actual viable solution for this (not just shitty comparisons locally), so if you actually find something, implement that, run the 10goldsmoke, if that actually looks better, du the full 100"* (2026-10-11) — what that order produced was the map step: the border from the chunk descriptions' closeness to the question, then one more model call that reads the border's map (parts, chunks, descriptions, tags) and names the chunks, then the rest in turn. It is the agent's find and not his concept: a model orders the chunks, the facets are unused, and the description texts are read from a side file because no database holds them. Taken out in the clean-up of 2026-10-17.
- *"dont use "more ai" in the artefact"* (2026-10-11, after the report on the map step) — the map call is one more model call in the artefact; nothing is built on it.
- *"so, actually, what fucking IS missing, is a REAL use of the graph format, where finally ending up somewhere should make you search the correct scopes no matter what desc or tags say etc.. ffs"* · *"because we both have these and things related to "persons" etc (or users) and nothing at all is actually using the graph"* · *"well, what i am thinking is that a "nearest" chunk etc could be used for search-start or search-range for that specific person or whatever pointer etc"* · *"or just see it as a loss? i am thinking perhaps my nearness idea with graphsearch is a play, i mean, we should use the fucking graph somehow.."* (on the PR batches that are described and tagged from their last pull request) · *"well, i think we want an agnostic search that, if it's correct chunk, stops there, but if not, actually does a search and semi-deterministically actually find.."* (2026-10-11, on the gold chunks whose own description and tags do not bring them up, and on the gold that is found and not floated) — said as what is missing and as a thought; nothing is built on it yet, and where the person or pointer comes from (the nearest chunk's own records or the question) is not said.
- *"i mran, sure, whatever, if we take our latest best run, and do that part for scope instead, where does that levave us? do gold smoke"* (2026-10-11, on the product's own name standing word for word in every question of the hundred) — the border was every branch of the tree whose name stands in the question, no model call; since 2026-10-19 (his "well build this, go on") it is every structure name standing there (`name_border`, see "Where"). The chain's order inside it and the map step were taken out in the clean-up of 2026-10-17.
- *"Okay perhaps we can make the scope clouds better. Perhaps we take several clouds. For example if there's a relevance cloud at the top for a specific scope, the combination is scope, and high value is supposed to be a sort of cloud, right? Perhaps we just take several such scope clouds? Or bad?"* · *"doing the cluster clouds could be a combination thing. We could first use both the clouds and then after, still limited by the chosen scope. Or perhaps you do the scope first and then you scope the cloud, meaning the clouds give extra weight to specific areas of the scope while perhaps still in the same branch."* (2026-10-11) — a cloud is a scope together with its high values; several of them, and as weight on areas inside the chosen scope. Asked and counted; nothing is built.
- *"ah yes, fuck, TIME, we dont have time in the graph!?"* · *"should we not check time-nearness both to eachother and to "now" unless time is mentioned in query, then nearness to that? and by that i mean using it as a ranking-weight"* (2026-10-11, after the gold of a question was shown to lie on a few days) — asked; since 2026-10-19 each chunk carries its records' own times in the graph (`times`; from 2026-10-17 it was their span) and the 4-combo reads nearness in time between chunks as the smallest gap between their records; nearness to "now" or to a time the question names is not built.
- *"Dude, it is INSANE if the top chunk is NOT a gold!"* (2026-10-12, on the first delivered chunk being gold on 37 of the hundred)
- *"Hm, do, for the top k cluster, what do we get if we take its siblings also?"* · *"No I literally meant the one above or under it. Pointer-based"* (2026-10-12) — a chunk's siblings are the chunk right above and the chunk right under it by its pointer, not everything under its parent.
- *"But dude, the combo should fucking work.. So, if we use the chunk-cloud, see if you can find a way to combo or lift with the tags"* · *"Ok, take that last cloud combo style.. How does scope before or after affect that?"* (2026-10-12)
- *"you say we actually get about 96% gold in max/total.. that MEANS, the actual chunks ARE touched, just not as well as the other chosen ones, but they ARE still chosen..which fucking means that we DO have connections to them"* · *"wait. thats pretty bad placement"* (2026-10-12, on the gold a side touches standing at places 26 to 38)
- *"/goal solve this"* (2026-10-12) — what that goal produced is the arm as it stands, in two builds. The order: inside the name border the chunk descriptions' closeness to the question with the border's name taken out and each chunk's closest tag to a query tag are each cut into clusters, a chunk's step is its two levels added, and the parents holding the majority of the first two steps' chunks are the scope, whose chunks go first inside a step. What is handed over (2026-10-13): by the graph's people (employees tied to channels and meetings, read through the person-to-chunk edges since 2026-10-17) a channel whose people are tied to nothing else of the product is apart and a pull request whose author is not one of the product's people is another project's; those, and the conversations that link only to such a pull request, are left out, and a conversation is handed over whole. Both are the agent's builds and not his concept: the name taken out, the levels added, the scope gauged after and used as weight, the first call's description left out of the order; and the handing over is fitted to how the benchmark was generated, never reads the question, and hands over something other than the chunk as it is; he has not said yes to it. The order of the touched gold is not solved by either.
- *"so, perhaps persons edges shouldnt go to scope directly, but to chunks instead?"* · *"my point just is, stop adding shit beside node -> chunk"* · *"well then, rebuild it"* (2026-10-17, on the graph's employees being tied only to channels and products while the dataset names them in the chunks' posts) — a person edge is the person's node to the chunk, nothing added to it. Built the same day (`test/graph/build_person_edges.py`); the arm reads the product's people through them.
- *"at first i think we should use it to find the rest of the conversation frmo the chosen chunk"* · *"time, scope, entities, chunknearness?"* · *"ok, so we agree, that IS the 4-combo. Make sure that is actually known and the actual implementation."* (2026-10-17) — the 4-combo: from the chosen chunk, the rest of its storyline is narrowed by time (nearness in time), scope (the same area), entities (the people it shares) and chunk nearness (see below), across kinds of record. *"shouldnt that enforce the relevance if its reach in many ways?"* · *"not near eachother.. i think, near eachother, based on the query?"* · *"yeah"* (2026-10-17) — a chunk reached in many ways is the more relevant; chunk nearness is near each other in what the query asks about (two chunks close to the same query tags), not near in general. *"well then, build it!"* (2026-10-17) — built that day: each chunk's time span in the graph (`build_chunk_times.py`), the chosen chunks are those in both first clouds, and `v4_walk.storyline` orders the rest by the ways it is tied to them, added over the chosen chunks.
- *"well, perhaps "far below the cut" isnt really a good place to pull shit from tho..?"* · *"so, since we do the clouds and narrowing before, perhaps we actually do a fuzzy cut at that stage?"* · *"ok, build the thing"* (2026-10-18, after the clouds were shown to be a fixed five-way split borrowed from the nearest-tag k) — each side's cloud is the chunks before the knee of its own closeness, as many as the closeness shows; the chunks in both clouds are the chosen chunks; the 4-combo reorders only inside the clouds and lifts nothing from below them. Built that day.
- *"isnt it perhaps more reasonable to take the nearest chunk depending on time and entities? meaning the most related, if there is no match, then perhaps no chunk, by no match i mean in the same scope, as in we are trying to detect if this chunk is part of a split content etc? so we get "the rest of the same content" ?"* (2026-10-18, on taking the chunk above and under) — asked, not built: from a chosen chunk only what continues the same content, nothing when nothing matches. *"it is as it is then, we cant overfit for that now"* (2026-10-18, on a conversation having no structure in the data: a Slack message is a flat record whose thread replies are empty, and a conversation is only the arm's own cut at the channel's long gaps) — nothing is built for conversations now.
- *"my point is, if it's "easy" to find when creating the graph from the dataset, then its reasonable to use, like the "filestructure" etc"* (2026-10-19, on the border by the product's name being fitted, since every question names its product) — structure that the graph's build reads off the dataset, such as the file structure and the names it holds, is reasonable to use. *"well build this, go on"* (2026-10-19, on the border matching only product names) — built that day: every product, channel, person, customer and company carries its name in the graph, customers are tied to the chunks that carry their id, and the border is where the names standing in the question meet (`name_border`).
- *"Well, what happened to making tags out of the topology? If tags from the query match one of those, something else happens."* (2026-10-07) — it was never built; the model reading the tree was built in its place.

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
- *"What fucking values, we did a ranking on them, check if the RANKING is meaningful"* (2026-10-14) · *"its a RANKING system.. so, jsut fucking try using the actual rank relationships?"* (2026-10-15) — the facet layer is read as a ranking.
- *"the facets were never supposed to carry the whole weight themselves, they are supposed to influence the already existing relationship for chunks and tags so to speak"* (2026-10-15) · *"we somehow need to put the relative relation there too, not just "yeah, its the most important facet of all the tags here" but what if it's still quite fucking unimportant"* (2026-10-16) · *"YOU CANNOT FORCE THEM TO TRY AND CHANGE THE FUCKING ORDERS"* (2026-10-16) · *"take 10.. with and without facets"* (2026-10-15) — built first as a nudge on closeness (places over the whole graph turned into a size and added to the cosine); replaced on 2026-10-19, see below.
- *"go"* (2026-10-19, on: the facet per query tag, not one per question; the facet net is not read on the question side, where its numbers stand on nothing; the first call names, per tag, the facet that matters most for it and says whether that facet matters for the tag at all) — built that day.
- *"i am thinking you have converted them to either a number, or just made arbitrary decisions for them"* · *"and you never stopped to think that perhaps how YOU converted the ranks was the fucking issue?"* (2026-10-19) — the facets' ranks are compared as ranks, never turned into a size and added to a cosine.
- *"how about they get a RELATIVE increase in importance, based on their relative rank compared to that chunk, based on the chosen facet? as in, the chunks are chosen first based on similarity, then that "most similar" IS a rank, and then that rank list is compared to the facets and is adjusted for relative rank"* · *"well thats the fucking point, that i goes both ways..?"* · *"construct and gold10smoketest it"* (2026-10-19) — built that day as `v4_walk.facet_relative_places`: per query tag, the border's chunks ranked by closeness and again, among the same chunks, by the net's value of the same edge in the named facet; a chunk stands midway between its two ranks (half the gap, either way); each chunk takes the best place any query tag gives it (the agent's choice); the clouds and the 4-combo read closeness alone. Replaced in the arm on 2026-10-20 by the adaptive facets (below).
- *"type of record? who gives a shit.. we know that from scope.."* · *"ok, but can we make them adaptive easily deterministically?"* · *"well do that then"* (2026-10-19, on the edges' facet values being mostly the record kind and the tag's own level) — each chunk's edge to its closest tag gets a standing in the named facet, read only against the same graph tag's other edges on chunks of the same kind (above, the same, below). *"thats why i fucking asked you to find the actual relationship to what gets added and what gets lost with the facets, to see what they actually affect, and thus be able to maybe do it adaptive"* · *"ok, do that and run a smoke?"* (2026-10-19, on: the chunks the facets push out hold gold most often when their tag is the query tag's own phrase) — an edge whose graph tag is the query tag's own phrase never stands below. Tested outside the arm on the arm's own order (`output/research/2026-10-19-adaptive-facets/`), then built into the arm on 2026-10-20 after his *"is there a reason to not use the adaptive?"* · *"soo.."* (`v4_walk.closest_edge_standing`, `cloud_combo`'s `standing`): the chunk moves one closeness level nearer or farther by its standing and the tags' cloud, of the size the knee gives, takes the chunks by moved level.
- *"we will NOT use your random made up 'check words'"* (2026-09-08) · *"NEARNESS, we cant fucking use explicit shit"* (2026-09-09) · *"Well that was fucking not the concept"* (2026-09-14, on word counts as facet values)

## Update

A rule he states, or a change he makes to the concept, goes into this file in the same turn as
one line of his words with the date. Nothing else does. At commit: `python refresh_graph.py`,
then `python tools/canon_extract.py`.
