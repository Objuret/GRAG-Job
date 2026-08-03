---
name: memory-is-downstream-of-conversation
description: "Memory files are snapshots, not authority — the live conversation is source of truth and overrides any stored memory"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9a32f7a1-4794-4c83-a79e-bacf02c56af1
---

Memory is a downstream snapshot of what the user said at some past point. The **live conversation is the source of truth**. If something the user says now conflicts with a memory, the conversation wins. The memory needs updating, not the other way around.

**Why:** The user is iterating on a design and his thinking moves. A memory written two days ago reflects two-days-ago thinking — load-bearing then, possibly stale now. Treating memory as authoritative over the live conversation flips the directionality and produces stale or wrong work. The user has been explicit: "the data flows from here to the files."

**How to apply:**

- When the user contradicts a memory in conversation, **don't argue with them from the memory.** Update the memory.
- When recalling a memory before acting, treat it as "here's what was true when this was written" — verify it's still true if the action depends on it, especially for design decisions and project state.
- Don't quote memory back to the user as the reason for doing or not doing something. Quote what they said *in conversation* and use the memory as background.
- When the conversation establishes a new fact or decision that supersedes a memory, **update the memory in the same turn**, not later.

Related: [[verify-before-asserting]] — same spirit applied to live system state. [[docs-track-reality]] — same spirit applied to documentation.
