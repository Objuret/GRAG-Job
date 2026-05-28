# Thesis documentation (repo truth + PDF corrections)

Documents produced from code-verified analysis of this monorepo and comparison with **Thesis2026VT.pdf**. Documentation in `docs/backend/` and root `README.md` may be stale; **trust these after cross-checking code**.

## Start here — Word paste (pick one)

| Document | Open when… |
|----------|------------|
| [**Thesis2026VT9_submission_pack.md**](Thesis2026VT9_submission_pack.md) | You want **structured paste blocks** with *WHERE IN WORD* labels and a 7-step quick start (recommended). |
| [**Thesis2026VT9_WORD_PASTE.txt**](Thesis2026VT9_WORD_PASTE.txt) | You want **plain text only** — same paste content, no markdown (Notepad / Word). |
| [**Thesis2026VT9_missing_references_APA7.md**](Thesis2026VT9_missing_references_APA7.md) | You need **APA 7 reference lines** — one entry per section, alphabetical. |

## Deep analysis

| Document | Use when you need… |
|----------|-------------------|
| [**repo_truth_comprehensive.md**](repo_truth_comprehensive.md) | **Full codebase analysis** — architecture, backend, frontend, retrieval, eval, legacy, ops commands, doc truth table (~20 sections) |
| [**thesis_pdf_vs_reality.md**](thesis_pdf_vs_reality.md) | **Full thesis vs repo comparison** — every major error marked [FEL]/[MISSVISANDE], three baselines, Ch.1–9 catalog |
| [**Thesis2026VT_korrigeringar.md**](Thesis2026VT_korrigeringar.md) | **Swedish replacement text** + `[N_GOLD]` / `[MEDIAN_*]` placeholders for kap. 7 |
| [**Thesis2026VT_kap6_ersattningstext.md**](Thesis2026VT_kap6_ersattningstext.md) | **Copy-paste chapter 6** into Word (Swedish) |
| [**Thesis2026VT_corrections_EN.md**](Thesis2026VT_corrections_EN.md) | **English parallel** for supervisor / abstract |

## Recommended workflow

1. Open **`Thesis2026VT9_submission_pack.md`** (or **`Thesis2026VT9_WORD_PASTE.txt`** if you prefer plain text) — follow the 7-step quick start.  
2. Paste references from **`Thesis2026VT9_missing_references_APA7.md`**; fix Chakraborty/Pan in-text per that doc.  
3. Paste `Thesis2026VT_kap6_ersattningstext.md` into chapter 6 if not already done.  
4. Use `thesis_pdf_vs_reality.md` for any remaining flagged sections outside the pack.  
5. Optional: re-run k=40 RAGAS and swap table values from `*_k40.report.json` when available.

## Source PDF

`Thesis2026VT.pdf` (user path: OneDrive EXAMENSARBETET/thesis workbench/) — not stored in git.

## Related repo docs (operational)

- [`../backend/status.md`](../backend/status.md) — what works, verified dates  
- [`../backend/ragas_eval_report.md`](../backend/ragas_eval_report.md) — gold-100 pilot notes  
- [`../backend/pilot_full_herb_report.md`](../backend/pilot_full_herb_report.md) — tagging run report  
- [`../graph_schema.md`](../graph_schema.md) — Neo4j contract  
