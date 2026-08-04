# REVIEW_REGISTER — the pile, one row per agent-written artifact

> **Interpretation, produced 2026-08-03, unreviewed by the user.** This register is itself one
> more agent artifact. It appears in its own table and holds the same status as everything
> listed in it.

This is the worklist for going through the agent-written material in this project. Every row
starts at `unreviewed`, including the four `docs/canon/` documents — an agent produced those on
2026-08-03 in a few hours, and they carry no more standing than a memory file or a state doc.
Nothing here outranks anything else here by age, by title, or by being cited elsewhere.

**Three kinds of thing, repo-wide.** *Intent* — what was supposed to be built — exists only in
the user's own typed turns (`docs/canon/raw/user_turns*`), with the honest caveat that a machine
filter decided what counted as a human turn. *State* — what exists — is the git history itself:
commits, diffs, and the actual file contents at each commit, plus the code, the graph and the
run outputs; re-derivable, checkable, nobody's opinion. *Interpretation* — every document listed
below — is a claim about intent or state, agent-written and unreviewed, checked against both
before it is acted on. State is evidence of drift from intent, never justification for it: "it
is in the code" and "the commit says so" are not arguments, they are the thing being
questioned.

**How to read the columns.**

- **What it claims to be** — the file's own first heading, copied mechanically. A
  self-description, not a verdict.
- **Last written** — filesystem last-modified date, not authorship date. A file touched today may
  have been written in May; for committed files `git log --follow` is the better answer.
- **Status** — `unreviewed` everywhere. Nothing in this project has been reviewed by the user.
- **Evidence pointers found** — a mechanical scan for citation markers (`[CHAT]`/`[DOC]` quote
  tags, git refs, `v3/output/` run dirs, corpus references, `docs/canon/` references). It reports
  that pointers exist, **not** that they support the claims. `none found` means the file asserts
  without pointing anywhere.

## 1. docs/canon — the four documents and this register

Agent-written 2026-08-03. `CANON_AUDIT.md` adjudicates other files; that does not exempt it from
the pile.

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `docs/canon/CANON_AUDIT.md` | Canon audit — what the repo tells agents vs. what the user actually said | 2026-08-03 | unreviewed | git refs, run dirs, corpus, canon docs |
| `docs/canon/DESIGN_HISTORY.md` | DESIGN_HISTORY — how this system was actually designed and built | 2026-08-03 | unreviewed | quote tags, git refs, corpus, canon docs |
| `docs/canon/OPEN_DECISIONS.md` | OPEN_DECISIONS — everything genuinely unresolved | 2026-08-03 | unreviewed | quote tags, git refs, run dirs, corpus, canon docs |
| `docs/canon/README.md` | docs/canon — the record, and how far each part of it can be trusted | 2026-08-03 | unreviewed | quote tags, git refs, corpus, canon docs |
| `docs/canon/USER_CANON.md` | USER_CANON — what the user actually said | 2026-08-03 | unreviewed | quote tags, git refs, corpus, canon docs |
| `docs/canon/REVIEW_REGISTER.md` | REVIEW_REGISTER — the pile, one row per agent-written artifact | 2026-08-03 | unreviewed | canon docs, corpus |

## 2. docs/canon/raw — records and corpus

`user_turns*.jsonl` / `.md` are **intent**: verbatim user turns, tool-extracted, spot-checked
byte-identical against the source transcripts. Their caveat is the machine filter — 10,313
user-role turns seen, 9,547 rejected by rule. The `EXTRACT_REPORT*` and `rejected_sample*` files
are that tool's own accounting of the filter. `git_record.md` and `desktop_docs_record.md` are
**interpretation** — agent-written reconstructions — and belong in the review pile.

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `docs/canon/raw/EXTRACT_REPORT.md` | Canon extraction report | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/EXTRACT_REPORT_desktop.md` | Canon extraction report | 2026-08-03 | unreviewed | corpus |
| `docs/canon/raw/desktop_docs_record.md` | Desktop docs record — the handoff/state corpus, 2026-05-25 → 07-12 | 2026-08-03 | unreviewed | git refs |
| `docs/canon/raw/git_record.md` | Git record — forensic reconstruction from git alone | 2026-08-03 | unreviewed | git refs, run dirs |
| `docs/canon/raw/rejected_sample.md` | Rejected turns - audit sample | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/rejected_sample_desktop.md` | Rejected turns - audit sample | 2026-08-03 | unreviewed | git refs |

Corpus files — intent, machine-filtered; what needs reviewing here is the filter that produced
them, not the prose inside them:

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `docs/canon/raw/user_turns.md` | Laptop half of the corpus — 676 verbatim human turns, from 2026-07-06 (md) | 2026-08-03 | unreviewed | n/a — this file is the evidence |
| `docs/canon/raw/user_turns_all.md` | The merged corpus — 803 verbatim human turns, 2026-05-14 to 2026-08-03 (md) | 2026-08-03 | unreviewed | n/a — this file is the evidence |
| `docs/canon/raw/user_turns_desktop.md` | Desktop half of the corpus — 127 verbatim human turns, from 2026-05-14 (md) | 2026-08-03 | unreviewed | n/a — this file is the evidence |
| `docs/canon/raw/user_turns.jsonl` | Laptop half of the corpus — 676 verbatim human turns, from 2026-07-06 (jsonl) | 2026-08-03 | unreviewed | n/a — this file is the evidence |
| `docs/canon/raw/user_turns_all.jsonl` | The merged corpus — 803 verbatim human turns, 2026-05-14 to 2026-08-03 (jsonl) | 2026-08-03 | unreviewed | n/a — this file is the evidence |
| `docs/canon/raw/user_turns_desktop.jsonl` | Desktop half of the corpus — 127 verbatim human turns, from 2026-05-14 (jsonl) | 2026-08-03 | unreviewed | n/a — this file is the evidence |

## 3. Root and v3 documents

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `CLAUDE.md` | CLAUDE.md | 2026-08-03 | unreviewed | git refs, run dirs, canon docs |
| `README.md` | exjobbet — HERB evaluation harness | 2026-06-28 | unreviewed | none found |
| `v3/README.md` | v3 — HERB evaluation | 2026-08-03 | unreviewed | canon docs |
| `v3/artefact/DESIGN.md` | v2 Artefact Rebuild — Design | 2026-06-28 | unreviewed | git refs |
| `v3/artefact/MODEL_CONTRACTS.md` | v2 model contracts — structured I/O at every model touchpoint | 2026-06-28 | unreviewed | none found |
| `v3/artefact/data/README.md` | herb-eval.dump | 2026-07-16 | unreviewed | none found |
| `v3/output/DATA_README.md` | HERB three-arm evaluation — data shipment notes | 2026-07-30 | unreviewed | run dirs |

## 4. State docs

In-repo (gitignored, present in the working tree):

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `docs/state/2026-07-20-v1-query-relative-areas.md` | 1. Purpose of this state document | 2026-07-20 | unreviewed | git refs, run dirs |
| `docs/state/2026-07-22-retrieval-literature-sweep.md` | Retrieval literature sweep — query-relative areas, facets, fusion, budgeted walks | 2026-07-22 | unreviewed | none found |
| `docs/state/2026-07-22-v1-curve-walk-facets-and-cluster-k.md` | 1. Purpose of this state document | 2026-07-22 | unreviewed | run dirs |
| `docs/state/2026-07-25-combine-clusterk-hybrid-and-judged-eval-usage-burn.md` | 1. Purpose of this state document | 2026-07-29 | unreviewed | git refs, run dirs |
| `docs/state/2026-07-28-audit-absorption-full-revert-corroboration-probe.md` | 2026-07-28 — Audit verdicts, rewrite-thread absorption, full revert, corroboration probe | 2026-07-29 | unreviewed | git refs, run dirs |

On the OneDrive state-transfer folder — the flat set; several are not mirrored into
`docs/state/`:

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-06-20-v3-contract-vector-arm.md` | State Transfer: v3 eval harness — contract done, vector arm next | 2026-06-21 | unreviewed | none found |
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-07-17-judge-shootout-rebuilt-artefact-v1-laptop.md` | State transfer — judge shoot-out, rebuilt artefact_v1, laptop environment (2026-07-17) | 2026-07-17 | unreviewed | git refs, run dirs |
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-07-20-gold100-shipment-claude-lane.md` | State transfer — gold-100 shipment shipped, claude CLI lane built (2026-07-20) | 2026-07-20 | unreviewed | git refs, run dirs |
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-07-20-v1-query-relative-areas.md` | 1. Purpose of this state document | 2026-07-20 | unreviewed | git refs, run dirs |
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-07-22-retrieval-literature-sweep.md` | Retrieval literature sweep — query-relative areas, facets, fusion, budgeted walks | 2026-07-22 | unreviewed | none found |
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-07-22-v1-curve-walk-facets-and-cluster-k.md` | 1. Purpose of this state document | 2026-07-22 | unreviewed | run dirs |
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-07-25-combine-clusterk-hybrid-and-judged-eval-usage-burn.md` | 1. Purpose of this state document | 2026-07-25 | unreviewed | git refs, run dirs |
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-07-28-audit-absorption-full-revert-corroboration-probe.md` | 2026-07-28 — Audit verdicts, rewrite-thread absorption, full revert, corroboration probe | 2026-07-28 | unreviewed | git refs, run dirs |
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-08-02-benchmark-validity-record.md` | Benchmark validity record — measurement only | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-08-02-corpus-facts.md` | Corpus facts — artefact design entry point | 2026-08-03 | unreviewed | run dirs |
| `C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/USER_CANON.md` | What the user actually said — verbatim | 2026-08-03 | unreviewed | git refs |

## 5. Memory — laptop (live, auto-loads every session)

`C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/`

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/MEMORY.md` | Memory Index | 2026-08-03 | unreviewed | git refs, run dirs, canon docs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_background_workers.md` | name: feedback-background-workers | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_commit_means_push.md` | name: commit-means-push | 2026-08-03 | unreviewed | git refs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_commit_style.md` | name: Commit message style (thesis repo) | 2026-08-03 | unreviewed | git refs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_final_audit_panel.md` | name: final-audit-panel | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_grounding.md` | name: Ground answers in current repo docs, not stale/git-archaeology | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_infer_context_like_a_human.md` | name: infer-context-like-a-human | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_judge_run_cost_math.md` | name: judge-run-cost-math | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_never_relaunch_expensive_runs.md` | name: never-relaunch-expensive-runs | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_orchestrator_mode.md` | name: feedback-orchestrator-mode | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_react_to_anger.md` | name: react-to-anger-dont-route-around-it | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_reusable_tools.md` | name: reusable-tools-not-custom-scripts | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_trust_revoked.md` | name: trust-revoked-explicit-instruction-only | 2026-08-03 | unreviewed | git refs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_user_concepts_are_canon.md` | name: user-concepts-are-canon-not-substitutes | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/feedback_visible_progress.md` | name: visible-progress-is-a-hard-requirement | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_adversarial_panel_verdicts.md` | name: v1-adversarial-panel-verdicts | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_agent_roster.md` | name: project-agent-roster | 2026-08-03 | unreviewed | run dirs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_audit_panel_2026_07_28.md` | name: audit-panel-2026-07-28 | 2026-08-03 | unreviewed | git refs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_benchmark_validity_caveats.md` | name: benchmark-validity-caveats | 2026-08-03 | unreviewed | git refs, run dirs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_combine_sweep_and_hybrid_results.md` | name: combine-sweep-and-hybrid-results | 2026-08-03 | unreviewed | git refs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_corroboration_probe_verdict.md` | name: corroboration-probe-verdict | 2026-08-03 | unreviewed | git refs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_curve_cut_experiment.md` | name: v1-curve-cut-experiment | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_gold100_results_and_judge.md` | name: gold100-results-and-judge | 2026-08-03 | unreviewed | git refs, run dirs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_headless_claude_models.md` | name: headless-claude-models | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_heldout100_generalization.md` | name: heldout100-generalization | 2026-08-03 | unreviewed | run dirs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_laptop_env_limits.md` | name: laptop-env-limits-no-graphify-broken-venv | 2026-08-03 | unreviewed | git refs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_source_of_truth.md` | name: Source of truth — djuret/monorepo branch + docs/ tree | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_terminology_canon.md` | name: project-terminology-canon | 2026-08-03 | unreviewed | run dirs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_v1_lineage_and_cost_delta.md` | name: v1-lineage-and-cost-delta | 2026-08-03 | unreviewed | none found |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_v1_machinery_fix_and_toggles.md` | name: v1-machinery-fix-and-toggles | 2026-08-03 | unreviewed | git refs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_v1_ordering_diagnosis.md` | name: v1-ordering-diagnosis | 2026-08-03 | unreviewed | git refs, run dirs |
| `C:/Users/jocke/.claude/projects/C--Coding-exjobbet-GRAG-Job/memory/project_v3_artefact_state_docs_missing.md` | name: v3-state-docs-location-onedrive | 2026-08-03 | unreviewed | none found |

## 6. Memory — desktop (copy under docs/canon/raw)

The live desktop memory directory sits on the other machine and is not reachable from here.
These 53 files are the copy taken 2026-08-03; a copy is what there is to review.

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `docs/canon/raw/desktop_memory/MEMORY.md` | Memory Index | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/ai-cost-boundary.md` | name: ai-cost-boundary | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/arms-share-only-corpus-and-generator.md` | name: arms-share-only-corpus-and-generator | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/artefact-pass2-design.md` | name: artefact-pass2-design | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/check-existing-before-adding.md` | name: check-existing-before-adding | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/code-readability-plain-naming.md` | name: code-readability-plain-naming | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/data-layout-storage-vs-working.md` | name: data-layout-storage-vs-working | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/delete-dont-preserve.md` | name: delete-dont-preserve | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/design-before-build.md` | name: design-before-build | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/design-hard-fields-before-tagging.md` | CONFIRMED as the carrier (2026-06-12) | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/docs-track-reality.md` | name: docs-track-reality | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/dual-dataset-eval-plan.md` | name: dual-dataset-eval-plan | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/eval-drop-llm-context-precision.md` | name: eval-drop-llm-context-precision | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/facet-semantic-framework.md` | The four load-bearing frameworks | 2026-08-03 | unreviewed | git refs |
| `docs/canon/raw/desktop_memory/feedback_dont_stop_for_benchmark_data.md` | name: feedback-dont-stop-for-benchmark-data | 2026-08-03 | unreviewed | git refs |
| `docs/canon/raw/desktop_memory/generator-is-neutral-pipe.md` | name: generator-is-neutral-pipe | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/gold-100-stratified-selection.md` | name: gold-100-stratified-selection | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/gold100-effective-n99.md` | name: gold100-effective-n99 | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/gold100-ported-to-v3.md` | name: gold100-ported-to-v3 | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/graph-is-references-not-copies.md` | The model | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/heed-user-intent-not-correct-it.md` | name: heed-user-intent-not-correct-it | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/herb-eval-arm.md` | name: herb-eval-arm | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/herb-eval-is-the-artefact.md` | name: herb-eval-is-the-artefact | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/lock-concept-language.md` | name: lock-concept-language | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/match-output-to-the-ask.md` | name: match-output-to-the-ask | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/memory-is-downstream-of-conversation.md` | name: memory-is-downstream-of-conversation | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/neo4j-data-location.md` | name: neo4j-data-location | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/nim-judge-min-tokens.md` | name: nim-judge-min-tokens | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/no-claude-attribution.md` | name: no-claude-attribution | 2026-08-03 | unreviewed | git refs |
| `docs/canon/raw/desktop_memory/no-cost-estimates.md` | name: no-cost-estimates | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/no-cutting-corners.md` | name: no-cutting-corners | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/no-fabricated-offline-checks.md` | name: no-fabricated-offline-checks | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/no-historical-or-defensive-comments.md` | name: no-historical-or-defensive-comments | 2026-08-03 | unreviewed | git refs |
| `docs/canon/raw/desktop_memory/no-silent-fallbacks.md` | name: no-silent-fallbacks | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/nvidia-llm-host.md` | Terms (verify against the dashboard — they change) | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/project_overview.md` | name: project-overview | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/prompts-are-context-reconcile-first.md` | name: prompts-are-context-reconcile-first | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/ragas-canonical-sources.md` | name: ragas-canonical-sources | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/retag-facet-analysis.md` | v1 tagger design ([backend/tagging/pipeline.py](../../../../../exjobbet/repo/backend/tagging/pipeline.py)) | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/retriever-routing-model.md` | The graph it routes over — REVISED (2026-06-11/12) | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/state-handoff-utmost-care.md` | name: state-handoff-utmost-care | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/tag-facets-vs-routing.md` | name: tag-facets-vs-routing | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/tagger-build-validation.md` | Related | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/thesis-is-done.md` | name: thesis-is-done | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/use-established-eval-libraries.md` | name: use-established-eval-libraries | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/user-owns-execution.md` | name: user-owns-execution | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/v2-chunking-model.md` | Decisions | 2026-08-03 | unreviewed | git refs |
| `docs/canon/raw/desktop_memory/v2-graph-spine.md` | name: v2-graph-spine | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/v2-mapping-key.md` | name: v2-mapping-key | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/v3-arm-model-stack.md` | name: v3-arm-model-stack | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/v3-artefact-subsystem.md` | name: v3-artefact-subsystem | 2026-08-03 | unreviewed | none found |
| `docs/canon/raw/desktop_memory/v3-question-id-scheme.md` | name: v3-question-id-scheme | 2026-08-03 | unreviewed | run dirs |
| `docs/canon/raw/desktop_memory/verify-before-asserting.md` | name: verify-before-asserting | 2026-08-03 | unreviewed | none found |

## 7. Memory — laptop copy under docs/canon/raw

Snapshot of section 5 taken 2026-08-03. Review the live files; these are listed so the pile is
complete and so drift between copy and live stays visible.

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `docs/canon/raw/laptop_memory/MEMORY.md` | Memory Index | 2026-07-30 | unreviewed | git refs, run dirs |
| `docs/canon/raw/laptop_memory/feedback_background_workers.md` | name: feedback-background-workers | 2026-07-30 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/feedback_commit_means_push.md` | name: commit-means-push | 2026-07-23 | unreviewed | git refs |
| `docs/canon/raw/laptop_memory/feedback_commit_style.md` | name: Commit message style (thesis repo) | 2026-05-17 | unreviewed | git refs |
| `docs/canon/raw/laptop_memory/feedback_final_audit_panel.md` | name: final-audit-panel | 2026-07-27 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/feedback_grounding.md` | name: Ground answers in current repo docs, not stale/git-archaeology | 2026-05-18 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/feedback_infer_context_like_a_human.md` | name: infer-context-like-a-human | 2026-07-16 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/feedback_judge_run_cost_math.md` | name: judge-run-cost-math | 2026-07-18 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/feedback_never_relaunch_expensive_runs.md` | name: never-relaunch-expensive-runs | 2026-07-24 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/feedback_orchestrator_mode.md` | name: feedback-orchestrator-mode | 2026-07-22 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/feedback_react_to_anger.md` | name: react-to-anger-dont-route-around-it | 2026-07-21 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/feedback_reusable_tools.md` | name: reusable-tools-not-custom-scripts | 2026-07-17 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/feedback_trust_revoked.md` | name: trust-revoked-explicit-instruction-only | 2026-07-16 | unreviewed | git refs |
| `docs/canon/raw/laptop_memory/feedback_user_concepts_are_canon.md` | name: user-concepts-are-canon-not-substitutes | 2026-07-21 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/feedback_visible_progress.md` | name: visible-progress-is-a-hard-requirement | 2026-07-16 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/project_adversarial_panel_verdicts.md` | name: v1-adversarial-panel-verdicts | 2026-07-22 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/project_agent_roster.md` | name: project-agent-roster | 2026-07-22 | unreviewed | run dirs |
| `docs/canon/raw/laptop_memory/project_audit_panel_2026_07_28.md` | name: audit-panel-2026-07-28 | 2026-07-28 | unreviewed | git refs |
| `docs/canon/raw/laptop_memory/project_benchmark_validity_caveats.md` | name: benchmark-validity-caveats | 2026-07-20 | unreviewed | git refs, run dirs |
| `docs/canon/raw/laptop_memory/project_combine_sweep_and_hybrid_results.md` | name: combine-sweep-and-hybrid-results | 2026-07-23 | unreviewed | git refs |
| `docs/canon/raw/laptop_memory/project_corroboration_probe_verdict.md` | name: corroboration-probe-verdict | 2026-07-29 | unreviewed | git refs |
| `docs/canon/raw/laptop_memory/project_curve_cut_experiment.md` | name: v1-curve-cut-experiment | 2026-07-22 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/project_gold100_results_and_judge.md` | name: gold100-results-and-judge | 2026-07-21 | unreviewed | git refs, run dirs |
| `docs/canon/raw/laptop_memory/project_headless_claude_models.md` | name: headless-claude-models | 2026-07-19 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/project_heldout100_generalization.md` | name: heldout100-generalization | 2026-07-30 | unreviewed | run dirs |
| `docs/canon/raw/laptop_memory/project_laptop_env_limits.md` | name: laptop-env-limits-no-graphify-broken-venv | 2026-07-21 | unreviewed | git refs |
| `docs/canon/raw/laptop_memory/project_source_of_truth.md` | name: Source of truth — djuret/monorepo branch + docs/ tree | 2026-05-18 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/project_terminology_canon.md` | name: project-terminology-canon | 2026-07-21 | unreviewed | run dirs |
| `docs/canon/raw/laptop_memory/project_v1_lineage_and_cost_delta.md` | name: v1-lineage-and-cost-delta | 2026-07-27 | unreviewed | none found |
| `docs/canon/raw/laptop_memory/project_v1_machinery_fix_and_toggles.md` | name: v1-machinery-fix-and-toggles | 2026-07-23 | unreviewed | git refs |
| `docs/canon/raw/laptop_memory/project_v1_ordering_diagnosis.md` | name: v1-ordering-diagnosis | 2026-07-22 | unreviewed | git refs, run dirs |
| `docs/canon/raw/laptop_memory/project_v3_artefact_state_docs_missing.md` | name: v3-state-docs-location-onedrive | 2026-07-27 | unreviewed | none found |

## 8. Agent definitions

`.claude/agents/` is gitignored, so these travel with the machine rather than the repo. They are
the surface that turns a written claim into an enforced rule.

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `.claude/agents/code-optimizer.md` | Role | 2026-08-03 | unreviewed | run dirs, canon docs |
| `.claude/agents/critical-reviewer.md` | Role | 2026-08-03 | unreviewed | run dirs, canon docs |
| `.claude/agents/eval-statistician.md` | Role | 2026-08-03 | unreviewed | run dirs, canon docs |
| `.claude/agents/graph-refresher.md` | Role | 2026-08-03 | unreviewed | canon docs |
| `.claude/agents/logician.md` | Role | 2026-08-03 | unreviewed | run dirs, canon docs |
| `.claude/agents/maths-algorithmist.md` | Role | 2026-08-03 | unreviewed | run dirs, canon docs |
| `.claude/agents/order-of-operations.md` | Role | 2026-08-03 | unreviewed | run dirs, canon docs |
| `.claude/agents/results-analyst.md` | Role | 2026-08-03 | unreviewed | run dirs, canon docs |
| `.claude/agents/retrieval-scientist.md` | Role | 2026-08-03 | unreviewed | run dirs, canon docs |
| `.claude/agents/v3-coder.md` | Role | 2026-08-03 | unreviewed | canon docs |

## 9. Other agent-written material in the tree

| File | What it claims to be | Last written | Status | Evidence pointers found |
|---|---|---|---|---|
| `docs/research/2026-06-27-facet-derivation-methods.md` | Facet-Derivation Methods — Reference Survey | 2026-06-28 | unreviewed | none found |
| `graphify-out/REFRESH.md` | Keeping the knowledge graph current | 2026-06-28 | unreviewed | none found |
| `graphify-out/GRAPH_REPORT.md` | Graph Report - .  (2026-08-01) | 2026-08-01 | unreviewed | git refs, run dirs |

## 10. Legacy worktrees

`.claude/worktrees/` holds two checkouts of the pre-v3 project, each with its own agent-written
doc set — AGENTS.md files, backend/frontend docs, prompts, memory files, a quarantine notice.
Agent-written and unreviewed like everything else, but describing a superseded build. Full paths,
non-vendor only:

- `.claude/worktrees/flamboyant-buck-4586c0/AGENTS.md` — Agents (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/README.md` — Exjobbet Monorepo (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/AGENTS.md` — Agents (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/README.md` — Documentation (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/docs/README.md` — Docs Index (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/docs/agent_brief.md` — Agent Brief (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/docs/architecture.md` — Architecture (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/docs/codebase_map.md` — Codebase Map (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/docs/env_and_config.md` — Environment and Configuration (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/docs/graph_schema.md` — Graph Schema (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/docs/prompts.md` — Prompts (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/docs/runbook.md` — Runbook (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/docs/status.md` — Status (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/prompts/extract_chunk.md` — Chunk Extraction Agent (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/backend/prompts/file_descriptor.md` — File Orchestrator Agent (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/frontend/AGENTS.md` — AGENTS.md — Onboarding for AI Models (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/frontend/README.md` — Antigrav Interface (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/frontend/docs/README.md` — Artifact Pipeline Workbench — Documentation Index (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/frontend/docs/api.md` — API Contract (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/frontend/docs/architecture.md` — Architecture (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/frontend/docs/plans.md` — Plans — Next Steps & Improvements (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/frontend/docs/requirements.md` — Requirements, Decisions & Design Rationale (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/frontend/docs/status.md` — Status — What Is Built, Mocked, and Missing (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/graph_export/README.md` — Graph export (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/memory/MEMORY.md` — - [Active development branch + live frontend layout](project_active_branch.md) — (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/memory/project_active_branch.md` — name: Active development branch and frontend layout (last written 2026-05-17)
- `.claude/worktrees/flamboyant-buck-4586c0/memory/project_architecture.md` — Reality (last written 2026-05-17)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/AGENTS.md` — Agents (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/README.md` — Thesis monorepo (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/backend/AGENTS.md` — Backend agents (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/backend/README.md` — Thesis indexing pipeline (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/backend/data/tagging_runs/pilot_001/HANDOFF.md` — HERB Semantic Tagging Pilot — Handoff (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/backend/data/tagging_runs/pilot_001/analysis.md` — HERB Tagging Pilot — `pilot_001` (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/backend/prompts/extract_chunk.md` — Chunk Extraction Agent (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/backend/prompts/extract_chunk_tags_only.md` — Chunk Keyword Extractor (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/backend/prompts/file_descriptor.md` — File Orchestrator Agent (last written 2026-05-15)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/README.md` — Documentation (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/backend/architecture.md` — Architecture (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/backend/codebase_map.md` — Codebase Map (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/backend/env_and_config.md` — Environment and Configuration (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/backend/herb_tagging_frames.md` — HERB Tagging Frames (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/backend/herb_tagging_schema.md` — HERB Tagging Schema (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/backend/pilot_full_herb_report.md` — pilot_full_herb — Methodology and Results (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/backend/prompts.md` — Prompts (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/backend/runbook.md` — Runbook (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/backend/status.md` — Status (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/frontend/architecture.md` — Architecture (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/frontend/plans.md` — Plans — Next Steps (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/frontend/query_interpretation_layer.md` — Prompt Interpretation Method (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/frontend/status.md` — Status — Built vs Planned (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/graph_schema.md` — Graph Schema (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/docs/system_map.md` — System map (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/frontend/AGENTS.md` — Frontend agents (last written 2026-05-17)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/frontend/README.md` — Antigrav Interface (last written 2026-05-17)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/graph_export/README.md` — Graph export (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/quarantine/DO_NOT_READ_UNLESS_LEGACY.md` — Legacy stack — do not read unless explicitly requested (last written 2026-05-18)
- `.claude/worktrees/hardcore-engelbart-ea5bc5/quarantine/README.md` — Quarantine (last written 2026-05-18)

## 11. What this register does not cover

Stated rather than omitted, because the pile has to be complete to be a worklist:

- **`docs/handoff/` is empty.** `CLAUDE.md` points at it as "frozen historical handoffs"; this
  working tree holds zero files there. Either they were never created on this machine or they
  live somewhere not found. Unresolved.
- **The live desktop memory directory** is on the other machine; section 6 lists the copy.
- **`v3/data/raw/Salesforce__HERB/README.md`** exists and is presumed dataset-provided rather
  than agent-written. It was not opened — it sits inside the data quarantine — so that
  presumption is unverified.
- **Git history and commit messages** are agent-written in places too. They are not enumerated
  here; `docs/canon/raw/git_record.md` is the closest thing to an index of them.
- **Claude Code transcripts** under `~/.claude/projects/*/` are the source the corpus was
  extracted from, not documents to review. Other projects' memory directories on this machine
  (ARC, Neural-Nursery, New-Mem-Order) are outside this project.
- **`v3/` source code and its comments** carry agent-written claims as well. Not enumerated.
- **Counts.** 5 canon documents + this register, 6 raw records, 6 corpus files, 2 root docs,
  5 v3 docs, 5 in-repo state docs, 11 OneDrive state docs, 32 live laptop memory files,
  53 desktop memory copies, 32 laptop memory copies, 10 agent definitions, 3 other tree docs,
  57 legacy worktree docs.
