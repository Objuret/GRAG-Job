---
name: user-owns-execution
description: "The user runs scripts and owns progress/output; I prepare and hand off the command, never background-run on their behalf"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0c5b602c-5471-4156-8834-cbec1452d659
---

The user must be the one running things — in their own active terminal, watching live progress — because they own the content and the progress.

**Why:** background / "shadow" runs I kick off are invisible to them and strip their ownership; the whole reason the work is scripts is so THEY execute and follow them. A run they can't see "may or may not be happening."

**How to apply:** never run the smoke / eval / builds in the background for the user. Finish the code, then hand them the exact command to run. Make runs followable — emit live progress (a counter / pips) to stdout so the terminal shows movement.

Links: [[no-fabricated-offline-checks]] [[heed-user-intent-not-correct-it]] [[dont-over-engineer-stop-and-talk]]
