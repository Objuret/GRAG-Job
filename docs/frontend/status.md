# Status — Built vs Planned

**Active UI:** `src/App.jsx`.

---

## Built

- [x] Two-lane canvas (pipeline + usage) + Clusters → Graph Query bridge  
- [x] Catalog (Pipeline / Usage), inspector forms per node kind, edge drawer, bottom lane comparison  
- [x] Demo lane results via `PRESET_RESULTS` + `SAMPLE_CHUNKS` in `workbenchData.ts`  
- [x] Themes and CSS tokens (`index.css`)
- [x] Query modules with chained `topic`, `entities`, `activity`, `temporal`, and `evidence` fragments
- [x] Undo/redo and clipboard support for canvas editing

---

## Not wired

- [ ] Browser-direct Neo4j read via `neo4j-driver` (replaces demo dataset/file/chunk/tag reads)
- [ ] Browser-direct Anthropic interpretation via `@anthropic-ai/sdk` (two-pass: handles → 5-facet → derived `w_query`)
- [ ] Cypher retrieval scoring per the deterministic weighted-overlap formula
- [ ] Answer call (Anthropic) over retrieved chunks per `answer_job` mode
- [ ] Field-name pass: drop legacy `cluster`/`canonicalId`/`weightLocal` for HERB
- [ ] Persisting canvas/module state across browser sessions

See [`plans.md`](plans.md) for the order, and the spec for interpretation/retrieval at [`query_interpretation_layer.md`](query_interpretation_layer.md).

---

## Inactive / Legacy

- `frontend/updated/` — tracked static prototype files. They are not imported by `src/main.tsx`; the active app is `src/App.jsx`.
