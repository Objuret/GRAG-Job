# Status — Built vs Planned

**Active UI:** `src/App.jsx`.

---

## Built

- [x] Two-lane canvas (pipeline + usage) + Clusters → Graph Query bridge  
- [x] Catalog (Pipeline / Usage), inspector forms per node kind, edge drawer, bottom lane comparison  
- [x] Demo lane results via `PRESET_RESULTS` + `SAMPLE_CHUNKS` in `workbenchData.ts`  
- [x] Themes and CSS tokens (`index.css`)

---

## Not wired

- [ ] HTTP API to Neo4j / retrieval (`docs/api.md`)  
- [ ] Typed client under `src/api/`  
- [ ] Replacing demo text with live graph counts and LLM output  

---

## Removed (cleanup)

- `mockClient.ts` — fake delayed API; unused by `App.jsx`  
- `components/` + `WorkspaceContext` — alternate TS layout never imported by `main.tsx`  
