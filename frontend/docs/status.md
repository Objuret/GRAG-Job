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

- [ ] HTTP API to Neo4j / retrieval (`docs/api.md`)  
- [ ] Typed client under `src/api/`  
- [ ] Replacing demo text with live graph counts and LLM output  
- [ ] Persisting canvas/module state outside the current browser session

---

## Inactive / Legacy

- `frontend/updated/` — tracked static prototype files. They are not imported by `src/main.tsx`; the active app is `src/App.jsx`.
