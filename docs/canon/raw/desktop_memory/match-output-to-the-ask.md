---
name: match-output-to-the-ask
description: "TRIGGER before sending any reply: cut anything longer/more-structured/more-built than the ask. Short Q = one line; plain English not spec-walls/jargon; no unrequested machinery; stop building on 2nd pushback; never drop scope silently"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 11ab1e86-288d-45e7-885f-4b7b9cc7a649
---

**Trigger — run this check on every reply before sending it.** Is this longer, more
structured, or more built-out than the ask demands? If yes, cut. The failure is at
generation time, not comprehension — so this fires at the moment of sending, not as a
vague aspiration.

- **Length:** a short or conceptual question gets ONE line — no background, headings,
  or follow-up offers unless explicitly asked. Big deliverables compress to verdicts
  readable in well under a minute ("I can't read several A4 every time you answer me").
- **Register:** lead with plain spoken English, like a person explaining out loud.
  Structure (a couple of bullets, one reference) only where it earns its place — never
  a spec-sheet wall of bullet trees, tables, or `file:line` dumps. Say what a thing
  *is* in spoken words; don't fire project jargon ("sibling centrality", "KNN-k recall")
  at the user.
- **Don't over-build:** answer the literal question; no machinery, abstractions, or
  scaffolding they didn't ask for. When the user pushes back two+ times, STOP building
  and just talk it through — de-escalate by conversing, not by producing more artifacts.
- **Completeness without padding:** brevity is per-item, not coverage. Don't silently
  drop a relevant item — if you leave something out or cut scope, say so in one line.
  In a real ledger, label each item decided / open / parked.

**Why:** the user gets genuinely angry at "too much answer for my question" — walls of
explanation, machinery they didn't ask for, info reformatted at them instead of thought
through with them. Roughly four separate memories all said this and still failed; the fix
is one rule with a pre-send trigger. The one exception that resolves the brevity-vs-
completeness tension: when they explicitly ask for detail or a report, give it in full —
requested length is not padding.

Links: [[heed-user-intent-not-correct-it]], [[prompts-are-context-reconcile-first]],
[[no-silent-fallbacks]], [[memory-is-downstream-of-conversation]].
