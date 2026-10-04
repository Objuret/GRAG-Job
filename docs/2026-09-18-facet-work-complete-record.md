# The facet work — complete record, 2026-05 to 2026-09-18

Written 2026-09-18 by the orchestrating Claude session, on the user's request: *"write the
complete unbiased doc for all of this, the entire thing we have done here, all the facet work,
the concepts behind it, the planned use and so on, all the way to where we are right now"*.

## 0. How to read this document

The reader is assumed to know nothing about the project.

Three kinds of statement appear, and they are kept apart:

- **His words.** The user's own sentences, quoted in italics with their date. These are the only
  source of intent. Spelling is his, unchanged.
- **Measurements.** Numbers a program printed, with the run or file they came from.
- **Constructions.** Designs or choices made by an agent (a Claude session or sub-agent), or
  brought in by the user as a finished text from elsewhere. Each is labelled with who made it.
  A construction is not the user's ruling unless a quote of his says so.

Sources: the project instruction file `CLAUDE.md` in the repository (the running record, itself
written by agents and therefore a claim, not proof), the state documents in this folder, the
files under `output/` in the repository, and the conversation of 2026-09-17. Where this document
repeats an older number, it comes from that record and was not re-measured for this document.
Numbers from 2026-09-17 were read from disk while writing.

Nothing here recommends a next step. Section 10 lists proposals that were made and not adopted,
labelled as such.

---

## 1. The project in brief

The repository is the user's master's thesis work: a retrieval system over a corporate corpus
(the HERB benchmark corpus: Slack threads, pull requests, documents, meeting transcripts, for 30
products). It compares retrieval "arms":

- two baselines, `lucene` (keyword) and `vector` (embedding), which never touch the graph;
- the **artefact**, a graph-based retrieval the thesis builds. Every artefact edition lives in
  `test/arms/`. There is no finished artefact.

The artefact's graph is a Neo4j database, `herb-eval-volmax`:

| item | count |
|---|---|
| chunks linked to a product | 4,808 |
| metadata chunks with no product edge, excluded from retrieval | 61 |
| tags | about 16,700 |
| `(Chunk)-[HAS_TAG]->(Tag)` edges on the product-linked chunks | 61,018 |
| tags per chunk, median / 95th percentile / max | 13 / 22 / 48 |
| chunk length in characters, median / 95th percentile / max | 3,394 / 3,972 / 5,325 |
| share of tags that sit on exactly one chunk | 62.8% |

Each chunk carries a model-written **description**. Each tag is a short semantic phrase. Both were
written by the "tagger", a model pipeline run in May 2026. The graph also has a structure layer:
Product, Kind, Channel, File, Employee, Customer nodes.

The retrieval chain, in his words (2026-09-02): *"the combo of query facets vs tagfacets, query
tags vs tags and then query desc vs chunk desc"*, and *"the wohle point of the facets, weights and
all weights of the tags-chunks-files-query, are about "how strong/relevant is the connection for
this specific query""*.

Evaluation uses two question sets: `10smoke` (10 questions) and `gold100` (100 questions), with a
72,000-character context budget. One metric, `context_recall_id`, is comparable across arms. A
standing rule of his (2026-08-02): *"you should not have the questions/gold available to you,
there is 0% good that can come out of taht"*. No design may be chosen from gold results. A
measured limit from 2026-09-08: ten smoke questions cannot show a mean recall change smaller than
about 0.15.

---

## 2. What a facet is — his record, in order

**Thesis, §6.4 (2026-05), in Swedish:** *"Taggar organiseras i klustren ämne, entiteter,
aktivitet, temporalitet och evidens, så att materialet kan beskrivas från flera analytiska
perspektiv. Klustertillhörigheten lagras på relationen mellan segment och tagg snarare än på
taggnoden, eftersom samma taggnamn kan ha olika analytisk funktion beroende på kontext."* — a
facet is an analytical perspective on the material, and it is stored on the edge between chunk
and tag, because the same tag can have a different analytical function in a different chunk.

**The original five (2026-05-07):** five questions a chunk answers — theme, object/entity,
event/process, time relevance, information need — each with a closed vocabulary, and one weight
per tag saying how salient the tag is to this chunk.

**The pilot (2026-05-13), an agent's rewrite:** renamed the five to topic, entities, activity,
temporal, evidence; dropped the vocabularies; redefined temporal as verbatim dates and evidence as
information kind; split the weight in two. The user did not write these definitions.

**His framing since:**

- 2026-05-30: *"facets are semantic dimensions, not extractors … structure takes the literal FACT;
  the facet keeps its intended MEANING"*.
- 2026-06-27: *"the facets are themed RELEVANCE weights"* · *"i really do NOT want an llm judge
  involved in the creation of them in the graph"*.
- 2026-07-01: a facet is a dial ("how much"), never a label ("which").
- 2026-08-31: *"it does not say what kind of tag it is, it says how relevant it is, in light of
  that facet"* · *"the tags have facetweights on the edge to the chunk saying how relevant they are
  according to that facet, and the facetweights from the QUERY, determines how many fucks the
  retrieval take to each tag's facets"*.
- 2026-09-06, the concept stated: *"how relevant the tag is to the chunk, according to EACH facet,
  and the query part says how much each facet matters for this query, THAT is the concept"* ·
  *"what we are truly after here, is a semantic relationship, something that separates "depending
  on""*.
- 2026-09-08: *"how tag is facet to chunk … for all facets"* — every facet value is per edge,
  never a property of the chunk alone or the tag alone.
- 2026-09-08: *"they are legendarily bad at 'picking numbers' like that, actually the whole reason
  we wound up here at all is because of that"* — no model writes a per-edge number.
- 2026-09-08: *"what the fuck does the benchmark have to do with it? this is about finding the
  correct chunks"* — facets are not judged by what one test set asks for.

**The five facets as ruled, one at a time, in conversation:**

| facet | ruled | definition |
|---|---|---|
| topic | 2026-09-08 | *"how central is the tag to the topic of the chunk"*; the chunk description is the chunk's topic. Value = cosine between the tag's embedding and the chunk description's embedding. Already in the graph, nothing to tag. |
| temporal | 2026-09-08 | how much the relation turns on time: when things happened, are happening or are due, as against content that reads the same whenever written. Never a date. His later wording (2026-09-15): *"its not just about time or dates, its about the relation of time, now, then, soon, before"*. |
| why | 2026-09-09 (*"yup"*) | how much cause or purpose is involved. |
| activity | 2026-09-08 (*"yeah, we go with that"*) | how much the tag's thing is something happening in this chunk — being done, changed, decided, run — as against being described or referenced. |
| concreteness | 2026-09-09 (*"yup"*) | how specific the chunk is about the tag's thing, as against general talk. |

Struck from the list: entities (*"this is about a fucking tag-chunk relationship, how does
'entities' possibly fit there?"*, 2026-09-08), evidence, and several agent-proposed candidates.

**Topic is the one value that stands.** His words, 2026-09-14: *"lets pretend that one iss
"correct" then, unless it's based on … tokencounts"* — it is not. On 2026-09-17: *"werent we gonna
leave "topic" alone? didnt we decide it was the only weight we already had that actually
worked?"* — confirmed; nothing in any later work touches topic.

**His sharpest statement of what the other four must be (2026-09-15):** *"This is about the
RELEVANCE OF THE TAG TO THE CHUNK! ,... NOT about "whats happening to the tag""*.

**The user's view of what a tag is (2026-09-17):** *"isnt the whole fucking point that a tag is
representing the entire chunk in some capacity.. not just a tiny part in the chunk, it is FROM
"both" and does represent "both" of those.. but seen from the outside, the tag is just pointing
to the chunk, no?"* — so the relevance of a tag is a relation to the whole chunk, never to one
sentence.

---

## 3. The planned use of the facets in retrieval

**Two sides, kept apart.** The edge values are query-independent by design. The query side adjusts
them. His words, 2026-09-13: *"Of course they don't change with the question, that's why we have
the interpretor put a value on its tags in relation to the query... So we can weight-adjust the
facets based on that.."*.

**The query side, the "querytagger"** (formulated with him 2026-09-14, confirmed *"Seems fine."*).
It reads the question and nothing else and produces: (1) a description of the content that would
answer the question, in the tagger's register; (2) tags, as semantic phrases, with no names of
people, products or channels; (3) no scope; (4) per tag, five weights — how relevant this tag is
to the described content, seen through each facet. Weights, not a ranking. Built as
`test/artefact/querytagger.py`. It still weights the old five facet names, not the ruled five.

**The sort.** His words, 2026-09-06: *"the queryfacets is the order of sorting-prio based on
facets for tags … like.. multi-key sort or multi-level sorting."* · *"first you pick a fizzy value
for fit of tags via the tag vs querytags embeddings, right? thats how you PICK the tags, when the
tags are picked, how do we decide which matters for this query?"* → the facet order. ·
*"perhaps we should have the order slightly fuzzy, meaning for a specific order, things can be
called "equal" if within a certain range of eachother"* · *"let clustering hand me the k, those
fixed numbers are enraging me"*. And 2026-07-15: *"i do NOT like arbitrary choices for k or any
number or value, fucking BASE it on something"*.

**The description link.** Query description against chunk description is its own link of the
chain (ruled 2026-09-10). His 2026-08-11: *"the chunk descriptions and the tags are supposed to
work TOGETHER to find gold.. it's a combo.."*.

**Graph shape.** Ruled 2026-09-14: no gate at the front; names in the question land on structure
nodes; the structure strengthens what the tags found and never cuts it. *"That's the point,
letting the graph structure tell which area the information can be found"*.

**What retrieval measurements have shown so far about facets** (record, 2026-09-09 to 09-14; the
edge values in all of these were the ones sections 5.2–5.5 describe, later struck):

- In every arm measured, the facet keys either changed nothing in the delivered set or moved
  recall by about 0.01.
- On 19,011 region edges (2026-09-13), how well each per-edge value separates gold chunks, as AUC:
  topic 0.51, temporal 0.51, why 0.50, activity 0.52, concreteness 0.62.
- Best artefact result on gold100 without any working facet layer: `context_recall_id` 0.491
  (2026-09-13), against vector 0.264 and lucene 0.122.

These results say the facet layers that existed carried no ranking information. They say nothing
about whether a correct facet layer would.

---

## 4. The rule that shapes every attempt

Two of his constraints pull against each other, and every attempt below is a way of living with
both:

1. A facet value is a **semantic judgement** about one tag in one chunk.
2. **No model writes the number** (2026-09-08), and no LLM judge creates the graph values
   (2026-06-27).

So each attempt needs something that understands meaning, and a separate fixed instrument that
turns that understanding into a number.

---

## 5. Every attempt at the four non-topic edge values, in order

| # | date | method | who designed it | outcome |
|---|---|---|---|---|
| 5.1 | 05-13 | the pilot model writes the weights | agent | 96% of weights on eight values; struck |
| 5.2 | 09-03/04 | values derived from word counts | agent | constant per tag or per chunk; still on the live graph |
| 5.3 | 09-08 | a model orders a tag's chunks | agent | the rank is the tag's chunk count; struck by him |
| 5.4 | 09-09 | token-share text statistics | agent, after his *"yup"* to "compute, not calls" | struck by him 09-14 |
| 5.5 | 09-13 | the same statistics per sentence, plus graph concentration | orchestrator | AUC 0.50–0.62; inert |
| 5.6 | 09-14 | embedding similarity to facet statements | orchestrator | inside its random null |
| 5.7 | 09-15 | entailment model on the tag's own sentences | orchestrator | two reviews, NO-GO |
| 5.8 | 09-15 | Haiku writes answers, an entailment reader scores them | with him, step by step | full layer on disk; struck 09-16 |
| 5.9 | 09-17 | counterfactuals + relevance ruler + trained network | a specification he brought | built to completion; layer carries little (section 6) |

### 5.1 The pilot's model-written weights (2026-05-13)

Measured 2026-08-31: 96% of weights sit on eight values between 0.5 and 1.0. Asked twice with the
same prompt (2026-09-08, claude-haiku-4-5, 2,118 edges): 75% of the numbers changed between the
two asks, median change 0.05, 90th percentile 0.40. "Evidence" was 0.89 on nearly every edge. This
is the measurement behind the no-model-writes-a-number rule.

### 5.2 The derived word-count layer (2026-09-03/04)

An agent derived the five values from word counts. Entities and activity are constant per tag on
6,222 of 6,222 multi-chunk tags; evidence is constant per chunk on 4,868 of 4,868. **These are the
values on the live graph's edges today** (`w_facets`). He had believed the edges carried the
tagger's weights: *"Wait, the current weights are word count derivations? Ffs, pin in that"*
(2026-09-14). The property `w_chunk` was removed from every edge on his order on 2026-09-09.

### 5.3 Within-tag ordering by a model (2026-09-08)

A model ranked a tag's chunks. Measured: a sliding window of 20 fixes only the top 10 positions
(tau 0.11 at n = 527), and a rank compared across tags equals the tag's chunk count. His words:
*"by that logic, we dont even have to do anything … that order is by amount of chunks a tag
has"*.

### 5.4 Token-share statistics (2026-09-09)

For each chunk: share of date/time tokens (temporal), of cause and purpose connectives (why), of
non-stative verbs (activity), of numbers and names (concreteness). Computed over the whole graph,
written to `output/facet_stats/`. A first version anchored the tag by string match and was struck
by him (*"NEARNESS, we cant fucking use explicit shit"*). On learning what the final version
counted, 2026-09-14: *"Well that was fucking not the concept"*. His earlier *"yup"* had answered
"compute, not calls", not "counts".

### 5.5 Per-sentence statistics and concentration (2026-09-13)

The orchestrator's construction during a long autonomous loop: the same statistics measured on the
tag's nearest sentences, and a graph-count "concentration" of the tag around the chunk. Several
builds were struck on review the same night. The values are zero on most edges (why 98.8%,
temporal 80.7%, concreteness 76.9%, activity 58.2%). AUC against gold per chunk: 0.50–0.52, with
concreteness 0.62.

### 5.6 Semantic readings through the embedder (2026-09-14)

Facet statements in his words embedded and compared with the tag's sentences, and the tag phrased
through the facet compared with the chunk description. Every value fell inside the band of 200
random probes put through the same pipeline. Under the embedder the four facets correlate
0.81–0.91 with each other: one measure under four names.

### 5.7 Entailment model on the tag's sentences (2026-09-15)

`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` with the facet in the hypothesis, on ten tags and
254 edges. Two independent review agents, run on his order, both said no: the null comparison was
confounded by whether the text contained the tag phrase; the anchoring was the string match he
had struck; the maximum rose with the number of sentences kept; "why" inverted on visible pairs;
temporal's strongest sentence was a timestamp line on 54 of 254 edges.

### 5.8 Written answers plus an entailment reader (2026-09-15) — built in full, then struck

**Ruled by him 2026-09-15:** the model answers a facet question in nuanced prose per tag per
chunk, and a fixed reader turns the answer into the value. The four questions were formulated
with him in lock step and refined over three prompt rounds, each judged by agents against the
chunk text (final round, 128 tags: temporal 111 right / 14 partly / 3 wrong; why 109/9/10;
activity 114/11/3; concreteness 95/23/10).

**The run:** claude-haiku-4-5 answered for all 4,808 chunks and 61,030 (chunk, tag) pairs. The
entailment reader scored 244,120 values, on the laptop CPU and a Google Colab T4; on 21,632 pairs
scored by both, the largest difference was 8e-6. Output: `output/facet_values/herb-eval-volmax/`.
Nothing was written to the graph.

**The values:** share under 0.05 — temporal 60%, why 67%, activity 62%, concreteness 86%.

**His objections, 2026-09-15:** *"This is about the RELEVANCE OF THE TAG TO THE CHUNK! ,... NOT
about "whats happening to the tag""* · *"you said "most facets are 0" on an edge.. thats.. that
means nothing fucking works dude"*.

**Struck 2026-09-16.** The state document of that date, which he brought into the session,
establishes why: Haiku was asked either-or questions and so made the facet judgement itself
(yes / no / partly plus a justification); the reader then judged that verdict against a
restatement of the same question. Haiku judged first, the reader recovered Haiku's judgement.
Rescaling, margins or extra poles do not repair that. The intended split is: the language model
supplies evidence or description from the text; the reader makes the judgement. The same document
states what the failure does **not** show: it does not show that query-independent edge values are
impossible, and it does not move the facet judgement to query time.

Measured 2026-09-16 by five research agents, without opening gold: the four reader columns are
four separate measures (Spearman between them ≤ 0.34), and they vary per edge within a tag. The
"most values are zero" reading was partly a scale error: each column has its own floor, and only
7.6% of edges fall under all four columns' yes/no cut points.

---

## 6. The 2026-09-17 build — the counterfactual-trained neural instrument

### 6.1 Where the design came from

The user pasted a complete written specification into the session, titled "Four-Facet Neural Edge
Instrument", and then pasted three corrections to it during the conversation. The texts are in a
different register from his own messages; he did not say who wrote them, and this record does not
guess. He adopted them as the task: *"/goal complete the spec"* and later *"/goal complete and
finish the build, the entire spec"*. The full text is saved verbatim at
`output/facet_neural/SPEC.md` in the repository.

### 6.2 The design, in plain words

1. A strong model (the "teacher") takes one chunk and all its tags. For every tag and every one of
   the four facets it writes a **counterfactual**: a copy of the whole chunk, changed as little
   as possible, in which that facet's contribution to that tag's relevance is neutralized.
   The teacher writes no number.
2. A fixed **relevance ruler** R measures the tag's relevance to the original chunk and to the
   counterfactual chunk. The training target is the relevance that was lost:
   `target = R(tag, chunk) − R(tag, counterfactual chunk)`.
3. A neural network (a cross-encoder on `tasksource/deberta-small-long-nli` with four separate
   output heads) is trained to predict the four targets from the **original** tag and chunk alone.
4. The trained network is run over all 61,018 edges. It is then the facet instrument. No teacher,
   no counterfactual and no ruler is needed at that stage.

The specification's facet definitions restate the user's concept: each facet value measures how
much that semantic dimension contributes to why this tag is relevant to this chunk, and explicitly
not whether temporal, causal, active or concrete language occurs in the chunk.

**What the specification left blank:** the ruler R, the teacher model, and a scaling function.

### 6.3 Decisions made during the build, and by whom

| decision | who | basis |
|---|---|---|
| teacher = claude-opus-5, effort high | him: *"use opus 5 on high"* | — |
| training and inference on the desktop GPU | him: *"use the desktop gpu"* | — |
| target is the signed loss, not the absolute difference; a rise in relevance is a failed intervention to inspect and reject, never clipped | his Correction 1 | — |
| no scaling function | his Correction 1 | — |
| network sizes and learning rates are starting defaults, tuned from validation only | his Correction 1 | — |
| R is resolved from evidence by comparing candidates on real counterfactuals; not an approval point | his Correction 2 | — |
| the teacher returns only the changed phrases; the script rebuilds the full counterfactual chunk | orchestrator | two-chunk smoke: 100 of 100 rebuilt exactly; a full rewrite per counterfactual never completed a call |
| chunks with many tags are asked in groups of tags | orchestrator, after two chunks with 31 and 37 tags failed | the long answer overran one reply and its beginning was lost |
| 260 training chunks plus 24 chunks generated a second time | build agent | diversity across record kinds, lengths and tag counts; the second generation measures how much a counterfactual varies between asks |
| R = `changed_span` (tag against only the edited sentences) | build agent | see 6.5; **the user rejected the reasoning**, see 6.6 |

### 6.4 The teacher stage — measured

| set | chunks | counterfactuals | calls | tokens in | tokens out |
|---|---|---|---|---|---|
| main | 260 | 12,240 | about 270 | 9.2M + retries | 4.1M + retries |
| second generation | 24 | 976 | 24 | 0.8M | 0.36M |
| smoke | 2 | 100 | 2 | 0.07M | 0.03M |

Figures for the main set are as of 258 chunks; the two failed chunks were recovered afterwards by
the tag-group fix. About 13% of counterfactuals came back unchanged: the teacher's statement that
the facet contributes nothing to that tag in that chunk. 11 of about 13,000 failed to rebuild and
are excluded. Per chunk, 75–97% of tags received a different change for the same facet, so the
counterfactuals are specific to the tag as the specification requires.

A median counterfactual changes one place, 2.5–3.0% of the chunk's characters. Every counterfactual
comes with a one-sentence note from the teacher explaining its decision. Example, tag "Salesforce",
facet temporal, unchanged: *"Salesforce is relevant only as the external system on one side of the
sync integration; no before/after, deadline, or change-over-time information contributes to that
relevance."* Example, same tag, facet concreteness: "between Salesforce and WorkFlowGenie" became
"between the connected external platform and WorkFlowGenie".

### 6.5 The ruler comparison — measured

Embedder for all cosine rulers: `nvidia/llama-nemotron-embed-1b-v2`, the harness embedder, float32.
Desktop GPU, laptop CPU and Colab vectors agree to about 1e-6.

Each ruler's **noise** is measured on its own scale: the 95th percentile of its change under a
counterfactual built for a *different* tag whose edited sentences do not touch this tag's best
sentence.

The **paired test** is a diagnostic built by the agents, not part of the specification. For one
counterfactual, it compares the relevance lost by the tag the counterfactual was aimed at with the
relevance lost by the chunk's other tags, read from the same two texts. A ruler that measures the
targeted relation scores above 0.50; 0.50 is a coin. Standard error about 0.004–0.005.

| ruler | what it reads | noise | median loss | lost beyond noise | gained beyond noise | paired test |
|---|---|---|---|---|---|---|
| whole-chunk cosine | tag against the whole text | 0.0109 | −0.0015 | 3.3% | 6.7% | **0.490** (0.500 on a clean subset of 2,646) |
| sentence max | tag against its best sentence | 0.0000 | 0.0000 | 7% | 13–15% | 0.480 |
| sentence mean | tag against every sentence, averaged | 0.0095 | −0.0008 | 1.9% | 5.0% | 0.527 (0.511 on the first 5,103) |
| changed span | tag against only the edited sentences | 0.1845 | −0.0146 | 1.3% | 3.8% | 0.526 (0.509 on the first 5,103) |
| cross-encoder reranker, 70-chunk subset | `ms-marco-MiniLM-L-6-v2` score | 0.5853 | 0.0000 | — | — | 0.513 |

Reading of the numbers, stated as the build agent stated it in `RULER.md`: no candidate separates
the targeted tag from the other tags of the same chunk by more than about two hundredths; on the
median counterfactual the tag reads as slightly *more* relevant afterwards. By eye on the extreme
cases, the agent attributed the rise to length: the counterfactual shortens or generalises the
text around the tag phrase and leaves the phrase standing.

For the whole-chunk ruler, 90.0% of the 10,630 changed counterfactuals did not move it beyond its
own noise.

### 6.6 The dispute over the ruler

The build agent chose `changed_span`, arguing that it is not diluted by chunk length (it measured a
dilution factor of 29 against a median of 34 sentences per chunk) and cannot jump to an unrelated
sentence. It also wrote, in its own report: *"The comparison did not find a ruler that measures
the tag-conditioned facet contribution."*

The whole-chunk ruler had not been measured on the full set at that point. The agent had switched
the chunk-sized texts off in its embedding script because they ran at 1.7 texts per second against
93 for sentences. The orchestrator reported that embedding as finished when it was not, and
corrected itself when the user questioned it.

The user rejected the sentence-level choice outright: *"because if you do it vs a sentence, all
facets will probably be very fucking close to eachother since a sentence most likely IS about
that fucking tag and so on.. AND it's semantic relationship to the chunk is quite fucking
impossible to determine based on its relationship to a sentence.. what a fucking dumb reason to
reject that"*.

He then ran the missing 7,904 whole-chunk embeddings himself on Google Colab (about 40 minutes on
a T4). The whole-chunk results in the table above come from that run. Checks of his argument:

| ruler | tag's relevance to the original text, median | edges whose four facet losses are all within noise of each other |
|---|---|---|
| whole chunk | 0.21 | 65.4% |
| sentence mean | 0.50 | 76.5% |
| changed span | — | 77.1% |
| sentence max | 0.71 | not computable, noise is zero |

The first column agrees with his point that a sentence containing the tag is simply about the tag.
The second shows the facets separating on somewhat more edges at chunk level, while remaining
indistinguishable on about two of three edges.

The user's reaction on seeing a real counterfactual beside the measurement (2026-09-18):
*"exactly, this sounds like a fucking bizarre way of measuring this"*.

**Two corrections to the orchestrator's wording, accepted 2026-09-18:** the measurements show the rulers did not respond tag-specifically; they do not prove that no tag-specific information exists in the targets. The attribution of the median rise to text length is an inference from reading extreme cases, not a measured correlation.

**A structural observation, the orchestrator's:** the specification asks the teacher for the
smallest possible change and then asks an instrument that reads a whole chunk to register it. Two
texts of 3,855 characters differing in one phrase receive nearly the same embedding. The five
rulers tried are all of one kind — they score how much a text is about a phrase — and the
counterfactuals change how the text relates to the tag, not what it is about.

### 6.7 Targets, training, test and the layer — measured

**Everything in this subsection was produced from `changed_span` targets.** Training began before
the whole-chunk measurement existed and was allowed to finish, labelled with that ruler's name.
No network has been trained on whole-chunk targets.

Targets: 12,083 tag–facet relations over 259 chunks; 11,673 kept; 410 (3.4%) rejected for sitting
below minus the noise; 1,530 measured zeros. 2,639 edges carry all four facets: train 1,787 /
validation 428 / test 424, split by chunk. Target median per facet 0.000 to −0.017.

Training: about 2 hours on the GTX 1080 Ti, 12 epochs with the backbone frozen and 8 with its last
two layers unfrozen. Best validation error at frozen epoch 11 (macro MAE 0.0410); unfreezing did
not improve it.

Held-out test, read once, 424 edges over 39 chunks:

| facet | MAE | spread of predictions | spread of targets | correlation with target |
|---|---|---|---|---|
| temporal | 0.0243 | 0.0030 | 0.0408 | 0.027 |
| why | 0.0499 | 0.0114 | 0.0692 | 0.190 |
| activity | 0.0391 | 0.0062 | 0.0565 | 0.119 |
| concreteness | 0.0472 | 0.0073 | 0.0652 | 0.132 |

The layer, 61,018 of 61,018 edges, checked against the graph edge by edge:

| facet | 5% | median | 95% | spread of the column | spread within a tag | spread within a chunk |
|---|---|---|---|---|---|---|
| temporal | −0.0139 | −0.0094 | −0.0052 | 0.0031 | 0.0012 | 0.0009 |
| why | −0.0505 | −0.0274 | −0.0164 | 0.0107 | 0.0033 | 0.0022 |
| activity | −0.0127 | −0.0054 | 0.0058 | 0.0060 | 0.0030 | 0.0019 |
| concreteness | −0.0183 | −0.0100 | 0.0052 | 0.0074 | 0.0035 | 0.0022 |

Spearman between facets: why–activity 0.46, temporal–concreteness 0.21, all other pairs under 0.09.

The predictions vary roughly ten times less than the targets and sit in a narrow band around each
facet's mean. No arm has read this layer, so nothing is known about its effect on retrieval.

The specification's data loop was run once and ended by the build agent: a second network trained
on the first wave only (80 training chunks, 851 edges) reached validation macro MAE 0.0428, against
0.0410 for the full set (181 chunks, 1,787 edges), on the same frozen validation set. Doubling the
data moved validation by 0.0018. The targets' own disagreement between two independent
generations of the same relation (974 relations) is a median of 0.0174, 95th percentile 0.1634.
The agent ended the loop on the specification's second condition: the targets' repeat dispersion
is the floor.

The build agent's final report measured the whole-chunk ruler on 47 chunks only (paired test
0.465) and lists the remaining 213 as unmeasured; it did not know that the orchestrator had
already measured all 260 with the user's Colab vectors (0.490, table in 6.5). Both numbers are at
or below a coin. Final teacher cost: 291 calls, 10.1M tokens in, 4.5M out. Test suite: 692 passed.
No process is left running on either machine.

### 6.8 Status against the specification's own completion list

| required | exists |
|---|---|
| counterfactual training data | yes |
| numeric training targets | yes, from `changed_span` |
| trained neural model, weights saved, reloads in a fresh process | yes |
| evaluation results | yes |
| full-graph facet predictions | yes, 61,018 edges |

By that list the build is complete. Whether the layer is a valid facet layer is a separate
question, and the measurements in 6.5 and 6.7 are the evidence on it.

---

## 7. Failures during the 2026-09-17 build

Recorded because the user asked for an unbiased account.

- The first build agent waited silently on one command for over ten minutes and was killed by a
  watchdog. The orchestrator said it would check and resume, and the session ended without it
  doing so. The user found the work not done.
- The orchestrator had inserted an approval stop into the build that the user had not asked for.
- The second agent and the teacher process it had started died when the editor session ended.
  Fix: long runs are started as detached processes with a PID file and polled; the progress file
  is updated at every step; a resume procedure is stored in the orchestrator's memory.
- The build agent skipped the whole-chunk ruler on the full set for speed, then chose a ruler.
- The orchestrator told the user the whole-chunk embeddings were finished when they were not; told
  him his login token was missing when it was present under another variable name; promised to
  fetch a 65 MB file through a connector that cannot carry it; created a new folder when an
  established one existed; and used a one-sentence example that made it look as if a single
  sentence had been measured.
- The inference script's resume logic lost 12 rows over three restarts; the agent found it while
  verifying, fixed it, and the final count matches the graph exactly.
- At the start of the day the user found dozens of orphaned processes. Cause: each Claude Code
  session leaves a `claude.exe` and a `keepawake.ps1` shell behind when it ends.

---

## 8. What is established, and what is not

**Established by measurement**

1. Models asked to write per-edge numbers give unstable, lattice-bound values (5.1).
2. Counting tokens does not give the facets (5.4, 5.5), and he has ruled it is not the concept.
3. The same embedder that gives a working topic value cannot tell the four facets apart (5.6).
4. An entailment model applied to the tag's own sentences fails in several identifiable ways (5.7).
5. A language model can write per-edge, graded, grounded prose about a tag in a chunk (5.8,
   judged by agents against the text), and a fixed entailment reader scores prose
   deterministically across machines. The 09-15 arrangement of the two was wrong (5.8).
6. claude-opus-5 produces tag-specific, facet-specific, minimal counterfactuals at scale, with an
   explanatory note each (6.4).
7. Embedding-similarity rulers, at sentence or whole-chunk size, and one reranker, do not register
   those counterfactuals in a tag-specific way (6.5).
8. A network trained on targets from such a ruler learns approximately the facet means (6.7).
9. The full pipeline — teacher, rebuild, targets, training on the desktop GPU, saving, reloading,
   inference over 61,018 edges — runs and resumes after interruption.

**Not established**

1. Whether any fixed instrument registers a removed facet as lost relevance. Only one kind of
   instrument has been tried.
2. Whether a correct facet layer improves retrieval. Every retrieval measurement so far used a
   layer that was later struck or shown to carry nothing.
3. Whether the querytagger's per-query weights are usable. One stability check (2026-09-14) found
   the tags themselves differ between two asks; his reading: *"the important part is not that the
   weigths are perfect, it's that the logic that made them is correct"*.
4. Whether the counterfactual corpus or the teacher's notes can serve a different measurement.
5. Whether the 09-15 Haiku answer corpus is reusable; the 09-16 document says not to assume so.

---

## 9. Open questions that are the user's to rule

1. What the four non-topic edge values are made from, given sections 5 and 6.
2. Whether "how much relevance is lost when a facet is neutralized" is the right target at all.
   His last words on it: *"this sounds like a fucking bizarre way of measuring this"*.
3. If the counterfactual idea is kept: which ruler.
4. From the 09-16 document, still unanswered: what evidential text a model should write per
   (chunk, tag); what hypothesis a reader judges it against so that it expresses the tag's
   relevance to the chunk through the facet; how the reader's output becomes the edge value.
5. What happens to the word-count values that sit on the live graph edges.
6. What the query-side weights do inside the sort (open since 2026-09-13).
7. His standing ask to remove the 61 metadata chunks from the database, not yet executed.

---

## 9b. The topic-as-anchor point, 2026-09-18

Raised by the user (*"is there no way of using the value from topic as a relative value anchor for this?"*) and confirmed by the author of the 09-17 specification (a GPT session, whose text the user pasted): the specification defined every facet target as lost overall relevance, `R(T,C) − R(T,C^(−F,T))`, while topic already measures the overall tag↔chunk relation. Each facet was therefore made to re-establish overall relevance instead of characterising the existing relation from one angle. The spec author's words: *"the mere existence of Topic should have stopped me from doing that"* and *"Salesforce can remain maximally relevant while the Temporal aspect of that relevance goes from strong to zero."* The user, on the neural layer: adjusting it by topic afterwards recovers nothing (section 6.7); topic belongs in the construction of the values. How topic and the four conditional values combine (multiplier, ceiling, separate coordinate) is unresolved. The user's instruction: test the mathematical idea before any further training run. Not built.

**Later the same day, 2026-09-18.** The user: *"my thinking is that the "main weight" on a tag, is the topic one, and the others adjust that weight depending on the relevance of a facet to the query"* — recorded in `CLAUDE.md` as his statement of the model (same as his 06-27 sentence). Two GPT proposals followed, both relayed by the user: (a) train four classifiers on changed-versus-unchanged counterfactual labels and store Topic × p — set aside by GPT itself after the orchestrator's critique (the label is Opus's verdict, the 09-16 information-flow objection; a probability is an order, not a magnitude; twins differing by one phrase); (b) build the four values as topic is built — a model writes a short facet-specific view of the chunk (per chunk) or of the tag↔chunk relation (per edge), the value is cos(tag, view) — and use the existing counterfactuals only to CHECK the construction: after a temporal neutralization for tag T, T's temporal value should fall while topic and the other three hold, and repeated writing should be stable. GPT's two pins: same embedder is not the same scale, report each facet's distribution separately; decide per-chunk versus per-edge by that test, not by cost. **Planned pilot (not started, awaiting the user's word):** four facet-view prompts drafted from his facet sentences and shown to him first; ~20 chunks with their counterfactuals, views per chunk and per edge, written twice for stability, a small model as writer; embedding on the desktop; tables for isolation, per-facet distributions, separation among the four, stability; pass or kill read off the isolation test. No training, nothing to the graph.

## 10. Proposals made by agents and not adopted

Listed for completeness. None is the user's, and none has been run.

- **Masked-tag prediction as the ruler** (orchestrator, 2026-09-17): hide the tag phrase in the
  chunk and measure how probable a local language model finds it, on the original and on the
  counterfactual. Reads the whole chunk; GPU time only; reuses the counterfactuals. Known gap:
  about 23% of tags are not in their chunk word for word. Untested.
- **Retraining on whole-chunk targets** (orchestrator): about three GPU hours, no teacher calls.
  Not done, because that ruler also scored a coin.
- **The teacher's notes as the carrier of the judgement** (orchestrator, an observation, not a
  design): each of the roughly 13,000 notes is a sentence about how the tag is relevant to the
  chunk through the facet.
- **Ten designs for using the 09-15 layer in retrieval** (research agents, 2026-09-16):
  `output/research/2026-09-16-ten-designs.md`. Superseded by the striking of that layer.
- **A rank transform or a three-pole reading of the 09-15 reader** (2026-09-16): declared
  insufficient by the 09-16 correction document.

---

## 11. Where everything is

Repository root: `C:\Coding\exjobbet\GRAG-Job` (branch `user-canon-record`; none of the facet work
from 2026-09-09 onward is committed).

| what | path |
|---|---|
| the running project record | `CLAUDE.md` |
| his typed messages, archive | `docs/canon/raw/user_turns_all.jsonl` |
| machines | `docs/ENVIRONMENT.md` |
| 09-17 specification with corrections, verbatim | `output/facet_neural/SPEC.md` |
| 09-17 build status and every resume command | `output/facet_neural/PROGRESS.md` |
| counterfactuals, one file per chunk, with the teacher's notes | `output/facet_neural/counterfactuals/herb-eval-volmax/` |
| second generation of 24 chunks | `output/facet_neural/counterfactuals_repeat/herb-eval-volmax/` |
| ruler reports | `output/facet_neural/RULER.md`, `RULER_all260.md`, `RULER_xenc_subset.md`, `RULER_smoke.md`; whole-chunk tables in `output/facet_neural/rulers/report_whole.log` and `facets_whole.log` |
| all ruler values per row | `output/facet_neural/rulers/whole/rulers.jsonl`, `null.jsonl` |
| all embeddings | `output/facet_neural/rulers/merged_whole.vectors.npz` |
| targets | `output/facet_neural/targets/main/` |
| trained model | `output/facet_neural/model/changed_span_20260917/` |
| the 09-17 layer | `output/facet_neural/layer/herb-eval-volmax/values.jsonl`, statistics in `output/facet_neural/LAYER.md` |
| code for the 09-17 build | `test/graph/facet_counterfactuals.py`, `facet_rulers.py`, `facet_rulers_report.py`, `facet_ruler_facets.py`, `facet_embed_gpu.py`, `test/graph/facet_neural/`, prompts in `test/graph/prompts/` |
| the 09-15 layer (struck) | `output/facet_values/herb-eval-volmax/`, answers in `output/facet_answers/herb-eval-volmax/` |
| the 09-09 token statistics (struck) | `output/facet_stats/` |
| backups of the graph's edge layers | `output/facet_weight_backup/` |
| research reports | `output/research/` |
| state documents, Colab notebooks | this folder, and `colab/` inside it |

Nothing from any of these attempts has been written to the Neo4j graph.

---

## 12. Machines

- **Laptop:** 16 GB RAM, no GPU. Holds about 8 concurrent Claude CLI workers; 30 exhausted memory
  on 2026-09-15. `claude` is not on PATH; the executable is `.local\bin\claude.exe` under the user
  profile.
- **Desktop "Djuret":** 32 GB RAM, GTX 1080 Ti 11 GB, reached by SSH. No fast half precision. For
  this network a batch of 8 runs ten times faster than a batch of 24, because the larger one
  overflows GPU memory and Windows pages it silently. Claude calls work there since 2026-09-17
  through a long-lived token passed as `CLAUDE_CODE_OAUTH_TOKEN`; the CLI was updated to 2.1.274.
  His words: *"desktop can easily do twice the amount the laptop can, laptop only has 16gb ram, pc
  has 32"*.
- **Google Colab T4:** used on 2026-09-15 and 2026-09-17 as a second GPU. In float32 it is about
  as fast as the 1080 Ti. Results go to Google Drive; files of tens of megabytes must be moved by
  the user by hand.

---

## 13. The facet-view pilot — 2026-09-18, run unattended on his /goal

Appended 2026-09-18 by the orchestrating Claude session. His /goal of the same day
(`docs/2026-09-18-goal-facet-views.md`): *"Build and validate the four non-topic facet values on
topic's own footing, and if they validate, produce them for every HAS_TAG edge of the graph"*,
run unattended under his added rules (define every uncertainty, research it, test competing
explanations, never choose by cost). The model of the edge in his words, 2026-09-18: *"my
thinking is that the "main weight" on a tag, is the topic one, and the others adjust that
weight depending on the relevance of a facet to the query"*. Everything below that is not a
quote of his is the orchestrating session's construction, or an agent's where named. The full
running record with every number is `output/facet_views/PROGRESS.md`; the statistics of the
check are `output/facet_views/CHECK_DESIGN.md`; the literature anchor is
`output/research/2026-09-18-facet-views-literature.md`.

### 13.1 The construction tested

Topic's own construction turned to the four facets: a small model (claude-haiku-4-5) writes a
1–2 sentence description of the chunk seen through one facet — a *view* — and the value is
cos(tag, view) under the harness embedder, the way topic is cos(tag, chunk description). Two
variants, both built: per chunk (one view per facet, no tag in sight) and per edge (per attached
phrase, the chunk as it concerns that phrase). The prompts were drafted from his facet sentences
(section 2) and the tagger's one line ("Describe the chunk's content in 1-3 sentences."),
reviewed by an independent agent against his sentences (18 findings, the drafts and the
reviewed versions both recorded), and fixed before any view was written; one canonical absence
line, "The text gives nothing here.", for an angle the text gives nothing from.

### 13.2 The check, fixed before any view existed

The 13,044 counterfactuals of section 6 as the falsification instrument, never a source of
values. For a counterfactual that neutralises facet F's contribution to tag T: T's F value must
fall beyond the writer's own write-to-write spread (rule a); it must fall more than T's other
three facet values on the same pair (rule b); other tags' F values on the same text must move
less (c); topic must hold (d); the two independent counterfactual generations must agree (e).
Every text written twice as independent calls; noise = the spread between the two writes;
statistics by a paired win rate with a cluster bootstrap over the 24 chunks and cluster
permutations, an eval-statistician agent's specification. KILL on (a) or (b); PASS needs all
five and a replication on write 2.

### 13.3 The pilot — measurements

24 chunks (the only ones with two counterfactual generations), 1,513 distinct texts (24
originals + 1,489 changed counterfactuals), 244 tags, 1,656 intervention rows. Writer: 6,097
calls over two machines, 167.7 M tokens in and 21.7 M out as the CLI counts them, 60 parse
re-asks, one failure re-asked; 04:04Z–07:49Z at 20 workers. Views: 14–23 words (edge), 42–64
words (chunk); absence lines on 0.8% of chunk views and 5.0% of edge views. Embeddings on the desktop GPU: 181,368 strings, one embedder recorded from the sidecar. The footing is approximate: Haiku's description of the original sits at cosine 0.31–0.91 (median 0.74) to the tagger's stored description vector, and the local topic follows the graph's topic order at Spearman 0.71 over the 244 original units (`check_final/register.md`).

Writer noise, two writes of the same text, over 18,209 (tag, text) units — median / p95 of
|Δ cosine|: chunk 0.027–0.035 / 0.091–0.133; edge 0.059–0.077 / 0.212–0.270; topic (the
description) 0.028 / 0.091.

The rule, plain cosine, write 1 (write 2 replicates every cell):

| variant | facet | R_F = median targeted drop / median noise [CI] | A_facet (targeted facet's drop beats the other three) ± SE | verdict |
|---|---|---|---|---|
| chunk | temporal | −0.33 [−0.75, −0.03] | 0.464 ± 0.033 | KILL (a)(b) |
| chunk | why | −0.12 [−0.61, 0.31] | 0.488 ± 0.047 | KILL (a)(b) |
| chunk | activity | 0.05 [−0.37, 0.33] | 0.556 ± 0.048 | KILL (a)(b) |
| chunk | concreteness | −0.06 [−0.42, 0.26] | 0.526 ± 0.042 | KILL (a)(b) |
| edge | temporal | 0.25 [−0.21, 0.62] | 0.513 ± 0.037 | KILL (a)(b) |
| edge | why | −0.17 [−0.55, 0.12] | 0.452 ± 0.031 | KILL (a)(b) |
| edge | activity | 0.09 [−0.17, 0.48] | 0.511 ± 0.026 | KILL (a)(b) |
| edge | concreteness | −0.11 [−0.36, 0.10] | 0.485 ± 0.032 | KILL (a)(b) |

Tag isolation 0.45–0.53; topic held (nothing moved); the share of rows whose targeted drop
clears the band 1.4–5.4% against a null's 2.5%; generation agreement −0.23 to +0.15. Two of the
eight KILLs (chunk activity, chunk concreteness) sit in the 0.52–0.58 window the design marks as
"by the rule, not by the data"; the other six are by the data. Three further readings of the
same views — the view with its projection on the description removed, the value relative to
the description's, and a cross-encoder relevance logit in place of the cosine — read the same
coin on every cell (cross-encoder A_facet 0.48–0.54; its own write-to-write band p95 14–20
logits).

### 13.4 Why — three measurements that separate the levels

1. **Coverage (text level, no embedder).** Does the targeted facet's view of the original carry
   any content word of the span the edit removed? Chunk variant: 0.30–0.77 of rows, against a
   same-facet, other-tag control of 0.31–0.75 — a whole-chunk facet view carries the words of
   any same-facet edit exactly as often as the targeted one; it is facet-level chunk content
   with no tag in it. Edge variant: 0.37–0.70 against 0.13–0.32, and the view of the
   counterfactual drops the removed words on 61–91% of covered rows — the per-edge view is
   tag-specific and follows the edit in words.
2. **The instrument alone.** Striking the edit's own words (median 1–2) out of the view text
   itself moves the tag's cosine by a median of −0.03 to +0.004, no more than striking random words (P(strip > random) 0.45–0.63); 0–0.6% of chunk rows past the writer's band, not computed on the edge views. The cosine of a phrase
   against a 15–50-word view does not read one or two facet words.
3. **The writer's variance.** Two writes of the same text move the same cosine by 0.03–0.08
   (median), a factor of 4 (edge temporal) to 21 (chunk concreteness) above the targeted edit's median effect (0.002–0.018); and the targeted drop does not repeat between the two writes: Pearson(Δ on write 1, Δ on write 2) −0.19 to +0.21 (chunk), +0.03 to +0.40 (edge), so under the check design's reading 60–100% of the observed Δ variance is writer noise.
4. **Untested: the views may not be the facets as ruled.** By eye on two chunks (one reader,
   unquantified) the temporal views carry the record's timestamps against the prompt's "not
   dates for their own sake", the concreteness views list named things, and the views run 2–3
   sentences where 1–2 were asked; no judge read the views against his four definitions.

An independent read-only audit (critical-reviewer) recomputed every headline number from the
row files, found the one estimator defect that could have manufactured a KILL (a fixed null of
0.5 for a per-column win rate whose base rate runs 0.45–0.54), corrected it, and found the
corrected contrast under 1.4 SE on every cell; its completeness findings were built in and
re-run with every pre-registered number unchanged.

### 13.5 What stands after the pilot

- Established by measurement: a small model writes per-edge facet descriptions that are about
  the tag, decoupled from topic (Spearman with topic −0.11 to 0.12 on the edge variant), and
  that follow a tag-specific counterfactual edit at the word level (coverage 0.37–0.70 against a same-facet control of 0.13–0.32) — word-level only, not judged against his definitions, and the four columns still correlate 0.36–0.49 with each other; neither the bi-encoder
  cosine nor a cross-encoder logit turns those texts into a per-edge value that registers the
  facet's contribution above the writer's own variance; the targeted drop's per-write noise is 0.03–0.06 (chunk) and 0.07–0.10 (edge) in cosine; the value as the mean of the two writes reads the same coin on rule (b) (0.45–0.56).
- Not established: whether any fixed instrument reads the facet relation off such a text (only
  the embedding-cosine family and one reranker were tried); whether the neutralisation test is the right falsification of an edge value (it was struck as a definition of the value on 09-17 and is used here only as the test; his last words on that measurement, 2026-09-18: *"exactly, this sounds like a fucking bizarre way of measuring this"*); and, by the check's own pre-registered power floor, an isolation AUC of 0.52–0.58 is undetectable at 24 chunks — two cosine cells (chunk activity 0.556, chunk concreteness 0.526) and two cross-encoder cells sit there, and resolving them would take 60–236 further chunks without the second-generation check.
- Not run, with the reason recorded in PROGRESS.md: a trained per-facet space over the views,
  a pair scorer with a facet hypothesis (needs his wording), structured extraction, comparative
  judgment, a probe on the counterfactual vectors (uses the counterfactuals as a source).
- Nothing written to the graph; no gold opened; the arms, the querytagger and topic untouched;
  no facet source produced (step 3 not reached). The 6,052 view files, the vectors, the scores
  and every check are under `output/facet_views/pilot/`.

Open, his: what the four non-topic edge values are made from — the questions of sections 9 and
9b stand, with one added: the text that describes the relation per edge now exists and follows the edit at the word level, and the instrument that makes its number does not.
