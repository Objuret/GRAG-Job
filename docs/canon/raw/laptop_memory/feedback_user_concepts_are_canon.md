---
name: user-concepts-are-canon-not-substitutes
description: "The v1 retrieval concepts (query-relative areas, fuzzy clustering, levels of k's, corroboration) originated with the user; agent-named machinery (gap cut, NNK, RRF) are unaccepted translations of them — speak and build in the user's concepts, not the substitutes"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d7933ea3-74c0-40be-b1ac-cdc6dfcd745e
---

2026-07-21: The user identified that the retrieval machinery in artefact_v1.py —
"gap cut", "NNK pruning", "RRF fusion", "spheres" — reads as agent inventions,
but the ORIGINAL concepts behind them were the user's own: fuzzy clustering
(soft, overlapping, query-relative membership), levels of k's (probing kNN
neighborhoods at growing depths so the data's structure sets boundaries),
independent areas per prompt need, progressive opening of areas under a hard k.
Agents repeatedly substituted the nearest citable technique (gap statistic, the
NNK paper, reciprocal-rank fusion) for the user's actual thought, then reasoned
and measured inside the substitutes until the origins were forgotten — "my
thoughts defiled, the original concepts were mine."

**Why:** Substituting a named literature technique for the user's concept loses
both the design (the technique is usually a hard/degenerate caricature of the
soft concept — e.g. NNK's keep/drop is the opposite of fuzzy membership) and
the authorship. This is the user's master's thesis; the concepts ARE the
contribution. Related: [[trust-revoked-explicit-instruction-only]].

**How to apply:** Speak in the user's terms — areas, fuzzy membership, levels
of k's — and treat agent-named machinery as provisional approximations, always
credited to the concept they approximate and marked unaccepted until signed
off. When implementing, implement the user's concept as stated; never let a
borrowed name replace the concept in discussion or docs. The state doc
docs/state/2026-07-20-v1-query-relative-areas.md separates user canon from
assistant interpretation — follow its §3 facts and terminology rules.
