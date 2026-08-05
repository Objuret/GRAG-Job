# HERB evaluation — the run record

The current record of every evaluation run in `v3/output/`: what each run is, what it
scores, and what it may be used to claim.

Every number here is recomputed from the run folders themselves — `run_manifest.json`,
`eval_manifest.json`, `eval_results.jsonl`, `arm_outputs.jsonl`. `context_recall_id` is
recomputed for every folder from `arm_outputs.jsonl` against
`data/questions.jsonl` citations (RAGAS `IDBasedContextRecall`: |retrieved ∩ gold| /
|gold|, over sets of string ids) and agrees exactly with the stored `eval_results.jsonl`
on all 26 retained folders carrying both — max absolute difference 0.00e+00, no cell
skipped. Rows that cannot be verified this way are marked UNVERIFIED, and figures whose
folder is no longer retained say so in place.

## Arms and terminology

**Baseline means lucene and vector** — the comparison arms. `hybrid` is a third
comparison arm (late fusion of those two, `pipelines/hybrid.py`).

`artefact_v1` and `artefact_v1_det` are **two configurations of the system under test**,
not baselines. They differ in the interpreter: `artefact_v1` plans with a model
(`interpreter_model` in the manifest, usually `claude-haiku-4-5`), `artefact_v1_det`
plans deterministically (`interpreter_model: deterministic`, zero model calls). Neither
is a pass-bar, and a measurement of one is never the bar the other must clear. **Which
leg is the reported artefact configuration is undecided** — this file reports both and
assumes neither.

| arm | code | retrieval unit | id space |
|---|---|---|---|
| `lucene` | `pipelines/lucene.py` | one whole HERB artifact | native artifact `id` |
| `vector` | `pipelines/vector.py` | one whole HERB artifact | native artifact `id` |
| `hybrid` | `pipelines/hybrid.py` | one whole HERB artifact | native artifact `id` |
| `artefact_v1` | `pipelines/artefact_v1.py` | one graph chunk | every artifact id the chunk carries |
| `artefact_v1_det` | `pipelines/artefact_v1_det.py` | one graph chunk | every artifact id the chunk carries |

`lucene`, `vector` and `hybrid` index `data/corpus/Salesforce__HERB/products/` only
(`lucene.py:161`, `vector.py:175`); the artefact arms query the `herb-eval` Neo4j graph,
which also covers `metadata/`.

## The unmatched-unit rule — applies to every cross-arm number below

The user ruled on 2026-07-26: *"k=50 does not mean the same for all arms, and thats
retarded"* (`docs/canon/raw/user_turns_all.md`:2901).

The run folders show exactly that. At k=50 on gold-100, per question:

| run | contexts | unique ids | context chars |
|---|---|---|---|
| `artefact_v1_det__gold100__20260801T072455Z` | 50 | 499.8 | 246,479 |
| `artefact_v1__gold100__20260718T231758Z` | 50 | 442.8 | 233,668 |
| `lucene__gold100__20260627T003236Z` | 50 | 50.0 | 59,006 |
| `vector__gold100__20260625T121031Z` | 50 | 50.0 | 23,137 |
| `hybrid__gold100__20260723T153637Z` | 50 | 50.0 | 41,224 |

One artefact "context" is a chunk carrying ~10 artifact ids; one baseline context is a
single artifact carrying one id. At the same k the artefact arms hold ~10× the ids and
4–10× the text. **A cross-arm ratio read at a common k is not a like-for-like lead and
must never be presented as one.**

It also moves the ceiling, so the arms are not even scored against the same maximum.
`context_recall_id` cannot exceed `min(ids retrieved, gold ids) / gold ids`:

| question set | ceiling at a 50-id budget | ceiling at a 500-id budget |
|---|---|---|
| gold-100 (gold ids: mean 39.3, max 254, 23/100 over 50) | 0.9085 | 1.0000 |
| held-out-100 (gold ids: mean 78.8, max 424, 67/100 over 50) | 0.7271 | 1.0000 |

At k=50 the baselines are capped at 0.9085 on gold-100 and **0.7271 on held-out-100**,
while the artefact arms carry enough ids to be effectively uncapped (1.0000 on both).
The ceiling is not shared.

Where a matched-budget comparison exists it is reported separately, below, naming the
runs it comes from.

## Question sets

`data/questions.jsonl` is the 1514-question pool; each set file lists ids.

| set | n | person | content | pr | company | url | overlap |
|---|---|---|---|---|---|---|---|
| `gold100.jsonl` | 100 | 22 | 55 | 17 | 5 | 1 | contains all 10 of `10smoke` |
| `heldout100.jsonl` | 100 | 20 | 21 | 20 | 20 | 19 | disjoint from gold-100 |
| `10smoke.jsonl` | 10 | 2 | 2 | 2 | 3 | 1 | subset of gold-100 |

gold-100 is not the equal 20-per-type draw `build_question_sets.py` produces. **Its
company (n=5) and url (n=1) cells are anecdotes** and per-type numbers from them carry no
weight. Held-out-100 is type-balanced, so its per-type cells (n≈20) are readable — but its
gold citation sets are twice the size, which is what drives the 0.7271 baseline ceiling
above.

---

# Current numbers

All comparisons are paired by question id. CIs are 95% on the paired per-question delta.

## gold-100, `context_recall_id`, read at k=50 (UNMATCHED UNITS)

| run | arm | recall_id | ids/q | chars/q |
|---|---|---|---|---|
| `artefact_v1_det__gold100__20260801T072455Z` | artefact_v1_det (shipped defaults) | **0.7339** | 499.8 | 246,479 |
| `artefact_v1__gold100__20260718T231758Z` | artefact_v1 | **0.6363** | 442.8 | 233,668 |
| `hybrid__gold100__20260723T153637Z` | hybrid | 0.1149 | 50 | 41,224 |
| `vector__gold100__20260625T121031Z` | vector | 0.1129 | 50 | 23,137 |
| `lucene__gold100__20260627T003236Z` | lucene | 0.0894 | 50 | 59,006 |

The artefact-vs-baseline gaps here (det − vector +0.6210, det − lucene +0.6445, det −
hybrid +0.6190, all 100/0 wins) are read at a common k, so **they are not a like-for-like
lead.** They are the numbers the unmatched-unit rule disqualifies.

The two system-under-test configurations differ from each other on the same units:
`artefact_v1` − `artefact_v1_det` = **−0.0975**, CI [−0.1382, −0.0569], W/L/T 18/50/32.
That comparison *is* like-for-like (both carry ~450–500 ids, ~235–246k chars).

## gold-100 at a matched retrieval budget (the like-for-like reading)

The k=500 baseline runs bring the baselines to the artefact arms' id count. Paired
against `artefact_v1_det__gold100__20260801T072455Z` (499.8 ids, 246,479 chars):

| baseline run | arm | ids/q | chars/q | recall_id | paired delta vs det | 95% CI | W/L/T |
|---|---|---|---|---|---|---|---|
| `veck500__gold100__20260723T154421Z` | vector, k=500 | 500 | 180,244 | 0.4100 | +0.3239 | [+0.2767, +0.3711] | 89/6/5 |
| `hybk500__gold100__20260723T154340Z` | hybrid, k=500 | 500 | 366,124 | 0.3883 | +0.3455 | [+0.3024, +0.3887] | 93/5/2 |
| `luck500__gold100__20260723T154401Z` | lucene, k=500 | 500 | 559,299 | 0.2742 | +0.4597 | [+0.4192, +0.5002] | 96/1/3 |

At a matched id budget the artefact-det lead over the strongest baseline is **0.7339 vs
0.4100, a ratio of 1.79×** — against ~10× read at a common k. `artefact_v1` at matched
budget: 0.6363 vs veck500 0.4100, delta +0.2263, CI [+0.1697, +0.2830], W/L/T 77/18/5
(1.55×).

Text budget is not matched in this comparison: veck500 uses less text than the artefact
run (180k vs 246k chars), luck500 more (559k). The id budget is matched exactly (500 vs
499.8); the character budget is not.

`hybk500`, `luck500` and `veck500` are `hybrid`-arm runs with `HERB_HYBRID_ALPHA` 0.5 /
0.0 / 1.0 — alpha 0.0 and 1.0 reproduce the lucene and vector arms exactly (`hybA0_lucene`
= 0.0894 and `hybA1_vector` = 0.1129, byte-matching the standalone arms at k=50).

## The only matched-character-budget experiment (n=10, anecdote scale)

The `__b72000` family caps every arm at 72,000 context chars per question on `10smoke`:

| run | arm | contexts | ids | chars | recall_id |
|---|---|---|---|---|---|
| `artefact_v1_det__10smoke__20260727T145652Z__b72000` | artefact_v1_det | 13.6 | 143.0 | 69,201 | 0.3952 |
| `vector__10smoke__20260727T145639Z__b72000` | vector | 50.0 | 50.0 | 14,811 | 0.1179 |
| `lucene__10smoke__20260727T145649Z__b72000` | lucene | 48.4 | 48.4 | 40,868 | 0.0796 |

Paired: det − vector +0.2773 (W/L 7/1), det − lucene +0.3156 (W/L 8/2). **n=10 — this is
an anecdote, not a result.** The cap binds only the artefact arm; both baselines run out
of contexts at k=50 well under 72,000 chars, so the budget is matched only from above.
Unconstrained, the same det configuration scores 0.7751 on these ten questions
(`artefact_v1_det__10smoke__20260721T111442Z`, 531 ids, 252,581 chars).

## held-out-100, `context_recall_id`, read at k=50 (UNMATCHED UNITS)

Retrieval-only — no arm generated answers, so there are no judged metrics on this set.

| run | arm | recall_id | ids/q | chars/q | ceiling |
|---|---|---|---|---|---|
| `artefact_v1__heldout100__20260729T205930Z` | artefact_v1 (haiku interpreter) | **0.5938** | 458.3 | 224,669 | 1.0000 |
| `vector__heldout100__20260729T224153Z` | vector | 0.1120 | 50 | 16,783 | 0.7271 |
| `lucene__heldout100__20260729T223312Z` | lucene | 0.0739 | 50 | 41,855 | 0.7271 |

Paired: artefact − vector +0.4818, CI [+0.4294, +0.5341], W/L/T 93/3/4; artefact − lucene
+0.5199, CI [+0.4673, +0.5725], W/L/T 97/1/2; vector − lucene +0.0381, CI [+0.0240,
+0.0523], W/L/T 64/24/12.

**No matched-budget comparison exists on held-out-100** — there is no k=500 baseline run
and no hybrid run on this set. The gap above is read at a common k and is therefore not a
like-for-like lead. On this set the unit mismatch is worse than on gold-100, because the
baseline ceiling is 0.7271.

Per-type (n≈20 per cell, so readable):

| run | person | content | pr | company | url |
|---|---|---|---|---|---|
| `artefact_v1__heldout100…` | 0.636 | 0.658 | 0.375 | 0.827 | 0.463 |
| `vector__heldout100…` | 0.086 | 0.157 | 0.119 | 0.160 | 0.031 |
| `lucene__heldout100…` | 0.057 | 0.098 | 0.087 | 0.099 | 0.025 |

gold-100 per-type, same metric — **company (n=5) and url (n=1) are anecdotes**:

| run | person (22) | content (55) | pr (17) | company (5) | url (1) |
|---|---|---|---|---|---|
| `artefact_v1_det__gold100__20260801T072455Z` | 0.609 | 0.776 | 0.717 | 0.864 | 0.839 |
| `artefact_v1__gold100__20260718T231758Z` | 0.600 | 0.701 | 0.421 | 0.775 | 0.839 |
| `veck500__gold100…` (matched budget) | 0.322 | 0.458 | 0.415 | 0.298 | 0.172 |
| `hybrid__gold100…` | 0.088 | 0.114 | 0.163 | 0.088 | 0.046 |
| `vector__gold100…` | 0.087 | 0.115 | 0.155 | 0.070 | 0.046 |
| `lucene__gold100…` | 0.056 | 0.099 | 0.111 | 0.072 | 0.034 |

## Judged metrics

Two judged comparisons exist. Both are gold-100; neither covers held-out-100.

### Trio A — the complete one (judge `claude-haiku-4-5`, all cells n=100)

`artefact_v1__gold100__20260718T231758Z` + `lucene__gold100__20260627T003236Z__j-claude-haiku-4-5`
+ `vector__gold100__20260625T121031Z__j-claude-haiku-4-5`.

| metric | artefact_v1 | lucene | vector |
|---|---|---|---|
| `faithfulness` | 0.8967 | 0.7100 | 0.6719 |
| `answer_correctness` | 0.2381 | 0.1883 | 0.2018 |
| `context_recall_llm` | 0.4892 | 0.2074 | 0.3639 |
| `semantic_similarity` | 0.3645 | 0.4100 | 0.4183 |
| `context_recall_id` | 0.6363 | 0.0894 | 0.1129 |

Read at k=50, so unmatched units, and subject to the generator confound below. There is
**no matched-budget judged comparison** — the k=500 baseline runs generated no answers.

Per-type `context_recall_llm`: artefact person 0.205 / content 0.689 / pr 0.324 / company
0.000 / url 1.000; lucene 0.111 / 0.306 / 0.088 / 0.000 / 0.000; vector 0.088 / 0.417 /
0.637 / 0.000 / 0.667. Every arm scores 0.000 on company-type judged recall (n=5,
anecdote). Note that all three arms nevertheless score well above zero on company-type
`context_recall_id` — 0.775–0.864 for the artefact arms — so the company failure at
answer time is not a retrieval failure in the id sense.

The June canon-judged results (`lucene__gold100__20260627T003236Z`, judge
`qwen/qwen3.5-397b-a17b`) stand as a second judge's opinion on the same lucene answers:
faithfulness 0.7178 vs haiku's 0.7100, `context_recall_llm` 0.2068 vs 0.2074.

### Trio B — the 2026-07-23 judged set (judge `claude-haiku-4-5`) — PARTIAL, use with care

`JUDGE_artefactGlobal__gold100__20260723T170605Z__j-claude-haiku-4-5` +
`JUDGE_hybrid__gold100__20260723T172437Z__j-claude-haiku-4-5` +
`JUDGE_vector__gold100__20260723T173630Z__j-claude-haiku-4-5`. All three answer legs were
generated by `claude-haiku-4-5`, so this trio has **no generator confound** — which is what
it was for. But the judged cells did not complete:

| metric | artefactGlobal | hybrid | vector |
|---|---|---|---|
| `context_recall_id` | 0.6812 (n=100) | 0.1149 (n=100) | 0.1129 (n=100) |
| `faithfulness` | 0.8707 (n=68) | 0.8852 (n=95) | 0.8789 (n=97) |
| `context_recall_llm` | 0.6171 (n=91) | 0.3598 (n=96) | 0.3740 (n=100) |
| `answer_correctness` | **n=0, all 91 cells errored** | 0.1818 (n=96) | 0.1440 (n=47) |

`answer_correctness` is unusable across this trio: the artefact leg has no scored cells at
all and the vector leg has 47 of 100. `faithfulness` and `context_recall_llm` sit on
different denominators per arm, so cross-arm reads of them are unpaired unless
re-restricted to the common question set. There is no lucene leg in this trio.

The artefact leg here is not the shipped default: it runs `HERB_NO_REVIEW=1` and
`HERB_NORM_SCOPE=global` (it is the same retrieval as `artefact_v1_haikuGLOB`, recall_id
0.6812 in both).

### Judge-agreement study (`__n10` dirs, 10 questions, 4 judges)

Same 10 answers scored by four judges. Retrieval metrics are identical across dirs by
construction (recall_id 0.0855 lucene / 0.1179 vector everywhere); only judged cells move.

| arm | judge | faithfulness | answer_correctness | context_recall_llm |
|---|---|---|---|---|
| lucene | claude-haiku-4-5 | 0.682 | 0.104 | 0.157 |
| lucene | claude-opus-4-8 | 0.729 | 0.104 | 0.212 |
| lucene | claude-sonnet-5 | 0.701 | 0.134 | 0.167 |
| lucene | gemini-3.5-flash | 0.631 (n=4) | — | 0.157 |
| vector | claude-haiku-4-5 | 0.550 | 0.181 | 0.307 |
| vector | claude-opus-4-8 | 0.762 | 0.195 | 0.430 |
| vector | claude-sonnet-5 | 0.700 | 0.223 | 0.307 |
| vector | gemini-3.5-flash | — | — | — |

Judge spread on `faithfulness` reaches 0.21 (vector: haiku 0.550, opus 0.762) — larger
than several of the arm differences this file reports. **The gemini-3.5-flash judge is
effectively dead**: 4 of 10 faithfulness cells on lucene, nothing on vector. n=10 per cell
throughout — this study bounds judge disagreement, it does not measure any arm.

---

# Metric validity — read before comparing

| metric | cross-arm validity |
|---|---|
| `context_recall_id` | **valid, at a matched retrieval budget only** — exact: gold citation ids found among retrieved ids, denominator is the gold set and identical for every arm. But the ceiling is not: it is capped by the ids an arm retrieves, which at a common k differs ~10× between the artefact arms and the baselines (0.9085 vs 1.0000 on gold-100; 0.7271 vs 1.0000 on held-out-100). Compare at a matched id budget, or state the mismatch. |
| `faithfulness`, `answer_correctness`, `context_recall_llm` | **valid within one judge, and only over the questions both arms actually scored** — use Trio A (all cells n=100). Trio B's judged cells are partial. Note the generator confound below. |
| `context_precision_id` | **NOT cross-arm comparable** — denominator is every id carried by retrieved chunks; measured id-density is ~500/question for the artefact arms vs 50 for the baselines at k=50. |
| `context_precision_nonllm`, `context_recall_nonllm` | **NOT cross-arm comparable** — string similarity of context text vs gold context text, which penalizes the artefact arms' raw-JSON context format regardless of content. |
| `semantic_similarity`, `chrf`, `string_similarity`, `rouge`, `bleu` | weak here: gold answers are entity lists, answers are prose; treat as noise floors. |
| `exact_match`, `string_presence` | dead on this data — `exact_match` is 0.0000 for every arm in every run; `string_presence` 0.00–0.08. |

---

# Run inventory

**This file is the record; the folders are the evidence kept for it.** 35 run folders
remain under `v3/output/`, plus 5 cache/asset dirs (`embed_cache`, `interp_cache`,
`query_embed_cache`, `tag_cluster_cache`, `tags`) and 3 auxiliary dirs
(`ablation_boost_vs_facets`, `poolcut_forensic`, `smoke`).

What is kept on disk, and why:

- **Everything a judge or a generator produced.** Model spend is not repeatable for free,
  so those outputs are the asset — the gold-100 trio, the `__j-<judge>` re-judges, the
  8 judge-agreement dirs, the `JUDGE_*` set, the generator probes.
- **The runs behind the headline numbers**, so every figure quoted here can be checked
  against its own rows rather than taken on this file's word.
- **The two sweep results reported as separable** — `detGLOB` and `clusterKglob`.

Everything else was retrieval-only: no generator, no judge, interpretations and embeddings
already cached, so the run is remade in minutes and the numbers below are its record. Runs
that did not finish are not kept — an incomplete run carries no citable aggregate — and
depth truncations are not kept, because `truncate_k.py` re-slices them from a parent run
on demand.

A folder with no `run_manifest.json` is derived: outputs copied for a re-judge
(`__j-<judge>`). Its provenance is the parent named in `eval_manifest.json`.
`JUDGE_artefactGlobal__gold100__20260723T170605Z__j-claude-haiku-4-5` carries no
`eval_manifest.json`, so its judge is read from the folder name alone — UNVERIFIED.

Sections below quote runs whose folders are not retained. The folder name identifies which
run produced the number; re-running that configuration reproduces it.

## Headline runs — cite these

| dir | arm | set | k | generator | judge | date | completion |
|---|---|---|---|---|---|---|---|
| `artefact_v1_det__gold100__20260801T072455Z` | artefact_v1_det | gold100 | 50 | none (retrieval-only) | none | 2026-08-01 | 100/100 |
| `artefact_v1__gold100__20260718T231758Z` | artefact_v1 | gold100 | 50 | claude-sonnet-5 | claude-haiku-4-5 | 2026-07-19 | 100/100 |
| `lucene__gold100__20260627T003236Z` | lucene | gold100 | 50 | qwen3.5-397b (NIM) | qwen3.5-397b | 2026-06-27 | 100/100 |
| `lucene__gold100__20260627T003236Z__j-claude-haiku-4-5` | lucene | gold100 | 50 | (same answers) | claude-haiku-4-5 | 2026-07-20 | 100/100 |
| `vector__gold100__20260625T121031Z` | vector | gold100 | 50 | qwen3.5-397b (NIM) | qwen3.5-397b | 2026-06-25 | 100/100 |
| `vector__gold100__20260625T121031Z__j-claude-haiku-4-5` | vector | gold100 | 50 | (same answers) | claude-haiku-4-5 | 2026-07-20 | 100/100 |
| `hybrid__gold100__20260723T153637Z` | hybrid (α=0.5) | gold100 | 50 | none | none | 2026-07-23 | 100/100 |
| `veck500__gold100__20260723T154421Z` | hybrid (α=1.0 = vector) | gold100 | 500 | none | none | 2026-07-23 | 100/100 |
| `luck500__gold100__20260723T154401Z` | hybrid (α=0.0 = lucene) | gold100 | 500 | none | none | 2026-07-23 | 100/100 |
| `hybk500__gold100__20260723T154340Z` | hybrid (α=0.5) | gold100 | 500 | none | none | 2026-07-23 | 100/100 |
| `artefact_v1__heldout100__20260729T205930Z` | artefact_v1 | heldout100 | 50 | none | none | 2026-07-29 | 100/100 |
| `vector__heldout100__20260729T224153Z` | vector | heldout100 | 50 | none | none | 2026-07-29 | 100/100 |
| `lucene__heldout100__20260729T223312Z` | lucene | heldout100 | 50 | none | none | 2026-07-29 | 100/100 |

`vector__gold100__20260625T121031Z/eval_manifest.json` carries `judge_model: null` — it
predates judge-provenance recording; its judge was `qwen/qwen3.5-397b-a17b`, the same as
the lucene June run. UNVERIFIED from that folder alone.

## Judge studies

- `JUDGE_artefactGlobal|hybrid|vector__gold100__2026072{3}T17*` — Trio B above. The three
  `…T1703-1704Z` folders are dead (see below); the `…T1706/1724/1736Z` folders ran, and
  their `__j-claude-haiku-4-5` siblings hold the scores. Partial judged cells.
- `lucene|vector__gold100__…__j-{claude-haiku-4-5,claude-opus-4-8,claude-sonnet-5,gemini-3.5-flash}__n10`
  — the 8 judge-agreement dirs, 10 questions each, 2026-07-17/18.
- `artefact_v1__modeltest3_{qwen,glm}` (+ `__j-claude-haiku-4-5`) — 3-question generator
  probes (qwen3.5-397b and z-ai/glm-5.2). n=3. Not evidence of anything.

## Depth truncation

`truncate_k.py` re-emits a run at shallower depths without regeneration, so a depth curve
is regenerated from its parent run rather than stored. No truncation folders are kept.

The one rule that governs regenerating them: truncation rebuilds `context_ids` from the
kept chunks' own `meta.chunk_ids` when that field is present, and otherwise slices the
flat id list — which is exact only where ids align one per context. That holds for lucene
and vector, and never for the artefact arm, whose chunks carry many ids each. An artefact
run whose source lacks `meta.chunk_ids` cannot be truncated meaningfully at all: slicing
to exactly k discards the chunks' own ids and measures a truncated id list rather than the
arm at depth k.

**Depths produced on gold-100:** lucene and vector both at k = 5, 10, 15, 20, 25, 30, 40,
50 — the full list named on 2026-06-27 plus the k=25 ordered on 07-20. `context_recall_id`
runs 0.0217 → 0.0894 for lucene and 0.0284 → 0.1129 for vector across that range. These
were produced by re-slicing the k=50 runs, not as fresh runs at each depth.

The artefact arm has no valid gold-100 depth curve. Its k=50 run lacks `meta.chunk_ids`,
so truncating it discards the chunks' own ids and measures a truncated id list — the
`__k25` slice read 0.1309 against the parent's 0.6363 for that reason alone. The only
sound artefact depth curve is on 10smoke with ids rebuilt: 0.1804 / 0.3313 / 0.4453 /
0.7269 at k = 5 / 10 / 20 / 50 (n=10). A gold-100 artefact depth curve needs a fresh run
per depth, or a k=50 run that records `meta.chunk_ids`.

## Sweep families

All sweeps are gold-100, n=100, retrieval-only, `artefact_v1_det` unless noted. The
shipped default is the code default of every `HERB_*` flag
(`CURVE_WALK=0, WALK_GATE=0, AGG=sum, NORM=relative, NORM_SCOPE=per_path,
W_TAG=W_DESC=W_SCOPE=1.0, STR_FACET=0.0, STR_GUIDE=0.0`), realized by
`artefact_v1_det__gold100__20260801T072455Z` at **recall_id 0.7339**.

`TRACE__gold100`, `artefact_v1_WARMCACHE__gold100__20260723T134847Z`,
`artefact_v1_detCUR__gold100__probe` and `artefact_v1_detMAX__gold100__probe` are
per-question identical to it (100/100).

### WTAG — the tag-path weight `HERB_W_TAG`

| run | W_TAG | recall_id | delta vs default | 95% CI | W/L/T |
|---|---|---|---|---|---|
| `WTAG0__gold100` | 0.0 | 0.7401 | +0.0062 | [−0.0040, +0.0165] | 4/2/94 |
| `WTAG05__gold100` | 0.5 | 0.7338 | −0.0001 | [−0.0002, +0.0001] | 0/1/99 |
| (default) | 1.0 | 0.7339 | — | — | — |
| `WTAG2__gold100` | 2.0 | 0.7337 | −0.0002 | [−0.0006, +0.0002] | 0/1/99 |
| `WTAG4__gold100` | 4.0 | 0.7339 | 0.0000 | [0, 0] | 0/0/100 |

**`W_TAG=0` scores above the shipped default (0.7401 vs 0.7339), but the CI includes
zero** — the two configurations differ on 6 of 100 questions. Between 0.5 and 4.0 the flag
is inert: it changes at most one question's retrieval.

### WG — the flat-regime widening gate `HERB_WALK_GATE`

| run | config | recall_id | delta vs default | 95% CI | W/L/T |
|---|---|---|---|---|---|
| `WG__gold100` / `WG_TRACE__gold100` | gate on | 0.7135 | −0.0204 | [−0.0386, −0.0021] | 7/24/69 |
| `WG_GUIDE__gold100` | gate on + `STR_GUIDE=1.0` | 0.7108 | −0.0231 | [−0.0412, −0.0049] | 6/24/70 |
| `WG_WTAG0__gold100` | gate on + `W_TAG=0` | 0.7401 | +0.0062 | [−0.0040, +0.0165] | 4/2/94 |
| `WG_WTAG2__gold100` | gate on + `W_TAG=2` | 0.6949 | −0.0389 | [−0.0641, −0.0138] | 13/29/58 |

The gate loses to the shipped default. `WG_WTAG0` is per-question identical to `WTAG0`
(100/100 tied): with the tag path zeroed, the gate has nothing to gate.

### TAGINFORM and the tags-first admit sweep `HERB_TAG_FIRST` / `HERB_TAG_ADMIT`

| run | config | recall_id | delta vs default | 95% CI | W/L/T |
|---|---|---|---|---|---|
| `TAGINFORM__gold100` | tags-first, admit 1.0 | 0.7135 | −0.0204 | [−0.0386, −0.0021] | 7/24/69 |
| `artefact_v1_det__gold100__20260801T082038Z` | tags-first, admit 0.5 | 0.6969 | −0.0370 | [−0.0607, −0.0134] | 10/28/62 |
| `artefact_v1_det__gold100__20260801T110508Z` | tags-first, admit 0.25 | 0.6725 | −0.0613 | [−0.0911, −0.0316] | 9/38/53 |
| `artefact_v1_det__gold100__20260801T010614Z` | tags-first, admit 0.0 + `STR_GUIDE=1.0` | 0.3672 | −0.3667 | [−0.4329, −0.3005] | 1/72/27 |
| `artefact_v1_det__gold100__20260801T081836Z` | flat + `STR_GUIDE=1.0` | 0.7319 | −0.0019 | [−0.0049, +0.0010] | 0/3/97 |

Tags-first loses monotonically as the admit coefficient tightens; at admit 0.0 with the
cluster guide it collapses. `TAGINFORM` is per-question identical to `WG__gold100`.
The cluster guide alone (`STR_GUIDE=1.0`, flat regime) is neutral.

`HERB_TAG_FIRST` and `HERB_TAG_ADMIT` are not knobs in the engine: the numbers above stand
as the record of these runs, and none of the configurations in this table is reproducible
from the current code.

### Value-system grid — `HERB_AGG` / `HERB_NORM` / `HERB_NORM_SCOPE`

On the `artefact_v1` (model interpreter) leg with `HERB_NO_REVIEW=1`, reference
`artefact_v1_haikuCELL1__gold100__20260723T142732Z` (sum / relative / per-path), 0.6039:

| run | change | recall_id | delta | 95% CI | W/L/T |
|---|---|---|---|---|---|
| `artefact_v1_haikuGLOB…150615Z` | `NORM_SCOPE=global` | 0.6812 | **+0.0774** | [+0.0410, +0.1137] | 42/4/54 |
| `artefact_v1_haikuNONE…150818Z` | `NORM=none` | 0.6536 | **+0.0497** | [+0.0149, +0.0845] | 40/5/55 |
| `artefact_v1_haikuFACET…151010Z` | `STR_FACET=1.0` | 0.6129 | +0.0090 | [−0.0167, +0.0346] | 18/6/76 |
| `artefact_v1_haikuMAX…145223Z` | `AGG=max` | 0.6028 | −0.0011 | [−0.0310, +0.0289] | 15/15/70 |
| `artefact_v1_haikuABS…145827Z` | `NORM=absolute` | 0.5359 | −0.0680 | [−0.1072, −0.0287] | 27/38/35 |
| `artefact_v1_haikuMAXABS…150423Z` | `AGG=max`, `NORM=absolute` | 0.5246 | −0.0793 | [−0.1186, −0.0400] | 25/42/33 |

The same two knobs on the det leg (`…__probe` folders, vs the shipped default 0.7339):
`artefact_v1_detGLOB` 0.7394 (**+0.0055, CI [+0.0004, +0.0106]** — the one sweep delta on
the det leg whose CI excludes zero), `artefact_v1_detNONE` 0.7390 (+0.0051, CI [−0.0000,
+0.0102]), `artefact_v1_detABS` 0.7321 (−0.0017). **Global normalization scope beats the
shipped per-path default on both legs**, by a lot on the model leg and by a little on the
det leg.

`artefact_v1_detMAX__gold100__probe` (`AGG=max`) is per-question identical to the default
on all 100 questions — on the det leg the sum/max choice changes no retrieval at all. Why
it is inert there while it moves the model leg is UNVERIFIED from the run folders.

### cluster-K — `HERB_CURVE_WALK` (model interpreter leg, `NO_REVIEW=1`)

| run | config | recall_id | reference | delta | 95% CI | W/L/T |
|---|---|---|---|---|---|---|
| `artefact_v1_clusterK…170113Z` | curve walk | 0.7341 | haikuCELL1 | +0.1302 | [+0.0846, +0.1758] | 55/11/34 |
| `artefact_v1_clusterKglob…170853Z` | curve walk + global | **0.7492** | haikuGLOB | +0.0680 | [+0.0306, +0.1053] | 44/17/39 |

`artefact_v1_clusterKglob` is the **highest gold-100 `context_recall_id` anywhere in
`v3/output/` (0.7492)**. Against the shipped det default it is +0.0154, CI [−0.0177,
+0.0485] — ahead, but not separable. Against its own leg's reference it is clearly ahead.
Both runs hold ~470–478 ids and ~241–243k chars, so they are budget-comparable with the
det runs.

### scope-reach / tag-pure grid (2026-07-23), reference `artefact_v1_detBASE…061336Z` 0.7039

| run | config | recall_id | delta | 95% CI | W/L/T |
|---|---|---|---|---|---|
| `artefact_v1_detS…062047Z` | reach=1, pure=0 | 0.7045 | +0.0007 | [−0.0007, +0.0020] | 2/1/97 |
| `artefact_v1_detP…062056Z` | reach=0, pure=1 | 0.7040 | +0.0002 | [−0.0003, +0.0007] | 2/1/97 |
| `artefact_v1_detG…062102Z` | gate=1 | 0.6868 | −0.0171 | [−0.0350, +0.0009] | 9/18/73 |
| `artefact_v1_detSPG…061427Z` | reach=1, pure=1, gate=1 | 0.6616 | −0.0422 | [−0.0750, −0.0095] | 19/31/50 |

`HERB_SCOPE_REACH` and `HERB_TAG_PURE` are individually inert; the gate costs, and the
three together cost most.

### Named det probes with no recorded configuration — numbers valid, cause UNVERIFIED

| run | recall_id | delta vs default | ids/q |
|---|---|---|---|
| `artefact_v1_detA…20260721T174645Z` | 0.7001 | −0.0338 | 513.6 |
| `artefact_v1_detf__gold100__20260721T173011Z` | 0.7001 | −0.0338 | 513.7 |
| `artefact_v1_detE…20260721T174645Z` | 0.6972 | −0.0366 | 511.2 |
| `artefact_v1_detR…20260721T174645Z` | 0.6972 | −0.0367 | 512.1 |
| `artefact_v1_det__gold100__20260721T173011Z` | 0.6972 | −0.0367 | 512.1 |
| `artefact_v1_detW2…20260722T002321Z` | 0.7005 | −0.0333 | 497.4 |
| `artefact_v1_detW…20260722T000643Z` | 0.6883 | −0.0456 | 494.4 |
| `artefact_v1_detK…20260721T230502Z` | 0.6368 | −0.0971 | 377.0 |

Their manifests are identical apart from the timestamp — every `HERB_*` flag sits at the
default and no other field distinguishes them. **What each varied is not recoverable from
disk.** The scores are real; the attribution is not. `detK` retrieves 37.1 contexts /
377 ids on average, so it clearly cut the pool, but the mechanism is unrecorded.

### Named det experiments (2026-07-25 → 07-28), vs the shipped default 0.7339

| run | recall_id | delta | 95% CI | ids/q | note |
|---|---|---|---|---|---|
| `detREBUILD__gold100` | 0.6906 | −0.0433 | [−0.0681, −0.0186] | 498.8 | ships with two comparison runs made the same day: `detREBUILD__gold100_artComp` (`artefact_v1`, 0.6719) and `detREBUILD__gold100_vectorComp` (`vector`, 0.1129 — retrieval per-question identical to the June vector run, 100/100, generated no answers) |
| `detPOOLCUT__gold100` | 0.6816 | −0.0523 | [−0.0779, −0.0267] | 505.9 | forensic trace in `poolcut_forensic/detPOOLCUT_trace` |
| `detADMIT__gold100` | 0.6339 | −0.1000 | [−0.1362, −0.0638] | 494.9 | |
| `detCURVEK__gold100~` | 0.6358 | −0.0981 | [−0.1309, −0.0653] | 340.1 | folder name carries a trailing `~` |
| `detTAGBAR__gold100` | 0.6251 | −0.1088 | [−0.1460, −0.0715] | 490.8 | `HERB_TAG_MIN_SIM=0.78` |
| `detDESCFIRST__gold100` | 0.6251 | −0.1088 | [−0.1460, −0.0715] | 490.8 | same per-question recall as `detTAGBAR` (100/100), retrieved id sets differ on 4 questions |

None beat the shipped default.

## 10smoke and probe runs

The 10-question smoke runs are development traces, not results: **n=10 is anecdote scale,
and most were mid-development configurations whose flags went unrecorded**, so nothing can
state what they tested. Two are retained: `artefact_v1__10smoke__20260720T135813Z`, which
carries generated answers, and `artefact_v1_detK__10smoke__20260721T225332Z`, retrieval-only
at recall_id 0.7560.

The `smoke/` subfolder holds 18 June harness probes of 1–14 questions, five of which
produced no output at all.

## Runs that are not here

A run that does not finish is deleted, not archived: an incomplete run carries no citable
aggregate, and leaving it on disk makes it findable by anything globbing this directory.

Two gaps that matter, because no surviving run fills them:

- **No `artefact_v1_det` held-out run.** The one attempt reached 1 of 100 and its
  `failures.jsonl` is empty, so the cause is unknown. Every held-out number in this file
  comes from the interpreting leg.
- **No hybrid held-out run**, so the matched-budget comparison exists on gold-100 only.

The three `JUDGE_*` 2026-07-23 folders that scored nothing were a NIM `404` on every call;
their surviving siblings (`…T1706/1724/1736Z`) hold Trio B's judged cells.

---

# Claims the statistics do not carry

Measured on n=100 paired, sign-flip permutation with BCa intervals and Holm correction.
Each of these is a sentence that has been written somewhere and does not survive its own
test.

- **"Leads all valid metrics" is false as worded.** `answer_correctness` against vector is
  not significant (p=0.096), and it is generator-confounded besides.
- **`clusterKglob` is not the best configuration.** Its +0.0154 over the det default is
  p=0.36 — smaller than best-of-36 selection noise — and its nDCG ordering is *worse*. What
  does hold: it beats its own leg's flat-global by +0.068 (p=4e-4).
- **Scope-dominance is a property of this benchmark, not a retrieval law.** It reaches
  significance on the model leg only (+0.077 global, p=6e-4) and the det leg is insensitive
  after Holm. HERB questions name their product, and product is the gold set's partition
  key — the alignment is structural.
- **"Facets are null" overstates it.** The result is a bounded failure to detect (±0.035)
  with a weakly positive tendency, not a point null.
- **The "~0.80 wall" is a tried-set enumeration on n=10** and optimistically biased. The
  gold-100 maximum over everything ever tried is 0.7492.
- **Curve-walk versus a constant cut at the same mean depth is not significant** at n=10
  (exact p=0.203, driven by two K=5 zeros). Against flat@50 it is supported.

Two that do hold: the +0.030 combine rebuild is real (p=0.0005, CI +0.014…+0.054) and is a
defect fix rather than a swept knob; and the det leg beats the model leg on gold-100 by
0.130 (p=5e-5).

---

# What no run supports

State these as gaps, not as results either way.

- **No hybrid held-out run.** Held-out-100 covers `artefact_v1`, `vector`, `lucene` only.
- **No `artefact_v1_det` held-out run.** The one attempt is dead at 1/100. Every held-out
  number for the system under test comes from the model-interpreter configuration, so the
  det-vs-model gap measured on gold-100 (−0.0975) has no held-out check.
- **No matched-budget comparison on held-out-100.** No k=500 baseline runs exist for that
  set, so the only cross-arm reading available there is at a common k — which the
  unmatched-unit rule disqualifies as a lead.
- **No judged comparison at a matched budget, on any set.** The k=500 baseline runs
  generated no answers, so `faithfulness` / `answer_correctness` / `context_recall_llm`
  exist only at k=50, where the units differ.
- **No judged run on held-out-100 at all.** Every held-out run is retrieval-only.
- **No lucene leg in Trio B**, so the one generator-matched judged comparison covers
  artefact / hybrid / vector only — and its `answer_correctness` is unusable.
- **No judged run of the shipped-default det configuration.** All 0801/0802 det runs are
  retrieval-only.
- **No statistical power for any per-type claim on gold-100 company (n=5) or url (n=1).**
- **No cost or wall-clock comparison of the arms at a matched budget.** Judge-side token
  usage was never persisted for any eval in this shipment (`judge_usage: null`
  everywhere).
- **What `detA` / `detE` / `detR` / `detf` / `detW` / `detW2` / `detK` varied.** Not
  recorded in any manifest field.

---

# Known properties of the benchmark and runs

- **Generator confound (judged/answer metrics only):** in Trio A the artefact answers come
  from `claude-sonnet-5` and both baseline answers from `qwen3.5-397b`. Retrieval id
  metrics are unaffected — they are computed from retrieved ids, not answers. Trio B was
  built to remove this confound (all three legs generated by `claude-haiku-4-5`) but its
  judged cells did not complete.
- **Company questions are two-hop joins.** Products files name customers only as `CUST-`
  ids; `data/corpus/Salesforce__HERB/metadata/customers_data.json` maps ids → company
  names. `lucene` and `vector` index `products/` only (`lucene.py:161`, `vector.py:175`)
  and structurally cannot resolve the join. The artefact arms do reach metadata — their
  company-type `context_recall_id` is 0.775–0.864 on gold-100 (n=5) and 0.827 on
  held-out-100 (n=20) — yet every arm scores 0.000 on company-type `context_recall_llm`.
  The failure is at answer construction, not at id retrieval.
- **Headroom.** Against its own id budget, the shipped det default leaves +0.2661 on
  gold-100 and the model leg +0.4062 on held-out-100. Neither arm is ceiling-bound.
- **Token accounting eras.** June baseline runs record one legacy `tokens` total per
  question (reported as input; e.g. lucene 20,831, vector 4,981). The 2026-07-19 artefact
  run records the split schema (`tokens_in` / `cached_input_tokens` / `tokens_out` /
  `reasoning_tokens`) but its claude-lane counts exclude cache reads, so its recorded
  generator input (2 tokens on the first question) massively undercounts the real usage.
  Output counts include model reasoning where the backend bills it. `artefact_v1_det` runs
  record zeros throughout — that configuration makes no model calls.
- **Timing fields include queue and stall time.** The 2026-07-19 artefact run waited out an
  exhausted API budget mid-run; its per-call maxima (~8 h) are stall, not compute. Medians
  are representative.
- **Judge-side cost is unrecorded.** `judge_usage`, `judge_elapsed_s`, `judge_backend` and
  `judge_effort` are `null` in every `eval_manifest.json` in this shipment.
- **Retrieval-only evals leave `judge_model: null`.** All 2026-07-29 → 08-02 folders
  (held-out runs, the WTAG/WG/TAGINFORM/TRACE sweeps) are retrieval-only: `judge_model` is
  null because no judge ran, not because provenance is missing.
- **Two different "gold-100" sets exist.** Every run here uses `data/gold100.jsonl`, whose
  type mix is 55 content / 22 person / 17 pr / 5 company / 1 url. That is not the
  type-balanced set described elsewhere. Its aggregate is a content-weighted average and is
  not HERB's natural mix.
- **Manifests carry no git sha.** Provenance is flags plus timestamp only, so a run cannot
  be tied to the exact code that produced it.
- **Hybrid rankings are k-dependent.** The fusion min-maxes over a 4k window before the
  cut, so k=50 is not a prefix of k=500 — the two orderings diverge on 100/100 questions.
  A hybrid number is only comparable to another hybrid number read at the same k.
- **The vector query-embed cache is keyed by question id alone.** It does not key on the
  embedder, so a model change reuses stale vectors silently.
- **The haiku judge was never validated on artefact-style contexts.** Its agreement was
  measured against baseline-style contexts only, and the artefact's contexts are raw JSON
  records rather than prose.
- **Cache dirs are not runs.** `embed_cache` (2 files), `interp_cache` (300),
  `query_embed_cache` (804), `tag_cluster_cache` (1) and `tags` (4 tagger output files)
  hold build artefacts. `ablation_boost_vs_facets` and `poolcut_forensic` hold analysis
  side-output, not arm outputs. The loose `question_ids*.jsonl` files at the top of
  `v3/output/` are id manifests from 2026-06-28.
