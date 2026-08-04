---
name: feedback-background-workers
description: "Always dispatch agents in the background (run_in_background true), never foreground — blocking the chat reads as hijacking and \"taking forever\""
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f6cb7de7-a772-4efd-8957-cc4d456d2cc8
  modified: 2026-07-29T22:49:12.363Z
---

Dispatch every agent/worker in the background (`run_in_background: true`) and let the completion notification bring the result. Never run an agent in the foreground — it freezes the conversation until the agent finishes.

**Why:** Foreground (synchronous) agent runs block the chat; the user cannot talk and experiences it as the assistant "hijacking my conversation with infinitywork" and it "taking actually forever." This happened repeatedly on 2026-07-30 and made the user furious.

**How to apply:** Fire the worker in the background, say in one short line what it's doing, and keep the conversation responsive. Report when the notification lands. Also keep the volume down — see [[feedback_orchestrator_mode]] and [[feedback_react_to_anger]]; do not chain multiple agents for small asks.
