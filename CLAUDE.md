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
- The artefact being worked on: `test/arms/artefact_v4.py` (the arm), `test/artefact/v4_walk.py`
  (the arithmetic that gives each chunk its value and the order), `test/artefact/query_content.py` (the two model requests). One
  path, one switch: `HERB_V4_OFFLINE`. What a run used: its `run_manifest.json` and each row's
  `meta`.
- `docs/ENVIRONMENT.md` — the machines, the Neo4j start, the model lane and how many calls this
  laptop holds at once. `docs/canon/raw/user_turns_all.jsonl` — his typed messages
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
- Runs: `ls output/k=chars`. The two baselines on the hundred:
  `lucene__gold100__cb72000__20260814T134547Z` and `vector__gold100__cb72000__20260814T145615Z`
  (their answers and judging were made through the lane before `--safe-mode`). Across arms only
  `context_recall_id` compares; `context_precision_id` and the nonllm pair are within-arm.
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

What may be done:

- Nothing built, run, or written to the database without his words naming it; a "yeah" is not a go (2026-09-03).
- *"Unless i litterally tell you its ok or i want to do this, you do NEVER just "run ahead" if you have something unsettled"* (2026-10-07, after "Three things in the build are mine … Stop me if any is wrong" was followed by building) — an unsettled point stops the work and is put to him; "stop me if wrong" is not his ok.
- *"ok, obviously switch it on ALWAYS switch on the newest built thing unless stated otherwise"* (2026-09-07)
- *"only make a switch when i specifically have asked for a "run both and see" or something like that.."* (2026-10-07) — a change replaces the old behaviour; the old one is in git.
- A comment says what the code does; his sentence goes in only where it is the reason, as one line (his "yes", 2026-10-07).
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

How to work with him:

- *"you write a really long thing that needs reflection on, especially by you, then you end it with a semi-irrelevant question, if I answer that, you will pretty much toss out all the other stuff from your prompt.. Doesn't that seem like a really sharp weakness in the harness?"* · *"Good, decided"* (2026-10-02) — a message carrying reflection, analysis or a design ends with no question; a question comes as its own short message after he has reacted.
- *"you DO know the core concepts we worked with, right? how about instead of dragging up the entire fucking ship and luggage of past ghosts you take a look at the concepts, compare them to what you are doing now or NOT doing now, figure out fitting application of those based on the core concepts i have been hammering for fucking ever"* · *"stop forcing me to course correct every goddamn fucking time"* (2026-10-04)
- *"so, how can i make you actually guild the fucking thing i want you to build instead of you building your own shit every time?"* (2026-10-05) — what is the agent's own choice in a build is said to him as such.
- *"you stopped everything? wtf dude, i want you to just fucking communicate what you are doing, you have been working for HOURS"* (2026-10-05)
- *"shesus the fuck you are babbling alot and saying very little"* (2026-10-06) · *"you are not speaking my language at all now..."* · *"dont give me a fucking bullet list.."* (2026-09-21)
- *"just dont do the "infinity-review" after, ok"* (2026-10-07)
- *"if you DO NOT UNDERSTAND, fucking get the information you need, ask me after you define the exact detail you dont get"* · *"dude, always do an internet search for the same concept also"* (2026-10-08) — a concept of his is first looked up in his own words and on the internet; the question to him comes after, and names the exact detail.
- *"Do absolutely fucking NOT never goddamn fucking EVER make up your own language, terms and explanations for shit I have already defined."* (2026-10-07, after "the chain", "place" and "stands out" were said for what the tags and the chunk descriptions hit, for scope, and for "where the truth seems to be"; his *"WHAT FUCKING CHAIN?"*)

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

The query side:

- *"it's querydesc, query, querytags, querytag-facets, right?"* (2026-09-29)
- *"the interpreter should describe the query as 'what type of content it's trying to find'"* (2026-09-14) · *"i think the actual thought would be "describe the content the query is looking for" as in, not trying to guess the exact content, but describe it, instead to make sure nothing is made up for forced so to speak, but also to keep it in the fitting dimension?"* (2026-10-06)
- *"I think we should make query tags from the actual prompt also"* (2026-10-02) — both tag lists are query tags.
- The readings on a query tag: *"maybe their relevance to the query-description"* · *"Yes, I think that's the play"* (2026-09-14) — per tag, per facet, how relevant the tag is to the described content seen through that facet.
- *"i would rather it did exactly as i wanted with the desc and tags, and then perhaps another call used that info + tree/scope"* (2026-10-06) · *"yup, like this"* (2026-10-07) — the first call writes the description and the tags with no tree; a second call gets the question, that description, those tags and the tree, and returns the scope.

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
- *"i THINK its a viable idea to use the structure last, as a "vertical cut" making the pool more narrow?"* · *"no i think i actually mean as it was said, as a filter"* (2026-10-07) — structure comes last and filters: a chunk outside the scope is out of the pool. *"that way we can gauge where the truth seems to be, and can thus cut "the others""* · *"yeah, but i dont think we use the second call if we do this, right?"* · *"Well, we can just cluster by scope and see if that gathers the correct scopes?"* · *"And perhaps keep minorities if same parents or something..?"* · *"the clustering here is just a gauge of where the most relevance seems to lie"* · *"thats why i said clustering tbh, to get the "largest clouds" of relevancy"* (2026-10-07) — the scope is gauged from what the tags and the chunk descriptions hit, by clustering those by scope; asked as questions, nothing here is built and the second call is not ruled out yet.
- A side thought, no go: *"what if we allow names of people, products and channels to be tags frmo the query, but we add scopes as if they were tags for the comparison?"* · *"a match on one of those does NOT pick/boost a chunk, it picks/boosts a scope, atleast for the conversation we are having about it now"* (2026-10-06)
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
- *"we will NOT use your random made up 'check words'"* (2026-09-08) · *"NEARNESS, we cant fucking use explicit shit"* (2026-09-09) · *"Well that was fucking not the concept"* (2026-09-14, on word counts as facet values)

## Update

A rule he states, or a change he makes to the concept, goes into this file in the same turn as
one line of his words with the date. Nothing else does. At commit: `python refresh_graph.py`,
then `python tools/canon_extract.py`.
