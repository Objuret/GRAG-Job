---
trigger: always_on
---

Build a frontend-only local workbench prototype for a layered thesis artifact pipeline.

The app must be self-contained and run entirely from synthetic mock data. Use generic labels only. Do not include machine-specific paths, real run IDs, real credentials, real repository names, or real dataset names.

The purpose is to design a future-ready interface architecture:
- typed node registry
- typed API contracts
- mock API client
- adapter-ready execution model
- explicit layer/run validity states
- artifact inspection
- completed-run comparison
- workspace persistence

The UI must be honest about capability:
- runnable
- inspectable only
- unavailable
- invalid
- not materialized yet

Do not present unavailable or invalid layers as runnable.
