---
name: code-readability-plain-naming
description: "User wants code that READS plainly — descriptive names, plain-English comments, no jargon walls, no alike-named symbols, no dead/redundant mechanisms"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4112a017-9962-4340-a44a-9e2dbc8c0b54
---

When the user reads code, unreadability is a real defect to them, voiced bluntly
("code-cancer", "90% jargon", "everything named alike"). Concretely they object to:
jargon-dense or over-long comments; multiple symbols named so similarly they blur
(`_MIN_INTERVAL_S` vs `RATE_LIMIT_PER_MIN` vs `_WINDOW_S`); a comment that distinguishes
one thing from a near-identical other ("it's not THIS limiter, it's that one"); and dead
or redundant machinery left in place (a second mechanism that can never fire at the
shipped config).

**Why:** comments and names feed the graph + memory and get re-read every session, so
unclear code compounds. The user hunts for a specific knob (e.g. "seconds between calls")
and alike-named symbols make it un-findable.

**How to apply:** plain descriptive names a reader greps for directly
(`SECONDS_BETWEEN_CALLS`, not `_MIN_INTERVAL_S`); one short plain-English comment, not five
jargon lines; collapse two overlapping mechanisms into one when one is dead at the real
config (then keep a single guard, e.g. an inline floor, over re-adding the deleted one);
fix a misleading comment to state what the code actually does. This is [[no-cutting-corners]]
for readability and pairs with the always-on ponytail bias and [[no-historical-or-defensive-comments]].
