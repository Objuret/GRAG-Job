---
name: no-silent-fallbacks
description: "User strongly rejects silent fallbacks/degradation paths — treat them as bloat, fail loud instead"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 40b65c6e-ba7a-48c9-9af0-b3c408dfd092
---

The user strongly rejects silent fallback / graceful-degradation code paths. On the
exact-name retrieval fallback they said: "I REALLY dont want silent fallback to
exact name matching, that is actual shit, why are there even fallback garbage,
that just means there is bloat."

**Why:** Reinforces the [[project-overview]] rule "no fallback providers, no
mocks — fail loud." A degraded path that still "works" hides a broken graph and
adds maintenance surface. The user wants brokenness to be visible immediately.

**How to apply:** When something is missing/unavailable (missing index,
embeddings, key, provider), raise a loud, actionable error naming the fix —
never quietly substitute a weaker mechanism. Don't add `try/catch → weaker
path`, `coalesce(x, default)` substitutes for real data, or "legacy"
compatibility options unless explicitly asked. Removing such bloat is welcome.
