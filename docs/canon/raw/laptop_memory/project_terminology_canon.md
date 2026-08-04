---
name: project-terminology-canon
description: "The project's exact vocabulary — artefact vs artifact, chunk/locator/record, citations, parts/areas/levels/anchor/walk/support/stated-scope, metric validity rules — and the agent coinages to avoid"
metadata: 
  node_type: memory
  type: project
  originSessionId: d7933ea3-74c0-40be-b1ac-cdc6dfcd745e
---

Grounded 2026-07-21 from v3/README.md, v3/output/DATA_README.md,
docs/state/2026-07-20-v1-query-relative-areas.md §3-4, CLAUDE.md, and the live code.

**Data/graph terms:**
- **artefact** (British spelling) = the system under test, the graph build. **artifact**
  (HERB's spelling) = one source record in the corpus carrying an `id` — the citation
  id space. Never mix.
- **Chunk** = ONE graph retrieval unit / source locator. Its `locator_json` selects
  record(s) in a raw file. A chunk is never "a record" or "hundreds of records";
  resolved artifact ids are the citation-space records its locator covers.
- **Hard fields** = chunk attributes (product, section, channel, employee_id, years,
  relevance_to_file). **Tag/HAS_TAG** edges carry w_chunk + aligned facets/w_facets +
  run_id. **Facets** = topic/entities/activity/temporal/evidence.
- **contexts** = resolved chunk texts handed to the generator (k of them = the shared
  top-k evidence budget). **context_ids** = artifact ids off the resolved records,
  deduped in rank order — NOT aligned 1:1 with contexts (truncate_k slicing
  context_ids[:k] is therefore invalid for the artefact arm; discovered 2026-07-21).
- **gold citations** = a question's `citations` (artifact ids). **oracle/quarantine** =
  corpus is oracle-stripped; truth read from raw by evaluators only; oracle sections
  (answerable/unanswerable_questions, product_profile) never retrievable.
- **gold-100**, **10smoke** = fixed question-id sets. Question ids `<product>::a|u::<index>`.

**Current arm (user's design) terms:** interpreter emits **parts** (+facets) and
**gate** = stated scope hints (only when explicitly named). Per part: kNN **pool** →
mutual-distance clusters → **areas**; part **anchors** at its highest-support tag;
**levels** = the anchor's containing-cluster chain (merge heights); **support** =
multi-k fuzzy weight (1/d² over K_LEVELS); **walk** = anchors open unconditionally,
widening by ascending height while pool < k; **stated-scope part** = the matching
chunk set as its own part; value sums across parts. "surface" (desc/structural) is an
AGENT coinage in code/docstrings, not user-named — flag for renaming.

**Metric validity (DATA_README — binding):**
- `context_recall_id`: VALID cross-arm (denominator = gold set).
- `context_precision_id`: NOT cross-arm comparable (denominator = every id carried by
  retrieved chunks; id-density differs per arm ~500 vs ~50). Within-arm variants OK.
- `context_*_nonllm`, text metrics: NOT cross-arm comparable (penalize raw-JSON contexts).
- Judged trio: valid within one judge only. Generator confound: artefact answers
  claude-sonnet-5 vs baselines qwen.

**Why:** The 2026-07-21 session drifted into agent coinages ("carrier chunks",
"id-density sweepers", "channels/surfaces", cross-arm precision claims) — the user
called it out; mixing terms causes wrong claims and defiled design language.
**How to apply:** Speak in the terms above; check DATA_README's validity table before
any cross-arm claim; never present precision_id or nonllm metrics across arms.
Related: [[user-concepts-are-canon-not-substitutes]].
