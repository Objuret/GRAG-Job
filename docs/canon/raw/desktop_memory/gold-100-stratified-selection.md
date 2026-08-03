---
name: gold-100-stratified-selection
description: how the v3 gold-100 eval subset is chosen (seeded stratified round-robin by HERB type) and the caveat
metadata: 
  node_type: memory
  type: project
  originSessionId: 23885846-e32a-4121-8dab-cb041903d440
---

The v3 gold-100 is a balanced ANSWERABLE subset of HERB, drawn by seeded
(`seed=0`) round-robin over the HERB answer types (person/content/company/pr/url)
— equal allocation, 20/type — by `v3/build_question_sets.py:stratified_gold`,
written to `output/question_ids.gold100.jsonl`. This is the same method v1 used to
make its 100 list (the v1 stored file only kept `{id, question, reference}` and
dropped `type`, so the round-robin wasn't visible in the artifact — but the draw
was stratified).

**Why:** the natural mix is lopsided (person 260 … url 20), so a proportional
draw leaves rare types with too few items to say anything per-type; equal
allocation gives each type a usable count. `url` has only 20 total, so 20/type
drains the whole url stratum.

**How to apply:** report per-type on the gold-100 and do NOT compare its aggregate
to HERB's published average (that average is over the natural 815 mix). Unanswerables
carry no type, so the gold-100 is answerable-only; the 699 unanswerable abstention
test is a separate draw. Run a set by pointing the orchestrator's ids-file at the
emitted view. Related: [[v3-question-id-scheme]], [[gold100-effective-n99]].
