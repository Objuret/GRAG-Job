---
trigger: always_on
---

The shipped workbench is **`src/App.jsx`** — two lanes (pipeline vs usage) plus a **Clusters → Graph Query** bridge.

Use synthetic labels in **`src/data/workbenchData.ts`** only; no credentials or machine paths.

When Neo4j queries exist, add **`src/api/client.ts`** and shrink demo-only fields — see **`docs/api.md`**.

Do not reintroduce a fake delayed API layer; call real HTTP or keep UI-local demo state only.
