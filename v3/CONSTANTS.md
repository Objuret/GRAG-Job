# Constants and tunables in `v3/`

Every hard-coded constant and tunable in `v3/` — module-level constants, environment-variable
defaults (name and default recorded), and numeric or string literals acting as a threshold, limit,
cap, k, temperature, batch size, timeout, tolerance, seed, model id, prompt or dimension, including
ones in function signature defaults, inline in expressions, and inside Cypher strings. Trivially
structural literals (0/1 as index or identity, list indices, obvious loop bounds, message-truncation
slices in error strings) are out, as are the test files (`v3/test_*.py`, `v3/artefact/tests/`), which
set no runtime behaviour. The last column is the point of the table: **`unknown` means no evidence
for the value was found anywhere** — not in the user's turns, not in a design doc, not in a git
message, not in a sweep, not in the code's own comments. It is not a judgement that the value is
wrong, and it is never a guess dressed up as a reason. A rationale written in a comment after the
fact is not evidence of derivation and is recorded as `unknown` with the comment quoted.

**The `where` column names the file and the symbol, never a line number.** Two backticked parts —
`` `file` · `SYMBOL` `` — is a module-level assignment. Three — `` `file` · `scope` · `literal` `` —
is a literal with no symbol of its own, located by its enclosing function (or by the Cypher constant
it sits inside) and quoted. `check_constants.py` at the repo root parses this table, re-reads each
named symbol out of the source with `ast`, and compares the recorded value against the code's.

Two facts frame the artefact section. First, across the 21 numeric tunables and flags of
`artefact_v1.py` — `W_TAG`, `W_DESC`, `W_SCOPE`, `STR_FACET`, `STR_WCHUNK`, `STR_RELEVANCE`,
`STR_DESC_HINT`, `STR_SCOPE_MATCH`, `STR_GUIDE`, `K_LEVELS`, `GUIDE_TAU`, `GUIDE_C`, `GUIDE_M`,
`GUIDE_LAMBDA`, `GUIDE_SEED`, `AGG`, `NORM`, `NORM_SCOPE`, `KNN_OVERFETCH`, `CURVE_WALK`,
`WALK_GATE` — `git log -p --follow` shows **no assignment line ever removed or
modified**: each is at its first-commit value. The claim covers those 21 lines and
nothing else; model ids in particular are outside it (`INTERPRET_MODEL` has carried three values).
Second, the 2026-07-23 combine sweep and the 2026-08 weight sweeps ran *around* these defaults
without changing any of them; where a sweep produced a winner it was not adopted (`HERB_NORM_SCOPE`:
sweep `global` 0.6812, shipped `per_path` 0.6039). So almost nothing in the artefact arm qualifies as
**swept** under the definition "the value was selected by a sweep" — the sweeps are evidence *about*
the values, not evidence *for* them, and rows say so.

Third, **no row marked `swept` names a run folder that is still on disk.** Those folders were
retrieval-only and were not retained; `v3/output/DATA_README.md` is where their figures survive,
recomputed from the folders that do remain. Each such row opens with `evidence not retained` and
names what the surviving record says, so nobody reads the class as "the evidence is here". Where
a surviving folder contradicts the row, the row states the surviving reading — `CURVE_WALK` is the
case where it does.

Evidence keys: `turns:L<n>` = `docs/canon/raw/user_turns_all.md`; `state:<file>` = the flat
state-transfer folder under OneDrive; `canon:<file>` = `docs/canon/`.

---

## `pipelines/artefact_v1.py` — the artefact arm (V1 engine)

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `DATABASE` / `NEO4J_DATABASE` | `"herb-eval"` | `pipelines/artefact_v1.py` · `DATABASE` | which Neo4j DB every artefact number comes from — the session in `prepare_over_corpus` and in `answer_one_question`, the det leg's per-database product vocabulary, and one half of the cluster-guide cache-entry name built by `_guide_key`, so pointing the arm at another database also reads a different guide entry | **user-specified** — "i want to retrieve the old 'post thesis cleaned up v1 graph', the one using 'herb-eval' db, and run the the current v3 arm and eval at k=50 on that one" (turns:L344) |
| `DATASET_ID` / `HERB_DATASET_ID` | `"Salesforce__HERB"` | `pipelines/artefact_v1.py` · `DATASET_ID` | dataset filter on every File match: the area-chunk join, both description kNNs, the tag-affinity count and the stated-scope match | **derived** — the dataset's own name; it is the `Source.name` written by the v1 build |
| `RUN_ID` / `HERB_TAG_RUN_ID` | `"pilot_full_herb"` | `pipelines/artefact_v1.py` · `RUN_ID` | which tagging run's HAS_TAG edges are visible — the tag-pool filter, the area-chunk join and the affinity count — and the other half of the cluster-guide cache-entry name (`_guide_key`), which `build_tag_clusters.py` also reads its pool under | **derived** — the single run_id present in `herb-eval` (`state:2026-08-02-corpus-facts.md`: "Single run_id `pilot_full_herb`") |
| `INTERPRET_MODEL` | `"claude-haiku-4-5"` | `pipelines/artefact_v1.py` · `INTERPRET_MODEL` | the model behind both interpreter passes and the sufficiency review, and part of the interpretation cache key | **unknown** — the user names haiku for the Claude lane (turns:L1186) and for the evals (turns:L3820), and is aware the arm makes haiku calls (turns:L2865), but no turn names a model for the interpreter. Git shows three values with no rationale in any commit message |
| `ALL_FACETS` | `("topic", "entities", "activity", "temporal", "evidence")` | `pipelines/artefact_v1.py` · `ALL_FACETS` | the five-facet vocabulary AND the canonical axis order of everything keyed by facet: the interpreter's neutral vector and its clamped score vector, the per-part facet columns `_open_area` hands the Cypher, the restack of the guide cache's `.npz` membership matrices (`np.stack([z[f] for f in ALL_FACETS])`), the facet blend `_guidance` builds in that same order, `build_tag_clusters._FACET_COL` and its per-facet fit loop, and the det leg's trigger dict. It is folded into `_INTERP_SIG`, so editing it invalidates every cached plan | **borrowed** — the facet set baked into `herb-eval`'s `HAS_TAG.facets`; the arm must match the graph it queries |
| `GROUND_INDEX` | `"tag_emb"` | `pipelines/artefact_v1.py` · `GROUND_INDEX` | Neo4j vector index for tag kNN, and one of the two indexes `prepare_over_corpus` requires present before a run starts | **derived** — the index name `reembed_herb_eval.embed_tags` creates |
| `DESC_INDEX` | `"chunk_desc_emb"` | `pipelines/artefact_v1.py` · `DESC_INDEX` | Neo4j vector index for description kNN, in both the flat lookup and the curve walk's clustered variant; also required present at prepare | **derived** — the index name `reembed_herb_eval.embed_chunk_descriptions` creates |
| `K_LEVELS` | `(8, 16, 32, 64)` | `pipelines/artefact_v1.py` · `K_LEVELS` | the doubling level sequence in `_multi_k_support`; the tag-pool width and both description-pool widths (`K_LEVELS[-1]` = 64); the extension base for stated scope; `_n_levels`'s multiplicity; the level count in `_ABS_REF`; the sufficiency review's evidence ladder; and the `knn_levels` field of the retrieval meta | **unknown** — named by the user as exactly the problem: "arbitrarily decided hard limits, like the 64 chunk limit, i bet there is way more than 1 of these dumb limits lying around not beeing seen" (turns:L4217; the 64 is `K_LEVELS[-1]`). `canon:OPEN_DECISIONS.md` §15 and `canon:USER_CANON.md` Part IV.C both list it as underived. Measured consequence: "the distance term spans 1.41× while the level staircase spans 4× → `K_LEVELS` is the value model, not a budget" (`state:2026-08-02-corpus-facts.md`) |
| `KNN_OVERFETCH` | `4` | `pipelines/artefact_v1.py` · `KNN_OVERFETCH` | over-fetch multiplier on both vector indexes before the row filters trim, at all three kNN call sites | **unknown** — the comment's stated purpose is "giving the row filters headroom", and that purpose is measured vacuous: "Filter survival exactly 1.0 on both indexes; `Chunk.empty` exists on 0 chunks → every row filter is a no-op and `KNN_OVERFETCH`'s stated purpose is vacuous" (`state:2026-08-02-corpus-facts.md`) |
| `CURVE_WALK` / `HERB_CURVE_WALK` | `off` | `pipelines/artefact_v1.py` · `CURVE_WALK` | progressive-frontier walk regime vs the flat regime; it also switches the `kept_k` rule and the `curve_walk` meta block | **swept** — evidence not retained. the 10smoke runs behind the constant-cut comparison (`artefact_v1_detCW__10smoke__20260722T025802Z`, `detCURVEK__gold100~`) are not on disk, and `v3/output/DATA_README.md` records that comparison as not significant (exact p 0.203 at n=10). The surviving flag-isolated pair is gold-100 n=100, budget-matched at 478.0 vs 480.9 ids, both manifests differing in this flag alone: `artefact_v1_clusterKglob__gold100__20260723T170853Z` (on) 0.7492 against `JUDGE_artefactGlobal__gold100__20260723T170605Z` (off) 0.6812 — +0.0680, CI [+0.0306, +0.1053], sign-flip p 2.45e-4. The `on` leg carries no `eval_results.jsonl`, so its 0.7492 is recomputed from `arm_outputs.jsonl`, not read from a stored cell; the `off` leg's 0.6812 is stored and verified. Running the judge-free `evals` phase on that folder would store it. Isolating the flag is not isolating a mechanism: it switches the stop rule, clusters the description path, and changes the `kept_k` rule together. **And the per-query K did not bind in it:** `meta.curve_walk.kept` is 50 on 100/100 questions and `semantic` has a minimum of 122, so `kept_k = min(len(semantic), k)` took the caller's k every time. The stop rule fired on all 100 (`stopped` true, 7–146 levels opened) and never reached the depth. That delta is ordering and membership; **per-query K has never been measured on gold-100.** The default is off and no surviving measurement selects it |
| `DOOR_TRACE` / `HERB_DOOR_TRACE` | `off` | `pipelines/artefact_v1.py` · `DOOR_TRACE` | per-chunk path-value trace into `meta.door_trace` | **unknown** — the rationale is the comment's own: "observability only, retrieval untouched. Heavy (whole pool per question); for diagnosis runs." Nothing records the choice of default |
| `WALK_GATE` / `HERB_WALK_GATE` | `off` | `pipelines/artefact_v1.py` · `WALK_GATE` | whether the flat regime's widening loop counts only tag-reached chunks or the whole pool | **swept** — evidence not retained. `WG__gold100`, `WG_WTAG0__gold100`, `WG_WTAG2__gold100` and `WG_GUIDE__gold100` are not on disk; `v3/output/DATA_README.md` carries their figures (gate on 0.7135 against the default 0.7339, CI [−0.0386, −0.0021]). No record adopts on, and the default stands at off |
| `FRESH_INTERP` / `HERB_FRESH_INTERP` | `off` | `pipelines/artefact_v1.py` · `FRESH_INTERP` | re-run the interpreter vs read the cached plan | **unknown** — the rationale is the comment's own: the default "freezes the plan across a retrieval sweep so the comparison is not confounded by interpreter sampling". The confound is real; nothing records the choice of default |
| `NO_REVIEW` / `HERB_NO_REVIEW` | `off` | `pipelines/artefact_v1.py` · `NO_REVIEW` | disable the sufficiency cut | **unknown** — "off = review on" restates the flag. The rationale is the comment's own: "The default runs the review; disabling it lets a retrieval sweep measure retrieval alone, with no per-question content cut confounding the depth" |
| `W_TAG` / `HERB_W_TAG` | `1.0` | `pipelines/artefact_v1.py` · `W_TAG` | weight of the tag path in the cross-path sum, and the tag term of the door trace | **unknown** — swept at 0 / 0.5 / 2 / 4 (`WTAG0__gold100`, `WTAG05__gold100`, `WTAG2__gold100`, `WTAG4__gold100`, `WG_WTAG0__gold100`, `WG_WTAG2__gold100`, none on disk) and the sweep did not select 1.0. The two records of the `W_TAG=0` result disagree and cannot both be right: `state:2026-08-02-benchmark-validity-record.md` says "+0.027, t 2.56" against a Westfall–Young bar of +0.036, while `v3/output/DATA_README.md` gives +0.0062, CI [−0.0040, +0.0165], W/L/T 4/2/94 — and 6 nonzero deltas summing to a mean of +0.027 force t ≤ 2.514, so the state doc's pair is internally impossible. Settling it needs a fresh retrieval-only run at `HERB_W_TAG=0`. The value is what it was on its first commit |
| `W_DESC` / `HERB_W_DESC` | `1.0` | `pipelines/artefact_v1.py` · `W_DESC` | weight of the description path | **unknown** — never varied in any run manifest under `v3/output/` |
| `W_SCOPE` / `HERB_W_SCOPE` | `1.0` | `pipelines/artefact_v1.py` · `W_SCOPE` | weight of the stated-scope path | **unknown** — never varied in any run manifest under `v3/output/` |
| `STR_FACET` / `HERB_STR_FACET` | `0.0` | `pipelines/artefact_v1.py` · `STR_FACET` | strength of the edge facet-agreement modifier | **swept** — evidence not retained. `artefact_v1_haikuFACET__gold100__20260723T151010Z` is not on disk; `v3/output/DATA_README.md` carries it at 0.6129, +0.0090, CI [−0.0167, +0.0346] against its own leg's reference, and its "Claims the statistics do not carry" section rules the "facets are null" reading an overstatement — a bounded failure to detect (±0.035) with a weakly positive tendency, not a point null. The inert 0.0 ships and no measurement selects it |
| `STR_WCHUNK` / `HERB_STR_WCHUNK` | `1.0` | `pipelines/artefact_v1.py` · `STR_WCHUNK` | strength of the `w_chunk` modifier | **unknown** — never varied in any manifest. Named in `state:2026-08-02-benchmark-validity-record.md` as one of three values whose origin "cannot be closed" |
| `STR_RELEVANCE` / `HERB_STR_RELEVANCE` | `1.0` | `pipelines/artefact_v1.py` · `STR_RELEVANCE` | strength of the `relevance_to_file` modifier | **unknown**, and flagged as an open contamination channel: `relevance_to_file` "was produced by a v1 LLM stage whose prompt contained the answer key … never ablated" (`state:2026-08-02-benchmark-validity-record.md`). That doc's "all 35 manifests show 1.0" describes a population that is no longer on disk: 22 `run_manifest.json` files remain, 5 of them carry `HERB_STR_RELEVANCE`, all at 1.0 |
| `STR_DESC_HINT` / `HERB_STR_DESC_HINT` | `1.0` | `pipelines/artefact_v1.py` · `STR_DESC_HINT` | strength of the description hint-match modifier | **unknown** — never varied in any manifest |
| `STR_SCOPE_MATCH` / `HERB_STR_SCOPE_MATCH` | `1.0` | `pipelines/artefact_v1.py` · `STR_SCOPE_MATCH` | strength of the stated-scope match-fraction modifier | **unknown** — never varied in any manifest |
| `DESC_HINT_M` / `HERB_DESC_HINT_M` | `2.0` | `pipelines/artefact_v1.py` · `DESC_HINT_M` | the factor a scope-hint-matching description chunk carries into the description path's modifier, lerped by `STR_DESC_HINT` | **unknown** — nothing derives 2.0; it is exposed as an env coefficient and recorded in `RETRIEVAL_FLAGS`, so a run's manifest carries the value it ran under. Named in `state:2026-08-02-benchmark-validity-record.md` as one of three values whose origin "cannot be closed" |
| `STR_GUIDE` / `HERB_STR_GUIDE` | `0.0` | `pipelines/artefact_v1.py` · `STR_GUIDE` | strength of the cluster-guide lift on tag support; 0 is off — no cache load, no `guide_stats`, no `guide` meta block. Values below 0 fail loud at import | **swept** — evidence not retained. the "cluster guide, −0.003, t −1.36" figure comes from `state:2026-08-02-benchmark-validity-record.md`, which names no run. It matches `v3/output/DATA_README.md`'s flat guide-alone row (`artefact_v1_det__gold100__20260801T081836Z`, −0.0019, CI [−0.0049, +0.0010]), not `WG_GUIDE__gold100` (−0.0231), which varies the walk gate as well and whose delta the gate alone accounts for (−0.0204). Neither folder is on disk. Off ships |
| `GUIDE_TAU` / `HERB_GUIDE_TAU` | `0.01` | `pipelines/artefact_v1.py` · `GUIDE_TAU` | membership-cell floor; cells below it drop before the guidance mass is summed | **unknown** — cited by name in `canon:CONTRADICTION_MAP.md` §2 as one of the arm's unbased constants |
| `GUIDE_C` / `HERB_GUIDE_C` | `128` | `pipelines/artefact_v1.py` · `GUIDE_C` | number of k-means prototypes per facet in the guide cache; also names the cache entry | **unknown** |
| `GUIDE_M` / `HERB_GUIDE_M` | `1.5` | `pipelines/artefact_v1.py` · `GUIDE_M` | fuzzifier of the membership exponent; values at or below 1.0 fail loud at import | **unknown** — the `> 1.0` guard is derived (the exponent divides by `m − 1`); 1.5 itself has no record |
| `GUIDE_LAMBDA` / `HERB_GUIDE_LAMBDA` | `0.05` | `pipelines/artefact_v1.py` · `GUIDE_LAMBDA` | participation floor λ in ω̃ = λ + (1−λ)·ω; names the cache entry and is applied by `build_tag_clusters.floor_participation` | **unknown** |
| `GUIDE_SEED` / `HERB_GUIDE_SEED` | `20260731` | `pipelines/artefact_v1.py` · `GUIDE_SEED` | k-means++ seed; also names the cache entry | **unknown** — the digits are the build date (2026-07-31), not a property of the data |
| `AGG` / `HERB_AGG` | `"sum"` | `pipelines/artefact_v1.py` · `AGG` | how a path folds a chunk's support over the parts that vouch for it; an unknown value fails loud at import | **swept** — evidence not retained. `artefact_v1_haikuMAX__gold100__20260723T145223Z`, `haikuMAXABS__…` and `detMAX__gold100__probe` are not on disk; `v3/output/DATA_README.md` carries their figures (`max` −0.0011, CI [−0.0310, +0.0289] on the model leg, per-question identical to the default on the det leg). `sum` ships and no measurement selects it |
| `NORM` / `HERB_NORM` | `"relative"` | `pipelines/artefact_v1.py` · `NORM` | scale each path's base reaches before the weighted sum; an unknown value fails loud at import | **swept** — evidence not retained. `artefact_v1_haikuABS__gold100__20260723T145827Z`, `haikuNONE__…`, `detABS__gold100__probe` and `detNONE__gold100__probe` are not on disk; `v3/output/DATA_README.md` carries their figures (`none` +0.0497, `absolute` −0.0680 on the model leg). `relative` ships and no measurement selects it |
| `NORM_SCOPE` / `HERB_NORM_SCOPE` | `"per_path"` | `pipelines/artefact_v1.py` · `NORM_SCOPE` | min-max per path, or globally over the union; inert unless `NORM` is `relative`; an unknown value fails loud at import | **unknown** — and the measurement contradicts the shipped value on both legs: `global` reads 0.6812 against `per_path` 0.6039 on the model leg, and `artefact_v1_detGLOB__gold100__probe` — on disk — reads 0.7394 against the det default's 0.7339, +0.0055, CI [+0.0004, +0.0106], the one det-leg sweep delta whose CI excludes zero. `artefact_v1_haikuGLOB__gold100__20260723T150615Z` is not on disk, but `JUDGE_artefactGlobal__gold100__20260723T170605Z` carries the same flag set and recomputes to 0.6812 exactly. No record explains keeping `per_path` |
| `_ABS_REF_DIST` | `0.5` | `pipelines/artefact_v1.py` · `_ABS_REF_DIST` | reference cosine distance at which absolute normalization saturates to 0.5 | **unknown** — inert at the default (`NORM` is `relative`) |
| `_ABS_UNIT` | `4.0` | `pipelines/artefact_v1.py` · `_ABS_UNIT` | support one level earns at the reference distance; also scales the stated-scope path's per-query reference | **derived** — `1 / _ABS_REF_DIST ** 2` |
| `_ABS_REF` | `16.0` | `pipelines/artefact_v1.py` · `_ABS_REF` | the tag and description paths' absolute reference | **derived** — `len(K_LEVELS) * _ABS_UNIT`; inherits `K_LEVELS`'s unknown provenance |
| `RETRIEVAL_FLAGS` | `23 entries` | `pipelines/artefact_v1.py` · `RETRIEVAL_FLAGS` | the regime switches and combine coefficients the runner copies into `run_manifest.json`; the det leg extends it with `HERB_DET_FACETS` | **derived** — one entry per exposed env knob, so a run documents its own value model |
| `EMBED_CACHE_DIR` | `output/query_embed_cache` | `pipelines/artefact_v1.py` · `EMBED_CACHE_DIR` | on-disk query-vector cache location | **unknown** — the content addressing names the entries, not the directory; nothing forces this location |
| `INTERP_CACHE_DIR` | `output/interp_cache` | `pipelines/artefact_v1.py` · `INTERP_CACHE_DIR` | on-disk interpretation cache location | **unknown** — the content addressing names the entries, not the directory; nothing forces this location |
| `GUIDE_CACHE_DIR` | `output/tag_cluster_cache` | `pipelines/artefact_v1.py` · `GUIDE_CACHE_DIR` | cluster-guide cache location, read by the arm and written by `build_tag_clusters.py` | **unknown** — the entry name carries the database, the run and every `HERB_GUIDE_*` value, but nothing forces the directory; `build_tag_clusters.py` imports this constant rather than agreeing with it independently |
| `GATE_SECTIONS` | `9 section names` | `pipelines/artefact_v1.py` · `GATE_SECTIONS` | the full top-level section enum of a HERB product file, oracle sections included. Its one read site is `OFFERED_SECTIONS`, which subtracts `EXCLUDED_SECTIONS`; the interpreter is offered that subset, never this tuple | **derived** — the top-level collection keys of a HERB product file |
| `EXCLUDED_SECTIONS` | `("answerable_questions", "unanswerable_questions", "product_profile")` | `pipelines/artefact_v1.py` · `EXCLUDED_SECTIONS` | sections retrieval can never return, and the sections subtracted from the interpreter's offered enum | **derived** — the eval oracle; the same strip `artefact/derive_corpus.py` · `ORACLE_KEYS` performs, plus `product_profile` |
| `_EXCLUDED_PARAM` | `3 section names` | `pipelines/artefact_v1.py` · `_EXCLUDED_PARAM` | the list form bound as `$excludedSections` in all four Cyphers: area chunks, both description kNNs, tag affinity and stated scope | **derived** — the Neo4j driver takes a list, not a tuple |
| `OFFERED_SECTIONS` | `6 section names` | `pipelines/artefact_v1.py` · `OFFERED_SECTIONS` | the enum named inside the pass-1 prompt, the whitelist `_parse_gate` validates the model's answer against, and the vocabulary the det leg matches literally | **derived** — `GATE_SECTIONS` minus `EXCLUDED_SECTIONS`; an excluded section can never be retrieved, so it is never offered |
| `FILLER` | `{"data", "information", "content", "record", "text", "chunk", "item", "find"}` | `pipelines/artefact_v1.py` · `FILLER` | interpreter tags dropped as generic before the parts are formed; also folded into `_INTERP_SIG` | **unknown** — no derivation from the corpus. `state:2026-08-02-benchmark-validity-record.md` names `"find"` in this live set as one of five terms whose presence shows the question file was open when it was written |
| `RAW_ROOT` | `data/raw` | `pipelines/artefact_v1.py` · `RAW_ROOT` | root every locator must resolve inside; enforced by `is_relative_to` in `_load_verified_doc` | **derived** — the untouched raw the graph references |
| `_PASS1_SYSTEM` | the three-step interpretation prompt | `pipelines/artefact_v1.py` · `_PASS1_SYSTEM` | what pass 1 emits: description, tags, gate; it interpolates `OFFERED_SECTIONS` and is folded into `_INTERP_SIG` | **unknown** — agent-written prose; no record derives the wording |
| `_PASS2_SYSTEM` | the five-facet scoring prompt | `pipelines/artefact_v1.py` · `_PASS2_SYSTEM` | the per-tag facet score array and its declared 0.0–1.0 scale; folded into `_INTERP_SIG` | **unknown** — agent-written prose |
| `_REVIEW_SYSTEM` | the sufficiency-verdict prompt | `pipelines/artefact_v1.py` · `_REVIEW_SYSTEM` | the `{"sufficient": bool}` contract the review turn answers under | **unknown** — agent-written prose |
| `_INTERP_SIG` | sha256 over 2 prompts, `FILLER`, `ALL_FACETS` and 5 function sources | `pipelines/artefact_v1.py` · `_INTERP_SIG` | the part of the interpretation cache key that invalidates every cached plan when a prompt, the facet set, the filler set or any of `_interpret` / `_clean_tag` / `_parse_gate` / `_validate_scores` / `_extract_json` changes | **derived** — a cached plan may only be served by the interpreter that would produce it now |
| NEO4J URI default | `"neo4j://localhost:7687"` | `pipelines/artefact_v1.py` · `_driver()` · `"neo4j://localhost:7687"` | Neo4j endpoint | **borrowed** — the Neo4j Bolt default port |
| NEO4J user default | `"neo4j"` | `pipelines/artefact_v1.py` · `_driver()` · `"neo4j"` | Neo4j user | **borrowed** — the Neo4j install default |
| `w_chunk` null default | `coalesce(r.w_chunk, 0.0)` | `pipelines/artefact_v1.py` · `_AREA_CHUNKS_CYPHER` · `coalesce(r.w_chunk, 0.0)` | what an edge with no `w_chunk` contributes. It is the modifier `STR_WCHUNK` lerps at full strength, so a null reads as 0.0 and `_mod` collapses that chunk's whole tag score to zero; it is also the secondary sort key choosing which edge supplies a chunk's modifiers | **unknown** — no record chooses 0.0 over 1.0 (the neutral factor), and the modifier is at strength 1.0 |
| `relevance_to_file` null default | `coalesce(c.relevance_to_file, 1.0)` | `pipelines/artefact_v1.py` · `_AREA_CHUNKS_CYPHER` · `coalesce(c.relevance_to_file, 1.0)` | what a chunk with no `relevance_to_file` contributes to the tag path | **derived** — 1.0 is the inert factor under `_mod`, so a missing value neither lifts nor damps |
| facet-weight null default | `coalesce(r.w_facets[fi], 0.0)` | `pipelines/artefact_v1.py` · `_AREA_CHUNKS_CYPHER` · `coalesce(r.w_facets[fi], 0.0)` | what a missing per-facet weight adds to the edge's facet term | **unknown** — "contributes nothing" restates what 0.0 does. A neutral prior of 1.0 on an unweighted facet is equally available and nothing records the choice between them |
| unknown-facet fallback | `ELSE 0.0` | `pipelines/artefact_v1.py` · `_AREA_CHUNKS_CYPHER` · `ELSE 0.0` | the part-side score for an edge facet name outside `ALL_FACETS` | **unknown** — "contributes nothing" restates what 0.0 does. An edge facet outside `ALL_FACETS` is scored silently rather than surfaced, and nothing records that choice |
| empty-chunk null default | `coalesce(c.empty, false)` | `pipelines/artefact_v1.py` · `_AREA_CHUNKS_CYPHER` · `coalesce(c.empty, false)` | a chunk without the `empty` flag counts as non-empty and stays retrievable; the same guard is in both description kNNs, the affinity count and the stated-scope match | **derived** — absence of the flag is absence of the condition. Measured inert: `Chunk.empty` exists on 0 chunks (`state:2026-08-02-corpus-facts.md`) |
| section null default | `coalesce(c.section, "")` | `pipelines/artefact_v1.py` · `_AREA_CHUNKS_CYPHER` · `coalesce(c.section, "")` | a chunk with no section is compared as the empty string, so it is never in the excluded set; same guard in both description kNNs, the affinity count and the stated-scope match | **derived** — a sectionless chunk belongs to no excluded section |
| edge-facets null default | `coalesce(r.facets, [])` | `pipelines/artefact_v1.py` · `_AREA_CHUNKS_CYPHER` · `coalesce(r.facets, [])` | an edge with no facets array iterates zero facets and scores a facet term of 0 | **derived** — an empty range over an absent list |
| years null default | `coalesce(c.years, [])` | `pipelines/artefact_v1.py` · `_hint_terms()` · `coalesce(c.years, [])` | a chunk with no years never matches a stated year | **derived** — an empty set intersects nothing |
| interpreter `temperature` | `0` | `pipelines/artefact_v1.py` · `_chat_json()` · `"temperature": 0` | interpreter and review sampling | **derived** — determinism for eval reproducibility (no effect on the claude CLI lane, which exposes no temperature: `nim._claude_chat`) |
| interpreter attempts | `2` tries | `pipelines/artefact_v1.py` · `_chat_json()` · `for attempt in (1, 2)` | how many times one interpreter turn may be issued before a malformed payload fails loud — two tries, i.e. one retry. An empty or truncated response fails on the first try regardless | **unknown** |
| interpreter NIM timeout | `480.0` s | `pipelines/artefact_v1.py` · `_chat_json()` · `timeout=480.0` | per-try wall clock for an interpreter or review call | **unknown** — git `90d1074` names the change ("480s NIM timeouts") with no measurement behind it |
| year sanity range | `1000 <= yi <= 9999` | `pipelines/artefact_v1.py` · `_parse_gate()` · `1000 <= yi <= 9999` | which parsed years survive into stated scope | **derived** — the 4-digit year form |
| pass-1 `max_tokens` | `512` | `pipelines/artefact_v1.py` · `_interpret()` · `512` | budget for description + tags + gate JSON | **unknown** |
| neutral facet value | `0.2` | `pipelines/artefact_v1.py` · `_interpret()` · `0.2` | the facet score of a tag pass 2 left unscored, the per-facet fallback inside the clamp, and the whole facet vector of the no-parts fallback part | **unknown** — 0.2 is 1/5 of the facet count, but nothing records that as the reason |
| pass-2 `max_tokens` | `1024` | `pipelines/artefact_v1.py` · `_interpret()` · `1024` | budget for the per-tag facet score array | **unknown** |
| facet clamp | `[0.0, 1.0]` | `pipelines/artefact_v1.py` · `_interpret()` · `min(1.0, max(0.0, …))` | range each returned facet value is clipped to | **derived** — the pass-2 prompt's own declared 0.0–1.0 scale |
| `_gap_break` minimum history | `3` gaps | `pipelines/artefact_v1.py` · `_gap_break()` · `len(gaps) < 3` | walked gaps needed before the stop test can fire | **unknown** |
| `_gap_break` float-noise floor | `1e-9` | `pipelines/artefact_v1.py` · `_gap_break()` · `1e-9` | a gap at or below this is never a break, and the same margin is added to the threshold | **unknown** — the guard is real and the magnitude is not derived; nothing records why 1e-9 |
| `_gap_break` threshold | `mean + 2.0 × std` | `pipelines/artefact_v1.py` · `_gap_break()` · `2.0 * float(np.std(gaps))` | how far a gap must jump to stop the curve walk | **unknown** — a two-sigma rule with no record of why two. Inert at the default (`CURVE_WALK` off) |
| distance floor in fuzzy support | `1e-6` | `pipelines/artefact_v1.py` · `_multi_k_support()` · `1e-6` | divide-by-zero guard in 1/d² | **unknown** — the Keller et al. 1985 citation covers the 1/d² weighting, not the floor; the guard is real and the magnitude is not derived |
| level doubling factor | `2` | `pipelines/artefact_v1.py` · `_multi_k_support()` · `levels[-1] * 2` | how the level sequence extends past `K_LEVELS[-1]` for the stated-scope path, and the same step in `_n_levels` | **derived** — the doubling `K_LEVELS` itself is built on |
| `_tag_affinity` lift | `support × (1 + affinity)` | `pipelines/artefact_v1.py` · `_part_levels()` · `1.0 + affinity.get(n, 0.0)` | structural affinity's multiplier on tag support, before the anchor argmax; affinity is a fraction in [0, 1], so the ceiling is 2× | **unknown** — an unflagged up-to-2× with no `HERB_STR_*` exposure and no manifest entry: "`_tag_affinity` is an unflagged ×2 applied before the anchor argmax — changes membership, no `STR_*`, in no manifest" (`state:2026-08-02-corpus-facts.md`) |
| tag-pool width | `k = K_LEVELS[-1]` = 64 | `pipelines/artefact_v1.py` · `_part_levels()` · `k=K_LEVELS[-1]` | LIMIT on the tag kNN Cypher | **unknown** — inherits `K_LEVELS`; this and the two description widths are the "64 chunk limit" the user named (turns:L4217) |
| tag-pool fetch | `KNN_OVERFETCH × 64` = 256 | `pipelines/artefact_v1.py` · `_part_levels()` · `fetch=KNN_OVERFETCH * K_LEVELS[-1]` | index over-fetch before the run filter and the trim | **unknown** — inherits both constants above |
| level-log height rounding | `4` dp | `pipelines/artefact_v1.py` · `_retrieve()` · `round(lv["height"], 4)` | precision of the merge heights recorded per level in `meta.parts` | **unknown** — forensics only, no retrieval effect; nothing records why 4 |
| level-log tag sample | `[:6]` | `pipelines/artefact_v1.py` · `_retrieve()` · `lv["tags"][:6]` | how many tag names per level land in `meta.parts` | **unknown** — forensics only, no retrieval effect |
| walk-entry height rounding | `4` dp | `pipelines/artefact_v1.py` · `open_level()` · `round(height, 4)` | precision of the opening height recorded per walk entry, in the tag and description branches alike | **unknown** — forensics only, no retrieval effect; nothing records why 4 |
| flat desc-kNN width / fetch | `64` / `256` | `pipelines/artefact_v1.py` · `open_desc()` · `k=K_LEVELS[-1]`, `fetch=KNN_OVERFETCH * K_LEVELS[-1]` | the flat regime's description neighborhood size | **unknown** — inherits `K_LEVELS` and `KNN_OVERFETCH` |
| curve desc-area width / fetch | `64` / `256` | `pipelines/artefact_v1.py` · `open_desc_area()` · `k=K_LEVELS[-1]`, `fetch=KNN_OVERFETCH * K_LEVELS[-1]` | the curve walk's clustered description neighborhood size | **unknown** — inherits `K_LEVELS` and `KNN_OVERFETCH` |
| frontier sequence bound | `1 << 30` | `pipelines/artefact_v1.py` · `_retrieve()` · `range(1 << 30)` | tiebreaker counter capacity for the curve walk frontier | **unknown** — a ceiling far above any real frontier size is the shape of the rule, not the number; nothing records why 1 << 30 |
| selected-score rounding | `4` dp | `pipelines/artefact_v1.py` · `_retrieve()` · `round(sc, 4)` | precision of the score recorded per selected chunk | **unknown** — recorded after ranking, so it cannot change order; that makes 4 harmless, not derived |
| guide mean-g rounding | `4` dp | `pipelines/artefact_v1.py` · `_retrieve()` · `round(guide_stats["g_sum"] / guide_stats["g_n"], 4)` | precision of the mean guidance mass in `meta.guide` | **unknown** — forensics only, no retrieval effect; nothing records why 4 |
| door-trace rounding | `6` dp | `pipelines/artefact_v1.py` · `_retrieve()` · `round(…, 6)` | precision of the per-path trace values | **unknown** — forensics only, no retrieval effect; nothing records why 6 here where every other rounding in the arm is 4 |
| review evidence ladder | `K_LEVELS` (8/16/32/64) | `pipelines/artefact_v1.py` · `_sufficient_cut()` · `for lv in [l for l in K_LEVELS if l < len(contexts)]` | the depths at which sufficiency is asked | **unknown** — inherits `K_LEVELS`; reuses a kNN width as a review cadence with no record connecting the two |
| review digest length | `240` chars per context | `pipelines/artefact_v1.py` · `_sufficient_cut()` · `contexts[i][:240]` | how much of each context the sufficiency reviewer sees | **unknown** |
| review `max_tokens` | `128` | `pipelines/artefact_v1.py` · `_sufficient_cut()` · `128` | budget for the `{"sufficient": bool}` verdict | **unknown** — a one-key JSON object needs a fraction of 128; having a budget is derived, the number is not |
| `answer_one_question` `k` default | `50` | `pipelines/artefact_v1.py` · `answer_one_question()` · `k: int = 50` | retrieval depth when the caller passes none | **user-specified** — "so, for academic rigor, we have done k=50 now" (turns:L217), and he runs it himself: "python run.py --arm herb_eval --set gold -k 50" (turns:L394). He later rules the cross-arm reading invalid: "k=50 does not mean the same for all arms, and thats retarded" (turns:L2901) |

## `pipelines/artefact_v1_det.py` — the deterministic leg

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `INTERPRET_MODEL` | `"deterministic"` | `pipelines/artefact_v1_det.py` · `INTERPRET_MODEL` | manifest label for the no-model leg | **unknown** — a label, not a model; the manifest needs a string and nothing forces this one |
| `_EID` | `\beid_[0-9a-f]+\b` | `pipelines/artefact_v1_det.py` · `_EID` | employee-id literal match in the stated scope | **derived** — HERB's `eid_*` id form (`metadata/employee.json`) |
| `_YEAR` | `\b(?:19\|20)\d{2}\b` | `pipelines/artefact_v1_det.py` · `_YEAR` | year literal match in the stated scope | **derived** — 4-digit years in the 1900s/2000s |
| `_FACET_MODE` / `HERB_DET_FACETS` | `""` | `pipelines/artefact_v1_det.py` · `_FACET_MODE` | which of the support / routing / edges facet placements run; also the `HERB_DET_FACETS` manifest entry and the `facet_channel` meta field | **unknown** — `artefact_v1_detf__gold100__20260721T173011Z` and `detA`/`detE`/`detR__gold100__20260721T174645Z` are not on disk, and `v3/output/DATA_README.md` lists that whole family under "Named det probes with no recorded configuration — numbers valid, cause UNVERIFIED". The one surviving folder of the same 2026-07-21 family, `artefact_v1_detK__gold100__20260721T230502Z`, carries `retrieval_flags: {}` — no `HERB_DET_FACETS` value was recorded in that era. Off ships; nothing measures the three placements |
| `FACETS_ON` | `off` | `pipelines/artefact_v1_det.py` · `FACETS_ON` | the support-shaper placement, on for `_FACET_MODE` in `1` / `support` / `all` | **derived** — reads `_FACET_MODE` |
| `ROUTING_ON` | `off` | `pipelines/artefact_v1_det.py` · `ROUTING_ON` | the distance-shaper placement, on for `routing` / `all` | **derived** — reads `_FACET_MODE` |
| `EDGES_ON` | `off` | `pipelines/artefact_v1_det.py` · `EDGES_ON` | the per-edge facet placement, on for `edges` / `all` | **derived** — reads `_FACET_MODE` |
| `_ANCHOR_TEXTS` | `5 facet-meaning sentences` | `pipelines/artefact_v1_det.py` · `_ANCHOR_TEXTS` | read twice: `_anchors` embeds its values, in order, as the rows of the anchor matrix each tag's geometry is scored against; `_facet_direction` iterates its keys, in the same order, to lay the question's trigger weights out against those rows. The key order is therefore load-bearing, not decoration — see the invariant below | **unknown** — agent-written prose; no record derives the wording |
| `_FACET_WORDS` | `4 keyword lists` | `pipelines/artefact_v1_det.py` · `_FACET_WORDS` | which facets a question's literal form triggers (entities / temporal / activity / evidence; topic has no list and leads only when nothing triggers) | **unknown** — `state:2026-08-02-benchmark-validity-record.md` names `"reviewers"`/`"authors"` in this live list among five terms whose presence shows the question file was open when it was written |
| neutral facet floor | `0.2` | `pipelines/artefact_v1_det.py` · `_facet_triggers()` · `0.2` | the weight an untriggered facet carries in the direction vector | **unknown** — same value as artefact_v1's neutral, same absence of record |
| plan neutral vector | `0.2` | `pipelines/artefact_v1_det.py` · `_det_plan()` · `0.2` | the facet vector of the single part when the edges placement is off | **unknown** — same value, same absence of record |
| triggered facet weight | `1.0` | `pipelines/artefact_v1_det.py` · `_facet_triggers()` · `d[facet] = 1.0` | weight a triggered facet, or the topic fallback, carries | **derived** — full weight is the scale's top |
| facet-direction epsilon | `1e-9` | `pipelines/artefact_v1_det.py` · `_facet_shaper()` · `np.maximum(G.sum(axis=1, keepdims=True), 1e-9)` | divide-by-zero guard normalizing the geometry rows, in the support shaper and the router alike | **unknown** — the guard is real and the magnitude is not derived; nothing records why 1e-9 |
| routing disagreement clamp | `[0.0, 1.0]` | `pipelines/artefact_v1_det.py` · `_facet_router()` · `np.clip(…, 0.0, 1.0)` | the ceiling on the facet-disagreement stretch of a tag pair's distance | **unknown** — the clamp never binds: disagreement is bounded by the sum of the question direction's two largest facet weights, at most 0.769231 over the 16 trigger patterns, so the attainable stretch ceiling is 1.7692× and nothing records why the clamp sits at 1.0 |
| `answer_one_question` `k` default | `50` | `pipelines/artefact_v1_det.py` · `answer_one_question()` · `k: int = 50` | retrieval depth | **user-specified** — turns:L217, turns:L394 (as artefact_v1) |

## `pipelines/lucene.py` — sparse baseline

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `K1` | `0.9` | `pipelines/lucene.py` · `K1` | BM25 term-frequency saturation; the `k1` default of `build_sparse_index` | **borrowed** — "Resources for Brewing BEIR" (Kamalloo et al. 2023) reference defaults, cited in the module docstring |
| `B` | `0.4` | `pipelines/lucene.py` · `B` | BM25 length normalization; the `b` default of `build_sparse_index` | **borrowed** — same source |
| BM25 variant | `method="lucene"` | `pipelines/lucene.py` · `build_sparse_index()` · `method="lucene"` | which BM25 formula in the bm25s family | **borrowed** — the Apache Lucene / Elasticsearch / Anserini variant, and bm25s's own default (module docstring) |
| `DEFAULT_TOP_K` | `10` | `pipelines/lucene.py` · `DEFAULT_TOP_K` | k when the caller passes none, in `retrieve_top_k_units` | **unknown** — dead in practice (`run.py` passes `orchestrator.DEFAULT_TOP_K` = 50). The user attacked a 10: "2. 10? fucking why just 10?" (turns:L731) |
| `ARTIFACT_TYPES` | `6 collection names` | `pipelines/lucene.py` · `ARTIFACT_TYPES` | which HERB arrays are flattened and indexed | **derived** — the six artifact arrays; metadata is excluded because no gold citation points at it (module docstring) |
| stemmer | `Stemmer.Stemmer("english")` | `pipelines/lucene.py` · `build_sparse_index()` · `"english"` | Snowball/Porter2 stemming, at index and query time | **borrowed** — bm25s's own analysis chain; the docstring is explicit it approximates rather than reproduces Lucene's `EnglishAnalyzer` |
| stopwords | `"en"` | `pipelines/lucene.py` · `build_sparse_index()` · `stopwords="en"` | bm25s English stopword list, at index and query time | **borrowed** — bm25s default |
| indexed text | `title + "\n" + contents` | `pipelines/lucene.py` · `build_sparse_index()` · `f'{d["title"]}\n{d["contents"]}'` | what BM25 sees per artifact | **borrowed** — "the standard BEIR concatenation" (comment) |

## `pipelines/vector.py` — dense baseline

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `EMBED_MODEL` | `"nvidia/llama-nemotron-embed-1b-v2"` | `pipelines/vector.py` · `EMBED_MODEL` | the one embedder across every arm: this arm's corpus and query sides, the artefact arm's query embeds and its cache key, the graph's semantic layer via `reembed_herb_eval.py`, the tag matrix via `embed_tags.py`, and RAGAS | **user-specified** — "just fucking make a new graph with the nemo embedder instead and delete the old embeddings in it" (turns:L438); "The things that were embedded before should be embedded with nemotron now, that was fucking all you had to do" (turns:L572) |
| `EMBED_BATCH` | `2048` | `pipelines/vector.py` · `EMBED_BATCH` | inputs per NIM `/embeddings` request; the `batch` default of `_embed` and `build_dense_index` | **derived** — NIM's documented per-request input cap; the comment states the token headroom check (~73 tokens/artifact ≈ 150k against a 300k cap) |
| `DEFAULT_TOP_K` | `10` | `pipelines/vector.py` · `DEFAULT_TOP_K` | k when the caller passes none | **unknown** — dead in practice (overridden by `orchestrator.DEFAULT_TOP_K` = 50) |
| `CACHE_DIR` | `output/embed_cache` | `pipelines/vector.py` · `CACHE_DIR` | corpus-matrix cache location, and where the `.cost.json` build record lands | **unknown** — the content addressing names the entries, not the directory; nothing forces this location |
| `QUERY_VECS_PATH` | `data/question_query_vecs.npz` | `pipelines/vector.py` · `QUERY_VECS_PATH` | precomputed question vectors the arm looks up by id | **derived** — the file `embed_questions.py` writes |
| `ARTIFACT_TYPES` | `6 collection names` | `pipelines/vector.py` · `ARTIFACT_TYPES` | which HERB arrays are read and embedded | **derived** — same rationale as lucene (module docstring) |
| `truncate` | `"NONE"` | `pipelines/vector.py` · `_embed_request()` · `"truncate": "NONE"` | over-long input errors instead of being clipped | **derived** — a fail-loud choice, stated in the function docstring |
| non-retryable statuses | `(401, 403, 404)` | `pipelines/vector.py` · `_embed_request()` · `(401, 403, 404)` | which HTTP errors skip the split-and-retry | **derived** — auth / permission / endpoint errors no split can fix |
| cache-key digest length | `[:16]` hex | `pipelines/vector.py` · `_cache_path()` · `h.hexdigest()[:16]` | filename length of the content address | **unknown** — 64 bits of a sha256; nothing records why 16 |
| context-window claim | `8192` tokens | `pipelines/vector.py` · module docstring · `8192-token` | why artifacts embed whole with no chunking | **borrowed** — the nemotron model card's stated context, cited in the docstring |

## `pipelines/hybrid.py` — late-fusion baseline

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `ALPHA` / `HERB_HYBRID_ALPHA` | `0.5` | `pipelines/hybrid.py` · `ALPHA` | fusion weight on the dense arm, and the one entry of this arm's manifest flags | **unknown** — the ends are measured (`v3/output/hybA0_lucene__gold100__20260723T154130Z` at 0.0, `hybA1_vector__…` at 1.0, `hybrid__gold100__20260723T153637Z` at 0.5) but no record selects 0.5; it is the even blend by construction |
| `OVERFETCH` | `4` | `pipelines/hybrid.py` · `OVERFETCH` | each arm's fetch depth as a multiple of k before the fusion | **unknown** — same numeral as `artefact_v1.KNN_OVERFETCH`, no record connecting or deriving either |
| `DEFAULT_TOP_K` | `10` | `pipelines/hybrid.py` · `DEFAULT_TOP_K` | k when the caller passes none | **unknown** — dead in practice |
| `RETRIEVAL_FLAGS` | `1 entry` | `pipelines/hybrid.py` · `RETRIEVAL_FLAGS` | the fusion weight recorded in `run_manifest.json` | **derived** — the arm's one exposed knob |
| alpha range check | `[0.0, 1.0]` | `pipelines/hybrid.py` · module body · `not 0.0 <= ALPHA <= 1.0` | rejects a weight outside the convex range, loud at import | **derived** — the fusion is a convex combination |

## `pipelines/artefact.py` — the v3-native arm entry

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `DEFAULT_TOP_K` | `10` | `pipelines/artefact.py` · `DEFAULT_TOP_K` | k when the caller passes none | **unknown** — this arm appears in 0 of 121 run manifests (`state:2026-08-02-benchmark-validity-record.md`) |
| `PRODUCT_LITERAL_BOOST` | `1.0` | `pipelines/artefact.py` · `PRODUCT_LITERAL_BOOST` | additive lift on every chunk in a named product's file | **unknown** — the comment offers a rationale ("roughly one strong facet-phrase match") with no measurement; `ablate_boost.py` was built to attribute it and its result is recorded nowhere |
| `TODAY` | `"2026-06-28"` | `pipelines/artefact.py` · `TODAY` | reference date relative date phrases resolve against, passed to `interpret` as `current_date` | **unknown** — a frozen build date hard-coded as the run's "today" |
| `_KEY_PATH` | `artefact/keys/Salesforce__HERB.yaml` | `pipelines/artefact.py` · `_KEY_PATH` | the dataset mapping key the index loads under | **derived** — the one key file for this dataset |
| `argsort` tiebreak | `kind="stable"` | `pipelines/artefact.py` · `retrieve_top_k_chunks()` · `kind="stable"` | deterministic order among equal scores | **derived** — determinism |

## `artefact/` — the native rebuild stages

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `CAP_TOKENS` | `3000` | `artefact/chunk.py` · `CAP_TOKENS` | the chunk size cap every kind packs toward; the `cap_tokens` default of `chunk_file` | **unknown** — the best-documented constant in the tree and still underived: recorded as a design decision (`canon:USER_CANON.md`:1431, 06-03/04, `[DOC]` not a user turn) explicitly framed "a calibration seed, not a verdict" with a named §15 sweep that was never run (`canon:OPEN_DECISIONS.md` §14). No turn in the record names 3000 |
| `GAP_FACTOR` | `6` | `artefact/chunk.py` · `GAP_FACTOR` | episode break when a gap exceeds 6× the channel's median positive gap | **unknown** — the comment claims the §15 sweep firms it; that sweep does not exist |
| `PROSE_SEAM` | `\n\s*\n\|(?<=[.!?])\s+` | `artefact/chunk.py` · `PROSE_SEAM` | paragraph-then-sentence split seams for an over-cap prose leaf | **derived** — ordinary prose boundaries |
| token estimator | `len(text) // 4`, floor 1 | `artefact/chunk.py` · `est_tokens()` · `max(1, len(text) // 4)` | the chars-per-token proxy the cap is measured in | **borrowed** — the common ~4-chars-per-token rule of thumb; the comment concedes it is approximate |
| prose split cap | `cap × 4` chars | `artefact/chunk.py` · `_split_leaves()` · `split_prose(text, cap * 4)` | char cap derived from the token cap | **derived** — the inverse of the char/4 proxy |
| episode day boundary | calendar date change | `artefact/chunk.py` · `_segment()` · `stream[i][2].date() != stream[i - 1][2].date()` | the second, unconditional episode break beside the gap rule | **derived** — a day boundary is a conversation boundary (design §9.4) |
| `LONG_TEXT_CHARS` | `200` | `artefact/probe.py` · `LONG_TEXT_CHARS` | median string length at/above which a leaf is prose, deciding one-chunk-per-record vs packing | **unknown** — a dispatch threshold on real data with no measurement behind it |
| `PARSEABLE_SUFFIXES` | `4 suffixes` | `artefact/scan.py` · `PARSEABLE_SUFFIXES` | formats parsed rather than cataloged opaque | **derived** — the formats downstream stages can read |
| `SKIP_DIRS` | `3 names` | `artefact/scan.py` · `SKIP_DIRS` | directories the scanner ignores | **derived** — non-corpus tooling directories |
| hash read block | `1 << 20` (1 MiB) | `artefact/scan.py` · `_hash_file()` · `f.read(1 << 20)` | streaming read size for sha256 | **unknown** — 1 MiB is one conventional streaming block among several and the digest is identical at any of them; nothing records the choice |
| `file_id` length | `sha256[:24]` | `artefact/scan.py` · `scan_file()` · `sha[:24]` | the graph's file identity | **unknown** — 96 bits of the digest; nothing records why 24. Consequence recorded: newline translation on Windows changes the hash, so "re-deriving the corpus invalidates all 5,377 chunk_ids and the tag checkpoint" (`state:2026-08-02-corpus-facts.md`) |
| `TAGGER_MODEL` | `"z-ai/glm-5.1"` | `artefact/tag.py` · `TAGGER_MODEL` | the model that writes the native tag corpus; the `model` default of `tag_chunk` and `smoke` | **unknown** — "Why the built tagger is `z-ai/glm-5.1` when the documented choice was Mistral Large — 06-28 — Undocumented. Three tagger-model decisions, each superseding the last; the final one has no rationale anywhere" (`canon:USER_CANON.md` Part IV.E) |
| `SYSTEM` (tagger) | the contextual-phrase-tag prompt | `artefact/tag.py` · `SYSTEM` | what a tag is, and the standing no-ids/dates/numbers/bare-names rule | **derived** from the user's standing rule that the model emits no numbers; the wording itself is **unknown** |
| tagger `temperature` | `0` | `artefact/tag.py` · `tag_chunk()` · `"temperature": 0` | tagging sampling | **derived** — reproducibility ("one temp-0 call per chunk, instance discarded — reproducible", module docstring) |
| tagger `max_tokens` | `1024` | `artefact/tag.py` · `tag_chunk()` · `"max_tokens": 1024` | budget for one chunk's tag list | **unknown** |
| smoke sample size | `n = 10` | `artefact/tag.py` · `smoke()` · `n: int = 10` | chunks tagged in the tagger smoke | **unknown** |
| projection rate | `40` RPM | `artefact/tag.py` · `smoke()` · `full / 40` | the rate the printed full-run projection assumes | **derived** — NIM's per-account 40/min limit, the same figure `nim.py`'s pacing comment cites |
| `ERROR_LIMIT` | `5` | `artefact/tag.py` · `ERROR_LIMIT` | consecutive bad responses before rotating off a model | **unknown** |
| `DRY_BACKOFF` | `(30, 60, 120, 300, 600)` | `artefact/tag.py` · `DRY_BACKOFF` | escalating cooldown when every model is walled; the last entry repeats | **unknown** — an escalating ladder with no measured basis |
| abort poll slice | `min(5.0, …)` s | `artefact/tag.py` · `tag_corpus()` · `time.sleep(min(5.0, wait - slept))` | how often the cooldown checks for abort | **unknown** — responsiveness is the shape of the rule, not the number; nothing records why 5.0 s |
| chunk ingest batch | `1000` | `artefact/graph_store.py` · `ingest()` · `batch: int = 1000` | chunk rows per UNWIND | **unknown** |
| `DB` | `"herb-v3"` | `artefact/graph_store.py` · `DB` | target database for the native build; the `name` default of `ensure_database`, `ingest` and `build` | **derived** — a distinct name from `herb-eval`, which this build must never touch (module docstring). Never materialized (`state:2026-08-02-corpus-facts.md`) |
| `_SAFE_DB` | `^[A-Za-z][A-Za-z0-9.-]{2,62}$` | `artefact/graph_store.py` · `_SAFE_DB` | database-name validation before string interpolation into `CREATE DATABASE` | **borrowed** — Neo4j's own database-name rules (3–63 chars) |
| `TAG_EMBED_BATCH` | `500` | `artefact/graph_store.py` · `TAG_EMBED_BATCH` | tag rows per UNWIND | **unknown** |
| `CONSTRAINTS` | `4 uniqueness constraints` | `artefact/graph_store.py` · `CONSTRAINTS` | the uniqueness constraints created before ingest: `Source.name`, `File.file_id`, `Chunk.chunk_id`, `Tag.tag_id` | **derived** — one identity per spine node (design §7) |
| `tag_id` form | `"{chunk_id}#{position}"` | `artefact/graph_store.py` · `_tag_rows()` · `f"{cid}#{pos}"` | one Tag node per emission | **derived** from design §7 — and measured a regression: it destroys "the 6,792 shared-phrase tags that are the only `Chunk → Tag ← Chunk` path" (`state:2026-08-02-corpus-facts.md`) |
| NEO4J URI default | `"neo4j://localhost:7687"` | `artefact/graph_store.py` · `driver()` · `"neo4j://localhost:7687"` | Neo4j endpoint for the native build | **borrowed** — the Neo4j Bolt default port |
| NEO4J user default | `"neo4j"` | `artefact/graph_store.py` · `driver()` · `"neo4j"` | Neo4j user for the native build | **borrowed** — the Neo4j install default |
| `INTERPRETER_MODEL` | `"meta/llama-3.3-70b-instruct"` | `artefact/interpreter.py` · `INTERPRETER_MODEL` | the v3-native query interpreter; the `model` default of `interpret` | **unknown** — no record selects it |
| `SYSTEM` (interpreter) | the four-field decomposition prompt | `artefact/interpreter.py` · `SYSTEM` | facet_phrases / literals / date_range / answer_shape, and the MUST-NOT set stated in prose | **derived** from MODEL_CONTRACTS §2 and the user's no-numbers rule; the wording itself is **unknown** |
| facet-phrase count cap | `maxItems: 8`, re-checked as `len(fp) > 8` | `artefact/interpreter.py` · `_SCHEMA` · `"maxItems": 8` | how many cluster centers one prompt may emit; the prompt says "0–8", the schema caps it and `_validate` rejects over it | **unknown** |
| `_KINDS` | `("person", "org", "product")` | `artefact/interpreter.py` · `_KINDS` | the literal kinds `_validate` accepts, matching the schema enum | **derived** — the three entity kinds the pre-pass directories carry |
| `_POLARITIES` | `("wanted", "excluded")` | `artefact/interpreter.py` · `_POLARITIES` | the literal polarities `_validate` accepts | **derived** — boost or no boost; there is no removal (§14.4) |
| `_DATE_RE` | `^\d{4}-\d{2}-\d{2}$` | `artefact/interpreter.py` · `_DATE_RE` | ISO date validation on both `date_range` endpoints | **derived** — the ISO 8601 date form the prompt demands |
| `_MUST_NOT_RE` | id/URL/year/date patterns | `artefact/interpreter.py` · `_MUST_NOT_RE` | the no-numbers contract, enforced by rejection on every facet phrase and literal token | **derived** — the MODEL_CONTRACTS §2 MUST-NOT set, and the user's standing rule that the model emits no numbers |
| interpreter `temperature` | `0` | `artefact/interpreter.py` · `interpret()` · `"temperature": 0` | interpretation sampling | **derived** — reproducibility ("One temp-0 call per prompt, instance discarded — reproducible", module docstring) |
| interpreter `max_tokens` | `1024` | `artefact/interpreter.py` · `interpret()` · `"max_tokens": 1024` | budget for the four-field interpretation JSON | **unknown** |
| smoke stratification | `per_type = 2` | `artefact/interpreter.py` · `_stratified()` · `per_type: int = 2` | questions per HERB type in the interpreter smoke; `smoke`'s `n_per_type` default and the bare-CLI default carry the same 2 | **unknown** |
| hardcoded smoke prompt | a verbatim HERB question about KnowledgeForce | `artefact/interpreter.py` · `__main__` · `"Find the name of company that reported the maximum number of issues that didn't need fixes in KnowledgeForce?"` | the default prompt when the module is run bare with no argument | **unknown**, and flagged: it "proves the prompts beside it were written with the question file open" (`state:2026-08-02-benchmark-validity-record.md`) |
| `_EXCLUDE_RE` | `(apart\s+from\|excluding\|except\|but\s+not\|not)\s*(?:the\s+\|a\s+\|an\s+)?$` | `artefact/prepass.py` · `_EXCLUDE_RE` | which words immediately before a name mark it excluded, anchored at the end of the lookback slice | **derived** — the `$` anchor's binding rule is stated and evidence-based; the keyword list itself is **unknown** |
| `_LOOKBACK` | `40` | `artefact/prepass.py` · `_LOOKBACK` | slice examined before a match | **unknown** — the comment calls it "generous"; the `$` anchor does the real binding |
| `_CORPUS` | `data/corpus/Salesforce__HERB` | `artefact/prepass.py` · `_CORPUS` | the corpus root the three name directories are read from | **derived** — the derived corpus view, oracle stripped |
| `_EMPLOYEE_JSON` | `data/corpus/Salesforce__HERB/metadata/employee.json` | `artefact/prepass.py` · `_EMPLOYEE_JSON` | the person-name directory | **derived** — HERB's own metadata file |
| `_CUSTOMERS_JSON` | `data/corpus/Salesforce__HERB/metadata/customers_data.json` | `artefact/prepass.py` · `_CUSTOMERS_JSON` | the org-name directory | **derived** — HERB's own metadata file |
| `TAGS_NPZ_GLOB` | `output/artefact_index/tags_*.npz` | `artefact/index.py` · `TAGS_NPZ_GLOB` | where the tag matrix is found; the `tags_glob` default of `graph_store.build` | **derived** — the path `embed_tags.py` writes |
| `ORACLE_KEYS` | `("answerable_questions", "unanswerable_questions")` | `artefact/derive_corpus.py` · `ORACLE_KEYS` | the eval oracle stripped from the corpus view | **derived** — the HERB question arrays, 815 + 699 (module docstring) |
| `RAG_UNSAFE_KEYS` | `("team", "customers")` | `artefact/derive_corpus.py` · `RAG_UNSAFE_KEYS` | membership links stripped | **derived** — the dataset card's own RAG Evaluation Note, quoted in the docstring |
| `STRIP_KEYS` | `4 keys` | `artefact/derive_corpus.py` · `STRIP_KEYS` | the `strip_keys` default of `derive_corpus`; a file carrying some but not all of them fails loud | **derived** — the two categories concatenated |
| serialization indent | `2` | `artefact/derive_corpus.py` · `_dump()` · `indent=2` | deterministic re-serialization of stripped files | **unknown** — stable hashes need a fixed indent, not this one; nothing records why 2 |
| prototype fixture file | `data/raw/Salesforce__HERB/products/PitchForce.json` | `artefact/resolver_prototype.py` · `H` | the demo file the resolver prototype resolves against | **unknown** — a demo fixture with no runtime effect; that makes the choice harmless, not derived |
| prototype char span | `[0, 60]` | `artefact/resolver_prototype.py` · `main()` · `["/documents/0/content", 0, 60]` | the demo char-span slice | **unknown** — a demo fixture with no runtime effect; that makes the span harmless, not derived |

## `orchestrator.py` — the run engine and the shared generator

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `DEFAULT_CORPUS` | `data/corpus/Salesforce__HERB` | `orchestrator.py` · `DEFAULT_CORPUS` | the only data a pipeline sees | **derived** — the derived corpus view, oracle stripped |
| `DEFAULT_OUTPUT` | `output` | `orchestrator.py` · `DEFAULT_OUTPUT` | where a run's folder is created | **unknown** — the run engine creates this directory; nothing forces the name |
| `DEFAULT_TOP_K` | `50` | `orchestrator.py` · `DEFAULT_TOP_K` | k for every arm on every run; `run.py`'s `-k` default reads it | **user-specified** — "so, for academic rigor, we have done k=50 now.. should we do more k's ?" (turns:L217); he runs `-k 50` himself (turns:L394, :3719). His later ruling limits how it may be read: "k=50 does not mean the same for all arms, and thats retarded" (turns:L2901) |
| `DEFAULT_WORKERS` | `2` | `orchestrator.py` · `DEFAULT_WORKERS` | questions answered concurrently | **unknown** — `run.py` overrides it to 1 anyway |
| `MAX_CONSECUTIVE_FAILURES` | `10` | `orchestrator.py` · `MAX_CONSECUTIVE_FAILURES` | back-to-back generation failures before the run aborts | **unknown** |
| `GENERATOR_MODEL` | `"qwen/qwen3.5-397b-a17b"` | `orchestrator.py` · `GENERATOR_MODEL` | the one answer-writer injected into every arm, unless `--generator` overrides it | **unknown** — no turn selects it; the user's turns about it are complaints ("why the fuck are we even using qwen anymore, this is so stupid", turns:L1380; "qwen ia NIM is fucking uselessly slow", turns:L1328). Git shows a mistral predecessor with no rationale in either commit |
| `_ANSWER_SCHEMA` | `4 schema keys` | `orchestrator.py` · `_ANSWER_SCHEMA` | the generator's structured output | **derived** — the answer is the only thing the generator owns; every other field is recorded by the harness |
| generator `temperature` | `0` | `orchestrator.py` · `generate()` · `"temperature": 0` | generation sampling | **derived** — determinism for eval reproducibility |
| `enable_thinking` | `False` | `orchestrator.py` · `generate()` · `{"enable_thinking": False}` | non-thinking generation | **derived** — NIM's authoritative switch; keeps guided JSON well-formed (comment) |
| generator `max_tokens` | `8192` | `orchestrator.py` · `generate()` · `"max_tokens": 8192` | answer budget | **unknown** — the comment justifies having *a* budget (NIM's own default truncates) but not this number |
| generator `min_tokens` | `1` | `orchestrator.py` · `generate()` · `"min_tokens": 1` | forces ≥1 generated token | **derived** — the observed Qwen failure of emitting end-of-turn first (comment) |
| generator timeout | `480.0` s | `orchestrator.py` · `generate()` · `timeout=480.0` | per-try wall clock | **unknown** — "the hosted model queues under load" is the stated reason; 480 is not measured anywhere |

## `run.py` — the CLI

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `ARMS` | `6 arm names` | `run.py` · `ARMS` | which `--arm` values are accepted | **derived** — the modules under `pipelines/` |
| `DATA` | `data` | `run.py` · `DATA` | where the fixed id-set files (`gold100.jsonl`, `10smoke.jsonl`) are resolved from | **derived** — a path |
| `OUTPUT` | `output` | `run.py` · `OUTPUT` | where a run folder is created | **unknown** — `run.py` creates this directory; nothing forces the name |
| gold id-set file | `data/gold100.jsonl` | `run.py` · `_fixed_ids_file()` · `"gold100.jsonl"` | the id set `--set gold` runs | **derived** — the named fixed set; not the file `build_question_sets.py` writes (`state:2026-08-02-benchmark-validity-record.md` records 6/100 overlap) |
| 10smoke id-set file | `data/10smoke.jsonl` | `run.py` · `_fixed_ids_file()` · `"10smoke.jsonl"` | the id set `--set 10smoke` runs | **derived** — the named fixed comparison set |
| `-k` default | `orchestrator.DEFAULT_TOP_K` = 50 | `run.py` · `main()` · `default=orchestrator.DEFAULT_TOP_K` | retrieval depth for a run | **user-specified** — turns:L217, turns:L394 |
| `-n` default | `5` | `run.py` · `main()` · `args.n = 5` | dev smoke subset size when `-n` is not given | **unknown** |
| `--workers` default | `1` | `run.py` · `main()` · `args.workers = 1` | parallelism while answering | **derived** — "safest under NIM's rate cap" (help text); 1 is the no-overlap floor |
| rejudge worker auto-size | `len(ids) × len(metrics_to_run())` | `run.py` · `_rejudge()` · `max(1, len(ids) * len(metrics_to_run()))` | cell fan-out for subscription CLI judges | **derived** — every cell at once, because the shared judge pool (`JUDGE_INFLIGHT`) is the real cap |
| wide-parallel judge families | `claude`, `gpt-`, `gemini` | `run.py` · `_wide_parallel_judge()` · `"claude" in model or "gpt-" in model or "gemini" in model` | which judges get the wide fan-out | **derived** — the subscription CLI lanes, which have no NIM queue |
| run-id timestamp format | `%Y%m%dT%H%M%SZ` UTC | `run.py` · `main()` · `"%Y%m%dT%H%M%SZ"` | run folder naming | **derived** — ISO-8601 basic, sortable |
| judge slug pattern | `[^a-z0-9.]+` → `-` | `run.py` · `_slug()` · `r"[^a-z0-9.]+"` | directory-safe `__j-<slug>` names | **derived** — filesystem safety |

## `contract.py`, `progress.py`, `run_lock.py`, `abort.py`, `questions.py`, `prompt_tokens.py`

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `GENERATOR_SYSTEM` | `"Answer the question using only the provided documents. Be concise."` | `contract.py` · `GENERATOR_SYSTEM` | the shared generator's system prompt — identical across arms | **unknown** — the fairness property (one prompt for all arms) is designed; the wording has no record |
| tqdm `ascii` | `True` | `progress.py` · `progress()` · `kwargs.setdefault("ascii", True)` | Windows-safe bar glyphs | **derived** — the target terminal |
| tqdm `dynamic_ncols` | `True` | `progress.py` · `progress()` · `kwargs.setdefault("dynamic_ncols", True)` | bars re-fit when the terminal is resized | **derived** — the target terminal |
| bar `disable` | `not isatty` | `progress.py` · `progress()` · `not getattr(file, "isatty", lambda: False)()` | bars off when output is captured | **derived** — captured logs must not fill with bar frames |
| lock acquire attempts | `2` | `run_lock.py` · `__enter__()` · `for _ in range(2)` | one stale-clear then one attempt | **derived** — exactly one stale-clear then one attempt |
| Win32 access flag | `0x1000` | `run_lock.py` · `_pid_alive()` · `process_query_limited_information = 0x1000` | the `OpenProcess` right the liveness probe asks for | **borrowed** — `PROCESS_QUERY_LIMITED_INFORMATION`, a Win32 API constant |
| Win32 running exit code | `259` | `run_lock.py` · `_pid_alive()` · `still_active = 259` | the `GetExitCodeProcess` value that means the process is alive | **borrowed** — `STILL_ACTIVE`, a Win32 API constant |
| lock file name | `.run.lock` | `run_lock.py` · `__init__()` · `".run.lock"` | the single-writer marker inside a run folder | **unknown** — a dotfile beside the run's outputs states the convention, not the name |
| abort poll interval | `0.1` s | `abort.py` · `watch()` · `time.sleep(0.1)` | keypress polling cadence | **unknown** — responsiveness is the shape of the rule, not the number; nothing records why 0.1 s |
| abort keys | `b"q"`, `b"Q"` | `abort.py` · `watch()` · `(b"q", b"Q")` | which keypress requests the graceful stop | **derived** — the key the harness advertises |
| `QUESTIONS` | `data/questions.jsonl` | `questions.py` · `QUESTIONS` | the question bank | **derived** — the file `build_questions.py` writes |
| `_TOKENIZER_ID` | `"Qwen/Qwen3-8B"` | `prompt_tokens.py` · `_TOKENIZER_ID` | tokenizer for exact generator token counts | **unknown** — the family follows `GENERATOR_MODEL`, the 8B checkpoint does not: nothing records whether its tokenizer is identical to the 397B generator's |

## `nim.py` — transport, pacing, retries

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `BASE_URL` | `"https://integrate.api.nvidia.com/v1"` | `nim.py` · `BASE_URL` | NIM endpoint, for both `post` and `judge_probe.py`'s catalog fetch | **borrowed** — NVIDIA's published endpoint |
| `SECONDS_BETWEEN_CALLS` / `NIM_SECONDS_BETWEEN_CALLS` | `3.0` | `nim.py` · `SECONDS_BETWEEN_CALLS` | per-(key, model) spacing between calls (~20/min) | **unknown**, and the comment beside it describes a different value: "5s is ~12 calls/min, well under NIM's 40/min" |
| pacing floor | `1.5` s | `nim.py` · `SECONDS_BETWEEN_CALLS` · `max(1.5, …)` | hard lower bound on call spacing, whatever the env says | **derived** — NIM's 40/min per-account ceiling is 1.5 s per call; below it NIM 429s (comment) |
| `MAX_TRIES` | `6` | `nim.py` · `MAX_TRIES` | how many times one call may be issued before it raises — six tries, i.e. five retries. It is also the default `max_tries` of the claude lane, and the number the self-check asserts | **unknown** |
| `RETRYABLE_STATUS` | `{408, 429, 500, 502, 503, 504}` | `nim.py` · `RETRYABLE_STATUS` | which HTTP statuses retry; anything else raises at once | **borrowed** — the standard transient-status set |
| `GIVE_UP_AFTER_S` | `300.0` | `nim.py` · `GIVE_UP_AFTER_S` | the call's total wall-clock budget: the loop breaks once elapsed-since-start plus the next delay would reach it, so request time and pacer waits count against it, not the backoff alone. The default `give_up_after_s` of `post`; the judge and embedder both pass their own | **unknown** |
| `MAX_DEGRADED_RETRIES` | `2` | `nim.py` · `MAX_DEGRADED_RETRIES` | retries on NIM's 400 "DEGRADED" blip before it raises as a plain 4xx | **unknown** — the comment gives the shape (a brief blip self-heals, and a sustained outage must not grind because a judge metric fans out per context) but nothing derives the count 2 |
| default request timeout | `120.0` s | `nim.py` · `post()` · `timeout: float = 120.0` | per-try wall clock when the caller passes none | **unknown** |
| exponential backoff | `2 ** attempt` s | `nim.py` · `_delay_after()` · `float(2 ** attempt)` | wait between retries with no `Retry-After`; the same expression covers transport errors in `post` and the claude lane's retry sleep | **borrowed** — standard exponential backoff |
| DEGRADED retry delay | `3.0` s | `nim.py` · `post()` · `delay = 3.0` | wait between DEGRADED retries | **unknown** |
| `_CLAUDE_EXE` fallback | `~/.local/bin/claude.exe` | `nim.py` · `_CLAUDE_EXE` | the Claude CLI when it is not on PATH | **derived** — the install location on this machine (`docs/ENVIRONMENT.md` records that it is not on the agent shell's PATH) |
| claude CLI output format | `--output-format json` | `nim.py` · `_claude_chat()` · `"--output-format", "json"` | the envelope the lane parses `result` and `usage` out of | **derived** — the only machine-readable CLI output |
| `_FENCE` | the JSON code-fence strip pattern | `nim.py` · `_FENCE` | the code fence stripped off a CLI verdict before it is parsed | **derived** — the fence a chat model wraps JSON in |
| round-robin start | `os.getpid()` | `nim.py` · `_next_bind` | which key lane a process claims first | **derived** — a PID offset decorrelates side-by-side processes |

## `eval/ragas.py` and `eval/ragas_catalog.py`

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `JUDGE_MODEL` / `RAGAS_JUDGE_MODEL` | `"claude-haiku-4-5"` | `eval/ragas.py` · `JUDGE_MODEL` | the judge for every scored metric; its slug also picks the backend and the driving profile | **user-specified** — "try haiku first then, and we can do this headless in the same way?" (turns:L1186); "we decided to use haiku for the fucking evals also" (turns:L3820); "using, as the others.. headless claude cli with my subscription" (turns:L3824) |
| `EMBED_MODEL` | `"nvidia/llama-nemotron-embed-1b-v2"` | `eval/ragas.py` · `EMBED_MODEL` | the scoring embedder | **user-specified** — turns:L438, turns:L572 (as `pipelines/vector.py`) |
| `JUDGE_REASONING_EFFORT` / `RAGAS_JUDGE_REASONING_EFFORT` | `"high"` | `eval/ragas.py` · `JUDGE_REASONING_EFFORT` | Codex judge effort, `None` on every other backend; a value outside low/medium/high/xhigh fails loud at import | **unknown** — top of the allowed set, no record of why |
| claude judge profile | `inflight 64, timeout 120.0 s, tries 2` | `eval/ragas.py` · `_judge_profile()` · `{"inflight": 64, "timeout_s": 120.0, "tries": 2}` | how the default judge is driven | **unknown** — the comment's rationale ("no queue to respect … RAM/network are the physical limits") explains running wide, not 64 / 120 / 2 |
| gpt judge profile | `inflight 64, timeout 180.0 s, tries 2` | `eval/ragas.py` · `_judge_profile()` · `{"inflight": 64, "timeout_s": 180.0, "tries": 2}` | Codex judge driving | **unknown** |
| gemini judge profile | `inflight 64, timeout 180.0 s, tries 2` | `eval/ragas.py` · `_judge_profile()` · gemini branch | Gemini judge driving | **unknown** — the numbers are copied deliberately ("Match the other subscription CLI judges", comment) from the claude/gpt rows, which have no origin either |
| giant-NIM profile | `inflight 8, timeout 480.0 s, tries 3` | `eval/ragas.py` · `_judge_profile()` · `{"inflight": 8, "timeout_s": 480.0, "tries": 3}` | hosted-giant judge driving | **unknown** — the queue rationale is stated, the numbers are not derived |
| giant-NIM model match | `397b`, `-675b`, `340b`, `ultra` | `eval/ragas.py` · `_judge_profile()` · `("397b", "-675b", "340b", "ultra")` | which model slugs count as hosted giants | **derived** — the parameter-count slugs of the models that queue |
| small-NIM profile | `inflight 8, timeout 90.0 s, tries 3` | `eval/ragas.py` · `_judge_profile()` · `{"inflight": 8, "timeout_s": 90.0, "tries": 3}` | small NIM judge driving | **unknown** |
| `JUDGE_TIMEOUT_S` / `RAGAS_JUDGE_TIMEOUT_S` | the profile's `timeout_s`, floored at `30.0` s | `eval/ragas.py` · `JUDGE_TIMEOUT_S` | the per-call timeout every judge backend is driven with, and half of the NIM lane's `give_up_after_s` | **unknown** — no record derives the 30 s floor |
| `JUDGE_MAX_TRIES` / `RAGAS_JUDGE_MAX_TRIES` | the profile's `tries`, floored at `1` | `eval/ragas.py` · `JUDGE_MAX_TRIES` | attempts per judge call on the NIM lane, the Gemini CLI retry loop, and the other half of `give_up_after_s` | **derived** — one attempt is the floor below which no call happens |
| `JUDGE_INFLIGHT` / `RAGAS_JUDGE_INFLIGHT` | the profile's `inflight`, floored at `1` | `eval/ragas.py` · `JUDGE_INFLIGHT` | the size of `_CALL_POOL`, the global cap on concurrent judge and embed calls | **derived** — one thread is the floor below which no call happens |
| `EMBED_TIMEOUT_S` / `RAGAS_EMBED_TIMEOUT_S` | `45` | `eval/ragas.py` · `EMBED_TIMEOUT_S` | embedder call timeout, and half its `give_up_after_s` | **unknown** |
| `EMBED_MAX_TRIES` / `RAGAS_EMBED_MAX_TRIES` | `1` | `eval/ragas.py` · `EMBED_MAX_TRIES` | embedder attempts (no retry) | **derived** — `nim.post` owns retry; stacking RAGAS's on top is the failure the `RunConfig` comment describes |
| `MAX_JUDGE_CONTEXT_CHARS` / `RAGAS_MAX_JUDGE_CONTEXT_CHARS` | `60000` | `eval/ragas.py` · `MAX_JUDGE_CONTEXT_CHARS` | the oversized-prompt warning threshold in `_check_judge_context_budget`, which no call site invokes | **unknown** — warning only, no behaviour change, and the warning does not run |
| over-threshold report cut | `[:8]` | `eval/ragas.py` · `_check_judge_context_budget()` · `over[:8]` | worst questions listed in that same unreachable warning | **unknown** — display only, inside a function nothing calls |
| `MAX_CONSECUTIVE_FAILED_QUESTIONS` | `10` | `eval/ragas.py` · `MAX_CONSECUTIVE_FAILED_QUESTIONS` | mostly-errored questions in a row before the eval aborts | **unknown** — the comment states the design intent (high enough that a short outage passes) without a measured outage length |
| question-failed rule | `errored × 2 >= total` cells | `eval/ragas.py` · `_run_pass()` · `cells_errored[qid] * 2 >= cells_total[qid]` | when a question counts as failed for the breaker | **derived** — "most cells errored" expressed exactly |
| `RunConfig(max_retries=1)` | `1` | `eval/ragas.py` · `score_outputs()` · `RunConfig(max_retries=1)` | RAGAS's own retry, capped at one attempt | **derived** — from an observed failure: RAGAS's default 10× nested on top of `nim.post`'s retries "turned one 429 into minutes of dead retries and, under concurrency, starved the shared pacer so parallel ran slower than serial" |
| empty-content retry | `range(3)` | `eval/ragas.py` · `_verdict()` · `for _ in range(3)` | attempts when a NIM judge returns no content | **unknown** — the cause is a real observed failure (the model leaks into thinking mode and emits zero content tokens), the count 3 has no record |
| judge `max_tokens` | `4096` | `eval/ragas.py` · `_post()` · `"max_tokens": 4096` | verdict-JSON budget on the NIM lane | **unknown** |
| judge `min_tokens` | `1` | `eval/ragas.py` · `_post()` · `"min_tokens": 1` | forces ≥1 token | **derived** — same observed empty-verdict failure as the generator |
| judge `enable_thinking` | `False` | `eval/ragas.py` · `_post()` · `{"enable_thinking": False}` | non-thinking verdicts on the NIM lane | **derived** — NIM's authoritative switch; keeps the verdict a direct structured 0/1 (comment) |
| RAGAS temperature default | `1e-8` | `eval/ragas.py` · `generate_text()` · `temperature=1e-8` | near-zero sampling in the two BaseRagasLLM hooks | **borrowed** — RAGAS's own signature default |
| gemini retry sleep | `1.5 × (attempt + 1)` s | `eval/ragas.py` · `_gemini_verdict()` · `time.sleep(1.5 * (attempt + 1))` | Gemini CLI retry spacing | **unknown** |
| gemini terminal-quota markers | `terminalquotaerror`, `daily quota` | `eval/ragas.py` · `_gemini_terminal_quota_error()` · `"terminalquotaerror"`, `"daily quota"` | which Gemini errors are terminal, so the retry loop breaks and the breaker names quota exhaustion | **derived** — the CLI's own error strings |
| tiktoken fallback encoding | `"o200k_base"` | `eval/ragas.py` · `_encoding_for()` · `"o200k_base"` | token estimate when the model is unknown to tiktoken | **borrowed** — the current OpenAI base encoding |
| encoding cache size | `lru_cache(maxsize=16)` | `eval/ragas.py` · `_encoding_for()` · `maxsize=16` | how many tokenizers stay resident | **unknown** — room for more than the judge models in play is the shape of the rule, not the number; nothing records why 16 |
| `_PER_CONTEXT` | `2 metric names` | `eval/ragas.py` · `_PER_CONTEXT` | which metrics fan out ~1 call per context: they get their own last pass and that pass's bar is driven by NIM calls instead of cells | **derived** — a property of those RAGAS metrics |
| `_CONTEXT_HEAVY_LLM` | `6 metric names` | `eval/ragas.py` · `_CONTEXT_HEAVY_LLM` | which metrics concatenate all contexts into one prompt. Its one read site is `_check_judge_context_budget`, which no call site invokes | **derived** — a property of those RAGAS metrics |
| `_REGISTRY` | `23 metric builders` | `eval/ragas.py` · `_REGISTRY` | which RAGAS class each catalog name instantiates and whether it takes the judge, the embedder, both or neither; the empty-needs rows are also what defines the free first pass | **derived** — the RAGAS classes for the feedable metrics; a `SELECTED` name absent here fails loud |
| `_ARTIFACT_TYPES` | `6 collection names` | `eval/ragas.py` · `_ARTIFACT_TYPES` | which HERB arrays gold citations are dereferenced from for the text-based metrics | **derived** — the same six arrays the baseline arms index |
| `CATALOG` | `37 metrics` | `eval/ragas_catalog.py` · `CATALOG` | the whole RAGAS menu, 28 of them feedable by HERB (`applies=True`) and 9 kept visible but unselectable | **derived** — the library's metric list, each row's `judge`/`embed`/`needs` read off the RAGAS docs |
| `SELECTED` | `14 metrics` | `eval/ragas_catalog.py` · `SELECTED` | exactly what a run scores: 4 free retrieval, 7 free answer-vs-gold, 3 judged | **unknown** — the free/judged split follows each metric's own cost and `context_precision_llm_ref` is commented out as the slow per-context pass, but nothing records why these 14 of the 28 feedable catalog metrics. `state:2026-08-02-benchmark-validity-record.md` records the consequence: "No rank-aware metric is in `eval/ragas_catalog.py`. Ordering changes are invisible" |
| `ragas` pin | `0.4.3` | `requirements.txt` · `ragas==0.4.3` | the frozen metric implementation | **derived** — the legacy `ragas.metrics` classes carry the id-based and non-LLM context metrics the newer collections API drops; judged scores are not comparable across ragas versions |

## Top-level scripts

| constant | value | where | what it controls | provenance |
|---|---|---|---|---|
| `GOLD_N` | `100` | `build_question_sets.py` · `GOLD_N` | size of the gold set this script draws; the `n` default of `stratified_gold` | **unknown** — the shipped `data/gold100.jsonl` is not reproducible from this script (6/100 overlap; `state:2026-08-02-benchmark-validity-record.md`), so this constant does not describe the set in use |
| `GOLD_SEED` | `0` | `build_question_sets.py` · `GOLD_SEED` | shuffle seed for the stratified draw; the `seed` default of `stratified_gold` | **unknown** — reproducibility forces a fixed seed, not this one; 0 is arbitrary |
| equal-allocation draw | round-robin over the 5 types | `build_question_sets.py` · `stratified_gold()` · `types[i % len(types)]` | the balanced answerable subset | **derived** — the docstring gives the reason (the natural mix is lopsided, person 260 … url 20) and states the cost (the subset no longer matches HERB's distribution) |
| `--ks` default | `5,10,15,20,30,40,50` | `truncate_k.py` · `main()` · `default="5,10,15,20,30,40,50"` | the depth ladder a run is re-emitted at | **user-specified** — "so not 5,10,15,20,30,40 ?" (turns:L221), immediately after accepting k=50 (turns:L217) |
| `BACKUP_DATABASE` / `HERB_BACKUP_DATABASE` | `"herb-eval-backup"` | `reembed_herb_eval.py` · `BACKUP_DATABASE` | read-only source of chunk-description text | **derived** — the pre-cleanup sibling DB; description text is embedding input only and never enters the live graph |
| `WRITE_BATCH` | `500` | `reembed_herb_eval.py` · `WRITE_BATCH` | vectors per write transaction, for tags and chunk descriptions alike | **unknown** |
| `LEGACY_FACET_INDEXES` | `6 index names` | `reembed_herb_eval.py` · `LEGACY_FACET_INDEXES` | the per-facet e5-era indexes dropped | **derived** — the names the superseded build wrote |
| `LEGACY_FACET_PROPS` | `7 property names` | `reembed_herb_eval.py` · `LEGACY_FACET_PROPS` | the per-facet e5-era properties removed from every Tag | **derived** — the names the superseded build wrote |
| vector index similarity | `'cosine'` | `reembed_herb_eval.py` · `_vector_index()` · `vector.similarity_function: 'cosine'` | the metric both `tag_emb` and `chunk_desc_emb` are created with, and therefore the metric every kNN in the arm scores under | **derived** — the embedder's own metric; vectors are unit-normalised |
| `TAGS_PATH` | `output/tags/Salesforce__HERB.jsonl` | `embed_tags.py` · `TAGS_PATH` | tag corpus in | **derived** — the path `artefact/tag.py` writes |
| `INDEX_DIR` | `output/artefact_index` | `embed_tags.py` · `INDEX_DIR` | tag matrix out | **derived** — the path `artefact/index.py` reads |
| tag cache-key digest length | `[:16]` hex | `embed_tags.py` · `_cache_path()` · `h.hexdigest()[:16]` | filename length of the tag matrix's content address | **unknown** — 64 bits of a sha256; nothing records why 16 |
| `MAX_ITER` | `60` | `build_tag_clusters.py` · `MAX_ITER` | Lloyd iteration cap per facet fit; the `max_iter` default of `weighted_spherical_kmeans` and the size of its progress bar | **unknown** |
| `TOL` | `1e-7` | `build_tag_clusters.py` · `TOL` | objective-movement convergence tolerance; the `tol` default of `weighted_spherical_kmeans` | **unknown** |
| membership distance floor | `1e-6` | `build_tag_clusters.py` · `memberships()` · `np.maximum(1.0 - X @ V.T, 1e-6)` | divide-by-zero guard in `d^(-2/(m-1))` | **unknown** — the guard is real and the magnitude is not derived; nothing records why 1e-6 |
| k-means++ distance floor | `0.0` | `build_tag_clusters.py` · `kmeanspp_init()` · `np.maximum(1.0 - X @ V[0], 0.0)` | keeps a floating-point negative cosine distance out of the D² draw | **derived** — a distance cannot be negative |
| `_FACET_COL` | `5 facet columns` | `build_tag_clusters.py` · `_FACET_COL` | the facet → column index map the participation matrix is filled through | **derived** — `ALL_FACETS`'s order, enumerated |
| `K` | `10` | `ablate_boost.py` · `K` | depth of the boost-vs-facets ablation | **unknown** — a one-off experiment constant; the ablation's result is recorded nowhere |
| `GOLD` | `data/gold100.jsonl` | `ablate_boost.py` · `GOLD` | the id set the ablation runs over | **derived** — the same fixed gold set `run.py --set gold` uses |
| `OUT` | `output/ablation_boost_vs_facets` | `ablate_boost.py` · `OUT` | where the ablation writes | **unknown** — the script creates this directory; nothing forces the name |
| `CONFIGS` | `("facets", "boost", "both")` | `ablate_boost.py` · `CONFIGS` | the three legs compared | **derived** — the two channels and their combination |
| `ID_METRICS` | `["context_recall_id", "context_precision_id"]` | `ablate_boost.py` · `ID_METRICS` | metrics the ablation scores | **derived** — the free, judge-free retrieval metrics |
| `DEFAULT_CORPUS` | `data/corpus/Salesforce__HERB` | `offline_eval.py` · `DEFAULT_CORPUS` | corpus root for gold text | **derived** — same as the orchestrator's |
| `OFFLINE` / `BATCHED_EMBED` | catalog-derived lists | `offline_eval.py` · `OFFLINE` | which metrics run without a judge, split by whether they need the embedder | **derived** — read straight off `CATALOG` flags |
| `TARGET_METRICS` | `("faithfulness", "answer_correctness", "context_recall_llm")` | `compare_arms.py` · `TARGET_METRICS` | metrics printed first | **unknown** — display order only |
| `DIR_RE` | `^(?P<arm>[a-z]+)__gold100__(?P<ts>\d{8}T\d{6}Z)(?:__k(?P<k>\d+))?$` | `compare_arms.py` · `DIR_RE` | which run folders the comparison tool sees; `export_raw.py` carries the identical pattern | **unknown** — it does not match the run-folder naming scheme it exists to read: "`[a-z]+` matches neither `artefact_v1` nor `artefact_v1_det`. The cross-arm table printer has never displayed the artefact" (`state:2026-08-02-corpus-facts.md`) |
| `MANIFEST` | `run_manifest.json` | `export_raw.py` · `MANIFEST` | the per-run file the exporter reads k from | **derived** — the name the runner writes |
| `FIELDS` | `6 CSV columns` | `export_raw.py` · `FIELDS` | the long-format export schema | **derived** — the tidy-long shape of `EvalResult` |
| `MODELS` | `2 generator legs` | `model_test.py` · `MODELS` | the two legs of the 3-question head-to-head | **user-specified** — "how good is glm 5.2 compared to qwen? perhaps do a test between 3 questions? do full question-answer-eval on the same 3 questions with full glm vs full qwen" (turns:L929) |
| `-k` default | `50` | `model_test.py` · `main()` · `default=50` | retrieval depth for the head-to-head | **user-specified** — turns:L217, turns:L394 |
| `_EXCLUDE` | `15 substrings` | `judge_probe.py` · `_EXCLUDE` | which catalog models are not judge candidates | **derived** — model families that cannot emit a chat verdict |
| `_CONTEXT` | one two-name sentence about a quarterly report | `judge_probe.py` · `_CONTEXT` | the context both probe verdicts are judged against | **unknown** — agent-written prose; carrying no corpus content is a property of the wording, not a derivation of it |
| `_PROBES` | `2 statements` | `judge_probe.py` · `_PROBES` | the known-truth faithfulness probe | **derived** — a minimal true/false pair |
| `_PROMPT` | the one-line faithfulness question | `judge_probe.py` · `_PROMPT` | what each candidate model is asked, and the `{"verdict": 1 or 0}` shape parsed back | **unknown** — agent-written prose; nothing measures it against a smaller prompt |
| probe `max_tokens` | `300` | `judge_probe.py` · `_probe_model()` · `"max_tokens": 300` | one probe verdict's output budget | **unknown** |
| probe timeout / tries | `90` s / `1` | `judge_probe.py` · `_probe_model()` · `timeout=90, max_tries=1` | how one probe call is driven | **unknown** |
| probe `--workers` default | `3` | `judge_probe.py` · `main()` · `default=3` | models probed in parallel | **derived** — "one key lane each" (help text), i.e. the size of the key pool |
| catalog listing timeout | `30` s | `judge_probe.py` · `main()` · `timeout=30` | the `/models` fetch | **unknown** |

---

## Unenforced invariants

Not constants — relationships between constants that the code depends on and nothing checks.

- **`_ANCHOR_TEXTS`'s keys must be `ALL_FACETS`, in the same order.**
  `pipelines/artefact_v1_det.py` · `_ANCHOR_TEXTS` against `pipelines/artefact_v1.py` · `ALL_FACETS`.
  `_anchors()` embeds `_ANCHOR_TEXTS.values()` as the rows of the anchor matrix; `_facet_direction()`
  builds the question's trigger vector by iterating `_ANCHOR_TEXTS`'s keys and looking each name up in
  a dict `_facet_triggers()` built from `ALL_FACETS`. So the support shaper's `G @ qdir` and the
  router's `(gap * qdir)` pair anchor row *i* with trigger weight *i* only while the two sequences
  agree. A facet in `ALL_FACETS` and absent from `_ANCHOR_TEXTS` drops silently out of every
  direction vector while `_FACET_WORDS` can still fire its trigger; a key in `_ANCHOR_TEXTS` and
  absent from `ALL_FACETS` raises `KeyError` at the first det question. Nothing asserts the equality,
  no test covers it, and no comment mentions it.

## Counts

Recounted from the table above by `python check_constants.py --counts`, which reads the rows back
and tallies them; the classes sum to the total.

- **Total rows: 305**

| provenance | rows |
|---|---|
| unknown | 148 |
| derived | 119 |
| borrowed | 21 |
| user-specified | 11 |
| swept | 6 |

`python check_constants.py` re-reads 171 of those rows against the source — 152 with a value the
parser can compare on both sides, 19 where the symbol is verified but the value is prose or an
expression it will not evaluate. The remaining 134 name no module-level symbol and are reported
UNCHECKED.

Two rows carry a disagreement between sources and say so in place: `NIM_SECONDS_BETWEEN_CALLS`
(the 3.0 s default and the comment beside it describe different rates) and `HERB_NORM_SCOPE` (the
sweep measures a different winner than the value that ships). Three rows describe
`_check_judge_context_budget`, a function no call site invokes: `MAX_JUDGE_CONTEXT_CHARS`,
`_CONTEXT_HEAVY_LLM` and the `[:8]` report cut.

`derived` is the strict class: the value is forced by something outside the choice — a name the code
or the dataset already carries, a schema or a library's requirement, an arithmetic identity, or a
decision with a citation. Everything short of that is `unknown`. Where a rule's *shape* follows from
something real but its *number* does not — a numerical guard's magnitude, a rounding precision, a
budget sized with headroom, `MAX_DEGRADED_RETRIES`, the empty-content retry, the routing clamp's 2×
ceiling — the row is classed `unknown` and states both halves, because the number is the thing being
asked about. A reason that restates the value's effect ("a missing weight contributes nothing") is
`unknown`, as is a name the code invents for its own artefact: a cache directory, a lock file, a
manifest label. A path that points at content another stage writes stays `derived` — the two must
agree.
