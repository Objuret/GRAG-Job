---
name: audit-panel-2026-07-28
description: "Five-agent serious audit of artefact logic+methodology ran 2026-07-28 — verdicts per shipping claim, the uncommitted-rewrite regression, and the landmine list"
metadata: 
  node_type: memory
  type: project
  originSessionId: 579f6380-b677-4892-9088-30ad076873ab
  modified: 2026-07-28T11:12:59.058Z
---

2026-07-28: the serious logic+methodology audit ran as five parallel read-only reviewers (logic, maths, order-of-operations, overfitting/leakage, statistics), covering the three lenses [[final-audit-panel]] required (academic rigor, senior-eng, overfitting/leakage). Nothing was launched or edited; all numbers recomputed from disk.

**Biggest finding — the working tree is not the measured code.** `v3/pipelines/artefact_v1.py` carries an uncommitted ~1000-line rewrite, newer than the newest state doc, covered by no state doc: only the description path admits chunks into the kept set (tags/stated-scope corroborate value only), normalization is hard-coded to the sweep-measured losing mode (absolute), and all HERB_* combine/walk flags are deleted — clusterKglob 0.7492 (best measured config) is unimplementable in it. Its one measured run is detDESCFIRST gold-100 **0.6251 vs the committed baseline 0.7339** (a −0.109 regression). New arithmetic bug in it: tag/desc pools extend to 256 rows (6 levels) but normalize against a fixed 4-level reference, so equal-distance scores drift 0.50→0.60→0.69 with pool width while stated-scope stays 0.50; the in-code comments claiming no drift are false and the test pinning the invariant is vacuous. The desc admission cut lands on K_LEVELS seams (keep=65 at the 64 boundary on structureless pools) — the same seam-artifact class the value knee was condemned for. All measured results live at HEAD commit 5006fed.

**Statistical verdicts per shipping claim (n=100 paired, sign-flip permutation + BCa CI + Holm):**
- Headline "0.64 vs 0.09/0.11": ~85% unit artifact — crediting one id per kept chunk drops artefact to 0.0904 ≈ lucene. Ships only as matched-id-budget: 0.73–0.75 vs 0.41/0.39/0.27 (~1.8×, all Holm p≈3e-4, rank-biserial 0.85–1.0). Missing control: granularity-matched baseline (packed multi-record chunks + bundle credit).
- "Leads all valid metrics" is false as worded: answer_correctness vs vector n.s. (p=0.096) and generator-confounded (sonnet vs qwen).
- +0.030 combine rebuild: REAL (p=0.0005, CI +0.014..+0.054) — defect fix, not a swept knob.
- "clusterKglob best config": NOT supported — +0.0154 over detCUR, p=0.36, smaller than best-of-36 selection noise; its ordering (nDCG) is *worse* than detCUR. What holds: it beats its own leg's flat-global (+0.068, p=4e-4).
- Cluster-K K-decision structurally inert at k=50: stops fired 100/100 yet semantic ≥122 everywhere → kept=50 always; area-granularity coarser than chunk target.
- Curve-walk 0.51 vs constant-cut 0.65: n.s. at n=10 (exact p=0.203, driven by two CoachForce K=5 zeros); vs flat@50 supported. Also mathematically expected: the stop reads area tightness, measured ⊥ gold depth.
- Facets "null": ship as bounded failure-to-detect (±0.035), tendency weakly positive — not a point null.
- ~0.80 wall: tried-set enumeration on n=10, optimistically biased; gold-100 max over everything tried is 0.7492.
- Scope-dominance: haiku leg only (+0.077 global, p=6e-4); det leg insensitive after Holm. Must ship as benchmark-structure alignment (HERB questions name their product = gold's partition key), not a retrieval law.
- haiku < det: supported on gold-100 (−0.130, p=5e-5). Pool-ceiling-1.0: unverifiable from disk (traces carry locators, not ids) — cite as n=10 diagnostic only.
- "All loss is ordering" false of the rewrite: 18/100 questions kept their whole semantic set and still recall<1 — pure membership loss.

**Leakage:** no direct answer-text leakage in any of 129 run dirs. But the arm resolves chunk text from full raw HERB (oracle in-file) at answer time — quarantine rests on herb-eval locator discipline, not v3 code. Soft vectors unverified: tag vocabulary partly minted by an oracle-reading tagger; relevance_to_file preserved from the contaminated build.

**Landmines:** two different "gold-100" sets exist — runs use data/gold100.jsonl (55 content/22 person/17 pr/5 company/1 url), NOT the balanced set README describes. Invalid flat-slice `__k` dirs (e.g. artefact 0718 __k25) sit next to shipment data. Partial 2026-07-23 JUDGE_* dirs are unusable (arm-correlated missingness: artefact answer_correctness 0/100 completions). Manifests carry no git sha — provenance is flags+timestamp only. Hybrid rankings are k-dependent (min-max over 4k window before cut; k=50 not a prefix of k=500, 100/100 diverge). Vector query-embed cache keyed by question id only — silent staleness on embedder change. Haiku judge never validated on artefact-style contexts. [[machinery-fix-and-toggles]] is stale: HERB_SCOPE_REACH/TAG_PURE exist in no source era, only in five 2026-07-23 manifests.

Cheap settling runs identified (not launched): det-leg gold-100 on the rewrite (membership-loss split via door trace), curve-walk on gold-100, the 715 held-out answerable questions on det (all local/model-free with warm caches).
