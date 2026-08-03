---
name: v3-question-id-scheme
description: "v3 mints question ids deterministically (HERB has NO native id) — <product>::a|u::<index> from (product file, array, position); 815+699=1514 unique; lives in v3/questions.py"
metadata: 
  node_type: memory
  type: project
  originSessionId: 47b27a98-6b98-483d-b6a5-fe4ebcda6175
---

DECIDED + BUILT 2026-06-22. HERB questions carry **no native id** — answerable
ones are dicts `{question, ground_truth, citations, type}`, unanswerable ones are
bare strings, both addressed only by array position. So v3 mints a stable id from
each question's physical coordinate:

`<product-stem>::<a|u>::<index>`  (e.g. `ActionGenie::a::0`, `ActionGenie::u::3`)

- The `a|u` marker is **required**, not decoration: both arrays are 0-indexed, so
  without it `answerable[0]` and `unanswerable[0]` collide.
- Deterministic (sorted product files + enumerate), collision-free (verified unique
  across all 1514: 815 answerable + 699 unanswerable), traces back to the exact raw
  record. It's the **paired-test join key**.
- The answerable index == HERB's `answerable_questions` position, so cross-build
  comparison pairs on `(product, index)` — NOT on the id string (format is build-local;
  do not claim string-equality with v1's `gold_<slug>_<n>`).

Lives in `v3/questions.py`: `mint_id()` + `load_questions(raw_root, ids=None)` →
`list[contract.QuestionWithTruth]`. Reads raw only (truth quarantine; pipelines never
import it). `ids` filter is EXACT — an unmatched id raises (no silent cohort shrink,
per [[no-silent-fallbacks]]). `ground_truth` normalized to a list (it's sometimes a
bare string in raw).

Record shape = `{id, question, type, ground_truth, citations}` — **NO `answerable`
field** (cut as redundant: a/u is already the id coordinate; `type` is the HERB
answer-category, `""` for unanswerable). A small dump emits three regenerable views in
`v3/output/`: `question_ids.jsonl` (1514), `.answerable.jsonl` (815),
`.unanswerable.jsonl` (699), each `{id, type, question}` (split is just an id-substring
filter — the loader stays source of truth).

Related: [[gold100-effective-n99]], [[v3-arm-model-stack]].
