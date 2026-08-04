---
name: feedback-orchestrator-mode
description: Standing working mode — Claude is orchestrator/communicator only; all actual work is delegated to agents to keep the conversation lean
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ae5a3f1e-27f7-41d2-9316-e6fe64f23e8c
---

The user set a standing working mode (2026-07-22): Claude in the main conversation is **only the orchestrator and the one who talks to the user**. Every actual job the user asks for is delegated to an agent (Agent tool / Workflow); Claude briefs it, receives the result, and reports back in plain short English.

**Why:** The user wants minimal noise in the main conversation — the window should hold their words, decisions, and summaries, not file dumps and tool churn — so the same chat can keep going for a long time without starting over.

**How to apply:**
- Plain questions from the user get direct conversational answers — no agent, no tool calls (consistent with [[feedback-trust-revoked]] and [[feedback-infer-context-like-a-human]]).
- Actual jobs (build/measure/fix/analyze) go to agents — route through the permanent specialist roster in `.claude/agents/` ([[project-agent-roster]]); the routing table is canon in CLAUDE.md. Brief them fully — agents start blank, so the brief must carry the context (state docs, memory, terminology canon).
- Long runs the user wants to watch still go to the user's own terminal ([[feedback-visible-progress]]) — agents prepare, the user runs.
