# Thesis documentation (repo truth + PDF corrections)

Documents produced from code-verified analysis of this monorepo and comparison with **Thesis2026VT.pdf**. Documentation in `docs/backend/` and root `README.md` may be stale; **trust these after cross-checking code**.

## Start here

| Document | Use when you need… |
|----------|-------------------|
| [**repo_truth_comprehensive.md**](repo_truth_comprehensive.md) | **Full codebase analysis** — architecture, backend, frontend, retrieval, eval, legacy, ops commands, doc truth table (~20 sections) |
| [**thesis_pdf_vs_reality.md**](thesis_pdf_vs_reality.md) | **Full thesis vs repo comparison** — every major error marked [FEL]/[MISSVISANDE], three baselines, Ch.1–9 catalog |
| [**Thesis2026VT_korrigeringar.md**](Thesis2026VT_korrigeringar.md) | **Swedish replacement text** + `[N_GOLD]` / `[MEDIAN_*]` placeholders for kap. 7 |
| [**Thesis2026VT_kap6_ersattningstext.md**](Thesis2026VT_kap6_ersattningstext.md) | **Copy-paste chapter 6** into Word (Swedish) |
| [**Thesis2026VT_corrections_EN.md**](Thesis2026VT_corrections_EN.md) | **English parallel** for supervisor / abstract |

## Recommended workflow

1. Read `repo_truth_comprehensive.md` once — understand what you actually built.  
2. Use `thesis_pdf_vs_reality.md` while editing the PDF — fix or replace flagged sections.  
3. Paste `Thesis2026VT_kap6_ersattningstext.md` into chapter 6.  
4. Copy filled values from `Thesis2026VT_korrigeringar.md` § *Ifyllda värden* (2026-05-20) into Word; reports stay in `ragas_exports/` (gitignored).  
5. Replace speculative chapter 7–8 narrative with evidence-based text from `ragas_eval_report.md`.

## Source PDF

`Thesis2026VT.pdf` (user path: OneDrive EXAMENSARBETET/thesis workbench/) — not stored in git.

## Related repo docs (operational)

- [`../backend/status.md`](../backend/status.md) — what works, verified dates  
- [`../backend/ragas_eval_report.md`](../backend/ragas_eval_report.md) — gold-100 pilot notes  
- [`../backend/pilot_full_herb_report.md`](../backend/pilot_full_herb_report.md) — tagging run report  
- [`../graph_schema.md`](../graph_schema.md) — Neo4j contract  
