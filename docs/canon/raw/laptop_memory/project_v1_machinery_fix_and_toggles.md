---
name: v1-machinery-fix-and-toggles
description: "2026-07-23: blind-control panel validated the seeded diagnosis (4 sterile scouts re-derived dead widening, scale incommensurability, degenerate stop rule, half-scale cosine); 24 defects fixed + 3 experiment flags (HERB_SCOPE_REACH, HERB_TAG_PURE, HERB_WALK_GATE) built and review-converged; 8-run det grid queued, detBASE = new post-fix baseline"
metadata: 
  node_type: memory
  type: project
  originSessionId: 42699b8f-4ff0-43ba-80ed-d017967a8cab
---

Blind-control protocol (user's design): re-run adversarial scouts with sterile
prompts — code files only, no state docs/memory/candidate issues. Overlap with the
seeded wave = real; blind-only = seeded blind spots; seeded-only = suspect. Result:
the seeded diagnosis core replicated (all four scouts found the dead flat-mode
widening, cross-path value-scale incommensurability, the gap-break degeneracy, the
(1+cos)/2 half-scale). Seeded-only content was mostly live measurements the control
could not reach; nothing looked fabricated. Blind-only bucket became the fix list.

Fixed 2026-07-23 (branch re-V1-k50, uncommitted; suites 69+36 green; all
review-converged with live Neo4j EXPLAIN/probes): pass-2 schema validation +
cleaned-tag echo matching + unscored-tags meta, zero-norm guards, tag-pool
ORDER BY + run_id scoping + 4x over-fetch/trim (desc kNN too), anchor-by-index,
curve-walk semantic-empty raises, plan not popped/aliased, retrieved-vs-returned
meta, InterpreterError carries usage, driver close on failed prepare, path-traversal
guard, det multi-word section phrases + whole-word earliest-mention product gating +
plural facet triggers, det anchor-embed counted + warmed pre-window, facet-trigger
dedup, truncate_k fails loud on non-1:1 records without meta.chunk_ids, Aborted
re-raised in _sufficient_cut, deterministic ORDER BY tiebreakers, test-suite state
hygiene.

Three experiment flags (all off = byte-identical, proven bitwise/byte-level;
recorded in RETRIEVAL_FLAGS/run manifests; user's toggleable-variants design):
- HERB_SCOPE_REACH=1 — scope keeps full membership (no horizon) but support
  multiplicity capped at len(K_LEVELS): same staircase as tag/desc paths.
- HERB_TAG_PURE=1 — tag chunk value = bare support (facetTerm/w_chunk/relevance
  dropped); det support shaping still flows through qt.weight. Note:
  HERB_DET_FACETS=edges|all + pure no-ops the edges placement by contract.
- HERB_WALK_GATE=1 — flat widening gate counts only tag-area-reached chunks, so
  desc/scope can no longer stop the walk; inert under HERB_CURVE_WALK.

**Why:** the old baselines (flat 0.6972, detW2 0.7005) measured a build with these
defects in; every toggle-grid comparison must run against a fresh post-fix detBASE,
not the old numbers.

**Toggle results (gold-100, det, k=50, retrieval-only, 2026-07-23):** detBASE
0.7039/0.0528 (post-fix baseline; broken-build flat was 0.6972/0.0518 — defect
fixes alone +0.007); detS 0.7045, detP 0.7040 (both ~inert alone: tag path
contributes ~1 chunk in flat mode, so re-scaling scope or tag values barely moves
the cut); detG 0.6868 (9 up / 18 down); detSPG 0.6616 (19 up / 31 down, worse
than G alone — negative interaction). Verdict: letting the walk actually run
HURTS — the widened tag areas' chunks are worse than the desc/scope chunks they
displace at the cut. The walk is no longer dead by bug; it loses on tag-layer
evidence quality (consistent with 12.6% URL-junk tags). The weights were not the
problem; build-side tag/description signal is the next real lever. Best current
config: all switches off. Parked, undecided:
door/surface vocabulary rename (user's word needed; in meta keys + HERB_DOOR_TRACE),
det part text through _readable (eid mangling — embedding probe first), stale
output/artefact_v1__*__k* folders carry canon-invalid flat-sliced ids (guard now
prevents new ones; deleting old ones is the user's call).
Related: [[v1-ordering-diagnosis]], [[v1-adversarial-panel-verdicts]],
[[v1-curve-cut-experiment]], [[trust-revoked-explicit-instruction-only]].
